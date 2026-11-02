'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const scripts=require('./combat-support-fixture.cjs');
const part=(text,start,end)=>{assert.equal(text.split(start).length,2);return text.slice(text.indexOf(start),text.indexOf(end,text.indexOf(start)));};
const plain=x=>JSON.parse(JSON.stringify(x));
function element(tag){return {tag,children:[],hidden:false,textContent:'',style:{},attrs:{},
 setAttribute(k,v){this.attrs[k]=v;},appendChild(x){this.children.push(x);return x;},
 getBoundingClientRect(){return {left:0,top:0,width:196,height:96};}};}
function unit(id,role,x=0,z=10){return {id,v32Enemy:true,v32Role:role,v32Label:role+' QA',kind:'v32',health:88,maxHealth:88,
 x,z,y:0,homeX:x,homeZ:z,heading:Math.PI,state:'combat',detect:1,searchClock:5,attackClock:0,patrolIndex:0,v33Faction:'palimpseste'};}
function context(){
 const q=unit('medic:1','medic'),ally={...unit('ally:1','rifle',2),health:50,maxHealth:100};
 const c={Math,Map,Set,Object,JSON,Number,String,performance:{now:()=>1000},camera:{x:0,z:0,y:1.72,yaw:0,pitch:0},
  state:{health:100,armor:30,tension:0,settings:{volume:0,reduceMotion:true,largeText:true,fov:67}},
  zone:{id:'qa-zone',robots:[q,ally],v32CoverPoints:[]},keys:new Set(),paused:false,cyber:false,
  S:{status:{jammed:0,suppressed:0},combat:{headshots:0},lastShotAt:-999},
  blocked:()=>false,blockAll:false,blockAlly:false,playerBlocked:false,
  lineBlocked:(x0,z0,x1,z1)=>c.blockAll||c.blockAlly&&(x0===q.x&&z0===q.z&&x1===ally.x&&z1===ally.z)||
    c.playerBlocked&&(x0===c.camera.x&&z0===c.camera.z||x1===c.camera.x&&z1===c.camera.z),
  headingVec:h=>({x:Math.sin(h),z:Math.cos(h)}),clamp:(n,a,b)=>Math.max(a,Math.min(b,n)),
  onEnemyDown:()=>{},snapshotCombatMaybe:()=>{},v32RaiseAlarm:()=>{},spawnReinforcements:()=>{},zoneCombatState:()=>({alarm:0}),
  damages:[],v32DamagePlayer:(...args)=>c.damages.push(args),deck:{hacks:{},cyberdeck:{energy:73}},innerWidth:1280,innerHeight:720,
  document:{hidden:false,head:element('head'),body:element('body'),createElement:element,getElementById:()=>null,querySelectorAll:()=>[]},
  observation:{phase:'combat',suspicion:1,memoryRemaining:5,searchTarget:null,canAttack:false},
  __SOMA_PERCEPTION70__:{beginEnemyFrame:()=>{},observer:()=>c.observation,applied:()=>{}},
  __SOMA_V42__:{isCrouched:()=>false,state:()=>c.deck,canUseOnFoot:()=>true,isMachine:()=>false},
  __SOMA_V70__:{modifiers:()=>({scanActive:true})},v27IsCyber:()=>c.cyber};
 c.window=c;vm.createContext(c);vm.runInContext(scripts.runtime,c);
 vm.runInContext(scripts.v32.match(/const ARCHETYPES=\{[\s\S]*?\n\};/)[0],c);
 vm.runInContext(part(scripts.v32,'function enemyMove(q,tx,tz,speed,dt){','function v32RaiseAlarm('),c);
 vm.runInContext(part(scripts.v32,'function v32UpdateEnemies(dt){','\nlet snapshotClock=0;'),c);
 c.q=q;c.ally=ally;c.api=c.__SOMA_COMBAT_SUPPORT74__;
 c.tick=(n=1,dt=.1)=>{for(let i=0;i<n;i++)c.v32UpdateEnemies(dt);};return c;
}

