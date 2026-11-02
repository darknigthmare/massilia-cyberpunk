'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),path=require('node:path');
const {scripts,part,context}=require('./combat-fixture.cjs');
const plain=x=>JSON.parse(JSON.stringify(x));

test('qualified design before proof: heavy75 fires immediately at personal acquisition',()=>{
 const c=context('heavy',true);c.acquire();assert.equal(c.state.health,86);assert.equal(c.q.attackClock,1.7);
});

test('heavy76 prepares0.70s with real perception70/radio72, then owner32 applies one original salve and armour',()=>{
 const c=context();c.state.armor=8;c.start();assert.equal(c.api.snapshot().activeChannels,1);assert.equal(c.q.attackClock,1.7);
 c.tick(6);assert.equal(c.state.health,100);c.tick();assert.equal(c.state.health,94);assert.equal(c.state.armor,0);
 assert.equal(c.S.combat.damageTaken,14);assert.equal(c.q.attackClock,1.7);assert.deepEqual(plain(c.api.snapshot().counters),{started:1,completed:1,interrupted:0});
 c.tick(5);assert.equal(c.state.health,94);assert.equal(c.deck.cyberdeck.energy,73);assert(!Object.hasOwn(c.state,'v76'));
});

test('cover or received impact cancels preparation; paid recovery remains and reacquisition starts a full salve',()=>{
 for(const change of [c=>c.cover(),c=>{c.q.health-=1;}]){
  const c=context();c.start();c.tick(5);change(c);c.tick();assert.equal(c.api.snapshot().activeChannels,0);
  assert(c.q.attackClock>=1.59);assert.equal(c.state.health,100);c.walls=[];c.tick(8);assert.equal(c.api.snapshot().counters.started,1);
  for(let i=0;i<30&&!c.api.isPreparing(c.q);i++)c.tick();assert.equal(c.api.snapshot().channels[0].progress,0);
  c.tick(6);assert.equal(c.state.health,100);c.tick();assert.equal(c.state.health,86);
 }
});

test('real radio reports permit search without heavy preparation or immediate blade impact',()=>{
 for(const role of ['heavy','blade']){
  const c=context(role);if(role==='blade'){c.q.z=1.4;c.q.homeZ=1.4;}c.q.heading=0;
  const scout=c.spawn('rifle',6,15);scout.attackClock=999;c.tick(15);const p=c.__SOMA_PERCEPTION70__.observer(c.q.id);
  assert.equal(p.reason,'radio-last-known');assert.equal(p.canAttack,false);assert.equal(p.canTrackCurrent,false);assert.equal(c.state.health,100);
  assert.equal(c.api.snapshot().activeChannels,0);
 }
});

test('factor33 and the real Rempart70 mitigation remain owned by damage32',()=>{
 const c=context();c.q.v33AttackFactor=.6;c.start();assert(Math.abs(c.q.attackClock-1.7/.6)<1e-8);c.tick(7);
 assert(Math.abs(c.state.health-91.6)<1e-8);assert(Math.abs(c.q.attackClock-1.7/.6)<1e-8);
 const d=context(),{createController}=require(path.resolve(__dirname,'../../src/v70/runtime.js'));let domain;
 const controller=createController({read:()=>domain,write:x=>{domain=x;},schedule:()=>{},context:()=>({energy:d.deck.cyberdeck.energy,health:d.state.health,
  onFoot:true,paused:d.paused,channeling:false,driving:false,cyberspace:false,tension:d.state.tension}),spend:(cost,tension)=>{d.deck.cyberdeck.energy-=cost;d.state.tension+=tension;return true;}});
 assert.equal(controller.activate('barrier').accepted,true);d.__SOMA_V70__.mitigateIncoming=amount=>controller.mitigate(amount).damage;
 d.state.armor=2;d.start();d.tick(7);assert(Math.abs(d.state.health-95.7)<1e-8);assert.equal(d.state.armor,0);
 assert(Math.abs(controller.snapshot().barrierRemaining-32.3)<1e-8);assert.equal(d.deck.cyberdeck.energy,45);
});

