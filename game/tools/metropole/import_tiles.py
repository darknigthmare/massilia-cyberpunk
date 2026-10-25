#!/usr/bin/env python3
"""Prepare source-preserving 250 m Lambert-93 vector tiles from an OSM PBF.

This optional development tool needs osmium, Shapely, pyproj, numpy and
mapbox-earcut. It never fabricates terrain, building heights, missing ways or
administrative coverage. The normal game launcher does not import this module.
"""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import tempfile
from typing import Iterable

import mapbox_earcut
import numpy as np
import osmium
from pyproj import Transformer
import shapely
from shapely.geometry import GeometryCollection, LineString, MultiLineString, MultiPolygon, Point, Polygon, box, mapping, shape
from shapely.geometry.polygon import orient
from shapely.ops import transform

ORIGIN = (892951.6480966414, 6247274.566415883)
CELL_SIZE = 250
SCHEMA = 'soma-metropole/vector-tiles/1'
CELL_SCHEMA = 'soma-massilia/geodata-cell/4'
FORBIDDEN = {'__proto__', 'prototype', 'constructor'}
FALSE_VALUES = {'', 'no', 'false', '0'}
TO_METRIC = Transformer.from_crs('EPSG:4326', 'EPSG:2154', always_xy=True)
TO_WGS84 = Transformer.from_crs('EPSG:2154', 'EPSG:4326', always_xy=True)


class ImportFailure(ValueError):
    """A preparation failure must not publish a partial tile directory."""


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value) -> str:
    return hashlib.sha256(canonical_json(value).encode('utf-8')).hexdigest()


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(data)
    return h.hexdigest()


def cell_id(x: int, y: int) -> str:
    """Positive grid Y runs south, as in the existing game."""
    if -2 <= x <= 2 and -2 <= y <= 2:
        return f'V52-MC-{y+3}{x+3}'
    return f'V52-MC-{"E" if x >= 0 else "W"}{abs(x):02d}-{"S" if y >= 0 else "N"}{abs(y):02d}'


def cell_bounds(x: int, y: int) -> tuple[float, float, float, float]:
    e = ORIGIN[0] + x * CELL_SIZE
    n = ORIGIN[1] - y * CELL_SIZE
    return (e - 125, n - 125, e + 125, n + 125)


def bounds_wgs84(bounds) -> list[float]:
    corners = [TO_WGS84.transform(e, n) for e in (bounds[0], bounds[2]) for n in (bounds[1], bounds[3])]
    return [min(p[0] for p in corners), min(p[1] for p in corners), max(p[0] for p in corners), max(p[1] for p in corners)]


def grid_cells(bounds) -> Iterable[tuple[int, int]]:
    x0 = math.floor((bounds[0] - ORIGIN[0] + 125) / CELL_SIZE)
    x1 = math.floor((bounds[2] - ORIGIN[0] + 125) / CELL_SIZE)
    y0 = math.floor((ORIGIN[1] - bounds[3] + 125) / CELL_SIZE)
    y1 = math.floor((ORIGIN[1] - bounds[1] + 125) / CELL_SIZE)
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            yield x, y


def truthy_tag(value) -> bool:
    return str(value or '').strip().lower() not in FALSE_VALUES


def polygon_layer(tags: dict) -> str | None:
    if truthy_tag(tags.get('building')) or truthy_tag(tags.get('building:part')):
        return 'buildings'
    if tags.get('highway') and tags.get('area') == 'yes':
        return 'roads'
    if tags.get('water') or tags.get('waterway') in {'riverbank', 'dock'} or tags.get('natural') == 'water':
        return 'hydrography'
    if tags.get('railway'):
        return 'rail'
    if tags.get('landuse') or tags.get('leisure') or tags.get('natural') in {'wood', 'scrub', 'heath', 'grassland', 'beach', 'bare_rock', 'sand', 'wetland'}:
        return 'landuse'
    return None


def line_layer(tags: dict) -> str | None:
    if tags.get('highway') and tags.get('area') != 'yes':
        return 'roads'
    if tags.get('railway'):
        return 'rail'
    if tags.get('waterway') and tags.get('waterway') not in {'riverbank', 'dock'}:
        return 'hydrography'
    return None


