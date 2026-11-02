"""The v73 roof extension preserves every byte of both frozen parent HTMLs."""
from pathlib import Path
import re
import sys
import unittest

GAME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GAME))
from tools import v73_fidelity as P


class RoofPatch73Tests(unittest.TestCase):
    def test_true_parents_only_gain_one_dependency_ordered_script(self):
        scripts = {name: (GAME / 'src/v73' / (name + '.js')).read_text() for name in P.MODULES}
        for filename, patch, parent, identifier in [
            ('SOMA_MASSILIA_URBAIN_v0_72.html', P.patch_html, 'soma-v69-roof-core', 'soma-roof-fidelity73-core'),
            ('metropole-viewer-v72.html', P.patch_viewer, 'viewer-roof-core', 'viewer-roof-fidelity73-core')]:
            html = (GAME / filename).read_text()
            out = patch(html, scripts)
            self.assertEqual(out.count('id="' + identifier + '"'), 1)
            self.assertLess(out.index('id="' + parent + '"'), out.index('id="' + identifier + '"'))
            self.assertEqual(re.sub(r'\n<script id="' + identifier + r'">[\s\S]*?</script>', '', out), html)
            with self.assertRaises(ValueError):
                patch(out, scripts)
            for bad in ['', '</ScRiPt>', None]:
                with self.assertRaises(ValueError):
                    patch(html, {P.MODULES[0]: bad})
            for broken in [html.replace('id="' + parent + '"', 'id="absent"'), html + '<script id="' + parent + '">x</script>']:
                with self.assertRaises(ValueError):
                    patch(broken, scripts)


if __name__ == '__main__':
    unittest.main()
