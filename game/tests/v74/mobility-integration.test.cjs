'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm');
const S=require('./mobility-fixture.cjs');
const plain=x=>JSON.parse(JSON.stringify(x));
function setup({height=(x,z)=>30,missing=()=>false,parent=false}={}){
 const c={console,Math,Number,Object,Array,Set,Map,JSON,Uint8Array,Float32Array,DataView,TextEncoder,Buffer,
   camera:{x:0,z:0,y:31.72,yaw:0,pitch:0},state:{health:100,flags:{},statistics:{},settings:{},driving:null,lastOnFoot:null},
   zone:{id:'synthetic-mobility',w:40,h:40,vehicles:[],colliders:[],roads:[],actors:[],robots:[],animals:[]},
   paused:false,keys:new Set(),touches:new Set(),v20Pad:{forward:0,side:0,throttle:0,steer:0,climb:0,sprint:false},
   lastGround:30,stats:{blockedSlope:0},move(){},nightCarryFactor:()=>1,clamp:(n,a,b)=>Math.max(a,Math.min(b,n)),
   onAccessDeck:()=>false,onSidewalk:()=>true,onRoad:()=>false,v42Crouched:()=>c.crouched||false,v42SanitizeDriving(){},
   isFlyingVehicleKind:k=>k==='air',isWaterVehicleKind:k=>k==='boat',vehicleSpec:()=>({width:1.8,length:4,exitOffset:.7,cameraHeight:1.4}),
   headingVec:h=>({x:Math.sin(h),z:Math.cos(h)}),rightVec:h=>({x:Math.cos(h),z:-Math.sin(h)}),
   orientedAabb:(x,z,w,l)=>({x0:x-w/2,x1:x+w/2,z0:z-l/2,z1:z+l/2}),
   announce:s=>{c.message=s;},save:()=>{c.saves=(c.saves||0)+1;},raisePoliceHeat(){},
   document:{body:{classList:{add(){},remove(){},toggle(){}}}},openPoint:()=>({x:15,z:15}),nearestLandingPad:()=>null};
 c.window=c;vm.createContext(c);vm.runInContext(S.terrainCore,c);vm.runInContext(S.collisionCore,c);vm.runInContext(S.seamCore,c);
 const K=c.__SOMA_TERRAIN56_CORE__,cols=81,step=.5,heights=new Float32Array(cols*cols),mask=new Uint8Array(cols*cols);
 for(let row=0;row<cols;row++)for(let col=0;col<cols;col++){const x=-20+col*step,z=-20+row*step,i=row*cols+col;heights[i]=height(x,z);mask[i]=missing(x,z)?0:1;}
 const grid=new K.Grid({cols,rows:cols,step,x0:-20,n0:20},heights,mask,{},{});
 c.ground=(z,x,zz)=>grid.sample(x,-zz);c.slope=(z,x,zz)=>grid.gradient(x,-zz);c.activeFor=()=>true;
 c.__SOMA_TERRAIN56__={activeFor:c.activeFor,ground:c.ground,slope:c.slope};
 c.__SOMA_V42__={isCrouched:c.v42Crouched};c.__SOMA_V58_CORE__={poseState:()=>null};c.poseVehicle=()=>null;
 let bodyHeight=1.8;c.__SOMA_CLEARANCE60__={core:{STANDING:1.8},withBody:(h,fn)=>{const old=bodyHeight;bodyHeight=h;try{return fn();}finally{bodyHeight=old;}},blocksAt:(volume)=>bodyHeight>volume.v60Volume.bottom-30};
 vm.runInContext(S.blocked,c);vm.runInContext(S.pedestrian,c);vm.runInContext(parent?S.parentSafeExit:S.safeExit,c);vm.runInContext(parent?S.parentEnterExit:S.enterExit,c);
 vm.runInContext(S.pose56,c);c.__SOMA_TERRAIN56__.poseCamera=c.poseCamera;
 vm.runInContext(parent?S.parentMove20:S.move20,c);vm.runInContext('{'+S.move42+'}',c);vm.runInContext('{'+(parent?S.parentMove56:S.move56)+'}',c);vm.runInContext(S.runtime,c);
 c.camera.y=c.ground(c.zone,c.camera.x,c.camera.z)+1.72;c.lastGround=c.camera.y-1.72;return c;
}
function cornerScene(){
 const c=setup(),sha='a'.repeat(64);
 const make=(id,gx,gy,bounds)=>({id,w:40,h:40,v52GridX:gx,v52GridY:gy,v50Record:{boundsL93:bounds,sourceReceipt:{sha256:sha}},vehicles:[],colliders:[],static:true});
 Object.assign(c.zone,make('current',0,0,[-20,-20,20,20]));
 const north=make('north',0,-1,[-20,20,20,60]),east=make('east',1,0,[20,-20,60,20]),ne=make('ne',1,-1,[20,20,60,60]);
 const zones=new Map([c.zone,north,east,ne].map(z=>[z.id,z]));
 c.C=c.__SOMA_V55_CORE__;c.DELTA={E:[1,0],W:[-1,0],N:[0,-1],S:[0,1]};c.isReal=z=>!!z?.v50Record;c.building=0;c.oldBlocked=c.blocked;
 c.loads=0;c.ensure=z=>{if(!z.static){c.loads++;throw Error('collision must not load a synthetic neighbor');}return z;};
 c.v52=()=>({district:{cells:[...zones.values()].map(z=>({id:z.id,gridX:z.v52GridX,gridY:z.v52GridY}))},zones:()=>zones});
 vm.runInContext(S.neighbor55+S.collision55,c);c.blocked=c.collision;
 c.lookups=[];c.__SOMA_V55__={core:c.C,neighbor:(z,side)=>{c.lookups.push(z.id+':'+side);return c.neighbor(z,side);}};
 c.camera.x=18.5;c.camera.z=-18.5;
 const car={id:'diagonal-source-owner-car',kind:'car',pilotable:true,condition:100,x:-19.6,z:19.6,heading:-Math.PI/4};ne.vehicles.push(car);
 const overlap=()=>{const p=c.C.transfer(c.zone.v50Record,ne.v50Record,c.camera),s=c.vehicleSpec(car);return c.__SOMA_V57_CORE__.circleFootprint([p.x,p.z],.38,c.__SOMA_V57_CORE__.obb(car.x,car.z,s.width,s.length,car.heading));};
 return {c,north,east,ne,car,overlap};
}
test('actual v20/v42/v56 controller preserves keyboard sides, crouch and NGF pose',()=>{
 const c=setup({height:(x,z)=>30+z*.25});c.keys.add('KeyW');for(let i=0;i<60;i++)c.move(1/60);
 assert.ok(Math.abs(c.camera.z-3.2)<1e-5);assert.ok(Math.abs(c.camera.y-c.ground(c.zone,c.camera.x,c.camera.z)-1.72)<1e-7);
 c.keys.clear();c.keys.add('KeyD');c.move(.1);assert.ok(c.camera.x<0,'historical v42 side correction remains in control');
 c.crouched=true;c.move(.1);assert.ok(Math.abs(c.camera.y-c.ground(c.zone,c.camera.x,c.camera.z)-1.05)<1e-7);
 assert.ok(c.__SOMA_MOBILITY74__.snapshot().stats.footSubsteps>=60);
});
test('a 120% measured slope is refused at 30, 60 and 120 Hz, with lastOnFoot synchronized',()=>{
 for(const hz of [30,60,120]){
  const c=setup({height:(x,z)=>30+z*1.2});c.keys.add('KeyW');for(let i=0;i<hz;i++)c.move(1/hz);
  assert.equal(c.camera.z,0);assert.equal(c.state.lastOnFoot.z,0);assert.ok(c.__SOMA_MOBILITY74__.snapshot().stats.slopeStops>0);
 }
});
test('admissible 50% and 80% slopes preserve the same measured sprint distance at 30, 60 and 120 Hz',()=>{
 for(const slope of [.5,.8])for(const hz of [30,60,120]){
  const c=setup({height:(x,z)=>30+z*slope});c.keys.add('KeyW');c.keys.add('ShiftLeft');for(let i=0;i<hz;i++)c.move(1/hz);
  assert.ok(Math.abs(c.camera.z-5.6)<1e-5,`slope ${slope}, ${hz} Hz: ${c.camera.z}`);
  assert.equal(c.state.lastOnFoot.z,c.camera.z);assert.ok(Math.abs(c.camera.y-c.ground(c.zone,c.camera.x,c.camera.z)-1.72)<1e-7);
 }
});
test('regression evidence: unmodified parent moves up the same 120% slope at 60 Hz',()=>{
 const before=setup({height:(x,z)=>30+z*1.2,parent:true});before.keys.add('KeyW');for(let i=0;i<60;i++)before.move(1/60);
 assert.ok(before.camera.z>3.19,'the actual parent fixed .35 m tolerance accepts every small frame');
});
test('oriented parked vehicle bodies stop feet; hidden vehicles leave no collision ghost',()=>{
 const c=setup();c.zone.vehicles.push({id:'synthetic-parked',kind:'car',x:0,z:3,heading:Math.PI/4});c.keys.add('KeyW');
 for(let i=0;i<40;i++)c.move(.1);assert.ok(c.camera.z<2);assert.ok(c.__SOMA_MOBILITY74__.snapshot().stats.vehicleStops>0);
 c.zone.vehicles[0].hidden=true;for(let i=0;i<10;i++)c.move(.1);assert.ok(c.camera.z>3);
 const before=setup({parent:true});before.zone.vehicles.push({id:'synthetic-parked',kind:'car',x:0,z:3,heading:Math.PI/4});before.keys.add('KeyW');
 for(let i=0;i<20;i++)before.move(.1);assert.ok(before.camera.z>6,'the actual parent walks through the same body');
});
test('an already built neighboring car is tested in its own metric coordinates using the actual seam core',()=>{
 const c=setup();c.zone.v50Record={boundsL93:[-20,-20,20,20]};c.camera.x=17;c.camera.yaw=Math.PI/2;
 const neighbor={static:true,v50Record:{boundsL93:[20,-20,60,20]},vehicles:[{id:'neighbor-car',kind:'car',x:-20.8,z:0,heading:0}]};
 c.__SOMA_V55__={core:c.__SOMA_V55_CORE__,neighbor:(z,side)=>side==='E'?neighbor:null};c.keys.add('KeyW');
 for(let i=0;i<10;i++)c.move(.1);assert.ok(c.camera.x<17.93);assert.ok(c.__SOMA_MOBILITY74__.snapshot().stats.vehicleStops>0);
 neighbor.static=false;for(let i=0;i<10;i++)c.move(.1);assert.ok(c.camera.x>18.5);
});
test('a diagonal-cell body protruding inside the current corner stops feet through real neighbor55 composition',()=>{
 const {c,overlap}=cornerScene();assert.equal(overlap(),false);c.__SOMA_MOBILITY74__.walk(.4,-.4);
 assert.equal(overlap(),false);assert.ok(c.__SOMA_MOBILITY74__.snapshot().stats.vehicleStops>0);
 assert.ok(c.lookups.includes('north:E'));assert.equal(c.loads,0);
});
test('diagonal lookup creates no scene and does not block for a distant or unbuilt neighbor',()=>{
 for(const mode of ['distant','unbuilt']){
  const {c,ne,car}=cornerScene();if(mode==='distant'){car.x=0;car.z=0;}else{ne.static=false;}
  c.__SOMA_MOBILITY74__.walk(.4,-.4);assert.ok(Math.abs(c.camera.x-18.9)<1e-6);assert.ok(Math.abs(c.camera.z+18.9)<1e-6);
  assert.equal(c.__SOMA_MOBILITY74__.snapshot().stats.vehicleStops,0);assert.equal(c.loads,0);assert.equal(ne.static,mode!=='unbuilt');
 }
 const {c}=cornerScene();c.camera.x=0;c.camera.z=0;c.__SOMA_MOBILITY74__.walk(.4,-.4);
 assert.equal(c.lookups.length,0,'a point away from every edge does not query neighbors');assert.equal(c.loads,0);
});
test('local dismount ignores its own body but refuses a different diagonal-cell vehicle body',()=>{
 const {c,ne,car}=cornerScene();
 // Its preferred right door is inside the NE-owned body; the left door is free.
 const own={id:'departing-car',kind:'car',pilotable:true,condition:100,x:17.8,z:-18.5,heading:0};c.zone.vehicles.push(own);
 c.camera.x=16;c.camera.z=-18.5;c.enterVehicle(own);
 const right=c.C.transfer(c.zone.v50Record,ne.v50Record,{x:own.x+1.69,z:own.z}),spec=c.vehicleSpec(car);
 assert.equal(c.__SOMA_V57_CORE__.circleFootprint([right.x,right.z],.38,c.__SOMA_V57_CORE__.obb(car.x,car.z,spec.width,spec.length,car.heading)),true);
 const p=c.__SOMA_MOBILITY74__.exitPoint(own);assert.ok(p,'the ignored vehicle itself does not seal every exit');
 assert.ok(p.x<own.x,'the different diagonal-owned body seals the preferred right door');
 const q=c.C.transfer(c.zone.v50Record,ne.v50Record,p),s=c.vehicleSpec(car);
 assert.equal(c.__SOMA_V57_CORE__.circleFootprint([q.x,q.z],.38,c.__SOMA_V57_CORE__.obb(car.x,car.z,s.width,s.length,car.heading)),false);
 assert.equal(c.loads,0);
});
test('real terrain-grid NoData and source collision owner stop the subdivided movement',()=>{
 const c=setup({missing:(x,z)=>z>1});c.keys.add('KeyW');for(let i=0;i<30;i++)c.move(.1);assert.ok(c.camera.z<=.63);
 const wall=setup();wall.zone.colliders.push({x0:-2,x1:2,z0:.8,z1:.9,tag:'solid'});wall.keys.add('KeyW');wall.move(.1);wall.move(.1);
 assert.ok(wall.camera.z<.43);assert.equal(wall.state.lastOnFoot.z,wall.camera.z);assert.ok(wall.__SOMA_MOBILITY74__.snapshot().stats.collisionStops>0);
});
test('invalid or stalled frames cannot tunnel and pause keeps foot state unchanged',()=>{
 const c=setup();c.keys.add('KeyW');for(const dt of [NaN,Infinity,-1,0])c.move(dt);assert.equal(c.camera.z,0);
 c.move(12);assert.ok(c.camera.z<=.320001);const before=plain(c.camera);c.paused=true;c.move(.1);assert.deepEqual(plain(c.camera),before);
});
test('actual enter/exit owners use NGF immediately, save once and stay near the vehicle',()=>{
 const c=setup({height:(x,z)=>45+x*.1});const v={id:'synthetic-car',kind:'car',pilotable:true,condition:100,x:0,z:0,heading:0};c.zone.vehicles.push(v);
 assert.equal(c.enterVehicle(v),true);assert.equal(c.camera.y,46.4);assert.equal(c.exitVehicle(),true);
 assert.equal(c.state.driving,null);assert.ok(Math.hypot(c.camera.x-v.x,c.camera.z-v.z)<=6);
 assert.ok(Math.abs(c.camera.y-c.ground(c.zone,c.camera.x,c.camera.z)-1.72)<1e-7);assert.equal(c.saves,1);
});
test('blocked doors refuse dismount instead of teleporting to lastOnFoot or openPoint',()=>{
 const c=setup(),v={id:'synthetic-car',kind:'car',pilotable:true,condition:100,x:0,z:0,heading:0};c.zone.vehicles.push(v);c.enterVehicle(v);
 c.state.lastOnFoot={zone:c.zone.id,x:14,z:14,yaw:0};
 // Closed ring: all candidate destinations outside it are free but unreachable.
 c.zone.colliders.push({x0:.9,x1:1,z0:-8,z1:8,tag:'wall'},{x0:-1,x1:-.9,z0:-8,z1:8,tag:'wall'},
   {x0:-8,x1:8,z0:2.1,z1:2.2,tag:'wall'},{x0:-8,x1:8,z0:-2.2,z1:-2.1,tag:'wall'});
 const pose=plain(c.camera),last=plain(c.state.lastOnFoot);assert.equal(c.exitVehicle(false,true),false);
 assert.equal(c.state.driving,v.id);assert.deepEqual(plain(c.camera),pose);assert.deepEqual(plain(c.state.lastOnFoot),last);
 assert.equal(c.saves||0,0);assert.match(c.message,/Sortie impossible/);assert.equal(c.__SOMA_MOBILITY74__.snapshot().stats.exitRefusals,1);
});
test('crouched driving does not permit an exit under a volume too low to stand',()=>{
 const c=setup(),v={id:'synthetic-car',kind:'car',pilotable:true,condition:100,x:0,z:0,heading:0};c.zone.vehicles.push(v);c.enterVehicle(v);c.crouched=true;
 c.zone.colliders.push({x0:-10,x1:10,z0:-10,z1:10,tag:'overhang',v60Volume:{bottom:31.4}});
 assert.equal(c.exitVehicle(),false);assert.equal(c.state.driving,v.id);assert.equal(c.saves||0,0);
});
test('regression evidence: the unmodified exit owner crosses the same closed wall ring',()=>{
 const c=setup({parent:true}),v={id:'synthetic-car',kind:'car',pilotable:true,condition:100,x:0,z:0,heading:0};c.zone.vehicles.push(v);c.enterVehicle(v);
 c.zone.colliders.push({x0:.9,x1:1,z0:-8,z1:8,tag:'wall'},{x0:-1,x1:-.9,z0:-8,z1:8,tag:'wall'},
   {x0:-8,x1:8,z0:2.1,z1:2.2,tag:'wall'},{x0:-8,x1:8,z0:-2.2,z1:-2.1,tag:'wall'});
 assert.equal(c.exitVehicle(false,true),true);assert.ok(Math.abs(c.camera.x)>1||Math.abs(c.camera.z)>2.2);
});
