/* Optional local route UI for the independent 0.70 flyover only.
 * Source graphs are read on demand while the scene owns no network request.
 * The lease is released after cancellation and byte-reader drainage.
 */
(function(root){
  'use strict';
  const EXAMPLE=Object.freeze({start:Object.freeze({e:892990.7467568527,n:6247192.082113549}),
    end:Object.freeze({e:892549.919307699,n:6247324.880334723}),mode:'foot',maxAxisDistanceM:.05});
  const copy=v=>JSON.parse(JSON.stringify(v));
  const message=error=>String(error?.message||error||'Erreur inconnue.').slice(0,500);
  const cancelled=()=>Object.assign(new Error('Analyse annulée.'),{name:'AbortError'});
  function summary(result){
    if(!result)return null;
    return {status:result.status,code:result.code,lengthMeters:result.route?.lengthMeters??null,mode:result.route?.mode??null,
      points:result.route?.points.length||0,segments:result.route?.segments.length||0,loadedCells:result.coverage?.loadedCells.length||0,
      resources:result.resources?copy(result.resources):null,sourcePbfSHA256:result.sourcePbfSHA256,
      physicalAccessibilityVerified:false,campaignRoutingActivated:false};
  }
  function createController({context,view,routeCore=root.__SOMA_ROUTE70_CORE__,routerCore=root.__SOMA_NAV63_CORE__}){
    if(typeof context?.acquireRouteLease!=='function'||typeof context?.readRouteAsset!=='function'||typeof context?.world!=='function'||
      typeof view?.show!=='function'||typeof view?.render!=='function'||typeof routeCore?.create!=='function')throw new TypeError('Contexte de survol et interface requis.');
    let session=null,last=null,opening=null,closing=null,operation=null,serial=0,reads=0,maximumConcurrentReads=0,inFlight=0;
    const state={open:false,phase:'closed',error:'',analyses:0};
    function notify(){view.state?.({...state,busy:state.phase==='computing'||state.phase==='waiting-scene'});}
    async function open(){
      if(closing)await closing;
      if(session)return opening;
      const current={id:++serial,abort:new AbortController(),computeAbort:null,lease:null,preview:null};session=current;
      state.open=true;state.phase='waiting-scene';state.error='';last=null;view.show();view.clear?.();notify();
      opening=(async()=>{
        try{current.lease=await context.acquireRouteLease({signal:current.abort.signal});
          if(session!==current||current.abort.signal.aborted){await current.lease.release();throw cancelled();}
          state.phase='ready';notify();return true;
        }catch(error){if(session===current&&!current.abort.signal.aborted){state.phase='error';state.error=message(error);view.error?.(state.error);notify();}return false;}
      })();
      return opening;
    }
    async function compute(request){
      if(operation)return operation;
      const current=session;if(!current)return null;
      operation=(async()=>{
        if(!await opening||session!==current||current.abort.signal.aborted)return null;
        const computeAbort=new AbortController();current.computeAbort=computeAbort;
        const abort=()=>computeAbort.abort();current.abort.signal.addEventListener('abort',abort,{once:true});
        state.phase='computing';state.error='';last=null;view.clear?.();notify();
        try{
          if(!current.preview)current.preview=routeCore.create({world:context.world(),routerCore,routerCoreSHA256:routeCore.CORE_SHA256,
            loadAsset:async(descriptor,options)=>{
              if(session!==current||current.abort.signal.aborted)throw cancelled();
              if(inFlight)throw new Error('Une seule lecture NAV est admise.');
              reads++;inFlight++;maximumConcurrentReads=Math.max(maximumConcurrentReads,inFlight);
              try{return await context.readRouteAsset(descriptor,options);}finally{inFlight--;}
            }});
          const result=await current.preview.preview({...request,signal:computeAbort.signal});
          if(session!==current||current.abort.signal.aborted)return null;
          last=result;state.analyses++;view.render(result);return result;
        }catch(error){if(session===current&&!current.abort.signal.aborted){state.error=message(error);view.error?.(state.error);}return null;}
        finally{current.abort.signal.removeEventListener('abort',abort);current.computeAbort=null;
          if(session===current&&!current.abort.signal.aborted){state.phase=state.error?'error':'ready';notify();}}
      })();
      try{return await operation;}finally{operation=null;}
    }
    function cancel(){session?.computeAbort?.abort();session?.preview?.cancel();}
    function close(){
      if(closing)return closing;if(!session)return Promise.resolve();
      const current=session;state.phase='closing';notify();current.abort.abort();current.computeAbort?.abort();current.preview?.cancel();
      closing=(async()=>{
        try{await opening;await operation;await current.lease?.release();}
        finally{current.preview=null;current.lease=null;if(session===current){session=null;state.open=false;state.phase='closed';last=null;view.hide?.();notify();}closing=null;}
      })();return closing;
    }
    const unsubscribe=context.onWorldChange?.(()=>{void close();});
    return Object.freeze({open,close,compute,cancel,invalidate(){if(!operation){last=null;state.error='';view.clear?.();}},result:()=>last?copy(last):null,
      snapshot:()=>({version:'0.70.0',...state,busy:!!operation,reads,inFlight,maximumConcurrentReads,last:summary(last),
        lease:context.snapshot?.()||null,physicalAccessibilityVerified:false,physicalMovementReady:false,campaignRoutingActivated:false}),
      async dispose(){unsubscribe?.();await close();}});
  }
  function plot(canvas,result){
    const ctx=canvas.getContext('2d');if(!ctx)return;
    const width=canvas.width,height=canvas.height;ctx.clearRect(0,0,width,height);ctx.fillStyle='#061119';ctx.fillRect(0,0,width,height);
    const points=result?.route?.points;if(!points?.length){ctx.fillStyle='#8aaba7';ctx.font='14px system-ui';ctx.fillText('Les axes apparaîtront après une analyse réussie.',20,35);return;}
    let w=Infinity,s=Infinity,e=-Infinity,n=-Infinity;for(const p of points){w=Math.min(w,p.e);s=Math.min(s,p.n);e=Math.max(e,p.e);n=Math.max(n,p.n);}
    const scale=Math.min((width-60)/Math.max(1,e-w),(height-60)/Math.max(1,n-s)),offsetX=(width-(e-w)*scale)/2,offsetY=(height-(n-s)*scale)/2;
    const xy=p=>[offsetX+(p.e-w)*scale,height-offsetY-(p.n-s)*scale];
    ctx.strokeStyle='#18363e';ctx.lineWidth=1;for(let x=20;x<width;x+=40){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,height);ctx.stroke();}
    ctx.strokeStyle='#69d9ce';ctx.lineWidth=3;ctx.beginPath();points.forEach((p,i)=>{const [x,y]=xy(p);i?ctx.lineTo(x,y):ctx.moveTo(x,y);});ctx.stroke();
    for(const [p,colour]of [[points[0],'#85e8a3'],[points.at(-1),'#ffd18a']]){const [x,y]=xy(p);ctx.beginPath();ctx.arc(x,y,5,0,2*Math.PI);ctx.fillStyle=colour;ctx.fill();}
    ctx.fillStyle='#bad8d2';ctx.font='12px system-ui';ctx.fillText('Nord ↑ · axes OSM · '+Math.round(result.route.lengthMeters)+' m',14,height-12);
  }
  const REASONS={axis_unavailable:'Aucun axe compatible à moins de 10 m. Rapprocher le point d’un axe cartographié.',
    axis_ambiguous:'Plusieurs axes sont proches. Choisir explicitement les axes ci-dessous puis relancer.',
    no_route_in_loaded_network:'Aucun itinéraire relié dans le secteur chargé. Le réseau extérieur ou les ouvrages exclus peuvent interrompre ce trajet.',
    source_endpoint_conflict:'Ces points correspondent à des axes sans jonction native commune. Aucun raccord n’a été ajouté.',
    time_budget:'Analyse interrompue : délai maximal atteint.',search_budget:'Analyse interrompue : budget de recherche atteint.',
    asset_budget:'Analyse interrompue : budget de fichiers atteint.',decoded_budget:'Analyse interrompue : budget de décompression atteint.',
    graph_budget:'Analyse interrompue : budget de graphe atteint.',resident_budget:'Analyse interrompue : budget mémoire atteint.',
    cancelled:'Calcul annulé.',no_navigation_sector:'Aucun secteur NAV préparé ici.',no_loaded_navigation:'Aucun secteur NAV n’a pu être chargé.'};
  function mount(context,document=root.document){
    const $=id=>document.getElementById(id),dialog=$('route70-dialog'),canvas=$('route70-map');if(!dialog||!canvas)throw new Error('Interface d’itinéraire absente.');
    let choices=null,markedStart=null,markedWorld=null,arrivalKind='camera';
    function readPoint(which){const p={};for(const axis of ['e','n']){const raw=$('route70-'+which+'-'+axis).value.trim();p[axis]=raw===''?NaN:Number(raw);}return p;}
    const validPoint=p=>Number.isFinite(p.e)&&Number.isFinite(p.n);
    function setPoint(which,p){for(const axis of ['e','n'])$('route70-'+which+'-'+axis).value=p?String(p[axis]):'';}
    const validPoints=()=>validPoint(readPoint('start'))&&validPoint(readPoint('end'));
    function place(p){return validPoint(p)?context.index?.()?.communeAt(p.e,p.n)?.name||null:null;}
    function updateSummary(){
      const start=readPoint('start'),end=readPoint('end'),a=place(start),b=place(end);
      $('route70-summary').textContent=(validPoint(start)?'Départ marqué'+(a?' · '+a:''):'Départ à marquer')+
        ' → '+(arrivalKind==='camera'?'arrivée ici':'arrivée définie')+(b?' · '+b:'');
      const s=controller.snapshot();$('route70-compute').disabled=s.busy||s.phase==='waiting-scene'||s.phase==='closing'||!validPoints();
    }
    function resetChoices(){choices=null;$('route70-choices').hidden=true;for(const id of ['route70-start-axis','route70-end-axis'])$(id).replaceChildren();
      controller.invalidate();$('route70-status').textContent='Points ou options modifiés. Relancer l’analyse des axes.';}
    function fill(request){
      for(const which of ['start','end'])setPoint(which,request[which]);
      markedStart={e:request.start.e,n:request.start.n};markedWorld=context.world();arrivalKind='coordinates';
      $('route70-mode').value=request.mode||'foot';$('route70-avoid-steps').checked=false;resetChoices();updateSummary();
    }
    const view={
      show(){if(!dialog.open)dialog.showModal();},hide(){if(dialog.open)dialog.close();},
      clear(){plot(canvas,null);$('route70-projections').textContent='';},
      error(text){$('route70-status').textContent='Analyse indisponible : '+text;},
      state(s){
        const busy=s.busy||s.phase==='closing';$('route70-compute').disabled=busy||!validPoints();$('route70-cancel').disabled=s.phase!=='computing';
        for(const id of ['route70-mark-start','route70-example','route70-camera-start','route70-camera-end'])$(id).disabled=busy;
        for(const id of ['route70-start-e','route70-start-n','route70-end-e','route70-end-n','route70-mode','route70-avoid-steps','route70-start-axis','route70-end-axis'])$(id).disabled=busy;
        if(s.phase==='waiting-scene')$('route70-status').textContent='Attente de la fin des chargements du survol…';
        if(s.phase==='ready'&&$('route70-status').textContent.startsWith('Attente'))$('route70-status').textContent=validPoints()?'Arrivée prête. Analyser le trajet vers ici.':'Marquer le départ ici, puis voler jusqu’à l’arrivée.';
        if(s.phase==='computing')$('route70-status').textContent='Lecture et vérification des axes du secteur…';
        if(s.phase==='closing')$('route70-status').textContent='Annulation des lectures avant la reprise du survol…';
      },
      render(result){
        choices=result.axisChoices||null;$('route70-choices').hidden=!choices;
        if(choices)for(const which of ['start','end']){
          const select=$('route70-'+which+'-axis');select.replaceChildren();const empty=document.createElement('option');empty.value='';empty.textContent='Choisir un axe';select.append(empty);
          for(const q of choices[which]){const option=document.createElement('option');option.value=q.key;option.textContent='Voie OSM '+q.wayId+' · '+q.distanceMeters.toFixed(2)+' m du point';select.append(option);}
        }
        const count=result.coverage?.loadedCells.length||0,omitted=result.coverage?.omittedCells.length||0,missing=result.coverage?.missingCells.length||0;
        $('route70-status').textContent=result.status==='route'?Math.round(result.route.lengthMeters)+' m sur les axes OSM · '+(result.route.mode==='car'?'voiture':'marche')+' · '+count+' secteurs analysés. Couverture locale partielle.':REASONS[result.code]||('Analyse interrompue : '+(result.reason||result.code));
        if(omitted||missing)$('route70-status').textContent+=' '+omitted+' secteurs hors limite, '+missing+' indisponibles. Rapprocher les points.';
        if(result.anchors)$('route70-projections').textContent='Projection du départ : '+result.anchors.start.distanceMeters.toFixed(2)+' m · arrivée : '+result.anchors.end.distanceMeters.toFixed(2)+' m. Ces écarts ne sont pas des accès vérifiés.';
        plot(canvas,result);
      }
    };
    const controller=createController({context,view});
    async function open(){
      if(!controller.snapshot().open){
        if(markedWorld!==context.world()){markedStart=null;markedWorld=null;}
        setPoint('start',markedStart);setPoint('end',context.camera());arrivalKind='camera';resetChoices();updateSummary();
        $('route70-precise').open=false;
      }
      return controller.open();
    }
    async function markStart(){
      const p=context.camera();if(!validPoint(p))return false;
      markedStart={e:p.e,n:p.n};markedWorld=context.world();setPoint('start',markedStart);resetChoices();updateSummary();
      await controller.close();return true;
    }
    function request(){
      const q={mode:$('route70-mode').value,avoidSteps:$('route70-avoid-steps').checked};
      for(const which of ['start','end']){q[which]={};for(const axis of ['e','n']){const raw=$('route70-'+which+'-'+axis).value.trim();q[which][axis]=raw===''?NaN:Number(raw);}
        const selected=$('route70-'+which+'-axis').value;if(choices&&selected)q[which+'AxisKey']=selected;}
      return q;
    }
    $('route70-open').onclick=()=>{void open();};$('route70-close').onclick=()=>{void controller.close();};$('route70-mark-start').onclick=()=>{void markStart();};
    dialog.addEventListener('cancel',event=>{event.preventDefault();void controller.close();});
    $('route70-form').onsubmit=event=>{event.preventDefault();void controller.compute(request());};$('route70-cancel').onclick=()=>controller.cancel();
    $('route70-example').onclick=()=>{fill(EXAMPLE);$('route70-status').textContent='Exemple prêt : Belsunce → République, environ 599 m d’axes sur l’édition AMP du 24 octobre 2026. Cliquer sur Analyser le trajet vers ici.';};
    for(const which of ['start','end']){
      function changed(){const p=readPoint(which);if(which==='start'){markedStart=validPoint(p)?p:null;markedWorld=context.world();}else arrivalKind='coordinates';resetChoices();updateSummary();}
      $('route70-camera-'+which).onclick=()=>{setPoint(which,context.camera());changed();if(which==='end'){arrivalKind='camera';updateSummary();}};
      for(const axis of ['e','n'])$('route70-'+which+'-'+axis).oninput=changed;
    }
    $('route70-mode').onchange=resetChoices;$('route70-avoid-steps').onchange=resetChoices;plot(canvas,null);
    return Object.freeze({...controller,open,markStart,example(){fill(EXAMPLE);},compute:q=>controller.compute(q||request()),
      snapshot:()=>({...controller.snapshot(),markers:{start:markedStart?{...markedStart}:null,arrival:validPoint(readPoint('end'))?readPoint('end'):null,arrivalKind}})});
  }
  const API=Object.freeze({VERSION:'0.70.0',EXAMPLE,createController,mount,plot});root.__SOMA_ROUTE70_UI_CORE__=API;
  if(typeof module!=='undefined'&&module.exports)module.exports=API;
  if(root.document){
    const viewer=root.__SOMA_METROPOLE_VIEWER__||root.__SOMA_METRO_VIEWER__;
    if(typeof viewer?.narrowContext==='function')root.__SOMA_ROUTE70_VIEWER__=mount(viewer.narrowContext());
    else{const button=root.document.getElementById('route70-open');if(button){button.disabled=true;button.title='Le survol doit être disponible avant son analyse locale.';}}
  }
})(typeof globalThis!=='undefined'?globalThis:this);
