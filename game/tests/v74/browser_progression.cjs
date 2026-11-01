#!/usr/bin/env node
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs/promises'),path=require('node:path');
const {chromium}=require('playwright');
const {sourceEvidence}=require('./browser_provenance.cjs');
const opts={url:'http://127.0.0.1:8774/SOMA_MASSILIA_URBAIN_v0_74.html',chromium:'/usr/bin/chromium',output:'/tmp/massilia-v74-progression',timeout:90000};
for(let i=2;i<process.argv.length;i++){const k=process.argv[i].replace(/^--/,'');assert(Object.hasOwn(opts,k)&&process.argv[i+1]);opts[k]=k==='timeout'?Number(process.argv[++i]):process.argv[++i];}
const output=path.resolve(opts.output),report={schema:'soma/browser-progression/74/1',passed:false,startedAt:new Date().toISOString(),steps:[],screenshots:[],pageErrors:[],consoleErrors:[],httpErrors:[],
 instrumentation:[
  'The native Pause → Archives & continuité → Centre de commandement buttons accept and hand in the first authored Act III operation; native E starts the timed extraction. F9 retains its older portraits shortcut.',
  'Existing authored scenes are entered and camera poses are placed at existing objective objects. Native vehicles are positioned at existing road portals to exercise the v44 vehicle seam owner; no scene, actor, vehicle, route or collider is invented.',
  'One existing interceptor is partially injured and another is set to zero health, then updateAI(.1) runs the real defeat/loot owner. Remaining interceptors are neutralized the same way after persistence checks; this is a controlled integration fixture, not a combat playthrough.',
  'The game is paused for comparisons and bounded owner ticks; old DOM callbacks are retained solely to verify that import invalidates them. No save, collision or progression API is replaced.',
  'A derivative of the authentic encounter export moves only the four exact historical interceptor records and their existing loot into the former corniche-route owner zone, and restores the old owned objective GPS. Public checksum helpers repackage this declared migration fixture; it is not presented as an authentic historical player save.',
 ],limits:['This bounded scenario does not establish a human campaign playthrough, traversal of the whole city or player GPU performance.','Legacy authored Act III scenes are tested as authored scenes and are not presented as measured Marseille geometry.']};
let browser,context,page,currentStep='load',partialText,finishedText;
async function step(name,run){currentStep=name;const row={name,startedAt:new Date().toISOString()};report.steps.push(row);process.stderr.write('[v74 progression] '+name+'\n');try{row.observation=await run();row.status='passed';return row.observation;}catch(e){row.status='failed';row.error=String(e.stack||e);throw e;}finally{row.finishedAt=new Date().toISOString();}}
async function shot(name){await page.screenshot({path:path.join(output,name+'.png')});report.screenshots.push(name+'.png');}
async function ready(){await page.waitForFunction(()=>window.__SOMA_V74__?.ready&&window.__SOMA_GROUP64__?.ready&&window.__SOMA_V37_SAVE__?.getStatus().ready&&window.__SOMA_PROGRESSION74__);}
async function commandMenu(){
 await page.evaluate(()=>{closeModals();openModal('pause');});const command=page.locator('[data-v45-command]');
 if(!await command.isVisible()){
  const back=page.locator('#pause .v66-back:visible');if(await back.count())await back.click();
  await page.locator('#pause .v66-section-button').filter({hasText:'Archives & continuité'}).click();
 }
 await command.click();await page.locator('#v45Command.open').waitFor({state:'visible'});
}
function snapshot(){
 const P=window.__SOMA_V37_SAVE__,saved=P.snapshot();P.validate(saved);const op=window.__SOMA_V45__.state().operations['asphalte-fantome'];
 return{zone:zone.id,credits:state.credits,reputation:state.reputation.port,operation:JSON.parse(JSON.stringify(op)),stats:JSON.parse(JSON.stringify(window.__SOMA_V45__.state().stats)),
  enemies:(zone.robots||[]).filter(q=>q.v45Owner==='operation-asphalte-fantome-2').map(q=>({id:q.id,health:q.health,downHandled:!!q.v32DownHandled,role:q.v32Role})),
  combat:JSON.parse(JSON.stringify(saved.payload.layers[32].zoneCombat['corniche-exterior']||null)),loot:JSON.parse(JSON.stringify(saved.payload.layers[32].loot)),
  xp:JSON.parse(JSON.stringify(state.player27)),saveStatus:P.getStatus(),newDomains:Object.keys(saved.payload.core).filter(k=>/^v7[1-9]$/.test(k)),progression:window.__SOMA_PROGRESSION74__.snapshot()};
}
async function atObject(type,operationId,index){return page.evaluate(({type,operationId,index})=>{
 closeModals();const o=zone.interactables.find(o=>o.type===type&&(!operationId||o.operationId===operationId&&o.step===index));if(!o)throw Error('Authored objective absent.');
 Object.assign(camera,{x:o.x,z:o.z,y:1.72});paused=false;const n=nearest();if(n?.ref!==o)throw Error('Native nearest interaction did not select '+o.id);
 return{id:o.id,x:o.x,z:o.z,blocked:blocked(zone,camera.x,camera.z,.38),visible:!lineBlocked(camera.x,camera.z,o.x,o.z)};
 },{type,operationId,index});}
