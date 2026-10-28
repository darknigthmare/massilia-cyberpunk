/* Transient evidence for historical police/security AI. The protected v70
 * kernel owns perception rules; existing scripts retain movement, arrest,
 * damage, cyberdeck effects and save ownership. No new player-position feed. */
(function(root){
  'use strict';
  const K=root.__SOMA_INFILTRATION70_CORE__;
  if(!K)throw Error('Legacy perception requires the verified infiltration70 core.');
  const finite=n=>typeof n==='number'&&Number.isFinite(n),clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
  const copy=value=>JSON.parse(JSON.stringify(value));
  let memory=K.initial(),activeZone=null,activeZoneId=null,pending=[],output=new Map(),entities=new Map(),error=null;
  let rejected=0,skipped=0;
  function currentZone(){return typeof zone==='undefined'?null:zone;}
  function reset(){memory=K.initial();pending=[];output=new Map();entities=new Map();error=null;rejected=0;skipped=0;activeZone=currentZone();activeZoneId=activeZone?.id??null;}
  function synchronise(){if(currentZone()!==activeZone||(currentZone()?.id??null)!==activeZoneId)reset();return activeZone;}
  function key(kind,q){
    const value=kind+':'+String(q?.id??'');
    return /^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,159}$/.test(value)&&q?.id!==undefined?value:null;
  }
  function alive(q){return q&&!q.retire&&(q.health===undefined||finite(q.health)&&q.health>0)&&finite(q.x)&&finite(q.z);}
  function boss(q){return !!(q.v26BossId||root.__SOMA_BOSSES36__?.handles?.(q));}
  function eligible(kind,q){
    if(!alive(q))return false;
    if(kind==='actor')return !!q.police&&(state.police?.level||0)>0&&!q.nightAnchored;
    if(kind==='vehicle')return !!(q.ai&&q.dispatch)&&(state.police?.level||0)>0&&!q.hidden&&!q.disabled&&state.driving!==q.id;
    return !q.v32Enemy&&!q.v42Camera&&!q.v27ICE&&!boss(q)&&
      (q.kind==='security'&&q.hostile||q.kind==='policeDrone'&&(q.hostile||(state.police?.level||0)>0));
  }
  function reportNoise(event){
    if(!synchronise()||!event||!Array.isArray(event.position)||event.position.length!==2||
      !event.position.every(finite)||typeof event.id!=='string')return false;
    if(pending.length>=K.CONFIG.maxSounds)pending.shift();
    pending.push({...event,position:event.position.slice()});return true;
  }
  function effects(kind,q){
    const raw=kind==='robot'?root.__SOMA_V42__?.state?.().hacks?.[activeZone.id]?.[q.id]:null;
    const timer=n=>finite(n)?clamp(n,0,3600):0;
    return {blind:timer(raw?.blind),lock:timer(raw?.lock),jam:timer(raw?.jam)};
  }
  function vision(kind,q,posture,available){
    if(!available)return 'unknown';
    const dx=camera.x-q.x,dz=camera.z-q.z,d=Math.hypot(dx,dz),h=finite(q.heading)?q.heading:0;
    const range=kind==='vehicle'?q.kind==='policeVTOL'?48:38:kind==='actor'?26:25;
    const tracked=output.get(key(kind,q));
    // Pursuit widens a real observer's cone; an administrative wanted level
    // alone never reveals the target. Blind/jam/lock stay the kernel's rules.
    const cosine=d<.05?1:(Math.sin(h)*dx+Math.cos(h)*dz)/d;
    if(d>=range*(posture?.65:1)||cosine<=(tracked?.confirmed?.05:.35))return 'blocked';
    const sight=root.__SOMA_SIGHT61__;
    if(sight?.activeFor?.(activeZone)&&(!sight.eyePoint(q.x,q.z)||!sight.eyePoint(camera.x,camera.z)))return 'unknown';
    return typeof lineBlocked!=='function'||lineBlocked(q.x,q.z,camera.x,camera.z)?'blocked':'visible';
  }
  function beginFrame(delta){
    const z=synchronise();if(!z)return null;
    if(paused)return status();
    const dt=finite(delta)?clamp(delta,0,K.CONFIG.maxStepSeconds):0;
    const available=state.health>0&&!state.recovery?.pending&&!(state.recoveryGrace>0)&&
      !(typeof v27IsCyber==='function'&&v27IsCyber());
    const posture=!state.driving&&!!root.__SOMA_V42__?.isCrouched?.();
    const candidates=[...(z.actors||[]).map(q=>['actor',q]),...(z.robots||[]).map(q=>['robot',q]),
      ...(z.vehicles||[]).map(q=>['vehicle',q])];
    const rows=[],live=new Map();skipped=0;
    for(const [kind,q]of candidates){
      if(!eligible(kind,q))continue;
      const id=key(kind,q);if(!id||live.has(id)||rows.length>=K.CONFIG.maxObservers){skipped++;continue;}
      live.set(id,q);
      if(entities.get(id)!==q){
        memory={...memory,tracks:memory.tracks.filter(row=>row.id!==id)};output.delete(id);
        // A profile from an older edition may carry a camera-derived patrol
        // target without observed evidence. Reset that transient police target
        // once when adopting its object; ordinary civilian routines stay owned
        // by the historical AI and no new saved property is introduced.
        if(kind==='actor'){q.targetX=q.x;q.targetZ=q.z;}
      }
      rows.push({id,position:[q.x,q.z],visual:vision(kind,q,posture,available),
        hearingRange:kind==='vehicle'?30:kind==='actor'?28:35,electronic:kind!=='actor',effects:effects(kind,q)});
    }
    // Unknown/dead/retired objects cannot keep or transfer a contact by id.
    entities=live;memory={...memory,tracks:memory.tracks.filter(row=>live.has(row.id))};
    try{
      const next=K.advance(memory,{dt,player:[camera.x,camera.z],observers:rows,noises:pending});
      memory=next.state;output=new Map(next.observers.map(row=>[row.id,row]));error=null;
    }catch(reason){
      rejected++;error=String(reason?.message||reason);output=new Map();
      memory=K.initial();
    }
    pending=[];return status();
  }
  function observer(kind,q){
    if(!synchronise()||entities.get(key(kind,q))!==q)return null;
    const row=output.get(key(kind,q));return row?copy(row):null;
  }
  function status(){
    return {version:'0.71.0',zoneId:activeZone?.id??null,clock:memory.clock,observerCount:output.size,
      activeSounds:memory.sounds.length,skippedObservers:skipped,
      rejectedFrames:rejected,error,sourceDataChanged:false,persistent:false};
  }
  function snapshot(){return {...status(),observers:[...output.values()].map(copy)};}
  root.__SOMA_LEGACY_PERCEPTION71__=Object.freeze({version:'0.71.0',beginFrame,observer,reportNoise,reset,snapshot});
})(window);
