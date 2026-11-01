'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm');
const scripts=require('./tactical-fixture.cjs'),R=require('../../src/v70/runtime.js'),A=require('../../src/v70/augmentations-core.js');
const plain=x=>JSON.parse(JSON.stringify(x));
function element(tag){return {tag,children:[],hidden:false,textContent:'',attrs:{},style:{},
 setAttribute(k,v){this.attrs[k]=v;},appendChild(x){x.parentElement=this;this.children.push(x);return x;}};}
function context({ngf=false}={}){
 const q={id:'unit:1',v32Enemy:true,v32Role:'netrunner',v32Label:'Tisseur local',health:41,maxHealth:82,x:0,z:10,y:-9000};
 const c={Math,Map,Set,Object,JSON,Number,String,camera:{x:0,y:ngf?101.72:1.72,z:0,yaw:0,pitch:0},innerWidth:1200,innerHeight:800,
  state:{health:100,armor:30,tension:0,settings:{fov:67,largeText:false},statistics:{shots:0}},zone:{id:'scan-qa',robots:[q]},paused:false,
  deck:{cyberdeck:{energy:100}},lineBlocked:()=>c.blocked,blocked:false,v27IsCyber:()=>c.cyber||false};
 const body=element('body'),head=element('head'),slot=element('section'),canvas=element('canvas');canvas.id='gl';
 canvas.getBoundingClientRect=()=>({left:20,top:10,width:1160,height:780});body.appendChild(slot);body.appendChild(canvas);
 const find=(node,id)=>node.id===id?node:node.children.map(x=>find(x,id)).find(Boolean);
 c.document={hidden:false,body,head,createElement:element,getElementById:id=>find(body,id)||find(head,id),querySelector:selector=>selector==='[data-v72-hud-slot="combat"]'?slot:null};
 c.__SOMA_V42__={canUseOnFoot:()=>!c.state.driving&&!c.cyber,state:()=>c.deck};
 c.controller=R.createController({read:()=>c.state.v70,write:v=>{c.state.v70=v;},
  context:()=>({energy:c.deck.cyberdeck.energy,tension:c.state.tension,health:c.state.health,paused:c.paused,
    onFoot:true,channeling:false,driving:!!c.state.driving,cyberspace:!!c.cyber}),
  spend(cost,tension){c.deck.cyberdeck.energy-=cost;c.state.tension+=tension;return true;},schedule:()=>{}});
 c.__SOMA_V70__={modifiers:c.controller.modifiers};c.window=c;c.root=c;
 if(ngf)c.__SOMA_SIGHT61__={activeFor:()=>true,eyePoint:(x,z,zone,height)=>[x,100+height,z],between:(a,b)=>{c.ray={a,b};return c.blocked;}};
 vm.createContext(c);
 c.V42_HUMAN_ROLES=new Set(['rifle','melee','sniper','netrunner']);
 const machineStart=scripts.v42.indexOf('function v42Machine(q){'),machineEnd=scripts.v42.indexOf('function v42Supports(',machineStart);
 vm.runInContext(scripts.v42.slice(machineStart,machineEnd),c);c.__SOMA_V42__.isMachine=c.v42Machine;
 vm.runInContext(scripts.runtime,c);
 const a=scripts.owner.indexOf('  function scan(){'),b=scripts.owner.indexOf('  function open(){',a);
 vm.runInContext(scripts.owner.slice(a,b),c);c.api=c.__SOMA_TACTICAL73__;c.q=q;
 c.activate=()=>c.controller.activate('scan');c.read=()=>plain(c.scan());c.maintain=()=>c.api.maintain();
 c.tick=(seconds)=>c.controller.tick(seconds);return c;
}
const markers=c=>c.document.getElementById('v73-tactical-markers').children.filter(x=>!x.hidden);

