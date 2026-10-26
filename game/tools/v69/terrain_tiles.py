#!/usr/bin/env python3
"""Prepare bounded, provenance-bearing IGN terrain tiles; never invent missing ground.

Retiling an existing terrain-grid/1 uses the standard library and copies float32
node bytes exactly. GeoTIFF import requires rasterio only in the generation
environment. Playing the game does not acquire a new Python dependency.
"""
from __future__ import annotations

import argparse
import base64
from collections import OrderedDict
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import re
import struct
from typing import Any

GRID_SCHEMA = 'soma-massilia/terrain-grid/1'
VECTOR_SCHEMA = 'soma-metropole/vector-tiles/1'
TARGET_SCHEMA = 'soma-metropole/terrain-target-cells/1'
TILES_SCHEMA = 'soma-metropole/terrain-tiles/1'
MAX_GRID_NODES = 5_000_000
MAX_TILE_NODES = 100_000
MAX_WINDOW_PIXELS = 16_000_000
CELL_SIZE = 250
STEPS = (1, 5, 25)
TOLERANCE = 1e-6


class TerrainError(ValueError):
    """A source, datum, target grid or coverage declaration is incompatible."""


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def _read_json(value):
    if isinstance(value, dict):
        return value
    path = Path(value)
    raw = path.read_bytes()
    if path.suffix == '.gz':
        raw = gzip.decompress(raw)
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise TerrainError('Un document JSON objet est requis.')
    return result


def file_fingerprint(path):
    digest, size = hashlib.sha256(), 0
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            size += len(chunk)
            digest.update(chunk)
    return {'name': Path(path).name, 'bytes': size, 'sha256': digest.hexdigest()}


def grid_digest(header_text, data, mask):
    return hashlib.sha256(header_text.encode('utf-8') + b'\0' + data + mask).hexdigest()


class TerrainGrid:
    def __init__(self, header, data, mask, digest, source=None, test_only=False):
        self.header, self.data, self.mask, self.sha256 = header, data, mask, digest
        self.cols, self.rows = header['cols'], header['rows']
        self.x0, self.n0, self.step = header['x0'], header['n0'], header['step']
        self.source, self.test_only = source or {}, test_only
        count, minimum, maximum = 0, math.inf, -math.inf
        for index, valid in enumerate(mask):
            if valid:
                height = struct.unpack_from('<f', data, index * 4)[0]
                count += 1
                minimum, maximum = min(minimum, height), max(maximum, height)
        self.stats = {'nodes': self.cols * self.rows, 'valid': count,
                      'noData': self.cols * self.rows - count,
                      'minM': minimum, 'maxM': maximum}

    def node(self, col, row):
        if col < 0 or row < 0 or col >= self.cols or row >= self.rows:
            return None
        index = row * self.cols + col
        return struct.unpack_from('<f', self.data, index * 4)[0] if self.mask[index] else None

    def sample(self, easting, northing):
        """The same fixed diagonal and strict NoData rule as the game sampler."""
        if not _finite(easting) or not _finite(northing):
            return None
        gx, gy = (easting - self.x0) / self.step, (self.n0 - northing) / self.step
        if gx < -1e-7 or gy < -1e-7 or gx > self.cols - 1 + 1e-7 or gy > self.rows - 1 + 1e-7:
            return None
        gx, gy = max(0, min(self.cols - 1, gx)), max(0, min(self.rows - 1, gy))
        col, row = min(self.cols - 2, math.floor(gx)), min(self.rows - 2, math.floor(gy))
        u, v = gx - col, gy - row
        if u + v <= 1:
            heights = (self.node(col, row), self.node(col + 1, row), self.node(col, row + 1))
            weights = (1 - u - v, u, v)
        else:
            heights = (self.node(col + 1, row + 1), self.node(col, row + 1), self.node(col + 1, row))
            weights = (u + v - 1, 1 - u, 1 - v)
        if any(height is None and weight > 1e-7 for height, weight in zip(heights, weights)):
            return None
        return sum((height if height is not None else 0) * weight for height, weight in zip(heights, weights))


