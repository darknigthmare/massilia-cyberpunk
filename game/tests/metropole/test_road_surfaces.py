"""Fixtures and the genuine Marseille correction: source-preserving subtraction."""
import builtins
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch as mock_patch

GAME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GAME / "tools"))
from metropole import road_surfaces as roads

try:
    from shapely.geometry import LineString, Polygon, box
    from shapely.ops import unary_union
    HAVE_SHAPELY = True
except ImportError:
    HAVE_SHAPELY = False


def cell_for(geometry, layer="foot"):
    triangles = roads._triangles(geometry)
    return {"contentSHA256": "a" * 64, "sourceSHA256": "b" * 64,
            "surfaces": {layer: triangles}, "areaM2": {layer: geometry.area}}


def surface(cell, layer):
    return unary_union([Polygon(triangle) for triangle in cell["surfaces"][layer]])


def seal(patch):
    patch.pop("integrity", None)
    patch["integrity"] = {"sha256": roads.object_digest(patch)}
    return patch


class GroundPolicyTests(unittest.TestCase):
    def test_surface_flags_are_explicit_and_conservative(self):
        for properties in ({}, {"layer": "0"}, {"layer": -0.0},
                           {"indoor": "no", "covered": False, "bridge": 0.0, "tunnel": "false"}):
            self.assertEqual(roads.withheld_reasons(properties), [])
        for properties, reason in (({"indoor": "room"}, "indoor"),
                                   ({"covered": "arcade"}, "covered"),
                                   ({"bridge": "movable"}, "bridge"),
                                   ({"tunnel": "building_passage"}, "tunnel"),
                                   ({"layer": "1"}, "nonzero-or-unknown-layer"),
                                   ({"layer": "0;1"}, "nonzero-or-unknown-layer")):
            self.assertIn(reason, roads.withheld_reasons(properties))

    @unittest.skipUnless(shutil.which("node"), "Node is needed for the real runtime guard")
    def test_runtime_guard_matches_generator_and_never_mutates_profiles(self):
        cases = [{}, {"indoor": "no", "covered": False, "bridge": 0.0},
                 {"indoor": "yes"}, {"covered": "colonnade"}, {"layer": "-1"},
                 {"layer": "0;1"}, {"bridge": "movable"}, {"tunnel": "covered"}]
        script = r"""
const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync(process.argv[1],'utf8'),cases=JSON.parse(process.argv[2]);
const core=require(process.argv[1]);
const profile={width:5.5,lanes:2,structural:false,geometrySHA256:'source',oneway:true};
const before=JSON.stringify(profile);
const results=cases.map(p=>core.reasons(p));
const next=core.profile({indoor:'yes'},profile);
assert.equal(next.width,5.5);assert.equal(next.geometrySHA256,'source');assert.equal(next.oneway,true);
assert.equal(next.structural,true);assert.equal(JSON.stringify(profile),before);
assert.equal(core.profile({},profile),profile);
const t={structure:p=>p.old===true},d={roadProfile:p=>({...profile})};
const c=vm.createContext({window:{__SOMA_TERRAIN56_CORE__:t,__SOMA_FIDELITY59_CORE__:d}});
vm.runInContext(source,c);assert(c.window.__SOMA_ROADS69__.install());
assert.equal(t.structure({indoor:'yes'}),true);assert.equal(t.structure({old:true}),true);
assert.equal(t.structure({}),false);assert.equal(d.roadProfile({covered:'arcade'}).structural,true);
assert.equal(d.roadProfile({covered:'no'}).structural,false);
const wrapped=t.structure;c.window.__SOMA_ROADS69__.install();assert.equal(t.structure,wrapped);
console.log(JSON.stringify(results));
"""
        result = subprocess.run([shutil.which("node"), "-e", script,
                                 str(GAME / "src/v69/road-fidelity.js"), json.dumps(cases)],
                                capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout), [roads.withheld_reasons(case) for case in cases])


