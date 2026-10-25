#!/usr/bin/env python3
"""Acquire official IGN native archives or WMS exports explicitly, never while playing.

Raw little-endian float32 BIL responses, provider metadata, request parameters
and SHA256 receipts remain available alongside GeoTIFF derivatives. WMS exports
require a separate coastal NoData assessment before terrain admission. Their CRS
comes from the advertised/requested WMS CRS, with unchanged numerical pixels;
the provider's malformed sample GeoTIFF WKT is not silently trusted.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import threading
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

try:
    from .terrain_tiles import TerrainError, file_fingerprint
except ImportError:
    from terrain_tiles import TerrainError, file_fingerprint

ORIGIN = (892951.6480966414, 6247274.566415883)
LAYER = 'ELEVATION.ELEVATIONGRIDCOVERAGE.HIGHRES'
WMS = 'https://data.geopf.fr/wms-r'
CAPABILITIES = WMS + '?SERVICE=WMS&REQUEST=GetCapabilities&VERSION=1.3.0'
CATALOGUE = ('https://data.geopf.fr/csw?REQUEST=GetRecordById&SERVICE=CSW&VERSION=2.0.2'
             '&OUTPUTSCHEMA=http://standards.iso.org/iso/19115/-3/mdb/2.0'
             '&elementSetName=full&ID=IGNF_RGE-ALTI')
MAX_RESPONSE = 64 * 1024 * 1024
MAX_TOTAL = 2 * 1024 * 1024 * 1024
METADATA_LIMIT = 8 * 1024 * 1024
NATIVE_NAME = re.compile(r'RGEALTI_2-0_5M_ASC_LAMB93-IGN69_D\d{3}_\d{4}-\d{2}-\d{2}\.7z')
NATIVE_NODE = re.compile(r'RGEALTI_FXX_(\d{4})_(\d{4})_MNT_LAMB93_IGN69\.asc')


def _json(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')


def _write_exact(path, raw):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != raw:
            raise TerrainError(f'Sortie existante différente conservée : {path}')
    else:
        with path.open('xb') as stream:
            stream.write(raw)


def _finite(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)


def projected_boundary(path, expected_sha256=None):
    """Project all declared WGS84 vertices; no bounding-box-only projection or repair."""
    try:
        from pyproj import Transformer
        from shapely.geometry import shape
        from shapely.ops import transform, unary_union
    except ImportError as error:
        raise TerrainError('Pyproj et Shapely sont requis pour planifier les acquisitions géographiques.') from error
    path = Path(path)
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if expected_sha256 and digest != expected_sha256:
        raise TerrainError('L’empreinte du contour ne correspond pas à celle attendue.')
    document = json.loads(raw)
    if document.get('crs'):
        raise TerrainError('Le contour doit être un GeoJSON WGS84 sans autre déclaration de CRS.')
    features = document.get('features', [document])
    polygons = []
    for feature in features:
        geometry = shape(feature.get('geometry', feature))
        if geometry.is_empty or geometry.geom_type not in ('Polygon', 'MultiPolygon') or not geometry.is_valid:
            raise TerrainError('Le contour doit contenir des polygones valides ; aucune réparation automatique.')
        west, south, east, north = geometry.bounds
        if not (-180 <= west <= east <= 180 and -90 <= south <= north <= 90):
            raise TerrainError('Coordonnées du contour hors WGS84.')
        polygons.append(geometry)
    if not polygons:
        raise TerrainError('Contour vide.')
    region = unary_union(polygons)
    projected = transform(Transformer.from_crs(4326, 2154, always_xy=True).transform, region)
    if not projected.is_valid or projected.is_empty or not all(math.isfinite(value) for value in projected.bounds):
        raise TerrainError('Projection du contour invalide.')
    return {'boundsL93': list(projected.bounds), 'areaM2': projected.area,
            'file': {'name': path.name, 'bytes': len(raw), 'sha256': digest}}


def make_plan(boundary, *, step=5, chunk=4096, origin=ORIGIN,
              max_response_bytes=MAX_RESPONSE, max_total_bytes=MAX_TOTAL):
    """Create cell-aligned, pixel-centred bounded requests without network calls."""
    if step not in (1, 5, 25) or isinstance(step, bool):
        raise TerrainError('Le pas doit être 1, 5 ou 25 m.')
    if not isinstance(chunk, int) or isinstance(chunk, bool) or not 1 <= chunk <= 5010:
        raise TerrainError('Dimension de requête hors limite publiée de 5 010 pixels.')
    for budget in (max_response_bytes, max_total_bytes):
        if not isinstance(budget, int) or isinstance(budget, bool) or budget <= 0:
            raise TerrainError('Les budgets doivent être des nombres entiers positifs d’octets.')
    if len(origin) != 2 or not all(_finite(v) for v in origin):
        raise TerrainError('Origine métrique invalide.')
    bounds = boundary.get('boundsL93')
    if (not isinstance(bounds, (list, tuple)) or len(bounds) != 4 or not all(_finite(v) for v in bounds)
            or bounds[0] >= bounds[2] or bounds[1] >= bounds[3]):
        raise TerrainError('Emprise projetée du contour invalide.')
    xmin, xmax = (math.floor((bounds[i] - origin[0] + 125) / 250) for i in (0, 2))
    ymin, ymax = (math.floor((origin[1] - bounds[i] + 125) / 250) for i in (3, 1))
    useful = [origin[0] + xmin * 250 - 125, origin[1] - ymax * 250 - 125,
              origin[0] + xmax * 250 + 125, origin[1] - ymin * 250 + 125]
    x0, n0 = useful[0] - step, useful[3] + step
    cols = round((useful[2] - useful[0]) / step) + 3
    rows = round((useful[3] - useful[1]) / step) + 3
    total = cols * rows * 4
    if total > max_total_bytes:
        raise TerrainError(f'Acquisition hors budget total : {total} octets bruts demandés.')
    jobs = []
    for row in range(0, rows, chunk):
        for col in range(0, cols, chunk):
            width, height = min(chunk, cols - col), min(chunk, rows - row)
            if width * height * 4 > max_response_bytes:
                raise TerrainError('Une réponse dépasse le budget ; réduire --chunk.')
            left, top = x0 + col * step - step / 2, n0 - row * step + step / 2
            bbox = [left, top - height * step, left + width * step, top]
            params = {'SERVICE': 'WMS', 'VERSION': '1.3.0', 'REQUEST': 'GetMap',
                      'LAYERS': LAYER, 'STYLES': 'normal', 'FORMAT': 'image/x-bil;bits=32',
                      'CRS': 'EPSG:2154', 'BBOX': ','.join(map(str, bbox)),
                      'WIDTH': width, 'HEIGHT': height, 'EXCEPTIONS': 'XML'}
            jobs.append({'id': f'r{row//chunk:02d}-c{col//chunk:02d}', 'row': row, 'col': col,
                         'width': width, 'height': height, 'bboxL93': bbox,
                         'url': WMS + '?' + urlencode(params)})
    return {'schema': 'soma-metropole/ign-wms-acquisition-plan/1', 'crs': 'EPSG:2154',
            'verticalDatum': 'NGF-IGN69', 'units': 'm', 'boundary': boundary,
            'origin': list(origin), 'cellSize': 250, 'stepM': step,
            'usefulBoundsL93': useful, 'gridNodeX0': x0, 'gridNodeN0': n0,
            'cols': cols, 'rows': rows, 'nodes': cols * rows, 'rawBytes': total,
            'maxResponseBytes': max_response_bytes, 'maxTotalBytes': max_total_bytes,
            'layer': LAYER, 'requests': jobs, 'sourceSurveyDate': 'not supplied',
            'newSurvey': False, 'notNativeSurveyResolution': True,
            'runtimeEligible': False,
            'coastalNoDataAssessment': 'Not assessed; the WMS may interpolate its NoData sentinel.'}


def validate_capabilities(raw):
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as error:
        raise TerrainError('Réponse de capacités XML invalide.') from error
    ns = {'w': 'http://www.opengis.net/wms'}
    formats = [node.text for node in root.findall('.//w:Request/w:GetMap/w:Format', ns)]
    names = [node.text for node in root.findall('.//w:Layer/w:Name', ns)]
    crs = [node.text for node in root.findall('.//w:CRS', ns)]
    if 'image/x-bil;bits=32' not in formats or LAYER not in names or 'EPSG:2154' not in crs:
        raise TerrainError('Le service n’annonce pas le MNT numérique, son format ou le CRS requis.')
    service = root.find('w:Service', ns)
    try:
        width = int(service.findtext('w:MaxWidth', namespaces=ns))
        height = int(service.findtext('w:MaxHeight', namespaces=ns))
    except (TypeError, ValueError, AttributeError) as error:
        raise TerrainError('Limites dimensionnelles du service absentes.') from error
    return {'maxWidth': width, 'maxHeight': height, 'sha256': hashlib.sha256(raw).hexdigest()}


def validate_catalogue(raw):
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as error:
        raise TerrainError('Métadonnées XML invalides.') from error
    text = ' '.join((element.text or '').strip() for element in root.iter())
    if (not re.search(r'RGE\s*ALTI', text, re.I) or not re.search(r'NGF[- ]IGN\s*1969', text, re.I)
            or not re.search(r'RGF93\s+Lambert\s+93', text, re.I)
            or 'EPSG:2154' not in text or 'Licence Ouverte' not in text):
        raise TerrainError('Les métadonnées ne confirment pas RGE ALTI, Lambert 93, NGF-IGN69 et la licence ouverte.')
    stopped = re.search(r'mise à jour a été arrêtée en (\d{4})', text)
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'provider': 'IGN',
            'product': 'RGE ALTI WMS-R numerical export', 'verticalDatum': 'NGF-IGN69',
            'units': 'm', 'crs': 'EPSG:2154', 'license': 'Licence Ouverte / Open License (official IGN catalogue declaration)',
            'attribution': 'IGN — RGE ALTI', 'sourceSurveyDate': 'not supplied',
            'productUpdateStopYearDeclaredByCatalogue': int(stopped[1]) if stopped else None}


def validate_bil(path, width, height, *, max_response_bytes=MAX_RESPONSE):
    import numpy as np
    if (not isinstance(width, int) or not isinstance(height, int) or isinstance(width, bool)
            or isinstance(height, bool) or width <= 0 or height <= 0):
        raise TerrainError('Dimensions ou budget de BIL invalides.')
    expected = width * height * 4
    if expected > max_response_bytes:
        raise TerrainError('Dimensions ou budget de BIL invalides.')
    path = Path(path)
    if path.stat().st_size != expected:
        raise TerrainError('Nombre d’octets BIL incorrect ; aucune interprétation d’image ou de texte.')
    values = np.memmap(path, mode='r', dtype='<f4', shape=(height, width))
    valid_count, minimum, maximum = 0, math.inf, -math.inf
    for start in range(0, height, 256):
        part = values[start:start + 256]
        present = part[part != -99999.0]
        if present.size:
            if not np.isfinite(present).all() or present.min() < -500 or present.max() > 9000:
                raise TerrainError('Altitude BIL invalide ; ne pas changer le datum ni combler les NoData.')
            valid_count += int(present.size)
            minimum, maximum = min(minimum, float(present.min())), max(maximum, float(present.max()))
    return {'nodes': width * height, 'valid': valid_count, 'noData': width * height - valid_count,
            'minM': minimum if valid_count else None, 'maxM': maximum if valid_count else None}


def normalise_bil(raw_path, tif_path, job, step, *, max_response_bytes=MAX_RESPONSE):
    """Assign the WMS-declared georeference; verify every numerical source pixel."""
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin
    raw_path, tif_path = Path(raw_path), Path(tif_path)
    stats = validate_bil(raw_path, job['width'], job['height'], max_response_bytes=max_response_bytes)
    bounds = job['bboxL93']
    if abs((bounds[2] - bounds[0]) / job['width'] - step) > 1e-8 or abs((bounds[3] - bounds[1]) / job['height'] - step) > 1e-8:
        raise TerrainError('L’emprise de requête ne correspond pas au pas déclaré.')
    values = np.memmap(raw_path, mode='r', dtype='<f4', shape=(job['height'], job['width']))
    source_sha = file_fingerprint(raw_path)['sha256']
    transform = from_origin(bounds[0], bounds[3], step, step)
    if not tif_path.exists():
        with rasterio.Env(GDAL_CACHEMAX=64 * 1024 * 1024):
            with rasterio.open(tif_path, 'w', driver='GTiff', width=job['width'], height=job['height'],
                               count=1, dtype='float32', crs='EPSG:2154', transform=transform,
                               nodata=-99999.0, tiled=True, blockxsize=256, blockysize=256,
                               compress='deflate', predictor=3, zlevel=4) as target:
                target.write(values, 1)
                target.set_band_unit(1, 'm')
                target.update_tags(VERTICAL_DATUM='NGF-IGN69', WMS_REQUESTED_CRS='EPSG:2154',
                                   SOURCE_RAW_SHA256=source_sha, SOURCE_URL=job['url'], SOURCE_LAYER=LAYER,
                                   SAMPLING=f'Server-exported {step}m grid; not a new native survey',
                                   SURVEY_DATE='Not supplied by WMS', SOURCE_CATALOGUE='IGNF_RGE-ALTI')
    with rasterio.open(tif_path) as restored:
        if (restored.crs is None or restored.crs.to_epsg() != 2154 or restored.dtypes != ('float32',)
                or restored.transform != transform or restored.nodata != -99999.0
                or restored.width != job['width'] or restored.height != job['height']
                or restored.units != ('m',) or restored.tags().get('VERTICAL_DATUM') != 'NGF-IGN69'
                or restored.tags().get('SOURCE_RAW_SHA256') != source_sha):
            raise TerrainError('Le GeoTIFF existant ne correspond pas à la géoréférence déclarée ; conservé.')
        for start in range(0, job['height'], 256):
            data = restored.read(1, window=((start, min(start + 256, job['height'])), (0, job['width'])))
            if data.astype('<f4', copy=False).tobytes() != values[start:start + 256].tobytes():
                raise TerrainError('Valeurs numériques modifiées pendant la normalisation ; sortie conservée.')
    return {'statistics': stats, 'normalised': {**file_fingerprint(tif_path),
            'crs': 'EPSG:2154', 'verticalDatum': 'NGF-IGN69', 'units': 'm',
            'normalisationChangesValues': False, 'rawSHA256': source_sha}}


def _get_metadata(url, target, validate):
    target = Path(target)
    if target.exists():
        raw = target.read_bytes()
    else:
        with urlopen(Request(url, headers={'User-Agent': 'Massilia-development-source-acquisition/0.69'}), timeout=30) as response:
            raw = response.read(METADATA_LIMIT + 1)
            if response.status != 200 or len(raw) > METADATA_LIMIT:
                raise TerrainError('Métadonnées officielles absentes ou hors budget.')
        validate(raw)
        _write_exact(target, raw)
    result = validate(raw)
    return {**result, 'url': url, 'path': target.name}


def native_jobs_from_feeds(feeds, *, max_archive_bytes=1024**3, max_total_bytes=MAX_TOTAL):
    """Read retained official ATOM feeds offline; do not guess archive URLs."""
    jobs, names = [], set()
    for feed in feeds:
        feed = Path(feed)
        raw = feed.read_bytes()
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as error:
            raise TerrainError('Flux ATOM natif invalide.') from error
        for link in root.iter('{http://www.w3.org/2005/Atom}link'):
            if link.get('type') != 'application/x-7z-compressed':
                continue
            url = link.get('href', '')
            parsed = urlsplit(url)
            name = parsed.path.rsplit('/', 1)[-1]
            if (parsed.scheme != 'https' or parsed.netloc != 'data.geopf.fr'
                    or parsed.query or parsed.fragment or not NATIVE_NAME.fullmatch(name)
                    or parsed.path != f'/telechargement/download/RGEALTI/{name[:-3]}/{name}'):
                raise TerrainError('Lien d’archive native non officiel ou format inattendu.')
            try:
                size = int(link.get('{https://data.geopf.fr/annexes/ressources/xsd/gpf_dl.xsd}length'))
            except (TypeError, ValueError) as error:
                raise TerrainError('Taille publiée de l’archive absente.') from error
            if size <= 0 or size > max_archive_bytes or name in names:
                raise TerrainError('Archive native dupliquée ou hors budget publié.')
            names.add(name)
            jobs.append({'url': url, 'expectedBytes': size, 'sourceFeed': feed.name,
                         'sourceFeedSHA256': hashlib.sha256(raw).hexdigest()})
    if not jobs or sum(job['expectedBytes'] for job in jobs) > max_total_bytes:
        raise TerrainError('Archives natives absentes ou hors budget total.')
    return jobs


def discover_native_feeds(departments, output):
    """Explicit official discovery, sequential and bounded to two small feeds per department."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    paths = []
    for department in departments:
        if not re.fullmatch(r'\d{3}', department):
            raise TerrainError('Le département doit être un code à trois chiffres, par exemple 013.')
        zone_url = f'https://data.geopf.fr/telechargement/resource/RGEALTI?zone=D{department}'
        zone = output / f'native-zone-D{department}.xml'

        def edition(raw):
            root = ET.fromstring(raw)
            links = [link.get('href') for entry in root.iter('{http://www.w3.org/2005/Atom}entry')
                     if re.fullmatch(rf'RGEALTI_2-0_5M_ASC_LAMB93-IGN69_D{department}_\d{{4}}-\d{{2}}-\d{{2}}',
                                     entry.findtext('{http://www.w3.org/2005/Atom}title', ''))
                     for link in entry.findall('{http://www.w3.org/2005/Atom}link')
                     if link.get('type') == 'application/atom+xml']
            if len(links) != 1 or not links[0].startswith('https://data.geopf.fr/telechargement/resource/RGEALTI/'):
                raise TerrainError('Une édition native 5 m unique et officielle est requise.')
            return {'editionURL': links[0]}

        result = _get_metadata(zone_url, zone, edition)
        path = output / f'native-D{department}.xml'
        _get_metadata(result['editionURL'], path, lambda raw: {'sha256': hashlib.sha256(raw).hexdigest()})
        native_jobs_from_feeds([path])
        paths.append(path)
    return paths


