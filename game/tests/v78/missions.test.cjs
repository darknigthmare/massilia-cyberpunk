'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {fixture,plain}=require('./missions-fixture.cjs');
const vehicleKinds=new Set(['road','bridge','garage','police']);
function vehiclePath(c,path){
 for(let i=1;i<path.length;i++)assert(c.WORLD.links.some(link=>((link.a===path[i-1]&&link.b===path[i])||(link.b===path[i-1]&&link.a===path[i]))&&vehicleKinds.has(link.kind||'road')),'Existing vehicle edge '+path[i-1]+' → '+path[i]);
}
test('parent77 escort dialogue loads a pedestrian delivery route and its native Tracer sends the player back to the contact',()=>{
 const c=fixture(true),id='corniche-ambulance-privee',s=c.call(id);assert(c.city.dialogue(s.node));assert.equal(c.city.state().route.targetZone,s.record.targetZone);assert.equal(c.city.state().route.vehicleOnly,false);c.traceButton(id).onclick();assert.equal(c.city.state().route.targetZone,s.record.zone);assert.equal(c.city.state().route.vehicleOnly,false);
});
test('parent77 Port run cannot start because the upper-road endpoint has no vehicle path from its street',()=>{
 const c=fixture(true);c.enter('port-exterior');const before=plain(c.city.state()),links=plain(c.WORLD.links);assert.equal(c.city.startRace('port'),false);assert.deepEqual(plain(c.city.state()),before);assert.deepEqual(plain(c.WORLD.links),links);
});
test('all three escort dialogues use existing vehicle edges and preserve native reward and exact source cleanup',()=>{
 for(const call of fixture().city.calls.filter(call=>call.type==='escort')){
  const c=fixture(),s=c.call(call.id),beforeCredits=c.state.credits;assert(c.city.dialogue(s.node));const r=c.city.state().route;assert.equal(r.targetZone,s.record.targetZone);assert.equal(r.label,call.title+' · acheminement');assert.equal(r.vehicleOnly,true);vehiclePath(c,r.path);assert.match(c.dialogue.lines[0],/trajet véhicule est chargé/);assert.equal(c.state.credits,beforeCredits);
  assert(c.city.resolve(call.id));assert.equal(c.state.credits,beforeCredits+call.reward);assert.equal(c.city.resolve(call.id),false);assert.equal(c.city.state().route.targetZone,null);
 }
});
test('all active call Tracer controls use the current source target and preserve the route mode',()=>{
 for(const call of fixture().city.calls){
  const c=fixture(),s=c.call(call.id);const old=c.manual();c.traceButton(call.id).onclick();const r=c.city.state().route;assert.notDeepEqual(plain(r),old);assert.equal(r.targetZone,call.type==='escort'?s.record.targetZone:s.record.zone);assert.equal(r.vehicleOnly,call.type==='escort');if(call.type==='escort')vehiclePath(c,r.path);assert.equal(c.closed,1);
 }
});
test('a manual GPS survives escort objective interactions, resolution and expiry',()=>{
 for(const ending of ['resolve','expire'])for(const call of fixture().city.calls.filter(call=>call.type==='escort')){
  const c=fixture(),s=c.call(call.id),manual=c.manual();assert(c.city.dialogue(s.node));assert.deepEqual(plain(c.city.state().route),manual);assert.match(c.dialogue.lines[0],/Destination GPS conservée/);assert(c.city[ending](call.id));assert.deepEqual(plain(c.city.state().route),manual);
 }
});
test('legacy pedestrian and new vehicle escort tuples clear only exact source routes',()=>{
 for(const mode of [false,true])for(const mutate of [null,r=>r.label+=' personnel',r=>r.targetZone='station-interiorA']){
  const c=fixture(),call=c.city.calls.find(call=>call.type==='escort'),s=c.call(call.id);assert(c.city.set(s.record.targetZone,call.title+' · acheminement',mode));if(mutate)mutate(c.city.state().route);const before=plain(c.city.state().route);assert(c.city.expire(call.id));if(mutate)assert.deepEqual(plain(c.city.state().route),before);else assert.equal(c.city.state().route.targetZone,null);
 }
});
test('vehicle route refusals and a disabled GPS remain explicit without replacing a manual destination or closing the menu',()=>{
 for(const disabled of [false,true]){
  const c=fixture(),id='corniche-ambulance-privee',s=c.call(id);c.enter('station-interiorA');const before=c.manual();if(disabled)c.city.state().settings.routePlanner=false;c.traceButton(id).onclick();assert.deepEqual(plain(c.city.state().route),before);assert.equal(c.closed,undefined);assert.match(c.lastAnnouncement,disabled?/désactivé/:/Aucune liaison routière/);assert.equal(s.record.status,'active');
 }
});
test('all eight runs now use existing vehicle routes; the other seven endpoint choices and paths remain unchanged',()=>{
 const old=fixture(true),fixed=fixture(),links=plain(fixed.WORLD.links);let started=0;
 for(const run of fixed.city.races){
  const before=fixture(true),after=fixture();before.enter(run.district+'-exterior');after.enter(run.district+'-exterior');assert(after.city.startRace(run.district));const active=after.city.state().raceActive;assert.equal(active.path[0],run.district+'-exterior');vehiclePath(after,active.path);assert.equal(after.city.state().route.vehicleOnly,true);assert.equal(after.city.state().races[run.id].attempts,1);
  if(run.district==='port'){assert.equal(before.city.startRace(run.district),false);assert.equal(active.path.at(-1),'corniche-exterior');}
  else{assert(before.city.startRace(run.district));assert.deepEqual(plain(active.path),plain(before.city.state().raceActive.path));assert.equal(after.city.targets[run.district],before.city.targets[run.district]);}
  const credits=after.state.credits;after.state.driving='fixture-original-driven-car';for(const id of active.path.slice(1)){after.zone=after.WORLD.zones[id];after.city.raceChanged(id);}assert.equal(after.city.state().races[run.id].wins,1);assert.equal(after.state.credits,credits+run.reward);assert.equal(after.city.state().raceActive,null);started++;
 }
 assert.equal(started,8);assert.deepEqual(plain(fixed.WORLD.links),links);assert.equal(Object.keys(fixed.WORLD.zones).length,Object.keys(old.WORLD.zones).length);
});
test('an unreachable run gives feedback and leaves saved course, stats and GPS untouched',()=>{
 const c=fixture();c.enter('station-interiorA');const manual=c.manual(),before=plain(c.city.state());assert.equal(c.city.startRace('port'),false);assert.deepEqual(plain(c.city.state()),before);assert.deepEqual(plain(c.city.state().route),manual);assert.match(c.lastAnnouncement,/Run indisponible/);
});
