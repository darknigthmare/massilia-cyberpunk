"""Verify edition74 fast launch integrity with the real centre asset validator."""
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
from tools import launch_cache_v74 as C
from tools.metropole.bootstrap import verify_world, SCHEMA, ORIGIN

spec = importlib.util.spec_from_file_location('launcher74_cache_tests', GAME.parent / 'lancer.py')
L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)


class LaunchCache74Tests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'game'
        self.root.mkdir()
        self.put('../lancer.py', 'fixture launcher')
        self.put('../payload/manifest.json', '{}')
        self.put('build_v74.py', '# fixture builder')
        self.put('src/v68/architecture-core.js', 'parent module')
        self.put('src/v72/fixture.js', 'frozen parent module')
        self.put('src/v73/fixture.js', 'frozen parent module')
        self.put('src/v74/fixture.js', 'new module')
        self.put('tools/launch_cache_v74.py', '# fixture cache')
        self.put('tools/metropole/bootstrap.py', '# fixture bootstrap')
        self.put('tools/v69/terrain_tiles.py', '# fixture tiler')
        self.put('data/v58/terrain.ign.json', '{}')
        territory = {'schema': 'soma-metropole/territory/1', 'id': '200054807', 'year': 2026,
                     'communes': [{'code': str(13000 + i)} for i in range(92)]}
        self.put('data/v69/territory.json', json.dumps(territory))
        for name in C.HTML_FILES:
            self.put(name, 'fixture output ' + name)
        inputs70 = {'originals': {'verifiedOriginal': True}}
        inputs71 = {'parentInputs': inputs70, 'sources71': {'fixture': True}}
        inputs72 = {'parentInputs': inputs71, 'sources72': {
            'src/v72/fixture.js': self.fp('src/v72/fixture.js')}}
        inputs73 = {'parentInputs': inputs72, 'sources73': {
            'src/v73/fixture.js': self.fp('src/v73/fixture.js')}}
        inputs74 = {'parentInputs': inputs73, 'sources74': {
            'src/v74/fixture.js': self.fp('src/v74/fixture.js')}}
        pin = lambda version: self.fp(f'SOMA_MASSILIA_URBAIN_v0_{version}.html')['sha256']
        self.builder = SimpleNamespace(B73=SimpleNamespace(B72=SimpleNamespace(B71=SimpleNamespace(
            B70=SimpleNamespace(PARENT_SHA256=pin('69')),
            PARENT_SHA256=pin('70')), PARENT_SHA256=pin('71')),
            PARENT_SHA256=pin('72')), PARENT_SHA256=pin('73'), inputs=lambda: inputs74)
        for version in ('71', '72', '73'):
            patch = mock.patch.object(C, f'PARENT_VIEWER{version}_SHA256',
                                      self.fp(f'metropole-viewer-v{version}.html')['sha256'])
            patch.start()
            self.addCleanup(patch.stop)
        dependencies = mock.patch.object(C, 'dependencies', return_value=(self.builder, verify_world))
        dependencies.start()
        self.addCleanup(dependencies.stop)
        expected = {'htmlSHA256': pin('69'),
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
        version_inputs = {'70': inputs70, '71': inputs71, '72': inputs72, '73': inputs73, '74': inputs74}
        for version in ('68', '69', '70', '71', '72', '73', '74'):
            name = f'SOMA_MASSILIA_URBAIN_v0_{version}.html'
            report = {'version': f'0.{version}.0', 'output': name, **self.fp(name)}
            if version in version_inputs:
                report['inputs'] = version_inputs[version]
            if version == '74':
                report['worldManifestSHA256'] = self.fp('data/v69/world/manifest.json')['sha256']
            self.put(f'data/v{version}/BUILD_REPORT.json', json.dumps(report))
        for version in ('71', '72', '73', '74'):
            name = f'metropole-viewer-v{version}.html'
            self.put(f'data/v{version}/VIEWER_BUILD_REPORT.json', json.dumps({
                'version': f'0.{version}.0', 'output': name, **self.fp(name),
                'inputs': version_inputs[version]}))
        for version in ('71', '72', '73'):
            self.put(f'data/v{version}/LAUNCH_CACHE.json', '{"preserved":true}')
        self.record()

    def put(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')

    def fp(self, relative):
        return C.fingerprint(self.root / relative)

    def record(self):
        return C.record_prepared(C.source_inputs(self.root), self.root)

    def test_repeat_hit_needs_no_builders_git_or_optional_metropole(self):
        self.assertFalse((self.root.parent / '.git').exists())
        self.assertFalse((self.root / 'data/v69/metropole').exists())
        before = self.fp(C.RECEIPT)
        with mock.patch('subprocess.call', side_effect=AssertionError('No reconstruction allowed')):
            for _ in range(2):
                result = C.try_ready(self.root)
                self.assertTrue(result['ready'], result)
                self.assertEqual(result['worldCells'], 1)
        self.assertEqual(self.fp(C.RECEIPT), before)
        for version in ('71', '72', '73'):
            self.assertEqual((self.root / f'data/v{version}/LAUNCH_CACHE.json').read_text(),
                             '{"preserved":true}')

    def test_optional_metropole_and_download_sources_are_outside_required_receipt(self):
        for directory in ('metropole', 'source'):
            self.put(f'data/v69/{directory}/optional.json', '{"optional":"changed"}')
        self.assertTrue(C.try_ready(self.root)['ready'])

    def test_parent_viewers_cannot_be_rebound_by_changing_their_reports(self):
        for version in ('71', '72', '73'):
            with self.subTest(version=version):
                name = f'metropole-viewer-v{version}.html'
                original = (self.root / name).read_text()
                path = self.root / f'data/v{version}/VIEWER_BUILD_REPORT.json'
                report = path.read_text()
                self.put(name, 'changed frozen parent viewer')
                changed = json.loads(report)
                changed.update(self.fp(name))
                path.write_text(json.dumps(changed))
                with self.assertRaisesRegex(ValueError, 'parent gelé'):
                    self.record()
                self.put(name, original)
                path.write_text(report)

    def test_parent_campaign_cannot_be_rebound_by_changing_its_report(self):
        name = 'SOMA_MASSILIA_URBAIN_v0_73.html'
        self.put(name, 'changed frozen parent campaign')
        path = self.root / 'data/v73/BUILD_REPORT.json'
        report = json.loads(path.read_text())
        report.update(self.fp(name))
        path.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, 'parent gelé'):
            self.record()

    def test_same_size_same_timestamp_source_and_generated_html_edits_miss(self):
        for name in ('src/v68/architecture-core.js', 'src/v72/fixture.js',
                     'SOMA_MASSILIA_URBAIN_v0_74.html', 'metropole-viewer-v74.html'):
            path = self.root / name
            raw, stat = path.read_bytes(), path.stat()
            path.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
            os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
            self.assertFalse(C.try_ready(self.root)['ready'], name)
            path.write_bytes(raw)
            self.assertTrue(C.try_ready(self.root)['ready'], name)

    def test_new_transitive_source_and_new_edition_inputs_miss(self):
        self.put('src/v68/new-dependency.js', 'another dependency')
        self.assertFalse(C.try_ready(self.root)['ready'])
        (self.root / 'src/v68/new-dependency.js').unlink()
        self.put('src/v74/fixture.js', 'changed edition module')
        self.assertFalse(C.try_ready(self.root)['ready'])

    def test_all_four_centre_asset_layers_are_hashed_even_on_receipt_hit(self):
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

    def test_report_and_html_cannot_be_changed_together_to_reuse_old_receipt(self):
        name = 'metropole-viewer-v74.html'
        self.put(name, 'rewritten viewer')
        report = json.loads((self.root / 'data/v74/VIEWER_BUILD_REPORT.json').read_text())
        report.update(self.fp(name))
        self.put('data/v74/VIEWER_BUILD_REPORT.json', json.dumps(report))
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
        (self.root / 'SOMA_MASSILIA_URBAIN_v0_74.html').unlink()
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


class Launcher74Tests(unittest.TestCase):
    def test_current_chain_has_thirteen_unique_builders_and_htmls_and_eleven_reports(self):
        self.assertEqual(len(L.BUILDERS), 13)
        self.assertEqual(len(set(L.BUILDERS)), 13)
        self.assertEqual(len(C.HTML_FILES), 13)
        self.assertEqual(len(set(C.HTML_FILES)), 13)
        self.assertEqual(len(C.REPORT_FILES), 11)
        self.assertEqual(len(set(C.REPORT_FILES)), 11)
        self.assertLess(L.BUILDERS.index('build_v73.py'), L.BUILDERS.index('build_v74.py'))
        self.assertLess(L.BUILDERS.index('tools/build_metropole_viewer_v73.py'),
                        L.BUILDERS.index('tools/build_metropole_viewer_v74.py'))
        self.assertEqual(C.RECEIPT, 'data/v74/LAUNCH_CACHE.json')

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

    def test_normal_hit_preserves_original_checks_and_serves74_without_builders(self):
        result = self.run_launcher(['--no-browser', '--port', '8766'], ready=True)
        self.assertEqual(result.code, 0)
        self.assertEqual((result.prepare, result.hit, result.record), (1, 1, 0))
        self.assertEqual(len(result.commands), 1)
        self.assertEqual(Path(result.commands[0][1]).name, 'serve_v74.py')
        self.assertIn('--no-browser', result.commands[0])
        self.assertIn('8766', result.commands[0])

    def test_normal_miss_runs_all_thirteen_builders_before_receipt_and_server(self):
        result = self.run_launcher(['--no-browser'])
        self.assertEqual(result.code, 0)
        self.assertEqual(len(result.commands), 14)
        self.assertEqual([Path(command[1]).name for command in result.commands].count('build_v74.py'), 1)
        self.assertIn('build_metropole_viewer_v74.py', [Path(c[1]).name for c in result.commands])
        self.assertEqual(result.record, 1)
        self.assertEqual(Path(result.commands[-1][1]).name, 'serve_v74.py')

    def test_prepare_is_full_chain_and_verify_is_full_and_read_only(self):
        prepared = self.run_launcher(['--prepare-only'], ready=True)
        self.assertEqual((prepared.hit, prepared.record), (0, 1))
        self.assertEqual(len(prepared.commands), 13)
        verified = self.run_launcher(['--verify'], ready=True)
        self.assertEqual((verified.prepare, verified.parts, verified.originals), (0, 1, 1))
        self.assertEqual((verified.hit, verified.record, verified.source), (0, 0, 0))
        self.assertEqual(len(verified.commands), 13)
        self.assertTrue(all(command[-1] == '--verify' for command in verified.commands))

    def test_failed_builder_neither_records_receipt_nor_starts_server(self):
        result = self.run_launcher(['--no-browser'], builder_failure=True)
        self.assertEqual(result.code, 2)
        self.assertEqual(len(result.commands), 2)
        self.assertEqual(result.record, 0)


if __name__ == '__main__':
    unittest.main()
