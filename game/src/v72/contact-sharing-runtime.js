/* Local radio carries fixed, observed evidence. It owns no campaign data,
 * damage, weapons or perception rules: all observations still come from K70.
 * Radio recipients search only; a new personal sighting is required to fire. */
(function(root){
  'use strict';
  const K=root.__SOMA_INFILTRATION70_CORE__;
  if(!K)throw Error('Contact sharing requires infiltration70.');
  const CONFIG=Object.freeze({rangeM:48,maxContacts:128,maxPeers:512,maxChecks:4096});
  const finite=n=>typeof n==='number'&&Number.isFinite(n);
  const copy=v=>JSON.parse(JSON.stringify(v));
  let activeZone=null,zoneId=null,clock=0,serial=0,contacts=new Map(),peers=new Map(),checks=0,dropped=0;
  function current(){return typeof zone==='undefined'?null:zone;}
  function reset(){activeZone=current();zoneId=activeZone?.id??null;clock=0;serial=0;contacts=new Map();peers=new Map();checks=0;dropped=0;}
  function sync(at=clock){
    const z=current();if(z!==activeZone||(z?.id??null)!==zoneId)reset();
    const nextClock=Math.max(clock,finite(at)?at:clock);
    if(nextClock>clock)checks=0;clock=nextClock;
    for(const [id,event]of contacts)if(event.expiresAt<=clock||!present(event.kind,event.object)||faction(event.kind,event.object)!==event.faction)contacts.delete(id);
    for(const [id,p]of peers)if(!present(p.kind,p.object))peers.delete(id);
    return z;
  }
  function present(kind,q){
    if(!q||q.retire||q.disabled||q.hidden||!finite(q.x)||!finite(q.z)||q.health!==undefined&&(!finite(q.health)||q.health<=0))return false;
    const list=kind==='actor'?activeZone?.actors:kind==='vehicle'?activeZone?.vehicles:activeZone?.robots;
    return !!list?.includes(q);
  }
  function faction(kind,q){
    if(typeof q.v33Faction==='string'&&q.v33Faction)return q.v33Faction==='police'?'police':'faction:'+q.v33Faction;
    if(kind==='actor'||kind==='vehicle'||q.kind==='policeDrone')return 'police';
    if(q.kind==='security'||q.v42Camera)return 'security:'+String(activeZone.v42Complex||activeZone.id);
    return 'squad:'+String(q.v33Squad||activeZone.id);
  }
  // Authored horizontal radio envelope in one zone. q.y is deliberately not
  // compared: legacy vehicles mix relative altitude and source terrain NGF.
  function location(q){return [q.x,q.z];}
  function publish(kind,id,q,row){
    // A received searchTarget, a sound and an administrative alert are never
    // retransmitted as a fresh sighting. A visual report samples both points.
    if(!row.canTrackCurrent||!Array.isArray(row.lastKnown)||!row.lastKnown.every(finite)||!present(kind,q))return;
    const ttl=Math.min(K.CONFIG.memorySeconds,row.memoryRemaining);
    if(!(ttl>0))return;
    const event={id:'radio72:'+ ++serial,originId:id,kind,object:q,faction:faction(kind,q),
      position:row.lastKnown.slice(),originPosition:location(q),observedAt:clock,expiresAt:clock+ttl};
    contacts.delete(id);contacts.set(id,event);
    while(contacts.size>CONFIG.maxContacts){contacts.delete(contacts.keys().next().value);dropped++;}
  }
  function exchange(owner,next,entities){
    if(!sync(next?.state?.clock)||!next?.state||!Array.isArray(next.observers)||!(entities instanceof Map))return;
    const live=new Set();
    for(const row of next.observers.slice(0,K.CONFIG.maxObservers)){
      const q=entities.get(row.id),kind=owner==='tactical'?'tactical':row.id.split(':')[0],id=owner+':'+row.id;
      if(!q||!present(kind,q))continue;
      live.add(id);const previous=peers.get(id);
      if(!previous&&peers.size>=CONFIG.maxPeers){dropped++;continue;}
      const p=previous?.object===q?previous:{object:q,kind,owner,received:null};
      peers.set(id,p);publish(kind,id,q,row);
    }
    for(const [id,p]of peers)if(p.owner===owner&&!live.has(id))peers.delete(id);
    for(const [id,event]of contacts)if(event.originId.startsWith(owner+':')&&!live.has(event.originId))contacts.delete(id);
    for(const row of next.observers){
      const id=owner+':'+row.id,p=peers.get(id);if(!p)continue;
      if(row.canTrackCurrent||row.heard){p.received=null;continue;}
      let best=null;
      const target=location(p.object),team=faction(p.kind,p.object);
      for(const event of contacts.values()){
        if(checks>=CONFIG.maxChecks)break;checks++;
        if(event.originId===id||event.faction!==team||!present(event.kind,event.object))continue;
        if(Math.hypot(event.originPosition[0]-target[0],event.originPosition[1]-target[1])>CONFIG.rangeM)continue;
        const remaining=event.expiresAt-clock;
        if(remaining<=0||row.lastKnown&&remaining<=row.memoryRemaining+1e-8)continue;
        if(!best||event.observedAt>best.observedAt||event.observedAt===best.observedAt&&event.id>best.id)best=event;
      }
      if(best){
        const remaining=Math.min(K.CONFIG.memorySeconds,best.expiresAt-clock);
        Object.assign(row,{phase:'search',confirmed:false,suspicion:Math.max(.5,row.suspicion),
          memoryRemaining:remaining,lastKnown:best.position.slice(),searchTarget:best.position.slice(),
          lastSense:'visual',soundId:null,canAttack:false,reason:'radio-last-known'});
        p.received={id:best.id,originId:best.originId,originKind:best.kind,observedAt:best.observedAt,
          expiresAt:best.expiresAt,position:best.position.slice(),originPosition:best.originPosition.slice(),faction:best.faction};
        const track=next.state.tracks.find(item=>item.id===row.id);
        if(track)Object.assign(track,{phase:row.phase,confirmed:false,suspicion:row.suspicion,memoryRemaining:remaining,
          lastKnown:row.lastKnown.slice(),lastSense:'visual',soundId:null});
      }
      if(p.received&&p.received.expiresAt>clock&&row.lastKnown){
        row.contact=copy(p.received);row.reason='radio-last-known';
        // Confirmation remains owned by this observer, including the tick
        // after reception. Neither a radio loop nor search can unlock a shot.
        row.canAttack=false;
      }else p.received=null;
    }
    // Keep K70's HUD consistent with the final transient search outputs.
    if(next.hud)Object.assign(next.hud,{searchingObservers:next.observers.filter(r=>r.phase==='search').length,
      combatObservers:next.observers.filter(r=>r.phase==='combat').length,
      rememberedObservers:next.observers.filter(r=>r.lastKnown).length});
  }
  function cameraContact(q,position){
    if(!sync()||!q?.v42Camera||!present('camera',q)||!position||!finite(position.x)||!finite(position.z)||position.x!==camera.x||position.z!==camera.z||
      state.health<=0||state.recovery?.pending||typeof paused!=='undefined'&&paused)return false;
    // This entry point is called only by the real v42 cone/LOS branch. Recheck
    // its geometry so stale ids and direct calls cannot invent a camera report.
    const dx=position.x-q.x,dz=position.z-q.z,d=Math.hypot(dx,dz),h=q.heading||0;
    if(d>=14||(Math.sin(h)*dx+Math.cos(h)*dz)/Math.max(.01,d)<=.22||
      typeof lineBlocked!=='function'||lineBlocked(q.x,q.z,position.x,position.z)||
      typeof v42VehicleBlocks==='function'&&v42VehicleBlocks(q.x,q.z,position.x,position.z)||
      (root.__SOMA_V42__?.state?.().hacks?.[activeZone.id]?.[q.id]?.blind||0)>0)return false;
    publish('camera','camera:'+String(q.id),q,{canTrackCurrent:true,lastKnown:[position.x,position.z],memoryRemaining:K.CONFIG.memorySeconds});
    return true;
  }
  function snapshot(){sync();return {version:'0.72.0',zoneId,clock,contactCount:contacts.size,peerCount:peers.size,
    checks,dropped,config:{...CONFIG},persistent:false,sourceDataChanged:false,
    contacts:[...contacts.values()].map(({object,...event})=>copy(event))};}
  root.__SOMA_CONTACT_SHARING72__=Object.freeze({version:'0.72.0',CONFIG,exchange,cameraContact,reset,snapshot});
})(window);
