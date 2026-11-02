import importlib.util
import json
from pathlib import Path
import sys
import unittest

GAME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GAME))
from tools import v76_architecture as A


class ArchitectureConflicts(unittest.TestCase):
    def test_triangle_clipping_finds_interior_maximum(self):
        # Independent source triangles cover a square; the measured central
        # summit is absent from every source polygon contour vertex.
        header = dict(cols=3, rows=3, step=5, x0=0, n0=10)
        meshes = [dict(trianglesL93=[[[0, 0], [10, 0], [0, 10]], [[10, 0], [10, 10], [0, 10]]])]
        result = A.triangle_extrema(meshes, header, [0, 0, 0, 0, 12, 0, 0, 0, 0], [1]*9)
        self.assertEqual(result['max'], 12)
        self.assertEqual(result['min'], 0)
        self.assertEqual(result['witnessL93'], [5, 5])

    def test_clip_respects_empty_and_source_triangle_courtyard(self):
        self.assertEqual(A.clip_triangle([[10, 10], [11, 10], [10, 11]], [[0, 0], [1, 0], [0, 1]]), [])
        # Source triangulation on the lower-left corner does not include the
        # far-corner summit, analogous to a courtyard excluded by mesh53.
        result = A.triangle_extrema([dict(trianglesL93=[[[0, 10], [4, 10], [0, 6]]])],
                                   dict(cols=3, rows=3, step=5, x0=0, n0=10), [0, 0, 0, 0, 12, 0, 0, 0, 0], [1]*9)
        self.assertEqual(result['max'], 0)

    def test_missing_data_is_never_replaced(self):
        with self.assertRaisesRegex(ValueError, 'NoData'):
            A.triangle_extrema([dict(trianglesL93=[[[0, 5], [5, 5], [0, 0]]])],
                               dict(cols=2, rows=2, step=5, x0=0, n0=5), [1, 2, 3, 4], [0, 1, 1, 1])

    def test_patch_has_no_parent_owner_or_viewer_mutation(self):
        scripts = {name: 'window.'+name.replace('-', '_')+'=true;' for name in A.MODULES}
        original = '<html><body><script id="soma-v52-runtime">nativeOwner()</script></body></html>'
        built = A.patch_html(original, scripts)
        self.assertIn('<script id="soma-v52-runtime">nativeOwner()</script>', built)
        self.assertEqual(A.patch_viewer(original, scripts), original)
        for name in A.MODULES:
            self.assertEqual(built.count('id="soma-v76-'+name+'"'), 1)
        with self.assertRaises(ValueError):
            A.patch_html(built, scripts)
        with self.assertRaises(ValueError):
            A.patch_html(original, {})
        scripts[A.MODULES[0]] = '</script>'
        with self.assertRaises(ValueError):
            A.patch_html(original, scripts)

    def test_every_published_row_retains_source_ground_and_eave_semantics(self):
        data = json.loads((GAME/'data/v76/architecture-conflicts.json').read_bytes())
        self.assertEqual(data['fragments'], 77)
        self.assertEqual(data['cells'], 40)
        self.assertEqual(data['over3cm'], 76)
        self.assertLess(data['provenance']['maximumIndependentDifferenceM'], 1e-6)
        for row in data['rows']:
            self.assertAlmostEqual(row['absoluteEaveNGF'], row['groundAltitude']+row['eaveHeight'])
            self.assertAlmostEqual(row['terrainAboveEave'], row['nativeFootprintMax']-row['absoluteEaveNGF'])
            self.assertGreater(row['terrainAboveEave'], 0)
        self.assertFalse(data['geometryChanged'])
        self.assertFalse(data['provenance']['sourceContractBugFound'])


if __name__ == '__main__':
    unittest.main()
