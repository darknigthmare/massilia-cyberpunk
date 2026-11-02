"""Edition, integrity and publication checks without rebuilding the large world."""
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
import build_v76 as B


def edition_fixture():
    """Use the actual inherited runtimes rather than pretend campaign modules."""
    runtime = (GAME / 'src/v70/runtime.js').read_text(encoding='utf-8')
    world = (GAME / 'src/v69/world-runtime.js').read_text(encoding='utf-8').replace(
        "button.onclick=()=>location.assign('metropole-viewer.html');",
        "button.onclick=()=>location.assign('metropole-viewer-v75.html');")
    return ('<!doctype html><html><head><title>parent</title></head><body>'
            '<script id="soma-v37-persistence">/* preserved continuity */</script>'
            '<script id="soma-v53-embedded-pack" type="application/json">{"source":true}</script>'
            '<script id="soma-v54-entry">explore.onclick=enterCampaign;</script>'
            '<script id="soma-v69-world-runtime">' + world + '</script>'
            '<script id="soma-v70-runtime">' + runtime + '</script></body></html>')


class Build76Tests(unittest.TestCase):
    def test_all_prior_frozen_sources_and_all_edition75_sources_remain_pinned(self):
        self.assertTrue(B.B75.FROZEN_PARENT_SOURCES.items() <= B.FROZEN_PARENT_SOURCES.items())
        expected75 = set(B.B75.V75_TOOLS) | {
            'src/v75/' + name + '.js' for name in B.B75.module_names()} | set(B.B75.SOURCE_DATA)
        self.assertTrue(expected75 <= B.FROZEN_PARENT_SOURCES.keys())
        for relative in expected75:
            with self.subTest(relative=relative):
                self.assertEqual(B.fingerprint(GAME / relative)['sha256'],
                                 B.FROZEN_PARENT_SOURCES[relative])

    def test_edition_link_title_and_ephemeral_domain(self):
        original = edition_fixture()
        output = B.patch_edition(original)
        self.assertIn("button.onclick=()=>location.assign('metropole-viewer-v76.html');", output)
        self.assertNotIn("location.assign('metropole-viewer-v75.html')", output)
        self.assertIn('0.76', output)
        self.assertIn('<script id="soma-v54-entry">explore.onclick=enterCampaign;</script>', output)
        self.assertIn('<script id="soma-v37-persistence">/* preserved continuity */</script>', output)
        self.assertIn('{"source":true}', output)
        self.assertNotIn('state.v76', output)
        self.assertNotIn('localStorage', output)
        self.assertNotIn('sessionStorage', output)
        self.assertIn('0.70.0', original)
        self.assertNotIn('soma-v76-', original)

    def test_edition_refuses_repeated_application_and_changed_flyover_anchor(self):
        original = edition_fixture()
        with self.assertRaises(ValueError):
            B.patch_edition(B.patch_edition(original))
        anchor = "button.onclick=()=>location.assign('metropole-viewer-v75.html');"
        for replacement in ('', anchor + anchor):
            with self.subTest(replacement=replacement):
                with self.assertRaises(ValueError):
                    B.patch_edition(original.replace(anchor, replacement))
        for replacement in ('', '<title>one</title><title>two</title>'):
            with self.assertRaises(ValueError):
                B.patch_edition(original.replace('<title>parent</title>', replacement))

    def test_parent_sources_are_frozen_before_extension_loading(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'build_v75.py').write_bytes(b'drift')
            with mock.patch.object(B, 'ROOT', root), \
                 mock.patch.object(B.B75, 'inputs', return_value={}), \
                 mock.patch.object(B, 'FROZEN_PARENT_SOURCES', {'build_v75.py': '0' * 64}), \
                 mock.patch.object(B, 'module_names') as modules:
                with self.assertRaisesRegex(ValueError, 'parent gelée différente'):
                    B.inputs()
                modules.assert_not_called()

    def test_script_snapshot_is_exact_bounded_and_cannot_end_its_container(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / 'src/v76'
            directory.mkdir(parents=True)
            module = directory / 'fixture.js'
            module.write_text('/* verified module */', encoding='utf-8')
            snapshot = {'modules76': ['fixture'], 'sources76': {
                'src/v76/fixture.js': B.fingerprint(module)}}
            with mock.patch.object(B, 'ROOT', root), mock.patch.object(B, 'module_names', return_value=('fixture',)):
                self.assertEqual(B.source_scripts(snapshot), {'fixture': '/* verified module */'})
                module.write_text('/* changed after snapshot */', encoding='utf-8')
                with self.assertRaises(ValueError):
                    B.source_scripts(snapshot)
                snapshot['sources76']['src/v76/fixture.js']['bytes'] = 2 * 1024 * 1024 + 1
                with self.assertRaises(ValueError):
                    B.source_scripts(snapshot)
                module.write_text('/* </ScRiPt > */', encoding='utf-8')
                snapshot['sources76']['src/v76/fixture.js'] = B.fingerprint(module)
                with self.assertRaises(ValueError):
                    B.source_scripts(snapshot)
                module.write_text('   ', encoding='utf-8')
                snapshot['sources76']['src/v76/fixture.js'] = B.fingerprint(module)
                with self.assertRaises(ValueError):
                    B.source_scripts(snapshot)

    def test_source_paths_refuse_external_and_internal_symlinks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'game'
            root.mkdir()
            (root / 'module.js').write_text('module')
            (root / 'linked.js').symlink_to(root / 'module.js')
            (root / 'linked').symlink_to(root, target_is_directory=True)
            with mock.patch.object(B, 'ROOT', root):
                self.assertEqual(B.source_path('module.js'), root / 'module.js')
                for relative in ('../escape', str(root / 'module.js'), 'linked.js', 'linked/module.js'):
                    with self.subTest(relative=relative), self.assertRaises(ValueError):
                        B.source_path(relative)

    def test_architecture_provenance_is_an_explicit_immutable_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / 'data/v76/architecture-conflicts.json'
            path.parent.mkdir(parents=True)
            path.write_text('{"conflicts":77}')
            with mock.patch.object(B, 'ROOT', root), \
                 mock.patch.object(B.B75, 'inputs', return_value={}), \
                 mock.patch.object(B, 'FROZEN_PARENT_SOURCES', {}), \
                 mock.patch.object(B, 'V76_TOOLS', ()), \
                 mock.patch.object(B, 'module_names', return_value=()):
                before = B.inputs()
                self.assertEqual(before['sources76']['data/v76/architecture-conflicts.json'], B.fingerprint(path))
                path.write_text('{"conflicts":76}')
                with self.assertRaisesRegex(ValueError, 'entrée a changé'):
                    B.require_unchanged(before, B.inputs())

    def test_missing_empty_or_duplicate_feature_contracts_are_refused(self):
        for declarations in (([],), (('one', 'one'),), (('../escape',),),
                             (('one',), ('one',)), (('upperCase',),)):
            modules = [mock.Mock(MODULES=value) for value in declarations]
            with mock.patch.object(B, 'extensions', return_value=modules):
                with self.assertRaises(ValueError):
                    B.module_names()

    def test_build_contract_imports_without_gis_or_optional_terrain_cache(self):
        harness = r"""
import importlib.abc, sys
class NoGIS(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'numpy','rasterio','osgeo','shapely','pyproj'}:
            raise AssertionError('Optional GIS dependency loaded: ' + fullname)
sys.meta_path.insert(0, NoGIS())
sys.path.insert(0, GAME_PATH)
import build_v76
from tools import launch_cache_v76
assert build_v76.module_names()
assert len(launch_cache_v76.HTML_FILES) == 17
assert not ({'numpy','rasterio','osgeo','shapely','pyproj'} & set(sys.modules))
""".replace('GAME_PATH', repr(str(GAME)))
        result = subprocess.run([sys.executable, '-B', '-S', '-c', harness], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_extension_is_a_build_error(self):
        with mock.patch.object(B.importlib, 'import_module', side_effect=ModuleNotFoundError('required')):
            with self.assertRaises(ModuleNotFoundError):
                B.extensions()

    def test_public_runtime_waits_for_parents_and_preserves_the_only_campaign_domain(self):
        harness = r'''
const vm=require('node:vm'),assert=require('node:assert/strict');
const queued=[],v70={cooldowns:{scan:13},trace:4},core={v70};
const root={__SOMA__:{version:'0.75.0',core},__SOMA_V70__:{ready:true},
  __SOMA_V75__:{ready:false},__SOMA_COMBAT76__:{snapshot:()=>({shown:1})}};
for(const key of ['localStorage','sessionStorage'])Object.defineProperty(root,key,{get(){throw Error('storage accessed')}});
const document={title:'parent',querySelector:()=>null};
const context={window:root,document,setTimeout:callback=>queued.push(callback)};
vm.runInNewContext(SOURCE,context);
assert.equal(root.__SOMA_V76__,undefined);assert.equal(queued.length,1);
root.__SOMA_V75__.ready=true;queued.shift()();
assert.equal(root.__SOMA_V76__.version,'0.76.0');assert.equal(root.__SOMA__.version,'0.76.0');
assert.equal(root.__SOMA_V76__.ready,true);assert.equal(root.__SOMA_V76__.ephemeral,true);
assert.equal(Object.isFrozen(root.__SOMA_V76__),true);
assert.equal(root.__SOMA__.core,core);assert.equal(core.v70,v70);
assert.deepEqual(Object.keys(core),['v70']);assert.equal(core.v70.cooldowns.scan,13);
assert.equal(core.v70.trace,4);assert.equal(root.__SOMA_V76__.snapshot().combat.shown,1);
'''.replace('SOURCE', json.dumps(B.EDITION_RUNTIME))
        result = subprocess.run(['node'], input=harness, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_wrong_parent_and_input_drift_prevent_build(self):
        parent = b'parent 0.75 from immutable sources'
        parent_report = {'version': '0.75.0', 'sha256': B.digest(parent),
                         'worldManifestSHA256': 'a' * 64, 'preparedCells': 3,
                         'geographicWorld': 'data/v69/world/manifest.json',
                         'originalFilesVerified': 27}
        before = {'parentInputs': {'originals': {str(i): {} for i in range(27)},
                                  'reusedWorldManifest': {'sha256': 'a' * 64}},
                  'frozenParentSources': {}, 'sources76': {}, 'modules76': []}
        with mock.patch.object(B, 'inputs', return_value=before), \
             mock.patch.object(B.B75, 'build_release', return_value=(parent, parent_report)):
            with self.assertRaises(ValueError):
                B.build_release()
        with mock.patch.object(B, 'inputs', side_effect=[before, {**before, 'drift': True}]), \
             mock.patch.object(B.B75, 'build_release', return_value=(parent, parent_report)), \
             mock.patch.object(B, 'PARENT_SHA256', B.digest(parent)), \
             mock.patch.object(B, 'source_scripts', return_value={}), \
             mock.patch.object(B, 'patch_html', return_value='derived fixture'):
            with self.assertRaisesRegex(ValueError, 'chang|drift|modifi'):
                B.build_release()

    def test_prepare_is_reproducible_and_verify_checks_both_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output, report_path = root / 'game76.html', root / 'data/v76/BUILD_REPORT.json'
            parent = root / 'parent75.html'
            parent.write_bytes(b'preserved parent')
            data = b'derived game76'
            report = {'version': '0.76.0', 'sha256': B.digest(data)}
            with mock.patch.object(B, 'ROOT', root), mock.patch.object(B, 'OUTPUT', output), \
                 mock.patch.object(B, 'REPORT', report_path), \
                 mock.patch.object(B, 'build_release', return_value=(data, report)):
                B.prepare()
                first = output.read_bytes(), report_path.read_bytes()
                B.prepare()
                self.assertEqual(first, (output.read_bytes(), report_path.read_bytes()))
                self.assertEqual(json.loads(report_path.read_text()), report)
                B.prepare(verify=True)
                self.assertEqual(parent.read_bytes(), b'preserved parent')
                self.assertFalse((root / 'data/v76/world').exists())
                output.write_bytes(b'corrupt')
                with self.assertRaises(ValueError):
                    B.prepare(verify=True)
                output.write_bytes(data)
                report_path.write_bytes(b'{}')
                with self.assertRaises(ValueError):
                    B.prepare(verify=True)

    def test_build_report_distinguishes_authored_marker_placement_from_source_geography(self):
        parent = b'verified fixture parent75'
        parent_report = {'originalFilesVerified': 27, 'preparedCells': 168,
                         'geographicWorld': 'data/v69/world/manifest.json',
                         'worldManifestSHA256': 'a' * 64}
        with mock.patch.object(B, 'inputs', return_value={}), \
             mock.patch.object(B.B75, 'build_release', return_value=(parent, parent_report)), \
             mock.patch.object(B, 'PARENT_SHA256', B.digest(parent)), \
             mock.patch.object(B, 'source_scripts', return_value={}), \
             mock.patch.object(B, 'patch_html', return_value='derived fixture'):
            _, report = B.build_release()
        self.assertFalse(report['renderedGeometryByteIdenticalToParent'])
        self.assertFalse(report['campaignGeographicRenderingModified'])
        self.assertTrue(report['sourceGeometryUnchanged'])
        self.assertTrue(report['sourceAssetsUnchanged'])
        self.assertEqual(report['newGeographicCells'], 0)
        self.assertIn('authored-gig-objective-placement', report['renderingChanges'])
        self.assertIn('native45-ui-defaults', report['renderingChanges'])

    def test_atomic_publication_refuses_escape_symlink_and_cleans_failures(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / 'game'
            root.mkdir()
            outside = base / 'outside'
            outside.write_bytes(b'preserved')
            target = root / 'output'
            with mock.patch.object(B, 'ROOT', root):
                with self.assertRaises(ValueError):
                    B.atomic_write(outside, b'overwrite')
                target.symlink_to(outside)
                with self.assertRaises(ValueError):
                    B.atomic_write(target, b'overwrite')
                self.assertEqual(outside.read_bytes(), b'preserved')
                target.unlink()
                with mock.patch.object(B.os, 'replace', side_effect=OSError('publication failed')):
                    with self.assertRaises(OSError):
                        B.atomic_write(target, b'prepared')
                for relative in ('SOMA_MASSILIA_URBAIN_v0_75.html', 'metropole-viewer-v75.html', 'data/v75/BUILD_REPORT.json', 'src/v75/runtime.js', 'build_v75.py', 'tools/serve_v75.py', 'build_v76.py', 'tools/serve_v76.py', 'data/v76/architecture-conflicts.json', 'data/v76/other-source.json', 'data/v76/world/manifest.json', 'new-source.py', 'src', 'tools', 'data'):
                    with self.assertRaisesRegex(ValueError, 'parent gelé'):
                        B.atomic_write(root / relative, b'overwrite')
                self.assertFalse(target.exists())
                self.assertEqual(list(root.iterdir()), [])

    def test_generated_report_cannot_cross_an_internal_directory_link(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            retained = root / 'data/retained'
            retained.mkdir(parents=True)
            (root / 'data/v76').symlink_to(retained, target_is_directory=True)
            with mock.patch.object(B, 'ROOT', root):
                with self.assertRaisesRegex(ValueError, 'Chemin de sortie'):
                    B.atomic_write(root / 'data/v76/BUILD_REPORT.json', b'overwrite')
            self.assertEqual(list(retained.iterdir()), [])

    def test_atomic_publication_protects_every_original_before_creating_anything(self):
        manifest = json.loads((GAME.parent / 'payload/manifest.json').read_bytes())
        root_files = {name for name in manifest['original_files'] if '/' not in name}
        self.assertEqual(B.ORIGINAL_ROOT_FILES, root_files)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with mock.patch.object(B, 'ROOT', root):
                for relative in (*manifest['original_files'], 'docs', 'tests', 'baseline'):
                    with self.subTest(relative=relative), self.assertRaises(ValueError):
                        B.atomic_write(root / relative, b'overwrite')
            self.assertEqual(list(root.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
