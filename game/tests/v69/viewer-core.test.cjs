'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const Viewer=require('../../src/v69/metropole-viewer-core.js'),A=require('../../src/v69/roof-core.js');
const html=fs.readFileSync(path.resolve(__dirname,'../../baseline/v66.html'),'utf8');
function core(id){const source=html.match(new RegExp('<script[^>]*id="'+id+'"[^>]*>([\\s\\S]*?)<\\/script>'))[1],context=vm.createContext({module:{exports:{}},TextEncoder,TextDecoder,atob:x=>Buffer.from(x,'base64').toString('binary')});vm.runInContext(source,context);return context.module.exports;}
const G=core('soma-v53-core'),T=core('soma-v56-terrain-core'),F=core('soma-v59-core');
const bounds=[891000,6246000,891250,6246250],center=[891125,6246125],deps={geo:G,terrain:T,fidelity:F,architecture:A};
function grid(mask=new Uint8Array(121).fill(1)){
 const header={x0:891000,n0:6246250,step:25,cols:11,rows:11};
 const values=new Float32Array(121);for(let y=0;y<11;y++)for(let x=0;x<11;x++)values[y*11+x]=20+x;
 return new T.Grid(header,values,mask,{},{});
}
function entry(features=[],terrain=grid()){
 const record={cellId:'V52-MC-33',boundsL93:bounds,contentSHA256:'record',sourceReceipt:{sha256:'source'},featureCollection:{features}};
 return{tile:{boundsL93:bounds},layers:{vector:record,terrain:{grid:terrain,pack:{}}}};
}
function terrainEntry(terrain=grid()){
 return{cellId:'V52-MC-33',tile:{terrainOnly:true,vector:null,contentSHA256:null,boundsL93:bounds.slice(),terrain:{url:'terrain.json.gz'}},
  layers:{terrain:{grid:terrain,pack:{}}}};
}
function meshFeature(id='osm/way/1',tags={},hole=false){
 const outer=[[891050,6246050],[891100,6246050],[891100,6246100],[891050,6246100],[891050,6246050]];
 const inner=[[891065,6246065],[891085,6246065],[891085,6246085],[891065,6246085],[891065,6246065]];
 const triangles=hole?[
  [outer[0],outer[1],inner[1]],[outer[0],inner[1],inner[0]],
  [outer[1],outer[2],inner[2]],[outer[1],inner[2],inner[1]],
  [outer[2],outer[3],inner[3]],[outer[2],inner[3],inner[2]],
  [outer[3],outer[0],inner[0]],[outer[3],inner[0],inner[3]]]:[[outer[0],outer[1],outer[2]],[outer[0],outer[2],outer[3]]];
 const rings=hole?[outer,inner]:[outer],walls=rings.flatMap(r=>r.slice(1).map((p,i)=>[r[i],p]));
 return{id,properties:{canonical_id:id,'soma:geometry_sha256':'geometry','soma:layer':'buildings',building:'apartments',height:'12',...tags,
  'soma:mesh53':[{ringsL93:rings,trianglesL93:triangles,wallsL93:walls,areaM2:hole?2100:2500}]}};
}
function vertices(result){const output=[];for(let i=0;i<result.vertices.length;i+=9)output.push(Array.from(result.vertices.slice(i,i+9)));return output;}

test('source landcover classes have distinct interpreted colours without changing their geometry',()=>{
 const kinds=[{natural:'wood'},{natural:'beach'},{natural:'bare_rock'},{natural:'wetland'},{landuse:'vineyard'},{landuse:'quarry'}];
 assert.equal(new Set(kinds.map(p=>Viewer.landcoverAppearance(p).kind)).size,kinds.length);
 assert.equal(new Set(kinds.map(p=>JSON.stringify(Viewer.landcoverAppearance(p).colour))).size,kinds.length);
 for(const tags of kinds){
  const f=meshFeature('osm/way/land',{...tags,'soma:layer':'landuse'},true),before=JSON.stringify(f),r=Viewer.buildTile(entry([f]),deps);
  const expected=Viewer.landcoverAppearance(tags),surface=vertices(r).slice(r.counts.terrainTriangles*3);
  assert(r.counts.landuseTriangles>0);assert.match(expected.source,/interpreted/);
  for(const v of surface){assert(v[1]>20);for(let c=0;c<3;c++)assert(Math.abs(v[6+c]-expected.colour[c])<1e-6);}
  assert.equal(JSON.stringify(f),before);
 }
 const material=Viewer.landcoverAppearance({natural:'wood'});material.colour[0]=99;
 assert(Viewer.landcoverAppearance({natural:'wood'}).colour[0]<1);
});

