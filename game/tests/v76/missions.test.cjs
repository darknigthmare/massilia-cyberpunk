'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm');
const fs=require('node:fs'),path=require('node:path');
const source=require('./missions-fixture.cjs'),plain=x=>JSON.parse(JSON.stringify(x));
function fixture(parent=false,loading=false){
 const events=new Map();
 const storage=new Map(),combat={zoneCombat:{},combat:{},loot:{}};
 const c={Math,Map,Set,Object,Array,Number,String,JSON,Date,performance:{now:()=>1000},setTimeout:()=>{},
  localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)},state:{zone:'station-exterior',health:100,armor:45,credits:240,reputation:{},recovery:{pending:false}},camera:{x:0,z:0},paused:false,
  blocked:()=>false,vehicleSpec:v=>({width:v.width||2,length:v.length||4}),lineBlocked:()=>false,renderer:{},document:{getElementById:()=>null,readyState:loading?'loading':'complete',addEventListener:(name,fn)=>events.set(name,fn)},announce:()=>{},showDialogue:(title,lines,choices)=>{c.dialogue={title,lines,choices};c.paused=true;},save:()=>{},
  __SOMA_V42__:{segmentRect:()=>false,state:()=>({finale:{status:'done'}})},__SOMA_V37_SAVE__:{schedule:()=>{}},
  __SOMA_V32__:{getState:()=>combat,zoneCombatState:id=>combat.zoneCombat[id]||(combat.zoneCombat[id]={enemies:{}}),snapshotCombat:()=>{for(const q of c.zone.robots)if(q.v32Enemy)c.__SOMA_V32__.zoneCombatState(c.zone.id).enemies[q.id]={health:q.health,maxHealth:q.maxHealth,armor:q.armor,state:q.state,detect:q.detect,downHandled:!!q.v32DownHandled};}},
  C:{hex:v=>v},extendNightWorld:()=>{}};
 c.window=c;c.globalThis=c;vm.createContext(c);
 vm.runInContext(source.worldData+'\n'+source.nightWorld+'\n'+source.authoredWorld+'\nvar WORLD=makeWorld();var D=Object.fromEntries(DISTRICTS.map(d=>[d.id,d]));var NARRATIVE={readables:{}};'+source.annexWorld,c);
 for(const z of Object.values(c.WORLD.zones))Object.assign(z,{robots:[],actors:[],vehicles:[],interactables:[],static:[]});c.zone=c.WORLD.zones['station-exterior'];
 const expose=`window.owner={state:()=>V43,story:V43_STORY,gigs:V43_GIGS,hotspots:V43_HOTSPOTS,accept:v43AcceptStory,node:v43StoryNodeDialogue,advance:v43CompleteStoryStep,close:v43CloseStory,acceptGig:v43AcceptGig,gigNode:v43GigNodeDialogue,returnGig:v43MarkGigReturn,closeGig:v43CloseGig,ensure:v43EnsureZone,spawn:v43SpawnEnemies,marker:${parent?'null':'v76GigPoint'},tick:v43TickChannel,channel:()=>v43Channel,unlock:v43RefreshUnlocks,command:v43CampaignConsoleDialogue,board:v43FixerBoardDialogue};`;
 vm.runInContext((parent?source.parentProduction:source.production).replace('v43Setup();',expose),c);
 vm.runInContext(source.city.replace('v45Setup();','window.route=v45FindRoute;window.city={state:()=>V45,fresh:v45Fresh,normalize:v45Normalize};'),c);
 vm.runInContext(source.geometry,c);
 c.enter=id=>{assert(c.WORLD.zones[id],id);c.zone=c.WORLD.zones[id];c.state.zone=id;c.owner.ensure(c.zone);c.paused=false;};
 c.point=(type,id,index)=>{const o=c.zone.interactables.find(o=>o.type===type&&(!id||o.storyId===id&&o.step===index||o.gigId===id));assert(o,type+' '+id);c.camera.x=o.x;c.camera.z=o.z;c.paused=false;return o;};
 c.command=()=>{c.enter('station-interiorA');return c.point('v43CampaignConsole');};
 c.board=g=>{const z=Object.values(c.WORLD.zones).find(z=>z.district===g.district&&z.type==='social');c.enter(z.id);return c.point('v43FixerBoard');};
 c.combat=combat;c.storage=storage;c.events=events;return c;
}
function completeStory(c,m,choice=0){
 c.command();assert.equal(c.owner.accept(m.id),true);const r=c.owner.state().story[m.id];
 for(const [index,s]of m.steps.entries()){
  assert.equal(c.owner.advance(m.id),false);c.enter(s.zone);const o=c.point('v43StoryNode',m.id,index);
  if(s.kind==='channel'){assert.equal(c.owner.node(o),true);for(let i=0;i<Math.ceil(s.duration/.1);i++)c.owner.tick(.1);c.owner.tick(.01);}
  else if(['fight','boss'].includes(s.kind)){
   const qs=c.zone.robots.filter(q=>q.v43Owner===`story-${m.id}-${index}`);assert.equal(qs.length,s.kind==='boss'?1:s.count);c.owner.node(o);assert.equal(r.step,index);
   for(const q of qs){q.health=0;q.v32DownHandled=true;}c.owner.node(o);
  }else{c.owner.node(o);const callback=c.dialogue.choices[choice].action;const old=c.state;c.state=plain(old);assert.equal(callback(),false);c.state=old;assert.equal(callback(),true);assert.equal(callback(),false);}
  assert.equal(r.step,index+1,m.id+' '+index);
 }
 c.enter('port-exterior');assert.equal(c.owner.close(m.id),false);c.command();const before=c.state.credits;
 c.owner.command(c.point('v43CampaignConsole'));const callback=c.dialogue.choices.find(q=>q.tone==='remise').action;
 const old=c.state;c.state=plain(old);assert.equal(callback(),false);c.state=old;assert.equal(callback(),true);assert.equal(callback(),false);assert.equal(c.state.credits,before+m.reward);assert.equal(r.paid,true);
}
test('all six native stories and eighteen stages preserve sequential unlocks, physical evidence, choices and one reward',()=>{
 const c=fixture();c.owner.unlock();for(const m of c.owner.story)completeStory(c,m);assert.equal(c.owner.state().stats.storyClosed,6);
 const s=c.__SOMA_MISSIONS76__.snapshot();assert.equal(s.newPersistenceDomain,false);assert(s.stories.every(m=>m.paid&&m.stages.every(s=>s.knownZone)));
});
test('every authored decision branch remains valid with no invalid-choice advancement',()=>{
 for(const m of fixture().owner.story)for(const [choice]of m.steps.find(s=>s.kind==='choice').choices){
  const c=fixture(),index=m.steps.findIndex(s=>s.kind==='choice'),r=c.owner.state().story[m.id];r.status='active';r.step=index;c.enter(m.steps[index].zone);c.owner.node(c.point('v43StoryNode',m.id,index));
  assert.equal(c.owner.advance(m.id,'invented'),false);const callback=c.dialogue.choices.find(q=>q.label===m.steps[index].choices.find(x=>x[0]===choice)[1]).action;assert.equal(callback(),true);assert.equal(r.choice,choice);
 }
});
test('all sixteen native combat infiltration and recovery gigs require physical boards, objectives and one district reward',()=>{
 const c=fixture();for(const g of c.owner.gigs){
  c.command();assert.equal(c.owner.acceptGig(g.id),false);c.board(g);assert.equal(c.owner.acceptGig(g.id),true);const r=c.owner.state().gigs[g.id];assert.equal(c.owner.returnGig(g.id),false);
  c.enter(g.zone);const o=c.point('v43GigNode',g.id);if(g.type==='combat'){c.owner.gigNode(o);assert.equal(r.status,'active');for(const q of c.zone.robots)if(q.v43Owner===`gig-${g.id}`){q.health=0;q.v32DownHandled=true;}assert.equal(c.owner.gigNode(o),true);}else{assert.equal(c.owner.gigNode(o),true);for(let i=0;i<30;i++)c.owner.tick(.1);}
  assert.equal(r.status,'return');c.command();assert.equal(c.owner.closeGig(g.id),false);const o2=c.board(g);c.owner.board(o2);const callback=c.dialogue.choices.find(q=>q.tone==='remise').action,old=c.state;c.state=plain(old);assert.equal(callback(),false);c.state=old;const before=c.state.credits;assert.equal(callback(),true);assert.equal(callback(),false);assert.equal(c.state.credits,before+g.reward);assert.equal(r.paid,true);
 }
 assert.equal(c.owner.state().stats.gigsClosed,16);
});
test('native43 parent reproduces bare progression and remote hand-in defects',()=>{
 const c=fixture(true);c.owner.unlock();assert.equal(c.owner.accept('manifestes-noyes'),true);assert.equal(c.owner.advance('manifestes-noyes'),true);c.owner.advance('manifestes-noyes');c.owner.advance('manifestes-noyes','invented');assert.equal(c.owner.close('manifestes-noyes'),true);
});
test('native channels cancel death driving pause displacement and imported roots without progressing',()=>{
 for(const interrupt of [c=>c.state.health=0,c=>c.state.driving='car',c=>c.paused=true,c=>c.camera.x+=1,c=>c.state=plain(c.state),c=>c.owner.state().story=plain(c.owner.state().story)]){
  const c=fixture();c.owner.unlock();c.command();c.owner.accept('manifestes-noyes');c.enter('port-garage');c.owner.node(c.point('v43StoryNode','manifestes-noyes',0));assert(c.owner.channel());c.owner.tick(.1);interrupt(c);c.owner.tick(.1);assert.equal(c.owner.channel(),null);assert.equal(c.owner.state().story['manifestes-noyes'].step,0);
 }
});
function validator(c){
 const part=(a,b)=>{const start=source.saver.indexOf(a);assert(start>=0);return source.saver.slice(start,source.saver.indexOf(b,start+a.length));};
 c.AUX36_IDS=new Set();c.root={schema:32,gigs:{},followingGig:null,redZones:{},combat:{kills:{}},zoneCombat:{},loot:{}};
 c.k={edition:37,zones:new Set(Object.keys(c.WORLD.zones)),districts:new Set(Object.keys(c.D)),gigs:new Set(),roles:new Set(['rifle','blade','sniper','netrunner','heavy','drone']),items:new Set()};c.api=()=>({freshState:()=>c.root});
 vm.runInContext(part('const record=(v,path)=>','\nfunction enemyIdKnown(')+part('function enemyIdKnown(','\n/* 0.37 helpers inserted')+part('function validateLayer(','\nfunction validate('),c);
}
test('all fifty-five authored story gig and boss identities restore combat32 and pass the real saver37; mutations and legacy loot are bounded',()=>{
 const c=fixture();validator(c);const audit=c.__SOMA_MISSIONS76__.snapshot();assert.equal(c.__SOMA_V43__,undefined);assert.equal(audit.encounters.length,19);let count=0;
 for(const e of audit.encounters){
  c.enter(e.zone);const qs=c.owner.spawn(c.zone,e.owner,e.count,e.boss);assert.equal(qs.length,e.count);
  for(const [i,q]of qs.entries()){
   count++;assert.equal(q.id,e.enemies[i].id);assert.equal(q.v32Role,e.enemies[i].role);assert.equal(c.__SOMA_MISSIONS76__.knownEnemy(q.id,e.zone),true);assert.equal(c.__SOMA_MISSIONS76__.knownEnemy(q.id,'invented'),false);
   const record={health:i%2?0:23,maxHealth:q.maxHealth,armor:.22,state:i%2?'dead':'search',detect:.4,downHandled:!!(i%2)};c.combat.zoneCombat[e.zone]={enemies:{[q.id]:record}};c.root.zoneCombat[e.zone]={enemies:{[q.id]:record}};
   c.root.loot={['loot-'+q.id]:{zone:e.zone,role:q.v32Role==='blade'?'melee':q.v32Role,x:0,z:0,collected:true}};assert.equal(c.validateLayer(32,c.root,c.k),undefined);
   assert.equal(c.enemyIdKnown(q.id,{...c.k,edition:36},e.zone),false);c.root.loot['loot-'+q.id].zone='station-exterior';if(e.zone!=='station-exterior')assert.throws(()=>c.validateLayer(32,c.root,c.k),/Butin/);c.root.loot={};
   for(const suffix of [-1,e.count,'00','invented'])assert.equal(c.enemyIdKnown(`v43-${e.owner}-${suffix}`,c.k,e.zone),false);
   c.zone.robots=c.zone.robots.filter(x=>x.v43Owner!==e.owner);const restored=c.owner.spawn(c.zone,e.owner,e.count,e.boss).find(x=>x.id===q.id);assert.equal(restored.health,record.health);assert.equal(restored.v32DownHandled,record.downHandled);assert.equal(restored.armor,.22);assert.equal(restored.v32Role,q.v32Role);
   c.root.zoneCombat={};
  }
  for(const role of ['melee','rifle','heavy'])assert.equal(c.__SOMA_MISSIONS76__.legacyLootRole('loot-'+e.enemies[0].id,e.zone,role),null);
 }
 assert.equal(count,55);assert.equal(audit.encounters.filter(e=>e.boss).length,1);
});

