'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const zlib = require('node:zlib');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {spawnSync} = require('node:child_process');
const K = require('../../src/v69/streaming-core.js');
const SOURCE = 'c'.repeat(64);
const digest = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const clone = value => JSON.parse(JSON.stringify(value));
const deferred = () => {let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return{promise,resolve,reject};};

function fixture(count=4, allLayers=false) {
  const files = new Map();
  const manifest = {schema:K.SCHEMA,crs:'EPSG:2154',units:'m',origin:K.ORIGIN.slice(),cellSize:250,
    source:{sha256:SOURCE,license:'QA fixture license',attribution:'QA fixture, never shipped as geography'},
    target:{id:'200054807',boundarySHA256:null},coverageExplicitPartial:true,tiles:[]};
  for(let i=0;i<count;i++){
    const cellId=i===0?'V52-MC-33':`V52-MC-E${String(i).padStart(2,'0')}-S00`;
    const e=K.ORIGIN[0]+i*250,n=K.ORIGIN[1],bounds=[e-125,n-125,e+125,n+125];
    const record={schema:'soma-massilia/geodata-cell/4',cellId,boundsL93:bounds,
      sourceReceipt:{sha256:SOURCE,license:'QA fixture license',attribution:'QA fixture'},
      featureCollection:{type:'FeatureCollection',features:[{type:'Feature',id:`qa/point/${i}`,
        properties:{name:'QA fixture, not real coverage'},geometry:{type:'Point',coordinates:[5.37,43.3]}}]}};
    const tile={cellId,gridX:i,gridY:0,boundsL93:bounds,vector:null,terrain:null,surfaces:null,navigation:null};
    for(const layer of allLayers?K.LAYERS:['vector']){
      const value=layer==='vector'?record:{schema:`qa/${layer}`,cellId};
      const decoded=Buffer.from(JSON.stringify(value)),bytes=zlib.gzipSync(decoded);
      const file=`tiles/${cellId}/${layer}.json.gz`;files.set(file,bytes);
      tile[layer]={path:file,bytes:bytes.length,sha256:digest(bytes),encoding:'gzip-json'};
    }
    manifest.tiles.push(tile);
  }
  return {manifest,files,fetchBytes:async file=>files.get(file)};
}

test('manifest keeps historical aliases and rejects inconsistent metric cells',()=>{
  const f=fixture();const before=JSON.stringify(f.manifest),m=K.validateManifest(f.manifest);
  assert.deepEqual(K.cellIdGrid('V52-MC-41'),{gridX:-2,gridY:1});
  assert.deepEqual(K.cellIdGrid('V52-MC-E123-N040'),{gridX:123,gridY:-40});
  assert.equal(K.cellIdGrid('V52-MC-E1-N40'),null);
  assert.equal(JSON.stringify(f.manifest),before);
  m.origin[0]++;assert.equal(f.manifest.origin[0],K.ORIGIN[0]);
  const shifted=clone(f.manifest);shifted.tiles[0].boundsL93[0]+=.1;
  assert.throws(()=>K.validateManifest(shifted),/décalée/);
  const wrongId=clone(f.manifest);wrongId.tiles[1].gridX=2;
  assert.throws(()=>K.validateManifest(wrongId),/identifiant/);
});

test('manifest requires declared partial coverage, source identity and safe local asset paths',()=>{
  for(const edit of [m=>m.coverageExplicitPartial=false,m=>m.origin[1]+=1,m=>m.source.sha256='',m=>m.source.license='',m=>m.target.id='other']){
    const m=fixture().manifest;edit(m);assert.throws(()=>K.validateManifest(m));
  }
  for(const file of ['../secret','/absolute','https://example.com/file','tiles/%2e%2e/file','tiles\\file','tiles//file','tiles/file?key=x']){
    const m=fixture().manifest;m.tiles[0].vector.path=file;assert.throws(()=>K.validateManifest(m),/fichier/);
  }
  const m=fixture().manifest;m.tiles.push({...clone(m.tiles[0]),cellId:'V52-MC-E00-S00'});
  assert.throws(()=>K.validateManifest(m),/dupliquée/);
});

