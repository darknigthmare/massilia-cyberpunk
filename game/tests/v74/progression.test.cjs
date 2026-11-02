'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm');
const source=require('./progression-fixture.cjs');
const plain=v=>JSON.parse(JSON.stringify(v));
const part=(s,a,b)=>{assert.equal(s.split(a).length,2,a);return s.slice(s.indexOf(a),s.indexOf(b,s.indexOf(a)+a.length));};
function fixture(parent=false){
 const storage=new Map(),combat={zoneCombat:{},combat:{},loot:{}};
 const c={Math,Map,Set,Object,Array,Number,String,JSON,Date,performance:{now:()=>1000},setTimeout:()=>{},
  localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)},
  state:{zone:'station-exterior',health:100,armor:45,credits:240,reputation:{port:0},recovery:{pending:false}},
  camera:{x:0,z:0,yaw:0,pitch:0},paused:false,blockedSight:false,lineBlocked:()=>c.blockedSight,
  renderer:{uploadStatic:()=>{},prepareSigns:()=>{}},buildZone:z=>{z.robots=[];z.vehicles=[];z.interactables=[];z.static=[];return c.test45.ensureZone(z);},
  WORLD:{zones:{},links:[]},D:{port:{name:'Port'},station:{name:'Station'}},document:{getElementById:()=>null},
  announce:()=>{},closeModals:()=>{c.paused=false;},showDialogue:(title,lines,choices)=>{c.dialogue={title,lines,choices};c.paused=true;},
  coreSaves:0,__SOMA_V37_SAVE__:{schedule:()=>{c.coreSaves++;}},
  __SOMA_V32__:{getState:()=>combat,zoneCombatState:id=>combat.zoneCombat[id]||(combat.zoneCombat[id]={enemies:{}}),
   snapshotCombat:()=>{const s=c.__SOMA_V32__.zoneCombatState(c.zone.id);for(const q of c.zone.robots||[])if(q.v32Enemy)s.enemies[q.id]={health:q.health,maxHealth:q.maxHealth,armor:q.armor,state:q.state,detect:q.detect,downHandled:!!q.v32DownHandled};}},
 };
 c.window=c;c.globalThis=c;
 for(const id of ['station-exterior','port-exterior','corniche-exterior','corniche-route','forge-exterior','forge-garage','exchange','couronne-exterior','couronne-periphery','calanques-exterior','relais-exterior','velours-exterior','if-exterior']){
  const district=id.split('-')[0];c.WORLD.zones[id]={id,district,type:'exterior',title:id,w:100,h:100,robots:[],actors:[],vehicles:[],interactables:[],static:[]};
  if(id!=='station-exterior')c.WORLD.links.push({a:'station-exterior',b:id,kind:'road',code:id});
 }
 c.zone=c.WORLD.zones['station-exterior'];
 vm.createContext(c);
 const expose=`window.test45={state:()=>V45,operations:V45_OPERATIONS,calls:V45_CALLS,accept:v45AcceptOperation,advance:v45CompleteOperationStep,close:v45CloseOperation,node:v45OperationNodeDialogue,command:v45CommandDialogue,render:v45RenderCommand,ensureZone:v45EnsureZone,spawn:v45SpawnEnemies,findRoute:v45FindRoute,tick:v45TickChannel,changed:v45OnZoneChanged,save:()=>v45Save(true),channel:()=>v45Channel,rebuild:v45RebuildCurrent};`;
 const body=(parent?source.parentCity:source.city).replace('v45Setup();',expose);
 vm.runInContext(body,c);
 c.owner=c.test45;c.combat=combat;c.storage=storage;
 c.enter=id=>{c.zone=c.WORLD.zones[id];c.state.zone=id;c.owner.ensureZone(c.zone);c.paused=false;};
 c.point=(op,index)=>{const o=c.zone.interactables.find(o=>o.operationId===op&&o.step===index);assert(o);c.camera.x=o.x;c.camera.z=o.z;return o;};
 c.importRoots=()=>{const root=c.owner.state(),next=plain(root);for(const k of Object.keys(root))delete root[k];Object.assign(root,next);c.state=plain(c.state);c.owner.rebuild();};
 return c;
}
function atStep(c,index){const op=c.owner.operations[0],s=c.owner.state().operations[op.id];s.status='active';s.step=index;s.acceptedAt=1;c.owner.state().tracked={kind:'operation',id:op.id};return {op,s};}

