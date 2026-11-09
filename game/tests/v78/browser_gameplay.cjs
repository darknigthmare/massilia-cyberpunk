#!/usr/bin/env node
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');
const {run}=require('./browser_harness.cjs');
const {hash}=require('./browser_provenance.cjs');

const chamberView=()=>({zone:zone.id,weapon:WEAPONS[state.weapon].name,
  action:window.__SOMA_CHAMBER78__.snapshot(),
  material:structuredClone(window.__SOMA_V30__.getState().durability[window.__SOMA_V30__.activeWeapon()]),
  reloadLeft,ammo:structuredClone(state.ammo)});

async function startChamber(page){
  const fixture=await page.evaluate(()=>{
    closeModals();window.__SOMA_CHAMBER78__.cancel();state.driving=null;
    state.weapon=WEAPONS.findIndex(w=>w.id==='pistol');state.health=Math.max(1,state.health);
    const names=['pistol','pacifier'];for(const id of names)if(!state.unlocked.includes(id))state.unlocked.push(id);
    v29State().weaponLoadout=[...names];
    const A=window.__SOMA_V30__,record=A.getState().durability[A.activeWeapon()];
    record.condition=100;record.jammed=true;paused=false;
    return{zone:zone.id,weapon:A.activeWeapon(),material:structuredClone(record)};
  });
  await page.keyboard.press('r');
  const started=await page.evaluate(()=>{paused=true;return{
    action:window.__SOMA_CHAMBER78__.snapshot(),reloadLeft,
    material:structuredClone(window.__SOMA_V30__.getState().durability[window.__SOMA_V30__.activeWeapon()])};});
  assert(started.action.active&&started.action.remaining>0);assert.equal(started.reloadLeft,0);
  assert.equal(started.material.jammed,true);
  return{fixture,started};
}

async function targetCallNode(page,id){
  return page.evaluate(id=>{
    const o=zone.interactables.find(o=>o.type==='v45CallNode'&&o.callId===id);
    if(!o)throw Error('Original authored call node absent');
    let pose=null;
    for(const radius of [1.6,2.4,.8])for(let k=0;k<16&&!pose;k++){
      const a=k*Math.PI/8,x=o.x+Math.cos(a)*radius,z=o.z+Math.sin(a)*radius;
      if(blocked(zone,x,z,.38))continue;
      camera.x=x;camera.z=z;camera.y=1.72;camera.yaw=Math.atan2(o.x-x,o.z-z);
      if(nearest()?.ref===o&&interactionVisible(o))pose={x,z,yaw:camera.yaw};
    }
    if(!pose)throw Error('No free source-node interaction pose');
    const selected=nearest();paused=false;interact();
    return{pose,node:{id:o.id,x:o.x,z:o.z},selected:{kind:selected.kind,id:selected.ref.id},
      route:structuredClone(window.__SOMA_V45__.state().route),
      dialogue:document.querySelector('#dialogue').textContent};
  },id);
}

