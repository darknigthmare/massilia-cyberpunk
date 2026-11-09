'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {setup,observe,plain,owners}=require('./world-fixture.cjs'),vm=require('node:vm');
function assertPhysicalRollback(f){
 const {c,from,to,car}=f,now=observe(c);
 for(const key of ['zone','state','camera','car','source','target','memory','classes'])assert.deepEqual(now[key],f.before[key],key);
 assert.equal(c.zone,from);assert.equal(from.vehicles,f.sourceArray);assert.equal(to.vehicles,f.targetArray);
 assert.equal(from.vehicles[0],car);assert.equal(from.vehicles[1],f.sourcePeer);assert.equal(to.vehicles[0],f.targetPeer);
 assert.equal(c.state.lastOnFoot,f.oldLast);assert.equal(c.transitioning,false);
 for(const[id,value]of f.memoryRefs)assert.equal(c.memory.get(id),value);
 for(const key of ['footCrossings','vehicleCrossings','blockedCrossings','maxMetricError','lastCrossing'])assert.deepEqual(plain(c.stats[key]),f.before.stats[key]);
 assert.match(c.stats.lastFailure,/(?:Injected|Persistent) observer failure/);
}
function installKnownFleet45(f){
 const {c,car}=f,vin='NM45-KNOWN';car.v45Vin=vin;car.v45Upgrades={engine:0,brakes:0,tires:0,armor:0};
 const record={vin,id:car.id,kind:car.kind,sourceZone:f.from.id,lastZone:f.from.id,paint:car.paint,condition:94,components:{body:94,engine:100,brakes:100,tires:100},upgrades:{...car.v45Upgrades}};
 c.V45={fleet:{activeVin:vin,vehicles:{[vin]:record}},stats:{vehiclesOwned:1}};c.v45Clamp=(x,a,b)=>Math.max(a,Math.min(b,x));c.v45Hash=()=>{throw Error('existing VIN must not be regenerated');};c.v45Save=()=>{c.fleetStore=plain(c.V45);};
 vm.runInContext(owners.fleet45,c);c.__SOMA_V45__={state:()=>c.V45,registerVehicle:c.v45RegisterVehicle};f.before=observe(c);return{record,vin,native:c.v45RegisterVehicle};
}
test('actual55 remembered outside try leaves a removed car and locked transition when58 snapshot throws',()=>{
 const f=setup({parent:true,fault:'remember'}),{c,from,to,car}=f;
 assert.throws(()=>c.handoff(from,to),/Injected observer failure/);assert.equal(c.transitioning,true);assert.equal(c.state.driving,null);assert(!from.vehicles.includes(car));
 assert.equal(c.handoff(from,to),false,'the leaked lock blocks a subsequent attempt');
});
test('actual55 late catch returns false but leaves the source car transferred and duplicated in the target membership',()=>{
 const {c,from,to,car,before}=setup({parent:true,fault:'register-before'});
 assert.equal(c.handoff(from,to),false);assert.equal(c.zone,from);assert.equal(c.state.driving,car.id);
 assert(Math.abs(car.x-(before.car.x-250))<c.C.EPS);assert(from.vehicles.includes(car)&&to.vehicles.includes(car));
 assert.notDeepEqual([...c.memory],before.memory);assert.equal(c.transitioning,false);
});
test('78 protects remember and every downstream observer boundary while preserving object and array identity',()=>{
 for(const fault of ['remember','enter','save52-before','save52-after','register-before','register-after','saveCore','refresh']){
  const f=setup({fault}),{c,from,to}=f;
  assert.equal(c.handoff(from,to),false,fault);assertPhysicalRollback(f);
  assert.equal(c.handoff(from,to),true,'a second attempt must work after '+fault);
  assert.equal(c.zone,to);assert.equal(c.transitioning,false);assert.equal(c.__SOMA_WORLD78__.snapshot().counts.restored,1);
 }
});
test('78 removes only newly-created memory entries when no previous snapshots existed',()=>{
 const f=setup({fault:'register-before',existingMemory:false});assert.equal(f.c.handoff(f.from,f.to),false);assertPhysicalRollback(f);assert.equal(f.c.memory.size,0);
});
test('foot handoff failure has the same scene rollback and the same unlocked retry',()=>{
 const f=setup({mode:'foot',fault:'saveCore'});assert.equal(f.c.handoff(f.from,f.to),false);assertPhysicalRollback(f);assert.equal(f.c.handoff(f.from,f.to),true);
 assert.equal(f.c.state.driving,null);assert.equal(f.c.stats.footCrossings,f.before.stats.footCrossings+1);assert.equal(f.c.stats.vehicleCrossings,f.before.stats.vehicleCrossings);
});
test('success preserves exact metric world coordinates and native vehicle registration',()=>{
 for(const parent of [true,false]){
  const f=setup({parent}),{c,from,to,car}=f;assert.equal(c.handoff(from,to,{code:'source-road',v50SourceId:'osm/way/123'}),true);
  assert.equal(c.C.metricError(from.v50Record,to.v50Record,f.before.camera,c.camera),0);assert.equal(c.state.driving,car.id);
  assert.equal(from.vehicles.includes(car),false);assert.equal(to.vehicles.filter(v=>v===car).length,1);assert.equal(to.vehicles[0],f.targetPeer);
  assert(Math.abs(car.x-(f.before.car.x-250))<c.C.EPS);assert.equal(car.heading,f.before.car.heading);assert.equal(car.condition,72);assert.equal(car.v45Vin,'fixture-vin');
  assert.equal(c.stats.vehicleCrossings,f.before.stats.vehicleCrossings+1);assert.deepEqual(plain(c.layer.global.drivenSeamCodes),['old-seam','source-road']);assert.equal(c.transitioning,false);
 }
});
test('failed native admission does not open a transaction, mutate the scene or call observers',()=>{
 const f=setup();f.c.admissionBlocked=true;assert.equal(f.c.handoff(f.from,f.to),false);assert.deepEqual(observe(f.c),f.before);assert.deepEqual(f.c.calls,[]);assert.equal(f.c.__SOMA_WORLD78__.snapshot().counts.captured,0);
});
test('a secondary recovery-render exception cannot hide the first failure or retain the transition lock',()=>{
 const f=setup({fault:'register-before'});f.c.__SOMA_V54__.refreshScene=()=>{f.c.document.body.classList.remove('driving');throw Error('Secondary renderer failure');};
 assert.equal(f.c.handoff(f.from,f.to),false);assertPhysicalRollback(f);assert.match(f.c.stats.lastFailure,/register-before/);assert.equal(f.c.handoff(f.from,f.to),true);
});
test('best-effort compensation restores native counters, while opaque45 registration remains explicitly outside this transaction',()=>{
 const f=setup({fault:'refresh'}),{c}=f;assert.equal(c.handoff(f.from,f.to),false);assertPhysicalRollback(f);
 assert.deepEqual(c.layerStore.global,{drivenSeamCodes:['old-seam'],drivenSeams:1});
 assert.equal(c.statsStore.vehicleCrossings,f.before.stats.vehicleCrossings);assert.equal(c.coreStore.zone,f.from.id);
 assert.equal(c.fleet.lastZone,f.to.id,'an independent45 observer may already have published its own lastZone');
 assert.equal(c.__SOMA_WORLD78__.snapshot().newPersistenceDomain,false);
});
test('native55 saveStats catches a storage failure; it does not invent a rollback exception',()=>{
 for(const parent of [true,false]){const f=setup({parent,fault:'storageQuota'});assert.equal(f.c.handoff(f.from,f.to),true);assert.equal(f.c.zone,f.to);assert.equal(f.c.transitioning,false);}
});
test('independent52 mission completion and its credit award stay together across rollback and retry',()=>{
 const f=setup({fault:'register-before'}),{c}=f,enter=c.oldEnter;c.state.credits=100;c.layer.completedMissions=[];
 c.oldEnter=(...args)=>{const result=enter(...args);if(!c.layer.completedMissions.includes('fixture-visit-award')){c.layer.completedMissions.push('fixture-visit-award');c.state.credits+=25;}return result;};
 assert.equal(c.handoff(f.from,f.to),false);assert.equal(c.state.credits,125);assert.deepEqual(c.layer.completedMissions,['fixture-visit-award']);
 assert.equal(c.state.x,f.before.state.x);assert.equal(c.state.zone,f.from.id);assert.equal(c.handoff(f.from,f.to),true);assert.equal(c.state.credits,125);assert.deepEqual(c.layer.completedMissions,['fixture-visit-award']);
});
test('durable observer failure cannot prevent in-memory restoration or final lock release',()=>{
 const f=setup(),{c}=f;c.v52=()=>({state:()=>c.layer,save(){throw Error('Persistent observer failure');}});
 assert.equal(c.handoff(f.from,f.to),false);assertPhysicalRollback(f);assert.equal(c.handoff(f.from,f.to),false);assert.equal(c.transitioning,false);
});
test('actual45 registration of an existing VIN does not duplicate its record across a physical55 rollback and retry',()=>{
 const f=setup({fault:'refresh'}),{c,car}=f,vin='NM45-REGISTERED';car.v45Vin=vin;car.v45Upgrades={engine:0,brakes:0,tires:0,armor:0};
 const record={vin,id:car.id,kind:car.kind,sourceZone:f.from.id,lastZone:f.from.id,paint:car.paint,condition:94,components:{body:94,engine:100,brakes:100,tires:100},upgrades:{...car.v45Upgrades}};
 c.V45={fleet:{activeVin:vin,vehicles:{[vin]:record}},stats:{vehiclesOwned:1}};c.v45Clamp=(x,a,b)=>Math.max(a,Math.min(b,x));c.v45Hash=()=>{throw Error('existing VIN must not be regenerated');};c.v45Save=()=>{c.fleetStore=plain(c.V45);};
 vm.runInContext(owners.fleet45,c);c.__SOMA_V45__={state:()=>c.V45,registerVehicle:c.v45RegisterVehicle};f.before=observe(c);const upgrades=car.v45Upgrades;
 assert.equal(c.handoff(f.from,f.to),false);assertPhysicalRollback(f);assert.equal(car.v45Upgrades,upgrades);assert.equal(c.V45.fleet.vehicles[vin],record);assert.equal(Object.keys(c.V45.fleet.vehicles).length,1);
 assert.equal(record.lastZone,f.from.id,'one existing-VIN native registration compensates its lastZone');
 assert.equal(c.__SOMA_WORLD78__.snapshot().counts.fleetCompensations,1);assert.equal(c.fleetStore.fleet.vehicles[vin].lastZone,f.from.id);
 assert.equal(c.handoff(f.from,f.to),true);assert.equal(Object.keys(c.V45.fleet.vehicles).length,1);assert.equal(c.V45.stats.vehiclesOwned,1);assert.equal(car.v45Vin,vin);
});
test('native58 Invalid entity state can reach the old unprotected remember boundary without replacing its implementation',()=>{
 for(const parent of [true,false]){
  const f=setup({parent}),{c}=f;f.from.actors=[null];
  if(parent){assert.throws(()=>c.handoff(f.from,f.to),/Invalid entity state/);assert.equal(c.transitioning,true);assert.equal(c.state.driving,null);}
  else{assert.equal(c.handoff(f.from,f.to),false);assert.equal(c.transitioning,false);assert.equal(c.state.driving,f.car.id);assert.equal(f.from.vehicles,f.sourceArray);assert.equal(f.to.vehicles,f.targetArray);assert.match(c.stats.lastFailure,/Invalid entity state/);}
  f.from.actors=[];assert.equal(c.handoff(f.from,f.to),!parent,'only the fixed owner releases the lock for retry');
 }
});
test('a target entity with the same id but a different identity survives failure unchanged',()=>{
 const f=setup({fault:'register-before'}),shadow={id:f.car.id,x:19,z:21,heading:-.4};f.to.vehicles.push(shadow);f.before=observe(f.c);
 assert.equal(f.c.handoff(f.from,f.to),false);assertPhysicalRollback(f);assert.equal(f.to.vehicles[1],shadow);assert.equal(f.to.vehicles.length,2);
});
test('a third-cell eviction snapshot is retained while only source and target memory slots roll back',()=>{
 const f=setup({fault:'register-before'}),{c}=f,enter=c.oldEnter,third={hash:'third-evicted',vehicles:[{id:'third-car'}]};
 c.oldEnter=(...args)=>{const result=enter(...args);c.memory.set('geo:third',third);return result;};
 assert.equal(c.handoff(f.from,f.to),false);assert.equal(c.memory.get('geo:third'),third);
 for(const[id,value]of f.memoryRefs)assert.equal(c.memory.get(id),value);
 assert.equal(f.from.vehicles,f.sourceArray);assert.equal(f.to.vehicles,f.targetArray);assert.equal(c.state.driving,f.car.id);assert.equal(c.transitioning,false);
});
test('spatial core properties absent before an attempt stay absent after rollback',()=>{
 const f=setup({fault:'register-before'});for(const key of ['x','z','yaw','pitch'])delete f.c.state[key];f.before=observe(f.c);
 assert.equal(f.c.handoff(f.from,f.to),false);assertPhysicalRollback(f);for(const key of ['x','z','yaw','pitch'])assert.equal(Object.hasOwn(f.c.state,key),false);
});
test('a known VIN is not registered for compensation if the attempt failed before registration was reached',()=>{
 const f=setup({fault:'save52-before'}),{c}=f,{record,native}=installKnownFleet45(f);let attempts=0;c.__SOMA_V45__.registerVehicle=v=>{attempts++;return native(v);};
 assert.equal(c.handoff(f.from,f.to),false);assertPhysicalRollback(f);assert.equal(attempts,0);assert.equal(record.lastZone,f.from.id);assert.equal(c.__SOMA_WORLD78__.snapshot().counts.fleetCompensations,0);
 assert.equal(c.handoff(f.from,f.to),true);assert.equal(attempts,1);
});
test('a failed45 compensation is attempted once, cannot break physical rollback, and does not duplicate the record on retry',()=>{
 const f=setup(),{c}=f,{record,native}=installKnownFleet45(f);let attempts=0;
 c.__SOMA_V45__.registerVehicle=v=>{attempts++;if(attempts===2)throw Error('Persistent compensation failure');const result=native(v);if(attempts===1)throw Error('Injected observer failure: register45-after');return result;};
 assert.equal(c.handoff(f.from,f.to),false);assertPhysicalRollback(f);assert.equal(attempts,2);assert.equal(record.lastZone,f.to.id,'durable failure may leave45 observation uncompensated');
 const snapshot=c.__SOMA_WORLD78__.snapshot();assert.equal(snapshot.counts.fleetCompensations,1);assert.equal(snapshot.counts.fleetCompensationExceptions,1);
 assert.equal(c.handoff(f.from,f.to),true);assert.equal(attempts,3);assert.equal(Object.keys(c.V45.fleet.vehicles).length,1);
});
