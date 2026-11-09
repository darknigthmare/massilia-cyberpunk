'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm');
const source=require('./missions-fixture.cjs'),plain=x=>JSON.parse(JSON.stringify(x));
function fixture(parent=false){
 const storage=new Map(),combat={zoneCombat:{},combat:{},loot:{}};
 const c={Math,Map,Set,Object,Array,Number,String,JSON,Date,performance:{now:()=>1000},setTimeout:()=>{},
  localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)},state:{zone:'station-exterior',health:100,armor:45,credits:240,reputation:{},recovery:{pending:false}},camera:{x:0,z:0},paused:false,
  blocked:()=>false,lineBlocked:()=>false,renderer:{uploadStatic:()=>{},prepareSigns:()=>{}},document:{getElementById:()=>null,readyState:'complete',addEventListener:()=>{}},
  buildZone:z=>{z.robots=[];z.vehicles=[];z.interactables=[];z.static=[];c.story.ensure(z);return c.city.ensure(z);},
  announce:message=>c.lastAnnouncement=message,closeModals:()=>c.paused=false,showDialogue:(title,lines,choices)=>{c.dialogue={title,lines,choices};c.paused=true;},save:()=>{},
  __SOMA_V42__:{state:()=>({finale:{status:'done'}})},__SOMA_V37_SAVE__:{schedule:()=>{}},
  __SOMA_V32__:{getState:()=>combat,snapshotCombat:()=>{}},C:{hex:v=>v},extendNightWorld:()=>{}};
 c.window=c;c.globalThis=c;vm.createContext(c);
 vm.runInContext(source.worldData+'\n'+source.nightWorld+'\n'+source.authoredWorld+'\nvar WORLD=makeWorld();var D=Object.fromEntries(DISTRICTS.map(d=>[d.id,d]));var NARRATIVE={readables:{}};'+source.annexWorld,c);
 for(const z of Object.values(c.WORLD.zones))Object.assign(z,{robots:[],actors:[],vehicles:[],interactables:[],static:[]});c.zone=c.WORLD.zones['station-exterior'];
 vm.runInContext((parent?source.parentProduction:source.production).replace('v43Setup();',`window.story={state:()=>V43,stories:V43_STORY,gigs:V43_GIGS,ensure:v43EnsureZone,tracked:v43TrackedText};`),c);
 vm.runInContext((parent?source.parentCity:source.city).replace('v45Setup();',`window.city={state:()=>V45,operations:V45_OPERATIONS,calls:V45_CALLS,races:V45_RACES,startRace:v45StartRace,finishRace:v45FinishRace,failRace:v45FailRace,raceChanged:v45RaceZoneChanged,callDialogue:v45CallDialogue,accept:v45AcceptOperation,node:v45OperationNodeDialogue,advance:v45CompleteOperationStep,close:v45CloseOperation,ensure:v45EnsureZone,tick:v45TickChannel,changed:v45OnZoneChanged,trace:v75TraceOperation,returnGuide:v74ReturnGuide,set:v45SetDestination,clear:v45ClearDestination,acceptCall:v45AcceptCall,resolveCall:v45ResolveCall,expireCall:v45ExpireCall,spawnCall:v45SpawnCall,tracked:v45TrackedText};window.__SOMA_V45__={setDestination:v45SetDestination};`),c);
 c.enter=id=>{assert(c.WORLD.zones[id],id);c.zone=c.WORLD.zones[id];c.state.zone=id;c.story.ensure(c.zone);c.city.ensure(c.zone);c.paused=false;};
 c.point=(type,id,index)=>{const o=c.zone.interactables.find(o=>o.type===type&&(!id||o.operationId===id&&o.step===index));assert(o,type);c.camera.x=o.x;c.camera.z=o.z;c.paused=false;return o;};
 c.manual=()=>{assert.equal(c.city.set('station-interiorA','Destination personnelle',false),true);return plain(c.city.state().route);};
 c.storage=storage;return c;
}
function finishStep(c,op,index){
 const step=op.steps[index];c.enter(step.zone);
 if(step.kind==='drive'){
  const car={id:'original-fixture-car',condition:61};c.state.driving=car.id;c.zone.vehicles.push(car);c.city.changed(op.steps[index-1].zone,step.zone);c.state.driving=null;
 }else{
  const o=c.point('v45OperationNode',op.id,index);
  if(step.kind==='combat')for(const q of c.zone.robots)if(q.v45Owner===`operation-${op.id}-${index}`){q.health=0;q.v32DownHandled=true;}
  assert.equal(c.city.node(o),true);
  if(step.kind==='channel')for(let i=0;i<Math.ceil(step.duration/.1)+1;i++)c.city.tick(.1);
  if(step.kind==='choice')assert.equal(c.dialogue.choices[0].action(),true);
 }
 assert.equal(c.city.state().operations[op.id].step,index+1,op.id+' step '+index);
}
test('v76 real operation acceptance and physical hand-in overwrite then erase an unrelated manual GPS',()=>{
 const c=fixture(true),before=c.manual();assert.equal(c.city.accept('asphalte-fantome'),true);assert.notDeepEqual(plain(c.city.state().route),before);
 const op=c.city.operations[0],r=c.city.state().operations[op.id];r.status='return';r.step=op.steps.length;c.enter('station-exterior');c.point('v45CommandConsole');c.manual();assert.equal(c.city.close(op.id),true);assert.equal(c.city.state().route.targetZone,null);
});
test('v76 real call resolution erases an unrelated manual GPS',()=>{
 const c=fixture(true),call=c.city.calls[0];c.city.spawnCall(call.id);c.city.acceptCall(call.id);c.manual();assert.equal(c.city.resolveCall(call.id),true);assert.equal(c.city.state().route.targetZone,null);
});
test('all twenty physical operation stages and five hand-ins preserve a manual destination while native travel may reroute its path',()=>{
 const c=fixture();let count=0;
 const intent=r=>({targetZone:r.targetZone,label:r.label,vehicleOnly:r.vehicleOnly,updatedAt:r.updatedAt});
 for(const op of c.city.operations){
  const manual=c.manual();assert.equal(c.city.accept(op.id),true);assert.deepEqual(plain(c.city.state().route),manual);
  for(const [index]of op.steps.entries()){finishStep(c,op,index);assert.deepEqual(intent(c.city.state().route),intent(manual));count++;}
  c.enter('station-exterior');c.point('v45CommandConsole');const credits=c.state.credits,before=plain(c.city.state().route);assert.equal(c.city.close(op.id),true);assert.deepEqual(plain(c.city.state().route),before);assert.equal(c.state.credits,credits+op.reward);assert.equal(c.city.close(op.id),false);
  assert.deepEqual(JSON.parse(c.storage.get('soma-massilia.city.v45')).route,before);
 }
 assert.equal(count,20);assert.equal(c.city.state().stats.operationsClosed,5);
});
test('an empty GPS follows all native operation stages including vehicle mode and return, then clears on hand-in',()=>{
 const c=fixture();
 for(const op of c.city.operations){
  assert.equal(c.city.accept(op.id),true);assert.equal(c.city.state().route.targetZone,op.steps[0].zone);
  for(const [index]of op.steps.entries()){
   // Re-entering a target through the native hook may consume that route.
   // Explicit tracing re-establishes the exact authored tuple before proof.
   assert.equal(c.city.trace(op.id),true);finishStep(c,op,index);
   const next=op.steps[index+1],route=c.city.state().route;
   assert.equal(route.targetZone,next?.zone||'station-exterior');assert.equal(route.vehicleOnly,next?.kind==='drive');
  }
  c.enter('station-exterior');c.point('v45CommandConsole');assert.equal(c.city.close(op.id),true);assert.equal(c.city.state().route.targetZone,null);
 }
});
test('route ownership requires exact source target label and mode, while explicit trace may replace a manual destination',()=>{
 for(const mutate of [r=>r.label+=' personnel',r=>r.vehicleOnly=true,r=>r.targetZone='velours-exterior']){
  const c=fixture(),op=c.city.operations[0];c.city.accept(op.id);mutate(c.city.state().route);const before=plain(c.city.state().route);finishStep(c,op,0);assert.deepEqual(plain(c.city.state().route),before);
  assert.equal(c.city.trace(op.id),true);assert.notDeepEqual(plain(c.city.state().route),before);
 }
});
test('both real return-guide labels clear only their own operation route and preserve false identity matches',()=>{
 for(const useGuide of [false,true]){
  const c=fixture(),op=c.city.operations[0],r=c.city.state().operations[op.id];r.status='return';r.step=op.steps.length;
  if(useGuide)assert.equal(c.city.returnGuide(op.id),true);else c.city.set('station-exterior',`Remettre le dossier · ${op.title}`,false);
  c.enter('station-exterior');c.point('v45CommandConsole');assert.equal(c.city.close(op.id),true);assert.equal(c.city.state().route.targetZone,null);
 }
});
test('all native calls preserve manual GPS on acceptance resolution and expiry, but remove their own stale route',()=>{
 for(const call of fixture().city.calls)for(const end of ['resolveCall','expireCall']){
  const c=fixture();c.city.spawnCall(call.id);const manual=c.manual();assert.equal(c.city.acceptCall(call.id),true);assert.deepEqual(plain(c.city.state().route),manual);assert.equal(c.city[end](call.id),true);assert.deepEqual(plain(c.city.state().route),manual);
  const own=fixture();own.city.spawnCall(call.id);assert.equal(own.city.acceptCall(call.id),true);assert.equal(own.city[end](call.id),true);assert.equal(own.city.state().route.targetZone,null);
 }
});
test('escort objective interactions preserve a manual GPS and report it; an owned route advances to the native destination',()=>{
 for(const call of fixture().city.calls.filter(x=>x.type==='escort'))for(const manual of [false,true]){
  const c=fixture();c.city.spawnCall(call.id);c.city.acceptCall(call.id);const s=c.city.state().calls[call.id];c.enter(s.zone);const o=c.zone.interactables.find(o=>o.type==='v45CallNode'&&o.callId===call.id);assert(o);
  const before=manual?c.manual():null;assert.equal(c.city.callDialogue(o),true);
  if(manual){assert.deepEqual(plain(c.city.state().route),before);assert.match(c.dialogue.lines[0],/Destination GPS conservée/);}
  else{assert.equal(c.city.state().route.targetZone,s.targetZone);assert.match(c.dialogue.lines[0],/trajet est chargé/);assert.equal(c.city.resolveCall(call.id),true);assert.equal(c.city.state().route.targetZone,null);}
 }
});
test('native race checkpoints timeout abandonment and finish preserve manual GPS and retain native results',()=>{
 let supported=0;
 for(const run of fixture().city.races)for(const ending of ['finish','fail']){
  const c=fixture();c.enter(run.district+'-exterior');const manual=c.manual();
  if(!c.city.startRace(run.district)){assert.equal(run.district,'port','only the historical port run targets an unreachable vehicle-only upper road');continue;}
  supported++;assert.deepEqual(plain(c.city.state().route),manual);const active=c.city.state().raceActive,credits=c.state.credits;
  if(ending==='finish'){
   c.state.driving='fixture-driven-car';for(const id of active.path.slice(1)){c.zone=c.WORLD.zones[id];c.city.raceChanged(id);assert.deepEqual(plain(c.city.state().route),manual);}
   assert.equal(c.city.state().races[run.id].wins,1);assert.equal(c.state.credits,credits+run.reward);
  }else{assert.equal(c.city.failRace('temps limite de fixture'),true);assert.deepEqual(plain(c.city.state().route),manual);assert.equal(c.city.state().races[run.id].wins,0);assert.equal(c.state.credits,credits);}
 }
 assert.equal(supported,14);
});
test('native race checkpoint guidance follows its own source tuple and clears at finish or abandonment',()=>{
 for(const ending of ['finish','fail']){
  const c=fixture();c.enter('corniche-exterior');assert.equal(c.city.startRace('corniche'),true);const active=c.city.state().raceActive,run=c.city.races.find(x=>x.id===active.id);assert.equal(c.city.state().route.targetZone,active.path[1]);
  if(ending==='finish'){
   c.state.driving='fixture-driven-car';for(const [index,id]of active.path.slice(1).entries()){c.zone=c.WORLD.zones[id];c.city.raceChanged(id);if(index<active.path.length-2){assert.equal(c.city.state().route.targetZone,active.path[index+2]);assert.equal(c.city.state().route.vehicleOnly,true);}}
   assert.equal(c.city.state().races[run.id].wins,1);
  }else assert.equal(c.city.failRace(),true);
  assert.equal(c.city.state().raceActive,null);assert.equal(c.city.state().route.targetZone,null);
 }
});
test('all eighteen story objectives and six returns trace to exact authored locations without a new domain',()=>{
 const c=fixture(),api=c.__SOMA_GUIDANCE77__;let stages=0;
 for(const m of c.story.stories){
  const r=c.story.state().story[m.id];r.status='active';
  for(const [index,step]of m.steps.entries()){r.step=index;assert.equal(api.target('story',m.id).zone,step.zone);const old=c.manual();assert.equal(api.trace('story',m.id),true);assert.notDeepEqual(plain(c.city.state().route),old);assert.equal(c.city.state().route.targetZone,step.zone);assert.equal(c.city.state().route.vehicleOnly,false);assert.deepEqual(plain(c.story.state().tracked),{kind:'story',id:m.id});stages++;}
  r.status='return';assert.equal(api.trace('story',m.id),true);assert.equal(c.city.state().route.targetZone,'station-interiorA');assert.match(c.story.tracked().detail,/intérieur A/);r.status='done';const route=plain(c.city.state().route);assert.equal(api.trace('story',m.id),false);assert.deepEqual(plain(c.city.state().route),route);
 }
 assert.equal(stages,18);assert.equal(api.snapshot().newPersistenceDomain,false);assert.equal(c.__SOMA_ROUTE77__.snapshot().newPersistenceDomain,false);
});
test('all sixteen gigs trace objectives and their exact district social boards; missing ambiguous and invalid content refuse unchanged',()=>{
 const c=fixture(),api=c.__SOMA_GUIDANCE77__;
 for(const g of c.story.gigs){
  const r=c.story.state().gigs[g.id];r.status='active';assert.equal(api.trace('gig',g.id),true);assert.equal(c.city.state().route.targetZone,g.zone);
  r.status='return';assert.equal(api.trace('gig',g.id),true);const board=c.WORLD.zones[c.city.state().route.targetZone];assert.equal(board.type,'social');assert.equal(board.district,g.district);
  r.status='done';assert.equal(api.trace('gig',g.id),false);
 }
 const g=c.story.gigs[0],r=c.story.state().gigs[g.id];r.status='return';const board=Object.values(c.WORLD.zones).find(z=>z.type==='social'&&z.district===g.district),route=plain(c.city.state().route);
 c.WORLD.zones.duplicate={...board,id:'duplicate'};assert.equal(api.trace('gig',g.id),false);delete c.WORLD.zones.duplicate;delete c.WORLD.zones[board.id];assert.equal(api.trace('gig',g.id),false);
 for(const [kind,id]of [['story','invented'],['gig','invented'],['operation',g.id]])assert.equal(api.trace(kind,id),false);assert.deepEqual(plain(c.city.state().route),route);
});
test('a disabled native route planner refuses explicit43 trace without changing tracked state or a manual route',()=>{
 const c=fixture(),m=c.story.stories[0],r=c.story.state().story[m.id];r.status='active';const route=c.manual(),tracked=plain(c.story.state().tracked);c.city.state().settings.routePlanner=false;
 assert.equal(c.__SOMA_GUIDANCE77__.trace('story',m.id),false);assert.deepEqual(plain(c.city.state().route),route);assert.deepEqual(plain(c.story.state().tracked),tracked);
});
