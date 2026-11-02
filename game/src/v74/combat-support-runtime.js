/* A bounded, unsaved preparation for the original v32 +18 restoration.
 * v32 still owns the actual heal, cover fire, damage and 3.2-second recovery. */
(function(root){
  'use strict';
  const CONFIG=Object.freeze({chargeSeconds:1.2,recoverySeconds:3.2,rangeMeters:16,
    maxChannels:32,maxCandidates:128,maxSelectionChecks:1024,maxSelectionLines:128,maxStepSeconds:.25});
  const channels=new Map(),counts={started:0,completed:0,interrupted:0};
  const finite=n=>typeof n==='number'&&Number.isFinite(n),clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
  const currentZone=()=>typeof zone==='undefined'?null:zone,currentState=()=>typeof state==='undefined'?null:state;
  let activeZone=null,activeZoneId=null,activeState=null,roster=new Set(),checks=0,lines=0,lastReason=null;
  function bump(key){counts[key]=Math.min(1e9,counts[key]+1);}
  function handles(q){return !!q?.v32Enemy&&q.v32Role==='medic'&&!q.v26BossId&&!q.v27ICE&&
    !root.__SOMA_BOSSES36__?.handles?.(q)&&!root.__SOMA_BOSSES36__?.suspended?.(q);}
  function available(q){return !!q?.v32Enemy&&!q.hidden&&!q.retire&&!q.disabled&&!q.v26BossId&&!q.v27ICE&&
    !root.__SOMA_BOSSES36__?.handles?.(q)&&!root.__SOMA_BOSSES36__?.suspended?.(q)&&
    finite(q.x)&&finite(q.z)&&finite(q.health)&&q.health>0&&q.id!==undefined&&q.id!==null;}
  // Same local faction precedence as contact-sharing72; a shared squad never
  // overrides an authored faction. There is no player-position query here.
  function faction(q){
    if(typeof q.v33Faction==='string'&&q.v33Faction)return q.v33Faction==='police'?'police':'faction:'+q.v33Faction;
    if(q.kind==='policeDrone')return 'police';
    if(q.kind==='security'||q.v42Camera)return 'security:'+String(activeZone.v42Complex||activeZone.id);
    return 'squad:'+String(q.v33Squad||activeZone.id);
  }
  function playable(){
    const s=currentState();return !!currentZone()&&!!s&&s.health>0&&!s.driving&&!s.recovery?.pending&&!(s.recoveryGrace>0)&&
      !(typeof paused!=='undefined'&&paused)&&!(typeof document!=='undefined'&&document.hidden)&&
      !(typeof v27IsCyber==='function'&&v27IsCyber());
  }
  function interrupt(q,reason){
    if(!channels.delete(q))return;
    q.attackClock=Math.max(finite(q.attackClock)?q.attackClock:0,CONFIG.recoverySeconds);
    bump('interrupted');lastReason=reason;
  }
  function clear(reason){for(const q of channels.keys())interrupt(q,reason);}
  function synchronise(){
    if(currentZone()!==activeZone||(currentZone()?.id??null)!==activeZoneId||currentState()!==activeState){
      clear('context-changed');activeZone=currentZone();activeZoneId=activeZone?.id??null;activeState=currentState();
      roster=new Set(activeZone?.robots||[]);checks=0;lines=0;
    }
    if(!playable())clear('inactive');return playable();
  }
  function effectsBlock(q){
    const e=root.__SOMA_V42__?.state?.().hacks?.[activeZone?.id]?.[q.id];
    return ['blind','jam','lock'].some(key=>(Number(e?.[key])||0)>0);
  }
  function point(q){
    const height=q.v32Role==='drone'?1.3:q.v32Role==='turret'?1.15:1.45;
    return root.__SOMA_SIGHT61__?.eyePoint?.(q.x,q.z,activeZone,height)||null;
  }
  function knownLine(q,ally){
    const sight=root.__SOMA_SIGHT61__;
    if(sight?.activeFor?.(activeZone)){
      // Both bodies use terrain NGF plus their body height. q.y is a local
      // animation offset, and camera.y must never become an NPC altitude.
      const from=point(q),to=point(ally);
      return Array.isArray(from)&&from.length===3&&from.every(finite)&&Array.isArray(to)&&to.length===3&&to.every(finite)&&
        typeof sight.between==='function'&&sight.between(from,to,activeZone)===false;
    }
    return typeof lineBlocked==='function'&&!lineBlocked(q.x,q.z,ally.x,ally.z);
  }
  function targetValid(q,ally){return ally!==q&&available(ally)&&roster.has(ally)&&
    finite(ally.maxHealth)&&ally.maxHealth>0&&ally.health<ally.maxHealth&&faction(ally)===faction(q)&&
    Math.hypot(ally.x-q.x,ally.z-q.z)<CONFIG.rangeMeters;}
  function medicValid(q){return handles(q)&&available(q)&&roster.has(q)&&
    (q.state==='combat'||channels.has(q)&&['search','patrol'].includes(q.state))&&!effectsBlock(q);}
  function invalidReason(q,row){
    if(!medicValid(q)||String(q.id)!==row.id)return 'medic-unavailable';
    if(q.health<row.health)return 'received-hit';
    if(faction(q)!==row.faction||String(row.ally.id)!==row.allyId||!targetValid(q,row.ally))return 'ally-unavailable';
    if(!knownLine(q,row.ally))return 'ally-line-lost';
    return null;
  }
  function maintainState(){
    synchronise();roster=new Set(activeZone?.robots||[]);
    for(const [q,row]of channels){const reason=invalidReason(q,row);if(reason)interrupt(q,reason);else row.health=q.health;}
  }
  function beginEnemyFrame(){checks=0;lines=0;maintainState();}
  function choose(q){
    const reserved=new Set([...channels.values()].map(row=>row.ally));
    let best=null,bestFraction=Infinity,bestDistance=Infinity;
    const robots=activeZone?.robots||[];
    for(let i=0;i<Math.min(robots.length,CONFIG.maxCandidates)&&checks<CONFIG.maxSelectionChecks;i++){
      checks++;const ally=robots[i];if(reserved.has(ally)||!targetValid(q,ally))continue;
      if(lines>=CONFIG.maxSelectionLines)break;lines++;if(!knownLine(q,ally))continue;
      const fraction=ally.health/ally.maxHealth,distance=Math.hypot(ally.x-q.x,ally.z-q.z);
      if(fraction<bestFraction||fraction===bestFraction&&(distance<bestDistance||distance===bestDistance&&String(ally.id)<String(best?.id))){
        best=ally;bestFraction=fraction;bestDistance=distance;
      }
    }
    return best;
  }
  function face(q,ally){q.heading=Math.atan2(ally.x-q.x,ally.z-q.z);}
  function advance(q,delta){
    if(!synchronise()||!medicValid(q)){interrupt(q,'medic-unavailable');return null;}
    const row=channels.get(q);
    if(row){
      const reason=invalidReason(q,row);if(reason){interrupt(q,reason);return null;}
      row.health=q.health;row.elapsed+=finite(delta)?clamp(delta,0,CONFIG.maxStepSeconds):0;face(q,row.ally);
      if(row.elapsed+1e-6<CONFIG.chargeSeconds)return null;
      channels.delete(q);bump('completed');lastReason=null;return row.ally;
    }
    if(q.attackClock>0||channels.size>=CONFIG.maxChannels)return null;
    const ally=choose(q);if(!ally)return null;
    // Readiness is consumed before preparation. Cancelling or resetting never
    // refunds it; the original v32 branch writes its same recovery on success.
    q.attackClock=CONFIG.recoverySeconds;face(q,ally);
    channels.set(q,{id:String(q.id),ally,allyId:String(ally.id),faction:faction(q),health:q.health,elapsed:0});
    bump('started');return null;
  }
  function describe(q){
    if(!handles(q))return null;const row=channels.get(q);
    return row?['Reprise médicale · '+Math.floor(clamp(row.elapsed/CONFIG.chargeSeconds,0,1)*100)+' %',
      'Touchez le médecin ou coupez sa vue sur l’allié.']:['Soutien médical','Prépare ses soins à vue. Touchez le médecin pour les interrompre.'];
  }
  // Keep the existing scalar in its historical enemy records. An unfinished
  // preparation reloads as paid recovery, never as a serialised channel.
  function recoveryForSave(q){return Math.max(0,finite(q.attackClock)?Math.min(3600,q.attackClock):0,channels.has(q)?CONFIG.recoverySeconds:0);}
  function restoreRecovery(q,record){if(handles(q)&&finite(record?.attackClock))q.attackClock=Math.max(finite(q.attackClock)?q.attackClock:0,clamp(record.attackClock,0,3600));}
  function reset(){clear('reset');activeZone=currentZone();activeZoneId=activeZone?.id??null;activeState=currentState();roster=new Set(activeZone?.robots||[]);checks=0;lines=0;}
  root.__SOMA_COMBAT_SUPPORT74__=Object.freeze({version:'0.74.0',config:CONFIG,handles,advance,beginEnemyFrame,
    isPreparing:q=>handles(q)&&channels.has(q),maintain:maintainState,reset,describe,recoveryForSave,restoreRecovery,
    snapshot:()=>{maintainState();return {version:'0.74.0',ephemeral:true,activeChannels:channels.size,counters:{...counts},
      selectionChecks:checks,selectionLines:lines,lastInterruption:lastReason,
      channels:[...channels].map(([q,row])=>({id:String(q.id),allyId:row.allyId,progress:clamp(row.elapsed/CONFIG.chargeSeconds,0,1)}))};}});
})(window);
