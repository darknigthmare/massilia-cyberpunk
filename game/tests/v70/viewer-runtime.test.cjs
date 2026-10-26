'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path'),{spawnSync}=require('node:child_process');
const UI=require('../../src/v70/viewer-runtime.js');
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
const flush=()=>new Promise(resolve=>setImmediate(resolve));
function result(status='route',code='source_axis_route'){return {status,code,sourcePbfSHA256:'a'.repeat(64),route:status==='route'?{mode:'foot',lengthMeters:599,points:[{e:0,n:0},{e:1,n:1}],segments:[{}]}:null,
 coverage:{loadedCells:['source-cell'],missingCells:[],omittedCells:[]},resources:{decodedBytes:99}};}
function fixture(overrides={}){
 const calls=[],frames=[],gate=deferred(),released=deferred();let active=0;
 const context={world:()=>({source:'verified test world only'}),readRouteAsset:async()=>new Uint8Array([1]),
  acquireRouteLease:async({signal})=>{calls.push('acquire');await gate.promise;if(signal.aborted)throw new Error('aborted');active++;return {async release(){calls.push('release');await released.promise;active--;}};},
  snapshot:()=>({locked:active>0}),onWorldChange(listener){context.changed=listener;return()=>{calls.push('unsubscribe');};},...overrides.context};
 const view={show(){calls.push('show');},hide(){calls.push('hide');},clear(){calls.push('clear');},state:s=>frames.push(s),render:r=>calls.push(r.code),error:e=>calls.push('error:'+e)};
 const routeCore={CORE_SHA256:'test-pinned-core',create(){calls.push('create-preview');return {preview:async()=>result(),cancel(){calls.push('cancel-preview');}};},...overrides.routeCore};
 return {ui:UI.createController({context,view,routeCore,routerCore:{}}),context,calls,frames,gate,released,view};
}
test('opening acquires and waits for the scene without loading NAV or creating its graph index',async()=>{
 const f=fixture(),opened=f.ui.open();assert.deepEqual(f.calls,['show','clear','acquire']);assert.equal(f.ui.snapshot().phase,'waiting-scene');
 assert.equal(f.ui.snapshot().reads,0);f.gate.resolve();await opened;assert.equal(f.ui.snapshot().phase,'ready');assert(!f.calls.includes('create-preview'));
 f.released.resolve();await f.ui.close();assert.equal(f.ui.snapshot().open,false);
});
test('a user request computes only after scene stability, and close awaits reader lease drainage',async()=>{
 const f=fixture(),opened=f.ui.open(),calculated=f.ui.compute(UI.EXAMPLE);await flush();assert(!f.calls.includes('create-preview'));
 f.gate.resolve();await opened;const r=await calculated;assert.equal(r.code,'source_axis_route');assert.equal(f.ui.snapshot().last.lengthMeters,599);
 const closed=f.ui.close();await flush();assert.equal(f.ui.snapshot().phase,'closing');assert(!f.calls.includes('hide'));
 f.released.resolve();await closed;assert.equal(f.calls.at(-1),'hide');assert.equal(f.ui.snapshot().physicalMovementReady,false);
});
test('closing a pending calculation aborts it and drains it before releasing or hiding',async()=>{
 const pending=deferred();let signal;
 const f=fixture({routeCore:{create(){return {preview:async q=>{signal=q.signal;return pending.promise;},cancel(){}};}}});
 f.gate.resolve();await f.ui.open();const operation=f.ui.compute(UI.EXAMPLE);await flush();const closed=f.ui.close();
 assert.equal(signal.aborted,true);await flush();assert(!f.calls.includes('release'));assert(!f.calls.includes('hide'));
 pending.resolve(result());await operation;await flush();assert(f.calls.includes('release'));assert(!f.calls.includes('source_axis_route'));
 f.released.resolve();await closed;assert.equal(f.ui.snapshot().inFlight,0);
});
test('an early close cancels scene acquisition and never initializes routing',async()=>{
 const f=fixture(),opened=f.ui.open(),closed=f.ui.close();f.gate.resolve();await opened;await closed;
 assert(!f.calls.includes('create-preview'));assert.equal(f.ui.snapshot().phase,'closed');assert.equal(f.ui.snapshot().reads,0);
});
test('reopening waits for the old lease release and cannot overlap sessions',async()=>{
 const f=fixture();f.gate.resolve();await f.ui.open();const close=f.ui.close(),reopen=f.ui.open();await flush();
 assert.equal(f.calls.filter(s=>s==='acquire').length,1);f.released.resolve();await close;await reopen;
 assert.equal(f.calls.filter(s=>s==='acquire').length,2);await f.ui.close();
});
test('repeated submit shares one operation and cancellation retains the scene lease',async()=>{
 const gate=deferred();let previewCalls=0,aborted=false;
 const f=fixture({routeCore:{create(){return {async preview(q){previewCalls++;q.signal.addEventListener('abort',()=>{aborted=true;gate.resolve(result('interrupted','cancelled'));});return gate.promise;},cancel(){}};}}});
 f.gate.resolve();await f.ui.open();const a=f.ui.compute(UI.EXAMPLE),b=f.ui.compute(UI.EXAMPLE);await flush();assert.equal(previewCalls,1);
 f.ui.cancel();await Promise.all([a,b]);assert(aborted);assert.equal(f.ui.snapshot().phase,'ready');assert(!f.calls.includes('release'));
 f.released.resolve();await f.ui.close();
});
test('world replacement clears stale results and cancels the previous analysis session',async()=>{
 const f=fixture();f.gate.resolve();f.released.resolve();await f.ui.open();await f.ui.compute(UI.EXAMPLE);assert(f.ui.result());
 f.context.changed();await flush();assert.equal(f.ui.snapshot().open,false);assert.equal(f.ui.result(),null);
 await f.ui.dispose();assert(f.calls.includes('unsubscribe'));
});
test('changing points invalidates the displayed result without rereading NAV',async()=>{
 const f=fixture();f.gate.resolve();f.released.resolve();await f.ui.open();await f.ui.compute(UI.EXAMPLE);assert(f.ui.result());
 f.ui.invalidate();assert.equal(f.ui.result(),null);assert.equal(f.ui.snapshot().reads,0);await f.ui.close();
});
test('invalid world/core and route failures are displayed without activating movement or releasing prematurely',async()=>{
 const f=fixture({routeCore:{create(){throw new Error('no prepared topology');}}});f.gate.resolve();await f.ui.open();
 assert.equal(await f.ui.compute(UI.EXAMPLE),null);assert.equal(f.ui.snapshot().phase,'error');assert.match(f.ui.snapshot().error,/topology/);assert(!f.calls.includes('release'));
 f.released.resolve();await f.ui.close();
});
test('the reader wrapper refuses concurrent NAV reads',async()=>{
 const gate=deferred();let second;
 const f=fixture({context:{readRouteAsset:async()=>gate.promise},routeCore:{create({loadAsset}){return {async preview(){const first=loadAsset({},{});second=loadAsset({},{});await assert.rejects(second,/seule lecture/);gate.resolve(new Uint8Array([1]));await first;return result();},cancel(){}};}}});
 f.gate.resolve();f.released.resolve();await f.ui.open();await f.ui.compute(UI.EXAMPLE);assert.equal(f.ui.snapshot().reads,1);assert.equal(f.ui.snapshot().maximumConcurrentReads,1);await f.ui.close();
});
test('2D drawing uses only the source route points and does not connect the user clicks',()=>{
 const lines=[],ctx={clearRect(){},fillRect(){},fillText(){},beginPath(){},moveTo(...a){lines.push(['move',...a]);},lineTo(...a){lines.push(['line',...a]);},stroke(){},arc(){},fill(){}};
 const canvas={width:820,height:300,getContext:()=>ctx},r=result();r.anchors={start:{input:{e:-999999,n:1000000}},end:{input:{e:1000000,n:-999999}}};
 UI.plot(canvas,r);assert(lines.length>0);assert(lines.every(a=>a.slice(1).every(n=>n>=0&&n<=820)));
});

