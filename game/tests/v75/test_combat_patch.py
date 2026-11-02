import re
import sys
import unittest
from pathlib import Path

GAME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GAME))
from tools import v75_combat as P


class CombatPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parent = (GAME / 'SOMA_MASSILIA_URBAIN_v0_74.html').read_text()
        cls.scripts = {name: (GAME / f'src/v75/{name}.js').read_text() for name in P.MODULES}
        cls.output = P.patch_html(cls.parent, cls.scripts)

    def test_strict_anchors_and_modules(self):
        self.assertIn(P.MARKER, self.output)
        for invalid in ({}, {P.MODULES[0]: ''}, {P.MODULES[0]: '</ScRiPt>'}):
            with self.assertRaises(ValueError):
                P.patch_html(self.parent, invalid)
        with self.assertRaises(ValueError):
            P.patch_html(self.output, self.scripts)
        with self.assertRaises(ValueError):
            P.patch_html(self.parent.replace('q.charge>1.05', 'q.charge>1.06'), self.scripts)

    def test_damage_heal_and_neural_effect_owners_stay_exact(self):
        def script(text, identity):
            return re.search(r'<script\b[^>]*id="' + identity + r'"[^>]*>([\s\S]*?)</script>', text)[1]
        before, after = (script(text, 'soma-v32-patch') for text in (self.parent, self.output))
        for start, end in [('function v32DamagePlayer(', 'function enemyMove('),
                           (" else if(q.v32Role==='netrunner'){", " else if(q.v32Role==='medic'){"),
                           (" else if(q.v32Role==='medic'){", "\n else{const ideal=")]:
            self.assertEqual(before[before.index(start):before.index(end, before.index(start))],
                             after[after.index(start):after.index(end, after.index(start))])
        for identity in ['soma-v37-persistence', 'soma-v74-combat-support-runtime', 'soma-v42-recovery']:
            self.assertEqual(script(self.parent, identity), script(self.output, identity))

    def test_viewer_passes_through(self):
        self.assertEqual(P.patch_viewer('<viewer/>', self.scripts), '<viewer/>')


if __name__ == '__main__':
    unittest.main()
