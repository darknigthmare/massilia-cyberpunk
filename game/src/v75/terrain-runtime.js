/* Explicit physical terrain pilot. Existing terrain56/58 owns the persisted
 * grid, render triangles, contact, foundations, vehicle poses and LOS61. */
(function(root){
  'use strict';
  let native=null,legacy=null,ready=false,busy=false,message='',relocations=0,entryRefused=false;
  const terrain=()=>root.__SOMA_TERRAIN56__;
  function active(){return !!native&&terrain()?.pack?.sha256===native.sha256;}
  function entrySupported(z,x,zz){
    if(!active())return true;
    const T=terrain();
    for(const [dx,dz] of [[0,0],[.4,0],[-.4,0],[0,.4],[0,-.4]])if(!Number.isFinite(T.ground(z,x+dx,zz+dz)))return false;
    const slope=T.slope(z,x,zz);
    return !!slope&&Number.isFinite(slope.e)&&Number.isFinite(slope.south)&&Math.hypot(slope.e,slope.south)<=.95+1e-7;
  }
  function relocated(z){
    relocations++;message='Position restaurée incompatible avec le relief pilote : entrée replacée sur une voie source libre de la cellule.';
    if(typeof announce==='function')announce(message,6);
  }
  function refused(z){
    entryRefused=true;
    message='Entrée refusée : aucune position libre et soutenue dans '+String(z?.v52CellId||z?.id||'cette cellule')+' avec le relief pilote. La partie est suspendue à l’écran titre.';
    const suspend=()=>{if(!entryRefused)return;paused=true;document.getElementById('boot')?.classList.add('open');refresh();};
    suspend();
    // Continuity import/continue owners close their modal after enterZone.
    // Reassert the existing title once that synchronous transition has ended.
    setTimeout(suspend,0);
    if(typeof announce==='function')announce(message,8);
  }
  function changed(){
    if(!ready)return;
    root.__SOMA_SIGHT61__?.clearCache?.();
    if(!active()||typeof zone==='undefined'||!terrain().activeFor(zone))return;
    const pose={x:camera.x,z:camera.z,yaw:camera.yaw,pitch:camera.pitch};
    if(entrySupported(zone,pose.x,pose.z)&&!blocked(zone,pose.x,pose.z,.38)){
      terrain().poseCamera();return;
    }
    // Reuse the actual terrain entry owner, including its checked source-road
    // fallback. A failed entry pauses at the existing title, never invents land.
    if(!state.driving&&enterZone(zone.id,null,pose)){terrain().poseCamera();return;}
    refused(zone);
  }
  async function select(mode){
    if(!ready||busy||!['native5m','legacy25m'].includes(mode))return false;
    if(mode==='native5m'&&active()||mode==='legacy25m'&&terrain()?.pack?.sha256===legacy.sha256)return true;
    if(terrain()?.activeFor?.(typeof zone==='undefined'?null:zone)){
      message='Revenez dans la ville historique avant de changer de relief.';refresh();return false;
    }
    busy=true;message='Préparation du relief…';refresh();
    try{
      const pack=mode==='native5m'?native:legacy;
      terrain().v75Preflight(pack);
      await terrain().install(pack,{persist:true});
      root.__SOMA_SIGHT61__?.clearCache?.();entryRefused=false;
      message=mode==='native5m'?'Pilote IGN 5 m actif : sol, rendu, véhicules et lignes de vue utilisent la même grille. Le choix est conservé par le cache de relief existant.':'Relief historique 25 m rétabli et conservé par le cache de relief existant.';
      return true;
    }catch(e){message='Changement refusé : '+String(e.message||e);return false;}
    finally{busy=false;refresh();}
  }
  function snapshot(){return {version:'0.75.0',ready,busy,selected:active()?'native5m':terrain()?.pack?.sha256===legacy?.sha256?'legacy25m':'declared-import',
    active:active(),pilot:true,sessionOnly:false,preferenceOwner:'terrain56/58 existing active-pack IndexedDB',stepM:terrain()?.grid?.step??null,
    gridSHA256:terrain()?.pack?.sha256??null,nativeGridSHA256:native?.sha256??null,
    sourceSHA256:native?.source?.nativeManifestSHA256??null,campaignCells:168,newGeographicCells:0,
    certified:false,relocations,entryRefused,message,renderContactAndLOS:'shared terrain56 Grid',
    sourceAudit:{terrainAboveFixedEaveFragments:77,terrainAboveFixedEaveUniqueObjects:77,thresholdM:0,terrainAboveFixedEave3cmFragments:76},
    sourceSampling:'strict bilinear from native IGN 5 m pixels; exact prepared nodes copied',
    buildingFoundations:'source IGN ground references retained; other bases use measured extrema over the complete footprint, excluding courtyard interiors'};}
  function refresh(){
    const el=document.getElementById('terrain75');if(!el)return;
    const inTerrain=terrain()?.activeFor?.(typeof zone==='undefined'?null:zone);
    el.querySelector('[data-terrain75-status]').textContent=message||(active()?'Pilote 5 m actif.':terrain()?.pack?.sha256===legacy?.sha256?'Relief historique 25 m actif.':'Relief importé actif · grille '+(terrain()?.grid?.step??'?')+' m.');
    for(const b of el.querySelectorAll('button'))b.disabled=busy||!ready||inTerrain;
    el.querySelector('[data-terrain75-native]').setAttribute('aria-pressed',String(active()));
  }
  function ui(){
    const panel=document.querySelector('#v52Atlas .v52-panel');if(!panel)return;
    if(!document.getElementById('terrain75')){
      const el=document.createElement('section');el.id='terrain75';
      el.innerHTML='<h3>Relief IGN 5 m · pilote du centre</h3><p data-terrain75-status role="status"></p><p>168 cellules du centre, 10,5 km². Les pixels IGN natifs à 5 m sont échantillonnés strictement sur la grille de campagne. Les inconnues restent absentes. Les altitudes NGF de bâtiment documentées restent conservées ; les autres fondations sont interprétées.</p><p><strong>Limite mesurée : le MNT dépasse l’égout de 77 fragments bâtis, correspondant à 77 objets source distincts ; 76 dépassent 3 cm.</strong> Les cotes IGN fixes restent conservées : certains corps peuvent donc rester partiellement engloutis. Ce pilote ne certifie ni les marches ni tous les accès.</p><p>Activez-le depuis la ville historique avant d’entrer dans Marseille réelle. Le cache de relief existant conserve ce choix au rechargement. Les imports de continuité conservent le relief installé. Une ancienne position impraticable est replacée sur une voie source libre, ou l’entrée est refusée.</p><div class="terrain56-actions"><button type="button" data-terrain75-native aria-pressed="false">Activer le pilote IGN 5 m</button><button type="button" data-terrain75-legacy>Revenir au relief historique 25 m</button></div>';
      panel.insertBefore(el,panel.querySelector('#terrain56')||panel.firstChild);
      el.querySelector('[data-terrain75-native]').onclick=()=>select('native5m');
      el.querySelector('[data-terrain75-legacy]').onclick=()=>select('legacy25m');
    }
    refresh();
  }
  function setup(){
    if(!terrain()?.ready||!root.__SOMA_V52__?.open){setTimeout(setup,100);return;}
    if(ready)return;
    try{
      native=JSON.parse((root.__SOMA_TERRAIN75_PARTS__||[]).join(''));
      if(native.source?.truth!=='IGN RGE ALTI native 5m-derived centre grid'||JSON.parse(native.gridHeader).step!==5)throw Error('Source de pilote incompatible');
      terrain().validatePack(native);
      const bundled=document.getElementById('soma-v56-terrain');legacy=JSON.parse(bundled.textContent);
      terrain().validatePack(legacy);
      delete root.__SOMA_TERRAIN75_PARTS__;
      const open=root.__SOMA_V52__.open;
      root.__SOMA_V52__.open=function(...args){const result=open.apply(this,args);ui();return result;};
      ready=true;API.ready=true;changed();ui();
    }catch(e){message='Pilote 5 m indisponible : '+String(e.message||e);ui();}
  }
  const API={ready:false,active,select,entrySupported,relocated,refused,entered:()=>{entryRefused=false;},changed,snapshot};
  root.__SOMA_TERRAIN75__=API;setup();
})(window);
