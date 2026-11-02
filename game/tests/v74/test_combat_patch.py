"""Derived v74 hooks must preserve the historical effects and frozen sources."""
from pathlib import Path
import hashlib
import re
import sys
import unittest

GAME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GAME))
from tools import v74_combat as P


def script(html, name):
    return re.search(r'<script\b[^>]*id="' + name + r'"[^>]*>([\s\S]*?)</script>', html)[1]


class CombatPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (GAME / 'SOMA_MASSILIA_URBAIN_v0_73.html').read_bytes()
        cls.parent = cls.original.decode()
        cls.scripts = {name: (GAME / f'src/v74/{name}.js').read_text() for name in P.MODULES}

    def test_real_heal_and_all_damage_owners_unchanged(self):
        html = P.patch_html(self.parent, self.scripts)
        self.assertEqual(html.count(P.MARKER), 1)
        self.assertEqual(html.count('id="soma-v74-combat-support-runtime"'), 1)
        effect = 'ally.health=Math.min(ally.maxHealth,ally.health+18);q.attackClock=3.2'
        old, new = script(self.parent, 'soma-v32-patch'), script(html, 'soma-v32-patch')
        self.assertEqual(new.count(effect), 1)
        for name in ('soma-v35-body', 'soma-v42-recovery', 'soma-v70-runtime', 'soma-v72-netrunner-runtime'):
            self.assertEqual(script(html, name), script(self.parent, name), name)
        self.assertEqual(script(html, 'soma-v33-patch'), P.patch_v33(script(self.parent, 'soma-v33-patch')))
        self.assertEqual(script(html, 'soma-v37-persistence'), P.patch_persistence(script(self.parent, 'soma-v37-persistence')))
        for start, end in [('function v32DamagePlayer(', '\nfunction enemyMove('),
                           ("if(q.v32Role==='blade'){", " else if(q.v32Role==='medic'){"),
                           ("\n else{const ideal=q.v32Role==='heavy'?", '\nlet snapshotClock=0;')]:
            self.assertEqual(old[old.index(start):old.index(end, old.index(start))],
                             new[new.index(start):new.index(end, new.index(start))])
        self.assertEqual(hashlib.sha256((GAME / 'SOMA_MASSILIA_URBAIN_v0_73.html').read_bytes()).digest(), hashlib.sha256(self.original).digest())
        self.assertEqual(P.patch_viewer('unchanged viewer', self.scripts), 'unchanged viewer')

    def test_missing_duplicate_drifted_anchors_fail_closed(self):
        for anchor in (" else if(q.v32Role==='medic'){", "\n else{const ideal=q.v32Role==='heavy'?",
                       'window.__SOMA_NETRUNNER72__?.beginEnemyFrame();',
                       "if(q.state==='combat'){",
                       'function loop(t){window.__SOMA_NETRUNNER72__?.maintain();',
                       'root.__SOMA_TACTICAL73__?.reset?.();', 'const role=q.v26BossId?',
                       'const rec=zoneCombatState(zoneId).enemies[q.id];if(!rec)return;',
                       'v34BaseArmor:q.v34BaseArmor};st.lastSeen=Date.now();save32()',
                       'out.health=Math.max(0,finite(out.health));\n  return out;',
                       "number(e.health,0,1e7,'Santé ennemie');",
                       "['Signal local','Observez ses déplacements.']);", '</body>'):
            for changed in ('', anchor + anchor):
                with self.subTest(anchor=anchor, duplicate=bool(changed)), self.assertRaises(ValueError):
                    P.patch_html(self.parent.replace(anchor, changed), self.scripts)

    def test_repeat_and_invalid_module_rejected(self):
        html = P.patch_html(self.parent, self.scripts)
        with self.assertRaises(ValueError):
            P.patch_html(html, self.scripts)
        for value in (None, '', '/* </ScRiPt > */'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                P.patch_html(self.parent, {'combat-support-runtime': value})


if __name__ == '__main__':
    unittest.main()
