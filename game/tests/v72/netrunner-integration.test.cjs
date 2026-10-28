'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm');
const scripts=require('./netrunner-fixture.cjs');
const part=(text,start,end)=>{assert.equal(text.split(start).length,2);return text.slice(text.indexOf(start),text.indexOf(end,text.indexOf(start)));};
const plain=x=>JSON.parse(JSON.stringify(x));
function element(tag){return {tag,children:[],hidden:false,textContent:'',attrs:{},setAttribute(k,v){this.attrs[k]=v;},appendChild(x){this.children.push(x);return x;},replaceChildren(){this.children=[];}};}
function context(){
 const q={id:'runner:1',v32Enemy:true,v32Role:'netrunner',v32Label:'Tisseur QA',kind:'v32',health:82,maxHealth:82,armor:.06,
  x:0,z:10,homeX:0,homeZ:10,heading:Math.PI,state:'combat',detect:1,searchClock:5,attackClock:0,patrolIndex:0};
 const a={vision:31,hearing:24,speed:.78,range:27,damage:0,cooldown:3.6};
 const c={Math,Map,Set,Object,JSON,Number,String,performance:{now:()=>1000},camera:{x:0,z:0,y:1.72,yaw:0,pitch:0},
  state:{health:100,armor:30,tension:0,settings:{volume:0,reduceMotion:true,largeText:true,highContrast:true,fov:67},statistics:{shots:0}},
  zone:{id:'qa-zone',robots:[q],v32CoverPoints:[]},keys:new Set(),paused:false,
  S:{status:{jammed:0,suppressed:0},combat:{headshots:0},lastShotAt:-999},ARCHETYPES:{netrunner:a,rifle:a},
  blocked:()=>false,blockSight:false,lineBlocked:()=>c.blockSight,headingVec:h=>({x:Math.sin(h),z:Math.cos(h)}),
  clamp:(n,a,b)=>Math.max(a,Math.min(b,n)),onEnemyDown:()=>{},snapshotCombatMaybe:()=>{},snapshotCombat:()=>{},save32:()=>{},
  announcements:[],announce:(...args)=>c.announcements.push(args),v32RaiseAlarm:()=>{},spawnReinforcements:()=>{},zoneCombatState:()=>({alarm:0,alarmDisabled:false}),
  damages:[],v32DamagePlayer:(...args)=>c.damages.push(args),deck:{hacks:{},cyberdeck:{energy:73}},innerWidth:1200,innerHeight:800,
  document:{hidden:false,head:element('head'),body:element('body'),createElement:element},
  observation:{phase:'combat',suspicion:1,memoryRemaining:5,searchTarget:[0,0],canAttack:true},
  __SOMA_PERCEPTION70__:{beginEnemyFrame:()=>{},observer:()=>c.observation,applied:()=>{},recordShot:()=>{}},
  __SOMA_V42__:{isCrouched:()=>false,state:()=>c.deck},v27IsCyber:()=>false};
 c.window=c;vm.createContext(c);vm.runInContext(scripts.runtime,c);
 vm.runInContext(part(scripts.v32,'function enemyMove(q,tx,tz,speed,dt){','function v32RaiseAlarm('),c);
 vm.runInContext(part(scripts.v32,'function v32UpdateEnemies(dt){','\nlet snapshotClock=0;'),c);
 c.q=q;c.a=a;c.api=c.__SOMA_NETRUNNER72__;c.tick=(n=1,dt=.1)=>{for(let i=0;i<n;i++)c.v32UpdateEnemies(dt);};
 return c;
}
function hud(c){return c.document.body.children.find(x=>x.id==='v72-netrunner-hud');}