@unittest.skipUnless(HAVE_SHAPELY, "Use the pinned geodata environment with Shapely 2.1.2")
class GeometryFixtures(unittest.TestCase):
    def test_crossing_preserves_the_valid_road_and_only_removes_unsupported_arms(self):
        horizontal = box(-5, -1, 5, 1)
        vertical = box(-1, -5, 1, 5)
        original = cell_for(horizontal.union(vertical), "road")
        untouched = copy.deepcopy(original)
        # The fixture cell is centred on zero, with local Z pointing south.
        corrected, report = roads.correct_cell(original, [-5, -5, 5, 5], horizontal, vertical)
        self.assertAlmostEqual(report["removedFootprintAreaM2"], 16, places=8)
        self.assertAlmostEqual(surface(corrected, "road").area, 20, places=8)
        self.assertLess(surface(corrected, "road").symmetric_difference(vertical).area, 1e-8)
        self.assertAlmostEqual(report["validOverlapLostM2"], 0, places=8)
        self.assertAlmostEqual(report["validOverlapPreservedM2"], 4, places=8)
        self.assertEqual(original, untouched)
        self.assertEqual(corrected["contentSHA256"], original["contentSHA256"])
        self.assertEqual(corrected["sourceSHA256"], original["sourceSHA256"])

    def test_clipping_keeps_courtyard_holes_and_cannot_add_surface(self):
        courtyard = Polygon([[-5, -5], [5, -5], [5, 5], [-5, 5]],
                            holes=[[[-2, -2], [2, -2], [2, 2], [-2, 2]]])
        original = cell_for(courtyard)
        corrected, _ = roads.correct_cell(original, [-5, -5, 5, 5], box(-5, -1, 5, 1), Polygon())
        actual = surface(corrected, "foot")
        self.assertAlmostEqual(actual.area, 72, places=8)
        self.assertLess(actual.intersection(box(-2, -2, 2, 2)).area, 1e-8)
        self.assertLess(actual.difference(courtyard).area, 1e-8)

    def test_explicit_sidewalk_protects_its_original_side_in_lambert_coordinates(self):
        line = LineString([[-5, 0], [5, 0]])
        profile = {"width": 2, "sidewalk": {"left": True, "leftWidth": 2,
                                              "right": False, "rightWidth": 1}}
        corridor = roads._road_corridor(line, profile)
        self.assertTrue(corridor.covers(box(-4, 1, 4, 3)))
        self.assertAlmostEqual(corridor.intersection(box(-4, -3, 4, -1)).area, 0, places=8)
        original = cell_for(box(-5, -5, 5, 5))
        corrected, _ = roads.correct_cell(original, [-5, -5, 5, 5], box(-5, -5, 5, 5), corridor)
        # Local Z is SOUTH, so the north-side sidewalk must be at negative Z.
        self.assertTrue(surface(corrected, "foot").covers(box(-4, -3, 4, -1)))
        self.assertAlmostEqual(surface(corrected, "foot").intersection(box(-4, 1, 4, 3)).area, 0, places=8)

    def test_unaffected_triangles_keep_exact_original_coordinates(self):
        original = cell_for(box(-5, -5, 5, 5))
        corrected, report = roads.correct_cell(original, [-5, -5, 5, 5], box(100, 100, 110, 110), Polygon())
        self.assertEqual(corrected["surfaces"], original["surfaces"])
        self.assertEqual(report["changedTriangles"], 0)

    def test_polygon_road_masks_keep_their_source_holes(self):
        plaza = Polygon([[0, 0], [10, 0], [10, 10], [0, 10]],
                        holes=[[[3, 3], [7, 3], [7, 7], [3, 7]]])
        corridor = roads._road_corridor(plaza, {"width": 5})
        self.assertEqual(corridor, plaza)
        self.assertAlmostEqual(corridor.area, 84, places=8)


