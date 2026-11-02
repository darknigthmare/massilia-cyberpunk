/* Actual transformed56/37/57/60 owners with declared synthetic scene bodies.
 * The separate native browser audit uses installed original source cells. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),cp=require('node:child_process'),vm=require('node:vm');
const game=path.resolve(__dirname,'../..');
const owners=JSON.parse(cp.execFileSync('python3',['-c',String.raw`
import json,re,sys
from pathlib import Path
g=Path(sys.argv[1]);sys.path.insert(0,str(g))
from tools.v76_mobility import patch_terrain, patch_cache_reconcile
h=(g/'SOMA_MASSILIA_URBAIN_v0_75.html').read_text()
def s(n):return re.search(r'<script\b[^>]*id="'+n+r'"[^>]*>([\s\S]*?)</script>',h)[1]
def span(t,a,b):return t[t.index(a):t.index(b,t.index(a))]
t=s('soma-v56-terrain-runtime');clearance=s('soma-v60-runtime')
print(json.dumps({'parent':span(t,' const oldEnter=enterZone;',' const oldActor=actorGeo;'),
 'entry':span(patch_terrain(t),' const oldEnter=enterZone;',' const oldActor=actorGeo;'),
 'restoreEntry':span(s('soma-v37-persistence'),'  state=normalizeCore37(robustNormalize(clone(p.core)));','api(31).ensureRecords();')+'api(31).ensureRecords();',
 'changedParent':span(s('soma-v75-terrain-runtime'),'  function changed(){','  async function select('),
 'changed':span(patch_cache_reconcile(s('soma-v75-terrain-runtime')),'  function changed(){','  async function select('),
 'vehicle':s('soma-v57-core'),'seams':s('soma-v55-core'),'clearance':s('soma-v60-core'),
 'standing':span(clearance,'function withBody(','function modelHeight('),
 'blocked':span(h,'function blocked(zone,x,z,r=.38){','function setupReserved(')}))
`,game],{encoding:'utf8',maxBuffer:8*1024*1024}));
function setup({parent=false,native=true}={}){
 const c={console,Math,Number,Object,Array,Set,Map,JSON,TextEncoder,Buffer,Uint8Array,Uint32Array,Float32Array,DataView,
  zone:{id:'historic',vehicles:[],static:true},camera:{x:11,z:12,yaw:.3},state:{driving:null,lastOnFoot:{x:11,z:12}},paused:false,
  status:'',lastGround:0,bodyHeight:1.8,stats:{unknownProfiles:0},calls:[],relocations:0,refusals:0,entered:0,
  ground:(z,x,zz)=>20,slope:()=>({e:0,south:0}),isFlyingVehicleKind:k=>k==='air',isWaterVehicleKind:k=>k==='boat',
  vehicleSpec:()=>({width:2,length:4}),onAccessDeck:()=>false,refresh(){},poseCamera(){},buildZone(){throw Error('fixture source zone already built');}};
 c.window=c;vm.createContext(c);
 for(const key of ['vehicle','seams','clearance'])vm.runInContext(owners[key],c);
 c.K=c.__SOMA_CLEARANCE60_CORE__;c.real=z=>z?.v52District===true;
 c.__SOMA_TERRAIN56__={activeFor:c.real,ground:(...a)=>c.ground(...a),poseCamera:c.poseCamera};
 vm.runInContext(owners.standing,c);vm.runInContext(owners.blocked,c);
 c.__SOMA_CLEARANCE60__={core:c.K,withBody:c.withBody,blocksAt:c.blocksAt};
 c.isReal=c.real;c.activeFor=c.real;c.v69GridFor=()=>true;
 c.footprintValid=(z,x,zz,r)=>[[0,0],[r,0],[-r,0],[0,r],[0,-r]].every(([dx,dz])=>Number.isFinite(c.ground(z,x+dx,zz+dz)));
 c.__SOMA_TERRAIN75__={active:()=>native,entrySupported:(z,x,zz)=>!native||c.footprintValid(z,x,zz,.4)&&Math.hypot(...Object.values(c.slope(z,x,zz)))<=.95+1e-7,
  relocated:()=>c.relocations++,refused:()=>{c.refusals++;},entered:()=>c.entered++};
 c.enterZone=(id,via,pose)=>{c.calls.push({id,via,pose});return true;};
 c.WORLD={zones:{}};vm.runInContext(fs.readFileSync(path.join(game,'src/v76/entry-runtime.js'),'utf8'),c);
 vm.runInContext('{'+(parent?owners.parent:owners.entry)+'}',c);
 const target={id:'real',v52District:true,w:40,h:40,static:true,colliders:[],vehicles:[],roads:[],spawn:{x:0,z:0,yaw:0},v50Record:{boundsL93:[-20,-20,20,20]}};
 c.WORLD.zones.real=target;return {c,target};
}
module.exports={setup,owners,game};
