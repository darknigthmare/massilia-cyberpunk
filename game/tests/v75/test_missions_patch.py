"""Missions75 derives only city45 from the unchanged edition74 parent."""
import re
import sys
import unittest
from pathlib import Path

GAME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GAME))
from tools.v75_missions import MARKER, patch_html, patch_viewer


class MissionPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parent = (GAME / 'SOMA_MASSILIA_URBAIN_v0_74.html').read_text()
        cls.modules = {'missions-runtime': (GAME / 'src/v75/missions-runtime.js').read_text()}
        cls.patched = patch_html(cls.parent, cls.modules)

    def test_only_existing_owners_change_without_weakening_proof_or_persistence(self):
        scripts = lambda h: dict(re.findall(r'<script\b[^>]*id="([^"]+)"[^>]*>([\s\S]*?)</script>', h))
        old, new = scripts(self.parent), scripts(self.patched)
        self.assertEqual(set(old), set(new))
        self.assertEqual({key for key in old if old[key] != new[key]}, {'soma-v45-city', 'soma-v43-production', 'soma-v37-persistence'})
        for name, end in [('v74AuthorizeStep', 'v74DriveProof'), ('v74CommandProof', 'v74RestoreEnemy'), ('v74RestoreEnemy', 'v74Checkpoint')]:
            segment = lambda body: body.split('function '+name+'(', 1)[1].split('function '+end+'(', 1)[0]
            self.assertEqual(segment(old['soma-v45-city']), segment(new['soma-v45-city']))
        self.assertNotIn('localStorage', self.modules['missions-runtime'])
        self.assertNotIn('core.v75', self.modules['missions-runtime'])
        for anchor in ['function snapshot(){', 'function writeAtomic(', 'function applyEnvelope(', 'function transact(']:
            segment = lambda body: body.split(anchor, 1)[1].split('\nfunction ', 1)[0]
            self.assertEqual(segment(old['soma-v37-persistence']), segment(new['soma-v37-persistence']))
        production = new['soma-v43-production']
        self.assertLess(production.index('window.__SOMA_MISSIONS75_CONTENT__='), production.index('v43Setup();'))
        self.assertEqual(patch_viewer(self.parent, self.modules), self.parent)

    def test_rejects_drift_reapplication_wrong_parent_and_bad_modules(self):
        for parent in [self.patched, self.parent.replace('id="soma-v74-edition"', 'id="changed"'), self.parent.replace('function v45Setup(){', 'function changed(){')]:
            with self.assertRaises(ValueError):
                patch_html(parent, self.modules)
        for module in ['', None, '</ScRiPt>']:
            with self.assertRaises(ValueError):
                patch_html(self.parent, {'missions-runtime': module})


if __name__ == '__main__':
    unittest.main()
