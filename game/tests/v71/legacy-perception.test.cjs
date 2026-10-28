'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const scripts=require('./legacy-fixture.cjs'),game=path.resolve(__dirname,'../..');
const core=fs.readFileSync(path.join(game,'src/v70/infiltration-core.js'),'utf8');
const plain=v=>JSON.parse(JSON.stringify(v));
function context(){
 const c={Math,Map,Set,Object,JSON,Number,String,performance:{now:()=>1000},paused:false,
  camera:{x:0,z:10,yaw:0},state:{health:100,armor:0,driving:null,tension:0,recoveryGrace:0,weapon:0,
   police:{level:4,heat:80,lastCrimeAt:1000,dispatchTick:0,compliance:0},statistics:{shots:0},settings:{volume:0}},
  zone:{id:'legacy-qa',district:'port',actors:[],animals:[],robots:[],vehicles:[],sidewalks:[],vehicleRoutes:[],airRoutes:[],waterRoutes:[],roadblocks:[]},
  keys:new Set(),rng:()=>()=>1,hash:()=>0,clamp:(n,a,b)=>Math.max(a,Math.min(b,n)),
  moveToward:(a,b,dt)=>a<b?Math.min(a+dt,b):Math.max(a-dt,b),blocked:()=>false,onRoad:()=>true,
  pedestrianVehicleClear:()=>true,blockSight:false,lineBlocked:()=>c.blockSight,
  headingVec:h=>({x:Math.sin(h),z:Math.cos(h)}),WEAPONS:[{kind:'fusil'}],
  v27Stats:()=>({noiseMult:1,damageTakenMult:1}),v27IsCyber:()=>false,
  deck:{hacks:{}},stuns:[],bodyHits:[],v32Archetypes:{rifle:{vision:30,hearing:40}},
  damageFlash:0,announcements:[],downs:[],arrests:[],routeQueries:[],flightControls:[],drivingControls:[],
  policeStunPlayer:(q,damage)=>c.stuns.push({id:q.id,damage}),announce:(...args)=>c.announcements.push(args),
  handlePlayerDown:label=>c.downs.push(label),__SOMA_BODY35__:{afterDamage:(...args)=>c.bodyHits.push(args)},
  isFlyingVehicleKind:k=>k==='policeVTOL',isWaterVehicleKind:k=>k==='boat',
  nearestRoutePoint:(routes,x,z)=>{c.routeQueries.push([x,z]);return {route:routes[0],index:0};},
  vehicleSpec:()=>({cruise:10,length:4,maxSteer:1}),angleDelta:(a,b)=>b-a,
  integrateFlyingVehicle:(q,controls)=>c.flightControls.push(plain(controls)),integrateVehicle:(q,controls)=>c.drivingControls.push(plain(controls)),
  vehicleAheadDistance:()=>Infinity,routeHeading:()=>0,vehicleBlockedAt:()=>false,
  policeLevelFromHeat:()=>c.state.police.level,ensurePoliceResponse:()=>{},spawnRoadblock:()=>{},clearRoadblocks:()=>{},
  performArrest:label=>c.arrests.push(label),raisePoliceHeat:()=>{}};
 c.__SOMA_V32__={archetypes:c.v32Archetypes};
 c.__SOMA_V42__={isCrouched:()=>!!c.crouched,canUseOnFoot:()=>!c.state.driving&&c.state.health>0,state:()=>c.deck};
 c.window=c;vm.createContext(c);vm.runInContext(core,c);vm.runInContext(scripts.perception70,c);
 vm.runInContext(scripts.legacy71,c);vm.runInContext(scripts.ai,c);vm.runInContext(scripts.police,c);
 c.step=(dt=.25)=>{c.updateAI(dt);c.__SOMA_PERCEPTION70__.beginEnemyFrame(dt);};
 c.observer=(kind,q)=>c.__SOMA_LEGACY_PERCEPTION71__.observer(kind,q);
 return c;
}
function officer(extra={}){return {id:'officer:1',police:true,dispatch:true,health:120,x:0,z:0,homeX:0,homeZ:0,targetX:0,targetZ:0,
 vx:0,vz:0,heading:0,phase:0,arrestCooldown:0,unitType:'intervention',...extra};}
