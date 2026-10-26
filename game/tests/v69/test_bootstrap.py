"""Validate real metropolitan bootstrap assets, caching and native routing data."""
from copy import deepcopy
from pathlib import Path
import base64
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.metropole import bootstrap as B


def blob(value, script_id='fixture', *, size=None, sha=None):
    raw = B.canonical(value)
    encoded = base64.b64encode(gzip.compress(raw, mtime=0)).decode('ascii')
    return (f'<script id="{script_id}" type="application/octet-stream" '
            f'data-encoding="gzip-base64" data-bytes="{len(raw) if size is None else size}" '
            f'data-sha256="{B.digest(raw) if sha is None else sha}">{encoded}</script>')


def seal(manifest):
    manifest['manifestContentSHA256'] = B.digest(B.canonical({key:value for key,value in manifest.items()
                                                           if key != 'manifestContentSHA256'}))
    return manifest


def tiny_world(directory):
    vector = B.asset(directory, 'tiles/V52-MC-33.vector.json.gz', {'fixture':'never geographic coverage'})
    manifest = seal({'schema':B.SCHEMA, 'origin':B.ORIGIN, 'coverageExplicitPartial':True,
                     'completeMetropole':False, 'buildInputs':{'bootstrapSourceSHA256':'a'*64},
                     'tiles':[{'cellId':'V52-MC-33','vector':vector,
                               'terrain':None,'surfaces':None,'navigation':None}]})
    (Path(directory)/'manifest.json').write_bytes(B.canonical(manifest))
    return manifest