const extracted=spawnSync('python',['-c',"import sys;sys.path.insert(0,'game/tools');import build_metropole_viewer_v70 as M;print(M.CONTEXT)"],{cwd:path.resolve(__dirname,'../../..'),encoding:'utf8'});
assert.equal(extracted.status,0,extracted.stderr);
function actualLease(){
 const scene=deferred(),reader=deferred(),state={running:0,queued:0},calls=[];
 const sandbox={URL,Promise,Error,Object,Set,performance,setTimeout,document:{},scene:scene.promise,reader:reader.promise,state,calls};
 vm.createContext(sandbox);vm.runInContext(`let store={snapshot:()=>state},manifest={source:'fixture'},manifestURL='https://viewer.example/world/manifest.json',worldIndex={};
 let worldPromise=scene,requestPromise=Promise.resolve(),keys=new Set(),jobs=new Map(),lastUpdate=0,camera={e:1,n:2,h:3};
 function releaseMouse(){calls.push('release-mouse');}async function readBytes(url,max,options){calls.push({url:url.href,max,signal:options.signal});return reader;}
 ${extracted.stdout}\nglobalThis.facade=route70Context;globalThis.jobControl={add:()=>jobs.set('fixture',{}),clear:()=>jobs.clear()};`,sandbox);
 return {...sandbox,facade:sandbox.facade,scene,reader,state,calls};
}
test('the actual derived facade waits for scene completion before admitting any NAV read',async()=>{
 const f=actualLease(),opened=f.facade.acquireRouteLease();assert.equal(f.facade.snapshot().locked,true);
 await assert.rejects(f.facade.readRouteAsset({path:'tiles/a.gz'},{maxEncodedBytes:99}),/créneau/);
 f.scene.resolve();const lease=await opened;assert.equal(f.facade.snapshot().sceneStable,true);
 const read=f.facade.readRouteAsset({path:'tiles/a.gz'},{maxEncodedBytes:99});const close=lease.release();await flush();assert.equal(f.facade.snapshot().locked,true);
 f.reader.resolve(new Uint8Array([1]));await read;await close;assert.equal(f.facade.snapshot().locked,false);
 assert.equal(f.calls[1].url,'https://viewer.example/world/tiles/a.gz');assert.equal(f.calls[1].max,99);
});
test('the actual facade refuses active scene requests, overlapping NAV reads and directory escapes',async()=>{
 const f=actualLease();f.scene.resolve();const lease=await f.facade.acquireRouteLease();
 f.state.running=1;await assert.rejects(f.facade.readRouteAsset({path:'tiles/a.gz'},{}),/réseau/);f.state.running=0;
 await assert.rejects(f.facade.readRouteAsset({path:'../other.gz'},{}),/hors du monde/);
 const first=f.facade.readRouteAsset({path:'tiles/a.gz'},{maxEncodedBytes:99});
 await assert.rejects(f.facade.readRouteAsset({path:'tiles/b.gz'},{}),/créneau/);
 f.reader.resolve(new Uint8Array());await first;await lease.release();
});
test('the actual facade unlocks when scene waiting is cancelled, without starting any reader',async()=>{
 const f=actualLease(),abort=new AbortController(),opened=f.facade.acquireRouteLease({signal:abort.signal});abort.abort();
 await assert.rejects(opened,e=>e.name==='AbortError');assert.equal(f.facade.snapshot().locked,false);assert.equal(f.calls.length,1);
});
test('queued visual jobs remain deferred while the facade waits for the scene network to drain',async()=>{
 const f=actualLease();f.jobControl.add();f.state.running=1;f.scene.resolve();const opened=f.facade.acquireRouteLease();await flush();assert.equal(f.facade.snapshot().sceneStable,false);
 f.state.running=0;const lease=await opened;assert.equal(f.facade.snapshot().sceneStable,true);f.jobControl.clear();await lease.release();
});

