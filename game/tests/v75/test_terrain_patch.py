"""Transform the real frozen terrain owner and reproduce the source-only pack."""
from pathlib import Path
import json
import re
import sys
import tempfile
import unittest

GAME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GAME))
from tools.v75_terrain import MODULES, DATA_MODULES, MARKER, derive, patch_html, patch_viewer


class TerrainPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parent = (GAME/'SOMA_MASSILIA_URBAIN_v0_74.html').read_text()
        cls.modules = {name:(GAME/'src/v75'/(name+'.js')).read_text() for name in MODULES}
        cls.result = patch_html(cls.parent, cls.modules)

    def test_only_terrain_entry_and_activation_are_transformed(self):
        def scripts(h):
            return {m[1]:m[2] for m in re.finditer(r'<script\b[^>]*id="([^"]+)"[^>]*>([\s\S]*?)</script>',h)}
        before, after = scripts(self.parent), scripts(self.result)
        self.assertEqual({name for name in before if before[name] != after[name]}, {'soma-v56-terrain-runtime'})
        self.assertEqual(set(after)-set(before), {'soma-v75-'+name for name in MODULES})
        self.assertEqual(self.result.count(MARKER),1)
        self.assertNotIn('localStorage',self.modules['terrain-runtime'])
        self.assertEqual(patch_viewer('unchanged viewer',self.modules),'unchanged viewer')

    def test_duplicate_missing_and_unsafe_modules_refused(self):
        with self.assertRaises(ValueError):patch_html(self.result,self.modules)
        with self.assertRaises(ValueError):patch_html(self.parent.replace('pose={...pose,...safe};','pose=unreviewed;'),self.modules)
        for value in ['',None,'</ScRiPt>']:
            with self.assertRaises(ValueError):patch_html(self.parent,{**self.modules,'terrain-runtime':value})

    def test_reproducible_exact_node_derivation_when_native_cache_installed(self):
        manifest=Path('/workspace/massilia-geodata-generated/terrain-amp-native5m-2022/manifest.json')
        if not manifest.exists():self.skipTest('native AMP cache unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            proof=derive(manifest,GAME/'data/v69/world/manifest.json',Path(tmp))
            self.assertEqual(proof,json.loads((GAME/'data/v75/terrain-source.json').read_text()))
            for name in DATA_MODULES:self.assertEqual((Path(tmp)/'src/v75'/(name+'.js')).read_bytes(),(GAME/'src/v75'/(name+'.js')).read_bytes())


if __name__ == '__main__':unittest.main()
