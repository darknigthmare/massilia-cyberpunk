"""Guard authored mission patch boundaries, frozen parents and strict assembly."""
from pathlib import Path
import hashlib
import re
import sys
import unittest

GAME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GAME))
from build_v68 import rewrite_script
from tools import v78_missions as M


class Missions78PatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = GAME / 'SOMA_MASSILIA_URBAIN_v0_77.html'
        cls.parent = cls.path.read_text(encoding='utf-8')
        cls.parent_sha = hashlib.sha256(cls.path.read_bytes()).hexdigest()
        cls.scripts = {name: (GAME / 'src/v78' / (name + '.js')).read_text(encoding='utf-8')
                       for name in M.MODULES}

    def test_only_the_existing_city_owner_changes_and_parent_file_is_untouched(self):
        output = M.patch_html(self.parent, self.scripts)
        old_body = re.search(r'<script\b[^>]*id="soma-v45-city"[^>]*>([\s\S]*?)</script>', self.parent)[1]
        recovered = rewrite_script(output, 'soma-v45-city', lambda _: old_body)
        self.assertEqual(recovered, self.parent)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), self.parent_sha)
        self.assertEqual(output.count(M.MARKER), 1)
        self.assertIn("const V45_RACE_TARGETS={port:'corniche-exterior'", output)

    def test_missing_repeated_wrong_parent_and_unsafe_modules_refuse(self):
        output = M.patch_html(self.parent, self.scripts)
        with self.assertRaises(ValueError):
            M.patch_html(output, self.scripts)
        for scripts in ({}, {M.MODULES[0]: ''}, {M.MODULES[0]: '</SCRIPT>'}):
            with self.subTest(scripts=scripts), self.assertRaises(ValueError):
                M.patch_html(self.parent, scripts)
        for replacement in ('', 'id="soma-v77-edition" id="soma-v77-edition"'):
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                M.patch_html(self.parent.replace('id="soma-v77-edition"', replacement), self.scripts)
        anchor = "const V45_RACE_TARGETS={port:'corniche-route'"
        for replacement in ('const V45_RACE_TARGETS={port:\'unknown\'', anchor + anchor):
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                M.patch_html(self.parent.replace(anchor, replacement), self.scripts)

    def test_viewer_is_identical_and_runtime_adds_no_storage_or_scene_owner(self):
        original = '<!doctype html><body>independent viewer</body>'
        self.assertEqual(M.patch_viewer(original, self.scripts), original)
        runtime = self.scripts[M.MODULES[0]]
        for forbidden in ('localStorage', 'sessionStorage', 'core.v78', 'WORLD.links=', 'enterZone='):
            self.assertNotIn(forbidden, runtime)


if __name__ == '__main__':
    unittest.main()
