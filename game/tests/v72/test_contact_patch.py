"""Strict derived transforms of the actual v70/v71 scripts, never parent edits."""
from pathlib import Path
import re
import sys
import unittest

GAME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GAME))
from tools.v70_gameplay import patch_gameplay
from tools.v71_legacy_perception import patch_html as legacy
from tools.v72_contact_sharing import MODULES, MARKER, patch_html


class ContactPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (GAME / 'baseline/v66.html').read_bytes()
        html = patch_gameplay(cls.original.decode())
        for name in ('perception-runtime', 'runtime'):
            html = html.replace('</body>', '<script id="soma-v70-' + name + '">' +
                (GAME / ('src/v70/' + name + '.js')).read_text() + '</script></body>')
        cls.parent = legacy(html, {'legacy-perception-runtime':
            (GAME / 'src/v71/legacy-perception-runtime.js').read_text()})
        cls.scripts = {name: (GAME / ('src/v72/' + name + '.js')).read_text() for name in MODULES}

    def test_only_owned_derived_adapters_change_and_module_is_after_kernel(self):
        html = patch_html(self.parent, self.scripts)
        self.assertEqual(html.count(MARKER), 1)
        self.assertLess(html.index('id="soma-v71-legacy-perception-runtime"'), html.index('id="soma-v72-contact-sharing-runtime"'))
        self.assertIn("exchange('tactical',next,entities)", html)
        self.assertIn("exchange('legacy',next,entities)", html)
        self.assertNotIn('const shared=contacts.at(-1)', html)
        self.assertNotIn("reportContact(q.id,{x:camera.x,z:camera.z},'camera');for", html)
        for name in ('soma-v32-patch', 'soma-v33-patch', 'soma-v35-body'):
            pattern = r'<script\b[^>]*id="' + name + r'"[^>]*>[\s\S]*?</script>'
            self.assertEqual(re.search(pattern, self.parent)[0], re.search(pattern, html)[0])
        self.assertEqual((GAME / 'baseline/v66.html').read_bytes(), self.original)

    def test_missing_or_duplicated_anchors_fail_closed(self):
        for anchor in ("memory=next.state;hud=next.hud;", "memory=next.state;output=new Map(next.observers.map(row=>[row.id,row]));",
                       "  function reportContact(sourceId,position,kind='camera'){", "root.__SOMA_LEGACY_PERCEPTION71__?.reset?.();",
                       "window.__SOMA_PERCEPTION70__?.reportContact(q.id,{x:camera.x,z:camera.z},'camera');for"):
            with self.subTest(anchor=anchor), self.assertRaises(ValueError):
                patch_html(self.parent.replace(anchor, ''), self.scripts)
            with self.subTest(duplicate=anchor), self.assertRaises(ValueError):
                patch_html(self.parent.replace(anchor, anchor + anchor), self.scripts)

    def test_repeated_patch_and_script_terminators_fail(self):
        html = patch_html(self.parent, self.scripts)
        with self.assertRaises(ValueError):
            patch_html(html, self.scripts)
        with self.assertRaises(ValueError):
            patch_html(self.parent, {'contact-sharing-runtime': '</ScRiPt>'})


if __name__ == '__main__':
    unittest.main()