def point_layer(tags: dict) -> str | None:
    if tags.get('highway') == 'crossing':
        return 'roads'
    if any(key in tags for key in ('name', 'amenity', 'shop', 'tourism', 'historic', 'public_transport', 'railway', 'emergency', 'healthcare')):
        return 'pois'
    if tags.get('highway') in {'traffic_signals', 'bus_stop', 'stop', 'give_way'}:
        return 'pois'
    return None


def polygon_parts(geometry) -> list[Polygon]:
    if geometry.is_empty:
        return []
    if isinstance(geometry, Polygon):
        return [geometry]
    if isinstance(geometry, (MultiPolygon, GeometryCollection)):
        return [p for part in geometry.geoms for p in polygon_parts(part)]
    return []


def line_parts(geometry) -> list[LineString]:
    if geometry.is_empty:
        return []
    if isinstance(geometry, LineString):
        return [geometry]
    if isinstance(geometry, (MultiLineString, GeometryCollection)):
        return [line for part in geometry.geoms for line in line_parts(part)]
    return []


def _runtime_centroid_inside(points, rings) -> bool:
    """Match frozen core53's strict centroid/ray test, without a new epsilon.

    Explicit additions preserve JavaScript's summation order; Python 3.12's
    builtin float sum can be more accurate than the browser's three additions.
    """
    point = [(points[0][axis] + points[1][axis] + points[2][axis]) / 3 for axis in (0, 1)]

    def in_ring(ring):
        ring = ring[:-1] if ring[0] == ring[-1] else ring
        inside = False
        for i, a in enumerate(ring):
            b = ring[i-1]
            if ((a[1] > point[1]) != (b[1] > point[1]) and
                    point[0] < (b[0]-a[0])*(point[1]-a[1])/(b[1]-a[1])+a[0]):
                inside = not inside
        return inside

    return bool(rings) and in_ring(rings[0]) and not any(in_ring(ring) for ring in rings[1:])


def mesh_for_polygon(polygon: Polygon, source_boundary) -> dict:
    """Triangulate the clipped polygon, while retaining only original walls.

    Earcut can emit near-collinear triangles with nanometre-scale altitude at
    Lambert-93 northings around six million metres. Such triangles cannot have
    a reliably interior centroid in Float64. Remove only numerical degeneracy
    (altitude <= eight coordinate ULPs), without moving any source ring or wall.
    The existing area-conservation check still rejects any meaningful loss.
    """
    polygon = orient(polygon, sign=1.0)
    rings = [list(polygon.exterior.coords), *[list(r.coords) for r in polygon.interiors]]
    open_rings = [ring[:-1] for ring in rings]
    vertices = np.asarray([q for ring in open_rings for q in ring], dtype=np.float64)
    ends = np.asarray(np.cumsum([len(ring) for ring in open_rings]), dtype=np.uint32)
    indices = mapbox_earcut.triangulate_float64(vertices, ends)
    triangles = []
    area_sum = 0.0
    for offset in range(0, len(indices), 3):
        points = vertices[indices[offset:offset+3]].tolist()
        triangle = Polygon(points)
        longest_edge = max(math.dist(a, b) for a, b in zip(points, points[1:] + points[:1]))
        coordinate_ulp = max(math.ulp(value) for point in points for value in point)
        if triangle.area < 1e-10 or longest_edge == 0 or 2*triangle.area/longest_edge <= 8*coordinate_ulp:
            continue
        if not _runtime_centroid_inside(points, rings):
            # Quarantine the invalid preparation by failing before publication;
            # do not bypass core53 or nudge vertices/centroids to make it pass.
            raise ImportFailure('triangulation-centroid-outside-runtime-footprint')
        if triangle.difference(polygon).area > max(1e-7, polygon.area * 1e-9):
            raise ImportFailure('triangulation-outside-source-polygon')
        triangles.append(points)
        area_sum += triangle.area
    if abs(area_sum - polygon.area) > max(1e-6, polygon.area * 1e-8):
        raise ImportFailure('triangulation-area-mismatch')
    walls = []
    original = source_boundary.intersection(polygon.boundary)
    for line in line_parts(original):
        coords = list(line.coords)
        for a, b in zip(coords, coords[1:]):
            if math.dist(a, b) > 1e-8:
                walls.append([list(a), list(b)])
    return {'ringsL93': rings, 'trianglesL93': triangles, 'wallsL93': walls, 'areaM2': polygon.area}


