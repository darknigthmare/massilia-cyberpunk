/* The v32 owner still applies its original tension, weapon jam and cooldown.
 * This bounded, unsaved adapter only prepares or interrupts that exact attack. */
(function(root){
  'use strict';
  const CONFIG=Object.freeze({chargeSeconds:1.1,maxChannels:64,maxStepSeconds:.25});
  const channels=new Map(),counts={started:0,completed:0,interrupted:0};
  let activeZone=null,activeZoneId=null,activeState=null,lastReason=null,hud=null,lastHUD='';
  const finite=n=>typeof n==='number'&&Number.isFinite(n),clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
  const currentZone=()=>typeof zone==='undefined'?null:zone;
  const currentState=()=>typeof state==='undefined'?null:state;
  function bump(name){counts[name]=Math.min(1e9,counts[name]+1);}
  function cooldown(q,a){return Math.max(.1,Number(a?.cooldown)||3.6)/Math.max(.1,finite(q.v33AttackFactor)?q.v33AttackFactor:1);}
  function eligible(q){return !!q?.v32Enemy&&q.v32Role==='netrunner'&&!q.v26BossId&&!q.v27ICE&&
    !root.__SOMA_BOSSES36__?.handles?.(q)&&!root.__SOMA_BOSSES36__?.suspended?.(q);}
  function playable(){
    const s=currentState();
    return !!currentZone()&&!!s&&s.health>0&&!s.driving&&!s.recovery?.pending&&!(s.recoveryGrace>0)&&
      !(typeof paused!=='undefined'&&paused)&&!(typeof document!=='undefined'&&document.hidden)&&
      !(typeof v27IsCyber==='function'&&v27IsCyber());
  }
  function interrupt(q,reason){
    const row=channels.get(q);if(!row)return;
    // An interrupted attempt consumes its original recovery. Briefly ducking
    // out of sight cannot refund a ready attack on the following frame.
    q.attackClock=Math.max(Number(q.attackClock)||0,row.cooldown,cooldown(q,row.archetype));
    channels.delete(q);bump('interrupted');lastReason=reason;
  }
  function clear(reason){for(const q of [...channels.keys()])interrupt(q,reason);}
  function synchronise(){
    if(currentZone()!==activeZone||(currentZone()?.id??null)!==activeZoneId||currentState()!==activeState){clear('context-changed');activeZone=currentZone();activeZoneId=activeZone?.id??null;activeState=currentState();}
    if(!playable())clear('inactive');
    return playable();
  }
  function knownLine(q){
    if(![q.x,q.z,camera.x,camera.z].every(finite)||typeof lineBlocked!=='function')return false;
    const sight=root.__SOMA_SIGHT61__;
    if(sight?.activeFor?.(activeZone)&&(!sight.eyePoint(q.x,q.z)||!sight.eyePoint(camera.x,camera.z)))return false;
    return !lineBlocked(q.x,q.z,camera.x,camera.z);
  }
  function effectsBlock(q){
    const e=root.__SOMA_V42__?.state?.().hacks?.[activeZone?.id]?.[q.id];
    return (Number(e?.blind)||0)>0||(Number(e?.jam)||0)>0;
  }
  function valid(q,a,allowed=true){
    const perception=root.__SOMA_PERCEPTION70__?.observer?.(q.id);
    return allowed&&q.health>0&&q.state==='combat'&&!effectsBlock(q)&&
      (!perception||perception.canAttack)&&Math.hypot(q.x-camera.x,q.z-camera.z)<=a.range&&knownLine(q);
  }
  function maintain(){maintainState();renderHUD();}
  function advance(q,a,delta,allowed){
    if(!synchronise())return false;
    // Bosses and digital ICE retain their historical owners and readiness.
    if(!eligible(q))return !!allowed&&q.attackClock<=0&&knownLine(q)&&Math.hypot(q.x-camera.x,q.z-camera.z)<=a.range;
    const row=channels.get(q);
    if(row&&q.health<row.health){interrupt(q,'received-hit');renderHUD();return false;}
    if(!valid(q,a,allowed)){interrupt(q,effectsBlock(q)?'system-disrupted':'contact-lost');renderHUD();return false;}
    if(!row){
      if(q.attackClock>0||channels.size>=CONFIG.maxChannels)return false;
      const recovery=cooldown(q,a);q.attackClock=recovery;
      channels.set(q,{health:q.health,elapsed:0,cooldown:recovery,archetype:a});bump('started');
      renderHUD();return false;
    }
    row.health=q.health;row.elapsed+=finite(delta)?clamp(delta,0,CONFIG.maxStepSeconds):0;
    if(row.elapsed+1e-6<CONFIG.chargeSeconds){renderHUD();return false;}
    channels.delete(q);bump('completed');lastReason=null;renderHUD();return true;
  }
  function playerSees(q){
    if(q.hidden||!playable()||!knownLine(q))return false;
    const sight=root.__SOMA_SIGHT61__,point=sight?.activeFor?.(activeZone)?sight.eyePoint(q.x,q.z,activeZone,1.45):[q.x,1.45,q.z];
    if(!Array.isArray(point)||!point.every(finite))return false;
    const dx=point[0]-camera.x,dz=point[2]-camera.z,dy=point[1]-(finite(camera.y)?camera.y:1.72);
    const yaw=Number(camera.yaw)||0,pitch=Number(camera.pitch)||0,sy=Math.sin(yaw),cy=Math.cos(yaw),sp=Math.sin(pitch),cp=Math.cos(pitch);
    // Project the unit's upper body into the actual camera frustum. ADS/FOV
    // changes use the same function as the renderer, with no off-screen marker.
    const vfov=typeof currentFovRadians==='function'?currentFovRadians():clamp((Number(currentState()?.settings?.fov)||67)*Math.PI/180,.5,2.2);
    const aspect=typeof innerWidth==='number'&&typeof innerHeight==='number'?clamp(innerWidth/Math.max(1,innerHeight),.5,4):1;
    const depth=dx*sy*cp+dy*sp+dz*cy*cp,horizontal=dx*cy-dz*sy,vertical=-dx*sy*sp+dy*cp-dz*cy*sp;
    return depth>0&&Math.abs(horizontal)<depth*Math.tan(vfov/2)*aspect&&Math.abs(vertical)<depth*Math.tan(vfov/2);
  }
  function visibleRows(){
    return [...channels].filter(([q])=>playerSees(q)).slice(0,4).map(([q,row])=>({
      label:String(q.v32Label||'Tisseur de trace').slice(0,100),progress:clamp(row.elapsed/CONFIG.chargeSeconds,0,1),
      remainingSeconds:Math.max(0,CONFIG.chargeSeconds-row.elapsed)}));
  }
  function snapshotHUD(){
    maintainState();const telegraphs=visibleRows();
    return {visibleChannels:telegraphs.length,telegraphs,hint:telegraphs.length?'Touchez le tisseur ou coupez la ligne de vue.':'',
      chargeSeconds:CONFIG.chargeSeconds};
  }
  // Snapshot reads also respect pause/import/death even outside the game loop.
  function maintainState(){
    synchronise();
    for(const [q,row]of channels){
      if(!(activeZone?.robots||[]).includes(q)||!eligible(q)||q.health<=0)interrupt(q,'unit-unavailable');
      else if(q.health<row.health)interrupt(q,'received-hit');
      else if(!valid(q,row.archetype))interrupt(q,effectsBlock(q)?'system-disrupted':'contact-lost');
      else row.health=q.health;
    }
  }
  function renderHUD(){
    if(typeof document==='undefined'||!document.body)return;
    const rows=visibleRows();
    if(!hud){
      hud=document.createElement('aside');hud.id='v72-netrunner-hud';hud.hidden=true;
      hud.setAttribute('role','status');hud.setAttribute('aria-live','polite');hud.setAttribute('aria-atomic','true');
      const style=document.createElement('style');style.textContent='#v72-netrunner-hud{position:fixed;left:50%;top:168px;transform:translateX(-50%);width:min(420px,calc(100vw - 24px));z-index:68;box-sizing:border-box;padding:10px 13px;background:#170f24f2;border:1px solid #c1a2ee;color:#fff;font:12px/1.45 system-ui;pointer-events:none}#v72-netrunner-hud[hidden]{display:none!important}#v72-netrunner-hud strong,#v72-netrunner-hud span{display:block}#v72-netrunner-hud meter{display:block;width:100%;height:10px}#v72-netrunner-hud small{display:block;color:#eadcf9;margin-top:5px}.body-large-text #v72-netrunner-hud{font-size:16px}';
      document.head.appendChild(style);document.body.appendChild(hud);
    }
    hud.hidden=!rows.length;
    const signature=JSON.stringify(rows.map(row=>[row.label,Math.floor(row.progress*20)]));
    if(signature===lastHUD)return;lastHUD=signature;hud.replaceChildren();
    for(const row of rows){
      const title=document.createElement('strong');title.textContent='INTRUSION EN PRÉPARATION · '+Math.floor(row.progress*100)+' %';
      const label=document.createElement('span');label.textContent=row.label;
      const meter=document.createElement('meter');meter.min=0;meter.max=1;meter.value=row.progress;meter.setAttribute('aria-label','Préparation de l’intrusion neurale');
      hud.appendChild(title);hud.appendChild(label);hud.appendChild(meter);
    }
    if(rows.length){const hint=document.createElement('small');hint.textContent='Touchez le tisseur ou coupez la ligne de vue.';hud.appendChild(hint);}
  }
  function reset(){clear('reset');activeZone=currentZone();activeZoneId=activeZone?.id??null;activeState=currentState();renderHUD();}
  root.__SOMA_NETRUNNER72__=Object.freeze({version:'0.72.0',config:CONFIG,advance,beginEnemyFrame:maintain,maintain,reset,snapshotHUD,
    snapshot:()=>{maintainState();return {ephemeral:true,activeChannels:channels.size,maxChannels:CONFIG.maxChannels,
      counters:{...counts},lastInterruption:lastReason,hud:snapshotHUD()};}});
})(window);
