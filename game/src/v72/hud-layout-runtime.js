/* Current-edition presentation only: retain the original DOM nodes and owners. */
(function(root){
  'use strict';
  if(root.__SOMA_HUD72__)return;
  const GROUPS=Object.freeze({
    header:['.topbar'],
    navigation:['#v44-gps','#v34-route-hud','#nightObjective','#trackedObjective','#v42-city-hud','#v45-route'],
    status:['#v43-cred','#modeText','#v34-launcher','#v45-autosave','#v45-save-indicator','#v43-tracker','#v45-tracker','#v32-hud','#v33-hud'],
    alerts:['#notice','#policeHud','#v45-pursuit','#bossHud','#cyberHud27','#v42-target-hud','#v42-hackbar','#v42-channel','#v43-channel','#v45-channel','#v72-netrunner-hud'],
    vitals:['#level27','.stats'],
    context:['#v52-hud','#terrain56-hud','#quick28'],
    combat:['#v70-hud','#v43-weapon','#v42-posture-hud','#stance28','.weapon','#vehicleHud','#v44-vehicle-hud','#v45-fleet-hud'],
    footer:['#v54-attribution'],
  });
  const STYLE=`
body.soma-v72 #v72-hud-layout{
  position:absolute;inset:max(12px,env(safe-area-inset-top)) max(12px,env(safe-area-inset-right)) max(8px,env(safe-area-inset-bottom)) max(12px,env(safe-area-inset-left));
  display:grid;grid-template-columns:clamp(220px,24vw,320px) minmax(0,1fr) clamp(210px,22vw,300px);
  grid-template-rows:auto auto minmax(24px,1fr) auto auto;
  grid-template-areas:"header header header" "navigation alerts status" ". . ." "vitals context combat" "footer footer footer";
  gap:10px 12px;z-index:16;pointer-events:none;box-sizing:border-box;
}
body.soma-v72 #v72-hud-layout .v72-hud-slot{
  display:flex;flex-direction:column;gap:8px;min-width:0;align-self:start;pointer-events:none;
}
body.soma-v72 #v72-hud-layout [data-v72-hud-slot="vitals"],
body.soma-v72 #v72-hud-layout [data-v72-hud-slot="context"],
body.soma-v72 #v72-hud-layout [data-v72-hud-slot="combat"]{align-self:end;}
body.soma-v72 #v72-hud-layout [data-v72-hud-slot="context"],
body.soma-v72 #v72-hud-layout [data-v72-hud-slot="alerts"]{width:min(100%,620px);justify-self:center;}
body.soma-v72 #v72-hud-layout [data-v72-hud]{
  position:static!important;inset:auto!important;transform:none!important;margin:0!important;
  width:100%!important;min-width:0!important;max-width:100%!important;box-sizing:border-box;
  z-index:auto!important;overflow-wrap:anywhere;
}
body.soma-v72 #v72-hud-layout [data-v72-hud][hidden]{display:none!important;}
body.soma-v72 #v72-hud-layout :is(button,a,input,select){pointer-events:auto;}
body.soma-v72 #v72-hud-layout :is(button,a,input,select):focus-visible{outline:3px solid #ffbc78;outline-offset:3px;}
body.soma-v72 #v72-hud-layout .topbar{
  display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1.5fr);gap:12px;align-items:center;
  padding:4px 0 8px;background:linear-gradient(#031019d9,#03101955,transparent);
}
body.soma-v72 #v72-hud-layout .topbar>*{min-width:0;max-width:100%;}
body.soma-v72 #v72-hud-layout .topbar .zone{text-align:right;white-space:normal;line-height:1.45;}
body.soma-v72 #v72-hud-layout .city-clock{white-space:nowrap;}
body.soma-v72 #v72-hud-layout #v43-cred{padding:7px 10px;}
body.soma-v72 #v72-hud-layout #modeText{padding:0 2px;text-align:right;}
body.soma-v72 #v72-hud-layout #v34-launcher{align-self:flex-end;width:auto!important;}
body.soma-v72 #v72-hud-layout #v45-autosave::before{content:none;}
body.soma-v72 #v72-hud-layout :is(#notice,#v45-autosave,#vehicleHud,#policeHud):not(.on){display:none!important;}
body.soma-v72 #v72-hud-layout :is(#v44-gps,#v34-route-hud,#nightObjective,#trackedObjective,#v45-tracker,#v52-hud){white-space:normal;}
body.soma-v72 #v72-hud-layout :is(#v44-gps,#v34-route-hud,#v45-tracker,#v52-hud) :is(b,strong,span,p){white-space:normal;overflow-wrap:anywhere;}
body.soma-v72 #v72-hud-layout #v52-hud{padding:9px 11px;}
body.soma-v72 #v72-hud-layout #terrain56-hud{font-size:11px;padding:6px 9px;}
body.soma-v72 #v72-hud-layout #level27{width:max-content!important;}
body.soma-v72 #v72-hud-layout .stats{padding:10px 11px;}
body.soma-v72 #v72-hud-layout .stats .row{grid-template-columns:74px minmax(0,1fr) max-content;gap:6px;}
body.soma-v72 #v72-hud-layout .stats .row>b{white-space:nowrap;overflow-wrap:normal;font-variant-numeric:tabular-nums;}
body.soma-v72 #v72-hud-layout .weapon{
  text-align:right;background:#0b131bcc;border:0;border-bottom:2px solid var(--v34-amber,#ffb35f);
  padding:12px 14px;box-shadow:0 5px 20px #0006;
}
body.soma-v72 #v72-hud-layout #stance28{text-align:right;}
body.soma-v72 #v72-hud-layout #v42-posture-hud{text-align:right;}
body.soma-v72 #v72-hud-layout #quick28{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;}
body.soma-v72 #v72-hud-layout #quick28 button{min-width:0;max-width:100%;white-space:normal;overflow-wrap:anywhere;}
body.soma-v72 #v72-hud-layout #v54-attribution{width:max-content!important;max-width:100%!important;white-space:normal;line-height:1.45;}
/* The v65 direct-body selectors no longer reach moved nodes. Preserve both
   existing menu gates explicitly, including pointer access for descendants. */
body.soma-v72:has(.modal.open) #v72-hud-layout,
body.soma-v72:has(.modal.open) #v72-hud-layout *,
body.soma-v72.v34-menu-open #v72-hud-layout,
body.soma-v72.v34-menu-open #v72-hud-layout *{visibility:hidden!important;pointer-events:none!important;}
@media(max-height:800px){
  body.soma-v72 #v72-hud-layout{gap:7px 10px;}
  body.soma-v72 #v72-hud-layout .v72-hud-slot{gap:6px;}
  body.soma-v72 #v72-hud-layout #v70-hud{padding:6px 8px;}
}
@media(max-width:1100px){
  body.soma-v72 #v72-hud-layout #quick28{grid-template-columns:repeat(2,minmax(0,1fr));}
  body.soma-v72 #v72-hud-layout .topbar .zone{font-size:10px;letter-spacing:.03em;}
}
@media(max-width:900px){
  body.soma-v72 #v72-hud-layout{grid-template-columns:minmax(0,1fr) minmax(0,1.15fr) minmax(0,1fr);gap:6px;}
  body.soma-v72 #v72-hud-layout .topbar{grid-template-columns:minmax(0,1fr) auto;}
  body.soma-v72 #v72-hud-layout .topbar .zone{grid-column:1/-1;text-align:left;}
  body.soma-v72 #v72-hud-layout .stats .row{grid-template-columns:58px minmax(0,1fr) max-content;gap:4px;}
}
/* Keep the existing narrow-screen policy for consumables. */
@media(max-width:760px){body.soma-v72 #v72-hud-layout #quick28{display:none!important;}}
`;
  function install(){
    const hud=document.querySelector('.game > .hud'),game=hud?.parentElement;
    if(!hud||!game)return;
    document.body.classList.add('soma-v72');
    const style=document.createElement('style');style.id='soma-v72-hud-style';
    const layout=document.createElement('div');layout.id='v72-hud-layout';
    const slots=new Map(),rules=[],managed=new Map();
    for(const [name,selectors]of Object.entries(GROUPS)){
      const slot=document.createElement('div');slot.className='v72-hud-slot';slot.dataset.v72HudSlot=name;
      slot.style.gridArea=name;layout.appendChild(slot);slots.set(name,slot);
      selectors.forEach((selector,i)=>rules.push('#v72-hud-layout [data-v72-hud="'+selector.slice(1)+'"]{order:'+i+'}'));
    }
    style.textContent=STYLE+'\n'+rules.join('\n');document.head.appendChild(style);hud.appendChild(layout);
    function mount(){
      for(const [name,selectors]of Object.entries(GROUPS))for(const selector of selectors){
        const node=selector[0]==='#'?document.getElementById(selector.slice(1)):hud.querySelector(selector);
        if(!node||node.parentElement===slots.get(name))continue;
        node.dataset.v72Hud=selector.slice(1);slots.get(name).appendChild(node);managed.set(selector,node);
      }
    }
    mount();layout.dataset.ready='true';
    // Owners create a few HUD roots lazily. Observe only insertion points,
    // never their per-frame text/innerHTML updates, and never poll game state.
    const observer=new MutationObserver(records=>{
      if(records.some(row=>Array.from(row.addedNodes).some(node=>node.nodeType===1)))mount();
    });
    observer.observe(document.body,{childList:true});observer.observe(game,{childList:true});observer.observe(hud,{childList:true});
    root.__SOMA_HUD72__=Object.freeze({version:'0.72.0',ready:true,
      snapshot:()=>({version:'0.72.0',managed:Array.from(managed.keys()),groups:Object.keys(GROUPS),persistent:false})});
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});else install();
})(window);
