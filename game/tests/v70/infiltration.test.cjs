'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const K=require('../../src/v70/infiltration-core.js');
const near=(a,b,epsilon=1e-10)=>assert(Math.abs(a-b)<=epsilon,`${a} != ${b}`);
const guard=(id='guard',extra={})=>({id,position:[0,0],visual:'blocked',hearingRange:40,electronic:false,...extra});
const frame=(extra={})=>({dt:.25,player:[10,0],observers:[guard()],noises:[],...extra});
function tick(state,extra={}){return K.advance(state,frame(extra));}
function seePlayer(observers=[guard('guard',{visual:'visible'})]){
  let result={state:K.initial()};
  for(let i=0;i<4;i++)result=tick(result.state,{observers});
  return result;
}

test('signature shares canonical posture and uses noise equipment independently of playback volume',()=>{
  const walk=K.signature({speed:3.2,crouched:false}),crouch=K.signature({speed:1.8,crouched:true});
  const quiet=K.signature({speed:3.2,crouched:false,noiseMultiplier:.4});
  assert(walk.level>crouch.level&&walk.radiusM>crouch.radiusM);
  assert(quiet.radiusM<walk.radiusM);
  assert.equal(crouch.posture,'crouched');assert.equal(K.signature({speed:5.6}).posture,'sprinting');
  assert.deepEqual(K.signature({speed:3.2,volume:0}),K.signature({speed:3.2,volume:1}));
  assert.equal(K.signature({speed:0}).radiusM,0);
  assert.equal(K.signature({speed:3.2,noiseMultiplier:0}).radiusM,0);
});

test('losing line of sight searches the last observed position instead of a moving player',()=>{
  const acquired=seePlayer();assert.equal(acquired.observers[0].phase,'combat');
  const lost=tick(acquired.state,{player:[80,40]});
  assert.deepEqual(lost.observers[0].lastKnown,[10,0]);
  assert.deepEqual(lost.observers[0].searchTarget,[10,0]);
  assert.equal(lost.observers[0].canTrackCurrent,false);assert.equal(lost.observers[0].canAttack,false);
  assert.equal(lost.observers[0].reason,'last-known-position');
  near(lost.observers[0].memoryRemaining,4.75);
});

test('heard gunfire stores its fixed emission position, never the later camera position',()=>{
  const shot={id:'shot:1',kind:'gunfire',position:[2,3],radiusM:45};
  let result=tick(K.initial(),{player:[30,30],noises:[shot]});
  assert.deepEqual(result.observers[0].lastKnown,[2,3]);
  assert.equal(result.observers[0].lastSense,'sound');assert.equal(result.observers[0].soundId,'shot:1');
  result=tick(result.state,{player:[200,150]});
  assert.deepEqual(result.observers[0].searchTarget,[2,3]);
  assert.equal(result.observers[0].canTrackCurrent,false);
});

test('replaying an event cannot renew its sound or memory after expiry',()=>{
  const shot={id:'shot:one-actual-trigger',kind:'gunfire',position:[1,0],radiusM:50};
  let result={state:K.initial()};
  for(let i=0;i<48;i++)result=tick(result.state,{noises:[shot]});
  assert.equal(result.state.sounds.length,0);assert.equal(result.observers[0].lastKnown,null);
  assert.equal(result.observers[0].memoryRemaining,0);assert.equal(result.observers[0].phase,'unaware');
  assert.equal(result.state.seenSounds.length,1);
});

test('a sound identity cannot move, change radius or change kind while retained',()=>{
  const shot={id:'shot:1',kind:'gunfire',position:[1,0],radiusM:50};
  const result=tick(K.initial(),{noises:[shot]});
  for(const change of [{position:[30,0]},{radiusM:10},{kind:'decoy'}]){
    assert.throws(()=>tick(result.state,{noises:[{...shot,...change}]}),/changed its emission/);
    assert.throws(()=>tick(K.initial(),{noises:[shot,{...shot,...change}]}),/changed its emission/);
  }
});

