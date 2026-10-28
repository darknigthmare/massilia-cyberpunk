'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),cp=require('node:child_process'),zlib=require('node:zlib'),crypto=require('node:crypto');
const D=require('../../src/v72/fidelity-core.js'),I=require('../../src/v72/road-inspector-core.js');
const game=path.resolve(__dirname,'../..'),baseline=fs.readFileSync(path.join(game,'baseline/v66.html'),'utf8');
function core(id){const source=baseline.match(new RegExp('<script[^>]*id="'+id+'"[^>]*>([\\s\\S]*?)<\\/script>'))[1],context=vm.createContext({module:{exports:{}},TextEncoder,TextDecoder,atob:x=>Buffer.from(x,'base64').toString('binary')});vm.runInContext(source,context);return context.module.exports;}
const F=core('soma-v59-core'),G=core('soma-v53-core'),T=core('soma-v56-terrain-core');
test('leading decimals use the declared unit, preserving source tags and structural policy',()=>{
 const p={width:'.5',highway:'footway',bridge:'yes',access:'no',foot:'yes'},before=JSON.stringify(p),old=F.roadProfile(p),r=D.profile(p,F.roadProfile);
 assert.equal(old.width,1.8);assert.equal(r.width,.5);assert.equal(r.widthSource,'osm-width');assert.equal(r.structural,true);assert.equal(JSON.stringify(p),before);
 assert.equal(D.profile({width:'.5 m'},F.roadProfile).width,.5);assert.equal(D.profile({width:'.5 ft'},F.roadProfile).invalidWidth,true);
 for(const v of ['..','narrow','.5;2','.5m bad','-.5',true,{},Infinity])assert.equal(D.normalizedWidth(v),v);
 assert.equal(D.profile({'width:carriageway':'7',lanes:'2'},F.roadProfile).width,6.5);
 const fresh=core('soma-v59-core');assert.equal(D.install(fresh),true);const installed=fresh.roadProfile;D.install(fresh);assert.equal(fresh.roadProfile,installed);assert.equal(fresh.roadProfile({width:'.5'}).width,.5);
});
function isolated(){
 const q=D.PROOF,p={canonical_id:q.id,'soma:layer':'roads','soma:geometry_sha256':q.geometrySHA256,width:'.5',highway:'footway',surface:'unpaved',access:'no',foot:'yes','soma:metricGeometry':{type:'LineString',coordinates:[[0,0],[4,0]]}},
 record={cellId:q.cellId,contentSHA256:q.cellSHA256,sourceReceipt:{sha256:q.sourceSHA256},featureCollection:{features:[{id:q.id,properties:p}]}},
 profile={width:1.8,widthSource:'estimated-from-class',invalidWidth:true,geometrySHA256:q.geometrySHA256,foot:true,unsealed:true,sidewalk:{},surface:'unpaved'},
 triangles=[[[0,-.9],[4,-.9],[4,.9]],[[0,-.9],[4,.9],[0,.9]]],surface={schema:'soma-metropole/surface-cell/1',cellId:q.cellId,contentSHA256:q.cellSHA256,sourcePbfSHA256:q.sourceSHA256,
 cell:{contentSHA256:q.cellSHA256,sourceSHA256:q.sourceSHA256,surfaces:{unsealed:triangles,road:[[[100,100],[101,100],[101,101]]]},areaM2:{unsealed:7.2,road:.5}},roadMetadata:{[q.id]:profile}};
 return {record,surface,projector:{toLocal:p=>p.slice()}};
}
test('only the source-bound isolated full rectangle is narrowed; other surfaces retain identity',()=>{
 const x=isolated(),before=JSON.stringify(x),r=D.deriveSurfaces(x.surface,x.record,x.projector);
 assert.equal(JSON.stringify(x),before);assert.notEqual(r,x.surface);assert.equal(r.cell.surfaces.road,x.surface.cell.surfaces.road);
 assert.equal(r.cell.areaM2.unsealed,2);assert.equal(r.roadMetadata[D.PROOF.id].width,.5);assert.equal(r.fidelity72[0].nativeDemDrape,true);
 for(const t of r.cell.surfaces.unsealed)for(const v of t)assert(Math.abs(Math.abs(v[1])-.25)<1e-9);
});
test('different cells, geometry, source, clipping, extra surfaces and overlapping triangles fail closed',()=>{
 for(const mutate of [x=>x.record.contentSHA256='other',x=>x.surface.sourcePbfSHA256='other',x=>x.surface.roadMetadata[D.PROOF.id].geometrySHA256='other',
   x=>x.surface.cell.surfaces.unsealed.push(x.surface.cell.surfaces.unsealed[0]),x=>x.surface.cell.surfaces.unsealed[0][0][0]=.1,
   x=>x.surface.cell.surfaces.unsealed=[[[0,-.9],[4,-.9],[4,.9]],[[0,-.9],[4,-.9],[0,.9]]]]){
  const x=isolated();mutate(x);assert.equal(D.deriveSurfaces(x.surface,x.record,x.projector),x.surface);
 }
});
const center=[0,0],camera={e:0,n:0,h:100,yaw:0,pitch:-Math.PI/2},road=[[-10,1,-10],[0,1,10],[10,1,-10]],ground=road.map(([x,y,z])=>[x,0,z]);
function geometry(tris,ranges=[],evidence={items:[],truncated:false}){const values=[];for(const t of tris)for(const p of t)values.push(...p,0,1,0,.5,.5,.5);return I.attach({vertices:new Float32Array(values),centerL93:center},ranges,evidence,true);}
const range={start:3,end:6,kind:'road',rendering:'prepared-union',sourceId:null};
function pick(g,opts={}){return I.pickScene({camera,meshes:[{id:'tile',geometry:g}],visibleCellIds:new Set(['tile']),...opts});}
function source(id,shift=0){return {facts:I.facts({canonical_id:id,access:'no',foot:'yes',highway:'residential',width:'5'},{width:5,widthSource:'osm-width'}),geometry:{type:'LineString',coordinates:[[-10,shift],[10,shift]]},profile:{width:5,sidewalk:{}}};}
test('actual rendered triangle is selected; overlapping source envelopes stay explicit candidates',()=>{
 const g=geometry([ground,road],[range],{items:[source('osm/way/1'),source('osm/way/2',1)],truncated:false}),before=Buffer.from(g.vertices.buffer).toString('hex'),r=pick(g);
 assert.equal(r.status,'road');assert.equal(r.selection.candidateCount,2);assert.equal(r.selection.sourceAttribution,'compatible-source-geometries');assert.equal(r.selection.hitL93.h,1);
 assert.equal(r.selection.navigation.sectorPrepared,true);assert.equal(r.selection.navigation.graphRead,false);assert.equal(r.selection.navigation.wayMembershipVerified,false);
 assert.equal(r.selection.candidates[0].sourceTags.access,'no');assert.equal(r.selection.physicalAccessibilityVerified,false);assert.equal(Buffer.from(g.vertices.buffer).toString('hex'),before);
 r.selection.candidates[0].sourceTags.access='yes';assert.equal(pick(g).selection.candidates[0].sourceTags.access,'no');
});
test('occluders, culling, visibility, absent local axes and budgets never invent a road or access',()=>{
 const above=road.map(([x,y,z])=>[x,20,z]);assert.equal(pick(geometry([ground,road,above],[range])).status,'occluded');
 assert.equal(pick(geometry([[...road].reverse()],[{...range,start:0,end:3}])).status,'empty');
 const g=geometry([ground,road],[range]);assert.equal(pick(g,{visibleCellIds:new Set()}).status,'empty');assert.equal(pick(g,{maxTriangles:1}).status,'budget');
 const s=pick(g).selection;assert.equal(s.candidates.length,0);assert.equal(s.physicalAccessibilityVerified,false);
 assert.throws(()=>I.attach({vertices:new Float32Array(27),centerL93:center},[{...range,start:1,end:3}]),/ranges/);
 assert.throws(()=>pick(g,{camera:{...camera,h:NaN}}),/Bounded/);
});
const source69=fs.readFileSync(path.join(game,'src/v69/metropole-viewer-core.js'),'utf8').replace('const material=A.appearance(p,id),canonical=','const material=root.__SOMA_MATERIAL70_CORE__.appearance(p,id),canonical=');
const source71=cp.execFileSync('python3',['-c','import sys;sys.path.insert(0,sys.argv[1]);from tools.v71_architecture import patch_geometry;print(patch_geometry(sys.stdin.read()))',game],{input:source69,encoding:'utf8'});
const source72=cp.execFileSync('python3',['-c','import sys;sys.path.insert(0,sys.argv[1]);from tools.v72_fidelity import patch_geometry;print(patch_geometry(sys.stdin.read()))',game],{input:source71,encoding:'utf8'});
function viewer(src){const c=vm.createContext({module:{exports:{}},Float32Array,Uint8Array,__SOMA_ARCHITECTURE71_CORE__:require('../../src/v71/architecture-inspector-core.js'),__SOMA_FIDELITY72_CORE__:D,__SOMA_ROAD_INSPECTION72_CORE__:I,__SOMA_MATERIAL70_CORE__:require('../../src/v70/material-extension-core.js')});vm.runInContext(src,c);return c.module.exports;}
const V71=viewer(source71),V72=viewer(source72),A=require('../../src/v69/roof-core.js');
const world=path.join(game,'data/v69/metropole'),manifestPath=path.join(world,'manifest.json');
function checked(descriptor){const raw=fs.readFileSync(path.join(world,descriptor.path));assert.equal(raw.length,descriptor.bytes);assert.equal(crypto.createHash('sha256').update(raw).digest('hex'),descriptor.sha256);return JSON.parse(zlib.gunzipSync(raw));}
test('real delivered .5m source rectangle changes rendered native-DEM road triangles and preserves all source files',{skip:!fs.existsSync(manifestPath)},()=>{
 const manifestRaw=fs.readFileSync(manifestPath),manifest=JSON.parse(manifestRaw),tile=manifest.tiles.find(t=>t.cellId===D.PROOF.cellId),record=checked(tile.vector),surface=checked(tile.surfaces),terrain=checked(tile.terrain),
  grid=T.load(terrain,tile.boundsL93),entry={tile,layers:{vector:record,surfaces:surface,terrain:{grid,pack:terrain}}},deps={geo:G,terrain:T,fidelity:F,architecture:A},before=JSON.stringify({record,surface,terrain});
 const old=V71.buildTile(entry,deps,{details:false}),fixed=V72.buildTile(entry,deps,{details:false});
 assert.equal(JSON.stringify({record,surface,terrain}),before);assert.deepEqual(fs.readFileSync(manifestPath),manifestRaw);
 assert.equal(fixed.roads72.corrections.length,1);assert.equal(Buffer.from(fixed.vertices.buffer).equals(Buffer.from(old.vertices.buffer)),false);assert.equal(fixed.counts.terrainTriangles,old.counts.terrainTriangles);
 const correction=fixed.roads72.corrections[0];assert.equal(correction.previousWidthMeters,1.8);assert.equal(correction.widthMeters,.5);
 const mg=record.featureCollection.features.find(f=>f.id===D.PROOF.id).properties['soma:metricGeometry'],a=mg.coordinates[0],b=mg.coordinates[1],e=(a[0]+b[0])/2,n=(a[1]+b[1])/2;
 const result=I.pickScene({camera:{e,n,h:grid.sample(e,n)+50,yaw:0,pitch:-Math.PI/2},meshes:[{id:tile.cellId,geometry:fixed}],visibleCellIds:new Set([tile.cellId])});
 assert.equal(result.status,'road');const hit=result.selection.candidates.find(c=>c.id===D.PROOF.id);assert(hit);assert.equal(hit.widthMeters,.5);assert.equal(hit.widthQuality,'declared');assert.equal(hit.sourceTags.access,'no');assert.equal(hit.sourceTags.foot,'yes');
 const local=G.metricProjector(tile.boundsL93),height=grid.sample(e,n);assert(Math.abs(result.selection.hitL93.h-height-.05)<.02);
 const unchanged=V72.buildTile({...entry,tile:{...tile,cellId:'other'},layers:{...entry.layers,vector:{...record,cellId:'other'},surfaces:{...surface,cellId:'other'}}},deps,{details:false});assert.equal(Buffer.from(unchanged.vertices.buffer).equals(Buffer.from(old.vertices.buffer)),true);
});
