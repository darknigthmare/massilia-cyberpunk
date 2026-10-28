"""Verify publication, source-only reconstruction and the actual derived viewer."""
from pathlib import Path
from unittest import mock
import json
import re
import subprocess
import sys
import tempfile
import unittest

GAME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GAME))
from tools import build_metropole_viewer_v71 as M


class Viewer71PublicationTests(unittest.TestCase):
    def test_source_only_reconstruction_uses_and_removes_a_temporary_parent(self):
        source, viewer = b'verified reconstructed parent69', b'verified viewer70'
        seen = []
        def derive(path, expected_sha):
            path = Path(path)
            self.assertTrue(path.is_file())
            self.assertEqual(path.read_bytes(), source)
            self.assertEqual(expected_sha, M.B71.digest(source))
            seen.append(path)
            return viewer
        with tempfile.TemporaryDirectory() as temporary:
            missing = Path(temporary) / 'parent69.html'
            with mock.patch.object(M.V70.V69, 'SOURCE', missing), \
                 mock.patch.object(M.B71.B70, 'build_v69', return_value=source), \
                 mock.patch.object(M, 'SOURCE_PARENT_SHA256', M.B71.digest(source)), \
                 mock.patch.object(M, 'PARENT_SHA256', M.B71.digest(viewer)), \
                 mock.patch.object(M.V70, 'build', side_effect=derive):
                self.assertEqual(M.parent_viewer(), viewer)
            self.assertFalse(missing.exists())
            self.assertEqual(len(seen), 1)
            self.assertFalse(seen[0].exists())

    def test_missing_explicit_source_is_not_silently_replaced(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'missing.html'
            with mock.patch.object(M.B71.B70, 'build_v69') as reconstruct:
                with self.assertRaises(OSError):
                    M.parent_viewer(path)
                reconstruct.assert_not_called()

    def test_parent_and_source_sha_drift_are_refused(self):
        with self.assertRaisesRegex(ValueError, 'SHA256'):
            M.parent_viewer(expected_sha='0' * 64)
        with mock.patch.object(M.V70, 'build', return_value=b'changed viewer70'):
            with self.assertRaisesRegex(ValueError, 'parent 0.70'):
                M.parent_viewer(M.V70.V69.SOURCE)
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.object(M.V70.V69, 'SOURCE', Path(temporary) / 'missing.html'), \
                 mock.patch.object(M.B71.B70, 'build_v69', return_value=b'changed parent69'), \
                 mock.patch.object(M.V70, 'build') as derive:
                with self.assertRaisesRegex(ValueError, 'source 0.69'):
                    M.parent_viewer()
                derive.assert_not_called()

    def test_failed_temporary_parent_build_is_cleaned(self):
        source = b'reconstructed69'
        seen = []
        def fail(path, _checksum):
            seen.append(Path(path))
            raise ValueError('parent viewer drift')
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.object(M.V70.V69, 'SOURCE', Path(temporary) / 'missing.html'), \
                 mock.patch.object(M.B71.B70, 'build_v69', return_value=source), \
                 mock.patch.object(M, 'SOURCE_PARENT_SHA256', M.B71.digest(source)), \
                 mock.patch.object(M.V70, 'build', side_effect=fail):
                with self.assertRaisesRegex(ValueError, 'drift'):
                    M.parent_viewer()
        self.assertEqual(len(seen), 1)
        self.assertFalse(seen[0].exists())

    def test_source_snapshot_drift_prevents_publication(self):
        before = {'parentInputs': {'originals': {str(i): {} for i in range(27)}}}
        with mock.patch.object(M.B71, 'inputs', side_effect=[before, {**before, 'drift': True}]), \
             mock.patch.object(M, 'parent_viewer', return_value=b'parent70'), \
             mock.patch.object(M.B71, 'source_scripts', return_value={}), \
             mock.patch.object(M, 'patch_html', return_value='derived viewer'):
            with self.assertRaisesRegex(ValueError, 'entrée a changé'):
                M.build_release()

    def test_repeated_prepare_and_verify_check_html_and_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output, report_path = root / 'viewer71.html', root / 'data/v71/VIEWER_BUILD_REPORT.json'
            parent = root / 'viewer70.html'
            parent.write_bytes(b'preserved viewer70')
            content = b'derived viewer71'
            report = {'version': '0.71.0', 'output': output.name, 'sha256': M.B71.digest(content)}
            with mock.patch.object(M.B71, 'ROOT', root), mock.patch.object(M, 'OUTPUT', output), \
                 mock.patch.object(M, 'REPORT', report_path), \
                 mock.patch.object(M, 'build_release', return_value=(content, report)):
                M.prepare()
                first = output.read_bytes(), report_path.read_bytes()
                M.prepare()
                self.assertEqual(first, (output.read_bytes(), report_path.read_bytes()))
                self.assertEqual(json.loads(report_path.read_text()), report)
                M.prepare(verify=True)
                output.write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError, 'survol 0.71'):
                    M.prepare(verify=True)
                output.write_bytes(content)
                report_path.write_bytes(b'{}')
                with self.assertRaisesRegex(ValueError, 'rapport du survol'):
                    M.prepare(verify=True)
                self.assertEqual(parent.read_bytes(), b'preserved viewer70')


