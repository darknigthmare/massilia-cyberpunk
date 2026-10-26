/* Original active augmentations for the existing campaign.
 *
 * This pure core owns timers, a finite absorption budget and neural load.
 * Energy and tension belong to the existing v42 cyberdeck/player: activate()
 * returns a debit proposal without modifying that external resource. The
 * adapter must atomically apply energyCost/tensionDelta and the returned state.
 * Neural trace is a risk meter, never a second energy reserve. It dissipates
 * at six points per second of unpaused game time and survives a save/reload.
 *
 * No DOM, wall clock, random numbers, geometry, global time dilation or saves.
 * advance() returns a state. activate()/mitigate() return {state, ...result}.
 * serialize() deliberately removes all active buffs; cooldowns remain intact.
 */
(function(root){
  'use strict';
  const SCHEMA='soma-massilia/augmentations/1';
  const IDS=Object.freeze(['scan','barrier','focus']);
  const ABILITIES=Object.freeze({
    scan:Object.freeze({id:'scan',label:'Écho de trame',cost:12,duration:5,cooldown:12,traceGain:16,tension:1}),
    barrier:Object.freeze({id:'barrier',label:'Rempart cortical',cost:28,duration:4,cooldown:24,traceGain:32,tension:3}),
    focus:Object.freeze({id:'focus',label:'Ancrage réflexe',cost:24,duration:5,cooldown:20,traceGain:24,tension:2})
  });
  const CONFIG=Object.freeze({traceMax:100,traceDecayPerSecond:6,tensionActivationLimit:95,
    barrierReduction:.55,barrierBudget:40,focusSpread:.65,focusRecoil:.65,
    maxStat:1e9,maxAdvanceSeconds:60,maxDamage:1e9});
  const PERSISTED=Object.freeze(['schema','selected','cooldowns','trace','stats']);
  const RUNTIME=Object.freeze([...PERSISTED,'active','barrierRemaining']);
  const STAT_KEYS=Object.freeze(['activations','scan','barrier','focus','damageAbsorbed']);
  const fail=message=>{throw new TypeError('Augmentations: '+message);};
  const own=(value,key)=>Object.hasOwn(value,key);
  function exact(value,keys,name){
    if(value===null||typeof value!=='object'||Array.isArray(value)||
      ![Object.prototype,null].includes(Object.getPrototypeOf(value)))fail(name+' must be a plain record');
    const descriptors=Object.getOwnPropertyDescriptors(value),found=Reflect.ownKeys(descriptors);
    if(found.length!==keys.length||found.some(key=>typeof key!=='string'||!keys.includes(key))||
      keys.some(key=>!own(descriptors,key)||!own(descriptors[key],'value')||!descriptors[key].enumerable))
      fail(name+' has missing, unknown or accessor fields');
    return value;
  }
  function number(value,min,max,name,integer=false){
    if(typeof value!=='number'||!Number.isFinite(value)||value<min||value>max||integer&&!Number.isInteger(value))
      fail(name+' outside bounds');
    return value;
  }
  function boolean(value,name){if(typeof value!=='boolean')fail(name+' must be boolean');return value;}
  function ability(id){return typeof id==='string'&&own(ABILITIES,id)?ABILITIES[id]:null;}
  function common(value){
    if(value.schema!==SCHEMA)fail('unknown schema');
    if(!ability(value.selected))fail('unknown selected augmentation');
    exact(value.cooldowns,IDS,'cooldowns');
    for(const id of IDS)number(value.cooldowns[id],0,ABILITIES[id].cooldown,id+' cooldown');
    number(value.trace,0,CONFIG.traceMax,'neural trace');
    exact(value.stats,STAT_KEYS,'stats');
    for(const key of STAT_KEYS)number(value.stats[key],0,CONFIG.maxStat,key+' statistic',key!=='damageAbsorbed');
  }
  function checked(value){
    exact(value,RUNTIME,'runtime state');common(value);exact(value.active,IDS,'active timers');
    for(const id of IDS){
      number(value.active[id],0,ABILITIES[id].duration,id+' active duration');
      if(value.active[id]>value.cooldowns[id]+1e-8)fail('active duration exceeds its cooldown');
    }
    number(value.barrierRemaining,0,CONFIG.barrierBudget,'remaining barrier budget');
    if((value.active.barrier>0)!==(value.barrierRemaining>0))fail('barrier timer and budget disagree');
    return value;
  }
  function validatePersistence(value){
    // Absence is the only legacy default. null and malformed present domains
    // must not silently discard waits or progress during an import.
    if(value===undefined)return true;
    exact(value,PERSISTED,'persisted state');common(value);return true;
  }
  function copy(value){
    return{schema:SCHEMA,selected:value.selected,cooldowns:{...value.cooldowns},trace:value.trace,
      stats:{...value.stats},active:{...value.active},barrierRemaining:value.barrierRemaining};
  }
  function initial(){
    return{schema:SCHEMA,selected:'scan',cooldowns:{scan:0,barrier:0,focus:0},trace:0,
      stats:{activations:0,scan:0,barrier:0,focus:0,damageAbsorbed:0},
      active:{scan:0,barrier:0,focus:0},barrierRemaining:0};
  }
  function restore(value){
    validatePersistence(value);
    if(value===undefined)return initial();
    return{schema:SCHEMA,selected:value.selected,cooldowns:{...value.cooldowns},trace:value.trace,
      stats:{...value.stats},active:{scan:0,barrier:0,focus:0},barrierRemaining:0};
  }
  function serialize(value){
    checked(value);
    return{schema:SCHEMA,selected:value.selected,cooldowns:{...value.cooldowns},trace:value.trace,stats:{...value.stats}};
  }
  function select(value,id){
    checked(value);if(!ability(id))fail('unknown selected augmentation');
    const next=copy(value);next.selected=id;return next;
  }
  function activationContext(value){
    exact(value,['energy','health','onFoot','paused','channeling','driving','cyberspace','tension'],'activation context');
    number(value.energy,0,1000,'external energy');number(value.health,0,10000,'health');number(value.tension,0,100,'tension');
    for(const key of ['onFoot','paused','channeling','driving','cyberspace'])boolean(value[key],key);
    return value;
  }
  function activate(value,id,context){
    checked(value);const c=activationContext(context),def=ability(id);
    const rejected=reason=>({accepted:false,state:copy(value),energyCost:0,tensionDelta:0,reason});
    if(!def)return rejected('unknown-augmentation');
    if(c.paused)return rejected('paused');
    if(c.health<=0)return rejected('dead');
    if(c.driving)return rejected('driving');
    if(c.cyberspace)return rejected('cyberspace');
    if(!c.onFoot)return rejected('not-on-foot');
    if(c.channeling)return rejected('channeling');
    if(c.tension>=CONFIG.tensionActivationLimit)return rejected('neural-instability');
    if(value.active[id]>0)return rejected('already-active');
    if(value.cooldowns[id]>0)return rejected('cooldown');
    if(c.energy<def.cost)return rejected('insufficient-energy');
    const trace=value.trace+def.traceGain;
    if(trace>CONFIG.traceMax)return rejected('neural-overload');
    const tensionDelta=def.tension+Math.floor(trace/25);
    if(c.tension+tensionDelta>100)return rejected('neural-overload');
    const next=copy(value);next.selected=id;next.trace=trace;next.active[id]=def.duration;next.cooldowns[id]=def.cooldown;
    next.stats.activations=Math.min(CONFIG.maxStat,next.stats.activations+1);
    next.stats[id]=Math.min(CONFIG.maxStat,next.stats[id]+1);
    if(id==='barrier')next.barrierRemaining=CONFIG.barrierBudget;
    return{accepted:true,state:next,energyCost:def.cost,tensionDelta,reason:'activated'};
  }
  function advance(value,dt,context){
    checked(value);number(dt,0,CONFIG.maxAdvanceSeconds,'game time step');
    exact(context,['paused','health','onFoot'],'advance context');
    boolean(context.paused,'paused');boolean(context.onFoot,'onFoot');number(context.health,0,10000,'health');
    const next=copy(value);
    if(context.health<=0||!context.onFoot){for(const id of IDS)next.active[id]=0;next.barrierRemaining=0;}
    if(context.paused)return next;
    next.trace=Math.max(0,next.trace-CONFIG.traceDecayPerSecond*dt);
    for(const id of IDS){
      next.cooldowns[id]=Math.max(0,next.cooldowns[id]-dt);
      next.active[id]=Math.max(0,next.active[id]-dt);
    }
    if(next.active.barrier===0)next.barrierRemaining=0;
    return next;
  }
  function mitigate(value,amount){
    checked(value);number(amount,0,CONFIG.maxDamage,'incoming damage');
    const next=copy(value),absorbed=value.active.barrier>0?Math.min(value.barrierRemaining,amount*CONFIG.barrierReduction):0;
    if(absorbed>0){
      next.barrierRemaining=Math.max(0,next.barrierRemaining-absorbed);
      next.stats.damageAbsorbed=Math.min(CONFIG.maxStat,next.stats.damageAbsorbed+absorbed);
      if(next.barrierRemaining===0)next.active.barrier=0;
    }
    return{state:next,damage:amount-absorbed,absorbed};
  }
  function modifiers(value){
    checked(value);const scanActive=value.active.scan>0,barrierActive=value.active.barrier>0,focusActive=value.active.focus>0;
    return{spread:focusActive?CONFIG.focusSpread:1,recoil:focusActive?CONFIG.focusRecoil:1,
      scanActive,barrierActive,focusActive,blocksHacking:barrierActive||focusActive,
      neuralLoad:value.trace,neuralRisk:value.trace>=75?'high':value.trace>=40?'elevated':'low'};
  }
  const API=Object.freeze({version:'0.70.0',SCHEMA,ABILITIES,CONFIG,initial,restore,select,activate,advance,mitigate,modifiers,serialize,validatePersistence});
  if(typeof module==='object'&&module.exports)module.exports=API;
  root.__SOMA_AUG70_CORE__=API;
})(typeof globalThis==='object'?globalThis:this);