def native_plan(boundary, feeds, *, max_archive_bytes=1024**3, max_total_bytes=MAX_TOTAL):
    jobs = native_jobs_from_feeds(feeds, max_archive_bytes=max_archive_bytes, max_total_bytes=max_total_bytes)
    return {'schema': 'soma-metropole/ign-native-acquisition-plan/1', 'boundary': boundary,
            'jobs': jobs, 'totalBytes': sum(job['expectedBytes'] for job in jobs),
            'maxArchiveBytes': max_archive_bytes, 'maxTotalBytes': max_total_bytes,
            'nativeStepM': 5, 'crs': 'EPSG:2154', 'verticalDatum': 'NGF-IGN69', 'units': 'm',
            'sourceSurveyDate': 'not supplied', 'newSurvey': False, 'maxWorkers': 2}


def fetch_native_archives(plan, output, *, workers=2, progress=None):
    """Retain exact native archives with their published byte counts and local SHA256."""
    if workers not in (1, 2) or isinstance(workers, bool):
        raise TerrainError('Un ou deux travailleurs réseau sont permis.')
    if (plan.get('schema') != 'soma-metropole/ign-native-acquisition-plan/1'
            or sum(j['expectedBytes'] for j in plan['jobs']) != plan['totalBytes']
            or plan['totalBytes'] > plan['maxTotalBytes']):
        raise TerrainError('Budget du plan natif incohérent.')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    source = _get_metadata(CATALOGUE, output / 'catalogue.xml', validate_catalogue)
    _write_exact(output / 'native-plan.json', _json(plan))
    stopped = threading.Event()

    def one(job):
        if stopped.is_set():
            raise TerrainError('Acquisition arrêtée après refus réseau/quota.')
        parsed = urlsplit(job['url'])
        name = parsed.path.rsplit('/', 1)[-1]
        if (parsed.scheme != 'https' or parsed.netloc != 'data.geopf.fr'
                or not NATIVE_NAME.fullmatch(name) or parsed.query or parsed.fragment
                or parsed.path != f'/telechargement/download/RGEALTI/{name[:-3]}/{name}'
                or not 0 < job['expectedBytes'] <= plan['maxArchiveBytes']):
            raise TerrainError('Destination ou budget d’archive invalide.')
        target, receipt_path = output / name, output / (name + '.receipt.json')
        if target.exists():
            if not receipt_path.exists():
                raise TerrainError('Archive existante sans reçu, conservée.')
            old = json.loads(receipt_path.read_text())
            if old.get('request') != job or file_fingerprint(target)['sha256'] != old['raw']['sha256']:
                raise TerrainError('Archive existante différente de son reçu, conservée.')
            return old
        partial = output / (name + '.partial')
        if partial.exists():
            raise TerrainError('Archive partielle conservée ; aucun remplacement implicite.')
        digest, size = hashlib.sha256(), 0
        with urlopen(Request(job['url'], headers={'User-Agent': 'Massilia-development-source-acquisition/0.69'}), timeout=120) as response:
            if response.status != 200:
                raise TerrainError('Réponse d’archive non disponible.')
            with partial.open('xb') as stream:
                for block in iter(lambda: response.read(1024 * 1024), b''):
                    size += len(block)
                    if size > job['expectedBytes']:
                        raise TerrainError('L’archive dépasse sa taille publiée.')
                    stream.write(block)
                    digest.update(block)
            server_date = response.headers.get('Date')
        with partial.open('rb') as raw_stream:
            signature = raw_stream.read(6)
        if size != job['expectedBytes'] or signature != b'7z\xbc\xaf\x27\x1c':
            raise TerrainError('Archive tronquée ou signature 7z incorrecte ; conservée partielle.')
        # Hard-link installation is atomic and refuses to replace any existing file.
        import os
        os.link(partial, target)
        partial.unlink()
        receipt = {'schema': 'soma-metropole/ign-native-acquisition-receipt/1', 'request': job,
                   'acquiredAtUTC': datetime.now(timezone.utc).isoformat(), 'serverDate': server_date,
                   'raw': {'path': name, 'bytes': size, 'sha256': digest.hexdigest()},
                   'source': source, 'newSurvey': False, 'sourceSurveyDate': 'not supplied',
                   'crs': 'EPSG:2154', 'verticalDatum': 'NGF-IGN69', 'units': 'm'}
        _write_exact(receipt_path, _json(receipt))
        if progress:
            progress({'event': 'native-acquired', **receipt['raw']})
        return receipt

    completed, failures = [], []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(one, job): job for job in plan['jobs']}
        for future in as_completed(futures):
            try:
                completed.append(future.result())
            except Exception as error:
                if isinstance(error, HTTPError) and error.code in (401, 403, 429):
                    stopped.set()
                failures.append({'url': futures[future]['url'], 'error': str(error)})
    report = {'schema': 'soma-metropole/ign-native-acquisition/1', 'source': source,
              'complete': not failures, 'archives': sorted(completed, key=lambda r: r['raw']['path']),
              'failures': sorted(failures, key=lambda r: r['url']), 'newSurvey': False}
    _write_exact(output / 'native-acquisition.json', _json(report))
    return report


