'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const game=path.resolve(__dirname,'../..'),scripts=require('./real-gameplay-fixture.cjs');
const core=fs.readFileSync(path.join(game,'src/v70/infiltration-core.js'),'utf8'),runtime=fs.readFileSync(path.join(game,'src/v70/perception-runtime.js'),'utf8');
const part=(text,start,end)=>{assert.equal(text.split(start).length,2);return text.slice(text.indexOf(start),text.indexOf(end,text.indexOf(start)));};
const plain=value=>JSON.parse(JSON.stringify(value));

function context(){
  const q={id:'guard:1',v32Enemy:true,v32Role:'blade',kind:'v32',health:100,maxHealth:100,x:0,z:0,homeX:0,homeZ:0,
    heading:0,state:'patrol',detect:0,searchClock:0,attackClock:0,patrolIndex:0,v33Squad:'squad:1'};
  const archetypes={rifle:{vision:30,hearing:40,speed:2,range:30,damage:9,cooldown:1},blade:{vision:30,hearing:40,speed:2,range:2,damage:9,cooldown:1}};
  const c={Math,Map,Set,Object,JSON,Number,String,performance:{now:()=>1000},camera:{x:0,z:10,y:1.72,yaw:0,pitch:0},
    state:{health:100,armor:0,weapon:0,settings:{volume:0},statistics:{shots:0}},zone:{id:'qa-zone',robots:[q],v32CoverPoints:[]},keys:new Set(),paused:false,
    S:{status:{jammed:0,suppressed:0},combat:{headshots:0},lastShotAt:-999},ARCHETYPES:archetypes,
    blocked:()=>false,blockSight:false,lineBlocked:()=>c.blockSight,headingVec:h=>({x:Math.sin(h),z:Math.cos(h)}),
    clamp:(n,a,b)=>Math.max(a,Math.min(b,n)),onEnemyDown:()=>{},snapshotCombatMaybe:()=>{},snapshotCombat:()=>{},save32:()=>{},
    alarms:[],v32RaiseAlarm:reason=>c.alarms.push(reason),spawnReinforcements:()=>{},zoneCombatState:()=>({alarm:0,alarmDisabled:false}),
    damage:[],v32DamagePlayer:(amount,label)=>c.damage.push([amount,label]),announce:()=>{},v27Stats:()=>({noiseMult:c.noiseMult??1}),
    WEAPONS:[{kind:'fusil',damage:20}],crouched:false,deck:{hacks:{}},
    __SOMA_V32__:{archetypes},__SOMA_V42__:{isCrouched:()=>c.crouched,canUseOnFoot:()=>!c.state.driving,
      isMachine:q=>q.v32Role==='drone'||q.v42Camera,state:()=>c.deck}};
  c.window=c;vm.createContext(c);vm.runInContext(core,c);vm.runInContext(runtime,c);
  vm.runInContext(part(scripts['soma-v32-patch'],'function enemyMove(q,tx,tz,speed,dt){','function v32RaiseAlarm('),c);
  vm.runInContext(part(scripts['soma-v32-patch'],'function v32UpdateEnemies(dt){','\nlet snapshotClock=0;'),c);
  return c;
}

test('real patched v32 follows remembered contact and cannot attack the hidden player',()=>{
  const c=context();for(let i=0;i<4;i++)c.v32UpdateEnemies(.25);
  assert.equal(c.zone.robots[0].state,'combat');
  c.blockSight=true;c.camera.z=-10;c.zone.robots[0].x=0;c.zone.robots[0].z=0;c.zone.robots[0].attackClock=0;
  const count=c.damage.length;c.v32UpdateEnemies(.25);
  assert(c.zone.robots[0].z>0,'movement must face the remembered +z contact, not the hidden player at -z');
  assert.equal(c.damage.length,count);
  assert.deepEqual(plain(c.__SOMA_PERCEPTION70__.observer('guard:1').lastKnown),[0,10]);
});

test('C-toggle posture is used with no Ctrl key and unknown LOS61 terrain stops tracking',()=>{
  const c=context();c.crouched=true;c.camera.z=21;c.v32UpdateEnemies(.25);
  assert.equal(c.__SOMA_PERCEPTION70__.observer('guard:1').canTrackCurrent,false);
  c.crouched=false;c.v32UpdateEnemies(.25);assert.equal(c.__SOMA_PERCEPTION70__.observer('guard:1').canTrackCurrent,true);
  const u=context();u.__SOMA_SIGHT61__={activeFor:()=>true,eyePoint:()=>null};u.v32UpdateEnemies(.25);
  assert.equal(u.__SOMA_PERCEPTION70__.observer('guard:1').reason,'unknown-line-of-sight');
  assert.equal(u.__SOMA_PERCEPTION70__.observer('guard:1').canAttack,false);
});