test('real v32 prepares visibly then applies its original intrusion exactly once with original cooldown',()=>{
 const c=context(),start=plain(c.state);c.tick();
 assert.equal(c.state.tension,0);assert.equal(c.S.status.jammed,0);assert.equal(c.api.snapshot().activeChannels,1);
 assert.equal(c.api.snapshotHUD().telegraphs[0].progress,0);assert.equal(hud(c).hidden,false);
 c.tick(5);const progress=c.api.snapshotHUD().telegraphs[0].progress;assert(progress>.4&&progress<.5);
 const meter=hud(c).children.find(x=>x.tag==='meter');assert.equal(meter.value,progress);assert.equal(meter.attrs['aria-label'],'Préparation de l’intrusion neurale');
 c.tick(6);assert.equal(c.state.tension,9);assert.equal(c.S.status.jammed,2.8);assert.equal(c.q.attackClock,3.6);
 c.tick();assert.equal(c.state.tension,9);assert.equal(c.api.snapshot().counters.completed,1);assert.equal(hud(c).hidden,true);
 assert.equal(c.state.health,start.health);assert.equal(c.state.armor,start.armor);assert.equal(c.deck.cyberdeck.energy,73);assert.equal(c.damages.length,0);
 assert.equal(c.announcements.filter(x=>x[0]==='INTRUSION NEURALE · arme perturbée').length,1);
 assert.equal(hud(c).attrs.role,'status');assert.equal(hud(c).attrs['aria-live'],'polite');
 assert(c.document.head.children[0].textContent.includes('.body-large-text'));
});

test('real accepted-shot wrapper interrupts only a received hit, with no impact or cooldown refund',()=>{
 const c=context();c.acceptShot=true;c.hit=false;
 c.shoot=()=>{if(c.acceptShot){c.state.statistics.shots++;if(c.hit)c.q.health-=4;}};
 vm.runInContext(part(scripts.v32,'const baseShoot=shoot;','const baseLootDynamicGeo='),c);
 c.tick();c.shoot();c.tick(3);assert.equal(c.api.snapshot().activeChannels,1,'accepted miss is not an interrupt');
 c.hit=true;c.shoot();c.tick();assert.equal(c.api.snapshot().activeChannels,0);assert.equal(c.api.snapshot().lastInterruption,'received-hit');
 assert.equal(c.state.tension,0);assert.equal(c.S.status.jammed,0);assert(c.q.attackClock>=3.4);
 c.tick(10);assert.equal(c.api.snapshot().counters.started,1);assert.equal(c.state.tension,0);
});

test('existing v33 arm damage factors still determine completion and interruption recovery',()=>{
 const c=context();c.q.v33AttackFactor=.6;c.tick(12);assert.equal(c.q.attackClock,6);assert.equal(c.state.tension,9);
 const hit=context();hit.tick(4);hit.q.health-=3;hit.q.v33AttackFactor=.6;hit.tick();assert(hit.q.attackClock>=5.8);
 assert.equal(hit.state.tension,0);assert.equal(hit.api.snapshot().lastInterruption,'received-hit');
});

test('losing true LOS interrupts and reacquiring it cannot start a ready attack for free',()=>{
 const c=context();c.tick(4);c.blockSight=true;c.observation.canAttack=false;c.tick();
 assert.equal(c.api.snapshot().activeChannels,0);assert.equal(c.api.snapshotHUD().visibleChannels,0);assert.equal(hud(c).hidden,true);
 assert(c.q.attackClock>=3.4);c.blockSight=false;c.observation.canAttack=true;c.tick(10);
 assert.equal(c.api.snapshot().counters.started,1);assert.equal(c.state.tension,0);
});

test('looking away hides the visible warning while an unobstructed hostile channel continues',()=>{
 const c=context();c.tick(4);c.camera.yaw=Math.PI;c.api.maintain();
 const hidden=c.api.snapshot();assert.equal(hidden.activeChannels,1);assert.equal(hidden.hud.visibleChannels,0);assert.deepEqual(plain(hidden.hud.telegraphs),[]);
 assert.equal(hud(c).hidden,true);assert(!JSON.stringify(hidden).includes('Tisseur QA'));
 c.camera.yaw=0;c.api.maintain();assert.equal(c.api.snapshotHUD().visibleChannels,1);assert.equal(hud(c).hidden,false);
 c.camera.pitch=1.2;c.api.maintain();assert.equal(c.api.snapshotHUD().visibleChannels,0);
});

