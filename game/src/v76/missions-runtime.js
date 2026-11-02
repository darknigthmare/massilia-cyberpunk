/* Native production43 definitions, combat32 records and physical progression. */
const v76Encounters=Object.freeze([
  ...V43_STORY.flatMap(m=>m.steps.flatMap((s,index)=>['fight','boss'].includes(s.kind)?[{kind:'story',id:m.id,owner:`story-${m.id}-${index}`,step:index,zone:s.zone,count:s.kind==='boss'?1:s.count||3,boss:s.kind==='boss'}]:[])),
  ...V43_GIGS.filter(g=>['combat','infiltration'].includes(g.type)).map(g=>({kind:'gig',id:g.id,owner:`gig-${g.id}`,zone:g.zone,count:g.type==='combat'?g.count:2,boss:false})),
].map(Object.freeze));
const v76Enemies=new Map(v76Encounters.flatMap(e=>Array.from({length:e.count},(_,index)=>[`v43-${e.owner}-${index}`,Object.freeze({encounter:e,index,role:e.boss?'heavy':['rifle','blade','sniper','netrunner'][index%4]})])));
function v76SourceEnemy(id,zoneId){const s=v76Enemies.get(id);return typeof zoneId==='string'&&s?.encounter.zone===zoneId?s:null;}
function v76RestoreRecovery(q,r){window.__SOMA_COMBAT75__?.restoreRecovery(q,r);window.__SOMA_COMBAT76__?.restoreRecovery(q,r);}
function v76RestoreEnemy(q,z){
  const source=v76SourceEnemy(q?.id,z?.id);if(!source)return q;
  q.v32Role=source.role;
  const r=window.__SOMA_V32__?.zoneCombatState?.(z.id)?.enemies?.[q.id];
  if(!r||!Number.isFinite(r.health))return q;v76RestoreRecovery(q,r);
  if(Number.isFinite(r.maxHealth)&&r.maxHealth>0)q.maxHealth=Math.max(q.maxHealth,Math.min(100000,r.maxHealth));
  q.health=Math.max(0,Math.min(q.maxHealth,r.health));q.v32DownHandled=!!r.downHandled;
  if(Number.isFinite(r.armor))q.armor=Math.max(0,Math.min(.85,r.armor));
  if(['patrol','search','combat','suspicious','suspicion','return','dead','disabled','idle'].includes(r.state))q.state=r.state;
  q.detect=Math.max(0,Math.min(1,Number(r.detect)||0));return q;
}
// The first setup43 can precede the appended combat adapters. Their scripts
// have all evaluated at DOMContentLoaded; reconcile only their paid scalar.
function v76ReconcileRecovery(){
  for(const z of Object.values(WORLD.zones))for(const q of z.robots||[]){
    if(!v76SourceEnemy(q.id,z.id))continue;
    const r=window.__SOMA_V32__?.zoneCombatState?.(z.id)?.enemies?.[q.id];
    if(r&&Number.isFinite(r.health))v76RestoreRecovery(q,r);
  }
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',v76ReconcileRecovery,{once:true});else setTimeout(v76ReconcileRecovery,0);
// Only this native gig marker was proved inside an original parked vehicle.
function v76GigMarkerClear(z,p){
  if(!p||![p.x,p.z].every(Number.isFinite)||blocked(z,p.x,p.z,.55))return false;
  const geometry=window.__SOMA_V57_CORE__,rect=window.__SOMA_V42__?.segmentRect;
  if(!geometry&&!rect)return false;
  for(const v of z.vehicles||[]){
    if(v.hidden)continue;const spec=vehicleSpec(v),width=spec.width||1.8,length=spec.length||4;
    if(geometry?geometry.circleFootprint([p.x,p.z],.55,geometry.obb(v.x,v.z,width,length,v.heading||0,.05)):
      rect(p.x,p.z,p.x,p.z,{x:v.x,z:v.z,width,length,heading:v.heading||0},.55))return false;
  }
  return z!==zone||!lineBlocked(p.x,p.z,p.x,p.z);
}
function v76GigPoint(z,g){
  const original=v43OpenPoint(z,`v43-gig-${g.id}`,.5);
  if(g.id!=='port-quai-muet'||z.id!=='port-exterior')return original;
  if(v76GigMarkerClear(z,original))return original;
  if(typeof v20FindFreeInteractionPoint!=='function')return null;
  for(let i=0;i<32;i++){
    const p=v20FindFreeInteractionPoint(z,`v76-gig-port-quai-muet-${i}`);
    if(v76GigMarkerClear(z,p))return p;
  }
  return null;
}
function v76Ready(){return Number(state.health)>0&&!state.recovery?.pending&&!state.driving;}
function v76Point(o,type){return v76Ready()&&zone?.interactables?.includes(o)&&o.type===type&&v43Dist(camera,o)<=3.2&&v43Visible(camera,o);}
function v76Proof(o,type){return v76Point(o,type)?{core:state,root:V43,stories:V43.story,gigs:V43.gigs,zone,object:o}:null;}
function v76ValidPoint(p,type){return !!p&&p.core===state&&p.root===V43&&p.stories===V43.story&&p.gigs===V43.gigs&&p.zone===zone&&v76Point(p.object,type);}
function v76StoryProof(o){
  const m=V43_STORY_BY_ID[o?.storyId],r=m&&v43StoryState(m.id),s=m?.steps[r?.step],p=v76Proof(o,'v43StoryNode');
  return p&&r.status==='active'&&s?.zone===zone.id&&o.step===r.step?{...p,record:r,index:r.step,channelReady:false}:null;
}
function v76Defeated(owner){
  const e=v76Encounters.find(e=>e.owner===owner&&e.zone===zone.id);if(!e)return false;
  return Array.from({length:e.count},(_,i)=>zone.robots.find(q=>q.id===`v43-${owner}-${i}`&&q.v43Owner===owner)).every(q=>q&&q.health<=0&&q.v32DownHandled===true);
}
function v76AuthorizeStory(m,r,s,choice,p){
  if(!v76ValidPoint(p,'v43StoryNode')||p.record!==r||p.index!==r.step||p.object.storyId!==m.id||p.object.step!==r.step||s.zone!==zone.id)return false;
  if(s.kind==='channel')return p.channelReady===true;
  if(['fight','boss'].includes(s.kind))return v76Defeated(`story-${m.id}-${r.step}`);
  return s.kind==='choice'&&(s.choices||[]).some(([id])=>id===choice);
}
function v76GigProof(o){const g=V43_GIG_BY_ID[o?.gigId],r=g&&v43GigState(g.id),p=v76Proof(o,'v43GigNode');return p&&r.status==='active'&&g.zone===zone.id?{...p,record:r,channelReady:false}:null;}
function v76AuthorizeGig(g,r,p){return v76ValidPoint(p,'v43GigNode')&&p.record===r&&p.object.gigId===g.id&&g.zone===zone.id&&(g.type==='combat'?v76Defeated(`gig-${g.id}`):p.channelReady===true);}
function v76CommandProof(){const o=zone?.id==='station-interiorA'&&zone.interactables.find(o=>o.id==='v43-command-console');return v76Proof(o,'v43CampaignConsole');}
function v76ValidCommand(p){return zone?.id==='station-interiorA'&&v76ValidPoint(p,'v43CampaignConsole')&&p.object.id==='v43-command-console';}
function v76BoardProof(district){const o=zone?.interactables?.find(o=>o.id===`v43-board-${district}`&&o.district===district);return v76Proof(o,'v43FixerBoard');}
function v76ValidBoard(p,district){return v76ValidPoint(p,'v43FixerBoard')&&zone.type==='social'&&zone.district===district&&p.object.district===district;}
function v76Checkpoint(){window.__SOMA_V37_SAVE__?.schedule?.();}
window.__SOMA_MISSIONS76__=Object.freeze({
  knownEnemy:(id,zoneId)=>!!v76SourceEnemy(id,zoneId),
  legacyLootRole:(id,zoneId,role)=>typeof id==='string'&&id.startsWith('loot-')&&role==='melee'&&v76SourceEnemy(id.slice(5),zoneId)?.role==='blade'?'blade':null,
  snapshot:()=>({owner:'soma-massilia.production.v43',combatOwner:'layer32.zoneCombat',newPersistenceDomain:false,locationRepairs:v76LocationRepairs,channelActive:!!v43Channel,
    encounters:v76Encounters.map(e=>({...e,enemies:Array.from({length:e.count},(_,index)=>({id:`v43-${e.owner}-${index}`,role:v76Enemies.get(`v43-${e.owner}-${index}`).role}))})),
    stories:V43_STORY.map(m=>({id:m.id,...v43StoryState(m.id),stages:m.steps.map((s,index)=>({index,zone:s.zone,kind:s.kind,knownZone:!!WORLD.zones[s.zone]}))})),
    gigs:V43_GIGS.map(g=>({id:g.id,type:g.type,zone:g.zone,knownZone:!!WORLD.zones[g.zone],...v43GigState(g.id)}))}),
});
