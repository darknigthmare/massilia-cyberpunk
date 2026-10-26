import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

from game.tools.metropole.building_parts import digest, generate_parts, loadproof

GIS_AVAILABLE = all(importlib.util.find_spec(name) is not None for name in ['shapely', 'mapbox_earcut', 'numpy', 'osmium', 'pyproj'])
SOURCE = '1' * 64


def feature(identity, ring, part=None, height='10', holes=None):
    rings = [ring] + (holes or [])
    p = {'canonical_id': identity, 'soma:layer': 'buildings', 'height': height,
        'building': 'yes', 'soma:geometry_sha256': digest(rings),
        'soma:mesh53': [{'ringsL93': rings, 'wallsL93': [
            [point, r[(i + 1) % len(r)]] for r in rings for i, point in enumerate(r)]}]}
    if part is not None:
        p['building:part'] = part
    return {'id': identity, 'properties': p}


def records(parts, parent=None):
    parent = parent or feature('osm/way/1', [[0, 0], [10, 0], [10, 10], [0, 10]], part='no', height='20')
    return [{'cellId': 'source-cell', 'contentSHA256': '2' * 64,
        'sourceReceipt': {'sha256': SOURCE}, 'featureCollection': {'features': [parent] + parts}}]


def part(identity, x0, x1, height='10'):
    return feature(identity, [[x0, 0], [x1, 0], [x1, 10], [x0, 10]], part='yes', height=height)


