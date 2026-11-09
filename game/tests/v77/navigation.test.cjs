'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),cp=require('node:child_process'),zlib=require('node:zlib'),crypto=require('node:crypto');
const N=require('../../src/v77/navigation-core.js'),I=require('../../src/v72/road-inspector-core.js'),fixture=require('./navigation-source.json');
const game=path.resolve(__dirname,'../..'),sha=b=>crypto.createHash('sha256').update(b).digest('hex'),clone=x=>JSON.parse(JSON.stringify(x));
const source=(side={left:true,leftWidth:1.5,right:false,rightWidth:1.5},coordinates=[[0,0],[20,0]])=>({facts:{id:'osm/way/1'},geometry:{type:'LineString',coordinates},profile:{width:4,sidewalk:side}});
const close=(a,b)=>assert(Math.abs(a-b)<1e-7,`${a} != ${b}`);
function extract(html,id){const m=html.match(new RegExp('<script id="'+id+'">([\\s\\S]*?)</script>'));assert(m,id);return m[1];}
function inspector(sourceText){const c=vm.createContext({module:{exports:{}},__SOMA_NAVIGATION77_CORE__:N,Float32Array,Set});vm.runInContext(sourceText,c);return c.module.exports;}
const originalInspector=fs.readFileSync(path.join(game,'src/v72/road-inspector-core.js'),'utf8');
const patchedInspector=cp.execFileSync('python3',['-B','-c',"import sys;sys.path.insert(0,'game');from tools.v77_navigation import patch_inspector;print(patch_inspector(sys.stdin.read()),end='')"],{cwd:path.dirname(game),input:originalInspector,encoding:'utf8',env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'}});
const fixedI=inspector(patchedInspector);
function pick(api,src,point,kind='walk'){
 const triangle=[[point[0]-1,0,-1-point[1]],[point[0],0,1-point[1]],[point[0]+1,0,-1-point[1]]],values=[];
 for(const p of triangle)values.push(...p,0,1,0,.5,.5,.5);
 const g=api.attach({vertices:new Float32Array(values),centerL93:[0,0]},[{start:0,end:3,kind,rendering:'prepared-union',sourceId:null}],{items:src,truncated:false},true);
 return api.pickScene({camera:{e:point[0],n:point[1],h:20,yaw:0,pitch:-Math.PI/2},meshes:[{id:'cell',geometry:g}],visibleCellIds:new Set(['cell'])});
}
test('left-only source sidewalk no longer extends across the opposite side of the Lambert-93 axis',()=>{
 const s=source(),before=JSON.stringify(s);
 assert.equal(pick(I,[s],[10,-3]).selection.candidateCount,1);
 assert.equal(pick(fixedI,[s],[10,-3]).selection.candidateCount,0);
 close(N.candidate(s,[10,3],'walk'),3);assert.equal(N.candidate(s,[10,-3],'walk'),null);
 assert.equal(N.candidate(s,[10,3],'road'),null);assert.equal(N.candidate(s,[10,3],'foot'),null);
 assert.equal(JSON.stringify(s),before);
});
test('axis reversal with exchanged side declarations preserves the same physical band',()=>{
 const cases=[source(),source({left:false,leftWidth:1.5,right:true,rightWidth:1.5}),source({left:true,leftWidth:.5,right:true,rightWidth:2.5})];
 for(const a of cases){const side=a.profile.sidewalk,b=source({left:side.right,leftWidth:side.rightWidth,right:side.left,rightWidth:side.leftWidth},a.geometry.coordinates.slice().reverse());
  for(const p of [[10,3],[10,-3],[10,2.52],[10,-4],[10,0],[-1,0],[21,0]])assert.equal(N.candidate(a,p,'walk'),N.candidate(b,p,'walk'));
 }
 const north=source(undefined,[[0,0],[0,20]]);close(N.candidate(north,[-3,10],'walk'),3);assert.equal(N.candidate(north,[3,10],'walk'),null);
});
test('side-specific widths retain existing centimetre tolerance and flat source ends',()=>{
 const s=source({left:true,leftWidth:.5,right:true,rightWidth:2});
 close(N.candidate(s,[10,2.529],'walk'),2.529);assert.equal(N.candidate(s,[10,2.531],'walk'),null);
 close(N.candidate(s,[10,-4.029],'walk'),4.029);assert.equal(N.candidate(s,[10,-4.031],'walk'),null);
 for(const p of [[-1,0],[21,0],[-1,3],[21,-3]])assert.equal(N.candidate(s,p,'walk'),null);
 close(N.candidate(s,[10,2.029],'road'),2.029);assert.equal(N.candidate(s,[10,2.031],'road'),null);
});
test('each source segment uses its own direction and repeated points never manufacture a candidate',()=>{
 const s=source(undefined,[[0,0],[0,0],[20,0]]);close(N.candidate(s,[10,3],'walk'),3);
 s.geometry={type:'MultiLineString',coordinates:[[[0,0],[20,0]],[[20,10],[0,10]]]};
 close(N.candidate(s,[10,3],'walk'),3);close(N.candidate(s,[10,7],'walk'),3);
 assert.equal(N.candidate(s,[10,-3],'walk'),null);assert.equal(N.candidate(s,[10,13],'walk'),null);
 s.geometry.coordinates=[[[0,0],[0,0]]];assert.equal(N.candidate(s,[0,0],'walk'),null);
});
test('source polygons retain holes and multiple polygons without a width buffer',()=>{
 const s=source(),outer=[[0,0],[20,0],[20,20],[0,20],[0,0]],hole=[[5,5],[15,5],[15,15],[5,15],[5,5]];
 s.geometry={type:'Polygon',coordinates:[outer,hole]};assert.equal(N.candidate(s,[2,2],'walk'),0);assert.equal(N.candidate(s,[10,10],'walk'),null);assert.equal(N.candidate(s,[-1,2],'walk'),null);
 s.geometry={type:'MultiPolygon',coordinates:[[outer,hole],[[[30,0],[40,0],[40,10],[30,10],[30,0]]]]};assert.equal(N.candidate(s,[35,5],'walk'),0);assert.equal(N.candidate(s,[10,10],'walk'),null);
});
test('overlapping compatible axes remain candidates; culling, occlusion and triangle budgets stay with the inspector',()=>{
 const a=source(),b=source();b.facts.id='osm/way/2';
 const r=pick(fixedI,[a,b],[10,3]);assert.equal(r.status,'road');assert.equal(r.selection.candidateCount,2);
 assert.equal(r.selection.sourceAttribution,'compatible-source-geometries');assert.equal(r.selection.physicalAccessibilityVerified,false);assert.equal(r.selection.navigation.graphRead,false);
 const empty=fixedI.attach({vertices:new Float32Array(),centerL93:[0,0]},[],{items:[a],truncated:false},true);
 assert.equal(fixedI.pickScene({camera:{e:10,n:3,h:20,yaw:0,pitch:-Math.PI/2},meshes:[{id:'cell',geometry:empty}],visibleCellIds:new Set(['cell'])}).status,'empty');
 const values=[];for(const height of [0,10])for(const p of [[9,height,-4],[10,height,-2],[11,height,-4]])values.push(...p,0,1,0,.5,.5,.5);
 const g=fixedI.attach({vertices:new Float32Array(values),centerL93:[0,0]},[{start:0,end:3,kind:'walk',rendering:'prepared-union',sourceId:null}],{items:[a],truncated:false},true),scene={camera:{e:10,n:3,h:20,yaw:0,pitch:-Math.PI/2},meshes:[{id:'cell',geometry:g}],visibleCellIds:new Set(['cell'])};
 assert.equal(fixedI.pickScene(scene).status,'occluded');assert.equal(fixedI.pickScene({...scene,maxTriangles:1}).status,'budget');assert.equal(fixedI.pickScene({...scene,visibleCellIds:new Set()}).status,'empty');
 // Real owner methods other than candidate selection are byte-identical.
 for(const name of ['facts','sources','attach','pickScene'])assert.equal(fixedI[name].toString(),I[name].toString());
});
function runtime(html){
 const c=vm.createContext({module:{exports:{}},Float32Array,Set,TextEncoder,TextDecoder,atob:x=>Buffer.from(x,'base64').toString('binary')});
 for(const id of ['viewer-geographic-core','viewer-terrain-core','viewer-dimension-core','viewer-fidelity72-core','viewer-architecture-core','viewer-roof-core','viewer-roof-fidelity73-core','viewer-material-extension70','viewer-architecture71-core',...(html.includes('id="viewer-navigation77-core"')?['viewer-navigation77-core']:[]),'viewer-road72-core','viewer-metropole-viewer-core','viewer-architecture74-core'])vm.runInContext(extract(html,id),c);
 return {G:c.__SOMA_V53_CORE__,T:c.__SOMA_TERRAIN56_CORE__,F:c.__SOMA_FIDELITY59_CORE__,A:c.__SOMA_ARCH68_CORE__,V:c.__SOMA_METRO_VIEW_CORE__,I:c.__SOMA_ROAD_INSPECTION72_CORE__};
}
const world=path.join(game,'data/v69/metropole'),parentPath=path.join(game,'metropole-viewer-v76.html');
test('native Charles Nédelec source and rendered walk union: only the false opposite-side candidate is removed',
 {skip:!fs.existsSync(path.join(world,'manifest.json'))||!fs.existsSync(parentPath)},()=>{
 const parent=fs.readFileSync(parentPath,'utf8'),patched=cp.execFileSync('python3',['-B','-c',"import sys;from pathlib import Path;sys.path.insert(0,'game');from tools import v77_navigation as n;print(n.patch_viewer(Path('game/metropole-viewer-v76.html').read_text(),{k:Path('game/src/v77',k+'.js').read_text() for k in n.MODULES}),end='')"],{cwd:path.dirname(game),maxBuffer:4*1024*1024,env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'}}).toString();
 const old=runtime(parent),now=runtime(patched),manifestRaw=fs.readFileSync(path.join(world,'manifest.json'));
 assert.equal(sha(manifestRaw),fixture.manifestSHA256);const manifest=JSON.parse(manifestRaw),tile=manifest.tiles.find(t=>t.cellId===fixture.tile.cellId);assert.deepEqual(tile,fixture.tile);
 const checked=d=>{const raw=fs.readFileSync(path.join(world,d.path));assert.equal(raw.length,d.bytes);assert.equal(sha(raw),d.sha256);return JSON.parse(zlib.gunzipSync(raw));};
 const record=checked(tile.vector),surface=checked(tile.surfaces),pack=checked(tile.terrain),feature=record.featureCollection.features.find(f=>f.id===fixture.feature.id);
 assert.deepEqual(feature,fixture.feature);assert.deepEqual(surface.roadMetadata[feature.id],fixture.profile);assert.deepEqual(surface.cell.surfaces.walk[fixture.triangleIndex],fixture.triangleLocal);
 assert.equal(record.sourceReceipt.sha256,fixture.sourcePbfSHA256);const grid=now.T.load(pack,tile.boundsL93),entry={tile,layers:{vector:record,surfaces:surface,terrain:{grid,pack}}},inputBefore=JSON.stringify({record,surface,pack});
 const options={details:false},a=old.V.buildTile(entry,{geo:old.G,terrain:old.T,fidelity:old.F,architecture:old.A},options),b=now.V.buildTile(entry,{geo:now.G,terrain:now.T,fidelity:now.F,architecture:now.A},options);
 assert(Buffer.from(a.vertices.buffer).equals(Buffer.from(b.vertices.buffer)));assert.deepEqual(clone(a.counts),clone(b.counts));assert.deepEqual(clone(a.roads72),clone(b.roads72));
 const [e,n]=fixture.pointL93,camera={e,n,h:grid.sample(e,n)+40,yaw:0,pitch:-Math.PI/2},pickActual=(api,g)=>api.pickScene({camera,meshes:[{id:tile.cellId,geometry:g}],visibleCellIds:new Set([tile.cellId])}),before=pickActual(old.I,a),after=pickActual(now.I,b);
 assert.equal(before.status,'road');assert.equal(after.status,'road');assert.equal(before.selection.surfaceKind,'walk');assert.equal(after.selection.surfaceKind,'walk');
 const falseCandidate=before.selection.candidates.find(x=>x.id===feature.id);assert(falseCandidate);close(falseCandidate.axisDistanceMeters,7.404572244420155);
 assert.equal(after.selection.candidates.some(x=>x.id===feature.id),false);assert(after.selection.candidateCount>0,'Other compatible mapped sidewalk axes must remain.');
 for(const key of ['selectedCellId','distanceMeters','hitL93','sourceAttribution','navigation','physicalAccessibilityVerified'])assert.deepEqual(clone(after.selection[key]),clone(before.selection[key]));
 assert.equal(JSON.stringify({record,surface,pack}),inputBefore);assert.equal(sha(fs.readFileSync(path.join(world,'manifest.json'))),fixture.manifestSHA256);
 const mask=new Uint8Array(grid.mask.length),missing=new now.T.Grid(grid,grid.heights,mask,pack,{}),emptyEntry={...entry,layers:{...entry.layers,terrain:{grid:missing,pack},vector:{...record,featureCollection:{...record.featureCollection,features:[feature]}}}};
 const gap=now.V.buildTile(emptyEntry,{geo:now.G,terrain:now.T,fidelity:now.F,architecture:now.A},options);assert.equal(gap.counts.roadTriangles,0);assert.equal(pickActual(now.I,gap).status,'empty');
 if(process.env.MASSILIA_NAVIGATION77_REPORT){const report={schema:'soma-massilia/navigation77-real-source-proof/1',fixtureSHA256:sha(fs.readFileSync(path.join(__dirname,'navigation-source.json'))),manifestSHA256:fixture.manifestSHA256,cellId:tile.cellId,sourceId:feature.id,pointL93:fixture.pointL93,terrainAltitudeNGF:grid.sample(e,n),before:clone(before),after:clone(after),renderedVerticesSHA256:sha(Buffer.from(b.vertices.buffer)),renderedGeometryByteIdentical:true,nativeNavigationChanged:false,sourceAssetsChanged:false,limits:'Compatible source axes of a rendered union remain candidates; no surface ownership, physical access or 1:1 survey is certified.'};fs.writeFileSync(process.env.MASSILIA_NAVIGATION77_REPORT,JSON.stringify(report,null,2)+'\n');}
});
