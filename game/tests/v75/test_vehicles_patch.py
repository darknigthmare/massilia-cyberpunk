"""The v75 contact guard must transform the real frozen v74 owner exactly once."""
from pathlib import Path
import re
import sys
import unittest

GAME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GAME))
from tools.v75_vehicles import MODULES, MARKER, patch_html, patch_viewer


class VehiclesPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parent = (GAME / 'SOMA_MASSILIA_URBAIN_v0_74.html').read_text()
        cls.modules = {'vehicle-runtime': (GAME / 'src/v75/vehicle-runtime.js').read_text()}
        cls.patched = patch_html(cls.parent, cls.modules)

    def test_only_contact_call_changes_in_the_mechanics_owner(self):
        self.assertEqual(MODULES, ('vehicle-runtime',))
        self.assertEqual(self.patched.count(MARKER), 1)
        before = dict(re.findall(r'<script\b[^>]*id="([^"]+)"[^>]*>([\s\S]*?)</script>', self.parent))
        after = dict(re.findall(r'<script\b[^>]*id="([^"]+)"[^>]*>([\s\S]*?)</script>', self.patched))
        self.assertEqual(set(after) - set(before), {'soma-v75-vehicle-runtime'})
        for name in before:
            self.assertEqual(before[name], after[name], name)
        original = 'if(vehicleBlockedAt(v,nx,nz,v.heading)){collided=true;impact=Math.max(impact,Math.abs(old));v.heading=previousHeading57;'
        self.assertEqual(self.parent.count(original), 1)
        self.assertNotIn(original, self.patched)
        self.assertNotIn('localStorage', after['soma-v75-vehicle-runtime'])
        self.assertNotIn('integrateVehicle=', after['soma-v75-vehicle-runtime'])

    def test_missing_duplicate_owner_module_and_wrong_parent_fail_closed(self):
        for html in [self.patched, self.parent.replace('id="soma-v74-mobility-runtime"', 'id="unknown-parent"'),
                     self.parent.replace('v.heading=previousHeading57;', 'v.heading=unknownHeading;')]:
            with self.assertRaises(ValueError):
                patch_html(html, self.modules)
        for text in ['', None, '</ScRiPt>']:
            with self.assertRaises(ValueError):
                patch_html(self.parent, {'vehicle-runtime': text})

    def test_viewer_is_a_byte_preserving_pass_through(self):
        viewer = (GAME / 'metropole-viewer-v74.html').read_text()
        self.assertEqual(patch_viewer(viewer, self.modules), viewer)


if __name__ == '__main__':
    unittest.main()
