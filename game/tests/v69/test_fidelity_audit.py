"""Independent audit regressions, including the actual frozen source cores."""
from copy import deepcopy
import base64
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import struct
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("fidelity_audit", ROOT / "game/tools/v69/fidelity_audit.py")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def embedded(value, *, declared_size=None, declared_hash=None):
    raw = json.dumps(value, separators=(",", ":")).encode()
    body = base64.b64encode(gzip.compress(raw, mtime=0)).decode()
    size = len(raw) if declared_size is None else declared_size
    sha = hashlib.sha256(raw).hexdigest() if declared_hash is None else declared_hash
    return f'<script id="fixture" data-encoding="gzip-base64" data-bytes="{size}" data-sha256="{sha}">{body}</script>'


def source_pack():
    def record(name, x, height="10"):
        return {"cellId": name, "boundsL93": [x, 2000, x+250, 2250],
                "sourceReceipt": {"sha256": "a"*64},
                "featureCollection": {"features": [{"id": "osm/way/1", "properties": {
                    "canonical_id": "osm/way/1", "soma:layer": "buildings", "height": height,
                    "soma:geometry_sha256": "b"*64,
                    "soma:mesh53": [{"ringsL93": [[[x, 2000]]]}],
                    "soma:metricGeometry": {"type": "Polygon", "coordinates": []}}}]}}
    return {"schema": "soma-massilia/geodata-pack/4", "records": [record("A", 1000), record("B", 1250)]}


class ArtifactTests(unittest.TestCase):
    def test_modified_baseline_is_refused_before_any_evaluation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "changed.html"
            path.write_text("<html>changed release</html>")
            with self.assertRaisesRegex(AUDIT.AuditError, "différente"):
                AUDIT.read_verified_baseline(path)

    def test_decoding_verifies_actual_bytes_and_duplicate_scripts(self):
        value = {"records": [], "source": "échantillon"}
        payload, proof = AUDIT.decode_blob(embedded(value), "fixture")
        self.assertEqual(payload, value)
        self.assertEqual(len(proof["sha256"]), 64)
        with self.assertRaisesRegex(AUDIT.AuditError, "dupliqué"):
            AUDIT.decode_blob(embedded(value)+embedded(value), "fixture")
        with self.assertRaisesRegex(AUDIT.AuditError, "Empreinte"):
            AUDIT.decode_blob(embedded(value, declared_hash="0"*64), "fixture")
        with self.assertRaises(AUDIT.AuditError):
            AUDIT.decode_blob(embedded(value, declared_size=AUDIT.MAX_EMBEDDED_BYTES+1), "fixture")

    def test_multicell_fragments_count_one_object_without_mutating_sources(self):
        pack = source_pack()
        before = deepcopy(pack)
        coverage, objects, records = AUDIT.collect_sources(pack)
        self.assertEqual(coverage["count"], 2)
        self.assertEqual(coverage["fragments"], 2)
        self.assertEqual(coverage["unique"], 1)
        self.assertEqual(coverage["multiCellBuildings"], 1)
        self.assertEqual(coverage["areaKm2"], .125)
        self.assertEqual(len(objects), 1)
        self.assertEqual(len(records), 2)
        self.assertEqual(pack, before)

    def test_conflicting_canonical_tags_are_not_silently_deduplicated(self):
        pack = source_pack()
        pack["records"][1]["featureCollection"]["features"][0]["properties"]["height"] = "20"
        with self.assertRaisesRegex(AUDIT.AuditError, "contradictoire"):
            AUDIT.collect_sources(pack)

    def test_fixture_duplicate_cell_and_shifted_grid_are_refused(self):
        for mutate in (
            lambda pack: pack.update(testOnly=True),
            lambda pack: pack["records"][0].update(v53Synthetic=True),
            lambda pack: pack["records"][1].update(cellId="A"),
            lambda pack: pack["records"][1].update(boundsL93=[1125, 2000, 1375, 2250]),
            lambda pack: pack["records"][1].update(boundsL93=[1250, 2000, 1500, float("nan")]),
        ):
            with self.subTest(mutate=mutate):
                pack = source_pack(); mutate(pack)
                with self.assertRaises(AUDIT.AuditError):
                    AUDIT.collect_sources(pack)

    def test_territorial_membership_is_not_an_area_coverage_claim(self):
        unknown = AUDIT.territory_summary(None)
        self.assertIsNone(unknown["coverageRatio"])
        self.assertFalse(unknown["boundaryValidated"])
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "territory.json"
            target.write_text(json.dumps({"schema": "soma-metropole/territory/1", "id": "200054807",
                "name": "AMP", "year": 2026, "communes": [{"code": f"{n:05d}"} for n in range(92)],
                "boundary": None, "source": {"license": "LO-2.0"}}))
            declared = AUDIT.territory_summary(target)
            self.assertEqual(declared["communeCount"], 92)
            self.assertFalse(declared["boundaryValidated"])
            self.assertIsNone(declared["coverageRatio"])
            payload = json.loads(target.read_text());payload["communes"][1]["code"] = payload["communes"][0]["code"]
            target.write_text(json.dumps(payload))
            with self.assertRaises(AUDIT.AuditError):
                AUDIT.territory_summary(target)

    def test_unavailable_node_is_reported_as_a_development_prerequisite(self):
        with self.assertRaisesRegex(AUDIT.AuditError, "exécuter"):
            AUDIT.run_cores({}, {}, node="/nonexistent/node-audit-test")

    def test_terrain_counts_only_valid_nodes_and_refuses_invalid_masks_or_shapes(self):
        terrain = {"gridHeader": json.dumps({"rows": 2, "cols": 2}),
                   "dataBase64": base64.b64encode(struct.pack("<4f", 1, 2, float("nan"), 4)).decode(),
                   "maskBase64": base64.b64encode(bytes([1, 1, 0, 1])).decode()}
        stats = AUDIT.terrain_statistics(terrain)
        self.assertEqual(stats["computedValid"], 3)
        self.assertEqual(stats["computedNoData"], 1)
        self.assertEqual(stats["computedMinM"], 1)
        self.assertEqual(stats["computedMaxM"], 4)
        for edit in (
            {"maskBase64": base64.b64encode(bytes([1, 2, 0, 1])).decode()},
            {"maskBase64": base64.b64encode(bytes([1, 1, 1, 1])).decode()},
            {"gridHeader": json.dumps({"rows": "2", "cols": 2})},
            {"gridHeader": json.dumps({"rows": 2, "cols": 3})},
        ):
            with self.subTest(edit=edit):
                with self.assertRaises(AUDIT.AuditError):
                    AUDIT.terrain_statistics({**terrain, **edit})