test('the real v32 branch prepares, then applies exactly +18 and its original recovery; no player contact or energy needed',()=>{
 const c=context();c.playerBlocked=true;const before=plain(c.state),keys=Object.keys(c.q);
 c.tick();assert.equal(c.ally.health,50);assert.equal(c.q.attackClock,3.2);assert.equal(c.api.snapshot().activeChannels,1);
 c.tick(11);assert.equal(c.ally.health,50);c.tick();assert.equal(c.ally.health,68);assert.equal(c.q.attackClock,3.2);
 assert.deepEqual(plain(c.api.snapshot().counters),{started:1,completed:1,interrupted:0});
 assert.equal(c.damages.length,0);assert.deepEqual(plain(c.state),before);assert.equal(c.deck.cyberdeck.energy,73);
 assert.deepEqual(Object.keys(c.q),keys);assert.equal(c.api.snapshot().ephemeral,true);
 c.tick(10);assert.equal(c.ally.health,68);
 const capped=context();capped.ally.health=95;capped.tick(13);assert.equal(capped.ally.health,100);
});

test('triage skips distant, occluded, hostile, invalid and self candidates before choosing a real visible ally',()=>{
 const c=context();c.q.health=1;
 const far={...unit('far','rifle',100),health:1},enemy={...unit('enemy','rifle',1),health:2,v33Faction:'axis'};
 const occluded={...unit('hidden-by-wall','rifle',3),health:3},dead={...unit('dead','rifle',1),health:0};
 const invalid={...unit('invalid','rifle',1),health:4,maxHealth:NaN},boss={...unit('boss','rifle',1),health:4,v26BossId:'boss'};
 const disabled={...unit('disabled','rifle',1),health:4,disabled:true};
 const old=c.lineBlocked;c.lineBlocked=(...p)=>p[2]===3||old(...p);
 c.zone.robots=[c.q,far,enemy,occluded,dead,invalid,boss,disabled,c.ally];
 c.tick();assert.equal(c.api.snapshot().channels[0].allyId,c.ally.id);c.tick(12);
 assert.equal(c.ally.health,68);assert.equal(c.q.health,1);assert.equal(occluded.health,3);assert.equal(enemy.health,2);
});

test('triage uses remaining health fraction, reserves an ally per channel, and never heals at the 16m boundary',()=>{
 const c=context(),lessUrgent={...unit('less-urgent','rifle',3),health:20,maxHealth:25};
 c.zone.robots.push(lessUrgent);c.tick();assert.equal(c.api.snapshot().channels[0].allyId,c.ally.id);
 const second=unit('medic:2','medic',1);c.zone.robots.push(second);c.tick();
 assert.equal(c.api.snapshot().channels.find(row=>row.id===second.id).allyId,lessUrgent.id);
 const boundary=context();boundary.ally.x=16;boundary.tick(20);assert.equal(boundary.ally.health,50);assert.equal(boundary.api.snapshot().counters.started,0);
});

test('local faction precedence matches radio72, including squad fallback without overriding authored factions',()=>{
 for(const [medicFaction,allyFaction,medicSquad,allySquad,expected]of [
  [null,null,'a','a',1],[null,null,'a','b',0],['axis','axis','a','b',1],['axis','palimpseste','a','a',0]]){
  const c=context();c.q.v33Faction=medicFaction;c.ally.v33Faction=allyFaction;c.q.v33Squad=medicSquad;c.ally.v33Squad=allySquad;c.tick();
  assert.equal(c.api.snapshot().activeChannels,expected);
 }
});

