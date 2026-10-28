"""Exercise the actual parent scripts and strict derived-document anchors."""
from pathlib import Path
import hashlib
import re
import sys
import unittest

GAME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GAME))
from tools.v70_gameplay import patch_gameplay
from tools.v71_legacy_perception import MODULES, MARKER, patch_html


class LegacyPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (GAME / 'baseline/v66.html').read_bytes()
        cls.parent = patch_gameplay(cls.original.decode())
        for name in ('perception-runtime', 'runtime'):
            text = (GAME / f'src/v70/{name}.js').read_text()
            cls.parent = cls.parent.replace('</body>', f'<script id="soma-v70-{name}">{text}</script></body>')
        cls.scripts = {name: (GAME / f'src/v71/{name}.js').read_text() for name in MODULES}

    def test_actual_main_owners_relay_and_frozen_sources_preserved(self):
        html = patch_html(self.parent, self.scripts)
        self.assertEqual(html.count(MARKER), 1)
        self.assertEqual(html.count('id="soma-v71-legacy-perception-runtime"'), 1)
        self.assertLess(html.index('id="soma-v70-runtime"'), html.index('id="soma-v71-legacy-perception-runtime"'))
        self.assertIn('reportNoise?.(pending[pending.length-1])', html)
        self.assertIn('reset();activeZone=zoneNow();root.__SOMA_LEGACY_PERCEPTION71__?.reset?.();', html)
        self.assertIn('const v26BaseUpdateAI=updateAI;', html)
        for name in ('soma-v32-patch', 'soma-v33-patch', 'soma-v35-body', 'soma-v42-recovery'):
            pattern = r'<script\b[^>]*id="' + name + r'"[^>]*>[\s\S]*?</script>'
            self.assertEqual(re.search(pattern, self.parent)[0], re.search(pattern, html)[0], name)
        self.assertEqual(hashlib.sha256((GAME / 'baseline/v66.html').read_bytes()).digest(), hashlib.sha256(self.original).digest())

    def test_missing_duplicate_or_modified_ai_anchors_fail(self):
        for old in ('function updateAI(dt){', 'targetX:camera.x,targetZ:camera.z',
                    'if(chasing&&dist<9&&!lineBlocked(',
                    "n=>n.police&&Math.hypot(n.x-camera.x,n.z-camera.z)<4&&!lineBlocked(n.x,n.z,camera.x,camera.z)",
                    'snapshotHUD,snapshot,reset:()=>{reset();activeZone=zoneNow();}'):
            with self.subTest(anchor=old), self.assertRaises(ValueError):
                patch_html(self.parent.replace(old, ''), self.scripts)
        with self.assertRaises(ValueError):
            patch_html(self.parent.replace('function updateAI(dt){', 'function updateAI(dt){function updateAI(dt){'), self.scripts)

    def test_repeated_patch_and_script_terminators_fail(self):
        html = patch_html(self.parent, self.scripts)
        with self.assertRaises(ValueError):
            patch_html(html, self.scripts)
        with self.assertRaises(ValueError):
            patch_html(self.parent, {'legacy-perception-runtime': '/* </ScRiPt > */'})


if __name__ == '__main__':
    unittest.main()