def clip_feature(source_geometry, properties: dict, tile) -> dict | None:
    """Return a prepared feature without closing missing or cut-cell walls."""
    clipped = source_geometry.intersection(tile)
    if source_geometry.geom_type in {'Polygon', 'MultiPolygon'}:
        polygons = [orient(p, sign=1.0) for p in polygon_parts(clipped) if p.area > 1e-8]
        if not polygons:
            return None
        polygons.sort(key=lambda p: (p.bounds, p.area))
        geometry = polygons[0] if len(polygons) == 1 else MultiPolygon(polygons)
        meshes = [mesh_for_polygon(p, source_geometry.boundary) for p in polygons]
    elif source_geometry.geom_type in {'LineString', 'MultiLineString'}:
        lines = [line for line in line_parts(clipped) if line.length > 1e-8]
        if not lines:
            return None
        geometry = lines[0] if len(lines) == 1 else MultiLineString(lines)
        meshes = None
    else:
        if clipped.is_empty:
            return None
        geometry, meshes = clipped, None
    metric = mapping(geometry)
    wgs = mapping(transform(TO_WGS84.transform, geometry))
    p = dict(properties)
    p['soma:metricGeometry'] = metric
    if meshes is not None:
        p['soma:mesh53'] = meshes
    return {'type': 'Feature', 'id': p['canonical_id'], 'properties': p, 'geometry': wgs}


def coordinate_count(value) -> int:
    if not isinstance(value, (tuple, list)):
        return 0
    if value and isinstance(value[0], (int, float)):
        return 1
    return sum(coordinate_count(v) for v in value)


def pbf_header(path: Path) -> dict:
    with osmium.io.Reader(str(path), osmium.osm.osm_entity_bits.NOTHING) as reader:
        header = reader.header()
        extent = header.box()
        bounds = [extent.bottom_left.lon, extent.bottom_left.lat, extent.top_right.lon, extent.top_right.lat] if extent.valid() else None
        return {'boundsWGS84': bounds, 'generator': header.get('generator') or None,
                'snapshotUTC': header.get('osmosis_replication_timestamp') or None}


def source_receipt(path: Path, supplied: dict, header: dict) -> dict:
    if not isinstance(supplied, dict):
        raise ImportFailure('Source receipt must be a JSON object.')
    for key in ('license', 'attribution'):
        if not isinstance(supplied.get(key), str) or not supplied[key].strip():
            raise ImportFailure(f'Missing source receipt field: {key}')
    fingerprint = file_sha256(path)
    if supplied.get('sha256') and supplied['sha256'] != fingerprint:
        raise ImportFailure('Source PBF SHA256 differs from the declared receipt.')
    result = dict(supplied)
    result.update({'id': supplied.get('id') or 'osm-pbf-' + fingerprint[:16], 'sha256': fingerprint,
                   'bytes': path.stat().st_size, 'date': supplied.get('date') or header['snapshotUTC'],
                   'sourceAuthenticityVerified': False})
    return result


