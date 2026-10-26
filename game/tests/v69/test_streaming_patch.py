"""Guard reconstruction changes against drift, duplication and source mutation."""
from pathlib import Path
import hashlib
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from v69_streaming import patch_streaming, patch_v52, patch_v53


class StreamingPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / 'baseline/v66.html'
        cls.raw = cls.path.read_bytes()
        cls.html = cls.raw.decode('utf-8')

    def script(self, name):
        match = re.search(r'<script\b[^>]*\bid="' + re.escape(name) + r'"[^>]*>(.*?)</script>', self.html, re.S)
        self.assertIsNotNone(match)
        return match[1]

    def test_complete_patch_preserves_source_files_and_data_blocks(self):
        result = patch_streaming(self.html)
        self.assertIn('transientIds:()=>[...TRANSIENT69.keys()]', result)
        self.assertIn('[EW][0-9]{2,4}-[NS][0-9]{2,4}', result)
        for name in ('soma-v53-embedded-pack', 'soma-v56-terrain', 'soma-v63-navigation'):
            marker = re.compile(r'(<script\b[^>]*\bid="' + name + r'"[^>]*>)(.*?)(</script>)', re.S)
            self.assertEqual(marker.search(self.html)[0], marker.search(result)[0])
        self.assertEqual(self.path.read_bytes(), self.raw)
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(), 'f1a6ce4b5957f634ff9fdbfaccfcf11c9e0d22159d01758dd56e29513581a014')

    def test_duplicate_patch_is_refused(self):
        with self.assertRaises(ValueError):
            patch_v53(patch_v53(self.script('soma-v53-core')))
        with self.assertRaises(ValueError):
            patch_v52(patch_v52(self.script('soma-v52-runtime')))

    def test_missing_and_duplicate_anchors_are_refused(self):
        v52 = self.script('soma-v52-runtime')
        with self.assertRaises(ValueError):
            patch_v52(v52.replace('function activeRecord(def)', 'function changed(def)'))
        with self.assertRaises(ValueError):
            patch_v52(v52 + "\nwindow.__SOMA_V52__={v54:")
        with self.assertRaises(ValueError):
            patch_streaming(self.html.replace('id="soma-v53-core"', 'id="removed-core"'))


if __name__ == '__main__':
    unittest.main()