test('NGF terrain height and the real positive-yaw/positive-pitch camera convention keep visible units in the HUD',()=>{
 const c=context();c.camera.y=101.72;
 c.__SOMA_SIGHT61__={activeFor:()=>true,eyePoint:(x,z,zone,height=1.65)=>[x,100+height,z]};
 c.tick(4);assert.equal(c.api.snapshotHUD().visibleChannels,1);assert.equal(hud(c).hidden,false);
 c.q.x=10;c.q.z=0;c.camera.yaw=Math.PI/2;c.tick();assert.equal(c.api.snapshotHUD().visibleChannels,1);
 c.camera.yaw=-Math.PI/2;c.api.maintain();assert.equal(c.api.snapshotHUD().visibleChannels,0);
 c.camera.yaw=Math.PI/2;c.camera.y=91.45;c.camera.pitch=Math.PI/4;c.api.maintain();assert.equal(c.api.snapshotHUD().visibleChannels,1);
 c.camera.pitch=-Math.PI/4;c.api.maintain();assert.equal(c.api.snapshotHUD().visibleChannels,0);
 c.__SOMA_SIGHT61__.eyePoint=()=>null;c.api.maintain();assert.equal(c.api.snapshotHUD().visibleChannels,0);
});

test('unknown LOS terrain, blind/jam effects, removed units and out-of-range channels cannot impact',()=>{
 for(const action of [c=>{c.__SOMA_SIGHT61__={activeFor:()=>true,eyePoint:()=>null};},
  c=>{c.deck.hacks[c.zone.id]={[c.q.id]:{jam:2}};},c=>{c.deck.hacks[c.zone.id]={[c.q.id]:{blind:2}};},
  c=>{c.zone.robots=[];},c=>{c.camera.z=-100;}]){
  const c=context();c.tick(5);action(c);c.api.maintain();c.tick(20);
  assert.equal(c.api.snapshot().activeChannels,0);assert.equal(c.state.tension,0);assert.equal(c.S.status.jammed,0);
 }
});

test('the real paused render loop clears charges before its no-simulation branch',()=>{
 const c=context();c.tick(4);c.paused=true;c.last=0;c.frameDebt=0;c.renderer={};c.requestAnimationFrame=()=>{};
 c.__SOMA_PERF65__={gate:{shouldRender:()=>false},stats:{simulationSteps:0}};
 c.currentWeather=()=>({});c.innerWidth=1200;c.innerHeight=800;c.devicePixelRatio=1;
 vm.runInContext(scripts.loop,c);c.loop(1000);
 assert.equal(c.api.snapshot().activeChannels,0);assert.equal(c.state.tension,0);assert.equal(hud(c).hidden,true);
 c.paused=false;c.tick(5);assert.equal(c.api.snapshot().counters.started,1);
});

test('death, recovery, zone replacement, same-object zone ID, state import and explicit import reset clear transient channels',()=>{
 for(const action of [c=>{c.state.health=0;},c=>{c.state.recovery={pending:true};},c=>{c.state.driving='car';},
  c=>{c.zone={...c.zone};},c=>{c.zone.id='other';},c=>{c.state={...c.state};},c=>{c.api.reset();}]){
  const c=context();c.tick(5);action(c);c.api.maintain();assert.equal(c.api.snapshot().activeChannels,0);assert.equal(c.state.tension,0);
 }
 assert(scripts.perception70.includes('root.__SOMA_LEGACY_PERCEPTION71__?.reset?.();root.__SOMA_NETRUNNER72__?.reset?.();'));
});

test('bounded state and large deltas never shortcut charge; boss and ICE owners remain outside channels',()=>{
 const c=context();c.tick();c.tick(1,20);assert.equal(c.state.tension,0);assert.equal(c.api.snapshotHUD().telegraphs[0].progress,.25/1.1);
 for(let i=0;i<100;i++){const q={...c.q,id:'runner:'+i,attackClock:0};c.zone.robots.push(q);c.api.advance(q,c.a,.1,true);}
 assert.equal(c.api.snapshot().activeChannels,c.api.config.maxChannels);assert.equal(c.api.snapshot().maxChannels,64);
 assert(!Object.keys(c.q).some(k=>/channel|netrunner72/i.test(k)));
 for(const type of ['boss','ice']){const d=context();if(type==='boss')d.q.v26BossId='boss26';else d.q.v27ICE=true;d.tick(20);assert.equal(d.api.snapshot().counters.started,0);}
});

test('original v42 still classifies netrunners as human and does not provide them machine quickhacks',()=>{
 const c=context();vm.runInContext(part(scripts.v42,'function v42Machine(q){','function v42Effects(q){'),c);
 c.V42_HUMAN_ROLES=new Set(['rifle','melee','sniper','netrunner']);assert.equal(c.v42Machine(c.q),false);assert.equal(c.v42Supports(c.q,'jam'),false);
});
