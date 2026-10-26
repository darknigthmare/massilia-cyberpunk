"""Export verified bundled data as bounded assets; this adds no geographic coverage.

The optional PBF/GeoTIFF importers create new editions separately. This bootstrap
keeps the supplied edition reproducible with Python's standard library only.
"""
from __future__ import annotations

import argparse
import base64
import datetime
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import re
import sys
import tempfile

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.v69.terrain_tiles import validate_grid, tile_from_grid
from tools.v69_heights import validate_height_bindings

SCHEMA = 'soma-metropole/world-manifest/1'
ORIGIN = [892951.6480966414, 6247274.566415883]
MAX_BLOB = 160 * 1024 * 1024
TILE_ID = re.compile(r'^V52-MC-(?:[1-5][1-5]|[EW][0-9]{2,4}-[NS][0-9]{2,4})$')
BOUNDARY_BUDGET = 32 * 1024 * 1024
HASH = re.compile(r'^[a-f0-9]{64}$')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _boundary_file(base, descriptor):
    """Read a bounded, pinned administrative source below its territory file."""
    if not isinstance(descriptor, dict):
        raise ValueError('Contour administratif : descripteur absent.')
    relative = descriptor.get('path')
    if (not isinstance(relative, str) or len(relative)>1000 or
            not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]*', relative) or
            any(part in ('', '.', '..') for part in relative.split('/'))):
        raise ValueError('Contour administratif : chemin relatif invalide.')
    path = (base/relative).resolve()
    if not path.is_relative_to(base) or not path.is_file():
        raise ValueError('Contour administratif : fichier absent ou hors répertoire.')
    size = descriptor.get('bytes')
    if (not isinstance(size, int) or isinstance(size, bool) or not 0<size<=BOUNDARY_BUDGET or
            not isinstance(descriptor.get('sha256'), str) or not HASH.fullmatch(descriptor['sha256'])):
        raise ValueError('Contour administratif : taille ou empreinte invalide.')
    if path.stat().st_size != size:
        raise ValueError('Contour administratif : taille de fichier modifiée.')
    raw = path.read_bytes()
    if len(raw) != size or digest(raw) != descriptor['sha256']:
        raise ValueError('Contour administratif : empreinte de fichier modifiée.')
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError('Contour administratif : objet JSON requis.')
    return value


def _polygon_coordinates(geometry):
    """Check the RFC 7946 structure; topology is covered by the pinned GIS receipt."""
    if not isinstance(geometry, dict) or geometry.get('type') not in ('Polygon', 'MultiPolygon'):
        raise ValueError('Contour administratif : géométrie polygonale requise.')
    polygons = [geometry.get('coordinates')] if geometry['type']=='Polygon' else geometry.get('coordinates')
    if not isinstance(polygons, list) or not polygons:
        raise ValueError('Contour administratif : polygone vide.')
    for polygon in polygons:
        if not isinstance(polygon, list) or not polygon:
            raise ValueError('Contour administratif : anneau absent.')
        for ring in polygon:
            if not isinstance(ring, list) or len(ring)<4 or ring[0]!=ring[-1]:
                raise ValueError('Contour administratif : anneau ouvert ou incomplet.')
            for point in ring:
                if (not isinstance(point, list) or len(point)!=2 or any(
                        not isinstance(n, (int,float)) or isinstance(n,bool) or not math.isfinite(n) for n in point) or
                        not -180<=point[0]<=180 or not -90<=point[1]<=90):
                    raise ValueError('Contour administratif : coordonnées WGS84 invalides.')