function robot(kind='security',extra={}){return {id:'machine:1',kind,health:100,hostile:true,x:0,z:0,homeX:0,homeZ:0,
 targetX:0,targetZ:0,heading:0,phase:0,...extra};}
function vehicle(kind='patrol',extra={}){return {id:'vehicle:1',kind,ai:true,dispatch:true,police:true,x:0,z:0,y:10,heading:0,
 speed:0,routeId:'route:1',routeIndex:0,...extra};}
function contact(c,count=4){for(let i=0;i<count;i++)c.step();}

test('real historical police pursues its observed contact, never the player hidden elsewhere',()=>{
 const c=context(),q=officer();c.zone.actors.push(q);contact(c);assert(c.observer('actor',q).confirmed);
 c.blockSight=true;c.camera.x=-50;c.camera.z=-50;q.x=0;q.z=0;q.vx=q.vz=0;const stuns=c.stuns.length;c.step();
 assert(q.z>0);assert.equal(q.targetX,0);assert.equal(q.targetZ,10);assert.equal(c.stuns.length,stuns);
 assert.deepEqual(plain(c.observer('actor',q).searchTarget),[0,10]);
 for(let i=0;i<22;i++)c.step();assert.equal(c.observer('actor',q).searchTarget,null);
});

test('wanted level and dispatch alone never reveal a position or allow stun',()=>{
 const c=context(),q=officer({targetX:100,targetZ:100});c.zone.actors.push(q);c.blockSight=true;c.camera.x=100;c.camera.z=100;contact(c);
 assert.equal(c.observer('actor',q).searchTarget,null);assert.equal(c.stuns.length,0);
 assert.notEqual(q.targetX,100);assert.notEqual(q.targetZ,100);
});

test('source dispatch spawns at its own patrol target without copying player coordinates',()=>{
 const c=context();c.state.police.level=1;c.camera.x=100;c.camera.z=100;
 c.pedestrianPoint=()=>({x:20,z:25});c.C={mix:()=>[0,0,0]};c.D={port:{cAccent:[1,1,1]}};
 vm.runInContext(scripts.dispatch,c);c.ensurePoliceResponse();assert.equal(c.zone.actors.length,2);
 for(const q of c.zone.actors){assert.equal(q.targetX,20);assert.equal(q.targetZ,25);}
});

test('historical security, drone and police weapons require visual confirmation',()=>{
 for(const kind of ['security','policeDrone']){
  const c=context(),q=robot(kind);c.zone.robots.push(q);contact(c);assert(c.observer('robot',q).confirmed);
  c.blockSight=true;c.camera.x=-50;c.camera.z=-50;q.x=0;q.z=0;q.phase=1.3;
  const health=c.state.health,stuns=c.stuns.length;c.step();assert.equal(c.state.health,health);assert.equal(c.stuns.length,stuns);
  assert.deepEqual(plain(c.observer('robot',q).searchTarget),[0,10]);
  if(kind==='policeDrone')assert(q.z>0);
 }
});

test('existing machine blind, lock and jam retain distinct real movement/weapon effects',()=>{
 for(const effect of ['blind','lock','jam']){
  const c=context(),q=robot('policeDrone');c.zone.robots.push(q);contact(c);q.x=0;q.z=0;q.phase=1.3;
  c.deck.hacks[c.zone.id]={[q.id]:{[effect]:5}};const stuns=c.stuns.length;c.step();const row=c.observer('robot',q);
  if(effect==='lock'){assert.equal(q.z,0);assert.equal(row.canMove,false);assert.equal(row.canTrackCurrent,true);}
  if(effect==='jam'){assert(q.z>0);assert.equal(row.canTrackCurrent,true);assert.equal(c.stuns.length,stuns);}
  if(effect==='blind'){assert.equal(row.canTrackCurrent,false);assert.equal(c.stuns.length,stuns);assert(row.searchTarget);}
 }
});

