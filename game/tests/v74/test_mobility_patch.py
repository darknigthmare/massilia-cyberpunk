"""Strict production transforms over the actual delivered v73 campaign."""
from pathlib import Path
import re
import sys
import unittest

GAME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GAME))
from tools.v74_mobility import MARKER, patch_html, patch_viewer


def scripts(html):
    return {m[1]: m[2] for m in re.finditer(r'<script\b[^>]*id="([^"]+)"[^>]*>([\s\S]*?)</script>', html)}


class MobilityPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parent = (GAME / 'SOMA_MASSILIA_URBAIN_v0_73.html').read_text()
        cls.modules = {'mobility-runtime': (GAME / 'src/v74/mobility-runtime.js').read_text()}
        cls.patched = patch_html(cls.parent, cls.modules)

    def test_only_historical_movement_owner_and_terrain_wrapper_are_transformed(self):
        before, after = scripts(self.parent), scripts(self.patched)
        self.assertEqual({name for name in before if before[name] != after[name]}, {'soma-v56-terrain-runtime'})
        self.assertEqual(set(after) - set(before), {'soma-v74-mobility-runtime'})
        # Source packs, core66, routing, progression and every existing named
        # script, except the terrain movement wrapper, remain byte identical.
        for name in before:
            if name != 'soma-v56-terrain-runtime':
                self.assertEqual(before[name], after[name], name)
        self.assertEqual(self.patched.count(MARKER), 1)
        self.assertNotIn('localStorage', after['soma-v74-mobility-runtime'])
        self.assertNotIn('createElement', after['soma-v74-mobility-runtime'])

    def test_duplicate_or_missing_owner_anchor_fails_instead_of_silently_bypassing_control(self):
        for html in [self.patched, self.parent.replace('const p=safeExitPoint(v);v.speed=0;', 'const p=unknownExit(v);v.speed=0;'),
                     self.parent.replace('function safeExitPoint(v){const spec=vehicleSpec(v);', 'function unknownExit(v){const spec=vehicleSpec(v);'),
                     self.parent.replace(' move=function(dt){\n  const from=zone,before=', ' move=function(dt){\n  const notFrom=zone,before=')]:
            with self.assertRaises(ValueError):
                patch_html(html, self.modules)
        for value in ['', None, '</ScRiPt>']:
            with self.assertRaises(ValueError):
                patch_html(self.parent, {'mobility-runtime': value})

    def test_viewer_remains_byte_identical(self):
        viewer = (GAME / 'metropole-viewer-v73.html').read_text()
        self.assertEqual(patch_viewer(viewer, self.modules), viewer)


if __name__ == '__main__':
    unittest.main()
