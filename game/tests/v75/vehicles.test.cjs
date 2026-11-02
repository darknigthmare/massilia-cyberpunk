'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {setup}=require('./vehicles-fixture.cjs');
const plain=v=>JSON.parse(JSON.stringify(v));
const ramp=(x,z)=>30+Math.max(0,Math.min(5,x))*.9;
function driveRamp(parent,hz){const c=setup({height:ramp,parent});Object.assign(c.vehicle,{x:-4,speed:13.5});let stopped=false;for(let i=0;i<hz*2;i++)if(!c.integrateVehicle(c.vehicle,{throttle:1},1/hz,false)){stopped=true;break;}return{c,stopped};}
test('regression: actual v57 edge averages accept a local slope above its .7 limit',()=>{
 const c=setup({height:ramp,parent:true}),v=c.vehicle;v.x=.6;
 assert.equal(c.vehicleBlockedAt(v,v.x,v.z,v.heading),false);
 assert.ok(c.slope(c.zone,v.x,v.z).e>.7);
 const {c:before,stopped}=driveRamp(true,60);assert.equal(stopped,true);assert.ok(before.vehicle.x>.6);
});
test('the real mechanics stop before an axle engages the native-grid steep patch, at 30/60/120 Hz',()=>{
 for(const hz of [30,60,120]){
  const {c,stopped}=driveRamp(false,hz),v=c.vehicle;assert.equal(stopped,true);assert.ok(v.x<-.9,`${hz} Hz: ${v.x}`);
  assert.ok(c.__SOMA_VEHICLES75__.snapshot().stats.slopeStops>0);assert.ok(Number.isFinite(v.speed));assert.equal(v.id,'original-owner-vehicle');
  assert.equal(c.vehicleBlockedAt(v,v.x,v.z,v.heading),false);
 }
});
test('admissible flat and 50% terrain retain the exact inherited speed, steering and distance at 30/60/120 Hz',()=>{
 for(const grade of [0,.5])for(const hz of [30,60,120]){
  const a=setup({height:x=>30+grade*x,parent:true}),b=setup({height:x=>30+grade*x});
  for(const c of [a,b]){c.vehicle.speed=8;for(let i=0;i<hz;i++)assert.equal(c.integrateVehicle(c.vehicle,{throttle:1,steer:.4},1/hz,false),true);}
  assert.deepEqual(plain(b.vehicle),plain(a.vehicle));assert.ok(b.__SOMA_VEHICLES75__.snapshot().stats.sweepSamples>hz);
 }
});
test('source oriented static/vehicle collisions remain authoritative at maximum speed and reverse',()=>{
 for(const direction of [1,-1])for(const hz of [30,60,120])for(const obstacle of ['wall','car']){
  const c=setup(),v=c.vehicle;Object.assign(v,{x:direction*-4,speed:direction*13.5});
  if(obstacle==='wall')c.zone.colliders.push({x0:-.05,x1:.05,z0:-4,z1:4,tag:'solid'});
  else c.zone.vehicles.push({id:'other',kind:'sedan',x:0,z:0,heading:0});
  let stopped=false;for(let i=0;i<hz*3;i++)if(!c.integrateVehicle(v,{throttle:direction},1/hz,false)){stopped=true;break;}
  assert.equal(stopped,true);assert.ok(direction*v.x<-.8);assert.equal(c.vehicleBlockedAt(v,v.x,v.z,v.heading),false);
 }
});
test('active terrain resolution, NoData and adjacent metric cells keep their existing owners',()=>{
 for(const step of [5,25]){
  const c=setup({step,missing:(x,z)=>x>=step}),v=c.vehicle;v.speed=13.5;let stopped=false;
  for(let i=0;i<600;i++)if(!c.integrateVehicle(v,{throttle:1},1/60,false)){stopped=true;break;}
  assert.equal(stopped,true);assert.ok(v.x<step);assert.ok(c.stats.missingGround>0);
 }
 const c=setup(),v=c.vehicle,other={...c.zone,id:'geo:neighbor',v52GridX:1,v50Record:{...c.zone.v50Record,boundsL93:[50,-50,150,50]},colliders:[{x0:-49.95,x1:-49.9,z0:-2,z1:2,tag:'solid'}],vehicles:[]};
 c.WORLD.zones[other.id]=other;c.gridIds.set('1:0','neighbor');Object.assign(v,{x:46,speed:13.5});
 for(let i=0;i<120;i++){if(!c.integrateVehicle(v,{throttle:1},1/60,false))break;}
 assert.ok(v.x<48.2);assert.ok(c.__SOMA_VEHICLES75__.snapshot().stats.collisionStops>0);
});
test('invalid dt, pause and stalled frame bounds remain v57 rules; air and water delegate untouched',()=>{
 const c=setup(),v=c.vehicle;v.speed=10;const initial=plain(v);
 for(const dt of [NaN,Infinity,-1])assert.equal(c.integrateVehicle(v,{},dt,true),false);assert.deepEqual(plain(v),initial);
 c.paused=true;c.integrateVehicle(v,{throttle:1},.1,true);assert.deepEqual(plain(v),initial);
 c.paused=false;c.integrateVehicle(v,{throttle:1},10,true);assert.ok(Math.hypot(v.x,v.z)<1.1);
 const a=setup({kind:'airTaxi'});assert.equal(a.integrateVehicle(a.vehicle,{},.1,false),true);assert.equal(a.flyingCalls,1);assert.equal(a.__SOMA_VEHICLES75__.snapshot().stats.pathChecks,0);
 const water=setup({kind:'boat'}),before=setup({kind:'boat',parent:true});water.integrateVehicle(water.vehicle,{},.1,false);before.integrateVehicle(before.vehicle,{},.1,false);assert.deepEqual(plain(water.vehicle),plain(before.vehicle));
});
test('diagonal-cell body and source collider contacts use the original v57 metric transform',()=>{
 for(const source of ['car','wall']){
  const c=setup(),v=c.vehicle,corner={...c.zone,id:'geo:diagonal',v52GridX:1,v52GridY:-1,
   v50Record:{...c.zone.v50Record,boundsL93:[50,50,150,150]},colliders:[],vehicles:[]};
  const east={...c.zone,id:'geo:east',v52GridX:1,v50Record:{...c.zone.v50Record,boundsL93:[50,-50,150,50]},colliders:[],vehicles:[]};
  const north={...c.zone,id:'geo:north',v52GridY:-1,v50Record:{...c.zone.v50Record,boundsL93:[-50,50,50,150]},colliders:[],vehicles:[]};
  for(const z of [corner,east,north]){c.WORLD.zones[z.id]=z;c.gridIds.set(z.v52GridX+':'+z.v52GridY,z.id.slice(4));}
  if(source==='car')corner.vehicles.push({id:'diagonal-car',kind:'sedan',x:-50,z:50,heading:Math.PI/4});
  else corner.colliders.push({x0:-50,x1:-49.85,z0:49.85,z1:50,tag:'solid'});
  Object.assign(v,{x:46,z:-46,heading:Math.PI*3/4,speed:13.5});let stopped=false;
  for(let i=0;i<120;i++)if(!c.integrateVehicle(v,{throttle:1},1/60,false)){stopped=true;break;}
  assert.equal(stopped,true);assert.ok(c.__SOMA_VEHICLES75__.snapshot().stats.collisionStops>0);
  assert.equal(c.vehicleBlockedAt(v,v.x,v.z,v.heading),false);assert.equal(c.zone.id,'geo:synthetic-vehicles');
 }
});
test('guard is ephemeral and reads the same live vehicle after a scene rebuild',()=>{
 const c=setup(),before=plain(c.vehicle),replacement={...c.vehicle,id:c.vehicle.id,condition:73};c.zone.vehicles=[replacement];
 assert.equal(c.__SOMA_VEHICLES75__.pathBlocked(replacement,.03,0,Math.PI/2,Math.PI/2),false);
 assert.deepEqual(plain(c.vehicle),before);assert.equal(replacement.condition,73);assert.equal(replacement.x,0);
 assert.equal(c.__SOMA_VEHICLES75__.snapshot().ephemeral,true);assert.equal(c.state.statistics.vehicleImpacts||0,0);
});
test('heading wrap, motorcycles and a stalled call retain the inherited mechanical profile',()=>{
 for(const kind of ['sedan','streetBike'])for(const reverse of [false,true]){
  const a=setup({kind,parent:true}),b=setup({kind});for(const c of [a,b]){
   Object.assign(c.vehicle,{heading:Math.PI-.001,speed:reverse?-2:13,steering:.2});
   assert.equal(c.integrateVehicle(c.vehicle,{throttle:reverse?-1:1,steer:1},.1,false),true);
  }
  assert.deepEqual(plain(b.vehicle),plain(a.vehicle));assert.ok(Number.isFinite(b.vehicle.lean));
 }
 const a=setup(),b=setup();for(const c of [a,b])c.vehicle.speed=10;
 a.integrateVehicle(a.vehicle,{throttle:1,steer:.3},.1,false);b.integrateVehicle(b.vehicle,{throttle:1,steer:.3},10,false);
 assert.deepEqual(plain(a.vehicle),plain(b.vehicle));
});
