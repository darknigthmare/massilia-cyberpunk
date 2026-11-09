'use strict';
// Real authored world and city owners; DOM, rendering and avatar poses are fixtures.
const path=require('node:path'),vm=require('node:vm'),cp=require('node:child_process');
const inherited=require('../v77/missions-fixture.cjs'),game=path.resolve(__dirname,'../..');
const current=JSON.parse(cp.execFileSync('python3',['-B','-c',String.raw`
import json,re,sys
from pathlib import Path
game=Path(sys.argv[1]);sys.path.insert(0,str(game))
from tools.v78_missions import MODULES,patch_html
parent=(game/'SOMA_MASSILIA_URBAIN_v0_77.html').read_text()
patched=patch_html(parent,{name:(game/'src/v78'/f'{name}.js').read_text() for name in MODULES})
def city(text):return re.search(r'<script\b[^>]*id="soma-v45-city"[^>]*>([\s\S]*?)</script>',text)[1]
print(json.dumps({'parentCity':city(parent),'city':city(patched)}))
`,game],{encoding:'utf8',maxBuffer:2*1024*1024,env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'}}));
const plain=value=>JSON.parse(JSON.stringify(value));
function fixture(parent=false){
 const storage=new Map(),combat={zoneCombat:{},combat:{},loot:{}};
 const c={Math,Map,Set,Object,Array,Number,String,JSON,Date,performance:{now:()=>1000},setTimeout:()=>{},
  localStorage:{getItem:key=>storage.get(key)||null,setItem:(key,value)=>storage.set(key,value)},
  state:{zone:'station-exterior',health:100,armor:45,credits:240,reputation:{},recovery:{pending:false}},camera:{x:0,z:0},paused:false,
  blocked:()=>false,lineBlocked:()=>false,renderer:{uploadStatic:()=>{},prepareSigns:()=>{}},
  document:{getElementById:()=>null,readyState:'complete',addEventListener:()=>{}},
  announce:message=>c.lastAnnouncement=message,closeModals:()=>{c.paused=false;c.closed=(c.closed||0)+1;},
  showDialogue:(title,lines,choices)=>{c.dialogue={title,lines,choices};c.paused=true;},save:()=>{},
  __SOMA_V42__:{state:()=>({finale:{status:'done'}})},__SOMA_V37_SAVE__:{schedule:()=>{}},
  __SOMA_V32__:{getState:()=>combat,snapshotCombat:()=>{}},C:{hex:value=>value},extendNightWorld:()=>{}};
 c.window=c;c.globalThis=c;vm.createContext(c);
 vm.runInContext(inherited.worldData+'\n'+inherited.nightWorld+'\n'+inherited.authoredWorld+'\nvar WORLD=makeWorld();var D=Object.fromEntries(DISTRICTS.map(d=>[d.id,d]));var NARRATIVE={readables:{}};'+inherited.annexWorld,c);
 for(const z of Object.values(c.WORLD.zones))Object.assign(z,{robots:[],actors:[],vehicles:[],interactables:[],static:[]});c.zone=c.WORLD.zones['station-exterior'];
 vm.runInContext(inherited.production.replace('v43Setup();','window.story={ensure:v43EnsureZone};'),c);
 const expose='window.city={state:()=>V45,find:v45FindRoute,targets:V45_RACE_TARGETS,calls:V45_CALLS,races:V45_RACES,spawn:v45SpawnCall,accept:v45AcceptCall,resolve:v45ResolveCall,expire:v45ExpireCall,dialogue:v45CallDialogue,render:v45RenderCommand,startRace:v45StartRace,raceChanged:v45RaceZoneChanged,failRace:v45FailRace,ensure:v45EnsureZone,set:v45SetDestination,clear:v45ClearDestination};';
 vm.runInContext((parent?current.parentCity:current.city).replace('v45Setup();',expose),c);
 c.buildZone=z=>{z.robots=[];z.vehicles=[];z.interactables=[];z.static=[];c.story.ensure(z);return c.city.ensure(z);};
 c.enter=id=>{if(!c.WORLD.zones[id])throw Error('Unknown source zone '+id);c.zone=c.WORLD.zones[id];c.state.zone=id;c.story.ensure(c.zone);c.city.ensure(c.zone);c.paused=false;};
 c.call=id=>{if(!c.city.spawn(id)||!c.city.accept(id))throw Error('Cannot accept fixture source call '+id);const s=c.city.state().calls[id];c.enter(s.zone);return{record:s,node:c.zone.interactables.find(o=>o.type==='v45CallNode'&&o.callId===id)};};
 c.manual=()=>{if(!c.city.set('station-interiorA','Destination personnelle',false))throw Error('Manual fixture route unavailable');return plain(c.city.state().route);};
 c.traceButton=id=>{const b={dataset:{v45TrackCall:id}},element={innerHTML:'',querySelectorAll:selector=>selector==='[data-v45-track-call]'?[b]:[]};c.document.getElementById=key=>key==='v45-command-body'?element:null;c.city.render('calls');if(typeof b.onclick!=='function')throw Error('Native call trace button missing');return b;};
 c.storage=storage;return c;
}
module.exports={fixture,plain,current};
