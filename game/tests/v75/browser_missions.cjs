#!/usr/bin/env node
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs/promises'),path=require('node:path');
const {chromium}=require('playwright'),{sourceEvidence,finishEvidence}=require('./browser_provenance.cjs');
const opts={url:'http://127.0.0.1:8777/SOMA_MASSILIA_URBAIN_v0_75.html',chromium:'/usr/bin/chromium',output:'/workspace/massilia-geodata-generated/validation-v75-2026-11-02/missions',timeout:90000};
for(let i=2;i<process.argv.length;i++){const k=process.argv[i].replace(/^--/,'');assert(Object.hasOwn(opts,k)&&process.argv[i+1]);opts[k]=k==='timeout'?Number(process.argv[++i]):process.argv[++i];}
const output=path.resolve(opts.output),report={schema:'soma/browser-missions/75/1',passed:false,startedAt:new Date().toISOString(),steps:[],screenshots:[],pageErrors:[],consoleErrors:[],httpErrors:[],
 instrumentation:[
  'A fresh browser profile enters Marseille through the native start button. One initial enterZone(station-exterior) selects the original authored campaign; subsequent on-foot journeys use its existing portals through nearest/interact, and driving uses native vehicles and v44 road seams.',
  'Pause → Archives & continuité → Centre de commandement accepts, traces and hands in each operation. Native E holds complete timed channels and native choice buttons select doctrine. Camera poses and existing vehicles are positioned at original objects/portals; this is bounded interaction QA, not continuous player traversal.',
  'For every authored encounter one unit is partially injured and another set to zero; updateAI(.1) invokes the real defeat/loot owner. Remaining units are neutralized the same way after export/import/reload checks. No actor, vehicle, route, collider, faction, damage handler or save API is invented or replaced.',
  'The real grouped exporter/importer64 and campaign validator37 exercise existing combat32, faction33, policy45 and campaign owners. Stale callbacks are held only to verify that grouped import invalidates them. Pauses bound comparison clocks.',
 ],limits:['Controlled defeat fixtures do not establish a human combat playthrough or player GPU performance.','The five operations use the original conceptual authored world; they do not activate physical AMP geography or certify a Marseille route at 1:1.']};
let browser,context,page,currentStep='load';
async function step(name,run){currentStep=name;const row={name,startedAt:new Date().toISOString()};report.steps.push(row);process.stderr.write('[v75 missions] '+name+'\n');try{row.observation=await run();row.status='passed';return row.observation;}catch(e){row.status='failed';row.error=String(e.stack||e);throw e;}finally{row.finishedAt=new Date().toISOString();}}
async function shot(name){await page.screenshot({path:path.join(output,name+'.png')});report.screenshots.push(name+'.png');}
async function ready(){await page.waitForFunction(()=>window.__SOMA_V75__?.ready&&window.__SOMA_GROUP64__?.ready&&window.__SOMA_V37_SAVE__?.getStatus().ready&&window.__SOMA_MISSIONS75__);}
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
  Object.assign(camera,{x:p.approach?.x??p.x,z:p.approach?.z??p.z,y:1.72});const n=nearest();if(n?.kind!=='portal'||n.ref!==p)throw Error('Native nearest refused portal '+p.code+' '+JSON.stringify({portal:p,camera:{x:camera.x,z:camera.z},visible:interactionVisible(p),nearest:n&&{kind:n.kind,id:n.ref.id}}));
  paused=false;interact();paused=true;if(zone.id!==next)throw Error('Native portal refused '+p.code);hops.push({from,to:zone.id,code:p.code,kind:p.kind});
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
  for(const op of ops.operations)await operation(op);
  const final=await page.evaluate(()=>window.__SOMA_MISSIONS75__.snapshot());assert(final.operations.every(op=>op.paid&&op.status==='done'));report.final=final;
  assert.deepEqual(report.pageErrors,[]);assert.deepEqual(report.consoleErrors,[]);assert.deepEqual(report.httpErrors,[]);report.passed=true;
 }catch(error){report.failure=String(error.stack||error);process.exitCode=1;try{if(page){report.diagnostic=await page.evaluate(()=>({zone:zone?.id,paused,save:window.__SOMA_V37_SAVE__?.getStatus(),missions:window.__SOMA_MISSIONS75__?.snapshot(),openModals:[...document.querySelectorAll('.modal.open')].map(x=>x.id)}));const invalid=await page.evaluate(()=>window.__qaInvalidCampaign||null);if(invalid)await fs.writeFile(path.join(output,'invalid-campaign-diagnostic.json'),JSON.stringify(invalid,null,2)+'\n');await shot('failure');}}catch(e){report.captureFailure=String(e);}}
 finally{await browser?.close();await finishEvidence(report,__filename);report.finishedAt=new Date().toISOString();await fs.writeFile(path.join(output,'report.json'),JSON.stringify(report,null,2)+'\n');process.stdout.write(JSON.stringify({passed:report.passed,report:path.join(output,'report.json'),steps:report.steps.map(({name,status})=>({name,status})),failure:report.failure,provenanceFailure:report.provenanceFailure},null,2)+'\n');}
}
main().catch(e=>{process.stderr.write(String(e.stack||e)+'\n');process.exitCode=1;});
