'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),path=require('node:path');
const {scripts,part,context}=require('./combat-fixture.cjs');
const plain=x=>JSON.parse(JSON.stringify(x));

test('qualified before proof: the real v74 sniper banks 1s behind a wall then hits within one reacquisition frame',()=>{
 const c=context('sniper',true);c.acquire();while((c.q.charge||0)<.99)c.tick();
 assert.equal(c.state.health,100);const charge=c.q.charge;c.cover();c.tick(15);
 assert.equal(c.q.charge,charge);assert.equal(c.state.health,100);assert(c.q.attackClock<0);
 c.walls=[];let frames=0;while(c.state.health===100&&frames<30){c.tick();frames++;}
 assert.equal(c.state.health,77);assert.equal(frames,1);
});

test('real perception70 + radio72 + makeEnemy32 prepare a fresh 1.05s shot and apply original damage/armour once',()=>{
 const c=context();c.state.armor=8;c.start();assert.equal(c.api.snapshot().activeChannels,1);assert.equal(c.q.attackClock,2.7);
 assert.equal(c.q.charge,undefined);assert.equal(c.state.health,100);c.tick(10);assert.equal(c.state.health,100);
 c.tick();assert.equal(c.state.health,85);assert.equal(c.state.armor,0);assert.equal(c.S.combat.damageTaken,23);assert.equal(c.q.attackClock,2.7);
 assert.deepEqual(plain(c.api.snapshot().counters),{started:1,completed:1,interrupted:0});c.tick(5);assert.equal(c.state.health,85);
 assert.equal(c.deck.cyberdeck.energy,73);assert(!Object.hasOwn(c.state,'v75'));
});

test('cover interrupts personal visual contact; paid recovery prevents a stale shot and the next shot prepares fully',()=>{
 const c=context();c.start();c.tick(9);c.cover();c.tick();
 assert.equal(c.api.snapshot().activeChannels,0);assert.equal(c.api.snapshot().lastInterruption,'contact-lost');assert(c.q.attackClock>=2.59);
 assert.equal(c.__SOMA_PERCEPTION70__.observer(c.q.id).canAttack,false);c.walls=[];c.tick(10);
 assert.equal(c.api.snapshot().counters.started,1);assert.equal(c.state.health,100);
 for(let i=0;i<30&&!c.api.snapshot().activeChannels;i++)c.tick();assert.equal(c.api.snapshot().activeChannels,1);
 assert.equal(c.api.snapshot().channels[0].progress,0);c.tick(10);assert.equal(c.state.health,100);c.tick();assert.equal(c.state.health,77);
});

test('a real radio report never starts or maintains a hidden sniper shot, blade impact or heavy salve',()=>{
 for(const role of ['sniper','blade','heavy']){
  const c=context(role);if(role==='blade'){c.q.z=1.4;c.q.homeZ=1.4;}
  c.q.heading=0;const scout=c.spawn('rifle',6,15);scout.attackClock=999;
  c.tick(15);const p=c.__SOMA_PERCEPTION70__.observer(c.q.id);
  assert.equal(p.reason,'radio-last-known',role);assert.equal(p.canAttack,false);assert.equal(p.canTrackCurrent,false);
  assert.equal(c.state.health,100);assert.equal(c.api.snapshot().activeChannels,0);
 }
});

test('real received health loss interrupts and factor33 controls both damage and paid recovery',()=>{
 const c=context();c.q.v33AttackFactor=.6;c.start();assert(Math.abs(c.q.attackClock-4.5)<1e-8);c.tick(4);c.q.health-=1;c.tick();
 assert.equal(c.api.snapshot().lastInterruption,'received-hit');assert(c.q.attackClock>=4.39);assert.equal(c.state.health,100);c.tick(20);assert.equal(c.state.health,100);
 const d=context();d.q.v33AttackFactor=.6;d.start();d.tick(11);assert(Math.abs(d.state.health-86.2)<1e-8);assert(Math.abs(d.q.attackClock-4.5)<1e-8);
});

test('the real paused render loop cancels before its no-simulation branch and cannot resume a ready shot',()=>{
 const c=context();c.start();c.tick(9);c.paused=true;c.last=0;c.frameDebt=0;c.renderer={};c.requestAnimationFrame=()=>{};
 c.__SOMA_PERF65__={gate:{shouldRender:()=>false},stats:{simulationSteps:0}};c.currentWeather=()=>({});c.devicePixelRatio=1;
 vm.runInContext(scripts.loop,c);c.loop(1000);assert.equal(c.api.snapshot().activeChannels,0);assert.equal(c.q.attackClock,2.7);
 c.paused=false;c.tick(10);assert.equal(c.state.health,100);assert.equal(c.api.snapshot().counters.started,1);
});