test('real paused render loop cancels before simulation; lifecycle changes never resume a preparation',()=>{
 const c=context();c.start();c.tick(5);c.paused=true;c.last=0;c.frameDebt=0;c.renderer={};c.requestAnimationFrame=()=>{};
 c.__SOMA_PERF65__={gate:{shouldRender:()=>false},stats:{simulationSteps:0}};c.currentWeather=()=>({});c.devicePixelRatio=1;
 vm.runInContext(scripts.loop,c);c.loop(1000);assert.equal(c.api.snapshot().activeChannels,0);assert.equal(c.q.attackClock,1.7);
 for(const action of [c=>c.__SOMA_PERCEPTION70__.reset(),c=>{c.state.health=0;},c=>{c.state.driving='car';},c=>{c.state.recovery={pending:true};},
  c=>{c.state.recoveryGrace=1;},c=>{c.document.hidden=true;},c=>{c.cyber=true;},c=>{c.state={...c.state};},c=>{c.zone={...c.zone};},
  c=>{c.zone.id='other';},c=>{c.zone.robots=[{...c.q}];},c=>{c.q.id='changed';},c=>{c.q.hidden=true;},c=>{c.q.disabled=true;},c=>{c.q.retire=true;}]){
  const d=context();d.start();d.tick(4);action(d);d.api.maintain();assert.equal(d.api.snapshot().activeChannels,0);assert.equal(d.q.attackClock,1.7);
 }
});

test('heavy warning shares the existing HUD and Écho with sniper/neural, bounded to four rows',()=>{
 const c=context();const sniper=c.spawn('sniper',2,20),runner=c.spawn('netrunner',-2,20);c.start();c.tick(3);c.__SOMA_NETRUNNER72__.maintain();
 assert.equal(c.hud().hidden,false);assert(c.hud().children.some(x=>/SALVE LOURDE EN PRÉPARATION/.test(x.textContent)));
 assert(c.hud().children.some(x=>x.tag==='meter'&&x.attrs['aria-label']==='Préparation de la salve lourde'));
 vm.runInContext(scripts.echo,c);const row=c.__SOMA_TACTICAL73__.scanTargets().find(r=>r.id===c.q.id);
 assert.match(row.roleLabel,/Salve préparée · 42 %/);assert.match(row.hint,/Touchez l’unité lourde/);
 const rows=c.__SOMA_NETRUNNER72__.snapshotHUD().telegraphs;assert(rows.some(r=>r.title==='SALVE LOURDE EN PRÉPARATION'));
 assert(rows.some(r=>r.title==='TIR DE PRÉCISION EN PRÉPARATION'));assert(rows.some(r=>!r.title));
 assert.equal(c.document.body.children.filter(x=>x.id==='v72-netrunner-hud').length,1);assert(rows.length<=4);
 c.camera.yaw=Math.PI;c.__SOMA_NETRUNNER72__.maintain();assert.equal(c.hud().hidden,true);
 assert.equal(c.__SOMA_TACTICAL73__.scanTargets().length,0);assert(sniper&&runner);
});

test('actual tactics33 and branch32 hold heavy aim and release the existing path after interruption',()=>{
 const c=context();c.tactics();c.q.health=c.q.maxHealth*.35;c.start();c.tick(2);const pose={x:c.q.x,z:c.q.z};assert(c.q.v33Target);
 c.q.vx=4;c.q.vz=5;c.tick(2);assert.equal(c.q.x,pose.x);assert.equal(c.q.z,pose.z);assert.equal(c.q.vx,0);assert.equal(c.q.vz,0);
 c.q.health-=1;c.tick();assert.equal(c.api.isPreparing(c.q),false);assert.equal(c.state.health,100);
 assert(Math.hypot(c.q.x-pose.x,c.q.z-pose.z)>0,'actual followTarget path resumes');assert(c.q.v33Target);
});

test('native sight61 receives NGF body-to-camera rays and stops preparation for missing ground/terrain/building cover',()=>{
 const c=context();c.camera.y=101.72;c.q.y=50000;c.rays=[];
 c.__SOMA_SIGHT61__={activeFor:()=>true,eyePoint:(x,z,zone,h)=>[x,100+h,z],between:(a,b)=>{c.rays.push([plain(a),plain(b)]);return false;}};
 c.start();c.tick(3);assert(c.rays.every(([a,b])=>a[1]===101.45&&b[1]===101.72));assert.equal(c.api.snapshotHUD().telegraphs.length,1);
 c.__SOMA_SIGHT61__.eyePoint=()=>null;c.api.maintain();assert.equal(c.api.snapshot().activeChannels,0);
 const d=context();d.__SOMA_SIGHT61__={activeFor:()=>true,eyePoint:(x,z,zone,h)=>[x,100+h,z],between:()=>true};d.camera.y=101.72;d.tick(30);
 assert.equal(d.api.snapshot().counters.started,0);assert.equal(d.state.health,100);
});

