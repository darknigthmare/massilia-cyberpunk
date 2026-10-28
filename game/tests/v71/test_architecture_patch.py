"""Exercise the derived inspector against the actual frozen viewer scripts."""
from pathlib import Path
import hashlib
import sys
import unittest

GAME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GAME))
sys.path.insert(0, str(GAME / 'tools'))
from tools import v71_architecture as P
from build_metropole_viewer_v70 import derive_controller


def scripts():
    return {name: (GAME / ('src/v71/' + name + '.js')).read_text() for name in P.MODULES}


def fixture():
    core = (GAME / 'src/v69/metropole-viewer-core.js').read_text().replace(
        'const material=A.appearance(p,id),canonical=',
        'const material=root.__SOMA_MATERIAL70_CORE__.appearance(p,id),canonical=')
    controller = derive_controller((GAME / 'src/v69/metropole-viewer.js').read_text())
    return ('<!doctype html><html><head><style></style></head><body><button id="open-help">Aide</button>'
            '<dialog id="help-dialog"></dialog>'
            '<script id="viewer-metropole-viewer-core">' + core + '</script>'
            '<script id="viewer-metropole-viewer">' + controller + '</script></body></html>')


class Architecture71PatchTests(unittest.TestCase):
    def test_campaign_is_byte_identical(self):
        original = '<html><body>Campaign save and geometry unchanged.</body></html>'
        self.assertEqual(P.patch_html(original, scripts()), original)

    def test_real_controller_and_geometry_gain_read_only_evidence_in_correct_order(self):
        original = fixture()
        output = P.patch_viewer(original, scripts())
        for identifier in ['viewer-architecture71-core', 'viewer-architecture71-runtime', 'architecture71-open', 'architecture71-dialog']:
            self.assertEqual(output.count('id="' + identifier + '"'), 1)
        self.assertLess(output.index('id="viewer-architecture71-core"'), output.index('id="viewer-metropole-viewer-core"'))
        self.assertLess(output.index('id="viewer-metropole-viewer"'), output.index('id="viewer-architecture71-runtime"'))
        self.assertIn('architectureContext:architecture71Context,narrowContext:()=>route70Context,', output)
        self.assertIn('acquire:route70Acquire', output)
        self.assertIn('visibleCellIds:new Set(targetIds)', output)
        self.assertIn('facts(p,dim,plan,material,record,base)', output)
        self.assertNotIn(P.MARKER, original)

    def test_render_functions_and_camera_matrices_remain_untouched(self):
        original = fixture()
        output = P.patch_viewer(original, scripts())
        for start, end in [('  function multiply(a,b){', '  let renderer;'),
                           ('  function updateTarget(force=false){', '  function inside(')]:
            parent = original[original.index(start):original.index(end, original.index(start))]
            child = output[output.index(start):output.index(end, output.index(start))]
            self.assertEqual(child, parent)

    def test_anchors_duplicate_or_drift_and_script_terminators_are_refused(self):
        original = fixture()
        patched = P.patch_viewer(original, scripts())
        with self.assertRaises(ValueError):
            P.patch_viewer(patched, scripts())
        for anchor in ['}counts.buildings++;', '    const counts=emptyCounts();', '        narrowContext:()=>route70Context,']:
            for replacement in ['', anchor + anchor]:
                with self.assertRaises(ValueError):
                    P.patch_viewer(original.replace(anchor, replacement), scripts())
        bad = scripts()
        bad[P.MODULES[0]] += '</ScRiPt>'
        with self.assertRaises(ValueError):
            P.patch_viewer(original, bad)

    def test_derived_patch_preserves_all_frozen_sources(self):
        paths = [GAME/'src/v69/metropole-viewer.js', GAME/'src/v69/metropole-viewer-core.js',
                 GAME/'tools/build_metropole_viewer_v70.py', GAME/'src/v70/viewer-runtime.js']
        before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
        P.patch_viewer(fixture(), scripts())
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths])


if __name__ == '__main__':
    unittest.main()
