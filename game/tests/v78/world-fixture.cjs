'use strict';
// The metric55 handoff/remember and58 snapshot owner are executed verbatim.
// Cells, admission, scene entry and failing observer APIs are declared fixtures:
// these tests prove synchronous rollback, not a physical source-road traversal.
const fs=require('node:fs'),path=require('node:path'),cp=require('node:child_process'),vm=require('node:vm');
const game=path.resolve(__dirname,'../..');
const owners=JSON.parse(cp.execFileSync('python3',['-B','-S','-c',String.raw`
import json,re,sys
from pathlib import Path
g=Path(sys.argv[1]);sys.path.insert(0,str(g))
from tools.v78_world import patch_handoff
h=(g/'SOMA_MASSILIA_URBAIN_v0_77.html').read_text()
def script(id):return re.search(r'<script\b[^>]*id="'+id+r'"[^>]*>([\s\S]*?)</script>',h)[1]
def span(t,a,b):return t[t.index(a):t.index(b,t.index(a))]
p=script('soma-v55-runtime');fixed=patch_handoff(p)
print(json.dumps({'core':script('soma-v55-core'),'snapshots':script('soma-v58-core'),
 'remember':span(p,'function remember(z){','function restore(z){'),
 'saveStats':span(p,'function saveStats(){','function remember(z){'),
 'before':span(p,'function handoff(','function transferAfterMove('),
 'after':span(fixed,'function handoff(','function transferAfterMove('),
 'fleet45':span(h,'function v45VinFor(','function v45UpgradeCost(')}))
`,game],{encoding:'utf8',maxBuffer:4*1024*1024}));
const plain=x=>JSON.parse(JSON.stringify(x));
function setup({parent=false,mode='vehicle',fault=null,existingMemory=true}={}){
 const car={id:'source-car',kind:'car',x:125.01,z:11,heading:.42,y:0,speed:4.1,steering:.2,condition:94,paint:[.1,.2,.3],v56Pose:{height:20}};
 const sourcePeer={id:'source-peer',x:17,z:12},targetPeer={id:'target-peer',x:12,z:8};
 const from={id:'geo:source',v52CellId:'source',v52District:true,static:true,v50Record:{boundsL93:[892000,6247000,892250,6247250],contentSHA256:'a'.repeat(64)},vehicles:[car,sourcePeer],actors:[{id:'source-actor'}],robots:[],animals:[]};
 const to={id:'geo:target',v52CellId:'target',v52District:true,static:true,v50Record:{boundsL93:[892250,6247000,892500,6247250],contentSHA256:'b'.repeat(64)},vehicles:[targetPeer],actors:[],robots:[],animals:[]};
 const classes=new Set(mode==='vehicle'?['driving','other-class']:['other-class']);
 const c={console,Math,Number,Object,Reflect,Array,Map,Set,JSON,structuredClone,from,to,car,sourcePeer,targetPeer,zone:from,
  state:{zone:from.id,driving:mode==='vehicle'?car.id:null,lastOnFoot:{zone:from.id,x:110,z:8,yaw:.2},x:car.x,z:car.z,yaw:.42,pitch:-.1},camera:{x:car.x,z:car.z,y:22,yaw:.42,pitch:-.1},
  transitioning:false,stats:{footCrossings:3,vehicleCrossings:4,blockedCrossings:2,maxMetricError:0,lastCrossing:{from:'prior'}},
  memory:new Map(),layer:{global:{drivenSeamCodes:['old-seam'],drivenSeams:1},visited:{source:true}},fault,failed:false,calls:[],
  document:{body:{classList:{contains:k=>classes.has(k),add:k=>classes.add(k),remove:(...names)=>names.forEach(k=>classes.delete(k)),toggle:(k,on)=>on?classes.add(k):classes.delete(k)}}},
  classes,admissionBlocked:false,layerStore:null,statsStore:null,coreStore:null,fleet:{activeVin:null,lastZone:null},
  isReal:z=>!!z?.v52District,vehicleBlockedAt:()=>c.admissionBlocked,collision:()=>c.admissionBlocked};
 c.window=c;vm.createContext(c);vm.runInContext(owners.core,c);vm.runInContext(owners.snapshots,c);c.C=c.__SOMA_V55_CORE__;
 c.inject=stage=>{c.calls.push(stage);if(c.fault===stage&&!c.failed){c.failed=true;throw Error('Injected observer failure: '+stage);}};
 const originalSnapshot=c.__SOMA_V58_CORE__.snapshotEntities;
 c.__SOMA_V58_CORE__={...c.__SOMA_V58_CORE__,snapshotEntities(rows){c.inject('remember');return originalSnapshot(rows);}};
 c.v52=()=>({state:()=>c.layer,save(){c.inject('save52-before');c.layerStore=plain(c.layer);c.inject('save52-after');}});
 c.oldEnter=(id,via,p)=>{c.zone=to;Object.assign(c.state,{zone:id,x:p.x,z:p.z,yaw:p.yaw,pitch:p.pitch});Object.assign(c.camera,p);c.document.body.classList.remove('driving','flying');c.layer.visited.target=true;c.inject('enter');return true;};
 c.KEY='soma-massilia-metric-travel-v55';c.localStorage={setItem(key,value){c.inject('storageQuota');c.statsStore=JSON.parse(value);}};
 c.save=()=>{c.coreStore=plain(c.state);c.inject('saveCore');};
 c.refresh=()=>c.inject('refresh');
 c.__SOMA_V54__={refreshScene(){c.inject('recoveryRender');}};
 c.__SOMA_V45__={registerVehicle(v){c.inject('register-before');v.v45Vin='fixture-vin';v.v45Upgrades={armor:1};v.paint=[.8,.2,.1];v.condition=72;c.fleet.activeVin='fixture-vin';c.fleet.lastZone=c.zone.id;c.inject('register-after');}};
 vm.runInContext(owners.saveStats,c);vm.runInContext(owners.remember,c);
 if(existingMemory){c.memory.set(from.id,{hash:'old-source',vehicles:[{id:'saved-source-car'}]});c.memory.set(to.id,{hash:'old-target',vehicles:[{id:'saved-target-car'}]});}
 vm.runInContext(fs.readFileSync(path.join(game,'src/v78/world-transaction-runtime.js'),'utf8'),c);
 vm.runInContext(parent?owners.before:owners.after,c);
 const sourceArray=from.vehicles,targetArray=to.vehicles,carOwn=Object.getOwnPropertyDescriptors(car),memoryRefs=new Map(c.memory),oldLast=c.state.lastOnFoot;
 const before=observe(c);
 return {c,from,to,car,sourcePeer,targetPeer,sourceArray,targetArray,carOwn,memoryRefs,oldLast,before};
}
function observe(c){return plain({zone:c.zone.id,state:c.state,camera:c.camera,car:c.car,source:c.from.vehicles,target:c.to.vehicles,memory:[...c.memory],stats:c.stats,classes:[...c.classes].sort(),transitioning:c.transitioning});}
module.exports={setup,observe,plain,owners,game};
