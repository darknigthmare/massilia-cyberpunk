"""Execute the actual patched terrain runtime, not a replacement sampler."""
import copy
import importlib.util
import json
from pathlib import Path
import re
import struct
import subprocess
import unittest

GAME = Path(__file__).resolve().parents[2]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P = load_module('terrain_runtime_patch69', GAME / 'tools/v69_terrain.py')
T = load_module('terrain_tiles_for_runtime69', GAME / 'tools/v69/terrain_tiles.py')
HTML = (GAME / 'baseline/v66.html').read_text()
CORE = re.search(r'<script\b[^>]*id="soma-v56-terrain-core"[^>]*>(.*?)</script>', HTML, re.S)[1]
SIGHT_CORE = re.search(r'<script\b[^>]*id="soma-v61-sight-core"[^>]*>(.*?)</script>', HTML, re.S)[1]
CONTACT_CORE = re.search(r'<script\b[^>]*id="soma-v57-core"[^>]*>(.*?)</script>', HTML, re.S)[1]
TRANSFER_CORE = re.search(r'<script\b[^>]*id="soma-v55-core"[^>]*>(.*?)</script>', HTML, re.S)[1]
CONTACT_RUNTIME = re.search(r'<script\b[^>]*id="soma-v57-runtime"[^>]*>(.*?)</script>', HTML, re.S)[1]
PERF_RUNTIME = re.search(r'<script\b[^>]*id="soma-v65-performance-runtime"[^>]*>(.*?)</script>', HTML, re.S)[1]
RUNTIME = re.search(r'<script\b[^>]*id="soma-v56-terrain-runtime"[^>]*>(.*?)</script>', HTML, re.S)[1]
del HTML
REAL_PACK = json.loads((GAME / 'data/v58/terrain.ign.json').read_text())
PATCHED = P.patch_terrain_runtime(RUNTIME)


def pack(bounds=(1000, 2000, 1250, 2250), step=25, offset=0, missing=()):
    header = T._tile_header(bounds, step)
    count = header['rows'] * header['cols']
    data, mask = bytearray(count * 4), bytearray([1] * count)
    for row in range(header['rows']):
        for col in range(header['cols']):
            e, n = header['x0'] + col * step, header['n0'] - row * step
            struct.pack_into('<f', data, (row * header['cols'] + col) * 4,
                             10 + (e - 1000) * .01 + (n - 2000) * .02 + offset)
    for index in missing:
        mask[index] = 0
    return T._pack(header, bytes(data), bytes(mask), {'truth': 'fixture',
                   'sourceGridSHA256': 'a' * 64, 'testOnly': True})