test('real perception70 plus radio72 can downgrade player contact while the existing visible-ally preparation finishes without a shot',()=>{
 const c=context();c.ally.x=0;c.ally.z=12;c.ally.homeX=0;c.ally.homeZ=12;c.ally.health=52;c.ally.attackClock=999;
 c.q.state='patrol';c.q.detect=0;c.q.searchClock=0;c.q.attackClock=10;c.q.heading=Math.PI;
 c.__SOMA_V32__={archetypes:vm.runInContext('ARCHETYPES',c)};
 vm.runInContext(fs.readFileSync(path.resolve(__dirname,'../../src/v70/infiltration-core.js'),'utf8'),c);
 vm.runInContext(scripts.radio72,c);vm.runInContext(scripts.perception70,c);
 c.tick(10);assert.equal(c.__SOMA_PERCEPTION70__.observer(c.q.id).canAttack,true);
 c.q.attackClock=0;c.tick();assert.equal(c.api.snapshot().activeChannels,1);assert.equal(c.q.heading,0);
 c.tick();const radio=c.__SOMA_PERCEPTION70__.observer(c.q.id);
 assert.equal(radio.phase,'search');assert.equal(radio.reason,'radio-last-known');assert.equal(radio.canAttack,false);
 assert.equal(c.q.state,'search');assert.equal(c.api.snapshot().activeChannels,1);
 c.tick(11);assert.equal(c.ally.health,70);assert.equal(c.api.snapshot().counters.completed,1);
 assert.equal(c.api.snapshot().counters.interrupted,0);assert.equal(c.damages.length,0);assert.equal(c.state.health,100);
 c.playerBlocked=true;c.tick(40);assert.equal(c.api.snapshot().counters.started,1,'search without reacquiring player contact cannot start another preparation');assert.equal(c.ally.health,70);
 assert.equal(c.__SOMA_PERCEPTION70__.observer(c.q.id).canAttack,false);assert.equal(c.damages.length,0);
});

test('only an existing medic preparation can continue in search or patrol; all ally and disruption guards still apply',()=>{
 for(const phase of ['search','patrol']){
  const c=context();c.tick(4);c.observation.phase=phase==='patrol'?'unaware':'search';c.observation.canAttack=false;
  c.tick(9);assert.equal(c.ally.health,68);assert.equal(c.api.snapshot().counters.completed,1);assert.equal(c.damages.length,0);
  c.q.attackClock=0;c.tick();assert.equal(c.api.snapshot().activeChannels,0);assert.equal(c.api.snapshot().counters.started,1);
  for(const action of [d=>{d.blockAlly=true;},d=>{d.q.health-=1;},d=>{d.deck.hacks[d.zone.id]={[d.q.id]:{jam:2}};}]){
   const d=context();d.tick(4);d.observation.phase=phase==='patrol'?'unaware':'search';action(d);d.tick();
   assert.equal(d.ally.health,50);assert.equal(d.api.snapshot().activeChannels,0);assert.equal(d.api.snapshot().counters.interrupted,1);assert(d.q.attackClock>=3.09);
  }
 }
 const c=context();const outsider={...c.q,id:'not-medic',v32Role:'rifle'};assert.equal(c.api.isPreparing(outsider),false);
});

test('a hit interrupts, consumes recovery and cannot retarget or shoot in the same frame',()=>{
 const c=context();c.tick(4);c.q.health-=3;c.observation.canAttack=true;c.observation.searchTarget=[0,0];c.tick();
 assert.equal(c.ally.health,50);assert.equal(c.api.snapshot().activeChannels,0);assert.equal(c.api.snapshot().lastInterruption,'received-hit');
 assert(c.q.attackClock>=3.09);assert.equal(c.damages.filter(args=>args[2]===c.q).length,0);c.tick(10);assert.equal(c.ally.health,50);
 assert.equal(c.api.snapshot().counters.started,1);
});