def open_store(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    db.execute('PRAGMA journal_mode=DELETE')
    db.execute('PRAGMA synchronous=FULL')
    db.executescript('''
      CREATE TABLE features(id TEXT PRIMARY KEY, layer TEXT NOT NULL, properties TEXT NOT NULL,
                            geometry BLOB NOT NULL, minx REAL,miny REAL,maxx REAL,maxy REAL);
      CREATE VIRTUAL TABLE feature_index USING rtree(rowid,minx,maxx,miny,maxy);
      CREATE TABLE source_ways(id INTEGER PRIMARY KEY, layer TEXT, tags TEXT NOT NULL,
                               node_refs TEXT NOT NULL, coordinates TEXT NOT NULL, selected INTEGER NOT NULL DEFAULT 0);
      CREATE TABLE source_relations(id INTEGER PRIMARY KEY, tags TEXT NOT NULL, members TEXT NOT NULL);
      CREATE TABLE source_nodes(id INTEGER PRIMARY KEY, tags TEXT NOT NULL);
      CREATE TABLE area_candidates(id TEXT PRIMARY KEY);
      CREATE TABLE assembled_areas(id TEXT PRIMARY KEY);
      CREATE TABLE rejected(id TEXT NOT NULL, reason TEXT NOT NULL, detail TEXT);
    ''')
    return db


class PbfImporter(osmium.SimpleHandler):
    def __init__(self, db, extent, *, max_feature_cells=100000):
        super().__init__()
        self.db, self.extent = db, extent
        self.max_feature_cells = max_feature_cells
        self.factory = osmium.geom.WKBFactory()
        self.counts = Counter()
        self.candidate_cells: set[tuple[int, int]] = set()
        # A deliberately generous geographic broad phase avoids projecting
        # every polygon of a regional PBF for a small requested district.
        # Exact inclusion is still checked in Lambert-93 below.
        self.coarse_wgs = None
        if extent is not None:
            # Index the exact administrative polygon once. Most features lie
            # wholly inside it and need no constructive intersection at all.
            shapely.prepare(extent)
            west,south,east,north = TO_WGS84.transform_bounds(*extent.bounds,densify_pts=101)
            self.coarse_wgs = (west-.01,south-.01,east+.01,north+.01)

    def reject(self, source_id, reason, detail=''):
        self.db.execute('INSERT INTO rejected VALUES(?,?,?)', (source_id, reason, str(detail)[:2000]))

    def store(self, source_id, layer, tags, geometry):
        if self.coarse_wgs is not None and not geometry.is_empty:
            a,b,c,d = geometry.bounds
            west,south,east,north = self.coarse_wgs
            if c<west or a>east or d<south or b>north:
                return False
        if any(key in FORBIDDEN for key in tags):
            self.reject(source_id, 'unsafe-property-key')
            return False
        if geometry.is_empty or not geometry.is_valid:
            self.reject(source_id, 'invalid-source-geometry', shapely.is_valid_reason(geometry))
            return False
        try:
            metric = transform(TO_METRIC.transform, geometry)
        except (ValueError, shapely.GEOSException) as error:
            self.reject(source_id, 'projection-failed', error)
            return False
        if metric.is_empty or not metric.is_valid or not all(math.isfinite(v) for v in metric.bounds):
            self.reject(source_id, 'invalid-projected-geometry')
            return False
        if self.extent is not None and not self.extent.intersects(metric):
            return False
        bounds = metric.bounds
        # The canonical geometry stays complete; the requested extent only
        # limits which cells are emitted, not the original source geometry.
        emitted_bounds = (bounds if self.extent is None or self.extent.covers(metric)
                          else metric.intersection(self.extent).bounds)
        cells = []
        for cell in grid_cells(emitted_bounds):
            if len(cells) >= self.max_feature_cells:
                raise ImportFailure(f'Feature {source_id} exceeds the cell budget; use a bounded import.')
            cells.append(cell)
        p = dict(tags)
        p.update({'canonical_id': source_id, 'soma:layer': layer,
                  'soma:geometry_sha256': digest(mapping(metric)),
                  'soma:sourceBoundsL93': list(bounds)})
        self.db.execute('INSERT OR REPLACE INTO features VALUES(?,?,?,?,?,?,?,?)',
                        (source_id, layer, canonical_json(p), sqlite3.Binary(shapely.to_wkb(metric)), *bounds))
        self.candidate_cells.update(cells)
        self.counts['acceptedCallbacks'] += 1
        return True

    def node(self, node):
        self.counts['nodesRead'] += 1
        tags = dict(node.tags)
        relevant = {'barrier','access','vehicle','motor_vehicle','motorcar','foot','bicycle',
                    'ford','entrance','indoor','covered'}
        if any(key in relevant or key.endswith(':conditional') for key in tags):
            self.db.execute('INSERT OR REPLACE INTO source_nodes VALUES(?,?)',(node.id,canonical_json(tags)))
        layer = point_layer(tags)
        if layer and node.location.valid():
            self.store(f'osm/node/{node.id}', layer, tags, Point(node.location.lon, node.location.lat))

    def way(self, way):
        self.counts['waysRead'] += 1
        tags = dict(way.tags)
        line_kind = line_layer(tags)
        polygon_kind = polygon_layer(tags)
        source_id = f'osm/way/{way.id}'
        if polygon_kind and way.is_closed():
            self.db.execute('INSERT OR IGNORE INTO area_candidates VALUES(?)', (source_id,))
        elif polygon_kind and polygon_kind == 'buildings':
            self.reject(source_id, 'open-building-way')
        if line_kind is None:
            return
        refs = [str(node.ref) for node in way.nodes]
        positions = [[node.location.lon, node.location.lat] if node.location.valid() else None for node in way.nodes]
        self.db.execute('INSERT OR REPLACE INTO source_ways VALUES(?,?,?,?,?,0)',
                        (way.id, line_kind, canonical_json(tags), canonical_json(refs), canonical_json(positions)))
        if len(positions) < 2 or any(p is None for p in positions):
            self.reject(source_id, 'missing-way-node-location')
            return
        p = dict(tags)
        p['soma:node_refs'] = refs
        selected = self.store(source_id, line_kind, p, LineString(positions))
        if selected:
            self.db.execute('UPDATE source_ways SET selected=1 WHERE id=?', (way.id,))

    def relation(self, relation):
        self.counts['relationsRead'] += 1
        tags = dict(relation.tags)
        members = [{'type': {'n':'node','w':'way','r':'relation'}.get(member.type, member.type),
                    'ref': str(member.ref), 'role': member.role} for member in relation.members]
        self.db.execute('INSERT OR REPLACE INTO source_relations VALUES(?,?,?)',
                        (relation.id, canonical_json(tags), canonical_json(members)))
        if tags.get('type') in {'multipolygon', 'boundary'} and polygon_layer(tags):
            self.db.execute('INSERT OR IGNORE INTO area_candidates VALUES(?)', (f'osm/relation/{relation.id}',))

    def area(self, area):
        tags = dict(area.tags)
        layer = polygon_layer(tags)
        if layer is None:
            return
        source_id = f'osm/{"way" if area.from_way() else "relation"}/{area.orig_id()}'
        self.db.execute('INSERT OR IGNORE INTO assembled_areas VALUES(?)', (source_id,))
        try:
            geometry = shapely.from_wkb(self.factory.create_multipolygon(area))
            self.store(source_id, layer, tags, geometry)
        except (ValueError, RuntimeError, shapely.GEOSException) as error:
            self.reject(source_id, 'unreadable-source-area', error)

    def finish(self):
        for (source_id,) in self.db.execute('SELECT id FROM area_candidates WHERE id NOT IN (SELECT id FROM assembled_areas)'):
            self.reject(source_id, 'unassembled-source-area')
        self.db.execute('INSERT INTO feature_index SELECT rowid,minx,maxx,miny,maxy FROM features')
        self.db.commit()


def write_gzip_json(path: Path, value, *, max_decoded_bytes=None) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = canonical_json(value).encode('utf-8')
    if max_decoded_bytes is not None and len(raw) > max_decoded_bytes:
        raise ImportFailure(f'Tile exceeds the decoded-byte budget ({len(raw)} > {max_decoded_bytes}).')
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('xb') as stream:
        with gzip.GzipFile(filename='', fileobj=stream, mode='wb', mtime=0, compresslevel=6) as compressed:
            compressed.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
    return {'path': str(path.name), 'sha256': file_sha256(path), 'bytes': path.stat().st_size,
            'encoding': 'gzip-json', 'decodedBytes': len(raw)}


def native_topology(db: sqlite3.Connection, path: Path) -> dict:
    """Stream original way/node identities and related restrictions into gzip."""
    temporary = path.with_suffix('.tmp')
    counts = Counter()
    with temporary.open('xb') as raw:
        with gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0, compresslevel=6) as output:
            output.write(b'{"schema":"soma-metropole/native-topology/1","ways":[')
            first = True
            selected_ids = set()
            selected_node_ids = set()
            for way_id, layer, tags, refs, positions in db.execute('SELECT id,layer,tags,node_refs,coordinates FROM source_ways WHERE selected=1 ORDER BY id'):
                value = {'id': str(way_id), 'layer': layer, 'tags': json.loads(tags),
                         'nodeRefs': json.loads(refs), 'coordinatesWGS84': json.loads(positions)}
                if not first: output.write(b',')
                output.write(canonical_json(value).encode('utf-8'))
                first = False; selected_ids.add(str(way_id)); counts['ways'] += 1
                selected_node_ids.update(value['nodeRefs'])
            output.write(b'],"relations":[')
            first = True
            for relation_id, tags, members in db.execute('SELECT id,tags,members FROM source_relations ORDER BY id'):
                parsed = json.loads(members)
                if not any(m['type'] == 'way' and m['ref'] in selected_ids for m in parsed):
                    continue
                value = {'id': str(relation_id), 'tags': json.loads(tags), 'members': parsed}
                if not first: output.write(b',')
                output.write(canonical_json(value).encode('utf-8'))
                first = False; counts['relations'] += 1
                if value['tags'].get('type') == 'restriction': counts['turnRestrictions'] += 1
            output.write(b'],"nodeTags":{')
            first = True
            for node_id,tags in db.execute('SELECT id,tags FROM source_nodes ORDER BY id'):
                if str(node_id) not in selected_node_ids:
                    continue
                if not first: output.write(b',')
                output.write(canonical_json(str(node_id)).encode('utf-8')+b':'+tags.encode('utf-8'))
                first = False; counts['taggedNodes'] += 1
                if truthy_tag(json.loads(tags).get('barrier')): counts['barrierNodes'] += 1
            output.write(b'},"nodeTagsComplete":true}')
        raw.flush(); os.fsync(raw.fileno())
    temporary.replace(path)
    return {'path':path.name, 'sha256':file_sha256(path), 'bytes':path.stat().st_size,
            'encoding':'gzip-json', 'counts':dict(counts)}