BOOTSTRAP = r"""
globalThis.window=globalThis;
window.__SOMA_TERRAIN56_QA__=true;
const RECORDS=new Map(),ZONES=new Map(),WORLD={zones:{}};
const hud={hidden:true,textContent:''};
const document={getElementById(id){return id==='soma-v56-terrain'?{textContent:JSON.stringify(input.real)}:id==='terrain56-hud'?hud:null},querySelector(){return null},body:{appendChild(){},classList:{add(){},toggle(){}}},addEventListener(){},hidden:false};
const indexedDB={open(){throw Error('No IndexedDB in the external-system fixture')}};
const setTimeout=()=>0;
window.__SOMA_V52__={records:()=>new Map(RECORDS),zones:()=>new Map(ZONES),open(){}};
window.__SOMA_V55__={ready:true,remember(){}};
window.__SOMA_V58_CORE__={poseState:value=>value};
window.__SOMA_FIDELITY59__={heightReference:()=>null};
window.__SOMA_FIDELITY59_CORE__={measure:value=>Number(value)||null};
window.__SOMA_V53_CORE__={inPolygon:()=>false};
window.__SOMA__={};
let zone=null,paused=false,state={driving:null};
const camera={x:0,y:1.72,z:0,yaw:0,pitch:0};
let baseEnters=0;
class Geo{
 constructor(){this.v=[];this.__v56=window.__SOMA_TERRAIN56__?.geometryScope||null;}
 tri(a,b,c,n,col){this.v.push({a,b,c,n,col});}
 quad(a,b,c,d,n,col){this.tri(a,b,c,n,col);this.tri(a,c,d,n,col);}
}
function buildZone(z){const g=new Geo();window.__SOMA_TERRAIN56__.buildTerrain(z,g,[.3,.3,.3]);z.static=g.v;return z;}
function blocked(){return false;}
function vehicleBlockedAt(){return false;}
function vehicleOverlapsAt(){return false;}
function roadAt(){return null;}
function integrateVehicle(){}
function move(){}
function enterZone(id,_,pose){baseEnters++;zone=WORLD.zones[id];if(pose)Object.assign(camera,pose);return !!zone;}
function actorGeo(){}
function animalGeo(){}
function robotGeo(){}
function roadblockGeo(){}
function vehicleGeo(){}
function update(){}
function openModal(){}
function closeModals(){return true;}
function applySettings(){}
function isFlyingVehicleKind(){return false;}
function isWaterVehicleKind(){return false;}
function vehicleSpec(){return {length:4,width:2,cameraHeight:1.4};}
function makeZone(id,bounds,features=[]){
 const record={cellId:id,boundsL93:bounds,v53Validated:true,contentSHA256:'known-record',sourceReceipt:{sha256:'b'.repeat(64)},featureCollection:{features}};
 const z={id:'geo:'+id,v52CellId:id,v52GridX:0,v52GridY:0,v52District:true,v50Record:record,roads:[],vehicles:[],colliders:[],spawn:{x:0,z:0,yaw:0},static:null};
 RECORDS.set(id,record);ZONES.set(id,z);WORLD.zones[z.id]=z;return z;
}
"""

NODE = r"""
const fs=require('node:fs'),vm=require('node:vm');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const context=vm.createContext({input,Buffer,TextEncoder,console,performance});
vm.runInContext(input.bootstrap,context);
vm.runInContext(input.core,context,{filename:'actual-terrain-core56.js'});
vm.runInContext(input.sight,context,{filename:'actual-sight-core61.js'});
vm.runInContext(input.runtime,context,{filename:'actual-terrain-runtime69.js'});
Promise.resolve().then(()=>{
 for(const script of input.post)vm.runInContext(script,context,{filename:'actual-dependent-runtime.js'});
 const result=vm.runInContext(input.actions,context,{filename:'test-actions.js'});
 return Promise.resolve(result);
}).then(result=>process.stdout.write(JSON.stringify(result))).catch(error=>{console.error(error.stack);process.exitCode=1});
"""


def execute(actions, packs=None, runtime=PATCHED, qa=True, post=()):
    bootstrap = BOOTSTRAP if qa else BOOTSTRAP.replace('window.__SOMA_TERRAIN56_QA__=true;', 'window.__SOMA_TERRAIN56_QA__=false;')
    fixture = {'bootstrap': bootstrap, 'core': CORE, 'sight': SIGHT_CORE, 'runtime': runtime,
               'real': REAL_PACK, 'packs': packs or [], 'actions': actions, 'post': list(post)}
    result = subprocess.run(['node', '-e', NODE], input=json.dumps(fixture),
                            text=True, capture_output=True, timeout=45)
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


