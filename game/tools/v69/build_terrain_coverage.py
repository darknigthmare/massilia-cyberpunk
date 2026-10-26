#!/usr/bin/env python3
"""Prepare administrative 5 m DEM coverage from already acquired local rasters.

No vector data or downloads are involved. The historical 250 m cell grid,
positive-area boundary selection, strict NoData sampler and two-worker batch
generation are the same as the checked metropolitan acquisition. A complete
output directory is published atomically; existing outputs are preserved.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
import multiprocessing as mp
from pathlib import Path
import re
import resource
import shutil
import sys
import tempfile
import time

GAME = Path(__file__).resolve().parents[2]
if str(GAME) not in sys.path:
    sys.path.insert(0, str(GAME))
from tools.v69 import terrain_tiles as T
from tools.v69.acquire_terrain import projected_boundary

MAX_OUTPUT_BYTES = 2 * 1024**3
MIN_RESERVE_BYTES = 2 * 1024**3
DEFAULT_RESERVE_BYTES = 4 * 1024**3
MAX_CANDIDATES = 250_000
MAX_TARGETS = 100_000
MAX_INPUT_BYTES = 16 * 1024**2
HASH = re.compile(r'^[a-f0-9]{64}$')
RASTER_INDEX_SCHEMA = 'soma-metropole/ign-native-raster-index/1'
_RAW_WRITE = T._write
_BUDGET = None
_VERBOSE = False


@dataclass
class Budget:
    counter: object
    stopped: object
    limit: int
    reserve: int
    directory: Path


def _json(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                       allow_nan=False) + '\n').encode('utf-8')


def _read(path):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > MAX_INPUT_BYTES:
        raise T.TerrainError('Source metadata missing or beyond its byte budget.')
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise T.TerrainError('Source metadata must be a JSON object.')
    return value


def targets_from_boundary(boundary):
    """Select only cells with positive projected intersection, retaining holes."""
    try:
        from pyproj import Transformer
        from shapely.geometry import box, shape
        from shapely.ops import transform, unary_union
        from shapely.prepared import prep
        # Reuse the importer's canonical cell identities, not its vector data.
        from tools.metropole.import_tiles import ORIGIN, cell_bounds, cell_id
    except ImportError as error:
        raise T.TerrainError('Install the optional geodata development requirements before planning.') from error
    boundary = Path(boundary)
    if boundary.stat().st_size > MAX_INPUT_BYTES:
        raise T.TerrainError('Administrative boundary exceeds its byte budget.')
    raw = boundary.read_bytes()
    checked = projected_boundary(boundary)
    if hashlib.sha256(raw).hexdigest() != checked['file']['sha256']:
        raise T.TerrainError('Administrative boundary changed during planning.')
    document = json.loads(raw)
    features = document.get('features', [document])
    region = unary_union([shape(feature.get('geometry', feature)) for feature in features])
    region = transform(Transformer.from_crs(4326, 2154, always_xy=True).transform, region)
    prepared = prep(region)
    east, north = ORIGIN
    bounds = region.bounds
    x0, x1 = (math.floor((value - east + 125) / 250) for value in (bounds[0], bounds[2]))
    y0, y1 = (math.floor((north - value + 125) / 250) for value in (bounds[3], bounds[1]))
    if (x1 - x0 + 1) * (y1 - y0 + 1) > MAX_CANDIDATES:
        raise T.TerrainError('Administrative target search exceeds the cell budget.')
    cells = []
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            extent = cell_bounds(x, y)
            polygon = box(*extent)
            if prepared.contains(polygon) or (prepared.intersects(polygon) and region.intersection(polygon).area > 0):
                cells.append({'cellId': cell_id(x, y), 'gridX': x, 'gridY': y, 'boundsL93': list(extent)})
                if len(cells) > MAX_TARGETS:
                    raise T.TerrainError('Administrative target list exceeds its cell budget.')
    result = {'schema': T.TARGET_SCHEMA, 'crs': 'EPSG:2154', 'origin': list(ORIGIN), 'cellSize': 250,
              'boundarySHA256': checked['file']['sha256'],
              'selection': 'strictly-positive-projected-intersection-area',
              'terrainOnly': True, 'vectorCoverageClaimed': False, 'tiles': cells}
    T._cells_manifest(result)
    return result


def checked_sources(raster_index, receipt, boundary_sha):
    """Bind every local raster to the retained index and compact source receipt."""
    raster_index, receipt = Path(raster_index), Path(receipt)
    index, source_receipt = _read(raster_index), T._receipt(_read(receipt))
    index_fp = T.file_fingerprint(raster_index)
    declared = source_receipt.get('rasterIndex', {})
    if (not isinstance(declared, dict) or declared.get('sha256') != index_fp['sha256']
            or ('bytes' in declared and declared['bytes'] != index_fp['bytes'])):
        raise T.TerrainError('Raster index differs from the compact source receipt.')
    if (index.get('schema') != RASTER_INDEX_SCHEMA or index.get('nativeStepM') != 5
            or index.get('boundarySHA256') != boundary_sha or index.get('crs') != 'EPSG:2154'
            or index.get('units') != 'm' or index.get('verticalDatum') != 'NGF-IGN69'):
        raise T.TerrainError('Raster index is not the requested administrative 5 m source.')
    for declaration in (index, source_receipt):
        if 'testOnly' in declaration and not isinstance(declaration['testOnly'], bool):
            raise T.TerrainError('The source fixture flag must be an explicit boolean.')
    if index.get('testOnly') is True:
        source_receipt['testOnly'] = True
    rasters = index.get('rasters')
    if not isinstance(rasters, list) or not rasters or len(rasters) > 10_000:
        raise T.TerrainError('Raster index is empty or beyond its file budget.')
    base, paths, fingerprints, seen = raster_index.parent.resolve(), [], [], set()
    for item in rasters:
        relative = item.get('path') if isinstance(item, dict) else None
        if (not isinstance(relative, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]*', relative)
                or any(part in ('', '.', '..') for part in relative.split('/'))):
            raise T.TerrainError('Unsafe path in the retained raster index.')
        path = (base / relative).resolve()
        if not path.is_relative_to(base) or path in seen or not path.is_file():
            raise T.TerrainError('Indexed raster is missing, duplicated or outside its source directory.')
        seen.add(path)
        actual = T.file_fingerprint(path)
        if (not isinstance(item.get('sha256'), str) or not HASH.fullmatch(item['sha256'])
                or actual['sha256'] != item['sha256'] or actual['bytes'] != item.get('bytes')
                or ('name' in item and actual['name'] != item['name'])):
            raise T.TerrainError('Indexed raster bytes differ from their source fingerprint.')
        paths.append(path)
        fingerprints.append(actual)
    mosaic = T.RasterMosaic(paths, source_receipt)
    try:
        if mosaic.dx != 5 or mosaic.dy != 5:
            raise T.TerrainError('The native source raster resolution must be exactly 5 m.')
    finally:
        mosaic.close()
    return paths, source_receipt, fingerprints


def _write_checked(budget, path, raw):
    if budget.stopped.is_set():
        raise T.TerrainError('Coverage preparation stopped; no partial output will be published.')
    with budget.counter.get_lock():
        growth = 0 if path.exists() else len(raw)
        if budget.counter.value + growth > budget.limit:
            budget.stopped.set()
            raise T.TerrainError('Coverage output byte budget exceeded.')
        if shutil.disk_usage(budget.directory).free - growth < budget.reserve:
            budget.stopped.set()
            raise T.TerrainError('Coverage disk reserve would be exceeded.')
        _RAW_WRITE(path, raw)
        budget.counter.value += growth


def _initialise(budget, verbose):
    global _BUDGET, _VERBOSE
    _BUDGET, _VERBOSE = budget, verbose


def _worker(job):
    paths, receipt, targets, output, batch = job
    output.mkdir(parents=True, exist_ok=True)
    original_tile, original_handle, original_write = T.RasterMosaic.tile, T.RasterMosaic._handle, T._write
    count, started = 0, time.monotonic()

    def write(path, raw):
        _write_checked(_BUDGET, path, raw)

    def tile(self, bounds, step):
        nonlocal count
        if _BUDGET.stopped.is_set():
            raise T.TerrainError('Another coverage batch stopped.')
        result = original_tile(self, bounds, step)
        count += 1
        if _VERBOSE and count % 1000 == 0:
            print(json.dumps({'event': 'progress', 'batch': batch, 'cells': count,
                              'outputBytes': _BUDGET.counter.value,
                              'seconds': round(time.monotonic() - started, 3)}), flush=True)
        return result

    def handle(self, path):
        if path not in self.handles and len(self.handles) >= 4:
            _, old = self.handles.popitem(last=False)
            old.close()
        return original_handle(self, path)

    T._write, T.RasterMosaic.tile, T.RasterMosaic._handle = write, tile, handle
    try:
        manifest = T.tiles_from_geotiff(paths, targets, output, 5, receipt)
    finally:
        T._write, T.RasterMosaic.tile, T.RasterMosaic._handle = original_write, original_tile, original_handle
    return {'batch': batch, 'coverage': manifest['coverage'],
            'manifest': f'batches/{batch:02d}/manifest.json',
            'seconds': time.monotonic() - started,
            'maxRSSKiB': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}


def _publish(stage, output):
    if output.exists() or output.is_symlink():
        raise T.TerrainError('Output already exists and is preserved.')
    stage.rename(output)


def build_coverage(boundary, raster_index, receipt, output, *, workers=2,
                   max_output_bytes=MAX_OUTPUT_BYTES, disk_reserve_bytes=DEFAULT_RESERVE_BYTES,
                   plan_only=False, verbose=False):
    """Produce target-cells.json, plan.json and optionally the checked DEM batches."""
    started = time.monotonic()
    if not isinstance(workers, int) or workers not in (1, 2) or isinstance(workers, bool):
        raise T.TerrainError('Coverage generation permits one or two workers.')
    if not isinstance(plan_only, bool) or not isinstance(verbose, bool):
        raise T.TerrainError('Planning and progress flags must be explicit booleans.')
    if (not isinstance(max_output_bytes, int) or isinstance(max_output_bytes, bool)
            or not 0 < max_output_bytes <= MAX_OUTPUT_BYTES):
        raise T.TerrainError('Output budget must be positive and no greater than 2 GiB.')
    if (not isinstance(disk_reserve_bytes, int) or isinstance(disk_reserve_bytes, bool)
            or not MIN_RESERVE_BYTES <= disk_reserve_bytes <= 64 * 1024**3):
        raise T.TerrainError('Disk reserve must be between 2 and 64 GiB.')
    boundary, raster_index, receipt, output = map(Path, (boundary, raster_index, receipt, output))
    output = output.absolute()
    if output.exists() or output.is_symlink():
        raise T.TerrainError('Output already exists and is preserved.')
    inputs = {path: T.file_fingerprint(path) for path in (boundary, raster_index, receipt)}
    targets = targets_from_boundary(boundary)
    paths, source_receipt, source_files = checked_sources(raster_index, receipt, targets['boundarySHA256'])
    actual_workers = min(workers, len(targets['tiles']))
    output.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(output.parent).free < disk_reserve_bytes + max_output_bytes:
        raise T.TerrainError('Insufficient disk headroom for the chosen output budget and reserve.')
    ctx = mp.get_context('fork')
    with tempfile.TemporaryDirectory(prefix='.terrain-coverage-', dir=output.parent) as temporary:
        stage = Path(temporary) / 'coverage'
        stage.mkdir()
        budget = Budget(ctx.Value('q', 0), ctx.Event(), max_output_bytes, disk_reserve_bytes, stage)
        target_raw = _json(targets)
        target_fp = {'name': 'target-cells.json', 'bytes': len(target_raw), 'sha256': hashlib.sha256(target_raw).hexdigest()}
        plan = {'schema': 'soma-metropole/terrain-generation-plan/1', 'targets': target_fp,
                'boundary': inputs[boundary], 'sourceIndex': inputs[raster_index], 'receipt': inputs[receipt],
                'stepM': 5, 'terrainOnly': True, 'vectorCoverageClaimed': False,
                'targetCells': len(targets['tiles']), 'tileNodes': 2809,
                'rawTileNodeBytes': len(targets['tiles']) * 2809 * 5,
                'workers': actual_workers, 'requestedWorkers': workers,
                'maxOpenSourceRasters': actual_workers * 4, 'maxOutputBytes': max_output_bytes,
                'diskReserveBytes': disk_reserve_bytes, 'planOnly': plan_only}
        _write_checked(budget, stage / 'target-cells.json', target_raw)
        _write_checked(budget, stage / 'plan.json', _json(plan))
        if verbose:
            print(json.dumps({'event': 'plan', **plan}), flush=True)
        if not plan_only:
            jobs = []
            for batch in range(actual_workers):
                subset = dict(targets)
                subset['tiles'] = targets['tiles'][batch * len(targets['tiles']) // actual_workers:
                                                   (batch + 1) * len(targets['tiles']) // actual_workers]
                jobs.append((paths, source_receipt, subset, stage / 'batches' / f'{batch:02d}', batch))
            with ctx.Pool(actual_workers, initializer=_initialise, initargs=(budget, verbose)) as pool:
                results = sorted(pool.imap_unordered(_worker, jobs), key=lambda result: result['batch'])
            manifests = []
            for result in results:
                manifest = json.loads((stage / result['manifest']).read_text())
                if manifest['source']['files'] != source_files:
                    raise T.TerrainError('Source rasters changed during coverage preparation.')
                for tile in manifest['tiles']:
                    if tile.get('terrain'):
                        tile['terrain']['path'] = f'batches/{result["batch"]:02d}/' + tile['terrain']['path']
                manifests.append(manifest)
            for manifest in manifests[1:]:
                for key in ('schema', 'crs', 'units', 'verticalDatum', 'cellSize', 'origin', 'source',
                            'targetDefinition', 'terrainOnly', 'vectorCoverageClaimed'):
                    if manifest.get(key) != manifests[0].get(key):
                        raise T.TerrainError('Coverage batches have different source/frame/target definitions.')
            final = dict(manifests[0])
            final['tiles'] = sorted([tile for manifest in manifests for tile in manifest['tiles']],
                                    key=lambda tile: (tile['gridY'], tile['gridX']))
            final['coverage'] = {key: sum(manifest['coverage'][key] for manifest in manifests)
                                 for key in manifests[0]['coverage']}
            if any(manifest.get('testOnly') for manifest in manifests):
                final['testOnly'] = True
            # Recheck real input bytes before publication, including raster data.
            checked_sources(raster_index, receipt, targets['boundarySHA256'])
            for path, fingerprint in inputs.items():
                if T.file_fingerprint(path) != fingerprint:
                    raise T.TerrainError('Coverage inputs changed during generation.')
            _write_checked(budget, stage / 'manifest.json', _json(final))
            report = {'schema': 'soma-metropole/terrain-generation/1', 'plan': plan, 'batches': results,
                      'manifest': T.file_fingerprint(stage / 'manifest.json'), 'coverage': final['coverage'],
                      'elapsedSeconds': time.monotonic() - started, 'terrainOnly': True,
                      'vectorCoverageClaimed': False, 'sourceSurveyDate': source_receipt.get('sourceSurveyDate', 'not supplied'),
                      'newSurvey': False, 'verificationPending': True,
                      'buildToolSourceSHA256': T.file_fingerprint(__file__)['sha256']}
            before_report = budget.counter.value
            for _ in range(4):
                report['outputBytes'] = before_report + len(_json(report))
            _write_checked(budget, stage / 'generation.json', _json(report))
        else:
            report = plan
        for path, fingerprint in inputs.items():
            if T.file_fingerprint(path) != fingerprint:
                raise T.TerrainError('Coverage metadata changed before publication.')
        if shutil.disk_usage(stage).free < disk_reserve_bytes:
            raise T.TerrainError('Coverage disk reserve is not satisfied before publication.')
        _publish(stage, output)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('boundary', 'raster-index', 'receipt', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--workers', type=int, choices=(1, 2), default=2)
    parser.add_argument('--max-output-bytes', type=int, default=MAX_OUTPUT_BYTES)
    parser.add_argument('--disk-reserve-bytes', type=int, default=DEFAULT_RESERVE_BYTES)
    parser.add_argument('--plan-only', action='store_true', help='publish target definitions and plan only; no DEM generation')
    parser.add_argument('--quiet', action='store_true')
    args = parser.parse_args()
    try:
        result = build_coverage(args.boundary, args.raster_index, args.receipt, args.output,
                                workers=args.workers, max_output_bytes=args.max_output_bytes,
                                disk_reserve_bytes=args.disk_reserve_bytes,
                                plan_only=args.plan_only, verbose=not args.quiet)
        print(json.dumps({'status': 'planned' if args.plan_only else 'prepared', 'output': str(args.output),
                          'targetCells': result.get('targetCells', result.get('coverage', {}).get('targetCells')),
                          'terrainOnly': True, 'vectorCoverageClaimed': False}), flush=True)
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.exit(1, f'Terrain coverage refused: {error}\n')


if __name__ == '__main__':
    main()