def validate_grid(pack, expected_bounds=None):
    """Validate the exact terrain-grid/1 bytes, checksum, CRS, datum and mask."""
    if not isinstance(pack, dict) or pack.get('schema') != GRID_SCHEMA or pack.get('encoding') != 'float32-le+valid-u8':
        raise TerrainError('Format de grille de relief incompatible.')
    header_text = pack.get('gridHeader')
    if not isinstance(header_text, str) or len(header_text) > 10000:
        raise TerrainError('Entête de grille invalide.')
    try:
        header = json.loads(header_text)
    except (TypeError, ValueError) as error:
        raise TerrainError('Entête de grille JSON invalide.') from error
    if not isinstance(header, dict):
        raise TerrainError('Entête de grille invalide.')
    for key, value in {'crs': 'EPSG:2154', 'units': 'm', 'verticalDatum': 'NGF-IGN69',
                       'rowOrder': 'north-to-south', 'nodeRegistration': 'grid-node',
                       'interpolation': 'fixed-diagonal-triangles'}.items():
        if header.get(key) != value:
            raise TerrainError(f'Convention de relief incompatible : {key}.')
    cols, rows, step = header.get('cols'), header.get('rows'), header.get('step')
    if (not isinstance(cols, int) or isinstance(cols, bool) or not isinstance(rows, int) or isinstance(rows, bool)
            or cols < 2 or rows < 2 or cols * rows > MAX_GRID_NODES
            or not _finite(step) or not .5 <= step <= 25
            or not all(_finite(header.get(key)) for key in ('x0', 'n0'))):
        raise TerrainError('Dimensions de grille hors budget.')
    bounds = header.get('boundsL93')
    if (not isinstance(bounds, list) or len(bounds) != 4 or not all(_finite(v) for v in bounds)
            or bounds[0] >= bounds[2] or bounds[1] >= bounds[3]):
        raise TerrainError('Emprise de grille invalide.')
    if expected_bounds is not None and (len(expected_bounds) != 4 or any(abs(a - b) > TOLERANCE for a, b in zip(bounds, expected_bounds))):
        raise TerrainError('Emprise de grille inattendue.')
    if (header['x0'] > bounds[0] + TOLERANCE or header['x0'] + (cols - 1) * step < bounds[2] - TOLERANCE
            or header['n0'] < bounds[3] - TOLERANCE or header['n0'] - (rows - 1) * step > bounds[1] + TOLERANCE):
        raise TerrainError('La grille ne couvre pas son emprise déclarée.')
    count = cols * rows
    blobs = []
    for key, byte_count in [('dataBase64', count * 4), ('maskBase64', count)]:
        value = pack.get(key)
        if not isinstance(value, str) or len(value) > 4 * math.ceil(byte_count / 3):
            raise TerrainError(f'Taille invalide : {key}.')
        try:
            raw = base64.b64decode(value, validate=True)
        except ValueError as error:
            raise TerrainError(f'Base64 invalide : {key}.') from error
        if len(raw) != byte_count:
            raise TerrainError(f'Données tronquées : {key}.')
        blobs.append(raw)
    data, mask = blobs
    if grid_digest(header_text, data, mask) != pack.get('sha256'):
        raise TerrainError('Empreinte de grille incorrecte.')
    valid = 0
    for i, value in enumerate(mask):
        if value not in (0, 1):
            raise TerrainError('Le masque doit contenir uniquement 0 ou 1.')
        if value:
            height = struct.unpack_from('<f', data, i * 4)[0]
            if not math.isfinite(height) or not -500 <= height <= 9000:
                raise TerrainError('Altitude valide hors limites.')
            valid += 1
    if not valid:
        raise TerrainError('La grille ne contient aucune altitude valide.')
    return TerrainGrid(header, data, mask, pack['sha256'], pack.get('source'), pack.get('testOnly') is True)


