/* Preparation only: v32 still applies heavy damage, armour and recovery.
 * The paid attempt is transient; the existing attackClock is its save owner. */
(function(root){
  'use strict';
  const CONFIG=Object.freeze({chargeSeconds:.7,maxChannels:32,maxVisible:4,maxStepSeconds:.25});
  const channels=new Map(),counts={started:0,completed:0,interrupted:0};
  const finite=n=>typeof n==='number'&&Number.isFinite(n),clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
  const currentZone=()=>typeof zone==='undefined'?null:zone,currentState=()=>typeof state==='undefined'?null:state;
  // The consumable28 owns its affected robots, 12 m admission and ten-second
  // performance.now deadline. Perception only reads that existing deadline.
  function isObscured(q){return finite(q?.v28ObscuredUntil)&&q.v28ObscuredUntil>performance.now();}
  let activeZone=null,activeZoneId=null,activeState=null,roster=new Set(),lastReason=null,lineChecks=0;
  function handles(q){return !!q?.v32Enemy&&q.v32Role==='heavy'&&!q.v26BossId&&!q.v27ICE&&
    !root.__SOMA_BOSSES36__?.handles?.(q)&&!root.__SOMA_BOSSES36__?.suspended?.(q);}
  function cooldown(q,a){return Math.max(.1,finite(a?.cooldown)?a.cooldown:1.7)/Math.max(.1,finite(q.v33AttackFactor)?q.v33AttackFactor:1);}
  function playable(){const s=currentState();return !!currentZone()&&!!s&&s.health>0&&!s.driving&&!s.recovery?.pending&&!(s.recoveryGrace>0)&&
    !(typeof paused!=='undefined'&&paused)&&!(typeof document!=='undefined'&&document.hidden)&&!(typeof v27IsCyber==='function'&&v27IsCyber());}
  function interrupt(q,reason){const row=channels.get(q);if(!row)return;
    q.attackClock=Math.max(finite(q.attackClock)?q.attackClock:0,row.cooldown,cooldown(q,row.archetype));
    channels.delete(q);counts.interrupted=Math.min(1e9,counts.interrupted+1);lastReason=reason;}
  function clear(reason){for(const q of channels.keys())interrupt(q,reason);}
  function synchronise(){
    if(currentZone()!==activeZone||(currentZone()?.id??null)!==activeZoneId||currentState()!==activeState){
      clear('context-changed');activeZone=currentZone();activeZoneId=activeZone?.id??null;activeState=currentState();}
    roster=new Set(activeZone?.robots||[]);if(!playable())clear('inactive');return playable();
  }
  function point(q){const sight=root.__SOMA_SIGHT61__;return sight?.activeFor?.(activeZone)?sight.eyePoint?.(q.x,q.z,activeZone,1.45):[q.x,1.45,q.z];}
  function knownLine(q){
    if(![q.x,q.z,camera.x,camera.z].every(finite))return false;
    lineChecks++;
    const sight=root.__SOMA_SIGHT61__;
    if(sight?.activeFor?.(activeZone)){
      // NPC y is an animation offset. The player's actual camera is already NGF.
      const from=point(q),ground=sight.eyePoint?.(camera.x,camera.z,activeZone,1.45),to=[camera.x,camera.y,camera.z];
      return Array.isArray(from)&&from.length===3&&from.every(finite)&&Array.isArray(ground)&&ground.length===3&&ground.every(finite)&&
        to.every(finite)&&typeof sight.between==='function'&&sight.between(from,to,activeZone)===false;
    }
    return typeof lineBlocked==='function'&&!lineBlocked(q.x,q.z,camera.x,camera.z);
  }
  function invalid(q,a,allowed=true){
    if(!handles(q)||!roster.has(q)||q.hidden||q.disabled||q.retire||!finite(q.health)||q.health<=0)return 'unit-unavailable';
    const p=root.__SOMA_PERCEPTION70__?.observer?.(q.id),effects=root.__SOMA_V42__?.state?.().hacks?.[activeZone?.id]?.[q.id];
    if(isObscured(q))return 'smoke-obscured';
    if(['blind','jam','lock'].some(key=>(Number(effects?.[key])||0)>0))return 'system-disrupted';
    // Radio is search evidence. Only this observer's current personal sight can
    // prepare or release the shot, even if somebody else reported the player.
    if(!allowed||q.state!=='combat'||p?.canAttack!==true||p.canTrackCurrent!==true||p.phase!=='combat'||
      !finite(a?.range)||Math.hypot(q.x-camera.x,q.z-camera.z)>a.range||!knownLine(q))return 'contact-lost';
    return null;
  }
  function maintain(){synchronise();for(const [q,row]of channels){
    const reason=String(q.id)!==row.id?'identity-changed':q.health<row.health?'received-hit':invalid(q,row.archetype);
    if(reason)interrupt(q,reason);else row.health=q.health;
  }}
  function beginEnemyFrame(){lineChecks=0;maintain();}
  function advance(q,a,delta,allowed){
    if(!synchronise()||!handles(q))return false;
    const row=channels.get(q);
    // Cooldown/capacity refusals need no extra ray beyond perception70.
    if(!row&&(q.attackClock>0||channels.size>=CONFIG.maxChannels))return false;
    const reason=row&&String(q.id)!==row.id?'identity-changed':row&&q.health<row.health?'received-hit':invalid(q,a,allowed);
    if(reason){interrupt(q,reason);return false;}
    if(!row){
      const recovery=cooldown(q,a);q.attackClock=recovery;
      channels.set(q,{id:String(q.id),health:q.health,elapsed:0,cooldown:recovery,archetype:a});
      counts.started=Math.min(1e9,counts.started+1);return false;
    }
    row.health=q.health;row.elapsed+=finite(delta)?clamp(delta,0,CONFIG.maxStepSeconds):0;
    if(row.elapsed+1e-6<CONFIG.chargeSeconds)return false;
    channels.delete(q);counts.completed=Math.min(1e9,counts.completed+1);lastReason=null;return true;
  }
  function playerSees(q){
    if(!playable())return false;const p=point(q);if(!Array.isArray(p)||p.length!==3||!p.every(finite)||!finite(camera.y))return false;
    const dx=p[0]-camera.x,dy=p[1]-camera.y,dz=p[2]-camera.z,yaw=Number(camera.yaw)||0,pitch=Number(camera.pitch)||0;
    const sy=Math.sin(yaw),cy=Math.cos(yaw),sp=Math.sin(pitch),cp=Math.cos(pitch),depth=dx*sy*cp+dy*sp+dz*cy*cp;
    const horizontal=dx*cy-dz*sy,vertical=-dx*sy*sp+dy*cp-dz*cy*sp;
    const vfov=typeof currentFovRadians==='function'?currentFovRadians():clamp((Number(currentState()?.settings?.fov)||67)*Math.PI/180,.5,2.2);
    const aspect=typeof innerWidth==='number'&&typeof innerHeight==='number'?clamp(innerWidth/Math.max(1,innerHeight),.5,4):1;
    return depth>0&&Math.abs(horizontal)<depth*Math.tan(vfov/2)*aspect&&Math.abs(vertical)<depth*Math.tan(vfov/2);
  }
  // HUD72 calls this after maintain(). Reading rows never adds another ray or
  // another DOM tree; at most four shared warning rows are mounted by its owner.
  function visibleTelegraphs(){return [...channels].filter(([q])=>playerSees(q)).slice(0,CONFIG.maxVisible).map(([q,row])=>({
    label:String(q.v32Label||'Unité lourde').slice(0,100),progress:clamp(row.elapsed/CONFIG.chargeSeconds,0,1),
    remainingSeconds:Math.max(0,CONFIG.chargeSeconds-row.elapsed),title:'SALVE LOURDE EN PRÉPARATION',
    meterLabel:'Préparation de la salve lourde',hint:'Touchez l’unité lourde ou coupez sa ligne de vue.'}));}
  function describe(q){const row=channels.get(q);return row?['Salve préparée · '+Math.floor(clamp(row.elapsed/CONFIG.chargeSeconds,0,1)*100)+' %',
    'Touchez l’unité lourde ou coupez sa ligne de vue.']:null;}
  function isPreparing(q){return handles(q)&&channels.has(q);}
  function recoveryForSave(q){const row=channels.get(q);return Math.max(0,finite(q.attackClock)?Math.min(3600,q.attackClock):0,row?Math.min(3600,Math.max(row.cooldown,cooldown(q,row.archetype))):0);}
  function restoreRecovery(q,record){if(handles(q)&&finite(record?.attackClock))q.attackClock=Math.max(finite(q.attackClock)?q.attackClock:0,clamp(record.attackClock,0,3600));}
  function reset(){clear('reset');activeZone=currentZone();activeZoneId=activeZone?.id??null;activeState=currentState();roster=new Set(activeZone?.robots||[]);}
  root.__SOMA_COMBAT76__=Object.freeze({version:'0.76.0',config:CONFIG,handles,advance,maintain,beginEnemyFrame,reset,describe,isObscured,
    visibleTelegraphs,isPreparing,recoveryForSave,restoreRecovery,snapshotHUD:()=>{maintain();return {telegraphs:visibleTelegraphs(),chargeSeconds:CONFIG.chargeSeconds};},
    snapshot:()=>{maintain();return {ephemeral:true,activeChannels:channels.size,maxChannels:CONFIG.maxChannels,lineChecks,
      counters:{...counts},lastInterruption:lastReason,channels:[...channels].map(([q,row])=>({id:String(q.id),progress:clamp(row.elapsed/CONFIG.chargeSeconds,0,1)}))};}});
})(window);
