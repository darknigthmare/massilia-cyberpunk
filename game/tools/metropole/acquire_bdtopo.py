#!/usr/bin/env python3
"""Explicit, bounded IGN BD TOPO building acquisition; never called by the game.

Example (from the repository root, optional GIS environment required):
  python game/tools/metropole/acquire_bdtopo.py --boundary boundary.geojson \
    --source-receipt ign-metadata.json --output /tmp/amp-bdtopo

The source receipt declares the vintage, licence, units, datum and the eaves
meaning of hauteur. Source pages remain unchanged. SQLite keeps full source
geometries intersecting the boundary, with per-page provenance. --resume verifies
configuration, page hashes and pagination before continuing a stopped run.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import threading
import urllib.parse
import urllib.request

ENDPOINT = 'https://data.geopf.fr/wfs/ows'
TYPE_NAME = 'BDTOPO_V3:batiment'
CRS = 'urn:ogc:def:crs:EPSG::2154'
FIELDS = {'ignId': 'cleabs', 'height': 'hauteur', 'groundAltitude': 'altitude_minimale_sol'}


class AcquisitionError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def read_json(path, maximum):
    path = Path(path)
    if path.stat().st_size > maximum:
        raise AcquisitionError('JSON byte budget exceeded.')
    try:
        return json.loads(path.read_text(encoding='utf-8'), parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    except (ValueError, UnicodeError) as error:
        raise AcquisitionError('Invalid JSON input.') from error


def save_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(path)


@dataclass(frozen=True)
class Limits:
    source_bytes: int = 1_500_000_000
    max_requests: int = 1000
    workers: int = 2
    step: int = 4000
    page_size: int = 5000
    page_bytes: int = 16 * 1024 * 1024
    max_pages_per_query: int = 32
    max_queries: int = 1000
    max_objects: int = 1_200_000
    timeout: int = 45

    def validate(self):
        if any(type(value) is not int or value <= 0 for value in asdict(self).values()):
            raise AcquisitionError('Budgets must be positive integers.')
        if self.source_bytes > 1_500_000_000 or self.workers > 2 or not 250 <= self.step <= 5000 or self.page_size > 5000 or self.page_bytes > 16*1024*1024 or self.max_requests > 1000 or self.max_queries > 1000 or self.max_pages_per_query > 32 or self.max_objects > 1_200_000 or self.timeout > 60:
            raise AcquisitionError('Acquisition safety budgets cannot be exceeded.')
        return self


def source_metadata(receipt):
    if not isinstance(receipt, dict):
        raise AcquisitionError('Declared IGN source receipt required.')
    required = ('provider', 'product', 'license', 'attribution', 'date', 'heightMeaning')
    if any(not isinstance(receipt.get(k), str) or not receipt[k].strip() or receipt[k].strip().lower() in {'unknown', 'inconnue', 'à déclarer'} for k in required):
        raise AcquisitionError('Source provider, product, licence, date and height meaning required.')
    try:
        date.fromisoformat(receipt['date'])
    except ValueError as error:
        raise AcquisitionError('Source vintage must be an ISO calendar date.') from error
    if receipt.get('crs') != 'EPSG:2154' or receipt.get('units') != 'm' or receipt.get('verticalDatum') != 'NGF-IGN69' or receipt.get('fields') != FIELDS:
        raise AcquisitionError('Declare WFS fields, EPSG:2154, m and NGF-IGN69 explicitly.')
    if receipt.get('heightKind', 'eaves') != 'eaves':
        raise AcquisitionError('The IGN hauteur field describes eaves, not a total roof height.')
    result = {k: receipt[k] for k in required + ('crs', 'units', 'verticalDatum', 'fields')}
    result.update(heightKind='eaves', independentSourceAuthenticityVerified=False)
    for key in ('sourceMetadataSHA256', 'sourceSpecificationSHA256'):
        value = receipt.get(key)
        if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
            raise AcquisitionError('Source metadata/specification SHA256 evidence required.')
        result[key] = value
    return result


def parse_page(raw, *, limit, expected=None, previous=None, seen=None):
    """Validate actual WFS counts/ordering; null CRS is allowed only when empty."""
    if not isinstance(raw, bytes) or len(raw) > limit.page_bytes:
        raise AcquisitionError('Response byte budget exceeded.')
    try:
        data = json.loads(raw, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    except (ValueError, UnicodeError) as error:
        raise AcquisitionError('WFS response is malformed JSON.') from error
    if not isinstance(data, dict) or data.get('type') != 'FeatureCollection' or not isinstance(data.get('features'), list):
        raise AcquisitionError('WFS FeatureCollection required.')
    features = data['features']
    crs = data.get('crs')
    if crs is not None and (not isinstance(crs, dict) or not isinstance(crs.get('properties'), dict)):
        raise AcquisitionError('Malformed response CRS.')
    crs_name = crs['properties'].get('name') if crs else None
    if (features and crs_name != CRS) or (not features and crs_name not in (None, CRS)):
        raise AcquisitionError('Wrong response CRS; nonempty responses require EPSG:2154.')
    matched, returned = data.get('numberMatched'), data.get('numberReturned')
    if type(matched) is not int or not 0 <= matched <= limit.page_size*limit.max_pages_per_query or type(returned) is not int or returned != len(features) or returned > limit.page_size:
        raise AcquisitionError('WFS response counts are invalid.')
    if expected is not None and matched != expected:
        raise AcquisitionError('Query count changed during pagination.')
    ids = []
    for feature in features:
        if not isinstance(feature, dict) or feature.get('type') != 'Feature' or not isinstance(feature.get('properties'), dict):
            raise AcquisitionError('Malformed source feature.')
        ident = feature['properties'].get('cleabs')
        if not isinstance(ident, str) or not ident:
            raise AcquisitionError('Stable IGN cleabs identity missing.')
        ids.append(ident)
    seen = seen or set()
    if ids != sorted(ids) or len(set(ids)) != len(ids) or (previous and ids and ids[0] <= previous) or any(i in seen for i in ids):
        raise AcquisitionError('Contradictory, repeated or unsorted pagination identities.')
    if len(seen)+len(ids) > matched or (not ids and len(seen) != matched):
        raise AcquisitionError('Missing or excessive pagination records.')
    return data


def insert_feature(db, feature, page_id, boundary):
    """Keep full source geometry; conflicting IDs fail rather than overwrite."""
    from shapely.geometry import shape
    ident = feature['properties']['cleabs']
    payload = canonical(feature)
    content_sha = hashlib.sha256(payload.encode()).hexdigest()
    old = db.execute('SELECT content_sha256 FROM objects WHERE ign_id=?', (ident,)).fetchone()
    if old and old[0] != content_sha:
        raise AcquisitionError('Conflicting source identity across query/page boundaries.')
    try:
        geometry = shape(feature['geometry'])
        if geometry.is_empty or not geometry.is_valid:
            raise ValueError('Invalid/empty source geometry; no repair applied.')
        if not boundary.intersects(geometry):
            return 'outside'
    except Exception as error:
        db.execute('INSERT OR IGNORE INTO quarantine VALUES(?,?,?,?)', (ident, page_id, content_sha, str(error)))
        return 'quarantined'
    if not old:
        db.execute('INSERT INTO objects VALUES(?,?,?,?,?,?,?,?,?)', (ident, content_sha, digest(feature['geometry']), payload, *geometry.bounds, 1))
    db.execute('INSERT OR IGNORE INTO object_pages VALUES(?,?)', (ident, page_id))
    return 'duplicate' if old else 'inserted'


def fetch_public(url, maximum, timeout):
    request = urllib.request.Request(url, headers={'User-Agent': 'MassiliaGeodata/0.69 (bounded public acquisition)', 'Accept': 'application/json'})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200 or urllib.parse.urlsplit(response.url).hostname != 'data.geopf.fr':
            raise AcquisitionError('Unexpected public service response or redirect.')
        raw = response.read(maximum+1)
        if len(raw) > maximum:
            raise AcquisitionError('Response byte budget exceeded.')
        return raw, {'status': response.status, 'contentType': response.headers.get('Content-Type')}


DDL = '''PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL;
CREATE TABLE objects(ign_id TEXT PRIMARY KEY,content_sha256 TEXT NOT NULL,geometry_sha256 TEXT NOT NULL,feature_json TEXT NOT NULL,min_x REAL,min_y REAL,max_x REAL,max_y REAL,geometry_valid INTEGER NOT NULL);
CREATE TABLE object_pages(ign_id TEXT,page_id TEXT,PRIMARY KEY(ign_id,page_id));
CREATE TABLE pages(page_id TEXT PRIMARY KEY,query_id TEXT,page_number INTEGER,sha256 TEXT,bytes INTEGER,matched INTEGER,returned INTEGER,receipt_path TEXT,receipt_sha256 TEXT);
CREATE TABLE queries(query_id TEXT PRIMARY KEY,bbox TEXT,matched INTEGER,returned INTEGER,page_count INTEGER,status TEXT);
CREATE TABLE quarantine(ign_id TEXT,page_id TEXT,content_sha256 TEXT,reason TEXT,PRIMARY KEY(ign_id,page_id));
CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);'''


def acquire(boundary_path, source_receipt_path, output, *, limits=None, resume=False, fetch=fetch_public, log=print):
    """Acquire explicitly, or resume only the same verified configuration."""
    from pyproj import Transformer
    from shapely.geometry import shape, box
    from shapely.ops import transform, unary_union
    from shapely.prepared import prep
    limits = (limits or Limits()).validate()
    boundary_path, source_receipt_path, output = map(Path, (boundary_path, source_receipt_path, output))
    source = source_metadata(read_json(source_receipt_path, 1024*1024))
    boundary_doc = read_json(boundary_path, 16*1024*1024)
    if not isinstance(boundary_doc, dict) or boundary_doc.get('type') != 'FeatureCollection' or len(boundary_doc.get('features', [])) != 1:
        raise AcquisitionError('Single validated administrative union required.')
    feature = boundary_doc['features'][0]
    if not isinstance(feature, dict) or not isinstance(feature.get('geometry'), dict):
        raise AcquisitionError('Administrative geometry is missing.')
    try:
        boundary = shape(feature['geometry'])
    except (ValueError, TypeError, KeyError) as error:
        raise AcquisitionError('Administrative geometry is malformed.') from error
    if boundary.is_empty or not boundary.is_valid:
        raise AcquisitionError('Invalid administrative boundary; no repairs applied.')
    boundary = transform(Transformer.from_crs('EPSG:4326', 'EPSG:2154', always_xy=True).transform, boundary)
    if not boundary.is_valid:
        raise AcquisitionError('Projected boundary is invalid.')
    prepared = prep(boundary)
    w, s, e, n = boundary.bounds
    if not (-500000 <= w < e <= 1500000 and 6000000 <= s < n <= 7300000):
        raise AcquisitionError('Boundary lies outside continental Lambert-93 domain.')
    queries = []
    if math.ceil((n-s)/limits.step)*math.ceil((e-w)/limits.step) > limits.max_queries*16:
        raise AcquisitionError('Administrative grid traversal budget exceeded.')
    for row in range(math.ceil((n-s)/limits.step)):
        for col in range(math.ceil((e-w)/limits.step)):
            bounds = [w+col*limits.step, s+row*limits.step, min(e, w+(col+1)*limits.step), min(n, s+(row+1)*limits.step)]
            if prepared.intersects(box(*bounds)):
                queries.append((f'q{row:03d}-{col:03d}', bounds))
                if len(queries) > limits.max_queries:
                    raise AcquisitionError('Administrative query-box budget exceeded.')
    if boundary.difference(unary_union([box(*b) for _, b in queries])).area > .0001:
        raise AcquisitionError('Query boxes leave a boundary coverage gap.')
    config = {'schema': 'soma-metropole/ign-wfs-config/1', 'endpoint': ENDPOINT, 'typeName': TYPE_NAME, 'limits': asdict(limits), 'boundarySHA256': file_sha(boundary_path), 'sourceReceiptSHA256': file_sha(source_receipt_path), 'sourceMetadata': source, 'queries': queries}
    config_sha = digest(config)
    if output.exists():
        if not resume:
            raise AcquisitionError('Output exists; use --resume to verify and continue it.')
        saved_config = read_json(output/'configuration.json', 16*1024*1024)
        if digest(saved_config) != config_sha:
            raise AcquisitionError('Resume source, boundary or budgets differ from saved configuration.')
    else:
        if resume:
            raise AcquisitionError('Resume directory does not exist.')
        output.mkdir(parents=True)
        (output/'pages').mkdir()
        (output/'boundary.geojson').write_bytes(boundary_path.read_bytes())
        save_json(output/'source-metadata.json', source)
        save_json(output/'configuration.json', config)
    lock_path = output/'acquisition.lock'
    if lock_path.exists():
        try:
            holder = int(lock_path.read_text())
            os.kill(holder, 0)
        except ProcessLookupError:
            if not resume:
                raise AcquisitionError('Stale acquisition lock requires --resume.')
            lock_path.unlink()
        except (ValueError, PermissionError) as error:
            raise AcquisitionError('Acquisition lock cannot safely be reclaimed.') from error
        else:
            raise AcquisitionError('Another acquisition process is active.')
    fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.write(fd, str(os.getpid()).encode()); os.close(fd)
    db = None
    try:
        database_path = output/'buildings.sqlite'
        existed = database_path.exists()
        db = sqlite3.connect(database_path, check_same_thread=False)
        if not existed:
            db.executescript(DDL)
            with db:
                db.executemany('INSERT INTO metadata VALUES(?,?)', [('configurationSHA256', config_sha), ('requests', '0'), ('startedAtUTC', utc())])
        if db.execute('SELECT value FROM metadata WHERE key=?', ('configurationSHA256',)).fetchone() != (config_sha,):
            raise AcquisitionError('SQLite configuration binding differs.')
        if file_sha(output/'boundary.geojson') != config['boundarySHA256'] or read_json(output/'source-metadata.json', 1024*1024) != source:
            raise AcquisitionError('Saved boundary/source metadata differs.')
        if db.execute('PRAGMA quick_check').fetchone() != ('ok',):
            raise AcquisitionError('SQLite integrity check failed.')
        # Validate persisted pages before issuing any resumed request.
        for page_id, query_id, number, sha, size, matched, returned, receipt_path, receipt_sha in db.execute('SELECT * FROM pages ORDER BY page_id'):
            path = output/'pages'/(page_id+'.geojson');receipt = output/receipt_path
            if not path.resolve().is_relative_to((output/'pages').resolve()) or not receipt.resolve().is_relative_to((output/'pages').resolve()):
                raise AcquisitionError('Saved page/receipt path escaped the acquisition directory.')
            if path.stat().st_size != size or file_sha(path) != sha or file_sha(receipt) != receipt_sha:
                raise AcquisitionError('Saved acquisition page/receipt checksum differs.')
        if (output/'source-index.json').exists():
            saved = read_json(output/'source-index.json', 16*1024*1024)
            if saved.get('configurationSHA256') != config_sha or saved.get('sqliteSHA256') != file_sha(database_path):
                raise AcquisitionError('Completed source index/database binding differs.')
            if saved.get('sourceSHA256') != digest({k:v for k,v in saved.items() if k not in ('sourceSHA256', 'sqliteSHA256', 'sqliteBytes')}):
                raise AcquisitionError('Completed source index checksum differs.')
            return saved
        mutex = threading.RLock(); stopped = threading.Event(); reserved = 0
        state = {'schema': 'soma-metropole/ign-wfs-progress/1', 'configurationSHA256': config_sha, 'startedAtUTC': db.execute('SELECT value FROM metadata WHERE key=?', ('startedAtUTC',)).fetchone()[0], 'status': 'running', 'queryBoxes': len(queries), 'sourceByteBudget': limits.source_bytes, 'maxConcurrentRequests': limits.workers}
        def checkpoint():
            state.update(updatedAtUTC=utc(), completedQueries=db.execute("SELECT count(*) FROM queries WHERE status='complete'").fetchone()[0], completedPages=db.execute('SELECT count(*) FROM pages').fetchone()[0], countUniqueIntersecting=db.execute('SELECT count(*) FROM objects').fetchone()[0], quarantinedObservations=db.execute('SELECT count(*) FROM quarantine').fetchone()[0], sourceBytes=sum(p.stat().st_size for p in (output/'pages').glob('*.geojson')), requests=int(db.execute("SELECT value FROM metadata WHERE key='requests'").fetchone()[0]))
            save_json(output/'progress.json', state)
        with mutex: checkpoint()
        def query(item):
            nonlocal reserved
            name, bounds = item
            with mutex:
                if db.execute("SELECT 1 FROM queries WHERE query_id=? AND status='complete'", (name,)).fetchone():
                    return
                old_pages = list(db.execute('SELECT page_number,matched FROM pages WHERE query_id=? ORDER BY page_number', (name,)))
            seen, previous, expected = set(), None, None
            for index, (number, _) in enumerate(old_pages):
                if number != index:
                    raise AcquisitionError('Saved pagination has a gap.')
                data = parse_page((output/'pages'/(name+f'-p{number:03d}.geojson')).read_bytes(), limit=limits, expected=expected, previous=previous, seen=seen)
                ids = [f['properties']['cleabs'] for f in data['features']]
                expected = data['numberMatched'];seen.update(ids);previous = ids[-1] if ids else previous
            page_number = len(old_pages)
            while expected is None or len(seen) < expected:
                if stopped.is_set():
                    raise AcquisitionError('Stopped after another query failed.')
                if page_number >= limits.max_pages_per_query:
                    raise AcquisitionError('Pagination budget exceeded.')
                params = {'SERVICE':'WFS', 'VERSION':'2.0.0', 'REQUEST':'GetFeature', 'TYPENAMES':TYPE_NAME, 'SRSNAME':'EPSG:2154', 'BBOX':','.join(map(str,bounds))+',EPSG:2154', 'COUNT':limits.page_size, 'STARTINDEX':page_number*limits.page_size, 'SORTBY':'cleabs', 'OUTPUTFORMAT':'application/json'}
                url = ENDPOINT+'?'+urllib.parse.urlencode(params)
                page_id = name+f'-p{page_number:03d}'
                page_path = output/'pages'/(page_id+'.geojson');receipt_path = output/'pages'/(page_id+'.receipt.json')
                # A crash may leave a fully saved page before its SQL commit.
                if page_path.exists() or receipt_path.exists():
                    if not page_path.exists() or not receipt_path.exists():
                        raise AcquisitionError('Incomplete orphan page: preserve it for inspection.')
                    receipt = read_json(receipt_path, 1024*1024);raw = page_path.read_bytes()
                    if receipt.get('requestedURL') != url or receipt.get('sha256') != hashlib.sha256(raw).hexdigest() or receipt.get('bytes') != len(raw):
                        raise AcquisitionError('Orphan page receipt/source differs.')
                else:
                    with mutex:
                        requests = int(db.execute("SELECT value FROM metadata WHERE key='requests'").fetchone()[0])
                        current_bytes = sum(p.stat().st_size for p in (output/'pages').glob('*.geojson'))
                        if requests >= limits.max_requests or current_bytes+reserved+limits.page_bytes > limits.source_bytes:
                            raise AcquisitionError('Request/source-byte budget reached; run remains incomplete.')
                        reserved += limits.page_bytes
                        with db: db.execute("UPDATE metadata SET value=? WHERE key='requests'", (str(requests+1),))
                    try:
                        started = utc();raw, http = fetch(url, limits.page_bytes, limits.timeout)
                        if http.get('status') != 200:
                            raise AcquisitionError('WFS HTTP status is not 200.')
                        data = parse_page(raw, limit=limits, expected=expected, previous=previous, seen=seen)
                        receipt = {'requestedURL':url, 'requestedAtUTC':started, 'completedAtUTC':utc(), 'tlsVerification':True, 'status':200, 'contentType':http.get('contentType'), 'bytes':len(raw), 'sha256':hashlib.sha256(raw).hexdigest(), 'numberMatched':data['numberMatched'], 'numberReturned':data['numberReturned'], 'timeStamp':data.get('timeStamp'), 'bboxL93':bounds, 'startIndex':page_number*limits.page_size, 'path':'pages/'+page_path.name}
                        page_path.write_bytes(raw);save_json(receipt_path, receipt)
                    finally:
                        with mutex: reserved -= limits.page_bytes
                data = parse_page(raw, limit=limits, expected=expected, previous=previous, seen=seen)
                ids = [f['properties']['cleabs'] for f in data['features']]
                with mutex:
                    with db:
                        for feature in data['features']:
                            insert_feature(db, feature, page_id, prepared)
                        if db.execute('SELECT count(*) FROM objects').fetchone()[0] > limits.max_objects:
                            raise AcquisitionError('Filtered object budget exceeded.')
                        db.execute('INSERT INTO pages VALUES(?,?,?,?,?,?,?,?,?)', (page_id,name,page_number,receipt['sha256'],len(raw),data['numberMatched'],len(ids),'pages/'+receipt_path.name,file_sha(receipt_path)))
                    checkpoint()
                expected = data['numberMatched'];seen.update(ids);previous = ids[-1] if ids else previous;page_number += 1
            with mutex:
                with db: db.execute('INSERT OR REPLACE INTO queries VALUES(?,?,?,?,?,?)', (name,canonical(bounds),expected,len(seen),page_number,'complete'))
                checkpoint();log(json.dumps({'query':name,'returned':len(seen),'pages':page_number,**state},ensure_ascii=False))
        try:
            with ThreadPoolExecutor(max_workers=limits.workers) as pool:
                futures = [pool.submit(query, item) for item in queries]
                for future in as_completed(futures):
                    try: future.result()
                    except BaseException:
                        stopped.set()
                        for pending in futures: pending.cancel()
                        raise
            with mutex: checkpoint()
            if state['completedQueries'] != len(queries):
                raise AcquisitionError('Incomplete administrative query traversal.')
            index_hash = hashlib.sha256()
            for ident, content_sha in db.execute('SELECT ign_id,content_sha256 FROM objects ORDER BY ign_id'):
                index_hash.update((canonical([ident,content_sha])+'\n').encode())
            pages = [dict(zip(('pageId','queryId','pageNumber','sha256','bytes','numberMatched','numberReturned','receiptPath','receiptSHA256'), row)) for row in db.execute('SELECT * FROM pages ORDER BY page_id')]
            receipt = {'schema':'soma-metropole/ign-bdtopo-source-index/1', **source, 'configurationSHA256':config_sha, 'boundaryPath':'boundary.geojson', 'boundarySHA256':config['boundarySHA256'], 'sourceMetadataPath':'source-metadata.json', 'sourceMetadataFileSHA256':file_sha(output/'source-metadata.json'), 'bboxL93':list(boundary.bounds), 'startedAtUTC':state['startedAtUTC'], 'completedAtUTC':utc(), 'queryBoxes':len(queries), 'pages':pages, 'uniqueIntersectingObjects':state['countUniqueIntersecting'], 'quarantinedObservations':state['quarantinedObservations'], 'sourceBytes':state['sourceBytes'], 'objectsIndexSHA256':index_hash.hexdigest(), 'geometriesClipped':False, 'queryAcquisitionComplete':True, 'sourceGeometryCoverageValidated':state['quarantinedObservations']==0, 'transactionSafe':False, 'matchingPerformed':False, 'runtimeIntegrationPerformed':False, 'completeMetropole':False, 'sourceSHA256Scheme':'Canonical JSON excluding sourceSHA256/sqliteSHA256/sqliteBytes; binds source pages and ordered object hashes.'}
            receipt['sourceSHA256'] = digest(receipt)
            with db: db.execute('INSERT INTO metadata VALUES(?,?)', ('sourceSHA256',receipt['sourceSHA256']))
            db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            receipt.update(sqliteSHA256=file_sha(database_path), sqliteBytes=database_path.stat().st_size)
            save_json(output/'source-index.json', receipt)
            state.update(status='complete', sourceSHA256=receipt['sourceSHA256']);save_json(output/'progress.json', state)
            return receipt
        except BaseException as error:
            with mutex:
                state.update(status='stopped-incomplete', error=str(error));checkpoint()
            raise
    finally:
        if db is not None: db.close()
        lock_path.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--boundary', type=Path, required=True, help='Official union FeatureCollection in WGS84')
    parser.add_argument('--source-receipt', type=Path, required=True, help='Declared vintage/licence/IGN69/eaves metadata JSON')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--source-budget', type=int, default=Limits.source_bytes)
    parser.add_argument('--max-requests', type=int, default=Limits.max_requests)
    parser.add_argument('--workers', type=int, default=Limits.workers)
    parser.add_argument('--step', type=int, default=Limits.step)
    args = parser.parse_args()
    try:
        result = acquire(args.boundary, args.source_receipt, args.output, limits=Limits(source_bytes=args.source_budget,max_requests=args.max_requests,workers=args.workers,step=args.step), resume=args.resume, log=lambda value: print(value,flush=True))
        print(json.dumps({k:result[k] for k in ('sourceSHA256','uniqueIntersectingObjects','sourceBytes','queryAcquisitionComplete','runtimeIntegrationPerformed')},ensure_ascii=False))
    except (OSError, ValueError, RuntimeError, sqlite3.Error, ImportError) as error:
        parser.exit(1, f'IGN acquisition stopped: {error}\n')


if __name__ == '__main__':
    main()