def _tile_header(bounds, step):
    if (not isinstance(bounds, (list, tuple)) or len(bounds) != 4 or not all(_finite(v) for v in bounds)
            or abs(bounds[2] - bounds[0] - CELL_SIZE) > TOLERANCE
            or abs(bounds[3] - bounds[1] - CELL_SIZE) > TOLERANCE):
        raise TerrainError('Une emprise Lambert-93 de 250 × 250 m est requise.')
    if step not in STEPS or isinstance(step, bool):
        raise TerrainError('Le pas de sortie doit être 1, 5 ou 25 m.')
    step = int(step)
    side = CELL_SIZE // step + 3
    if side * side > MAX_TILE_NODES:
        raise TerrainError('Tuile de relief hors budget.')
    return {'boundsL93': list(bounds), 'cols': side, 'rows': side, 'crs': 'EPSG:2154',
            'x0': bounds[0] - step, 'n0': bounds[3] + step, 'step': step,
            'units': 'm', 'verticalDatum': 'NGF-IGN69', 'haloNodes': 1,
            'interpolation': 'fixed-diagonal-triangles', 'nodeRegistration': 'grid-node',
            'rowOrder': 'north-to-south'}


def _pack(header, data, mask, source):
    if not any(mask):
        return None
    header_text = _json_bytes(header).decode('utf-8')
    source = dict(source)
    receipt = source.get('receipt') or {}
    synthetic = (source.get('testOnly') is True or receipt.get('testOnly') is True
                 or str(source.get('truth', '')).startswith('fixture')
                 or str(receipt.get('truth', '')).startswith('fixture'))
    if synthetic:
        source['truth'] = 'fixture'
    pack = {'schema': GRID_SCHEMA, 'encoding': 'float32-le+valid-u8',
            'gridHeader': header_text, 'dataBase64': base64.b64encode(data).decode('ascii'),
            'maskBase64': base64.b64encode(mask).decode('ascii'),
            'sha256': grid_digest(header_text, data, mask), 'source': source, 'certified': False}
    if synthetic:
        pack['testOnly'] = True
    pack['stats'] = validate_grid(pack).stats
    return pack


def tile_from_grid(grid, bounds_l93, source_receipt=None):
    """Retile aligned source nodes byte-for-byte, including signed zero and NoData."""
    if not isinstance(grid, TerrainGrid):
        grid = validate_grid(grid)
    if grid.step not in STEPS:
        raise TerrainError('Le pas source ne permet pas un re-tuilage sans rééchantillonnage.')
    header = _tile_header(bounds_l93, grid.step)
    col_offset = (header['x0'] - grid.x0) / grid.step
    row_offset = (grid.n0 - header['n0']) / grid.step
    if abs(col_offset - round(col_offset)) > TOLERANCE or abs(row_offset - round(row_offset)) > TOLERANCE:
        raise TerrainError('La tuile ne s’aligne pas sur les nœuds source ; aucun rééchantillonnage implicite.')
    col_offset, row_offset = round(col_offset), round(row_offset)
    count = header['cols'] * header['rows']
    data, mask = bytearray(count * 4), bytearray(count)
    for row in range(header['rows']):
        sr = row_offset + row
        if not 0 <= sr < grid.rows:
            continue
        for col in range(header['cols']):
            sc = col_offset + col
            if not 0 <= sc < grid.cols:
                continue
            target, original = row * header['cols'] + col, sr * grid.cols + sc
            data[target * 4:target * 4 + 4] = grid.data[original * 4:original * 4 + 4]
            mask[target] = grid.mask[original]
    source = {'truth': 'derived-grid', 'method': 'node-copy-no-resampling',
              'sourceGridSHA256': grid.sha256, 'sourceNodeValuesUnchanged': True,
              'crs': 'EPSG:2154', 'verticalDatum': 'NGF-IGN69', 'units': 'm',
              'receipt': source_receipt if source_receipt is not None else grid.source,
              'testOnly': grid.test_only}
    return _pack(header, bytes(data), bytes(mask), source)


def _receipt(value):
    receipt = _read_json(value)
    for key in ('provider', 'product', 'license', 'attribution'):
        if not isinstance(receipt.get(key), str) or not receipt[key].strip():
            raise TerrainError(f'Provenance GeoTIFF manquante : {key}.')
    if receipt.get('verticalDatum') != 'NGF-IGN69' or receipt.get('units') != 'm':
        raise TerrainError('Le datum NGF-IGN69 et les unités m doivent être déclarés explicitement.')
    return dict(receipt)


