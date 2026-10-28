/* Uses the existing scene lease; it never reads NAV or acquires geography. */
(function(root){
  'use strict';
  const number=n=>typeof n==='number'&&Number.isFinite(n)?new Intl.NumberFormat('fr-FR',{maximumFractionDigits:2}).format(n)+' m':'Indisponible';
  const WIDTH={'osm-width':'Largeur déclarée OSM','osm-est-width':'Estimation déclarée OSM','estimated-from-lanes':'Estimation selon les voies','estimated-from-class':'Estimation selon la classe'};
  const KIND={road:'Chaussée',unsealed:'Surface non revêtue',paved:'Surface pavée',foot:'Surface piétonne',walk:'Trottoir',mark:'Marquage'};
  function mount(context,document=root.document){
    const $=id=>document.getElementById(id),dialog=$('road72-dialog');if(!dialog)throw new Error('Road inspection panel absent.');
    const write=(id,value)=>{$(id).textContent=value;};
    function row(parent,label,value){const p=document.createElement('p'),b=document.createElement('b');b.textContent=label+' : ';p.append(b,document.createTextNode(value));parent.append(p);}
    function clear(){$('road72-candidates').replaceChildren();write('road72-surface','');write('road72-navigation','');}
    const view={show(){if(!dialog.open)dialog.showModal();},hide(){if(dialog.open)dialog.close();},
      waiting(){clear();write('road72-status','Stabilisation de la vue avant lecture de la surface visée…');},
      error(message){clear();write('road72-status','Inspection indisponible : '+message);},render(result){
        clear();const s=result.selection;
        if(!s){write('road72-status',result.status==='budget'?'Budget d’inspection atteint. Rapprochez-vous de la voie.':result.status==='occluded'?'Le réticule rencontre un bâtiment, le relief ou une autre surface. Visez une surface routière visible.':'Aucune surface routière visible à moins de 1 500 m.');return;}
        write('road72-status',(KIND[s.surfaceKind]||'Surface routière')+' à '+number(s.distanceMeters)+' · '+s.selectedCellId);
        write('road72-surface',s.rendering==='prepared-union'?'Surface préparée fusionnée : les objets ci-dessous sont compatibles avec le point visé. Leur contribution individuelle n’est pas conservée dans les triangles.':'Ruban rendu depuis l’axe source de la voie.');
        if(!s.candidates.length)write('road72-surface','Surface routière rendue ; aucun objet source local ne peut être attribué au point visé. Un axe voisin peut être hors de cette cellule.');
        if(s.candidateCount>1)write('road72-surface',$('road72-surface').textContent+' Plusieurs voies se recouvrent ici ; aucune n’est choisie automatiquement.');
        if(s.sourceEvidenceTruncated)write('road72-surface',$('road72-surface').textContent+' La liste des géométries source est partielle.');
        const nav=s.navigation;write('road72-navigation',nav.sectorPrepared?'NAV : un secteur source est préparé ici. Son graphe n’a pas été lu ; l’appartenance et les permissions de cette voie ne sont pas vérifiées.':'NAV : aucun secteur de navigation préparé n’est déclaré pour cette cellule.');
        for(const c of s.candidates){
          const card=document.createElement('article'),title=document.createElement('h3');title.textContent=c.name||c.id;card.append(title);
          row(card,'Largeur utilisée',number(c.widthMeters)+' · '+(WIDTH[c.widthSource]||c.widthSource));
          row(card,'Type / revêtement',(c.sourceTags.highway||'Inconnu')+' / '+c.surface);
          const access=Object.entries(c.sourceTags).filter(([k])=>/^(?:access|foot|bicycle|vehicle|motor_vehicle|motorcar|wheelchair)(?::|$)/.test(k));
          row(card,'Tags d’accès',access.length?access.map(([k,v])=>k+'='+v).join(' · '):'Non déclarés dans les tags disponibles');
          const structure=Object.entries(c.sourceTags).filter(([k])=>['bridge','tunnel','covered','indoor','layer','location'].includes(k));
          row(card,'Tags d’ouvrage',structure.length?structure.map(([k,v])=>k+'='+v).join(' · '):'Aucun tag d’ouvrage présent');
          if(c.correction)row(card,'Dimension corrigée',number(c.correction.previousWidthMeters)+' → '+number(c.correction.widthMeters)+' depuis width='+c.sourceTags.width+' ; relief natif conservé');
          const details=document.createElement('details'),summary=document.createElement('summary'),table=document.createElement('table');summary.textContent='Tags source disponibles';details.append(summary,table);
          for(const [key,value]of Object.entries(c.sourceTags)){const tr=document.createElement('tr'),a=document.createElement('th'),b=document.createElement('td');a.textContent=key;b.textContent=value;tr.append(a,b);table.append(tr);}card.append(details);
          if(c.osmURL){const a=document.createElement('a');a.href=c.osmURL;a.target='_blank';a.rel='noopener noreferrer';a.textContent='Voir '+c.id+' sur OpenStreetMap';card.append(a);}
          $('road72-candidates').append(card);
        }
        if(s.candidateCount>s.candidates.length){const p=document.createElement('p');p.textContent=(s.candidateCount-s.candidates.length)+' autres objets compatibles non affichés.';$('road72-candidates').append(p);}
      }};
    const controller=root.__SOMA_ARCHITECTURE71_UI_CORE__.createController(context,view);
    $('road72-open').onclick=()=>{void controller.open();};$('road72-close').onclick=()=>{void controller.close();};
    dialog.addEventListener('cancel',e=>{e.preventDefault();void controller.close();});
    document.addEventListener('keydown',e=>{
      if(e.code!=='KeyJ'||e.repeat||e.altKey||e.ctrlKey||e.metaKey||e.target?.closest?.('input,textarea,select,[contenteditable="true"]'))return;
      const open=document.querySelector('dialog[open]');if(open&&open!==dialog)return;
      e.preventDefault();e.stopImmediatePropagation();if(controller.snapshot().open)void controller.close();else void controller.open();
    },true);
    return controller;
  }
  const API=Object.freeze({VERSION:'0.72.0',mount});root.__SOMA_ROAD_INSPECTION72_UI_CORE__=API;
  if(typeof module!=='undefined'&&module.exports)module.exports=API;
  if(root.document){const viewer=root.__SOMA_METROPOLE_VIEWER__||root.__SOMA_METRO_VIEWER__;
    if(typeof viewer?.roadInspectionContext==='function')root.__SOMA_ROAD_INSPECTION72_VIEWER__=mount(viewer.roadInspectionContext());
    else{const button=root.document.getElementById('road72-open');if(button)button.disabled=true;}}
})(typeof window!=='undefined'?window:globalThis);
