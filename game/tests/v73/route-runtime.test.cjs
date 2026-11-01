'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),path=require('node:path'),{spawnSync}=require('node:child_process');
const generated=spawnSync('python3',['-c',"import sys;from pathlib import Path;sys.path.insert(0,'game');from tools import v71_route_viewer as A,v72_routing as B,v73_routing as C;print(C.runtime(B.runtime(A.runtime(Path('game/src/v70/viewer-runtime.js').read_text()))))"],{cwd:path.resolve(__dirname,'../../..'),encoding:'utf8'});
assert.equal(generated.status,0,generated.stderr);
const flush=()=>new Promise(resolve=>setImmediate(resolve));
function fixture(){
 const elements=new Map(),calls=[];let world={source:'one'},camera={e:100,n:200};
 function element(id){if(!elements.has(id))elements.set(id,{value:'',checked:false,hidden:false,disabled:false,textContent:'',open:false,
  showModal(){this.open=true;},close(){this.open=false;},replaceChildren(){},append(){},addEventListener(){},getContext(){return null;}});return elements.get(id);}
 const document={getElementById:element,createElement:()=>({})},context={world:()=>world,camera:()=>camera,
  acquireRouteLease:async()=>({release:async()=>calls.push('release')}),readRouteAsset:async()=>new Uint8Array([1]),
  onWorldChange(listener){context.changed=listener;return()=>{};}};
 const routeCore={CORE_SHA256:'test-pinned',create(){return {cancel(){},async preview(q){calls.push(q);return {status:'route',code:'source_axis_route',
  route:{mode:'foot',lengthMeters:12,points:[q.start,q.end],segments:[]},coverage:{loadedCells:[],missingCells:[],omittedCells:[]},continuation:{available:false}};}};}};
 const mod={exports:{}},sandbox={module:mod,__SOMA_ROUTE70_CORE__:routeCore,__SOMA_NAV63_CORE__:{},AbortController,console};
 vm.runInNewContext(generated.stdout,sandbox);const ui=mod.exports.mount(context,document);element('route70-mode').value='foot';
 return {ui,e:element,calls,context,camera:p=>camera=p,world:p=>world=p};
}
test('camera guidance survives the flight to arrival and is removed without another NAV read',async()=>{
 const f=fixture();await f.ui.open();await f.ui.markStart();f.camera({e:300,n:450});await f.ui.open();
 f.e('route73-mark-guide').onclick();await flush();assert.equal(f.ui.snapshot().open,false);
 assert.deepEqual(JSON.parse(JSON.stringify(f.ui.snapshot().markers.corridorGuide)),{e:300,n:450});
 f.camera({e:700,n:800});await f.ui.open();await f.ui.compute();const q=f.calls.find(c=>typeof c==='object');
 assert.deepEqual(JSON.parse(JSON.stringify(q.start)),{e:100,n:200});assert.deepEqual(JSON.parse(JSON.stringify(q.end)),{e:700,n:800});
 assert.deepEqual(JSON.parse(JSON.stringify(q.corridorGuide)),{e:300,n:450});assert.equal(f.ui.snapshot().markers.guideIsRouteWaypoint,false);
 const before=f.calls.filter(c=>typeof c==='object').length;f.e('route73-clear-guide').onclick();
 assert.equal(f.ui.result(),null);assert.equal(f.ui.snapshot().markers.corridorGuide,null);assert.equal(f.calls.filter(c=>typeof c==='object').length,before);
 await f.ui.compute();const last=f.calls.filter(c=>typeof c==='object').at(-1);assert.equal(last.corridorGuide,undefined);await f.ui.close();
});
test('manual coordinates invalidate the prior result, reset expansion, and reject partial guide input',async()=>{
 const f=fixture();await f.ui.open();await f.ui.markStart();f.camera({e:700,n:800});await f.ui.open();
 f.e('route70-guide-e').value='500';f.e('route70-guide-e').oninput();assert.equal(f.e('route70-compute').disabled,true);
 f.e('route70-guide-n').value='600';f.e('route70-guide-n').oninput();assert.equal(f.e('route70-compute').disabled,false);
 await f.ui.compute();assert(f.ui.result());f.e('route70-guide-e').value='520';f.e('route70-guide-e').oninput();assert.equal(f.ui.result(),null);
 await f.ui.compute();const q=f.calls.filter(c=>typeof c==='object').at(-1);assert.equal(q.corridorGuide.e,520);assert.equal(q.corridorStage,0);
 await f.ui.close();
});
test('world replacement and example selection discard guide markers from a different analysis',async()=>{
 const f=fixture();await f.ui.open();f.e('route70-guide-e').value='500';f.e('route70-guide-n').value='600';f.e('route70-guide-e').oninput();
 f.ui.example();assert.equal(f.ui.snapshot().markers.corridorGuide,null);
 f.e('route70-guide-e').value='500';f.e('route70-guide-n').value='600';f.e('route70-guide-e').oninput();
 f.world({source:'two'});f.context.changed();await flush();await f.ui.open();assert.equal(f.ui.snapshot().markers.corridorGuide,null);
 assert.equal(f.e('route70-guide-e').value,'');assert.equal(f.e('route70-guide-n').value,'');await f.ui.close();
});
