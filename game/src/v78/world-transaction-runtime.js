/* Local rollback data for the existing metric55 handoff, never a save/cache. */
(function(root){
  'use strict';
  const counts={captured:0,restored:0,fleetCompensations:0,fleetCompensationExceptions:0};
  const spatialKeys=['zone','driving','lastOnFoot','x','z','yaw','pitch'];
  const own=value=>value?Object.getOwnPropertyDescriptors(value):null;
  function restoreOwn(value,descriptors){
    if(!value||!descriptors)return;
    for(const key of Reflect.ownKeys(value))if(!Object.hasOwn(descriptors,key))delete value[key];
    Object.defineProperties(value,descriptors);
  }
  function capture({from,to,car,stats,memory,layer,state,camera,body}){
    const arrays=[];
    for(const host of new Set([from,to]))arrays.push({host,reference:host.vehicles,items:[...(host.vehicles||[])]});
    const entries=[...new Set([from.id,to.id])].map(id=>({id,present:memory.has(id),value:memory.get(id)}));
    const global=layer?.global,codes=global?.drivenSeamCodes,carOwn=own(car),vin=carOwn?.v45Vin?.value;
    const fleetRoot=root.__SOMA_V45__?.state?.(),fleetRecord=typeof vin==='string'?fleetRoot?.fleet?.vehicles?.[vin]:null;
    counts.captured++;
    return {arrays,entries,memory,car,carOwn,stats,statsOwn:own(stats),state,
      statePose:spatialKeys.map(key=>[key,Object.getOwnPropertyDescriptor(state,key)]),camera,cameraOwn:own(camera),global,
      codes:Array.isArray(codes)?{reference:codes,items:[...codes]}:null,drivenSeams:global?.drivenSeams,
      body,classes:{driving:!!body?.classList?.contains('driving'),flying:!!body?.classList?.contains('flying')},
      vin,fleetRoot,fleetRecord,registrationAttempted:false,fleetCompensationAttempted:false,restored:false};
  }
  function restoreBody(t){
    for(const name of ['driving','flying'])t?.body?.classList?.toggle(name,t.classes[name]);
  }
  function restore(t){
    if(!t||t.restored)return false;
    restoreOwn(t.car,t.carOwn);
    for(const {host,reference,items}of t.arrays){
      reference.splice(0,reference.length,...items);host.vehicles=reference;
    }
    for(const entry of t.entries){if(entry.present)t.memory.set(entry.id,entry.value);else t.memory.delete(entry.id);}
    restoreOwn(t.stats,t.statsOwn);restoreOwn(t.camera,t.cameraOwn);
    for(const[key,descriptor]of t.statePose){if(descriptor)Object.defineProperty(t.state,key,descriptor);else delete t.state[key];}
    if(t.codes){t.codes.reference.splice(0,t.codes.reference.length,...t.codes.items);t.global.drivenSeamCodes=t.codes.reference;t.global.drivenSeams=t.drivenSeams;}
    restoreBody(t);t.restored=true;counts.restored++;return true;
  }
  function compensateFleet(t){
    const api=root.__SOMA_V45__;
    if(!t?.restored||!t.registrationAttempted||t.fleetCompensationAttempted||!t.car||!t.fleetRecord||
      t.fleetRecord.id!==t.car.id||api?.state?.()!==t.fleetRoot||t.fleetRoot.fleet.vehicles[t.vin]!==t.fleetRecord||
      typeof api.registerVehicle!=='function')return false;
    t.fleetCompensationAttempted=true;counts.fleetCompensations++;
    try{api.registerVehicle(t.car);return true;}catch{counts.fleetCompensationExceptions++;return false;}
    finally{restoreOwn(t.car,t.carOwn);}
  }
  root.__SOMA_WORLD78__=Object.freeze({capture,restore,restoreBody,compensateFleet,
    snapshot:()=>({version:'0.78.0',owner:'metric55 synchronous handoff',ephemeral:true,newPersistenceDomain:false,
      geographicDataChanged:false,counts:{...counts},scope:'Physical scene rollback; native persistence compensation is best effort.'})});
})(window);
