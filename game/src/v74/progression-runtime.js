/* Helpers live in the existing v45 owner. No additional persistent state. */
const v74CityEnemyZones=new Map([
  ...V45_OPERATIONS.flatMap(op=>op.steps.flatMap((step,index)=>step.kind==='combat'?
    Array.from({length:step.count||4},(_,i)=>[`v45-operation-${op.id}-${index}-${i}`,step.zone]):[])),
  ...V45_CALLS.filter(call=>call.type==='combat').flatMap(call=>
    Array.from({length:3},(_,i)=>[`v45-call-${call.id}-${i}`,v45PrimaryZone(call.district)])),
]);
function v74PlayerReady(){return Number(state.health)>0&&!state.recovery?.pending;}
function v74LegacyEnemy(id,zoneId){return zoneId==='corniche-route'&&/^v45-operation-asphalte-fantome-2-[0-3]$/.test(id);}
function v74Point(o,type){
  return v74PlayerReady()&&!state.driving&&zone?.interactables?.includes(o)&&o.type===type&&
    v45Dist(camera,o)<=3.2&&v45Visible(camera,o);
}
function v74StepProof(o){
  const op=V45_OPERATION_BY_ID[o?.operationId],record=op&&v45OperationState(op.id),step=op?.steps[record?.step];
  if(!op||record.status!=='active'||!step||step.zone!==zone?.id||o.step!==record.step||
    !v74Point(o,'v45OperationNode'))return null;
  return {core:state,owner:V45,record,zone,object:o,index:record.step,channelReady:false};
}
function v74AuthorizeStep(op,record,step,choice,proof){
  if(!proof||proof.core!==state||proof.owner!==V45||proof.record!==record||proof.zone!==zone||
    proof.index!==record.step||step.zone!==zone?.id||!v74PlayerReady())return false;
  if(step.kind==='drive')return proof.driven===true&&proof.from!==zone.id&&!!state.driving&&!!v45CurrentVehicle();
  if(!v74Point(proof.object,'v45OperationNode')||proof.object.operationId!==op.id||proof.object.step!==record.step)return false;
  if(step.kind==='channel')return proof.channelReady===true;
  if(step.kind==='combat')return v45OwnerEnemies(`operation-${op.id}-${record.step}`).length===0;
  if(step.kind==='choice')return (step.choices||[]).some(([id])=>id===choice);
  return false;
}
function v74DriveProof(id,from){
  const record=v45OperationState(id);
  return {core:state,owner:V45,record,zone,index:record?.step,driven:true,from};
}
function v74CommandProof(){
  const o=zone?.id==='station-exterior'&&zone.interactables?.find(o=>o.id==='v45-command-console'&&o.type==='v45CommandConsole');
  return o&&v74Point(o,'v45CommandConsole')?{core:state,owner:V45,zone,object:o,records:V45.operations}:null;
}
function v74ValidCommand(proof){
  return !!proof&&proof.core===state&&proof.owner===V45&&proof.zone===zone&&
    proof.records===V45.operations&&zone.id==='station-exterior'&&v74Point(proof.object,'v45CommandConsole');
}
function v74RestoreEnemy(q,z){
  const combat=window.__SOMA_V32__,current=combat?.zoneCombatState?.(z.id)?.enemies?.[q.id];
  const legacy=z.id==='corniche-exterior'&&v74LegacyEnemy(q.id,'corniche-route')?
    combat?.getState?.().zoneCombat?.['corniche-route']?.enemies?.[q.id]:null;
  // A terminal, already-rewarded legacy defeat cannot become a fresh body.
  const saved=legacy?.health===0&&legacy.downHandled===true?legacy:current||legacy;
  if(!saved||!Number.isFinite(saved.health))return q;
  if(Number.isFinite(saved.maxHealth)&&saved.maxHealth>0)q.maxHealth=Math.max(q.maxHealth,v45Clamp(saved.maxHealth,1,100000));
  q.health=v45Clamp(saved.health,0,q.maxHealth);q.v32DownHandled=!!saved.downHandled;
  if(Number.isFinite(saved.armor))q.armor=v45Clamp(saved.armor,0,.85);
  if(['patrol','search','combat','suspicious','suspicion','return','dead','disabled','idle'].includes(saved.state))q.state=saved.state;
  q.detect=v45Clamp(saved.detect,0,1);return q;
}
function v74Checkpoint(){window.__SOMA_V37_SAVE__?.schedule?.();}
function v74MigrateRoute(){
  const op=V45_OPERATION_BY_ID['asphalte-fantome'],record=v45OperationState(op.id),step=op.steps[record?.step],route=V45.route;
  if(V45.tracked?.kind!=='operation'||V45.tracked.id!==op.id||record.status!=='active'||
    ![1,2].includes(record.step)||route.targetZone!=='corniche-route'||route.label!==step.label)return false;
  const path=v45FindRoute(zone?.id||state.zone,step.zone,step.kind==='drive');
  // A player saved on the former upper road may first need its existing
  // pedestrian lift. Keep an empty vehicle path explicit; invent no crossing.
  V45.route={...route,targetZone:step.zone,path,vehicleOnly:step.kind==='drive',updatedAt:Date.now()};v45Save(true);return true;
}
function v74ReturnGuide(id){
  const op=V45_OPERATION_BY_ID[id],record=op&&v45OperationState(id);
  if(!op||record.status!=='return')return false;
  const ok=v45SetDestination('station-exterior',`Remettre au centre des opérations · ${op.title}`);
  closeModals();announce('Retournez à pied au centre des opérations de Station Zéro pour remettre les preuves.',4);return ok;
}
window.__SOMA_PROGRESSION74__=Object.freeze({
  knownEnemy:(id,zoneId)=>typeof zoneId==='string'&&(v74CityEnemyZones.get(id)===zoneId||v74LegacyEnemy(id,zoneId)),
  legacyLootRole:(id,zoneId,role)=>id==='loot-v45-operation-asphalte-fantome-2-1'&&zoneId==='corniche-route'&&role==='melee'?'blade':role,
  sync:v74MigrateRoute,
  snapshot:()=>({owner:'soma-massilia.city.v45',combatOwner:'layer32.zoneCombat',newPersistenceDomain:false,
    channelActive:!!v45Channel,returnConsoleAvailable:!!v74CommandProof(),
    operations:V45_OPERATIONS.map(op=>{const r=v45OperationState(op.id);return{id:op.id,status:r.status,step:r.step,paid:r.paid,choice:r.choice};}),
    tracked:V45.tracked?{...V45.tracked}:null}),
});
