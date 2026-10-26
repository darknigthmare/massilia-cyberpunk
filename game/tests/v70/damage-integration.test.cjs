'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const scripts=require('./real-gameplay-fixture.cjs'),R=require('../../src/v70/runtime.js'),A=require('../../src/v70/augmentations-core.js');
const runtime=fs.readFileSync(path.resolve(__dirname,'../../src/v70/runtime.js'),'utf8');
const part=(text,start,end)=>{assert.equal(text.split(start).length,2);return text.slice(text.indexOf(start),text.indexOf(end,text.indexOf(start)));};
const near=(a,b)=>assert(Math.abs(a-b)<1e-8,`${a} != ${b}`);

function game({factor=1,barrier=true,health=100,armor=2}={}){
  const source={id:'legacy-security',kind:'security',health:100,hostile:true,x:0,z:8,phase:1.3,arrestCooldown:0};
  const c={Math,Number,Map,Set,Object,JSON,paused:false,camera:{x:0,z:0},damageFlash:0,reducerCalls:[],traumas:[],announcements:[],downs:[],
    state:{health,armor,tension:0,recoveryGrace:0,recovery:{pending:false},police:{level:4}},
    zone:{id:'damage-qa',actors:[],animals:[],vehicles:[],robots:[source]},S:{combat:{damageTaken:0}},
    v27Stats:()=>({damageTakenMult:factor}),clamp:(n,a,b)=>Math.max(a,Math.min(b,n)),announce:(...args)=>c.announcements.push(args),
    afterDamage:(before,q,kind)=>c.traumas.push({before,after:c.state.health,q,kind}),handlePlayerDown:reason=>c.downs.push(reason),
    rng:()=>()=>1,hash:()=>0,performance:{now:()=>0},lineBlocked:()=>false,blocked:()=>false};
  c.window=c;c.__SOMA_BODY35__={afterDamage:c.afterDamage};
  let saved,energy=100;
  const controller=R.createController({read:()=>saved,write:v=>{saved=v;},context:()=>({energy,tension:c.state.tension,health:c.state.health,
    paused:c.paused,onFoot:true,channeling:false,driving:false,cyberspace:false}),
    spend(cost,tension){energy-=cost;c.state.tension+=tension;return true;},schedule:()=>{}});
  if(barrier)assert.equal(controller.activate('barrier').accepted,true);
  // The actual production setup uses this identity reducer, not a wrapper
  // around the v32 hook. Its real guard prevents charging during recovery.
  const guarded=R.wrapDamage(controller,amount=>amount,()=>!c.paused&&!c.state.recovery?.pending&&!(c.state.recoveryGrace>0));
  c.incomingReducer=n=>{c.reducerCalls.push(n);return guarded(n);};
  vm.createContext(c);
  vm.runInContext(part(runtime,'function mitigateIncoming(amount){','\n  function setup(){'),c);
  c.__SOMA_V70__={mitigateIncoming:c.mitigateIncoming};
  const main=scripts['qa-main-gameplay'];
  vm.runInContext(part(main,'function v26DamagePlayer(amount,label,source){','\nfunction v26SpawnBossMinion('),c);
  vm.runInContext(part(main,'function policeStunPlayer(source,amount=6){','\nfunction spawnRoadblock(){'),c);
  // Execute the existing body35 wrapper, including its stat multiplier and
  // no-op guards, rather than replacing police damage with the v32 path.
  vm.runInContext(part(scripts['soma-v35-body'],'const originalPolice=policeStunPlayer;','\nconst originalRecovery='),c);
  vm.runInContext(part(main,'function updateAI(dt){','\nfunction move(dt){'),c);
  vm.runInContext(part(scripts['soma-v32-patch'],'function v32DamagePlayer(amount,label,source){','\nfunction enemyMove('),c);
  return{c,source,controller,hit(owner,amount=10){
    if(owner==='v32')return c.v32DamagePlayer(amount,'physical impact',source);
    if(owner==='boss')return c.v26DamagePlayer(amount,'campaign impact',source);
    if(owner==='police')return c.policeStunPlayer(source,amount);
    return c.updateAI(.2);
  }};
}

