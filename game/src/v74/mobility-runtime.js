/* Ground movement and local dismounts. The existing terrain, collision,
 * stance, vehicle, seam and save owners remain authoritative. */
(function(root){
  'use strict';
  const LIMITS=Object.freeze({footStepM:.12,footSlope:.95,exitRadiusM:6,exitSlope:.7});
  const stats={footSubsteps:0,slopeStops:0,collisionStops:0,vehicleStops:0,missingGroundStops:0,exitChecks:0,exitRefusals:0};
  const terrain=()=>root.__SOMA_TERRAIN56__;
  const real=z=>terrain()?.activeFor?.(z)===true;
  function ground(z,x,zz){const h=terrain()?.ground?.(z,x,zz);return Number.isFinite(h)?h:null;}
  function supported(z,x,zz,r,limit){
    for(const [dx,dz] of [[0,0],[r,0],[-r,0],[0,r],[0,-r]])if(ground(z,x+dx,zz+dz)===null)return false;
    const s=terrain()?.slope?.(z,x,zz);
    return !!s&&Number.isFinite(s.e)&&Number.isFinite(s.south)&&Math.hypot(s.e,s.south)<=limit+1e-7;
  }
  function vehicleClear(x,zz,ignore=null){
    const K=root.__SOMA_V57_CORE__;
    if(!K?.circleFootprint||!K?.obb)return pedestrianVehicleClear(x,zz,ignore,.38);
    const hosts=new Set([zone]),seams=root.__SOMA_V55__,near=new Map();
    // Only already built adjacent cells can have live vehicles. Keep the
    // existing seam owner and its coordinate transform, with no new loading.
    for(const side of ['N','S','E','W']){
      if(side==='N'&&zz> -zone.h/2+12||side==='S'&&zz<zone.h/2-12||side==='W'&&x> -zone.w/2+12||side==='E'&&x<zone.w/2-12)continue;
      const n=seams?.neighbor?.(zone,side);near.set(side,n);if(n?.static)hosts.add(n);
    }
    // A body owned by a diagonal cell can protrude across the shared corner
    // before the pedestrian footprint crosses either edge. Compose the real
    // metric neighbor lookup; querying it never constructs an adjacent scene.
    for(const vertical of ['N','S'])for(const horizontal of ['E','W']){
      if(!near.has(vertical)||!near.has(horizontal))continue;
      const a=near.get(vertical),b=near.get(horizontal);
      const diagonal=a&&seams.neighbor(a,horizontal)||b&&seams.neighbor(b,vertical);
      if(diagonal?.static)hosts.add(diagonal);
    }
    for(const host of hosts){
      const p=host===zone?{x,z:zz}:seams.core.transfer(zone.v50Record,host.v50Record,{x,z:zz});
      for(const v of host.vehicles||[]){
        if(v.id===ignore||v.hidden||isFlyingVehicleKind(v.kind)||isWaterVehicleKind(v.kind))continue;
        const s=vehicleSpec(v);
        if(K.circleFootprint([p.x,p.z],.38,K.obb(v.x,v.z,s.width,s.length,v.heading||0)))return false;
      }
    }
    return true;
  }
  function walk(dx,dz){
    if(!real(zone)||state.driving||paused||![dx,dz,camera.x,camera.z].every(Number.isFinite))return false;
    const count=Math.max(1,Math.ceil(Math.hypot(dx,dz)/LIMITS.footStepM));
    if(count>128)return false;
    const sx=dx/count,sz=dz/count;
    function advance(x,zz){
      const before=ground(zone,camera.x,camera.z),after=ground(zone,x,zz),distance=Math.hypot(x-camera.x,zz-camera.z);
      if(before===null||after===null){stats.missingGroundStops++;return false;}
      if(!supported(zone,x,zz,.38,LIMITS.footSlope)||distance>1e-8&&Math.abs(after-before)>distance*LIMITS.footSlope+1e-7){stats.slopeStops++;return false;}
      if(blocked(zone,x,zz,.38)){stats.collisionStops++;return false;}
      if(!vehicleClear(x,zz)){stats.vehicleStops++;return false;}
      camera.x=x;camera.z=zz;return true;
    }
    for(let i=0;i<count;i++){
      stats.footSubsteps++;
      // Preserve the original controller's sliding along an obstacle.
      if(Math.abs(sx)>1e-10)advance(camera.x+sx,camera.z);
      if(Math.abs(sz)>1e-10)advance(camera.x,camera.z+sz);
    }
    return true;
  }
  function exitPoint(v){
    if(!real(zone)||!v||isFlyingVehicleKind(v.kind)||isWaterVehicleKind(v.kind))return null;
    const spec=vehicleSpec(v),h=Number(v.heading)||0,f={x:Math.sin(h),z:Math.cos(h)},r={x:Math.cos(h),z:-Math.sin(h)};
    const side=spec.exitOffset+spec.width*.55,long=spec.length*.55+1;
    const raw=[[r.x*side,r.z*side],[-r.x*side,-r.z*side],[-f.x*long,-f.z*long],[f.x*long,f.z*long]],candidates=[];
    for(let ring=0;ring<4;ring++)for(let i=0;i<raw.length;i++){
      const mul=1+ring*.58,x=v.x+raw[i][0]*mul,z=v.z+raw[i][1]*mul,distance=Math.hypot(x-v.x,z-v.z);
      if(distance>LIMITS.exitRadiusM)continue;
      candidates.push({x,z,distance,score:(onSidewalk(zone,x,z,.3)?0:onRoad(zone,x,z,.05)?4:1)+ring*.4+i*.03});
    }
    candidates.sort((a,b)=>a.score-b.score);
    const clearance=root.__SOMA_CLEARANCE60__,standing=clearance?.core?.STANDING||1.8;
    const check=p=>{
      stats.exitChecks++;
      if(!supported(zone,p.x,p.z,.38,LIMITS.exitSlope)||blocked(zone,p.x,p.z,.38)||!vehicleClear(p.x,p.z,v.id))return false;
      const count=Math.max(1,Math.ceil(p.distance/.2));
      // Test the route out of the body too: a free destination beyond a wall
      // is not an available door. Ignore only the vehicle being left.
      for(let i=1;i<=count;i++){
        const x=v.x+(p.x-v.x)*i/count,z=v.z+(p.z-v.z)*i/count;
        if(!supported(zone,x,z,.38,LIMITS.exitSlope)||blocked(zone,x,z,.38)||!vehicleClear(x,z,v.id))return false;
      }
      return true;
    };
    const find=()=>candidates.find(check)||null;
    const p=clearance?.withBody?clearance.withBody(standing,find):find();
    if(!p){stats.exitRefusals++;return null;}
    return {x:p.x,z:p.z};
  }
  root.__SOMA_MOBILITY74__=Object.freeze({ready:true,walk,exitPoint,
    snapshot:()=>({version:'0.74.0',ephemeral:true,limits:{...LIMITS},stats:{...stats},newGeographicCells:0})});
})(window);