test('equipment noise multiplier changes the actual hearing envelope',()=>{
  const shot={id:'shot:1',kind:'gunfire',position:[20,0],radiusM:45};
  const loud=tick(K.initial(),{noises:[shot]});
  const silenced=tick(K.initial(),{noises:[{...shot,noiseMultiplier:.25}]});
  assert.equal(loud.observers[0].heard,true);assert.equal(silenced.observers[0].heard,false);
  assert.equal(silenced.observers[0].lastKnown,null);
});

test('footsteps cause investigation without confirming combat by themselves',()=>{
  let result={state:K.initial()};
  for(let i=0;i<32;i++)result=tick(result.state,{player:[100,100],noises:[
    {id:'step:'+i,kind:'footstep',position:[1,0],radiusM:16,strength:1}]});
  assert.equal(result.observers[0].phase,'search');assert.equal(result.observers[0].confirmed,false);
  assert.equal(result.observers[0].suspicion,K.CONFIG.movementAlertCap);
  assert.deepEqual(result.observers[0].searchTarget,[1,0]);assert.equal(result.observers[0].canAttack,false);
});

test('unknown visual evidence never tracks or authorises an attack',()=>{
  const acquired=seePlayer();
  const result=tick(acquired.state,{player:[90,90],observers:[guard('guard',{visual:'unknown'})]});
  assert.equal(result.observers[0].canTrackCurrent,false);assert.equal(result.observers[0].canAttack,false);
  assert.deepEqual(result.observers[0].lastKnown,[10,0]);
  assert.equal(result.observers[0].reason,'unknown-line-of-sight');
});

test('existing optical hack blinds only its electronic target while preserving alerts and memory',()=>{
  const observers=[guard('drone',{electronic:true,visual:'visible'}),guard('human',{visual:'visible'})];
  const acquired=seePlayer(observers);
  const result=tick(acquired.state,{player:[25,0],observers:[
    guard('drone',{electronic:true,visual:'visible',effects:{blind:7}}),
    guard('human',{visual:'visible',effects:{blind:7}})]});
  const drone=result.observers.find(row=>row.id==='drone'),human=result.observers.find(row=>row.id==='human');
  assert.equal(drone.phase,'combat');assert.equal(drone.canTrackCurrent,false);
  assert.deepEqual(drone.lastKnown,[10,0]);assert.equal(drone.reason,'existing-optics-disabled');
  assert.equal(human.canTrackCurrent,true);assert.deepEqual(human.lastKnown,[25,0]);
  assert.equal(result.energyCost,0);assert(!('energy' in result.state));
  assert.equal(drone.effects.blind,7); // v42 remains the timer owner.
});

test('existing weapon jam and motor lock retain visual contact and the existing timer owner',()=>{
  const acquired=seePlayer([guard('drone',{electronic:true,visual:'visible'})]);
  const result=tick(acquired.state,{player:[12,0],observers:[
    guard('drone',{electronic:true,visual:'visible',effects:{jam:6,lock:5}})]});
  const row=result.observers[0];assert.equal(row.canTrackCurrent,true);assert.equal(row.canAttack,false);
  assert.equal(row.canMove,false);assert.deepEqual(row.lastKnown,[12,0]);assert.equal(row.phase,'combat');
  assert.deepEqual(row.effects,{blind:0,jam:6,lock:5});
});

test('a decoy can redirect a blind search without giving access to the player position',()=>{
  const acquired=seePlayer();
  const result=tick(acquired.state,{player:[90,90],noises:[
    {id:'decoy:1',kind:'decoy',position:[-4,3],radiusM:30}]});
  assert.deepEqual(result.observers[0].searchTarget,[-4,3]);
  assert.equal(result.observers[0].canTrackCurrent,false);assert.equal(result.observers[0].confirmed,true);
});