test('all thirty-four source locations have authored foot approaches and hand-in routes; twenty-four repairs derive from exact existing owners',()=>{
 const c=fixture(),audit=c.__SOMA_MISSIONS76__.snapshot();assert.equal(audit.locationRepairs.length,23);
 for(const row of audit.locationRepairs){
  const [root,collection,id,...rest]=row.source.split('.');let entry=vm.runInContext(root+'.'+collection,c);entry=Array.isArray(entry)?entry.find(x=>x.id===id):entry[id];
  const zone=rest[0].startsWith('steps[')?entry.steps[Number(rest[0].match(/\d+/)[0])].zone:entry.zone;assert.equal(row.zone,zone,row.source);assert(c.WORLD.zones[row.zone]);
 }
 let stages=0;for(const m of c.owner.story){let from='station-interiorA';for(const s of m.steps){assert(c.route(from,s.zone).length>0,m.id+' '+from+' -> '+s.zone);from=s.zone;stages++;}assert(c.route(from,'station-interiorA').length>0);}
 for(const g of c.owner.gigs){const board=Object.values(c.WORLD.zones).find(z=>z.district===g.district&&z.type==='social');assert(c.route(board.id,g.zone).length>0);assert(c.route(g.zone,board.id).length>0);stages++;}
 assert.equal(stages,34);
 const m=c.owner.story.at(-1),r=c.owner.state().story[m.id];r.status='active';r.step=0;c.enter(m.steps[0].zone);const o=c.point('v43StoryNode',m.id,0);for(const q of c.zone.robots)if(q.v43Owner===`story-${m.id}-0`){q.health=0;q.v32DownHandled=true;}c.owner.node(o);assert.equal(r.step,1);assert(c.zone.interactables.some(o=>o.storyId===m.id&&o.step===1),'same-zone next channel is installed without leaving');
});
test('all fifty-five localized damage records use the same strict source identity and zone whitelist',()=>{
 const c=fixture();validator(c);for(const e of c.__SOMA_MISSIONS76__.snapshot().encounters)for(const q of e.enemies){
  const root={schema:33,territories:{},enemyParts:{[e.zone]:{[q.id]:{hp:{torso:9},max:{torso:20},disabled:[]}}},pursuit:null};c.api=()=>({freshState:()=>root});assert.equal(c.validateLayer(33,root,c.k),undefined);
  root.enemyParts['station-exterior']=root.enemyParts[e.zone];delete root.enemyParts[e.zone];assert.throws(()=>c.validateLayer(33,root,c.k),/Partie ennemie.*identifiant inconnu/);
 }
});