test('the real paid Écho acquires frontal bodies, publishes tactical advice, and never mutates combat',()=>{
 const c=context(),unit=plain(c.q),health=c.state.health;assert.deepEqual(c.read(),[]);
 assert.equal(c.activate().accepted,true);assert.equal(c.deck.cyberdeck.energy,88);assert.equal(c.state.v70.cooldowns.scan,12);
 assert.equal(c.state.v70.stats.scan,1);assert.equal(c.controller.snapshot().active.scan,5);
 const rows=c.read();assert.equal(rows.length,1);assert.equal(rows[0].healthPercent,50);assert.equal(rows[0].roleLabel,'Intrusion neurale');
 assert.equal(rows[0].electronic,false);assert.match(rows[0].hint,/Touchez le tisseur/);c.maintain();assert.equal(markers(c).length,1);
 assert.match(markers(c)[0].children[0].textContent,/Tisseur local/);assert.match(markers(c)[0].children[1].textContent,/50 %/);
 assert.equal(c.document.getElementById('v73-tactical-hud').attrs['aria-live'],'polite');
 assert.deepEqual(plain(c.q),unit);assert.equal(c.state.health,health);assert.equal(c.state.armor,30);assert.equal(c.state.statistics.shots,0);
 assert.equal(c.activate().accepted,false);assert.equal(c.deck.cyberdeck.energy,88);
});

test('NGF bodies use sight61.eyePoint, absolute camera.y, and positive yaw/pitch without NPC y offsets',()=>{
 const c=context({ngf:true});c.lineBlocked=()=>{throw Error('NGF scan must use the 3D ray');};c.activate();assert.equal(c.read().length,1);
 assert.deepEqual(plain(c.ray.a),[0,101.72,0]);assert.deepEqual(plain(c.ray.b),[0,101.45,10]);
 c.q.x=10;c.q.z=0;c.camera.yaw=Math.PI/2;assert.equal(c.read().length,1);
 c.camera.yaw=-Math.PI/2;assert.equal(c.read().length,0);
 c.camera.yaw=Math.PI/2;c.camera.y=91.45;c.camera.pitch=Math.PI/4;assert.equal(c.read().length,1);
 c.camera.pitch=-Math.PI/4;assert.equal(c.read().length,0);
 c.camera.yaw=0;c.camera.pitch=0;c.camera.y=101.72;c.q.x=0;c.q.z=10;
 c.__SOMA_SIGHT61__.eyePoint=()=>null;assert.equal(c.read().length,0);
});

test('markers disappear immediately behind obstacles, offscreen, out of range or outside the current FOV',()=>{
 const c=context({ngf:true});c.activate();c.read();c.maintain();assert.equal(markers(c).length,1);
 for(const change of [()=>{c.blocked=true;},()=>{c.camera.yaw=Math.PI;},()=>{c.q.z=25;},()=>{c.camera.pitch=1.4;},()=>{c.q.hidden=true;}]){
  c.blocked=false;c.camera.yaw=0;c.camera.pitch=0;c.q.z=10;c.q.hidden=false;c.read();change();c.maintain();
  assert.equal(c.api.snapshot().visibleTargets,0);assert.equal(markers(c).length,0);
 }
 c.q.hidden=false;c.camera.pitch=0;c.q.z=10;c.q.x=8;c.camera.yaw=0;c.blocked=false;
 c.currentFovRadians=()=>.4;assert.equal(c.read().length,0);c.currentFovRadians=()=>1.8;assert.equal(c.read().length,1);
});

test('flat authored zones retain the actual legacy LOS owner and ignore local NPC y',()=>{
 const c=context();c.activate();assert.equal(c.read().length,1);c.blocked=true;c.maintain();assert.equal(c.api.snapshot().visibleTargets,0);
 c.blocked=false;c.q.v32Role='drone';assert.equal(c.read()[0].electronic,true);assert.equal(c.read()[0].roleLabel,'Drone de combat');
});

