'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const P=require('../../src/v71/route-presentation-core.js');
const hashes={sourcePbfSHA256:'a'.repeat(64),sourcePackSHA256:'b'.repeat(64),nativeTopologySHA256:'c'.repeat(64),routingCoreSHA256:'d'.repeat(64)};
const world={source:{sha256:hashes.sourcePbfSHA256},sourcePackSHA256:hashes.sourcePackSHA256,nativeTopologySHA256:hashes.nativeTopologySHA256,navigationCore:{sha256:hashes.routingCoreSHA256}};
const a={e:892000,n:6247000},b={e:892010,n:6247000},c={e:892010,n:6247010};
const segment=(a,b,wayId='123',extra={})=>({a:{...a},b:{...b},wayId,name:'Rue source',steps:false,segmentIndex:1,sourceT0:0,sourceT1:1,cellIds:['cell-source'],...extra});
function result(segments=[segment(a,b)]){return{schema:'soma-metropole/route-preview/1',status:'route',code:'source_axis_route',...hashes,
 physicalAccessibilityVerified:false,campaignRoutingActivated:false,route:{segments,lengthMeters:segments.reduce((sum,s)=>sum+Math.hypot(s.b.e-s.a.e,s.b.n-s.a.n),0),completeBetweenAnchors:true}};}
const flat=(b,h=10)=>[[[b.minE,b.minN,h],[b.maxE,b.minN,h],[b.minE,b.maxN,h]],[[b.maxE,b.minN,h],[b.maxE,b.maxN,h],[b.minE,b.maxN,h]]];
const context={terrainTriangles:b=>flat(b),spanAvailable:()=>true};
const near=(x,y)=>assert(Math.abs(x-y)<1e-5,`${x} != ${y}`);