class RasterMosaic:
    """Lazy, bounded windows over aligned EPSG:2154 rasters, without a giant merge.

    Four-corner interpolation is strict: missing/NoData corners never get filled
    from the remaining corners. Adjacent raster files may supply those corners.
    Conflicting overlapping valid samples stop generation rather than choosing
    silently between two surveys.
    """
    def __init__(self, paths, receipt, max_window_pixels=MAX_WINDOW_PIXELS):
        try:
            import rasterio
        except ImportError as error:
            raise TerrainError('Rasterio est requis pour générer des tuiles GeoTIFF, pas pour jouer.') from error
        self.rasterio, self.receipt = rasterio, _receipt(receipt)
        self.sources, self.handles = [], OrderedDict()
        self.max_window_pixels = max_window_pixels
        if not isinstance(paths, (list, tuple)):
            paths = [paths]
        if not paths:
            raise TerrainError('Au moins un raster source est requis.')
        seen = set()
        for value in paths:
            path = Path(value).resolve()
            if path in seen:
                raise TerrainError('Le même raster source est fourni plusieurs fois.')
            seen.add(path)
            with rasterio.open(path) as src:
                if src.crs is None or src.crs.to_epsg() != 2154:
                    raise TerrainError('Les sources GeoTIFF doivent être en EPSG:2154 ; aucune reprojection implicite.')
                if src.count != 1 or src.width < 2 or src.height < 2:
                    raise TerrainError('Un MNT monobande géoréférencé est requis.')
                if str(src.dtypes[0]).startswith('complex'):
                    raise TerrainError('Un MNT doit contenir des altitudes réelles, pas des nombres complexes.')
                t = src.transform
                if t.a <= 0 or t.e >= 0 or abs(t.b) > 1e-12 or abs(t.d) > 1e-12:
                    raise TerrainError('Le raster doit être orienté nord en haut, sans rotation.')
                unit = src.units[0] if src.units else None
                if unit and unit.lower() not in ('m', 'metre', 'meter', 'metres', 'meters'):
                    raise TerrainError('Unité verticale raster incompatible avec les mètres déclarés.')
                for key, datum in src.tags().items():
                    if key.lower().replace('_', '') in ('verticaldatum', 'verticalcrs') and datum not in ('NGF-IGN69', 'EPSG:5720'):
                        raise TerrainError('Le datum vertical du raster contredit la déclaration NGF-IGN69.')
                if not self.sources:
                    self.x0, self.n0, self.dx, self.dy = t.c, t.f, t.a, -t.e
                if abs(t.a - self.dx) > 1e-9 or abs(-t.e - self.dy) > 1e-9:
                    raise TerrainError('Les rasters mosaïqués doivent partager la même résolution native.')
                col, row = (t.c - self.x0) / self.dx, (self.n0 - t.f) / self.dy
                if abs(col - round(col)) > TOLERANCE or abs(row - round(row)) > TOLERANCE:
                    raise TerrainError('Les rasters mosaïqués doivent partager le même carroyage natif.')
                self.sources.append({'path': path, 'col': round(col), 'row': round(row),
                                     'width': src.width, 'height': src.height,
                                     **file_fingerprint(path)})
        if self.receipt.get('sha256'):
            if len(self.sources) != 1:
                raise TerrainError('Une empreinte unique dans le reçu ne peut pas identifier plusieurs rasters.')
            if self.receipt['sha256'] != self.sources[0]['sha256']:
                raise TerrainError('L’empreinte du raster ne correspond pas au reçu fourni.')

    def close(self):
        for handle in self.handles.values():
            handle.close()
        self.handles.clear()

    def _handle(self, path):
        if path in self.handles:
            self.handles.move_to_end(path)
            return self.handles[path]
        if len(self.handles) >= 8:
            _, handle = self.handles.popitem(last=False)
            handle.close()
        self.handles[path] = self.rasterio.open(path)
        return self.handles[path]

    def tile(self, bounds_l93, step):
        from rasterio.windows import Window
        header = _tile_header(bounds_l93, step)
        if step + 1e-9 < max(self.dx, self.dy):
            raise TerrainError('Suréchantillonnage refusé : le pas demandé est plus fin que le raster source.')
        # Source pixel centres, not pixel corners, are the MNT sample locations.
        left = math.floor((header['x0'] - self.x0) / self.dx - .5)
        right = math.floor((header['x0'] + (header['cols'] - 1) * step - self.x0) / self.dx - .5) + 1
        top = math.floor((self.n0 - header['n0']) / self.dy - .5)
        bottom = math.floor((self.n0 - (header['n0'] - (header['rows'] - 1) * step)) / self.dy - .5) + 1
        windows, used_sources = [], []
        budget = 0
        for source in self.sources:
            c0, r0 = max(left, source['col']), max(top, source['row'])
            c1 = min(right, source['col'] + source['width'] - 1)
            r1 = min(bottom, source['row'] + source['height'] - 1)
            if c1 < c0 or r1 < r0:
                continue
            budget += (c1 - c0 + 1) * (r1 - r0 + 1)
            if budget > self.max_window_pixels:
                raise TerrainError('Fenêtres raster hors budget mémoire ; choisir un MNT adapté au LOD demandé.')
            data = self._handle(source['path']).read(1, window=Window(c0 - source['col'], r0 - source['row'], c1 - c0 + 1, r1 - r0 + 1), masked=True)
            windows.append((c0, r0, c1, r1, data))
            used_sources.append(source)

        def native_node(col, row):
            found = None
            for c0, r0, c1, r1, image in windows:
                if not c0 <= col <= c1 or not r0 <= row <= r1:
                    continue
                value = image[row - r0, col - c0]
                # numpy masked scalars have a truthy mask; zero is valid ground.
                if bool(getattr(value, 'mask', False)):
                    continue
                number = float(value)
                if not math.isfinite(number) or not -500 <= number <= 9000:
                    raise TerrainError('Altitude raster non masquée hors limites ; vérifier le datum et les NoData.')
                if found is not None and abs(found - number) > 1e-6:
                    raise TerrainError('Altitudes contradictoires dans le chevauchement de deux MNT.')
                found = number
            return found

        count = header['cols'] * header['rows']
        values, mask = bytearray(count * 4), bytearray(count)
        for row in range(header['rows']):
            north = header['n0'] - row * step
            gy = (self.n0 - north) / self.dy - .5
            iy, v = math.floor(gy), gy - math.floor(gy)
            for col in range(header['cols']):
                east = header['x0'] + col * step
                gx = (east - self.x0) / self.dx - .5
                ix, u = math.floor(gx), gx - math.floor(gx)
                weighted = [(ix, iy, (1-u)*(1-v)), (ix+1, iy, u*(1-v)),
                            (ix, iy+1, (1-u)*v), (ix+1, iy+1, u*v)]
                height, valid = 0., True
                for sx, sy, weight in weighted:
                    if weight <= 1e-12:
                        continue
                    sample = native_node(sx, sy)
                    if sample is None:
                        valid = False
                        break
                    height += weight * sample
                if valid:
                    index = row * header['cols'] + col
                    struct.pack_into('<f', values, index * 4, height)
                    mask[index] = 1
        source = {'truth': 'derived-raster', 'method': 'strict-bilinear-at-grid-nodes',
                  'crs': 'EPSG:2154', 'verticalDatum': 'NGF-IGN69', 'units': 'm',
                  'verticalDatumVerification': 'declared-in-receipt',
                  'nativePixelSizeM': [self.dx, self.dy], 'receipt': self.receipt,
                  'files': [{k: s[k] for k in ('name', 'bytes', 'sha256')} for s in used_sources]}
        return _pack(header, bytes(values), bytes(mask), source)