class Viewer71RealParentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parent = GAME / 'metropole-viewer-v70.html'
        if not parent.is_file():
            raise unittest.SkipTest('Generated v70 viewer absent; source-only reconstruction is tested separately.')
        raw = parent.read_bytes()
        if M.B71.digest(raw) != M.PARENT_SHA256:
            raise AssertionError('The real v70 viewer does not match its pinned SHA256.')
        cls.original = raw.decode('utf-8')
        scripts = {name: (GAME / f'src/v71/{name}.js').read_text(encoding='utf-8')
                   for name in M.B71.module_names()}
        cls.output = M.patch_html(cls.original, scripts)
        cls.controller = M.V70.V69.script(cls.output, 'viewer-metropole-viewer')

    def test_metadata_return_link_and_runtime_use_edition71(self):
        data = json.loads(M.V70.V69.script(self.output, 'soma-viewer-data', json_only=True))
        self.assertEqual(data['version'], '0.71.0')
        self.assertEqual(data['returnToGame'], 'SOMA_MASSILIA_URBAIN_v0_71.html')
        self.assertEqual(data['parentViewer70SHA256'], M.PARENT_SHA256)
        self.assertEqual(data['newGeographicCells'], 0)
        self.assertFalse(data['newPersistenceDomain'])
        self.assertIn('SURVOL MÉTROPOLITAIN · 0.71', self.output)
        self.assertIn('href="SOMA_MASSILIA_URBAIN_v0_71.html"', self.output)
        self.assertNotIn('href="SOMA_MASSILIA_URBAIN_v0_70.html"', self.output)
        self.assertIn("version:'0.71.0',worldIndex:", self.controller)

    def test_geographic_and_router_cores_remain_exact_and_campaign_stays_out(self):
        for identifier in ('viewer-geographic-core', 'viewer-terrain-core', 'viewer-dimension-core',
                           'viewer-architecture-core', 'viewer-roof-core', 'viewer-streaming-core',
                           'viewer-world-index70', 'viewer-source-router63'):
            self.assertEqual(M.V70.V69.script(self.output, identifier),
                             M.V70.V69.script(self.original, identifier), identifier)
        router = M.V70.V69.script(self.output, 'viewer-source-router63')
        self.assertEqual(M.B71.digest(router.encode()), M.V70.CORE_SHA256)
        for text in ('soma-v37-persistence', 'localStorage.', 'sessionStorage.', '<script src='):
            self.assertNotIn(text, self.output)

    def test_all_derived_scripts_parse_and_have_unique_ids(self):
        scripts = re.findall(r'<script\b([^>]*)>([\s\S]*?)</script>', self.output)
        ids = []
        for attributes, source in scripts:
            identifier = re.search(r'\bid="([^"]+)"', attributes)
            self.assertIsNotNone(identifier)
            ids.append(identifier[1])
            if 'application/json' in attributes:
                json.loads(source)
                continue
            checked = subprocess.run(['node', '--check'], input=source, text=True, capture_output=True)
            self.assertEqual(checked.returncode, 0, identifier[1] + ': ' + checked.stderr)
        self.assertEqual(len(ids), len(set(ids)))

    def test_double_application_and_changed_edition_anchors_are_refused(self):
        with self.assertRaises(ValueError):
            M.patch_edition(self.output)
        anchor = 'SURVOL MÉTROPOLITAIN · 0.70'
        for replacement in ('', anchor + anchor):
            with self.assertRaises(ValueError):
                M.patch_edition(self.original.replace(anchor, replacement))


if __name__ == '__main__':
    unittest.main()
