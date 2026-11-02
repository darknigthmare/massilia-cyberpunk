/* Écho presentation only. The v70 controller still owns activation, five-second
 * duration, cyberdeck debit, cooldown and persistence. No entity is modified. */
(function(root){
  'use strict';
  const CONFIG=Object.freeze({rangeMeters:24,maxCandidates:128,maxTargets:8,maxMarkers:4});
  const ROLES=Object.freeze({
    rifle:['Lancier','Coupez sa ligne de tir.'],heavy:['Unité lourde','Utilisez un couvert entre les salves.'],
    blade:['Assaut rapproché','Gardez vos distances.'],sniper:['Tir de précision','Rompez la ligne de vue.'],
    netrunner:['Intrusion neurale','Touchez le tisseur ou coupez sa vue.'],
    medic:['Soutien médical','Peut restaurer les unités blessées.'],
    drone:['Drone de combat','Visez la machine à portée pour vérifier les quickhacks.'],
    turret:['Tourelle','Visez la machine à portée pour vérifier les quickhacks.']
  });
  const finite=n=>typeof n==='number'&&Number.isFinite(n),clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
  const currentZone=()=>typeof zone==='undefined'?null:zone,currentState=()=>typeof state==='undefined'?null:state;
  let activeZone=null,activeZoneId=null,activeState=null,tracked=[],overlay=null,status=null,markers=[];
  function active(){
    const s=currentState();
    return !!currentZone()&&!!s&&s.health>0&&!s.driving&&!s.recovery?.pending&&!(s.recoveryGrace>0)&&
      !(typeof paused!=='undefined'&&paused)&&!(typeof document!=='undefined'&&document.hidden)&&
      !(typeof v27IsCyber==='function'&&v27IsCyber())&&root.__SOMA_V42__?.canUseOnFoot?.()===true&&
      root.__SOMA_V70__?.modifiers?.().scanActive===true;
  }
  function clear(){tracked=[];if(overlay)overlay.hidden=true;if(status)status.hidden=true;for(const node of markers)node.hidden=true;}
  function synchronise(){
    if(currentZone()!==activeZone||(currentZone()?.id??null)!==activeZoneId||currentState()!==activeState){
      clear();activeZone=currentZone();activeZoneId=activeZone?.id??null;activeState=currentState();
    }
    if(!active()){clear();return false;}return true;
  }
  function viewport(){
    const rect=typeof document!=='undefined'?document.getElementById('gl')?.getBoundingClientRect?.():null;
    const width=Number(rect?.width)||(typeof innerWidth==='number'?innerWidth:0),height=Number(rect?.height)||(typeof innerHeight==='number'?innerHeight:0);
    return width>0&&height>0?{left:Number(rect?.left)||0,top:Number(rect?.top)||0,width,height}:null;
  }
  function point(q){
    const sight=root.__SOMA_SIGHT61__;
    // NPC y values are animation/local offsets, never an NGF body altitude.
    const height=q.v32Role==='drone'?1.3:q.v32Role==='turret'?1.15:1.45;
    if(sight?.activeFor?.(activeZone))return sight.eyePoint?.(q.x,q.z,activeZone,height)||null;
    return [q.x,height,q.z];
  }
  function projection(q,view){
    if(!view||!q||q.hidden||!(q.health>0)||![q.x,q.z,camera.x,camera.y,camera.z].every(finite))return null;
    const distance=Math.hypot(q.x-camera.x,q.z-camera.z);if(distance>CONFIG.rangeMeters)return null;
    const p=point(q);if(!Array.isArray(p)||p.length!==3||!p.every(finite))return null;
    const dx=p[0]-camera.x,dy=p[1]-camera.y,dz=p[2]-camera.z,yaw=Number(camera.yaw)||0,pitch=Number(camera.pitch)||0;
    const sy=Math.sin(yaw),cy=Math.cos(yaw),sp=Math.sin(pitch),cp=Math.cos(pitch);
    const depth=dx*sy*cp+dy*sp+dz*cy*cp,horizontal=dx*cy-dz*sy,vertical=-dx*sy*sp+dy*cp-dz*cy*sp;
    const vfov=typeof currentFovRadians==='function'?currentFovRadians():clamp((Number(currentState()?.settings?.fov)||67)*Math.PI/180,.5,2.2);
    const half=Math.tan(vfov/2),nx=horizontal/(depth*half*view.width/view.height),ny=vertical/(depth*half);
    if(depth<=0||!finite(nx)||!finite(ny)||Math.abs(nx)>=1||Math.abs(ny)>=1)return null;
    const sight=root.__SOMA_SIGHT61__;
    if(sight?.activeFor?.(activeZone)){
      // Use the actual absolute camera altitude, not a second terrain sample.
      if(typeof sight.between!=='function'||sight.between([camera.x,camera.y,camera.z],p,activeZone))return null;
    }else if(typeof lineBlocked!=='function'||lineBlocked(camera.x,camera.z,q.x,q.z))return null;
    return {x:view.left+(nx+1)*view.width/2,y:view.top+(1-ny)*view.height/2,distance};
  }
  function describe(q,projection){
    const electronic=root.__SOMA_V42__?.isMachine?.(q)===true;
    const role=q.v26BossId?['Unité majeure','Ses protocoles relèvent de son propre système.']:ROLES[q.v32Role]||(q.v42Camera?['Caméra','Visez la machine à portée pour vérifier les quickhacks.']:['Signal local','Observez ses déplacements.']);
    const maximum=finite(q.maxHealth)&&q.maxHealth>0?q.maxHealth:q.health;
    return {id:String(q.id).slice(0,120),label:String(q.v32Label||q.name||q.label||(q.v42Camera?'Caméra':'Signal local')).slice(0,100),
      roleLabel:role[0],hint:role[1],distance:projection.distance,healthPercent:Math.round(clamp(q.health/maximum*100,0,100)),electronic};
  }
  function rows(){
    if(!synchronise())return[];
    const view=viewport(),robots=activeZone?.robots||[];
    return tracked.filter(row=>robots.includes(row.q)&&String(row.q.id)===row.id).flatMap(row=>{
      const p=projection(row.q,view);return p?[{q:row.q,projection:p,info:describe(row.q,p)}]:[];
    });
  }
  function scanTargets(){
    if(!synchronise())return[];
    const view=viewport(),found=[];
    for(const q of (activeZone.robots||[]).slice(0,CONFIG.maxCandidates)){
      const p=projection(q,view);if(p)found.push({q,id:String(q.id),projection:p});
    }
    found.sort((a,b)=>a.projection.distance-b.projection.distance||a.id.localeCompare(b.id));
    tracked=found.slice(0,CONFIG.maxTargets).map(({q,id})=>({q,id}));
    return found.slice(0,CONFIG.maxTargets).map(row=>describe(row.q,row.projection));
  }
  function mount(){
    if(overlay||typeof document==='undefined'||!document.body)return;
    const style=document.createElement('style');style.id='soma-v73-tactical-style';
    style.textContent=`#v73-tactical-markers{position:fixed;inset:0;pointer-events:none;z-index:18}#v73-tactical-markers[hidden],#v73-tactical-markers [hidden],#v73-tactical-hud[hidden]{display:none!important}.v73-tactical-marker{position:fixed;box-sizing:border-box;width:196px;min-height:70px;padding:7px 9px;border:1px solid #75e3db;border-left:3px solid #75e3db;background:#061b24ed;color:#effffa;font:12px/1.4 system-ui;overflow-wrap:anywhere;pointer-events:none}.v73-tactical-marker strong,.v73-tactical-marker span,.v73-tactical-marker small{display:block}.v73-tactical-marker small{color:#d6f2ef;font-size:11px}#v73-tactical-hud{position:fixed;left:0;top:0;width:1px;height:1px;padding:0;margin:-1px;border:0;overflow:hidden;clip:rect(0,0,0,0);clip-path:inset(50%);white-space:nowrap;pointer-events:none}#v73-tactical-markers[data-large-text="true"] .v73-tactical-marker{font-size:16px}#v73-tactical-markers[data-large-text="true"] .v73-tactical-marker small{font-size:14px}body:has(.modal.open) #v73-tactical-markers,body.v34-menu-open #v73-tactical-markers{display:none!important}`;
    document.head.appendChild(style);
    overlay=document.createElement('div');overlay.id='v73-tactical-markers';overlay.hidden=true;overlay.setAttribute('aria-hidden','true');
    for(let i=0;i<CONFIG.maxMarkers;i++){
      const node=document.createElement('div');node.className='v73-tactical-marker';node.hidden=true;
      for(const tag of ['strong','span','small'])node.appendChild(document.createElement(tag));markers.push(node);overlay.appendChild(node);
    }
    document.body.appendChild(overlay);
    status=document.createElement('aside');status.id='v73-tactical-hud';status.hidden=true;status.setAttribute('role','status');status.setAttribute('aria-live','polite');status.setAttribute('aria-atomic','true');
    // The visible count already belongs to v70-hud. Keep this live summary
    // outside HUD grid flow so long text cannot push health/ammo offscreen.
    document.body.appendChild(status);
  }
  function render(){
    const current=rows();mount();if(!overlay)return;
    overlay.hidden=!active();status.hidden=overlay.hidden;
    if(overlay.hidden)return;
    const summary='ÉCHO · '+current.length+' unité'+(current.length===1?'':'s')+' visible'+(current.length===1?'':'s')+(current[0]?' · '+current[0].info.roleLabel+' · intégrité '+current[0].info.healthPercent+' %':' · balayez la rue du regard.');
    if(status.textContent!==summary)status.textContent=summary;
    const large=!!currentState()?.settings?.largeText;
    overlay.setAttribute('data-large-text',String(large));status.setAttribute('data-large-text',String(large));
    const view=viewport(),placed=[],reserved=Array.from(document.querySelectorAll?.('#v72-hud-layout [data-v72-hud]')||[])
      .filter(node=>!node.hidden).map(node=>node.getBoundingClientRect?.()).filter(rect=>rect?.width>0&&rect?.height>0);
    const overlaps=(a,b)=>a.left<b.right+6&&a.right+6>b.left&&a.top<b.bottom+6&&a.bottom+6>b.top;
    for(const node of markers)node.hidden=true;
    for(const row of current){
      if(placed.length>=CONFIG.maxMarkers)break;
      const node=markers[placed.length],p=row.projection,info=row.info;
      node.children[0].textContent=info.label+' · '+info.roleLabel;
      node.children[1].textContent=Math.round(info.distance)+' m · intégrité '+info.healthPercent+' %';node.children[2].textContent=info.hint;
      // Font size and long labels change the real box. Measure after assigning
      // text, before reserving space; the fallback is only for DOM-less QA.
      node.hidden=false;const measured=node.getBoundingClientRect?.(),width=Number(measured?.width)||196,height=Number(measured?.height)||(large?180:128);
      if(view.width<width+24||view.height<height+24){node.hidden=true;continue;}
      let box=null;
      for(const [dx,dy]of [[12,-height],[-width-12,-height],[12,12],[-width-12,12]]){
        const left=clamp(p.x+dx,view.left+12,view.left+view.width-width-12),top=clamp(p.y+dy,view.top+12,view.top+view.height-height-12);
        const candidate={left,top,right:left+width,bottom:top+height};
        if(![...placed,...reserved].some(b=>overlaps(candidate,b))){box=candidate;break;}
      }
      if(!box){node.hidden=true;continue;}placed.push(box);node.hidden=false;node.style.left=box.left+'px';node.style.top=box.top+'px';
    }
  }
  function reset(){clear();activeZone=currentZone();activeZoneId=activeZone?.id??null;activeState=currentState();}
  root.__SOMA_TACTICAL73__=Object.freeze({version:'0.73.0',config:CONFIG,scanTargets,maintain:render,reset,
    snapshot:()=>{const targets=rows().map(row=>({...row.info}));return {version:'0.73.0',ephemeral:true,scanActive:active(),visibleTargets:targets.length,
      maxCandidates:CONFIG.maxCandidates,maxMarkers:CONFIG.maxMarkers,targets};}});
})(window);
