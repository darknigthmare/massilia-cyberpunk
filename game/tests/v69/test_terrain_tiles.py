"""Terrain contract, exact legacy node conservation and real GeoTIFF ingestion."""
import base64
import copy
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

GAME = Path(__file__).resolve().parents[2]
MODULE = GAME / 'tools/v69/terrain_tiles.py'
SPEC = importlib.util.spec_from_file_location('massilia_terrain69', MODULE)
T = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(T)
try:
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin
except ImportError:
    rasterio = None


def make_grid(bounds=(1000, 2000, 1250, 2250), step=25, invalid=()):
    cols = round((bounds[2] - bounds[0]) / step) + 3
    rows = round((bounds[3] - bounds[1]) / step) + 3
    header = {'boundsL93': list(bounds), 'cols': cols, 'rows': rows,
              'crs': 'EPSG:2154', 'x0': bounds[0] - step,
              'n0': bounds[3] + step, 'step': step, 'units': 'm',
              'verticalDatum': 'NGF-IGN69', 'haloNodes': 1,
              'interpolation': 'fixed-diagonal-triangles',
              'nodeRegistration': 'grid-node', 'rowOrder': 'north-to-south'}
    values = bytearray(cols * rows * 4)
    mask = bytearray([1] * (cols * rows))
    for row in range(rows):
        for col in range(cols):
            struct.pack_into('<f', values, (row * cols + col) * 4, row * 5.25 + col * .125)
    struct.pack_into('<f', values, 0, -0.0)
    for index in invalid:
        mask[index] = 0
    return T._pack(header, bytes(values), bytes(mask), {'truth': 'fixture-only',
                   'license': 'Test', 'attribution': 'Test synthetic grid'})


def change_payload(pack, *, data=None, mask=None, header=None):
    result = copy.deepcopy(pack)
    raw_data = data if data is not None else base64.b64decode(pack['dataBase64'])
    raw_mask = mask if mask is not None else base64.b64decode(pack['maskBase64'])
    if header is not None:
        result['gridHeader'] = json.dumps(header, sort_keys=True, separators=(',', ':'))
    result['dataBase64'] = base64.b64encode(raw_data).decode('ascii')
    result['maskBase64'] = base64.b64encode(raw_mask).decode('ascii')
    result['sha256'] = T.grid_digest(result['gridHeader'], raw_data, raw_mask)
    return result


def cells(*bounds):
    return {'schema': T.VECTOR_SCHEMA, 'crs': 'EPSG:2154',
            'origin': [1125, 2125], 'cellSize': 250,
            'tiles': [{'cellId': f'CELL-{i}',
                       'gridX': round(((bound[0] + bound[2]) / 2 - 1125) / 250),
                       'gridY': round((2125 - (bound[1] + bound[3]) / 2) / 250),
                       'boundsL93': list(bound), 'vector': None, 'terrain': None,
                       'navigation': None} for i, bound in enumerate(bounds)]}


RECEIPT = {'provider': 'Synthetic test provider', 'product': 'Synthetic analytical plane',
           'license': 'Test-only', 'attribution': 'Synthetic, not IGN observations',
           'verticalDatum': 'NGF-IGN69', 'units': 'm', 'testOnly': True}