@unittest.skipUnless(HAVE_SHAPELY, "Use the pinned geodata environment with Shapely 2.1.2")
class RealMarseillePatch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = GAME / "baseline/v66.html"
        cls.path = GAME / "data/v69/road-surfaces.json"
        if not cls.baseline.exists() or not cls.path.exists():
            raise unittest.SkipTest("Prepare the original release and generate the real road correction first")
        cls.html = cls.baseline.read_text(encoding="utf-8")
        cls.patch = json.loads(cls.path.read_text(encoding="utf-8"))
        cls.data, _, _ = roads._embedded(cls.html, roads.FIDELITY_ID)
        cls.corrected = roads._apply_data(cls.data, cls.patch)

    def test_actual_72_source_roads_and_27_cells_are_corrected(self):
        roads._validate_patch(self.patch)
        self.assertEqual(len(self.patch["roadMetadata"]), 72)
        self.assertEqual(len(self.patch["report"]["sourceAffectedCells"]), 27)
        self.assertEqual(len(self.patch["cells"]), 27)
        self.assertGreater(self.patch["report"]["removedFootprintAreaM2"], 3500)
        self.assertLess(self.patch["report"]["maximumValidOverlapLostM2"], 1e-6)
        self.assertGreater(self.patch["report"]["validOverlapPreservedM2"], 1000)
        self.assertEqual(self.patch["report"]["beforeSurfaceTriangles"], 99229)
        for source_id, change in self.patch["roadMetadata"].items():
            before = self.data["roadMetadata"][source_id]
            after = change["replacement"]
            self.assertFalse(before["structural"])
            self.assertTrue(after["structural"])
            self.assertTrue(set(after["v69WithheldReasons"]) & {"indoor", "covered"})
            self.assertEqual(after["geometrySHA256"], before["geometrySHA256"])
            self.assertEqual(after["width"], before["width"])
            self.assertEqual(after["oneway"], before["oneway"])

    def test_real_triangles_are_a_subtraction_and_preserve_source_identity(self):
        removed = 0
        for cell_id, change in self.patch["cells"].items():
            before = self.data["cells"][cell_id]
            after = self.corrected["cells"][cell_id]
            self.assertEqual(before["contentSHA256"], after["contentSHA256"])
            self.assertEqual(before["sourceSHA256"], after["sourceSHA256"])
            for layer in before["surfaces"]:
                old, new = surface(before, layer), surface(after, layer)
                self.assertLess(new.difference(old).area, 1e-6, (cell_id, layer))
                expected = change["report"]["removedLayerAreaM2"][layer]
                self.assertAlmostEqual(old.difference(new).area, expected, places=6)
                removed += expected
        self.assertGreater(removed, 3500)
        for cell_id in set(self.data["cells"]) - set(self.patch["cells"]):
            self.assertEqual(self.corrected["cells"][cell_id], self.data["cells"][cell_id])
        self.assertEqual(self.corrected["basePackSHA256"], self.data["basePackSHA256"])
        self.assertEqual(roads.object_digest(self.corrected), self.patch["targetDataSHA256"])

    def test_stairs_are_audited_without_inventing_step_heights(self):
        stairs = self.patch["report"]["stairs"]
        self.assertEqual(stairs["uniqueWays"], 728)
        self.assertEqual(stairs["withStepCount"], 193)
        self.assertEqual(stairs["withExplicitElevation"], 0)
        self.assertEqual(stairs["newStepVolumes"], 0)

    def test_real_generation_is_repeatable_and_keeps_the_frozen_baseline(self):
        before = roads.digest(self.baseline.read_bytes())
        with tempfile.TemporaryDirectory(prefix="massilia-road-regeneration-") as directory:
            destination = Path(directory) / "road-surfaces.json"
            generated = roads.generate(self.baseline, destination)
            self.assertEqual(generated, self.patch)
            self.assertEqual(destination.read_bytes(), self.path.read_bytes())
        self.assertEqual(roads.digest(self.baseline.read_bytes()), before)

    def test_html_application_uses_stdlib_and_changes_only_the_derived_surface_blob(self):
        original_import = builtins.__import__

        def no_shapely(name, *args, **kwargs):
            if name == "shapely" or name.startswith("shapely."):
                raise AssertionError("An ordinary game build must not require Shapely")
            return original_import(name, *args, **kwargs)

        untouched = copy.deepcopy(self.patch)
        with mock_patch("builtins.__import__", side_effect=no_shapely):
            output = roads.apply_to_html(self.html, self.patch)
        old_blob = roads._script_pattern(roads.FIDELITY_ID).search(self.html)[0]
        new_blob = roads._script_pattern(roads.FIDELITY_ID).search(output)[0]
        self.assertEqual(self.html.replace(old_blob, "DERIVED_SURFACES"), output.replace(new_blob, "DERIVED_SURFACES"))
        updated, contract, _ = roads._embedded(output, roads.FIDELITY_ID)
        self.assertEqual(contract["sha256"], self.patch["targetDataSHA256"])
        self.assertEqual(updated, self.corrected)
        self.assertEqual(roads.apply_to_html(output, self.patch), output)
        self.assertEqual(self.patch, untouched)

    def test_corrupt_patch_and_different_sources_are_refused(self):
        broken = copy.deepcopy(self.patch)
        broken["report"]["removedFootprintAreaM2"] += 1
        with self.assertRaisesRegex(ValueError, "checksum"):
            roads.apply_to_html(self.html, broken)
        opening = roads._script_pattern(roads.PACK_ID).search(self.html)[1]
        changed = self.html.replace(opening, opening.replace(self.patch["sources"]["geographicPack"]["sha256"], "0" * 64), 1)
        with self.assertRaisesRegex(ValueError, "different geographic"):
            roads.apply_to_html(changed, self.patch)

    def test_patch_cannot_change_dimensions_or_source_cell_hashes_even_if_resealed(self):
        broken = copy.deepcopy(self.patch)
        change = next(iter(broken["roadMetadata"].values()))
        change["replacement"]["width"] += 1
        change["afterSHA256"] = roads.object_digest(change["replacement"])
        seal(broken)
        with self.assertRaisesRegex(ValueError, "dimension or identity"):
            roads.apply_to_html(self.html, broken)
        broken = copy.deepcopy(self.patch)
        change = next(iter(broken["cells"].values()))
        change["replacement"]["contentSHA256"] = "0" * 64
        change["afterSHA256"] = roads.object_digest(change["replacement"])
        seal(broken)
        with self.assertRaisesRegex(ValueError, "source cell identity"):
            roads.apply_to_html(self.html, broken)


if __name__ == "__main__":
    unittest.main()
