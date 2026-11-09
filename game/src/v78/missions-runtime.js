/* Reuse the existing45 GPS and authored road graph; no pickup ledger is added. */
function v78CallRouteFailure45(vehicleOnly){
  return !V45.settings.routePlanner?'Planificateur GPS désactivé. Destination GPS conservée.':
    vehicleOnly?'Aucune liaison routière connue depuis ce secteur. Destination GPS conservée.':
      'Aucune liaison piétonne connue depuis ce secteur. Destination GPS conservée.';
}
function v78TraceCall45(id){
  const call=V45_CALL_BY_ID[id],record=call&&V45.calls[id];
  if(!call||record?.status!=='active')return false;
  const escort=call.type==='escort',target=escort?record.targetZone:record.zone;
  const label=escort?`${call.title} · acheminement`:call.title;
  if(!v45SetDestination(target,label,escort)){
    announce(v78CallRouteFailure45(escort),4);return false;
  }
  announce(`Itinéraire ${escort?'véhicule':'piéton'} chargé · ${WORLD.zones[target]?.title||target}`,3);
  return true;
}
function v78EscortDialogue45(call,record){
  const owned=v77CallRoute45(call,record),manual=!!V45.route?.targetZone&&!owned;
  const guided=v77AutoDestination45(record.targetZone,`${call.title} · acheminement`,true,owned);
  const destination=WORLD.zones[record.targetZone]?.title||record.targetZone;
  const message=guided?`Le trajet véhicule est chargé dans le GPS. Rejoignez ${destination} en véhicule.`:
    manual?`Destination GPS conservée. Rejoignez ${destination} en véhicule ; le bouton Tracer de l’appel permet de charger son trajet.`:
      v78CallRouteFailure45(true);
  showDialogue(call.title,[message],[{label:'Fermer'}],D[call.district]?.name||call.district,'ESCORTE');
  return true;
}
window.__SOMA_MISSIONS78__=Object.freeze({traceCall:v78TraceCall45,
  snapshot:()=>({owner:'soma-massilia.city.v45',newPersistenceDomain:false,
    portRunTarget:V45_RACE_TARGETS.port,escortVehicleRoutes:true,
    scope:'Authored conceptual world; route graph is not proof of geographic physical access.'})});
