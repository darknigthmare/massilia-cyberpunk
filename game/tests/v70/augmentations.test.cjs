'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const K=require('../../src/v70/augmentations-core.js');
const near=(actual,expected)=>assert(Math.abs(actual-expected)<1e-9,`${actual} != ${expected}`);
const context=(extra={})=>({energy:100,health:100,onFoot:true,paused:false,channeling:false,driving:false,cyberspace:false,tension:0,...extra});
const frame=(extra={})=>({paused:false,health:100,onFoot:true,...extra});
const activate=(id,state=K.initial(),extra={})=>K.activate(state,id,context(extra));
const frozen=value=>{if(value&&typeof value==='object'){Object.freeze(value);for(const child of Object.values(value))frozen(child);}return value;};

test('the browser core loads without DOM, storage, wall clocks or a second resource',()=>{
  const sandbox=vm.createContext({});
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../../src/v70/augmentations-core.js'),'utf8'),sandbox);
  assert.equal(vm.runInContext('__SOMA_AUG70_CORE__.version',sandbox),'0.70.0');
  const state=K.initial();assert(!('energy' in state));assert(!('tension' in state));
  assert.equal(K.validatePersistence(undefined),true);assert.deepEqual(K.restore(undefined),state);
  assert.equal(state.stats.activations,0);assert.equal(state.trace,0);
});

test('all three original abilities debit the existing energy only through an activation proposal',()=>{
  for(const [id,cost,duration,cooldown] of [['scan',12,5,12],['barrier',28,4,24],['focus',24,5,20]]){
    const before=frozen(K.initial()),resource=frozen(context()),snapshot=JSON.stringify([before,resource]);
    const result=K.activate(before,id,resource);
    assert.equal(result.accepted,true);assert.equal(result.energyCost,cost);
    assert.equal(result.state.active[id],duration);assert.equal(result.state.cooldowns[id],cooldown);
    assert.equal(result.state.stats.activations,1);assert.equal(result.state.stats[id],1);
    assert.equal(result.state.selected,id);assert.equal(JSON.stringify([before,resource]),snapshot);
    assert.equal(resource.energy,100);assert.equal(resource.tension,0);
  }
});

test('scan reports a timed information window without weapon, damage or hacking changes',()=>{
  const start=activate('scan').state,mod=K.modifiers(start);
  assert.equal(mod.scanActive,true);assert.equal(mod.blocksHacking,false);
  assert.equal(mod.spread,1);assert.equal(mod.recoil,1);
  assert.equal(K.mitigate(start,20).damage,20);
  assert.equal(K.modifiers(K.advance(start,4.9,frame())).scanActive,true);
  assert.equal(K.modifiers(K.advance(start,5,frame())).scanActive,false);
  assert.equal(K.advance(start,5,frame()).cooldowns.scan,7);
});

test('barrier reduces actual damage by 55 percent until its finite absorption budget is exhausted',()=>{
  const start=activate('barrier').state,hit=K.mitigate(start,20);
  near(hit.damage,9);near(hit.absorbed,11);near(hit.state.barrierRemaining,29);
  assert.equal(start.barrierRemaining,40);
  const second=K.mitigate(hit.state,100);
  near(second.absorbed,29);near(second.damage,71);near(second.state.stats.damageAbsorbed,40);
  assert.equal(second.state.active.barrier,0);assert.equal(second.state.barrierRemaining,0);
  assert.equal(K.mitigate(second.state,10).damage,10);
  assert.equal(second.state.cooldowns.barrier,24);
});

test('barrier expiry removes protection and remaining budget without clearing cooldown',()=>{
  const expired=K.advance(activate('barrier').state,4,frame());
  assert.equal(expired.active.barrier,0);assert.equal(expired.barrierRemaining,0);
  assert.equal(expired.cooldowns.barrier,20);assert.equal(K.mitigate(expired,20).absorbed,0);
});

test('focus changes spread and recoil only, without global time scaling',()=>{
  const start=activate('focus').state,mod=K.modifiers(start);
  near(mod.spread,.65);near(mod.recoil,.65);assert.equal(mod.blocksHacking,true);
  assert(!('timeScale' in mod));assert(!('damageMultiplier' in mod));
  assert.equal(K.mitigate(start,20).damage,20);
  const expired=K.advance(start,5,frame());assert.equal(K.modifiers(expired).spread,1);
  assert.equal(expired.cooldowns.focus,15);
});

