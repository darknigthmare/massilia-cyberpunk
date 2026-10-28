"""Strict derived hooks on the actual delivered parent; no source mutation."""
from pathlib import Path
import hashlib
import re
import sys
import unittest

GAME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GAME))
from tools import v72_netrunner as P


def script(html, name):
    return re.search(r'<script\b[^>]*id="' + name + r'"[^>]*>([\s\S]*?)</script>', html)[1]


class NetrunnerPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (GAME / 'SOMA_MASSILIA_URBAIN_v0_71.html').read_bytes()
        cls.parent = cls.original.decode()
        cls.scripts = {name: (GAME / f'src/v72/{name}.js').read_text() for name in P.MODULES}

    def test_original_neural_effect_and_all_other_attack_owners_preserved(self):
        html = P.patch_html(self.parent, self.scripts)
        self.assertEqual(html.count(P.MARKER), 1)
        self.assertEqual(html.count('id="soma-v72-netrunner-runtime"'), 1)
        effect = "state.tension=clamp(state.tension+9,0,100);S.status.jammed=2.8;announce('INTRUSION NEURALE · arme perturbée',2);q.attackClock=a.cooldown/Math.max(.1,q.v33AttackFactor??1)"
        self.assertEqual(script(html, 'soma-v32-patch').count(effect), 1)
        for name in ('soma-v33-patch', 'soma-v35-body', 'soma-v42-recovery', 'soma-v70-runtime'):
            self.assertEqual(script(html, name), script(self.parent, name), name)
        old = script(self.parent, 'soma-v32-patch')
        new = script(html, 'soma-v32-patch')
        for start, end in [("if(q.v32Role==='blade'){", " else if(q.v32Role==='netrunner'){"),
                           (" else if(q.v32Role==='medic'){", " }else if(q.state==='patrol'||q.state==='search'){"),
                           ('const baseShoot=shoot;', 'const baseLootDynamicGeo=')]:
            self.assertEqual(old[old.index(start):old.index(end, old.index(start))],
                             new[new.index(start):new.index(end, new.index(start))])
        self.assertEqual(hashlib.sha256((GAME / 'SOMA_MASSILIA_URBAIN_v0_71.html').read_bytes()).digest(), hashlib.sha256(self.original).digest())

    def test_missing_duplicate_or_drifted_anchors_fail_closed(self):
        for anchor in (" else if(q.v32Role==='netrunner'){", " else if(q.v32Role==='medic'){",
                       'function v32UpdateEnemies(dt){if(!zone)return;window.__SOMA_PERCEPTION70__?.beginEnemyFrame(dt);',
                       'function loop(t){\n const P=window.__SOMA_PERF65__,',
                       'root.__SOMA_LEGACY_PERCEPTION71__?.reset?.();', '</body>'):
            for changed in ('', anchor + anchor):
                with self.subTest(anchor=anchor, duplicate=bool(changed)), self.assertRaises(ValueError):
                    P.patch_html(self.parent.replace(anchor, changed), self.scripts)

    def test_repetition_and_invalid_modules_rejected_before_mutation(self):
        html = P.patch_html(self.parent, self.scripts)
        with self.assertRaises(ValueError):
            P.patch_html(html, self.scripts)
        for value in (None, '', '/* </ScRiPt > */'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                P.patch_html(self.parent, {'netrunner-runtime': value})

    def test_radio_order_remains_composable_at_public_reset_anchor(self):
        # Radio extends the same public reset; the netrunner hook keeps it.
        parent = self.parent.replace('root.__SOMA_LEGACY_PERCEPTION71__?.reset?.();',
            'root.__SOMA_LEGACY_PERCEPTION71__?.reset?.();root.__SOMA_CONTACT_SHARING72__?.reset?.();')
        html = P.patch_html(parent, self.scripts)
        self.assertIn('root.__SOMA_LEGACY_PERCEPTION71__?.reset?.();root.__SOMA_NETRUNNER72__?.reset?.();root.__SOMA_CONTACT_SHARING72__?.reset?.();', html)


if __name__ == '__main__':
    unittest.main()
