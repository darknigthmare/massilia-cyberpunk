"""Production76 is a bounded extension of the frozen75 owner scripts."""
import re
import sys
import unittest
from pathlib import Path

GAME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GAME))
from tools.v76_missions import MARKER, LOCATION_REPAIRS, patch_html, patch_viewer


class MissionPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parent = (GAME / 'SOMA_MASSILIA_URBAIN_v0_75.html').read_text()
        cls.modules = {'missions-runtime': (GAME / 'src/v76/missions-runtime.js').read_text()}
        cls.patched = patch_html(cls.parent, cls.modules)

    def test_only_real_production_and_identity_validation_owners_change(self):
        scripts = lambda h: dict(re.findall(r'<script\b[^>]*id="([^"]+)"[^>]*>([\s\S]*?)</script>', h))
        old, new = scripts(self.parent), scripts(self.patched)
        self.assertEqual(set(old), set(new))
        self.assertEqual({key for key in old if old[key] != new[key]}, {'soma-v43-production', 'soma-v37-persistence', 'soma-v45-city', 'soma-v64-group-runtime'})
        self.assertEqual(old['soma-v45-city'].replace("schema:'soma-city/45',revision:1,", "schema:'soma-city/45',revision:1,uiTab:'operations',").replace('const next={...fresh,...raw};', "const next={...fresh,...raw};next.uiTab=['operations','calls','fleet','runs','city'].includes(raw.uiTab)?raw.uiTab:fresh.uiTab;"), new['soma-v45-city'])
        self.assertNotIn('localStorage', self.modules['missions-runtime'])
        self.assertNotIn('core.v76', self.modules['missions-runtime'])
        for anchor in ['function snapshot(){', 'function writeAtomic(', 'function applyEnvelope(', 'function transact(']:
            segment = lambda body: body.split(anchor, 1)[1].split('\nfunction ', 1)[0]
            self.assertEqual(segment(old['soma-v37-persistence']), segment(new['soma-v37-persistence']))
        production = new['soma-v43-production']
        self.assertLess(production.index('const v76Encounters='), production.index('v43Setup();'))
        self.assertLess(production.index('window.__SOMA_MISSIONS76__='), production.index('v43Setup();'))
        for alias, zone, source in LOCATION_REPAIRS:
            self.assertNotIn("zone:'"+alias+"'", production)
            self.assertIn(source, production)
        self.assertEqual(patch_viewer(self.parent, self.modules), self.parent)

    def test_rejects_drift_reapplication_wrong_parent_and_bad_modules(self):
        for parent in [self.patched, self.parent.replace('id="soma-v75-edition"', 'id="changed"'), self.parent.replace('function v43Setup(){', 'function changed(){'), self.parent.replace("'port-ferry'", "'changed-ferry'")]:
            with self.assertRaises(ValueError):
                patch_html(parent, self.modules)
        for module in ['', None, '</ScRiPt>']:
            with self.assertRaises(ValueError):
                patch_html(self.parent, {'missions-runtime': module})


if __name__ == '__main__':
    unittest.main()