def load_territory_reference(path):
    """Validate source identity and the acquired GIS proof without GIS dependencies.

    This checks receipt bindings and GeoJSON structure, not polygon topology anew.
    The independent acquisition receipt records the actual Shapely validity check.
    """
    path = Path(path)
    raw = path.read_bytes()
    territory = json.loads(raw)
    if not isinstance(territory, dict):
        raise ValueError('La référence administrative AMP 2026 doit être un objet.')
    communes = territory.get('communes', [])
    if (territory.get('schema')!='soma-metropole/territory/1' or territory.get('id')!='200054807' or
            territory.get('year')!=2026 or not isinstance(communes,list) or len(communes)!=92):
        raise ValueError('La référence administrative AMP 2026 est requise.')
    codes = [row.get('code') if isinstance(row,dict) else None for row in communes]
    if any(not isinstance(code,str) or not re.fullmatch(r'[0-9]{5}',code) for code in codes) or len(set(codes))!=92:
        raise ValueError('La référence administrative AMP exige 92 codes uniques.')
    boundary = territory.get('boundary')
    if boundary is None:
        return territory, digest(raw), None
    if (not isinstance(boundary,dict) or boundary.get('schema')!='soma-metropole/administrative-boundary/1' or
            boundary.get('crs')!='EPSG:4326' or 'vintage' not in boundary or boundary['vintage'] is not None or
            boundary.get('vintageStatus')!='not-stated-by-service'):
        raise ValueError('Contour administratif : CRS ou millésime déclaré incompatible.')
    base = path.resolve().parent
    geometry = _boundary_file(base, boundary)
    source = boundary.get('source')
    source_data = _boundary_file(base, source)
    raw_receipt = _boundary_file(base, boundary.get('rawReceipt'))
    validation = _boundary_file(base, boundary.get('validationReceipt'))
    official_url = 'https://geo.api.gouv.fr/epcis/200054807/communes?format=geojson&geometry=contour&fields=nom,code,population'
    if (raw_receipt.get('schema')!='soma-metropole/public-acquisition/1' or raw_receipt.get('httpStatus')!=200 or
            raw_receipt.get('url')!=official_url or raw_receipt.get('finalURL')!=official_url or
            source.get('url')!=official_url or raw_receipt.get('sha256')!=source['sha256'] or
            raw_receipt.get('bytes')!=source['bytes'] or source.get('vintageStatus')!='not-stated-by-service' or
            'vintage' not in source or source['vintage'] is not None or
            not raw_receipt.get('acquiredUTC') or raw_receipt['acquiredUTC']!=boundary.get('acquiredUTC')):
        raise ValueError('Contour administratif : reçu HTTP ou source officielle contradictoire.')
    try:
        acquired = datetime.datetime.fromisoformat(raw_receipt['acquiredUTC'])
        if acquired.utcoffset()!=datetime.timedelta(0):
            raise ValueError('UTC required')
    except (TypeError, ValueError) as error:
        raise ValueError('Contour administratif : date UTC invalide.') from error
    if (validation.get('schema')!='soma-metropole/administrative-boundary-receipt/1' or
            validation.get('targetId')!=territory['id'] or validation.get('source')!=raw_receipt or
            validation.get('boundarySHA256')!=boundary['sha256'] or validation.get('boundaryBytes')!=boundary['bytes'] or
            validation.get('crs')!='EPSG:4326' or validation.get('administrativeCompositionYearMatched')!=2026 or
            validation.get('communeCount')!=92 or validation.get('communeCodes')!=sorted(codes) or
            validation.get('invalidSourceGeometries')!=0 or validation.get('unionValid') is not True or
            validation.get('geometryRepairApplied') is not False or validation.get('activatedInGame') is not False or
            validation.get('completeMetropole') is not False or validation.get('certifiedOneToOne') is not False):
        raise ValueError('Contour administratif : reçu de validité absent ou lié à une autre source.')
    for document in (source_data, geometry):
        if document.get('type')!='FeatureCollection' or 'crs' in document or not isinstance(document.get('features'),list):
            raise ValueError('Contour administratif : GeoJSON RFC 7946 requis.')
    features = source_data['features']
    source_codes = [feature.get('properties',{}).get('code') for feature in features if isinstance(feature,dict)]
    if len(features)!=92 or len(source_codes)!=92 or set(source_codes)!=set(codes):
        raise ValueError('Contour administratif : communes sources différentes de la référence 2026.')
    for feature in features:
        _polygon_coordinates(feature.get('geometry'))
    if (len(geometry['features'])!=1 or geometry['features'][0].get('properties',{}).get('code')!=territory['id'] or
            geometry['features'][0].get('properties',{}).get('sourceSHA256')!=source['sha256']):
        raise ValueError('Contour administratif : union liée à un autre EPCI ou fichier source.')
    _polygon_coordinates(geometry['features'][0].get('geometry'))
    return territory, digest(raw), boundary['sha256']


