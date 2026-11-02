'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {setup,owners}=require('./entry-fixture.cjs');
const vm=require('node:vm');
const car=(id,x,z,kind='car')=>({id,x,z,heading:Math.PI/4,kind});
const plain=x=>JSON.parse(JSON.stringify(x));
test('actual75 entry accepts an original parked-body overlap;76 falls back to another existing source centre',()=>{
 for(const parent of [true,false]){const {c,target}=setup({parent});target.vehicles=[car('parked',0,0)];target.roads=[{x:0,z:0,angle:.1},{x:8,z:3,angle:.6}];
  assert.equal(c.enterZone('real',null,{x:100,z:100,yaw:.9}),true);
  assert.equal(c.calls[0].pose.x,parent?0:8);assert.equal(c.calls[0].pose.z,parent?0:3);assert.equal(c.relocations,1);assert.equal(c.entered,1);
  if(!parent)assert.ok(c.__SOMA_MOBILITY76__.snapshot().stats.vehicleStops>0);
 }
});
test('restored native positions require standing clearance even inside a crouched movement context',()=>{
 const {c,target}=setup();target.colliders=[{x0:-2,x1:2,z0:-2,z1:2,tag:'canopy',v60Volume:{bottom:21.4,top:25}}];target.roads=[{x:8,z:3,angle:.6}];c.bodyHeight=1.15;
 assert.equal(c.blocked(target,0,0,.38),false,'the actual60 interval admits the crouched body');
 assert.equal(c.enterZone('real',null,{x:0,z:0,yaw:.9}),true);assert.equal(c.calls[0].pose.x,8);assert.equal(c.bodyHeight,1.15);
});
test('when every source centre is occupied, native entry refuses before any downstream pose, driving or lastOnFoot mutation',()=>{
 const {c,target}=setup();target.vehicles=[car('parked',0,0)];target.roads=[{x:0,z:0,angle:0}];
 const before=plain({state:c.state,camera:c.camera});assert.equal(c.enterZone('real',null,{x:0,z:0}),false);
 assert.deepEqual(plain({state:c.state,camera:c.camera}),before);assert.equal(c.calls.length,0);assert.equal(c.refusals,1);assert.equal(c.relocations,0);
});
test('native validity uses the target source cell and already built neighboring vehicle owners in exact metric coordinates',()=>{
 const {c,target}=setup(),sha='a'.repeat(64);target.v50Record.sourceReceipt={sha256:sha};target.vehicles=[];
 const east={id:'east',static:true,v50Record:{boundsL93:[20,-20,60,20],sourceReceipt:{sha256:sha}},vehicles:[car('neighbor',-20.2,0)]};
 let loads=0,queries=0;c.__SOMA_V55__={core:c.__SOMA_V55_CORE__,neighbor:(z,side)=>{queries++;return z===target&&side==='E'?east:null;}};c.buildZone=()=>{loads++;throw Error('must not load a neighbor');};
 assert.equal(c.__SOMA_MOBILITY76__.valid(target,18.4,0),false);assert.ok(queries>0);assert.equal(loads,0);
 east.static=false;assert.equal(c.__SOMA_MOBILITY76__.valid(target,18.4,0),true);assert.equal(loads,0);
});
test('a diagonal-cell body is checked through actual55 transfer, without creating a scene',()=>{
 const {c,target}=setup();const north={id:'north',static:true,v50Record:{boundsL93:[-20,20,20,60]},vehicles:[]},east={id:'east',static:true,v50Record:{boundsL93:[20,-20,60,20]},vehicles:[]},ne={id:'ne',static:true,v50Record:{boundsL93:[20,20,60,60]},vehicles:[{...car('diagonal',-19.8,19.8),heading:-Math.PI/4}]};
 c.__SOMA_V55__={core:c.__SOMA_V55_CORE__,neighbor:(z,s)=>z===target?(s==='N'?north:s==='E'?east:null):z===north&&s==='E'?ne:null};
 assert.equal(c.__SOMA_MOBILITY76__.valid(target,18.8,-18.8),false);ne.vehicles[0].hidden=true;assert.equal(c.__SOMA_MOBILITY76__.valid(target,18.8,-18.8),true);
});
test('missing terrain, excessive native slope, building collisions and invalid coordinates are refused',()=>{
 const {c,target}=setup(),P=c.__SOMA_MOBILITY76__;assert.equal(P.valid(target,0,0),true);
 c.ground=()=>null;assert.equal(P.valid(target,0,0),false);c.ground=()=>20;c.slope=()=>({e:.96,south:0});assert.equal(P.valid(target,0,0),false);
 c.slope=()=>({e:.4,south:.5});assert.equal(P.valid(target,0,0),true);target.colliders=[{x0:-1,x1:1,z0:-1,z1:1,tag:'source-building'}];assert.equal(P.valid(target,0,0),false);
 assert.equal(P.valid(target,NaN,0),false);assert.equal(P.valid(target,Infinity,0),false);
});
test('hidden, flying and water bodies retain the existing74 foot collision semantics',()=>{
 const {c,target}=setup(),P=c.__SOMA_MOBILITY76__;target.vehicles=[car('hidden',0,0),car('air',0,0,'air'),car('boat',0,0,'boat')];target.vehicles[0].hidden=true;
 assert.equal(P.valid(target,0,0),true);
});
test('legacy25m paths match the actual75 owner, including crouched clearance and the existing vehicle policy',()=>{
 for(const parent of [true,false]){const {c,target}=setup({parent,native:false});target.vehicles=[car('parked',0,0)];target.roads=[{x:0,z:0,angle:.2}];
  target.colliders=[{x0:-2,x1:2,z0:-2,z1:2,tag:'canopy',v60Volume:{bottom:21.4,top:25}}];c.bodyHeight=1.15;
  assert.equal(c.enterZone('real',null,{x:100,z:100}),true);assert.equal(c.calls[0].pose.x,0);assert.equal(c.calls[0].pose.z,0);
  assert.equal(c.relocations,0);assert.equal(c.__SOMA_MOBILITY76__.snapshot().stats.checks,0);assert.equal(c.bodyHeight,1.15);
 }
});