async function driveAuthoredRoute(page,target){
  return page.evaluate(target=>{
    closeModals();paused=true;keys.clear();touches.clear();
    const A=window.__SOMA_V45__,route=A.findRoute(zone.id,target,true);
    if(route.length<2)throw Error('No original vehicle route '+zone.id+' → '+target);
    const v=zone.vehicles.find(v=>v.pilotable&&!v.hidden&&!v.ai&&!v.disabled&&
      !isFlyingVehicleKind(v.kind)&&!isWaterVehicleKind(v.kind));
    if(!v)throw Error('No original parked road vehicle in '+zone.id);
    v.speed=0;Object.assign(camera,{x:v.x,z:v.z});
    if(!enterVehicle(v))throw Error('Native vehicle entry refused');
    const sourceVehicle={id:v.id,kind:v.kind,sourcePose:{x:v.x,z:v.z}},hops=[];paused=false;
    for(const next of route.slice(1)){
      const from=zone.id,p=zone.portals.find(p=>p.target===next&&p.v44VehiclePassable&&p.v53LegalTravel!==false);
      const car=zone.vehicles.find(q=>q.id===state.driving);
      if(!p||!car)throw Error('Missing original road seam '+from+' → '+next);
      for(let i=0;i<12;i++)move(.1);
      car.x=p.x;car.z=p.z;
      car.heading=p.side==='N'?Math.PI:p.side==='S'?0:p.side==='W'?-Math.PI/2:Math.PI/2;car.speed=.5;
      if(!window.__SOMA_V44__.tryVehicleSeam())throw Error('Native vehicle seam refused '+p.code);
      const arrived=zone.vehicles.find(q=>q.id===state.driving),condition=arrived.condition;
      update(.1);
      const retained=zone.vehicles.find(q=>q.id===state.driving);
      if(retained!==arrived||retained.condition!==condition)throw Error('Native update replaced the carried car');
      hops.push({from,to:zone.id,code:p.code,kind:p.kind,vehicle:state.driving,
        sameObjectAfterOwnerUpdate:true,condition});
    }
    const car=zone.vehicles.find(q=>q.id===state.driving);car.speed=0;
    if(!exitVehicle())throw Error('Native dismount refused');
    paused=true;return{route,sourceVehicle,hops};
  },target);
}

