#!/usr/bin/env python3
"""Diagnose real terrain holes and commune destinations without filling ground.

Offline development command, using already acquired native rasters. It checks
the installed world's link to its DEM edition, reads only partial cells and the
commune destination cells, and separates missing source footprints from native
NoData and the strict interpolation fringe. Administrative exterior is reported
as exterior, never automatically called sea. No game asset is changed.

Example (optional GIS requirements are needed only for this diagnostic)::

  python diagnose_terrain_coverage.py --world WORLD/manifest.json \
    --terrain DEM/manifest.json --boundary amp-boundary.geojson \
    --territory territory.json --anchors settlement-anchors.json \
    --raster-index IMPORT/raster-index.json --receipt IMPORT/source-receipt.json \
    --output /tmp/terrain-coverage.json
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
import re
import sys
import tempfile

GAME = Path(__file__).resolve().parents[2]
if str(GAME) not in sys.path:
    sys.path.insert(0, str(GAME))
from tools.v69 import terrain_tiles as T
from tools.v69 import build_terrain_coverage as B
from tools.v69.acquire_terrain import projected_boundary

SCHEMA = 'soma-metropole/terrain-coverage-diagnostic/1'
MAX_METADATA_BYTES = 256 * 1024**2
MAX_ASSET_BYTES = 4 * 1024**2
MAX_DECODED_BYTES = 16 * 1024**2
MAX_PARTIAL_CELLS = 1000
ORIGIN = [892951.6480966414, 6247274.566415883]


def _read(path, limit=MAX_METADATA_BYTES):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > limit:
        raise T.TerrainError('Diagnostic input is absent or exceeds its byte budget.')
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise T.TerrainError('Diagnostic metadata must be an object.')
    return value


def _relative(base, relative):
    if (not isinstance(relative, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]*', relative)
            or any(p in ('', '.', '..') for p in relative.split('/'))):
        raise T.TerrainError('Unsafe diagnostic asset path.')
    path = (base / relative).resolve()
    if not path.is_relative_to(base.resolve()):
        raise T.TerrainError('Diagnostic asset escapes its source directory.')
    return path


def _asset(base, cell):
    descriptor = cell.get('terrain')
    if not isinstance(descriptor, dict) or descriptor.get('encoding') != 'gzip-json':
        raise T.TerrainError('A real terrain asset is required for a diagnostic cell.')
    path = _relative(base, descriptor.get('path'))
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_ASSET_BYTES:
        raise T.TerrainError('Terrain asset is missing or exceeds its compressed byte budget.')
    raw = path.read_bytes()
    if len(raw) != descriptor.get('bytes') or hashlib.sha256(raw).hexdigest() != descriptor.get('sha256'):
        raise T.TerrainError('Terrain asset differs from its manifest fingerprint.')
    # A bounded read prevents a malformed compressed input allocating an entire
    # decompression bomb before the terrain validator can inspect dimensions.
    import io
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
        decoded = stream.read(MAX_DECODED_BYTES + 1)
    if len(decoded) > MAX_DECODED_BYTES:
        raise T.TerrainError('Terrain asset exceeds its decoded byte budget.')
    grid = T.validate_grid(json.loads(decoded), cell['boundsL93'])
    if (grid.sha256 != descriptor.get('gridSHA256') or grid.step != descriptor.get('stepM')
            or any(grid.stats[key] != descriptor.get(field) for key, field in
                   [('nodes', 'nodes'), ('valid', 'validNodes'), ('noData', 'noDataNodes')])):
        raise T.TerrainError('Terrain grid differs from its manifest statistics or fingerprint.')
    complete = all(grid.mask[r * grid.cols + c]
                   for r in range(1, grid.rows - 1) for c in range(1, grid.cols - 1))
    if descriptor.get('complete') is not complete:
        raise T.TerrainError('Terrain completeness contradicts its useful node mask.')
    return grid


def _percentiles(values):
    if not values:
        return None
    ordered = sorted(values)
    def percentile(fraction):
        place = (len(ordered) - 1) * fraction
        lo = math.floor(place)
        return ordered[lo] + (ordered[math.ceil(place)] - ordered[lo]) * (place - lo)
    return {'min': ordered[0], 'p50': percentile(.5), 'p95': percentile(.95), 'max': ordered[-1]}


def grid_quality(grid):
    """Describe the actual 250 m terrain mesh, not a claimed survey accuracy."""
    elevations, slopes, unknown = [], [], 0
    for r in range(1, grid.rows - 1):
        for c in range(1, grid.cols - 1):
            value = grid.node(c, r)
            if value is not None:
                elevations.append(value)
    for r in range(1, grid.rows - 2):
        for c in range(1, grid.cols - 2):
            nw, ne, sw, se = (grid.node(c, r), grid.node(c + 1, r),
                              grid.node(c, r + 1), grid.node(c + 1, r + 1))
            for vertices in ((nw, ne, sw), (se, sw, ne)):
                if any(value is None for value in vertices):
                    unknown += 1
                else:
                    a, b, d = vertices
                    slopes.append(math.degrees(math.atan(math.hypot(b - a, d - a) / grid.step)))
    return {'stepM': grid.step, 'usefulNodes': (grid.cols - 2) * (grid.rows - 2),
            'validUsefulNodes': len(elevations), 'elevationM_NGF69': _percentiles(elevations),
            'meshTriangleSlopeDegrees': _percentiles(slopes),
            'unknownMeshTriangles': unknown,
            'unknownMeshAreaM2': unknown * grid.step**2 / 2,
            'meaning': '250 m useful cell; fixed diagonal mesh; spacing is not an accuracy bound'}


class NativeEvidence:
    """Read small native windows, preserving the same four-corner mask rule."""
    def __init__(self, mosaic):
        self.mosaic = mosaic

    def reasons(self, bounds, points):
        from rasterio.windows import Window
        m = self.mosaic
        left = math.floor((bounds[0] - m.x0) / m.dx - .5) - 1
        right = math.floor((bounds[2] - m.x0) / m.dx - .5) + 2
        top = math.floor((m.n0 - bounds[3]) / m.dy - .5) - 1
        bottom = math.floor((m.n0 - bounds[1]) / m.dy - .5) + 2
        windows, pixels = [], 0
        for source in m.sources:
            c0, r0 = max(left, source['col']), max(top, source['row'])
            c1 = min(right, source['col'] + source['width'] - 1)
            r1 = min(bottom, source['row'] + source['height'] - 1)
            if c0 > c1 or r0 > r1:
                continue
            pixels += (c1 - c0 + 1) * (r1 - r0 + 1)
            if pixels > T.MAX_WINDOW_PIXELS:
                raise T.TerrainError('Native diagnostic windows exceed their pixel budget.')
            data = m._handle(source['path']).read(1, masked=True, window=Window(
                c0 - source['col'], r0 - source['row'], c1 - c0 + 1, r1 - r0 + 1))
            windows.append((c0, r0, c1, r1, data))

        def status(col, row):
            covered, values = False, []
            for c0, r0, c1, r1, data in windows:
                if c0 <= col <= c1 and r0 <= row <= r1:
                    covered = True
                    value = data[row - r0, col - c0]
                    if not bool(getattr(value, 'mask', False)):
                        value = float(value)
                        if not math.isfinite(value) or not -500 <= value <= 9000:
                            raise T.TerrainError('Unmasked native diagnostic altitude is invalid.')
                        values.append(value)
            if values and max(values) - min(values) > 1e-6:
                raise T.TerrainError('Native sources contradict each other.')
            return 'valid' if values else 'source-nodata' if covered else 'missing-raster-footprint'

        result = []
        for east, north in points:
            x, y = (east - m.x0) / m.dx - .5, (m.n0 - north) / m.dy - .5
            ix, iy, u, v = math.floor(x), math.floor(y), x % 1, y % 1
            contributors = [status(c, r) for c, r, weight in
                            [(ix, iy, (1-u)*(1-v)), (ix+1, iy, u*(1-v)),
                             (ix, iy+1, (1-u)*v), (ix+1, iy+1, u*v)] if weight > 1e-12]
            if 'missing-raster-footprint' in contributors:
                reason = 'missing-raster-footprint'
            elif 'source-nodata' in contributors:
                reason = 'strict-interpolation-fringe' if 'valid' in contributors else 'native-source-nodata'
            else:
                raise T.TerrainError('A missing terrain node has all valid native contributors.')
            result.append(reason)
        return result


def _frame(manifest):
    if manifest.get('origin') != ORIGIN or manifest.get('cellSize') != 250 or manifest.get('crs') != 'EPSG:2154':
        raise T.TerrainError('Diagnostic requires the historical metropolitan EPSG:2154 cell frame.')
    definition = {'schema': T.TARGET_SCHEMA, 'origin': ORIGIN, 'cellSize': 250, 'crs': 'EPSG:2154',
                  'boundarySHA256': '0' * 64,
                  'tiles': [{key: item[key] for key in ('cellId', 'gridX', 'gridY', 'boundsL93')}
                            for item in manifest['tiles']]}
    T._cells_manifest(definition)
    from tools.metropole.import_tiles import cell_id
    if any(item['cellId'] != cell_id(item['gridX'], item['gridY']) for item in manifest['tiles']):
        raise T.TerrainError('A diagnostic cell identity contradicts its canonical grid position.')
    return {item['cellId']: item for item in manifest['tiles']}


def diagnose(world, terrain, boundary, territory, anchors, raster_index, receipt):
    """Return a source-bound diagnostic; all inputs and assets remain unchanged."""
    import shapely
    from shapely.geometry import shape
    from shapely.ops import transform, unary_union
    from pyproj import Transformer
    from tools.build_metropole_viewer import audited_settlement_anchors, source_anchor

    paths = {key: Path(value) for key, value in dict(world=world, terrain=terrain, boundary=boundary,
             territory=territory, anchors=anchors, rasterIndex=raster_index, receipt=receipt).items()}
    fingerprints = {key: T.file_fingerprint(path) for key, path in paths.items()}
    w, dem = _read(world), _read(terrain)
    if w.get('schema') != 'soma-metropole/world-manifest/1' or dem.get('schema') != T.TILES_SCHEMA:
        raise T.TerrainError('A world manifest and a real DEM edition are required.')
    wcells, dcells = _frame(w), _frame(dem)
    boundary_sha = fingerprints['boundary']['sha256']
    if (w.get('sourceManifests', {}).get('terrain') != fingerprints['terrain']['sha256']
            or w.get('target', {}).get('boundarySHA256') != boundary_sha
            or dem.get('targetDefinition', {}).get('boundarySHA256') != boundary_sha):
        raise T.TerrainError('World, DEM edition and administrative boundary are not linked.')
    if set(wcells) != set(dcells) or any(wcells[k]['boundsL93'] != dcells[k]['boundsL93'] for k in wcells):
        raise T.TerrainError('World and DEM cell coverage differ.')
    for key in wcells:
        if (wcells[key].get('terrain') or {}).get('gridSHA256') != (dcells[key].get('terrain') or {}).get('gridSHA256'):
            raise T.TerrainError('An installed world terrain grid differs from its DEM edition.')
    projected_boundary(boundary, boundary_sha)
    to_l93 = Transformer.from_crs(4326, 2154, always_xy=True).transform
    boundary_data = _read(boundary)
    region = transform(to_l93, unary_union([shape(f['geometry']) for f in boundary_data['features']]))
    shapely.prepare(region)
    native_paths, source_receipt, _ = B.checked_sources(raster_index, receipt, boundary_sha)
    if dem.get('source', {}).get('receipt') != source_receipt:
        raise T.TerrainError('The native source receipt differs from the DEM source edition.')
    mosaic = T.RasterMosaic(native_paths, source_receipt)
    cache, checked = {}, set()

    def load(cell_id):
        if cell_id not in cache:
            g = _asset(paths['terrain'].parent, dcells[cell_id])
            installed = _asset(paths['world'].parent, wcells[cell_id])
            if g.data != installed.data or g.mask != installed.mask or g.header != installed.header:
                raise T.TerrainError('Installed terrain bytes differ from their source DEM grid.')
            cache[cell_id] = g
            checked.add(cell_id)
        return cache[cell_id]

    reason_names = ('native-source-nodata', 'strict-interpolation-fringe', 'missing-raster-footprint')
    totals, unique, unique_distances, partial_rows = Counter(dict.fromkeys(reason_names, 0)), {}, {}, []
    partials = [item for item in dem['tiles'] if (item.get('terrain') or {}).get('complete') is False]
    if len(partials) > MAX_PARTIAL_CELLS:
        mosaic.close()
        raise T.TerrainError('Partial terrain diagnostic exceeds its cell budget.')
    try:
        for item in partials:
            g = load(item['cellId'])
            points = [(g.x0 + c * g.step, g.n0 - r * g.step)
                      for r in range(1, g.rows - 1) for c in range(1, g.cols - 1)
                      if not g.mask[r * g.cols + c]]
            reasons = NativeEvidence(mosaic).reasons(item['boundsL93'], points)
            geometries = shapely.points(points)
            interior = shapely.covers(region, geometries)
            distances = [float(value) for value in shapely.distance(geometries[interior], region.boundary)]
            distance_values = iter(distances)
            counts = Counter(reasons)
            for point, reason, inside in zip(points, reasons, interior):
                key = (round((point[0] - ORIGIN[0]) / g.step, 6),
                       round((ORIGIN[1] - point[1]) / g.step, 6))
                evidence = (reason, bool(inside))
                if key in unique and unique[key] != evidence:
                    raise T.TerrainError('Shared missing nodes have contradictory diagnostic evidence.')
                unique[key] = evidence
                if inside:
                    unique_distances[key] = next(distance_values)
            quality = grid_quality(g)
            counts.update(usefulMissingNodeOccurrences=len(points), insideAdministrative=int(interior.sum()),
                          outsideAdministrative=len(points) - int(interior.sum()),
                          allGridNoDataIncludingHalo=g.stats['noData'])
            totals.update(counts)
            partial_rows.append({'cellId': item['cellId'], 'boundsL93': item['boundsL93'],
                                 'noData': dict(counts), 'insideDistanceToBoundaryM': _percentiles(distances),
                                 'mesh': quality, 'action': 'preserve-source-nodata'})
    finally:
        mosaic.close()

    territory_data, anchor_data = _read(territory), _read(anchors)
    descriptor = territory_data.get('boundary', {}).get('source', {})
    commune_path = _relative(paths['territory'].parent, descriptor.get('path'))
    commune_fp = T.file_fingerprint(commune_path)
    if any(commune_fp[k] != descriptor.get(k) for k in ('sha256', 'bytes')):
        raise T.TerrainError('Commune contours differ from their administrative receipt.')
    fingerprints['communeContours'] = commune_fp
    commune_features = _read(commune_path)['features']
    names = {str(row['code']): row['nom'] for row in territory_data['communes']}
    communes = {str(f['properties']['code']): {'name': names[str(f['properties']['code'])],
                                              'geometry': f['geometry']} for f in commune_features}
    if (len(communes) != len(commune_features) or set(communes) != set(names)
            or w.get('target', {}).get('communeCount') != len(names)
            or w.get('target', {}).get('territorySHA256') != fingerprints['territory']['sha256']
            or anchor_data.get('territorySHA256') != fingerprints['territory']['sha256']
            or anchor_data.get('boundarySHA256') != boundary_sha
            or anchor_data.get('sources', {}).get('communeContours') !=
            {key: descriptor[key] for key in ('path', 'sha256', 'bytes')}):
        raise T.TerrainError('Commune destinations and administrative composition differ.')
    audited = audited_settlement_anchors(anchor_data, communes, boundary_sha)
    # The administrative polygons locate the partial cells. They are not a
    # bathymetric or sea mask, so an exterior point keeps its explicit status.
    commune_codes = sorted(communes)
    metric_communes = [transform(to_l93, shape(communes[code]['geometry'])) for code in commune_codes]
    commune_tree = shapely.STRtree(metric_communes)
    for row in partial_rows:
        cell_polygon = shapely.box(*row['boundsL93'])
        row['administrativeCommunes'] = [
            {'code': commune_codes[int(index)], 'name': communes[commune_codes[int(index)]]['name'],
             'intersectionAreaM2': float(cell_polygon.intersection(metric_communes[int(index)]).area)}
            for index in sorted(commune_tree.query(cell_polygon, predicate='intersects'))
            if cell_polygon.intersection(metric_communes[int(index)]).area > 0]
    centres = []
    from tools.metropole.import_tiles import cell_id
    for code, commune in sorted(communes.items()):
        anchor = audited[code]
        if anchor['status'] == 'source-place':
            east, north = anchor['pointL93']
            projected = to_l93(*anchor['pointWGS84'])
            if max(abs(a - b) for a, b in zip(projected, (east, north))) > 1e-4:
                raise T.TerrainError('A settlement metric point contradicts its geographic position.')
            meaning = 'source-osm-place-node'
        else:
            east, north = to_l93(*source_anchor(commune['geometry']))
            meaning = 'administrative-contour-fallback; not a surveyed settlement centre'
        x, y = math.floor((east - ORIGIN[0] + 125) / 250), math.floor((ORIGIN[1] - north + 125) / 250)
        identity = cell_id(x, y)
        if anchor['status'] == 'source-place' and anchor['cellId'] != identity:
            raise T.TerrainError('A settlement anchor names the wrong terrain cell.')
        grid = load(identity) if identity in dcells else None
        elevation = grid.sample(east, north) if grid else None
        centres.append({'code': code, 'name': commune['name'], 'anchorStatus': anchor['status'],
                        'pointMeaning': meaning, 'pointL93': [east, north], 'cellId': identity,
                        'elevationM_NGF69': elevation, 'groundKnown': elevation is not None,
                        'cellMesh': grid_quality(grid) if grid else None})
    unique_counts = Counter(dict.fromkeys(reason_names, 0))
    unique_counts.update(reason for reason, _ in unique.values())
    unique_counts.update(insideAdministrative=sum(inside for _, inside in unique.values()),
                         outsideAdministrative=sum(not inside for _, inside in unique.values()),
                         uniqueUsefulMissingNodes=len(unique))
    by_position = {}
    for name, wanted in [('insideAdministrative', True), ('outsideAdministrative', False)]:
        position_counts = Counter(dict.fromkeys(reason_names, 0))
        position_counts.update(reason for reason, inside in unique.values() if inside is wanted)
        by_position[name] = dict(position_counts)
    for key, path in paths.items():
        if T.file_fingerprint(path) != fingerprints[key]:
            raise T.TerrainError('A diagnostic input changed during examination.')
    if T.file_fingerprint(commune_path) != commune_fp:
        raise T.TerrainError('Commune contours changed during examination.')
    # No repeated full-world QA: this report states exactly which assets were
    # inspected, alongside the source metadata validation and native fingerprints.
    return {'schema': SCHEMA, 'inputs': fingerprints, 'source': source_receipt,
            'coverage': {'worldCells': len(wcells), 'partialCells': len(partials),
                         'completeUsefulCells': sum((c.get('terrain') or {}).get('complete') is True
                                                    for c in dcells.values()),
                         'missingTerrainCells': sum(c.get('terrain') is None for c in dcells.values()),
                         'checkedCells': len(checked), 'checkedTerrainAssets': len(checked) * 2,
                         'nativeRastersFingerprintChecked': len(native_paths),
                         'communes': len(centres), 'knownDestinationGround': sum(c['groundKnown'] for c in centres),
                         'sourcePlaceDestinations': sum(c['anchorStatus'] == 'source-place' for c in centres),
                         'contourFallbackDestinations': sum(c['anchorStatus'] == 'contour-fallback' for c in centres)},
            'noDataOccurrences': dict(totals), 'uniqueUsefulNoData': dict(unique_counts),
            'uniqueNoDataByAdministrativePosition': by_position,
            'uniqueInsideNoDataDistanceToBoundaryM': _percentiles(list(unique_distances.values())),
            'unknownMeshAreaM2InPartialCells': sum(c['mesh']['unknownMeshAreaM2'] for c in partial_rows),
            'partialCells': partial_rows, 'communeDestinations': centres,
            'semantics': {'native-source-nodata': 'Every contributing native pixel is masked; no altitude is supplied.',
                          'strict-interpolation-fringe': 'At least one valid and one masked native contributor; strict sampling rejects the point.',
                          'missing-raster-footprint': 'At least one required contributor has no retained source raster footprint.',
                          'outsideAdministrative': 'Outside the supplied administrative polygons; this alone does not prove sea.',
                          'insideAdministrative': 'Inside the supplied polygons; coastline editions and interpolation can differ.'},
            'limitations': ['No sea or bathymetry is invented; masked altitudes remain unknown.',
                            'Native spacing and mesh slope are not survey accuracy or engineering deck elevation.',
                            'An MNT models ground; bridges, tunnels, stairs and roof shapes need independent measurements.',
                            'Only partial cells and destination cells are decoded; this is not a repeated exhaustive asset audit.'],
            'assetsModified': False, 'certifiedOneToOne': False}


def write_report(path, report):
    """Publish only a finished report, preserving an existing different file."""
    path = Path(path)
    raw = B._json(report)
    if len(raw) > 16 * 1024**2:
        raise T.TerrainError('Diagnostic report exceeds its output byte budget.')
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != raw:
            raise T.TerrainError('An existing different diagnostic report is preserved.')
        return
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.terrain-diagnostic-', delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
            os.link(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for name in ('world', 'terrain', 'boundary', 'territory', 'anchors', 'raster-index', 'receipt', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    try:
        report = diagnose(args.world, args.terrain, args.boundary, args.territory, args.anchors,
                          args.raster_index, args.receipt)
        write_report(args.output, report)
        print(json.dumps({'report': str(args.output), 'sha256': T.file_fingerprint(args.output)['sha256'],
                          'coverage': report['coverage'], 'uniqueUsefulNoData': report['uniqueUsefulNoData']}))
    except (T.TerrainError, OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f'Terrain coverage diagnostic failed: {error}\n')


if __name__ == '__main__':
    main()