test('real perception import reset, death, driving, recovery, tab, state/zone identity and body replacement consume preparation',()=>{
 for(const action of [c=>{c.__SOMA_PERCEPTION70__.reset();},c=>{c.state.health=0;},c=>{c.state.driving='car';},c=>{c.state.recovery={pending:true};},
  c=>{c.state.recoveryGrace=1;},c=>{c.document.hidden=true;},c=>{c.cyber=true;},c=>{c.state={...c.state};},c=>{c.zone={...c.zone};},
  c=>{c.zone.id='other';},c=>{c.zone.robots=[{...c.q}];},c=>{c.q.id='changed';},c=>{c.q.hidden=true;},c=>{c.q.disabled=true;},c=>{c.q.retire=true;}]){
  const c=context();c.start();c.tick(5);action(c);c.api.maintain();assert.equal(c.api.snapshot().activeChannels,0);assert.equal(c.q.attackClock,2.7);
 }
});

test('the one shared warning node uses real frustum and Écho75 reports the active channel, with no new HUD',()=>{
 const c=context();c.start();c.tick(4);c.__SOMA_NETRUNNER72__.maintain();
 assert.equal(c.hud().hidden,false);assert.match(c.hud().children[0].textContent,/TIR DE PRÉCISION EN PRÉPARATION/);
 assert.equal(c.hud().children.find(x=>x.tag==='meter').attrs['aria-label'],'Préparation du tir de précision');
 assert.equal(c.document.body.children.filter(x=>x.tag==='aside').length,1);
 vm.runInContext(scripts.echo,c);const row=c.__SOMA_TACTICAL73__.scanTargets().find(r=>r.id===c.q.id);
 assert.match(row.roleLabel,/Tir préparé · 38 %/);assert.match(row.hint,/Touchez le tireur/);
 c.camera.yaw=Math.PI;c.api.maintain();c.__SOMA_NETRUNNER72__.maintain();assert.equal(c.hud().hidden,true);
 assert.equal(c.api.snapshot().activeChannels,1);assert.equal(c.__SOMA_TACTICAL73__.scanTargets().length,0);
 c.camera.yaw=0;c.camera.pitch=1.2;c.__SOMA_NETRUNNER72__.maintain();assert.equal(c.hud().hidden,true);
 c.camera.pitch=0;c.cover();c.tick();c.__SOMA_NETRUNNER72__.maintain();assert.equal(c.hud().hidden,true);
});

test('mixed sniper and neural channels share four warning rows while their real effects and cooldown owners stay independent',()=>{
 const c=context();const runner=c.spawn('netrunner',2,20,1);c.start();c.__SOMA_NETRUNNER72__.maintain();
 const rows=c.__SOMA_NETRUNNER72__.snapshotHUD().telegraphs;assert.equal(rows.length,2);
 assert(rows.some(row=>row.title==='TIR DE PRÉCISION EN PRÉPARATION'));assert(rows.some(row=>!row.title));
 assert.equal(c.document.body.children.filter(x=>x.id==='v72-netrunner-hud').length,1);
 c.tick(11);assert.equal(c.state.health,77);assert.equal(c.state.tension,9);assert.equal(c.S.status.jammed,2.8);
 assert.equal(c.q.attackClock,2.7);assert.equal(runner.attackClock,3.6);assert.equal(c.deck.cyberdeck.energy,73);
});

test('real tactics33 keep an acquired sniper aiming throughout preparation and resume their actual path on impact',()=>{
 const c=context();c.tactics();c.start();c.tick(2);assert(c.q.v33Target,'real overwatch assignment exists');
 const pose={x:c.q.x,z:c.q.z};assert.equal(c.q.v33Order,'overwatch');assert.equal(c.api.isPreparing(c.q),true);
 c.q.vx=4;c.q.vz=5;c.tick();assert.equal(c.q.vx,0);assert.equal(c.q.vz,0);
 c.tick(7);assert.equal(c.state.health,100);assert.equal(c.q.x,pose.x);assert.equal(c.q.z,pose.z);
 assert.equal(c.q.heading,Math.PI);assert.equal(c.__SOMA_PERCEPTION70__.observer(c.q.id).canAttack,true);
 c.tick();assert.equal(c.state.health,77);assert.equal(c.q.attackClock,2.7);assert.equal(c.api.isPreparing(c.q),false);
 assert(c.q.z>pose.z,'actual followTarget/moveAlongPath resume during recovery');assert(c.q.vz>0);assert.equal(c.q.heading,0);
});