def _cells_manifest(value):
    manifest = _read_json(value)
    if manifest.get('schema') not in (VECTOR_SCHEMA, TARGET_SCHEMA) or manifest.get('crs') != 'EPSG:2154' or manifest.get('cellSize') != CELL_SIZE:
        raise TerrainError('Un manifeste vector-tiles/1 ou terrain-target-cells/1 en EPSG:2154, cellules de 250 m, est requis.')
    if manifest['schema'] == TARGET_SCHEMA:
        if not isinstance(manifest.get('boundarySHA256'), str) or not re.fullmatch(r'[a-f0-9]{64}', manifest['boundarySHA256']):
            raise TerrainError('L’empreinte du contour administratif des cellules de relief est requise.')
        if any(key in manifest for key in ('featureCollection', 'vector')):
            raise TerrainError('Une définition de cellules de relief ne déclare aucune couche vectorielle.')
    origin = manifest.get('origin', manifest.get('originL93'))
    if not isinstance(origin, (list, tuple)) or len(origin) != 2 or not all(_finite(v) for v in origin):
        raise TerrainError('L’origine Lambert-93 du carroyage est requise.')
    if 'origin' in manifest and 'originL93' in manifest and manifest['origin'] != manifest['originL93']:
        raise TerrainError('Deux origines de carroyage contradictoires sont déclarées.')
    tiles = manifest.get('tiles')
    if not isinstance(tiles, list) or not tiles or len(tiles) > 250_000:
        raise TerrainError('Liste des cellules absente ou hors budget.')
    seen, bounds_seen = set(), set()
    for tile in tiles:
        if manifest['schema'] == TARGET_SCHEMA and isinstance(tile, dict) and any(key in tile for key in ('featureCollection', 'vector', 'v53Validated')):
            raise TerrainError('Une cellule cible du relief ne peut pas déclarer de donnée vectorielle.')
        if not isinstance(tile, dict) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,120}', tile.get('cellId', '')):
            raise TerrainError('Identifiant de cellule absent ou dangereux.')
        if tile['cellId'] in seen:
            raise TerrainError('Identifiant de cellule dupliqué.')
        seen.add(tile['cellId'])
        _tile_header(tile.get('boundsL93'), 25)
        bounds_key = tuple(tile['boundsL93'])
        if bounds_key in bounds_seen:
            raise TerrainError('Deux identifiants déclarent la même emprise de cellule.')
        bounds_seen.add(bounds_key)
        for key in ('gridX', 'gridY'):
            if not isinstance(tile.get(key), int) or isinstance(tile.get(key), bool):
                raise TerrainError(f'Index de carroyage invalide : {key}.')
        center = [origin[0] + tile['gridX'] * CELL_SIZE, origin[1] - tile['gridY'] * CELL_SIZE]
        expected = [center[0] - 125, center[1] - 125, center[0] + 125, center[1] + 125]
        if any(abs(a - b) > TOLERANCE for a, b in zip(tile['boundsL93'], expected)):
            raise TerrainError('L’emprise de cellule contredit son index et l’origine du carroyage.')
    return manifest


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != data:
        raise TerrainError(f'Sortie existante différente conservée : {path}')
    if not path.exists():
        with path.open('xb') as stream:
            stream.write(data)


