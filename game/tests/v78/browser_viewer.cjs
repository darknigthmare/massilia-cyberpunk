#!/usr/bin/env node
'use strict';
const assert=require('node:assert/strict');
const {run}=require('./browser_harness.cjs');

async function aimAt(page,target){
  const pose={e:target.e,n:target.n-40/Math.tan(1.5),h:target.h+40};
  assert(await page.evaluate(p=>window.__SOMA_METRO_VIEWER__.teleportMetric(p.e,p.n,p.h),pose));
  await page.evaluate(()=>window.__SOMA_METRO_VIEWER__.ready());
  await page.waitForFunction(id=>{
    const s=window.__SOMA_METRO_VIEWER__.snapshot();
    return s.pendingGeometry===0&&s.geometry.meshes>0&&s.targetIds.includes(id)&&
      s.cache.running===0&&s.cache.queued===0;
  },target.cell);
  await page.locator('#scene').dispatchEvent('mousedown');
  await page.evaluate(()=>window.dispatchEvent(new MouseEvent('mousemove',{
    movementX:-window.__SOMA_METRO_VIEWER__.snapshot().camera.yaw/.002,movementY:475,bubbles:true})));
  await page.evaluate(()=>window.dispatchEvent(new MouseEvent('mouseup',{bubbles:true})));
  const scene=await page.evaluate(()=>window.__SOMA_METRO_VIEWER__.snapshot());
  assert(Math.abs(scene.camera.pitch+1.5)<1e-8);assert(Math.abs(scene.camera.yaw)<.005);
  assert(scene.cache.residentIds.includes(target.cell));
  return{target,pose,scene};
}

