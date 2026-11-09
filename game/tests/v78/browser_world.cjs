#!/usr/bin/env node
'use strict';
const assert=require('node:assert/strict');
const{run}=require('./browser_harness.cjs');

run({scope:'world',script:__filename,
  instrumentation:[
    'A fresh browser profile clicks the native geographic Explorer and keeps its default25m terrain.',
    'enterZone selects the existing source cell12. Its original taxi is placed at its original verified source-road portal only after native roadGate/canCross and vehicle-body checks pass on both cells.',
    'The native55 handoff executes directly. This is a bounded successful-transfer fixture, not continuous driving or a natural I/O failure. No vehicle, geometry, save, renderer or handoff API is replaced.',
    'Transactional rollback under injected I/O exceptions is covered separately by source-owner unit tests, not claimed by this positive browser path.'
  ],
  scenario:async t=>{
    const{page,step,shot}=t;
    await step('load-native-geographic-campaign-with-historical-terrain-default',async()=>{
      assert.equal((await page.goto(t.opts.url,{waitUntil:'domcontentloaded'})).status(),200);await t.ready();
      await page.waitForFunction(()=>window.__SOMA_V55__?.ready&&window.__SOMA_TERRAIN75__?.ready);
      await page.getByRole('button',{name:'Explorer Marseille réelle',exact:true}).click();
      await page.waitForFunction(()=>!paused&&zone?.v52District);
      const r=await page.evaluate(()=>({version:window.__SOMA_V78__.version,terrain:window.__SOMA_TERRAIN75__.snapshot(),zone:zone.id}));
      assert.equal(r.terrain.selected,'legacy25m');assert.equal(r.terrain.stepM,25);return r;
    });
    await step('original-source-taxi-and-road-seam-pass-native-body-gates',async()=>{
      const r=await page.evaluate(()=>{
        closeModals();paused=true;if(!enterZone('geo:V52-MC-12'))throw Error('Original source-cell entry refused');
        paused=true;const A=window.__SOMA_V55__,from=zone;
        const v=from.vehicles.find(v=>v.id==='geo:V52-MC-12-pilot-taxi');
        const p=from.portals.find(p=>p.code==='V52-4D9B0BA7'&&p.target==='geo:V52-MC-W01-N03');
        if(!v||!p||!p.v53VerifiedSeam||!p.v44VehiclePassable||p.v53LegalTravel===false)throw Error('Verified source witness absent');
        const plan=A.canCross(from,p.side,{x:p.x,z:p.z},v);if(!plan.ok)throw Error(plan.reason);
        const sourcePose={x:p.x,z:p.z,heading:Math.PI},targetPose=A.core.transfer(from.v50Record,plan.to.v50Record,sourcePose);
        const sourceBlocked=vehicleBlockedAt(v,sourcePose.x,sourcePose.z,sourcePose.heading,v.id,from,v.y||0);
        const targetBlocked=vehicleBlockedAt(v,targetPose.x,targetPose.z,sourcePose.heading,v.id,plan.to,v.y||0);
        if(sourceBlocked||targetBlocked)throw Error('Source or target whole-body gate refused');
        return{from:from.id,to:plan.to.id,vehicle:{id:v.id,x:v.x,z:v.z,heading:v.heading,condition:v.condition},
          portal:{code:p.code,side:p.side,sourceRoad:p.v50SourceId,verified:p.v53VerifiedSeam},sourcePose,targetPose,sourceBlocked,targetBlocked};
      });
      assert.equal(r.portal.sourceRoad,'osm/way/460530280');assert.equal(r.sourceBlocked,false);assert.equal(r.targetBlocked,false);
      t.report.sourceWitness=r;return r;
    });
    await step('native55-transfer-retains-world-position-and-exact-car-membership',async()=>{
      const r=await page.evaluate(()=>{
        const A=window.__SOMA_V55__,from=zone,v=from.vehicles.find(v=>v.id==='geo:V52-MC-12-pilot-taxi');
        const p=from.portals.find(p=>p.code==='V52-4D9B0BA7'),plan=A.canCross(from,p.side,{x:p.x,z:p.z},v);
        v.speed=0;Object.assign(camera,{x:v.x,z:v.z});if(!enterVehicle(v))throw Error('Native source taxi entry refused');
        Object.assign(v,{x:p.x,z:p.z,heading:Math.PI});Object.assign(camera,{x:v.x,z:v.z,yaw:Math.PI});
        window.__SOMA_TERRAIN56__.poseCamera();
        const before={zone:from.id,camera:{x:camera.x,y:camera.y,z:camera.z},
          car:{id:v.id,x:v.x,z:v.z,heading:v.heading,condition:v.condition},
          world:A.core.world(from.v50Record,camera),travel:A.progress().travel};
        const ok=A.handoff(from,plan.to,plan.portal),retained=zone.vehicles.find(q=>q.id===state.driving);
        const after={zone:zone.id,camera:{x:camera.x,y:camera.y,z:camera.z},
          car:retained&&{id:retained.id,x:retained.x,z:retained.z,heading:retained.heading,condition:retained.condition},
          world:A.core.world(zone.v50Record,camera),travel:A.progress().travel};
        return{before,ok,after,sameCar:retained===v,sourceMembership:from.vehicles.filter(q=>q===v).length,
          targetMembership:plan.to.vehicles.filter(q=>q===v).length};
      });
      t.report.nativeTransfer=r;assert.equal(r.ok,true);assert.equal(r.sameCar,true);
      assert.equal(r.sourceMembership,0);assert.equal(r.targetMembership,1);assert.equal(r.after.zone,'geo:V52-MC-W01-N03');
      assert.equal(r.after.car.condition,r.before.car.condition);assert.deepEqual(r.after.world,r.before.world);
      assert.equal(r.after.travel.vehicleCrossings,r.before.travel.vehicleCrossings+1);
      assert.equal(r.after.travel.lastCrossing.mode,'vehicle');assert.equal(r.after.travel.lastCrossing.errorMeters,0);
      await shot('native-geographic-taxi-seam');return r;
    });
  }
});