test('inland water without a declared level colours only its source footprint on valid terrain',()=>{
 const f=meshFeature('osm/way/lake',{'soma:layer':'hydrography',natural:'water',water:'lake'},true),before=JSON.stringify(f);
 const result=Viewer.buildTile(entry([f]),deps),surface=vertices(result).slice(result.counts.terrainTriangles*3);
 assert(result.counts.waterTriangles>0);assert.equal(result.counts.drapedWaterTriangles,result.counts.waterTriangles);
 for(let i=0;i<surface.length;i+=3){
  const tri=surface.slice(i,i+3),e=tri.reduce((s,v)=>s+v[0]+center[0],0)/3,n=tri.reduce((s,v)=>s+center[1]-v[2],0)/3;
  assert(!(e>891065&&e<891085&&n>6246065&&n<6246085),'A source water courtyard/hole stays open.');
  for(const v of tri)assert(Math.abs(v[1]-(grid().sample(v[0]+center[0],center[1]-v[2])+.035))<1e-4);
 }
 const masked=Viewer.buildTile(entry([f],grid(new Uint8Array(121))),deps);
 assert.equal(masked.counts.waterTriangles,0);assert(masked.counts.missingSurfacePieces>0);
 assert.equal(JSON.stringify(f),before);assert.match(result.landscapePolicy,/visual footprint/);
});

test('a declared water level is distinct from a visual overlay and remains source-bound',()=>{
 const f=meshFeature('osm/way/lake',{'soma:layer':'hydrography',natural:'water',ele:'-2.5'},true),result=Viewer.buildTile(entry([f]),deps);
 const surface=vertices(result).slice(result.counts.terrainTriangles*3);
 assert.equal(result.counts.drapedWaterTriangles,0);assert.equal(result.counts.waterTriangles,8);
 assert(surface.every(v=>v[1]===-2.5));
});

test('gabled source walls meet the ridge instead of leaving an open triangular gable',()=>{
 const f=meshFeature('osm/way/gable',{'roof:shape':'gabled','roof:height':'3','roof:orientation':'along',heritage:'yes'});
 const mesh=f.properties['soma:mesh53'][0];
 for(const point of mesh.ringsL93[0])if(point[1]===6246100)point[1]=6246080;
 const input=entry([f]),before=JSON.stringify(f),references=A.referenceIndex([input.layers.vector]);
 const result=Viewer.buildTile(input,deps,{references,canonicalDatumsMap:new Map([[f.id,40]]),details:false});
 assert.equal(result.counts.modelledRoofs,1);assert.equal(result.counts.sourceWallSegments,4);
 const wall=vertices(result).filter(v=>Math.abs(v[4])<1e-7);
 for(const east of [891050,891100])assert(wall.some(v=>Math.abs(v[0]+center[0]-east)<1e-5&&Math.abs(center[1]-v[2]-6246065)<1e-5&&v[1]===52),'Each source gable must contain its ridge endpoint.');
 assert.equal(JSON.stringify(f),before);
});

