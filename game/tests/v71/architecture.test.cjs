'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path'),cp=require('node:child_process');
const I=require('../../src/v71/architecture-inspector-core.js'),UI=require('../../src/v71/architecture-inspector-runtime.js');
const center=[891125,6246125];
function geometry(triangles,ranges=[]){
 const values=[];for(const tri of triangles)for(const p of tri)values.push(...p,0,1,0,.5,.5,.5);
 return I.attach({vertices:new Float32Array(values),centerL93:center,geometryBytes:values.length*4},ranges);
}
const roof=[[-10,20,-10],[0,20,10],[10,20,-10]],ground=[[-50,0,-50],[0,0,50],[50,0,-50]];
const camera={e:center[0],n:center[1],h:100,yaw:0,pitch:-Math.PI/2};
const fact=I.facts({canonical_id:'osm/way/123',height:'20',name:'Source house'},{height:20,minHeight:0,heightSource:'osm-height'},
 {shape:'flat',modelled:true},{wallSource:'osm-building-colour',roofSource:'interpreted-marseille-palette'}, {cellId:'tile'},0);
function pick(g,options={}){return I.pickScene({camera,meshes:[{id:'tile',geometry:g}],visibleCellIds:new Set(['tile']),...options});}

test('evidence separates OSM dimensions, material interpretations and unsurveyed roofs',()=>{
 const p={canonical_id:'osm/way/123',name:'<b>Source</b>',height:'20','building:material':'glass'},before=JSON.stringify(p);
 const r=I.facts(p,{height:20,heightSource:'osm-height'}, {shape:'gabled',modelled:true}, {wallSource:'osm-building-material'}, {cellId:'tile'},33);
 assert.equal(r.osmURL,'https://www.openstreetmap.org/way/123');assert.equal(r.heightQuality,'declared');
 assert.equal(r.roof.quality,'inferred-parametric');assert.equal(r.roof.surveyed,false);assert.equal(r.appearance.facadeSurveyed,false);
 assert.equal(r.appearance.lightingSource,'interpreted-cyberpunk');assert.equal(r.baseQuality,'derived-from-valid-dem');assert.equal(r.architecturalOneToOneCertified,false);
 assert.equal(JSON.stringify(p),before);r.sourceTags.height='99';assert.equal(p.height,'20');
});
test('IGN eaves are labelled eaves and never become a surveyed total roof height',()=>{
 const r=I.facts({canonical_id:'osm/relation/99'}, {height:19,heightKind:'eaves',heightSource:'ign-bdtopo-height',groundAltitude:30},
 {shape:'flat',reason:'ign-eaves-flat-roof-approximation'}, {},{},30);
 assert.equal(r.heightKind,'eaves');assert.equal(r.heightQuality,'matched-reference');assert.equal(r.roof.quality,'unsurveyed-eaves-approximation');assert.equal(r.baseQuality,'matched-source-base');
 assert.equal(I.facts({}, {height:9,heightSource:'estimated-levels'}, {},{},{}).heightQuality,'estimated');
 assert.equal(I.facts({canonical_id:'osm/way/1?bad'}, {},{},{},{}).osmURL,null);
});
test('picking uses the nearest actual rendered triangle and preserves source buffers',()=>{
 const g=geometry([ground,roof],[{start:3,end:6,facts:fact}]),before=Buffer.from(g.vertices.buffer).toString('hex'),r=pick(g);
 assert.equal(r.status,'building');assert.equal(r.selection.id,'osm/way/123');assert(Math.abs(r.selection.distanceMeters-80)<1e-8);
 assert.equal(r.selection.hitL93.h,20);assert.equal(r.selection.selectedCellId,'tile');assert.equal(Buffer.from(g.vertices.buffer).toString('hex'),before);
 r.selection.sourceTags.height='999';assert.equal(pick(g).selection.sourceTags.height,'20');
});
test('visible terrain and other source surfaces occlude a building instead of selecting through them',()=>{
 const above=ground.map(([x,y,z])=>[x,40,z]),g=geometry([roof,above],[{start:0,end:3,facts:fact}]);
 assert.equal(pick(g).status,'occluded');assert.equal(pick(g).selection,null);
});
test('front-face winding matches renderer culling and below-canopy duplicates remain pickable',()=>{
 assert.equal(pick(geometry([[...roof].reverse()],[{start:0,end:3,facts:fact}])).status,'empty');
 const g=geometry([roof,[...roof].reverse()],[{start:0,end:6,facts:fact}]);
 const r=pick(g,{camera:{...camera,h:0,pitch:Math.PI/2}});assert.equal(r.status,'building');assert(Math.abs(r.selection.distanceMeters-20)<1e-8);
});
test('a courtyard is not filled by an inspector hit and inactive cached tiles are excluded',()=>{
 const side=roof.map(([x,y,z])=>[x+50,y,z]),g=geometry([ground,side],[{start:3,end:6,facts:fact}]);
 assert.equal(pick(g).status,'occluded');assert.equal(pick(g,{visibleCellIds:new Set()}).status,'empty');
});
test('insufficient triangle budget explicitly refuses to claim a nearest building',()=>{
 const g=geometry([ground,roof],[{start:3,end:6,facts:fact}]),r=pick(g,{maxTriangles:1});
 assert.equal(r.status,'budget');assert.equal(r.testedTriangles,1);assert.equal(r.selection,null);
});
test('range, camera and geometry budgets fail before unbounded loops or ambiguous identities',()=>{
 const raw={vertices:new Float32Array(27),centerL93:center};
 assert.throws(()=>I.attach(raw,[{start:1,end:3,facts:fact}]),/ranges/);
 assert.throws(()=>I.attach(raw,[{start:0,end:3,facts:fact},{start:0,end:3,facts:fact}]),/ranges/);
 assert.throws(()=>pick(geometry([roof]),{camera:{...camera,h:NaN}}),/Bounded/);
 assert.throws(()=>pick(geometry([roof]),{maxTriangles:Infinity}),/Bounded/);
 assert.throws(()=>I.pickScene({camera,meshes:[{id:'tile',geometry:raw}],visibleCellIds:new Set(['tile'])}),/metadata/);
});
test('near clipping, source NoData holes and finite distance do not create virtual hit planes',()=>{
 const g=geometry([]);assert.equal(pick(g).status,'empty');
 assert.equal(pick(geometry([roof],[{start:0,end:3,facts:fact}]),{maxDistance:50}).status,'empty');
 assert.equal(pick(geometry([roof],[{start:0,end:3,facts:fact}]),{camera:{...camera,h:20.1}}).status,'empty');
});

