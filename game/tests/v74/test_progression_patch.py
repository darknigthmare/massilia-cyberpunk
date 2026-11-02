"""Transforms use the actual v73 parent and refuse drift or double application."""
import re
import sys
import unittest
from pathlib import Path

GAME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GAME))
from tools.v74_progression import MARKER, patch_html, patch_viewer


def scripts(html):
    return dict(re.findall(r'<script\b[^>]*id="([^"]+)"[^>]*>([\s\S]*?)</script>', html))


class ProgressionPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parent = (GAME / 'SOMA_MASSILIA_URBAIN_v0_73.html').read_text()
        cls.modules = {'progression-runtime': (GAME / 'src/v74/progression-runtime.js').read_text()}
        cls.patched = patch_html(cls.parent, cls.modules)

    def test_only_real_city_owner_and_strict_combat_identity_validation_change(self):
        before, after = scripts(self.parent), scripts(self.patched)
        self.assertEqual(set(before), set(after))
        self.assertEqual({name for name in before if before[name] != after[name]}, {'soma-v45-city', 'soma-v37-persistence', 'soma-v64-group-runtime'})
        self.assertEqual(self.patched.count(MARKER), 1)
        saver = after['soma-v37-persistence']
        for anchor in ['function snapshot(){', 'function writeAtomic(', 'function applyEnvelope(', 'function transact(']:
            old = before['soma-v37-persistence'].split(anchor, 1)[1].split('\nfunction ', 1)[0]
            new = saver.split(anchor, 1)[1].split('\nfunction ', 1)[0]
            self.assertEqual(old, new)
        self.assertNotIn('core.v74', self.modules['progression-runtime'])
        self.assertNotIn('localStorage', self.modules['progression-runtime'])

    def test_missing_anchor_bad_module_wrong_parent_and_repeat_are_refused(self):
        for parent in [self.patched, self.parent.replace('id="soma-v73-edition"', 'id="soma-old-edition"'),
                       self.parent.replace('function v45CompleteOperationStep(id,choice=null){', 'function changed(){')]:
            with self.assertRaises(ValueError):
                patch_html(parent, self.modules)
        for bad in ['', None, '</ScRiPt>']:
            with self.assertRaises(ValueError):
                patch_html(self.parent, {'progression-runtime': bad})

    def test_viewer_remains_byte_identical(self):
        self.assertEqual(patch_viewer(self.parent, self.modules), self.parent)


if __name__ == '__main__':
    unittest.main()
