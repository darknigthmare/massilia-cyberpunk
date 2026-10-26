'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {createHash}=require('node:crypto'),{gzipSync}=require('node:zlib'),path=require('node:path');
const Preview=require('../../src/v70/route-preview-core.js');
const baseline=fs.readFileSync(path.join(__dirname,'../../baseline/v66.html'),'utf8');
const source=baseline.match(/<script[^>]+id="soma-v63-nav-core"[^>]*>([\s\S]*?)<\/script>/)[1];
const hash=v=>createHash('sha256').update(v).digest('hex'),mod={exports:{}};
assert.equal(hash(source),Preview.CORE_SHA256);assert.equal(hash(baseline),Preview.BASELINE_SHA256);
vm.runInNewContext(source,{module:mod});const core=mod.exports;
const ORIGIN=[892951.6480966414,6247274.566415883],PBF='a'.repeat(64),PACK='b'.repeat(64),TOPO='c'.repeat(64),GEOM='d'.repeat(64);
const pt=(e,n=0)=>({e:ORIGIN[0]+e,n:ORIGIN[1]+n}),clone=v=>JSON.parse(JSON.stringify(v));
function tile(x=0,y=0){return {cellId:x===0&&y===0?'V52-MC-33':`V52-MC-${x>=0?'E':'W'}${Math.abs(x).toString().padStart(2,'0')}-${y<=0?'N':'S'}${Math.abs(y).toString().padStart(2,'0')}`,
 gridX:x,gridY:y,contentSHA256:hash(`${x}:${y}`),boundsL93:[ORIGIN[0]+x*250-125,ORIGIN[1]-y*250-125,ORIGIN[0]+x*250+125,ORIGIN[1]-y*250+125]};}
function graph(t,nodes,edgeRows,turns=[]){
 const ways=Object.fromEntries(edgeRows.map(e=>[e[2],{name:'Rue native '+e[2],geometrySHA256:GEOM}]));
 const edges=edgeRows.map(e=>[e[0],e[1],e[2],Math.hypot(nodes[e[0]][1]-nodes[e[1]][1],nodes[e[0]][2]-nodes[e[1]][2]),e[3]??15,e[4]??0,[t.cellId],e[5]??1]);
 return {schema:'soma/navigation-source/1',version:'0.69.0',sourcePbfSHA256:PBF,sourcePackSHA256:PACK,nativeTopologySHA256:TOPO,routingCoreSHA256:Preview.CORE_SHA256,
  nodes:nodes.map(n=>[n[0],...Object.values(pt(n[1],n[2]))]),edges,ways,turns,cellHashes:{[t.cellId]:t.contentSHA256},nodeTags:{},
  edgeSources:edgeRows.map((e,i)=>({wayId:e[2],segmentIndex:e[5]??1,t0:e[6]??0,t1:e[7]??1,startNative:nodes[e[0]][0].startsWith('n/'),endNative:nodes[e[1]][0].startsWith('n/')})),
  bicycleMasks:edges.map(()=>3),sourceStatus:{nativeNodeIdentity:true,vectorConstrained:true,nodeTagsComplete:true,physicalAccessibilityVerified:false,physicalMovementReady:false,campaignRoutingActivated:false}};
}
function setup(specs,{mutateWorld,budgets,loadAsset,decode,now,mutateGraph}={}){
 const assets=new Map(),tiles=[],graphs=[];
 for(let i=0;i<specs.length;i++){
  const [t,g]=specs[i];if(mutateGraph)mutateGraph(g,i);
  const raw=Buffer.from(JSON.stringify(g)),data=gzipSync(raw);
  t.navigation={path:t.cellId+'.json.gz',bytes:data.length,decodedBytes:raw.length,sha256:hash(data),encoding:'gzip-json'};
  tiles.push(t);graphs.push(g);assets.set(t.navigation.path,data);
 }
 const world={schema:'soma-metropole/world-manifest/1',crs:'EPSG:2154',units:'m',cellSize:250,origin:ORIGIN,source:{sha256:PBF},sourcePackSHA256:PACK,nativeTopologySHA256:TOPO,
  navigationCore:{scriptId:'soma-v63-nav-core',version:'0.63.0',sha256:Preview.CORE_SHA256,baselineSHA256:Preview.BASELINE_SHA256},
  coverageExplicitPartial:true,physicalMovementReady:false,campaignRoutingActivated:false,tiles};
 mutateWorld?.(world);
 const requests=[];
 const api=Preview.create({world,routerCore:core,routerCoreSHA256:Preview.CORE_SHA256,budgets,decode,now,
  loadAsset:loadAsset||(async(d,options)=>{requests.push({d,options});return assets.get(d.path);})});
 return {api,world,assets,requests,graphs};
}
function simple(options){const t=tile();return setup([[t,graph(t,[['n/1',-100,0],['n/2',100,0]],[[0,1,'100']])]],options);}
function seam(options){const a=tile(),b=tile(1);return setup([
 [a,graph(a,[['n/1',-50,0],['clip/100/1/0.500000000000',125,0]],[[0,1,'100',15,0,1,0,.5]])],
 [b,graph(b,[['clip/100/1/0.500000000000',125,0],['n/2',300,0]],[[0,1,'100',15,0,1,.5,1]])]],options);}

