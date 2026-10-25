"""Bounded numerical acquisition contracts; all HTTP responses are local fixtures."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

GAME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GAME / 'tools/v69'))
SPEC = importlib.util.spec_from_file_location('acquire_terrain69', GAME / 'tools/v69/acquire_terrain.py')
A = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(A)
try:
    import numpy as np
    import rasterio
    from pyproj import Transformer
except ImportError:
    rasterio = None
try:
    import py7zr
except ImportError:
    py7zr = None

CAPS = b'''<WMS_Capabilities xmlns="http://www.opengis.net/wms"><Service>
<MaxWidth>5010</MaxWidth><MaxHeight>5010</MaxHeight></Service><Capability>
<Request><GetMap><Format>image/x-bil;bits=32</Format></GetMap></Request>
<Layer><CRS>EPSG:2154</CRS><Layer><Name>ELEVATION.ELEVATIONGRIDCOVERAGE.HIGHRES</Name>
</Layer></Layer></Capability></WMS_Capabilities>'''
CATALOGUE = '''<fixture>Synthetic test catalogue: RGE ALTI, EPSG:2154,
RGF93 Lambert 93 et NGF-IGN 1969, Licence Ouverte.
La mise à jour a été arrêtée en 2024.</fixture>'''.encode()


def local_boundary():
    e, n = A.ORIGIN
    return {'boundsL93': [e - 10, n - 10, e + 10, n + 10],
            'file': {'name': 'fixture.geojson', 'sha256': '0' * 64}, 'testOnly': True}


class Reply(io.BytesIO):
    def __init__(self, raw, content_type='image/x-bil;bits=32'):
        super().__init__(raw)
        self.status = 200
        self.headers = {'Content-Type': content_type, 'Date': 'Sun, 25 Oct 2026 00:00:00 GMT'}


class PlanTests(unittest.TestCase):
    def test_plan_is_offline_bounded_and_cell_aligned(self):
        with patch.object(A, 'urlopen', side_effect=AssertionError('No network during planning')):
            plan = A.make_plan(local_boundary(), step=25)
        self.assertEqual((plan['cols'], plan['rows'], plan['nodes']), (13, 13, 169))
        self.assertEqual(plan['rawBytes'], 676)
        self.assertEqual(len(plan['requests']), 1)
        self.assertEqual(plan['gridNodeX0'], A.ORIGIN[0] - 150)
        self.assertEqual(plan['gridNodeN0'], A.ORIGIN[1] + 150)
        bbox = plan['requests'][0]['bboxL93']
        self.assertEqual(bbox[0] + 12.5, plan['gridNodeX0'])
        self.assertEqual(bbox[3] - 12.5, plan['gridNodeN0'])
        self.assertFalse(plan['newSurvey'])

    def test_full_amp_reproducible_budget(self):
        boundary = {'boundsL93': [840432.7599510866, 6232221.795831317,
                                  926837.6290563704, 6299234.073853413]}
        plan = A.make_plan(boundary, step=5)
        self.assertEqual((plan['cols'], plan['rows']), (17353, 13453))
        self.assertEqual(plan['rawBytes'], 933799636)
        self.assertEqual(len(plan['requests']), 20)
        self.assertTrue(all(j['width'] * j['height'] * 4 <= A.MAX_RESPONSE for j in plan['requests']))
        with self.assertRaisesRegex(A.TerrainError, 'budget total'):
            A.make_plan(boundary, step=1)

    def test_chunks_are_adjacent_pixel_lattices_without_overlap(self):
        plan = A.make_plan(local_boundary(), step=25, chunk=7)
        first, right, below = plan['requests'][:3]
        self.assertEqual(first['bboxL93'][2], right['bboxL93'][0])
        self.assertEqual(first['bboxL93'][1], below['bboxL93'][3])
        self.assertEqual(sum(j['width'] * j['height'] * 4 for j in plan['requests']), plan['rawBytes'])

    def test_request_dimension_and_byte_budgets(self):
        for kwargs in ({'chunk': 5011}, {'step': True}, {'max_total_bytes': 675},
                       {'max_response_bytes': 675}, {'origin': [0, float('nan')]}):
            with self.subTest(kwargs=kwargs), self.assertRaises(A.TerrainError):
                A.make_plan(local_boundary(), step=25, **kwargs) if 'step' not in kwargs else A.make_plan(local_boundary(), **kwargs)

    def test_worker_and_tampered_budgets_rejected_before_network(self):
        plan = A.make_plan(local_boundary(), step=25)
        with tempfile.TemporaryDirectory() as directory, patch.object(A, 'urlopen', side_effect=AssertionError('No network')):
            for workers in (0, 3, True):
                with self.assertRaises(A.TerrainError):
                    A.fetch_plan(plan, directory, workers=workers)
            plan['maxTotalBytes'] = 1
            with self.assertRaisesRegex(A.TerrainError, 'budget total'):
                A.fetch_plan(plan, directory)


class MetadataTests(unittest.TestCase):
    def test_published_contract_and_no_new_survey_claim(self):
        self.assertEqual(A.validate_capabilities(CAPS)['maxWidth'], 5010)
        source = A.validate_catalogue(CATALOGUE)
        self.assertEqual(source['verticalDatum'], 'NGF-IGN69')
        self.assertEqual(source['productUpdateStopYearDeclaredByCatalogue'], 2024)
        self.assertEqual(source['sourceSurveyDate'], 'not supplied')

    def test_missing_numerical_format_crs_and_datum_rejected(self):
        for raw in (CAPS.replace(b'bits=32', b'bits=8'), CAPS.replace(b'EPSG:2154', b'EPSG:4326')):
            with self.assertRaises(A.TerrainError):
                A.validate_capabilities(raw)
        for old in (b'NGF-IGN 1969', b'RGF93 Lambert 93', b'EPSG:2154', b'Licence Ouverte'):
            with self.subTest(old=old), self.assertRaises(A.TerrainError):
                A.validate_catalogue(CATALOGUE.replace(old, b'unknown'))
        with self.assertRaises(A.TerrainError):
            A.validate_catalogue(b'HTTP error')


class NativePlanTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.name = 'RGEALTI_2-0_5M_ASC_LAMB93-IGN69_D013_2022-12-16.7z'
        self.url = f'https://data.geopf.fr/telechargement/download/RGEALTI/{self.name[:-3]}/{self.name}'
        self.feed = self.root / 'native.xml'
        self.body = b'7z\xbc\xaf\x27\x1c' + b'fixture archive body'
        self.feed.write_text(f'<feed xmlns="http://www.w3.org/2005/Atom" xmlns:g="https://data.geopf.fr/annexes/ressources/xsd/gpf_dl.xsd"><entry><link type="application/x-7z-compressed" href="{self.url}" g:length="{len(self.body)}"/></entry></feed>')

    def tearDown(self):
        self.directory.cleanup()

    def test_native_plan_retains_published_bytes_hash_and_url_offline(self):
        with patch.object(A, 'urlopen', side_effect=AssertionError('No network')):
            plan = A.native_plan(local_boundary(), [self.feed])
        self.assertEqual(plan['totalBytes'], len(self.body))
        self.assertEqual(plan['nativeStepM'], 5)
        self.assertEqual(plan['jobs'][0]['sourceFeedSHA256'], hashlib.sha256(self.feed.read_bytes()).hexdigest())
        self.assertEqual(plan['jobs'][0]['url'], self.url)

    def test_native_budget_duplicate_and_unofficial_links_refused(self):
        with self.assertRaises(A.TerrainError):
            A.native_plan(local_boundary(), [self.feed], max_total_bytes=1)
        with self.assertRaises(A.TerrainError):
            A.native_plan(local_boundary(), [self.feed], max_archive_bytes=1)
        with self.assertRaises(A.TerrainError):
            A.native_plan(local_boundary(), [self.feed, self.feed])
        self.feed.write_text(self.feed.read_text().replace('data.geopf.fr/telechargement', 'example.org/telechargement'))
        with self.assertRaises(A.TerrainError):
            A.native_plan(local_boundary(), [self.feed])

    def test_native_download_exact_bytes_and_resume(self):
        plan = A.native_plan(local_boundary(), [self.feed])
        calls = []

        def request(req, timeout):
            calls.append(req.full_url)
            return Reply(CATALOGUE, 'text/xml') if req.full_url == A.CATALOGUE else Reply(self.body, 'application/x-7z-compressed')

        with patch.object(A, 'urlopen', side_effect=request):
            report = A.fetch_native_archives(plan, self.root)
            self.assertTrue(report['complete'])
            self.assertEqual(report['archives'][0]['raw']['sha256'], hashlib.sha256(self.body).hexdigest())
            self.assertEqual(A.fetch_native_archives(plan, self.root), report)
            self.assertEqual(len(calls), 2)

    def test_native_download_rejects_truncation_and_keeps_partial(self):
        plan = A.native_plan(local_boundary(), [self.feed])
        with patch.object(A, 'urlopen', side_effect=lambda req, timeout: Reply(CATALOGUE, 'text/xml') if req.full_url == A.CATALOGUE else Reply(self.body[:-1])):
            report = A.fetch_native_archives(plan, self.root)
        self.assertFalse(report['complete'])
        self.assertFalse((self.root / self.name).exists())
        self.assertTrue((self.root / (self.name + '.partial')).exists())


@unittest.skipUnless(rasterio, 'GIS generation dependencies not installed')
class RasterTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)

    def tearDown(self):
        self.directory.cleanup()

    def raw(self, values, name='test.bil'):
        path = self.root / name
        path.write_bytes(np.asarray(values, dtype='<f4').tobytes())
        return path

    def test_exact_little_endian_nodata_and_valid_zero(self):
        path = self.raw([0.0, -0.0, -99999, 7.25])
        stats = A.validate_bil(path, 2, 2)
        self.assertEqual(stats, {'nodes': 4, 'valid': 3, 'noData': 1, 'minM': 0, 'maxM': 7.25})
        self.assertEqual(path.read_bytes()[4:8], struct.pack('<f', -0.0))

    def test_wrong_bytes_nan_and_interpolated_nodata_are_quarantined(self):
        for values in ([0, 1, 2], [0, float('nan'), 1, 2], [0, -99998.9921875, 1, 2], [0, 1, 2, 9001]):
            with self.subTest(values=values), self.assertRaises(A.TerrainError):
                A.validate_bil(self.raw(values), 2, 2)
        with self.assertRaises(A.TerrainError):
            A.validate_bil(self.raw([1]), True, 1)

    def test_float32_georeference_preserves_every_pixel_bit_and_mask(self):
        raw = self.raw([0.0, -0.0, -99999, 7.25])
        job = {'width': 2, 'height': 2, 'bboxL93': [892949.1480966414, 6247267.066415883,
                 892959.1480966414, 6247277.066415883], 'url': A.WMS + '?fixture=true'}
        tif = self.root / 'derived.tif'
        receipt = A.normalise_bil(raw, tif, job, 5)
        with rasterio.open(tif) as restored:
            self.assertEqual(restored.crs.to_epsg(), 2154)
            self.assertEqual(restored.xy(0, 0), A.ORIGIN)
            self.assertEqual(restored.read(1).astype('<f4').tobytes(), raw.read_bytes())
            self.assertEqual(restored.read_masks(1).tolist(), [[255, 255], [0, 255]])
            self.assertEqual(restored.tags()['VERTICAL_DATUM'], 'NGF-IGN69')
        self.assertFalse(receipt['normalised']['normalisationChangesValues'])
        self.assertEqual(receipt['normalised']['rawSHA256'], hashlib.sha256(raw.read_bytes()).hexdigest())
        A.normalise_bil(raw, tif, job, 5)
        before = tif.read_bytes()
        raw.write_bytes(np.array([0, 0, 0, 0], dtype='<f4').tobytes())
        with self.assertRaises(A.TerrainError):
            A.normalise_bil(raw, tif, job, 5)
        self.assertEqual(tif.read_bytes(), before)

    def test_boundary_projects_all_vertices_and_verifies_hash(self):
        document = {'type': 'Polygon', 'coordinates': [[[5.2, 43.2], [5.4, 43.2], [5.4, 43.4], [5.2, 43.4], [5.2, 43.2]]]}
        path = self.root / 'boundary.geojson'
        path.write_text(json.dumps(document))
        result = A.projected_boundary(path, hashlib.sha256(path.read_bytes()).hexdigest())
        transform = Transformer.from_crs(4326, 2154, always_xy=True)
        points = [transform.transform(*point) for point in document['coordinates'][0]]
        self.assertEqual(result['boundsL93'], [min(p[0] for p in points), min(p[1] for p in points),
                                              max(p[0] for p in points), max(p[1] for p in points)])
        with self.assertRaises(A.TerrainError):
            A.projected_boundary(path, '0' * 64)

    def test_local_http_fixture_fetch_and_verified_resume(self):
        plan = A.make_plan(local_boundary(), step=25)
        job = plan['requests'][0]
        data = np.arange(169, dtype='<f4')
        data[0] = -99999
        calls = []

        def request(req, timeout):
            calls.append(req.full_url)
            if req.full_url == A.CAPABILITIES:
                return Reply(CAPS, 'text/xml')
            if req.full_url == A.CATALOGUE:
                return Reply(CATALOGUE, 'text/xml')
            self.assertEqual(req.full_url, job['url'])
            return Reply(data.tobytes())

        with patch.object(A, 'urlopen', side_effect=request):
            report = A.fetch_plan(plan, self.root, workers=2)
            self.assertTrue(report['complete'])
            self.assertEqual(report['receipts'][0]['statistics']['noData'], 1)
            self.assertEqual(len(calls), 3)
            self.assertEqual(A.fetch_plan(plan, self.root), report)
            self.assertEqual(len(calls), 3)
        (self.root / (job['id'] + '.bil')).write_bytes(b'changed')
        with patch.object(A, 'urlopen', side_effect=AssertionError('No repeat download')):
            with self.assertRaisesRegex(A.TerrainError, 'Sortie existante différente'):
                A.fetch_plan(plan, self.root)


@unittest.skipUnless(rasterio and py7zr, 'Native GIS import dependencies not installed')
class NativeImportTests(unittest.TestCase):
    def test_native_asc_integer_centres_nodata_values_and_receipts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            asc = root / 'native.asc'
            asc.write_text('ncols 1000\nnrows 1000\nxllcorner 889997.5\nyllcorner 6245002.5\ncellsize 5\nNODATA_value -99999\n' + '-99999 -0.0 ' + '0.0 ' * 998 + '\n' + ('5.5 ' * 1000 + '\n') * 999)
            name = 'RGEALTI_2-0_5M_ASC_LAMB93-IGN69_D013_2022-12-16.7z'
            archive = root / name
            selected = 'source/RGEALTI_FXX_0890_6250_MNT_LAMB93_IGN69.asc'
            with py7zr.SevenZipFile(archive, 'w') as compressed:
                compressed.write(asc, selected)
                compressed.write(asc, 'source/RGEALTI_FXX_0800_6400_MNT_LAMB93_IGN69.asc')
            receipt = root / 'archive.receipt.json'
            receipt.write_text(json.dumps({'raw': A.file_fingerprint(archive), 'crs': 'EPSG:2154',
                'verticalDatum': 'NGF-IGN69', 'units': 'm', 'testOnly': True}))
            point = Transformer.from_crs(2154, 4326, always_xy=True).transform(*A.ORIGIN)
            e, n = point
            boundary = root / 'boundary.geojson'
            boundary.write_text(json.dumps({'type': 'Polygon', 'coordinates': [[[e-.001,n-.001],[e+.001,n-.001],[e+.001,n+.001],[e-.001,n+.001],[e-.001,n-.001]]]}))
            output = root / 'output'
            report = A.import_native_archive(archive, receipt, boundary, output)
            self.assertTrue(report['testOnly'])
            self.assertEqual(len(report['rasters']), 1)
            self.assertEqual(report['rasters'][0]['noDataNodes'], 1)
            tif = output / report['rasters'][0]['path']
            with rasterio.open(tif) as restored, rasterio.open(asc) as source:
                self.assertEqual(restored.xy(0, 0), (890000, 6250000))
                self.assertEqual(restored.read(1).astype('<f4').tobytes(), source.read(1).astype('<f4').tobytes())
                self.assertEqual(restored.crs.to_epsg(), 2154)
            self.assertFalse((output / 'extracted/source/RGEALTI_FXX_0800_6400_MNT_LAMB93_IGN69.asc').exists())
            self.assertEqual(A.import_native_archive(archive, receipt, boundary, output), report)
            with tif.open('ab') as stream:
                stream.write(b'changed')
            with self.assertRaisesRegex(A.TerrainError, 'diffère de son reçu'):
                A.import_native_archive(archive, receipt, boundary, output)


if __name__ == '__main__':
    unittest.main()
