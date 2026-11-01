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
import build_v74 as B


def edition_fixture():
    """Use the actual inherited runtimes rather than pretend campaign modules."""
    runtime = (GAME / 'src/v70/runtime.js').read_text(encoding='utf-8')
    world = (GAME / 'src/v69/world-runtime.js').read_text(encoding='utf-8').replace(
        "button.onclick=()=>location.assign('metropole-viewer.html');",
        "button.onclick=()=>location.assign('metropole-viewer-v73.html');")
    return ('<!doctype html><html><head><title>parent</title></head><body>'
            '<script id="soma-v37-persistence">/* preserved continuity */</script>'
            '<script id="soma-v53-embedded-pack" type="application/json">{"source":true}</script>'
            '<script id="soma-v54-entry">explore.onclick=enterCampaign;</script>'
            '<script id="soma-v69-world-runtime">' + world + '</script>'
            '<script id="soma-v70-runtime">' + runtime + '</script></body></html>')


class Build74Tests(unittest.TestCase):
    def test_all_prior_frozen_sources_and_all_edition73_sources_remain_pinned(self):
        self.assertTrue(B.B73.FROZEN_PARENT_SOURCES.items() <= B.FROZEN_PARENT_SOURCES.items())
        expected73 = set(B.B73.V73_TOOLS) | {
            'src/v73/' + name + '.js' for name in B.B73.module_names()}
        self.assertTrue(expected73 <= B.FROZEN_PARENT_SOURCES.keys())
        for relative in expected73:
            with self.subTest(relative=relative):
                self.assertEqual(B.fingerprint(GAME / relative)['sha256'],
                                 B.FROZEN_PARENT_SOURCES[relative])

    def test_edition_link_title_and_ephemeral_domain(self):
        original = edition_fixture()
        output = B.patch_edition(original)
        self.assertIn("button.onclick=()=>location.assign('metropole-viewer-v74.html');", output)
        self.assertNotIn("location.assign('metropole-viewer-v73.html')", output)
        self.assertIn('0.74', output)
        self.assertIn('<script id="soma-v54-entry">explore.onclick=enterCampaign;</script>', output)
        self.assertIn('<script id="soma-v37-persistence">/* preserved continuity */</script>', output)
        self.assertIn('{"source":true}', output)
        self.assertNotIn('state.v74', output)
        self.assertNotIn('localStorage', output)
        self.assertNotIn('sessionStorage', output)
        self.assertIn('0.70.0', original)
        self.assertNotIn('soma-v74-', original)

    def test_edition_refuses_repeated_application_and_changed_flyover_anchor(self):
        original = edition_fixture()
        with self.assertRaises(ValueError):
            B.patch_edition(B.patch_edition(original))
        anchor = "button.onclick=()=>location.assign('metropole-viewer-v73.html');"
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
            (root / 'build_v73.py').write_bytes(b'drift')
            with mock.patch.object(B, 'ROOT', root), \
                 mock.patch.object(B.B73, 'inputs', return_value={}), \
                 mock.patch.object(B, 'FROZEN_PARENT_SOURCES', {'build_v73.py': '0' * 64}), \
                 mock.patch.object(B, 'module_names') as modules:
                with self.assertRaisesRegex(ValueError, 'parent gelée différente'):
                    B.inputs()
                modules.assert_not_called()

    def test_script_snapshot_is_exact_bounded_and_cannot_end_its_container(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / 'src/v74'
            directory.mkdir(parents=True)
            module = directory / 'fixture.js'
            module.write_text('/* verified module */', encoding='utf-8')
            snapshot = {'modules74': ['fixture'], 'sources74': {
                'src/v74/fixture.js': B.fingerprint(module)}}
            with mock.patch.object(B, 'ROOT', root), mock.patch.object(B, 'module_names', return_value=('fixture',)):
                self.assertEqual(B.source_scripts(snapshot), {'fixture': '/* verified module */'})
                module.write_text('/* changed after snapshot */', encoding='utf-8')
                with self.assertRaises(ValueError):
                    B.source_scripts(snapshot)
                snapshot['sources74']['src/v74/fixture.js']['bytes'] = 2 * 1024 * 1024 + 1
                with self.assertRaises(ValueError):
                    B.source_scripts(snapshot)
                module.write_text('/* </ScRiPt > */', encoding='utf-8')
                snapshot['sources74']['src/v74/fixture.js'] = B.fingerprint(module)
                with self.assertRaises(ValueError):
                    B.source_scripts(snapshot)
                module.write_text('   ', encoding='utf-8')
                snapshot['sources74']['src/v74/fixture.js'] = B.fingerprint(module)
                with self.assertRaises(ValueError):
                    B.source_scripts(snapshot)

    def test_missing_empty_or_duplicate_feature_contracts_are_refused(self):
        for declarations in (([],), (('one', 'one'),), (('../escape',),),
                             (('one',), ('one',)), (('upperCase',),)):
            modules = [mock.Mock(MODULES=value) for value in declarations]
            with mock.patch.object(B, 'extensions', return_value=modules):
                with self.assertRaises(ValueError):
                    B.module_names()

    def test_missing_extension_is_a_build_error(self):
        with mock.patch.object(B.importlib, 'import_module', side_effect=ModuleNotFoundError('required')):
            with self.assertRaises(ModuleNotFoundError):
                B.extensions()

    def test_public_runtime_waits_for_parents_and_preserves_the_only_campaign_domain(self):
        harness = r'''
const vm=require('node:vm'),assert=require('node:assert/strict');
const queued=[],v70={cooldowns:{scan:13},trace:4},core={v70};
const root={__SOMA__:{version:'0.73.0',core},__SOMA_V70__:{ready:true},
  __SOMA_V73__:{ready:false},__SOMA_COMBAT_SUPPORT74__:{snapshot:()=>({shown:1})}};
for(const key of ['localStorage','sessionStorage'])Object.defineProperty(root,key,{get(){throw Error('storage accessed')}});
const document={title:'parent',querySelector:()=>null};
const context={window:root,document,setTimeout:callback=>queued.push(callback)};
vm.runInNewContext(SOURCE,context);
assert.equal(root.__SOMA_V74__,undefined);assert.equal(queued.length,1);
root.__SOMA_V73__.ready=true;queued.shift()();
assert.equal(root.__SOMA_V74__.version,'0.74.0');assert.equal(root.__SOMA__.version,'0.74.0');
assert.equal(root.__SOMA_V74__.ready,true);assert.equal(root.__SOMA_V74__.ephemeral,true);
assert.equal(Object.isFrozen(root.__SOMA_V74__),true);
assert.equal(root.__SOMA__.core,core);assert.equal(core.v70,v70);
assert.deepEqual(Object.keys(core),['v70']);assert.equal(core.v70.cooldowns.scan,13);
assert.equal(core.v70.trace,4);assert.equal(root.__SOMA_V74__.snapshot().combat.shown,1);
'''.replace('SOURCE', json.dumps(B.EDITION_RUNTIME))
        result = subprocess.run(['node'], input=harness, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_wrong_parent_and_input_drift_prevent_build(self):
        parent = b'parent 0.73 from immutable sources'
        parent_report = {'version': '0.73.0', 'sha256': B.digest(parent),
                         'worldManifestSHA256': 'a' * 64, 'preparedCells': 3,
                         'geographicWorld': 'data/v69/world/manifest.json',
                         'originalFilesVerified': 27}
        before = {'parentInputs': {'originals': {str(i): {} for i in range(27)},
                                  'reusedWorldManifest': {'sha256': 'a' * 64}},
                  'frozenParentSources': {}, 'sources74': {}, 'modules74': []}
        with mock.patch.object(B, 'inputs', return_value=before), \
             mock.patch.object(B.B73, 'build_release', return_value=(parent, parent_report)):
            with self.assertRaises(ValueError):
                B.build_release()
        with mock.patch.object(B, 'inputs', side_effect=[before, {**before, 'drift': True}]), \
             mock.patch.object(B.B73, 'build_release', return_value=(parent, parent_report)), \
             mock.patch.object(B, 'PARENT_SHA256', B.digest(parent)), \
             mock.patch.object(B, 'source_scripts', return_value={}), \
             mock.patch.object(B, 'patch_html', return_value='derived fixture'):
            with self.assertRaisesRegex(ValueError, 'chang|drift|modifi'):
                B.build_release()

    def test_prepare_is_reproducible_and_verify_checks_both_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output, report_path = root / 'game74.html', root / 'data/v74/BUILD_REPORT.json'
            parent = root / 'parent73.html'
            parent.write_bytes(b'preserved parent')
            data = b'derived game74'
            report = {'version': '0.74.0', 'sha256': B.digest(data)}
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
                self.assertFalse((root / 'data/v74/world').exists())
                output.write_bytes(b'corrupt')
                with self.assertRaises(ValueError):
                    B.prepare(verify=True)
                output.write_bytes(data)
                report_path.write_bytes(b'{}')
                with self.assertRaises(ValueError):
                    B.prepare(verify=True)

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
                for relative in ('SOMA_MASSILIA_URBAIN_v0_73.html', 'metropole-viewer-v73.html', 'data/v73/BUILD_REPORT.json', 'src/v73/runtime.js', 'build_v73.py', 'tools/serve_v73.py'):
                    with self.assertRaisesRegex(ValueError, 'parent gelé'):
                        B.atomic_write(root / relative, b'overwrite')
                self.assertFalse(target.exists())
                self.assertEqual(list(root.iterdir()), [])


class Build74RealParentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parent = GAME / 'SOMA_MASSILIA_URBAIN_v0_73.html'
        if not parent.is_file():
            raise unittest.SkipTest('Generated v73 HTML absent; parent reconstruction is exercised by release verification.')
        raw = parent.read_bytes()
        if B.digest(raw) != B.PARENT_SHA256:
            raise AssertionError('Real parent73 HTML does not match its pinned SHA256.')
        cls.original = raw.decode('utf-8')
        scripts = {name: (GAME / f'src/v74/{name}.js').read_text(encoding='utf-8')
                   for name in B.module_names()}
        cls.output = B.patch_html(cls.original, scripts)

    @staticmethod
    def script(html, identifier):
        matches = re.findall(r'<script\b[^>]*\bid="' + re.escape(identifier) + r'"[^>]*>([\s\S]*?)</script>', html)
        if not matches:
            raise AssertionError('Missing real script: ' + identifier)
        # The inherited parts proof and runtime share a historical ID. Verify
        # both byte sequences without changing that frozen parent structure.
        return tuple(matches)

    def test_original_pack_geographic_cores_and_campaign_continuity_are_byte_identical(self):
        for identifier in ('soma-v53-embedded-pack',
                           'soma-v69-roof-core', 'soma-v69-building-parts',
                           'soma-v69-height-references', 'soma-v70-augmentations-core',
                           'soma-v70-infiltration-core'):
            self.assertEqual(self.script(self.output, identifier), self.script(self.original, identifier), identifier)
        self.assertIn("button.onclick=()=>location.assign('metropole-viewer-v74.html');", self.output)
        self.assertIn('id="soma-v74-edition"', self.output)
        self.assertNotIn('state.v74', self.output)

    def test_campaign_saver_changes_only_reviewed_identities_and_existing_recovery_field(self):
        original, = self.script(self.original, 'soma-v37-persistence')
        expected = original
        changes = (
            ("number(e.health,0,1e7,'Santé ennemie');",
             "number(e.health,0,1e7,'Santé ennemie');if(e.attackClock!==undefined)number(e.attackClock,0,3600,'Recharge ennemie');"),
            ("function enemyIdKnown(id,k){if(typeof id==='string'&&id.startsWith('v36-'))",
             "function enemyIdKnown(id,k,zoneId=null){if(typeof id==='string'&&id.startsWith('v45-'))return k.edition>=37&&window.__SOMA_PROGRESSION74__?.knownEnemy(id,zoneId)===true;if(typeof id==='string'&&id.startsWith('v36-'))"),
            ("if(!enemyIdKnown(id,k))fail('Adversaire'", "if(!enemyIdKnown(id,k,z))fail('Adversaire'"),
            ('enemyIdKnown(id.slice(5),k)', 'enemyIdKnown(id.slice(5),k,l.zone)'),
            ("member(l.role,k.roles,'Butin')",
             "member(window.__SOMA_PROGRESSION74__?.legacyLootRole(id,l.zone,l.role)||l.role,k.roles,'Butin')"),
            ('for(const partMap of Object.values(q.enemyParts))',
             'for(const [partZone,partMap] of Object.entries(q.enemyParts))'),
            ("if(!enemyIdKnown(id,k))fail('Partie ennemie'", "if(!enemyIdKnown(id,k,partZone))fail('Partie ennemie'"),
        )
        for before, after in changes:
            self.assertEqual(expected.count(before), 1, before)
            expected = expected.replace(before, after, 1)
        self.assertEqual(self.script(self.output, 'soma-v37-persistence'), (expected,))

    def test_survol_does_not_reassign_the_real_v54_campaign_button(self):
        # The historical campaign entry remains in its own inherited module.
        identifiers = re.findall(r'<script\b[^>]*\bid="([^"]+)"[^>]*>', self.original)
        entry_modules = [key for key in identifiers if key.startswith('soma-v54-')]
        self.assertTrue(entry_modules)
        for identifier in entry_modules:
            self.assertEqual(self.script(self.output, identifier), self.script(self.original, identifier), identifier)


if __name__ == '__main__':
    unittest.main()
