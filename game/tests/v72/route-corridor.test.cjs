'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {Preview,core,pt,tile,graph,setup,simple,seam}=require('./route-fixture.cjs');
function chain(count,options){
 const specs=[];
 for(let x=0;x<count;x++){
  const t=tile(x),id0=x===0?'n/1':'clip/100/1/'+(x/count).toFixed(12),id1=x===count-1?'n/2':'clip/100/1/'+((x+1)/count).toFixed(12);
  specs.push([t,graph(t,[[id0,x*250-125,0],[id1,x*250+125,0]],[[0,1,'100',15,0,1,x/count,(x+1)/count]])]);
 }
 return setup(specs,options);
}
test('native source routes cross forty-eight cells without mutating inputs or retaining graphs',async()=>{
 assert.equal(Preview.VERSION,'0.72.0');
 const f=chain(48),before=JSON.stringify(f.world)+JSON.stringify(f.graphs);
 const r=await f.api.preview({start:pt(-100),end:pt(47*250+100)});
 assert.equal(r.status,'route',r.reason);assert.equal(r.route.lengthMeters,11950);assert.equal(r.coverage.loadedCells.length,48);
 assert.equal(r.route.segments.length,48);assert.equal(r.globalDisconnectionProven,false);assert.equal(r.searchScope,'bounded_source_corridor');
 assert.equal(r.physicalAccessibilityVerified,false);assert.equal(r.campaignRoutingActivated,false);
 assert.equal(f.api.snapshot().residentGraphs,0);assert.equal(JSON.stringify(f.world)+JSON.stringify(f.graphs),before);
});
test('an overlong direct spine is interrupted before IO and can explicitly expand',async()=>{
 const f=chain(100),q={start:pt(-100),end:pt(99*250+100)};
 const initial=await f.api.preview(q);assert.equal(initial.code,'corridor_cell_budget');assert.equal(f.requests.length,0);
 assert.equal(initial.coverage.spineCells,100);assert.equal(initial.coverage.uncoveredSpineCells.length,4);
 assert.equal(initial.continuation.available,true);assert.equal(initial.continuation.requiresExplicitRequest,true);
 const expanded=await f.api.preview({...q,corridorStage:1});assert.equal(expanded.status,'route',expanded.reason);
 assert.equal(expanded.coverage.loadedCells.length,100);assert.equal(expanded.coverage.corridorStage,1);assert.equal(expanded.continuation.available,false);
});
test('both endpoint cells precede lateral cells under a tight corridor budget',async()=>{
 const a=tile(),b=tile(1),lateral=tile(0,-1),f=setup([
 [a,graph(a,[['n/1',-100,0],['clip/100/1/0.500000000000',125,0]],[[0,1,'100',15,0,1,0,.5]])],
 [b,graph(b,[['clip/100/1/0.500000000000',125,0],['n/2',300,0]],[[0,1,'100',15,0,1,.5,1]])],
 [lateral,graph(lateral,[],[])]],{budgets:{maxCells:2,corridorM:250}});
 const r=await f.api.preview({start:pt(-80),end:pt(290)});assert.equal(r.status,'route');assert.equal(r.coverage.omittedCells.length,1);
 assert.deepEqual(r.coverage.selectedCells,[a.cellId,b.cellId]);
});
test('missing coverage cannot become an assertion that no route exists',async()=>{
 const f=seam(),api=Preview.create({world:f.world,routerCore:core,routerCoreSHA256:Preview.CORE_SHA256,
 loadAsset:async d=>{if(d.path.includes('E01'))throw Object.assign(Error('missing'),{status:404});return f.assets.get(d.path);}});
 const r=await api.preview({start:pt(-40),end:pt(110)});assert.equal(r.status,'route');
 // Missing arrival has no axis; widening remains an explicit option.
 const missing=await api.preview({start:pt(-40),end:pt(290)});assert.equal(missing.code,'axis_unavailable');assert.equal(missing.continuation.available,true);
 assert.equal(missing.globalDisconnectionProven,false);assert.equal(missing.route,null);
});
test('omitted lateral coverage reports corridor incomplete instead of no route',async()=>{
 const a=tile(),b=tile(1),side=tile(0,-1),f=setup([
 [a,graph(a,[['n/1',-100,0],['n/2',50,0]],[[0,1,'100']])],
 [b,graph(b,[['n/3',200,0],['n/4',300,0]],[[0,1,'200']])],
 [side,graph(side,[],[])]],{budgets:{maxCells:2,corridorM:250}});
 const r=await f.api.preview({start:pt(-80),end:pt(290)});assert.equal(r.code,'corridor_incomplete');
 assert.equal(r.continuation.available,true);assert.equal(r.globalDisconnectionProven,false);assert.equal(r.route,null);
});
test('known descriptor byte budgets refuse before issuing any reads',async()=>{
 for(const budgets of [{maxEncodedBytes:1},{maxDecodedBytes:1}]){
  const f=simple({budgets}),r=await f.api.preview({start:pt(-80),end:pt(80)});
  assert(['asset_budget','decoded_budget'].includes(r.code));assert.equal(f.requests.length,0);assert.equal(r.route,null);
 }
});
test('crossing source axes, access masks, turns and steps retain native semantics',async()=>{
 const t=tile(),cross=setup([[t,graph(t,[['n/1',-100,0],['n/2',100,0],['n/3',0,-100],['n/4',0,100]],[[0,1,'100'],[2,3,'200']])]]);
 assert.equal((await cross.api.preview({start:pt(-80),end:pt(0,80)})).code,'no_route_in_loaded_network');
 const f=simple({mutateGraph(g){g.edges[0][4]=7;}});
 assert.equal((await f.api.preview({start:pt(80),end:pt(-80),mode:'car'})).route,null);
 const g=graph(t,[['n/1',-100,0],['n/2',0,0],['n/3',0,100]],[[0,1,'100'],[1,2,'200',15,1]],
 [{id:'300',via:'n/2',from:'100',to:'200',kind:'no_right_turn'}]),turn=setup([[t,g]]);
 assert.equal((await turn.api.preview({start:pt(-80),end:pt(0,80),mode:'car'})).route,null);
 assert.equal((await turn.api.preview({start:pt(-80),end:pt(0,80),mode:'foot'})).status,'route');
 assert.equal((await turn.api.preview({start:pt(-80),end:pt(0,80),avoidSteps:true})).route,null);
});
test('cancel, deadline, busy ownership and graph release survive corridor expansion',async()=>{
 let signal;const f=simple({budgets:{maxMilliseconds:20},loadAsset:async(_d,o)=>{signal=o.signal;return new Promise(()=>{});}});
 const result=await f.api.preview({start:pt(-80),end:pt(80),corridorStage:1});assert.equal(result.code,'time_budget');assert.equal(signal.aborted,true);
 assert.equal(f.api.snapshot().busy,false);assert.equal(f.api.snapshot().residentGraphs,0);
 const ac=new AbortController();ac.abort();const r=await f.api.preview({start:pt(-80),end:pt(80),signal:ac.signal});assert.equal(r.code,'cancelled');assert.equal(r.continuation.available,false);
 assert.equal((await simple().api.preview({start:pt(-80),end:pt(80),corridorStage:2})).status,'interrupted');
});
