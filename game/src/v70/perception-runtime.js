/* Adapter for the real v32 AI and existing v42 posture/quickhacks. No saves,
 * resource bank, damage implementation or audio-volume dependency is added. */
(function(root){
  'use strict';
  const K=root.__SOMA_INFILTRATION70_CORE__;
  if(!K)throw Error('Infiltration core 70 must precede its runtime.');
  let memory=K.initial(),activeZone=null,previousPose=null,strideDistance=0,serial=0;
  let pending=[],contacts=[],output=new Map(),entities=new Map(),written=new Map(),foreign=new Map();
  let hud={signature:K.signature(),suspicion:0,visibleObservers:0,searchingObservers:0,combatObservers:0,rememberedObservers:0};
  let lastError=null;
  const finite=n=>typeof n==='number'&&Number.isFinite(n),clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
  const copy=value=>JSON.parse(JSON.stringify(value));
  const timer=n=>finite(n)?clamp(n,0,3600):0;
  function zoneNow(){return typeof zone==='undefined'?null:zone;}
  function reset(){memory=K.initial();previousPose=null;strideDistance=0;pending=[];contacts=[];output=new Map();entities=new Map();written=new Map();foreign=new Map();lastError=null;}
  function synchronise(){const current=zoneNow();if(current!==activeZone){reset();activeZone=current;}return current;}
  function onFoot(){
    if(root.__SOMA_V42__?.canUseOnFoot)return root.__SOMA_V42__.canUseOnFoot();
    return !!zoneNow()&&!state.driving&&!state.recovery?.pending&&state.health>0&&!(typeof v27IsCyber==='function'&&v27IsCyber());
  }
  function crouched(){return !!(root.__SOMA_V42__?.isCrouched?.()??(!state.driving&&(keys.has('ControlLeft')||keys.has('ControlRight'))));}
  function noiseMultiplier(){const value=typeof v27Stats==='function'?v27Stats().noiseMult:1;return finite(value)?clamp(value,0,4):1;}
  function emit(kind,position,radiusM,strength=1,duration){
    if(pending.length>=K.CONFIG.maxSounds)pending.shift();
    pending.push({id:'v70-sound:'+ ++serial,kind,position:position.slice(),radiusM,strength,duration});
  }
  function recordShot(){
    if(!synchronise()||!onFoot())return false;
    const weapon=typeof WEAPONS==='undefined'?null:WEAPONS[state.weapon];
    if(!weapon||weapon.kind==='mêlée')return false;
    emit('gunfire',[camera.x,camera.z],45*noiseMultiplier(),1,2.4);return true;
  }
  function reportContact(sourceId,position,kind='camera'){
    if(!synchronise()||!position||!finite(position.x)||!finite(position.z))return false;
    const row={sourceId:String(sourceId),position:[position.x,position.z],kind,at:memory.clock};
    contacts=contacts.filter(item=>item.sourceId!==row.sourceId);contacts.push(row);
    if(contacts.length>64)contacts.shift();return true;
  }
  function isMachine(q){
    if(root.__SOMA_V42__?.isMachine)return root.__SOMA_V42__.isMachine(q);
    if(q.v32Enemy&&['rifle','melee','sniper','netrunner'].includes(q.v32Role))return false;
    return !!(q.v42Camera||q.kind==='policeDrone'||q.kind==='security'||['drone','turret'].includes(q.v32Role));
  }
  function visual(q,a,posture){
    const dx=camera.x-q.x,dz=camera.z-q.z,d=Math.hypot(dx,dz)||.01;
    const f=headingVec(q.heading||0),dot=(f.x*dx+f.z*dz)/d;
    if(d>=a.vision*(q.v33VisionFactor??1)*(posture?.65:1)||dot<=(q.state==='combat'?.05:.48))return'blocked';
    const sight=root.__SOMA_SIGHT61__;
    if(sight?.activeFor?.(activeZone)&&(!sight.eyePoint(q.x,q.z)||!sight.eyePoint(camera.x,camera.z)))return'unknown';
    return lineBlocked(q.x,q.z,camera.x,camera.z)?'blocked':'visible';
  }
  function phase(q){return q.state==='combat'?'combat':q.state==='search'?'search':'unaware';}
  function beginEnemyFrame(delta){
    const current=synchronise();if(!current)return null;
    const dt=finite(delta)?clamp(delta,0,K.CONFIG.maxStepSeconds):0;
    const robots=(current.robots||[]).filter(q=>q.v32Enemy&&q.health>0);
    const eligible=robots.filter(q=>!q.v26BossId&&!root.__SOMA_BOSSES36__?.suspended(q));
    const archetypes=root.__SOMA_V32__?.archetypes;
    if(!archetypes)return null;
    const posture=crouched(),point=[camera.x,camera.z],distance=previousPose?Math.hypot(point[0]-previousPose[0],point[1]-previousPose[1]):0;
    // Teleports and zone transitions do not manufacture footsteps. Movement
    // sound remains active when v42 playback or the master volume is muted.
    const travelled=onFoot()&&distance<=Math.max(3,50*dt)?distance:0;
    const movement={speed:dt>0?Math.min(50,travelled/dt):0,crouched:posture,noiseMultiplier:noiseMultiplier()};
    const signature=K.signature(movement);previousPose=point.slice();
    if(onFoot()){
      strideDistance+=travelled;
      const stride=posture?1.25:movement.speed>=4.5?1.85:1.55;
      if(strideDistance>=stride&&signature.level>0){strideDistance%=stride;emit('footstep',point,signature.radiusM,signature.level,.4);}
    }else strideDistance=0;
    contacts=contacts.filter(row=>memory.clock-row.at<K.CONFIG.memorySeconds);
    for(const [id,row]of foreign){row.left=Math.max(0,row.left-dt);if(!row.left)foreign.delete(id);}
    const previousOutput=output,trackMap=new Map(memory.tracks.map(row=>[row.id,{...row,lastKnown:row.lastKnown?.slice()??null}]));
    const groups=new Map(robots.map((q,i)=>[q.id,q.v33Squad||`${current.id}:${Math.floor(i/4)}`]));
    const rows=[];
    for(const q of eligible){
      if(entities.has(q.id)&&entities.get(q.id)!==q){trackMap.delete(q.id);written.delete(q.id);foreign.delete(q.id);}
      entities.set(q.id,q);
      const before=written.get(q.id),external=(!before||q.state!==before.state||q.detect>before.detect+.05)&&
        (q.state==='combat'||q.state==='search'||q.detect>=1);
      if(external){
        const shared=contacts.at(-1)||[...previousOutput.values()].find(row=>row.confirmed&&row.lastKnown&&groups.get(row.id)===groups.get(q.id));
        if(shared){
          const position=shared.position||shared.lastKnown;
          const remaining=shared.position?Math.max(0,5-(memory.clock-shared.at)):shared.memoryRemaining;
          trackMap.set(q.id,{id:q.id,suspicion:Math.max(1,clamp(q.detect||0,0,1.2)),phase:'combat',confirmed:true,
            memoryRemaining:clamp(remaining,0,5),lastKnown:position.slice(),lastSense:shared.lastSense||'visual',soundId:shared.soundId||null});
        }else foreign.set(q.id,{left:5,phase:q.state==='combat'?'combat':'search',detect:clamp(q.detect||0,0,1.2)});
      }
      const a=archetypes[q.v32Role]||archetypes.rifle,effects=root.__SOMA_V42__?.state?.().hacks?.[current.id]?.[q.id]||{};
      rows.push({id:q.id,position:[q.x,q.z],visual:visual(q,a,posture),hearingRange:Math.min(500,a.hearing||0),electronic:isMachine(q),
        effects:{blind:timer(effects.blind),lock:timer(effects.lock),jam:timer(effects.jam)},
        seed:{suspicion:clamp(q.detect||0,0,1.2),phase:phase(q),memoryRemaining:clamp(q.searchClock||0,0,5)}});
    }
    memory={...memory,tracks:[...trackMap.values()].filter(row=>eligible.some(q=>q.id===row.id))};
    try{
      const next=K.advance(memory,{dt,player:point,observers:rows,noises:pending,movement});
      memory=next.state;hud=next.hud;lastError=null;output=new Map(next.observers.map(row=>[row.id,row]));
      for(const [id,alert]of foreign){const row=output.get(id);if(row&&!row.canTrackCurrent&&!row.lastKnown){
        row.phase=alert.phase;row.confirmed=alert.phase==='combat';row.suspicion=Math.max(row.suspicion,alert.detect);
        row.memoryRemaining=alert.left;row.reason='external-alert-without-location';}}
    }catch(error){
      // A failed observation must never silently restore the old camera chase.
      lastError=String(error?.message||error);output=new Map(rows.map(row=>[row.id,{id:row.id,suspicion:0,phase:'search',confirmed:false,
        memoryRemaining:0,lastKnown:null,searchTarget:null,canTrackCurrent:false,canAttack:false,canMove:false,heard:false,
        audibility:0,lastSense:null,reason:'observation-rejected',effects:row.effects}]));
    }
    pending=[];
    hud={...hud,suspicion:Math.max(0,...[...output.values()].map(row=>row.suspicion)),
      visibleObservers:[...output.values()].filter(row=>row.canTrackCurrent).length,
      searchingObservers:[...output.values()].filter(row=>row.phase==='search').length,
      combatObservers:[...output.values()].filter(row=>row.phase==='combat').length,
      rememberedObservers:[...output.values()].filter(row=>row.lastKnown!==null).length};
    const live=new Set(eligible.map(q=>q.id));
    for(const map of [entities,written,foreign])for(const id of map.keys())if(!live.has(id))map.delete(id);
    return snapshotHUD();
  }
  function observer(id){const row=output.get(id);return row?copy(row):null;}
  function applied(q){written.set(q.id,{object:q,state:q.state,detect:q.detect});}
  function snapshotHUD(){return copy({...hud,zoneId:activeZone?.id??null,observerCount:output.size,activeSounds:memory.sounds.length,
    error:lastError,ready:true});}
  function snapshot(){const view=snapshotHUD();return{...view,hud:view,observers:[...output.values()].map(copy),sourceDataChanged:false};}
  root.__SOMA_PERCEPTION70__=Object.freeze({version:'0.70.0',beginEnemyFrame,observer,applied,recordShot,reportContact,
    snapshotHUD,snapshot,reset:()=>{reset();activeZone=zoneNow();}});
})(window);
