"""Guard the narrow handoff55 rewrite; no generated HTML is edited."""
from pathlib import Path
import re
import sys
import unittest

GAME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GAME))
from tools import v78_world as W


def script(html, name):
    return re.search(r'<script\b[^>]*id="' + name + r'"[^>]*>([\s\S]*?)</script>', html)[1]


class WorldPatch78Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parent = (GAME / 'SOMA_MASSILIA_URBAIN_v0_77.html').read_text()
        cls.runtime = (GAME / 'src/v78/world-transaction-runtime.js').read_text()
        cls.output = W.patch_html(cls.parent, {W.MODULES[0]: cls.runtime})

    def test_only_handoff_owner_and_the_new_local_helper_change(self):
        before = script(self.parent, 'soma-v55-runtime')
        after = script(self.output, 'soma-v55-runtime')
        begin = before.index('function handoff(')
        end = before.index('function transferAfterMove(', begin)
        self.assertEqual(after[:begin], before[:begin])
        self.assertEqual(after[after.index('function transferAfterMove('):], before[end:])
        for name in ['soma-v37-persistence', 'soma-v45-city', 'soma-v56-terrain-runtime', 'soma-v57-runtime', 'soma-v75-vehicle-runtime']:
            if 'id="' + name + '"' in self.parent:
                with self.subTest(name=name):
                    self.assertEqual(script(self.output, name), script(self.parent, name))
        self.assertEqual(script(self.output, 'soma-v78-world-transaction-runtime').strip(), self.runtime.strip())

    def test_source_snapshot_is_inside_try_and_recovery_cannot_skip_finally(self):
        body = script(self.output, 'soma-v55-runtime')
        handoff = body[body.index('function handoff('):body.index('function transferAfterMove(')]
        self.assertLess(handoff.index('try{'), handoff.index('remember(from);'))
        self.assertIn('finally{transitioning=false;}', handoff)
        self.assertIn('try{window.__SOMA_V54__.refreshScene();}catch{}', handoff)
        self.assertIn('window.__SOMA_WORLD78__.restoreBody(transaction78);return false;', handoff)

    def test_no_persistence_domain_or_geographic_viewer_change(self):
        self.assertEqual(W.patch_viewer('<html>viewer</html>', {}), '<html>viewer</html>')
        self.assertNotIn('localStorage', self.runtime)
        self.assertNotIn('sessionStorage', self.runtime)
        self.assertNotIn('indexedDB', self.runtime)
        self.assertNotIn('state.v78', self.output)

    def test_reapplication_and_missing_or_ambiguous_owner_fail_closed(self):
        with self.assertRaises(ValueError):
            W.patch_html(self.output, {W.MODULES[0]: self.runtime})
        body = script(self.parent, 'soma-v55-runtime')
        for changed in [body.replace('remember(from);', '', 1), body + body]:
            with self.subTest(size=len(changed)), self.assertRaises(ValueError):
                W.patch_handoff(changed)

    def test_missing_empty_and_script_terminating_runtime_are_rejected(self):
        for value in [None, '', ' \n', '</ScRiPt>']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                W.patch_html(self.parent, {W.MODULES[0]: value})


if __name__ == '__main__':
    unittest.main()