test('an open roof has the same source surface visible from both sides without invented thickness',()=>{
 const f=meshFeature('osm/way/canopy',{building:'roof','roof:shape':'hipped','roof:height':'3'});
 for(const point of f.properties['soma:mesh53'][0].ringsL93[0])if(point[1]===6246100)point[1]=6246080;
 const input=entry([f]),before=JSON.stringify(f),references=A.referenceIndex([input.layers.vector]);
 const result=Viewer.buildTile(input,deps,{references,canonicalDatumsMap:new Map([[f.id,40]]),details:false});
 assert(result.counts.canopyBackfaceTriangles>0);assert.equal(result.counts.buildingTriangles,2*result.counts.canopyBackfaceTriangles);
 assert.equal(result.counts.sourceWallSegments,0);
 const surface=vertices(result).slice(result.counts.terrainTriangles*3);
 for(let i=0;i<surface.length;i+=6){
  const top=surface.slice(i,i+3),bottom=surface.slice(i+3,i+6);
  assert(top.every(v=>v[4]>0));assert(bottom.every(v=>v[4]<0));
  const positions=vs=>vs.map(v=>JSON.stringify(v.slice(0,3))).sort();
  assert.deepEqual(positions(top),positions(bottom));
 }
 assert.equal(JSON.stringify(f),before);
});

test('roof dimension derivation never revives dimensions rejected by the source dimension core',()=>{
 const p={building:'roof',height:'10','roof:height':'.5'},dim={height:10,minHeight:9.8,heightSource:'osm-height',valid:false};
 assert.equal(A.roofDimensions(p,dim),dim);assert.equal(dim.valid,false);
});