function documentFixture(){
 const elements=new Map(),ctx={clearRect(){},fillRect(){},fillText(){},beginPath(){},moveTo(){},lineTo(){},stroke(){},arc(){},fill(){}};
 function element(){return {value:'',textContent:'',checked:false,hidden:false,disabled:false,open:false,children:[],width:820,height:300,
  addEventListener(name,listener){this[name]=listener;},showModal(){this.open=true;},close(){this.open=false;},getContext:()=>ctx,
  replaceChildren(){this.children=[];},append(node){this.children.push(node);}};}
 const document={getElementById(id){if(!elements.has(id))elements.set(id,element());return elements.get(id);},createElement:element};
 document.getElementById('route70-mode').value='foot';return {document,elements};
}
test('marking a departure closes and releases the lease, then arrival uses the new exact camera position',async()=>{
 const previous=global.__SOMA_ROUTE70_CORE__,f=documentFixture(),requests=[],cam={...UI.EXAMPLE.start};let locked=false,world={edition:'fixture'};
 const release=deferred();
 const context={camera:()=>({...cam}),world:()=>world,index:()=>({communeAt:()=>({name:'Marseille'})}),snapshot:()=>({locked}),onWorldChange:()=>()=>{},
  readRouteAsset:async()=>{throw Error('No fixture byte read expected');},acquireRouteLease:async()=>{locked=true;return {async release(){await release.promise;locked=false;}};}};
 global.__SOMA_ROUTE70_CORE__={CORE_SHA256:'fixture',create(){return {async preview(q){requests.push(q);return result();},cancel(){}};}};
 try{
  const ui=UI.mount(context,f.document);await ui.open();assert.equal(f.elements.get('route70-precise').open,false);assert(f.elements.get('route70-compute').disabled);
  const marking=ui.markStart();await flush();assert.equal(locked,true);assert.equal(ui.snapshot().phase,'closing');
  release.resolve();await marking;assert.equal(locked,false);assert.equal(ui.snapshot().open,false);assert.equal(f.elements.get('route70-dialog').open,false);
  assert.deepEqual(ui.snapshot().markers.start,UI.EXAMPLE.start);
  Object.assign(cam,UI.EXAMPLE.end);await ui.open();
  assert.deepEqual(ui.snapshot().markers.start,UI.EXAMPLE.start);assert.deepEqual(ui.snapshot().markers.arrival,UI.EXAMPLE.end);
  assert.match(f.elements.get('route70-summary').textContent,/Départ marqué.*Marseille.*arrivée ici.*Marseille/);
  assert.equal(f.elements.get('route70-start-e').value,String(UI.EXAMPLE.start.e));assert.equal(f.elements.get('route70-end-n').value,String(UI.EXAMPLE.end.n));
  assert.equal(f.elements.get('route70-compute').disabled,false);await ui.compute();
  assert.deepEqual(requests[0].start,UI.EXAMPLE.start);assert.deepEqual(requests[0].end,UI.EXAMPLE.end);assert.equal(requests[0].mode,'foot');
  await ui.close();world={edition:'other fixture'};await ui.open();assert.equal(ui.snapshot().markers.start,null);assert(f.elements.get('route70-compute').disabled);await ui.close();
 }finally{if(previous===undefined)delete global.__SOMA_ROUTE70_CORE__;else global.__SOMA_ROUTE70_CORE__=previous;}
});
test('the explicit example preserves source coordinates without opening precision fields or auto-routing',async()=>{
 const previous=global.__SOMA_ROUTE70_CORE__,f=documentFixture(),world={edition:'fixture'};let calculations=0;
 global.__SOMA_ROUTE70_CORE__={CORE_SHA256:'fixture',create(){return {async preview(){calculations++;return result();},cancel(){}};}};
 try{
  const context={camera:()=>({e:1,n:2}),world:()=>world,index:()=>null,readRouteAsset:async()=>new Uint8Array(),acquireRouteLease:async()=>({async release(){}})};
  const ui=UI.mount(context,f.document);await ui.open();ui.example();assert.equal(calculations,0);
  assert.deepEqual(ui.snapshot().markers.start,UI.EXAMPLE.start);assert.deepEqual(ui.snapshot().markers.arrival,UI.EXAMPLE.end);
  assert.equal(f.elements.get('route70-precise').open,false);await ui.close();
 }finally{if(previous===undefined)delete global.__SOMA_ROUTE70_CORE__;else global.__SOMA_ROUTE70_CORE__=previous;}
});