test('regression: original v45 native remote dossier button pays; v74 requires real console and adds the return guide',()=>{
 const before=fixture(true),a=atStep(before,4);a.s.status='return';assert.equal(before.owner.close(a.op.id),true);assert.equal(before.state.credits,1000);
 const c=fixture(),{op,s}=atStep(c,4);s.status='return';c.enter('port-exterior');
 assert.equal(c.owner.close(op.id),false);assert.equal(c.state.credits,240);assert.equal(s.paid,false);
 c.enter('station-exterior');c.owner.ensureZone(c.zone);const console=c.zone.interactables.find(o=>o.type==='v45CommandConsole');
 c.camera.x=console.x+10;c.camera.z=console.z;assert.equal(c.owner.close(op.id),false);
 c.camera.x=console.x;c.camera.z=console.z;c.blockedSight=true;assert.equal(c.owner.close(op.id),false);c.blockedSight=false;
 assert.equal(c.owner.command(),true);const handIn=c.dialogue.choices.find(x=>x.label.startsWith('Clore'));assert(handIn);
 assert.equal(handIn.action(),true);assert.equal(handIn.action(),false);assert.equal(c.owner.close(op.id),false);
 assert.equal(c.state.credits,240+op.reward);assert.equal(c.state.reputation.port,3);assert.equal(c.owner.state().stats.operationsClosed,1);
 assert.equal(s.paid,true);assert(c.coreSaves>0);assert.equal(c.owner.state().operations[c.owner.operations[1].id].status,'available');
 const saved=JSON.parse(c.storage.get('soma-massilia.city.v45'));assert.equal(saved.operations[op.id].paid,true);
 assert(source.city.includes('data-v45-return-op'));assert(source.city.includes('Tracer la remise'));
});

test('real content combat identities validate before setup, with exact operation/call counts and source zones',()=>{
 const c=fixture(),known=c.__SOMA_PROGRESSION74__.knownEnemy;
 for(const op of c.owner.operations)for(const [index,step]of op.steps.entries())if(step.kind==='combat'){
  for(let i=0;i<step.count;i++)assert.equal(known(`v45-operation-${op.id}-${index}-${i}`,step.zone),true);
  assert.equal(known(`v45-operation-${op.id}-${index}-${step.count}`,step.zone),false);
  assert.equal(known(`v45-operation-${op.id}-${index}-0`,'station-exterior'),false);
 }
 for(const call of c.owner.calls){const id=`v45-call-${call.id}-0`,zone=`${call.district}-exterior`;
  assert.equal(known(id,zone),call.type==='combat');assert.equal(known(`v45-call-${call.id}-3`,zone),false);
 }
 assert.equal(known('v45-operation-invented-2-0','port-exterior'),false);
 assert.equal(known('v45-operation-asphalte-fantome-2-0'),false);
 assert.equal(c.__SOMA_V45__,undefined,'identity registration does not wait for UI/setup45');
 const original=part(source.parentSaver,'function enemyIdKnown(', '\nfunction saneTree(');
 const patched=part(source.saver,'function enemyIdKnown(', '\nfunction saneTree(');
 c.k={edition:37,zones:new Set(Object.keys(c.WORLD.zones))};
 vm.runInContext(original,c);assert.equal(c.enemyIdKnown('v45-operation-asphalte-fantome-2-0',c.k,'corniche-route'),false);
 vm.runInContext(patched,c);assert.equal(c.enemyIdKnown('v45-operation-asphalte-fantome-2-0',c.k,'corniche-route'),true);
 assert.equal(c.enemyIdKnown('v45-operation-asphalte-fantome-2-0',c.k,'port-exterior'),false);
 assert.equal(c.enemyIdKnown('v45-operation-asphalte-fantome-2-0',{...c.k,edition:36},'corniche-route'),false);
});

test('existing v32 encounter records restore partial damage and neutralizations on rebuild/import without new ledger or loot',()=>{
 const c=fixture(),{op}=atStep(c,2);c.enter('corniche-exterior');
 const first=c.zone.robots.filter(q=>q.v45Owner===`operation-${op.id}-2`);assert.equal(first.length,4);
 first[0].health=27;first[1].health=0;first[1].v32DownHandled=true;
 c.__SOMA_V32__.snapshotCombat();const before=plain(c.combat.zoneCombat);c.owner.rebuild();
 const restored=c.zone.robots.filter(q=>q.v45Owner===`operation-${op.id}-2`);
 assert.equal(restored[0].health,27);assert.equal(restored[1].health,0);assert.equal(restored[1].v32DownHandled,true);
 assert(restored.some(q=>q.v32Role==='blade'));assert(!restored.some(q=>q.v32Role==='melee'));
 c.importRoots();assert.equal(c.zone.robots.find(q=>q.id===first[0].id).health,27);
 assert.equal(c.zone.robots.find(q=>q.id===first[1].id).v32DownHandled,true);
 assert.deepEqual(plain(c.combat.zoneCombat),before);assert.equal(c.state.credits,240);
 assert.deepEqual(Object.keys(c.owner.state()).filter(k=>/v74|enemy|encounter/.test(k)),[]);
});

