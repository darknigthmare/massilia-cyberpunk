/* Metropolitan preparation and diagnostics, separate from the active campaign. */
(function(){
  'use strict';
  const VERSION='0.69.0';
  let manifest=null,store=null,pending=null,lastError='';
  const read=id=>JSON.parse(document.getElementById(id)?.textContent||'{}');
  const target=read('soma-v69-territory'),audit=read('soma-v69-fidelity-audit');
  const roads=read('soma-v69-road-report');
  const V=()=>window.__SOMA_V52__,T=()=>window.__SOMA_TERRAIN56__;
  const terrainGrids=new WeakMap();

  async function readManifest(response){
    // Four asset descriptors for ~50k metropolitan cells exceed a 16 MiB
    // index. Bound both the advertised size and the actual streamed bytes.
    const maximum=128*1024*1024,length=Number(response.headers.get('content-length'));
    if(Number.isFinite(length)&&length>maximum)throw Error('Index métropolitain supérieur au budget de 128 Mio.');
    if(!response.body)throw Error('Flux du manifeste indisponible.');
    const reader=response.body.getReader(),decoder=new TextDecoder('utf-8',{fatal:true}),parts=[];
    let bytes=0;
    try{
      while(true){const {value,done}=await reader.read();if(done)break;
        bytes+=value.byteLength;if(bytes>maximum)throw Error('Index métropolitain supérieur au budget de 128 Mio.');
        parts.push(decoder.decode(value,{stream:true}));
      }
      parts.push(decoder.decode());
    }catch(error){try{await reader.cancel(error);}catch{}throw error;}
    finally{reader.releaseLock();}
    return JSON.parse(parts.join(''),(key,value)=>{if(['__proto__','prototype','constructor'].includes(key))throw Error('Clé de manifeste interdite.');return value;});
  }

  function validators(){return {
    vector(value,tile){
      const metric=window.__SOMA_V53_CORE__.metricCell({id:tile.cellId,gridX:tile.gridX,gridY:tile.gridY},V().district);
      return window.__SOMA_V53_CORE__.normalizeRecord(value,tile.cellId,{cells:[metric]});
    },
    terrain(value,tile){
      if(value.testOnly||!value.source||/fixture|synthetic/i.test(value.source.truth||''))throw Error('Une fixture ne constitue pas un relief réel.');
      const grid=T().core.load(value,tile.boundsL93);
      if(grid.stats.noData)throw Error('Relief incomplet : aucune activation 3D.');
      const bounds=tile.boundsL93;
      if(![1,5,25].includes(grid.step)||grid.haloNodes!==1||grid.cols!==250/grid.step+3||grid.rows!==grid.cols||
        Math.abs(grid.x0-(bounds[0]-grid.step))>1e-6||Math.abs(grid.n0-(bounds[3]+grid.step))>1e-6)throw Error('Carroyage du relief téléchargé incompatible.');
      terrainGrids.set(value,grid);
      return value;
    },
    surfaces(value,tile,world){
      if(value.schema!=='soma-metropole/surface-cell/1'||value.cellId!==tile.cellId||
        value.sourcePbfSHA256!==world.source.sha256||value.contentSHA256!==tile.contentSHA256||
        value.cell?.contentSHA256!==value.contentSHA256||value.cell?.sourceSHA256!==world.source.sha256)throw Error('Surfaces liées à une autre cellule ou source.');
      for(const layer of ['road','unsealed','paved','foot','walk','mark']){
        const triangles=value.cell.surfaces?.[layer]||[];
        if(!Array.isArray(triangles)||triangles.length>400000||triangles.some(t=>!Array.isArray(t)||t.length!==3||t.some(p=>!Array.isArray(p)||p.length!==2||!p.every(Number.isFinite)||Math.abs(p[0])>126||Math.abs(p[1])>126)))throw Error('Maillage routier hors cellule ou hors budget.');
      }
      return value;
    },
    navigation(value,tile,world){
      if(value.sourcePbfSHA256!==world.source.sha256||value.sourcePackSHA256!==world.sourcePackSHA256||value.cellHashes?.[tile.cellId]!==tile.contentSHA256)throw Error('Navigation liée à une autre édition.');
      window.__SOMA_NAV63_CORE__.validate(value);return value;
    }
  };}

  function activeTerrainMatches(entry,zone){
    const terrain=T(),downloaded=terrainGrids.get(entry.layers.terrain),active=terrain.v69?.gridFor(zone);
    if(!downloaded||!active||active.stats?.noData!==0)return false;
    const pack=downloaded.pack,activePack=active.pack;
    if(!/^[a-f0-9]{64}$/i.test(activePack?.sha256||'')||
      !(pack.sha256===activePack.sha256||active===terrain.grid&&pack.source?.sourceGridSHA256===activePack.sha256))return false;
    for(const key of ['step','crs','units','verticalDatum'])if(downloaded[key]!==active[key])return false;
    if(downloaded.crs!=='EPSG:2154'||downloaded.units!=='m'||downloaded.verticalDatum!=='NGF-IGN69')return false;
    // Grid arrays are exposed and mutable. Recheck the measured values rather
    // than treating a retained source hash or revision as a content guarantee.
    // The largest admitted tile compares 251 x 251 nodes, including its edges.
    for(let row=1;row<downloaded.rows-1;row++)for(let col=1;col<downloaded.cols-1;col++){
      const expected=downloaded.node(col,row),actual=active.sample(downloaded.x0+col*downloaded.step,downloaded.n0-row*downloaded.step);
      if(!Number.isFinite(expected)||!Number.isFinite(actual)||Math.abs(expected-actual)>1e-6)return false;
    }
    return true;
  }

  function canActivate(entry){
    // New editions require an explicit migration of the complete routing and
    // exploration catalogues. Merely having four files does not perform it.
    const record=V().records().get(entry.cellId),catalog=window.__SOMA_EXPLORE64__.catalog();
    return !!record&&record.contentSHA256===entry.layers.vector?.contentSHA256&&
      manifest.source.sha256===catalog.sourcePbfSHA256&&manifest.sourcePackSHA256===catalog.sourcePackSHA256&&
      activeTerrainMatches(entry,V().zones().get(entry.cellId));
  }

  async function prepare(){
    if(store)return store;if(pending)return pending;
    pending=(async()=>{
      const url=new URL('data/v69/world/manifest.json',location.href);
      const response=await fetch(url,{credentials:'same-origin'});
      if(!response.ok)throw Error('Manifeste territorial indisponible : HTTP '+response.status);
      manifest=window.__SOMA_STREAM69_CORE__.validateManifest(await readManifest(response));
      store=window.__SOMA_STREAM69_CORE__.createTileStore({manifest,baseURL:url.href,
        maxResidentBytes:128*1024*1024,maxInFlight:2,maxPending:32,validators:validators(),canActivate,
        onAttach(id,entry){
          if(entry.readyFor3D)entry.layers.vector=V().records().get(id);
        }});
      lastError='';return store;
    })().catch(error=>{lastError=String(error.message||error);throw error;}).finally(()=>pending=null);
    return pending;
  }

  function protect(){
    if(!store)return;
    const current=typeof zone!=='undefined'?zone.v52CellId:null;
    const active=manifest.tiles.find(tile=>tile.cellId===current);
    store.protect(active?manifest.tiles.filter(tile=>Math.abs(tile.gridX-active.gridX)<=1&&Math.abs(tile.gridY-active.gridY)<=1).map(tile=>tile.cellId):[]);
  }

  async function load(id,{require3D=false}={}){
    try{const cache=await prepare();protect();const entry=await cache.load(id,{require3D});lastError='';return entry;}
    catch(error){lastError=String(error.message||error);throw error;}
  }
  async function enter(id){
    const entry=await load(id,{require3D:true});
    if(!entry.readyFor3D)throw Error('Cette édition ne possède pas encore toutes les liaisons de jeu validées pour cette cellule.');
    return window.__SOMA_V54__.enter(id);
  }

  function snapshot(){return {version:VERSION,target:{id:target.id,name:target.name,communes:target.communes?.length||0,
      boundaryAvailable:!!target.boundary},prepared:manifest?.coverage||null,cache:store?.snapshot()||null,
    terrainMosaic:T()?.v69?.snapshot()||null,buildingParts:window.__SOMA_PARTS69__?.summary()||null,
    heightReferences:window.__SOMA_HEIGHTS69__?.summary()||null,
    completeMetropole:false,certifiedOneToOne:false,lastError,
    note:'Les paramètres OSM, les mesures IGN et les interprétations architecturales restent distincts.'};}

  function open(){
    let modal=document.getElementById('v69Metropole');
    if(!modal){
      modal=document.createElement('section');modal.id='v69Metropole';modal.className='modal';
      modal.setAttribute('role','dialog');modal.setAttribute('aria-label','Production géographique métropolitaine');
      modal.innerHTML='<div class="panel"><header class="v66-dev-head"><div><small>ESPACE DÉVELOPPEMENT</small><h2>Fidélité métropolitaine</h2></div><button data-v69-close>Fermer</button></header><p data-v69-target></p><p data-v69-facts></p><p data-v69-limit></p><details><summary>Communes du périmètre officiel</summary><p data-v69-communes></p></details><div class="actions"><button data-v69-load>Vérifier les couches de la cellule actuelle</button></div><pre data-v69-report style="white-space:pre-wrap"></pre></div>';
      document.body.append(modal);modal.querySelector('[data-v69-close]').onclick=closeModals;
      modal.querySelector('[data-v69-load]').onclick=async()=>{
        const output=modal.querySelector('[data-v69-report]');output.textContent='Vérification des fichiers, empreintes et couches…';
        try{const id=zone?.v52CellId||'V52-MC-33';await load(id,{require3D:true});output.textContent=JSON.stringify(snapshot(),null,2);}
        catch(error){output.textContent=String(error.message||error);}
      };
    }
    modal.querySelector('[data-v69-target]').textContent=`${target.name||'Aix-Marseille-Provence'} · ${target.communes?.length||0} communes · référence administrative 2026`;
    modal.querySelector('[data-v69-facts]').textContent='Socle actuel : 168 cellules, 10,5 km², relief IGN échantillonné à 25 m. Le lot de 14 279 références IGN décrit la hauteur à l’égout et le pied du bâtiment ; les toitures non relevées restent approximatives. Les voies couvertes incohérentes ont été retirées des surfaces de sol. Les parties documentées restent visibles ; les emprises résiduelles inconnues restent sans volume, collision ou occlusion inventés.';
    modal.querySelector('[data-v69-limit]').textContent='Métropole complète et fidélité architecturale 1:1 non validées. Les contours administratifs détaillés, les données géographiques extérieures et les relevés de hauteur manquants restent à acquérir. Les dômes et pyramides utilisent des profils paramétriques explicitement inférés.';
    modal.querySelector('[data-v69-communes]').textContent=(target.communes||[]).map(c=>c.nom).sort((a,b)=>a.localeCompare(b,'fr')).join(' · ');
    modal.querySelector('[data-v69-report]').textContent=JSON.stringify({status:snapshot(),baseAudit:audit.auditScope||{},roads:roads},null,2);
    openModal('v69Metropole');
  }

  function mountFlyoverEntry(){
    if(document.getElementById('v69-metropole-entry'))return;
    const entry=document.getElementById('v54-explore')||document.getElementById('v54-real-entry');
    if(!entry){setTimeout(mountFlyoverEntry,120);return;}
    const button=document.createElement('button');button.id='v69-metropole-entry';button.type='button';
    button.textContent='Survoler la métropole';button.title='Survol libre de la carte disponible';
    button.onclick=()=>location.assign('metropole-viewer.html');entry.insertAdjacentElement('afterend',button);
  }

  function setup(){
    if(!window.__SOMA_V68__||!window.__SOMA_STREAM69_CORE__||!T()?.ready){setTimeout(setup,120);return;}
    window.__SOMA_V69__={version:VERSION,target,audit,prepare,load,enter,snapshot,open};
    window.__SOMA__.version=VERSION;document.title='SOMA//MASSILIA 0.69 — Marseille augmentée';
    for(const selector of ['.v34-edition span','.topbar .brand small']){const node=document.querySelector(selector);if(node)node.textContent='0.69';}
    mountFlyoverEntry();
    const grid=document.querySelector('#v66Dev .v66-dev-grid');
    if(grid&&!document.getElementById('v69-production-button')){
      const button=document.createElement('button');button.id='v69-production-button';button.textContent='Fidélité & périmètre métropolitain';button.onclick=open;grid.append(button);
    }
  }
  setup();
})();