test('an existing quickhack or takedown channel refuses every new active augmentation',()=>{
  for(const id of Object.keys(K.ABILITIES)){
    const result=activate(id,K.initial(),{channeling:true});
    assert.equal(result.accepted,false);assert.equal(result.reason,'channeling');
    assert.equal(result.energyCost,0);assert.equal(result.tensionDelta,0);assert.deepEqual(result.state,K.initial());
  }
  assert.equal(K.modifiers(activate('barrier').state).blocksHacking,true);
  assert.equal(K.modifiers(activate('focus').state).blocksHacking,true);
  assert.equal(K.modifiers(activate('scan').state).blocksHacking,false);
});

test('invalid gameplay modes refuse activation without spending or inventing progress',()=>{
  for(const [change,reason] of [[{paused:true},'paused'],[{health:0},'dead'],[{onFoot:false},'not-on-foot'],
    [{driving:true},'driving'],[{cyberspace:true},'cyberspace'],[{tension:95},'neural-instability'],[{energy:11},'insufficient-energy']]){
    const result=activate('scan',K.initial(),change);
    assert.equal(result.accepted,false);assert.equal(result.reason,reason);assert.deepEqual(result.state,K.initial());
    assert.equal(result.energyCost,0);assert.equal(result.tensionDelta,0);
  }
  for(const id of ['unknown','__proto__','constructor',{},null]){
    const result=activate(id);assert.equal(result.accepted,false);assert.equal(result.reason,'unknown-augmentation');
  }
});

test('a buff cannot be refreshed while active or recast during its remaining cooldown',()=>{
  const start=activate('scan').state;
  assert.equal(activate('scan',start).reason,'already-active');
  const expired=K.advance(start,5,frame());assert.equal(activate('scan',expired).reason,'cooldown');
  const ready=K.advance(start,12,frame());assert.equal(activate('scan',ready).accepted,true);
});

test('neural load increases explicit tension risk and blocks overload without spending energy',()=>{
  const low=activate('barrier'),loaded=K.initial();loaded.trace=60;
  const high=activate('barrier',loaded);
  assert(high.tensionDelta>low.tensionDelta);assert.equal(high.state.trace,92);
  assert.equal(K.modifiers(high.state).neuralRisk,'high');
  const overload=activate('scan',high.state);
  assert.equal(overload.accepted,false);assert.equal(overload.reason,'neural-overload');assert.equal(overload.energyCost,0);
  assert.deepEqual(overload.state,high.state);
  const cooled=K.advance(high.state,2,frame());near(cooled.trace,80);
  assert.equal(activate('scan',cooled).accepted,true);
});

test('multiple augmentations share external energy and increase neural risk rather than a new reserve',()=>{
  let state=K.initial(),energy=100,tension=0;
  for(const id of ['scan','barrier','focus']){
    const result=activate(id,state,{energy,tension});assert.equal(result.accepted,true);
    energy-=result.energyCost;tension+=result.tensionDelta;state=result.state;
  }
  assert.equal(energy,36);assert.equal(state.trace,72);assert(tension>0);
  assert.equal(state.stats.activations,3);assert.equal(K.modifiers(state).scanActive,true);
  assert.equal(K.modifiers(state).focusActive,true);assert.equal(K.modifiers(state).barrierActive,true);
});

test('paused game time freezes timers and trace and active time advances by the supplied game seconds',()=>{
  const start=frozen(activate('focus').state),same=K.advance(start,30,frame({paused:true}));
  assert.deepEqual(same,start);assert.notEqual(same,start);assert.notEqual(same.cooldowns,start.cooldowns);
  const whole=K.advance(start,1,frame());let split=start;
  for(let i=0;i<4;i++)split=K.advance(split,.25,frame());
  near(split.active.focus,whole.active.focus);near(split.trace,whole.trace);near(split.cooldowns.focus,whole.cooldowns.focus);
});

test('death and leaving the on-foot mode cancel all buffs without resetting waits or load',()=>{
  let start=activate('barrier').state;start=activate('focus',start).state;
  for(const change of [{health:0},{onFoot:false}]){
    const next=K.advance(start,0,frame(change));assert.deepEqual(next.active,{scan:0,barrier:0,focus:0});
    assert.equal(next.barrierRemaining,0);assert.deepEqual(next.cooldowns,start.cooldowns);assert.equal(next.trace,start.trace);
  }
});

test('save/reload drops every active buff but preserves cooldowns, neural risk, selection and statistics',()=>{
  let state=activate('scan').state;state=activate('barrier',state).state;state=K.mitigate(state,10).state;
  const stored=frozen(K.serialize(state));assert.equal(K.validatePersistence(stored),true);
  assert(!('active' in stored));assert(!('barrierRemaining' in stored));
  const restored=K.restore(JSON.parse(JSON.stringify(stored)));
  assert.deepEqual(restored.active,{scan:0,barrier:0,focus:0});assert.equal(restored.barrierRemaining,0);
  assert.deepEqual(K.serialize(restored),stored);assert.equal(activate('barrier',restored).reason,'cooldown');
  near(restored.stats.damageAbsorbed,5.5);assert.equal(restored.selected,'barrier');
});

