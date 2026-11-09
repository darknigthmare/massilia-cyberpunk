"""Strict source transformation and preservation of ammunition/damage owners."""
import re
import sys
import unittest
from pathlib import Path

GAME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GAME))
from tools import v77_combat as P


def script(text, identity):
    return re.search(r'<script\b[^>]*id="' + identity + r'"[^>]*>([\s\S]*?)</script>', text)[1]


class CombatPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parent = (GAME / 'SOMA_MASSILIA_URBAIN_v0_76.html').read_text()
        cls.scripts = {name: (GAME / f'src/v77/{name}.js').read_text() for name in P.MODULES}
        cls.output = P.patch_html(cls.parent, cls.scripts)

    def test_strict_sources_and_single_application(self):
        for invalid in ({}, {P.MODULES[0]: ''}, {P.MODULES[0]: '</ScRiPt>'}):
            with self.assertRaises(ValueError):
                P.patch_html(self.parent, invalid)
        with self.assertRaises(ValueError):
            P.patch_html(self.output, self.scripts)
        with self.assertRaises(ValueError):
            P.patch_html(self.parent.replace('state.weapon=n;announce(WEAPONS[n].name)', 'state.weapon=n;changed()'), self.scripts)

    def test_native_ammunition_transfer_and_weapon_definitions_remain_exact(self):
        for start in ['reload=function(){if(v27IsCyber())', 'finishReload=function(){const id=v27ReloadWeaponId']:
            before = next(line for line in self.parent.splitlines() if line.startswith(start))
            after = next(line for line in self.output.splitlines() if line.startswith(start))
            self.assertEqual(before, after)
        start, end = 'const WEAPONS=', '].map(w=>({...w,c:C.hex(w.col)}));'
        def definitions(text):
            a = text.index(start)
            return text[a:text.index(end, a) + len(end)]
        self.assertEqual(definitions(self.parent), definitions(self.output))

    def test_combat_perception_and_existing_actions_preserved(self):
        for identity in ['soma-v32-patch', 'soma-v33-patch', 'soma-v70-perception-runtime',
                         'soma-v72-netrunner-runtime', 'soma-v74-combat-support-runtime',
                         'soma-v75-combat-telegraph-runtime', 'soma-v76-combat-heavy-runtime']:
            self.assertEqual(script(self.parent, identity), script(self.output, identity))
        self.assertIn('function clearScene(){\n window.__SOMA_RELOAD77__?.reset();', script(self.output, 'soma-v37-persistence'))

    def test_viewer_unchanged(self):
        self.assertEqual(P.patch_viewer('<viewer/>', self.scripts), '<viewer/>')


if __name__ == '__main__':
    unittest.main()