test('with real tactics33, damage or cover cancels aiming and the retained overwatch path resumes immediately',()=>{
 for(const action of [c=>{c.q.health-=1;},c=>{c.cover();}]){
  const c=context();c.tactics();c.start();c.tick(2);assert(c.q.v33Target);const before=c.q.z;
  action(c);c.tick();assert.equal(c.api.isPreparing(c.q),false);assert.equal(c.state.health,100);assert(c.q.attackClock>=2.59);
  assert(c.q.z>before);assert(c.q.vz>0);assert.equal(c.q.heading,0);
  assert(c.q.v33Target,'the real tactical destination remains owned by33');
 }
});

test('terrain body points and real sight61 box rays respect NGF, camera height, unknown terrain and local NPC animation',()=>{
 const c=context();c.camera.y=101.72;c.q.y=50000;c.rays=[];c.walls=[];
 c.__SOMA_SIGHT61__={activeFor:()=>true,eyePoint:(x,z,zone,h)=>[x,100+h,z],between:(a,b)=>{c.rays.push([plain(a),plain(b)]);return false;}};
 c.start();c.tick(3);assert.equal(c.api.snapshotHUD().telegraphs.length,1);
 assert(c.rays.every(([a,b])=>a[1]===101.45&&b[1]===101.72));
 c.__SOMA_SIGHT61__.eyePoint=()=>null;c.api.maintain();assert.equal(c.api.snapshot().activeChannels,0);assert.equal(c.state.health,100);
 const d=context();d.__SOMA_SIGHT61__={activeFor:()=>true,eyePoint:(x,z,zone,h)=>[x,100+h,z],between:()=>true};d.camera.y=101.72;d.tick(30);
 assert.equal(d.api.snapshot().counters.started,0);
});

test('floor32 and territory33 real save owners preserve paid recovery, strip charge and restore without resuming a channel',()=>{
 const c=context();c.start();c.tick(9);c.saveOwners();c.snapshotCombat();
 const rec=plain(c.zoneCombatState(c.zone.id).enemies[c.q.id]),saved=plain(c.serializeEnemy(c.q));
 assert.equal(rec.attackClock,2.7);assert.equal(saved.attackClock,2.7);assert(!Object.keys(saved).some(k=>/charge|elapsed|channel/i.test(k)));
 c.__SOMA_PERCEPTION70__.reset();const fresh=c.spawn('sniper',0,20,20);fresh.id=c.q.id;fresh.attackClock=.4;c.restoreEnemy(fresh);assert.equal(fresh.attackClock,2.7);
 c.restoreRoster(c.zone,{roster:{[saved.id]:saved}});c.api.maintain();assert.equal(c.zone.robots[0].attackClock,2.7);assert.equal(c.api.snapshot().activeChannels,0);
 c.q=c.zone.robots[0];c.tick(10);assert.equal(c.state.health,100);assert.equal(c.api.snapshot().counters.started,1);
 c.q.attackClock=18;assert.equal(c.serializeEnemy(c.q).attackClock,18);delete rec.attackClock;
 c.zoneCombatState(c.zone.id).enemies[c.q.id]=rec;fresh.attackClock=.4;c.restoreEnemy(fresh);assert.equal(fresh.attackClock,.4);
});