class GridTests(unittest.TestCase):
    def test_valid_zero_and_signed_zero_are_not_nodata(self):
        grid = T.validate_grid(make_grid())
        self.assertEqual(grid.node(0, 0), 0)
        self.assertEqual(struct.pack('<f', grid.node(0, 0)), b'\x00\x00\x00\x80')
        self.assertEqual(grid.sample(grid.x0, grid.n0), 0)
        self.assertIsNone(grid.sample(grid.x0 - 1, grid.n0))

    def test_checksum_changes_are_rejected(self):
        pack = make_grid()
        raw = bytearray(base64.b64decode(pack['dataBase64']))
        raw[10] ^= 1
        pack['dataBase64'] = base64.b64encode(raw).decode('ascii')
        with self.assertRaisesRegex(T.TerrainError, 'Empreinte'):
            T.validate_grid(pack)

    def test_invalid_mask_and_valid_nan_are_rejected(self):
        pack = make_grid()
        mask = bytearray(base64.b64decode(pack['maskBase64']))
        mask[0] = 2
        with self.assertRaisesRegex(T.TerrainError, 'masque'):
            T.validate_grid(change_payload(pack, mask=mask))
        raw = bytearray(base64.b64decode(pack['dataBase64']))
        struct.pack_into('<f', raw, 0, float('nan'))
        with self.assertRaisesRegex(T.TerrainError, 'Altitude'):
            T.validate_grid(change_payload(pack, data=raw))

    def test_crs_datum_and_dimensions_are_checked_before_decoding(self):
        pack = make_grid()
        for field, wrong in [('crs', 'EPSG:4326'), ('verticalDatum', 'EGM96'),
                             ('units', 'ft'), ('rowOrder', 'south-to-north'),
                             ('interpolation', 'bilinear')]:
            with self.subTest(field=field):
                h = json.loads(pack['gridHeader']); h[field] = wrong
                with self.assertRaises(T.TerrainError):
                    T.validate_grid(change_payload(pack, header=h))
        h = json.loads(pack['gridHeader']); h['cols'] = h['rows'] = 5000
        with self.assertRaisesRegex(T.TerrainError, 'budget'):
            T.validate_grid(change_payload(pack, header=h))

    def test_all_nodata_is_not_an_installable_grid(self):
        pack = make_grid()
        mask = bytes(len(base64.b64decode(pack['maskBase64'])))
        with self.assertRaisesRegex(T.TerrainError, 'aucune altitude'):
            T.validate_grid(change_payload(pack, mask=mask))

    def test_masked_missing_corner_is_not_interpolated_as_zero(self):
        grid = T.validate_grid(make_grid(invalid=(0,)))
        self.assertIsNone(grid.node(0, 0))
        self.assertIsNone(grid.sample(grid.x0 + 5, grid.n0 - 5))
        self.assertEqual(grid.sample(grid.x0 + 25, grid.n0), grid.node(1, 0))

    def test_retile_is_exact_for_every_float32_and_mask_byte(self):
        pack = make_grid(invalid=(7, 80))
        before = json.dumps(pack, sort_keys=True)
        grid = T.validate_grid(pack)
        tile = T.validate_grid(T.tile_from_grid(grid, [1000, 2000, 1250, 2250]))
        self.assertEqual(tile.data, grid.data)
        self.assertEqual(tile.mask, grid.mask)
        self.assertEqual(tile.sample(1113.5, 2142.75), grid.sample(1113.5, 2142.75))
        self.assertEqual(json.dumps(pack, sort_keys=True), before)

    def test_adjacent_tiles_share_identical_nodes_and_halo(self):
        source = T.validate_grid(make_grid((1000, 2000, 1500, 2250)))
        a = T.validate_grid(T.tile_from_grid(source, [1000, 2000, 1250, 2250]))
        b = T.validate_grid(T.tile_from_grid(source, [1250, 2000, 1500, 2250]))
        for row in range(a.rows):
            ai = (row * a.cols + 10) * 4
            bi = row * b.cols * 4
            self.assertEqual(a.data[ai:ai + 12], b.data[bi:bi + 12])
            self.assertEqual(a.mask[row * a.cols + 10:row * a.cols + 13],
                             b.mask[row * b.cols:row * b.cols + 3])

    def test_misalignment_does_not_trigger_implicit_resampling(self):
        with self.assertRaisesRegex(T.TerrainError, 'rééchantillonnage'):
            T.tile_from_grid(make_grid(), [1000.5, 2000, 1250.5, 2250])

    def test_partial_and_absent_coverage_remain_explicit(self):
        source = T.validate_grid(make_grid())
        adjacent = T.validate_grid(T.tile_from_grid(source, [1250, 2000, 1500, 2250]))
        self.assertGreater(adjacent.stats['noData'], 0)
        self.assertIsNone(adjacent.node(12, 6))
        self.assertIsNone(T.tile_from_grid(source, [5000, 5000, 5250, 5250]))

    def test_manifest_assets_are_deterministic_and_preserve_existing_outputs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); source = root / 'source.json'
            source.write_text(json.dumps(make_grid()))
            target = cells([1000, 2000, 1250, 2250], [1250, 2000, 1500, 2250], [5000, 5000, 5250, 5250])
            a = T.tiles_from_grid(source, target, root / 'a')
            b = T.tiles_from_grid(source, target, root / 'b')
            self.assertEqual(a, b)
            self.assertEqual(a['coverage'], {'targetCells': 3, 'completeCells': 1,
                                           'partialCells': 1, 'missingCells': 1})
            self.assertIsNone(a['tiles'][2]['terrain'])
            link = a['tiles'][0]['terrain']
            raw = (root / 'a' / link['path']).read_bytes()
            self.assertEqual(raw, (root / 'b' / link['path']).read_bytes())
            self.assertEqual(hashlib.sha256(raw).hexdigest(), link['sha256'])
            T.validate_grid(json.loads(gzip.decompress(raw)))
            self.assertEqual(a, T.tiles_from_grid(source, target, root / 'a'))
            asset = root / 'a' / link['path']; asset.write_bytes(b'user output')
            with self.assertRaisesRegex(T.TerrainError, 'conservée'):
                T.tiles_from_grid(source, target, root / 'a')
            self.assertEqual(asset.read_bytes(), b'user output')

    def test_unsafe_ids_duplicate_cells_and_bad_target_budgets_are_rejected(self):
        for invalid in [cells(), cells([1000, 2000, 1250, 2250], [1000, 2000, 1250, 2250])]:
            with self.assertRaises(T.TerrainError): T._cells_manifest(invalid)
        bad = cells([1000, 2000, 1250, 2250]); bad['tiles'][0]['cellId'] = '../escape'
        with self.assertRaises(T.TerrainError): T._cells_manifest(bad)
        with self.assertRaises(T.TerrainError): T._tile_header([1000, 2000, 1251, 2250], 25)
        with self.assertRaises(T.TerrainError): T._tile_header([1000, 2000, 1250, 2250], .5)

    def test_administrative_terrain_targets_never_claim_vector_coverage(self):
        target = cells([1000, 2000, 1250, 2250])
        target.update(schema=T.TARGET_SCHEMA, boundarySHA256='b' * 64)
        for tile in target['tiles']:
            for key in ('vector', 'terrain', 'navigation'):
                del tile[key]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root / 'source.json'
            source.write_text(json.dumps(make_grid()))
            result = T.tiles_from_grid(source, target, root / 'terrain')
        self.assertTrue(result['terrainOnly'])
        self.assertFalse(result['vectorCoverageClaimed'])
        self.assertEqual(result['targetDefinition'], {'schema': T.TARGET_SCHEMA, 'boundarySHA256': 'b' * 64})
        self.assertNotIn('vector', result['tiles'][0])

    def test_terrain_target_boundary_provenance_and_vector_claims_are_rejected(self):
        target = cells([1000, 2000, 1250, 2250])
        target['schema'] = T.TARGET_SCHEMA
        for bad_sha in (None, 'short', 123):
            target['boundarySHA256'] = bad_sha
            with self.subTest(boundarySHA256=bad_sha), self.assertRaisesRegex(T.TerrainError, 'contour administratif'):
                T._cells_manifest(target)
        target['boundarySHA256'] = 'a' * 64
        with self.assertRaisesRegex(T.TerrainError, 'vectorielle'):
            T._cells_manifest(target)
        del target['tiles'][0]['vector']
        target['tiles'][0]['gridY'] = 1
        with self.assertRaisesRegex(T.TerrainError, 'contredit'):
            T._cells_manifest(target)

    def test_cell_origin_and_grid_indexes_cannot_silently_relabel_coverage(self):
        target = cells([1000, 2000, 1250, 2250])
        target['tiles'][0]['gridX'] = 1
        with self.assertRaisesRegex(T.TerrainError, 'contredit'):
            T._cells_manifest(target)
        target = cells([1000, 2000, 1250, 2250]); del target['origin']
        with self.assertRaisesRegex(T.TerrainError, 'origine'):
            T._cells_manifest(target)

    def test_declared_fixtures_stay_fixture_marked_after_retiling(self):
        original = make_grid()
        tile = T.tile_from_grid(original, [1000, 2000, 1250, 2250], original['source'])
        self.assertTrue(tile['testOnly'])
        self.assertEqual(tile['source']['truth'], 'fixture')

    def test_actual_delivered_grid_retiles_without_changing_any_source_byte(self):
        source = GAME / 'data/v58/terrain.ign.json'
        original = source.read_bytes()
        pack = json.loads(original)
        grid = T.validate_grid(pack)
        self.assertEqual(grid.stats['nodes'], 17689)
        self.assertEqual(grid.stats['valid'], 17689)
        self.assertEqual(grid.sha256, '38eadcbdf00a64384e00923a85ce9886ec4d9a420d610dc9ccfd4449c41f344b')
        b = grid.header['boundsL93']
        for x in range(13):
            for y in range(13):
                bounds = [b[0] + x * 250, b[1] + y * 250,
                          b[0] + (x + 1) * 250, b[1] + (y + 1) * 250]
                tile = T.validate_grid(T.tile_from_grid(grid, bounds))
                for row in range(tile.rows):
                    sr = round((grid.n0 - tile.n0) / 25) + row
                    for col in range(tile.cols):
                        sc = round((tile.x0 - grid.x0) / 25) + col
                        i, j = (row * tile.cols + col) * 4, (sr * grid.cols + sc) * 4
                        self.assertEqual(tile.data[i:i + 4], grid.data[j:j + 4])
                self.assertEqual(tile.stats['noData'], 0)
        self.assertEqual(source.read_bytes(), original)

    def test_cli_inspect_reports_actual_stats_without_encoded_data(self):
        result = subprocess.run([sys.executable, str(MODULE), 'inspect', '--grid',
                                 str(GAME / 'data/v58/terrain.ign.json')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['stats']['nodes'], 17689)
        self.assertNotIn('Base64', result.stdout)


@unittest.skipUnless(rasterio is not None, 'Rasterio is optional outside the terrain-generation environment.')
class RasterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def raster(self, name='plane.tif', *, x=974.5, north=2275.5, width=301,
               height=301, resolution=1, crs='EPSG:2154', add=0., nodata_points=(), constant=None):
        cols, rows = np.meshgrid(np.arange(width), np.arange(height))
        east = x + (cols + .5) * resolution
        n = north - (rows + .5) * resolution
        data = ((east - 1000) * .1 + (n - 2000) * .2 + add).astype('float32')
        if constant is not None: data.fill(constant)
        for row, col in nodata_points: data[row, col] = -9999
        path = self.root / name
        with rasterio.open(path, 'w', driver='GTiff', width=width, height=height,
                           count=1, dtype='float32', nodata=-9999, crs=crs,
                           transform=from_origin(x, north, resolution, resolution)) as dataset:
            dataset.write(data, 1)
        return path

    def test_geotiff_nodes_follow_the_analytical_plane_and_keep_provenance(self):
        path = self.raster()
        mosaic = T.RasterMosaic(path, RECEIPT)
        try:
            pack = mosaic.tile([1000.25, 2000.25, 1250.25, 2250.25], 5)
            grid = T.validate_grid(pack)
            self.assertEqual(grid.cols, 53)
            self.assertEqual(grid.stats['noData'], 0)
            for col, row in [(0, 0), (12, 27), (52, 52)]:
                e, n = grid.x0 + col * 5, grid.n0 - row * 5
                self.assertAlmostEqual(grid.node(col, row), (e - 1000) * .1 + (n - 2000) * .2, places=4)
            self.assertEqual(pack['source']['files'][0]['sha256'], T.file_fingerprint(path)['sha256'])
            self.assertEqual(pack['source']['verticalDatumVerification'], 'declared-in-receipt')
            self.assertFalse(pack['certified'])
            self.assertTrue(pack['testOnly'])
            self.assertEqual(pack['source']['truth'], 'fixture')
        finally: mosaic.close()

    def test_nodata_corner_is_not_filled_by_bilinear_interpolation(self):
        path = self.raster(nodata_points=[(150, 150)])
        mosaic = T.RasterMosaic(path, RECEIPT)
        try:
            grid = T.validate_grid(mosaic.tile([1000.25, 2000.25, 1250.25, 2250.25], 25))
            self.assertIsNone(grid.node(6, 6))
            self.assertGreater(grid.stats['noData'], 0)
            self.assertIsNotNone(grid.node(5, 5))
        finally: mosaic.close()

    def test_zero_raster_height_is_valid_and_outside_coverage_is_missing(self):
        mosaic = T.RasterMosaic(self.raster(constant=0), RECEIPT)
        try:
            grid = T.validate_grid(mosaic.tile([1000, 2000, 1250, 2250], 25))
            self.assertEqual(grid.stats['valid'], 169)
            self.assertEqual(grid.sample(1125, 2125), 0)
            self.assertIsNone(mosaic.tile([5000, 5000, 5250, 5250], 25))
        finally: mosaic.close()

    def test_adjacent_geotiffs_supply_each_others_interpolation_corners(self):
        a = self.raster('a.tif', width=150)
        b = self.raster('b.tif', x=1124.5, width=151)
        mosaic = T.RasterMosaic([a, b], RECEIPT)
        try:
            pack = mosaic.tile([999.75, 1999.75, 1249.75, 2249.75], 25)
            grid = T.validate_grid(pack)
            self.assertAlmostEqual(grid.node(6, 6), 37.425, places=4)
            self.assertEqual(len(pack['source']['files']), 2)
        finally: mosaic.close()

    def test_conflicting_overlapping_surveys_stop_generation(self):
        mosaic = T.RasterMosaic([self.raster('a.tif'), self.raster('b.tif', add=1)], RECEIPT)
        try:
            with self.assertRaisesRegex(T.TerrainError, 'contradictoires'):
                mosaic.tile([1000, 2000, 1250, 2250], 25)
        finally: mosaic.close()

    def test_unmasked_invalid_height_is_not_silently_treated_as_missing(self):
        mosaic = T.RasterMosaic(self.raster(constant=10000), RECEIPT)
        try:
            with self.assertRaisesRegex(T.TerrainError, 'hors limites'):
                mosaic.tile([1000, 2000, 1250, 2250], 25)
        finally: mosaic.close()

    def test_crs_datum_receipt_resolution_and_file_hash_are_verified(self):
        with self.assertRaisesRegex(T.TerrainError, 'EPSG:2154'):
            T.RasterMosaic(self.raster('wgs.tif', crs='EPSG:4326'), RECEIPT)
        path = self.raster()
        for receipt in [{**RECEIPT, 'verticalDatum': 'EGM96'},
                        {**RECEIPT, 'units': 'ft'},
                        {**RECEIPT, 'license': ''},
                        {**RECEIPT, 'sha256': '0' * 64}]:
            with self.subTest(receipt=receipt):
                with self.assertRaises(T.TerrainError): T.RasterMosaic(path, receipt)
        with self.assertRaisesRegex(T.TerrainError, 'résolution'):
            T.RasterMosaic([path, self.raster('res.tif', resolution=5)], RECEIPT)

    def test_window_memory_budget_is_checked_before_reading_native_data(self):
        mosaic = T.RasterMosaic(self.raster(), RECEIPT, max_window_pixels=100)
        try:
            with self.assertRaisesRegex(T.TerrainError, 'budget mémoire'):
                mosaic.tile([1000, 2000, 1250, 2250], 25)
        finally: mosaic.close()

    def test_complex_pixels_cannot_be_silently_cast_to_real_altitudes(self):
        path = self.root / 'complex.tif'
        with rasterio.open(path, 'w', driver='GTiff', width=3, height=3, count=1,
                           dtype='complex64', crs='EPSG:2154',
                           transform=from_origin(1000, 2250, 1, 1)) as dataset:
            dataset.write(np.full((3, 3), 10 + 3j, dtype='complex64'), 1)
        with self.assertRaisesRegex(T.TerrainError, 'complexes'):
            T.RasterMosaic(path, RECEIPT)

    def test_a_coarse_raster_cannot_be_presented_as_new_high_resolution_ground(self):
        mosaic = T.RasterMosaic(self.raster(resolution=5), RECEIPT)
        try:
            with self.assertRaisesRegex(T.TerrainError, 'Suréchantillonnage'):
                mosaic.tile([1000, 2000, 1250, 2250], 1)
        finally: mosaic.close()

    def test_geotiff_cli_produces_a_loadable_hashed_asset(self):
        path = self.raster()
        targets, receipt = self.root / 'cells.json', self.root / 'receipt.json'
        targets.write_text(json.dumps(cells([1000, 2000, 1250, 2250])))
        receipt.write_text(json.dumps(RECEIPT))
        result = subprocess.run([sys.executable, str(MODULE), 'from-geotiff', '--raster', str(path),
                                 '--cells', str(targets), '--receipt', str(receipt), '--step', '1',
                                 '--output', str(self.root / 'output')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['coverage']['completeCells'], 1)
        manifest = json.loads(Path(report['manifest']).read_text())
        link = manifest['tiles'][0]['terrain']
        pack = json.loads(gzip.decompress((self.root / 'output' / link['path']).read_bytes()))
        self.assertEqual(T.validate_grid(pack).cols, 253)


if __name__ == '__main__':
    unittest.main()
