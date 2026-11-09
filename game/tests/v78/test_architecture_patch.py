"""Exercise the actual frozen viewer anchors, without rewriting parent sources."""
from pathlib import Path
import sys
import unittest

GAME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GAME))
from tools import v78_architecture as P


@unittest.skipUnless((GAME / 'metropole-viewer-v77.html').is_file(), 'prepared parent77 viewer required')
class Architecture78PatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parent = (GAME / 'metropole-viewer-v77.html').read_text()
        cls.scripts = {P.MODULES[0]: (GAME / 'src/v78/architecture-roof-core.js').read_text()}

    def test_campaign_is_exact_identity_and_viewer_loads_after73(self):
        self.assertEqual(P.patch_html(self.parent, self.scripts), self.parent)
        result = P.patch_viewer(self.parent, self.scripts)
        self.assertLess(result.index('id="viewer-roof-fidelity73-core"'), result.index('id="viewer-architecture78-core"'))
        self.assertLess(result.index('id="viewer-architecture78-core"'), result.index('id="viewer-metropole-viewer-core"'))
        self.assertNotIn('id="viewer-architecture78-core"', self.parent)
        self.assertIn('roofFrame78', result)
        self.assertIn('Le profil pyramidal et son sommet sont interprétés', result)

    def test_repeated_application_and_injection_are_refused(self):
        result = P.patch_viewer(self.parent, self.scripts)
        with self.assertRaises(ValueError):
            P.patch_viewer(result, self.scripts)
        for scripts in ({}, {P.MODULES[0]: ''}, {P.MODULES[0]: '</script><script>'}):
            with self.subTest(scripts=scripts), self.assertRaises(ValueError):
                P.patch_viewer(self.parent, scripts)

    def test_missing_or_ambiguous_frozen_owner_anchors_are_refused(self):
        for original, replacement in [('viewer-roof-fidelity73-core', 'missing-parent'),
                                      ('viewer-metropole-viewer-core', 'missing-geometry'),
                                      ('viewer-architecture71-runtime', 'missing-inspector')]:
            with self.subTest(original=original), self.assertRaises(ValueError):
                P.patch_viewer(self.parent.replace(original, replacement), self.scripts)
        duplicated = self.parent.replace('<script id="viewer-roof-fidelity73-core">',
                                         '<script id="viewer-roof-fidelity73-core"></script><script id="viewer-roof-fidelity73-core">')
        with self.assertRaises(ValueError):
            P.patch_viewer(duplicated, self.scripts)

    def test_existing_occlusion_navigation_and_terrain_owners_remain_exact(self):
        import re
        result = P.patch_viewer(self.parent, self.scripts)
        for name in ['viewer-road72-core', 'viewer-geographic-core', 'viewer-terrain-core',
                     'viewer-architecture71-core', 'viewer-source-router63', 'viewer-metropole-viewer']:
            pattern = r'<script id="' + name + r'">([\s\S]*?)</script>'
            self.assertEqual(re.search(pattern, result)[1], re.search(pattern, self.parent)[1], name)


if __name__ == '__main__':
    unittest.main()
