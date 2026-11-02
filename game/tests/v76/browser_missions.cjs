#!/usr/bin/env node
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs/promises'),path=require('node:path');
const {chromium}=require('playwright'),{sourceEvidence,finishEvidence}=require('./browser_provenance.cjs');
const opts={url:'http://127.0.0.1:8787/SOMA_MASSILIA_URBAIN_v0_76.html',chromium:'/usr/bin/chromium',output:'/workspace/massilia-geodata-generated/validation-v76-2026-11-02/missions',timeout:90000,scope:'all'};
for(let i=2;i<process.argv.length;i++){const k=process.argv[i].replace(/^--/,'');assert(Object.hasOwn(opts,k)&&process.argv[i+1]);opts[k]=k==='timeout'?Number(process.argv[++i]):process.argv[++i];}
assert(['all','operations','production43'].includes(opts.scope));
const output=path.resolve(opts.output),report={schema:'soma/browser-missions/76/1',scope:opts.scope,passed:false,startedAt:new Date().toISOString(),steps:[],screenshots:[],pageErrors:[],consoleErrors:[],httpErrors:[],
 instrumentation:[
  'A fresh browser profile enters Marseille through the native start button. One initial enterZone(station-exterior) selects the original authored campaign; subsequent on-foot journeys use its existing portals through nearest/interact, and driving uses native vehicles and v44 road seams.',
  'Pause → Archives & continuité → Centre de commandement accepts, traces and hands in each operation. Native E holds complete timed channels and native choice buttons select doctrine. Camera poses and existing vehicles are positioned at original objects/portals; each foot portal selects a nearby collision-free pose where the real nearest()/visibility owners select that portal; this is bounded interaction QA, not continuous player traversal.',
  'For every authored encounter one unit is partially injured and another set to zero; updateAI(.1) invokes the real defeat/loot owner. Remaining units are neutralized the same way after export/import/reload checks. No actor, vehicle, route, collider, faction, damage handler or save API is invented or replaced.',
  'The real grouped exporter/importer64 and campaign validator37 exercise existing combat32, faction33, policy45 and campaign owners. Stale callbacks are held only to verify that grouped import invalidates them. Pauses bound comparison clocks.',
  'Native43 scenarios set the prerequisite finale42 to done, then use physical campaign/fixer consoles. Before the boss story only the four prior production43 story records are marked done/paid as an explicit prerequisite fixture, with no currency or XP grant. Existing authored portals, objectives and native E channels advance the selected stories and three gig types.',
  'Native43 combat uses declared health fixtures followed by updateAI(.1), preserving the real defeat/loot32 handler. One ordinary foe and the authored boss are saved both wounded and defeated; all progression, reward and persistence APIs remain native.',
 ],limits:['Controlled defeat fixtures do not establish a human combat playthrough or player GPU performance.','The five operations and production43 stories/gigs use the original conceptual authored world; they do not activate physical AMP geography or certify a Marseille route at 1:1.']};
