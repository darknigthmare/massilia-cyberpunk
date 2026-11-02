/* The native-pilot entry owner keeps its original source-road centres,
 * relocation notice and refusal. No geometry, position cache or save is added. */
(function(root){
  'use strict';
  const stats={checks:0,standingStops:0,vehicleStops:0};
  function vehicleClear(target,x,z){
    const K=root.__SOMA_V57_CORE__,seams=root.__SOMA_V55__;
    if(!K?.circleFootprint||!K?.obb)return false;
    const hosts=new Set([target]),near=new Map();
    // Inspect live neighboring bodies without constructing another scene.
    // Their coordinates belong to their own source cell, including diagonals.
    for(const side of ['N','S','E','W']){
      if(side==='N'&&z> -target.h/2+12||side==='S'&&z<target.h/2-12||side==='W'&&x> -target.w/2+12||side==='E'&&x<target.w/2-12)continue;
      const n=seams?.neighbor?.(target,side);near.set(side,n);if(n?.static)hosts.add(n);
    }
    for(const vertical of ['N','S'])for(const horizontal of ['E','W']){
      if(!near.has(vertical)||!near.has(horizontal))continue;
      const a=near.get(vertical),b=near.get(horizontal),diagonal=a&&seams.neighbor(a,horizontal)||b&&seams.neighbor(b,vertical);
      if(diagonal?.static)hosts.add(diagonal);
    }
    for(const host of hosts){
      const p=host===target?{x,z}:seams.core.transfer(target.v50Record,host.v50Record,{x,z});
      for(const v of host.vehicles||[]){
        if(v.hidden||isFlyingVehicleKind(v.kind)||isWaterVehicleKind(v.kind))continue;
        const spec=vehicleSpec(v);
        if(K.circleFootprint([p.x,p.z],.38,K.obb(v.x,v.z,spec.width,spec.length,v.heading||0)))return false;
      }
    }
    return true;
  }
  function valid(target,x,z){
    stats.checks++;
    const T=root.__SOMA_TERRAIN56__,P=root.__SOMA_TERRAIN75__,C=root.__SOMA_CLEARANCE60__;
    if(!P?.active()||!T?.activeFor(target)||![x,z].every(Number.isFinite)||!P.entrySupported(target,x,z))return false;
    // Entering/continuing requires a standing body even when called inside a
    // crouched movement frame. Restore the caller's body context on return.
    if(!C?.withBody||C.withBody(C.core.STANDING,()=>blocked(target,x,z,.38))){stats.standingStops++;return false;}
    if(!vehicleClear(target,x,z)){stats.vehicleStops++;return false;}
    return true;
  }
  root.__SOMA_MOBILITY76__=Object.freeze({ready:true,valid,snapshot:()=>({version:'0.76.0',ephemeral:true,
    nativePilotOnly:true,positionOwner:'terrain56 entry and terrain75 relocation/refusal',
    sourceRoadCandidates:'unchanged segment centres',bodyRadiusM:.38,supportRadiusM:.4,slopeLimit:.95,
    stats:{...stats},newGeographicCells:0})});
  // The cached pilot can have reconciled its restored pose before this module
  // was parsed. Reuse its owner once for the current cell, never preload cells.
  const pilot=root.__SOMA_TERRAIN75__;
  if(pilot?.ready&&pilot.active())pilot.changed();
})(window);