test('all four real owners mitigate after defence and before armour exactly once',()=>{
  for(const owner of ['v32','boss','police','security'])for(const factor of [.35,1.75]){
    const g=game({factor}),raw=(owner==='security'?7:10)*factor,received=raw*.45,absorbed=raw*.55;
    const tension=g.c.state.tension;g.hit(owner);
    assert.equal(g.c.reducerCalls.length,1,owner+' reducer calls');near(g.c.reducerCalls[0],raw);
    near(g.controller.snapshot().barrierRemaining,40-absorbed);
    near(g.c.state.armor,Math.max(0,2-received));near(g.c.state.health,100-Math.max(0,received-2));
    assert.equal(g.c.traumas.length,1,owner+' body callback');
    if(owner==='v32')assert.equal(g.c.S.combat.damageTaken,Math.ceil(received));
    if(owner==='boss')near(g.c.state.tension-tension,2.5);
    if(owner==='police'){near(g.c.state.tension-tension,3);assert.equal(g.source.arrestCooldown,1.5);}
  }
});

test('the original .35/1.75 stat clamps precede the common reduction',()=>{
  for(const [factor,expected]of [[0,.35],[9,1.75]])for(const owner of ['v32','boss','police','security']){
    const g=game({factor});g.hit(owner);near(g.c.reducerCalls[0],(owner==='security'?7:10)*expected);
  }
});

test('the shared forty-point budget is spent once across four different combat owners',()=>{
  const g=game({factor:1.75,health:200,armor:10});
  g.hit('v32',20);g.hit('boss',20);g.hit('police',10);g.hit('security');
  assert.equal(g.c.reducerCalls.length,4);near(g.controller.snapshot().barrierRemaining,0);
  near(g.controller.snapshot().persisted.stats.damageAbsorbed,40);
  near(g.c.state.health,150.25);assert.equal(g.c.state.armor,0);assert.equal(g.c.traumas.length,4);
  assert.equal(g.c.S.combat.damageTaken,16);
});

test('police drones reach only the existing police kernel, not the security reduction as well',()=>{
  const g=game({armor:0});g.source.kind='policeDrone';g.source.z=1;g.hit('security');
  assert.equal(g.c.reducerCalls.length,1);near(g.c.reducerCalls[0],8);
  near(g.controller.snapshot().barrierRemaining,35.6);near(g.c.state.health,96.4);
  assert.equal(g.c.traumas.length,1);assert.equal(g.c.traumas[0].kind,'police');
});

test('existing recovery, invalid-input and cooldown guards never debit protection',()=>{
  for(const owner of ['v32','boss','police'])for(const mode of ['paused','pending','invalid','cooldown']){
    if(mode==='cooldown'&&owner!=='police')continue;
    const g=game();if(mode==='paused')g.c.paused=true;if(mode==='pending')g.c.state.recovery.pending=true;
    if(mode==='cooldown')g.source.arrestCooldown=1;
    g.hit(owner,mode==='invalid'?NaN:10);
    near(g.controller.snapshot().barrierRemaining,40);assert.equal(g.c.state.health,100);assert.equal(g.c.state.armor,2);
    assert.equal(g.c.reducerCalls.length,0);
  }
  for(const owner of ['v32','boss','security']){
    const g=game();g.c.state.recoveryGrace=2;g.hit(owner);
    near(g.controller.snapshot().barrierRemaining,40);assert.equal(g.c.reducerCalls.length,0);assert.equal(g.c.state.health,100);
  }
});

test('common reducer refuses protection charges in recovery even for direct historical-kernel calls',()=>{
  const g=game();g.c.state.recovery.pending=true;
  // This tests the reducer guard independently of the outer simulation guard;
  // it deliberately does not invent a new guard in the historical health owner.
  near(g.c.mitigateIncoming(20),20);near(g.controller.snapshot().barrierRemaining,40);
  g.c.state.recovery.pending=false;g.c.paused=true;
  near(g.c.mitigateIncoming(20),20);near(g.controller.snapshot().barrierRemaining,40);
});

test('without protection, the original police health floor and consequences remain',()=>{
  const g=game({barrier:false,health:2,armor:0});const tension=g.c.state.tension;g.hit('police',20);
  assert.equal(g.c.state.health,1);assert.equal(g.source.arrestCooldown,1.5);near(g.c.state.tension-tension,3);
  assert.equal(g.c.downs.length,0);assert.equal(g.c.traumas.length,1);assert.equal(g.c.announcements.length,1);
});
