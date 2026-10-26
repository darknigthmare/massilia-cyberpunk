/* Original tactical implants: the campaign owns resources and all real effects.
 * No geometry changes, free energy, global time dilation or second save slot.
 */
(function(root){
  'use strict';
  const A=root.__SOMA_AUG70_CORE__||(typeof require==='function'?require('./augmentations-core.js'):null);
  if(!A)throw new Error('Augmentations core must load before campaign adapter.');
  function createController(bridge){
    for(const name of ['read','write','context','spend','schedule'])if(typeof bridge?.[name]!=='function')throw new TypeError('Campaign bridge missing '+name);
    let value=A.restore(bridge.read()),saveClock=0,lastReason='ready';
    const sync=()=>bridge.write(A.serialize(value));
    sync();
    return{
      activate(id){
        if(bridge.ready&&bridge.ready()!==true){lastReason='campaign-unavailable';return{accepted:false,reason:lastReason,energyCost:0,tensionDelta:0};}
        if(id==='focus'&&bridge.focusAllowed&&bridge.focusAllowed()!==true){lastReason='reduced-motion';return{accepted:false,reason:lastReason,energyCost:0,tensionDelta:0};}
        const result=A.activate(value,id,bridge.context());lastReason=result.reason;
        if(!result.accepted)return result;
        // The resource bridge rechecks the real deck before committing. A failed
        // debit must never award a buff, a counter or a cooldown.
        if(bridge.spend(result.energyCost,result.tensionDelta)!==true){lastReason='resource-changed';return{accepted:false,reason:lastReason,energyCost:0,tensionDelta:0};}
        value=result.state;sync();bridge.schedule();return{...result,state:A.serialize(value)};
      },
      tick(dt){
        const c=bridge.context(),before=A.serialize(value);
        value=A.advance(value,dt,{paused:c.paused,health:c.health,onFoot:c.onFoot&&!c.driving&&!c.cyberspace});sync();
        if(!c.paused){saveClock+=dt;if(saveClock>=1){saveClock=0;if(JSON.stringify(before)!==JSON.stringify(A.serialize(value)))bridge.schedule();}}
      },
      mitigate(amount){
        const c=bridge.context();
        if(c.paused||!c.onFoot||c.driving||c.cyberspace||c.health<=0)return{damage:amount,absorbed:0};
        const result=A.mitigate(value,amount);
        if(result.absorbed>0){value=result.state;sync();bridge.schedule();}
        return{damage:result.damage,absorbed:result.absorbed};
      },
      restore(raw){value=A.restore(raw);saveClock=0;lastReason='restored';sync();},
      modifiers:()=>A.modifiers(value),
      snapshot:()=>({persisted:A.serialize(value),active:{...value.active},barrierRemaining:value.barrierRemaining,modifiers:A.modifiers(value),lastReason}),
      flush:sync
    };
  }
  function wrapDamage(controller,previous,canMitigate){
    if(typeof previous!=='function'||typeof canMitigate!=='function')throw new TypeError('A real guarded damage hook is required.');
    return function(amount,...args){
      if(canMitigate()!==true||!Number.isFinite(amount)||amount<=0||amount>A.CONFIG.maxDamage)return previous.call(this,amount,...args);
      return previous.call(this,controller.mitigate(amount).damage,...args);
    };
  }
  function handleShortcut(event,actions){
    if(event.repeat||event.altKey||event.ctrlKey||event.metaKey||!event.shiftKey)return false;
    const id=({F2:'scan',F3:'barrier',F4:'focus'})[event.code];
    if(event.code!=='F1'&&typeof id!=='string')return false;
    // Claim the chord before checking gameplay context: otherwise a refused
    // implant in a vehicle falls through to the old F-key consumable handler.
    event.preventDefault();event.stopImmediatePropagation();
    if(event.target?.closest?.('input,textarea,select,[contenteditable="true"]'))return true;
    if(event.code==='F1'){if(actions.hasZone)actions.togglePanel();return true;}
    actions.activate(id);return true;
  }
  const API=Object.freeze({createController,wrapDamage,handleShortcut});
  if(typeof module==='object'&&module.exports)module.exports=API;
  if(!root.document)return;

  const VERSION='0.70.0',PANEL='v70-tactics';
  const names={scan:'Écho de trame',barrier:'Rempart cortical',focus:'Ancrage réflexe'};
  const help={scan:'Lit les unités visibles pendant 5 s. Les obstacles restent opaques.',
    barrier:'Réduit les impacts de combat de 55 %, jusqu’à 40 points absorbés, pendant 4 s.',
    focus:'Réduit de 35 % le recul de visée pendant 5 s. Ne modifie ni dégâts ni portée.'};
  const reasons={paused:'Reprenez la partie avant activation.',dead:'Continuité corporelle interrompue.',driving:'Activation disponible à pied.',
    cyberspace:'Sortez de la plongée avant activation.','not-on-foot':'Rejoignez la rue à pied.',channeling:'Terminez la liaison en cours.',
    'neural-instability':'Tension trop élevée.','already-active':'Implant déjà actif.',cooldown:'Implant en récupération.',
    'insufficient-energy':'Charge cyberdeck insuffisante.','neural-overload':'Charge neurale trop élevée.',
    'campaign-unavailable':'La continuité doit être prête avant activation.','reduced-motion':'Le mouvement réduit neutralise déjà le recul de visée.',
    'resource-changed':'Le cyberdeck ne peut pas régler ce coût.','unknown-augmentation':'Implant inconnu.'};
  let controller=null,incomingReducer=null,installed=false,uiClock=0,lastZone=null,scanRows=[],message='';
  const number=(n,fallback=0)=>typeof n==='number'&&Number.isFinite(n)?n:fallback;
  const bounded=(n,min,max)=>Math.max(min,Math.min(max,number(n)));
  const deck=()=>root.__SOMA_V42__?.state?.().cyberdeck;
  function context(){return{
    energy:bounded(deck()?.energy,0,1000),health:bounded(state.health,0,10000),
    onFoot:!!root.__SOMA_V42__?.canUseOnFoot?.(),paused:!!paused,
    channeling:!!root.__SOMA_V42__?.isChanneling?.(),driving:!!state.driving,
    cyberspace:typeof v27IsCyber==='function'&&!!v27IsCyber(),tension:bounded(state.tension,0,100)
  };}
  function saveReady(){const s=root.__SOMA_V37_SAVE__?.getStatus?.();return s?.ready===true&&s.blocked!==true;}
  function spend(cost,tensionDelta){
    if(!saveReady()||!Number.isFinite(cost)||!Number.isFinite(tensionDelta)||
      !Number.isFinite(state.tension)||state.tension+tensionDelta>100||number(deck()?.energy,-1)<cost)return false;
    if(root.__SOMA_V42__.debitEnergy(cost)!==true)return false;
    state.tension=Math.max(0,Math.min(100,state.tension+tensionDelta));return true;
  }
  function announceResult(result,id){
    message=result.accepted?names[id]+' actif.':reasons[result.reason]||'Activation indisponible.';
    if(typeof announce==='function')announce(message,2);render();
  }
  function activate(id){const result=controller.activate(id);announceResult(result,id);return result;}
  function scan(){
    if(!controller.modifiers().scanActive||!zone||!context().onFoot)return[];
    const rows=[];
    for(const q of zone.robots||[]){
      if(!(q.health>0)||!Number.isFinite(q.x)||!Number.isFinite(q.z))continue;
      const distance=Math.hypot(q.x-camera.x,q.z-camera.z);
      if(distance>24||typeof lineBlocked!=='function'||lineBlocked(camera.x,camera.z,q.x,q.z))continue;
      rows.push({id:String(q.id),label:String(q.v32Label||q.name||q.label||(q.v42Camera?'Caméra':'Signal local')),
        distance,healthPercent:Math.round(bounded(q.health/Math.max(1,number(q.maxHealth,q.health))*100,0,100)),
        electronic:!!(q.v42Camera||['drone','turret'].includes(q.v32Role)||['policeDrone','security'].includes(q.kind))});
    }
    return rows.sort((a,b)=>a.distance-b.distance||a.id.localeCompare(b.id)).slice(0,8);
  }
  function open(){if(!zone||state.health<=0)return false;render();openModal(PANEL);render();return true;}
  function runFromPanel(id){closeModals();return activate(id);}
  function mount(){
    const style=document.createElement('style');style.id='soma-v70-style';
    style.textContent=`#v70-hud{position:fixed;bottom:236px;left:18px;z-index:12;box-sizing:border-box;width:250px;pointer-events:none;font:11px monospace;color:#d8f6ef;background:#07171cda;border:1px solid #39767b;border-top:2px solid #75e3db;padding:7px 10px;border-radius:3px}#v70-hud[hidden]{display:none}#v70-hud b{color:#8aeee1}#v70-hud p{margin:3px 0}#v70-tactics .panel{max-width:840px;max-height:90vh;overflow:auto}#v70-tactics .v70-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}#v70-tactics article{background:#0a1c24;border:1px solid #32626d;padding:14px}#v70-tactics h3{color:#94ebe2;margin:0 0 8px}#v70-tactics p{line-height:1.5}#v70-tactics small{color:#a6c1c8}#v70-tactics button:focus-visible{outline:3px solid #efd39a;outline-offset:3px}#v70-tactics [data-v70-message]{color:#efd39a;min-height:1.6em}#v70-tactics .v70-readout{display:flex;flex-wrap:wrap;gap:16px;padding:12px;background:#061219;margin:14px 0}#v70-tactics .v70-scan{padding-left:20px}@media(max-width:700px){#v70-hud{left:8px;width:min(250px,calc(100vw - 16px));font-size:10px}#v70-tactics .v70-grid{grid-template-columns:1fr}}`;
    document.head.append(style);
    const hud=document.createElement('aside');hud.id='v70-hud';hud.setAttribute('aria-label','État tactique');hud.hidden=true;
    hud.innerHTML='<b>CORTEX TACTIQUE · MAJ+F1</b><p data-v70-energy></p><p data-v70-perception></p><p data-v70-active></p>';document.body.append(hud);
    const modal=document.createElement('div');modal.id=PANEL;modal.className='modal';
    modal.innerHTML='<div class="panel" role="dialog" aria-modal="true" aria-labelledby="v70-title"><h2 id="v70-title">Cortex tactique</h2><p>Trois protocoles actifs alimentés par votre cyberdeck. Les puces et talents existants restent pris en compte par le combat et la discrétion.</p><div class="v70-readout"><span data-v70-deck></span><span data-v70-load></span><span data-v70-tension></span></div><div class="v70-grid"></div><p data-v70-message role="status" aria-live="polite"></p><h3>Unités visibles · Écho de trame</h3><ul class="v70-scan"></ul><h3>Intrusion urbaine</h3><p data-v70-target></p><div data-v70-hacks></div><p><small>Rempart et Ancrage interrompent l’accès aux hacks pendant leur activation. Écho reste compatible. Les implants cessent au chargement ; les délais et la charge neurale restent enregistrés.</small></p><div class="actions"><button type="button" data-v70-close>Revenir à la rue</button></div></div>';
    document.body.append(modal);
    const grid=modal.querySelector('.v70-grid');
    for(const [i,id]of ['scan','barrier','focus'].entries()){
      const card=document.createElement('article'),title=document.createElement('h3'),text=document.createElement('p'),cost=document.createElement('small'),status=document.createElement('p'),button=document.createElement('button');
      title.textContent=names[id]+' · Maj+F'+(i+2);text.textContent=help[id];status.dataset.v70Status=id;
      cost.textContent='Charge +'+A.ABILITIES[id].traceGain+' · tension à partir de +'+A.ABILITIES[id].tension;
      button.type='button';button.dataset.v70Ability=id;button.textContent='Activer · '+A.ABILITIES[id].cost+' énergie';button.onclick=()=>runFromPanel(id);
      card.append(title,text,cost,status,button);grid.append(card);
    }
    modal.querySelector('[data-v70-close]').onclick=()=>closeModals();
    const cortex=document.querySelector('#cortex .actions')||document.querySelector('#cortex .panel');
    if(cortex&&!document.querySelector('[data-v70-open]')){
      const button=document.createElement('button');button.type='button';button.dataset.v70Open='1';
      button.textContent='Augmentations actives';button.onclick=open;cortex.append(button);
    }
    const hacks=modal.querySelector('[data-v70-hacks]');
    for(const [id,def]of Object.entries(root.__SOMA_V42__.programs||{})){
      const button=document.createElement('button');button.type='button';button.dataset.v70Hack=id;
      button.textContent=def.name+' · '+def.cost+' énergie';button.onclick=()=>{closeModals();const result=root.__SOMA_V42__.beginHack(id);message=result?'Liaison engagée.':'Visez une machine accessible ; vérifiez énergie et récupération.';render();};hacks.append(button);
    }
    document.addEventListener('keydown',event=>handleShortcut(event,{hasZone:!!zone,activate,
      togglePanel:()=>{if(modal.classList.contains('open'))closeModals();else open();}}),true);
  }
  function render(){
    if(!controller)return;
    const s=controller.snapshot(),c=context(),hud=document.getElementById('v70-hud'),modal=document.getElementById(PANEL);
    hud.hidden=!c.onFoot||c.paused;
    const percept=root.__SOMA_PERCEPTION70__?.snapshotHUD?.()||root.__SOMA_PERCEPTION70__?.snapshot?.()?.hud||{};
    const signature=({still:'à l’arrêt',crouched:'accroupi',sprinting:'course',walking:'marche'})[percept.signature?.posture]||'à pied',suspicion=Math.round(bounded(percept.suspicion,0,1)*100);
    hud.querySelector('[data-v70-energy]').textContent='Cyberdeck '+Math.floor(c.energy)+' · charge neurale '+Math.round(s.persisted.trace)+'%';
    const level=number(percept.signature?.level),noise=level<=0?'silencieux':level<.3?'discret':level<.65?'audible':'bruyant';
    hud.querySelector('[data-v70-perception]').textContent=signature+' · '+noise+' · suspicion '+suspicion+'%';
    const active=Object.entries(s.active).filter(([,time])=>time>0).map(([id,time])=>names[id]+' '+time.toFixed(1)+' s');
    scanRows=scan();
    hud.querySelector('[data-v70-active]').textContent=(active.join(' · ')||'Maj+F2 Écho · Maj+F3 Rempart · Maj+F4 Ancrage')+
      (s.modifiers.scanActive?' · '+scanRows.length+' signal'+(scanRows.length===1?'':'s')+' visible'+(scanRows.length===1?'':'s'):'');
    modal.querySelector('[data-v70-deck]').textContent='Cyberdeck '+Math.floor(c.energy)+' / '+Math.floor(number(deck()?.max,100));
    modal.querySelector('[data-v70-load]').textContent='Charge neurale '+Math.round(s.persisted.trace)+' / 100';
    modal.querySelector('[data-v70-tension]').textContent='Tension '+Math.round(c.tension)+' / 100';
    modal.querySelector('[data-v70-message]').textContent=message;
    for(const id of ['scan','barrier','focus']){
      const status=modal.querySelector('[data-v70-status="'+id+'"]'),button=modal.querySelector('[data-v70-ability="'+id+'"]');
      status.textContent=s.active[id]>0?'Actif · '+s.active[id].toFixed(1)+' s':s.persisted.cooldowns[id]>0?'Récupération · '+Math.ceil(s.persisted.cooldowns[id])+' s':'Prêt · attente '+A.ABILITIES[id].cooldown+' s';
      button.disabled=s.active[id]>0||s.persisted.cooldowns[id]>0||c.energy<A.ABILITIES[id].cost||c.channeling||!c.onFoot||!saveReady()||(id==='focus'&&!!state.settings?.reduceMotion);
    }
    const list=modal.querySelector('.v70-scan');list.replaceChildren();
    for(const row of scanRows){const li=document.createElement('li');li.textContent=row.label+' · '+Math.round(row.distance)+' m · intégrité '+row.healthPercent+'%'+(row.electronic?' · système électronique':'');list.append(li);}
    if(!scanRows.length){const li=document.createElement('li');li.textContent=s.modifiers.scanActive?'Aucune unité visible à portée.':'Activez Écho pour lire les unités visibles.';list.append(li);}
    const target=root.__SOMA_V42__.targetMachine?.();
    modal.querySelector('[data-v70-target]').textContent=target?String(target.v32Label||target.label||'Machine ciblée')+' · '+Math.round(Math.hypot(target.x-camera.x,target.z-camera.z))+' m':'Visez une machine à moins de 18 m, sans obstacle.';
    for(const button of modal.querySelectorAll('[data-v70-hack]'))button.disabled=!target||s.modifiers.blocksHacking||c.channeling||!c.onFoot;
  }
  function tick(dt){
    if(!controller||!Number.isFinite(dt)||dt<0)return;
    const zoneId=zone?.id||null;
    if(lastZone!==null&&lastZone!==zoneId){const raw=controller.snapshot().persisted;controller.restore(raw);}
    lastZone=zoneId;controller.tick(Math.min(dt,.25));uiClock+=dt;
    if(uiClock>=.2){uiClock=0;render();}
  }
  function mitigateIncoming(amount){
    return incomingReducer?incomingReducer(amount):amount;
  }
  function setup(){
    if(installed)return;
    if(!root.__SOMA_V69__||!root.__SOMA_V42__?.debitEnergy||!root.__SOMA_V42__?.canUseOnFoot||!saveReady()){
      setTimeout(setup,100);return;
    }
    controller=createController({read:()=>state.v70,write:value=>{state.v70=value;},context,spend,
      ready:saveReady,focusAllowed:()=>!state.settings?.reduceMotion,schedule:()=>root.__SOMA_V37_SAVE__.schedule()});
    const hooks=root.__SOMA_V32_COMBAT_HOOKS__;
    if(!hooks||typeof hooks.damage!=='function')throw new Error('Real combat damage hook unavailable.');
    incomingReducer=wrapDamage(controller,amount=>amount,()=>!paused&&!state.recovery?.pending&&!(state.recoveryGrace>0));
    mount();installed=true;
    root.__SOMA_V70__={version:VERSION,ready:true,activate,open,tick,mitigateIncoming,
      modifiers:()=>controller.modifiers(),blocksHacking:()=>controller.modifiers().blocksHacking,
      restoreCampaign(raw){controller.restore(raw);lastZone=null;scanRows=[];root.__SOMA_PERCEPTION70__?.reset?.();render();},
      snapshot:()=>({version:VERSION,...controller.snapshot(),energy:number(deck()?.energy),tension:number(state.tension),
        channel:root.__SOMA_V42__.channelStatus?.()||null,scanTargets:scanRows.map(v=>({...v})),perception:root.__SOMA_PERCEPTION70__?.snapshot?.()||null})};
    root.__SOMA__.version=VERSION;document.title='SOMA//MASSILIA 0.70 — Cortex tactique';
    for(const selector of ['.v34-edition span','.topbar .brand small']){const item=document.querySelector(selector);if(item)item.textContent='0.70';}
    render();
  }
  setup();
})(typeof window!=='undefined'?window:globalThis);