test('real v32 accepted-shot wrapper stores an emission once and ignores refused fire',()=>{
  const c=context();c.blockSight=true;c.camera.z=8;c.acceptShot=false;
  c.shoot=()=>{if(c.acceptShot)c.state.statistics.shots++;};
  vm.runInContext(part(scripts['soma-v32-patch'],'const baseShoot=shoot;','const baseLootDynamicGeo='),c);
  c.shoot();c.v32UpdateEnemies(.25);assert.equal(c.__SOMA_PERCEPTION70__.snapshot().activeSounds,0);
  c.acceptShot=true;c.shoot();c.camera.x=100;c.camera.z=100;c.v32UpdateEnemies(.25);
  assert.deepEqual(plain(c.__SOMA_PERCEPTION70__.observer('guard:1').lastKnown),[0,8]);
});

test('physical footsteps remain audible to guards when restitution volume is zero',()=>{
  const c=context();c.blockSight=true;c.camera.x=0;c.camera.z=0;c.zone.robots[0].z=-5;c.v32UpdateEnemies(.25);
  c.camera.x=2;c.v32UpdateEnemies(.25);
  const row=c.__SOMA_PERCEPTION70__.observer('guard:1');
  assert.equal(row.heard,true);assert.equal(row.lastSense,'sound');assert.equal(c.state.settings.volume,0);
  assert.deepEqual(plain(row.lastKnown),[2,0]);assert.equal(row.phase,'search');
  const exported=c.__SOMA_PERCEPTION70__.snapshot();assert(exported.hud.signature.level>0);
  assert.equal(exported.hud.suspicion,row.suspicion);exported.hud.signature.level=999;
  assert(c.__SOMA_PERCEPTION70__.snapshotHUD().signature.level<=1);
});

test('a foreign squad alarm keeps readiness without manufacturing a player location',()=>{
  const c=context();c.blockSight=true;c.camera.z=100;c.v32UpdateEnemies(.25);
  const q=c.zone.robots[0];q.state='combat';q.detect=1;q.searchClock=6;c.v32UpdateEnemies(.25);
  const row=c.__SOMA_PERCEPTION70__.observer(q.id);
  assert.equal(q.state,'combat');assert.equal(row.reason,'external-alert-without-location');
  assert.equal(row.searchTarget,null);assert.equal(row.canAttack,false);assert.equal(q.z,0);
});

test('real CCTV alert shares only the position actually seen before the player moved',()=>{
  const c=context();const q=c.zone.robots[0];q.heading=Math.PI;
  c.camera.z=6;c.zone.v42Complex='qa';c.zone.robots.push({id:'camera:1',v42Camera:true,kind:'security',health:55,x:0,z:0,heading:0});
  c.v42Dist=(a,b)=>Math.hypot(a.x-b.x,a.z-b.z);c.v42Effects=()=>null;c.v42VehicleBlocks=()=>false;
  vm.runInContext(part(scripts['soma-v42-recovery'],'let v42SecurityClock=0;','function v42Ambience()'),c);
  c.v42TickSecurity(.9);assert.equal(q.state,'combat');
  c.blockSight=true;c.camera.x=100;c.camera.z=100;c.v32UpdateEnemies(.25);
  assert.deepEqual(plain(c.__SOMA_PERCEPTION70__.observer(q.id).searchTarget),[0,6]);
});

test('real v33 cover selection uses a remembered point and never a hidden camera position',()=>{
  const c=context();for(let i=0;i<4;i++)c.v32UpdateEnemies(.25);c.blockSight=true;c.camera.x=-100;c.camera.z=-100;c.v32UpdateEnemies(.25);
  c.zone.v32CoverPoints=[{x:10,z:10}];c.coverCandidates=p=>[p];const targets=[];
  c.lineBlocked=(x,z,tx,tz)=>{targets.push([tx,tz]);return true;};
  vm.runInContext(part(scripts['soma-v33-patch'],'function chooseCover(q,order,reserved){','\nfunction assignTactics(){'),c);
  c.chooseCover(c.zone.robots[0],'cover',new Set());assert(targets.length>0);
  assert(targets.every(p=>p[0]===0&&p[1]===10));
});

test('sharing an old squad contact does not restart its memory lifetime',()=>{
  const c=context();for(let i=0;i<4;i++)c.v32UpdateEnemies(.25);c.blockSight=true;
  for(let i=0;i<10;i++)c.v32UpdateEnemies(.25);
  const old=c.__SOMA_PERCEPTION70__.observer('guard:1').memoryRemaining;
  c.zone.robots.push({...c.zone.robots[0],id:'guard:2',x:-5,state:'combat',detect:1,searchClock:6});
  c.v32UpdateEnemies(.25);
  assert(c.__SOMA_PERCEPTION70__.observer('guard:2').memoryRemaining<=old-.25+1e-8);
});