test('a known visual contact takes precedence over simultaneous sound and does not lose its source',()=>{
  const result=tick(K.initial(),{observers:[guard('guard',{visual:'visible'})],noises:[
    {id:'decoy:1',kind:'decoy',position:[-4,3],radiusM:30}]});
  assert.deepEqual(result.observers[0].lastKnown,[10,0]);assert.equal(result.observers[0].lastSense,'visual');
  assert.equal(result.observers[0].soundId,null);
});

test('zero acoustic transmission and range edges do not create sound evidence',()=>{
  const noise={id:'noise:1',kind:'gunfire',position:[10,0],radiusM:10};
  assert.equal(tick(K.initial(),{noises:[noise]}).observers[0].heard,false);
  assert.equal(tick(K.initial(),{observers:[guard('guard',{acousticTransmission:0})],
    noises:[{...noise,radiusM:20}]}).observers[0].heard,false);
});

test('pure stepping leaves the previous state, observations and source positions unchanged',()=>{
  const before=seePlayer(),input=frame({noises:[{id:'shot:1',kind:'gunfire',position:[3,2],radiusM:40}]});
  const encoded=JSON.stringify([before.state,input]),result=K.advance(before.state,input);
  assert.equal(JSON.stringify([before.state,input]),encoded);
  result.observers[0].lastKnown[0]=999;assert.deepEqual(before.state.tracks[0].lastKnown,[10,0]);
  assert.deepEqual(input.noises[0].position,[3,2]);
  assert.notEqual(result.state.tracks[0].lastKnown,result.observers[0].lastKnown);
});

test('fixed evidence gives matching perception across frame partitions and observer ordering',()=>{
  function simulate(dt,count,reverse){
    let result={state:K.initial()};
    for(let i=0;i<count;i++)result=tick(result.state,{dt,observers:
      (reverse?[guard('z',{visual:'visible'}),guard('a',{visual:'visible'})]:
        [guard('a',{visual:'visible'}),guard('z',{visual:'visible'})])});
    return result;
  }
  const a=simulate(.1,10,false),b=simulate(.25,4,true);
  near(a.state.clock,b.state.clock);
  for(let i=0;i<2;i++){
    near(a.observers[i].suspicion,b.observers[i].suspicion);
    assert.deepEqual(a.observers[i].lastKnown,b.observers[i].lastKnown);
    assert.equal(a.observers[i].phase,b.observers[i].phase);
  }
});

test('memory and event budgets stay bounded and missing observers are released',()=>{
  let result={state:K.initial()};
  for(let i=0;i<300;i++)result=tick(result.state,{noises:[
    {id:'step:'+i,kind:'footstep',position:[1,0],radiusM:16}]});
  assert.equal(result.state.seenSounds.length,256);assert(result.state.sounds.length<=2);
  result=tick(result.state,{observers:[]});assert.equal(result.state.tracks.length,0);
  assert.throws(()=>tick(K.initial(),{observers:Array.from({length:257},(_,i)=>guard('unit:'+i))}),/budget/);
  assert.throws(()=>tick(K.initial(),{observers:[guard(),guard()]}),/duplicate observer/);
});

test('malformed observations, timers, posture and unbounded frame times fail explicitly',()=>{
  for(const extra of [{dt:NaN},{dt:1},{dt:-1},{player:[Infinity,0]},
    {observers:[guard('guard',{visual:true})]},{observers:[guard('guard',{effects:{blind:Infinity}})]},
    {noises:[{id:'unsafe space',kind:'gunfire',position:[0,0],radiusM:20}]}])
    assert.throws(()=>tick(K.initial(),extra),/Infiltration/);
  assert.throws(()=>K.signature({speed:3.2,crouched:1}),/posture/);
  assert.throws(()=>K.signature({speed:3.2,noiseMultiplier:-1}),/noise multiplier/);
});