test('lost ally LOS, range, identity, faction, health, membership or availability cancels without a partial heal',()=>{
 for(const action of [c=>{c.blockAlly=true;},c=>{c.ally.x=100;},c=>{c.ally.id='reused-id';},
  c=>{c.ally.v33Faction='axis';},c=>{c.q.v33Faction='axis';},c=>{c.ally.health=100;},c=>{c.ally.health=0;},
  c=>{c.ally.hidden=true;},c=>{c.ally.disabled=true;},c=>{c.ally.retire=true;},
  c=>{c.zone.robots=[c.q,{...c.ally}];},c=>{c.zone.robots=[c.ally];},c=>{c.q.id='new-medic-id';}]){
  const c=context();c.tick(4);action(c);const health=c.ally.health;c.tick();
  assert.equal(c.api.snapshot().activeChannels,0);assert.equal(c.api.snapshot().counters.interrupted,1);
  assert.equal(c.ally.health,health);assert(c.q.attackClock>=3.09);
 }
});

test('blind, jam and lock cancel preparation under the existing v42 effects owner',()=>{
 for(const effect of ['blind','jam','lock']){const c=context();c.tick(4);c.deck.hacks[c.zone.id]={[c.q.id]:{[effect]:2}};
  c.api.maintain();assert.equal(c.api.snapshot().activeChannels,0);assert.equal(c.q.attackClock,3.2);c.tick(15);assert.equal(c.ally.health,50);
 }
});

test('the real paused render loop cancels before its no-simulation return',()=>{
 const c=context();c.tick(4);c.paused=true;c.last=0;c.frameDebt=0;c.renderer={};c.requestAnimationFrame=()=>{};
 c.__SOMA_PERF65__={gate:{shouldRender:()=>false},stats:{simulationSteps:0}};c.currentWeather=()=>({});c.devicePixelRatio=1;
 vm.runInContext(scripts.loop,c);c.loop(1000);assert.equal(c.api.snapshot().activeChannels,0);assert.equal(c.ally.health,50);
 assert.equal(c.q.attackClock,3.2);c.paused=false;c.tick(10);assert.equal(c.api.snapshot().counters.started,1);
});

test('death, recovery, driving, hidden tab, cyberspace, zone and state replacement clear temporary preparations',()=>{
 for(const action of [c=>{c.state.health=0;},c=>{c.state.recovery={pending:true};},c=>{c.state.recoveryGrace=2;},
  c=>{c.state.driving='car';},c=>{c.document.hidden=true;},c=>{c.cyber=true;},c=>{c.zone={...c.zone};},
  c=>{c.zone.id='another-zone';},c=>{c.state={...c.state};},c=>{c.api.reset();}]){
  const c=context();c.tick(4);action(c);c.api.maintain();assert.equal(c.api.snapshot().activeChannels,0);
  assert.equal(c.ally.health,50);assert.equal(c.q.attackClock,3.2);
 }
 const c=context();c.tick(4);
 const reset=scripts.perception70.match(/reset:\(\)=>\{reset\(\);activeZone=zoneNow\(\);[\s\S]*?\}\}\);/)[0].slice('reset:'.length,-3);
 vm.runInContext('(function(){const root=window,reset=()=>{},zoneNow=()=>zone;let activeZone,activeZoneId;('+reset+')();})();',c);
 assert.equal(c.api.snapshot().activeChannels,0);assert.equal(c.q.attackClock,3.2);
});

test('NGF LOS uses two terrain body points, rejects unknown heights and ignores NPC animation and player camera altitude',()=>{
 const c=context();c.camera.y=901.72;c.q.y=50000;c.ally.y=-50000;const rays=[];
 c.__SOMA_SIGHT61__={activeFor:()=>true,eyePoint:(x,z,zone,h)=>[x,100+h,z],between:(a,b,zone)=>{rays.push([plain(a),plain(b),zone.id]);return false;}};
 c.tick(13);assert.equal(c.ally.health,68);assert(rays.length>0);assert(rays.every(([a,b,z])=>a[1]===101.45&&b[1]===101.45&&z==='qa-zone'));
 for(const sight of [
  {activeFor:()=>true,eyePoint:()=>null,between:()=>false},
  {activeFor:()=>true,eyePoint:(x,z)=>[x,101.45,z]},
  {activeFor:()=>true,eyePoint:(x,z)=>[x,NaN,z],between:()=>false},
  {activeFor:()=>true,eyePoint:(x,z)=>[x,101.45,z],between:()=>true}]){
  const d=context();d.__SOMA_SIGHT61__=sight;d.tick(20);assert.equal(d.ally.health,50);assert.equal(d.api.snapshot().activeChannels,0);
 }
});

