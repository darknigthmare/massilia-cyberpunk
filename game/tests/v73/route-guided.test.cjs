'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {Preview,core,pt,tile,graph,setup,simple}=require('./route-fixture.cjs');
function detour(options={}){
 const rows=[
  [0,0,[[-50,0],[0,125]]],[0,-1,[[0,125],[0,375]]],[0,-2,[[0,375],[0,625]]],
  [0,-3,[[0,625],[0,750],[125,750]]],[1,-3,[[125,750],[375,750]]],
  [2,-3,[[375,750],[550,750],[550,625]]],[2,-2,[[550,625],[550,375]]],
  [2,-1,[[550,375],[550,125]]],[2,0,[[550,125],[550,0]]]
 ],ids=new Map();let segment=0;
 return setup(rows.map(([x,y,points])=>{const t=tile(x,y),nodes=points.map(([e,n])=>{
  const key=e+':'+n;if(!ids.has(key))ids.set(key,'n/'+(ids.size+1));return [ids.get(key),e,n];
 });return [t,graph(t,nodes,points.slice(1).map((_,i)=>[i,i+1,'100',15,0,++segment]))];}),options);
}
const query={start:pt(-40,20),end:pt(550,10),maxAxisDistanceM:10,mode:'foot'};
test('a guide selects a real native detour omitted by both direct attempts, without altering budgets',async()=>{
 const f=detour(),before=JSON.stringify(f.world)+JSON.stringify(f.graphs),q={...query,start:pt(-48,5)};
 const direct=await f.api.preview(q),wide=await f.api.preview({...q,corridorStage:1});
 assert.equal(direct.route,null);assert.equal(wide.route,null);
 const r=await f.api.preview({...q,corridorGuide:pt(250,750),corridorStage:1});
 assert.equal(r.status,'route',r.reason);assert(r.route.lengthMeters>1900);assert.equal(r.coverage.corridorShape,'guided_polyline');
 assert.deepEqual(r.coverage.corridorGuide,pt(250,750));assert.equal(r.coverage.guideIsRouteWaypoint,false);
 assert.equal(r.route.segments.length,11);assert.equal(r.routingCoreSHA256,Preview.CORE_SHA256);
 assert.equal(r.physicalAccessibilityVerified,false);assert.equal(r.globalDisconnectionProven,false);
 assert(r.resources.accountedResidentBytes<=128*1024*1024);assert.equal(f.api.snapshot().budgets.maxMilliseconds,6000);
 assert.equal(f.api.snapshot().residentGraphs,0);assert.equal(f.api.snapshot().busy,false);
 assert.equal(JSON.stringify(f.world)+JSON.stringify(f.graphs),before);
});
test('guide position is not snapped, required as a route waypoint or connected to the returned route',async()=>{
 const t=tile(),g=tile(0,-2),f=setup([[t,graph(t,[['n/1',-100,0],['n/2',100,0]],[[0,1,'100']])],[g,graph(g,[],[])]]),
  r=await f.api.preview({start:pt(-80),end:pt(80),corridorGuide:pt(0,500)});
 assert.equal(r.status,'route');assert.equal(r.route.lengthMeters,160);
 assert(r.route.points.every(p=>p.n===pt(0).n));assert.equal(r.coverage.guideIsRouteWaypoint,false);
 assert.equal(r.coverage.loadedCells.length,2);
});
test('the complete bent spine is reserved before IO, with neither leg reduced to a prefix',async()=>{
 const f=detour({budgets:{maxCells:3}}),r=await f.api.preview({...query,corridorGuide:pt(250,750)});
 assert.equal(r.code,'corridor_cell_budget');assert(r.coverage.uncoveredSpineCells.length>0);assert.equal(f.requests.length,0);assert.equal(r.route,null);
});
test('known unprepared guide sectors remain missing, without manufactured file reads or connectivity',async()=>{
 const missing=tile(1,-3).cellId,f=detour({mutateWorld(world){delete world.tiles.find(t=>t.cellId===missing).navigation;}}),
  r=await f.api.preview({...query,start:pt(-48,5),corridorGuide:pt(250,750),corridorStage:1});
 assert.equal(r.code,'corridor_incomplete');assert.equal(r.route,null);assert.equal(r.coverage.completeRequestedSector,false);
 assert.deepEqual(r.coverage.missingCells,[missing]);assert(!f.requests.some(q=>q.options.cellId===missing));
 assert.equal(r.globalDisconnectionProven,false);assert.equal(r.physicalMovementReady,false);
});
test('guide geometry cannot connect crossing OSM identities',async()=>{
 const t=tile(),f=setup([[t,graph(t,[['n/1',-100,0],['n/2',100,0],['n/3',0,-100],['n/4',0,100]],[[0,1,'100'],[2,3,'200']])]]),
 r=await f.api.preview({start:pt(-80),end:pt(0,80),corridorGuide:pt(0,0)});
 assert.equal(r.code,'no_route_in_loaded_network');assert.equal(r.route,null);
});
test('guide input is copied before asynchronous reads and malformed guide requests stop before IO',async()=>{
 let resume;const gate=new Promise(resolve=>resume=resolve),f=simple({loadAsset:async d=>{await gate;return fixture.assets.get(d.path);}}),fixture=f;
 const guide=pt(0,20),q={start:pt(-80),end:pt(80),corridorGuide:guide},operation=f.api.preview(q);
 guide.e+=10000;guide.n+=10000;resume();const r=await operation;assert.equal(r.status,'route');assert.deepEqual(r.coverage.corridorGuide,pt(0,20));
 for(const corridorGuide of [null,[],{},NaN,{e:1,n:Infinity},{e:1,n:'2'}]){
  const f=simple(),bad=await f.api.preview({start:pt(-80),end:pt(80),corridorGuide});assert.equal(bad.code,'position');assert.equal(f.requests.length,0);
 }
});
test('file integrity, preflight memory/byte limits and cancellation stay active with a guide',async()=>{
 const q={start:pt(-80),end:pt(80),corridorGuide:pt(0,20)};
 const broken=simple({loadAsset:async()=>new Uint8Array([1])});assert.equal((await broken.api.preview(q)).code,'integrity');
 for(const budgets of [{maxEncodedBytes:1},{maxDecodedBytes:1}]){const f=simple({budgets});const r=await f.api.preview(q);assert.equal(r.route,null);assert.equal(f.requests.length,0);}
 let signal;const blocked=simple({loadAsset:async(_d,o)=>{signal=o.signal;return new Promise(()=>{});}}),pending=blocked.api.preview(q);
 blocked.api.cancel();const cancelled=await pending;assert.equal(cancelled.code,'cancelled');assert(signal.aborted);assert.equal(blocked.api.snapshot().residentGraphs,0);
});
