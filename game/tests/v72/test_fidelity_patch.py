"""Patch the true frozen parent; do not edit any geographic source."""
from pathlib import Path
import sys
import unittest

GAME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GAME))
from tools import v72_fidelity as P


def scripts():
    return {name: (GAME / ('src/v72/' + name + '.js')).read_text() for name in P.MODULES}


class Fidelity72PatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (GAME / 'metropole-viewer-v71.html').read_text()

    def test_true_parent_patches_once_in_dependency_order(self):
        out = P.patch_viewer(self.html, scripts())
        for identifier in ['viewer-fidelity72-core', 'viewer-road72-core', 'viewer-road72-runtime', 'road72-open', 'road72-dialog']:
            self.assertEqual(out.count('id="' + identifier + '"'), 1)
        self.assertLess(out.index('id="viewer-dimension-core"'), out.index('id="viewer-fidelity72-core"'))
        self.assertLess(out.index('id="viewer-road72-core"'), out.index('id="viewer-metropole-viewer-core"'))
        self.assertLess(out.index('id="viewer-architecture71-runtime"'), out.index('id="viewer-road72-runtime"'))
        self.assertIn('roadInspectionContext:roadInspection72Context', out)
        self.assertIn('deriveSurfaces(entry.layers.surfaces,record,projector)', out)
        with self.assertRaises(ValueError):
            P.patch_viewer(out, scripts())

    def test_renderer_camera_and_streaming_remain_identical(self):
        out = P.patch_viewer(self.html, scripts())
        for start, end in [('  function multiply(a,b){', '  let renderer;'),
                           ('  function updateTarget(force=false){', '  function inside(')]:
            self.assertEqual(self.html[self.html.index(start):self.html.index(end, self.html.index(start))],
                             out[out.index(start):out.index(end, out.index(start))])

    def test_campaign_only_gets_decimal_profile_wrapper(self):
        html = '<html><body><script id="soma-v59-core">dimension</script><p>save</p></body></html>'
        out = P.patch_html(html, scripts())
        self.assertIn('id="soma-fidelity72-core"', out)
        self.assertNotIn('id="road72-dialog"', out)
        self.assertIn('<p>save</p>', out)

    def test_drift_duplicate_anchors_and_script_terminators_fail(self):
        for anchor in ['const features=record.featureCollection.features||[],sourceSurfaces=entry.layers.surfaces;', '},inspection71);']:
            for replacement in ['', anchor + anchor]:
                with self.assertRaises(ValueError):
                    P.patch_viewer(self.html.replace(anchor, replacement), scripts())
        bad = scripts()
        bad[P.MODULES[0]] += '</ScRiPt>'
        with self.assertRaises(ValueError):
            P.patch_viewer(self.html, bad)


if __name__ == '__main__':
    unittest.main()