let browser,context,page,currentStep='load';
async function step(name,run){currentStep=name;const row={name,startedAt:new Date().toISOString()};report.steps.push(row);process.stderr.write('[v76 missions] '+name+'\n');try{row.observation=await run();row.status='passed';return row.observation;}catch(e){row.status='failed';row.error=String(e.stack||e);throw e;}finally{row.finishedAt=new Date().toISOString();}}
async function shot(name){await page.screenshot({path:path.join(output,name+'.png')});report.screenshots.push(name+'.png');}
async function ready(){await page.waitForFunction(()=>window.__SOMA_V76__?.ready&&window.__SOMA_GROUP64__?.ready&&window.__SOMA_V37_SAVE__?.getStatus().ready&&window.__SOMA_MISSIONS75__&&window.__SOMA_MISSIONS76__);}
async function commandMenu(){
 await page.evaluate(()=>{closeModals();openModal('pause');});const command=page.locator('[data-v45-command]');
 if(!await command.isVisible()){const back=page.locator('#pause .v66-back:visible');if(await back.count())await back.click();await page.locator('#pause .v66-section-button').filter({hasText:'Archives & continuité'}).click();}
 await command.click();await page.locator('#v45Command.open').waitFor({state:'visible'});
}
async function footRoute(target){return page.evaluate(target=>{
 closeModals();paused=true;keys.clear();touches.clear();if(state.driving)throw Error('Foot journey started while driving.');
 const route=window.__SOMA_V45__.findRoute(zone.id,target),hops=[];if(!route.length)throw Error('No authored foot route '+zone.id+' -> '+target);
 for(const next of route.slice(1)){
  const from=zone.id,p=zone.portals.find(p=>p.target===next&&p.v53LegalTravel!==false);if(!p)throw Error('No existing portal '+from+' -> '+next);
  const candidates=[{x:p.approach?.x??p.x,z:p.approach?.z??p.z},{x:p.x,z:p.z}];
  for(const radius of [.25,.5,.75,1,1.5,2,2.5,3])for(let angle=0;angle<32;angle++)candidates.push({x:p.x+Math.cos(angle*Math.PI/16)*radius,z:p.z+Math.sin(angle*Math.PI/16)*radius});
  let pose=null,checks=0;const refusals=[];
  for(const candidate of candidates){
   checks++;if(Math.hypot(candidate.x-p.x,candidate.z-p.z)>=3.2||blocked(zone,candidate.x,candidate.z,.38))continue;
   Object.assign(camera,{...candidate,y:1.72});const n=nearest();if(interactionVisible(p)&&n?.kind==='portal'&&n.ref===p){pose={...candidate,y:1.72};break;}
   if(refusals.length<8)refusals.push({pose:candidate,visible:interactionVisible(p),nearest:n&&{kind:n.kind,id:n.ref.id}});
  }
  if(!pose)throw Error('Native nearest refused all legal portal poses '+p.code+' '+JSON.stringify({portal:p,checks,refusals}));
  paused=false;interact();paused=true;if(zone.id!==next)throw Error('Native portal refused '+p.code);hops.push({from,to:zone.id,code:p.code,kind:p.kind,interactionPose:pose,poseCandidatesChecked:checks});
 }
 return{route,hops};
},target);}
async function atObject(type,operationId,index){return page.evaluate(({type,operationId,index})=>{
 closeModals();paused=true;const o=zone.interactables.find(o=>o.type===type&&(!operationId||o.operationId===operationId&&o.step===index));if(!o)throw Error('Authored objective absent.');
 Object.assign(camera,{x:o.x,z:o.z,y:1.72});const n=nearest();if(n?.ref!==o)throw Error('Native nearest refused objective '+o.id+' '+JSON.stringify(n&&{kind:n.kind,id:n.ref.id}));
 if(blocked(zone,camera.x,camera.z,.38)||lineBlocked(camera.x,camera.z,o.x,o.z))throw Error('Original objective is not physically accessible '+o.id);
 paused=false;return{id:o.id,x:o.x,z:o.z,zone:zone.id};
},{type,operationId,index});}
async function snapshot(id){return page.evaluate(id=>{
 paused=true;const P=window.__SOMA_V37_SAVE__,saved=P.snapshot();try{P.validate(saved);}catch(error){window.__qaInvalidCampaign=saved;throw Error(error.message+' '+JSON.stringify(Object.entries(saved.payload.layers[32].zoneCombat).flatMap(([zone,record])=>Object.keys(record.enemies||{}).map(id=>({zone,id})))));}
 const A=window.__SOMA_V45__,op=A.operations.find(op=>op.id===id),r=A.state().operations[id],owner=`operation-${id}-${op.steps.findIndex(s=>s.kind==='combat')}`;
 return{zone:zone.id,credits:state.credits,reputation:state.reputation[op.district]||0,operation:JSON.parse(JSON.stringify(r)),policy:A.state().policy,stats:JSON.parse(JSON.stringify(A.state().stats)),
  enemies:zone.robots.filter(q=>q.v45Owner===owner).map(q=>({id:q.id,health:q.health,maxHealth:q.maxHealth,downHandled:!!q.v32DownHandled,role:q.v32Role,faction:q.v33Faction??null})),
  hotspotEnemies:zone.robots.filter(q=>window.__SOMA_MISSIONS75__.knownHotspotEnemy(q.id,zone.id)).map(q=>({id:q.id,health:q.health,maxHealth:q.maxHealth,downHandled:!!q.v32DownHandled,role:q.v32Role,faction:q.v33Faction??null})),
  combat:JSON.parse(JSON.stringify(saved.payload.layers[32].zoneCombat[zone.id]||null)),loot:JSON.parse(JSON.stringify(saved.payload.layers[32].loot)),xp:JSON.parse(JSON.stringify(state.player27)),
  factions:JSON.parse(JSON.stringify(saved.payload.layers[33])),saveStatus:P.getStatus(),newDomains:Object.keys(saved.payload.core).filter(k=>/^v7[1-9]$/.test(k)),channel:window.__SOMA_PROGRESSION74__.snapshot().channelActive};
},id);}
async function grouped(filename){
 await page.evaluate(()=>{window.__SOMA_V37_SAVE__.schedule();if(!window.__SOMA_V37_SAVE__.flush())throw Error('Checkpoint refused.');window.__SOMA_V45__.save();window.__SOMA_GROUP64__.open();});
 const event=page.waitForEvent('download');await page.locator('#v64-group-export').click();const download=await event;await download.saveAs(path.join(output,filename));return fs.readFile(path.join(output,filename),'utf8');
}
async function driveRoute(target){return page.evaluate(target=>{
 closeModals();paused=true;keys.clear();touches.clear();const A=window.__SOMA_V45__,route=A.findRoute(zone.id,target,true);if(route.length<2)throw Error('No existing road approach '+zone.id+' -> '+target);
 const v=zone.vehicles.find(v=>v.pilotable&&!v.hidden&&!v.ai&&!v.disabled&&!isFlyingVehicleKind(v.kind)&&!isWaterVehicleKind(v.kind));if(!v)throw Error('No native parked road vehicle in '+zone.id);
 v.speed=0;Object.assign(camera,{x:v.x,z:v.z});if(!enterVehicle(v))throw Error('Native vehicle entry refused.');const hops=[];paused=false;
 for(const next of route.slice(1)){
  const from=zone.id,p=zone.portals.find(p=>p.target===next&&p.v44VehiclePassable&&p.v53LegalTravel!==false),car=zone.vehicles.find(q=>q.id===state.driving);if(!p||!car)throw Error('Missing authored road seam '+from+' -> '+next);
  for(let i=0;i<12;i++)move(.1);car.x=p.x;car.z=p.z;car.heading=p.side==='N'?Math.PI:p.side==='S'?0:p.side==='W'?-Math.PI/2:Math.PI/2;car.speed=.5;
  if(!window.__SOMA_V44__.tryVehicleSeam())throw Error('Native road seam refused '+p.code);const arrived=zone.vehicles.find(q=>q.id===state.driving),condition=arrived.condition;update(.1);const retained=zone.vehicles.find(q=>q.id===state.driving);if(retained!==arrived||retained.condition!==condition)throw Error('Objective rebuild changed the native driven vehicle.');hops.push({from,to:zone.id,code:p.code,kind:p.kind,vehicle:state.driving,sameObjectAfterOwnerUpdate:retained===arrived,conditionBefore:condition,conditionAfter:retained.condition});
 }
 const car=zone.vehicles.find(q=>q.id===state.driving);car.speed=0;if(!exitVehicle())throw Error('Native dismount refused.');paused=true;return{route,hops};
},target);}
async function operation(op){
 await step(op.id+'/native-acceptance',async()=>{await commandMenu();await page.locator(`[data-v45-accept-op="${op.id}"]`).click();const s=await snapshot(op.id);assert.equal(s.operation.status,'active');assert.equal(s.operation.step,0);return s;});
 for(const [index,s]of op.steps.entries()){
  if(s.kind==='channel')await step(op.id+'/timed-channel-and-interruption',async()=>{
   const journey=await footRoute(s.zone),point=await atObject('v45OperationNode',op.id,index);
   await page.keyboard.down('e');await page.waitForFunction(()=>window.__SOMA_PROGRESSION74__.snapshot().channelActive);await page.keyboard.up('e');
   let state=await snapshot(op.id);assert.equal(state.operation.step,index);assert.equal(state.channel,false);
   const pendingText=await page.evaluate(()=>window.__SOMA_GROUP64__.exportText());await atObject('v45OperationNode',op.id,index);await page.keyboard.down('e');await page.waitForFunction(()=>window.__SOMA_PROGRESSION74__.snapshot().channelActive);
   let interruptedImport;try{interruptedImport=await page.evaluate(text=>window.__SOMA_GROUP64__.importText(text,true),pendingText);}finally{await page.keyboard.up('e');}
   assert.equal(interruptedImport.ok,true);state=await snapshot(op.id);assert.equal(state.operation.step,index);assert.equal(state.channel,false);
   await atObject('v45OperationNode',op.id,index);await page.keyboard.down('e');try{await page.waitForFunction(({id,index})=>window.__SOMA_V45__.state().operations[id].step===index+1,{id:op.id,index},{timeout:30000});}finally{await page.keyboard.up('e');}
   state=await snapshot(op.id);assert.equal(state.operation.step,index+1);assert.equal(state.channel,false);return{journey,point,interruptedImport,state};
  });
  else if(s.kind==='drive')await step(op.id+'/native-trace-and-road-transfer',async()=>{
   await commandMenu();await page.locator(`[data-v45-track-op="${op.id}"]`).click();const gps=await page.evaluate(()=>JSON.parse(JSON.stringify(window.__SOMA_V45__.state().route)));assert.equal(gps.vehicleOnly,true);assert.equal(gps.targetZone,s.zone);
   const journey=await driveRoute(s.zone),state=await snapshot(op.id);assert.equal(state.operation.step,index+1);return{gps,journey,state};
  });
  else if(s.kind==='combat')await step(op.id+'/authored-encounter-export-import-and-reload',async()=>{
   const journey=await footRoute(s.zone);const owner=`operation-${op.id}-${index}`;
   const roster=await page.evaluate(owner=>{paused=true;const qs=zone.robots.filter(q=>q.v45Owner===owner),hotspots=zone.robots.filter(q=>window.__SOMA_MISSIONS75__.knownHotspotEnemy(q.id,zone.id));if(qs.length<2)throw Error('Authored encounter missing.');qs[0].health=27;qs[1].health=0;if(hotspots.length>1){hotspots[0].health=39;hotspots[1].health=0;}updateAI(.1);return qs.map(q=>({id:q.id,health:q.health,role:q.v32Role}));},owner);assert.equal(roster.length,s.count);
   const before=await snapshot(op.id);assert.equal(before.enemies[1].downHandled,true);assert(Object.keys(before.loot).includes('loot-'+before.enemies[1].id));assert.deepEqual(before.newDomains,[]);
   const text=await grouped(op.id+'-partial-grouped.json');const imported=await page.evaluate(text=>window.__SOMA_GROUP64__.importText(text,true),text);assert.equal(imported.ok,true);
   const restored=await snapshot(op.id);assert.deepEqual(restored.enemies,before.enemies);assert.deepEqual(restored.hotspotEnemies,before.hotspotEnemies);assert.deepEqual(restored.loot,before.loot);assert.deepEqual(restored.xp,before.xp);assert.deepEqual(restored.factions,before.factions);
   await page.reload({waitUntil:'domcontentloaded'});await ready();const reloaded=await snapshot(op.id);assert.deepEqual(reloaded.enemies,before.enemies);assert.deepEqual(reloaded.hotspotEnemies,before.hotspotEnemies);assert.deepEqual(reloaded.loot,before.loot);assert.deepEqual(reloaded.xp,before.xp);assert.equal(reloaded.credits,before.credits);assert.equal(reloaded.saveStatus.blocked,false);assert.equal(reloaded.saveStatus.loadSource,'current');
   await page.evaluate(owner=>{for(const q of zone.robots)if(q.v45Owner===owner||window.__SOMA_MISSIONS75__.knownHotspotEnemy(q.id,zone.id))q.health=0;updateAI(.1);},owner);
   const point=await atObject('v45OperationNode',op.id,index);await page.keyboard.press('e');const complete=await snapshot(op.id);assert.equal(complete.operation.step,index+1);await shot(op.id+'-encounter-secured');return{journey,point,before,imported,restored,reloaded,complete};
  });
  else if(s.kind==='choice')await step(op.id+'/native-choice-and-expired-import-callback',async()=>{
   const journey=await footRoute(s.zone),point=await atObject('v45OperationNode',op.id,index);await page.keyboard.press('e');await page.locator('#dialogueChoices button').first().waitFor({state:'visible'});
   await page.evaluate(()=>{window.__qaStaleChoice=document.querySelector('#dialogueChoices button').onclick;});const text=await page.evaluate(()=>window.__SOMA_GROUP64__.exportText());
   const imported=await page.evaluate(text=>window.__SOMA_GROUP64__.importText(text,true),text);assert.equal(imported.ok,true);await page.evaluate(()=>window.__qaStaleChoice());const stale=await snapshot(op.id);assert.equal(stale.operation.step,index);
   await atObject('v45OperationNode',op.id,index);await page.keyboard.press('e');await page.locator('#dialogueChoices button').filter({hasText:s.choices[0][1]}).click();const state=await snapshot(op.id);assert.equal(state.operation.choice,s.choices[0][0]);assert.equal(state.operation.status,'return');return{journey,point,imported,stale,state};
  });
 }
 await step(op.id+'/physical-return-and-reward-once',async()=>{
  await footRoute('port-exterior');await commandMenu();assert.equal(await page.locator(`[data-v45-close-op="${op.id}"]`).count(),0);await page.locator(`[data-v45-return-op="${op.id}"]`).click();
  const gps=await page.evaluate(()=>JSON.parse(JSON.stringify(window.__SOMA_V45__.state().route)));assert.equal(gps.targetZone,'station-exterior');
  const journey=await footRoute('station-exterior');await atObject('v45CommandConsole');await commandMenu();const before=await snapshot(op.id);
  await page.evaluate(id=>{window.__qaStaleHandIn=document.querySelector(`[data-v45-close-op="${id}"]`).onclick;},op.id);const text=await page.evaluate(()=>window.__SOMA_GROUP64__.exportText());const imported=await page.evaluate(text=>window.__SOMA_GROUP64__.importText(text,true),text);assert.equal(imported.ok,true);
  await page.evaluate(()=>window.__qaStaleHandIn());let state=await snapshot(op.id);assert.equal(state.operation.paid,false);assert.equal(state.credits,before.credits);
  await atObject('v45CommandConsole');await commandMenu();await page.evaluate(id=>{window.__qaHandIn=document.querySelector(`[data-v45-close-op="${id}"]`).onclick;},op.id);await page.locator(`[data-v45-close-op="${op.id}"]`).click();await page.evaluate(()=>{window.__qaHandIn();window.__SOMA_V37_SAVE__.flush();});
  state=await snapshot(op.id);assert.equal(state.credits,before.credits+op.reward);assert.equal(state.reputation,before.reputation+3);assert.equal(state.operation.paid,true);assert.equal(state.operation.status,'done');assert.equal(state.policy,safeChoice(op));assert.equal(state.stats.operationsClosed,before.stats.operationsClosed+1);
  const completed=await grouped(op.id+'-completed-grouped.json');assert.equal((await page.evaluate(text=>window.__SOMA_GROUP64__.importText(text,true),completed)).ok,true);const final=await snapshot(op.id);assert.equal(final.credits,state.credits);assert.equal(final.operation.paid,true);assert.equal(await page.evaluate(id=>window.__SOMA_V45__.closeOperation(id),op.id),false);await shot(op.id+'-reward-once');return{gps,journey,before,imported,state,final};
 });
}
function safeChoice(op){return op.steps.at(-1).choices[0][0];}
async function at43(type,id,index){return page.evaluate(({type,id,index})=>{
 closeModals();paused=true;const o=zone.interactables.find(o=>o.type===type&&(!id||o.storyId===id&&o.step===index||o.gigId===id));if(!o)throw Error('Native43 objective missing '+type+' '+id+' '+index);
 Object.assign(camera,{x:o.x,z:o.z,y:1.72});const n=nearest();if(n?.ref!==o)throw Error('Native nearest refused43 '+o.id+' '+JSON.stringify(n&&{kind:n.kind,id:n.ref.id}));
 if(blocked(zone,camera.x,camera.z,.38)||lineBlocked(camera.x,camera.z,o.x,o.z))throw Error('Native43 point inaccessible '+o.id);paused=false;return{id:o.id,zone:zone.id,x:o.x,z:o.z};
},{type,id,index});}
async function snapshot43(kind,id){return page.evaluate(({kind,id})=>{
 paused=true;const P=window.__SOMA_V37_SAVE__,saved=P.snapshot();P.validate(saved);const A=window.__SOMA_V43__,r=A.state()[kind==='story'?'story':'gigs'][id],e=window.__SOMA_MISSIONS76__.snapshot().encounters.find(e=>e.kind===kind&&e.id===id);
 return{zone:zone.id,credits:state.credits,record:JSON.parse(JSON.stringify(r)),production:JSON.parse(JSON.stringify(A.state())),
 enemies:zone.robots.filter(q=>q.v43Owner===e?.owner).map(q=>({id:q.id,health:q.health,maxHealth:q.maxHealth,downHandled:!!q.v32DownHandled,role:q.v32Role,faction:q.v33Faction??null})),
 loot:JSON.parse(JSON.stringify(saved.payload.layers[32].loot)),xp:JSON.parse(JSON.stringify(state.player27)),factions:JSON.parse(JSON.stringify(saved.payload.layers[33])),combat:JSON.parse(JSON.stringify(saved.payload.layers[32].zoneCombat[zone.id]||null)),save:P.getStatus(),channel:window.__SOMA_MISSIONS76__.snapshot().channelActive,newDomains:Object.keys(saved.payload.core).filter(k=>/^v7[1-9]$/.test(k))};
},{kind,id});}
async function accept43(kind,def){
 const target=kind==='story'?'station-interiorA':await page.evaluate(d=>Object.values(WORLD.zones).find(z=>z.district===d&&z.type==='social').id,def.district);
 const journey=await footRoute(target),point=await at43(kind==='story'?'v43CampaignConsole':'v43FixerBoard');await page.keyboard.press('e');
 await page.locator('#dialogueChoices button').filter({hasText:(kind==='story'?'Ouvrir · ':'Accepter · ')+def.title}).click();const state=await snapshot43(kind,def.id);assert.equal(state.record.status,'active');return{journey,point,state};
}
async function encounter43(kind,def,index){
 const e=await page.evaluate(({kind,id})=>window.__SOMA_MISSIONS76__.snapshot().encounters.find(e=>e.kind===kind&&e.id===id),{kind,id:def.id}),journey=await footRoute(e.zone);
 const fixture=await page.evaluate(e=>{paused=true;const qs=zone.robots.filter(q=>q.v43Owner===e.owner);if(qs.length!==e.count)throw Error('Native43 roster missing '+e.owner);qs[0].health=37;if(qs.length>1)qs[1].health=0;updateAI(.1);return qs.map(q=>({id:q.id,health:q.health,downHandled:!!q.v32DownHandled,role:q.v32Role}));},e);
 let before=await snapshot43(kind,def.id);assert.equal(before.enemies[0].health,37);if(e.count>1){assert.equal(before.enemies[1].downHandled,true);assert(Object.hasOwn(before.loot,'loot-'+before.enemies[1].id));}assert.deepEqual(before.newDomains,[]);
 const text=await grouped(`native43-${def.id}-wounded-grouped.json`),imported=await page.evaluate(text=>window.__SOMA_GROUP64__.importText(text,true),text);assert.equal(imported.ok,true);
 let restored=await snapshot43(kind,def.id);for(const key of ['enemies','loot','xp','factions'])assert.deepEqual(restored[key],before[key],key+' after import43');
 await page.reload({waitUntil:'domcontentloaded'});await ready();let reloaded=await snapshot43(kind,def.id);for(const key of ['enemies','loot','xp','factions'])assert.deepEqual(reloaded[key],before[key],key+' after reload43');assert.equal(reloaded.save.blocked,false);assert.equal(reloaded.save.loadSource,'current');
 await page.evaluate(e=>{for(const q of zone.robots)if(q.v43Owner===e.owner)q.health=0;updateAI(.1);},e);const defeated=await snapshot43(kind,def.id);assert(defeated.enemies.every(q=>q.health===0&&q.downHandled));
 const downText=await grouped(`native43-${def.id}-defeated-grouped.json`);assert.equal((await page.evaluate(text=>window.__SOMA_GROUP64__.importText(text,true),downText)).ok,true);await page.reload({waitUntil:'domcontentloaded'});await ready();
 const downReload=await snapshot43(kind,def.id);for(const key of ['enemies','loot','xp','factions'])assert.deepEqual(downReload[key],defeated[key],key+' defeated reload43');
 const point=await at43(kind==='story'?'v43StoryNode':'v43GigNode',def.id,index);await page.keyboard.press('e');const completed=await snapshot43(kind,def.id);if(kind==='story')assert.equal(completed.record.step,index+1);else assert.equal(completed.record.status,'return');
 await shot('native43-'+def.id+'-secured');return{e,journey,fixture,before,imported,restored,reloaded,defeated,downReload,point,completed};
}
async function channel43(kind,def,index,stage){
 const journey=await footRoute(stage.zone),type=kind==='story'?'v43StoryNode':'v43GigNode',point=await at43(type,def.id,index);
 await page.keyboard.down('e');await page.waitForFunction(()=>window.__SOMA_MISSIONS76__.snapshot().channelActive);await page.keyboard.up('e');let state=await snapshot43(kind,def.id);assert.equal(state.channel,false);if(kind==='story')assert.equal(state.record.step,index);else assert.equal(state.record.status,'active');
 const text=await page.evaluate(()=>window.__SOMA_GROUP64__.exportText());await at43(type,def.id,index);await page.keyboard.down('e');await page.waitForFunction(()=>window.__SOMA_MISSIONS76__.snapshot().channelActive);let imported;try{imported=await page.evaluate(text=>window.__SOMA_GROUP64__.importText(text,true),text);}finally{await page.keyboard.up('e');}assert.equal(imported.ok,true);
 state=await snapshot43(kind,def.id);assert.equal(state.channel,false);await at43(type,def.id,index);await page.keyboard.down('e');try{await page.waitForFunction(({kind,id,index})=>{const r=window.__SOMA_V43__.state()[kind==='story'?'story':'gigs'][id];return kind==='story'?r.step===index+1:r.status==='return';},{kind,id:def.id,index},{timeout:30000});}finally{await page.keyboard.up('e');}
 const completed=await snapshot43(kind,def.id);assert.equal(completed.channel,false);return{journey,point,imported,completed};
}
async function return43(kind,def){
 const target=kind==='story'?'station-interiorA':await page.evaluate(d=>Object.values(WORLD.zones).find(z=>z.district===d&&z.type==='social').id,def.district),type=kind==='story'?'v43CampaignConsole':'v43FixerBoard';
 const away=await footRoute('station-exterior'),remote=await page.evaluate(({kind,id})=>{const a=window.__SOMA_V43__;return kind==='story'?a.closeStory(id):a.closeGig(id);},{kind,id:def.id});assert.equal(remote,false);
 const journey=await footRoute(target),point=await at43(type);await page.keyboard.press('e');const label=(kind==='story'?'Clore · ':'Remettre · ')+def.title;
 await page.locator('#dialogueChoices button').filter({hasText:label}).waitFor({state:'visible'});await page.evaluate(label=>{window.__qaStale43=[...document.querySelectorAll('#dialogueChoices button')].find(b=>b.textContent.includes(label)).onclick;},label);
 const expectedReward=await page.evaluate(credits=>Math.max(0,Math.round(credits*Math.max(1,Number(v27Stats().contractReward)||1))),def.reward);
 const text=await page.evaluate(()=>window.__SOMA_GROUP64__.exportText()),before=await snapshot43(kind,def.id),imported=await page.evaluate(text=>window.__SOMA_GROUP64__.importText(text,true),text);assert.equal(imported.ok,true);await page.evaluate(()=>window.__qaStale43());const stale=await snapshot43(kind,def.id);assert.equal(stale.record.paid,false);assert.equal(stale.credits,before.credits);
 await at43(type);await page.keyboard.press('e');await page.evaluate(label=>{window.__qaHand43=[...document.querySelectorAll('#dialogueChoices button')].find(b=>b.textContent.includes(label)).onclick;},label);
 await page.locator('#dialogueChoices button').filter({hasText:label}).click();await page.evaluate(()=>window.__qaHand43());const completed=await snapshot43(kind,def.id);assert.equal(completed.record.paid,true);assert.equal(completed.record.status,'done');assert.equal(completed.credits,before.credits+expectedReward);assert.equal(completed.production.streetCred,before.production.streetCred+def.cred);assert.equal(completed.production.stats[kind==='story'?'storyClosed':'gigsClosed'],before.production.stats[kind==='story'?'storyClosed':'gigsClosed']+1);
 const completedText=await grouped(`native43-${def.id}-completed-grouped.json`);assert.equal((await page.evaluate(text=>window.__SOMA_GROUP64__.importText(text,true),completedText)).ok,true);await page.reload({waitUntil:'domcontentloaded'});await ready();const final=await snapshot43(kind,def.id);assert.equal(final.credits,completed.credits);assert.equal(final.record.paid,true);assert.equal(final.production.streetCred,completed.production.streetCred);assert.equal(await page.evaluate(({kind,id})=>kind==='story'?window.__SOMA_V43__.closeStory(id):window.__SOMA_V43__.closeGig(id),{kind,id:def.id}),false);
 await shot('native43-'+def.id+'-reward-once');return{away,remote,journey,point,before,imported,stale,completed,final};
}
async function story43(def){
 await step('native43/'+def.id+'/physical-acceptance',()=>accept43('story',def));
 for(const [index,s]of def.steps.entries()){
  if(s.kind==='channel')await step('native43/'+def.id+'/native-channel',()=>channel43('story',def,index,s));
  else if(['fight','boss'].includes(s.kind))await step('native43/'+def.id+'/combat32-import-rawreload',()=>encounter43('story',def,index));
  else await step('native43/'+def.id+'/choice-stale-callback',async()=>{
   const journey=await footRoute(s.zone),point=await at43('v43StoryNode',def.id,index);await page.keyboard.press('e');await page.locator('#dialogueChoices button').first().waitFor({state:'visible'});await page.evaluate(()=>{window.__qaChoice43=document.querySelector('#dialogueChoices button').onclick;});
   const text=await page.evaluate(()=>window.__SOMA_GROUP64__.exportText()),imported=await page.evaluate(text=>window.__SOMA_GROUP64__.importText(text,true),text);assert.equal(imported.ok,true);await page.evaluate(()=>window.__qaChoice43());const stale=await snapshot43('story',def.id);assert.equal(stale.record.step,index);
   await at43('v43StoryNode',def.id,index);await page.keyboard.press('e');await page.locator('#dialogueChoices button').filter({hasText:s.choices[0][1]}).click();const completed=await snapshot43('story',def.id);assert.equal(completed.record.choice,s.choices[0][0]);assert.equal(completed.record.status,'return');return{journey,point,imported,stale,completed};
  });
 }
 await step('native43/'+def.id+'/physical-return-reward-once',()=>return43('story',def));
}
async function native43(){
 const audit=await step('native43/all-source-identity-location-and-route-audit',async()=>{
  const result=await page.evaluate(()=>{
   paused=true;window.__SOMA_V42__.state().finale.status='done';window.__SOMA_V42__.save();const A=window.__SOMA_V43__;A.refreshUnlocks();const source=window.__SOMA_MISSIONS76__.snapshot();
   const routes=[];for(const m of A.story){let from='station-interiorA';for(const [index,s]of m.steps.entries()){const path=window.__SOMA_V45__.findRoute(from,s.zone);if(!path.length)throw Error('Story43 has no authored approach '+m.id+' '+index);routes.push({kind:'story',id:m.id,index,from,to:s.zone,path});from=s.zone;}if(!window.__SOMA_V45__.findRoute(from,'station-interiorA').length)throw Error('Story43 has no hand-in route '+m.id);}
   for(const g of A.gigs){const board=Object.values(WORLD.zones).find(z=>z.district===g.district&&z.type==='social'),path=window.__SOMA_V45__.findRoute(board.id,g.zone);if(!path.length||!window.__SOMA_V45__.findRoute(g.zone,board.id).length)throw Error('Gig43 has no authored approach '+g.id);routes.push({kind:'gig',id:g.id,from:board.id,to:g.zone,path});}
   return{source,stories:JSON.parse(JSON.stringify(A.story)),gigs:JSON.parse(JSON.stringify(A.gigs)),routes};
  });assert.equal(result.source.encounters.reduce((n,e)=>n+e.enemies.length,0),55);assert.equal(result.source.locationRepairs.length,23);assert.equal(result.routes.length,34);assert(result.source.stories.every(m=>m.stages.every(s=>s.knownZone)));assert(result.source.gigs.every(g=>g.knownZone));
  await fs.writeFile(path.join(output,'authored-production43-audit.json'),JSON.stringify(result,null,2)+'\n');return result;
 });
 await story43(audit.stories[0]);
 await step('native43/boss-prerequisite-fixture',async()=>page.evaluate(()=>{paused=true;const A=window.__SOMA_V43__,s=A.state();for(const m of A.story.slice(0,4)){const r=s.story[m.id];r.status='done';r.step=m.steps.length;r.paid=true;}A.refreshUnlocks();A.save();return{fixture:'Only prior production43 story records marked done/paid; no rewards granted.',story:s.story};}));
 await story43(audit.stories.find(m=>m.id==='venus-hypotheses'));
 for(const type of ['combat','infiltration','recovery']){
  const def=audit.gigs.find(g=>g.type===type);await step('native43/'+def.id+'/physical-acceptance',()=>accept43('gig',def));
  if(type==='combat')await step('native43/'+def.id+'/combat32-import-rawreload',()=>encounter43('gig',def));
  else{
   if(type==='infiltration')await step('native43/'+def.id+'/wounded-source-roster-import',async()=>{
    const journey=await footRoute(def.zone),before=await page.evaluate(id=>{paused=true;const qs=zone.robots.filter(q=>q.v43Owner===`gig-${id}`);qs[0].health=43;qs[1].health=0;updateAI(.1);return qs.map(q=>({id:q.id,health:q.health,role:q.v32Role,downHandled:!!q.v32DownHandled}));},def.id),text=await grouped(`native43-${def.id}-wounded-grouped.json`);assert.equal((await page.evaluate(text=>window.__SOMA_GROUP64__.importText(text,true),text)).ok,true);const restored=await snapshot43('gig',def.id);assert.deepEqual(restored.enemies.map(q=>({id:q.id,health:q.health,role:q.role,downHandled:q.downHandled})),before);await page.evaluate(id=>{for(const q of zone.robots)if(q.v43Owner===`gig-${id}`)q.health=0;updateAI(.1);},def.id);return{journey,before,restored};
   });
   await step('native43/'+def.id+'/native-channel',()=>channel43('gig',def,undefined,def));
  }
  await step('native43/'+def.id+'/physical-return-reward-once',()=>return43('gig',def));
 }
}

