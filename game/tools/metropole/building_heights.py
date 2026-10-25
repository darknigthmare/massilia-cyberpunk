#!/usr/bin/env python3
"""Conservatively match local IGN BD TOPO heights to prepared OSM footprints.

This optional GIS tool performs no network acquisition. A verified local IGN
GeoJSON and an explicit EPSG:2154/metres/NGF-IGN69 receipt are prerequisites.
Only declared relative HAUTEUR and ground-reference fields are used; an absolute
roof Z coordinate is never silently converted into a building height.

Example receipt fields (change them explicitly for another IGN export schema):
  {"sha256":"<actual file SHA256>","license":"Licence Ouverte 2.0",
   "date":"2026-09-23","crs":"EPSG:2154","units":"m",
   "verticalDatum":"NGF-IGN69",
   "fields":{"ignId":"CLEABS","height":"HAUTEUR","groundAltitude":"Z_MIN_SOL"}}
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import tempfile

SCHEMA = 'soma-metropole/building-height-matches/1'
MIN_IOU = .90
MIN_MARGIN = .15
FALSE = {'', 'no', 'false', '0'}
HASH = re.compile(r'[a-f0-9]{64}')
IDENTITY = re.compile(r'osm/(?:way|relation)/[1-9]\d*')
DEFAULT_FIELDS = {'ignId': 'CLEABS', 'height': 'HAUTEUR', 'groundAltitude': 'Z_MIN_SOL'}
DEFAULT_NODATA = (-9999, -99999, 9999, 99999)


class HeightMatchError(ValueError):
    """Unverifiable source evidence must not create a height reference."""


@dataclass(frozen=True)
class MatchLimits:
    max_records: int = 100_000
    max_osm_buildings: int = 500_000
    max_ign_features: int = 200_000
    max_fragments_per_building: int = 4096
    max_geometry_coordinates: int = 100_000
    max_candidates_per_building: int = 512
    max_comparisons: int = 10_000_000
    max_file_bytes: int = 512 * 1024 * 1024
    max_tile_bytes: int = 16 * 1024 * 1024
    max_building_bytes: int = 32 * 1024 * 1024
    max_spool_bytes: int = 4 * 1024 * 1024 * 1024

    def validate(self):
        if any(not isinstance(value, int) or isinstance(value, bool) or value <= 0 for value in vars(self).values()):
            raise HeightMatchError('All processing budgets must be positive integers.')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_sha256(path):
    checksum = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            checksum.update(chunk)
    return checksum.hexdigest()


def binding_key(canonical_id, geometry_sha256, source_sha256):
    if not isinstance(canonical_id, str) or not IDENTITY.fullmatch(canonical_id):
        raise HeightMatchError('A canonical OSM way/relation identity is required.')
    if any(not isinstance(value, str) or not HASH.fullmatch(value) for value in (geometry_sha256, source_sha256)):
        raise HeightMatchError('Geometry and source SHA256 bindings are required.')
    return canonical([source_sha256, canonical_id, geometry_sha256])


def _gis():
    try:
        import shapely
        from shapely.geometry import Polygon, box, shape
        from shapely.ops import unary_union
        from shapely.strtree import STRtree
    except ImportError as error:
        raise RuntimeError('Height matching needs the optional geodata environment with Shapely 2.1.2.') from error
    if int(shapely.__version__.split('.')[0]) < 2:
        raise RuntimeError('Shapely 2 is required for the bounded STRtree query interface.')
    return Polygon, box, shape, unary_union, STRtree


def _read_json(path, maximum):
    path = Path(path)
    if path.stat().st_size > maximum:
        raise HeightMatchError('Source JSON exceeds its byte budget; partition the source before matching.')
    try:
        return json.loads(path.read_text(encoding='utf-8'), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except (UnicodeError, ValueError) as error:
        raise HeightMatchError('Source JSON is invalid or contains a non-finite literal.') from error


def _is_lambert93(value):
    return str(value).strip().upper() in {
        'EPSG:2154', 'URN:OGC:DEF:CRS:EPSG::2154',
        'HTTP://WWW.OPENGIS.NET/DEF/CRS/EPSG/0/2154',
    }


def _receipt(receipt, ign_path):
    if not isinstance(receipt, dict):
        raise HeightMatchError('An IGN source receipt is required.')
    for field in ('license', 'date'):
        value = receipt.get(field)
        if not isinstance(value, str) or not value.strip() or value.strip().lower() in {'unknown', 'inconnue', 'à déclarer'}:
            raise HeightMatchError(f'Missing declared IGN {field}.')
    try:
        timestamp = receipt['date']
        date.fromisoformat(timestamp) if len(timestamp) == 10 else datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    except ValueError as error:
        raise HeightMatchError('An ISO date or timestamp is required on the IGN receipt.') from error
    if not _is_lambert93(receipt.get('crs')) or receipt.get('units') != 'm' or receipt.get('verticalDatum') != 'NGF-IGN69':
        raise HeightMatchError('IGN CRS, units and datum must explicitly be EPSG:2154, m and NGF-IGN69.')
    expected = receipt.get('sha256')
    if not isinstance(expected, str) or not HASH.fullmatch(expected) or file_sha256(ign_path) != expected:
        raise HeightMatchError('Local IGN GeoJSON SHA256 differs from the source receipt.')
    fields = receipt.get('fields', DEFAULT_FIELDS)
    if not isinstance(fields, dict) or set(fields) != set(DEFAULT_FIELDS) or any(not isinstance(value, str) or not value or len(value) > 100 for value in fields.values()):
        raise HeightMatchError('Explicit ignId, height and groundAltitude field names are required.')
    nodata = receipt.get('noData', list(DEFAULT_NODATA))
    if not isinstance(nodata, list) or len(nodata) > 100 or any(not isinstance(value, (str, int, float)) or isinstance(value, bool) for value in nodata):
        raise HeightMatchError('The NoData declaration must be a bounded list of scalar values.')
    return {key: receipt[key] for key in ('sha256', 'license', 'date', 'crs', 'units', 'verticalDatum')} | {
        'id': receipt.get('id'), 'fields': dict(fields), 'noData': list(nodata),
        'sourceFileIntegrityVerified': True, 'independentSourceAuthenticityVerified': False,
    }


def _coordinate_count(value, maximum, depth=0):
    if depth > 8 or not isinstance(value, (list, tuple)):
        raise HeightMatchError('Invalid polygon coordinate structure.')
    if value and isinstance(value[0], (int, float)):
        if len(value) not in (2, 3) or any(isinstance(n, bool) or not isinstance(n, (int, float)) or not math.isfinite(n) for n in value):
            raise HeightMatchError('Polygon coordinates must be finite numeric pairs/triples.')
        return 1
    count = 0
    for child in value:
        count += _coordinate_count(child, maximum, depth + 1)
        if count > maximum:
            raise HeightMatchError('Polygon coordinate budget exceeded.')
    return count


def _metric_geometry(value, limits):
    _, _, shape, _, _ = _gis()
    if not isinstance(value, dict) or value.get('type') not in {'Polygon', 'MultiPolygon'}:
        raise HeightMatchError('A Polygon/MultiPolygon footprint is required.')
    _coordinate_count(value.get('coordinates'), limits.max_geometry_coordinates)
    polygons = [value['coordinates']] if value['type'] == 'Polygon' else value['coordinates']
    if not polygons or any(not polygon or any(len(ring) < 4 or ring[0] != ring[-1] for ring in polygon) for polygon in polygons):
        raise HeightMatchError('GeoJSON footprint rings must be explicitly closed; no closing edge was invented.')
    geometry = shape(value)
    if geometry.is_empty or not geometry.is_valid or not math.isfinite(geometry.area) or geometry.area <= .01:
        raise HeightMatchError('Invalid, empty or degenerate source footprint; no repair was applied.')
    # Reject obvious longitude/latitude or local-game-coordinate input even if
    # its metadata was accidentally labelled Lambert-93. No reprojection occurs.
    west, south, east, north = geometry.bounds
    if not (-500_000 <= west < east <= 1_500_000 and 6_000_000 <= south < north <= 7_300_000):
        raise HeightMatchError('Footprint is outside the plausible EPSG:2154 France domain.')
    return geometry


def _field(properties, name):
    found = [value for key, value in properties.items() if str(key).casefold() == name.casefold()]
    if len(found) != 1:
        return None, 'missing-or-ambiguous-ign-field:' + name
    return found[0], None


def _number(value, nodata):
    if value is None or isinstance(value, bool) or isinstance(value, (list, dict)):
        return None
    if any(str(value).strip().casefold() == str(missing).strip().casefold() for missing in nodata):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    for missing in nodata:
        try:
            if number == float(missing):
                return None
        except (TypeError, ValueError):
            pass
    return number


def _ign_rows(path, receipt, limits):
    _, box, shape, _, STRtree = _gis()
    source = _read_json(path, limits.max_file_bytes)
    if not isinstance(source, dict) or source.get('type') != 'FeatureCollection' or not isinstance(source.get('features'), list):
        raise HeightMatchError('A local IGN GeoJSON FeatureCollection is required.')
    declared_crs = source.get('crs')
    if declared_crs is not None and not (isinstance(declared_crs, dict) and isinstance(declared_crs.get('properties'), dict) and _is_lambert93(declared_crs['properties'].get('name'))):
        raise HeightMatchError('GeoJSON CRS contradicts the EPSG:2154 source receipt.')
    if len(source['features']) > limits.max_ign_features:
        raise HeightMatchError('IGN feature budget exceeded; match smaller source packages.')
    rows, identities = [], set()
    for index, feature in enumerate(source['features']):
        if not isinstance(feature, dict) or feature.get('type') != 'Feature' or not isinstance(feature.get('properties'), dict):
            raise HeightMatchError('Malformed IGN GeoJSON feature.')
        properties = feature['properties']
        values, errors = {}, []
        for target, field in receipt['fields'].items():
            value, error = _field(properties, field)
            values[target] = value
            if error:
                errors.append(error)
        identity = values['ignId']
        if not isinstance(identity, str) or not identity.strip() or len(identity) > 200:
            errors.append('missing-or-invalid-ign-identity')
            identity = None
        elif identity in identities:
            raise HeightMatchError('Duplicate IGN identity; source ambiguity must be resolved before matching.')
        else:
            identities.add(identity)
        try:
            geometry = _metric_geometry(feature.get('geometry'), limits)
            geometry_error = None
        except (HeightMatchError, ValueError, TypeError) as error:
            # Keep invalid neighbours as spatial blockers. Dropping one could
            # make a nearby, weaker candidate look uniquely matchable.
            try:
                invalid = shape(feature.get('geometry'))
                bounds = invalid.bounds
                if invalid.is_empty or len(bounds) != 4 or not all(math.isfinite(n) for n in bounds):
                    raise ValueError('no finite envelope')
                geometry = box(*bounds)
            except Exception as failure:
                raise HeightMatchError('IGN geometry has no verifiable spatial envelope.') from failure
            geometry_error = str(error)
        height = _number(values['height'], receipt['noData'])
        ground = _number(values['groundAltitude'], receipt['noData'])
        if height is None or not .05 < height <= 1000:
            errors.append('missing-or-invalid-relative-ign-height')
        if ground is None or not -1000 <= ground <= 9000:
            errors.append('missing-or-invalid-ign-ground-reference')
        rows.append({'ignId': identity, 'featureIndex': index, 'geometry': geometry,
                     'geometryError': geometry_error, 'errors': sorted(set(errors)),
                     'height': height, 'groundAltitude': ground})
    return rows, STRtree([row['geometry'] for row in rows])


def _active(value):
    return value is not None and str(value).strip().lower() not in FALSE


def _osm_priority(properties):
    if _active(properties.get('building:part')):
        return 'active-osm-building-part'
    if str(properties.get('building', '')).strip().lower() == 'roof':
        return 'open-osm-roof-structure'
    # Even an unusable nonempty declaration is withheld, rather than silently
    # replacing a source author's conflicting or malformed explicit height.
    if properties.get('height') is not None and str(properties['height']).strip():
        return 'explicit-osm-height-preserved'
    try:
        if float(properties.get('layer', 0) or 0) != 0:
            return 'non-ground-osm-structure'
    except (ValueError, TypeError):
        return 'non-ground-osm-structure'
    if str(properties.get('location', '')).strip().lower() in {'underground', 'underwater', 'overground'}:
        return 'non-ground-osm-structure'
    minimum = properties.get('min_height', '0')
    minimum_level = properties.get('building:min_level', '0')
    try:
        if float(minimum or 0) != 0 or float(minimum_level or 0) != 0:
            return 'elevated-or-unknown-osm-base'
    except (ValueError, TypeError):
        return 'elevated-or-unknown-osm-base'
    return None


def _spool(records, db, limits):
    db.executescript('''CREATE TABLE objects(binding TEXT PRIMARY KEY,identity TEXT UNIQUE,geometry_sha TEXT,
                        source_sha TEXT,properties TEXT);
                       CREATE TABLE fragments(binding TEXT,cell_id TEXT,cell_sha TEXT,payload TEXT,
                        payload_sha TEXT, UNIQUE(binding,cell_id,payload_sha));''')
    sources, cells = set(), set()
    count, spooled_bytes = 0, 0
    for record_index, record in enumerate(records):
        if record_index >= limits.max_records:
            raise HeightMatchError('OSM record budget exceeded.')
        if not isinstance(record, dict) or record.get('v53Synthetic') or record.get('v50Synthetic') or record.get('testOnly'):
            raise HeightMatchError('Only real, prepared source records can provide building footprints.')
        source_receipt = record.get('sourceReceipt')
        if not isinstance(source_receipt, dict):
            raise HeightMatchError('OSM source receipt metadata must be an object.')
        source_sha = source_receipt.get('sha256')
        if not isinstance(source_sha, str) or not HASH.fullmatch(source_sha):
            raise HeightMatchError('Every OSM record needs its source PBF SHA256 binding.')
        sources.add(source_sha)
        if len(sources) > 1:
            raise HeightMatchError('Match one OSM snapshot at a time; source snapshots must not be mixed.')
        cell_id, cell_sha = record.get('cellId'), record.get('contentSHA256')
        if not isinstance(cell_id, str) or cell_id in cells or not isinstance(cell_sha, str) or not HASH.fullmatch(cell_sha):
            raise HeightMatchError('OSM cell identity/content binding is missing or duplicated.')
        cells.add(cell_id)
        collection = record.get('featureCollection')
        features = collection.get('features') if isinstance(collection, dict) else None
        if not isinstance(features, list):
            raise HeightMatchError('Prepared OSM feature collection missing.')
        for feature in features:
            if not isinstance(feature, dict) or not isinstance(feature.get('properties'), dict):
                raise HeightMatchError('Prepared OSM feature/properties must be objects.')
            p = feature['properties']
            if p.get('soma:layer') != 'buildings':
                continue
            identity = p.get('canonical_id') or feature.get('id')
            geometry_sha = p.get('soma:geometry_sha256')
            key = binding_key(identity, geometry_sha, source_sha)
            properties = canonical({name: value for name, value in p.items() if name not in {'soma:metricGeometry', 'soma:mesh53'}})
            previous = db.execute('SELECT binding,properties FROM objects WHERE identity=?', (identity,)).fetchone()
            if previous is None:
                count += 1
                if count > limits.max_osm_buildings:
                    raise HeightMatchError('OSM building budget exceeded; match smaller source packages.')
                db.execute('INSERT INTO objects VALUES(?,?,?,?,?)', (key, identity, geometry_sha, source_sha, properties))
                spooled_bytes += len(properties.encode())
            elif previous != (key, properties):
                raise HeightMatchError(f'Conflicting source fragments for {identity}.')
            meshes = p.get('soma:mesh53')
            if not isinstance(meshes, list) or any(not isinstance(mesh, dict) for mesh in meshes):
                raise HeightMatchError('Prepared OSM source walls are required for footprint completeness.')
            payload = {'geometry': p.get('soma:metricGeometry'), 'meshes': [
                {'ringsL93': mesh.get('ringsL93'), 'wallsL93': mesh.get('wallsL93')} for mesh in meshes]}
            text = canonical(payload)
            if len(text.encode()) > limits.max_tile_bytes:
                raise HeightMatchError('OSM fragment exceeds its geometry byte budget.')
            cursor = db.execute('INSERT OR IGNORE INTO fragments VALUES(?,?,?,?,?)',
                                (key, cell_id, cell_sha, text, hashlib.sha256(text.encode()).hexdigest()))
            if cursor.rowcount:
                spooled_bytes += len(text.encode())
            if spooled_bytes > limits.max_spool_bytes:
                raise HeightMatchError('SQLite source-byte budget exceeded; no partial report is published.')
    db.commit()
    if not sources:
        raise HeightMatchError('At least one prepared OSM source record is required.')
    return next(iter(sources)), count, len(cells)


def _joined_osm_geometry(fragments, limits):
    Polygon, _, _, union, _ = _gis()
    geometries, nodes, edges = [], defaultdict(set), set()
    coordinate_count = 0
    for fragment in fragments:
        coordinate_count += _coordinate_count(fragment.get('geometry', {}).get('coordinates'), limits.max_geometry_coordinates)
        if coordinate_count > limits.max_geometry_coordinates:
            raise HeightMatchError('Canonical OSM building coordinate budget exceeded.')
        geometry = _metric_geometry(fragment['geometry'], limits)
        mesh_geometries = []
        for mesh in fragment['meshes']:
            rings = mesh.get('ringsL93')
            if not isinstance(rings, list) or not rings:
                raise HeightMatchError('Prepared OSM rings missing.')
            for ring in rings:
                _coordinate_count(ring, limits.max_geometry_coordinates)
            polygon = Polygon(rings[0], rings[1:])
            if polygon.is_empty or not polygon.is_valid:
                raise HeightMatchError('Invalid prepared OSM footprint.')
            mesh_geometries.append(polygon)
            walls = mesh.get('wallsL93')
            if not isinstance(walls, list):
                raise HeightMatchError('Prepared OSM source walls missing.')
            for wall in walls:
                if not isinstance(wall, list) or len(wall) != 2:
                    raise HeightMatchError('Invalid prepared OSM source wall.')
                for point in wall:
                    _coordinate_count(point, limits.max_geometry_coordinates)
                a, b = (tuple(round(float(v)*10000) for v in point[:2]) for point in wall)
                if a == b:
                    continue
                edge = tuple(sorted((a, b)))
                if edge not in edges:
                    edges.add(edge); nodes[a].add(b); nodes[b].add(a)
        if not mesh_geometries or geometry.symmetric_difference(union(mesh_geometries)).area > max(.01, geometry.area*1e-8):
            raise HeightMatchError('OSM prepared mesh and metric footprint disagree.')
        geometries.append(geometry)
    if len(nodes) < 3 or any(len(neighbours) != 2 for neighbours in nodes.values()):
        raise HeightMatchError('Incomplete OSM source-wall boundary; a clipped footprint is not a complete building.')
    result = union(geometries)
    if result.is_empty or not result.is_valid:
        raise HeightMatchError('Invalid canonical OSM footprint union.')
    return result


def match_building_heights(records, ign_path, receipt, *, min_iou=MIN_IOU, min_margin=MIN_MARGIN,
                           limits=None, scratch=None):
    """Return immutable source-bound matches from verified LOCAL source files.

    OSM fragments are aggregated on disk, one canonical building is unioned at
    a time, and candidate queries/comparisons have hard budgets. Both forward
    and reciprocal IoU margins must pass. A matching file is not acquisition or
    an architectural certification.
    """
    limits = limits or MatchLimits(); limits.validate()
    if not MIN_IOU <= min_iou <= 1 or not MIN_MARGIN <= min_margin <= 1:
        raise HeightMatchError('The conservative IoU/margin policy cannot be weakened.')
    ign_path = Path(ign_path)
    if ign_path.stat().st_size > limits.max_file_bytes:
        raise HeightMatchError('IGN file exceeds its processing budget.')
    provenance = _receipt(receipt, ign_path)
    ign_rows, tree = _ign_rows(ign_path, provenance, limits)
    from shapely.errors import GEOSException
    _, _, shape, _, _ = _gis()
    rejected, provisional = [], []
    reverse = defaultdict(list)
    reverse_blocked = set()
    comparisons = 0
    with tempfile.TemporaryDirectory(prefix='massilia-heights-', dir=scratch) as temporary:
        db = sqlite3.connect(str(Path(temporary)/'footprints.sqlite'))
        try:
            source_sha, object_count, cell_count = _spool(records, db, limits)
            for key, identity, geometry_sha, osm_sha, encoded_properties in db.execute('SELECT * FROM objects ORDER BY binding'):
                binding = {'canonicalId': identity, 'geometrySHA256': geometry_sha, 'sourceSHA256': osm_sha}
                properties = json.loads(encoded_properties)
                priority = _osm_priority(properties)
                if priority and priority != 'explicit-osm-height-preserved':
                    rejected.append({**binding, 'reason': priority}); continue
                fragment_count, fragment_bytes = db.execute('SELECT COUNT(*),SUM(LENGTH(payload)) FROM fragments WHERE binding=?', (key,)).fetchone()
                if fragment_count > limits.max_fragments_per_building or (fragment_bytes or 0) > limits.max_building_bytes:
                    raise HeightMatchError('OSM canonical fragment/byte budget exceeded; no partial matching report is published.')
                fragments = db.execute('SELECT cell_id,cell_sha,payload FROM fragments WHERE binding=? ORDER BY cell_id,payload_sha', (key,)).fetchall()
                try:
                    geometry = _joined_osm_geometry([json.loads(row[2]) for row in fragments], limits)
                except (HeightMatchError, ValueError, TypeError, GEOSException) as error:
                    # An incomplete outline can still contest an IGN feature.
                    # Do not let dropping it make another footprint look unique.
                    for _, _, encoded in fragments:
                        try:
                            envelope = shape(json.loads(encoded)['geometry']).envelope
                            if not envelope.is_empty:
                                reverse_blocked.update(int(index) for index in tree.query(envelope))
                        except (ValueError, TypeError, KeyError, AttributeError, GEOSException):
                            raise HeightMatchError('Unverifiable OSM geometry has no usable spatial envelope.') from error
                    rejected.append({**binding, 'reason': 'unverifiable-osm-footprint', 'detail': str(error)}); continue
                indices = sorted(int(index) for index in tree.query(geometry))
                if len(indices) > limits.max_candidates_per_building:
                    reverse_blocked.update(indices)
                    rejected.append({**binding, 'reason': 'candidate-budget-exceeded'}); continue
                scored, invalid_neighbour = [], False
                for index in indices:
                    row = ign_rows[index]
                    if row['geometryError']:
                        if geometry.intersects(row['geometry']):
                            invalid_neighbour = True
                        continue
                    comparisons += 1
                    if comparisons > limits.max_comparisons:
                        raise HeightMatchError('Comparison budget exceeded; no partial matching report is published.')
                    try:
                        intersection = geometry.intersection(row['geometry']).area
                    except GEOSException:
                        invalid_neighbour = True
                        reverse_blocked.add(index)
                        continue
                    if intersection <= 0:
                        continue
                    iou = intersection / (geometry.area+row['geometry'].area-intersection)
                    score = {'ignIndex': index, 'iou': iou, 'osmCoverage': intersection/geometry.area,
                             'ignCoverage': intersection/row['geometry'].area}
                    scored.append(score)
                    reverse[index].append((iou, key))
                    reverse[index].sort(key=lambda value: (-value[0], value[1]))
                    del reverse[index][2:]
                if priority:
                    rejected.append({**binding, 'reason': priority}); continue
                if invalid_neighbour:
                    rejected.append({**binding, 'reason': 'unverifiable-ign-neighbour-geometry'}); continue
                scored.sort(key=lambda row: (-row['iou'], ign_rows[row['ignIndex']]['ignId'] or '', row['ignIndex']))
                if not scored or scored[0]['iou'] < min_iou:
                    rejected.append({**binding, 'reason': 'insufficient-footprint-iou', 'bestIoU': scored[0]['iou'] if scored else 0}); continue
                best = scored[0]
                runner_up = scored[1]['iou'] if len(scored) > 1 else 0
                margin = best['iou']-runner_up
                if margin < min_margin:
                    rejected.append({**binding, 'reason': 'ambiguous-ign-candidates', 'bestIoU': best['iou'], 'margin': margin}); continue
                row = ign_rows[best['ignIndex']]
                if row['errors']:
                    rejected.append({**binding, 'reason': 'unusable-ign-height-reference', 'details': row['errors']}); continue
                provisional.append({'key': key, **binding, **best, 'margin': margin, 'runnerUpIoU': runner_up,
                    'height': row['height'], 'groundAltitude': row['groundAltitude'], 'ignId': row['ignId'],
                    'cells': dict(sorted((cell, sha) for cell, sha, _ in fragments))})
        finally:
            db.close()
    matches = {}
    for row in provisional:
        if row['ignIndex'] in reverse_blocked:
            rejected.append({key: row[key] for key in ('canonicalId','geometrySHA256','sourceSHA256')} |
                            {'reason': 'unverifiable-reciprocal-osm-neighbour'})
            continue
        claims = reverse[row['ignIndex']]
        reverse_margin = claims[0][0]-(claims[1][0] if len(claims)>1 else 0)
        if claims[0][1] != row['key'] or reverse_margin < min_margin:
            rejected.append({key: row[key] for key in ('canonicalId','geometrySHA256','sourceSHA256')} |
                            {'reason': 'ambiguous-reciprocal-osm-candidates', 'reciprocalMargin': reverse_margin})
            continue
        key = row.pop('key'); row.pop('ignIndex')
        matches[key] = {**row, 'reciprocalMargin': reverse_margin, 'heightSource': 'ign-bdtopo-height',
                        'method': 'footprint-iou-unique-reciprocal', 'decision': 'accepted-conservative-match'}
    rejected.sort(key=lambda row: (row['canonicalId'], row['reason']))
    report = {'schema': SCHEMA, 'version': '0.69.0', 'crs': 'EPSG:2154', 'units': 'm', 'verticalDatum': 'NGF-IGN69',
              'sourceSHA256': source_sha, 'ignSource': provenance,
              'policy': {'minimumIoU': min_iou, 'minimumMargin': min_margin, 'minimumReciprocalMargin': min_margin,
                         'preserveExplicitOSMHeight': True, 'excludeActiveOSMParts': True,
                         'deriveHeightFromAbsoluteRoofZ': False},
              'matches': dict(sorted(matches.items())), 'rejected': rejected,
              'statistics': {'osmBuildings': object_count, 'osmCells': cell_count, 'ignFeatures': len(ign_rows),
                             'accepted': len(matches), 'rejected': len(rejected), 'comparisons': comparisons,
                             'rejectedByReason': dict(sorted(Counter(row['reason'] for row in rejected).items())),
                             'invalidIGNGeometry': sum(bool(row['geometryError']) for row in ign_rows),
                             'reciprocalBlockedIGNFeatures': len(reverse_blocked),
                             'unusableIGNReferences': sum(bool(row['errors']) for row in ign_rows)},
              'newHeightAcquisition': False, 'certifiedBuildings': 0,
              'meaning': 'Derived matches from declared local sources; not a network acquisition, metropolitan coverage or 1:1 architectural certification.'}
    report['proofSHA256'] = digest(report)
    return report


def validate_matches(report):
    """Validate saved metadata without importing optional GIS libraries."""
    if not isinstance(report, dict) or report.get('schema') != SCHEMA:
        raise HeightMatchError('Building-height match schema invalid.')
    if report.get('proofSHA256') != digest({key: value for key, value in report.items() if key != 'proofSHA256'}):
        raise HeightMatchError('Building-height match proof checksum differs.')
    if report.get('crs') != 'EPSG:2154' or report.get('units') != 'm' or report.get('verticalDatum') != 'NGF-IGN69':
        raise HeightMatchError('Saved height units/CRS/datum unknown.')
    policy = report.get('policy')
    if not isinstance(policy, dict) or any(not isinstance(policy.get(field), (int, float)) or isinstance(policy.get(field), bool) or not math.isfinite(policy[field]) or not minimum <= policy[field] <= 1
                                         for field, minimum in [('minimumIoU',MIN_IOU),('minimumMargin',MIN_MARGIN),('minimumReciprocalMargin',MIN_MARGIN)]):
        raise HeightMatchError('Saved matching policy was weakened.')
    if policy.get('preserveExplicitOSMHeight') is not True or policy.get('excludeActiveOSMParts') is not True or policy.get('deriveHeightFromAbsoluteRoofZ') is not False:
        raise HeightMatchError('Saved source-priority/relative-height policy was weakened.')
    if report.get('newHeightAcquisition') is not False or report.get('certifiedBuildings') != 0:
        raise HeightMatchError('A local matching proof cannot claim acquisition or architectural certification.')
    ign_source = report.get('ignSource')
    if not isinstance(ign_source, dict) or not isinstance(ign_source.get('sha256'), str) or not HASH.fullmatch(ign_source['sha256']) or ign_source.get('verticalDatum') != 'NGF-IGN69' or ign_source.get('units') != 'm' or not _is_lambert93(ign_source.get('crs')):
        raise HeightMatchError('Saved IGN source binding/units/datum missing.')
    matches = report.get('matches')
    if not isinstance(matches, dict) or not isinstance(report.get('sourceSHA256'), str) or not HASH.fullmatch(report['sourceSHA256']):
        raise HeightMatchError('Saved source snapshot/matches missing.')
    for key, row in matches.items():
        if not isinstance(row, dict):
            raise HeightMatchError('Saved height match must be an object.')
        if key != binding_key(row.get('canonicalId'), row.get('geometrySHA256'), row.get('sourceSHA256')) or row['sourceSHA256'] != report.get('sourceSHA256'):
            raise HeightMatchError('Saved source/geometry binding differs.')
        for field, lower, upper in (('height',.05,1000), ('groundAltitude',-1000,9000),
                                    ('iou',policy['minimumIoU'],1), ('margin',policy['minimumMargin'],1),
                                    ('reciprocalMargin',policy['minimumReciprocalMargin'],1)):
            value = row.get(field)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or not lower <= value <= upper:
                raise HeightMatchError(f'Invalid saved height evidence: {field}.')
        if row['height'] <= .05:
            raise HeightMatchError('Saved relative height must be greater than 0.05 m.')
        if not isinstance(row.get('ignId'), str) or not row['ignId']:
            raise HeightMatchError('Saved IGN identity missing.')
    return report


def _asset(base, descriptor, limits):
    if not isinstance(descriptor, dict) or descriptor.get('encoding') != 'gzip-json':
        raise HeightMatchError('A verified gzip-json vector descriptor is required.')
    relative = descriptor.get('path')
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise HeightMatchError('Vector asset paths must be relative.')
    path = (base/relative).resolve()
    if not path.is_relative_to(base.resolve()):
        raise HeightMatchError('Vector asset escapes its source package.')
    if path.stat().st_size > limits.max_file_bytes or path.stat().st_size != descriptor.get('bytes') or file_sha256(path) != descriptor.get('sha256'):
        raise HeightMatchError('Vector asset checksum/size differs from its manifest.')
    with gzip.open(path, 'rb') as stream:
        raw = stream.read(limits.max_tile_bytes+1)
    if len(raw) > limits.max_tile_bytes or len(raw) != descriptor.get('decodedBytes'):
        raise HeightMatchError('Decoded vector tile size differs or exceeds its budget.')
    return json.loads(raw)


def records_from_manifest(path, limits=None):
    limits = limits or MatchLimits()
    path = Path(path)
    manifest = _read_json(path, min(limits.max_file_bytes,64*1024*1024))
    if not isinstance(manifest, dict) or manifest.get('schema') != 'soma-metropole/vector-tiles/1' or manifest.get('crs') != 'EPSG:2154' or manifest.get('units') != 'm':
        raise HeightMatchError('Metric vector manifest required.')
    tiles = manifest.get('tiles')
    if not isinstance(tiles, list) or len(tiles) > limits.max_records:
        raise HeightMatchError('Invalid or oversized vector manifest.')
    for tile in tiles:
        if not isinstance(tile, dict):
            raise HeightMatchError('Vector tile descriptor must be an object.')
        record = _asset(path.parent, tile.get('vector'), limits)
        if record.get('cellId') != tile.get('cellId') or record.get('sourceReceipt', {}).get('sha256') != manifest.get('source', {}).get('sha256'):
            raise HeightMatchError('Vector tile identity/source differs from its manifest.')
        yield record


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--manifest', type=Path)
    source.add_argument('--records', type=Path, help='Prepared record, records array or pack v4 JSON')
    parser.add_argument('--ign', type=Path, required=True, help='Local IGN BD TOPO GeoJSON in EPSG:2154')
    parser.add_argument('--receipt', type=Path, required=True, help='Non-secret source receipt metadata')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--scratch', type=Path, help='Directory for temporary SQLite aggregation')
    parser.add_argument('--max-osm-buildings', type=int, default=MatchLimits.max_osm_buildings)
    parser.add_argument('--max-ign-features', type=int, default=MatchLimits.max_ign_features)
    parser.add_argument('--max-candidates', type=int, default=MatchLimits.max_candidates_per_building)
    parser.add_argument('--max-comparisons', type=int, default=MatchLimits.max_comparisons)
    args = parser.parse_args()
    limits = MatchLimits(max_osm_buildings=args.max_osm_buildings, max_ign_features=args.max_ign_features,
                         max_candidates_per_building=args.max_candidates, max_comparisons=args.max_comparisons)
    try:
        limits.validate()
        if args.output.exists():
            raise HeightMatchError('Output already exists; preserve it and choose a new path.')
        if args.manifest:
            records = records_from_manifest(args.manifest, limits)
        else:
            payload = _read_json(args.records, limits.max_file_bytes)
            if not isinstance(payload, (list, dict)):
                raise HeightMatchError('Prepared record, records array or pack object required.')
            records = payload if isinstance(payload, list) else payload.get('records', [payload])
        receipt = _read_json(args.receipt, 1024*1024)
        report = match_building_heights(records, args.ign, receipt, limits=limits, scratch=args.scratch)
        validate_matches(report)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        created = False
        try:
            with args.output.open('x', encoding='utf-8') as stream:
                created = True
                stream.write(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+'\n')
        except BaseException:
            if created:
                args.output.unlink(missing_ok=True)
            raise
        print(json.dumps({'output':str(args.output), **report['statistics'], 'newHeightAcquisition':False}, ensure_ascii=False))
    except (OSError, ValueError, TypeError, RuntimeError, sqlite3.Error) as error:
        parser.exit(1, f'Height matching refused: {error}\n')


if __name__ == '__main__':
    main()