test('read-only panel owns one lease, returns detached evidence and releases once on repeated close',async()=>{
 let releases=0,reads=0,shows=0,hides=0;
 const controller=UI.createController({available:()=>true,acquire:async()=>({release:async()=>{releases++;}}),inspect(){reads++;return {status:'building',selection:fact};}},
  {show(){shows++;},hide(){hides++;}});
 assert.equal(await controller.open(),true);assert.equal(await controller.open(),false);assert.equal(reads,1);assert.equal(shows,1);
 controller.snapshot().result.selection.sourceTags.height='99';assert.equal(controller.snapshot().result.selection.sourceTags.height,'20');
 await Promise.all([controller.close(),controller.close()]);assert.equal(releases,1);assert.equal(hides,1);assert.equal(controller.snapshot().phase,'closed');
});
test('closing during an uncooperative pending acquire cannot publish stale facts or retain a lease',async()=>{
 let resolve,releases=0,renders=0;const promise=new Promise(r=>{resolve=r;});
 const c=UI.createController({available:()=>true,acquire:()=>promise,inspect:()=>({status:'building',selection:fact})},{render(){renders++;}});
 const opening=c.open(),closing=c.close();resolve({release:async()=>{releases++;}});
 assert.equal(await opening,false);await closing;assert.equal(renders,0);assert.equal(releases,1);assert.equal(c.snapshot().phase,'closed');
});
test('inspection refuses an occupied route lease without opening a second dialog',async()=>{
 let calls=0;const c=UI.createController({available:()=>false,acquire(){calls++;},inspect(){}},{show(){calls++;}});
 assert.equal(await c.open(),false);assert.equal(calls,0);assert.equal(c.snapshot().open,false);
});

