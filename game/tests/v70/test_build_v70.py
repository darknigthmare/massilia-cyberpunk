"""Source/precondition and publication checks without rebuilding the large world."""
from pathlib import Path
from unittest import mock
import hashlib
import json
import sys
import tempfile
import unittest

GAME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GAME))
import build_v70 as B


def fixture():
    saver = ('function validateCore37(core,edition){\n'
             ' for(const key of Object.keys(core)){\n'
             '  const version=key.match(/^(?:v|player|campaign)(\\d+)/);\n'
             ' }\n}\nfunction applyEnvelope(envelope){\n'
             '  state=normalizeCore37(robustNormalize(clone(p.core)));state.driving=null;state.lastOnFoot=null;\n}\n')
    return ('<!doctype html><html><head><title>parent</title></head><body>'
            '<script id="soma-v37-persistence">' + saver + '</script>'
            '<script id="soma-v53-embedded-pack" type="application/json">{"unchangedSource":true}</script>'
            '<script id="soma-v69-roof-core">/* parent roofs */</script>'
            '<script id="soma-v68-building-renderer">const seed = 1, material = K.appearance(p, seed);</script>'
            '<script id="soma-v69-world-runtime">/* parent footer */'
            "button.onclick=()=>location.assign('metropole-viewer.html');</script>"
            '<script id="campaign-entry">explore.onclick=enterCampaign;</script></body></html>')


