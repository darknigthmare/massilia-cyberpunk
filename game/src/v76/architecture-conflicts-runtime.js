/* Native Atlas audit: the existing v52 cell button owns selection and saving.
 * Queries, pages and displayed references are ephemeral. No world data moves. */
(function(root){
  'use strict';
  let model=null,ready=false,problem='',query='',scope='all',over3cm=false,page=0,selected=null,message='';
  const atlas=()=>root.__SOMA_V52__,pilot=()=>root.__SOMA_TERRAIN75__?.snapshot?.();
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  // Some acquired WFS labels contain a literal Unicode escape. Keep the
  // stored source value intact and only decode its human-readable label.
  const label=value=>esc(String(value??'inconnue').replace(/\\u([a-f0-9]{4})/gi,(_,hex)=>String.fromCharCode(parseInt(hex,16))));
  const meters=value=>Number(value).toFixed(3)+' m';
  const sourceBound=id=>model?.bound(id,atlas()?.records?.(),root.__SOMA_HEIGHTS69__)||false;
  function selectCell(id){
    const row=model?.get(id);if(!row||!sourceBound(id))return false;
    atlas().open('terrain');
    const button=document.querySelector('[data-v52-cell="'+row.cellId+'"]');
    if(!button){message='Cellule source indisponible dans cet Atlas.';refresh();return false;}
    button.click();
    const success=atlas().state().selected===row.cellId;
    message=success?'Cellule '+row.cellId+' sélectionnée dans l’Atlas. Son bouton « Entrer dans la cellule » conserve les contrôles d’accès habituels.':'La sélection native a refusé cette cellule.';
    refresh();return success;
  }
  function inspect(id){if(!model?.get(id))return false;selected=id;message='';refresh();return true;}
  function refresh(){
    const section=document.getElementById('architecture76');if(!section||!model)return;
    const current=atlas()?.state?.().selected,pack=pilot(),filtered=model.list({query,cellId:scope==='selected'?current:null,over3cm,page});page=filtered.page;
    section.querySelector('[data-architecture76-status]').textContent=problem||'77 objets source · '+model.data.cells+' cellules · 76 écarts > 0,030 m. '+
      (pack?.active?'Pilote IGN 5 m actif.':pack?.selected==='legacy25m'?'Relief historique 25 m actif : ces écarts décrivent le pilote 5 m.':'Ces écarts décrivent la grille du pilote 5 m, pas le relief importé.')+
      ' Cellule Atlas : '+(current||'aucune')+'.';
    section.querySelector('[data-architecture76-results]').textContent=filtered.total+' référence(s) · page '+(page+1)+'/'+filtered.pages;
    section.querySelector('[data-architecture76-rows]').innerHTML=filtered.rows.map(r=>'<tr><td><button type="button" data-architecture76-inspect="'+r.id+'">'+esc(r.id)+'</button><br><small>'+esc(r.ignId)+'</small></td><td>'+esc(r.cellId)+'</td><td>'+meters(r.absoluteEaveNGF)+'</td><td>'+meters(r.nativeFootprintMax)+'</td><td>+'+meters(r.terrainAboveEave)+'</td></tr>').join('')||'<tr><td colspan="5">Aucune référence pour ce filtre.</td></tr>';
    for(const button of section.querySelectorAll('[data-architecture76-inspect]'))button.onclick=()=>inspect(button.dataset.architecture76Inspect);
    section.querySelector('[data-architecture76-prev]').disabled=page===0;section.querySelector('[data-architecture76-next]').disabled=page+1>=filtered.pages;
    section.querySelector('[data-architecture76-message]').textContent=message;
    const details=section.querySelector('[data-architecture76-details]'),row=model.get(selected);
    if(!row){details.textContent='Choisissez une référence pour consulter ses cotes, sa provenance et sélectionner sa cellule.';return;}
    const bound=sourceBound(row.id),p=model.data.provenance;
    details.innerHTML='<h4>'+esc(row.id)+' · '+esc(row.ignId)+'</h4><p>'+esc(row.cellId)+' · '+(bound?'Liaison avec les sources actuellement installées vérifiée.':'Liaison avec les sources installées indisponible ; sélection de cellule désactivée.')+'</p>'+
      '<p>Sol minimal IGN : '+meters(row.groundAltitude)+' NGF · hauteur à l’égout : '+meters(row.eaveHeight)+' · égout de référence : '+meters(row.absoluteEaveNGF)+' NGF.<br>MNT sous l’emprise : '+meters(row.nativeFootprintMin)+' à '+meters(row.nativeFootprintMax)+' NGF · dépassement maximal : +'+meters(row.terrainAboveEave)+'.</p>'+
      '<p>Point du maximum MNT (Lambert-93) : E '+row.witnessL93[0].toFixed(3)+' · N '+row.witnessL93[1].toFixed(3)+' m. Ce point localise le calcul sous l’emprise, sans certifier un accès.</p>'+
      '<p>BD TOPO : '+esc(p.ignDate)+' · champs '+esc(p.ignFields.groundAltitude)+' / '+esc(p.ignFields.height)+'. Méthode altimétrique déclarée : '+label(row.sourceAltitudeMethod||'inconnue')+' · précision source déclarée : '+(Number.isFinite(row.sourceAltitudePrecisionM)?meters(row.sourceAltitudePrecisionM):'inconnue')+'.<br>RGE ALTI : archives décembre 2022, pas natif 5 m ; échantillonnage bilinéaire strict, puis nœuds float32 et masques conservés. OSM : instantané déclaré septembre 2026. Ces millésimes et précisions ne déterminent pas la cause du conflit.</p>'+
      '<p>Appariement conservateur d’emprises : IoU '+row.iou.toFixed(4)+' · marges '+row.margin.toFixed(4)+' / '+row.reciprocalMargin.toFixed(4)+'. Façades et faîtage restent inconnus ; l’égout ne mesure pas la toiture.</p>'+
      '<button type="button" data-architecture76-cell'+(bound?'':' disabled')+'>Sélectionner cette cellule dans l’Atlas</button>'+
      '<details><summary>Empreintes des sources et du contrôle</summary><p style="overflow-wrap:anywhere">Géométrie OSM : '+esc(row.geometrySHA256)+'<br>Cellule : '+esc(row.cells[row.cellId])+'<br>PBF OSM : '+esc(row.sourceSHA256)+'<br>IGN BD TOPO : '+esc(p.ignSourceSHA256)+'<br>Preuve d’appariement : '+esc(p.heightProofSHA256)+'<br>Grille pilote 5 m : '+esc(p.gridSHA256)+'<br>Audit parent 77 : '+esc(p.parentAuditSHA256)+'</p><p>Contrôle indépendant par intersection des triangles source et MNT, hors cours. Les champs sol/hauteur correspondent exactement au fichier IGN conservé. Aucun défaut de contrat source établi. Intégrité des fichiers contrôlée ; aucun nouveau relevé de terrain.</p></details>';
    details.querySelector('[data-architecture76-cell]').onclick=()=>selectCell(row.id);
  }
  function ui(){
    const panel=document.querySelector('#v52Atlas .v52-panel');if(!panel||!model)return;
    if(!document.getElementById('architecture76')){
      const section=document.createElement('section');section.id='architecture76';section.className='v52-card';
      section.innerHTML='<details data-architecture76-audit><summary><strong>Conflits bâti / relief IGN 5 m · 77 références</strong></summary><h3>Égouts IGN et relief sous les emprises</h3><p data-architecture76-status role="status"></p><p>Le maximum du MNT dépasse l’égout de référence de ces objets. Les cotes IGN et la géométrie source sont conservées. Les écarts ne mesurent ni une façade réelle ni la part du bâtiment engloutie. Aucun accès ou raccord n’est créé.</p><div class="v52-actions"><label>Rechercher OSM, IGN ou cellule <input data-architecture76-query type="search" maxlength="80" placeholder="osm/way/69129984"></label><label>Périmètre <select data-architecture76-scope><option value="all">Toutes les références</option><option value="selected">Cellule Atlas sélectionnée</option></select></label><label><input data-architecture76-threshold type="checkbox"> Écarts > 0,030 m seulement</label></div><p data-architecture76-results aria-live="polite"></p><div style="overflow-x:auto"><table><caption>Cotes de référence NGF-IGN69, en mètres</caption><thead><tr><th scope="col">Objet source</th><th scope="col">Cellule</th><th scope="col">Égout NGF</th><th scope="col">MNT maximum NGF</th><th scope="col">Dépassement</th></tr></thead><tbody data-architecture76-rows></tbody></table></div><div class="v52-actions"><button type="button" data-architecture76-prev>Précédent</button><button type="button" data-architecture76-next>Suivant</button></div><p data-architecture76-message role="status"></p><article data-architecture76-details></article></details>';
      panel.insertBefore(section,panel.querySelector('#terrain75')||panel.querySelector('#v52-body'));
      section.querySelector('[data-architecture76-query]').oninput=e=>{query=e.target.value.slice(0,80);page=0;refresh();};
      section.querySelector('[data-architecture76-scope]').onchange=e=>{scope=e.target.value==='selected'?'selected':'all';page=0;refresh();};
      section.querySelector('[data-architecture76-threshold]').onchange=e=>{over3cm=e.target.checked;page=0;refresh();};
      section.querySelector('[data-architecture76-prev]').onclick=()=>{page--;refresh();};section.querySelector('[data-architecture76-next]').onclick=()=>{page++;refresh();};
    }
    refresh();
  }
  function snapshot(){const filtered=model?.list({query,cellId:scope==='selected'?atlas()?.state?.().selected:null,over3cm,page});return {version:'0.76.0',ready,ephemeral:true,geometryChanged:false,sourceDatumChanged:false,
    total:model?.data.fragments||0,uniqueObjects:model?.data.uniqueObjects||0,over3cm:model?.data.over3cm||0,cells:model?.data.cells||0,
    query,scope,page:filtered?.page||0,filtered:filtered?.total||0,selected,selectedSourceBound:selected?sourceBound(selected):null,
    atlasCell:atlas()?.state?.().selected||null,pilotActive:pilot()?.active||false,thresholdM:0,gridSHA256:model?.data.provenance.gridSHA256||null,problem};}
  function setup(){
    if(!atlas()?.open||!root.__SOMA_HEIGHTS69__||!root.__SOMA_TERRAIN75__?.ready){setTimeout(setup,100);return;}
    if(ready)return;
    try{
      model=root.__SOMA_ARCHITECTURE76_CORE__.create(root.__SOMA_ARCHITECTURE76_DATA__);delete root.__SOMA_ARCHITECTURE76_DATA__;
      const open=atlas().open;atlas().open=function(...args){const result=open.apply(this,args);ui();return result;};
      const body=document.getElementById('v52-body');if(body&&typeof MutationObserver!=='undefined')new MutationObserver(refresh).observe(body,{childList:true});
      ready=true;API.ready=true;ui();
    }catch(e){problem='Audit bâti indisponible : '+String(e.message||e);}
  }
  const API={ready:false,snapshot,inspect,selectCell,refresh};root.__SOMA_ARCHITECTURE76__=API;setup();
})(window);
