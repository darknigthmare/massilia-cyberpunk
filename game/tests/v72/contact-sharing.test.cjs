'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const scripts=require('./contact-fixture.cjs'),game=path.resolve(__dirname,'../..');
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
 vm.runInContext(scripts.legacy71,c);vm.runInContext(scripts.radio72,c);vm.runInContext(scripts.ai,c);vm.runInContext(scripts.police,c);
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
function observe(c,count=4){for(let i=0;i<count;i++)c.step();}


test('real police shares a sampled contact with a colleague, without granting stun or arrest',()=>{
 const c=context(),source=officer(),receiver=officer({id:'officer:2',x:10,homeX:10,targetX:10});
 c.zone.actors.push(source,receiver);c.lineBlocked=(x)=>c.blockSight||x>5;observe(c);
 const row=c.observer('actor',receiver);assert.deepEqual(plain(row.searchTarget),[0,10]);
 assert.equal(row.reason,'radio-last-known');assert.equal(row.canAttack,false);assert.equal(row.confirmed,false);
 assert.equal(row.canTrackCurrent,false);assert.equal(row.contact.originId,'legacy:actor:officer:1');
 c.blockSight=true;c.camera.x=-100;c.camera.z=-100;const stuns=c.stuns.length;
 c.state.police.compliance=3.1;c.step();c.updatePolice(.2);
 assert.equal(c.stuns.length,stuns);assert.equal(c.arrests.length,0);
 assert.deepEqual(plain(c.observer('actor',receiver).searchTarget),[0,10]);
 assert.equal(scripts.sourceDamagePreserved,true);assert.equal(scripts.v32Preserved,true);
});

test('received evidence cannot relay itself or restart the original expiry in a loop',()=>{
 const c=context(),a=officer(),b=officer({id:'officer:2',x:10,homeX:10,targetX:10});
 c.zone.actors.push(a,b);c.lineBlocked=x=>c.blockSight||x>5;c.step();
 const first=c.observer('actor',b).contact;assert(first);c.blockSight=true;c.camera.x=c.camera.z=100;
 let last=Infinity;
 for(let i=0;i<23;i++){
  c.step();const row=c.observer('actor',b);assert(row.memoryRemaining<=last+1e-8);last=row.memoryRemaining;
  if(row.contact)assert.equal(row.contact.expiresAt,first.expiresAt);
 }
 assert.equal(c.observer('actor',a).searchTarget,null);assert.equal(c.observer('actor',b).searchTarget,null);
 assert.equal(c.__SOMA_CONTACT_SHARING72__.snapshot().contactCount,0);
});

test('radio is limited by faction, original source range and local zone space',()=>{
 const c=context(),a=officer(),near=officer({id:'near',x:10,homeX:10,targetX:10}),far=officer({id:'far',x:60,homeX:60,targetX:60});
 const enemy=robot('security',{id:'enemy',x:12});c.zone.actors.push(a,near,far);c.zone.robots.push(enemy);
 c.lineBlocked=x=>x>5;c.step();assert(c.observer('actor',near).contact);
 assert.equal(c.observer('actor',far).searchTarget,null);assert.equal(c.observer('robot',enemy).searchTarget,null);
 c.blockSight=true;c.lineBlocked=()=>true;c.zone.id='new-local-space';c.step();
 for(const q of [a,near,far])assert.equal(c.observer('actor',q).searchTarget,null);
});

test('real camera alerts only nearby local security and keeps the observed point',()=>{
 const c=context(),near=robot('security',{id:'security:near',x:10}),far=robot('security',{id:'security:far',x:70});
 const officer1=officer({x:12}),camera1=robot('security',{id:'camera:1',v42Camera:true});
 c.zone.v42Complex='local';c.zone.robots.push(near,far,camera1);c.zone.actors.push(officer1);c.lineBlocked=x=>x>5;
 c.v42Dist=(a,b)=>Math.hypot(a.x-b.x,a.z-b.z);c.v42Effects=()=>null;c.v42VehicleBlocks=()=>false;
 vm.runInContext(scripts.camera,c);c.v42TickSecurity(.9);c.blockSight=true;c.lineBlocked=()=>true;
 c.camera.x=c.camera.z=100;c.step();
 assert.deepEqual(plain(c.observer('robot',near).searchTarget),[0,10]);
 assert.equal(c.observer('robot',near).canAttack,false);assert.equal(c.observer('robot',far).searchTarget,null);
 assert.equal(c.observer('actor',officer1).searchTarget,null);
 assert.equal(c.__SOMA_CONTACT_SHARING72__.cameraContact({...camera1},c.camera),false);
 assert.equal(c.__SOMA_CONTACT_SHARING72__.cameraContact(camera1,{x:0,z:10}),false);
});

test('explicitly compatible tactical units can exchange observations with historical police',()=>{
 const c=context(),a=officer({x:10,homeX:10,targetX:10}),q=robot('v32',{id:'tactical',v32Enemy:true,v32Role:'rifle',
  v33Faction:'police',v33Squad:'p',state:'patrol',detect:0,searchClock:0});
 c.zone.actors.push(a);c.zone.robots.push(q);c.lineBlocked=x=>x>5;c.step();c.step();
 assert.equal(c.observer('actor',a).contact.originId,'tactical:tactical');
 assert.deepEqual(plain(c.observer('actor',a).searchTarget),[0,10]);
 assert.equal(c.observer('actor',a).canAttack,false);
});

