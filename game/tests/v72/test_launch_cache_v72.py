"""Verify fast launch integrity with the real centre-world asset validator."""
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
import importlib.util
import json
import os
import sys
import tempfile
import unittest

GAME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GAME))
from tools import launch_cache_v72 as C
from tools.metropole.bootstrap import verify_world, SCHEMA, ORIGIN

spec = importlib.util.spec_from_file_location('launcher72_cache_tests', GAME.parent / 'lancer.py')
L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)


class LaunchCacheTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'game'
        self.root.mkdir()
        self.put('../lancer.py', 'fixture launcher')
        self.put('../payload/manifest.json', '{}')
        self.put('build_v72.py', '# fixture builder')
        self.put('src/v68/architecture-core.js', 'parent module')
        self.put('src/v72/fixture.js', 'new module')
        self.put('tools/launch_cache_v72.py', '# fixture cache')
        self.put('tools/metropole/bootstrap.py', '# fixture bootstrap')
        self.put('tools/v69/terrain_tiles.py', '# fixture tiler')
        self.put('data/v58/terrain.ign.json', '{}')
        territory = {'schema': 'soma-metropole/territory/1', 'id': '200054807', 'year': 2026,
                     'communes': [{'code': str(13000 + i)} for i in range(92)]}
        self.put('data/v69/territory.json', json.dumps(territory))
        for name in C.HTML_FILES:
            self.put(name, 'fixture output ' + name)
        original_inputs = {'originals': {'verifiedOriginal': True}}
        parent_inputs = {'parentInputs': original_inputs, 'sources71': {'fixture': True}}
        current_inputs = {'parentInputs': parent_inputs,
                          'sources72': {'src/v72/fixture.js': self.fp('src/v72/fixture.js')}}
        self.builder = SimpleNamespace(B71=SimpleNamespace(
            B70=SimpleNamespace(PARENT_SHA256=self.fp(C.HTML_FILES[1])['sha256']),
            PARENT_SHA256=self.fp(C.HTML_FILES[2])['sha256']),
            PARENT_SHA256=self.fp(C.HTML_FILES[3])['sha256'], inputs=lambda: current_inputs)
        self.viewer_pin = mock.patch.object(C, 'PARENT_VIEWER71_SHA256', self.fp('metropole-viewer-v71.html')['sha256'])
        self.viewer_pin.start()
        self.addCleanup(self.viewer_pin.stop)
        self.dependencies = mock.patch.object(C, 'dependencies', return_value=(self.builder, verify_world))
        self.dependencies.start()
        self.addCleanup(self.dependencies.stop)
        expected = {'htmlSHA256': self.builder.B71.B70.PARENT_SHA256,
                    'terrainFileSHA256': self.fp('data/v58/terrain.ign.json')['sha256'],
                    'territoryFileSHA256': self.fp('data/v69/territory.json')['sha256'],
                    'bootstrapSourceSHA256': self.fp('tools/metropole/bootstrap.py')['sha256'],
                    'terrainTilerSourceSHA256': self.fp('tools/v69/terrain_tiles.py')['sha256']}
        cell = {'cellId': 'V52-MC-33'}
        for layer in ('vector', 'terrain', 'surfaces', 'navigation'):
            name = layer + '/V52-MC-33.json.gz'
            self.put('data/v69/world/' + name, 'verified ' + layer)
            cell[layer] = {'path': name, **self.fp('data/v69/world/' + name)}
        world = {'schema': SCHEMA, 'origin': ORIGIN, 'coverageExplicitPartial': True,
                 'completeMetropole': False, 'buildInputs': expected, 'tiles': [cell],
                 'target': {'boundarySHA256': None, 'territorySHA256': expected['territoryFileSHA256']}}
        world['manifestContentSHA256'] = C.digest(C.canonical(world))
        self.put('data/v69/world/manifest.json', json.dumps(world))
        for version in ('68', '69', '70', '71', '72'):
            name = f'SOMA_MASSILIA_URBAIN_v0_{version}.html'
            value = {'version': f'0.{version}.0', 'output': name, **self.fp(name)}
            if version == '70':
                value['inputs'] = original_inputs
            if version == '71':
                value['inputs'] = parent_inputs
            if version == '72':
                value.update(inputs=self.builder.inputs(),
                             worldManifestSHA256=self.fp('data/v69/world/manifest.json')['sha256'])
            self.put(f'data/v{version}/BUILD_REPORT.json', json.dumps(value))
        for version, inputs in (('71', parent_inputs), ('72', current_inputs)):
            name = f'metropole-viewer-v{version}.html'
            self.put(f'data/v{version}/VIEWER_BUILD_REPORT.json', json.dumps({
                'version': f'0.{version}.0', 'output': name, **self.fp(name), 'inputs': inputs}))
        self.put('data/v71/LAUNCH_CACHE.json', '{"preserved":true}')
        self.record()

    def put(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')

    def fp(self, relative):
        return C.fingerprint(self.root / relative)

    def record(self):
        return C.record_prepared(C.source_inputs(self.root), self.root)

    def test_repeat_hit_uses_no_builders_and_needs_no_git_or_optional_metropole(self):
        self.assertFalse((self.root.parent / '.git').exists())
        self.assertFalse((self.root / 'data/v69/metropole').exists())
        before = self.fp(C.RECEIPT)
        with mock.patch('subprocess.call', side_effect=AssertionError('No reconstruction allowed')):
            for _ in range(2):
                result = C.try_ready(self.root)
                self.assertTrue(result['ready'], result)
                self.assertEqual(result['worldCells'], 1)
        self.assertEqual(self.fp(C.RECEIPT), before)
        self.assertEqual((self.root / 'data/v71/LAUNCH_CACHE.json').read_text(), '{"preserved":true}')

    def test_optional_metropole_and_download_sources_are_outside_required_receipt(self):
        for directory in ('metropole', 'source'):
            self.put(f'data/v69/{directory}/optional.json', '{"optional":"changed"}')
        self.assertTrue(C.try_ready(self.root)['ready'])

    def test_parent_viewer_cannot_be_rebound_by_changing_its_report(self):
        name = 'metropole-viewer-v71.html'
        self.put(name, 'changed frozen parent viewer')
        path = self.root / 'data/v71/VIEWER_BUILD_REPORT.json'
        report = json.loads(path.read_text())
        report.update(self.fp(name))
        path.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, 'parent gelé'):
            self.record()

    def test_same_size_same_timestamp_source_and_generated_html_edits_miss(self):
        for name in ('src/v68/architecture-core.js', C.HTML_FILES[4], C.HTML_FILES[8]):
            path = self.root / name
            raw, stat = path.read_bytes(), path.stat()
            path.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
            os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
            self.assertFalse(C.try_ready(self.root)['ready'], name)
            path.write_bytes(raw)
            self.assertTrue(C.try_ready(self.root)['ready'], name)

    def test_new_transitive_source_and_pinned_new_edition_inputs_miss(self):
        self.put('src/v68/new-dependency.js', 'another dependency')
        self.assertFalse(C.try_ready(self.root)['ready'])
        (self.root / 'src/v68/new-dependency.js').unlink()
        self.put('src/v72/fixture.js', 'changed edition module')
        self.assertFalse(C.try_ready(self.root)['ready'])

    def test_all_four_actual_centre_asset_layers_are_hashed_even_on_receipt_hit(self):
        for layer in ('vector', 'terrain', 'surfaces', 'navigation'):
            path = self.root / f'data/v69/world/{layer}/V52-MC-33.json.gz'
            raw = path.read_bytes()
            path.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
            result = C.try_ready(self.root)
            self.assertFalse(result['ready'], layer)
            self.assertIn('Asset modifié', result['reason'])
            path.write_bytes(raw)
            self.assertTrue(C.try_ready(self.root)['ready'])
        path.unlink()
        self.assertFalse(C.try_ready(self.root)['ready'])

    def test_report_and_html_cannot_be_changed_together_to_reuse_an_old_receipt(self):
        name = C.HTML_FILES[-1]
        self.put(name, 'rewritten viewer')
        report = json.loads((self.root / 'data/v72/VIEWER_BUILD_REPORT.json').read_text())
        report.update(self.fp(name))
        self.put('data/v72/VIEWER_BUILD_REPORT.json', json.dumps(report))
        self.assertFalse(C.try_ready(self.root)['ready'])

    def test_missing_or_bad_receipt_and_incomplete_outputs_fall_back(self):
        path = self.root / C.RECEIPT
        raw = path.read_bytes()
        for content in (b'{}', b'[]', b'not json', b'x' * (2 * 1024 * 1024 + 1)):
            path.write_bytes(content)
            self.assertFalse(C.try_ready(self.root)['ready'])
        path.unlink()
        self.assertFalse(C.try_ready(self.root)['ready'])
        path.write_bytes(raw)
        (self.root / C.HTML_FILES[4]).unlink()
        self.assertFalse(C.try_ready(self.root)['ready'])

    def test_record_refuses_concurrent_transitive_edits_and_external_symlinks(self):
        before = C.source_inputs(self.root)
        self.put('src/v68/architecture-core.js', 'changed parent code')
        with self.assertRaisesRegex(ValueError, 'Sources modifiées'):
            C.record_prepared(before, self.root)
        path = self.root / C.RECEIPT
        path.unlink()
        external = self.root.parent / 'protected.json'
        external.write_text('untouched')
        path.symlink_to(external)
        self.assertFalse(C.try_ready(self.root)['ready'])
        with self.assertRaises(ValueError):
            self.record()
        self.assertEqual(external.read_text(), 'untouched')