async function fresh45ImportProof(){
 await commandMenu();const exported=await page.evaluate(()=>window.__SOMA_GROUP64__.exportText()),primary=page,isolated=await browser.newContext({viewport:{width:1440,height:1000},locale:'fr-FR',acceptDownloads:true});
 try{
  assert.deepEqual((await isolated.storageState()).origins,[]);page=await isolated.newPage();page.setDefaultTimeout(opts.timeout);page.on('pageerror',e=>report.pageErrors.push({step:currentStep,error:String(e.stack||e)}));page.on('console',m=>{if(m.type()==='error')report.consoleErrors.push({step:currentStep,text:m.text()});});page.on('response',r=>{if(r.status()>=400)report.httpErrors.push({step:currentStep,status:r.status(),url:r.url()});});
  assert.equal((await page.goto(opts.url,{waitUntil:'domcontentloaded'})).status(),200);await ready();await page.getByRole('button',{name:'Explorer Marseille réelle',exact:true}).click();await page.waitForFunction(()=>!paused&&zone?.v52District);await page.evaluate(()=>{paused=true;});
  const fresh=await page.evaluate(()=>({uiTab:window.__SOMA_V45__.state().uiTab,commandWasOpened:document.querySelector('#v45Command.open')!==null}));assert.equal(fresh.uiTab,'operations');assert.equal(fresh.commandWasOpened,false);
  const imported=await page.evaluate(text=>window.__SOMA_GROUP64__.importText(text,true),exported);assert.equal(imported.ok,true);
  const old=await page.evaluate(text=>{const C=window.__SOMA_GROUP64_CORE__,p=C.decode(text);delete p.modules['45'].value.uiTab;return C.encode(p);},exported);
  const legacyImported=await page.evaluate(text=>window.__SOMA_GROUP64__.importText(text,true),old);assert.equal(legacyImported.ok,true);assert.equal(await page.evaluate(()=>window.__SOMA_V45__.state().uiTab),'operations');
  const afterLegacy=await page.evaluate(text=>window.__SOMA_GROUP64__.importText(text,true),exported);assert.equal(afterLegacy.ok,true);
  const rejected=[];for(const mutation of [{uiTab:8},{uiTab:'invented'},{unknown45:true}]){
   const result=await page.evaluate(async({text,mutation})=>{const C=window.__SOMA_GROUP64_CORE__,p=C.decode(text);Object.assign(p.modules['45'].value,mutation);const capture=()=>JSON.stringify(Object.keys(localStorage).sort().map(k=>[k,localStorage.getItem(k)])),before=capture();let refusal=null;try{await window.__SOMA_GROUP64__.importText(C.encode(p),true);}catch(error){refusal=String(error.message||error);}return{mutation,refusal,storageUnchanged:before===capture()};},{text:exported,mutation});assert(result.refusal);assert.equal(result.storageUnchanged,true);rejected.push(result);
  }
  return{fixture:'A native command-menu export is imported directly into a second fresh profile without opening its command menu. A rechecksummed copy omits only the legitimate historical uiTab45 field; malformed type/enum and unknown-field copies are refusal fixtures.',fresh,imported,legacyImported,afterLegacy,rejected};
 }finally{await isolated.close();page=primary;await page.evaluate(()=>{closeModals();paused=true;});}
}