class TerrainRuntimeTests(unittest.TestCase):
    def test_patch_refuses_drift_duplicate_anchors_and_double_application(self):
        self.assertEqual(PATCHED.count(P._MARKER), 1)
        self.assertEqual(PATCHED.count('anchors.get(String(id))'), 2)
        for source in [PATCHED, RUNTIME.replace('function anchorIndex(){', 'function other(){'),
                       RUNTIME + '\nconst activeFor=z=>!!grid&&isReal(z);']:
            with self.assertRaises(ValueError): P.patch_terrain_runtime(source)

    def test_original_real_grid_samples_vehicle_pose_and_camera_stay_identical(self):
        actions = """(()=>{
          const bounds=[892826.6480966414,6247149.566415883,893076.6480966414,6247399.566415883];
          const z=makeZone('legacy',bounds);zone=z;camera.x=20;camera.z=-10;
          const T=window.__SOMA_TERRAIN56__,vehicle={x:20,z:-10,heading:.4,kind:'car'};
          T.poseCamera();const pose=T.poseVehicle(vehicle,z);
          return {h:T.ground(z,20,-10),slope:T.slope(z,20,-10),cameraY:camera.y,
            pose:{height:pose.height,up:pose.up,right:pose.right,forward:pose.forward},sha:T.pack.sha256};
        })()"""
        original = execute(actions, runtime=RUNTIME)
        current = execute(actions)
        self.assertEqual(current, original)
        self.assertEqual(current['sha'], REAL_PACK['sha256'])

    def test_two_tiles_keep_node_halos_heights_and_normals_consistent(self):
        a, b = pack(), pack((1250, 2000, 1500, 2250))
        result = execute("""(()=>{
          const T=window.__SOMA_TERRAIN56__,V=T.v69;
          V.attach('a',input.packs[0],[1000,2000,1250,2250]);
          V.attach('b',input.packs[1],[1250,2000,1500,2250]);
          const a=makeZone('a',[1000,2000,1250,2250]),b=makeZone('b',[1250,2000,1500,2250]);
          const ga=new Geo(),gb=new Geo();T.buildTerrain(a,ga,[.2,.2,.2]);T.buildTerrain(b,gb,[.2,.2,.2]);
          return {edge:[T.ground(a,125,0),T.ground(b,-125,0)],
            gradients:[T.slope(a,125,0),T.slope(b,-125,0)],
            normals:[ga.v[0].n,gb.v[0].n],triangles:[ga.v.length,gb.v.length],
            hashes:[a.v56Build.terrainSHA256,b.v56Build.terrainSHA256],baseline:T.pack.sha256,snapshot:V.snapshot()};
        })()""", [a, b])
        self.assertEqual(result['edge'][0], result['edge'][1])
        for key in ('e', 'south'):
            self.assertAlmostEqual(result['gradients'][0][key], result['gradients'][1][key], places=12)
        self.assertEqual(result['normals'][0], result['normals'][1])
        self.assertEqual(result['triangles'], [200, 200])
        self.assertEqual(result['hashes'], [a['sha256'], b['sha256']])
        self.assertEqual(result['baseline'], REAL_PACK['sha256'])
        self.assertEqual(result['snapshot']['attachedTiles'], 2)

    def test_incompatible_seams_and_lod_steps_reject_without_partial_admission(self):
        for candidate, expected in [(pack((1250, 2000, 1500, 2250), offset=.04), '3 cm'),
                                    (pack((1250, 2000, 1500, 2250), step=5), 'LOD')]:
            with self.subTest(expected=expected):
                result = execute("""(()=>{const V=window.__SOMA_TERRAIN56__.v69;
                  V.attach('a',input.packs[0],[1000,2000,1250,2250]);
                  const before=V.revision;let error=null;
                  try{V.attach('b',input.packs[1],[1250,2000,1500,2250])}catch(e){error=e.message}
                  return {error,size:V.snapshot().attachedTiles,unchanged:V.revision===before};})()""", [pack(), candidate])
                self.assertIn(expected, result['error'])
                self.assertEqual(result['size'], 1)
                self.assertTrue(result['unchanged'])

    def test_halo_conflicts_are_caught_even_when_shared_edge_nodes_agree(self):
        candidate = pack((1250, 2000, 1500, 2250))
        grid = T.validate_grid(candidate)
        data = bytearray(grid.data)
        # Only B's west halo differs; its useful shared edge (col1) is intact.
        struct.pack_into('<f', data, (6 * grid.cols) * 4, grid.node(0, 6) + .04)
        candidate = T._pack(grid.header, bytes(data), grid.mask, candidate['source'])
        result = execute("""(()=>{const V=window.__SOMA_TERRAIN56__.v69;
          V.attach('a',input.packs[0],[1000,2000,1250,2250]);
          try{V.attach('b',input.packs[1],[1250,2000,1500,2250]);return false}catch(e){return e.message}})()""", [pack(), candidate])
        self.assertIn('halo', result)

    def test_nodata_in_attached_tile_never_falls_through_to_legacy_ground(self):
        original = T.validate_grid(REAL_PACK)
        bounds = [892826.6480966414, 6247149.566415883, 893076.6480966414, 6247399.566415883]
        tile = T.tile_from_grid(original, bounds)
        g = T.validate_grid(tile); mask = bytearray(g.mask); mask[6 * g.cols + 6] = 0
        tile = T._pack(g.header, g.data, bytes(mask), {**tile['source'], 'truth': 'fixture'})
        result = execute("""(()=>{
          const T=window.__SOMA_TERRAIN56__,V=T.v69,b=JSON.parse(input.packs[0].gridHeader).boundsL93;
          V.attach('hole',input.packs[0],b);const z=makeZone('hole',b);zone=z;
          const missing=T.ground(z,0,0),collision=blocked(z,0,0,.38),before=V.revision;
          let refusal=null;try{V.detach(['hole'])}catch(e){refusal=e.message}
          zone=null;const removed=V.detach(['hole']);
          return {missing,collision,refusal,removed,restored:T.ground(z,0,0),revisionChanged:V.revision>before};
        })()""", [tile])
        self.assertIsNone(result['missing'])
        self.assertTrue(result['collision'])
        self.assertIn('actif', result['refusal'])
        self.assertEqual(result['removed'], 1)
        self.assertIsNotNone(result['restored'])
        self.assertTrue(result['revisionChanged'])

    def test_unknown_real_cell_cannot_enter_with_a_flat_fallback(self):
        result = execute("""(()=>{const z=makeZone('absent',[1000,2000,1250,2250]);
          return {entered:enterZone(z.id),baseEnters,active:window.__SOMA_TERRAIN56__.activeFor(z)};})()""")
        self.assertEqual(result, {'entered': False, 'baseEnters': 0, 'active': False})

    def test_registering_records_after_attach_refreshes_global_building_datums(self):
        result = execute("""(()=>{
          const T=window.__SOMA_TERRAIN56__,V=T.v69;V.attach('a',input.packs[0],[1000,2000,1250,2250]);
          const source={id:'building',properties:{'soma:layer':'buildings',canonical_id:'building',
             'soma:mesh53':[{ringsL93:[[[1050,2200],[1060,2200],[1060,2190],[1050,2190]]]}]}};
          const z=makeZone('a',[1000,2000,1250,2250],[source]);
          const first=T.buildingDatum(z,{},'building');
          const next=JSON.parse(JSON.stringify(z.v50Record));
          next.featureCollection.features[0].properties['soma:mesh53'][0].ringsL93[0].push([1070,2220]);
          RECORDS.set('a',next);z.v50Record=next;
          const second=T.buildingDatum(z,{},'building');
          return {first,second};
        })()""", [pack()])
        self.assertGreater(result['second']['max'], result['first']['max'])
        self.assertAlmostEqual(result['first']['base'], 14.6, places=4)
        self.assertAlmostEqual(result['second']['base'], 15.1, places=4)

    def test_actual_surface_triangulation_uses_the_tile_and_matches_ground(self):
        result = execute("""(()=>{
          const T=window.__SOMA_TERRAIN56__;T.v69.attach('a',input.packs[0],[1000,2000,1250,2250]);
          const z=makeZone('a',[1000,2000,1250,2250]),g=new Geo();
          g.__v56={kind:'surface',zone:z};
          g.tri([-20,.035,-20],[-20,.035,45],[45,.035,-20],[0,1,0],[.2,.2,.2]);
          return {triangles:g.v.length,match:g.v.every(t=>[t.a,t.b,t.c].every(p=>Math.abs(p[1]-(T.ground(z,p[0],p[2])+.035))<1e-8)),
            normals:g.v.every(t=>t.n[1]>0)};
        })()""", [pack()])
        self.assertGreater(result['triangles'], 1)
        self.assertTrue(result['match'])
        self.assertTrue(result['normals'])

    def test_attach_reuse_revision_clear_and_active_protection_are_atomic(self):
        result = execute("""(()=>{const V=window.__SOMA_TERRAIN56__.v69;
          const start=V.revision;V.attach('a',input.packs[0],[1000,2000,1250,2250]);
          const admitted=V.revision,reused=V.attach('a',input.packs[0],[1000,2000,1250,2250]);
          const same=V.revision===admitted;zone=makeZone('a',[1000,2000,1250,2250]);
          let blocked=false;try{V.clear()}catch{blocked=true}const unchanged=V.snapshot().attachedTiles===1;
          zone=null;const removed=V.clear();return {start,admitted,reused:reused.reused,same,blocked,unchanged,removed,end:V.revision};})()""", [pack()])
        self.assertEqual(result['admitted'], result['start'] + 1)
        self.assertTrue(all(result[key] for key in ('reused', 'same', 'blocked', 'unchanged')))
        self.assertEqual(result['removed'], 1)
        self.assertEqual(result['end'], result['admitted'] + 1)

    def test_fixture_missing_provenance_and_method_override_are_rejected(self):
        with self.assertRaisesRegex(AssertionError, 'fixture'):
            execute("window.__SOMA_TERRAIN56__.v69.attach('a',input.packs[0],[1000,2000,1250,2250])", [pack()], qa=False)
        invalid = copy.deepcopy(pack()); invalid['source'] = {'truth': 'declared'}
        with self.assertRaisesRegex(AssertionError, 'empreinte'):
            execute("window.__SOMA_TERRAIN56__.v69.attach('a',input.packs[0],[1000,2000,1250,2250])", [invalid])
        invalid = copy.deepcopy(pack()); header = json.loads(invalid['gridHeader']); header['sample'] = 'override'
        g = T.validate_grid(invalid); invalid = T._pack(header, g.data, g.mask, invalid['source'])
        with self.assertRaisesRegex(AssertionError, 'champ inconnu'):
            execute("window.__SOMA_TERRAIN56__.v69.attach('a',input.packs[0],[1000,2000,1250,2250])", [invalid])

    def test_tile_cache_budget_is_a_real_admission_limit(self):
        result = execute("""(()=>{
          const K=window.__SOMA_TERRAIN56_CORE__,V=window.__SOMA_TERRAIN56__.v69;
          const base=input.packs[0],data=K.load(base),raw=Buffer.from(base.dataBase64,'base64'),mask=Buffer.from(base.maskBase64,'base64');
          let refused=null;
          for(let i=0;i<=V.snapshot().maxTiles;i++){
            const h=JSON.parse(base.gridHeader),dx=i*500;
            h.x0+=dx;h.boundsL93=h.boundsL93.map((v,n)=>n%2===0?v+dx:v);
            const text=JSON.stringify(h),p={...base,gridHeader:text,sha256:K.digest(text,raw,mask)};
            try{V.attach('tile-'+i,p,h.boundsL93)}catch(e){refused=e.message;break;}
          }
          return {refused,count:V.snapshot().attachedTiles,max:V.snapshot().maxTiles};
        })()""", [pack()])
        self.assertIn('budget de tuiles', result['refused'])
        self.assertEqual(result['count'], result['max'])

    def test_legacy_rays_are_identical_when_no_overlay_is_attached(self):
        result = execute("""(()=>{const T=window.__SOMA_TERRAIN56__,K=window.__SOMA_SIGHT61_CORE__;
          const o=[892951.6480966414,60,-6247274.566415883],directions=[[1,0,0],[0,-1,0],[.6,-.8,0]];
          return directions.map(d=>({old:K.terrain(T.grid,o,d,500),current:T.v69.traceTerrain(o,d,500,K)}));})()""")
        for row in result:
            self.assertEqual(row['current'], row['old'])

    def test_ray_walks_useful_tile_intervals_and_finds_nearest_terrain_in_second_tile(self):
        samples = []
        for bounds in [(1000, 2000, 1250, 2250), (1250, 2000, 1500, 2250)]:
            p = pack(bounds); g = T.validate_grid(p); data = bytearray(g.data)
            for row in range(g.rows):
                for col in range(g.cols):
                    east = g.x0 + col * g.step
                    struct.pack_into('<f', data, (row * g.cols + col) * 4, 10 + max(0, east - 1250) * .04)
            samples.append(T._pack(g.header, bytes(data), g.mask, p['source']))
        result = execute("""(()=>{const T=window.__SOMA_TERRAIN56__,V=T.v69,K=window.__SOMA_SIGHT61_CORE__;
          V.attach('a',input.packs[0],[1000,2000,1250,2250]);V.attach('b',input.packs[1],[1250,2000,1500,2250]);
          return {hit:V.traceTerrain([1125,15,-2125],[1,0,0],350,K),
            vertical:V.traceTerrain([1125,20,-2125],[0,-1,0],100,K)};})()""", samples)
        self.assertEqual(result['hit']['kind'], 'terrain')
        self.assertEqual(result['hit']['cellId'], 'b')
        self.assertAlmostEqual(result['hit']['distance'], 250, places=7)
        self.assertEqual(result['hit']['terrainSHA256'], samples[1]['sha256'])
        self.assertAlmostEqual(result['vertical']['distance'], 10, places=7)

    def test_flat_ray_passes_two_tiles_but_stops_at_unknown_coverage(self):
        samples = []
        for bounds in [(1000, 2000, 1250, 2250), (1250, 2000, 1500, 2250)]:
            p = pack(bounds); g = T.validate_grid(p)
            samples.append(T._pack(g.header, struct.pack('<f', 10) * (g.cols * g.rows), g.mask, p['source']))
        result = execute("""(()=>{const V=window.__SOMA_TERRAIN56__.v69,K=window.__SOMA_SIGHT61_CORE__;
          V.attach('a',input.packs[0],[1000,2000,1250,2250]);V.attach('b',input.packs[1],[1250,2000,1500,2250]);
          return {clear:V.traceTerrain([1125,15,-2125],[1,0,0],300,K),gap:V.traceTerrain([1125,15,-2125],[1,0,0],450,K)};})()""", samples)
        self.assertIsNone(result['clear'])
        self.assertEqual(result['gap']['kind'], 'unknown-terrain')
        self.assertAlmostEqual(result['gap']['distance'], 375, places=7)

    def test_ray_does_not_fill_nodata_in_a_later_tile(self):
        samples = []
        for index, bounds in enumerate([(1000, 2000, 1250, 2250), (1250, 2000, 1500, 2250)]):
            p = pack(bounds); g = T.validate_grid(p); mask = bytearray(g.mask)
            if index: mask[6 * g.cols + 3] = 0
            samples.append(T._pack(g.header, struct.pack('<f', 10) * (g.cols * g.rows), bytes(mask), p['source']))
        result = execute("""(()=>{const V=window.__SOMA_TERRAIN56__.v69,K=window.__SOMA_SIGHT61_CORE__;
          V.attach('a',input.packs[0],[1000,2000,1250,2250]);V.attach('b',input.packs[1],[1250,2000,1500,2250]);
          return V.traceTerrain([1125,15,-2125],[1,0,0],300,K);})()""", samples)
        self.assertEqual(result['kind'], 'unknown-terrain')
        self.assertEqual(result['cellId'], 'b')
        self.assertGreaterEqual(result['distance'], 125)
        self.assertLess(result['distance'], 200)

    def test_nodata_at_interval_midpoint_stops_at_its_true_entry_not_the_tile_edge(self):
        samples = []
        for index, bounds in enumerate([(1000, 2000, 1250, 2250), (1250, 2000, 1500, 2250)]):
            p = pack(bounds); g = T.validate_grid(p); mask = bytearray(g.mask)
            if index: mask[6 * g.cols + 6] = 0
            samples.append(T._pack(g.header, struct.pack('<f', 10) * (g.cols * g.rows), bytes(mask), p['source']))
        result = execute("""(()=>{const V=window.__SOMA_TERRAIN56__.v69,K=window.__SOMA_SIGHT61_CORE__;
          V.attach('a',input.packs[0],[1000,2000,1250,2250]);V.attach('b',input.packs[1],[1250,2000,1500,2250]);
          return V.traceTerrain([1125,15,-2125],[1,0,0],375,K);})()""", samples)
        self.assertEqual(result['kind'], 'unknown-terrain')
        self.assertAlmostEqual(result['distance'], 225, places=7)


