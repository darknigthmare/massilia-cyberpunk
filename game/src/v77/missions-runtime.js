/* Explicit authored43 guidance uses the existing city45 route owner. */
function v77Target43(kind,id){
  if(kind==='story'){
    const m=V43_STORY_BY_ID[id],r=m&&v43StoryState(id);
    if(!m||!r||!['active','return'].includes(r.status))return null;
    const step=m.steps[r.step];
    return r.status==='return'?{zone:'station-interiorA',label:`Table de campagne · ${m.title}`}:
      step&&WORLD.zones[step.zone]?{zone:step.zone,label:step.label}:null;
  }
  if(kind==='gig'){
    const g=V43_GIG_BY_ID[id],r=g&&v43GigState(id);
    if(!g||!r||!['active','return'].includes(r.status))return null;
    if(r.status==='active')return WORLD.zones[g.zone]?{zone:g.zone,label:g.title}:null;
    // These are exactly the authored social zones in which ensureZone43
    // installs the district board. Ambiguous/missing content is not guessed.
    const boards=Object.values(WORLD.zones).filter(z=>z.type==='social'&&z.district===g.district);
    return boards.length===1?{zone:boards[0].id,label:`Borne de mandats · ${g.title}`}:null;
  }
  return null;
}
function v77Trace43(kind,id){
  const target=v77Target43(kind,id),city=window.__SOMA_V45__;
  if(!target||typeof city?.setDestination!=='function')return false;
  // This explicit click may replace the current GPS destination. Merely
  // following, accepting, completing or restoring43 does not change it.
  if(!city.setDestination(target.zone,target.label,false)){
    announce('Aucune liaison piétonne connue depuis ce secteur.',3.5);return false;
  }
  V43.tracked={kind,id};v43Save(true);v43RefreshHUD();closeModals();
  announce(`Itinéraire piéton chargé · ${WORLD.zones[target.zone]?.title||target.zone}`,3);
  return true;
}
window.__SOMA_GUIDANCE77__=Object.freeze({target:v77Target43,trace:v77Trace43,
  snapshot:()=>({owner:'soma-massilia.production.v43',routeOwner:'soma-massilia.city.v45',newPersistenceDomain:false})});