test('the original paused render loop clears readouts before any early return',()=>{
 const c=context();c.activate();c.read();c.maintain();c.paused=true;c.last=0;c.frameDebt=0;c.renderer={};c.requestAnimationFrame=()=>{};
 c.__SOMA_PERF65__={gate:{shouldRender:()=>false},stats:{simulationSteps:0}};c.currentWeather=()=>({});c.devicePixelRatio=1;
 vm.runInContext(scripts.loop,c);c.loop(1000);assert.equal(c.api.snapshot().visibleTargets,0);assert.equal(markers(c).length,0);
 assert.equal(c.document.getElementById('v73-tactical-hud').hidden,true);assert.equal(c.controller.snapshot().active.scan,5);
 c.tick(3);assert.equal(c.controller.snapshot().active.scan,5);assert.equal(c.state.v70.cooldowns.scan,12);
});

test('death, driving, cyber, recovery, hidden document and context changes erase tracked identities',()=>{
 for(const change of [c=>{c.state.health=0;},c=>{c.state.driving='car';},c=>{c.cyber=true;},c=>{c.state.recovery={pending:true};},
  c=>{c.state.recoveryGrace=1;},c=>{c.document.hidden=true;},c=>{c.zone={...c.zone};},c=>{c.zone.id='new-cell';},c=>{c.state={...c.state};}]){
  const c=context();c.activate();c.read();c.maintain();change(c);c.maintain();assert.equal(c.api.snapshot().visibleTargets,0);assert.equal(markers(c).length,0);
 }
 for(const change of [c=>{c.zone.robots=[{...c.q}];},c=>{c.q.id='other';},c=>{c.q.health=0;},c=>{c.zone.robots=[];}]){
  const c=context();c.activate();c.read();change(c);assert.equal(c.api.snapshot().visibleTargets,0);
 }
});

test('five seconds, cooldowns, import and strict core.v70 persistence remain owned by the existing controller',()=>{
 const c=context();c.activate();c.read();c.tick(3);assert.equal(c.read().length,1);c.tick(2);c.maintain();
 assert.equal(c.controller.modifiers().scanActive,false);assert.equal(c.api.snapshot().visibleTargets,0);assert.equal(markers(c).length,0);
 assert.equal(c.state.v70.cooldowns.scan,7);assert.equal(c.deck.cyberdeck.energy,88);assert.equal(A.validatePersistence(c.state.v70),true);
 assert(!JSON.stringify(c.state).includes('v73'));assert(!('active'in c.state.v70));
 const restored=context();restored.activate();restored.read();const raw=plain(restored.state.v70);restored.controller.restore(raw);restored.maintain();
 assert.equal(restored.api.snapshot().visibleTargets,0);assert.equal(restored.state.v70.cooldowns.scan,12);assert.equal(restored.state.v70.stats.scan,1);
 assert(scripts.perception.includes('root.__SOMA_NETRUNNER72__?.reset?.();root.__SOMA_TACTICAL73__?.reset?.();'));
 assert(scripts.owner.includes('scanTargets:scan().map(v=>({...v}))'));
});

test('candidate/target/marker budgets are bounded, markup is text, and marker cards do not overlap',()=>{
 const c=context();c.zone.robots=Array.from({length:300},(_,i)=>({...c.q,id:'unit:'+String(i).padStart(3,'0'),x:(i%8-3.5)*1.2,z:9+Math.floor(i/8)*.08}));
 c.zone.robots[0].v32Label='<img src=x onerror=alert(1)>';let rays=0;c.lineBlocked=()=>{rays++;return false;};
 c.activate();const rows=c.read();assert.equal(rays,128);assert.equal(rows.length,8);c.maintain();assert(markers(c).length<=4);assert(markers(c).length>0);
 assert.equal(c.api.snapshot().maxCandidates,128);assert.equal(c.api.snapshot().maxMarkers,4);
 const boxes=markers(c).map(n=>({left:parseFloat(n.style.left),top:parseFloat(n.style.top),right:parseFloat(n.style.left)+196,bottom:parseFloat(n.style.top)+88}));
 for(let i=0;i<boxes.length;i++)for(let j=i+1;j<boxes.length;j++)assert(!(boxes[i].left<boxes[j].right&&boxes[i].right>boxes[j].left&&boxes[i].top<boxes[j].bottom&&boxes[i].bottom>boxes[j].top));
 assert(markers(c).every(n=>n.children.length===3));
});

