import re
import sys
import unittest
from pathlib import Path

GAME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GAME))
from tools import v76_combat as P


def script(text, identity):
    return re.search(r'<script\b[^>]*id="' + identity + r'"[^>]*>([\s\S]*?)</script>', text)[1]


class CombatPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parent = (GAME / 'SOMA_MASSILIA_URBAIN_v0_75.html').read_text()
        cls.scripts = {name: (GAME / f'src/v76/{name}.js').read_text() for name in P.MODULES}
        cls.output = P.patch_html(cls.parent, cls.scripts)

    def test_strict_anchors_and_modules(self):
        self.assertIn(P.MARKER, self.output)
        for invalid in ({}, {P.MODULES[0]: ''}, {P.MODULES[0]: '</ScRiPt>'}):
            with self.assertRaises(ValueError):
                P.patch_html(self.parent, invalid)
        with self.assertRaises(ValueError):
            P.patch_html(self.output, self.scripts)
        with self.assertRaises(ValueError):
            P.patch_html(self.parent.replace("else{const ideal=q.v32Role==='heavy'?11", "else{const ideal=q.v32Role==='heavy'?12"), self.scripts)

    def test_existing_damage_heal_sniper_boss_and_neural_owners_stay_exact(self):
        before, after = (script(text, 'soma-v32-patch') for text in (self.parent, self.output))
        for start, end in [('function v32DamagePlayer(', 'function enemyMove('),
                           (" else if(q.v32Role==='sniper'){", " else if(q.v32Role==='netrunner'){"),
                           (" else if(q.v32Role==='netrunner'){", " else if(q.v32Role==='medic'){"),
                           (" else if(q.v32Role==='medic'){", "\n else{const ")]:
            self.assertEqual(before[before.index(start):before.index(end, before.index(start))],
                             after[after.index(start):after.index(end, after.index(start))])
        for identity in ['soma-v37-persistence', 'soma-v74-combat-support-runtime', 'soma-v42-recovery',
                         'soma-v75-combat-telegraph-runtime', 'soma-v36-bosses', 'soma-v61-sight-runtime', 'soma-v61-sight-core']:
            self.assertEqual(script(self.parent, identity), script(self.output, identity))
        self.assertIn('if(window.__SOMA_COMBAT75__?.isPreparing(q)||window.__SOMA_COMBAT76__?.isPreparing(q))', script(self.output, 'soma-v33-patch'))

    def test_real_consumable_owner_and_all_its_side_effects_stay_exact(self):
        start, end = 'function v28UseConsumable(', 'function v28Rest()'
        before, after = (text[text.index(start):text.index(end, text.index(start))] for text in (self.parent, self.output))
        self.assertEqual(before, after)
        self.assertIn("if(root.__SOMA_COMBAT76__?.isObscured(q))return'blocked';", script(self.output, 'soma-v70-perception-runtime'))
        self.assertIn("if(kind==='robot'&&root.__SOMA_COMBAT76__?.isObscured(q))return 'blocked';", script(self.output, 'soma-v71-legacy-perception-runtime'))

    def test_viewer_passes_through(self):
        self.assertEqual(P.patch_viewer('<viewer/>', self.scripts), '<viewer/>')


if __name__ == '__main__':
    unittest.main()