def import_native_archive(archive, archive_receipt, boundary_path, output, *,
                          max_extracted_bytes=2 * 1024**3, selection_buffer_m=365):
    """Extract target native nodes offline, retaining ASC and unchanged GeoTIFF derivatives.

    365 m covers any corner of a 250 m cell intersecting the boundary plus the
    5 m halo and bilinear neighbour. It does not enlarge the declared territory.
    """
    try:
        import numpy as np
        import py7zr
        import rasterio
        from pyproj import Transformer
        from shapely.geometry import box, shape
        from shapely.ops import transform, unary_union
    except ImportError as error:
        raise TerrainError('Py7zr, Rasterio, Numpy, Pyproj et Shapely sont requis pour l’import natif.') from error
    archive, output = Path(archive), Path(output)
    receipt = json.loads(Path(archive_receipt).read_text())
    fingerprint = file_fingerprint(archive)
    if (not NATIVE_NAME.fullmatch(archive.name) or fingerprint['sha256'] != receipt['raw']['sha256']
            or fingerprint['bytes'] != receipt['raw']['bytes'] or receipt.get('crs') != 'EPSG:2154'
            or receipt.get('verticalDatum') != 'NGF-IGN69' or receipt.get('units') != 'm'):
        raise TerrainError('Archive native différente du reçu ou géoréférence non déclarée.')
    boundary = projected_boundary(boundary_path)
    document = json.loads(Path(boundary_path).read_text())
    features = document.get('features', [document])
    region = unary_union([shape(feature.get('geometry', feature)) for feature in features])
    region = transform(Transformer.from_crs(4326, 2154, always_xy=True).transform, region).buffer(selection_buffer_m)
    manifest_path = output / (archive.name + '.import.json')
    if manifest_path.exists():
        old = json.loads(manifest_path.read_text())
        if (old.get('archive', {}).get('sha256') != fingerprint['sha256']
                or old.get('boundary', {}).get('file', {}).get('sha256') != boundary['file']['sha256']
                or old.get('selectionBufferM') != selection_buffer_m):
            raise TerrainError('Un import différent existe déjà ; conservé.')
        for item in old['sourceFiles'] + old['rasters']:
            if file_fingerprint(output / item['path'])['sha256'] != item['sha256']:
                raise TerrainError('Un fichier importé diffère de son reçu ; conservé.')
        return old
    output.mkdir(parents=True, exist_ok=True)
    target = output / 'extracted'
    selected, inventory = [], []
    with py7zr.SevenZipFile(archive) as compressed:
        for item in compressed.list():
            member = PurePosixPath(item.filename)
            if member.is_absolute() or '..' in member.parts or '\\' in item.filename:
                raise TerrainError('Chemin dangereux dans l’archive ; aucune extraction.')
            if item.is_directory:
                continue
            if item.filename.lower().endswith('.asc'):
                matched = NATIVE_NODE.fullmatch(member.name)
                if not matched:
                    raise TerrainError('Nom de dalle native inattendu.')
                x, north = (int(v) * 1000 for v in matched.groups())
                if not region.intersects(box(x - 2.5, north - 4997.5, x + 4997.5, north + 2.5)):
                    continue
            if item.uncompressed < 0 or (target / item.filename).exists():
                raise TerrainError('Extraction existante ou taille invalide ; aucun remplacement.')
            selected.append(item.filename)
            inventory.append({'path': item.filename, 'bytes': item.uncompressed, 'crc32': item.crc32})
        if not selected or sum(item['bytes'] for item in inventory) > max_extracted_bytes:
            raise TerrainError('Extraction native vide ou hors budget.')
        compressed.extract(path=target, targets=selected)
    files, rasters = [], []
    # The archive CRCs are checked by py7zr; SHA256 receipts bind every selected
    # source file and derivative. ASC NoData remains a sentinel, never a height.
    for item in inventory:
        path = target / item['path']
        if not path.is_file() or path.is_symlink() or path.stat().st_size != item['bytes']:
            raise TerrainError('Fichier extrait différent de son inventaire.')
        source_record = {**file_fingerprint(path), 'path': path.relative_to(output).as_posix()}
        files.append(source_record)
        if path.suffix.lower() != '.asc':
            continue
        matched = NATIVE_NODE.fullmatch(path.name)
        expected_node = tuple(int(v) * 1000 for v in matched.groups())
        with rasterio.open(path) as source:
            if (source.count != 1 or source.width != 1000 or source.height != 1000
                    or source.res != (5, 5) or source.transform.b or source.transform.d
                    or source.transform.a <= 0 or source.transform.e >= 0 or source.nodata != -99999
                    or tuple(source.xy(0, 0)) != expected_node
                    or (source.crs is not None and source.crs.to_epsg() != 2154)):
                raise TerrainError('Grille native inattendue : nœuds, orientation, pas ou NoData.')
            values = source.read(1).astype('<f4')
            present = values[values != source.nodata]
            if (not np.isfinite(present).all() or (present.size and (present.min() < -500 or present.max() > 9000))):
                raise TerrainError('Altitudes natives invalides ; aucune correction implicite.')
            derivative = output / 'normalised' / archive.stem / (path.stem + '.tif')
            if derivative.exists():
                raise TerrainError('GeoTIFF dérivé existant sans reçu final, conservé.')
            derivative.parent.mkdir(parents=True, exist_ok=True)
            with rasterio.open(derivative, 'w', driver='GTiff', width=1000, height=1000, count=1,
                               dtype='float32', crs='EPSG:2154', transform=source.transform, nodata=-99999,
                               tiled=True, blockxsize=256, blockysize=256, compress='deflate', predictor=3, zlevel=4) as result:
                result.write(values, 1)
                result.set_band_unit(1, 'm')
                result.update_tags(VERTICAL_DATUM='NGF-IGN69', SOURCE_ASC_SHA256=source_record['sha256'],
                                   SOURCE_ARCHIVE_SHA256=fingerprint['sha256'], SOURCE_EDITION=archive.stem,
                                   SAMPLING='Native 5m MNT nodes; unchanged numerical pixels',
                                   SOURCE_CRS_DECLARATION='Official archive LAMB93-IGN69; catalogue EPSG:2154',
                                   SURVEY_DATE='Not supplied')
        with rasterio.open(derivative) as restored:
            if restored.crs.to_epsg() != 2154 or restored.read(1).astype('<f4').tobytes() != values.tobytes():
                raise TerrainError('La normalisation a modifié les nœuds natifs.')
            bounds = list(restored.bounds)
        rasters.append({**file_fingerprint(derivative), 'path': derivative.relative_to(output).as_posix(),
                        'sourceASC': source_record, 'nativeStepM': 5, 'validNodes': int(present.size),
                        'noDataNodes': int(values.size - present.size), 'boundsL93': bounds,
                        'crs': 'EPSG:2154', 'verticalDatum': 'NGF-IGN69', 'units': 'm',
                        'normalisationChangesValues': False})
    report = {'schema': 'soma-metropole/ign-native-import/1', 'archive': fingerprint,
              'archiveReceipt': file_fingerprint(archive_receipt), 'source': receipt.get('source', {}),
              'boundary': boundary, 'selectionBufferM': selection_buffer_m, 'nativeStepM': 5,
              'sourceFiles': files, 'rasters': rasters, 'newSurvey': False,
              'sourceSurveyDate': 'not supplied', 'sourceEdition': archive.stem,
              'crs': 'EPSG:2154', 'verticalDatum': 'NGF-IGN69', 'units': 'm'}
    if receipt.get('testOnly'):
        report['testOnly'] = True
    _write_exact(manifest_path, _json(report))
    return report


