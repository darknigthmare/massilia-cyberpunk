/* Recharge27 owns ammunition; this adapter owns only the live action identity. */
(function(root){
  'use strict';
  let pending=null;
  const weapon=()=>WEAPONS[state.weapon];
  function cancel(){
    const active=!!pending||reloadLeft>0;
    pending=null;reloadLeft=0;v27ReloadWeaponId=null;
    return active;
  }
  function compatible(){
    return !!pending&&pending.core===state&&pending.ammo===state.ammo&&pending.record===state.ammo?.[pending.id]&&
      pending.scene===zone&&pending.zoneId===zone?.id&&weapon()?.id===pending.id&&v27ReloadWeaponId===pending.id&&
      state.health>0&&!state.recovery?.pending&&!state.driving&&!v27IsCyber();
  }
  function maintain(){
    if(pending&&(!compatible()||reloadLeft<=0))cancel();
    else if(!pending&&reloadLeft>0)cancel();
  }
  const ownerReload=reload;
  reload=function(...args){
    maintain();
    if(paused||!zone||state.health<=0||state.recovery?.pending||state.driving)return false;
    const before=reloadLeft,result=ownerReload(...args);
    if(reloadLeft>before&&reloadLeft>0&&v27ReloadWeaponId){
      const id=v27ReloadWeaponId;
      pending={core:state,ammo:state.ammo,record:state.ammo[id],scene:zone,zoneId:zone.id,id};
    }
    return result;
  };
  const ownerFinish=finishReload;
  finishReload=function(...args){
    // The native timer reaches zero before calling this function. Do not use
    // maintain() here: validate identity, then let27 transfer the actual rounds.
    if(!compatible()){cancel();return false;}
    if(reloadLeft>0)return false;
    pending=null;
    const result=ownerFinish(...args);
    reloadLeft=0;
    return result;
  };
  const ownerUpdate=update;
  update=function(...args){maintain();return ownerUpdate(...args);};
  const ownerEnter=enterZone;
  enterZone=function(...args){
    const scene=zone,id=zone?.id,result=ownerEnter(...args);
    if(result&&(scene!==zone||id!==zone?.id))cancel();
    return result;
  };
  function snapshot(){
    const active=reloadLeft>0&&compatible();
    return {active,weaponId:active?pending.id:null,remaining:active?reloadLeft:0};
  }
  root.__SOMA_RELOAD77__={version:'0.77.0',cancel,reset:cancel,maintain,snapshot};
})(window);
