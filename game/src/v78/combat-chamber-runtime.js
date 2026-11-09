/* The material30 owner keeps its native timer, wear and jammed record. */
(function(root){
  'use strict';
  function compatible(task){
    return !!task&&task.core===state&&task.scene===zone&&task.zoneId===zone?.id&&
      WEAPONS[state.weapon]?.name===task.weapon&&S.durability[task.weapon]===task.record&&task.record.jammed===true&&
      state.health>0&&!state.recovery?.pending&&!state.driving&&!v27IsCyber();
  }
  function cancel(){
    const active=!!materialJamTask;
    materialJamTask=null;
    return active;
  }
  function maintain(){
    if(materialJamTask&&!compatible(materialJamTask))cancel();
  }
  function snapshot(){
    const active=compatible(materialJamTask);
    return {active,weaponName:active?materialJamTask.weapon:null,
      remaining:active?Math.max(0,materialJamTask.left):0,ephemeral:true};
  }
  // These existing selection APIs own the actual weapon change. A failed or
  // unchanged selection does not interrupt the native chamber action.
  for(const action of ['cycle','slot']){
    const owner=action==='cycle'?cycleWeapon:v29SelectSlot;
    const guarded=function(...args){
      const before=state.weapon,result=owner(...args);
      if(state.weapon!==before)cancel();
      return result;
    };
    if(action==='cycle')cycleWeapon=guarded;else v29SelectSlot=guarded;
  }
  const ownerEnter=enterZone;
  enterZone=function(...args){
    const scene=zone,id=zone?.id,result=ownerEnter(...args);
    if(scene!==zone||id!==zone?.id)cancel();
    return result;
  };
  root.__SOMA_CHAMBER78__=Object.freeze({version:'0.78.0',cancel,reset:cancel,maintain,snapshot});
})(window);
