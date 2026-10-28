/* Read-only architectural inspection; the viewer owns the short scene lease. */
(function(root){
  'use strict';
  const clone=v=>JSON.parse(JSON.stringify(v));
  function createController(context,view={}){
    for(const key of ['acquire','inspect','available'])if(typeof context?.[key]!=='function')throw new TypeError('Inspection context missing '+key);
    let session=null,last=null,phase='closed',nonce=0;
    async function release(active){const lease=active.lease;active.lease=null;await lease?.release();}
    async function close(){
      const active=session;if(!active)return;if(active.closing)return active.closing;nonce++;phase='closing';active.abort.abort();
      active.closing=(async()=>{try{await active.opening;await release(active);}
      finally{if(session===active){session=null;phase='closed';view.hide?.();}}})();return active.closing;
    }
    async function open(){
      if(session||!context.available())return false;
      const token=++nonce,active={abort:new AbortController(),lease:null,opening:null};session=active;last=null;phase='waiting';view.show?.();view.waiting?.();
      active.opening=(async()=>{
        try{
          active.lease=await context.acquire({signal:active.abort.signal});
          if(session!==active||token!==nonce||active.abort.signal.aborted){await release(active);return false;}
          last=context.inspect();phase='ready';view.render?.(clone(last));return true;
        }catch(error){if(!active.abort.signal.aborted){phase='error';view.error?.(error?.message||String(error));}return false;}
      })();
      return active.opening;
    }
    context.onWorldChange?.(()=>{last=null;void close();});
    return Object.freeze({open,close,snapshot:()=>({version:'0.71.0',phase,open:!!session,result:last?clone(last):null})});
  }
  const number=n=>typeof n==='number'&&Number.isFinite(n)?new Intl.NumberFormat('fr-FR',{maximumFractionDigits:1}).format(n)+' m':'Non disponible';
  const HEIGHT={'osm-height':'Hauteur déclarée OSM','osm-levels':'Hauteur estimée à partir des niveaux OSM','estimated-from-levels':'Hauteur estimée à partir des niveaux OSM','ign-bdtopo-height':'Référence IGN appariée','procedural-estimate':'Hauteur estimée'};
  const MATERIAL={'osm-building-colour':'Couleur déclarée OSM','osm-roof-colour':'Couleur déclarée OSM','osm-building-material':'Palette interprétée depuis le matériau OSM','osm-building-facade-material':'Palette interprétée depuis le matériau de façade OSM','osm-roof-material':'Palette interprétée depuis le matériau OSM','interpreted-marseille-palette':'Palette régionale interprétée'};
  function mount(context,document=root.document){
    const $=id=>document.getElementById(id),dialog=$('architecture71-dialog');
    if(!dialog)throw new Error('Architectural inspection panel is absent.');
    const write=(id,value)=>{$(id).textContent=value;};
    function clear(){for(const id of ['architecture71-facts','architecture71-tags'])$(id).replaceChildren();$('architecture71-source').hidden=true;}
    function row(label,value,quality){
      const item=document.createElement('div'),title=document.createElement('dt'),body=document.createElement('dd'),note=document.createElement('small');
      title.textContent=label;body.textContent=value;note.textContent=quality;body.append(note);item.append(title,body);$('architecture71-facts').append(item);
    }
    const view={show(){if(!dialog.open)dialog.showModal();},hide(){if(dialog.open)dialog.close();},waiting(){clear();write('architecture71-status','Stabilisation de la vue avant lecture du bâtiment visé…');},
      error(message){clear();write('architecture71-status','Inspection indisponible : '+message);},render(result){
        clear();const s=result.selection;
        if(!s){write('architecture71-name','Inspecter un bâtiment');write('architecture71-status',result.status==='budget'?'La vue dépasse le budget d’inspection. Rapprochez-vous du bâtiment.':result.status==='occluded'?'Le réticule rencontre le terrain ou une autre surface. Visez une façade ou un toit visible.':'Aucun bâtiment visible sous le réticule à moins de 1 500 m.');return;}
        write('architecture71-name',s.name||'Bâtiment OSM');write('architecture71-status','Bâtiment visible à '+number(s.distanceMeters)+' · '+s.id);
        row(s.heightKind==='eaves'?'Hauteur à l’égout utilisée':'Hauteur utilisée dans le modèle',number(s.heightMeters),HEIGHT[s.heightSource]||'Hauteur estimée ou dérivée ; voir les tags source.');
        row('Base du modèle · NGF',number(s.baseAltitudeNGFMeters),s.baseQuality==='matched-source-base'?'Altitude de la référence IGN appariée.':'Base dérivée du relief IGN disponible, sans précision de seuil ou de trottoir certifiée.');
        row('Toiture',s.roof.displayedShape+(s.roof.requestedShape&&s.roof.requestedShape!==s.roof.displayedShape?' · tag : '+s.roof.requestedShape:''),s.roof.quality==='unsurveyed-eaves-approximation'?'Toit plat d’approximation au niveau de l’égout ; le toit n’est pas relevé.':s.roof.quality==='inferred-parametric'?'Profil paramétrique inféré ; ses paramètres ne constituent pas un relevé du toit.':'Toiture non relevée ; représentation approximative.');
        row('Façade',MATERIAL[s.appearance.wallSource]||'Palette interprétée', 'Fenêtres et lumières cyberpunk interprétées ; disposition de façade non relevée.');
        row('Couverture',MATERIAL[s.appearance.roofSource]||'Palette interprétée','La palette du matériau ne constitue pas une mesure de couleur ou une texture relevée.');
        row('Emprise', 'Triangles préparés depuis OSM','Les contours et cours restent ceux des données disponibles. La précision architecturale 1:1 et l’accès physique ne sont pas certifiés.');
        for(const [key,value]of Object.entries(s.sourceTags)){const tr=document.createElement('tr'),a=document.createElement('th'),b=document.createElement('td');a.textContent=key;b.textContent=value;tr.append(a,b);$('architecture71-tags').append(tr);}
        const source=$('architecture71-source');if(s.osmURL){source.href=s.osmURL;source.hidden=false;}
      }};
    const controller=createController(context,view);
    $('architecture71-open').onclick=()=>{void controller.open();};$('architecture71-close').onclick=()=>{void controller.close();};
    dialog.addEventListener('cancel',e=>{e.preventDefault();void controller.close();});
    document.addEventListener('keydown',e=>{
      if(e.code!=='KeyI'||e.repeat||e.altKey||e.ctrlKey||e.metaKey||e.target?.closest?.('input,textarea,select,[contenteditable="true"]'))return;
      if(document.querySelector('dialog[open]')!==dialog&&document.querySelector('dialog[open]'))return;
      e.preventDefault();e.stopImmediatePropagation();if(controller.snapshot().open)void controller.close();else void controller.open();
    },true);
    return controller;
  }
  const API=Object.freeze({VERSION:'0.71.0',createController,mount});root.__SOMA_ARCHITECTURE71_UI_CORE__=API;
  if(typeof module!=='undefined'&&module.exports)module.exports=API;
  if(root.document){
    const viewer=root.__SOMA_METROPOLE_VIEWER__||root.__SOMA_METRO_VIEWER__;
    if(typeof viewer?.architectureContext==='function')root.__SOMA_ARCHITECTURE71_VIEWER__=mount(viewer.architectureContext());
    else{const button=root.document.getElementById('architecture71-open');if(button)button.disabled=true;}
  }
})(typeof window!=='undefined'?window:globalThis);
