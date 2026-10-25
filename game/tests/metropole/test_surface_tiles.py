"""True v59 dimensions, native-axis seams and source polygon holes."""
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

GAME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GAME / "tools"))
from metropole import surface_tiles as surfaces

try:
    from pyproj import Transformer
    from shapely.affinity import affine_transform
    from shapely.geometry import GeometryCollection, LineString, Point, Polygon, box, mapping, shape
    from shapely.ops import unary_union
    from metropole.import_tiles import clip_feature, ORIGIN
    HAVE_GIS = True
except ImportError:
    HAVE_GIS = False

BASELINE = GAME / "baseline/v66.html"
REAL_SAMPLE = Path("/workspace/massilia-geodata-generated/vector-sample-strict-v2/manifest.json")
GLOBAL_SAMPLE = Path("/workspace/massilia-geodata-generated/surfaces-sample-strict-v2-final/surface-manifest.json")


def world_surface(asset, layers=None):
    bounds = asset["boundsL93"]
    ce, cn = (bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2
    selected = asset["cell"]["surfaces"]
    polygons = [Polygon([[ce + x, cn - z] for x, z in triangle])
                for name, triangles in selected.items() if layers is None or name in layers for triangle in triangles]
    return unary_union(polygons)


def fixture(directory):
    directory = Path(directory)
    directory.mkdir()
    e, n = ORIGIN
    bounds = [[e - 125, n - 125, e + 125, n + 125],
              [e + 125, n - 125, e + 375, n + 125]]
    inverse = Transformer.from_crs("EPSG:2154", "EPSG:4326", always_xy=True)
    forward = Transformer.from_crs("EPSG:4326", "EPSG:2154", always_xy=True)
    pbf = "a" * 64
    receipt = {"id": "fixture-source", "sha256": pbf, "license": "test", "attribution": "geometry fixtures"}
    native = {"schema": "soma-metropole/native-topology/1", "ways": [], "relations": [],
              "nodeTags": {"71": {"highway": "crossing", "crossing": "marked"}}, "nodeTagsComplete": True}
    objects = []

    def add(source_id, layer, geometry, tags):
        properties = {**tags, "canonical_id": source_id, "soma:layer": layer,
                      "soma:geometry_sha256": surfaces.digest(mapping(geometry))}
        objects.append((geometry, properties))

    def road(way_id, metric_coordinates, tags):
        coordinates = [list(inverse.transform(*q)) for q in metric_coordinates]
        metric_geometry = LineString([forward.transform(*q) for q in coordinates])
        native["ways"].append({"id": str(way_id), "layer": "roads", "tags": tags,
                                 "nodeRefs": [str(way_id * 10 + i) for i in range(len(coordinates))],
                                 "coordinatesWGS84": coordinates})
        add(f"osm/way/{way_id}", "roads", metric_geometry, tags)
        return metric_geometry

    axis = road(7, [(e - 205, n - 40), (e + 65, n + 30), (e + 195, n - 10), (e + 455, n + 60)],
                {"highway": "residential", "width": "7.4", "lanes": "2", "sidewalk": "left", "sidewalk:left:width": "1.2"})
    hidden = road(8, [(e - 200, n + 95), (e + 450, n + 95)],
                  {"highway": "footway", "width": "3", "indoor": "yes"})
    plaza = Polygon([(e - 115, n - 115), (e - 15, n - 115), (e - 15, n - 55), (e - 115, n - 55)],
                    holes=[[(e - 110, n - 110), (e - 100, n - 110), (e - 100, n - 100), (e - 110, n - 100)]])
    add("osm/relation/5", "roads", plaza, {"highway": "pedestrian", "area": "yes", "surface": "paving_stones"})
    building = Polygon([(e - 85, n - 110), (e - 25, n - 110), (e - 25, n - 60), (e - 85, n - 60)],
                       holes=[[(e - 65, n - 95), (e - 45, n - 95), (e - 45, n - 75), (e - 65, n - 75)]])
    add("osm/way/20", "buildings", building, {"building": "yes"})
    water = box(e - 98, n - 110, e - 90, n - 100)
    add("osm/way/30", "hydrography", water, {"natural": "water"})
    add("osm/node/71", "roads", Point(list(axis.coords)[1]), {"highway": "crossing", "crossing": "marked"})
    tiles = []
    for cell_id, extent in zip(("V52-MC-33", "V52-MC-34"), bounds):
        features = []
        for geometry, properties in objects:
            feature = clip_feature(geometry, properties, box(*extent))
            if feature is not None:
                features.append(feature)
        record = {"schema": "soma-massilia/geodata-cell/4", "cellId": cell_id, "boundsL93": extent,
                  "sourceReceipt": receipt, "featureCollection": {"type": "FeatureCollection", "features": features}}
        record["contentSHA256"] = surfaces.digest(record["featureCollection"])
        descriptor = surfaces.write_asset(directory / f"{cell_id}.json.gz", record, 16 * 1024 * 1024)
        tiles.append({"cellId": cell_id, "boundsL93": extent, "vector": descriptor})
    topology = surfaces.write_asset(directory / "native-topology.json.gz", native, 16 * 1024 * 1024)
    manifest = {"schema": "soma-metropole/vector-tiles/1", "crs": "EPSG:2154", "units": "m",
                "source": receipt, "bounds": [bounds[0][0], bounds[0][1], bounds[1][2], bounds[1][3]],
                "tiles": tiles, "nativeTopology": topology, "boundary": None}
    path = directory / "manifest.json"
    path.write_bytes(surfaces.canonical(manifest) + b"\n")
    return path, {"axis": axis, "hidden": hidden, "plaza": plaza, "building": building, "water": water, "bounds": bounds}


@unittest.skipUnless(HAVE_GIS, "Optional geodata environment is required")
class SpatialIndexFixtures(unittest.TestCase):
    def test_mixed_dimension_overlay_debris_keeps_polygon_holes_and_never_occludes_pavement(self):
        polygon = box(0, 0, 100, 100).difference(box(20, 20, 30, 30))
        debris = GeometryCollection([polygon, LineString([(100, 0), (150, 0)]), Point(160, 0)])
        clean = surfaces._polygonal(debris)
        self.assertEqual(clean.wkb, polygon.wkb)
        self.assertTrue(Polygon().difference(clean).is_empty)
        # Clipping can create line/point contacts even from polygon-only inputs.
        # They remain metadata candidates but never enter mixed-dimension GEOS
        # differences, including the permanently empty marking layer.
        cell, report = surfaces.cell_surfaces((0, 0, 250, 250),
            {"road": debris, "foot": box(90, 0, 120, 20)},
            GeometryCollection([box(40, 40, 50, 50), LineString([(0, 60), (100, 60)])]))
        self.assertAlmostEqual(cell["areaM2"]["road"], 9800)
        self.assertAlmostEqual(cell["areaM2"]["foot"], 400)
        self.assertEqual(cell["surfaces"]["mark"], [])
        self.assertAlmostEqual(report["surfaceAreaM2"], 10200)

    def test_empty_coverage_and_masks_never_overlay_empty_against_mixed_dimensions(self):
        mixed = GeometryCollection([box(0, 0, 100, 100), LineString([(100, 0), (150, 0)])])
        outside, report = surfaces.cell_surfaces((0, 0, 250, 250), {"road": mixed}, mixed, Polygon())
        self.assertEqual(sum(outside["areaM2"].values()), 0)
        self.assertEqual(report, {"pavementConflictAreaRemovedM2": 0.0, "surfaceAreaM2": 0.0})
        inside, report = surfaces.cell_surfaces((0, 0, 250, 250), {"road": mixed}, Polygon())
        self.assertAlmostEqual(inside["areaM2"]["road"], 10000)
        self.assertEqual(report["pavementConflictAreaRemovedM2"], 0)

    def test_local_construction_matches_global_union_with_holes_seams_and_material_overlaps(self):
        # Native bends extend beyond every cell. Polygon holes and overlapping
        # masks deliberately cross seams, where clipping before union matters.
        axis = LineString([(-180, -70), (90, 40), (280, -20), (740, 110)])
        body, walk = surfaces.road_bands(axis, {"width": 8.2, "sidewalk": {"left": True, "leftWidth": 1.5}})
        plaza = Polygon([(-50, -100), (310, -100), (310, 95), (-50, 95)],
                        holes=[[(110, -30), (150, -30), (150, 25), (110, 25)]])
        building = Polygon([(210, -60), (310, -60), (310, 65), (210, 65)],
                           holes=[[(235, -35), (280, -35), (280, 30), (235, 30)]])
        layers = {"road": [("axis", body)], "walk": [("axis", walk)],
                  "paved": [("plaza-a", plaza.intersection(box(-125, -125, 125, 125))),
                            ("plaza-b", plaza.intersection(box(125, -125, 375, 125)))],
                  "unsealed": [("track", box(290, -85, 450, -60))],
                  "foot": [("foot", LineString([(-200, 20), (800, 20)]).buffer(1.3))]}
        masks = [building.intersection(box(125, -125, 275, 125)),
                 building.intersection(box(275, -125, 525, 125)), box(180, -100, 195, -35)]
        global_layers = {layer: unary_union([g for _, g in entries]) for layer, entries in layers.items()}
        global_mask = unary_union(masks)
        coverage = Polygon([(-110, -120), (570, -120), (570, 105), (300, 105), (-110, 80)])
        index = surfaces.SurfaceSpatialIndex(layers, masks)
        for bounds in ((-125, -125, 125, 125), (125, -125, 375, 125), (375, -125, 625, 125)):
            with self.subTest(bounds=bounds):
                expected, report = surfaces.cell_surfaces(bounds, global_layers, global_mask, coverage)
                actual, actual_report, _ = index.cell(bounds, surfaces.CoverageClip(coverage))
                for layer in surfaces.LAYERS:
                    before = world_surface({"boundsL93": bounds, "cell": expected}, {layer})
                    after = world_surface({"boundsL93": bounds, "cell": actual}, {layer})
                    self.assertLess(before.symmetric_difference(after).area, 1e-7)
                    self.assertAlmostEqual(expected["areaM2"][layer], actual["areaM2"][layer], places=6)
                for key in report:
                    self.assertAlmostEqual(report[key], actual_report[key], places=6)

    def test_distant_geometries_never_enter_a_constructive_union_and_touching_ids_are_retained(self):
        local = [("local", box(10, 10, 20, 20)), ("edge", box(250, 10, 260, 20))]
        distant = [("distant-" + str(i), box(10000 + i * 12, 10000, 10010 + i * 12, 10010)) for i in range(2000)]
        calls = []
        real_gis = surfaces._gis

        def checked_gis():
            result = list(real_gis())
            real_union = result[8]

            def local_union(geometries):
                geometries = list(geometries)
                calls.append(len(geometries))
                self.assertLessEqual(len(geometries), 6, "A territory-wide constructive union regressed")
                self.assertTrue(all(g.is_empty or g.bounds[0] <= 250 for g in geometries))
                return real_union(geometries)

            result[8] = local_union
            return tuple(result)

        with patch.object(surfaces, "_gis", checked_gis):
            index = surfaces.SurfaceSpatialIndex({"road": local + distant}, [box(12, 12, 14, 14), box(20000, 20000, 20100, 20100)])
            self.assertEqual(calls, [], "Index construction must not union native bands")
            actual, _, identifiers = index.cell((0, 0, 250, 250))
        self.assertEqual(identifiers, {"local", "edge"})
        self.assertAlmostEqual(actual["areaM2"]["road"], 96)
        self.assertEqual(index.stats["candidateEntries"], 3)
        self.assertEqual(index.stats["maxCellCandidates"], 3)
        self.assertEqual(index.stats["layerEntries"]["road"], 2002)

    def test_prepared_boundary_matches_intersection_inside_outside_and_along_a_hole(self):
        coverage = box(0, 0, 1000, 1000).difference(box(430, 430, 570, 570))
        prepared = surfaces.CoverageClip(coverage)
        for bounds in ((0, 0, 250, 250), (375, 375, 625, 625), (2000, 2000, 2250, 2250)):
            tile = box(*bounds)
            self.assertTrue(prepared.clip(tile).equals(tile.intersection(coverage)))

    def test_cells_without_pavement_need_no_mask_union(self):
        index = surfaces.SurfaceSpatialIndex({}, [box(10, 10, 50, 50)])
        actual, report, identifiers = index.cell((0, 0, 250, 250))
        expected, expected_report = surfaces.cell_surfaces((0, 0, 250, 250), {}, box(10, 10, 50, 50))
        self.assertEqual(actual, expected)
        self.assertEqual(report, expected_report)
        self.assertEqual(identifiers, set())
        self.assertEqual(index.stats["candidateEntries"], 0)


@unittest.skipUnless(HAVE_GIS and shutil.which("node") and BASELINE.exists(), "Prepared baseline, Node and optional geodata environment are required")
class SurfaceTileFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="massilia-surfaces-")
        cls.root = Path(cls.temporary.name)
        cls.manifest, cls.geometry = fixture(cls.root / "vectors")
        cls.output = cls.root / "surfaces"
        cls.prepared = surfaces.prepare_surfaces(cls.manifest, cls.output)
        cls.assets = {tile["cellId"]: surfaces.read_asset(cls.output, tile["surface"]) for tile in cls.prepared["tiles"]}

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_actual_frozen_core_profiles_explicit_units_and_preserves_estimation_sources(self):
        values, core = surfaces.profile_sources({"width": {"highway": "residential", "width": "12 ft", "lanes": "4"},
                                                "estimate": {"highway": "residential", "est_width": "6.3"},
                                                "lanes": {"highway": "primary", "lanes": "3"},
                                                "class": {"highway": "footway"}}, {}, BASELINE)
        self.assertAlmostEqual(values["roads"]["width"]["width"], 3.6576)
        self.assertEqual(values["roads"]["width"]["widthSource"], "osm-width")
        self.assertAlmostEqual(values["roads"]["estimate"]["width"], 6.3)
        self.assertEqual(values["roads"]["estimate"]["widthSource"], "osm-est-width")
        self.assertEqual(values["roads"]["lanes"]["widthSource"], "estimated-from-lanes")
        self.assertEqual(values["roads"]["class"]["widthSource"], "estimated-from-class")
        self.assertEqual(core["version"], "0.59.0")
        self.assertEqual(core, self.prepared["dimensionCore"])

    def test_dimension_batches_equal_one_batch_of_the_actual_core(self):
        roads = {str(i): {"highway": name, "lanes": str(i + 1)} for i, name in enumerate(("residential", "primary", "footway"))}
        buildings = {"ground": {"building": "yes"}, "raised": {"building": "yes", "min_height": "4"}}
        self.assertEqual(surfaces.profile_sources(roads, buildings, BASELINE, batch_size=1),
                         surfaces.profile_sources(roads, buildings, BASELINE, batch_size=4096))

    def test_oblique_native_road_and_left_sidewalk_match_global_bands_across_the_seam(self):
        asset_a, asset_b = (self.assets[cell] for cell in ("V52-MC-33", "V52-MC-34"))
        profile = asset_a["roadMetadata"]["osm/way/7"]
        self.assertAlmostEqual(profile["width"], 7.4)
        self.assertEqual(profile["widthSource"], "osm-width")
        axis = self.geometry["axis"]
        expected_road = axis.buffer(3.7, cap_style="flat", join_style="mitre")
        expected_walk = axis.buffer(4.9, single_sided=True, join_style="mitre").difference(
            axis.buffer(3.7, single_sided=True, join_style="mitre")).difference(expected_road)
        extent = box(self.geometry["bounds"][0][0], self.geometry["bounds"][0][1],
                     self.geometry["bounds"][1][2], self.geometry["bounds"][1][3])
        road = unary_union([world_surface(asset_a, {"road"}), world_surface(asset_b, {"road"})])
        walk = unary_union([world_surface(asset_a, {"walk"}), world_surface(asset_b, {"walk"})])
        self.assertLess(road.symmetric_difference(expected_road.intersection(extent)).area, 1e-6)
        self.assertLess(walk.symmetric_difference(expected_walk.intersection(extent)).area, 1e-6)
        self.assertLess(world_surface(asset_a).intersection(world_surface(asset_b)).area, 1e-6)
        seam = LineString([(self.geometry["bounds"][0][2], self.geometry["bounds"][0][1]),
                           (self.geometry["bounds"][0][2], self.geometry["bounds"][0][3])])
        self.assertLess(world_surface(asset_a, {"road"}).intersection(seam).symmetric_difference(
            world_surface(asset_b, {"road"}).intersection(seam)).length, 1e-6)

    def test_plaza_and_building_courtyards_are_preserved_and_water_is_not_paved(self):
        actual = world_surface(self.assets["V52-MC-33"], {"paved"})
        expected = self.geometry["plaza"].difference(self.geometry["building"]).difference(self.geometry["water"])
        self.assertLess(actual.symmetric_difference(expected).area, 1e-6)
        self.assertLess(actual.intersection(self.geometry["building"]).area, 1e-6)
        self.assertLess(actual.intersection(self.geometry["water"]).area, 1e-6)
        inner = Polygon(self.geometry["building"].interiors[0])
        self.assertAlmostEqual(actual.intersection(inner).area, 400, places=6)
        hole = Polygon(self.geometry["plaza"].interiors[0])
        self.assertLess(actual.intersection(hole).area, 1e-6)

    def test_indoor_geometry_is_withheld_and_no_markings_or_ign_heights_are_invented(self):
        for asset in self.assets.values():
            self.assertTrue(asset["roadMetadata"]["osm/way/8"]["structural"])
            self.assertIn("indoor", asset["roadMetadata"]["osm/way/8"]["v69WithheldReasons"])
            self.assertEqual(asset["cell"]["surfaces"]["mark"], [])
            self.assertEqual(asset["buildings"], {})
            self.assertEqual(asset["heightReferences"]["status"], "explicitly-absent")
            self.assertEqual(asset["sourcePbfSHA256"], "a" * 64)
            self.assertLess(world_surface(asset).intersection(self.geometry["hidden"].buffer(1.5)).area, 1e-6)
        self.assertEqual(self.prepared["report"]["sourceRoadPointsRetainedInVectors"], 1)
        self.assertNotIn("osm/node/71", self.assets["V52-MC-33"]["roadMetadata"])

    def test_sidewalks_need_explicit_source_tags_and_polygon_places_are_not_buffered(self):
        plain, sidewalk = surfaces.road_bands(self.geometry["axis"], {"width": 3.6576, "sidewalk": {"known": False}})
        self.assertTrue(sidewalk.is_empty)
        self.assertAlmostEqual(plain.area, self.geometry["axis"].length * 3.6576, places=5)
        area, side = surfaces.road_bands(self.geometry["plaza"], {"width": 50, "sidewalk": {"left": True, "leftWidth": 5}})
        self.assertEqual(area, self.geometry["plaza"])
        self.assertTrue(side.is_empty)

    def test_preparation_is_repeatable_and_does_not_replace_user_outputs(self):
        second = self.root / "surfaces-second"
        before = self.manifest.read_bytes()
        result = surfaces.prepare_surfaces(self.manifest, second)
        self.assertEqual(result, self.prepared)
        for path in self.output.iterdir():
            self.assertEqual(path.read_bytes(), (second / path.name).read_bytes())
        self.assertEqual(self.manifest.read_bytes(), before)
        with self.assertRaisesRegex(surfaces.SurfaceFailure, "already exists"):
            surfaces.prepare_surfaces(self.manifest, second)

    def test_a_contradictory_native_axis_is_rejected_without_publishing_a_directory(self):
        copied = self.root / "wrong-axis"
        shutil.copytree(self.manifest.parent, copied)
        manifest = json.loads((copied / "manifest.json").read_text())
        native = surfaces.read_asset(copied, manifest["nativeTopology"])
        native["ways"][0]["coordinatesWGS84"][0][0] += .0001
        (copied / "native-topology.json.gz").unlink()
        manifest["nativeTopology"] = surfaces.write_asset(copied / "native-topology.json.gz", native, 16 * 1024 * 1024)
        (copied / "manifest.json").write_bytes(surfaces.canonical(manifest))
        destination = self.root / "invalid-output"
        with self.assertRaisesRegex(surfaces.SurfaceFailure, "contradictory full native"):
            surfaces.prepare_surfaces(copied / "manifest.json", destination)
        self.assertFalse(destination.exists())

    def test_checksum_drift_is_rejected_before_surface_publication(self):
        copied = self.root / "wrong-checksum"
        shutil.copytree(self.manifest.parent, copied)
        manifest = json.loads((copied / "manifest.json").read_text())
        asset = copied / manifest["tiles"][0]["vector"]["path"]
        with asset.open("ab") as stream:
            stream.write(b"drift")
        with self.assertRaisesRegex(surfaces.SurfaceFailure, "checksum"):
            surfaces.prepare_surfaces(copied / "manifest.json", self.root / "bad-checksum-output")
        self.assertFalse((self.root / "bad-checksum-output").exists())

    def test_manifest_change_during_scan_is_rejected_before_publication(self):
        copied = self.root / "changed-manifest"
        shutil.copytree(self.manifest.parent, copied)
        path = copied / "manifest.json"

        def mutate_after_scan(event):
            if event["phase"] == "vectors-scanned":
                path.write_bytes(path.read_bytes() + b"\n")

        destination = self.root / "changed-source-output"
        with self.assertRaisesRegex(surfaces.SurfaceFailure, "manifest changed"):
            surfaces.prepare_surfaces(path, destination, progress=mutate_after_scan)
        self.assertFalse(destination.exists())

    def test_requested_coverage_remains_a_hard_surface_boundary(self):
        extent = box(*self.geometry["bounds"][0])
        masked, _ = surfaces.cell_surfaces(self.geometry["bounds"][0],
                    {"road": box(*self.geometry["bounds"][0])}, Polygon(),
                    box(self.geometry["bounds"][0][0], self.geometry["bounds"][0][1], ORIGIN[0], self.geometry["bounds"][0][3]))
        self.assertAlmostEqual(masked["areaM2"]["road"], extent.area / 2, places=6)


