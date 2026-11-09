"""Strict native30 transformation and preservation of shared combat owners."""
import re
import sys
import unittest
from pathlib import Path

GAME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GAME))
from tools import v78_combat as P


def script(text, identity):
    return re.search(r'<script\b[^>]*id="' + identity + r'"[^>]*>([\s\S]*?)</script>', text)[1]


class CombatPatch78Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parent = (GAME / 'SOMA_MASSILIA_URBAIN_v0_77.html').read_text()
        cls.scripts = {name: (GAME / f'src/v78/{name}.js').read_text() for name in P.MODULES}
        cls.output = P.patch_html(cls.parent, cls.scripts)

    def test_sources_are_required_and_transform_is_single_and_strict(self):
        for invalid in ({}, {P.MODULES[0]: ''}, {P.MODULES[0]: '</ScRiPt>'}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                P.patch_html(self.parent, invalid)
        with self.assertRaises(ValueError):
            P.patch_html(self.output, self.scripts)
        for anchor in ['function clearJam(){\n', 'let materialJamTask=null;\n',
                       'materialJamTask={weapon:w,record:d,left:.9};',
                       'function loop(t){window.__SOMA_RELOAD77__?.maintain();']:
            for replacement in ['', anchor + anchor]:
                with self.subTest(anchor=anchor, replacement=replacement), self.assertRaises(ValueError):
                    P.patch_html(self.parent.replace(anchor, replacement), self.scripts)

    def test_native_timer_completion_wear_and_ammunition_transfer_stay_owned(self):
        native = ("task.left-=Math.min(.1,Math.max(0,Number(dt)||0));if(task.left>0)return;\n"
                  " materialJamTask=null;if(!task.record.jammed)return;task.record.jammed=false;"
                  "task.record.condition=Math.max(1,task.record.condition-.6);save();toast('Chambre dégagée');")
        self.assertIn(native, self.parent)
        self.assertIn(native, self.output)
        for prefix in ['reload=function(){if(v27IsCyber())',
                       'finishReload=function(){const id=v27ReloadWeaponId']:
            before = next(line for line in self.parent.splitlines() if line.startswith(prefix))
            after = next(line for line in self.output.splitlines() if line.startswith(prefix))
            self.assertEqual(before, after)
        self.assertIn('left:.9,core:state,scene:zone,zoneId:zone.id', self.output)
        self.assertNotIn('localStorage', self.scripts[P.MODULES[0]])
        self.assertNotIn('state.v78', self.scripts[P.MODULES[0]])

    def test_existing_combat_reload_and_perception_sources_are_preserved(self):
        for identity in ['soma-v32-patch', 'soma-v33-patch', 'soma-v70-perception-runtime',
                         'soma-v72-netrunner-runtime', 'soma-v74-combat-support-runtime',
                         'soma-v75-combat-telegraph-runtime', 'soma-v76-combat-heavy-runtime',
                         'soma-v77-combat-reload-runtime']:
            with self.subTest(identity=identity):
                self.assertEqual(script(self.parent, identity), script(self.output, identity))
        self.assertIn('function clearScene(){\n window.__SOMA_CHAMBER78__?.reset();\n window.__SOMA_RELOAD77__?.reset();',
                      script(self.output, 'soma-v37-persistence'))
        self.assertEqual(self.output.count(P.MARKER), 1)

    def test_viewer_has_no_chamber_state_or_changes(self):
        self.assertEqual(P.patch_viewer('<viewer/>', self.scripts), '<viewer/>')


if __name__ == '__main__':
    unittest.main()
