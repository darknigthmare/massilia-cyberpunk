/* Perception memory for the existing combat AI, not a second combat or hacking
 * system. The adapter owns geometry, posture, actual shots, quickhack channels,
 * energy, damage and saves. This core owns only transient evidence and memory.
 *
 * initial() -> ephemeral state.
 * signature({speed,crouched,noiseMultiplier}) -> authored movement noise.
 * advance(state, {dt,player,observers,noises,movement}) -> {state,observers,hud}.
 *
 * Positions are [x,z] in one local zone. Reset with initial() on zone changes.
 * visual is 'visible'/'blocked'/'unknown', already resolved by the real cone,
 * posture and LOS61. Unknown sight is never permission to track or attack.
 * Each new sound has a unique id and a fixed emission position. Repeating its
 * id cannot move it or refresh its lifetime. Sound playback volume is not input.
 *
 * Observer effects consume the existing v42 blind/lock/jam timers. Blind affects
 * explicitly electronic optics only; jam disables weapons, not perception.
 * Hearing uses an authored radial envelope and optional acousticTransmission;
 * it is not a physical simulation of sound propagation through source buildings.
 */
(function(root){
  'use strict';
  const SCHEMA='soma-massilia/infiltration-memory/1';
  const CONFIG=Object.freeze({visualRate:1.4,hearingRate:.8,decayRate:.34,
    memorySeconds:5,combatThreshold:1,maxSuspicion:1.2,
    movementAlertCap:.95,maxObservers:256,maxSounds:64,maxStepSeconds:.25});
  const kinds=new Set(['footstep','gunfire','decoy']);
  const visuals=new Set(['visible','blocked','unknown']);
  const phases=new Set(['unaware','suspicious','search','combat']);
  const fail=message=>{throw new TypeError('Infiltration: '+message);};
  const record=value=>value!==null&&typeof value==='object'&&!Array.isArray(value);
  function number(value,min,max,name){
    if(typeof value!=='number'||!Number.isFinite(value)||value<min||value>max)fail(name+' outside bounds');
    return value;
  }
  function point(value,name){
    if(!Array.isArray(value)||value.length!==2)fail(name+' must be [x,z]');
    return value.map(v=>number(v,-1e7,1e7,name));
  }
  function identity(value,name){
    if(typeof value!=='string'||!/^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,159}$/.test(value))fail('invalid '+name);
    return value;
  }
  function boolean(value,name){if(typeof value!=='boolean')fail('invalid '+name);return value;}

  function initial(){return{schema:SCHEMA,clock:0,tracks:[],sounds:[],seenSounds:[]};}

  function signature({speed=0,crouched=false,noiseMultiplier=1}={}){
    number(speed,0,50,'movement speed');boolean(crouched,'posture');
    number(noiseMultiplier,0,4,'noise multiplier');
    // The engine's ordinary speeds are 1.8/3.2/5.6 m/s. This is a gameplay
    // envelope, explicitly independent of audio volume and not a decibel claim.
    const level=speed<.05?0:Math.min(1,speed/5.6*(crouched?.28:1)*noiseMultiplier);
    const radiusM=level===0?0:2+22*level;
    return{level,radiusM,posture:crouched?'crouched':speed>=4.5?'sprinting':speed>=.05?'walking':'still'};
  }

  function sound(value,clock){
    if(!record(value)||!kinds.has(value.kind))fail('invalid sound event');
    const noiseMultiplier=number(value.noiseMultiplier??1,0,4,'sound noise multiplier');
    return{id:identity(value.id,'sound id'),kind:value.kind,position:point(value.position,'sound position'),
      radiusM:number(value.radiusM,0,500,'sound radius')*noiseMultiplier,
      strength:number(value.strength??1,0,1,'sound strength'),
      duration:number(value.duration??(value.kind==='gunfire'?2.4:.4),.01,5,'sound duration'),
      emittedAt:clock};
  }

  function checkedState(value){
    if(!record(value)||value.schema!==SCHEMA||!Array.isArray(value.tracks)||!Array.isArray(value.sounds)||
      !Array.isArray(value.seenSounds)||value.seenSounds.length>256||
      value.tracks.length>CONFIG.maxObservers||value.sounds.length>CONFIG.maxSounds)fail('invalid ephemeral state');
    number(value.clock,0,1e12,'clock');
    const tracks=new Map(),sounds=new Map();
    for(const row of value.tracks){
      if(!record(row)||!phases.has(row.phase)||typeof row.confirmed!=='boolean'||
        !['visual','sound',null].includes(row.lastSense))fail('invalid observer memory');
      const id=identity(row.id,'observer id');
      if(tracks.has(id))fail('duplicate observer memory');
      number(row.suspicion,0,CONFIG.maxSuspicion,'suspicion');
      number(row.memoryRemaining,0,CONFIG.memorySeconds,'memory time');
      if(row.lastKnown!==null)point(row.lastKnown,'last known position');
      if(row.soundId!==null)identity(row.soundId,'remembered sound id');
      tracks.set(id,row);
    }
    for(const row of value.sounds){
      if(!record(row))fail('invalid retained sound');
      const id=identity(row.id,'retained sound id');
      if(sounds.has(id)||!kinds.has(row.kind))fail('invalid retained sound identity');
      point(row.position,'retained sound position');number(row.radiusM,0,2000,'retained sound radius');
      number(row.strength,0,1,'retained sound strength');number(row.duration,.01,5,'retained sound duration');
      number(row.emittedAt,0,value.clock,'sound time');
      sounds.set(id,row);
    }
    const seen=new Set(value.seenSounds.map(id=>identity(id,'seen sound id')));
    if(seen.size!==value.seenSounds.length||[...sounds.keys()].some(id=>!seen.has(id)))fail('invalid sound replay history');
    return{tracks,sounds,seen};
  }

  function observer(value){
    if(!record(value)||!visuals.has(value.visual))fail('invalid observer observation');
    const seed=value.seed??{},effects=value.effects??{};
    if(!record(seed)||!record(effects))fail('invalid observer seed or effects');
    if(seed.phase!==undefined&&!phases.has(seed.phase))fail('invalid seeded phase');
    return{id:identity(value.id,'observer id'),position:point(value.position,'observer position'),
      visual:value.visual,electronic:boolean(value.electronic??false,'electronic classification'),
      hearingRange:number(value.hearingRange??0,0,500,'hearing range'),
      acousticTransmission:number(value.acousticTransmission??1,0,1,'acoustic transmission'),
      seed:{suspicion:number(seed.suspicion??0,0,CONFIG.maxSuspicion,'seeded suspicion'),
        phase:seed.phase??'unaware',memoryRemaining:number(seed.memoryRemaining??0,0,CONFIG.memorySeconds,'seeded memory')},
      effects:{blind:number(effects.blind??0,0,3600,'optical effect'),
        lock:number(effects.lock??0,0,3600,'motor effect'),jam:number(effects.jam??0,0,3600,'weapon effect')}};
  }

  function advance(previous,frame){
    const checked=checkedState(previous);
    if(!record(frame)||!Array.isArray(frame.observers)||frame.observers.length>CONFIG.maxObservers||
      !Array.isArray(frame.noises??[])||(frame.noises??[]).length>CONFIG.maxSounds)fail('invalid frame or budget');
    const dt=number(frame.dt,0,CONFIG.maxStepSeconds,'frame duration'),player=point(frame.player,'player position');
    const clock=number(previous.clock+dt,0,1e12,'advanced clock'),rows=frame.observers.map(observer),ids=new Set();
    for(const row of rows){if(ids.has(row.id))fail('duplicate observer in frame');ids.add(row.id);}
    // Expire before insertion. Events repeated during their lifetime are
    // immutable. A bounded history of the 256 most recent ids also prevents a
    // repeated event from being restarted after expiry. The adapter allocates a
    // unique id for every actual new shot/step and resets on a zone change.
    const sounds=new Map([...checked.sounds].filter(([,row])=>clock-row.emittedAt<row.duration));
    const seen=new Set(checked.seen);
    for(const value of frame.noises??[]){
      const next=sound(value,previous.clock),old=checked.sounds.get(next.id)??sounds.get(next.id);
      if(old){
        if(old.kind!==next.kind||old.position.some((v,i)=>v!==next.position[i])||old.radiusM!==next.radiusM||
          old.strength!==next.strength||old.duration!==next.duration)fail('a sound id changed its emission');
        continue;
      }
      if(seen.has(next.id))continue;
      seen.add(next.id);
      if(clock-next.emittedAt<next.duration)sounds.set(next.id,next);
    }
    if(sounds.size>CONFIG.maxSounds)fail('active sound budget exceeded');
    while(seen.size>256){
      const victim=[...seen].find(id=>!sounds.has(id));
      if(victim===undefined)fail('sound replay history budget exceeded');
      seen.delete(victim);
    }
    const results=[];
    for(const row of rows){
      const prior=checked.tracks.get(row.id);
      let suspicion=prior?.suspicion??row.seed.suspicion,
        memoryRemaining=Math.max(0,(prior?.memoryRemaining??row.seed.memoryRemaining)-dt),
        confirmed=prior?.confirmed??row.seed.phase==='combat',
        lastKnown=prior?.lastKnown?.slice()??null,lastSense=prior?.lastSense??null,soundId=prior?.soundId??null;
      const blind=row.electronic&&row.effects.blind>0,visible=row.visual==='visible'&&!blind;
      let strongest=null;
      for(const event of sounds.values()){
        const distance=Math.hypot(event.position[0]-row.position[0],event.position[1]-row.position[1]);
        const radius=Math.min(event.radiusM,row.hearingRange);
        if(radius<=0||distance>=radius)continue;
        const audibility=event.strength*row.acousticTransmission*(1-distance/radius);
        if(audibility<=0)continue;
        if(!strongest||audibility>strongest.audibility||audibility===strongest.audibility&&event.id<strongest.event.id)
          strongest={event,audibility};
      }
      if(visible){
        suspicion=Math.min(CONFIG.maxSuspicion,suspicion+dt*CONFIG.visualRate);
        memoryRemaining=CONFIG.memorySeconds;lastKnown=player.slice();lastSense='visual';soundId=null;
        if(suspicion>=CONFIG.combatThreshold)confirmed=true;
      }else if(strongest){
        const event=strongest.event,cap=event.kind==='gunfire'||confirmed?CONFIG.maxSuspicion:CONFIG.movementAlertCap;
        suspicion=Math.min(Math.max(cap,suspicion),suspicion+dt*CONFIG.hearingRate*strongest.audibility);
        if(event.kind==='gunfire'&&suspicion>=CONFIG.combatThreshold)confirmed=true;
        memoryRemaining=CONFIG.memorySeconds;lastKnown=event.position.slice();lastSense='sound';soundId=event.id;
      }else suspicion=Math.max(0,suspicion-dt*CONFIG.decayRate);
      if(memoryRemaining===0){lastKnown=null;lastSense=null;soundId=null;confirmed=false;}
      const phase=confirmed&&memoryRemaining>0?'combat':!visible&&lastKnown&&memoryRemaining>0?'search':
        suspicion>.1?'suspicious':'unaware';
      const canTrackCurrent=visible,canAttack=visible&&confirmed&&!(row.electronic&&row.effects.jam>0);
      results.push({id:row.id,suspicion,phase,confirmed,memoryRemaining,lastKnown,lastSense,soundId,
        searchTarget:lastKnown?.slice()??null,canTrackCurrent,canAttack,
        canMove:!(row.electronic&&row.effects.lock>0),heard:!!strongest,
        audibility:strongest?.audibility??0,
        reason:visible?'visual-contact':strongest?'sound-at-emission':blind?'existing-optics-disabled':
          row.visual==='unknown'?'unknown-line-of-sight':lastKnown?'last-known-position':'no-contact',
        effects:{...row.effects}});
    }
    results.sort((a,b)=>a.id.localeCompare(b.id,'en'));
    const tracks=results.map(({id,suspicion,phase,confirmed,memoryRemaining,lastKnown,lastSense,soundId})=>
      ({id,suspicion,phase,confirmed,memoryRemaining,lastKnown:lastKnown?.slice()??null,lastSense,soundId}));
    const retained=[...sounds.values()].sort((a,b)=>a.id.localeCompare(b.id,'en')).map(row=>({...row,position:row.position.slice()}));
    const movement=signature(frame.movement??{});
    return{state:{schema:SCHEMA,clock,tracks,sounds:retained,seenSounds:[...seen]},observers:results,
      hud:{signature:movement,suspicion:Math.max(0,...results.map(row=>row.suspicion)),
        visibleObservers:results.filter(row=>row.canTrackCurrent).length,
        searchingObservers:results.filter(row=>row.phase==='search').length,
        combatObservers:results.filter(row=>row.phase==='combat').length,
        rememberedObservers:results.filter(row=>row.lastKnown!==null).length},
      energyCost:0,meaning:'existing quickhack resource/effect ownership retained; transient perception only'};
  }

  const API=Object.freeze({version:'0.70.0',CONFIG,initial,signature,advance});
  if(typeof module==='object'&&module.exports)module.exports=API;
  root.__SOMA_INFILTRATION70_CORE__=API;
})(typeof globalThis==='object'?globalThis:this);