function v42Context(){
  const c=context();c.zone.robots=[{id:'drone:1',kind:'security',v32Role:'drone',health:100,x:0,z:10,heading:0}];c.camera.z=0;
  c.WORLD={zones:{}};c.v27IsCyber=()=>false;c.localStorage={getItem:()=>null,setItem:()=>{}};c.__SOMA__={};
  c.__SOMA_V70__={blocksHacking:()=>!!c.blockAugments};
  const text=scripts['soma-v42-recovery'];
  const api=text.match(/window\.__SOMA_V42__=(\{version:V42_VERSION[\s\S]*?\});window\.__SOMA__\.version/)[1];
  const altered=text.replace('\nv42Setup();\n})();','\nwindow.__SOMA_V42__='+api+';\n})();');
  assert.notEqual(altered,text);vm.runInContext(altered,c);return c;
}

test('real v42 exposes the real channel, an immutable copy, and its sole resource debit',()=>{
  const c=v42Context(),api=c.__SOMA_V42__;
  assert.equal(api.canUseOnFoot(),true);assert.equal(api.isChanneling(),false);assert.equal(api.channelStatus(),null);
  assert.equal(api.beginHack('blind'),true);assert.equal(api.isChanneling(),true);
  const status=api.channelStatus();assert(Object.isFrozen(status));assert.equal(status.type,'hack');assert.equal(status.program,'blind');
  assert.throws(()=>{status.elapsed=999;},TypeError);assert.equal(api.channelStatus().elapsed,0);
  assert.equal(api.debitEnergy(9),true);assert.equal(api.state().cyberdeck.energy,91);
  assert.equal(api.debitEnergy(-1),false);assert.equal(api.debitEnergy(1000),false);assert.equal(api.state().cyberdeck.energy,91);
});

test('barrier/focus hook blocks a new real v42 channel while an inactive hook allows it',()=>{
  const c=v42Context();c.blockAugments=true;assert.equal(c.__SOMA_V42__.beginHack('blind'),false);
  assert.equal(c.__SOMA_V42__.state().cyberdeck.energy,100);c.blockAugments=false;
  assert.equal(c.__SOMA_V42__.beginHack('blind'),true);
});

test('real v62 and group64 conditions consult the live channel rather than a missing saved field',()=>{
  const c=v42Context();c.busy=false;c.real=()=>true;c.hostile=()=>false;c.damageFlash=0;c.lastHealth=null;c.lastDanger=-1e9;
  c.reloadLeft=0;c.sourceValid=()=>true;c.K={refusal:row=>row};c.S={discovered:{poi:true}};
  vm.runInContext(part(scripts['soma-v62-runtime'],'function conditions(p,includeBusy=true){','\nfunction probeDiscover('),c);
  assert.equal(c.conditions({id:'poi'}).mission,false);c.__SOMA_V42__.beginHack('blind');
  assert.equal(c.conditions({id:'poi'}).mission,true);
  c.ready=true;c.E=()=>({summary:()=>({busy:false})});c.api=n=>c['__SOMA_V'+n+'__'];
  vm.runInContext(part(scripts['soma-v64-group-runtime'],'function refusal(){','\nfunction capture(){'),c);
  assert.match(c.refusal(),/action en cours/);
});

test('real v43 recoil kick and visual recoil use focus modifier without changing ballistic spread',()=>{
  function run(modifier,reduceMotion=false){
    const c=context();c.state.settings.reduceMotion=reduceMotion;c.state.statistics.hits=0;c.state.statistics.robotsDisabled=0;
    c.V43={gun:{shots:0,hits:0,streak:0,downs:0}};c.v43Save=()=>{};c.recoil=1;c.v43ShotPattern=0;c.v43HitTimer=0;c.v43DownTimer=0;
    c.__SOMA_V70__={modifiers:()=>({recoil:modifier})};c.shoot=()=>{c.state.statistics.shots++;};
    vm.runInContext(part(scripts['soma-v43-production'],'function v43InstallGunplay(){','\nfunction v43InstallEconomy(){'),c);
    c.v43InstallGunplay();c.shoot();return{pitch:c.camera.pitch,recoil:c.recoil};
  }
  const ordinary=run(1),focused=run(.6),reduced=run(.6,true);
  assert(Math.abs(focused.pitch/ordinary.pitch-.6)<1e-10);assert.equal(focused.recoil,.6);assert.equal(reduced.pitch,0);
});

test('the actual main update advances augments once before movement per simulation frame',()=>{
  const c=context(),calls=[];
  Object.assign(c,{move:()=>calls.push('move'),updateAI:()=>{},updatePolice:()=>{},updateNightlife:()=>{},ambientClock:0,barkTimer:0,
    weatherClock:0,fireCD:0,recoil:0,muzzle:0,reloadLeft:0,noticeTimer:0,damageFlash:0,saveClock:0,hash:()=>0,nearest:()=>null,
    $:()=>({classList:{remove:()=>{}}}),touches:new Set(),updateHUD:()=>calls.push('hud')});
  c.state.time=0;c.state.tension=0;c.state.memory=100;c.__SOMA_V70__={tick:dt=>calls.push('tick:'+dt)};
  vm.runInContext(scripts['qa-real-update'],c);c.update(.1);c.update(.05);
  assert.deepEqual(calls,['tick:0.1','move','hud','tick:0.05','move','hud']);
});
