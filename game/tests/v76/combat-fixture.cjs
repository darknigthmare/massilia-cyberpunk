/* Real delivered owners; only geometry/resources are qualified test fixtures. */
'use strict';
const path=require('node:path'),cp=require('node:child_process'),vm=require('node:vm'),fs=require('node:fs');
const game=path.resolve(__dirname,'../..');
const scripts=JSON.parse(cp.execFileSync('python3',['-c',String.raw`
import json,re,sys
from pathlib import Path
game=Path(sys.argv[1]);sys.path.insert(0,str(game))
from tools.v76_combat import patch_html,MODULES
parent=(game/'SOMA_MASSILIA_URBAIN_v0_75.html').read_text()
patched=patch_html(parent,{name:(game/f'src/v76/{name}.js').read_text() for name in MODULES})
ids={'v32':'soma-v32-patch','v33':'soma-v33-patch','v42':'soma-v42-recovery','city':'soma-v45-city',
 'persistence':'soma-v37-persistence','perception':'soma-v70-perception-runtime','radio':'soma-v72-contact-sharing-runtime',
 'neural':'soma-v72-netrunner-runtime','medical':'soma-v74-combat-support-runtime','sniper':'soma-v75-combat-telegraph-runtime','legacy':'soma-v71-legacy-perception-runtime','runtime':'soma-v76-combat-heavy-runtime',
 'echo':'soma-v73-tactical-runtime','sight':'soma-v61-sight-core','sightRuntime':'soma-v61-sight-runtime'}
def script(text,name):return re.search(r'<script\b[^>]*id="'+name+r'"[^>]*>([\s\S]*?)</script>',text)[1]
out={key:script(patched,value) for key,value in ids.items()}
out['before32']=script(parent,ids['v32'])
out['beforePerception']=script(parent,ids['perception'])
out['beforeLegacy']=script(parent,ids['legacy'])
out['consumable']=parent[parent.index('function v28UseConsumable('):parent.index('function v28Rest()')]
out['before75']=script(parent,ids['sniper'])
a=patched.index('function loop(t){');out['loop']=patched[a:patched.index('function controls(){',a)]
print(json.dumps(out))
`,game],{encoding:'utf8',maxBuffer:8*1024*1024}));
const part=(text,start,end)=>{const a=text.indexOf(start);if(a<0)throw Error('Missing fixture anchor '+start);const b=text.indexOf(end,a+start.length);if(b<0)throw Error('Missing fixture end '+end);return text.slice(a,b);};
function element(tag){return {tag,children:[],hidden:false,textContent:'',style:{},attrs:{},
 setAttribute(k,v){this.attrs[k]=v;},appendChild(x){this.children.push(x);return x;},replaceChildren(){this.children=[];},
 getBoundingClientRect(){return {left:0,top:0,width:196,height:96};}};}