test('actual native61 runtime and exact prism/DTM core gate heavy damage for open, building, ridge and NoData fixtures',()=>{
 // Qualified synthetic source cell: native61 owns every ray and intersection.
 // The source dimensions/ground adapter below is declared fixture data, not IGN.
 for(const mode of ['open','building','terrain','nodata']){
  const c=context();c.camera.y=101.72;c.q.y=50000;
  const features=mode==='building'?[{id:'fixture-building',properties:{'soma:layer':'buildings','soma:mesh53':[{areaM2:12,ringsL93:[[[-3,-8],[3,-8],[3,-6],[-3,-6],[-3,-8]]]}]}}]:[];
  Object.assign(c.zone,{v52District:'fixture',v52CellId:'fixture',static:[],vehicles:[],v50Record:{cellId:'fixture',v53Validated:true,
   boundsL93:[-50,-50,50,50],sourceReceipt:{sha256:'synthetic-test'},featureCollection:{features}}});
  const grid={x0:-50,n0:50,cols:21,rows:21,step:5,
   node:(x,y)=>mode==='nodata'&&y===11?null:mode==='terrain'&&y===11?106:100,
   sample:(x,n)=>100};
  c.__SOMA_TERRAIN56__={activeFor:()=>true,ground:()=>100,grid,pack:{sha256:'synthetic-test'},buildingDatum:()=>({base:100,min:100})};
  c.__SOMA_V50__={core:{buildingHeight:()=>10}};c.__SOMA_FIDELITY59_CORE__={dimension:()=>({valid:true,minHeight:0,height:10,heightSource:'synthetic-test'})};
  c.__SOMA_FIDELITY59__={heightReference:()=>null};c.__SOMA_CLEARANCE60__={ready:true};
  c.__SOMA_V57_CORE__={SpatialIndex:class{constructor(boxes){this.boxes=boxes;}query(){return this.boxes;}}};
  c.__SOMA_V52__={zones:()=>new Map([['fixture',c.zone]]),open:()=>{}};c.__SOMA__={};c.buildZone=()=>{};
  c.v34ShotOccluded=()=>false;c.v34ResolveHit=()=>null;c.document.querySelector=()=>null;
  vm.runInContext(scripts.sightRuntime,c);assert.equal(c.__SOMA_SIGHT61__.ready,true);
  c.tick(30);const summary=c.__SOMA_SIGHT61__.summary();assert(summary.statistics.rays>0);
  if(mode==='open'){assert(c.state.health<100);assert(c.api.snapshot().counters.completed>0);}
  else{assert.equal(c.state.health,100,mode);assert.equal(c.api.snapshot().counters.started,0,mode);
   assert(summary.statistics[mode==='building'?'buildingHits':mode==='terrain'?'terrainHits':'unknownStops']>0,mode);}
 }
});

test('floor32, roster33 and city45 save only paid attackClock and restore without resuming heavy charge',()=>{
 const c=context();c.start();c.tick(5);c.saveOwners();c.snapshotCombat();
 const rec=plain(c.zoneCombatState(c.zone.id).enemies[c.q.id]),saved=plain(c.serializeEnemy(c.q));
 assert.equal(rec.attackClock,1.7);assert.equal(saved.attackClock,1.7);assert(!Object.keys(saved).some(k=>/charge|elapsed|channel/i.test(k)));
 c.__SOMA_PERCEPTION70__.reset();const fresh=c.spawn('heavy',0,15,20);fresh.id=c.q.id;fresh.attackClock=.4;c.restoreEnemy(fresh);assert.equal(fresh.attackClock,1.7);
 c.restoreRoster(c.zone,{roster:{[saved.id]:saved}});c.api.maintain();assert.equal(c.zone.robots[0].attackClock,1.7);assert.equal(c.api.snapshot().activeChannels,0);
 c.v45Clamp=c.clamp;c.v74LegacyEnemy=()=>false;vm.runInContext(part(scripts.city,'function v74RestoreEnemy(q,z){','function v74Checkpoint('),c);
 const q={...c.q,attackClock:0};c.v74RestoreEnemy(q,c.zone);assert.equal(q.attackClock,1.7);
});

test('boss/ICE/suspended actors stay outside the heavy feature; large deltas and channels obey finite budgets',()=>{
 for(const change of [q=>{q.v26BossId='boss';},q=>{q.v27ICE=true;},q=>{q.id='boss36';},q=>{q.id='suspended';}]){
  const c=context();c.__SOMA_BOSSES36__={handles:q=>q.id==='boss36',suspended:q=>q.id==='suspended'};change(c.q);c.tick(30);assert.equal(c.api.snapshot().counters.started,0);
 }
 const c=context();c.start();c.tick(1,100);assert.equal(c.state.health,100);assert.equal(c.api.snapshot().channels[0].progress,.25/.7);
 const cap=context();cap.state.health=100000;for(let i=1;i<50;i++)cap.spawn('heavy',i/20,15,i);cap.tick(8);
 assert.equal(cap.api.snapshot().activeChannels,32);cap.tick();assert(cap.api.snapshot().lineChecks<=128);
 assert.equal(cap.__SOMA_NETRUNNER72__.snapshotHUD().telegraphs.length,4);
});