def embedded(html, script_id):
    pattern = r'<script\b([^>]*\bid="' + re.escape(script_id) + r'"[^>]*)>(.*?)</script>'
    matches = list(re.finditer(pattern, html, re.S))
    if len(matches) != 1:
        raise ValueError(f'Source absente ou dupliquée : {script_id}')
    attrs = dict(re.findall(r'([\w-]+)="([^\"]*)"', matches[0][1]))
    body = matches[0][2]
    if attrs.get('data-encoding') == 'gzip-base64':
        size = int(attrs.get('data-bytes', '0'))
        if not 0 < size <= MAX_BLOB:
            raise ValueError('Source décompressée hors budget.')
        packed = base64.b64decode(''.join(body.split()), validate=True)
        with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
            raw = stream.read(size + 1)
            if len(raw) != size or stream.read(1):
                raise ValueError('Taille de source incorporée incorrecte.')
        if digest(raw) != attrs.get('data-sha256'):
            raise ValueError('Empreinte de source incorporée incorrecte.')
    else:
        raw = body.encode('utf-8')
        if len(raw) > MAX_BLOB:
            raise ValueError('Source JSON hors budget.')
    return json.loads(raw), digest(raw)


def _write(path, raw):
    path = Path(path)
    if path.is_file() and path.read_bytes() == raw:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents an existing .tmp symlink from redirecting a
    # write. Keep the temporary on the destination filesystem for atomic replace.
    stream = tempfile.NamedTemporaryFile(mode='wb', dir=path.parent,
                                        prefix=path.name + '.', suffix='.tmp',
                                        delete=False)
    temporary = Path(stream.name)
    try:
        with stream:
            stream.write(raw)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def asset(directory, relative, value, **extra):
    if not isinstance(relative,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]*',relative) or any(x in ('', '.', '..') for x in relative.split('/')):
        raise ValueError('Chemin de sortie invalide.')
    destination=Path(directory)/relative
    if not destination.resolve().is_relative_to(Path(directory).resolve()):
        raise ValueError('Le chemin de sortie quitte le répertoire par un lien symbolique.')
    output = io.BytesIO()
    with gzip.GzipFile(fileobj=output, mode='wb', filename='', mtime=0, compresslevel=6) as stream:
        stream.write(canonical(value))
    raw = output.getvalue()
    _write(destination, raw)
    return {'path':relative, 'sha256':digest(raw), 'bytes':len(raw), 'encoding':'gzip-json', **extra}


def local_navigation(graph, cell_id):
    edges = [edge for edge in graph['edges'] if cell_id in edge[6]]
    indices = sorted({index for edge in edges for index in edge[:2]})
    mapping = {old:new for new,old in enumerate(indices)}
    nodes = [graph['nodes'][index] for index in indices]
    ways = {edge[2] for edge in edges}
    node_ids = {node[0] for node in nodes}
    referenced_cells = {cell for edge in edges for cell in edge[6]} | {cell_id}
    turns = [turn for turn in graph['turns'] if turn['from'] in ways and turn['via'] in node_ids]
    # An only_* turn remains restrictive even when its permitted destination
    # leaves this cell. Keep that way's metadata, without inventing its edges.
    referenced_ways = ways | {turn['to'] for turn in turns}
    return {**graph, 'nodes':nodes,
            'edges':[[mapping[e[0]],mapping[e[1]],*e[2:]] for e in edges],
            'ways':{key:row for key,row in graph['ways'].items() if key in referenced_ways},
            'turns':turns,
            'cellHashes':{key:graph['cellHashes'][key] for key in sorted(referenced_cells)},
            'tileCellId':cell_id, 'tileSubset':True,
            'routingScope':'Selected cell edges only. The verified original full graph remains active for gameplay.'}


