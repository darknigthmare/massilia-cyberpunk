"""Verify source-only derivation, publication and the actual v74 viewer contract."""
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
from tools import build_metropole_viewer_v75 as M


class Viewer75PublicationTests(unittest.TestCase):
    def test_parent_derivation_delegates_without_publishing_any_parent(self):
        parent = b'verified reconstructed viewer74'
        with mock.patch.object(M.V74, 'build', return_value=parent) as build, \
             mock.patch.object(M.V74, 'prepare', side_effect=AssertionError('No parent publication')), \
             mock.patch.object(M, 'PARENT_SHA256', M.B75.digest(parent)):
            self.assertEqual(M.parent_viewer(), parent)
            build.assert_called_once_with(None, M.SOURCE_PARENT_SHA256)

    def test_missing_explicit_source_is_not_silently_replaced(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'missing.html'
            with mock.patch.object(M.B75.B74.B73.B72.B71.B70, 'build_v69') as reconstruct:
                with self.assertRaises(OSError):
                    M.parent_viewer(path)
                reconstruct.assert_not_called()

    def test_parent_and_source_sha_drift_are_refused(self):
        with self.assertRaisesRegex(ValueError, 'SHA256'):
            M.parent_viewer(expected_sha='0' * 64)
        with mock.patch.object(M.V74, 'build', return_value=b'changed viewer74'):
            with self.assertRaisesRegex(ValueError, 'parent 0.74'):
                M.parent_viewer()

    def test_source_snapshot_drift_prevents_publication(self):
        before = {'parentInputs': {'parentInputs': {'originals': {str(i): {} for i in range(27)}}}}
        with mock.patch.object(M.B75, 'inputs', side_effect=[before, {**before, 'drift': True}]), \
             mock.patch.object(M, 'parent_viewer', return_value=b'parent74'), \
             mock.patch.object(M.B75, 'source_scripts', return_value={}), \
             mock.patch.object(M, 'patch_html', return_value='derived viewer'):
            with self.assertRaisesRegex(ValueError, 'entrée a changé'):
                M.build_release()

    def test_repeated_prepare_and_verify_check_html_and_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output, report_path = root / 'viewer75.html', root / 'data/v75/VIEWER_BUILD_REPORT.json'
            parent = root / 'metropole-viewer-v74.html'
            parent.write_bytes(b'preserved viewer74')
            content = b'derived viewer75'
            report = {'version': '0.75.0', 'output': output.name, 'sha256': M.B75.digest(content)}
            with mock.patch.object(M.B75, 'ROOT', root), mock.patch.object(M, 'OUTPUT', output), \
                 mock.patch.object(M, 'REPORT', report_path), \
                 mock.patch.object(M, 'build_release', return_value=(content, report)):
                M.prepare()
                first = output.read_bytes(), report_path.read_bytes()
                M.prepare()
                self.assertEqual(first, (output.read_bytes(), report_path.read_bytes()))
                self.assertEqual(json.loads(report_path.read_text()), report)
                M.prepare(verify=True)
                output.write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError, 'survol 0.75'):
                    M.prepare(verify=True)
                output.write_bytes(content)
                report_path.write_bytes(b'{}')
                with self.assertRaisesRegex(ValueError, 'rapport du survol'):
                    M.prepare(verify=True)
                self.assertEqual(parent.read_bytes(), b'preserved viewer74')


class Viewer75RealParentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parent = GAME / 'metropole-viewer-v74.html'
        if not parent.is_file():
            raise unittest.SkipTest('Generated v74 viewer absent; source-only derivation tested separately.')
        raw = parent.read_bytes()
        if M.B75.digest(raw) != M.PARENT_SHA256:
            raise AssertionError('Real v74 viewer does not match its pinned SHA256.')
        cls.original = raw.decode('utf-8')
        scripts = {name: (GAME / f'src/v75/{name}.js').read_text(encoding='utf-8')
                   for name in M.B75.module_names()}
        cls.output = M.patch_html(cls.original, scripts)
        cls.controller = M.V69.script(cls.output, 'viewer-metropole-viewer')

    def test_metadata_return_link_and_runtime_use_edition75(self):
        data = json.loads(M.V69.script(self.output, 'soma-viewer-data', json_only=True))
        self.assertEqual(data['version'], '0.75.0')
        self.assertEqual(data['returnToGame'], 'SOMA_MASSILIA_URBAIN_v0_75.html')
        self.assertEqual(data['parentViewer74SHA256'], M.PARENT_SHA256)
        self.assertEqual(data['newGeographicCells'], 0)
        self.assertFalse(data['newPersistenceDomain'])
        self.assertIn('SURVOL MÉTROPOLITAIN · 0.75', self.output)
        self.assertIn('Itinéraire par corridor · 0.75', self.output)
        self.assertIn("version:'0.75.0',...state", M.V69.script(self.output, 'viewer-runtime70'))
        self.assertIn('href="SOMA_MASSILIA_URBAIN_v0_75.html"', self.output)
        self.assertNotIn('href="SOMA_MASSILIA_URBAIN_v0_74.html"', self.output)
        self.assertIn("version:'0.75.0',worldIndex:", self.controller)

    def test_campaign_and_external_scripts_stay_out(self):
        for text in ('soma-v37-persistence', 'localStorage.', 'sessionStorage.', '<script src='):
            self.assertNotIn(text, self.output)
        for identifier in ('viewer-terrain-core', 'viewer-dimension-core', 'viewer-architecture-core',
                           'viewer-roof-core', 'viewer-streaming-core', 'viewer-world-index70',
                           'viewer-source-router63'):
            self.assertEqual(M.V69.script(self.output, identifier),
                             M.V69.script(self.original, identifier), identifier)

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
        anchor = 'SURVOL MÉTROPOLITAIN · 0.74'
        for replacement in ('', anchor + anchor):
            with self.assertRaises(ValueError):
                M.patch_edition(self.original.replace(anchor, replacement))


if __name__ == '__main__':
    unittest.main()
