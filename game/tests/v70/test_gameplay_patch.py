"""Strict transformations of the real frozen script edition, without a build."""
import hashlib
from pathlib import Path
import re
import sys
import unittest

GAME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GAME))
from tools.v70_gameplay import patch_gameplay


class GameplayPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = GAME / 'baseline/v66.html'
        if not cls.source.exists():
            raise unittest.SkipTest('Prepare the verified original payload before testing its real scripts.')
        cls.original_sha = hashlib.sha256(cls.source.read_bytes()).hexdigest()
        text = cls.source.read_text()
        cls.ids = ['soma-v32-patch', 'soma-v33-patch', 'soma-v42-recovery', 'soma-v43-production',
                   'soma-v62-runtime', 'soma-v64-group-runtime']
        cls.html = ''.join(re.search(r'<script\b[^>]*id="' + name + r'"[^>]*>[\s\S]*?</script>', text)[0]
                           for name in cls.ids)
        main = next(m[2] for m in re.finditer(r'<script\b([^>]*)>([\s\S]*?)</script>', text)
                    if 'function update(dt){move(dt);' in m[2])
        cls.html += '<script>' + main + '</script>'

    def test_all_real_script_edits_preserve_the_immutable_source(self):
        result = patch_gameplay(self.html)
        self.assertEqual(result.count('id="soma-v32-patch"'), 1)
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), self.original_sha)
        self.assertIn('perception: fixed emissions', result)
        self.assertIn('isChanneling:()=>!!v42Channel', result)
        self.assertNotIn('api(42)?.state()?.channel', result)

    def test_duplicate_missing_or_already_transformed_scripts_fail(self):
        for changed in (self.html + self.html, self.html.replace('soma-v32-patch', 'missing-module'),
                        patch_gameplay(self.html)):
            with self.subTest(size=len(changed)), self.assertRaises(ValueError):
                patch_gameplay(changed)

    def test_actual_gameplay_anchor_drift_is_never_accepted(self):
        for anchor in ('S.lastShotAt=performance.now()/1000;', 'function chooseCover(q,order,reserved){',
                       'isCrouched:v42Crouched,toggleCrouch:',
                       'kick=Math.min(.013,.0025+(Number(w?.damage)||20)/6500)',
                       'api(42)?.state()?.channel', 'function v26DamagePlayer(amount,label,source){',
                       'source.arrestCooldown=1.5;let dmg=amount;',
                       "let dmg=7*(typeof v27Stats==='function'?clamp(v27Stats().damageTakenMult,.35,1.75):1);"):
            with self.subTest(anchor=anchor), self.assertRaises(ValueError):
                patch_gameplay(self.html.replace(anchor, '/* required anchor changed */', 1))


if __name__ == '__main__':
    unittest.main()