def prepare_world(html, output_dir, terrain_path, territory_path):
    territory, territory_sha, boundary_sha = load_territory_reference(territory_path)
    expected_inputs = {'htmlSHA256':digest(html.encode('utf-8')),
                       'terrainFileSHA256':digest(Path(terrain_path).read_bytes()),
                       'territoryFileSHA256':territory_sha,
                       'bootstrapSourceSHA256':digest(Path(__file__).read_bytes()),
                       'terrainTilerSourceSHA256':digest((Path(__file__).resolve().parents[1]/'v69/terrain_tiles.py').read_bytes())}
    cache = Path(output_dir)/'manifest.json'
    if cache.is_file():
        try:
            cached = json.loads(cache.read_bytes())
            if cached.get('buildInputs') == expected_inputs:
                verify_world(output_dir, expected_inputs, territory_path=territory_path)
                return cached
        except (ValueError, OSError, KeyError, TypeError):
            pass
    pack, pack_sha = embedded(html, 'soma-v53-embedded-pack')
    fidelity, fidelity_sha = embedded(html, 'soma-v59-fidelity-data')
    graph, _ = embedded(html, 'soma-v63-navigation')
    if pack.get('schema') != 'soma-massilia/geodata-pack/4' or pack.get('testOnly') or not pack.get('records'):
        raise ValueError('Le socle géographique vérifié est requis.')
    source = pack['sourceReceipt']
    height_proof = None
    height_rows = {}
    if re.search(r'\bid="soma-v69-building-height-matches"',html):
        height_proof,_ = embedded(html,'soma-v69-building-height-matches')
        validate_height_bindings(height_proof,pack['records'],source_sha=source['sha256'])
        height_rows = {row['canonicalId']:row for row in height_proof['matches'].values()}
    if graph['sourcePackSHA256'] != pack_sha or graph['sourcePbfSHA256'] != source['sha256']:
        raise ValueError('Navigation et données géographiques incompatibles.')
    terrain_pack = json.loads(Path(terrain_path).read_text(encoding='utf-8'))
    grid = validate_grid(terrain_pack)
    manifest = {'schema':SCHEMA, 'crs':'EPSG:2154', 'units':'m', 'origin':ORIGIN,
                'cellSize':250, 'source':source, 'sourcePackSHA256':pack_sha,
                'fidelitySHA256':fidelity_sha, 'terrainGridSHA256':grid.sha256,
                'target':{'id':territory['id'], 'name':territory['name'], 'communeCount':92,
                          'territorySHA256':territory_sha, 'boundarySHA256':boundary_sha},
                'coverageExplicitPartial':True, 'completeMetropole':False,
                'edition':'bundled-centre-0.69', 'buildInputs':expected_inputs, 'tiles':[]}
    if height_proof:
        manifest['heightReferences'] = {'proofSHA256':height_proof['proofSHA256'],
            'ignSourceSHA256':height_proof['ignSource']['sha256'],'references':len(height_rows),
            'heightKind':'eaves','roofSurveyed':False,'accuracy':'source-match-not-certified'}
    seen, positions = set(), set()
    records = sorted(pack['records'], key=lambda row:row['cellId'])
    for record in records:
        cell_id = record['cellId']
        if not TILE_ID.fullmatch(cell_id) or cell_id in seen or record.get('v53Synthetic'):
            raise ValueError('Tuile source invalide ou dupliquée.')
        seen.add(cell_id)
        x, y = record['grid']['x'], record['grid']['y']
        if (x,y) in positions:
            raise ValueError('Deux identifiants occupent une même cellule.')
        positions.add((x,y))
        expected = [ORIGIN[0]+x*250-125, ORIGIN[1]-y*250-125,
                    ORIGIN[0]+x*250+125, ORIGIN[1]-y*250+125]
        if any(abs(a-b)>.001 for a,b in zip(record['boundsL93'],expected)):
            raise ValueError('Une tuile est décalée du repère historique.')
        cell = {'cellId':cell_id, 'gridX':x, 'gridY':y, 'boundsL93':record['boundsL93'],
                'contentSHA256':record['contentSHA256'],
                'vector':asset(output_dir, f'tiles/{cell_id}.vector.json.gz', record)}
        terrain = tile_from_grid(grid, record['boundsL93'], terrain_pack.get('source'))
        cell['terrain'] = None if terrain is None else asset(output_dir,
            f'tiles/{cell_id}.terrain.json.gz', terrain, gridSHA256=terrain['sha256'], stepM=grid.step,
            complete=terrain['stats']['noData']==0)
        surface = fidelity['cells'].get(cell_id)
        if surface and surface['contentSHA256'] == record['contentSHA256'] and surface['sourceSHA256'] == source['sha256']:
            ids = {str(f.get('properties',{}).get('canonical_id') or f.get('id'))
                   for f in record['featureCollection']['features']}
            payload = {'schema':'soma-metropole/surface-cell/1', 'cellId':cell_id,
                       'sourcePbfSHA256':source['sha256'], 'contentSHA256':record['contentSHA256'],
                       'cell':surface,
                       'roadMetadata':{key:row for key,row in fidelity['roadMetadata'].items() if key in ids},
                       'buildings':{key:row for key,row in fidelity['buildings'].items() if key in ids}}
            for identity in ids:
                row = height_rows.get(identity)
                if row and row['cells'].get(cell_id)==record['contentSHA256']:
                    payload['buildings'][identity] = {
                        **row,'cellContentSHA256':record['contentSHA256'],
                        'heightKind':'eaves','roofSurveyed':False,'accuracy':'source-match-not-certified',
                        'proofSHA256':height_proof['proofSHA256'],
                        'ignSourceSHA256':height_proof['ignSource']['sha256']}
            cell['surfaces'] = asset(output_dir,f'tiles/{cell_id}.surfaces.json.gz',payload)
        else:
            cell['surfaces'] = None
        cell['navigation'] = asset(output_dir,f'tiles/{cell_id}.navigation.json.gz',local_navigation(graph,cell_id))
        cell['readiness'] = 'prepared-original-edition' if all(cell.get(k) for k in ('vector','terrain','surfaces','navigation')) else 'incomplete'
        manifest['tiles'].append(cell)
    manifest['coverage'] = {'vectorCells':len(records), 'areaOfCellsKm2':len(records)*.0625,
                            'completeLayerCells':sum(c['readiness']=='prepared-original-edition' for c in manifest['tiles']),
                            'newGeographicCells':0, 'administrativeCoverageRatio':None}
    manifest['manifestContentSHA256']=digest(canonical(manifest))
    _write(Path(output_dir)/'manifest.json',canonical(manifest)+b'\n')
    return manifest


