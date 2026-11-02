"""Only the actual native terrain entry condition changes over frozen75."""
from pathlib import Path
import re
import sys
import unittest

GAME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GAME))
from tools.v76_mobility import MODULES, MARKER, patch_html, patch_viewer


class MobilityPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parent = (GAME/'SOMA_MASSILIA_URBAIN_v0_75.html').read_text()
        cls.modules = {name:(GAME/'src/v76'/(name+'.js')).read_text() for name in MODULES}
        cls.result = patch_html(cls.parent, cls.modules)

    def test_only_entry_owner_changes_and_viewer_is_unchanged(self):
        def scripts(h):
            return {m[1]:m[2] for m in re.finditer(r'<script\b[^>]*id="([^"]+)"[^>]*>([\s\S]*?)</script>',h)}
        before, after = scripts(self.parent), scripts(self.result)
        self.assertEqual({n for n in before if before[n] != after[n]}, {'soma-v56-terrain-runtime', 'soma-v75-terrain-runtime'})
        self.assertEqual(set(after)-set(before), {'soma-v76-entry-runtime'})
        self.assertEqual(self.result.count(MARKER), 1)
        self.assertEqual(patch_viewer('viewer', self.modules), 'viewer')
        source = self.modules['entry-runtime']
        for forbidden in ('localStorage', 'indexedDB', 'buildZone(', 'enterZone(', 'setTimeout(', 'setInterval('):
            self.assertNotIn(forbidden, source)

    def test_mutated_parent_duplicate_and_unsafe_modules_fail_closed(self):
        with self.assertRaises(ValueError):
            patch_html(self.result, self.modules)
        with self.assertRaises(ValueError):
            patch_html(self.parent.replace('   let pose=args[2]||target.spawn;', '   let pose=unknown;'), self.modules)
        for value in ('', None, '</ScRiPt>'):
            with self.assertRaises(ValueError):
                patch_html(self.parent, {'entry-runtime':value})

    def test_real_driving_handoff_keeps_its_captured_pre56_entry_owner(self):
        # Runtime55 captures its old entry before terrain56 installs its wrapper.
        seam = re.search(r'<script id="soma-v55-runtime">([\s\S]*?)</script>', self.result)[1]
        self.assertIn('const ok=oldEnter(to.id,null,targetPose);', seam)
        self.assertIn('oldEnter=enterZone;enterZone=function(id,viaCode=null,pose=null)', seam)
        self.assertLess(self.result.index('<script id="soma-v55-runtime">'), self.result.index('<script id="soma-v56-terrain-runtime">'))
        self.assertNotIn('SOMA_MOBILITY76', seam)


if __name__ == '__main__':
    unittest.main()
