'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const R=require('../../src/v70/runtime.js'),A=require('../../src/v70/augmentations-core.js');
function game(){
 const value={saved:undefined,energy:100,tension:0,paused:false,onFoot:true,health:100,channeling:false,driving:false,cyberspace:false,ready:true,focus:true,saves:0,debits:0};
 const controller=R.createController({read:()=>value.saved,write:p=>{value.saved=p;},
  context:()=>({energy:value.energy,tension:value.tension,health:value.health,paused:value.paused,onFoot:value.onFoot,channeling:value.channeling,driving:value.driving,cyberspace:value.cyberspace}),
  ready:()=>value.ready,focusAllowed:()=>value.focus,
  spend(cost,tension){if(value.failDebit||value.energy<cost)return false;value.energy-=cost;value.tension+=tension;value.debits++;return true;},schedule:()=>value.saves++});
 return{value,controller};
}
test('activation commits actual resources once and stores only the strict optional domain',()=>{
 const {value:v,controller:c}=game();assert.equal(v.saved.schema,A.SCHEMA);assert.equal(c.activate('barrier').accepted,true);
 assert.equal(v.energy,72);assert.equal(v.debits,1);assert.equal(v.tension,4);assert.equal(v.saves,1);
 assert.equal(v.saved.cooldowns.barrier,24);assert(!('active'in v.saved));assert.equal(A.validatePersistence(v.saved),true);
 assert.equal(c.activate('barrier').accepted,false);assert.equal(v.energy,72);assert.equal(v.debits,1);
});
test('a resource rejected at commit cannot award a buff or progress',()=>{
 const {value:v,controller:c}=game();v.failDebit=true;const before=c.snapshot();
 assert.equal(c.activate('scan').reason,'resource-changed');assert.equal(v.energy,100);assert.equal(v.saves,0);
 assert.deepEqual(c.snapshot().persisted,before.persisted);assert.deepEqual(c.snapshot().active,before.active);
});
test('blocked campaign and reduced-motion focus refuse without changing the real deck',()=>{
 const {value:v,controller:c}=game();v.ready=false;assert.equal(c.activate('scan').reason,'campaign-unavailable');
 v.ready=true;v.focus=false;assert.equal(c.activate('focus').reason,'reduced-motion');
 assert.equal(v.energy,100);assert.equal(v.debits,0);assert.equal(v.saved.stats.activations,0);
});
test('existing hacking channels refuse activation and scan does not block a later hack',()=>{
 const {value:v,controller:c}=game();v.channeling=true;assert.equal(c.activate('focus').reason,'channeling');
 v.channeling=false;c.activate('scan');assert.equal(c.modifiers().blocksHacking,false);
 c.activate('barrier');assert.equal(c.modifiers().blocksHacking,true);
});
test('cooldowns survive pause and reload while active protection never survives import',()=>{
 const {value:v,controller:c}=game();c.activate('barrier');v.paused=true;c.tick(3);assert.equal(v.saved.cooldowns.barrier,24);
 v.paused=false;c.tick(1);assert.equal(v.saved.cooldowns.barrier,23);const raw=JSON.parse(JSON.stringify(v.saved));
 c.restore(raw);assert.equal(c.snapshot().active.barrier,0);assert.equal(c.snapshot().barrierRemaining,0);
 assert.equal(c.snapshot().persisted.cooldowns.barrier,23);assert.equal(v.energy,72);
 c.restore(undefined);assert.equal(c.snapshot().persisted.stats.activations,0);assert.equal(c.modifiers().barrierActive,false);
});
test('a real damage hook receives the reduced amount, arguments and receiver',()=>{
 const {controller:c}=game();c.activate('barrier');const owner={health:100},source={id:'unit'};
 const wrapped=R.wrapDamage(c,function(amount,label,q){assert.equal(label,'impact');assert.equal(q,source);this.health-=amount;return amount;},()=>true);
 assert.equal(wrapped.call(owner,20,'impact',source),9);assert.equal(owner.health,91);
 assert.equal(c.snapshot().barrierRemaining,29);assert.equal(c.snapshot().persisted.stats.damageAbsorbed,11);
});
test('legacy recovery guards and invalid no-op amounts never spend the barrier budget',()=>{
 const {controller:c}=game();c.activate('barrier');let allowed=false,calls=0;
 const wrapped=R.wrapDamage(c,n=>{calls++;return Number.isFinite(n)&&n>0&&allowed?n:0;},()=>allowed);
 assert.equal(wrapped(20),0);assert.equal(c.snapshot().barrierRemaining,40);
 allowed=true;for(const n of [NaN,Infinity,-1,0])assert.equal(wrapped(n),0);
 assert.equal(c.snapshot().barrierRemaining,40);assert.equal(calls,5);
});
test('snapshots are defensive and leaving on-foot gameplay cancels effects without refund',()=>{
 const {value:v,controller:c}=game();c.activate('focus');const s=c.snapshot();s.active.focus=999;s.persisted.cooldowns.focus=0;
 assert.equal(c.snapshot().active.focus,5);v.driving=true;c.tick(.1);assert.equal(c.modifiers().focusActive,false);
 assert(v.saved.cooldowns.focus>19);assert.equal(v.energy,76);
});

function key(extra={}){return{code:'F2',shiftKey:true,prevented:false,stopped:false,preventDefault(){this.prevented=true;},stopImmediatePropagation(){this.stopped=true;},...extra};}
test('a refused tactical chord in driving, cyberspace or pause cannot consume the legacy F2 object',()=>{
 for(const mode of ['driving','cyberspace','paused']){
  const {value:v,controller:c}=game();v[mode]=true;if(mode!=='paused')v.onFoot=false;
  let patches=1,result=null;const event=key();
  assert.equal(R.handleShortcut(event,{hasZone:true,togglePanel(){},activate:id=>{result=c.activate(id);}}),true);
  if(!event.stopped&&!v.paused)patches--;
  assert.equal(patches,1);assert.equal(result.accepted,false);assert.equal(v.energy,100);assert.equal(v.debits,0);
  assert(event.prevented&&event.stopped);
 }
});
test('plain F2 still reaches its legacy action while shifted F2 activates only the implant',()=>{
 const {value:v,controller:c}=game();let patches=1,panels=0;
 const actions={hasZone:true,togglePanel:()=>panels++,activate:id=>c.activate(id)};
 const plain=key({shiftKey:false});assert.equal(R.handleShortcut(plain,actions),false);if(!plain.stopped)patches--;
 assert.equal(patches,0);assert.equal(v.energy,100);
 const shifted=key();assert.equal(R.handleShortcut(shifted,actions),true);assert.equal(v.energy,88);assert.equal(v.debits,1);
 R.handleShortcut(key({code:'F1'}),actions);assert.equal(panels,1);
});
test('owned chords in editable controls do not activate or fall through; unrelated shortcuts stay free',()=>{
 let calls=0;const actions={hasZone:true,togglePanel:()=>calls++,activate:()=>calls++};
 const editing=key({target:{closest:()=>({})}});assert.equal(R.handleShortcut(editing,actions),true);assert(editing.stopped);assert.equal(calls,0);
 for(const extra of [{ctrlKey:true},{altKey:true},{metaKey:true},{repeat:true},{code:'F5'}]){
  const event=key(extra);assert.equal(R.handleShortcut(event,actions),false);assert.equal(event.stopped,false);
 }
 assert.equal(calls,0);
});
