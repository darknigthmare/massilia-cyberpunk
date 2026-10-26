"""Coverage evidence must distinguish absent files, masked sea/coast and ground."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

GAME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GAME))
from tools.v69 import diagnose_terrain_coverage as D
from tools.v69 import terrain_tiles as T
from tools.v69 import build_terrain_coverage as B
from tools.build_metropole_viewer import json_bytes

try:
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin
    from shapely.geometry import box, mapping
    from shapely.ops import transform
    from pyproj import Transformer
    GIS = bool(importlib.util.find_spec('osmium') and importlib.util.find_spec('mapbox_earcut'))
except ImportError:
    GIS = False


class DiagnosticPureTests(unittest.TestCase):
    def test_exact_plane_slope_uses_mesh_triangles_and_unknown_is_never_zero(self):
        header = T._tile_header([0, 0, 250, 250], 5)
        data, mask = bytearray(), bytearray()
        for row in range(header['rows']):
            for col in range(header['cols']):
                data.extend(struct.pack('<f', 10 + col * .5 + row))
                mask.append(1)
        mask[20 * header['cols'] + 20] = 0
        pack = T._pack(header, data, mask, {'testOnly': True})
        quality = D.grid_quality(T.validate_grid(pack))
        expected = D.math.degrees(D.math.atan(D.math.hypot(.5, 1) / 5))
        self.assertAlmostEqual(quality['meshTriangleSlopeDegrees']['max'], expected)
        self.assertEqual(quality['unknownMeshTriangles'], 6)
        self.assertEqual(quality['unknownMeshAreaM2'], 75)
        self.assertEqual(quality['validUsefulNodes'], 2600)

    def test_atomic_report_never_overwrites_existing_different_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.json'
            D.write_report(path, {'testOnly': True, 'value': 1})
            before = path.read_bytes()
            D.write_report(path, {'testOnly': True, 'value': 1})
            with self.assertRaises(T.TerrainError):
                D.write_report(path, {'testOnly': True, 'value': 2})
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(list(path.parent.glob('.terrain-diagnostic-*')), [])

    def test_unsafe_paths_and_unbounded_inputs_are_rejected(self):
        for path in ('../x', '/etc/passwd', 'x//y', 'x/./y', 'https://example.invalid/x'):
            with self.subTest(path=path), self.assertRaises(T.TerrainError):
                D._relative(Path('/tmp'), path)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'metadata.json'
            path.write_text('{}')
            with self.assertRaises(T.TerrainError):
                D._read(path, limit=1)


@unittest.skipUnless(GIS, 'Optional GIS development dependencies are not installed')
class DiagnosticRealRasterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        east, north = D.ORIGIN
        self.to_geo = Transformer.from_crs(2154, 4326, always_xy=True).transform
        self.to_l93 = Transformer.from_crs(4326, 2154, always_xy=True).transform
        self.commune_geometries = [mapping(transform(self.to_geo, box(east - 124, north - 124, east + 124, north + 124))),
                                  mapping(transform(self.to_geo, box(east + 126, north - 124, east + 374, north + 124)))]
        features = [{'type': 'Feature', 'properties': {'code': code}, 'geometry': geometry}
                    for code, geometry in zip(('13001', '13002'), self.commune_geometries)]
        self.boundary = self.root / 'boundary.geojson'
        self.boundary.write_bytes(B._json({'type': 'FeatureCollection', 'features': features}))
        self.commune_path = self.root / 'communes.geojson'
        self.commune_path.write_bytes(self.boundary.read_bytes())
        self.raster = self.root / 'analytical.tif'
        x0, n0 = east - 500, north + 500
        self.raster_transform = from_origin(x0 - 2.5, n0 + 2.5, 5, 5)
        data = np.full((201, 201), 100, dtype='<f4')
        data[75:87, 165:175] = -99999
        with rasterio.open(self.raster, 'w', driver='GTiff', count=1, width=201, height=201,
                           dtype='float32', crs='EPSG:2154', nodata=-99999, transform=self.raster_transform) as target:
            target.write(data, 1)
            target.set_band_unit(1, 'm')
            target.update_tags(VERTICAL_DATUM='NGF-IGN69')
        self.index, self.receipt = self.root / 'index.json', self.root / 'receipt.json'
        self.index.write_bytes(B._json({'schema': B.RASTER_INDEX_SCHEMA, 'crs': 'EPSG:2154', 'units': 'm',
            'verticalDatum': 'NGF-IGN69', 'nativeStepM': 5, 'testOnly': True,
            'boundarySHA256': T.file_fingerprint(self.boundary)['sha256'],
            'rasters': [{**T.file_fingerprint(self.raster), 'path': self.raster.name}]}))
        self.source = {'provider': 'QA analytical fixture', 'product': 'No real IGN survey', 'license': 'Test-only',
            'attribution': 'Synthetic QA', 'crs': 'EPSG:2154', 'units': 'm', 'verticalDatum': 'NGF-IGN69',
            'testOnly': True, 'rasterIndex': T.file_fingerprint(self.index)}
        self.receipt.write_bytes(B._json(self.source))
        targets = B.targets_from_boundary(self.boundary)
        self.dem_path = self.root / 'dem' / 'manifest.json'
        self.dem = T.tiles_from_geotiff([self.raster], targets, self.dem_path.parent, 5, self.source)
        self.territory = self.root / 'territory.json'
        self.contour_descriptor = {**T.file_fingerprint(self.commune_path), 'path': self.commune_path.name}
        self.contour_descriptor.pop('name')
        self.territory.write_bytes(B._json({'schema': 'soma-metropole/territory/1',
            'communes': [{'code': '13001', 'nom': 'QA alpha'}, {'code': '13002', 'nom': 'QA beta'}],
            'boundary': {'sha256': targets['boundarySHA256'], 'source': self.contour_descriptor}}))
        self.anchors = self.root / 'anchors.json'
        self.make_anchors()
        self.world = self.root / 'world.json'
        # Reusing actual prepared terrain files is intentional; no fake vector
        # FeatureCollection or 3D availability is needed by a terrain diagnostic.
        tiles = copy.deepcopy(self.dem['tiles'])
        for item in tiles:
            item['terrain']['path'] = 'dem/' + item['terrain']['path']
        self.world_data = {'schema': 'soma-metropole/world-manifest/1', 'crs': 'EPSG:2154',
            'cellSize': 250, 'origin': D.ORIGIN, 'tiles': tiles,
            'sourceManifests': {'terrain': T.file_fingerprint(self.dem_path)['sha256']},
            'target': {'boundarySHA256': targets['boundarySHA256'], 'communeCount': 2,
                       'territorySHA256': T.file_fingerprint(self.territory)['sha256']}}
        self.world.write_bytes(B._json(self.world_data))

    def tearDown(self):
        self.temp.cleanup()

    def make_anchors(self):
        point = list(self.to_geo(*D.ORIGIN))
        metric = {'type': 'Point', 'coordinates': D.ORIGIN}
        geom_sha = hashlib.sha256(json_bytes(metric)).hexdigest()
        feature = {'type': 'Feature', 'id': 'osm/node/123', 'geometry': {'type': 'Point', 'coordinates': point},
            'properties': {'canonical_id': 'osm/node/123', 'place': 'village', 'name': 'QA alpha',
                           'ref:INSEE': '13001', 'soma:metricGeometry': metric, 'soma:geometry_sha256': geom_sha}}
        collection = {'type': 'FeatureCollection', 'features': [feature]}
        raw = json_bytes(collection)
        table = {'schema': 'soma-metropole/settlement-anchors/1', 'sourcePbfSHA256': 'a'*64,
            'vectorManifestSHA256': 'b'*64, 'territorySHA256': T.file_fingerprint(self.territory)['sha256'],
            'boundarySHA256': T.file_fingerprint(self.boundary)['sha256'],
            'coverage': {'communeCodes': ['13001', '13002'], 'communeCount': 2, 'sourcePointCount': 1, 'contourFallbackCount': 1},
            'sources': {'communeContours': self.contour_descriptor,
                'vectorManifest': {'bytes': 1, 'sha256': 'b'*64, 'receiptOnly': True},
                'canonicalStore': {'bytes': 1, 'sha256': 'c'*64, 'receiptOnly': True},
                'pointFeatures': {'encoding': 'inline-json', 'featureCollection': collection,
                                  'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}},
            'anchors': {'13001': {'code': '13001', 'name': 'QA alpha', 'status': 'source-place',
                'canonicalId': 'osm/node/123', 'nodeId': 123, 'pointWGS84': point, 'pointL93': D.ORIGIN,
                'geometrySHA256': geom_sha, 'sourcePbfSHA256': 'a'*64, 'vectorManifestSHA256': 'b'*64,
                'cellId': 'V52-MC-33', 'contentSHA256': 'd'*64, 'cellContentSHA256': 'd'*64,
                'evidence': {'canonicalId': 'osm/node/123', 'nodeId': 123, 'withinCommune': True, 'unique': True,
                    'place': 'village', 'sourceName': 'QA alpha', 'refINSEE': '13001', 'candidateIds': ['osm/node/123'],
                    'matchedBy': 'ref:INSEE'}},
                '13002': {'code': '13002', 'name': 'QA beta', 'status': 'contour-fallback',
                          'evidence': {'reason': 'test-only-no-place'}}}}
        table['proofSHA256'] = hashlib.sha256(json_bytes(table)).hexdigest()
        self.anchors.write_bytes(B._json(table))

    def diagnose(self):
        return D.diagnose(self.world, self.dem_path, self.boundary, self.territory, self.anchors,
                          self.index, self.receipt)

    def test_native_reasons_separate_mask_fringe_and_missing_footprint(self):
        m = T.RasterMosaic([self.raster], self.source)
        try:
            # Native pixel centres have an exact zero interpolation weight for
            # the three other pixels; an adjacent masked pixel cannot leak in.
            x0, n0 = D.ORIGIN[0] - 500, D.ORIGIN[1] + 500
            points = [(x0 + 168 * 5, n0 - 80 * 5),
                      (x0 + 164.5 * 5, n0 - 80 * 5),
                      (x0 - 10, n0)]
            bounds = [x0 - 10, n0 - 500, x0 + 900, n0]
            self.assertEqual(D.NativeEvidence(m).reasons(bounds, points),
                             ['native-source-nodata', 'strict-interpolation-fringe', 'missing-raster-footprint'])
            with self.assertRaisesRegex(T.TerrainError, 'all valid'):
                D.NativeEvidence(m).reasons(bounds, [(x0 + 10, n0 - 10)])
        finally:
            m.close()

    def test_real_raster_diagnostic_keeps_two_communes_and_explicit_fallback(self):
        before = {p: T.file_fingerprint(p) for p in (self.world, self.dem_path, self.raster, self.anchors)}
        report = self.diagnose()
        self.assertEqual(report['coverage']['communes'], 2)
        self.assertEqual(report['coverage']['knownDestinationGround'], 2)
        self.assertEqual(report['coverage']['sourcePlaceDestinations'], 1)
        self.assertEqual(report['coverage']['contourFallbackDestinations'], 1)
        self.assertGreater(report['uniqueUsefulNoData']['native-source-nodata'], 0)
        self.assertGreater(report['uniqueUsefulNoData']['insideAdministrative'], 0)
        self.assertFalse(report['assetsModified'])
        self.assertFalse(report['certifiedOneToOne'])
        self.assertTrue(report['source']['testOnly'])
        self.assertTrue(all(c['elevationM_NGF69'] == 100 for c in report['communeDestinations']))
        self.assertEqual(before, {p: T.file_fingerprint(p) for p in before})

    def test_wrong_world_edition_native_receipt_or_duplicate_cell_is_rejected(self):
        for mutation in ('edition', 'identity', 'receipt'):
            with self.subTest(mutation=mutation):
                original = self.world.read_bytes()
                if mutation == 'receipt':
                    self.source['product'] = 'Different QA source'
                    self.receipt.write_bytes(B._json(self.source))
                else:
                    changed = copy.deepcopy(self.world_data)
                    if mutation == 'edition':
                        changed['sourceManifests']['terrain'] = '0'*64
                    else:
                        changed['tiles'][0]['cellId'] = 'V52-MC-E999-S999'
                    self.world.write_bytes(B._json(changed))
                with self.assertRaises(T.TerrainError):
                    self.diagnose()
                self.world.write_bytes(original)

    def test_tampered_installed_asset_never_becomes_reported_ground(self):
        item = self.world_data['tiles'][0]
        path = self.root / item['terrain']['path']
        path.write_bytes(path.read_bytes() + b'tampered')
        with self.assertRaisesRegex(T.TerrainError, 'fingerprint'):
            self.diagnose()


if __name__ == '__main__':
    unittest.main()