def requested_extent(bounds_l93=None, boundary_path: Path | None = None):
    extent = None
    if bounds_l93 is not None:
        if len(bounds_l93) != 4 or not all(math.isfinite(v) for v in bounds_l93) or bounds_l93[0] >= bounds_l93[2] or bounds_l93[1] >= bounds_l93[3]:
            raise ImportFailure('Invalid requested Lambert-93 bounds.')
        extent = box(*bounds_l93)
    if boundary_path:
        value = json.loads(Path(boundary_path).read_text(encoding='utf-8'))
        if value.get('type') == 'FeatureCollection':
            geometry = shapely.union_all([shape(f['geometry']) for f in value['features']])
        elif value.get('type') == 'Feature': geometry = shape(value['geometry'])
        else: geometry = shape(value)
        if geometry.geom_type not in {'Polygon','MultiPolygon'} or not geometry.is_valid:
            raise ImportFailure('The boundary must be a valid RFC 7946 WGS84 polygon or multipolygon.')
        if geometry.is_empty or not all(math.isfinite(v) for v in geometry.bounds) or not (
                -180 <= geometry.bounds[0] <= geometry.bounds[2] <= 180 and
                -90 <= geometry.bounds[1] <= geometry.bounds[3] <= 90):
            raise ImportFailure('The boundary coordinates must use WGS84 longitude/latitude.')
        boundary = transform(TO_METRIC.transform, geometry)
        extent = boundary if extent is None else boundary.intersection(extent)
    if extent is not None and extent.is_empty:
        raise ImportFailure('Requested extent is empty.')
    return extent