test('all thirteen source43 snipers and the ordinary heavy boss retain paid cooldown through real75/76 adapters, including first setup before adapter availability',()=>{
 const adapters=[['v75','combat-telegraph-runtime.js'],['v76','combat-heavy-runtime.js']];
 for(const late of [false,true]){
  const c=fixture(false,true);const install=()=>{for(const [edition,name]of adapters)vm.runInContext(fs.readFileSync(path.join(__dirname,'../../src',edition,name),'utf8'),c);};if(!late)install();let count=0;
  for(const e of c.__SOMA_MISSIONS76__.snapshot().encounters){
   const actor=e.enemies.find(q=>['sniper','heavy'].includes(q.role));if(!actor)continue;count++;c.enter(e.zone);
   const r={health:37,maxHealth:e.boss?460:125,armor:.22,state:'combat',detect:1,downHandled:false,attackClock:1.7};
   c.combat.zoneCombat[e.zone]={enemies:{[actor.id]:r}};c.zone.robots=c.zone.robots.filter(q=>q.v43Owner!==e.owner);const q=c.owner.spawn(c.zone,e.owner,e.count,e.boss).find(q=>q.id===actor.id);
   assert.equal(q.health,37);assert.equal(q.attackClock,late?.6:1.7);
  }
  assert.equal(count,14);if(late){install();c.events.get('DOMContentLoaded')();}
  for(const z of Object.values(c.WORLD.zones))for(const q of z.robots||[])if(['sniper','heavy'].includes(q.v32Role)&&c.__SOMA_MISSIONS76__.knownEnemy(q.id,z.id)){
   const r=c.combat.zoneCombat[z.id]?.enemies[q.id];if(!r)continue;assert.equal(q.attackClock,1.7);assert.equal(q.health,37);assert.equal(c.__SOMA_COMBAT75__.isPreparing(q),false);assert.equal(c.__SOMA_COMBAT76__.isPreparing(q),false);
  }
  for(const bad of [undefined,NaN,Infinity]){const e=c.__SOMA_MISSIONS76__.snapshot().encounters.find(e=>e.boss),id=e.enemies[0].id;c.enter(e.zone);c.combat.zoneCombat[e.zone]={enemies:{[id]:{health:35,attackClock:bad}}};c.zone.robots=[];assert.equal(c.owner.spawn(c.zone,e.owner,1,true)[0].attackClock,.6);}
  const e=c.__SOMA_MISSIONS76__.snapshot().encounters.find(e=>e.boss),id=e.enemies[0].id;c.enter(e.zone);c.combat.zoneCombat[e.zone]={enemies:{[id]:{health:35,attackClock:1e9}}};c.zone.robots=[];assert.equal(c.owner.spawn(c.zone,e.owner,1,true)[0].attackClock,3600);
  c.combat.zoneCombat[e.zone].enemies[id]={health:NaN,attackClock:10};c.zone.robots=[];assert.equal(c.owner.spawn(c.zone,e.owner,1,true)[0].attackClock,.6,'invalid health never restores partial record');
 }
});