async function exportGrouped(filename){
 await page.evaluate(()=>window.__SOMA_GROUP64__.open());const event=page.waitForEvent('download');await page.locator('#v64-group-export').click();const download=await event;await download.saveAs(path.join(output,filename));return fs.readFile(path.join(output,filename),'utf8');
}
async function main(){
 await fs.mkdir(output,{recursive:true});report.provenance=await sourceEvidence(__filename);
 try{
  browser=await chromium.launch({executablePath:opts.chromium,headless:true,args:['--no-sandbox','--enable-webgl','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
  context=await browser.newContext({viewport:{width:1440,height:1000},locale:'fr-FR',acceptDownloads:true});assert.deepEqual((await context.storageState()).origins,[]);
  page=await context.newPage();page.setDefaultTimeout(opts.timeout);page.on('pageerror',e=>report.pageErrors.push({step:currentStep,error:String(e.stack||e)}));
  page.on('console',m=>{if(m.type()==='error')report.consoleErrors.push({step:currentStep,text:m.text()});});page.on('response',r=>{if(r.status()>=400)report.httpErrors.push({step:currentStep,status:r.status(),url:r.url()});});
  report.environment={chromium:browser.version(),playwright:require('playwright/package.json').version,softwareWebGL:true,freshContext:true};
  await step('native-dossier-acceptance-and-authored-timed-extraction',async()=>{
   assert.equal((await page.goto(opts.url,{waitUntil:'domcontentloaded'})).status(),200);await ready();
   await page.getByRole('button',{name:'Explorer Marseille réelle',exact:true}).click();await page.waitForFunction(()=>!paused&&zone?.v52District);
   await page.evaluate(()=>{if(!enterZone('station-exterior'))throw Error('Authored Station Zéro unavailable.');closeModals();});
   await commandMenu();await page.locator('[data-v45-accept-op="asphalte-fantome"]').click();
   await page.evaluate(()=>{closeModals();if(!enterZone('port-exterior'))throw Error('Authored Port unavailable.');});
   const point=await atObject('v45OperationNode','asphalte-fantome',0);assert.equal(point.blocked,false);
   await page.keyboard.down('e');try{await page.waitForFunction(()=>window.__SOMA_V45__.state().operations['asphalte-fantome'].step===1,null,{timeout:30000});}finally{await page.keyboard.up('e');}
   const result=await page.evaluate(snapshot);assert.equal(result.operation.status,'active');assert.equal(result.operation.step,1);await shot('01-extraction-complete');return{point,result};
  });
  await step('existing-road-seams-advance-drive-and-create-native-encounter',async()=>{
   const result=await page.evaluate(()=>{
    closeModals();paused=true;const A=window.__SOMA_V45__,route=A.findRoute(zone.id,'corniche-exterior',true);if(route.length<2)throw Error('No authored vehicle route to Corniche.');
    const v=zone.vehicles.find(v=>v.pilotable&&!v.hidden&&!v.ai&&!v.disabled&&!isFlyingVehicleKind(v.kind)&&!isWaterVehicleKind(v.kind));if(!v)throw Error('No native parked road vehicle.');
    v.speed=0;Object.assign(camera,{x:v.x,z:v.z});if(!enterVehicle(v))throw Error('Native vehicle entry refused.');keys.clear();touches.clear();paused=false;const hops=[];
    for(const next of route.slice(1)){
     const from=zone.id,p=zone.portals.find(p=>p.target===next&&p.v44VehiclePassable&&p.v53LegalTravel!==false),car=zone.vehicles.find(q=>q.id===state.driving);if(!p||!car)throw Error('Missing authored road seam '+from+' -> '+next);
     for(let i=0;i<12;i++)move(.1);car.x=p.x;car.z=p.z;car.heading=p.side==='N'?Math.PI:p.side==='S'?0:p.side==='W'?-Math.PI/2:Math.PI/2;car.speed=.5;
     if(!window.__SOMA_V44__.tryVehicleSeam())throw Error('Native road seam refused '+p.code);update(.1);hops.push({from,to:zone.id,portal:p.code,vehicle:state.driving});
    }
    const car=zone.vehicles.find(q=>q.id===state.driving);car.speed=0;if(!exitVehicle())throw Error('Native dismount refused.');paused=true;
    return{route,hops,operation:JSON.parse(JSON.stringify(A.state().operations['asphalte-fantome'])),enemies:zone.robots.filter(q=>q.v45Owner==='operation-asphalte-fantome-2').map(q=>({id:q.id,role:q.v32Role,health:q.health}))};
   });assert.equal(result.operation.step,2);assert.equal(result.enemies.length,4);assert(result.enemies.some(q=>q.role==='blade'));return result;
  });
  await step('real-defeat-loot-and-campaign-checkpoint',async()=>{
   const result=await page.evaluate(()=>{
    const enemies=zone.robots.filter(q=>q.v45Owner==='operation-asphalte-fantome-2');enemies[0].health=27;enemies[1].health=0;updateAI(.1);paused=true;
    const P=window.__SOMA_V37_SAVE__;P.schedule();if(!P.flush())throw Error('Real checkpoint refused: '+P.getStatus().lastError);window.__SOMA_V45__.save();return null;
   });const saved=await page.evaluate(snapshot);assert.equal(saved.enemies[0].health,27);assert.equal(saved.enemies[1].health,0);assert.equal(saved.enemies[1].downHandled,true);
   assert(Object.keys(saved.loot).some(id=>id===`loot-${saved.enemies[1].id}`));assert.deepEqual(saved.newDomains,[]);await shot('02-encounter-checkpoint');return saved;
  });
  await step('authentic-grouped-export-import-restores-partial-encounter',async()=>{
   const before=await page.evaluate(snapshot);partialText=await exportGrouped('partial-encounter-grouped.json');
   const result=await page.evaluate(async text=>{
    state.credits+=17;for(const q of zone.robots)if(q.v45Owner==='operation-asphalte-fantome-2')q.health=q.maxHealth;
    const imported=await window.__SOMA_GROUP64__.importText(text,true);return imported;
   },partialText);assert.equal(result.ok,true);const after=await page.evaluate(snapshot);
   assert.equal(after.credits,before.credits);assert.deepEqual(after.enemies,before.enemies);assert.deepEqual(after.loot,before.loot);assert.deepEqual(after.xp,before.xp);assert.equal(after.operation.step,2);return{before,imported:result,after};
  });
  await step('exact-legacy-encounter-and-owned-gps-migrate-through-real-grouped-import',async()=>{
   const before=await page.evaluate(snapshot);
   const fixture=await page.evaluate(text=>{
    const G=window.__SOMA_GROUP64__,C=window.__SOMA_GROUP64_CORE__,payload=G.validate(text).payload,campaign=JSON.parse(payload.campaign),combat=campaign.payload.layers[32].zoneCombat;
    const ids=Array.from({length:4},(_,i)=>`v45-operation-asphalte-fantome-2-${i}`),legacy=combat['corniche-route']||{enemies:{},alarm:0,alarmDisabled:false,reinforced:false,cleared:false,lastSeen:0};
    for(const id of ids){legacy.enemies[id]=combat['corniche-exterior'].enemies[id];delete combat['corniche-exterior'].enemies[id];}
    combat['corniche-route']=legacy;
    for(const id of ids){const loot=campaign.payload.layers[32].loot['loot-'+id];if(loot){loot.zone='corniche-route';if(id.endsWith('-1')&&loot.role==='blade')loot.role='melee';}}
    const module45=payload.modules[45].value,step=window.__SOMA_V45__.operations[0].steps[2];
    module45.route={...module45.route,targetZone:'corniche-route',label:step.label,path:[],vehicleOnly:false};module45.tracked={kind:'operation',id:'asphalte-fantome'};
    campaign.checksum=C.hash(JSON.stringify(campaign.payload));payload.campaign=JSON.stringify(campaign);const migrated=C.encode(payload);G.validate(migrated);return{ids,text:migrated};
   },partialText);
   await fs.writeFile(path.join(output,'legacy-corniche-derivative-fixture.json'),fixture.text);
   const imported=await page.evaluate(text=>window.__SOMA_GROUP64__.importText(text,true),fixture.text);assert.equal(imported.ok,true);const after=await page.evaluate(snapshot);
   assert.deepEqual(after.enemies,before.enemies);assert.equal(after.credits,before.credits);assert.deepEqual(after.xp,before.xp);assert.equal(after.operation.step,2);
   const gps=await page.evaluate(()=>JSON.parse(JSON.stringify(window.__SOMA_V45__.state().route)));assert.equal(gps.targetZone,'corniche-exterior');
   return{fixtureIDs:fixture.ids,fixtureFile:'legacy-corniche-derivative-fixture.json',before,imported,after,gps};
  });
  await step('reload-restores-damage-downHandled-and-no-extra-defeat-reward',async()=>{
   const before=await page.evaluate(snapshot);await page.reload({waitUntil:'domcontentloaded'});await ready();await page.evaluate(()=>{paused=true;});const after=await page.evaluate(snapshot);
   assert.equal(after.zone,'corniche-exterior');assert.deepEqual(after.enemies,before.enemies);assert.deepEqual(after.loot,before.loot);assert.deepEqual(after.xp,before.xp);assert.equal(after.credits,before.credits);assert.equal(after.saveStatus.blocked,false);return{before,after};
  });
  await step('finish-native-evidence-choice-and-remote-return-guide',async()=>{
   await page.evaluate(()=>{for(const q of zone.robots)if(q.v45Owner==='operation-asphalte-fantome-2')q.health=0;updateAI(.1);closeModals();});
   await atObject('v45OperationNode','asphalte-fantome',2);await page.keyboard.press('e');
   const beforeReturn=await page.evaluate(()=>{const route=window.__SOMA_V45__.findRoute(zone.id,'station-exterior');if(!route.length)throw Error('No authored return route.');if(!enterZone('station-exterior'))throw Error('Station entry refused.');return{route};});
   await atObject('v45OperationNode','asphalte-fantome',3);await page.keyboard.press('e');await page.locator('#dialogueChoices button').filter({hasText:'Confier les preuves à l’union des conducteurs'}).click();
   await page.evaluate(()=>{closeModals();if(!enterZone('port-exterior'))throw Error('Authored remote scene unavailable.');});await commandMenu();
   assert.equal(await page.locator('[data-v45-close-op="asphalte-fantome"]').count(),0);await page.locator('[data-v45-return-op="asphalte-fantome"]').click();
   const result=await page.evaluate(()=>({status:window.__SOMA_V45__.state().operations['asphalte-fantome'].status,route:JSON.parse(JSON.stringify(window.__SOMA_V45__.state().route)),credits:state.credits}));
   assert.equal(result.status,'return');assert.equal(result.route.targetZone,'station-exterior');await shot('03-return-guided');return{beforeReturn,result};
  });
  await step('native-hand-in-callback-invalidated-by-real-import',async()=>{
   await page.evaluate(()=>{closeModals();enterZone('station-exterior');});await atObject('v45CommandConsole');await commandMenu();
   await page.evaluate(()=>{const b=document.querySelector('[data-v45-close-op="asphalte-fantome"]');if(!b)throw Error('No native physical hand-in button.');window.__qaOldHandIn=b.onclick;});
   const before=await page.evaluate(snapshot);const text=await page.evaluate(()=>window.__SOMA_GROUP64__.exportText());
   const imported=await page.evaluate(text=>window.__SOMA_GROUP64__.importText(text,true),text);assert.equal(imported.ok,true);
   await page.evaluate(()=>window.__qaOldHandIn());const after=await page.evaluate(snapshot);assert.equal(after.credits,before.credits);assert.equal(after.operation.status,'return');assert.equal(after.operation.paid,false);return{before,imported,after};
  });
  await step('native-physical-hand-in-pays-once-and-survives-import-and-reload',async()=>{
   await atObject('v45CommandConsole');await commandMenu();const before=await page.evaluate(snapshot);
   await page.evaluate(()=>{window.__qaHandIn=document.querySelector('[data-v45-close-op="asphalte-fantome"]').onclick;});
   await page.locator('[data-v45-close-op="asphalte-fantome"]').click();await page.evaluate(()=>{window.__qaHandIn();window.__SOMA_V37_SAVE__.flush();paused=true;});
   const after=await page.evaluate(snapshot);assert.equal(after.credits,before.credits+760);assert.equal(after.reputation,before.reputation+3);assert.equal(after.operation.paid,true);assert.equal(after.operation.status,'done');assert.equal(after.stats.operationsClosed,before.stats.operationsClosed+1);
   await shot('04-physical-hand-in-once');finishedText=await exportGrouped('completed-operation-grouped.json');
   const imported=await page.evaluate(text=>window.__SOMA_GROUP64__.importText(text,true),finishedText);assert.equal(imported.ok,true);const restored=await page.evaluate(snapshot);assert.equal(restored.credits,after.credits);assert.equal(restored.operation.paid,true);
   await page.reload({waitUntil:'domcontentloaded'});await ready();await page.evaluate(()=>{paused=true;});const reloaded=await page.evaluate(snapshot);assert.equal(reloaded.credits,after.credits);assert.equal(reloaded.operation.paid,true);assert.equal(reloaded.stats.operationsClosed,after.stats.operationsClosed);assert.equal(reloaded.saveStatus.blocked,false);
   const second=await page.evaluate(()=>window.__SOMA_V45__.closeOperation('asphalte-fantome'));assert.equal(second,false);return{before,after,imported,restored,reloaded,second};
  });
  assert.deepEqual(report.pageErrors,[]);assert.deepEqual(report.consoleErrors,[]);assert.deepEqual(report.httpErrors,[]);report.passed=true;
 }catch(error){report.failure=String(error.stack||error);process.exitCode=1;try{if(page){report.diagnostic=await page.evaluate(()=>({title:document.title,v74:!!window.__SOMA_V74__?.ready,v73:!!window.__SOMA_V73__?.ready,v70:!!window.__SOMA_V70__?.ready,group:window.__SOMA_GROUP64__?.ready,save:window.__SOMA_V37_SAVE__?.getStatus(),progression:window.__SOMA_PROGRESSION74__?.snapshot(),zone:zone?.id,paused,openModals:[...document.querySelectorAll('.modal.open')].map(x=>x.id)}));await shot('failure');}}catch(e){report.captureFailure=String(e);}}
 finally{await browser?.close();report.provenanceFinished=await sourceEvidence(__filename);report.sourceSetUnchanged=report.provenance.aggregateSHA256===report.provenanceFinished.aggregateSHA256;report.finishedAt=new Date().toISOString();await fs.writeFile(path.join(output,'report.json'),JSON.stringify(report,null,2)+'\n');process.stdout.write(JSON.stringify({passed:report.passed,report:path.join(output,'report.json'),steps:report.steps.map(({name,status})=>({name,status})),failure:report.failure},null,2)+'\n');}
}
main().catch(e=>{process.stderr.write(String(e.stack||e)+'\n');process.exitCode=1;});