test('tactical actors, cameras and scripted bosses never execute the historical security kernel',()=>{
 const c=context();c.__SOMA_BOSSES36__={handles:q=>q.id==='boss36',suspended:()=>false};
 c.zone.robots.push(robot('security',{v32Enemy:true,id:'tactical'}),robot('security',{v26BossId:'boss26',id:'boss26'}),
  robot('security',{id:'boss36'}),robot('security',{v42Camera:true,id:'cctv'}));
 contact(c,8);assert.equal(c.__SOMA_LEGACY_PERCEPTION71__.snapshot().observerCount,0);
 assert.equal(c.stuns.length,0);assert.equal(c.bodyHits.length,0);assert.equal(c.state.health,100);
 assert.equal(scripts.sourceDamagePreserved,true);
});

test('real footstep emitter is shared at its fixed position even with audio muted',()=>{
 const c=context(),q=officer({z:-5});c.zone.actors.push(q);c.blockSight=true;c.camera.x=c.camera.z=0;c.step();
 c.camera.x=2;c.step();c.camera.x=100;c.camera.z=100;c.step();const row=c.observer('actor',q);
 assert.equal(row.lastSense,'sound');assert.deepEqual(plain(row.searchTarget),[2,0]);
 assert.equal(c.state.settings.volume,0);assert.equal(row.canAttack,false);
});

test('real shot emitter shares evidence once without moving it after the player moves',()=>{
 const c=context(),q=officer({z:-5});c.zone.actors.push(q);c.blockSight=true;c.camera.x=c.camera.z=0;c.step();
 c.__SOMA_PERCEPTION70__.recordShot();c.camera.x=100;c.camera.z=100;c.step();
 assert.deepEqual(plain(c.observer('actor',q).searchTarget),[0,0]);
 assert.equal(c.observer('actor',q).lastSense,'sound');assert.equal(c.observer('actor',q).canAttack,false);
});

test('ground police route selection and aerial steering use the observed location',()=>{
 for(const kind of ['patrol','policeVTOL']){
  const c=context(),q=vehicle(kind);c.camera.x=10;c.camera.z=10;c.zone.vehicles.push(q);
  c.zone.vehicleRoutes.push({id:'route:1',points:[{x:0,z:0},{x:0,z:20}],kind:'other'});
  c.zone.airRoutes.push({id:'route:1',points:[{x:0,z:0,y:10},{x:0,z:20,y:10}],kind:'air'});
  contact(c);assert(c.observer('vehicle',q).confirmed);c.routeQueries=[];c.flightControls=[];
  c.blockSight=true;c.camera.x=-100;c.camera.z=-100;c.step();
  if(kind==='patrol')assert.deepEqual(c.routeQueries,[[10,10]]);
  else {assert.equal(c.flightControls.length,1);assert(c.flightControls[0].steer>0);}
 }
});

test('aerial pressure cannot hit through a wall after last contact',()=>{
 const c=context(),q=vehicle('policeVTOL');c.zone.vehicles.push(q);c.zone.airRoutes.push({id:'route:1',points:[{x:0,z:0,y:10},{x:0,z:20,y:10}]});
 contact(c);q.phaseShot=-1;c.blockSight=true;c.camera.z=-10;const tension=c.state.tension;c.step();assert.equal(c.state.tension,tension);
});

test('voluntary arrest keeps its timer and requires an officer actually seeing the player',()=>{
 const c=context(),q=officer({z:8});c.zone.actors.push(q);c.state.police.lastCrimeAt=1000;c.camera.z=10;c.step();
 c.state.police.compliance=3.1;c.updatePolice(.2);assert.equal(c.arrests.length,1);
 c.blockSight=true;c.state.police.compliance=3.1;c.step();c.updatePolice(.2);assert.equal(c.arrests.length,1);
});