class EmbeddedAndAssetTests(unittest.TestCase):
    def test_gzip_blob_requires_exact_size_and_sha(self):
        value = {'source':'QA fixture','points':[1,2,3]}
        result, sha = B.embedded(blob(value), 'fixture')
        self.assertEqual(result, value)
        self.assertEqual(sha, hashlib.sha256(B.canonical(value)).hexdigest())
        for html in (blob(value, size=1), blob(value, size=0), blob(value, size=B.MAX_BLOB+1),
                     blob(value, sha='0'*64)):
            with self.subTest(html=html[:130]), self.assertRaises(ValueError):
                B.embedded(html, 'fixture')

    def test_missing_duplicate_truncated_and_plain_sources(self):
        html = blob({'fixture':True})
        for text in ('', html+html):
            with self.assertRaisesRegex(ValueError, 'absente ou dupliquée'):
                B.embedded(text, 'fixture')
        with self.assertRaises((ValueError, OSError, EOFError)):
            B.embedded(re.sub(r'>[^<]+</script>', '>AAAA</script>', html), 'fixture')
        plain = '<script id="fixture" type="application/json">{"quality":"declared"}</script>'
        value, sha = B.embedded(plain, 'fixture')
        self.assertEqual(value, {'quality':'declared'})
        self.assertEqual(sha, B.digest(b'{"quality":"declared"}'))
        with mock.patch.object(B, 'MAX_BLOB', 5), self.assertRaisesRegex(ValueError, 'hors budget'):
            B.embedded(plain, 'fixture')

    def test_assets_are_deterministic_and_identical_outputs_are_not_rewritten(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            first = B.asset(root, 'tiles/source.json.gz', {'b':[2,3], 'a':'échantillon'})
            path = root/first['path']
            original = path.read_bytes()
            self.assertEqual(len(original), first['bytes'])
            self.assertEqual(B.digest(original), first['sha256'])
            self.assertEqual(gzip.decompress(original), B.canonical({'a':'échantillon','b':[2,3]}))
            self.assertEqual(original[4:8], b'\0\0\0\0', 'Gzip time must not change the release hash.')
            os.utime(path, ns=(1_000_000_000,1_000_000_000))
            before = path.stat().st_mtime_ns
            second = B.asset(root, 'tiles/source.json.gz', {'a':'échantillon','b':[2,3]})
            self.assertEqual(first, second)
            self.assertEqual(path.stat().st_mtime_ns, before)

    def test_output_paths_cannot_escape_or_disagree_with_the_browser_contract(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)/'world';root.mkdir()
            for relative in ('../outside.gz', '/absolute.gz', 'tiles//file.gz', 'tiles/./file.gz',
                             'tiles\\file.gz', 'C:/file.gz', '.hidden.gz', 'tiles/%2e%2e/file.gz'):
                with self.subTest(path=relative), self.assertRaises(ValueError):
                    B.asset(root, relative, {})
            outside = Path(name)/'outside';outside.mkdir()
            (root/'tiles').symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                B.asset(root, 'tiles/escaped.gz', {})
            self.assertFalse((outside/'escaped.gz').exists())

    def test_nonfinite_asset_data_is_refused_before_publication(self):
        with tempfile.TemporaryDirectory() as name:
            with self.assertRaises(ValueError):
                B.asset(name, 'tiles/invalid.gz', {'height':float('nan')})
            self.assertFalse((Path(name)/'tiles/invalid.gz').exists())

    def test_preexisting_temporary_symlinks_cannot_redirect_asset_writes(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)/'world'; (root/'tiles').mkdir(parents=True)
            for dangling in (False, True):
                with self.subTest(dangling=dangling):
                    suffix = 'dangling' if dangling else 'existing'
                    outside = Path(name)/(suffix + '.txt')
                    if not dangling:
                        outside.write_bytes(b'outside must stay untouched')
                    relative = f'tiles/{suffix}.json.gz'
                    poisoned = root/(relative + '.tmp')
                    poisoned.symlink_to(outside)
                    descriptor = B.asset(root, relative, {'audit':'source'})
                    published = root/relative
                    self.assertFalse(published.is_symlink())
                    self.assertEqual(gzip.decompress(published.read_bytes()), B.canonical({'audit':'source'}))
                    self.assertEqual(B.digest(published.read_bytes()), descriptor['sha256'])
                    self.assertTrue(poisoned.is_symlink())
                    if dangling:
                        self.assertFalse(outside.exists())
                    else:
                        self.assertEqual(outside.read_bytes(), b'outside must stay untouched')

    def test_failed_atomic_publication_preserves_previous_asset_and_cleans_temporary(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            destination = root/'source.json.gz'
            destination.write_bytes(b'previous verified asset')
            with mock.patch.object(Path, 'replace', side_effect=OSError('publication refused')):
                with self.assertRaisesRegex(OSError, 'publication refused'):
                    B._write(destination, b'replacement')
            self.assertEqual(destination.read_bytes(), b'previous verified asset')
            self.assertEqual(list(root.iterdir()), [destination])


class LocalNavigationTests(unittest.TestCase):
    def graph(self):
        return {'schema':'soma/navigation-source/1',
                'sourcePackSHA256':'a'*64,'sourcePbfSHA256':'b'*64,
                'nodes':[['unused',0,0],['native-A',10,0],['native-B',20,0],
                         ['native-C',30,0],['native-D',20,10]],
                'edges':[[1,2,'way-A',10,15,0,['cell-A','cell-B'],91],
                         [2,3,'way-B',10,15,0,['cell-B'],92],
                         [2,4,'way-C',10,7,1,['cell-A'],93]],
                'ways':{'way-A':{'name':'A'},'way-B':{'name':'B'},'way-C':{'name':'C'}},
                'turns':[{'from':'way-A','via':'native-B','to':'way-C','kind':'no_left_turn'},
                         {'from':'way-A','via':'native-B','to':'way-B','kind':'only_straight_on'}],
                'cellHashes':{'cell-A':'c'*64,'cell-B':'d'*64}}

    def test_native_nodes_edge_flags_and_cross_cell_hashes_survive_local_remapping(self):
        graph = self.graph();before = deepcopy(graph)
        local = B.local_navigation(graph, 'cell-A')
        self.assertEqual(graph, before, 'Bootstrap must not mutate the original full graph.')
        self.assertEqual(local['nodes'], [graph['nodes'][i] for i in (1,2,4)])
        self.assertEqual(local['edges'], [[0,1,*graph['edges'][0][2:]], [1,2,*graph['edges'][2][2:]]])
        self.assertEqual(local['cellHashes'], graph['cellHashes'],
                         'A cross-cell edge still depends on every source cell it traverses.')
        self.assertEqual(local['tileCellId'], 'cell-A')
        self.assertTrue(local['tileSubset'])

    def test_only_turn_toward_an_outside_edge_cannot_become_an_illegal_local_exit(self):
        graph = self.graph();graph['turns'] = [graph['turns'][1]]
        local = B.local_navigation(graph, 'cell-A')
        self.assertIn(graph['turns'][0], local['turns'])
        self.assertIn('way-B', local['ways'], 'Restriction targets need metadata even without a local edge.')
        self.assertEqual(len(local['edges']), 2)
        node = local['nodes'].index(['native-B',20,0])
        # The actual JS router verifies the semantic effect, not only that a rule exists.
        source = (ROOT/'SOMA_MASSILIA_URBAIN_v0_69.html').read_text(encoding='utf-8')
        script = re.search(r'<script\b[^>]*\bid="soma-v63-nav-core"[^>]*>(.*?)</script>', source, re.S)[1]
        code = "const vm=require('node:vm'),fs=require('node:fs');const input=JSON.parse(fs.readFileSync(0,'utf8'));vm.runInThisContext(input.source);const K=globalThis.__SOMA_NAV63_CORE__;K.validate(input.graph);const r=K.createRouter(input.graph);if(r.turnAllowed(input.node,0,1,'car'))throw Error('Illegal turn became allowed');"
        result = subprocess.run(['node','-e',code], input=json.dumps({'source':script,'graph':local,'node':node}),
                                text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode,0,result.stderr)


class VerifyWorldTests(unittest.TestCase):
    def test_asset_tampering_and_expected_input_mismatch_are_detected(self):
        with tempfile.TemporaryDirectory() as name:
            manifest = tiny_world(name)
            self.assertEqual(B.verify_world(name), manifest)
            with self.assertRaisesRegex(ValueError, 'reconstruction'):
                B.verify_world(name, {'bootstrapSourceSHA256':'different'})
            path = Path(name)/manifest['tiles'][0]['vector']['path']
            path.write_bytes(path.read_bytes()+b'corrupted')
            with self.assertRaisesRegex(ValueError, 'Asset modifié'):
                B.verify_world(name)

    def test_manifest_content_seal_detects_changes_before_asset_reads(self):
        with tempfile.TemporaryDirectory() as name:
            manifest = tiny_world(name)
            manifest['completeMetropole'] = True
            (Path(name)/'manifest.json').write_bytes(B.canonical(manifest))
            with self.assertRaises(ValueError):
                B.verify_world(name)
            manifest['completeMetropole'] = False;manifest['unverifiedClaim'] = 'changed'
            (Path(name)/'manifest.json').write_bytes(B.canonical(manifest))
            with self.assertRaisesRegex(ValueError, 'manifeste territorial a été modifié'):
                B.verify_world(name)

    def test_even_a_resealed_manifest_cannot_reference_outside_assets(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)/'world';root.mkdir()
            manifest = tiny_world(root)
            outside = Path(name)/'outside.gz';outside.write_bytes(b'outside')
            manifest['tiles'][0]['vector'] = {'path':'../outside.gz','bytes':7,'sha256':B.digest(b'outside'),'encoding':'gzip-json'}
            (root/'manifest.json').write_bytes(B.canonical(seal(manifest)))
            with self.assertRaisesRegex(ValueError, 'hors répertoire'):
                B.verify_world(root)


class BoundaryReferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)/'reference'; self.root.mkdir()
        self.path = self.root/'territory.json'
        shutil.copyfile(ROOT/'data/v69/territory.json', self.path)
        shutil.copytree(ROOT/'data/v69/acquisition', self.root/'acquisition')
        self.reference = json.loads(self.path.read_bytes())

    def tearDown(self):
        self.temp.cleanup()

    def save(self):
        self.path.write_bytes(B.canonical(self.reference))

    def repin(self, descriptor, value):
        raw = B.canonical(value)
        (self.root/descriptor['path']).write_bytes(raw)
        descriptor.update(bytes=len(raw), sha256=B.digest(raw))

    def test_actual_boundary_and_receipts_validate_after_reference_is_moved(self):
        territory, _, boundary_sha = B.load_territory_reference(self.path)
        self.assertEqual(boundary_sha, self.reference['boundary']['sha256'])
        self.assertEqual(len(territory['communes']), 92)
        self.assertIsNone(territory['boundary']['vintage'])
        self.assertEqual(territory['boundary']['vintageStatus'], 'not-stated-by-service')

    def test_all_boundary_files_are_pinned_even_when_the_reference_is_unchanged(self):
        boundary = self.reference['boundary']
        for descriptor in (boundary, boundary['source'], boundary['rawReceipt'], boundary['validationReceipt']):
            with self.subTest(path=descriptor['path']):
                path = self.root/descriptor['path']; original = path.read_bytes()
                path.write_bytes(original+b' ')
                try:
                    with self.assertRaisesRegex(ValueError, 'Contour administratif'):
                        B.load_territory_reference(self.path)
                finally:
                    path.write_bytes(original)

    def test_boundary_paths_reject_traversal_and_external_symlinks(self):
        boundary = self.reference['boundary']; original = boundary['path']
        for path in ('../outside.geojson', '/tmp/outside.geojson', 'acquisition/../outside.geojson'):
            boundary['path'] = path; self.save()
            with self.assertRaisesRegex(ValueError, 'chemin relatif'):
                B.load_territory_reference(self.path)
        boundary['path'] = original
        outside = Path(self.temp.name)/'outside.geojson'; outside.write_bytes((self.root/original).read_bytes())
        (self.root/'escaped.geojson').symlink_to(outside)
        boundary['path'] = 'escaped.geojson'; self.save()
        with self.assertRaisesRegex(ValueError, 'hors répertoire'):
            B.load_territory_reference(self.path)

    def test_resealed_wrong_source_codes_are_not_hidden_by_valid_receipt_hashes(self):
        boundary = self.reference['boundary']
        source = json.loads((self.root/boundary['source']['path']).read_bytes())
        source['features'][0]['properties']['code'] = '99999'; self.repin(boundary['source'], source)
        receipt = json.loads((self.root/boundary['rawReceipt']['path']).read_bytes())
        receipt.update(sha256=boundary['source']['sha256'], bytes=boundary['source']['bytes']); self.repin(boundary['rawReceipt'], receipt)
        union = json.loads((self.root/boundary['path']).read_bytes())
        union['features'][0]['properties']['sourceSHA256'] = boundary['source']['sha256']; self.repin(boundary, union)
        proof = json.loads((self.root/boundary['validationReceipt']['path']).read_bytes())
        proof.update(source=receipt, boundarySHA256=boundary['sha256'], boundaryBytes=boundary['bytes'])
        self.repin(boundary['validationReceipt'], proof); self.save()
        with self.assertRaisesRegex(ValueError, 'communes sources différentes'):
            B.load_territory_reference(self.path)

    def test_resealed_invalid_gis_receipt_and_forged_http_status_are_refused(self):
        boundary = self.reference['boundary']
        proof = json.loads((self.root/boundary['validationReceipt']['path']).read_bytes())
        for changes in ({'unionValid':False}, {'geometryRepairApplied':True}, {'communeCodes':['99999']*92}):
            self.repin(boundary['validationReceipt'], {**proof, **changes}); self.save()
            with self.assertRaisesRegex(ValueError, 'reçu de validité'):
                B.load_territory_reference(self.path)
        self.repin(boundary['validationReceipt'], proof)
        receipt = json.loads((self.root/boundary['rawReceipt']['path']).read_bytes())
        receipt['httpStatus'] = 403; self.repin(boundary['rawReceipt'], receipt); self.save()
        with self.assertRaisesRegex(ValueError, 'reçu HTTP'):
            B.load_territory_reference(self.path)

    def test_missing_boundary_remains_explicitly_unknown(self):
        self.reference['boundary'] = None; self.save()
        self.assertIsNone(B.load_territory_reference(self.path)[2])


class RealBootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html_path = ROOT/'SOMA_MASSILIA_URBAIN_v0_69.html'
        if not cls.html_path.is_file():
            raise RuntimeError('Build the actual v0.69 HTML before running its bootstrap regression.')
        cls.html = cls.html_path.read_text(encoding='utf-8')
        cls.temp = tempfile.TemporaryDirectory(prefix='massilia-bootstrap-qa-')
        cls.output = Path(cls.temp.name)/'world'
        cls.terrain = ROOT/'data/v58/terrain.ign.json'
        cls.territory = ROOT/'data/v69/territory.json'
        cls.manifest = B.prepare_world(cls.html, cls.output, cls.terrain, cls.territory)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_real_168_cell_export_has_verified_assets_and_explicit_partial_coverage(self):
        manifest = B.verify_world(self.output)
        self.assertEqual(len(manifest['tiles']),168)
        self.assertEqual(manifest['coverage']['vectorCells'],168)
        self.assertEqual(manifest['coverage']['newGeographicCells'],0)
        self.assertFalse(manifest['completeMetropole'])
        self.assertTrue(manifest['coverageExplicitPartial'])
        self.assertEqual(manifest['target']['communeCount'],92)
        self.assertEqual(manifest['target']['boundarySHA256'],json.loads(self.territory.read_bytes())['boundary']['sha256'])
        self.assertIsNone(manifest['coverage']['administrativeCoverageRatio'])
        self.assertEqual(manifest['buildInputs']['bootstrapSourceSHA256'], B.digest(Path(B.__file__).read_bytes()))
        self.assertEqual(manifest['manifestContentSHA256'], B.digest(B.canonical({k:v for k,v in manifest.items() if k!='manifestContentSHA256'})))

    def test_measured_eave_sidecars_bind_every_reference_to_its_actual_source_cell(self):
        identities=set()
        for tile in self.manifest['tiles']:
            record=json.loads(gzip.decompress((self.output/tile['vector']['path']).read_bytes()))
            surfaces=json.loads(gzip.decompress((self.output/tile['surfaces']['path']).read_bytes()))
            features={f['properties']['canonical_id']:f for f in record['featureCollection']['features']}
            for identity,row in surfaces['buildings'].items():
                if row.get('heightKind')!='eaves':
                    continue
                identities.add(identity)
                self.assertEqual(row['sourceSHA256'],record['sourceReceipt']['sha256'])
                self.assertEqual(row['cellContentSHA256'],record['contentSHA256'])
                self.assertEqual(row['geometrySHA256'],features[identity]['properties']['soma:geometry_sha256'])
                self.assertEqual(row['proofSHA256'],self.manifest['heightReferences']['proofSHA256'])
                self.assertFalse(row['roofSurveyed'])
                self.assertGreater(row['height'],0)
        self.assertEqual(len(identities),14279)

    def test_valid_cache_is_verified_and_reused_without_redecoding_or_regenerating(self):
        before = {path.relative_to(self.output):path.stat().st_mtime_ns for path in self.output.rglob('*') if path.is_file()}
        with (mock.patch.object(B,'embedded',side_effect=AssertionError('A verified cache must not decode the full source again.')),
              mock.patch.object(B,'asset',side_effect=AssertionError('A verified cache must not regenerate assets.'))):
            cached = B.prepare_world(self.html,self.output,self.terrain,self.territory)
        after = {path.relative_to(self.output):path.stat().st_mtime_ns for path in self.output.rglob('*') if path.is_file()}
        self.assertEqual(cached,self.manifest)
        self.assertEqual(before,after)

    def test_boundary_file_drift_is_refused_before_a_previously_verified_cache_is_reused(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            shutil.copyfile(self.territory,root/'territory.json')
            shutil.copytree(self.territory.parent/'acquisition',root/'acquisition')
            boundary = json.loads((root/'territory.json').read_bytes())['boundary']
            source = root/boundary['source']['path']; source.write_bytes(source.read_bytes()+b' ')
            before = (self.output/'manifest.json').read_bytes()
            with (mock.patch.object(B,'embedded',side_effect=AssertionError('Must validate before decoding')),
                  self.assertRaisesRegex(ValueError,'Contour administratif')):
                B.prepare_world(self.html,self.output,self.terrain,root/'territory.json')
            self.assertEqual((self.output/'manifest.json').read_bytes(),before)

    def test_a_changed_bootstrap_source_stamp_invalidates_the_cache(self):
        path = self.output/'manifest.json';original = path.read_bytes()
        changed = json.loads(original);changed['buildInputs']['bootstrapSourceSHA256'] = '0'*64
        path.write_bytes(B.canonical(seal(changed)))
        try:
            with (mock.patch.object(B,'embedded',side_effect=RuntimeError('source decode required')),
                  self.assertRaisesRegex(RuntimeError,'source decode required')):
                B.prepare_world(self.html,self.output,self.terrain,self.territory)
        finally:
            path.write_bytes(original)

    def test_corrupt_cached_assets_are_not_silently_accepted(self):
        path = self.output/self.manifest['tiles'][0]['vector']['path'];original = path.read_bytes()
        path.write_bytes(original+b'corrupt')
        try:
            with (mock.patch.object(B,'embedded',side_effect=RuntimeError('rebuild after verification failure')),
                  self.assertRaisesRegex(RuntimeError,'verification failure')):
                B.prepare_world(self.html,self.output,self.terrain,self.territory)
        finally:
            path.write_bytes(original)

    def test_real_manifest_and_all_local_graphs_pass_the_actual_javascript_cores(self):
        if shutil.which('node') is None:
            self.fail('Node.js is required for the actual streaming/navigation interoperability check.')
        nav_source = re.search(r'<script\b[^>]*\bid="soma-v63-nav-core"[^>]*>(.*?)</script>',self.html,re.S)[1]
        code = r"""
const fs=require('node:fs'),path=require('node:path'),zlib=require('node:zlib'),vm=require('node:vm');
const input=JSON.parse(fs.readFileSync(0,'utf8')),K=require(input.core);
vm.runInThisContext(input.nav);const N=globalThis.__SOMA_NAV63_CORE__;
const manifest=JSON.parse(fs.readFileSync(path.join(input.directory,'manifest.json')));
K.validateManifest(manifest);
const graphs=[];
for(const tile of manifest.tiles){const g=JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(input.directory,tile.navigation.path))));N.validate(g);graphs.push(g);}
const store=K.createTileStore({manifest,fetchBytes:async file=>fs.readFileSync(path.join(input.directory,file)),
 validators:{navigation:g=>{N.validate(g);return g;}}});
(async()=>{
 const selection=[manifest.tiles[0],manifest.tiles.find(t=>t.cellId==='V52-MC-33'),manifest.tiles.at(-1)];
 for(const tile of selection){const entry=await store.load(tile.cellId,{require3D:true});if(entry.readyFor3D)throw Error('No physical activation gate was supplied');if(entry.missingLayers.length)throw Error('Missing prepared data');}
 const g=graphs.find(g=>g.edges.some(e=>(e[4]&3)&&Math.hypot(g.nodes[e[0]][1]-g.nodes[e[1]][1],g.nodes[e[0]][2]-g.nodes[e[1]][2])>1));
 const e=g.edges.find(e=>(e[4]&3)&&Math.hypot(g.nodes[e[0]][1]-g.nodes[e[1]][1],g.nodes[e[0]][2]-g.nodes[e[1]][2])>1);
 const a=g.nodes[e[(e[4]&1)?0:1]],b=g.nodes[e[(e[4]&1)?1:0]];
 const route=N.createRouter(g).route({e:a[1],n:a[2]},{e:b[1],n:b[2]},{mode:'foot',maxSnap:1});
 if(!route.ok||route.lengthMeters<=0)throw Error('Actual native-node route failed');
 process.stdout.write(JSON.stringify({graphs:graphs.length,loaded:selection.length,routeMeters:route.lengthMeters}));
})().catch(error=>{console.error(error);process.exitCode=1});
"""
        result = subprocess.run(['node','-e',code],input=json.dumps({'directory':str(self.output),
                                'core':str(ROOT/'src/v69/streaming-core.js'),'nav':nav_source}),
                                text=True,capture_output=True,check=False)
        self.assertEqual(result.returncode,0,result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['graphs'],168)
        self.assertEqual(report['loaded'],3)
        self.assertGreater(report['routeMeters'],0)


if __name__ == '__main__':
    unittest.main()