test('consecutive native segments group by way and steps without merging later returns',()=>{
 const r=result([segment(a,b),segment(b,c),segment(c,b,'456',{name:'Autre rue',steps:true}),segment(b,a)]),before=JSON.stringify(r),plan=P.itinerary(r);
 assert.equal(plan.groups.length,3);assert.equal(plan.groups[0].segments,2);assert.equal(plan.groups[0].lengthMeters,20);
 assert.equal(plan.groups[1].steps,true);assert.equal(plan.groups[2].wayId,'123');assert.equal(plan.totalMeters,40);assert.equal(JSON.stringify(r),before);
});
test('long itineraries keep a bounded prefix and account for the unrendered tail',()=>{
 const segments=[];for(let i=0;i<P.MAX_GROUPS+5;i++)segments.push(segment({e:a.e+i,n:a.n},{e:a.e+i+1,n:a.n},String(i+1)));
 segments.push(segment({e:a.e+P.MAX_GROUPS+5,n:a.n},{e:a.e+P.MAX_GROUPS+6,n:a.n},String(P.MAX_GROUPS)));
 const plan=P.itinerary(result(segments));assert.equal(plan.groups.length,P.MAX_GROUPS);assert.equal(plan.groups.at(-1).lengthMeters,1);assert.equal(plan.truncatedMeters,6);
});
test('alternatives use only declared names, identities, source steps and projection distances',()=>{
 assert.equal(P.choiceLabel({wayId:'123',name:'Rue\nRépublique',steps:true,distanceMeters:1.234}),'Rue République · OSM 123 · escaliers · 1.23 m du point');
 assert.equal(P.choiceLabel({wayId:'123',distanceMeters:0}),'Voie OSM 123 · 0.00 m du point');
 assert(P.choiceLabel({wayId:'123',name:'x'.repeat(1000),distanceMeters:2}).length<300);
});
test('source record rejects every foreign fingerprint and owns detached coordinate copies',()=>{
 const r=result(),owned=P.record(r,world);r.route.segments[0].a.e++;r.route.segments[0].cellIds[0]='changed';
 assert.equal(owned.segments[0].a.e,a.e);assert.equal(owned.segments[0].cellIds[0],'cell-source');
 for(const k of Object.keys(hashes)){const bad=result();bad[k]='e'.repeat(64);assert.throws(()=>P.record(bad,world),/autre édition/);}
 assert.throws(()=>P.record(result(),null),/autre édition/);
});
test('unavailable, disconnected, fabricated lengths and unbounded coordinates are refused',()=>{
 for(const change of [r=>{r.status='interrupted';},r=>{r.route.lengthMeters++;},r=>{r.physicalAccessibilityVerified=true;},
  r=>{r.route.segments.push(segment(c,b));r.route.lengthMeters+=10;},r=>{r.route.segments[0].a.e=1e300;},r=>{r.route.segments[0].sourceT1=2;}]){
  const r=result();change(r);assert.throws(()=>P.itinerary(r));
 }
});
test('upward marker ribbons follow source coordinates and preserve source data',()=>{
 const r=result(),record=P.record(r,world),before=JSON.stringify(record),shape=P.buildOverlay(record,context);
 assert.equal(shape.renderedSpans,2);assert.equal(shape.omittedSpans,0);assert.equal(shape.vertices.length,2*6*9);assert.equal(shape.geometryBytes,shape.vertices.byteLength);
 assert.equal(shape.renderedMeters,10);assert.equal(JSON.stringify(record),before);assert(shape.geometryBytes<=shape.maxBytes);
 for(let i=0;i<shape.vertices.length;i+=9){near(shape.vertices[i+1],10.25);near(shape.vertices[i+3],0);near(shape.vertices[i+4],1);}
 for(let i=0;i<shape.vertices.length;i+=27){const v=shape.vertices,ax=v[i+9]-v[i],az=v[i+11]-v[i+2],bx=v[i+18]-v[i],bz=v[i+20]-v[i+2];assert(az*bx-ax*bz>0,'upward winding');}
});
test('a missing or partial terrain interval makes a gap without connecting across it',()=>{
 const record=P.record(result([segment(a,{e:a.e+20,n:a.n})]),world),bounds=[];
 const shape=P.buildOverlay(record,{terrainTriangles:b=>flat(b,5),spanAvailable:b=>{bounds.push(b);return b.minE>=a.e+10;}});
 assert.equal(shape.consideredSpans,4);assert.equal(shape.omittedSpans,2);assert.equal(shape.renderedSpans,2);assert.equal(shape.renderedMeters,10);
 const xs=[];for(let i=0;i<shape.vertices.length;i+=9)xs.push(shape.vertices[i]+shape.centerL93[0]);assert(Math.min(...xs)>=a.e+10);
 assert(bounds.every(b=>b.maxE-b.minE<=5.00001&&b.maxN-b.minN<=1.30001));
});
test('nonfinite heights omit complete spans, never turn missing ground into sea level',()=>{
 for(const missing of [null,undefined,NaN,Infinity]){const shape=P.buildOverlay(P.record(result(),world),{terrainTriangles:b=>flat(b).map(t=>t.map(p=>[p[0],p[1],missing])),spanAvailable:()=>true});assert.equal(shape.geometryBytes,0);assert.equal(shape.omittedSpans,2);}
});
test('marker workload and geometry have an explicit hard cap even for a long valid axis',()=>{
 const shape=P.buildOverlay(P.record(result([segment(a,{e:a.e+100000,n:a.n})]),world),context);
 assert.equal(shape.consideredSpans,P.MAX_SPANS);assert.equal(shape.truncated,true);assert.equal(shape.geometryBytes,shape.maxBytes);
 for(const options of [{maxSpans:4097},{spacing:0},{width:100},{lift:2}])assert.throws(()=>P.buildOverlay(P.record(result(),world),{...context,...options}));
});
test('a zero-length native result has no marker geometry',()=>{
 const record=P.record(result([]),world),shape=P.buildOverlay(record,context);assert.equal(shape.geometryBytes,0);assert.deepEqual(shape.centerL93,[0,0]);
});
test('ribbons split at actual native DEM triangles instead of cutting below a five-metre peak',()=>{
 const baseline=fs.readFileSync(path.resolve(__dirname,'../../baseline/v66.html'),'utf8'),source=baseline.match(/<script[^>]+id="soma-v56-terrain-core"[^>]*>([\s\S]*?)<\/script>/)[1],m={exports:{}};
 vm.runInNewContext(source,{module:m,TextEncoder,TextDecoder});
 const grid=new m.exports.Grid({x0:a.e-2.5,n0:a.n+5,step:5,cols:3,rows:3},new Float64Array([0,0,0,0,10,0,0,0,0]),new Uint8Array(9).fill(1),{},{}),native=[];
 const bounds=[grid.x0,grid.n0-10,grid.x0+10,grid.n0],ce=(bounds[0]+bounds[2])/2,cn=(bounds[1]+bounds[3])/2;
 grid.cellTriangles(bounds,t=>native.push(t.map(p=>[p[0]+ce,cn-p[2],p[1]])));
 const shape=P.buildOverlay(P.record(result([segment(a,{e:a.e+5,n:a.n})]),world),{terrainTriangles:()=>native,spanAvailable:()=>true}),v=shape.vertices;
 assert.equal(shape.renderedMeters,5);assert(shape.vertices.length>6*9,'native break requires additional triangles');
 let highest=0;
 for(let i=0;i<v.length;i+=9){const e=v[i]+shape.centerL93[0],n=shape.centerL93[1]-v[i+2];near(v[i+1],grid.sample(e,n)+.25);highest=Math.max(highest,v[i+1]);}
 near(highest,10.25);
 for(let i=0;i<v.length;i+=27){const e=(v[i]+v[i+9]+v[i+18])/3+shape.centerL93[0],n=shape.centerL93[1]-(v[i+2]+v[i+11]+v[i+20])/3,h=(v[i+1]+v[i+10]+v[i+19])/3;near(h,grid.sample(e,n)+.25);}
});
test('partial or overlapping native triangle coverage never claims a complete marked span',()=>{
 const record=P.record(result(),world);
 for(const read of [b=>flat(b).slice(0,1),b=>[...flat(b),...flat(b)],()=>null,()=>Array(65).fill([[0,0,0],[1,0,0],[0,1,0]])]){
  const shape=P.buildOverlay(record,{terrainTriangles:read,spanAvailable:()=>true});assert.equal(shape.renderedMeters,0);assert.equal(shape.geometryBytes,0);assert.equal(shape.omittedSpans,2);
 }
});
test('actual AMP route yields source named steps and bounded complete-terrain markers',{skip:!process.env.MASSILIA_ROUTE_WORLD},async()=>{
 const filename=process.env.MASSILIA_ROUTE_WORLD,w=JSON.parse(fs.readFileSync(filename,'utf8')),
  baseline=fs.readFileSync(path.resolve(__dirname,'../../baseline/v66.html'),'utf8'),source=baseline.match(/<script[^>]+id="soma-v63-nav-core"[^>]*>([\s\S]*?)<\/script>/)[1],m={exports:{}};
 vm.runInNewContext(source,{module:m});
 const Core=require('../../src/v70/route-preview-core.js'),api=Core.create({world:w,routerCore:m.exports,routerCoreSHA256:Core.CORE_SHA256,
  loadAsset:async d=>fs.readFileSync(path.join(path.dirname(filename),d.path))});
 const r=await api.preview({start:{e:892990.7467568527,n:6247192.082113549},end:{e:892549.919307699,n:6247324.880334723},mode:'foot',maxAxisDistanceM:.05});
 assert.equal(r.status,'route',r.reason);near(r.route.lengthMeters,599.486655769);const plan=P.itinerary(r),record=P.record(r,w),shape=P.buildOverlay(record,context);
 assert(plan.groups.some(g=>g.name==='Rue de la République'));assert(plan.groups.length>1);near(plan.groups.reduce((sum,g)=>sum+g.lengthMeters,0),r.route.lengthMeters);
 assert(shape.renderedSpans>100);assert(shape.geometryBytes<=shape.maxBytes);assert.equal(api.snapshot().residentGraphs,0);
 const tm={exports:{}},terrainSource=baseline.match(/<script[^>]+id="soma-v56-terrain-core"[^>]*>([\s\S]*?)<\/script>/)[1];
 vm.runInNewContext(terrainSource,{module:tm,TextEncoder,TextDecoder,atob});
 const index=require('../../src/v70/world-index.js').createWorldIndex(w),resident=new Set(r.coverage.loadedCells),meshes=new Map();
 for(const id of resident){const tile=index.get(id),d=tile.terrain,encoded=fs.readFileSync(path.join(path.dirname(filename),d.path));
  assert.equal(require('node:crypto').createHash('sha256').update(encoded).digest('hex'),d.sha256);
  const pack=JSON.parse(require('node:zlib').gunzipSync(encoded));meshes.set(id,{token:{layers:{terrain:{grid:tm.exports.load(pack,tile.boundsL93)}}}});
 }
 const sourceContext=require('node:child_process').execFileSync('python3',['-c','from tools.v71_route_viewer import CONTEXT; print(CONTEXT)'],{cwd:path.resolve(__dirname,'../..'),encoding:'utf8'}),bridge={
  root:{__SOMA_ROUTE71_PRESENTATION__:P},worldIndex:index,manifest:w,targetIds:resident,renderer:{registry:{meshes}},Math};
 vm.createContext(bridge);vm.runInContext(sourceContext,bridge);
 const native=P.buildOverlay(record,{terrainTriangles:bridge.route71Terrain,spanAvailable:bridge.route71Span});
 assert(native.renderedSpans>100);assert(native.geometryBytes<=native.maxBytes);
 for(let i=0;i<native.vertices.length;i+=27){const v=native.vertices,e=(v[i]+v[i+9]+v[i+18])/3+native.centerL93[0],n=native.centerL93[1]-(v[i+2]+v[i+11]+v[i+20])/3,
  h=(v[i+1]+v[i+10]+v[i+19])/3,tile=index.cellAt(e,n),ground=meshes.get(tile.cellId).token.layers.terrain.grid.sample(e,n);
  assert(Number.isFinite(ground));assert(Math.abs(h-ground-.25)<.002,'native surface centroid follows actual DEM');
 }
});
