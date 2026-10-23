'use strict';
const fs=require('fs'),vm=require('vm'),assert=require('assert');
let src=fs.readFileSync(__dirname+'/../../src/v67/world-runtime.js','utf8');
src=src.replace(/setup\(\);\s*\}\)\(\);\s*$/,"globalThis.__V67_TEST__={ensure,density,daypart,weatherKey,districtLine,pulse,trafficFactor,visualLimit};})();");
const context={
 console, Math, Date,
 state:{time:8,police:{level:0},settings:{},v67:null},
 zone:{district:'port',actors:[],vehicles:[],robots:[]},
 D:{port:{name:'Port',faction:'Dockers'}},
 currentWeather:()=>({name:'Clair'}),
 hash:s=>{let h=0;for(const c of String(s))h=((h<<5)-h+c.charCodeAt(0))|0;return h},
 v28State:()=>({incidents:{}}),V28_DATA:{incidents:[]},
 save:()=>{},showDialogue:()=>{},showBark:()=>{},announce:()=>{},
 npcDialogue:()=>{},triggerAmbientBark:()=>{},updateAI:()=>{},actorGeo:()=>{},vehicleGeo:()=>{},robotGeo:()=>{},animalGeo:()=>{},
 isFlyingVehicleKind:()=>false,isWaterVehicleKind:()=>false,vehicleSpec:()=>({cruise:10}),
 camera:{x:0,z:0},paused:false,openModal:()=>{},enterZone:()=>true,
 document:{getElementById:()=>null,createElement:()=>({style:{},appendChild(){},setAttribute(){}}),head:{appendChild(){}}},
 window:{__SOMA_UI66__:null,__SOMA__:{}},setTimeout:()=>{},
};
vm.createContext(context);vm.runInContext(src,context,{filename:'world-runtime.js'});
const T=context.__V67_TEST__;
assert(T);
assert.equal(T.daypart(),'morning');
assert.equal(T.weatherKey(),'clear');
assert.equal(T.density(),'standard');
assert(T.districtLine('port').length>20);
assert.equal(T.trafficFactor(),0.9); // rush hour, clear
context.state.time=2; context.currentWeather=()=>({name:'Pluie'}); context.state.police.level=4;
assert(Math.abs(T.trafficFactor()-0.84*0.9)<1e-9);
context.state.settings.v67Density='eco';assert(T.visualLimit('actor')<92);
context.state.settings.v67Density='dense';assert(T.visualLimit('vehicle')>155);
const p=T.pulse();assert.equal(p.id,'port');assert('line' in p&&'weatherLine' in p);
console.log(JSON.stringify({passed:true,checks:10,traffic:T.trafficFactor(),pulse:p.id}));