const game=path.resolve(__dirname,'../..'),baseline=fs.readFileSync(path.join(game,'baseline/v66.html'),'utf8');
function core(id){const source=baseline.match(new RegExp('<script[^>]*id="'+id+'"[^>]*>([\\s\\S]*?)<\\/script>'))[1],context=vm.createContext({module:{exports:{}},TextEncoder,TextDecoder,atob:x=>Buffer.from(x,'base64').toString('binary')});vm.runInContext(source,context);return context.module.exports;}
const G=core('soma-v53-core'),T=core('soma-v56-terrain-core'),F=core('soma-v59-core'),A=require('../../src/v69/roof-core.js'),M=require('../../src/v70/material-extension-core.js');
const source=fs.readFileSync(path.join(game,'src/v69/metropole-viewer-core.js'),'utf8').replace('const material=A.appearance(p,id),canonical=','const material=root.__SOMA_MATERIAL70_CORE__.appearance(p,id),canonical=');
const derived=cp.execFileSync('python3',['-c','import sys;sys.path.insert(0,sys.argv[1]);from tools.v71_architecture import patch_geometry;print(patch_geometry(sys.stdin.read()))',game],{input:source,encoding:'utf8'});
const c=vm.createContext({module:{exports:{}},Float32Array,Uint8Array,__SOMA_ARCHITECTURE71_CORE__:I,__SOMA_MATERIAL70_CORE__:M});vm.runInContext(derived,c);const V=c.module.exports;
const originalContext=vm.createContext({module:{exports:{}},Float32Array,Uint8Array,__SOMA_MATERIAL70_CORE__:M});vm.runInContext(source,originalContext);const V70=originalContext.module.exports;
function realEntry(tags={}){
 const bounds=[891000,6246000,891250,6246250],outer=[[891110,6246110],[891140,6246110],[891140,6246140],[891110,6246140],[891110,6246110]],
 feature={id:'osm/way/123',properties:{canonical_id:'osm/way/123','soma:layer':'buildings','soma:geometry_sha256':'a'.repeat(64),building:'apartments',height:'20',...tags,
 'soma:mesh53':[{ringsL93:[outer],trianglesL93:[[outer[0],outer[1],outer[2]],[outer[0],outer[2],outer[3]]],wallsL93:outer.slice(1).map((p,i)=>[outer[i],p]),areaM2:900}]}},
 record={cellId:'tile',boundsL93:bounds,contentSHA256:'record',sourceReceipt:{sha256:'b'.repeat(64)},featureCollection:{features:[feature]}},
 grid=new T.Grid({x0:891000,n0:6246250,step:25,cols:11,rows:11},new Float32Array(121).fill(30),new Uint8Array(121).fill(1),{},{});
 return {tile:{boundsL93:bounds},layers:{vector:record,terrain:{grid,pack:{}}}};
}
test('actual geometry builder records rendered building identity without changing any vertex or source fact',()=>{
 const entry=realEntry({'building:colour':'red'}),before=JSON.stringify(entry.layers.vector),deps={geo:G,terrain:T,fidelity:F,architecture:A};
 const g=V.buildTile(entry,deps,{details:false}),old=V70.buildTile(entry,deps,{details:false});
 assert.deepEqual(g.vertices,old.vertices);assert.equal(JSON.stringify(entry.layers.vector),before);assert.equal(g.architecture71.ranges.length,1);
 assert.equal(g.architecture71.ranges[0].facts.appearance.wallSource,'osm-building-colour');
 const r=pick(g);assert.equal(r.status,'building');assert.equal(r.selection.id,'osm/way/123');assert.equal(r.selection.hitL93.h,50);assert.equal(r.selection.heightMeters,20);
});
test('actual DEM-only geometry remains a source occluder and contains no fabricated building evidence',()=>{
 const entry=realEntry();entry.tile={...entry.tile,terrainOnly:true,vector:null,contentSHA256:null,terrain:{url:'terrain'}};delete entry.layers.vector;
 const g=V.buildTerrainTile(entry),old=V70.buildTerrainTile(entry);assert.deepEqual(g.vertices,old.vertices);assert.equal(g.architecture71.ranges.length,0);assert.equal(pick(g).status,'occluded');
});