test('city45 encounter restores its paid sniper recovery through the same owner; malformed37 cooldowns remain refused',()=>{
 const c=context();c.start();c.saveOwners();c.snapshotCombat();c.v45Clamp=c.clamp;c.v74LegacyEnemy=()=>false;
 vm.runInContext(part(scripts.city,'function v74RestoreEnemy(q,z){','function v74Checkpoint('),c);
 const q={...c.q,attackClock:0};c.v74RestoreEnemy(q,c.zone);assert.equal(q.attackClock,2.7);
 Object.assign(c,{record:()=>{},api:()=>({freshState:()=>({})}),validateShape:()=>{},set:()=>new Set(),knownKeys:()=>{},enumOf:()=>{},member:()=>{},
  enemyIdKnown:()=>true,fail:(...args)=>{throw Error(args.join(':'));},number:(n,min,max,label)=>{if(typeof n!=='number'||!Number.isFinite(n)||n<min||n>max)throw Error(label);}});
 vm.runInContext(part(scripts.persistence,'function validateLayer(v,q,k){','function validate('),c);
 const k={districts:new Set(),roles:new Set(['sniper']),zones:new Set([c.zone.id])},layer={schema:32,gigs:{},followingGig:null,redZones:{},combat:{kills:{}},zoneCombat:{[c.zone.id]:{enemies:{[c.q.id]:{health:78,state:'combat',attackClock:2.7}}}},loot:{}};
 assert.doesNotThrow(()=>c.validateLayer(32,layer,k));for(const bad of [-1,3601,NaN,Infinity,'2.7',null]){layer.zoneCombat[c.zone.id].enemies[c.q.id].attackClock=bad;assert.throws(()=>c.validateLayer(32,layer,k),/Recharge ennemie/);}
});

test('real Rempart70 still absorbs sniper damage before armour with the finite budget; weapons stay owned by32',()=>{
 const c=context(),{createController}=require(path.resolve(__dirname,'../../src/v70/runtime.js'));let domain;
 const controller=createController({read:()=>domain,write:x=>{domain=x;},schedule:()=>{},context:()=>({energy:c.deck.cyberdeck.energy,health:c.state.health,
  onFoot:true,paused:c.paused,channeling:false,driving:false,cyberspace:false,tension:c.state.tension}),spend:(cost,tension)=>{c.deck.cyberdeck.energy-=cost;c.state.tension+=tension;return true;}});
 assert.equal(controller.activate('barrier').accepted,true);c.__SOMA_V70__.mitigateIncoming=amount=>controller.mitigate(amount).damage;
 c.state.armor=5;c.start();c.tick(11);assert(Math.abs(c.state.health-94.65)<1e-8);assert.equal(c.state.armor,0);
 assert(Math.abs(controller.snapshot().barrierRemaining-27.35)<1e-8);assert.equal(c.deck.cyberdeck.energy,45);
});

test('heavy and blade keep true personal sight counterplay and their own original weapon damage and cooldown',()=>{
 for(const [role,z,damage,cooldown]of [['blade',1.4,15,.82],['heavy',15,14,1.7]]){
  const c=context(role);c.q.z=z;c.q.homeZ=z;c.acquire();assert.equal(c.state.health,100-damage);assert.equal(c.q.attackClock,cooldown);
  c.walls.push({lo:[-2,0,z/3],hi:[2,4,z/2]});c.tick(40);assert.equal(c.state.health,100-damage);assert.equal(c.api.snapshot().activeChannels,0);
 }
});

test('boss/ICE, human quickhacks, large deltas, shared DOM and active channel bounds retain their contracts',()=>{
 for(const change of [q=>{q.v26BossId='boss';},q=>{q.v27ICE=true;},q=>{q.id='boss36';}]){
  const c=context();c.__SOMA_BOSSES36__={handles:q=>q.id==='boss36',suspended:()=>false};change(c.q);c.tick(30);assert.equal(c.api.snapshot().counters.started,0);
 }
 const c=context();c.start();c.tick(1,100);assert.equal(c.state.health,100);assert.equal(c.api.snapshot().channels[0].progress,.25/1.05);
 const cap=context();cap.state.health=100000;for(let i=1;i<50;i++)cap.spawn('sniper',i/20,20,i);cap.tick(8);
 assert.equal(cap.api.snapshot().activeChannels,32);cap.tick();assert.equal(cap.api.snapshot().activeChannels,32);
 assert(cap.api.snapshot().lineChecks<=128,'64 update rays plus two explicit 32-channel snapshots');
 assert.equal(cap.__SOMA_NETRUNNER72__.snapshotHUD().telegraphs.length,4);assert.equal(cap.document.body.children.filter(x=>x.id==='v72-netrunner-hud').length,1);
 vm.runInContext(part(scripts.v42,'function v42Machine(q){','function v42Effects('),c);c.V42_HUMAN_ROLES=new Set(['rifle','melee','sniper','netrunner']);
 assert.equal(c.v42Machine(c.q),false);assert.equal(c.v42Supports(c.q,'jam'),false);
});