test('fresh and selected states are independent and all public transitions avoid mutation',()=>{
  const a=K.initial(),b=K.initial();a.stats.scan=2;assert.equal(b.stats.scan,0);
  const start=frozen(activate('barrier').state),snapshot=JSON.stringify(start);
  K.mitigate(start,30);K.advance(start,.2,frame());K.modifiers(start);K.serialize(start);K.select(start,'focus');
  assert.equal(JSON.stringify(start),snapshot);assert.equal(K.select(start,'focus').selected,'focus');
  assert.throws(()=>K.select(start,'constructor'),/unknown selected/);
});

test('statistics saturate without integer wraparound or non-finite output',()=>{
  const state=K.initial();for(const k of ['activations','scan','barrier','focus','damageAbsorbed'])state.stats[k]=K.CONFIG.maxStat;
  const result=activate('barrier',state);assert.equal(result.state.stats.activations,K.CONFIG.maxStat);
  assert.equal(result.state.stats.barrier,K.CONFIG.maxStat);
  const hit=K.mitigate(result.state,100);assert.equal(hit.state.stats.damageAbsorbed,K.CONFIG.maxStat);
  assert.equal(K.validatePersistence(K.serialize(hit.state)),true);
});

test('strict persistence refuses malformed present domains instead of replacing them with fresh state',()=>{
  const bad=[];
  for(const value of [null,[],new Date(),0,'',true])bad.push(value);
  bad.push({...K.serialize(K.initial()),extra:true});
  const missing=K.serialize(K.initial());delete missing.trace;bad.push(missing);
  for(const change of [{schema:'future'},{selected:'constructor'},{trace:NaN},{trace:Infinity},{trace:-1},{trace:101},{trace:'4'}])bad.push({...K.serialize(K.initial()),...change});
  for(const value of [-1,12.1,Infinity,'2',null]){const row=K.serialize(K.initial());row.cooldowns.scan=value;bad.push(row);}
  for(const value of [-1,.5,1e9+1,NaN,'1']){const row=K.serialize(K.initial());row.stats.scan=value;bad.push(row);}
  const nested=K.serialize(K.initial());nested.stats.unexpected=0;bad.push(nested);
  const polluted=K.serialize(K.initial());polluted.cooldowns=JSON.parse('{"scan":0,"barrier":0,"focus":0,"__proto__":{}}');bad.push(polluted);
  for(const value of bad){assert.throws(()=>K.validatePersistence(value),TypeError);assert.throws(()=>K.restore(value),TypeError);}
});

test('strict validation refuses inherited, accessor, symbol and non-enumerable fields without executing getters',()=>{
  const good=K.serialize(K.initial()),inherited=Object.assign(Object.create({hidden:true}),good);
  assert.throws(()=>K.validatePersistence(inherited),/plain record/);
  let calls=0;const accessor={...good};Object.defineProperty(accessor,'trace',{enumerable:true,get(){calls++;return 0;}});
  assert.throws(()=>K.validatePersistence(accessor),/accessor fields/);assert.equal(calls,0);
  const symbol={...good,[Symbol('hidden')]:0};assert.throws(()=>K.validatePersistence(symbol),/unknown/);
  const hidden={...good};Object.defineProperty(hidden,'trace',{value:0,enumerable:false});assert.throws(()=>K.validatePersistence(hidden),/fields/);
  assert.equal(K.validatePersistence(Object.assign(Object.create(null),good)),true);
});

test('runtime and external inputs reject NaN, coercion and contradictory barrier states',()=>{
  for(const input of [NaN,Infinity,-1,'1',null,61])assert.throws(()=>K.advance(K.initial(),input,frame()),TypeError);
  for(const input of [NaN,Infinity,-1,'1',null,K.CONFIG.maxDamage+1])assert.throws(()=>K.mitigate(K.initial(),input),TypeError);
  for(const change of [{energy:NaN},{energy:'100'},{health:Infinity},{tension:-1},{onFoot:1},{paused:'false'},{channeling:null}])
    assert.throws(()=>activate('scan',K.initial(),change),TypeError);
  const active=K.initial();active.active.barrier=1;active.cooldowns.barrier=5;assert.throws(()=>K.modifiers(active),/budget disagree/);
  const budget=K.initial();budget.barrierRemaining=1;assert.throws(()=>K.modifiers(budget),/budget disagree/);
  const impossible=K.initial();impossible.active.scan=1;assert.throws(()=>K.serialize(impossible),/exceeds its cooldown/);
});