run({scope:'gameplay',script:__filename,
  instrumentation:[
    'A fresh browser profile clicks Explorer Marseille réelle. enterZone subsequently selects existing authored zones for bounded systems checks; this is not continuous geographic traversal.',
    'Two original guns are marked carried/owned. The original pistol material30 record is explicitly set jammed/condition100 to start its real R action. No timer, weapon definition, serializer or production function is replaced.',
    'paused freezes the native simulation for identity comparisons. The death check sets health0, calls the installed maintain owner, then restores health; no natural death/recovery campaign is claimed.',
    'An unrelated automatically generated call is resolved through its public owner only to isolate the escort fixture, without claiming its physical objective or rewards were earned.',
    'At call nodes the fixture selects a bounded collision-free pose where real nearest/visibility chooses the original object. Tracer and run-start buttons are clicked in the native command menu.',
    'For driven checks, original parked cars are placed at original passable portals and native44 handoff/update/dismount execute. This is a bounded seam/progression check, not continuous street driving or passenger transport.',
    'The real37/64 serializers/importers verify interrupted actions and continuity. Fixtures are isolated from user profiles.'
  ],
  scenario:async t=>{
    const{page,step,shot}=t;
    await step('load-current-campaign-through-native-explorer',async()=>{
      assert.equal((await page.goto(t.opts.url,{waitUntil:'domcontentloaded'})).status(),200);
      await t.ready();await page.waitForFunction(()=>window.__SOMA_CHAMBER78__&&window.__SOMA_MISSIONS78__);
      await page.getByRole('button',{name:'Explorer Marseille réelle',exact:true}).click();
      await page.waitForFunction(()=>!paused&&zone?.v52District);
      return page.evaluate(()=>({edition:window.__SOMA_V78__.snapshot(),zone:zone.id,sourceCampaign:true}));
    });
    await step('native-cortex-menu-remains-usable',async()=>{
      await page.keyboard.press('Shift+F1');await page.locator('#v70-tactics.open').waitFor({state:'visible'});
      assert(await page.evaluate(()=>paused));await page.locator('#v70-tactics [data-v70-close]').click();
      await page.waitForFunction(()=>!paused);return{openedAndClosed:true};
    });
    await step('source-zone-and-native-chamber-fixture',async()=>{
      assert(await page.evaluate(()=>enterZone('station-exterior')));
      return startChamber(page);
    });
    await step('ordinary-pause-and-same-arsenal-selection-preserve-chamber',async()=>{
      const before=await page.evaluate(chamberView);await page.waitForTimeout(180);
      await page.evaluate(()=>openModal('arsenal'));
      await page.locator('#arsenalGrid .card').nth(0).getByRole('button',{name:'Équiper',exact:true}).click();
      const after=await page.evaluate(chamberView);
      assert.deepEqual(after.action,before.action);assert.deepEqual(after.material,before.material);
      return{before,after,realPauseMilliseconds:180};
    });
    await step('arsenal-change-and-return-abandon-chamber-without-wear',async()=>{
      await page.locator('#arsenalGrid .card').nth(1).getByRole('button',{name:'Équiper',exact:true}).click();
      assert.equal((await page.evaluate(chamberView)).action.active,false);
      await page.locator('#arsenalGrid .card').nth(0).getByRole('button',{name:'Équiper',exact:true}).click();
      const after=await page.evaluate(chamberView);assert.equal(after.action.active,false);
      assert.equal(after.material.jammed,true);assert.equal(after.material.condition,100);
      await shot('arsenal-cancels-native-chamber');await page.evaluate(()=>closeModals());return after;
    });
    await step('native-zone-transition-cancels-chamber-instantly',async()=>{
      const before=await startChamber(page);
      const after=await page.evaluate(()=>{if(!enterZone('corniche-exterior'))throw Error('Source zone refused');paused=true;return{
        zone:zone.id,action:window.__SOMA_CHAMBER78__.snapshot(),
        material:structuredClone(window.__SOMA_V30__.getState().durability[window.__SOMA_V30__.activeWeapon()])};});
      assert.equal(after.action.active,false);assert.equal(after.action.remaining,0);
      assert.equal(after.material.jammed,true);assert.equal(after.material.condition,100);return{before,after};
    });
    await step('controlled-death-invalidates-native-chamber',async()=>{
      await startChamber(page);
      const after=await page.evaluate(()=>{const health=state.health;state.health=0;window.__SOMA_CHAMBER78__.maintain();
        const r={action:window.__SOMA_CHAMBER78__.snapshot(),material:structuredClone(window.__SOMA_V30__.getState().durability[window.__SOMA_V30__.activeWeapon()])};state.health=health;return r;});
      assert.equal(after.action.active,false);assert.equal(after.material.jammed,true);assert.equal(after.material.condition,100);
      return{after,fixture:'Explicit health0 then maintain, health restored; natural death is not tested.'};
    });
    await step('group64-refuses-a-live-chamber-without-mutating-it',async()=>{
      await startChamber(page);const before=await page.evaluate(chamberView);
      const after=await page.evaluate(()=>{let error='';try{window.__SOMA_GROUP64__.exportText();}catch(e){error=e.message;}
        return{error,refusal:window.__SOMA_GROUP64__.refusal(),action:window.__SOMA_CHAMBER78__.snapshot(),material:structuredClone(window.__SOMA_V30__.getState().durability[window.__SOMA_V30__.activeWeapon()])};});
      assert.match(after.error,/action en cours/);assert.deepEqual(after.action,before.action);assert.deepEqual(after.material,before.material);
      await page.evaluate(()=>window.__SOMA_CHAMBER78__.cancel());return{before,after};
    });
    await step('real37-import-replaces-record-and-clears-chamber',async()=>{
      const text=await page.evaluate(()=>window.__SOMA_V37_SAVE__.exportText());await startChamber(page);
      const after=await page.evaluate(text=>{const root=state,record=window.__SOMA_V30__.getState().durability[window.__SOMA_V30__.activeWeapon()];
        const result=window.__SOMA_V37_SAVE__.importText(text);paused=true;return{result,rootReplaced:root!==state,
          recordReplaced:record!==window.__SOMA_V30__.getState().durability[window.__SOMA_V30__.activeWeapon()],action:window.__SOMA_CHAMBER78__.snapshot()};},text);
      assert.equal(after.result,true);assert(after.rootReplaced&&after.recordReplaced);assert.equal(after.action.active,false);
      return{after,bytes:Buffer.byteLength(text),sha256:hash(text)};
    });
    await step('native-R-completes-chamber-once-with-original-wear',async()=>{
      const before=await startChamber(page);await page.evaluate(()=>{closeModals();paused=false;});
      await page.waitForFunction(()=>!window.__SOMA_CHAMBER78__.snapshot().active&&
        window.__SOMA_V30__.getState().durability[window.__SOMA_V30__.activeWeapon()].jammed===false);
      const after=await page.evaluate(()=>{paused=true;return{
        action:window.__SOMA_CHAMBER78__.snapshot(),reloadLeft,
        material:structuredClone(window.__SOMA_V30__.getState().durability[window.__SOMA_V30__.activeWeapon()])};});
      assert.equal(after.reloadLeft,0);assert(Math.abs(after.material.condition-99.4)<1e-8);return{before,after};
    });
    await step('ordinary-ammunition-reload-keeps-native27-transfer',async()=>{
      await page.evaluate(()=>{closeModals();state.ammo.pistol.mag=1;state.ammo.pistol.reserve=20;paused=false;});
      await page.keyboard.press('r');await page.waitForFunction(()=>reloadLeft<=0&&state.ammo.pistol.mag===12);
      const after=await page.evaluate(()=>{paused=true;return{ammo:structuredClone(state.ammo.pistol),chamber:window.__SOMA_CHAMBER78__.snapshot(),reload:window.__SOMA_RELOAD77__.snapshot()};});
      assert.deepEqual(after.ammo,{mag:12,reserve:9});assert.equal(after.chamber.active,false);assert.equal(after.reload.active,false);return after;
    });
    await step('native-escort-object-loads-vehicle-delivery-guidance',async()=>{
      const setup=await page.evaluate(()=>{closeModals();enterZone('corniche-exterior');paused=true;const A=window.__SOMA_V45__;
        const existing=A.state().director.activeCall;if(existing&&!A.resolveCall(existing))throw Error('Automatic call fixture cleanup refused');
        const id='corniche-ambulance-privee';if(!A.spawnCall(id)||!A.acceptCall(id))throw Error('Source escort refused');
        return{id,call:structuredClone(A.state().calls[id]),credits:state.credits};});
      const after=await targetCallNode(page,setup.id);
      assert.equal(after.route.targetZone,setup.call.targetZone);assert.equal(after.route.vehicleOnly,true);
      assert.match(after.dialogue,/trajet véhicule est chargé/);await shot('escort-vehicle-guidance');
      t.report.escort={...setup};return{setup,after};
    });
    await step('manual-GPS-survives-escort-dialogue-and-explicit-Tracer-targets-delivery',async()=>{
      const id=t.report.escort.id;
      const manual=await page.evaluate(()=>{closeModals();const A=window.__SOMA_V45__;if(!A.setDestination('port-exterior','Destination personnelle',true))throw Error('Manual route fixture refused');return structuredClone(A.state().route);});
      const after=await targetCallNode(page,id);assert.deepEqual(after.route,manual);assert.match(after.dialogue,/Destination GPS conservée/);
      await page.evaluate(()=>{closeModals();window.__SOMA_V45__.openCommand('calls');});
      await page.locator('[data-v45-track-call="'+id+'"]').click();
      const traced=await page.evaluate(()=>{paused=true;return structuredClone(window.__SOMA_V45__.state().route);});
      assert.equal(traced.targetZone,t.report.escort.call.targetZone);assert.equal(traced.vehicleOnly,true);
      assert.match(traced.label,/acheminement/);return{manual,after,traced};
    });
    await step('escort-delivery-completes-through-original-vehicle-seams',async()=>{
      const expected=t.report.escort;
      const before=await page.evaluate(()=>({credits:state.credits,stats:structuredClone(window.__SOMA_V45__.state().stats)}));
      const drive=await driveAuthoredRoute(page,expected.call.targetZone);
      const after=await page.evaluate(id=>({credits:state.credits,call:structuredClone(window.__SOMA_V45__.state().calls[id]),stats:structuredClone(window.__SOMA_V45__.state().stats),route:structuredClone(window.__SOMA_V45__.state().route)}),expected.id);
      assert.equal(after.call.status,'done');assert.equal(after.stats.callsResolved,before.stats.callsResolved+1);
      assert.equal(after.credits,before.credits+360);assert.equal(after.route.targetZone,null);return{before,drive,after};
    });
    await step('native-Port-run-starts-and-pays-once-after-existing-road-seam',async()=>{
      const before=await page.evaluate(()=>{closeModals();if(!enterZone('port-exterior'))throw Error('Original Port zone refused');paused=true;
        const A=window.__SOMA_V45__;A.openCommand('runs');return{credits:state.credits,result:structuredClone(A.state().races['run-port']),stats:structuredClone(A.state().stats)};});
      await page.locator('[data-v45-start-race="port"]').click();
      const active=await page.evaluate(()=>structuredClone(window.__SOMA_V45__.state().raceActive));
      assert(active);assert.equal(active.path[0],'port-exterior');assert.equal(active.path.at(-1),'corniche-exterior');
      const drive=await driveAuthoredRoute(page,active.path.at(-1));
      const after=await page.evaluate(()=>({credits:state.credits,active:window.__SOMA_V45__.state().raceActive,
        result:structuredClone(window.__SOMA_V45__.state().races['run-port']),stats:structuredClone(window.__SOMA_V45__.state().stats)}));
      assert.equal(after.active,null);assert.equal(after.result.attempts,before.result.attempts+1);
      assert.equal(after.result.wins,before.result.wins+1);assert.equal(after.credits,before.credits+280);
      assert.equal(after.stats.racesWon,before.stats.racesWon+1);
      assert.equal(await page.evaluate(()=>window.__SOMA_V45__.finishRace()),false);await shot('Port-run-native-completion');
      return{before,active,drive,after,scope:'Conceptual authored vehicle seams, not a continuous geographic driving test.'};
    });
    await step('group64-roundtrip-keeps-current-progression-and-resource-owners',async()=>{
      const exported=await page.evaluate(()=>{window.__SOMA_CHAMBER78__.cancel();window.__SOMA_RELOAD77__.cancel();
        const G=window.__SOMA_GROUP64__,text=G.exportText(),core=JSON.parse(G.validate(text).payload.campaign).payload.core;
        return{text,credits:state.credits,ammo:structuredClone(state.ammo),race:structuredClone(window.__SOMA_V45__.state().races['run-port']),
          newDomains:Object.keys(core).filter(k=>/^v7[1-8]$/.test(k))};});
      assert.deepEqual(exported.newDomains,[]);
      const after=await page.evaluate(async text=>{state.credits+=17;const result=await window.__SOMA_GROUP64__.importText(text,true);paused=true;
        return{result,credits:state.credits,ammo:structuredClone(state.ammo),race:structuredClone(window.__SOMA_V45__.state().races['run-port']),chamber:window.__SOMA_CHAMBER78__.snapshot()};},exported.text);
      assert.equal(after.result.ok,true);assert.equal(after.credits,exported.credits);
      assert.deepEqual(after.ammo,exported.ammo);assert.deepEqual(after.race,exported.race);assert.equal(after.chamber.active,false);
      await fs.writeFile(path.join(t.output,'grouped-save-v78.json'),exported.text);
      return{expected:{...exported,text:undefined},after,bytes:Buffer.byteLength(exported.text),sha256:hash(exported.text)};
    });
    await step('browser-reload-restores-current-native-progression',async()=>{
      const before=await page.evaluate(()=>({credits:state.credits,ammo:structuredClone(state.ammo),race:structuredClone(window.__SOMA_V45__.state().races['run-port'])}));
      await t.reload();await t.ready();
      const after=await page.evaluate(()=>{paused=true;return{credits:state.credits,ammo:structuredClone(state.ammo),race:structuredClone(window.__SOMA_V45__.state().races['run-port']),chamber:window.__SOMA_CHAMBER78__.snapshot(),save:window.__SOMA_V37_SAVE__.getStatus()};});
      assert.equal(after.credits,before.credits);assert.deepEqual(after.ammo,before.ammo);assert.deepEqual(after.race,before.race);
      assert.equal(after.chamber.active,false);assert.equal(after.save.blocked,false);return{before,after};
    });
  }
});