test('only the proved obstructed native quay gig marker moves to bounded reachable candidates, keeping all original vehicles and other gig points',()=>{
 const c=fixture(),g=c.owner.gigs.find(g=>g.id==='port-quai-muet');c.enter(g.zone);const z=c.zone,original=c.owner.marker(z,g);
 const car={id:'port-exterior-parked-0',x:original.x,z:original.z,width:2.35,length:6.25,heading:Math.PI/2};z.vehicles=[car];const before=plain(car);let calls=0;c.v20FindFreeInteractionPoint=()=>{calls++;return calls===1?original:{x:original.x+8,z:original.z};};const next=c.owner.marker(z,g);assert.equal(calls,2);assert.equal(next.x,original.x+8);assert.deepEqual(plain(car),before);
 for(const other of c.owner.gigs.filter(x=>x.id!==g.id)){c.enter(other.zone);assert(c.owner.marker(c.zone,other));}assert.equal(calls,2);
 c.enter(g.zone);c.v20FindFreeInteractionPoint=()=>{calls++;return original;};calls=0;assert.equal(c.owner.marker(c.zone,g),null);assert.equal(calls,32);
 c.v20FindFreeInteractionPoint=()=>({x:original.x+8,z:original.z});c.owner.state().gigs[g.id].status='active';z.interactables=[];c.owner.ensure(z);assert.equal(z.interactables.find(x=>x.gigId===g.id).x,original.x+8);
});
test('native45 UI shape accepts fresh and old grouped data with only the five known tab values and rejects unknown fields before storage changes',()=>{
 const c=fixture();assert.equal(c.city.fresh().uiTab,'operations');assert.equal(c.city.normalize({...c.city.fresh(),uiTab:'fleet'}).uiTab,'fleet');assert.equal(c.city.normalize({...c.city.fresh(),uiTab:14}).uiTab,'operations');
 vm.runInContext(source.groupCore,c);const core=c.__SOMA_GROUP64_CORE__,state=c.city.state(),before=plain(state),storage=plain([...c.storage]);
 const validate=source.group.match(/for\(const\[v,m\]of Object.entries\(p.modules\)\)\{if\(v==='45'\)[\s\S]*?C.shape\(m.value,api\(v\).state\(\)\);\}/)[0];
 c.api=v=>({state:()=>state});c.C=core;
 function run(value){c.p={modules:{45:{value}}};vm.runInContext(validate,c);return value;}
 for(const tab of ['operations','calls','fleet','runs','city'])assert.equal(run({...before,uiTab:tab}).uiTab,tab);const old={...before};delete old.uiTab;assert.equal(run(old).uiTab,'operations');Object.assign(state,old);assert.equal(run({...before,uiTab:'fleet'}).uiTab,'fleet');
 for(const uiTab of [7,{},null,'invented'])assert.throws(()=>run({...before,uiTab}),/Onglet/);assert.throws(()=>run({...before,unknown45:true}),/Champ de dossier inconnu/);assert.deepEqual(plain([...c.storage]),storage);
});

test('the relocated quay marker uses the actual reachable-component20 selector and geometry57 clearance without moving the original car',()=>{
 const c=fixture();vm.runInContext(source.random+'\n'+source.placement,c);const g=c.owner.gigs.find(g=>g.id==='port-quai-muet');c.enter(g.zone);const z=c.zone,original=c.owner.marker(z,g);z.vehicles=[{id:'original-car',x:original.x,z:original.z,width:2.35,length:6.25,heading:Math.PI/2}];const before=plain(z.vehicles);
 c.blocked=(z,x,zz,r)=>Math.abs(x)+r>z.w/2||Math.abs(zz)+r>z.h/2;const next=c.owner.marker(z,g);assert(next);assert.notDeepEqual(plain(next),plain(original));assert(c.v20ReachableInteractionCells(z).some(p=>p.x===next.x&&p.z===next.z));assert.equal(c.__SOMA_V57_CORE__.circleFootprint([next.x,next.z],.55,c.__SOMA_V57_CORE__.obb(original.x,original.z,2.35,6.25,Math.PI/2,.05)),false);assert.deepEqual(plain(z.vehicles),before);
});
