/* Ground vehicle contact adapter. The v24 mechanics, v45 fleet, v55 seams,
 * v56 ground and v57 oriented collision owners remain authoritative. */
(function(root){
  'use strict';
  const LIMITS=Object.freeze({cornerStepM:.04,maxSamples:128,maxSlope:.7});
  const stats={pathChecks:0,sweepSamples:0,collisionStops:0,slopeStops:0,missingGroundStops:0,invalidPaths:0};
  const terrestrial=v=>!!v&&!isFlyingVehicleKind(v.kind)&&!isWaterVehicleKind(v.kind);
  function pathBlocked(v,x,z,heading,previousHeading){
    const T=root.__SOMA_TERRAIN56__,K=root.__SOMA_V57_CORE__;
    if(!terrestrial(v)||!T?.activeFor?.(zone)||!K)return vehicleBlockedAt(v,x,z,heading);
    stats.pathChecks++;
    if(![v.x,v.z,x,z,heading,previousHeading].every(Number.isFinite)){stats.invalidPaths++;return true;}
    const spec=vehicleSpec(v),angle=Math.atan2(Math.sin(heading-previousHeading),Math.cos(heading-previousHeading));
    // A centre-only step does not bound a turning bumper. Bound the motion of
    // every point of both existing v57 contact bodies. Only the sampling
    // budget uses the larger vehicle-to-vehicle body; neither body changes.
    const radius=Math.hypot(spec.width*.5+.09,spec.length*.5+.09);
    const count=Math.max(1,Math.ceil((Math.hypot(x-v.x,z-v.z)+Math.abs(angle)*radius)/LIMITS.cornerStepM));
    if(count>LIMITS.maxSamples){stats.invalidPaths++;return true;}
    for(let i=1;i<=count;i++){
      stats.sweepSamples++;
      const t=i/count,px=v.x+(x-v.x)*t,pz=v.z+(z-v.z)*t,h=previousHeading+angle*t;
      if(vehicleBlockedAt(v,px,pz,h)){stats.collisionStops++;return true;}
      const poly=K.obb(px,pz,spec.width*.92,spec.length*.92,h,.03);
      const support=[[px,pz],...poly,...poly.map((p,j)=>[(p[0]+poly[(j+1)%4][0])/2,(p[1]+poly[(j+1)%4][1])/2])];
      // v57's edge-average rise can hide a steep patch below one axle. Ask
      // the active ground owner at the same nine supports, at its own grid
      // resolution. Missing source ground never becomes an invented support.
      for(const [sx,sz] of support){
        const ground=T.ground(zone,sx,sz),s=T.slope(zone,sx,sz);
        if(!Number.isFinite(ground)||!s||![s.e,s.south].every(Number.isFinite)){stats.missingGroundStops++;return true;}
        if(Math.hypot(s.e,s.south)>LIMITS.maxSlope+1e-7){stats.slopeStops++;return true;}
      }
    }
    return false;
  }
  root.__SOMA_VEHICLES75__=Object.freeze({ready:true,pathBlocked,
    snapshot:()=>({version:'0.75.0',ephemeral:true,limits:{...LIMITS},stats:{...stats},newVehicleSpecs:0,newGeographicCells:0})});
})(window);
