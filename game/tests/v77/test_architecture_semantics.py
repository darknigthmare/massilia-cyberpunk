import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

GAME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GAME))
from tools import v77_architecture as A


class ArchitectureSemantics(unittest.TestCase):
    def setUp(self):
        self.original = '<html><body><script>'+ (GAME/'src/v76/architecture-conflicts-runtime.js').read_text()+'</script></body></html>'
        self.scripts = {name: 'window.'+name.replace('-', '_')+'=true;' for name in A.MODULES}

    def test_patch_changes_terminology_and_delegates_details_only(self):
        built = A.patch_html(self.original, self.scripts)
        self.assertIn('root.__SOMA_ARCHITECTURE77__?.paragraphs(row)', built)
        self.assertIn('Sol minimal + hauteur NGF (calcul)', built)
        self.assertNotIn('égout de référence :', built)
        self.assertIn("refres", built)
        # Native identity binding and cell-selection calls remain in place.
        for value in ('sourceBound(row.id)', 'selectCell(row.id)', 'nativeFootprintMax', 'terrainAboveEave'):
            self.assertIn(value, built)
        for name in A.MODULES:
            self.assertEqual(built.count('id="soma-v77-'+name+'"'), 1)
        self.assertEqual(A.patch_viewer(self.original, self.scripts), self.original)

    def test_patch_refuses_duplicate_application_missing_owner_or_bad_scripts(self):
        with self.assertRaises(ValueError):
            A.patch_html(A.patch_html(self.original, self.scripts), self.scripts)
        with self.assertRaises(ValueError):
            A.patch_html('<html><body></body></html>', self.scripts)
        with self.assertRaises(ValueError):
            A.patch_html(self.original, {})
        self.scripts[A.MODULES[0]] = '</script>'
        with self.assertRaises(ValueError):
            A.patch_html(self.original, self.scripts)

    def test_provenance_binds_parent_and_official_definitions(self):
        raw = (GAME/'data/v76/architecture-conflicts.json').read_bytes()
        data = json.loads((GAME/'data/v77/architecture-semantics.json').read_bytes())
        self.assertEqual(data['provenance']['parentCatalogueSHA256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(data['provenance']['document']['sha256'], A.DOCUMENT_SHA256)
        self.assertEqual(data['provenance']['document']['printedPages'], [68, 76, 77, 78])
        self.assertFalse(data['geometryChanged'])
        self.assertFalse(data['referenceChanged'])
        self.assertFalse(data['cohortChanged'])

    def test_source_verification_rejects_changed_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)/'source.json'
            source.write_bytes(b'{"field":null}')
            expected = A.sha(source.read_bytes())
            self.assertEqual(A.verified(source, expected), b'{"field":null}')
            source.write_bytes(b'{"field":0}')
            with self.assertRaisesRegex(ValueError, 'Source différente'):
                A.verified(source, expected)


if __name__ == '__main__':
    unittest.main()