test('real core56 terrain triangles use local metres, absolute NGF and finite normals',()=>{
 const result=Viewer.buildTile(entry(),deps);assert.equal(result.counts.terrainTriangles,200);assert.equal(result.vertices.length,200*3*9);
 assert.ok(vertices(result).every(v=>v.every(Number.isFinite)&&v[0]>=-125&&v[0]<=125&&v[2]>=-125&&v[2]<=125&&v[1]>=20&&v[1]<=30&&v[4]>0));
 assert.deepEqual(result.centerL93,center);
});
test('missing terrain nodes remove faces rather than generating a flat floor',()=>{
 const mask=new Uint8Array(121).fill(1);mask[5*11+5]=0;
 const result=Viewer.buildTile(entry([],grid(mask)),deps);assert.ok(result.counts.missingTerrainTriangles>0);assert.ok(result.counts.terrainTriangles<200);
 assert.ok(vertices(result).every(v=>v[1]>=20));
});
test('typed terrain-only tiles need no geographic, building or architecture dependencies',()=>{
 const input=terrainEntry(),before=JSON.stringify(input.tile),result=Viewer.buildTerrainTile(input);
 assert.equal(result.counts.terrainTriangles,200);assert.equal(result.counts.triangles,200);
 for(const key of ['buildings','buildingTriangles','roadTriangles','waterTriangles','windows'])assert.equal(result.counts[key],0);
 assert.deepEqual(result.centerL93,center);assert.deepEqual(result.boundsL93,bounds);
 assert.ok(vertices(result).every(v=>v.every(Number.isFinite)&&v[0]>=-125&&v[0]<=125&&v[2]>=-125&&v[2]<=125&&v[1]>=20&&v[1]<=30&&v[4]>0));
 assert.deepEqual(Viewer.buildTile(input).vertices,result.vertices);
 assert.equal(result.geometryBytes,result.vertices.byteLength);assert.equal(JSON.stringify(input.tile),before);
 result.boundsL93[0]=0;assert.equal(input.tile.boundsL93[0],bounds[0]);
});
test('terrain-only masks omit NoData strictly, including an entirely unknown tile',()=>{
 const mask=new Uint8Array(121).fill(1);mask[60]=0;const before=mask.slice();
 const partial=Viewer.buildTerrainTile(terrainEntry(grid(mask)));
 assert.ok(partial.counts.missingTerrainTriangles>0);assert.ok(partial.counts.terrainTriangles<200);assert.deepEqual(mask,before);
 const unknown=Viewer.buildTerrainTile(terrainEntry(grid(new Uint8Array(121))),{}, {maxVertices:0});
 assert.equal(unknown.vertices.length,0);assert.equal(unknown.counts.terrainTriangles,0);assert.equal(unknown.counts.missingTerrainTriangles,200);
 assert.equal(unknown.geometryBytes,0);assert.match(unknown.heightPolicy,/NoData faces omitted/);
});
test('terrain-only declaration rejects contradictory vector data or malformed metric bounds',()=>{
 for(const override of [{terrainOnly:false},{vector:{}},{contentSHA256:'vector-sha'},{terrain:null},{surfaces:{}},{navigation:{}},
  {boundsL93:[0,0,NaN,1]},{boundsL93:[1,0,0,1]}]){
  const input=terrainEntry();Object.assign(input.tile,override);assert.throws(()=>Viewer.buildTerrainTile(input),TypeError);
 }
 const vector=terrainEntry();vector.layers.vector={featureCollection:{features:[]}};assert.throws(()=>Viewer.buildTile(vector),TypeError);
 const sourceSurface=terrainEntry();sourceSurface.layers.surfaces={};assert.throws(()=>Viewer.buildTerrainTile(sourceSurface),TypeError);
 const untyped=terrainEntry();delete untyped.tile.terrainOnly;assert.throws(()=>Viewer.buildTile(untyped),TypeError);
});
test('terrain-only geometry enforces its vertex budget without mutating source data',()=>{
 const values=Float32Array.from({length:121},(_,i)=>i/10),mask=new Uint8Array(121).fill(1);
 const terrain=new T.Grid({x0:891000,n0:6246250,step:25,cols:11,rows:11},values,mask,{},{}),input=terrainEntry(terrain);
 const beforeValues=values.slice(),beforeMask=mask.slice();
 assert.throws(()=>Viewer.buildTerrainTile(input,{}, {maxVertices:3}),RangeError);
 assert.throws(()=>Viewer.buildTerrainTile(input,{}, {maxVertices:NaN}),RangeError);
 assert.deepEqual(values,beforeValues);assert.deepEqual(mask,beforeMask);
});
test('source courtyard roofs and source wall segments remain unchanged',()=>{
 const feature=meshFeature('osm/way/1',{heritage:'yes'},true),before=JSON.stringify(feature),result=Viewer.buildTile(entry([feature]),deps,{details:false});
 assert.equal(JSON.stringify(feature),before);assert.equal(result.counts.sourceWallSegments,8);assert.equal(result.counts.buildings,1);
 const building=vertices(result).slice(result.counts.terrainTriangles*3);
 for(let i=0;i<8*3;i+=3){const tri=building.slice(i,i+3),e=tri.reduce((s,v)=>s+v[0]+center[0],0)/3,n=tri.reduce((s,v)=>s+center[1]-v[2],0)/3;
  assert.ok(!(e>891065&&e<891085&&n>6246065&&n<6246085));}
});
test('walls are drawn only from wallsL93, including clipped source footprints',()=>{
 const feature=meshFeature();feature.properties['soma:mesh53'][0].wallsL93.pop();
 const result=Viewer.buildTile(entry([feature]),deps,{details:false});assert.equal(result.counts.sourceWallSegments,3);
});
test('missing ground withholds a building; supplied canonical datum is shared explicitly',()=>{
 const feature=meshFeature(),missing=new Uint8Array(121).fill(0),terrain=grid(missing);
 const a=Viewer.buildTile(entry([feature],terrain),deps);assert.equal(a.counts.buildings,0);assert.equal(a.counts.missingGroundBuildings,1);
 const b=Viewer.buildTile(entry([feature],terrain),deps,{canonicalDatumsMap:new Map([[feature.id,40]]),details:false});
 assert.equal(b.counts.buildings,1);assert.ok(vertices(b).every(v=>v[1]>=40));
});
test('a shared canonical datum cannot conceal missing ground in another loaded fragment',()=>{
 const feature=meshFeature(),input=entry([feature]),before=JSON.stringify(feature);
 const result=Viewer.buildTile(input,deps,{canonicalDatumsMap:new Map([[feature.id,40]]),missingCanonicalDatums:new Set([feature.id]),details:false});
 assert.equal(result.counts.buildings,0);assert.equal(result.counts.missingGroundBuildings,1);
 assert.equal(JSON.stringify(feature),before);
});
test('OSM explicit height wins and absent heights are counted as estimates',()=>{
 const feature=meshFeature(),explicit=Viewer.buildTile(entry([feature]),deps,{details:false});assert.equal(explicit.counts.estimatedBuildings,0);
 delete feature.properties.height;const estimated=Viewer.buildTile(entry([feature]),deps,{details:false});assert.equal(estimated.counts.estimatedBuildings,1);
});
test('source-bound IGN ground altitude wins over terrain maxima and a generic canonical datum',()=>{
 const feature=meshFeature();delete feature.properties.height;
 const reference={sourceSHA256:'source',cellContentSHA256:'record',geometrySHA256:'geometry',iou:.95,margin:.2,height:14,groundAltitude:55,ignId:'QA-IGN-building'};
 const result=Viewer.buildTile(entry([feature]),deps,{details:false,canonicalDatumsMap:new Map([[feature.id,40]]),heightReferences:new Map([[feature.id,reference]])});
 assert.equal(result.counts.ignHeightBuildings,1);assert.equal(result.counts.estimatedBuildings,0);
 const roof=vertices(result).slice(result.counts.terrainTriangles*3,result.counts.terrainTriangles*3+6);
 assert.equal(roof.length,6);assert.ok(roof.every(v=>v[1]===69));
});
test('measured IGN ground altitude remains admissible when canonical terrain contains NoData',()=>{
 const feature=meshFeature();delete feature.properties.height;
 const reference={sourceSHA256:'source',cellContentSHA256:'record',geometrySHA256:'geometry',iou:.95,margin:.2,height:14,groundAltitude:55,ignId:'QA-IGN-building'};
 const input=entry([feature],grid(new Uint8Array(121))),before=JSON.stringify(feature);
 const result=Viewer.buildTile(input,deps,{details:false,canonicalDatumsMap:new Map([[feature.id,40]]),missingCanonicalDatums:new Set([feature.id]),heightReferences:new Map([[feature.id,reference]])});
 assert.equal(result.counts.buildings,1);assert.equal(result.counts.ignHeightBuildings,1);assert.equal(result.counts.missingGroundBuildings,0);
 const roof=vertices(result).slice(0,6);assert.ok(roof.every(v=>v[1]===69));assert.equal(JSON.stringify(feature),before);
});
function eavesSidecar(feature,overrides={}){
 return{schema:'soma-metropole/surface-cell/1',cellId:'V52-MC-33',sourcePbfSHA256:'source',
  cell:{contentSHA256:'record',sourceSHA256:'source',surfaces:{}},buildings:{[feature.id]:{
   sourceSHA256:'source',geometrySHA256:'geometry',cellContentSHA256:'record',height:15,groundAltitude:55,
   heightKind:'eaves',roofSurveyed:false,accuracy:'source-match-not-certified',proofSHA256:'a'.repeat(64),ignId:'QA-eaves',...overrides}}};
}
test('source-bound eaves references never add roof:height or invent a surveyed roof profile',()=>{
 const feature=meshFeature('osm/way/1',{'roof:shape':'dome','roof:height':'6'});delete feature.properties.height;
 const input=entry([feature]);input.layers.surfaces=eavesSidecar(feature);const before=JSON.stringify(input.layers.surfaces);
 const result=Viewer.buildTile(input,deps,{details:false});
 assert.equal(result.counts.ignHeightBuildings,1);assert.equal(result.counts.unsurveyedRoofs,1);assert.equal(result.counts.modelledRoofs,0);
 const roof=vertices(result).slice(result.counts.terrainTriangles*3,result.counts.terrainTriangles*3+6);
 assert.ok(roof.every(v=>v[1]===70));assert.equal(JSON.stringify(input.layers.surfaces),before);
});
test('stale source, cell and geometry eaves bindings fall back to explicit estimates',()=>{
 const feature=meshFeature();delete feature.properties.height;
 for(const mismatch of [{sourceSHA256:'other-source'},{cellContentSHA256:'other-cell'},{geometrySHA256:'other-geometry'},{roofSurveyed:true}]){
  const input=entry([feature]);input.layers.surfaces=eavesSidecar(feature,mismatch);const result=Viewer.buildTile(input,deps,{details:false});
  assert.equal(result.counts.ignHeightBuildings,0);assert.equal(result.counts.unsurveyedRoofs,0);assert.equal(result.counts.estimatedBuildings,1);
 }
});
test('eaves references cannot override OSM height, parts, elevated floors or canopies',()=>{
 for(const tags of [{height:'12'},{height:0},{height:'0'},{'building:part':'yes'},{min_height:'1'},{'building:min_level':'1'},{layer:'1'},{building:'roof'}]){
  const feature=meshFeature('osm/way/1',tags);if(!Object.hasOwn(tags,'height'))delete feature.properties.height;
  const input=entry([feature]);input.layers.surfaces=eavesSidecar(feature);const result=Viewer.buildTile(input,deps,{details:false});
  assert.equal(result.counts.ignHeightBuildings,0);assert.equal(result.counts.unsurveyedRoofs,0);
 }
});
test('explicit numeric zero floors and layer retain source-bound IGN eaves references',()=>{
 for(const value of [undefined,null,'',false,0,-0,'0','0.0','-0','+0.00','.0','0e3',' 0.0 ']){
  const feature=meshFeature('osm/way/1',{min_height:value,'building:min_level':value,layer:value});delete feature.properties.height;
  const input=entry([feature]);input.layers.surfaces=eavesSidecar(feature);const before=JSON.stringify(feature);
  const result=Viewer.buildTile(input,deps,{details:false});
  assert.equal(result.counts.ignHeightBuildings,1,`zero datum ${String(value)}`);
  assert.equal(result.counts.unsurveyedRoofs,1);assert.equal(result.counts.estimatedBuildings,0);
  assert.equal(JSON.stringify(feature),before);
 }
});
test('nonnumeric, nonfinite and nonzero floor or layer values cannot enable IGN references',()=>{
 for(const key of ['min_height','building:min_level','layer'])for(const value of [true,NaN,Infinity,{},[],1,-1,'1','NaN','no','0x0',' ']){
  const feature=meshFeature('osm/way/1',{[key]:value});delete feature.properties.height;
  const input=entry([feature]);input.layers.surfaces=eavesSidecar(feature);const result=Viewer.buildTile(input,deps,{details:false});
  assert.equal(result.counts.ignHeightBuildings,0,`${key}: ${String(value)}`);assert.equal(result.counts.unsurveyedRoofs,0);
 }
});
test('zero floors never relax source or cell binding for IGN eaves',()=>{
 for(const mismatch of [{sourceSHA256:'other-source'},{cellContentSHA256:'other-cell'},{geometrySHA256:'other-geometry'}]){
  const feature=meshFeature('osm/way/1',{min_height:'0.0','building:min_level':0,layer:'0'});delete feature.properties.height;
  const input=entry([feature]);input.layers.surfaces=eavesSidecar(feature,mismatch);const result=Viewer.buildTile(input,deps,{details:false});
  assert.equal(result.counts.ignHeightBuildings,0);assert.equal(result.counts.unsurveyedRoofs,0);assert.equal(result.counts.estimatedBuildings,1);
 }
});
test('IGN candidate classification trims source tokens and excludes located structures',()=>{
 for(const part of [' no ',' NO ',' false ',false,' 0 ',0,'']){
  const feature=meshFeature('osm/way/1',{'building:part':part});delete feature.properties.height;
  const input=entry([feature]);input.layers.surfaces=eavesSidecar(feature);
  assert.equal(Viewer.buildTile(input,deps,{details:false}).counts.ignHeightBuildings,1,`inactive part ${String(part)}`);
 }
 for(const tags of [{'building:part':' YES '},{'building:part':[]},{'building:part':{}},{building:' ROOF '},
  {location:' Underground '},{location:' UNDERWATER '},{location:'overground'}]){
  const feature=meshFeature('osm/way/1',tags);delete feature.properties.height;
  const input=entry([feature]);input.layers.surfaces=eavesSidecar(feature);
  assert.equal(Viewer.buildTile(input,deps,{details:false}).counts.ignHeightBuildings,0,JSON.stringify(tags));
 }
});
test('cyberpunk panels use reserved emissive colours while preserving source geometry',()=>{
 const feature=meshFeature(),before=JSON.stringify(feature),result=Viewer.buildTile(entry([feature]),deps);
 assert.ok(result.counts.windows>0);assert.ok(result.counts.litWindows>0);assert.ok(vertices(result).some(v=>Math.max(...v.slice(6))>1.25));assert.equal(JSON.stringify(feature),before);
});
test('monument parts receive no invented rows of apartment windows',()=>{
 const result=Viewer.buildTile(entry([meshFeature('osm/way/1',{'building:part':'yes'})]),deps);
 assert.equal(result.counts.windows,0);
});
test('unknown parent volumes can be omitted through a source-bound runtime proof',()=>{
 const feature=meshFeature(),result=Viewer.buildTile(entry([feature]),deps,{omitBuildingIds:new Set([feature.id])});
 assert.equal(result.counts.buildings,0);assert.equal(result.counts.omittedOutlines,1);assert.equal(result.counts.unknownFootprintAreaM2,2500);
});
test('a local part crossing the parent courtyard cannot falsely prove outline containment',()=>{
 const parent=meshFeature('osm/way/1',{'building:part':'no'},true),part=meshFeature('osm/way/2',{'building:part':'yes'});
 const result=Viewer.buildTile(entry([parent,part]),deps,{details:false});
 assert.equal(result.counts.omittedOutlines,0);assert.equal(result.counts.buildings,2);
});
test('source road bands are draped and unsupported elevated structures are withheld',()=>{
 const road={id:'osm/way/2',properties:{'soma:layer':'roads',highway:'residential','soma:metricGeometry':{type:'LineString',coordinates:[[891000,6246125],[891250,6246125]]}}};
 const good=Viewer.buildTile(entry([road]),deps);assert.ok(good.counts.roadTriangles>0);assert.equal(good.counts.estimatedRoadWidths,1);
 road.properties.bridge='yes';const bridge=Viewer.buildTile(entry([road]),deps);assert.equal(bridge.counts.roadTriangles,0);assert.equal(bridge.counts.unsupportedStructures,1);
});
test('a height-only sidecar does not suppress source road fallback bands',()=>{
 const road={id:'osm/way/2',properties:{'soma:layer':'roads',highway:'residential','soma:metricGeometry':{type:'LineString',coordinates:[[891000,6246125],[891250,6246125]]}}};
 const input=entry([road]);input.layers.surfaces=eavesSidecar({id:'unrelated-height-reference'});
 const result=Viewer.buildTile(input,deps);assert.ok(result.counts.roadTriangles>0);
 road.properties.indoor='yes';const indoor=Viewer.buildTile(input,deps);assert.equal(indoor.counts.roadTriangles,0);
});
test('NoData source nodes do not receive road faces',()=>{
 const road={id:'osm/way/2',properties:{'soma:layer':'roads',highway:'residential','soma:metricGeometry':{type:'LineString',coordinates:[[891000,6246125],[891250,6246125]]}}};
 const result=Viewer.buildTile(entry([road],grid(new Uint8Array(121))),deps);assert.equal(result.counts.roadTriangles,0);assert.ok(result.counts.missingSurfacePieces>0);
});
test('missing dependencies and runaway geometry are explicit failures',()=>{
 assert.throws(()=>Viewer.buildTile(entry(),{}),TypeError);
 assert.throws(()=>Viewer.buildTile(entry(),deps,{maxVertices:3}),RangeError);
});