def _gzip(data):
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, filename='', mode='wb', mtime=0) as stream:
        stream.write(data)
    return buffer.getvalue()


def _write_tiles(cells, output_dir, make_tile, source):
    output = Path(output_dir)
    manifest = {'schema': TILES_SCHEMA, 'crs': 'EPSG:2154', 'units': 'm',
                'verticalDatum': 'NGF-IGN69', 'cellSize': CELL_SIZE,
                'origin': cells.get('origin', cells.get('originL93')), 'source': source,
                'certified': False, 'tiles': []}
    if cells['schema'] == TARGET_SCHEMA:
        manifest.update(terrainOnly=True, vectorCoverageClaimed=False,
                        targetDefinition={'schema': TARGET_SCHEMA,
                                          'boundarySHA256': cells['boundarySHA256']})
    counts = {'targetCells': len(cells['tiles']), 'completeCells': 0, 'partialCells': 0, 'missingCells': 0}
    for cell in cells['tiles']:
        item = {k: cell[k] for k in ('cellId', 'gridX', 'gridY', 'boundsL93')}
        pack = make_tile(cell['boundsL93'])
        if pack is None:
            item.update(terrain=None, coverage='missing', reason='no-valid-source-nodes')
            counts['missingCells'] += 1
        else:
            grid = validate_grid(pack)
            # Completeness refers to useful cell nodes; halo validity is also
            # explicit and never silently filled from another altitude.
            complete = all(grid.mask[row * grid.cols + col] for row in range(1, grid.rows - 1) for col in range(1, grid.cols - 1))
            relative = f'tiles/{cell["cellId"]}.terrain-{grid.step}m.json.gz'
            raw = _gzip(_json_bytes(pack))
            _write(output / relative, raw)
            item.update(terrain={'path': relative, 'sha256': hashlib.sha256(raw).hexdigest(),
                                 'bytes': len(raw), 'encoding': 'gzip-json',
                                 'gridSHA256': pack['sha256'], 'stepM': grid.step,
                                 'nodes': grid.stats['nodes'], 'validNodes': grid.stats['valid'],
                                 'noDataNodes': grid.stats['noData'], 'complete': complete},
                        coverage='complete' if complete else 'partial')
            if pack.get('testOnly'):
                item['terrain']['testOnly'] = True
                manifest['testOnly'] = True
            counts['completeCells' if complete else 'partialCells'] += 1
        manifest['tiles'].append(item)
    manifest['coverage'] = counts
    _write(output / 'manifest.json', _json_bytes(manifest) + b'\n')
    return manifest