@unittest.skipUnless(HAVE_GIS and shutil.which("node") and BASELINE.exists() and REAL_SAMPLE.exists() and GLOBAL_SAMPLE.exists(),
                     "Checked real source and its original global-union surfaces are optional")
class RealSampleRegression(unittest.TestCase):
    def test_real_cells_match_original_global_surfaces_metadata_and_provenance(self):
        original = json.loads(GLOBAL_SAMPLE.read_text())
        self.assertEqual(original["sourceVectorManifest"]["sha256"], surfaces.file_sha256(REAL_SAMPLE))
        with tempfile.TemporaryDirectory(prefix="massilia-surface-index-real-") as temporary:
            destination = Path(temporary) / "surfaces"
            actual = surfaces.prepare_surfaces(REAL_SAMPLE, destination)
            self.assertEqual(actual["dimensionCore"], original["dimensionCore"])
            for key in ("roadWidthSources", "withheldReasons", "sourceRoadPointsRetainedInVectors", "newElevations", "inventedMarkings"):
                self.assertEqual(actual["report"][key], original["report"][key])
            self.assertEqual(len(actual["tiles"]), len(original["tiles"]))
            for old_tile, tile in zip(original["tiles"], actual["tiles"]):
                self.assertEqual(tile["cellId"], old_tile["cellId"])
                before = surfaces.read_asset(GLOBAL_SAMPLE.parent, old_tile["surface"])
                after = surfaces.read_asset(destination, tile["surface"])
                self.assertEqual(before["roadMetadata"], after["roadMetadata"])
                for key in ("sourcePbfSHA256", "sourceVectorManifestSHA256", "nativeTopologySHA256", "dimensionCoreSHA256", "buildings", "heightReferences", "policy"):
                    self.assertEqual(before[key], after[key])
                for layer in surfaces.LAYERS:
                    self.assertLess(world_surface(before, {layer}).symmetric_difference(world_surface(after, {layer})).area, 1e-6)
                    self.assertAlmostEqual(before["cell"]["areaM2"][layer], after["cell"]["areaM2"][layer], places=5)
            self.assertEqual(actual["report"]["spatialPreparation"]["cellsQueried"], 2)


if __name__ == "__main__":
    unittest.main()
