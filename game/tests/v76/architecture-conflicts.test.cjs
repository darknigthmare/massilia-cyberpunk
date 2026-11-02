'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),zlib=require('node:zlib'),crypto=require('node:crypto');
const game=path.resolve(__dirname,'../..'),K=require('../../src/v76/architecture-conflicts-core.js');
const data=JSON.parse(fs.readFileSync(path.join(game,'data/v76/architecture-conflicts.json'))),model=K.create(data);
const clone=x=>JSON.parse(JSON.stringify(x)),digest=x=>crypto.createHash('sha256').update(x).digest('hex');
test('fixed77 preserves strict-positive cohort including the 4.1mm discrepancy and bounded filters',()=>{
 assert.equal(model.data.rows.length,77);assert.equal(model.data.cells,40);assert.equal(model.list().rows.length,10);assert.equal(model.list().pages,8);
 assert.equal(model.list({over3cm:true}).total,76);assert.equal(model.list({query:'osm/way/68979799'}).total,1);
 const tiny=model.get('osm/way/68979799');assert.ok(tiny.terrainAboveEave>0&&tiny.terrainAboveEave<.005);
 assert.equal(model.list({query:'BATIMENT',page:999}).page,7);assert.equal(model.list({query:'missing'}).total,0);
 assert.equal(model.list({cellId:'V52-MC-W02-S04'}).rows[0].id,'osm/way/69129984');
 assert.equal(model.get('osm/way/69129984').groundAltitude,43.1);assert.equal(model.get('osm/way/69129984').eaveHeight,3);
 assert.ok(Object.isFrozen(model.data.rows[0]));assert.throws(()=>{model.data.rows[0].groundAltitude=999;},TypeError);
});
test('tampered counts, source datums, identity and provenance are refused',()=>{
 for(const change of [d=>d.rows.pop(),d=>d.rows[0].groundAltitude++,d=>d.rows[0].sourceSHA256='a'.repeat(64),d=>d.rows[0].geometrySHA256='unknown',d=>d.rows[1].id=d.rows[0].id,d=>d.geometryChanged=true,d=>d.rows[0].terrainAboveEave=-1,d=>d.thresholdM=.03]){
  const d=clone(data);change(d);assert.throws(()=>K.create(d));
 }
});
const records=new Map(),manifest=JSON.parse(fs.readFileSync(path.join(game,'data/v69/world/manifest.json'))),heightRaw=fs.readFileSync(path.join(game,'data/v69/building-height-matches.json.gz'));
const heightProof=JSON.parse(zlib.gunzipSync(heightRaw)),c={JSON,Number,Object,Array,Set,Map};c.window=c;
c.document={getElementById:()=>({textContent:JSON.stringify(heightProof)})};c.__SOMA_V52__={records:()=>records};vm.createContext(c);
vm.runInContext(fs.readFileSync(path.join(game,'src/v69/height-references.js'),'utf8'),c);
for(const t of manifest.tiles){const raw=fs.readFileSync(path.join(game,'data/v69/world',t.vector.path));assert.equal(digest(raw),t.vector.sha256);const r=JSON.parse(zlib.gunzipSync(raw));r.v53Validated=true;records.set(r.cellId,r);}
test('all77 rows bind to the real height-reference owner and immutable source records',()=>{
 assert.equal(digest(heightRaw),data.provenance.compressedHeightFileSHA256);
 assert.equal(heightProof.proofSHA256,data.provenance.heightProofSHA256);
 for(const r of data.rows)assert.equal(model.bound(r.id,records,c.__SOMA_HEIGHTS69__),true,r.id);
 const r=data.rows[0],record=records.get(r.cellId),before=record.contentSHA256;record.contentSHA256='f'.repeat(64);
 assert.equal(model.bound(r.id,records,c.__SOMA_HEIGHTS69__),false);record.contentSHA256=before;
 assert.equal(model.bound('invented',records,c.__SOMA_HEIGHTS69__),false);
});
test('versioned JS payload equals compact proof JSON without external cache dependency',()=>{
 const context={window:{}};vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(game,'src/v76/architecture-conflicts-data.js'),'utf8'),context);
 assert.deepEqual(JSON.parse(JSON.stringify(context.window.__SOMA_ARCHITECTURE76_DATA__)),data);
 assert.ok(data.provenance.maximumIndependentDifferenceM<1e-6);assert.equal(data.provenance.sourceContractBugFound,false);
});
function runtime(){
 const cells=[],A={selected:'V52-MC-33'},context={JSON,Number,Math,Object,Array,Set,Map,console,timers:[]};context.window=context;
 context.document={querySelector:selector=>{const match=selector.match(/^\[data-v52-cell="([^"]+)"\]$/);return match?{click:()=>{A.selected=match[1];cells.push(match[1]);}}:null;},getElementById:()=>null};
 context.setTimeout=fn=>context.timers.push(fn);context.__SOMA_ARCHITECTURE76_CORE__=K;context.__SOMA_ARCHITECTURE76_DATA__=clone(data);
 context.__SOMA_TERRAIN75__={ready:true,snapshot:()=>({active:false,selected:'legacy25m'})};context.__SOMA_HEIGHTS69__=c.__SOMA_HEIGHTS69__;
 context.__SOMA_V52__={open:tab=>{context.openTab=tab;},state:()=>A,records:()=>records,enterCell:()=>{throw Error('audit must not enter campaign');}};
 vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(game,'src/v76/architecture-conflicts-runtime.js'),'utf8'),context);
 return {context,A,cells,api:context.__SOMA_ARCHITECTURE76__};
}
test('runtime uses the real native cell action while preserving terrain, geometry and persistence ownership',()=>{
 const r=runtime();assert.equal(r.api.ready,true);assert.equal(r.api.snapshot().pilotActive,false);assert.equal(r.api.snapshot().total,77);
 assert.equal(r.api.inspect('osm/way/69129984'),true);assert.equal(r.api.snapshot().selectedSourceBound,true);
 assert.equal(r.api.selectCell('osm/way/69129984'),true);assert.equal(r.context.openTab,'terrain');assert.equal(r.A.selected,'V52-MC-W02-S04');assert.deepEqual(r.cells,['V52-MC-W02-S04']);
 assert.equal(r.api.selectCell('invented'),false);assert.equal(r.api.snapshot().geometryChanged,false);assert.equal(r.api.snapshot().sourceDatumChanged,false);
 const row=data.rows[0],record=records.get(row.cellId),before=record.contentSHA256;record.contentSHA256='0'.repeat(64);
 assert.equal(r.api.selectCell(row.id),false);assert.equal(r.cells.length,1);record.contentSHA256=before;
 assert.equal(r.context.__SOMA_ARCHITECTURE76_DATA__,undefined,'only immutable bounded catalogue remains');
});