def fetch_plan(plan, output, *, workers=2, progress=None):
    """Fetch bounded requests with at most two workers; verify before reuse."""
    if workers not in (1, 2) or isinstance(workers, bool):
        raise TerrainError('Un ou deux travailleurs réseau sont permis.')
    if (plan.get('schema') != 'soma-metropole/ign-wms-acquisition-plan/1'
            or plan.get('stepM') not in (1, 5, 25) or plan.get('crs') != 'EPSG:2154'
            or plan.get('units') != 'm' or plan.get('verticalDatum') != 'NGF-IGN69'):
        raise TerrainError('Contrat du plan d’acquisition invalide.')
    total, identifiers = 0, set()
    for job in plan['requests']:
        width, height = job.get('width'), job.get('height')
        if (not isinstance(width, int) or not isinstance(height, int)
                or isinstance(width, bool) or isinstance(height, bool)
                or not 1 <= width <= 5010 or not 1 <= height <= 5010
                or not re.fullmatch(r'r\d+-c\d+', job.get('id', '')) or job['id'] in identifiers):
            raise TerrainError('Dimensions ou identifiant de requête invalides.')
        identifiers.add(job['id'])
        size = width * height * 4
        if size > plan['maxResponseBytes']:
            raise TerrainError('Une requête dépasse le budget de réponse.')
        total += size
    if total != plan['rawBytes'] or total > plan['maxTotalBytes']:
        raise TerrainError('Le plan dépasse son budget total ou son décompte est incohérent.')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    caps = _get_metadata(CAPABILITIES, output / 'capabilities.xml', validate_capabilities)
    source = _get_metadata(CATALOGUE, output / 'catalogue.xml', validate_catalogue)
    for job in plan['requests']:
        if job['width'] > caps['maxWidth'] or job['height'] > caps['maxHeight']:
            raise TerrainError('Une requête dépasse les limites actuellement publiées par le service.')
    _write_exact(output / 'plan.json', _json(plan))
    stopped = threading.Event()

    def one(job):
        if stopped.is_set():
            raise TerrainError('Acquisition arrêtée après refus réseau/quota ; aucune tentative de contournement.')
        if urlsplit(job['url']).scheme != 'https' or urlsplit(job['url']).netloc != 'data.geopf.fr':
            raise TerrainError('Destination d’acquisition non officielle.')
        expected = job['width'] * job['height'] * 4
        raw_path, tif_path = output / (job['id'] + '.bil'), output / (job['id'] + '.tif')
        raw_receipt = output / (job['id'] + '.raw.receipt.json')
        receipt_path = output / (job['id'] + '.receipt.json')
        if receipt_path.exists():
            old = json.loads(receipt_path.read_text())
            if old.get('request') != job or file_fingerprint(raw_path)['sha256'] != old['raw']['sha256'] or file_fingerprint(tif_path)['sha256'] != old['normalised']['sha256']:
                raise TerrainError('Une acquisition existante diffère de son reçu ; aucun remplacement.')
            return old
        if raw_path.exists():
            if not raw_receipt.exists():
                raise TerrainError('BIL existant sans reçu d’acquisition, conservé sans remplacement.')
            raw_record = json.loads(raw_receipt.read_text())
            if raw_record.get('request') != job or file_fingerprint(raw_path)['sha256'] != raw_record['raw']['sha256']:
                raise TerrainError('BIL existant différent de son reçu, conservé.')
        else:
            partial = output / (job['id'] + '.bil.partial')
            if partial.exists():
                raise TerrainError('Réponse partielle conservée ; choisir un nouveau dossier pour une nouvelle acquisition.')
            digest, size = hashlib.sha256(), 0
            with urlopen(Request(job['url'], headers={'User-Agent': 'Massilia-development-source-acquisition/0.69'}), timeout=120) as response:
                kind = response.headers.get('Content-Type', '')
                if response.status != 200 or not kind.startswith('image/x-bil'):
                    raise TerrainError(f'Le service ne renvoie pas de BIL numérique : HTTP {response.status}, {kind}.')
                with partial.open('xb') as stream:
                    for block in iter(lambda: response.read(1024 * 1024), b''):
                        size += len(block)
                        if size > expected or size > plan['maxResponseBytes']:
                            raise TerrainError('Réponse au-delà du nombre d’octets attendu.')
                        digest.update(block)
                        stream.write(block)
                if size != expected:
                    raise TerrainError('Réponse BIL tronquée.')
                server_date = response.headers.get('Date')
            # Exclusive installation preserves any existing user file.
            with raw_path.open('xb') as target, partial.open('rb') as source_stream:
                for block in iter(lambda: source_stream.read(1024 * 1024), b''):
                    target.write(block)
            partial.unlink()
            raw_record = {'request': job, 'acquiredAtUTC': datetime.now(timezone.utc).isoformat(),
                          'serverDate': server_date,
                          'raw': {'name': raw_path.name, 'bytes': size, 'sha256': digest.hexdigest(),
                                  'encoding': 'float32-little-endian-bil', 'nodata': -99999.0}}
            _write_exact(raw_receipt, _json(raw_record))
        derived = normalise_bil(raw_path, tif_path, job, plan['stepM'], max_response_bytes=plan['maxResponseBytes'])
        receipt = {'schema': 'soma-metropole/ign-wms-acquisition-receipt/1', **raw_record, **derived,
                   'source': source, 'sourceSurveyDate': 'not supplied', 'newSurvey': False}
        _write_exact(receipt_path, _json(receipt))
        if progress:
            progress({'event': 'acquired', 'id': job['id'], 'rawBytes': raw_record['raw']['bytes'], **derived['statistics']})
        return receipt

    completed, failures = [], []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(one, job): job for job in plan['requests']}
        for future in as_completed(futures):
            job = futures[future]
            try:
                completed.append(future.result())
            except Exception as error:
                if isinstance(error, HTTPError) and error.code in (401, 403, 429):
                    stopped.set()
                failures.append({'id': job['id'], 'error': str(error)})
                if progress:
                    progress({'event': 'failure', **failures[-1]})
    report = {'schema': 'soma-metropole/ign-wms-acquisition/1', 'source': source, 'capabilities': caps,
              'plan': 'plan.json', 'stepM': plan['stepM'], 'crs': 'EPSG:2154',
              'verticalDatum': 'NGF-IGN69', 'units': 'm', 'newSurvey': False,
              'completed': len(completed), 'requested': len(plan['requests']), 'complete': not failures,
              'runtimeEligible': False,
              'coastalNoDataAssessment': 'Not assessed; numerical-range validation cannot exclude plausible sentinel mixtures.',
              'receipts': sorted(completed, key=lambda item: item['request']['id']),
              'failures': sorted(failures, key=lambda item: item['id'])}
    _write_exact(output / 'acquisition.json', _json(report))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('plan', 'fetch', 'native-plan', 'native-fetch', 'native-import'))
    parser.add_argument('--boundary', required=True, type=Path)
    parser.add_argument('--boundary-sha256')
    parser.add_argument('--step', required=True, type=int, choices=(1, 5, 25))
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--origin', type=float, nargs=2, default=ORIGIN)
    parser.add_argument('--chunk', type=int, default=4096)
    parser.add_argument('--max-response-bytes', type=int, default=MAX_RESPONSE)
    parser.add_argument('--max-total-bytes', type=int, default=MAX_TOTAL)
    parser.add_argument('--workers', type=int, choices=(1, 2), default=2)
    parser.add_argument('--native-feed', action='append', type=Path,
                        help='flux ATOM d’une édition native conservé localement (répétable)')
    parser.add_argument('--department', action='append',
                        help='code département natif sur trois chiffres ; défaut AMP : 013, 083, 084')
    parser.add_argument('--archive', action='append', type=Path)
    parser.add_argument('--archive-receipt', action='append', type=Path)
    parser.add_argument('--max-archive-bytes', type=int, default=1024**3)
    parser.add_argument('--max-extracted-bytes', type=int, default=2 * 1024**3)
    args = parser.parse_args()
    try:
        boundary = projected_boundary(args.boundary, args.boundary_sha256)
        if args.command.startswith('native-'):
            if args.step != 5:
                raise TerrainError('Ce chemin natif importe uniquement le produit 5 m annoncé, sans sur-échantillonnage.')
            if args.command == 'native-import':
                if not args.archive or not args.archive_receipt or len(args.archive) != len(args.archive_receipt):
                    raise TerrainError('Fournir chaque --archive et son --archive-receipt correspondant, dans le même ordre.')
                reports = [import_native_archive(archive, receipt, args.boundary, args.output,
                                                 max_extracted_bytes=args.max_extracted_bytes)
                           for archive, receipt in zip(args.archive, args.archive_receipt)]
                print(json.dumps({'imports': len(reports), 'rasters': sum(len(r['rasters']) for r in reports),
                                  'output': str(args.output)}, ensure_ascii=False), flush=True)
                return 0
            feeds = args.native_feed
            if not feeds:
                if args.command == 'native-plan':
                    raise TerrainError('Le plan natif est hors réseau : fournir les flux ATOM locaux avec --native-feed.')
                feeds = discover_native_feeds(args.department or ('013', '083', '084'), args.output)
            plan = native_plan(boundary, feeds, max_archive_bytes=args.max_archive_bytes,
                               max_total_bytes=args.max_total_bytes)
            _write_exact(args.output / 'native-plan.json', _json(plan))
            if args.command == 'native-plan':
                print(json.dumps({'manifest': str(args.output / 'native-plan.json'),
                                  'archives': len(plan['jobs']), 'rawBytes': plan['totalBytes']}), flush=True)
                return 0
            report = fetch_native_archives(plan, args.output, workers=args.workers,
                                          progress=lambda value: print(json.dumps(value, ensure_ascii=False), flush=True))
            print(json.dumps({'manifest': str(args.output / 'native-acquisition.json'),
                              'archives': len(report['archives']), 'complete': report['complete']}), flush=True)
            return 0 if report['complete'] else 1
        plan = make_plan(boundary, step=args.step, chunk=args.chunk, origin=args.origin,
                         max_response_bytes=args.max_response_bytes, max_total_bytes=args.max_total_bytes)
        _write_exact(args.output / 'plan.json', _json(plan))
        if args.command == 'plan':
            result = {'manifest': str(args.output / 'plan.json'), 'requests': len(plan['requests']),
                      'nodes': plan['nodes'], 'rawBytes': plan['rawBytes']}
        else:
            report = fetch_plan(plan, args.output, workers=args.workers,
                                progress=lambda value: print(json.dumps(value, ensure_ascii=False), flush=True))
            result = {'manifest': str(args.output / 'acquisition.json'),
                      'completed': report['completed'], 'requested': report['requested'], 'complete': report['complete']}
            print(json.dumps(result, ensure_ascii=False), flush=True)
            return 0 if report['complete'] else 1
        print(json.dumps(result, ensure_ascii=False), flush=True)
        return 0
    except (TerrainError, OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f'Acquisition terrain impossible : {error}\n')


if __name__ == '__main__':
    raise SystemExit(main())