test('unknown source sight, crouch, pause and respawn identities stay conservative',()=>{
 const c=context(),q=officer();c.zone.actors.push(q);c.crouched=true;c.camera.z=20;c.step();
 assert.equal(c.observer('actor',q).canTrackCurrent,false);c.crouched=false;c.step();assert.equal(c.observer('actor',q).canTrackCurrent,true);
 c.__SOMA_SIGHT61__={activeFor:()=>true,eyePoint:()=>null};c.step();assert.equal(c.observer('actor',q).reason,'unknown-line-of-sight');
 const before=plain(c.__SOMA_LEGACY_PERCEPTION71__.snapshot());c.paused=true;c.__SOMA_LEGACY_PERCEPTION71__.beginFrame(.25);
 assert.deepEqual(plain(c.__SOMA_LEGACY_PERCEPTION71__.snapshot()),before);
 c.paused=false;c.blockSight=true;delete c.__SOMA_SIGHT61__;const replacement=officer();c.zone.actors=[replacement];c.step();
 assert.equal(c.observer('actor',replacement).searchTarget,null);assert.equal(c.observer('actor',q),null);
});

test('zone transfer, import reset and lowered wanted level discard transient contacts',()=>{
 const c=context(),q=officer();c.zone.actors.push(q);contact(c);assert(c.observer('actor',q).searchTarget);
 c.state.police.level=0;c.step();assert.equal(c.observer('actor',q),null);
 c.state.police.level=4;c.blockSight=true;c.step();assert.equal(c.observer('actor',q).searchTarget,null);
 c.blockSight=false;contact(c);c.__SOMA_PERCEPTION70__.reset();assert.equal(c.observer('actor',q),null);
 c.zone={...c.zone,id:'other-zone',actors:[officer()]};c.blockSight=true;c.step();
 assert.equal(c.__SOMA_LEGACY_PERCEPTION71__.snapshot().zoneId,'other-zone');assert.equal(c.observer('actor',c.zone.actors[0]).searchTarget,null);
});

test('snapshots are detached and observer budget never grows without bound',()=>{
 const c=context();for(let i=0;i<300;i++)c.zone.actors.push(officer({id:'officer:'+i}));c.step();
 const s=c.__SOMA_LEGACY_PERCEPTION71__.snapshot();assert.equal(s.observerCount,256);assert.equal(s.skippedObservers,44);
 s.observers[0].lastKnown[0]=999;assert.notEqual(c.__SOMA_LEGACY_PERCEPTION71__.snapshot().observers[0].lastKnown[0],999);
 assert.equal(s.persistent,false);assert.equal(s.sourceDataChanged,false);
});

test('same-id replacement cannot inherit a previous combat cone or a contact',()=>{
 const c=context(),q=officer();c.zone.actors.push(q);contact(c);assert(c.observer('actor',q).confirmed);
 const replacement=officer();c.zone.actors=[replacement];c.camera.x=10;c.camera.z=2;c.step();
 assert.equal(c.observer('actor',replacement).canTrackCurrent,false);
 assert.equal(c.observer('actor',replacement).searchTarget,null);
});

test('a reused zone object with a new source identity cannot retain contact memory',()=>{
 const c=context(),q=officer();c.zone.actors.push(q);contact(c);assert(c.observer('actor',q).searchTarget);
 c.zone.id='changed-source-zone';c.blockSight=true;c.step();assert.equal(c.observer('actor',q).searchTarget,null);
});

test('real digital ICE keeps its original attack owner and does not gain physical perception immunity',()=>{
 const c=context(),q=robot('security',{v27ICE:true,phase:1.3});c.zone.type='v27-cyber';c.zone.robots.push(q);
 c.v27IsCyber=()=>true;c.camera.x=5;c.camera.z=10;c.step();
 assert.equal(c.state.health,93);assert.equal(c.bodyHits.length,1);assert.equal(q.heading,Math.atan2(5,10));
 assert.equal(c.observer('robot',q),null);assert.equal(c.__SOMA_LEGACY_PERCEPTION71__.snapshot().observerCount,0);
});