class Build70Tests(unittest.TestCase):
    def scripts(self):
        return {name: '/* source ' + name + ' */' for name in B.MODULES}

    def test_module_order_optional_domain_and_parent_geography(self):
        original = fixture()
        seen = []
        html = B.patch_html(original, self.scripts(), lambda value: seen.append(value) or value)
        self.assertEqual(len(seen), 1)
        order = ['soma-v70-augmentations-core', 'soma-v70-infiltration-core', 'soma-v37-persistence',
                 'soma-v69-roof-core', 'soma-v70-material-extension-core', 'soma-v68-building-renderer',
                 'soma-v69-world-runtime', 'soma-v70-perception-runtime', 'soma-v70-runtime']
        self.assertEqual([html.index('id="' + key + '"') for key in order],
                         sorted(html.index('id="' + key + '"') for key in order))
        self.assertIn('{"unchangedSource":true}', html)
        self.assertIn('augmentations.validatePersistence(entry.value)', html)
        self.assertIn('window.__SOMA_V70__?.restoreCampaign?.(state.v70);', html)
        self.assertIn('(window.__SOMA_MATERIAL70_CORE__?.appearance || K.appearance)(p, seed)', html)
        self.assertIn('const version=key.match(/^(?:v|player|campaign)(\\d+)/);', html)
        self.assertNotIn('soma-v70-', original)

    def test_duplicate_drift_and_script_terminators_refused(self):
        html = B.patch_html(fixture(), self.scripts(), lambda value: value)
        with self.assertRaises(ValueError):
            B.patch_html(html, self.scripts(), lambda value: value)
        for old in ('<head>', 'material = K.appearance(p, seed);', 'function validateCore37(core,edition){\n'):
            with self.assertRaises(ValueError):
                B.patch_html(fixture().replace(old, ''), self.scripts(), lambda value: value)
        for name in B.MODULES:
            scripts = self.scripts()
            scripts[name] = '/* </ScRiPt > <script> */'
            with self.assertRaises(ValueError):
                B.patch_html(fixture(), scripts, lambda value: value)

    def test_flyover_targets_current_viewer_without_changing_campaign_entry(self):
        html = B.patch_html(fixture(), self.scripts(), lambda value: value)
        self.assertIn("button.onclick=()=>location.assign('metropole-viewer-v70.html');", html)
        self.assertNotIn("location.assign('metropole-viewer.html')", html)
        self.assertIn('<script id="campaign-entry">explore.onclick=enterCampaign;</script>', html)
        old = "button.onclick=()=>location.assign('metropole-viewer.html');"
        for changed in ('', old + old):
            with self.assertRaises(ValueError):
                B.patch_html(fixture().replace(old, changed), self.scripts(), lambda value: value)

    def test_exact_script_bytes_and_budget(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / 'src/v70'
            directory.mkdir(parents=True)
            snapshots = {'sources70': {}}
            for name, text in self.scripts().items():
                path = directory / (name + '.js')
                path.write_text(text)
                snapshots['sources70'][str(path.relative_to(root))] = B.fingerprint(path)
            with mock.patch.object(B, 'ROOT', root):
                self.assertEqual(B.source_scripts(snapshots), self.scripts())
                (directory / 'runtime.js').write_text('/* changed after snapshot */')
                with self.assertRaisesRegex(ValueError, 'pendant la lecture'):
                    B.source_scripts(snapshots)
                snapshots['sources70']['src/v70/runtime.js']['bytes'] = 2 * 1024 * 1024 + 1
                with self.assertRaisesRegex(ValueError, 'volumineux'):
                    B.source_scripts(snapshots)

    def original_fixture(self, temporary):
        base = Path(temporary)
        root, payload = base / 'game', base / 'payload'
        root.mkdir()
        payload.mkdir()
        entries = {}
        for i in range(27):
            path = root / f'original-{i}.txt'
            path.write_text(f'original source {i}')
            entries[path.name] = B.fingerprint(path)
        manifest = {'format': 1, 'original_files': entries}
        raw = json.dumps(manifest).encode()
        (payload / 'manifest.json').write_bytes(raw)
        return root, manifest, B.digest(raw)

    def test_originals_are_pinned_and_corruption_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, manifest, checksum = self.original_fixture(temporary)
            with mock.patch.object(B, 'ROOT', root), mock.patch.object(B, 'ORIGINAL_MANIFEST_SHA256', checksum):
                self.assertEqual(B.originals(), manifest['original_files'])
                (root / 'original-3.txt').write_text('unexpected')
                with self.assertRaisesRegex(ValueError, 'original différent'):
                    B.originals()
                (root.parent / 'payload/manifest.json').write_bytes(b'{}')
                with self.assertRaisesRegex(ValueError, 'manifeste.*changé'):
                    B.originals()

    def test_original_manifest_path_escape_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, manifest, checksum = self.original_fixture(temporary)
            manifest['original_files']['../outside.txt'] = manifest['original_files'].pop('original-0.txt')
            raw = json.dumps(manifest).encode()
            (root.parent / 'payload/manifest.json').write_bytes(raw)
            with mock.patch.object(B, 'ROOT', root), mock.patch.object(B, 'ORIGINAL_MANIFEST_SHA256', B.digest(raw)):
                with self.assertRaisesRegex(ValueError, 'hors livraison'):
                    B.originals()

    def test_frozen_source_hash_drift_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'build_v69.py').write_bytes(b'changed')
            with mock.patch.object(B, 'ROOT', root), mock.patch.object(B, 'originals', return_value={}), \
                 mock.patch.object(B, 'FROZEN69_SOURCES', {'build_v69.py': '0' * 64}):
                with self.assertRaisesRegex(ValueError, 'gelée différente'):
                    B.inputs()

    def test_parent_and_input_drift_prevent_publication(self):
        parent = fixture().encode()
        before = {'originals': {str(i): {} for i in range(27)},
                  'reusedWorldManifest': {'sha256': 'a' * 64}}
        with mock.patch.object(B, 'inputs', return_value=before), \
             mock.patch.object(B, 'build_v69', return_value=parent):
            with self.assertRaisesRegex(ValueError, 'parent 0.69'):
                B.build_release()
        with mock.patch.object(B, 'inputs', side_effect=[before, {**before, 'drift': True}]), \
             mock.patch.object(B, 'build_v69', return_value=parent), \
             mock.patch.object(B, 'PARENT_SHA256', B.digest(parent)), \
             mock.patch.object(B, 'verify_world', return_value={'tiles': []}), \
             mock.patch.object(B, 'world_inputs', return_value={}), \
             mock.patch.object(B, 'source_scripts', return_value=self.scripts()), \
             mock.patch.object(B, 'patch_html', return_value='derived source fixture'):
            with self.assertRaisesRegex(ValueError, 'entrée a changé'):
                B.build_release()

    def test_repeated_prepare_and_verify_only_touch_generated_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data, report = b'derived game', {'version': '0.70.0', 'sha256': B.digest(b'derived game')}
            output, report_path = root / 'game70.html', root / 'data/v70/BUILD_REPORT.json'
            (root / 'parent69.html').write_bytes(b'unchanged parent')
            with mock.patch.object(B, 'ROOT', root), mock.patch.object(B, 'OUTPUT', output), \
                 mock.patch.object(B, 'REPORT', report_path), mock.patch.object(B, 'build_release', return_value=(data, report)):
                B.prepare()
                first = output.read_bytes(), report_path.read_bytes()
                B.prepare()
                self.assertEqual(first, (output.read_bytes(), report_path.read_bytes()))
                B.prepare(verify=True)
                self.assertEqual((root / 'parent69.html').read_bytes(), b'unchanged parent')
                self.assertFalse((root / 'data/v70/world').exists())
                output.write_bytes(b'drift')
                with self.assertRaisesRegex(ValueError, 'HTML 0.70'):
                    B.prepare(verify=True)
                output.write_bytes(data)
                report_path.write_bytes(b'{}')
                with self.assertRaisesRegex(ValueError, 'rapport 0.70'):
                    B.prepare(verify=True)

    def test_atomic_outputs_refuse_symlinks_and_clean_failed_temporary(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / 'game'
            root.mkdir()
            outside = base / 'outside'
            outside.write_bytes(b'preserve')
            target = root / 'output'
            target.symlink_to(outside)
            with mock.patch.object(B, 'ROOT', root):
                with self.assertRaises(ValueError):
                    B.atomic_write(target, b'overwrite')
                self.assertEqual(outside.read_bytes(), b'preserve')
                target.unlink()
                with mock.patch.object(B.os, 'replace', side_effect=OSError('publication failed')):
                    with self.assertRaises(OSError):
                        B.atomic_write(target, b'prepared')
                self.assertFalse(target.exists())
                self.assertEqual(list(root.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