test('the actual v37 layer validator accepts v45 combat and loot, rejects unknown IDs and mismatched source zones',()=>{
 const c=fixture(),{op}=atStep(c,2);c.enter('corniche-exterior');c.__SOMA_V32__.snapshotCombat();
 const root={schema:32,gigs:{},followingGig:null,redZones:{},combat:{kills:{}},zoneCombat:plain(c.combat.zoneCombat),loot:{}};
 const q=c.zone.robots[1];root.loot['loot-'+q.id]={zone:c.zone.id,role:q.v32Role,x:q.x,z:q.z,collected:false};
 c.root=root;c.k={edition:37,zones:new Set(Object.keys(c.WORLD.zones)),districts:new Set(['port','station']),gigs:new Set(),roles:new Set(['rifle','blade','sniper','netrunner']),items:new Set()};
 c.api=()=>({freshState:()=>c.root});c.AUX36_IDS=new Set();
 const helpers=part(source.saver,'const record=(v,path)=>', '\nfunction enemyIdKnown(');
 vm.runInContext(helpers+part(source.saver,'function enemyIdKnown(', '\n/* 0.37 helpers inserted')+
  part(source.saver,'function validateLayer(', '\nfunction validate('),c);
 assert.equal(c.validateLayer(32,c.root,c.k),undefined);
 const good=c.root.zoneCombat['corniche-exterior'];delete c.root.zoneCombat['corniche-exterior'];c.root.zoneCombat['port-exterior']=good;
 assert.throws(()=>c.validateLayer(32,c.root,c.k),/Adversaire.*identifiant inconnu/);
 delete c.root.zoneCombat['port-exterior'];c.root.zoneCombat['corniche-exterior']=good;
 c.root.loot['loot-'+q.id].zone='port-exterior';assert.throws(()=>c.validateLayer(32,c.root,c.k),/Butin.*identifiant inconnu/);
 c.root.loot['loot-'+q.id].zone='corniche-exterior';good.enemies['v45-operation-asphalte-fantome-2-4']={health:50};
 assert.throws(()=>c.validateLayer(32,c.root,c.k),/Adversaire.*identifiant inconnu/);
 assert.equal(c.owner.state().operations[op.id].status,'active');
});

test('the real v45 objective rebuild retains the native driven vehicle and its mechanical values',()=>{
 const original=fixture(true),p=atStep(original,1);original.enter('corniche-route');original.state.driving='native-car';original.zone.vehicles.push({id:'native-car',condition:61});
 original.owner.changed('port-exterior','corniche-route');assert.equal(p.s.step,2);assert.equal(original.zone.vehicles.find(v=>v.id==='native-car'),undefined,'original objective rebuild discards the transferred car');
 const c=fixture(),a=atStep(c,1);c.enter('corniche-exterior');c.state.driving='native-car';const car={id:'native-car',condition:61,speed:2,x:4,z:6};c.zone.vehicles.push(car);
 c.owner.changed('port-exterior','corniche-exterior');assert.equal(a.s.step,2);assert.equal(c.state.driving,car.id);assert.equal(c.zone.vehicles.find(v=>v.id===car.id),car);
 assert.deepEqual(Object.fromEntries(['id','condition','speed','x','z'].map(k=>[k,car[k]])),{id:'native-car',condition:61,speed:2,x:4,z:6});assert.equal(c.zone.vehicles.filter(v=>v.id===car.id).length,1);
});

