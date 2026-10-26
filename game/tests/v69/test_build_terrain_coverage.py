"""Offline administrative targets and atomic, bounded, real-raster DEM builds."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

GAME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GAME))
from tools.v69 import build_terrain_coverage as B
from tools.v69 import terrain_tiles as T

try:
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin
    from pyproj import Transformer
    from shapely.geometry import Polygon, box, mapping
    from shapely.ops import transform
    GIS = bool(importlib.util.find_spec('osmium') and importlib.util.find_spec('mapbox_earcut'))
except ImportError:
    GIS = False

ORIGIN = [892951.6480966414, 6247274.566415883]


class BudgetTests(unittest.TestCase):
    def test_invalid_worker_and_resource_budgets_fail_before_reading_inputs(self):
        for options in ({'workers': 3}, {'workers': True}, {'workers': 1.0}, {'plan_only': 'yes'}, {'max_output_bytes': 0},
                        {'max_output_bytes': B.MAX_OUTPUT_BYTES + 1}, {'disk_reserve_bytes': 1}):
            with self.subTest(options=options), self.assertRaises(T.TerrainError):
                B.build_coverage('absent-boundary', 'absent-index', 'absent-receipt', 'absent-output', **options)

    def test_byte_ceiling_and_projected_disk_growth_stop_before_writing(self):
        ctx = B.mp.get_context('fork')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            budget = B.Budget(ctx.Value('q', 0), ctx.Event(), 10, B.MIN_RESERVE_BYTES, root)
            with self.assertRaisesRegex(T.TerrainError, 'byte budget'):
                B._write_checked(budget, root / 'too-large', b'x' * 11)
            self.assertFalse((root / 'too-large').exists())
            budget = B.Budget(ctx.Value('q', 0), ctx.Event(), 1000, B.MIN_RESERVE_BYTES, root)
            with patch.object(B.shutil, 'disk_usage', return_value=SimpleNamespace(free=B.MIN_RESERVE_BYTES + 10)):
                with self.assertRaisesRegex(T.TerrainError, 'disk reserve'):
                    B._write_checked(budget, root / 'reserve', b'x' * 11)
            self.assertFalse((root / 'reserve').exists())
            self.assertEqual(budget.counter.value, 0)


@unittest.skipUnless(GIS, 'Optional GIS development requirements are not installed')
class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.boundary = self.root / 'boundary.geojson'
        east, north = ORIGIN
        outer = box(east - 365, north - 365, east + 365, north + 365)
        hole = box(east - 130, north - 130, east + 130, north + 130)
        self.write_boundary(self.boundary, Polygon(outer.exterior.coords, [hole.exterior.coords]))
        self.raster = self.root / 'analytical-plane.tif'
        x0, n0 = np.floor((east - 500) / 5) * 5, np.ceil((north + 500) / 5) * 5
        x, n = x0 + np.arange(201) * 5, n0 - np.arange(201) * 5
        data = (30 + (x[None, :] - east) * .01 + (n[:, None] - north) * .02).astype('<f4')
        data[42:65, 44:69] = -99999
        with rasterio.open(self.raster, 'w', driver='GTiff', count=1, width=201, height=201,
                           dtype='float32', crs='EPSG:2154', nodata=-99999,
                           transform=from_origin(x0 - 2.5, n0 + 2.5, 5, 5)) as target:
            target.write(data, 1)
            target.set_band_unit(1, 'm')
            target.update_tags(VERTICAL_DATUM='NGF-IGN69')
        self.index = self.root / 'raster-index.json'
        self.receipt = self.root / 'receipt.json'
        self.update_receipts()

    def tearDown(self):
        self.temp.cleanup()

    def write_boundary(self, path, metric_polygon):
        geographic = transform(Transformer.from_crs(2154, 4326, always_xy=True).transform, metric_polygon)
        path.write_text(json.dumps({'type': 'FeatureCollection', 'features': [
            {'type': 'Feature', 'properties': {'testOnly': True}, 'geometry': mapping(geographic)}]}))

    def update_receipts(self):
        index = {'schema': B.RASTER_INDEX_SCHEMA, 'crs': 'EPSG:2154', 'units': 'm',
                 'verticalDatum': 'NGF-IGN69', 'nativeStepM': 5, 'testOnly': True,
                 'boundarySHA256': T.file_fingerprint(self.boundary)['sha256'],
                 'rasters': [{**T.file_fingerprint(self.raster), 'path': self.raster.name}]}
        self.index.write_bytes(B._json(index))
        receipt = {'provider': 'Synthetic QA provider', 'product': 'Analytical plane, never IGN data',
                   'license': 'Test-only', 'attribution': 'Synthetic local fixture', 'testOnly': True,
                   'crs': 'EPSG:2154', 'units': 'm', 'verticalDatum': 'NGF-IGN69',
                   'sourceSurveyDate': 'Not a real survey', 'rasterIndex': T.file_fingerprint(self.index)}
        self.receipt.write_bytes(B._json(receipt))

    def build(self, name, **options):
        return B.build_coverage(self.boundary, self.index, self.receipt, self.root / name,
                                max_output_bytes=1024**2, **options)

    def test_hole_is_retained_and_cell_ids_use_the_historical_grid(self):
        target = B.targets_from_boundary(self.boundary)
        self.assertEqual(target['schema'], T.TARGET_SCHEMA)
        self.assertEqual(len(target['tiles']), 8)
        expected = {f'V52-MC-{row}{col}' for row in (2, 3, 4) for col in (2, 3, 4)} - {'V52-MC-33'}
        self.assertEqual({cell['cellId'] for cell in target['tiles']}, expected)
        self.assertFalse(target['vectorCoverageClaimed'])
        self.assertTrue(all('vector' not in cell for cell in target['tiles']))
        self.assertEqual(target['boundarySHA256'], hashlib.sha256(self.boundary.read_bytes()).hexdigest())
        far = self.root / 'far-boundary.geojson'
        e, n = ORIGIN[0] - 120 * 250, ORIGIN[1] + 210 * 250
        self.write_boundary(far, box(e - 10, n - 10, e + 10, n + 10))
        cell = B.targets_from_boundary(far)['tiles'][0]
        self.assertEqual((cell['cellId'], cell['gridX'], cell['gridY']), ('V52-MC-W120-N210', -120, -210))
        self.assertEqual(cell['boundsL93'], [e - 125, n - 125, e + 125, n + 125])

    def test_one_and_two_workers_generate_identical_numerical_assets_and_nodata(self):
        first, second = self.build('one', workers=1), self.build('two', workers=2)
        self.assertEqual(first['coverage'], second['coverage'])
        self.assertEqual(first['coverage']['targetCells'], 8)
        self.assertGreater(first['coverage']['partialCells'], 0)
        manifests = [json.loads((self.root / name / 'manifest.json').read_text()) for name in ('one', 'two')]
        self.assertTrue(all(m['testOnly'] and m['terrainOnly'] and not m['vectorCoverageClaimed'] for m in manifests))
        for left, right in zip(manifests[0]['tiles'], manifests[1]['tiles']):
            self.assertEqual(left['cellId'], right['cellId'])
            self.assertEqual(left['boundsL93'], right['boundsL93'])
            self.assertEqual(left['terrain']['gridSHA256'], right['terrain']['gridSHA256'])
            self.assertEqual((self.root / 'one' / left['terrain']['path']).read_bytes(),
                             (self.root / 'two' / right['terrain']['path']).read_bytes())
        self.assertEqual(first['outputBytes'], sum(p.stat().st_size for p in (self.root / 'one').rglob('*') if p.is_file()))
        self.assertEqual(second['outputBytes'], sum(p.stat().st_size for p in (self.root / 'two').rglob('*') if p.is_file()))

    def test_complete_directory_is_published_once_and_existing_outputs_are_preserved(self):
        observed = []
        publish = B._publish

        def before_publish(stage, output):
            self.assertFalse(output.exists())
            manifest = json.loads((stage / 'manifest.json').read_text())
            self.assertEqual(len(manifest['tiles']), 8)
            self.assertTrue(all((stage / cell['terrain']['path']).is_file() for cell in manifest['tiles']))
            observed.append(True)
            publish(stage, output)

        with patch.object(B, '_publish', side_effect=before_publish):
            self.build('atomic', workers=2)
        self.assertEqual(observed, [True])
        before = (self.root / 'atomic/manifest.json').read_bytes()
        with self.assertRaisesRegex(T.TerrainError, 'already exists'):
            self.build('atomic', workers=1)
        self.assertEqual((self.root / 'atomic/manifest.json').read_bytes(), before)
        self.assertEqual(list(self.root.glob('.terrain-coverage-*')), [])

    def test_late_numerical_failure_leaves_no_published_or_partial_output(self):
        with rasterio.open(self.raster, 'r+') as source:
            data = source.read(1)
            data[52, 52] = np.nan
            source.write(data, 1)
        self.update_receipts()
        with self.assertRaisesRegex(T.TerrainError, 'Altitude raster'):
            self.build('invalid', workers=2)
        self.assertFalse((self.root / 'invalid').exists())
        self.assertEqual(list(self.root.glob('.terrain-coverage-*')), [])

    def test_plan_only_publishes_no_dem_and_does_not_touch_existing_dataset(self):
        plan = self.build('plan', workers=2, plan_only=True)
        self.assertEqual(plan['targetCells'], 8)
        self.assertTrue(plan['planOnly'])
        self.assertTrue((self.root / 'plan/target-cells.json').is_file())
        self.assertFalse((self.root / 'plan/manifest.json').exists())
        self.assertFalse((self.root / 'plan/batches').exists())

    def test_index_fixture_flag_cannot_be_lost_when_compact_receipt_omits_it(self):
        receipt = json.loads(self.receipt.read_text())
        del receipt['testOnly']
        self.receipt.write_bytes(B._json(receipt))
        self.build('index-fixture', workers=2)
        manifest = json.loads((self.root / 'index-fixture/manifest.json').read_text())
        self.assertTrue(manifest['testOnly'])
        self.assertTrue(manifest['source']['receipt']['testOnly'])
        import gzip
        for tile in manifest['tiles']:
            if tile['terrain']:
                pack = json.loads(gzip.decompress((self.root / 'index-fixture' / tile['terrain']['path']).read_bytes()))
                self.assertTrue(pack['testOnly'])
                self.assertEqual(pack['source']['truth'], 'fixture')

    def test_public_cli_prepares_a_bounded_two_worker_dataset(self):
        output = self.root / 'cli-output'
        result = subprocess.run([sys.executable, str(Path(B.__file__)), '--boundary', str(self.boundary),
            '--raster-index', str(self.index), '--receipt', str(self.receipt), '--output', str(output),
            '--workers', '2', '--max-output-bytes', str(1024**2), '--disk-reserve-bytes',
            str(B.MIN_RESERVE_BYTES), '--quiet'], text=True, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'prepared')
        manifest = json.loads((output / 'manifest.json').read_text())
        self.assertEqual(manifest['coverage']['targetCells'], 8)
        self.assertTrue(manifest['testOnly'])
        self.assertFalse(manifest['vectorCoverageClaimed'])

    def test_source_hash_boundary_and_path_drift_refuse_before_publication(self):
        raw = self.index.read_bytes()
        index = json.loads(raw)
        for key, value in (('boundarySHA256', 'f' * 64), ('nativeStepM', 25)):
            wrong = {**index, key: value}
            self.index.write_bytes(B._json(wrong))
            receipt = json.loads(self.receipt.read_text())
            receipt['rasterIndex'] = T.file_fingerprint(self.index)
            self.receipt.write_bytes(B._json(receipt))
            with self.subTest(key=key), self.assertRaises(T.TerrainError):
                self.build('foreign-' + key, plan_only=True)
            self.assertFalse((self.root / ('foreign-' + key)).exists())
        self.update_receipts()
        index = json.loads(self.index.read_text())
        index['rasters'][0]['path'] = '../outside.tif'
        self.index.write_bytes(B._json(index))
        receipt = json.loads(self.receipt.read_text());receipt['rasterIndex'] = T.file_fingerprint(self.index)
        self.receipt.write_bytes(B._json(receipt))
        with self.assertRaisesRegex(T.TerrainError, 'Unsafe path'):
            self.build('unsafe', plan_only=True)
        self.assertFalse((self.root / 'unsafe').exists())


if __name__ == '__main__':
    unittest.main()
