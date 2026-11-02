/* Guidance uses content45, its route owner and the unchanged progression74 proofs. */
function v75TraceOperation(id){
  const op=V45_OPERATION_BY_ID[id],record=op&&v45OperationState(id),step=op?.steps[record?.step];
  if(!op||record.status!=='active'||!step)return false;
  const driving=step.kind==='drive',ok=v45SetDestination(step.zone,step.label,driving);
  if(!ok)announce(driving?'Aucune liaison routière depuis ce secteur. Rejoignez un accès routier existant.':'Aucune liaison connue depuis ce secteur.',3.5);
  else if(driving)announce(zone.id===step.zone?'Entrez dans ce secteur en véhicule par une couture routière pour valider le trajet.':'Trajet routier chargé · montez à bord et traversez les coutures indiquées.',3.5);
  return ok;
}
function v75HotspotEnemy(id,zoneId){
  if(typeof id!=='string'||typeof zoneId!=='string')return null;
  const hotspot=window.__SOMA_MISSIONS75_CONTENT__?.find(h=>h.zone===zoneId);
  if(!hotspot)return null;
  for(let index=0;index<hotspot.count;index++)if(id===`v43-hotspot-${hotspot.id}-${index}`)return{hotspot,index};
  return null;
}
function v75RestoreHotspotEnemy(q,z){
  const source=v75HotspotEnemy(q?.id,z?.id);if(!source)return q;
  if(source.index%4===1&&q.v32Role==='melee')q.v32Role='blade';
  return v74RestoreEnemy(q,z);
}
function v75ReconcileHotspotEnemies(z){for(const q of z?.robots||[])v75RestoreHotspotEnemy(q,z);}
window.__SOMA_MISSIONS75__=Object.freeze({
  knownHotspotEnemy:(id,zoneId)=>!!v75HotspotEnemy(id,zoneId),
  restoreHotspotEnemy:v75RestoreHotspotEnemy,
  legacyLootRole:(id,zoneId,role)=>{
    if(typeof id!=='string'||!id.startsWith('loot-')||role!=='melee')return null;
    const source=v75HotspotEnemy(id.slice(5),zoneId);return source&&source.index%4===1?'blade':null;
  },
  snapshot:()=>({owner:'soma-massilia.city.v45',newPersistenceDomain:false,
    hotspotEncounters:(window.__SOMA_MISSIONS75_CONTENT__||[]).map(h=>({id:h.id,zone:h.zone,count:h.count,owner:'soma-massilia.production.v43',combatOwner:'layer32.zoneCombat'})),
    operations:V45_OPERATIONS.map(op=>{const r=v45OperationState(op.id);return{id:op.id,status:r.status,step:r.step,paid:r.paid,choice:r.choice,
      stages:op.steps.map((s,index)=>({index,zone:s.zone,kind:s.kind,knownZone:!!WORLD.zones[s.zone],
        approach:index?v45FindRoute(op.steps[index-1].zone,s.zone,s.kind==='drive'):[],
        returnRoute:v45FindRoute(s.zone,'station-exterior'),count:s.kind==='combat'?s.count:undefined}))};})}),
});
