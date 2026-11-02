import importlib.util
from pathlib import Path
import unittest

GAME = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('architecture74', GAME / 'tools/v74_architecture.py')
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)
SCRIPTS = {name: (GAME / 'src/v74' / (name + '.js')).read_text() for name in PATCH.MODULES}


class ArchitecturePatch(unittest.TestCase):
    def test_rebuilt_parent_anchors_and_unique_scripts(self):
        for path, apply in [(GAME / 'metropole-viewer-v73.html', PATCH.patch_viewer),
                            (GAME / 'SOMA_MASSILIA_URBAIN_v0_73.html', PATCH.patch_html)]:
            if not path.exists():
                self.skipTest('Rebuilt v73 parent required.')
            original = path.read_text()
            output = apply(original, SCRIPTS)
            self.assertEqual(output.count('/* Two reviewed source roofs'), 1)
            self.assertIn('soma-roof-fidelity73-core' if 'SOMA_' in path.name else 'viewer-roof-fidelity73-core', output)
            with self.assertRaises(ValueError):
                apply(output, SCRIPTS)
            self.assertEqual(path.read_text(), original)

    def test_missing_parent_or_invalid_module_refused(self):
        with self.assertRaises(ValueError):
            PATCH.patch_viewer('', SCRIPTS)
        with self.assertRaises(ValueError):
            PATCH.patch_html('', {'architecture-datum-core': '</script>'})


if __name__ == '__main__':
    unittest.main()