function context(role='heavy',before=false){
 const c={Math,Map,Set,Object,JSON,Number,String,Date,performance:{now:()=>c.now},now:1000,camera:{x:0,z:0,y:1.72,yaw:0,pitch:0},
  state:{health:100,armor:0,tension:0,settings:{volume:0,reduceMotion:true,largeText:true,fov:67},statistics:{shots:0}},
  zone:{id:'qa-combat75',district:'qa',robots:[],v32CoverPoints:[],colliders:[]},keys:new Set(),paused:false,cyber:false,
  S:{status:{jammed:0,suppressed:0},combat:{damageTaken:0,headshots:0},lastShotAt:-999,zoneCombat:{}},
  headingVec:h=>({x:Math.sin(h),z:Math.cos(h)}),clamp:(n,a,b)=>Math.max(a,Math.min(b,n)),
  blocked:()=>true,onEnemyDown:()=>{},snapshotCombatMaybe:()=>{},save32:()=>{},v32RaiseAlarm:()=>{},spawnReinforcements:()=>{},
  announcements:[],announce:(...args)=>c.announcements.push(args),handlePlayerDown:()=>{},deck:{hacks:{},cyberdeck:{energy:73}},
  innerWidth:1280,innerHeight:720,document:{hidden:false,head:element('head'),body:element('body'),createElement:element,getElementById:()=>null,querySelectorAll:()=>[]},
  __SOMA_V42__:{isCrouched:()=>false,state:()=>c.deck,canUseOnFoot:()=>true,isMachine:()=>false},
  __SOMA_V70__:{modifiers:()=>({scanActive:true})},v27IsCyber:()=>c.cyber,
  D:{qa:{cBase:[.2,.2,.2],cAccent:[.5,.4,.3]}},C:{mix:a=>a},enemyPoint:(z,index)=>({x:index*3,z:20})};
 c.window=c;vm.createContext(c);vm.runInContext(scripts.sight,c);
 // Actual sight61 slab rays against explicitly synthetic, mutable wall boxes.
 c.walls=[];c.rays=[];
 c.lineBlocked=(x,z,tx,tz)=>{const from=[x,1.45,z],to=[tx,1.72,tz],d=to.map((v,i)=>v-from[i]),n=Math.hypot(...d);return c.walls.some(w=>c.__SOMA_SIGHT61_CORE__.box(from,d.map(v=>v/n),w.lo,w.hi,n)!==null);};
 vm.runInContext(scripts.v32.match(/const ARCHETYPES=\{[\s\S]*?\n\};/)[0],c);
 vm.runInContext(part(scripts.v32,'function makeEnemy(z,','function restoreEnemy('),c);
 c.archetypes=vm.runInContext('ARCHETYPES',c);c.__SOMA_V32__={archetypes:c.archetypes,zoneCombatState:c.zoneCombatState,getState:()=>c.S};
 c.spawn=(nextRole=role,x=0,z=20,index=c.zone.robots.length)=>{const q=c.makeEnemy(c.zone,null,null,nextRole,index,{id:'v32-qa-'+nextRole+'-'+index});
  Object.assign(q,{x,z,homeX:x,homeZ:z,heading:Math.atan2(-x,-z),state:'patrol',detect:0,attackClock:0,v33Faction:'palimpseste'});c.zone.robots.push(q);return q;};
 c.q=c.spawn(role,0,role==='heavy'?15:20);
 vm.runInContext(fs.readFileSync(path.join(game,'src/v70/infiltration-core.js'),'utf8'),c);
 vm.runInContext(scripts.radio,c);vm.runInContext(before?scripts.beforePerception:scripts.perception,c);
 vm.runInContext(scripts.neural,c);vm.runInContext(scripts.medical,c);vm.runInContext(scripts.sniper,c);if(!before)vm.runInContext(scripts.runtime,c);
 vm.runInContext(part(scripts.v32,'function v32DamagePlayer(','function v32RaiseAlarm('),c);
 vm.runInContext(part(before?scripts.before32:scripts.v32,'function v32UpdateEnemies(dt){','\nlet snapshotClock=0;'),c);
 c.api=c.__SOMA_COMBAT76__;c.tick=(n=1,dt=.1)=>{for(let i=0;i<n;i++)c.v32UpdateEnemies(dt);};
 c.acquire=()=>{for(let i=0;i<30&&!c.__SOMA_PERCEPTION70__.observer(c.q.id)?.canAttack;i++)c.tick();};
 c.start=()=>{c.acquire();for(let i=0;i<4&&!c.api.snapshot().activeChannels;i++)c.tick();};
 c.cover=()=>c.walls.push({lo:[-2,0,8],hi:[2,4,10]});
 c.consume=()=>{c.stock={consumables:{smokeCapsule:1},stats:{consumablesUsed:0}};c.v28State=()=>c.stock;c.save=()=>{};vm.runInContext(scripts.consumable,c);return c.v28UseConsumable('smokeCapsule');};
 c.hud=()=>c.document.body.children.find(x=>x.id==='v72-netrunner-hud');
 c.saveOwners=()=>{vm.runInContext(part(scripts.v32,'function restoreEnemy(q,','function redZoneState('),c);
  vm.runInContext(part(scripts.v33,'function serializeEnemy(q){','function snapshotTerritoryRuntime('),c);
  vm.runInContext(part(scripts.v33,'function restoreRoster(z,t){','function safeEnemyPoint('),c);
  c.finite=n=>Number.isFinite(n)?n:0;c.safeEnemyPoint=(z,q)=>q;};
 c.tactics=()=>{
  c.zone.w=108;c.zone.h=84;c.zone.v32CoverPoints=[{x:0,z:26}];c.S.stats={coverMoves:0,flanks:0};
  c.finite=n=>Number.isFinite(n)?n:0;c.ARCH=c.archetypes;
  c.activeEnemies=()=>c.zone.robots.filter(q=>q.v32Enemy&&q.health>0);
  // The tested path/capsule geometry is a qualified empty room plus wall boxes.
  // Body damage modifiers, chatter and boss effects are outside this scenario.
  c.blocked=(zone,x,z,r=.38)=>c.walls.some(w=>x+r>w.lo[0]&&x-r<w.hi[0]&&z+r>w.lo[2]&&z-r<w.hi[2]);
  c.applyPartEffects=()=>{};c.bossModifierTick=()=>{};c.combatChatter=()=>{};
  vm.runInContext(part(scripts.v33,'function segmentClear(','function escortTick('),c);
  vm.runInContext(part(scripts.v33,'let tacticClock=0,chatterClock=0;','\n/* soma-v36-boss-hooks */'),c);
  c.tick=(n=1,dt=.1)=>{for(let i=0;i<n;i++){c.preTactics(dt);c.v32UpdateEnemies(dt);c.postTactics(dt);}};
 };
 return c;
}
module.exports={scripts,part,context,element};