test('Écho73 reads the actual preparation and counterplay only for its visible bodies',()=>{
 const c=context();vm.runInContext(scripts.echo,c);c.tick(4);const echo=c.__SOMA_TACTICAL73__;
 const row=echo.scanTargets().find(row=>row.id===c.q.id);assert.match(row.roleLabel,/Reprise médicale · 25 %/);assert.match(row.hint,/Touchez le médecin/);
 c.camera.yaw=Math.PI;assert.equal(echo.scanTargets().length,0);c.camera.yaw=0;c.playerBlocked=true;
 assert.equal(echo.scanTargets().length,0);assert.equal(c.api.snapshot().activeChannels,1);
 c.playerBlocked=false;c.q.health-=1;c.api.maintain();assert.match(echo.scanTargets().find(row=>row.id===c.q.id).roleLabel,/Soutien médical/);
});

test('frame selection, line checks and active state remain bounded, with no large-delta shortcut or boss/ICE channel',()=>{
 const c=context();c.tick();c.tick(1,100);assert.equal(c.ally.health,50);assert.equal(c.api.snapshot().channels[0].progress,.25/1.2);
 const budget=context();budget.ally.health=100;for(let i=0;i<150;i++)budget.zone.robots.push(unit('medic:'+i,'medic',i/20));
 budget.tick();assert.equal(budget.api.snapshot().selectionChecks,1024);assert(budget.api.snapshot().selectionLines<=128);assert.equal(budget.api.snapshot().activeChannels,0);
 const lineBudget=context();lineBudget.zone.robots=[];
 for(let i=0;i<3;i++)lineBudget.zone.robots.push(unit('m:'+i,'medic',0));
 for(let i=0;i<100;i++)lineBudget.zone.robots.push({...unit('a:'+i,'rifle',2+i/100),health:10});
 lineBudget.tick();assert.equal(lineBudget.api.snapshot().selectionLines,128);
 const candidates=context();candidates.zone.robots=[candidates.q];
 for(let i=0;i<127;i++)candidates.zone.robots.push(unit('full:'+i,'rifle',2));candidates.zone.robots.push(candidates.ally);
 candidates.tick();assert.equal(candidates.api.snapshot().selectionChecks,128);assert.equal(candidates.api.snapshot().activeChannels,0);
 const cap=context();cap.zone.robots=[];const medics=[];
 for(let i=0;i<40;i++){const q=unit('m:'+i,'medic',0);medics.push(q);cap.zone.robots.push(q,{...unit('a:'+i,'rifle',2),health:10});}
 for(const q of medics){cap.api.beginEnemyFrame();cap.api.advance(q,.1);}
 assert.equal(cap.api.snapshot().activeChannels,32);
 for(const change of [q=>{q.v26BossId='boss';},q=>{q.v27ICE=true;},q=>{q.id='owned36';}]){
  const d=context();d.__SOMA_BOSSES36__={handles:q=>q.id==='owned36',suspended:()=>false};change(d.q);d.tick(15);
  assert.equal(d.api.snapshot().counters.started,0);
 }
});

test('the actual v33 enemy serializer preserves paid recovery and omits temporary channel state across roster restore',()=>{
 const c=context();c.tick(4);c.q.health-=2;c.api.maintain();
 vm.runInContext(part(scripts.v33,'function serializeEnemy(q){','function snapshotTerritoryRuntime('),c);
 vm.runInContext(part(scripts.v33,'function restoreRoster(z,t){','function safeEnemyPoint('),c);
 c.finite=n=>Number.isFinite(n)?n:0;c.safeEnemyPoint=(z,q)=>q;
 const saved=c.serializeEnemy(c.q);assert.equal(saved.attackClock,3.2);assert(!Object.keys(saved).some(k=>/support74|channel|elapsed/i.test(k)));
 c.restoreRoster(c.zone,{roster:{[saved.id]:saved}});c.api.maintain();assert.equal(c.zone.robots[0].attackClock,3.2);
 assert.equal(c.api.snapshot().activeChannels,0);assert(!Object.hasOwn(c.state,'v74'));
});