@unittest.skipUnless(shutil.which("node"), "Node.js required for delivered-core audit tests")
class DeliveredCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html, _ = AUDIT.read_verified_baseline(ROOT / "game/baseline/v66.html")
        cls.scripts = AUDIT.core_sources(cls.html)

    def test_height_precedence_and_units_use_actual_shipped_core(self):
        geometry_hash = "c"*64
        ign = {"geometrySHA256": geometry_hash, "height": 20, "groundAltitude": 7,
               "ignId": "IGN-test", "iou": .99, "margin": .99}
        rows = [
            {"id": "explicit", "p": {"height": "10", "building:levels": "8", "soma:geometry_sha256": geometry_hash}, "ign": ign},
            {"id": "ign", "p": {"building:levels": "8", "soma:geometry_sha256": geometry_hash}, "ign": ign},
            {"id": "levels", "p": {"building:levels": "4"}},
            {"id": "unknown", "p": {"building": "yes"}},
            {"id": "feet", "p": {"height": "10 ft"}},
            {"id": "invalid", "p": {"height": "not-a-measurement", "building:levels": "2"}},
        ]
        result = AUDIT.run_cores(self.scripts, {"operation": "dimensions", "rows": rows})
        self.assertEqual([d["heightSource"] for d in result], ["osm-height", "ign-bdtopo-height", "estimated-from-levels", "procedural-estimate", "osm-height", "estimated-from-levels"])
        self.assertEqual(result[0]["height"], 10)
        self.assertEqual(result[1]["height"], 20)
        self.assertAlmostEqual(result[4]["height"], 3.048)

    def test_real_inventory_counts_source_members_not_fragments_and_never_certifies(self):
        report = AUDIT.create_report(ROOT / "game/baseline/v66.html", ROOT / "game/data/v58/terrain.ign.json",
                                    ROOT / "game/data/v63/navigation.json", territory_path=ROOT / "game/data/v69/territory.json")
        self.assertEqual(report["cells"]["count"], 168)
        self.assertEqual(report["cells"]["areaKm2"], 10.5)
        self.assertEqual(report["cells"]["counts"]["buildings"], 34986)
        self.assertEqual(report["cells"]["fragmentsByLayer"]["buildings"], 38206)
        self.assertEqual(report["buildings"]["sourceHeightDistribution"], {
            "osm-height": 477, "ign-bdtopo-height": 23, "estimated-from-levels": 5140, "procedural-estimate": 29346})
        self.assertEqual(report["buildings"]["declaredHeightOrIGN"], 500)
        self.assertEqual(report["buildings"]["activeBuildingParts"], 359)
        self.assertEqual(report["buildings"]["sourceHeightByObjectKind"]["buildingParts"]["osm-height"], 273)
        self.assertEqual(report["buildings"]["sourceHeightByObjectKind"]["otherBuildingObjects"]["osm-height"], 204)
        self.assertEqual(report["roads"]["widthDistribution"]["osm-width"], 100)
        self.assertEqual(report["roads"]["indoorCoveredClassifiedAsNonStructural"], 72)
        self.assertEqual(report["cellSeams"]["matchedRoadEndpointPairs"], 967)
        self.assertEqual(report["navigation"]["crossCellSegments"], 1631)
        self.assertTrue(report["terrain"]["sourceCoreValidated"])
        self.assertEqual(report["terrain"]["computedNodes"], 17689)
        self.assertFalse(report["auditScope"]["activeV69CorrectionsIncluded"])
        self.assertFalse(report["certification"]["completeMetropoleAMP"])
        self.assertIsNone(report["requestedTerritory"]["coverageRatio"])
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            AUDIT.write_report(report, output); first = output.read_bytes()
            AUDIT.write_report(report, output)
            self.assertEqual(first, output.read_bytes())
            self.assertNotIn("generatedAt", output.read_text())

    def test_a_graph_bound_to_other_sources_or_cell_versions_is_refused(self):
        original = json.loads((ROOT / "game/data/v63/navigation.json").read_text())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "navigation.json"
            for mutation, message in (
                (lambda graph: graph.update(sourcePbfSHA256="0"*64), "autre source"),
                (lambda graph: graph["cellHashes"].update({next(iter(graph["cellHashes"])): "0"*64}), "Empreintes"),
            ):
                graph = deepcopy(original);mutation(graph);path.write_text(json.dumps(graph))
                with self.subTest(message=message):
                    with self.assertRaisesRegex(AUDIT.AuditError, message):
                        AUDIT.create_report(ROOT / "game/baseline/v66.html", ROOT / "game/data/v58/terrain.ign.json", path)


if __name__ == "__main__":
    unittest.main()