async function main(){
 await fs.mkdir(output,{recursive:true});report.provenance=await sourceEvidence(__filename);
 try{
  browser=await chromium.launch({executablePath:opts.chromium,headless:true,args:['--no-sandbox','--enable-webgl','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
  context=await browser.newContext({viewport:{width:1440,height:1000},locale:'fr-FR',acceptDownloads:true});assert.deepEqual((await context.storageState()).origins,[]);
  page=await context.newPage();page.setDefaultTimeout(opts.timeout);page.on('pageerror',e=>report.pageErrors.push({step:currentStep,error:String(e.stack||e)}));page.on('console',m=>{if(m.type()==='error')report.consoleErrors.push({step:currentStep,text:m.text()});});page.on('response',r=>{if(r.status()>=400)report.httpErrors.push({step:currentStep,status:r.status(),url:r.url()});});
  report.environment={chromium:browser.version(),playwright:require('playwright/package.json').version,softwareWebGL:true,freshContext:true};
  const ops=await step('fresh-profile-and-authored-five-operation-audit',async()=>{
   assert.equal((await page.goto(opts.url,{waitUntil:'domcontentloaded'})).status(),200);await ready();await page.getByRole('button',{name:'Explorer Marseille réelle',exact:true}).click();await page.waitForFunction(()=>!paused&&zone?.v52District);
   const result=await page.evaluate(()=>{if(!enterZone('station-exterior'))throw Error('Original campaign selection refused.');paused=true;return{audit:window.__SOMA_MISSIONS75__.snapshot(),operations:JSON.parse(JSON.stringify(window.__SOMA_V45__.operations))};});assert.equal(result.operations.length,5);
   for(const op of result.audit.operations)for(const s of op.stages){assert.equal(s.knownZone,true);assert(s.returnRoute.length>0);if(s.index)assert(s.approach.length>0);}
   await fs.writeFile(path.join(output,'authored-operation-audit.json'),JSON.stringify(result,null,2)+'\n');return result;
  });
  if(opts.scope!=='production43')for(const op of ops.operations)await operation(op);
  if(opts.scope!=='operations'){await step('native45/direct-fresh-import-legacy-optional-ui-and-strict-refusals',fresh45ImportProof);await native43();}
  const final=await page.evaluate(()=>({operations:window.__SOMA_MISSIONS75__.snapshot(),production43:window.__SOMA_MISSIONS76__.snapshot()}));if(opts.scope!=='production43')assert(final.operations.operations.every(op=>op.paid&&op.status==='done'));if(opts.scope!=='operations'){assert(final.production43.stories.filter(m=>['manifestes-noyes','venus-hypotheses'].includes(m.id)).every(m=>m.paid&&m.status==='done'));assert(final.production43.gigs.filter(g=>['port-quai-muet','port-balise-ferry','corniche-eau-verre'].includes(g.id)).every(g=>g.paid&&g.status==='done'));}report.final=final;
  assert.deepEqual(report.pageErrors,[]);assert.deepEqual(report.consoleErrors,[]);assert.deepEqual(report.httpErrors,[]);report.passed=true;
 }catch(error){report.failure=String(error.stack||error);process.exitCode=1;try{if(page){report.diagnostic=await page.evaluate(()=>({zone:zone?.id,paused,save:window.__SOMA_V37_SAVE__?.getStatus(),missions:window.__SOMA_MISSIONS75__?.snapshot(),openModals:[...document.querySelectorAll('.modal.open')].map(x=>x.id)}));const invalid=await page.evaluate(()=>window.__qaInvalidCampaign||null);if(invalid)await fs.writeFile(path.join(output,'invalid-campaign-diagnostic.json'),JSON.stringify(invalid,null,2)+'\n');await shot('failure');}}catch(e){report.captureFailure=String(e);}}
 finally{await browser?.close();await finishEvidence(report,__filename);report.finishedAt=new Date().toISOString();await fs.writeFile(path.join(output,'report.json'),JSON.stringify(report,null,2)+'\n');process.stdout.write(JSON.stringify({passed:report.passed,report:path.join(output,'report.json'),steps:report.steps.map(({name,status})=>({name,status})),failure:report.failure,provenanceFailure:report.provenanceFailure},null,2)+'\n');}
}
main().catch(e=>{process.stderr.write(String(e.stack||e)+'\n');process.exitCode=1;});