def tiles_from_grid(source_path, cells_manifest, output_dir):
    cells, source_pack = _cells_manifest(cells_manifest), _read_json(source_path)
    grid = validate_grid(source_pack)
    source = {'method': 'node-copy-no-resampling', 'gridSHA256': grid.sha256,
              'crs': 'EPSG:2154', 'verticalDatum': 'NGF-IGN69', 'units': 'm',
              'file': file_fingerprint(source_path), 'receipt': source_pack.get('source', {})}
    return _write_tiles(cells, output_dir,
                        lambda bounds: tile_from_grid(grid, bounds, source_pack.get('source')),
                        source)


def tiles_from_geotiff(raster_paths, cells_manifest, output_dir, step, receipt):
    cells = _cells_manifest(cells_manifest)
    if step not in STEPS:
        raise TerrainError('Le pas doit être 1, 5 ou 25 m.')
    mosaic = RasterMosaic(raster_paths, receipt)
    try:
        source = {'method': 'strict-bilinear-at-grid-nodes', 'receipt': mosaic.receipt,
                  'crs': 'EPSG:2154', 'verticalDatum': 'NGF-IGN69', 'units': 'm',
                  'files': [{k: s[k] for k in ('name', 'bytes', 'sha256')} for s in mosaic.sources],
                  'nativePixelSizeM': [mosaic.dx, mosaic.dy], 'verticalDatumVerification': 'declared-in-receipt'}
        return _write_tiles(cells, output_dir, lambda bounds: mosaic.tile(bounds, step), source)
    finally:
        mosaic.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    inspect = sub.add_parser('inspect', help='vérifier une grille sans afficher les données encodées')
    inspect.add_argument('--grid', required=True, type=Path)
    existing = sub.add_parser('from-grid', help='re-tuiler les mêmes nœuds sans rééchantillonnage')
    existing.add_argument('--grid', required=True, type=Path)
    raster = sub.add_parser('from-geotiff', help='préparer des MNT locaux avec NoData strict')
    raster.add_argument('--raster', required=True, action='append', type=Path)
    raster.add_argument('--receipt', required=True, type=Path)
    raster.add_argument('--step', required=True, type=int, choices=STEPS)
    for item in (existing, raster):
        item.add_argument('--cells', required=True, type=Path)
        item.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'inspect':
            grid = validate_grid(_read_json(args.grid))
            result = {'sha256': grid.sha256, 'header': grid.header, 'stats': grid.stats}
        elif args.command == 'from-grid':
            manifest = tiles_from_grid(args.grid, args.cells, args.output)
            result = {'manifest': str(args.output / 'manifest.json'), 'coverage': manifest['coverage']}
        else:
            manifest = tiles_from_geotiff(args.raster, args.cells, args.output, args.step, args.receipt)
            result = {'manifest': str(args.output / 'manifest.json'), 'coverage': manifest['coverage']}
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except (TerrainError, OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f'Préparation du relief impossible : {error}\n')


if __name__ == '__main__':
    raise SystemExit(main())