test('source death/replacement and receiver replacement never inherit an object identity',()=>{
 const c=context(),a=officer(),b=officer({id:'officer:2',x:10,homeX:10,targetX:10});
 c.zone.actors.push(a,b);c.lineBlocked=x=>x>5;c.step();assert(c.observer('actor',b).contact);
 c.zone.actors=[officer(),officer({id:'officer:2',x:10,homeX:10,targetX:10})];c.blockSight=true;c.lineBlocked=()=>true;c.step();
 assert.equal(c.observer('actor',c.zone.actors[0]).searchTarget,null);
 assert.equal(c.observer('actor',c.zone.actors[1]).searchTarget,null);
 assert.equal(c.__SOMA_CONTACT_SHARING72__.snapshot().contactCount,0);
 assert.equal(c.observer('actor',b),null);
});

test('old campaigns, wanted alone, imports and zone object transfers do not supply contacts',()=>{
 const c=context(),a=officer({targetX:100,targetZ:100});c.zone.actors.push(a);c.blockSight=true;observe(c);
 assert.equal(c.observer('actor',a).searchTarget,null);assert.equal(c.__SOMA_CONTACT_SHARING72__.snapshot().contactCount,0);
 c.blockSight=false;c.step();assert(c.__SOMA_CONTACT_SHARING72__.snapshot().contactCount);
 c.__SOMA_PERCEPTION70__.reset();assert.equal(c.__SOMA_CONTACT_SHARING72__.snapshot().contactCount,0);
 c.blockSight=true;c.step();assert.equal(c.observer('actor',a).searchTarget,null);
 c.zone={...c.zone,id:'transferred',actors:[officer()]};c.step();assert.equal(c.observer('actor',c.zone.actors[0]).searchTarget,null);
});

test('radio snapshots are detached; contact, observer and pair-work budgets stay bounded',()=>{
 const c=context();for(let i=0;i<300;i++)c.zone.actors.push(officer({id:'officer:'+i,x:i%4}));c.step();
 const s=c.__SOMA_CONTACT_SHARING72__.snapshot();assert(s.contactCount<=128);assert(s.peerCount<=512);assert(s.checks<=4096);
 assert(s.dropped>0);assert.equal(c.__SOMA_LEGACY_PERCEPTION71__.snapshot().observerCount,256);
 s.contacts[0].position[0]=999;assert.notEqual(c.__SOMA_CONTACT_SHARING72__.snapshot().contacts[0].position[0],999);
 assert.equal(s.persistent,false);assert.equal(s.sourceDataChanged,false);
});

test('lowered wanted level discards police broadcasts before a later dispatch',()=>{
 const c=context(),a=officer(),b=officer({id:'officer:2',x:10,homeX:10,targetX:10});
 c.zone.actors.push(a,b);c.lineBlocked=x=>x>5;c.step();assert(c.observer('actor',b).contact);
 c.state.police.level=0;c.step();assert.equal(c.__SOMA_CONTACT_SHARING72__.snapshot().contactCount,0);
 c.state.police.level=4;c.lineBlocked=()=>true;c.step();assert.equal(c.observer('actor',b).searchTarget,null);
});

test('radio keeps motor lock and weapon jam; firing still needs a new personal visual confirmation',()=>{
 const c=context(),a=robot('security',{id:'source'}),b=robot('security',{id:'receiver',x:10});
 c.zone.robots.push(a,b);c.lineBlocked=x=>x>5;c.deck.hacks[c.zone.id]={[b.id]:{lock:5,jam:5}};
 c.step();let row=c.observer('robot',b);assert(row.contact);assert.equal(row.canMove,false);assert.equal(row.canAttack,false);
 c.lineBlocked=()=>false;observe(c);row=c.observer('robot',b);assert.equal(row.canTrackCurrent,true);
 assert.equal(row.contact,undefined);assert.equal(row.canAttack,false);
 c.deck.hacks[c.zone.id][b.id]={};c.step();assert.equal(c.observer('robot',b).canAttack,true);
});

test('a broadcast stores its original emitter point and cannot use a moving relay to reach farther',()=>{
 const c=context(),a=officer(),b=officer({id:'officer:2',x:70,homeX:70,targetX:70});
 c.zone.actors.push(a,b);c.lineBlocked=x=>c.blockSight||x>5;c.step();
 const event=c.__SOMA_CONTACT_SHARING72__.snapshot().contacts[0];assert.deepEqual(event.originPosition,[0,0]);
 a.x=40;c.blockSight=true;c.step();assert.equal(c.observer('actor',b).searchTarget,null);
 assert.deepEqual(c.__SOMA_CONTACT_SHARING72__.snapshot().contacts[0].originPosition,[0,0]);
});


test('mixed terrain NGF and relative vehicle altitude do not create a false vertical radio barrier',()=>{
 const c=context(),a=officer({y:420}),b=officer({id:'officer:2',x:10,y:0,homeX:10,targetX:10});
 c.zone.actors.push(a,b);c.lineBlocked=x=>x>5;c.__SOMA_SIGHT61__={activeFor:()=>true,eyePoint:()=>({y:421.72})};
 c.step();assert(c.observer('actor',b).contact);
 assert.deepEqual(plain(c.observer('actor',b).contact.originPosition),[0,0]);
 assert.equal(c.__SOMA_CONTACT_SHARING72__.CONFIG.heightM,undefined);
});