run({scope:'viewer',script:__filename,
  instrumentation:[
    'A fresh browser profile stays at the native title screen and opens the independent flyover with its actual entry button.',
    'Native teleportMetric and synthetic mouse drag position the ordinary camera over two documented source witnesses. ready() and running/queued/pending geometry are awaited after each teleport.',
    'The selected source roof and road come from actual streamed rendered triangles. No triangle, hit, ray, model, source response or inspector owner is replaced.',
    'The roof profile and apex are inferred from explicit OSM shape/height and a bounded convex frame. This is not a surveyed roof or architectural1:1 claim.'
  ],
  scenario:async t=>{
    const{page,step,shot}=t;
    await step('load-current-title-with-native-flyover-entry',async()=>{
      assert.equal((await page.goto(t.opts.url,{waitUntil:'domcontentloaded'})).status(),200);
      await t.ready();await page.locator('#v69-metropole-entry').waitFor({state:'visible'});
      return page.evaluate(()=>({version:window.__SOMA_V78__.version,paused,
        titleVisible:document.querySelector('#boot').classList.contains('open')}));
    });
    await step('native-button-opens-current-independent-streamed-viewer',async()=>{
      await t.navigate(()=>page.locator('#v69-metropole-entry').click());
      assert.match(page.url(),/metropole-viewer-v78\.html/);
      await page.waitForFunction(()=>window.__SOMA_METRO_VIEWER__&&window.__SOMA_ARCHITECTURE78_CORE__);
      await page.evaluate(()=>window.__SOMA_METRO_VIEWER__.ready());
      await page.waitForFunction(()=>{const s=window.__SOMA_METRO_VIEWER__.snapshot();return s.renderedFrames>1&&s.buildings>0&&s.pendingGeometry===0;});
      const r=await page.evaluate(()=>{const m=JSON.parse(document.getElementById('soma-viewer-data').textContent);
        return{metadata:{version:m.version,returnToGame:m.returnToGame},scene:window.__SOMA_METRO_VIEWER__.snapshot(),architecture:window.__SOMA_ARCHITECTURE78_CORE__.snapshot()};});
      assert.equal(r.metadata.version,'0.78.0');assert.equal(r.metadata.returnToGame,'SOMA_MASSILIA_URBAIN_v0_78.html');
      assert.equal(r.scene.campaignPersistenceLoaded,false);assert.equal(r.scene.webglError,0);
      assert.deepEqual(r.scene.webglErrors,[]);assert.deepEqual(r.scene.errors,[]);assert.equal(r.scene.buildFailures,0);
      assert.equal(r.architecture.sourceFootprintsChanged,false);t.report.viewerMode=r.scene.mode;
      await shot('installed-viewer-source-scene');return r;
    });
    const baseline=await t.storage();
    await step('native-building-inspector-observes-interpreted-source-pyramid',async()=>{
      const target={id:'osm/way/264887685',cell:'V52-MC-W04-S00',
        e:891967.6098140328,n:6247387.865841345,h:46.81017304225207};
      const witness=await aimAt(page,target);
      await page.locator('#architecture71-open').click();
      await page.waitForFunction(()=>window.__SOMA_ARCHITECTURE71_VIEWER__.snapshot().phase==='ready');
      const result=await page.evaluate(()=>window.__SOMA_ARCHITECTURE71_VIEWER__.snapshot().result);
      t.report.roofWitness={...witness,result};
      assert.equal(result.status,'building');assert.equal(result.selection.id,target.id);
      const s=result.selection;
      assert.equal(s.roof.modelled,true);assert.equal(s.roof.displayedShape,'pyramidal');
      assert.equal(s.roof.reason,'osm-parametric-pyramidal-source-clipped-convex-frame');
      assert.equal(s.roof.surveyed,false);assert.equal(s.sourceTags['roof:shape'],'pyramidal');
      assert.equal(s.footprint.geometrySHA256,'fad077b2a1f2806c832547bc840f58cb00dec744f121fd4acda7193a17a106a3');
      assert(s.hitL93.h<45.5&&s.hitL93.h>41.8,'The real ray must meet the lowered roof slope, not the former flat top or a wall.');
      assert.equal(s.sourceTags['roof:height'],'5');assert.equal(s.heightMeters,35);
      assert(Math.abs(s.baseAltitudeNGFMeters-11.81017304225207)<1e-6);
      assert.equal(s.roofFrame78.boundaryToleranceMeters,.01);assert.equal(s.roofFrame78.sourceFootprintRetained,true);
      assert.equal(s.roofFrame78.entireBoundariesChecked,true);assert.equal(s.roofFrame78.apexInferred,true);
      assert.equal(s.roofFrame78.roofSurveyed,false);assert.equal(s.architecturalOneToOneCertified,false);
      const text=await page.locator('#architecture71-dialog').textContent();
      assert.match(text,/Cadre de toiture interprété/);assert.match(text,/Emprise, retraits et positions des murs source conservés/);
      assert.match(text,/nouveaux triangles de toiture limités aux triangles préparés/);
      await shot('source-pyramid-interpreted-inspector');
      await page.keyboard.press('i');await page.locator('#architecture71-dialog').waitFor({state:'hidden'});
      return{target,result,scope:'Rendered source witness; source contours retained and profile/apex explicitly interpreted.'};
    });
    await step('road-inspector-retains-directed-source-sidewalk-attribution',async()=>{
      const target={cell:'V52-MC-13',e:892976.311340941,n:6247730.345141885,h:36.1181956192};
      const witness=await aimAt(page,target);
      await page.locator('#road72-open').click();
      await page.waitForFunction(()=>window.__SOMA_ROAD_INSPECTION72_VIEWER__.snapshot().phase==='ready');
      const result=await page.evaluate(()=>window.__SOMA_ROAD_INSPECTION72_VIEWER__.snapshot().result);
      t.report.roadWitness={...witness,result};
      assert.equal(result.status,'road');assert.equal(result.selection.surfaceKind,'walk');
      assert(Math.hypot(result.selection.hitL93.e-target.e,result.selection.hitL93.n-target.n)<.25);
      const ids=result.selection.candidates.map(c=>c.id);
      assert(ids.includes('osm/way/353224808'));assert(!ids.includes('osm/way/460530284'));
      assert.equal(result.selection.physicalAccessibilityVerified,false);
      assert.equal(result.selection.navigation.graphRead,false);
      await shot('retained-source-sidewalk-inspector');await page.keyboard.press('j');
      await page.locator('#road72-dialog').waitFor({state:'hidden'});return{target,result};
    });
    await step('independent-inspection-preserves-all-campaign-storage',async()=>{
      assert.deepEqual(await t.storage(),baseline);
      const scene=await page.evaluate(()=>window.__SOMA_METRO_VIEWER__.snapshot());
      assert.equal(scene.buildFailures,0);assert.deepEqual(scene.errors,[]);assert.deepEqual(scene.webglErrors,[]);
      return{storageKeys:Object.keys(baseline),byteIdentical:true,scene};
    });
    await step('native-return-link-restores-current-game',async()=>{
      await t.navigate(()=>page.locator('#return-game').click());await t.ready();
      const r=await page.evaluate(()=>({version:window.__SOMA_V78__.version,
        save:window.__SOMA_V37_SAVE__.getStatus(),chamber:window.__SOMA_CHAMBER78__.snapshot()}));
      assert.equal(r.version,'0.78.0');assert.equal(r.save.blocked,false);assert.equal(r.chamber.active,false);return r;
    });
  }
});