test('real frozen core63 is reused and a native clipped seam joins without source mutation',async()=>{
 const f=seam(),before=JSON.stringify(f.world)+JSON.stringify(f.graphs),result=await f.api.preview({start:pt(-40,3),end:pt(290,4),mode:'foot'});
 assert.equal(result.status,'route',result.reason);assert.equal(result.route.lengthMeters,330);assert.equal(result.route.segments.length,2);
 assert.deepEqual(result.route.points,[pt(-40),pt(125),pt(290)]);assert.equal(result.anchors.start.distanceMeters,3);
 assert.equal(result.anchors.start.connectionProvided,false);assert.equal(result.route.completeBetweenAnchors,true);assert.equal(result.route.partialNetwork,true);
 assert.deepEqual(result.route.segments.map(s=>s.wayId),['100','100']);assert.equal(result.route.segments[0].sourceT1,.5);
 assert.equal(result.physicalAccessibilityVerified,false);assert.equal(result.campaignRoutingActivated,false);
 assert.equal(JSON.stringify(f.world)+JSON.stringify(f.graphs),before);assert.equal(f.api.snapshot().residentGraphs,0);
 assert(f.requests.every(r=>r.options.maxEncodedBytes===r.d.bytes&&r.options.signal instanceof AbortSignal));
});
test('coordinates that cross without common native identity never create a junction',async()=>{
 const t=tile(),f=setup([[t,graph(t,[['n/1',-100,0],['n/2',100,0],['n/3',0,-100],['n/4',0,100]],[[0,1,'100'],[2,3,'200']])]]);
 const r=await f.api.preview({start:pt(-80),end:pt(0,80),mode:'foot'});
 assert.equal(r.status,'interrupted');assert.equal(r.code,'no_route_in_loaded_network');assert.equal(r.route,null);
});
test('ambiguous nearby axes require an explicit source choice and never draw click connectors',async()=>{
 const t=tile(),f=setup([[t,graph(t,[['n/1',-100,-2],['n/2',100,-2],['n/3',-100,2],['n/4',100,2]],[[0,1,'100'],[2,3,'200']])]]);
 const r=await f.api.preview({start:pt(-80),end:pt(80),mode:'foot'});assert.equal(r.code,'axis_ambiguous');assert.equal(r.axisChoices.start.length,2);
 const key=r.axisChoices.start.find(q=>q.wayId==='100').key;
 const chosen=await f.api.preview({start:pt(-80),end:pt(80),mode:'foot',startAxisKey:key,endAxisKey:key});
 assert.equal(chosen.status,'route');assert.deepEqual(chosen.route.points,[pt(-80,-2),pt(80,-2)]);
});
test('coincident non-native endpoint alternatives from core63 are refused',async()=>{
 const t=tile(),f=setup([[t,graph(t,[['n/1',-100,0],['n/2',100,0],['n/3',0,-100],['n/4',0,100]],[[0,1,'100'],[2,3,'200']])]]);
 const choices=await f.api.preview({start:pt(0),end:pt(0,80),mode:'foot'});assert.equal(choices.code,'axis_ambiguous');
 const r=await f.api.preview({start:pt(0),end:pt(0,80),mode:'foot',startAxisKey:choices.axisChoices.start.find(q=>q.wayId==='100').key});
 assert.equal(r.code,'source_endpoint_conflict');assert.equal(r.route,null);
});
test('zero-length results cannot claim a transition between unrelated coincident axes',async()=>{
 const t=tile(),f=setup([[t,graph(t,[['n/1',-100,0],['n/2',100,0],['n/3',0,-100],['n/4',0,100]],[[0,1,'100'],[2,3,'200']])]]);
 const choices=await f.api.preview({start:pt(0),end:pt(0)}),keys=choices.axisChoices.start;
 const r=await f.api.preview({start:pt(0),end:pt(0),startAxisKey:keys.find(q=>q.wayId==='100').key,endAxisKey:keys.find(q=>q.wayId==='200').key});
 assert.equal(r.code,'source_endpoint_conflict');assert.equal(r.route,null);
});
test('one-way car access remains directional while pedestrian source access is retained',async()=>{
 const f=simple({mutateGraph(g){g.edges[0][4]=7;}});
 assert.equal((await f.api.preview({start:pt(-80),end:pt(80),mode:'car'})).status,'route');
 assert.equal((await f.api.preview({start:pt(80),end:pt(-80),mode:'car'})).status,'interrupted');
 assert.equal((await f.api.preview({start:pt(80),end:pt(-80),mode:'foot'})).status,'route');
});
test('actual frozen core enforces car turn rules and step avoidance',async()=>{
 const t=tile(),g=graph(t,[['n/1',-100,0],['n/2',0,0],['n/3',0,100]],[[0,1,'100'],[1,2,'200',15,1]],
  [{id:'300',via:'n/2',from:'100',to:'200',kind:'no_right_turn'}]),f=setup([[t,g]]);
 assert.equal((await f.api.preview({start:pt(-80),end:pt(0,80),mode:'car'})).code,'no_route_in_loaded_network');
 assert.equal((await f.api.preview({start:pt(-80),end:pt(0,80),mode:'foot'})).status,'route');
 assert.notEqual((await f.api.preview({start:pt(-80),end:pt(0,80),mode:'foot',avoidSteps:true})).status,'route');
});
test('prepared refusals for barriers, covered roads and unresolved conditions are not revived',async()=>{
 const t=tile(),g=graph(t,[['n/1',-100,0],['n/2',-20,0],['n/3',20,0],['n/4',100,0]],[[0,1,'100'],[2,3,'200']]);
 g.nodeTags={'n/2':{barrier:'gate',locked:'yes'}};g.ways['300']={geometrySHA256:GEOM,covered:'yes','access:conditional':'yes @ (Mo-Fr)'};
 const f=setup([[t,g]]),r=await f.api.preview({start:pt(-80),end:pt(80),mode:'foot'});
 assert.equal(r.code,'no_route_in_loaded_network');assert.equal(r.route,null);
});
test('a missing cell is explicit and is never bridged by proximity',async()=>{
 const f=seam(),reader=async(d)=>{if(d.path.includes('E01'))throw Object.assign(new Error('missing'),{status:404});return f.assets.get(d.path);};
 const api=Preview.create({world:f.world,routerCore:core,routerCoreSHA256:Preview.CORE_SHA256,loadAsset:reader});
 const r=await api.preview({start:pt(-40),end:pt(290),mode:'foot'});
 assert.equal(r.status,'interrupted');assert.equal(r.route,null);assert.deepEqual(r.coverage.missingCells,[tile(1).cellId]);assert.equal(r.coverage.completeRequestedSector,false);
});
test('cell count caps loading and an incomplete sector is explicit',async()=>{
 const f=seam({budgets:{maxCells:1}}),r=await f.api.preview({start:pt(-40),end:pt(290),mode:'foot'});
 assert.equal(f.requests.length,1);assert.equal(r.route,null);assert.equal(r.coverage.requestedCells,2);assert.equal(r.coverage.omittedCells.length,1);
});
test('SHA, byte length, PBF, topology, core and cell source mismatches refuse analysis',async()=>{
 const mutations=[g=>g.sourcePbfSHA256='e'.repeat(64),g=>g.sourcePackSHA256='e'.repeat(64),g=>g.nativeTopologySHA256='e'.repeat(64),
  g=>g.routingCoreSHA256='e'.repeat(64),g=>g.cellHashes['V52-MC-33']='e'.repeat(64),g=>g.nodes[0][0]='1',g=>g.edgeSources[0].t1=2,
  g=>g.sourceStatus.physicalMovementReady=true,g=>g.ways['100'].geometrySHA256='missing'];
 for(const mutateGraph of mutations){const f=simple({mutateGraph}),r=await f.api.preview({start:pt(-80),end:pt(80)});assert.equal(r.status,'refused',r.reason);assert.equal(r.code,'integrity');}
 for(const corrupt of [bytes=>Buffer.concat([bytes,Buffer.from('x')]),bytes=>{const b=Buffer.from(bytes);b[20]^=1;return b;}]){
  const f=simple();for(const[k,v]of f.assets)f.assets.set(k,corrupt(v));assert.equal((await f.api.preview({start:pt(-80),end:pt(80)})).code,'integrity');
 }
});
test('native coordinate, metadata, permissions and turn conflicts across tiles are refused',async()=>{
 for(const change of [g=>g.nodes[0][1]+=.001,g=>g.ways['100'].name='Other name']){
  const f=seam({mutateGraph(g,i){if(i===1)change(g);}}),r=await f.api.preview({start:pt(-40),end:pt(290)});
  assert.equal(r.status,'refused');assert(['conflict','integrity'].includes(r.code));
 }
});
test('strict per-asset, decoded, resident and graph budgets bound analysis',async()=>{
 let f=simple({budgets:{maxAssetEncodedBytes:1}}),r=await f.api.preview({start:pt(-80),end:pt(80)});assert.equal(r.code,'asset_budget');assert.equal(f.requests.length,0);
 f=simple({decode:async()=>new Uint8Array(2*1024*1024+1)});r=await f.api.preview({start:pt(-80),end:pt(80)});assert.equal(r.code,'decoded_budget');
 f=simple({budgets:{maxNodes:1}});r=await f.api.preview({start:pt(-80),end:pt(80)});assert.equal(r.status,'refused');assert.equal(r.code,'integrity');
 assert.throws(()=>simple({budgets:{maxResidentBytes:1}}),/mémoire/);assert.throws(()=>simple({budgets:{maxCells:65}}),/Budget invalide/);
 assert.throws(()=>simple({budgets:{maxExpanded:Infinity}}),/Budget invalide/);assert.throws(()=>simple({budgets:{unknown:1}}),/Budget inconnu/);
});
test('catalogue metadata and graphs share the resident accounting limit',async()=>{
 const f=simple(),decoded=f.world.tiles[0].navigation.decodedBytes,catalogue=f.api.snapshot().catalogueAccountedBytes;
 const api=Preview.create({world:f.world,routerCore:core,routerCoreSHA256:Preview.CORE_SHA256,
  budgets:{maxDecodedBytes:decoded,maxResidentBytes:decoded*8+catalogue-1},loadAsset:async d=>f.assets.get(d.path)});
 assert.equal((await api.preview({start:pt(-80),end:pt(80)})).code,'resident_budget');
 assert.throws(()=>simple({budgets:{maxDecodedBytes:1,maxResidentBytes:8}}),e=>e.code==='catalogue_budget');
});
test('a stalled reader is aborted at the deadline and graph storage is released',async()=>{
 let signal;const f=simple({budgets:{maxMilliseconds:20},loadAsset:async(_d,o)=>{signal=o.signal;return new Promise(()=>{});}});
 const r=await f.api.preview({start:pt(-80),end:pt(80)});assert.equal(r.code,'time_budget');assert.equal(signal.aborted,true);assert.equal(f.api.snapshot().busy,false);assert.equal(f.api.snapshot().residentGraphs,0);
});
test('external cancellation, concurrent requests and explicit cancellation remain isolated',async()=>{
 const f=simple({loadAsset:async()=>new Promise(()=>{})}),abort=new AbortController();
 const pending=f.api.preview({start:pt(-80),end:pt(80),signal:abort.signal});await assert.rejects(f.api.preview({start:pt(-80),end:pt(80)}),/déjà/);abort.abort();
 assert.equal((await pending).code,'cancelled');assert.equal(f.api.snapshot().busy,false);
 const next=f.api.preview({start:pt(-80),end:pt(80)});f.api.cancel();assert.equal((await next).status,'interrupted');assert.equal(f.api.snapshot().residentGraphs,0);
});
test('deadline after synchronous router work discards the result instead of presenting it',async()=>{
 let time=0;const f=simple({now:()=>time}),slow={...core,createRouter(g){const r=core.createRouter(g);return {...r,route(...args){const out=r.route(...args);time=4000;return out;}};}};
 const api=Preview.create({world:f.world,routerCore:slow,routerCoreSHA256:Preview.CORE_SHA256,now:()=>time,loadAsset:async d=>f.assets.get(d.path)});
 const r=await api.preview({start:pt(-80),end:pt(80)});assert.equal(r.code,'time_budget');assert.equal(r.route,null);
});
test('the real router search cap interrupts rather than returning a truncated successful path',async()=>{
 const t=tile(),nodes=Array.from({length:40},(_,i)=>['n/'+(i+1),-100+i*5,0]),edges=Array.from({length:39},(_,i)=>[i,i+1,'100',15,0,i+1]);
 const f=setup([[t,graph(t,nodes,edges)]],{budgets:{maxExpanded:24}}),r=await f.api.preview({start:pt(-99),end:pt(94)});
 assert.equal(r.status,'interrupted');assert.equal(r.code,'search_budget');assert.equal(r.route,null);
});
test('mutable caller coordinates do not alter endpoints during asynchronous reads',async()=>{
 let release;const f=simple(),api=Preview.create({world:f.world,routerCore:core,routerCoreSHA256:Preview.CORE_SHA256,
  loadAsset:async d=>{await new Promise(resolve=>release=resolve);return f.assets.get(d.path);}});
 const request={start:pt(-80),end:pt(80),mode:'foot'},pending=api.preview(request);request.end.e+=10000;request.mode='car';release();
 const r=await pending;assert.equal(r.status,'route');assert.deepEqual(r.route.points,[pt(-80),pt(80)]);assert.equal(r.route.mode,'foot');
 assert.equal((await api.preview({start:pt(-80),end:pt(80),signal:{}})).code,'position');
});
test('world identity is copied and changing the caller manifest cannot redirect a running analysis',async()=>{
 const f=simple(),before=JSON.stringify(f.world);f.world.source.sha256='e'.repeat(64);f.world.tiles[0].navigation.path='elsewhere';
 const r=await f.api.preview({start:pt(-80),end:pt(80)});assert.equal(r.status,'route');assert.equal(r.sourcePbfSHA256,PBF);assert.notEqual(JSON.stringify(f.world),before);
 assert.throws(()=>simple({mutateWorld(w){w.navigationCore.sha256='e'.repeat(64);}}),/moteur NAV/);
 assert.throws(()=>simple({mutateWorld(w){w.physicalMovementReady=true;}}),/Monde NAV/);
});
test('there is no DOM, fetch, storage or campaign dependency in the browser export',()=>{
 const runtime=fs.readFileSync(path.join(__dirname,'../../src/v70/route-preview-core.js'),'utf8'),context={};
 vm.runInNewContext(runtime,context);assert.equal(context.__SOMA_ROUTE70_CORE__.VERSION,'0.70.0');
 for(const name of ['document','fetch','localStorage','sessionStorage','__SOMA__'])assert.equal(Object.hasOwn(context,name),false);
});
test('real AMP world: Belsunce to République uses verified sectors and actual native turns',
 {skip:!process.env.MASSILIA_ROUTE_WORLD},async()=>{
 const file=path.resolve(process.env.MASSILIA_ROUTE_WORLD),base=path.dirname(file),raw=fs.readFileSync(file),world=JSON.parse(raw),loads=[];
 const {gunzipSync}=require('node:zlib');
 function location(cell,name){const t=world.tiles.find(t=>t.cellId===cell),g=JSON.parse(gunzipSync(fs.readFileSync(path.join(base,t.navigation.path))));
  const e=g.edges.filter(e=>g.ways[e[2]].name===name).sort((a,b)=>b[3]-a[3])[0],a=g.nodes[e[0]],z=g.nodes[e[1]];
  return {e:(a[1]+z[1])/2,n:(a[2]+z[2])/2};}
 const api=Preview.create({world,routerCore:core,routerCoreSHA256:Preview.CORE_SHA256,
  loadAsset:async(d,o)=>{const raw=fs.readFileSync(path.join(base,d.path));assert(raw.length<=o.maxEncodedBytes);loads.push(o.cellId);return raw;}});
 const r=await api.preview({start:location('V52-MC-33','Cours Belsunce'),end:location('V52-MC-31','Rue de la République'),mode:'foot',maxAxisDistanceM:.05});
 assert.equal(r.status,'route',r.reason);assert(Math.abs(r.route.lengthMeters-599.4866557693185)<1e-6);
 assert.deepEqual([...new Set(r.route.segments.map(s=>s.name))],['Cours Belsunce','Rue Tapis Vert','Rue Colbert','Place Sadi Carnot','Rue de la République']);
 assert.equal(api.snapshot().catalogueCells,51809);assert.equal(loads.length,15);assert(r.resources.decodedBytes*8<10*1024*1024);
 assert(r.resources.catalogueAccountedBytes>40*1024*1024);assert(r.resources.accountedResidentBytes<64*1024*1024);
 assert.equal(hash(fs.readFileSync(file)),hash(raw));assert.equal(api.snapshot().residentGraphs,0);
});