function terrainOnlyFixture() {
  const f=fixture(1,true);
  Object.assign(f.manifest.tiles[0],{terrainOnly:true,vector:null,surfaces:null,navigation:null,contentSHA256:null});
  return f;
}

test('terrain-only cells require an explicit null vector, valid terrain and no vector-derived layers or content hash',()=>{
  const f=terrainOnlyFixture(),before=JSON.stringify(f.manifest);
  const normalized=K.validateManifest(f.manifest);
  assert.equal(JSON.stringify(f.manifest),before);
  assert.equal(normalized.tiles[0].terrainOnly,true);
  assert.equal(normalized.tiles[0].vector,null);
  assert.equal(normalized.tiles[0].contentSHA256,null);
  normalized.tiles[0].terrain.path='changed';
  assert.notEqual(f.manifest.tiles[0].terrain.path,'changed');
  for(const edit of [
    t=>delete t.terrainOnly,t=>t.terrainOnly=false,t=>t.terrainOnly='true',
    t=>delete t.vector,t=>t.vector=fixture(1).manifest.tiles[0].vector,
    t=>delete t.terrain,t=>t.terrain=null,t=>t.terrain.path='../terrain.json.gz',
    t=>t.surfaces=fixture(1,true).manifest.tiles[0].surfaces,
    t=>t.navigation=fixture(1,true).manifest.tiles[0].navigation,
    t=>delete t.contentSHA256,t=>t.contentSHA256='a'.repeat(64),t=>t.contentSHA256='null',
  ]) {
    const bad=terrainOnlyFixture().manifest;edit(bad.tiles[0]);
    assert.throws(()=>K.validateManifest(bad));
  }
  const omitted=terrainOnlyFixture().manifest;
  delete omitted.tiles[0].surfaces;delete omitted.tiles[0].navigation;
  assert.equal(K.validateManifest(omitted).tiles[0].surfaces,null);
  assert.equal(K.validateManifest(omitted).tiles[0].navigation,null);
});

test('terrain-only loading never invents vector data or becomes 3D-ready, including cache hits',async()=>{
  const f=terrainOnlyFixture(),reads=[];let activationCalls=0;
  const store=K.createTileStore({...f,fetchBytes:async file=>{reads.push(file);return f.files.get(file);},
    canActivate:()=>{activationCalls++;return true;}});
  const id=f.manifest.tiles[0].cellId;
  await assert.rejects(store.load(id),/absentes/);
  await assert.rejects(store.load(id,{require3D:true}),/absentes/);
  assert.equal(reads.length,0);
  const entry=await store.load(id,{layers:['terrain']});
  assert.deepEqual(Object.keys(entry.layers),['terrain']);
  assert.equal(entry.layers.vector,undefined);
  assert.equal(entry.layers.terrain.schema,'qa/terrain');
  assert.deepEqual(entry.missingLayers,['vector','surfaces','navigation']);
  assert.equal(entry.readyFor3D,false);
  const cached=await store.load(id,{layers:['terrain']});
  assert.equal(cached.layers.terrain,entry.layers.terrain);
  assert.equal(cached.readyFor3D,false);
  assert.deepEqual(store.snapshot().readyFor3D,[]);
  await assert.rejects(store.load(id),/absentes/);
  await assert.rejects(store.load(id,{require3D:true}),/absentes/);
  assert.deepEqual(reads,[f.manifest.tiles[0].terrain.path]);
  assert.equal(activationCalls,0);
});