class Launcher72Tests(unittest.TestCase):
    def run_launcher(self, arguments, *, ready=False, builder_failure=False):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            game, payload = root / 'game', root / 'payload'
            game.mkdir()
            payload.mkdir()
            (payload / 'manifest.json').write_text(json.dumps({'format': 1,
                    'original_files': {str(i): {} for i in range(27)}}))
            commands = []
            def run(command, **kwargs):
                commands.append(command)
                return 2 if builder_failure and len(commands) == 2 else 0
            with mock.patch.object(L, 'ROOT', root), mock.patch.object(L, 'GAME', game), \
                 mock.patch.object(L, 'PAYLOAD', payload), mock.patch.object(L, 'prepare') as prepare, \
                 mock.patch.object(L, 'check_parts') as parts, mock.patch.object(L, 'check_game') as originals, \
                 mock.patch.object(C, 'try_ready', return_value={'ready': ready, 'seconds': .2}) as hit, \
                 mock.patch.object(C, 'source_inputs', return_value={'expected': 'source'}) as source, \
                 mock.patch.object(C, 'record_prepared') as record, \
                 mock.patch.object(L.subprocess, 'call', side_effect=run), \
                 mock.patch.object(sys, 'argv', ['lancer.py', *arguments]):
                code = L.main()
                return SimpleNamespace(code=code, commands=commands, prepare=prepare.call_count,
                    parts=parts.call_count, originals=originals.call_count, hit=hit.call_count,
                    source=source.call_count, record=record.call_count)

    def test_normal_hit_preserves_original_preparation_checks_and_serves72_without_builders(self):
        result = self.run_launcher(['--no-browser', '--port', '8766'], ready=True)
        self.assertEqual(result.code, 0)
        self.assertEqual(result.prepare, 1)
        self.assertEqual(result.hit, 1)
        self.assertEqual(result.record, 0)
        self.assertEqual(len(result.commands), 1)
        self.assertEqual(Path(result.commands[0][1]).name, 'serve_v72.py')
        self.assertIn('--no-browser', result.commands[0])
        self.assertIn('8766', result.commands[0])

    def test_normal_miss_rebuilds_all_editions_and_records_only_after_success(self):
        result = self.run_launcher(['--no-browser'])
        self.assertEqual(result.code, 0)
        self.assertEqual(len(result.commands), 10)
        self.assertIn('build_v72.py', [Path(c[1]).name for c in result.commands])
        self.assertIn('build_metropole_viewer_v72.py', [Path(c[1]).name for c in result.commands])
        self.assertEqual(result.record, 1)

    def test_prepare_only_always_runs_full_chain_and_verify_is_read_only_and_full(self):
        prepared = self.run_launcher(['--prepare-only'], ready=True)
        self.assertEqual(prepared.hit, 0)
        self.assertEqual(len(prepared.commands), 9)
        self.assertEqual(prepared.record, 1)
        verified = self.run_launcher(['--verify'], ready=True)
        self.assertEqual((verified.prepare, verified.parts, verified.originals), (0, 1, 1))
        self.assertEqual((verified.hit, verified.record), (0, 0))
        self.assertEqual(len(verified.commands), 9)
        self.assertTrue(all(command[-1] == '--verify' for command in verified.commands))

    def test_failed_builder_neither_records_a_receipt_nor_starts_server(self):
        result = self.run_launcher(['--no-browser'], builder_failure=True)
        self.assertEqual(result.code, 2)
        self.assertEqual(len(result.commands), 2)
        self.assertEqual(result.record, 0)


if __name__ == '__main__':
    unittest.main()