class TerrainConsumerTests(unittest.TestCase):
    def patched_scripts(self):
        html = ('<script id="soma-v57-runtime">' + CONTACT_RUNTIME + '</script>'
                '<script id="unrelated-script">const untouched=true;</script>'
                '<script id="soma-v65-performance-runtime">' + PERF_RUNTIME + '</script>')
        result = P.patch_consumers(html)
        return html, result, [re.search(r'<script id="' + name + r'">(.*?)</script>', result, re.S)[1]
                              for name in ('soma-v57-runtime', 'soma-v65-performance-runtime')]

    def test_consumers_patch_refuses_drift_and_leaves_other_scripts_unchanged(self):
        original, patched, _ = self.patched_scripts()
        self.assertIn('<script id="unrelated-script">const untouched=true;</script>', patched)
        self.assertEqual(patched.count('terrain.v69?.gridFor(wz)'), 1)
        self.assertEqual(patched.count('T()?.v69?.revision??T()?.grid'), 2)
        for bad in [patched, original.replace('K.groundFootprint(terrain.grid,', 'K.changed(terrain.grid,'),
                    original.replace('T()?.grid!==job.terrain', 'T()?.grid===job.terrain')]:
            with self.assertRaises(ValueError): P.patch_consumers(bad)

    def test_real_vehicle_footprint_uses_new_tile_instead_of_distant_legacy_grid(self):
        _, _, scripts = self.patched_scripts()
        dependencies = """
          window.__SOMA_V52__.district={cells:[{id:'a',gridX:0,gridY:0}]};
          window.__SOMA_BOOT57__={state:{},complete(){}};
        """
        action = """(()=>{const T=window.__SOMA_TERRAIN56__;
          T.v69.attach('a',input.packs[0],[1000,2000,1250,2250]);
          const z=makeZone('a',[1000,2000,1250,2250]);
          return {blocked:window.__SOMA_V57__.footprintBlocked({id:'car',kind:'car'},0,0,0,'car',z),
                  missing:window.__SOMA_V57__.summary().collision.missingGround};})()"""
        original = execute(action, [pack()], post=[CONTACT_CORE, TRANSFER_CORE, dependencies, CONTACT_RUNTIME])
        current = execute(action, [pack()], post=[CONTACT_CORE, TRANSFER_CORE, dependencies, scripts[0]])
        self.assertTrue(original['blocked'])
        self.assertEqual(original['missing'], 1)
        self.assertFalse(current['blocked'])
        self.assertEqual(current['missing'], 0)

    def test_real_preparation_job_is_stale_after_mosaic_revision_changes(self):
        _, _, scripts = self.patched_scripts()
        dependencies = """
          window.addEventListener=()=>{};
          window.__SOMA_GROUP64__={ready:true,status:()=>({busy:false})};
          window.__SOMA_EXPLORE64__={ready:true,summary:()=>({busy:false})};
          const cacheState={settings:{prebuild:true,cacheSize:13},cache:{},global:{prebuilds:0,evictions:0}};
          window.__SOMA_V52__.state=()=>cacheState;
          window.__SOMA_V52__.v54={};
          window.__SOMA_V52__.district={cells:[{id:'a',gridX:0,gridY:0}]};
          window.__SOMA_PERF65__={stats:{},gate:{invalidate(){}},invalidate(){},markDirty(){},
            SerialQueue:class{constructor(options){this.options=options;this.pending=[];globalThis.testQueue=this;}
              replace(jobs){this.pending=jobs;}clear(){this.pending=[];}wake(){}snapshot(){return {pending:this.pending.length}}}};
        """
        action = """(()=>{const V=window.__SOMA_TERRAIN56__.v69;
          V.attach('a',input.packs[0],[1000,2000,1250,2250]);
          const z=makeZone('a',[1000,2000,1250,2250]);
          window.__SOMA_V65__.request('a');const job=testQueue.pending[0];
          V.attach('b',input.packs[1],[1250,2000,1500,2250]);
          const result=testQueue.options.run(job);return {result,built:!!z.static};})()"""
        inputs = [pack(), pack((1250, 2000, 1500, 2250))]
        original = execute(action, inputs, post=[dependencies, PERF_RUNTIME])
        current = execute(action, inputs, post=[dependencies, scripts[1]])
        self.assertTrue(original['result']['built'])
        self.assertEqual(current['result'], {'stale': True})
        self.assertFalse(current['built'])


if __name__ == '__main__':
    unittest.main()
