"""The source-side inspection fix must not alter rendered or routed geometry."""
import re
from pathlib import Path
import sys
import unittest

GAME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GAME))
from tools import v77_navigation as N


class NavigationPatchTests(unittest.TestCase):
    def setUp(self):
        self.core = (GAME / 'src/v77/navigation-core.js').read_text()
        self.inspector = (GAME / 'src/v72/road-inspector-core.js').read_text()
        self.html = ('<body><script id="viewer-metropole-viewer-core">geometry();</script>'
                     '<script id="viewer-road72-core">' + self.inspector + '</script>'
                     '<script id="viewer-source-router63">nativeRouter();</script></body>')

    def test_campaign_is_identical_and_does_not_require_an_inspection_owner(self):
        self.assertIs(N.patch_html(self.html, {}), self.html)

    def test_only_candidate_logic_changes_in_the_existing_inspection_owner(self):
        value = N.patch_inspector(self.inspector)
        start = self.inspector.index('  function candidate(')
        tail = self.inspector.index('  function boxHit(')
        self.assertEqual(value[:start], self.inspector[:start])
        self.assertEqual(value[value.index('  function boxHit('):], self.inspector[tail:])
        self.assertIn('__SOMA_NAVIGATION77_CORE__.candidate(source,point,kind)', value)

    def test_core_precedes_inspector_and_other_scripts_are_byte_identical(self):
        value = N.patch_viewer(self.html, {'navigation-core': self.core})
        self.assertLess(value.index('id="viewer-navigation77-core"'), value.index('id="viewer-road72-core"'))
        for identifier in ('viewer-metropole-viewer-core', 'viewer-source-router63'):
            pattern = '<script id="' + identifier + '">(.*?)</script>'
            self.assertEqual(re.search(pattern, value, re.S)[1], re.search(pattern, self.html, re.S)[1])

    def test_missing_ambiguous_and_duplicate_owners_are_refused(self):
        with self.assertRaises(ValueError):
            N.patch_inspector('missing')
        with self.assertRaises(ValueError):
            N.patch_inspector(self.inspector + self.inspector)
        with self.assertRaises(ValueError):
            N.patch_inspector(N.patch_inspector(self.inspector))
        with self.assertRaises(ValueError):
            N.patch_viewer(self.html + self.html, {'navigation-core': self.core})
        patched = N.patch_viewer(self.html, {'navigation-core': self.core})
        with self.assertRaises(ValueError):
            N.patch_viewer(patched, {'navigation-core': self.core})

    def test_missing_empty_or_script_closing_modules_are_refused(self):
        for scripts in ({}, {'navigation-core': None}, {'navigation-core': ''}, {'navigation-core': '</SCRIPT>'}):
            with self.subTest(scripts=scripts):
                with self.assertRaises(ValueError):
                    N.patch_viewer(self.html, scripts)


if __name__ == '__main__':
    unittest.main()
