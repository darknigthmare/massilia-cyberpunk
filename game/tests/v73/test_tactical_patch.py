"""Strict transforms on actual v72 scripts; no generated source is committed."""
import re
import sys
import unittest
from pathlib import Path

GAME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GAME))
from tools.v73_tactics import MARKER, patch_html, patch_viewer


def scripts(html):
    return {m[1]: m[2] for m in re.finditer(r'<script\b[^>]*id="([^"]+)"[^>]*>([\s\S]*?)</script>', html)}


class TacticalPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parent = (GAME / 'SOMA_MASSILIA_URBAIN_v0_72.html').read_text()
        cls.modules = {'tactical-runtime': (GAME / 'src/v73/tactical-runtime.js').read_text()}
        cls.patched = patch_html(cls.parent, cls.modules)

    def test_real_parent_damage_save_and_ability_owners_are_unchanged(self):
        before, after = scripts(self.parent), scripts(self.patched)
        changed = {key for key in before if before[key] != after[key]}
        self.assertEqual(changed, {'soma-v70-runtime', 'soma-v70-perception-runtime', 'soma-v72-hud-layout-runtime'})
        for key in ['soma-v32-patch', 'soma-v42-recovery', 'soma-v70-augmentations-core']:
            if key in before:
                self.assertEqual(before[key], after[key])
        self.assertEqual(set(after) - set(before), {'soma-v73-tactical-runtime'})
        self.assertEqual(self.patched.count(MARKER), 1)

    def test_real_owner_reuses_activation_and_produces_fresh_snapshots(self):
        owner = scripts(self.patched)['soma-v70-runtime']
        self.assertIn('function scan(){return root.__SOMA_TACTICAL73__?.scanTargets()||[];}', owner)
        self.assertIn('scanTargets:scan().map(v=>({...v}))', owner)
        # Activation/controller/save bridge and all keyboard bindings remain exact.
        before = scripts(self.parent)['soma-v70-runtime']
        for start, end in [('  function createController(', '  function wrapDamage('),
                           ('  function handleShortcut(', '  const API='),
                           ('  function setup(){', '  setup();')]:
            # setup differs only in the scan snapshot freshness expression.
            original = before[before.index(start):before.index(end, before.index(start))]
            original = original.replace('scanTargets:scanRows.map(v=>({...v}))', 'scanTargets:scan().map(v=>({...v}))')
            self.assertIn(original, owner)

    def test_duplicate_missing_anchor_and_script_injection_fail_closed(self):
        with self.assertRaises(ValueError):
            patch_html(self.patched, self.modules)
        with self.assertRaises(ValueError):
            patch_html(self.parent.replace('function loop(t){window.__SOMA_NETRUNNER72__?.maintain();', 'function otherLoop(t){'), self.modules)
        with self.assertRaises(ValueError):
            patch_html(self.parent.replace("'#trackedObjective','#v42-city-hud'", "'#trackedObjective','#unknown-panel'"), self.modules)
        for bad in ['', None, '</ScRiPt><script>alert(1)']:
            with self.assertRaises(ValueError):
                patch_html(self.parent, {'tactical-runtime': bad})


    def test_all_existing_hud_nodes_keep_one_owner_and_campaign_objective_joins_navigation(self):
        def groups(html):
            body = scripts(html)['soma-v72-hud-layout-runtime']
            block = body.split('const GROUPS=Object.freeze({', 1)[1].split('  });', 1)[0]
            return {name: re.findall(r"'([^']+)'", values) for name, values in re.findall(r'(\w+):\[([^\]]+)\]', block)}
        before, after = groups(self.parent), groups(self.patched)
        self.assertEqual(sorted(item for rows in before.values() for item in rows),
                         sorted(item for rows in after.values() for item in rows))
        self.assertIn('#v45-tracker', after['navigation'])
        self.assertNotIn('#v45-tracker', after['status'])
        self.assertEqual(sum(rows.count('#v45-tracker') for rows in after.values()), 1)
        self.assertEqual(len(after['status']), len(before['status']) - 1)

    def test_viewer_is_an_exact_passthrough(self):
        self.assertEqual(patch_viewer(self.parent, self.modules), self.parent)


if __name__ == '__main__':
    unittest.main()