test('all five authored drive steps have existing road-only approaches; the original Corniche upper route is disconnected',()=>{
 const c=fixture();
 // Night venues only add night/service links, which vehicle adjacency excludes.
 assert(!/connect\([^\n]*,'(?:road|bridge|garage|police)'\)/.test(source.nightLinks));
 c.C={hex:value=>value};c.extendNightWorld=()=>{};vm.runInContext(source.worldData+'\n'+source.authoredWorld+'\nWORLD=makeWorld();',c);
 assert.deepEqual(plain(c.owner.operations[0].steps.slice(1,3).map(s=>s.zone)),['corniche-exterior','corniche-exterior']);
 const table=[];
 for(const op of c.owner.operations)for(const [i,step]of op.steps.entries())if(step.kind==='drive'){
  const from=op.steps[i-1].zone;
  // Exercise the actual v45 graph owner against the actual authored makeWorld.
  c.from=from;c.to=step.zone;
  const route=vm.runInContext('test45.findRoute(from,to,true)',c);
  assert(route.length>=2,op.id+': '+from+' -> '+step.zone);
  for(let j=1;j<route.length;j++)assert(c.WORLD.links.some(l=>((l.a===route[j-1]&&l.b===route[j])||(l.b===route[j-1]&&l.a===route[j]))&&['road','bridge','garage','police'].includes(l.kind)));
  table.push({operation:op.id,from,to:step.zone,path:plain(route)});
 }
 assert.equal(table.length,5);c.from='port-exterior';c.to='corniche-route';assert.deepEqual(plain(vm.runInContext('test45.findRoute(from,to,true)',c)),[]);
});

test('legacy Corniche IDs preserve partial health, handled defeats and global loot without reward duplication',()=>{
 const c=fixture(),{op}=atStep(c,2),id='v45-operation-asphalte-fantome-2-0',second='v45-operation-asphalte-fantome-2-1';
 c.combat.zoneCombat['corniche-route']={enemies:{[id]:{health:0,maxHealth:150,downHandled:true,state:'dead'},[second]:{health:27,maxHealth:150,downHandled:false,state:'search'}}};
 c.combat.loot['loot-'+id]={zone:'corniche-route',role:'rifle',collected:true};
 c.enter('corniche-exterior');assert.equal(c.zone.robots.find(q=>q.id===id).health,0);assert.equal(c.zone.robots.find(q=>q.id===id).v32DownHandled,true);assert.equal(c.zone.robots.find(q=>q.id===second).health,27);
 c.__SOMA_V32__.snapshotCombat();c.combat.zoneCombat['corniche-exterior'].enemies[id].health=120;c.combat.zoneCombat['corniche-exterior'].enemies[id].downHandled=false;
 c.owner.rebuild();assert.equal(c.zone.robots.find(q=>q.id===id).health,0);assert.equal(c.zone.robots.find(q=>q.id===id).v32DownHandled,true);
 assert.equal(c.state.credits,240);assert.equal(Object.keys(c.combat.loot).length,1);assert.equal(c.combat.loot['loot-'+id].collected,true);
 const api=c.__SOMA_PROGRESSION74__;assert.equal(api.knownEnemy(id,'corniche-route'),true);assert.equal(api.knownEnemy(id,'corniche-exterior'),true);
 assert.equal(api.knownEnemy('v45-operation-asphalte-fantome-2-4','corniche-route'),false);assert.equal(api.knownEnemy('v45-operation-memoire-moteurs-2-0','corniche-route'),false);
 assert.equal(api.legacyLootRole('loot-'+second,'corniche-route','melee'),'blade');assert.equal(api.legacyLootRole('loot-'+id,'corniche-route','melee'),'melee');
 assert.equal(c.owner.state().operations[op.id].step,2);
});

test('source and legacy 151/150 interceptors preserve 151 HP, terminal defeats and the existing 100000 cap',()=>{
 const before=fixture(true);atStep(before,2);before.enter('corniche-route');const old=before.zone.robots.find(q=>q.id==='v45-operation-asphalte-fantome-2-2');
 assert.equal(old.health,151);assert.equal(old.maxHealth,150);
 const c=fixture();atStep(c,2);c.enter('corniche-exterior');const id=old.id,body=()=>c.zone.robots.find(q=>q.id===id);
 assert.equal(body().health,151);assert.equal(body().maxHealth,151);c.__SOMA_V32__.snapshotCombat();
 const record=c.combat.zoneCombat['corniche-exterior'].enemies[id];record.maxHealth=150;c.owner.rebuild();assert.equal(body().health,151);assert.equal(body().maxHealth,151);
 delete c.combat.zoneCombat['corniche-exterior'].enemies[id];c.combat.zoneCombat['corniche-route']={enemies:{[id]:{health:151,maxHealth:150,downHandled:false,state:'patrol'}}};
 c.owner.rebuild();assert.equal(body().health,151);assert.equal(body().maxHealth,151);
 const legacy=c.combat.zoneCombat['corniche-route'].enemies[id];legacy.health=0;legacy.downHandled=true;c.owner.rebuild();assert.equal(body().health,0);assert.equal(body().v32DownHandled,true);assert.equal(c.state.credits,240);
 delete c.combat.zoneCombat['corniche-route'].enemies[id];c.combat.zoneCombat['corniche-exterior'].enemies[id]={health:1e7,maxHealth:1e7,downHandled:false,state:'patrol'};
 c.owner.rebuild();assert.equal(body().health,100000);assert.equal(body().maxHealth,100000);
});

