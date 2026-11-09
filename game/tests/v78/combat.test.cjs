'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {context,sources}=require('./combat-fixture.cjs');
test('native30 reproduces obsolete chamber clearing after a scene change;78 cancels it',()=>{
 const old=context(true);old.start();old.enterZone('other');old.advance();assert.equal(old.record().jammed,false);assert.equal(old.record().condition,79.4);
 const c=context();c.start();c.enterZone('other');assert.equal(c.api.snapshot().active,false);c.advance();assert.equal(c.record().jammed,true);assert.equal(c.record().condition,80);
});
test('valid native chamber action retains duration, one wear debit and native completion',()=>{
 const c=context();const ammo=JSON.stringify(c.state.ammo);c.start();assert.equal(c.reloadLeft,0);assert(c.api.snapshot().active);c.advance(8);assert.equal(c.record().jammed,true);c.advance(2);assert.equal(c.record().jammed,false);assert.equal(c.record().condition,79.4);assert.equal(c.api.snapshot().active,false);assert.equal(c.saveCalls,1);c.advance();assert.equal(c.record().condition,79.4);assert.equal(c.saveCalls,1);assert.equal(JSON.stringify(c.state.ammo),ammo);
});
test('ordinary pause retains remaining chamber time and resumes the same native action',()=>{
 const c=context();c.start();c.advance(3);c.paused=true;const remaining=c.api.snapshot().remaining;c.advance(20);c.api.maintain();assert.equal(c.api.snapshot().remaining,remaining);assert.equal(c.record().jammed,true);c.paused=false;c.advance(7);assert.equal(c.record().jammed,false);
});
test('core, scene, weapon record and incompatible body states invalidate without material writes',()=>{
 for(const change of [c=>{c.state={...c.state};},c=>{c.zone={...c.zone};},c=>{c.zone.id='changed';},c=>{c.S.durability[c.WEAPONS[0].name]={...c.record()};},c=>{c.state.health=0;},c=>{c.state.recovery.pending=true;},c=>{c.state.driving='vehicle';},c=>{c.cyber=true;}]){
  const c=context();c.start();const record=c.record();c.paused=true;change(c);c.api.maintain();assert.equal(c.api.snapshot().active,false);c.paused=false;c.advance();assert.equal(record.jammed,true);assert.equal(record.condition,80);
 }
});
test('arsenal, slot and cycling cancel immediately, including away-and-back during pause',()=>{
 for(const select of [c=>c.arsenalClick(1),c=>c.v29SelectSlot(1),c=>c.cycleWeapon(1)]){
  const c=context();c.start();c.paused=true;select(c);assert.equal(c.api.snapshot().active,false);c.arsenalClick(0);c.paused=false;c.advance();assert.equal(c.record().jammed,true);assert.equal(c.record().condition,80);
 }
});
test('unchanged and refused selections or scene entry preserve a compatible action',()=>{
 const c=context();c.start();c.paused=true;c.arsenalClick(0);assert(c.api.snapshot().active);assert.equal(c.v29SelectSlot(99),false);assert(c.api.snapshot().active);assert.equal(c.enterZone('missing'),false);assert(c.api.snapshot().active);c.paused=false;c.advance();assert.equal(c.record().jammed,false);
});
test('deposit of the active weapon cancels while an unrelated loadout removal preserves',()=>{
 const c=context();c.start();c.paused=true;assert(c.v29EquipWeapon('pistol').ok);assert.equal(c.api.snapshot().active,false);c.advance();assert.equal(c.record().jammed,true);
 const other=context();other.start();assert(other.v29EquipWeapon('rifle').ok);assert(other.api.snapshot().active);other.advance();assert.equal(other.record().jammed,false);
});
test('import reset and a repair resolving the jam cancel obsolete work without extra wear',()=>{
 const c=context();c.start();c.api.reset();c.advance();assert.equal(c.record().jammed,true);assert.equal(c.record().condition,80);
 const repaired=context();repaired.start();repaired.record().jammed=false;repaired.record().condition=95;repaired.api.maintain();assert.equal(repaired.api.snapshot().active,false);repaired.advance();assert.equal(repaired.record().condition,95);
});
test('new clearing refuses an absent scene, death and pending recovery',()=>{
 for(const change of [c=>{c.zone=null;},c=>{c.state.health=0;},c=>{c.state.recovery.pending=true;}]){
  const c=context();c.record().jammed=true;change(c);assert.equal(c.clearJam(),false);assert.equal(c.api.snapshot().active,false);assert.equal(c.record().condition,80);
 }
});
test('native27 ammunition transfer and existing77 reload identity remain unchanged',()=>{
 assert.equal(sources.before.reload,sources.after.reload);assert.equal(sources.before.finish,sources.after.finish);assert.equal(sources.before.reload77,sources.after.reload77);
 const c=context();c.reload();assert(c.__SOMA_RELOAD77__.snapshot().active);assert.equal(c.api.snapshot().active,false);c.advance(20);assert.equal(c.state.ammo.pistol.mag,12);assert.equal(c.state.ammo.pistol.reserve,9);assert.equal(c.__SOMA_RELOAD77__.snapshot().active,false);
});
test('the real64 transfer refusal sees only a live compatible chamber action',()=>{
 const vm=require('node:vm');
 for(const before of [true,false]){
  const c=context(before);c.E=()=>({summary:()=>({busy:false})});c.api64=()=>({isChanneling:()=>false,state:()=>({raceActive:false})});
  vm.runInContext('let ready=true,busy=false;const api=globalThis.api64;'+sources[before?'before':'after'].refusal64+';globalThis.refusal64=refusal;',c);
  c.start();c.paused=true;
  if(before)assert.equal(c.refusal64(),null);
  else{assert.match(c.refusal64(),/Terminez l’action/);c.api.cancel();assert.equal(c.refusal64(),null);}
 }
});