test('qualified real consumable28 before proof: brume pays stock but perception75 keeps attack right',()=>{
 const c=context('rifle',true);c.q.z=8;c.q.homeZ=8;c.acquire();assert.equal(c.state.health,92);
 assert.equal(c.consume().ok,true);assert.equal(c.stock.consumables.smokeCapsule,0);assert.equal(c.q.v28ObscuredUntil,11000);
 c.tick(20);assert.equal(c.state.health,84);assert.equal(c.__SOMA_PERCEPTION70__.observer(c.q.id).canAttack,true);
});

test('real consumable28 smoke blocks personal sight70, retains hearing/radio search, uses exact authored stock/radius/deadline',()=>{
 const c=context('rifle');c.q.z=8;c.q.homeZ=8;const outside=c.spawn('rifle',0,12);outside.attackClock=999;c.acquire();assert.equal(c.state.health,92);
 assert.equal(c.consume().ok,true);assert.equal(c.stock.consumables.smokeCapsule,0);assert.equal(c.stock.stats.consumablesUsed,1);
 assert.equal(c.q.v28ObscuredUntil,11000);assert.equal(outside.v28ObscuredUntil,undefined);
 outside.z=40;c.tick(20);const p=c.__SOMA_PERCEPTION70__.observer(c.q.id);assert.equal(p.canAttack,false);assert.equal(p.canTrackCurrent,false);
 assert.equal(c.state.health,92);c.__SOMA_PERCEPTION70__.recordShot();c.tick();assert(c.__SOMA_PERCEPTION70__.observer(c.q.id).searchTarget);
 assert.equal(c.__SOMA_PERCEPTION70__.observer(c.q.id).canAttack,false);c.now=10999;c.tick();assert.equal(c.state.health,92);
 c.now=11000;for(let i=0;i<30&&c.state.health===92;i++)c.tick();assert(c.state.health<92);assert.equal(c.api.isObscured(c.q),false);
});

test('smoke cancels a real heavy channel with paid recovery and expiry follows source performance.now even across pause',()=>{
 const c=context();c.q.z=8;c.q.homeZ=8;c.start();c.tick(4);assert.equal(c.consume().ok,true);c.tick();
 assert.equal(c.api.isPreparing(c.q),false);assert.equal(c.state.health,100);assert(c.q.attackClock>=1.59);
 c.paused=true;c.now=11000;c.api.maintain();assert.equal(c.api.isObscured(c.q),false);assert.equal(c.q.v28ObscuredUntil,11000);
});

test('legacy71 smoke affects only robots already marked by real consumable28, leaving human/vehicle and boss/ICE ownership intact',()=>{
 const c=context('rifle');c.state.police={level:1};c.zone.actors=[];c.zone.vehicles=[];
 const robot={id:'old-security',kind:'security',hostile:true,health:100,x:0,z:8,heading:Math.PI};c.zone.robots.push(robot);
 vm.runInContext(scripts.legacy,c);const api=c.__SOMA_LEGACY_PERCEPTION71__;
 for(let i=0;i<30&&!api.observer('robot',robot)?.canAttack;i++)api.beginFrame(.1);assert.equal(api.observer('robot',robot).canAttack,true);
 c.consume();api.beginFrame(.1);assert.equal(api.observer('robot',robot).canAttack,false);assert.equal(api.observer('robot',robot).canTrackCurrent,false);
 c.now=11000;api.beginFrame(.1);assert.equal(api.observer('robot',robot).canAttack,true);
});

test('sniper75 preparation, guard33 and medical74/neural72 owners remain active under76',()=>{
 const c=context('sniper');c.acquire();for(let i=0;i<4&&!c.__SOMA_COMBAT75__.isPreparing(c.q);i++)c.tick();c.tick(10);assert.equal(c.state.health,100);c.tick();assert.equal(c.state.health,77);
 assert.equal(c.q.attackClock,2.7);assert.equal(c.api.snapshot().counters.started,0);
 const d=context('sniper');d.tactics();d.acquire();for(let i=0;i<4&&!d.__SOMA_COMBAT75__.isPreparing(d.q);i++)d.tick();d.tick();const z=d.q.z;d.tick(2);assert.equal(d.q.z,z);
 d.q.health-=1;d.tick();assert(d.q.z>z);assert(d.__SOMA_COMBAT_SUPPORT74__&&d.__SOMA_NETRUNNER72__);
});