test('only the exact tracked old operation route migrates; manual GPS and progress counters remain intact',()=>{
 const c=fixture(),{op}=atStep(c,1),root=c.owner.state(),step=op.steps[1],api=c.__SOMA_PROGRESSION74__;
 root.route={targetZone:'corniche-route',label:step.label,path:[],vehicleOnly:true,updatedAt:1};const before=plain(root.stats);
 assert.equal(api.sync(),true);assert.equal(root.route.targetZone,'corniche-exterior');assert(root.route.path.length>=2);assert.equal(api.sync(),false);assert.deepEqual(plain(root.stats),before);
 root.route={targetZone:'corniche-route',label:'Mon point manuel',path:['station-exterior','corniche-route'],vehicleOnly:false,updatedAt:8};const manual=plain(root.route);
 assert.equal(api.sync(),false);assert.deepEqual(plain(root.route),manual);
 root.route.label=step.label;root.tracked={kind:'call',id:'port-convoi-sans-nom'};assert.equal(api.sync(),false);assert.equal(root.route.targetZone,'corniche-route');
 assert.equal(c.state.credits,240);
});

test('native channel cannot skip duration, survive death/import or complete from a different object',()=>{
 const c=fixture(),{op,s}=atStep(c,0);c.enter('port-exterior');const o=c.point(op.id,0);
 assert.equal(c.owner.advance(op.id),false);assert.equal(c.owner.node({...o}),false);assert.equal(c.owner.node(o),true);
 for(let i=0;i<25;i++)c.owner.tick(.1);assert.equal(s.step,0);c.owner.tick(.1);assert.equal(s.step,1);
 for(const interrupt of [c=>{c.state.health=0;},c=>c.importRoots(),c=>{c.zone={...c.zone};},c=>{c.state.recovery.pending=true;}]){
  const d=fixture(),p=atStep(d,0);d.enter('port-exterior');d.owner.node(d.point(p.op.id,0));d.owner.tick(.1);interrupt(d);d.owner.tick(10);
  assert.equal(d.owner.channel(),null);assert.equal(d.owner.state().operations[p.op.id].step,0);
 }
});

test('combat evidence is physical, drive requires transition, choice and hand-in callbacks expire on grouped-style root replacement',()=>{
 const c=fixture(),{op,s}=atStep(c,2);c.enter('corniche-exterior');const o=c.point(op.id,2);
 assert.equal(c.owner.node(o),true);assert.equal(s.step,2);for(const q of c.zone.robots)if(q.v45Owner===`operation-${op.id}-2`){q.health=0;q.v32DownHandled=true;}
 c.paused=false;assert.equal(c.owner.node(o),true);assert.equal(s.step,3);
 c.enter('station-exterior');assert.equal(c.owner.node(c.point(op.id,3)),true);const stale=c.dialogue.choices[0].action;
 c.importRoots();assert.equal(stale(),false);assert.equal(c.owner.state().operations[op.id].step,3);
 c.paused=false;assert.equal(c.owner.node(c.point(op.id,3)),true);const choose=c.dialogue.choices[0].action;
 assert.equal(choose(),true);assert.equal(choose(),false);assert.equal(c.owner.state().operations[op.id].status,'return');
 const console=c.zone.interactables.find(o=>o.type==='v45CommandConsole');c.camera.x=console.x;c.camera.z=console.z;c.owner.command();const oldHandIn=c.dialogue.choices[0].action;
 c.importRoots();assert.equal(oldHandIn(),false);assert.equal(c.state.credits,240);
 const d=fixture(),p=atStep(d,1);d.enter('corniche-exterior');d.state.driving='car';d.zone.vehicles.push({id:'car'});d.owner.changed('port-exterior','corniche-exterior');
 assert.equal(p.s.step,2);assert.equal(d.owner.advance(p.op.id),false);
});
