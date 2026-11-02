/* Actual v24/v56/v57 owners transformed over v74. All geometry in this fixture
 * is declared synthetic; the native-browser run is a separate proof. */
'use strict';
const path=require('node:path'),cp=require('node:child_process'),vm=require('node:vm');
const game=path.resolve(__dirname,'../..');
const S=JSON.parse(cp.execFileSync('python3',['-c',String.raw`
import json,re,sys
from pathlib import Path
game=Path(sys.argv[1]);sys.path.insert(0,str(game))
from tools.v75_vehicles import patch_html
parent=(game/'SOMA_MASSILIA_URBAIN_v0_74.html').read_text()
html=patch_html(parent,{'vehicle-runtime':(game/'src/v75/vehicle-runtime.js').read_text()})
def script(name):return re.search(r'<script\b[^>]*id="'+name+r'"[^>]*>([\s\S]*?)</script>',html)[1]
def span(text,a,b):return text[text.index(a):text.index(b,text.index(a))]
v57=script('soma-v57-runtime');terrain=script('soma-v56-terrain-runtime')
print(json.dumps({'core':script('soma-v57-core'),'terrainCore':script('soma-v56-terrain-core'),'seamCore':script('soma-v55-core'),
 'specs':span(html,'const VEHICLE_SPECS={','const VEHICLE_BRANDS='),
 'integrate':span(html,'function integrateVehicle(v,input,dt,playerControlled=false){','function nearestLandingPad('),
 'parentIntegrate':span(parent,'function integrateVehicle(v,input,dt,playerControlled=false){','function nearestLandingPad('),
 'collision':span(v57,'function index(z){','function actualRoad('),
 'wrapper57':span(v57,' integrateVehicle=function(v,input,dt,player=false){',' const originalOpen='),
 'wrapper56':span(terrain,' const oldIntegrate=integrateVehicle;',' const oldMove=move;'),
 'runtime':script('soma-v75-vehicle-runtime')}))
`,game],{encoding:'utf8',maxBuffer:8*1024*1024}));
function setup({height=()=>30,missing=()=>false,parent=false,step=5,kind='sedan'}={}){
 const c={console,Math,Number,Map,WeakMap,Set,Array,Object,Float32Array,Uint8Array,Buffer,DataView,TextEncoder,
  state:{armor:100,statistics:{}},paused:false,damageFlash:0,stats:{footprintQueries:0,broadCandidates:0,polygonContacts:0,vehicleContacts:0,missingGround:0,slopeStops:0,substeps:0,ignoredInvalidFrames:0},
  indices:new WeakMap(),gridIds:new Map(),buildingDepth:0,
  clamp:(n,a,b)=>Math.max(a,Math.min(b,n)),moveToward:(n,t,d)=>n<t?Math.min(t,n+d):Math.max(t,n-d),wrapAngle:n=>Math.atan2(Math.sin(n),Math.cos(n)),
  isFlyingVehicleKind:k=>k==='airTaxi',isWaterVehicleKind:k=>k==='boat',isMotorcycleKind:k=>k.endsWith('Bike'),
  headingVec:h=>({x:Math.sin(h),z:Math.cos(h)}),announce(){},raisePoliceHeat(){},onAccessDeck:()=>false,buildZone:z=>{z.static=true;},poseVehicle:()=>null,
  integrateFlyingVehicle(){c.flyingCalls=(c.flyingCalls||0)+1;return true;},previousVehicleBlocked:()=>false,previousOverlaps:()=>false};
 c.window=c;vm.createContext(c);for(const key of ['core','terrainCore','seamCore','specs'])vm.runInContext(S[key],c);
 vm.runInContext('function vehicleSpec(v){return VEHICLE_SPECS[v.kind]}',c);
 const K=c.__SOMA_TERRAIN56_CORE__,cols=101,origin=-step*50,heights=new Float32Array(cols*cols),mask=new Uint8Array(cols*cols);
 for(let row=0;row<cols;row++)for(let col=0;col<cols;col++){const x=origin+col*step,z=origin+row*step,i=row*cols+col;heights[i]=height(x,z);mask[i]=missing(x,z)?0:1;}
 const grid=new K.Grid({cols,rows:cols,step,x0:origin,n0:-origin},heights,mask,{},{}),sha='a'.repeat(64);
 c.zone={id:'geo:synthetic-vehicles',w:100,h:100,v52District:true,v52GridX:0,v52GridY:0,static:true,v50Record:{boundsL93:[-50,-50,50,50],v53Validated:true,v53Synthetic:false,sourceReceipt:{sha256:sha}},vehicles:[],colliders:[],actors:[],robots:[],animals:[]};
 c.WORLD={zones:{[c.zone.id]:c.zone}};c.gridIds.set('0:0','synthetic-vehicles');c.real=z=>!!z?.v52District&&!!z.v50Record?.v53Validated;
 c.ground=(z,x,zz)=>grid.sample(x,-zz);c.slope=(z,x,zz)=>grid.gradient(x,-zz);c.activeFor=z=>c.real(z);
 c.__SOMA_TERRAIN56__={activeFor:c.activeFor,ground:c.ground,slope:c.slope,grid,v69:{gridFor:()=>grid}};c.__SOMA_V58_CORE__={poseState:()=>null};
 c.K=c.__SOMA_V57_CORE__;vm.runInContext(S.collision,c);c.vehicleBlockedAt=c.footprintBlocked;c.vehicleOverlapsAt=c.overlapVehicles;
 vm.runInContext(parent?S.parentIntegrate:S.integrate,c);vm.runInContext('{'+S.wrapper56+'}',c);c.previousIntegrate=c.integrateVehicle;vm.runInContext(S.wrapper57,c);
 if(!parent)vm.runInContext(S.runtime,c);
 c.vehicle={id:'original-owner-vehicle',kind,x:0,z:0,heading:Math.PI/2,speed:0,steering:0,condition:100,lean:0};c.zone.vehicles.push(c.vehicle);
 return c;
}
module.exports={setup,S};