def verify_world(directory, expected_inputs=None, *, territory_path=None):
    root = Path(directory).resolve()
    manifest = json.loads((root/'manifest.json').read_bytes())
    if (manifest.get('schema') != SCHEMA or manifest.get('origin') != ORIGIN or
            manifest.get('coverageExplicitPartial') is not True or manifest.get('completeMetropole') is not False):
        raise ValueError('Manifeste territorial incompatible.')
    if manifest.get('manifestContentSHA256')!=digest(canonical({k:v for k,v in manifest.items() if k!='manifestContentSHA256'})):
        raise ValueError('Le manifeste territorial a été modifié.')
    if expected_inputs is not None and manifest.get('buildInputs') != expected_inputs:
        raise ValueError('Les assets ne correspondent pas à cette reconstruction.')
    target = manifest.get('target', {})
    if expected_inputs is not None or territory_path is not None or target.get('boundarySHA256') is not None:
        reference = territory_path or Path(__file__).resolve().parents[2]/'data/v69/territory.json'
        _, territory_sha, boundary_sha = load_territory_reference(reference)
        if target.get('boundarySHA256')!=boundary_sha or target.get('territorySHA256')!=territory_sha:
            raise ValueError('Le manifeste et la référence administrative du contour divergent.')
    for cell in manifest['tiles']:
        for key in ('vector','terrain','surfaces','navigation'):
            entry = cell.get(key)
            if entry is None:
                continue
            path = root/entry['path']
            if not path.resolve().is_relative_to(root) or not path.is_file():
                raise ValueError('Asset absent ou hors répertoire.')
            raw = path.read_bytes()
            if len(raw) != entry['bytes'] or digest(raw) != entry['sha256']:
                raise ValueError(f'Asset modifié : {cell["cellId"]}/{key}')
    return manifest


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--html', type=Path, default=root/'SOMA_MASSILIA_URBAIN_v0_69.html')
    parser.add_argument('--terrain', type=Path, default=root/'data/v58/terrain.ign.json')
    parser.add_argument('--territory', type=Path, default=root/'data/v69/territory.json')
    parser.add_argument('--output', type=Path, default=root/'data/v69/world')
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    manifest = verify_world(args.output,territory_path=args.territory) if args.verify else prepare_world(args.html.read_text(encoding='utf-8'),args.output,args.terrain,args.territory)
    print(json.dumps(manifest['coverage'],ensure_ascii=False))


if __name__ == '__main__':
    main()
