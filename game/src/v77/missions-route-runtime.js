/* Automatic mission transitions may change only their own authored route.
 * No second GPS ledger or persistent ownership field is introduced. A route
 * is recognized conservatively from the exact source target/label/mode tuple.
 */
function v77RouteMatches45(target,label,vehicleOnly=false){
  const r=V45.route;
  return !!r?.targetZone&&r.targetZone===target&&r.label===label&&r.vehicleOnly===!!vehicleOnly;
}
function v77OperationStepRoute45(op,step){
  return !!step&&v77RouteMatches45(step.zone,step.label,step.kind==='drive');
}
function v77OperationReturnRoute45(op){
  return v77RouteMatches45('station-exterior',`Remettre le dossier · ${op.title}`)||
    v77RouteMatches45('station-exterior',`Remettre au centre des opérations · ${op.title}`);
}
function v77AutoDestination45(target,label,vehicleOnly=false,owned=false){
  if(V45.route?.targetZone&&!owned)return false;
  return v45SetDestination(target,label,vehicleOnly);
}
function v77ClearOperationRoute45(op){
  if(!v77OperationReturnRoute45(op))return false;
  v45ClearDestination();return true;
}
function v77CallRoute45(call,s){
  return v77RouteMatches45(s.zone,call.title,call.type==='escort')||
    call.type==='escort'&&v77RouteMatches45(s.zone,call.title,false)||
    call.type==='escort'&&v77RouteMatches45(s.targetZone,`${call.title} · acheminement`,false);
}
function v77ClearCallRoute45(call,s){
  if(!v77CallRoute45(call,s))return false;
  v45ClearDestination();return true;
}
function v77RaceRoute45(active,index=active?.index+1){
  const run=active&&V45_RACES.find(x=>x.id===active.id);
  return !!run&&v77RouteMatches45(active.path[index],`${run.title} · point ${index}/${active.path.length-1}`,true);
}
function v77ClearRaceRoute45(active,index){
  if(!v77RaceRoute45(active,index))return false;
  v45ClearDestination();return true;
}
window.__SOMA_ROUTE77__=Object.freeze({snapshot:()=>({owner:'soma-massilia.city.v45',newPersistenceDomain:false,
  operationReturnZone:'station-exterior',storyReturnZone:'station-interiorA'})});