@unittest.skipUnless(GIS_AVAILABLE, 'Run geometry preparation tests in the optional geodata venv.')
class BuildingPartsTests(unittest.TestCase):
    def test_full_ground_coverage_can_suppress_parent_without_changing_sources(self):
        data = records([part('osm/way/2', 0, 5, height='20'), part('osm/way/3', 5, 10, height='20')])
        before = json.dumps(data, sort_keys=True)
        proof = generate_parts(data)
        parent = proof['parents']['osm/way/1']
        self.assertTrue(parent['suppressParent'])
        self.assertEqual(parent['status'], 'derived-complete')
        self.assertAlmostEqual(parent['coverageRatio'], 1)
        self.assertEqual(set(proof['partParents']), {'osm/way/2', 'osm/way/3'})
        self.assertEqual(json.dumps(data, sort_keys=True), before)
        self.assertEqual(loadproof(proof, data), proof)
        self.assertEqual(parent['residualByCell']['source-cell']['meshes'], [])

    def test_partial_replacement_keeps_residual_and_only_original_source_walls(self):
        data = records([part('osm/way/2', 0, 8)])
        parent = generate_parts(data)['parents']['osm/way/1']
        self.assertFalse(parent['suppressParent'])
        self.assertTrue(parent['replaceParent'])
        self.assertTrue(parent['remainingUnresolved'])
        self.assertAlmostEqual(parent['coverageRatio'], .8)
        self.assertAlmostEqual(parent['residualAreaM2'], 20)
        meshes = parent['residualByCell']['source-cell']['meshes']
        self.assertAlmostEqual(sum(mesh['areaM2'] for mesh in meshes), 20)
        walls = [wall for mesh in meshes for wall in mesh['wallsL93']]
        self.assertTrue(walls)
        self.assertFalse(any(abs(a[0] - 8) < 1e-9 and abs(b[0] - 8) < 1e-9 for a, b in walls))
        self.assertFalse(parent['artificialCutWalls'])

    def test_courtyard_is_never_filled_by_coverage_or_residual_triangulation(self):
        outer = [[0, 0], [10, 0], [10, 10], [0, 10]]
        hole = [[3, 3], [7, 3], [7, 7], [3, 7]]
        parent = feature('osm/way/1', outer, part='no', holes=[hole])
        data = records([part('osm/way/2', 0, 2)], parent)
        proof = generate_parts(data)
        derived = proof['parents']['osm/way/1']
        self.assertAlmostEqual(derived['parentAreaM2'], 84)
        self.assertAlmostEqual(derived['coveredAreaM2'], 20)
        self.assertAlmostEqual(derived['residualAreaM2'], 64)
        from shapely.geometry import Polygon
        courtyard = Polygon(hole)
        for mesh in derived['residualByCell']['source-cell']['meshes']:
            for triangle in mesh['trianglesL93']:
                self.assertLess(Polygon(triangle).intersection(courtyard).area, 1e-8)

    def test_elevated_roofs_and_unknown_heights_do_not_prove_ground_coverage(self):
        elevated = part('osm/way/2', 0, 10)
        elevated['properties']['min_height'] = '4'
        unknown = part('osm/way/3', 0, 10)
        del unknown['properties']['height']
        proof = generate_parts(records([elevated, unknown]))
        self.assertNotIn('osm/way/1', proof['parents'])
        self.assertTrue(any(row['reason'] == 'no-ground-parts-with-explicit-height' for row in proof['ambiguities']))

    def test_ambiguous_containment_never_assigns_parts_by_centroid(self):
        data = records([part('osm/way/2', 0, 5)])
        data[0]['featureCollection']['features'].append(feature('osm/way/3', [[-1, -1], [11, -1], [11, 11], [-1, 11]]))
        proof = generate_parts(data)
        self.assertFalse(proof['parents'])
        self.assertTrue(any(row['reason'] == 'ambiguous-geometric-parent' for row in proof['ambiguities']))

    def test_relation_membership_requires_the_same_pbf_snapshot(self):
        data = records([part('osm/way/2', 0, 5)])
        data[0]['featureCollection']['features'].append(feature('osm/way/3', [[-1, -1], [11, -1], [11, 11], [-1, 11]]))
        relations = [{'id': 9, 'tags': {'type': 'building'}, 'members': [
            {'type': 'w', 'ref': 1, 'role': 'outline'}, {'type': 'w', 'ref': 2, 'role': 'part'}]}]
        proof = generate_parts(data, relations=relations, relations_source_sha=SOURCE)
        self.assertEqual(proof['partParents']['osm/way/2']['parentId'], 'osm/way/1')
        self.assertEqual(proof['parents']['osm/way/1']['association'], ['osm-building-relation'])
        with self.assertRaises(ValueError):
            generate_parts(data, relations=relations, relations_source_sha='9' * 64)

    def test_ground_columns_do_not_punch_holes_in_a_source_canopy(self):
        data = records([part('osm/way/2', 0, 2)])
        data[0]['featureCollection']['features'][0]['properties']['building'] = 'roof'
        self.assertFalse(generate_parts(data)['parents'])

    def test_complete_footprint_without_the_declared_height_envelope_is_withheld(self):
        data = records([part('osm/way/2', 0, 5), part('osm/way/3', 5, 10)])
        proof = generate_parts(data)
        self.assertFalse(proof['parents'])
        self.assertTrue(any(row['reason'] == 'height-envelope-conflict' for row in proof['ambiguities']))

    def test_truncated_source_walls_cannot_prove_a_complete_part(self):
        data = records([part('osm/way/2', 0, 8)])
        data[0]['featureCollection']['features'][1]['properties']['soma:mesh53'][0]['wallsL93'].pop()
        proof = generate_parts(data)
        self.assertFalse(proof['parents'])
        self.assertTrue(any(row['reason'] == 'incomplete-source-wall-boundary' for row in proof['withheldGeometry']))

    def test_complete_metric_outline_can_preserve_a_preexisting_missing_wall_without_repair(self):
        data = records([part('osm/way/2', 0, 8)])
        data[0]['boundsL93'] = [-10, -10, 20, 20]
        data[0]['featureCollection']['features'][0]['properties']['soma:mesh53'][0]['wallsL93'].pop()
        parent = generate_parts(data)['parents']['osm/way/1']
        self.assertEqual(parent['footprintCompletenessProof'], 'no-exposed-cell-cuts')
        self.assertTrue(parent['sourceFootprintComplete'])
        self.assertFalse(parent['sourceWallsComplete'])
        self.assertFalse(parent['artificialCutWalls'])

    def test_checksums_and_geometry_bindings_reject_stale_replacements(self):
        data = records([part('osm/way/2', 0, 8)])
        proof = generate_parts(data)
        changed = copy.deepcopy(proof)
        changed['parents']['osm/way/1']['coverageRatio'] = 1
        with self.assertRaises(ValueError):
            loadproof(changed, data)
        stale = copy.deepcopy(data)
        stale[0]['featureCollection']['features'][1]['properties']['soma:geometry_sha256'] = '4' * 64
        with self.assertRaises(ValueError):
            loadproof(proof, stale)
        with self.assertRaises(ValueError):
            generate_parts(data, min_coverage=.9)
        forged_link = copy.deepcopy(proof)
        forged_link['partParents']['osm/way/2']['parentId'] = 'osm/way/999'
        forged_link['proofSHA256'] = digest({key: value for key, value in forged_link.items() if key != 'proofSHA256'})
        with self.assertRaises(ValueError):
            loadproof(forged_link, data)


class StandardLibraryProofTests(unittest.TestCase):
    def test_invalid_proof_is_rejected_without_gis(self):
        with self.assertRaises(ValueError):
            loadproof({'schema': 'wrong'})


if __name__ == '__main__':
    unittest.main()