test('the unchanged action handler preserves all four consumables and pays once for the existing shifted scan',()=>{
 const c=context();let plainActions=0;const actions={hasZone:true,togglePanel(){},activate:id=>c.controller.activate(id)};
 for(const code of ['F1','F2','F3','F4']){
  const event={code,shiftKey:false,preventDefault(){},stopImmediatePropagation(){throw Error('plain F keys remain legacy');}};
  if(!R.handleShortcut(event,actions))plainActions++;
 }
 assert.equal(plainActions,4);const chord={code:'F2',shiftKey:true,preventDefault(){},stopImmediatePropagation(){}};
 assert.equal(R.handleShortcut(chord,actions),true);assert.equal(c.deck.cyberdeck.energy,88);assert.equal(c.read().length,1);
 assert.equal(R.handleShortcut({...chord,repeat:true},actions),false);assert.equal(c.state.v70.stats.scan,1);
});

test('long labels and large text reserve measured rectangles and avoid the real HUD panels',()=>{
 const c=context();c.q.v32Label='Très longue identité de terrain '.repeat(4);c.state.settings.largeText=true;c.activate();c.read();c.maintain();
 const measured={width:196,height:192};
 for(const marker of c.document.getElementById('v73-tactical-markers').children)marker.getBoundingClientRect=()=>measured;
 const reserved={left:680,right:1180,top:100,bottom:790,width:500,height:690};
 c.document.querySelectorAll=()=>[{hidden:false,getBoundingClientRect:()=>reserved}];c.maintain();
 assert.equal(markers(c).length,1);const node=markers(c)[0],left=parseFloat(node.style.left),top=parseFloat(node.style.top);
 assert(left+196<reserved.left);assert(top>=22);assert(top+192<=778);
 assert.equal(c.document.getElementById('v73-tactical-markers').attrs['data-large-text'],'true');
 assert.equal(c.document.getElementById('v73-tactical-hud').attrs['data-large-text'],'true');
 assert.match(node.children[0].textContent,/Très longue identité/);
 c.document.querySelectorAll=()=>[{hidden:false,getBoundingClientRect:()=>({left:0,top:0,right:1200,bottom:800,width:1200,height:800})}];
 c.maintain();assert.equal(markers(c).length,0,'a card with no free space yields to the HUD');
});


test('electronic classification delegates to the actual v42 owner, including human security guards',()=>{
 const c=context();c.activate();c.q.kind='security';c.q.v32Role='rifle';assert.equal(c.read()[0].electronic,false);
 c.q.v32Role='netrunner';assert.equal(c.read()[0].electronic,false);c.q.v32Role='drone';assert.equal(c.read()[0].electronic,true);
});


test('the screen reader summary stays outside HUD grid flow while the existing count remains visible',()=>{
 const c=context();c.activate();c.read();c.maintain();
 const summary=c.document.getElementById('v73-tactical-hud');assert.equal(summary.parentElement,c.document.body);
 assert.equal(summary.attrs.role,'status');assert.equal(summary.attrs['aria-live'],'polite');assert.match(summary.textContent,/ÉCHO · 1 unité visible/);
 assert.equal(c.document.querySelector('[data-v72-hud-slot="combat"]').children.length,0,'the adapter adds no grid row');
 const css=c.document.getElementById('soma-v73-tactical-style').textContent;
 assert.match(css,/#v73-tactical-hud\{position:fixed;[^}]*width:1px;height:1px/);
 c.paused=true;c.maintain();assert.equal(summary.hidden,true);
});