test('real floor snapshot32 and restoreEnemy retain paid preparation as cooldown, accept legacy records and preserve long cover-fire recovery',()=>{
 const c=context();c.tick(4);assert(c.q.attackClock<3.2);
 c.record={enemies:{}};c.zoneCombatState=()=>c.record;c.save32=()=>{};
 vm.runInContext(part(scripts.v32,'function snapshotCombat(){','function redZoneState('),c);
 vm.runInContext(part(scripts.v32,'function restoreEnemy(q,zoneId=zone?.id){','function snapshotCombat(){'),c);
 vm.runInContext(part(scripts.v33,'function serializeEnemy(q){','function snapshotTerritoryRuntime('),c);
 c.finite=n=>Number.isFinite(n)?n:0;c.snapshotCombat();
 const saved=plain(c.record.enemies[c.q.id]);assert.equal(saved.attackClock,3.2);assert.equal(c.serializeEnemy(c.q).attackClock,3.2);
 assert(c.q.attackClock<3.2);assert(!Object.keys(saved).some(k=>/channel|elapsed|support74/i.test(k)));
 const restored={...c.q,attackClock:.4};c.api.reset();c.restoreEnemy(restored);assert.equal(restored.attackClock,3.2);
 c.zone.robots=[restored,c.ally];c.tick(10);assert.equal(c.ally.health,50);assert.equal(c.api.snapshot().activeChannels,0);
 delete c.record.enemies[c.q.id].attackClock;const legacy={...c.q,attackClock:.4};c.restoreEnemy(legacy);assert.equal(legacy.attackClock,.4);
 c.q.attackClock=18;c.zone.robots=[c.q,c.ally];c.snapshotCombat();assert.equal(c.record.enemies[c.q.id].attackClock,18);
 assert.equal(c.serializeEnemy(c.q).attackClock,18);const long={...c.q,attackClock:.4};c.restoreEnemy(long);assert.equal(long.attackClock,18);
});

test('actual layer32 validator rejects malformed optional recovery while keeping old enemy records valid',()=>{
 const c=context();
 Object.assign(c,{record:()=>{},api:()=>({freshState:()=>({})}),validateShape:()=>{},set:()=>new Set(),knownKeys:()=>{},
  enumOf:()=>{},member:()=>{},enemyIdKnown:()=>true,fail:(...args)=>{throw Error(args.join(':'));},
  number:(n,min,max,label)=>{if(typeof n!=='number'||!Number.isFinite(n)||n<min||n>max)throw Error(label);}});
 vm.runInContext(part(scripts.persistence,'function validateLayer(v,q,k){','function validate('),c);
 const k={districts:new Set(),roles:new Set(['medic']),zones:new Set([c.zone.id])};
 const layer={schema:32,gigs:{},followingGig:null,redZones:{},combat:{kills:{}},zoneCombat:{[c.zone.id]:{enemies:{[c.q.id]:{health:88,state:'combat'}}}},loot:{}};
 assert.doesNotThrow(()=>c.validateLayer(32,layer,k));
 for(const cooldown of [0,3.2,18,3600]){layer.zoneCombat[c.zone.id].enemies[c.q.id].attackClock=cooldown;assert.doesNotThrow(()=>c.validateLayer(32,layer,k));}
 for(const cooldown of [-1,3601,Infinity,NaN,'3.2',null]){layer.zoneCombat[c.zone.id].enemies[c.q.id].attackClock=cooldown;assert.throws(()=>c.validateLayer(32,layer,k),/Recharge ennemie/);}
});