test('a metropolitan index copies each tile once and still isolates nested header and tile metadata',()=>{
  const input=fixture(0).manifest,serializations=new Uint8Array(5000);
  input.metadata={quality:{status:'QA metadata, no geographic assets'}};
  for(let i=0;i<serializations.length;i++){
    const x=i+100,cellId=`V52-MC-E${String(x).padStart(2,'0')}-S00`;
    const e=K.ORIGIN[0]+x*250,n=K.ORIGIN[1];
    input.tiles.push({cellId,gridX:x,gridY:0,boundsL93:[e-125,n-125,e+125,n+125],
      vector:{path:`tiles/${cellId}.json.gz`,sha256:'a'.repeat(64),bytes:100,encoding:'gzip-json'},
      terrain:null,surfaces:null,navigation:null,metadata:{quality:{status:'declared'}},
      toJSON(){serializations[i]++;return {...this,toJSON:undefined};}});
  }
  const normalized=K.validateManifest(input);
  assert.equal(normalized.tiles.length,5000);
  assert(serializations.every(count=>count===1),'A full-index clone would serialize each tile twice.');
  assert.equal(input.tiles[0].gridX,100);
  normalized.metadata.quality.status='changed';
  normalized.source.license='changed';
  normalized.target.boundarySHA256='b'.repeat(64);
  normalized.tiles[0].metadata.quality.status='changed';
  normalized.tiles[0].boundsL93[0]=0;
  normalized.tiles[0].vector.path='changed';
  assert.equal(input.metadata.quality.status,'QA metadata, no geographic assets');
  assert.equal(input.source.license,'QA fixture license');
  assert.equal(input.target.boundarySHA256,null);
  assert.equal(input.tiles[0].metadata.quality.status,'declared');
  assert.notEqual(input.tiles[0].boundsL93[0],0);
  assert.match(input.tiles[0].vector.path,/^tiles\//);
});

test('a genuine gzip/JSON/SHA pipeline loads one source tile without claiming 3D readiness',async()=>{
  const f=fixture(),attached=[];const store=K.createTileStore({...f,onAttach:(id,entry)=>attached.push([id,entry])});
  const entry=await store.load('V52-MC-33');
  assert.equal(entry.layers.vector.sourceReceipt.sha256,SOURCE);
  assert.equal(entry.readyFor3D,false);
  assert.deepEqual(entry.missingLayers,['terrain','surfaces','navigation']);
  assert.equal(attached.length,1);
  assert.equal(entry.accountedBytes,entry.decodedBytes*4);
  assert.equal(store.get(entry.cellId),entry);
  assert.equal(await K.sha256(f.files.values().next().value),digest(f.files.values().next().value));
});

test('bytes and hash are checked BEFORE decompression and no corrupt tile is attached',async()=>{
  const f=fixture();let decoded=0,attached=0;
  const bad=clone(f.manifest);bad.tiles[0].vector.sha256='0'.repeat(64);
  const store=K.createTileStore({manifest:bad,fetchBytes:f.fetchBytes,decodeBytes:async b=>{decoded++;return b;},onAttach:()=>attached++});
  await assert.rejects(store.load('V52-MC-33'),/SHA-256/);
  assert.equal(decoded,0);assert.equal(attached,0);assert.equal(store.snapshot().resident,0);
  const short=K.createTileStore({...f,fetchBytes:async file=>f.files.get(file).subarray(1)});
  await assert.rejects(short.load('V52-MC-33'),/taille du fichier/);
});

test('compressed and decoded caps reject oversized assets without dropping valid cache entries',async()=>{
  const f=fixture();
  const compressed=K.createTileStore({...f,maxCompressedBytes:10});
  await assert.rejects(compressed.load('V52-MC-33'),/compressée/);
  const decoded=K.createTileStore({...f,maxDecodedBytes:50});
  await assert.rejects(decoded.load('V52-MC-33'),/budget/);
});

test('contradictory vector source or cell identities fail before attachment',async()=>{
  const f=fixture();const file=f.manifest.tiles[0].vector.path;
  const raw=JSON.parse(zlib.gunzipSync(f.files.get(file)));raw.sourceReceipt.sha256='d'.repeat(64);
  const bytes=zlib.gzipSync(Buffer.from(JSON.stringify(raw)));f.files.set(file,bytes);
  Object.assign(f.manifest.tiles[0].vector,{bytes:bytes.length,sha256:digest(bytes)});
  const store=K.createTileStore(f);await assert.rejects(store.load('V52-MC-33'),/contradictoire/);
  assert.equal(store.snapshot().resident,0);
});

test('real GeoJSON objects are evicted through the detach callback under the byte budget',async()=>{
  const f=fixture(3),external=new Map(),decodedSizes=[...f.files.values()].map(b=>zlib.gunzipSync(b).length);
  const budget=Math.max(...decodedSizes)*2+5;
  const store=K.createTileStore({...f,memoryFactor:1,maxResidentBytes:budget,
    onAttach:(id,entry)=>external.set(id,entry.layers.vector),onDetach:id=>external.delete(id)});
  const [a,b,c]=f.manifest.tiles.map(t=>t.cellId);
  await store.load(a);await store.load(b);store.get(a);await store.load(c);
  assert.equal(store.get(b),null);assert.equal(external.has(b),false);
  assert.deepEqual(new Set(store.snapshot().residentIds),new Set([a,c]));
  assert(store.snapshot().accountedBytes<=budget);
});

test('active/protected tiles cannot be evicted to disguise a budget overflow',async()=>{
  const f=fixture(2),size=zlib.gunzipSync(f.files.values().next().value).length;
  const store=K.createTileStore({...f,memoryFactor:1,maxResidentBytes:size+20});
  const [a,b]=f.manifest.tiles.map(t=>t.cellId);
  await store.load(a);store.protect([a]);
  await assert.rejects(store.load(b),/protégées/);
  assert(store.get(a));assert.equal(store.get(b),null);
  assert.throws(()=>store.remove(a),/protégée/);
  store.protect([]);await store.load(b);assert.equal(store.get(a),null);
});

test('duplicate tile requests share one asset read and then use the cache',async()=>{
  const f=fixture();let reads=0;const gate=deferred();
  const store=K.createTileStore({...f,fetchBytes:async file=>{reads++;await gate.promise;return f.files.get(file);}});
  const first=store.load('V52-MC-33'),second=store.load('V52-MC-33');gate.resolve();
  const [a,b]=await Promise.all([first,second]);assert.equal(a,b);assert.equal(reads,1);
  const cached=await store.load(a.cellId);
  assert.equal(cached.layers.vector,a.layers.vector);assert.equal(reads,1);
});

test('at most two asynchronous reads run, with a bounded pending queue',async()=>{
  const f=fixture(4);let running=0,maximum=0;const gates=[];
  const store=K.createTileStore({...f,maxPending:4,fetchBytes:async file=>{
    running++;maximum=Math.max(maximum,running);const gate=deferred();gates.push(gate);await gate.promise;
    running--;return f.files.get(file);
  }});
  const loads=f.manifest.tiles.map(tile=>store.load(tile.cellId));
  assert.equal(gates.length,2);assert.equal(store.snapshot().queued,2);
  gates[0].resolve();gates[1].resolve();
  while(gates.length<4)await new Promise(resolve=>setImmediate(resolve));
  gates[2].resolve();gates[3].resolve();await Promise.all(loads);assert.equal(maximum,2);
  const blocked=deferred();const limited=K.createTileStore({...f,maxPending:1,fetchBytes:async file=>{await blocked.promise;return f.files.get(file);}});
  const one=limited.load(f.manifest.tiles[0].cellId);
  await assert.rejects(limited.load(f.manifest.tiles[1].cellId),/file de chargement/);
  blocked.resolve();await one;
  await assert.rejects(limited.request(f.manifest.tiles.map(tile=>tile.cellId)),/cibles hors budget/);
  assert.throws(()=>K.createTileStore({...f,onAttach:async()=>{}}),/synchrone/);
});

test('a stale response that ignores AbortSignal is never attached after changing target',async()=>{
  const f=fixture(2),gate=deferred(),attached=[];
  const [a,b]=f.manifest.tiles.map(tile=>tile.cellId);
  const store=K.createTileStore({...f,fetchBytes:async(file,settings)=>{
    if(settings.tile.cellId===a)await gate.promise;return f.files.get(file);
  },onAttach:id=>attached.push(id)});
  const old=store.load(a);const rejection=assert.rejects(old,error=>error.name==='AbortError');
  const current=store.request([b],{protectedIds:[b]});await rejection;
  gate.resolve();const result=await current;
  assert.equal(result[0].status,'fulfilled');assert.deepEqual(attached,[b]);assert.equal(store.get(a),null);
});

test('missing dependencies cannot be requested as a ready metropolitan scene',async()=>{
  const f=fixture();let reads=0;
  const store=K.createTileStore({...f,fetchBytes:async file=>{reads++;return f.files.get(file);},canActivate:()=>true});
  await assert.rejects(store.load('V52-MC-33',{require3D:true}),/absentes/);
  assert.equal(reads,0);const entry=await store.load('V52-MC-33');assert.equal(entry.readyFor3D,false);
});

test('all dependency files still require the injected activation gate and layer validators',async()=>{
  const f=fixture(1,true),validated=[];
  const validators=Object.fromEntries(K.LAYERS.map(layer=>[layer,value=>{validated.push(layer);return value;}]));
  const closed=K.createTileStore({...f,validators});
  assert.equal((await closed.load('V52-MC-33',{require3D:true})).readyFor3D,false);
  const open=K.createTileStore({...f,validators,canActivate:entry=>entry.layers.terrain.schema==='qa/terrain'});
  const ready=await open.load('V52-MC-33',{require3D:true});
  assert.equal(ready.readyFor3D,true);assert.deepEqual(ready.missingLayers,[]);
  assert.equal(validated.length,8);
});

test('cached readiness is revoked and restored against the current activation gate without refetching',async()=>{
  const f=fixture(1,true);let allowed=true,reads=0;
  const store=K.createTileStore({...f,fetchBytes:async file=>{reads++;return f.files.get(file);},canActivate:()=>allowed});
  const first=await store.load('V52-MC-33',{require3D:true}),originalUse=first.lastUsed;
  assert.equal(first.readyFor3D,true);assert.equal(reads,4);
  allowed=false;
  const revoked=await store.load(first.cellId,{require3D:true});
  assert.equal(revoked.readyFor3D,false);assert.deepEqual(store.snapshot().readyFor3D,[]);
  assert.equal(first.readyFor3D,true,'Previously published status must not be mutated.');
  assert.equal(first.lastUsed,originalUse);
  assert.equal(revoked.layers,first.layers);assert.equal(reads,4);
  allowed=true;
  const restored=await store.load(first.cellId,{require3D:true});
  assert.equal(restored.readyFor3D,true);assert.equal(revoked.readyFor3D,false);
  assert.deepEqual(store.snapshot().readyFor3D,[first.cellId]);assert.equal(reads,4);
});

test('a cached status refresh does not mutate the previous entry of an in-flight layer upgrade',async()=>{
  const f=fixture(1,true),gate=deferred();let allowed=false,reads=0;
  const store=K.createTileStore({...f,fetchBytes:async(file,settings)=>{
    reads++;if(settings.layer==='terrain')await gate.promise;return f.files.get(file);
  },canActivate:()=>allowed});
  const partial=await store.load('V52-MC-33'),use=partial.lastUsed;
  const upgrade=store.load(partial.cellId,{require3D:true});
  const refresh=await store.load(partial.cellId);
  assert.equal(refresh.readyFor3D,false);assert.equal(partial.lastUsed,use);
  assert.deepEqual(Object.keys(partial.layers),['vector']);
  assert.equal(refresh.layers,partial.layers);
  allowed=true;gate.resolve();const complete=await upgrade;
  assert.equal(complete.readyFor3D,true);assert.deepEqual(complete.missingLayers,[]);
  assert.deepEqual(Object.keys(partial.layers),['vector'],'A completed upgrade replaces, rather than mutates, its previous payload map.');
  assert.equal(refresh.readyFor3D,false);assert.equal(reads,4);
});

// Patch tests execute the real v53 geographic validator, and the actual v52
// registry functions inserted into its IIFE. External rendering/DOM is stubbed.
const baselinePath=path.resolve(__dirname,'../../baseline/v66.html');
const html=fs.readFileSync(baselinePath,'utf8');
const script=id=>html.match(new RegExp('<script\\b[^>]*\\bid="'+id+'"[^>]*>([\\s\\S]*?)<\\/script>'))?.[1];
const python=process.env.PYTHON || (process.platform==='win32'?'python':'python3');
function patched(name,body){
  const result=spawnSync(python,['-c','import sys;sys.path.insert(0,sys.argv[1]);from v69_streaming import '+name+';sys.stdout.write('+name+'(sys.stdin.read()))',path.resolve(__dirname,'../../tools')],{input:body,encoding:'utf8'});
  assert.equal(result.status,0,result.stderr);return result.stdout;
}
const core53=patched('patch_v53',script('soma-v53-core'));
const registry52=patched('patch_v52',script('soma-v52-runtime'));

function runtime(){
  const context=vm.createContext({console,TextEncoder,Map,Set,structuredClone,setTimeout(){},
    document:{getElementById(){return null}},localStorage:{getItem(){return null},setItem(){throw Error('Unexpected persistence write');}},
    window:{__SOMA_V52_CORE__:{isPublicGeometry:r=>!!r?.v53Validated,truthLabel:()=>''},__SOMA_V57_CORE__:{sourceRoadAccess:()=>false}}});
  vm.runInContext('let zone=null;const WORLD={zones:{},links:[]};',context);
  vm.runInContext(core53,context);context.window.__SOMA_V53_CORE__=context.__SOMA_V53_CORE__;
  const expose=`globalThis.Q={register:registerTransient69,remove:removeTransient69,activeRecord,records:RECORDS,zones:ZONES,district:DISTRICT,grid:METRIC_GRID53,transient:TRANSIENT69,
    seed(def,record){I50={freshZone:r=>({id:'geo:'+r.cellId,v50Record:r,portals:[],v50PortalCatalog:[],v50Seams:[]})};RECORDS.set(def.id,record);ZONES.set(def.id,{id:'geo:'+def.id,v50Record:record,portals:[],v50PortalCatalog:[],v50Seams:[]});},
    active(id){zone=ZONES.get(id)||{v51ParentCellId:id};},world:WORLD};\nasync function setup(){`;
  assert.equal(registry52.split('async function setup(){').length,2);
  vm.runInContext(registry52.replace('async function setup(){',expose),context);
  return context;
}

function metricRow(context,id='V52-MC-E123-N040'){
  context.id=id;
  return vm.runInContext(`(()=>{
    const c=__SOMA_V53_CORE__,g=${JSON.stringify(K.cellIdGrid(id))},def=c.metricCell({id, ...g},Q.district);
    const center=[(def.boundsL93[0]+def.boundsL93[2])/2,(def.boundsL93[1]+def.boundsL93[3])/2];
    const row={schema:'soma-massilia/geodata-cell/4',cellId:id,boundsL93:def.boundsL93,boundsWGS84:def.boundsWGS84,
      sourceReceipt:{id:'qa-never-shipped',sha256:'${SOURCE}',license:'QA fixture',attribution:'QA fixture'},
      featureCollection:{type:'FeatureCollection',features:[{type:'Feature',id:'qa-point',properties:{'soma:layer':'pois','soma:metricGeometry':{type:'Point',coordinates:center}},geometry:{type:'Point',coordinates:c.inverse(center)}}]}};
    return {def,row};})()`,context);
}

test('the widened REAL v53 validator accepts four-digit indices without relaxing source geometry',()=>{
  const c=runtime(),{def,row}=metricRow(c,'V52-MC-E1234-N040');
  c.fixture={def,row};
  assert.doesNotThrow(()=>vm.runInContext('__SOMA_V53_CORE__.normalizeRecord(fixture.row,null,{cells:[fixture.def]})',c));
  row.featureCollection.features[0].geometry.coordinates[0]+=1;
  assert.throws(()=>vm.runInContext('__SOMA_V53_CORE__.normalizeRecord(fixture.row,null,{cells:[fixture.def]})',c),/hors cellule|décalée/);
});

test('transient registration adds real registry entries and eviction releases them without IndexedDB writes',()=>{
  const c=runtime(),{def,row}=metricRow(c);c.fixture={def,row};
  // Preserve a known original record to exercise replacement refusal separately.
  vm.runInContext("Q.seed(Q.district.cells.find(x=>x.id==='V52-MC-33'),{v53Validated:true,featureCollection:{features:[]}})",c);
  vm.runInContext('Q.register(fixture.def,fixture.row)',c);
  assert.equal(c.Q.records.has(row.cellId),true);assert.equal(c.Q.zones.get(row.cellId).v69Transient,true);
  assert.equal(c.Q.activeRecord(def).cellId,row.cellId);
  assert.equal(c.Q.district.cells.filter(d=>d.id===row.cellId).length,1);
  vm.runInContext('Q.remove([fixture.row.cellId])',c);
  assert.equal(c.Q.records.has(row.cellId),false);assert.equal(c.Q.zones.has(row.cellId),false);
  assert.equal(c.Q.world.zones['geo:'+row.cellId],undefined);
  assert.equal(c.Q.grid.cells.some(d=>d.id===row.cellId),false);
  assert.equal(c.Q.district.cells.some(d=>d.id===row.cellId),false);
});

test('original tiles, current cells and the current neighbourhood stay protected',()=>{
  const c=runtime(),a=metricRow(c,'V52-MC-E123-N040'),b=metricRow(c,'V52-MC-E124-N040');
  c.a=a;c.b=b;
  vm.runInContext("Q.seed(Q.district.cells.find(x=>x.id==='V52-MC-33'),{v53Validated:true,featureCollection:{features:[]}});Q.register(a.def,a.row);Q.register(b.def,b.row);Q.active(a.row.cellId)",c);
  assert.throws(()=>vm.runInContext('Q.remove([a.row.cellId])',c),/protégée/);
  assert.throws(()=>vm.runInContext('Q.remove([b.row.cellId])',c),/protégée/);
  assert.throws(()=>vm.runInContext('Q.register(a.def,a.row)',c),/remplacée/);
  assert.throws(()=>vm.runInContext("Q.remove(['V52-MC-33'])",c),/transitoires/);
  const original=metricRow(c,'V52-MC-33');c.original=original;
  assert.throws(()=>vm.runInContext('Q.register(original.def,original.row)',c),/socle original/);
});

test('transient registration refuses shifted definitions, malformed records and alias collisions transactionally',()=>{
  const c=runtime(),a=metricRow(c);c.fixture=a;
  const count=c.Q.district.cells.length;
  a.def.boundsL93[0]+=1;
  assert.throws(()=>vm.runInContext('Q.register(fixture.def,fixture.row)',c),/décalée/);
  assert.equal(c.Q.district.cells.length,count);assert.equal(c.Q.records.size,0);
  const alias=metricRow(c,'V52-MC-E00-S00');c.alias=alias;
  assert.throws(()=>vm.runInContext('Q.register(alias.def,alias.row)',c),/même cellule/);
});