test('the actual37 continuity sequence clears driving before native on-foot validation and preserves source fallback notices',()=>{
 const {c,target}=setup();target.vehicles=[car('parked-source-body',0,0)];target.roads=[{x:8,z:3,angle:.6}];
 c.p={core:{zone:'real',x:0,z:0,yaw:.4,pitch:0,driving:'serialized-old-car',lastOnFoot:{x:0,z:0},v70:{}}};
 c.VERSIONS=[];c.clone=plain;c.normalizeCore37=x=>x;c.robustNormalize=x=>x;c.clearScene=()=>{};c.applySettings=()=>{};c.api=()=>({ensureRecords(){}});
 vm.runInContext(owners.restoreEntry,c);assert.equal(c.state.driving,null);assert.equal(c.state.lastOnFoot,null);assert.equal(c.calls[0].pose.x,8);
 assert.equal(c.relocations,1);assert.equal(c.refusals,0);assert.ok(c.__SOMA_MOBILITY76__.snapshot().stats.vehicleStops>0);
});

function cacheOwner(c,{parent=false}={}){
 c.root=c;c.ready=true;c.terrain=()=>c.__SOMA_TERRAIN56__;c.active=c.__SOMA_TERRAIN75__.active;c.entrySupported=c.__SOMA_TERRAIN75__.entrySupported;c.refused=c.__SOMA_TERRAIN75__.refused;
 vm.runInContext(parent?owners.changedParent:owners.changed,c);c.__SOMA_TERRAIN75__.changed=c.changed;c.__SOMA_TERRAIN75__.ready=true;
}
test('actual75 cache reconciliation accepts parked overlap;76 changed reuses actual entry fallback on the installed terrain',()=>{
 for(const parent of [true,false]){const {c,target}=setup({parent});c.zone=target;c.camera.x=0;c.camera.z=0;target.vehicles=[car('original-parked',0,0)];target.roads=[{x:8,z:3,angle:.6}];
  const installed=c.__SOMA_TERRAIN56__;cacheOwner(c,{parent});c.changed();assert.equal(c.calls.length,parent?0:1);
  if(!parent){assert.equal(c.calls[0].pose.x,8);assert.equal(c.relocations,1);}assert.equal(c.__SOMA_TERRAIN56__,installed);assert.equal(c.refusals,0);
 }
});
test('late helper initialization reconciles a cached native pose once with the actual75 changed owner',()=>{
 const {c,target}=setup();c.zone=target;c.camera.x=0;c.camera.z=0;target.vehicles=[car('original-parked',0,0)];target.roads=[{x:8,z:3,angle:.6}];cacheOwner(c);
 // Exercise script order explicitly:75 is already ready with its original pose.
 const fs=require('node:fs'),path=require('node:path'),{game}=require('./entry-fixture.cjs');
 vm.runInContext(fs.readFileSync(path.join(game,'src/v76/entry-runtime.js'),'utf8'),c);assert.equal(c.calls.length,1);assert.equal(c.calls[0].pose.x,8);assert.equal(c.relocations,1);
});
test('cache reconciliation retains the75 driving body contract and never asks standing76 to validate the seated camera',()=>{
 const {c,target}=setup();c.zone=target;c.camera.x=0;c.camera.z=0;target.vehicles=[car('current-car',0,0)];c.state.driving='current-car';cacheOwner(c);
 const before=c.__SOMA_MOBILITY76__.snapshot().stats.checks;c.changed();assert.equal(c.calls.length,0);assert.equal(c.refusals,0);assert.equal(c.state.driving,'current-car');
 assert.equal(c.__SOMA_MOBILITY76__.snapshot().stats.checks,before);
});
test('a legacy25m cache does not trigger extra reconciliation when the76 helper loads',()=>{
 const {c,target}=setup({native:false});c.zone=target;c.camera.x=0;c.camera.z=0;target.vehicles=[car('original-parked',0,0)];cacheOwner(c);
 let calls=0;c.__SOMA_TERRAIN75__.changed=()=>calls++;const fs=require('node:fs'),path=require('node:path'),{game}=require('./entry-fixture.cjs');
 vm.runInContext(fs.readFileSync(path.join(game,'src/v76/entry-runtime.js'),'utf8'),c);assert.equal(calls,0);assert.equal(c.calls.length,0);
});
test('a valid cached native pose keeps exact source coordinates and the installed terrain object',()=>{
 const {c,target}=setup();c.zone=target;c.camera={x:3.25,z:-7.125,yaw:.321,pitch:-.2};cacheOwner(c);
 const pose=plain(c.camera),terrain=c.__SOMA_TERRAIN56__;c.changed();assert.deepEqual(plain(c.camera),pose);assert.equal(c.calls.length,0);assert.equal(c.refusals,0);assert.equal(c.__SOMA_TERRAIN56__,terrain);
});
test('occupied native cache fallback refuses explicitly while retaining the installed terrain and prior state',()=>{
 const {c,target}=setup();c.zone=target;c.camera.x=0;c.camera.z=0;target.vehicles=[car('original-parked',0,0)];target.roads=[{x:0,z:0,angle:0}];cacheOwner(c);
 const before=plain({state:c.state,camera:c.camera}),terrain=c.__SOMA_TERRAIN56__;c.changed();assert.equal(c.calls.length,0);assert.ok(c.refusals>0);assert.equal(c.relocations,0);
 assert.deepEqual(plain({state:c.state,camera:c.camera}),before);assert.equal(c.__SOMA_TERRAIN56__,terrain);
});
