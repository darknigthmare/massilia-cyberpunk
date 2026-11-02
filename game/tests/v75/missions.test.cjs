'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm');
const source=require('./missions-fixture.cjs'),plain=x=>JSON.parse(JSON.stringify(x));
function fixture(parent=false){
 const storage=new Map(),combat={zoneCombat:{},combat:{},loot:{}};
 const c={Math,Map,Set,Object,Array,Number,String,JSON,Date,performance:{now:()=>1000},setTimeout:()=>{},
  localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)},
  state:{zone:'station-exterior',health:100,armor:45,credits:240,reputation:{},recovery:{pending:false}},camera:{x:0,z:0,yaw:0,pitch:0},paused:false,
  lineBlocked:()=>false,renderer:{uploadStatic:()=>{},prepareSigns:()=>{}},document:{getElementById:()=>null},
  buildZone:z=>{z.robots=[];z.vehicles=[];z.interactables=[];z.static=[];c.test43.ensure(z);return c.owner.ensure(z);},
  announce:(message)=>{c.lastAnnouncement=message;},closeModals:()=>{c.paused=false;},showDialogue:(title,lines,choices)=>{c.dialogue={title,lines,choices};c.paused=true;},
  __SOMA_V37_SAVE__:{schedule:()=>{}},__SOMA_V32__:{getState:()=>combat,zoneCombatState:id=>combat.zoneCombat[id]||(combat.zoneCombat[id]={enemies:{}}),
   snapshotCombat:()=>{const s=c.__SOMA_V32__.zoneCombatState(c.zone.id);for(const q of c.zone.robots||[])if(q.v32Enemy)s.enemies[q.id]={health:q.health,maxHealth:q.maxHealth,armor:q.armor,state:q.state,detect:q.detect,downHandled:!!q.v32DownHandled};}},
  C:{hex:v=>v},extendNightWorld:()=>{}};
 c.window=c;c.globalThis=c;vm.createContext(c);
 vm.runInContext(source.worldData+'\n'+source.authoredWorld+'\nvar WORLD=makeWorld();var D=Object.fromEntries(DISTRICTS.map(d=>[d.id,d]));',c);
 for(const z of Object.values(c.WORLD.zones))Object.assign(z,{robots:[],actors:[],vehicles:[],interactables:[],static:[]});c.zone=c.WORLD.zones['station-exterior'];
 const expose=`window.owner={state:()=>V45,operations:V45_OPERATIONS,accept:v45AcceptOperation,node:v45OperationNodeDialogue,advance:v45CompleteOperationStep,close:v45CloseOperation,ensure:v45EnsureZone,tick:v45TickChannel,changed:v45OnZoneChanged,rebuild:v45RebuildCurrent,trace:${parent?'null':'v75TraceOperation'},command:v45CommandDialogue,channel:()=>v45Channel};`;
 vm.runInContext((parent?source.parentProduction:source.production).replace('v43Setup();','window.test43={hotspots:V43_HOTSPOTS,spawn:v43SpawnEnemies,ensure:v43EnsureZone};'),c);
 vm.runInContext((parent?source.parentCity:source.city).replace('v45Setup();',expose),c);
 c.enter=id=>{c.zone=c.WORLD.zones[id];c.state.zone=id;c.test43.ensure(c.zone);c.owner.ensure(c.zone);c.paused=false;};
 c.point=(op,index)=>{const o=c.zone.interactables.find(o=>o.operationId===op&&o.step===index);assert(o);c.camera.x=o.x;c.camera.z=o.z;return o;};
 c.combat=combat;c.storage=storage;return c;
}
test('all twenty authored stages advance only through their current physical objective or driven transfer, then pay once in order',()=>{
 const c=fixture();let expectedCredits=240;
 for(const op of c.owner.operations){
  assert.equal(c.owner.accept(op.id),true);const record=c.owner.state().operations[op.id];
  for(const [index,step]of op.steps.entries()){
   assert.equal(record.step,index);assert.equal(c.owner.advance(op.id),false,'bare API cannot skip proof74');
   if(step.kind==='drive'){
    const from=c.zone.id;c.enter(step.zone);const car={id:'native-fixture-car',condition:61};c.state.driving=car.id;c.zone.vehicles.push(car);
    c.owner.changed(from,step.zone);assert.equal(record.step,index+1);assert.equal(c.zone.vehicles.find(v=>v.id===car.id),car);c.state.driving=null;
   }else{
    c.enter(step.zone);const o=c.point(op.id,index);
    if(step.kind==='channel'){
     assert.equal(c.owner.node(o),true);for(let i=0;i<Math.ceil(step.duration/.1)-1;i++)c.owner.tick(.1);assert.equal(record.step,index);c.owner.tick(.11);
    }else if(step.kind==='combat'){
     const enemies=c.zone.robots.filter(q=>q.v45Owner===`operation-${op.id}-${index}`);assert.equal(enemies.length,step.count);
     c.owner.node(o);assert.equal(record.step,index);c.paused=false;
     for(const q of enemies){assert.equal(c.__SOMA_PROGRESSION74__.knownEnemy(q.id,step.zone),true);assert.equal(c.__SOMA_PROGRESSION74__.knownEnemy(q.id,'station-exterior'),false);q.health=0;q.v32DownHandled=true;}
     assert.equal(c.owner.node(o),true);
    }else{
     assert.equal(c.owner.node(o),true);const choose=c.dialogue.choices[0].action;
     const oldState=c.state;c.state=plain(c.state);assert.equal(choose(),false,'import root invalidates callback');c.state=oldState;
     assert.equal(choose(),true);assert.equal(choose(),false);
    }
   }
   assert.equal(record.step,index+1,op.id+' stage '+index);
  }
  assert.equal(record.status,'return');c.enter('port-exterior');assert.equal(c.owner.close(op.id),false);
  c.enter('station-exterior');const console=c.zone.interactables.find(o=>o.type==='v45CommandConsole');c.camera.x=console.x;c.camera.z=console.z;
  assert.equal(c.owner.close(op.id),true);assert.equal(c.owner.close(op.id),false);expectedCredits+=op.reward;
  assert.equal(c.state.credits,expectedCredits);assert.equal(c.state.reputation[op.district],3);assert.equal(record.choice,op.steps.at(-1).choices[0][0]);
  assert.equal(JSON.parse(c.storage.get('soma-massilia.city.v45')).operations[op.id].paid,true);
 }
 assert.equal(c.owner.state().stats.operationSteps,20);assert.equal(c.owner.state().stats.operationsClosed,5);
 const audit=c.__SOMA_MISSIONS75__.snapshot();assert.equal(audit.newPersistenceDomain,false);
 for(const op of audit.operations)for(const s of op.stages){assert.equal(s.knownZone,true);assert(s.returnRoute.length>0);if(s.index)assert(s.approach.length>0);}
});
test('the native trace callbacks retain vehicleOnly for all five drive stages and keep ordinary stages on foot',()=>{
 const c=fixture();
 for(const op of c.owner.operations)for(const [index,step]of op.steps.entries()){
  const r=c.owner.state().operations[op.id];r.status='active';r.step=index;c.enter(op.steps[Math.max(0,index-1)].zone);
  assert.equal(c.owner.trace(op.id),true);const route=c.owner.state().route;
  assert.equal(route.targetZone,step.zone);assert.equal(route.vehicleOnly,step.kind==='drive');
  if(step.kind==='drive')for(let i=1;i<route.path.length;i++)assert(c.WORLD.links.some(l=>((l.a===route.path[i-1]&&l.b===route.path[i])||(l.b===route.path[i-1]&&l.a===route.path[i]))&&['road','bridge','garage','police'].includes(l.kind)));
 }
 const r=c.owner.state().operations['ligne-secours'];r.status='done';assert.equal(c.owner.trace('ligne-secours'),false);
 assert(!source.city.includes('action:()=>v45SetDestination(step.zone,step.label)'));
});
test('an inactive authored operation node explains its status and retains the unchanged v74 physical gating',()=>{
 const old=fixture(true),c=fixture();
 for(const x of [old,c]){x.enter('forge-garage');x.o=x.point('memoire-moteurs',0);}
 assert.equal(old.owner.node(old.o),false);assert.equal(c.owner.node(c.o),true);assert.match(c.dialogue.lines[0],/pas encore autorisé/);
 c.camera.x+=10;assert.equal(c.owner.node(c.o),false);c.camera.x=c.o.x;assert.equal(c.owner.node({...c.o}),false);
 assert.equal(c.owner.state().operations['memoire-moteurs'].step,0);
});
test('each authored channel cancels on pause, death, owner import and displacement without saving temporary proof',()=>{
 for(const op of fixture().owner.operations)for(const interrupt of [c=>{c.paused=true;},c=>{c.state.health=0;},c=>{c.state=plain(c.state);},c=>{c.camera.x+=1;}]){
  const c=fixture(),r=c.owner.state().operations[op.id];r.status='active';r.step=0;c.enter(op.steps[0].zone);c.owner.node(c.point(op.id,0));c.owner.tick(.1);interrupt(c);c.owner.tick(.1);
  assert.equal(c.owner.channel(),null);assert.equal(r.step,0);assert.equal(c.owner.advance(op.id),false);
 }
});
test('every automatic hotspot identity is bounded by immutable source43 content before API43 setup, with no story/gig admission',()=>{
 const c=fixture(),api=c.__SOMA_MISSIONS75__,content=c.__SOMA_MISSIONS75_CONTENT__;
 assert.equal(c.__SOMA_V43__,undefined,'identity readiness does not depend on late owner43 setup');
 assert(Object.isFrozen(content));assert.equal(content.length,c.test43.hotspots.length);
 for(const h of c.test43.hotspots){
  const declaration=content.find(q=>q.id===h.id);assert(Object.isFrozen(declaration));assert.deepEqual(plain(declaration),{id:h.id,zone:h.zone,count:h.count});
  for(let i=0;i<h.count;i++){const id=`v43-hotspot-${h.id}-${i}`;assert.equal(api.knownHotspotEnemy(id,h.zone),true);assert.equal(api.knownHotspotEnemy(id,'station-exterior'),false);}
  for(const suffix of [-1,h.count,'01','bogus'])assert.equal(api.knownHotspotEnemy(`v43-hotspot-${h.id}-${suffix}`,h.zone),false);
  for(const owner of ['story','gig','invented'])assert.equal(api.knownHotspotEnemy(`v43-${owner}-${h.id}-0`,h.zone),false);
 }
 assert.equal(api.knownHotspotEnemy('v43-hotspot-invented-hotspot-0','couronne-periphery'),false);
 const h=content.find(q=>q.zone==='couronne-periphery'),id=`v43-hotspot-${h.id}-1`;
 assert.equal(api.legacyLootRole('loot-'+id,h.zone,'melee'),'blade');assert.equal(api.legacyLootRole('loot-'+id,'port-exterior','melee'),null);
 assert.equal(api.legacyLootRole(`loot-v43-hotspot-${h.id}-0`,h.zone,'melee'),null);
});
test('native hotspot43 spawning restores health and handled defeats from combat32; real validator37 accepts only exact source enemy and loot zones',()=>{
 const c=fixture();c.enter('couronne-periphery');const hotspot=c.test43.hotspots.find(h=>h.zone===c.zone.id),prefix=`v43-hotspot-${hotspot.id}-`,bodies=()=>c.zone.robots.filter(q=>q.id.startsWith(prefix));
 assert.equal(bodies().length,hotspot.count);assert.equal(bodies()[1].v32Role,'blade');bodies()[0].health=27;bodies()[1].health=0;bodies()[1].v32DownHandled=true;
 c.__SOMA_V32__.snapshotCombat();c.owner.rebuild();assert.equal(bodies()[0].health,27);assert.equal(bodies()[1].health,0);assert.equal(bodies()[1].v32DownHandled,true);assert.equal(c.state.credits,240);
 const q=bodies()[1],root={schema:32,gigs:{},followingGig:null,redZones:{},combat:{kills:{}},zoneCombat:plain(c.combat.zoneCombat),loot:{}};
 root.loot['loot-'+q.id]={zone:c.zone.id,role:'melee',x:q.x,z:q.z,collected:true};
 c.root=root;c.k={edition:37,zones:new Set(Object.keys(c.WORLD.zones)),districts:new Set(Object.keys(c.D)),gigs:new Set(),roles:new Set(['rifle','blade','sniper','netrunner','heavy','drone']),items:new Set()};c.api=()=>({freshState:()=>c.root});c.AUX36_IDS=new Set();
 const part=(a,b)=>{const start=source.saver.indexOf(a);assert(start>=0);return source.saver.slice(start,source.saver.indexOf(b,start+a.length));};
 vm.runInContext(part('const record=(v,path)=>','\nfunction enemyIdKnown(')+part('function enemyIdKnown(','\n/* 0.37 helpers inserted')+part('function validateLayer(','\nfunction validate('),c);
 assert.equal(c.validateLayer(32,c.root,c.k),undefined);assert.equal(c.enemyIdKnown(q.id,{...c.k,edition:36},c.zone.id),false);
 root.loot['loot-'+q.id].zone='port-exterior';assert.throws(()=>c.validateLayer(32,c.root,c.k),/Butin.*identifiant inconnu/);root.loot['loot-'+q.id].zone=c.zone.id;
 const good=root.zoneCombat[c.zone.id];root.zoneCombat['port-exterior']=good;delete root.zoneCombat[c.zone.id];assert.throws(()=>c.validateLayer(32,c.root,c.k),/Adversaire.*identifiant inconnu/);
 delete root.zoneCombat['port-exterior'];root.zoneCombat[c.zone.id]=good;good.enemies[prefix+hotspot.count]={health:1};assert.throws(()=>c.validateLayer(32,c.root,c.k),/Adversaire.*identifiant inconnu/);
});
