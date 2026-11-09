'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {context,sources}=require('./combat-fixture.cjs');
const ammo=c=>JSON.stringify(c.state.ammo);

test('before proof: native arsenal changes the active gun but completes the previous reload27',()=>{
 const c=context(true);assert.equal(c.start(),1.1);c.paused=true;c.arsenalClick(1);
 assert.equal(c.state.weapon,1);assert.equal(c.reloadLeft,1.1);assert.equal(c.v27ReloadWeaponId,'pistol');
 c.paused=false;c.advance();assert.equal(c.state.ammo.pistol.mag,12);assert.equal(c.state.ammo.pistol.reserve,9);
});

test('arsenal cancels only a real weapon change; owner27 still transfers exactly once for a normal reload',()=>{
 const c=context();const before=ammo(c);c.start();c.paused=true;c.arsenalClick(1);
 assert.equal(c.api.snapshot().active,false);assert.equal(c.reloadLeft,0);assert.equal(c.v27ReloadWeaponId,null);
 c.paused=false;c.advance();assert.equal(ammo(c),before);c.finishReload();assert.equal(ammo(c),before);
 const d=context();d.start();d.paused=true;d.arsenalClick(0);assert.equal(d.api.snapshot().active,true);
 d.paused=false;d.advance(.5);assert(Math.abs(d.reloadLeft-.6)<1e-8);d.advance(.61);
 assert.equal(d.state.ammo.pistol.mag,12);assert.equal(d.state.ammo.pistol.reserve,9);
 const committed=ammo(d);d.finishReload();d.advance();assert.equal(ammo(d),committed);assert.equal(d.reloadLeft,0);
});

test('before proof and repair: depositing the active loadout weapon invalidates its live reload',()=>{
 const old=context(true);old.start();assert.equal(old.v29EquipWeapon('pistol').ok,true);old.advance();assert.equal(old.state.ammo.pistol.mag,12);
 const c=context(),before=ammo(c);c.start();assert.equal(c.v29EquipWeapon('pistol').ok,true);
 assert.equal(c.state.weapon,1);assert.equal(c.api.snapshot().active,false);c.advance();assert.equal(ammo(c),before);
 const d=context();d.start();assert.equal(d.v29EquipWeapon('rifle').ok,true);assert.equal(d.api.snapshot().active,true);
});

test('actual old Digit5 handler cancels; native carried slots and cycling keep their cancellation contract',()=>{
 for(const action of [c=>{c.controls();c.events.keydown[0]({code:'Digit5',repeat:false,preventDefault(){}});},
  c=>c.v29SelectSlot(1),c=>c.cycleWeapon(1)]){
  const c=context(),before=ammo(c);c.start();action(c);assert.equal(c.reloadLeft,0);assert.equal(c.api.snapshot().active,false);c.advance();assert.equal(ammo(c),before);
 }
});

test('pause and repeated reload input do not consume rounds, restart the clock or cancel a valid action',()=>{
 const c=context(),before=ammo(c);c.start();c.finishReload();assert.equal(ammo(c),before);assert.equal(c.api.snapshot().active,true);
 c.advance(.4);const left=c.reloadLeft;c.reload();assert.equal(c.reloadLeft,left);
 c.paused=true;c.api.maintain();c.advance(99);c.reload();assert.equal(c.reloadLeft,left);assert.equal(ammo(c),before);
 c.paused=false;c.advance(left+.01);assert.equal(c.state.ammo.pistol.mag,12);assert.equal(c.state.ammo.pistol.reserve,9);
});

test('completion refuses stale state, ammunition roots, records, scenes, weapons and unavailable bodies',()=>{
 const changes=[c=>{c.state={...c.state};},c=>{c.state.ammo={...c.state.ammo};},c=>{c.state.ammo.pistol={...c.state.ammo.pistol};},
  c=>{c.zone={...c.zone};},c=>{c.zone.id='changed';},c=>{c.state.weapon=1;},c=>{c.state.health=0;},
  c=>{c.state.recovery.pending=true;},c=>{c.state.driving='car';},c=>{c.cyber=true;}];
 for(const change of changes){
  const c=context();c.start();change(c);const before=ammo(c);c.reloadLeft=-.1;c.finishReload();assert.equal(ammo(c),before);assert.equal(c.api.snapshot().active,false);
  const d=context();d.start();change(d);d.api.maintain();assert.equal(d.reloadLeft,0);assert.equal(d.v27ReloadWeaponId,null);
 }
});

test('successful scene transition and import reset cancel without creating ammunition or a persistent domain',()=>{
 const c=context(),before=ammo(c);c.start();assert.equal(c.enterZone('other'),true);assert.equal(c.reloadLeft,0);c.advance();assert.equal(ammo(c),before);
 const d=context();d.start();assert.equal(d.enterZone('missing'),false);assert.equal(d.api.snapshot().active,true);
 d.api.reset();assert.equal(d.api.snapshot().active,false);assert.equal(d.v27ReloadWeaponId,null);assert(!Object.hasOwn(d.state,'v77'));
});

test('native melee, empty reserve and full magazines do not manufacture a reload transaction',()=>{
 for(const setup of [c=>{c.state.weapon=2;},c=>{c.state.ammo.pistol.reserve=0;},c=>{c.state.ammo.pistol.mag=12;}]){
  const c=context();setup(c);const before=ammo(c);c.start();assert.equal(c.api.snapshot().active,false);c.finishReload();assert.equal(ammo(c),before);
 }
 assert(sources.after.loop.startsWith('function loop(t){window.__SOMA_RELOAD77__?.maintain();'));
});