def prepare_tiles(pbf: Path, output: Path, receipt: dict, *, bounds_l93=None,
                  boundary_path: Path | None = None, max_tiles=100000,
                  max_features=12000, max_coordinates=300000, max_tile_bytes=16*1024*1024,
                  location_index='flex_mem') -> dict:
    pbf, output = Path(pbf).resolve(), Path(output).absolute()
    if output.exists():
        raise ImportFailure('Output already exists; preserve it and choose a new output directory.')
    if max_tiles < 1 or max_features < 1 or max_coordinates < 1 or max_tile_bytes < 1:
        raise ImportFailure('Budgets must be positive integers.')
    extent = requested_extent(bounds_l93, boundary_path)
    header = pbf_header(pbf)
    provenance = source_receipt(pbf, receipt, header)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.metropole-import-', dir=output.parent) as temporary:
        stage = Path(temporary)/'world'
        stage.mkdir()
        db = open_store(stage/'canonical.sqlite')
        try:
            importer = PbfImporter(db, extent, max_feature_cells=max_tiles)
            importer.apply_file(str(pbf), locations=True, idx=location_index)
            importer.finish()
            cells = sorted(importer.candidate_cells, key=lambda q:(q[1],q[0]))
            if len(cells) > max_tiles:
                raise ImportFailure(f'Import requires {len(cells)} cells, beyond --max-tiles={max_tiles}.')
            tiles, fragment_counts = [], Counter()
            for x, y in cells:
                bounds = cell_bounds(x,y)
                tile = box(*bounds)
                if extent is not None and not extent.intersects(tile):
                    continue
                clip_extent = tile if extent is None or extent.covers(tile) else tile.intersection(extent)
                if clip_extent.area <= 1e-8:
                    continue
                features = []
                query = '''SELECT f.id,f.layer,f.properties,f.geometry FROM features f JOIN feature_index r ON f.rowid=r.rowid
                           WHERE r.minx<=? AND r.maxx>=? AND r.miny<=? AND r.maxy>=? ORDER BY f.id'''
                for source_id, layer, props, blob in db.execute(query,(bounds[2],bounds[0],bounds[3],bounds[1])):
                    properties = json.loads(props)
                    if source_id.startswith('osm/relation/'):
                        rel = db.execute('SELECT members FROM source_relations WHERE id=?',(int(source_id.rsplit('/',1)[1]),)).fetchone()
                        if rel:
                            members = json.loads(rel[0]); properties['soma:member_ways'] = [m['ref'] for m in members if m['type']=='way']
                            properties['soma:relation_members'] = members
                    try:
                        feature = clip_feature(shapely.from_wkb(blob),properties,clip_extent)
                    except ImportFailure as error:
                        raise ImportFailure(f'Cell {cell_id(x,y)}, {source_id}: {error}') from error
                    if feature is not None:
                        features.append(feature); fragment_counts[layer] += 1
                if not features:
                    continue
                n_coordinates = sum(coordinate_count(f['geometry']['coordinates'])+
                                    sum(coordinate_count(m['trianglesL93'])+coordinate_count(m['wallsL93']) for m in f['properties'].get('soma:mesh53',[]))
                                    for f in features)
                if len(features)>max_features or n_coordinates>max_coordinates:
                    raise ImportFailure(f'Cell {cell_id(x,y)} exceeds its geometry budget; no output published.')
                record = {'schema':CELL_SCHEMA,'version':'0.69.0','cellId':cell_id(x,y),
                          'boundsL93':list(bounds),'boundsWGS84':bounds_wgs84(bounds),'grid':{'x':x,'y':y},
                          'sourceReceipt':provenance,'v53Synthetic':False,
                          'certification':{'status':'staged','certified':False,'humanReviewed':False,'playable':False,'terrainAvailable':False},
                          'featureCollection':{'type':'FeatureCollection','features':features},
                          'seams':[]}
                record['contentSHA256'] = digest(record['featureCollection'])
                relative = f'tiles/{cell_id(x,y)}.json.gz'
                descriptor = write_gzip_json(stage/relative,record,max_decoded_bytes=max_tile_bytes); descriptor['path']=relative
                tiles.append({'cellId':cell_id(x,y),'gridX':x,'gridY':y,'boundsL93':list(bounds),
                              'vector':descriptor,'terrain':None,'navigation':None,
                              'featureCount':len(features),'coordinateCount':n_coordinates})
            topology = native_topology(db,stage/'native-topology.json.gz')
            rejected = [{'sourceId':source_id,'reason':reason,'detail':detail} for source_id,reason,detail in db.execute('SELECT id,reason,detail FROM rejected ORDER BY id,reason')]
            report = {'schema':'soma-metropole/vector-import-report/1','source':provenance,
                      'sourceHeader':header,'callbacks':dict(importer.counts),'tiles':len(tiles),
                      'canonicalFeatures':db.execute('SELECT COUNT(*) FROM features').fetchone()[0],
                      'canonicalCounts':dict(db.execute('SELECT layer,COUNT(*) FROM features GROUP BY layer')),
                      'fragmentCounts':dict(fragment_counts),'rejected':rejected,
                      'noInventedTerrain':True,'certifiedCells':0,'coverageExplicitPartial':True}
            manifest = {'schema':SCHEMA,'version':'0.69.0','crs':'EPSG:2154','units':'m',
                        'origin':list(ORIGIN),'cellSize':CELL_SIZE,'source':provenance,
                        'sourceBoundsWGS84':header['boundsWGS84'],
                        'bounds':list(extent.bounds) if extent is not None else (
                            [min(t['boundsL93'][0] for t in tiles),min(t['boundsL93'][1] for t in tiles),max(t['boundsL93'][2] for t in tiles),max(t['boundsL93'][3] for t in tiles)] if tiles else None),
                        'coverageExplicitPartial':True,'completeMetropole':False,
                        'tiles':tiles,'nativeTopology':topology,
                        'boundary':{'path':str(boundary_path),'sha256':file_sha256(Path(boundary_path))} if boundary_path else None,
                        'meaning':'Vector preparation only. Null terrain/navigation never means flat terrain or a playable certified cell.'}
            (stage/'IMPORT_REPORT.json').write_text(canonical_json(report)+'\n',encoding='utf-8')
            db.close()
            manifest['canonicalStore']={'path':'canonical.sqlite','sha256':file_sha256(stage/'canonical.sqlite'),
                                        'bytes':(stage/'canonical.sqlite').stat().st_size,'encoding':'sqlite3'}
            (stage/'manifest.json').write_text(canonical_json(manifest)+'\n',encoding='utf-8')
            stage.rename(output)
            return manifest
        finally:
            try: db.close()
            except sqlite3.Error: pass


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pbf',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--receipt',type=Path,required=True,help='JSON metadata, never credentials')
    parser.add_argument('--bounds-l93',type=float,nargs=4)
    parser.add_argument('--boundary',type=Path,help='Official RFC 7946 WGS84 Polygon/Feature/FeatureCollection')
    parser.add_argument('--max-tiles',type=int,default=100000)
    parser.add_argument('--max-features',type=int,default=12000)
    parser.add_argument('--max-coordinates',type=int,default=300000)
    parser.add_argument('--max-tile-bytes',type=int,default=16*1024*1024)
    parser.add_argument('--location-index',default='flex_mem')
    args=parser.parse_args()
    try:
        manifest=prepare_tiles(args.pbf,args.output,json.loads(args.receipt.read_text(encoding='utf-8')),
                               bounds_l93=args.bounds_l93,boundary_path=args.boundary,max_tiles=args.max_tiles,
                               max_features=args.max_features,max_coordinates=args.max_coordinates,
                               max_tile_bytes=args.max_tile_bytes,location_index=args.location_index)
        print(json.dumps({'status':'prepared','tiles':len(manifest['tiles']),'manifest':str(args.output/'manifest.json'),
                          'coverageExplicitPartial':True,'completeMetropole':False},ensure_ascii=False))
    except (OSError,ValueError,RuntimeError,sqlite3.Error,shapely.GEOSException) as error:
        parser.exit(1,f'Import refused: {error}\n')


if __name__=='__main__':
    main()
