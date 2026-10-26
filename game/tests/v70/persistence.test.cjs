'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {spawnSync}=require('node:child_process');
const baseline=path.resolve(__dirname,'../../baseline/v66.html');
const originalHTML=fs.readFileSync(baseline,'utf8');
const original=originalHTML.match(/<script\b[^>]*\bid="soma-v37-persistence"[^>]*>([\s\S]*?)<\/script>/)[1];
const augSource=fs.readFileSync(path.resolve(__dirname,'../../src/v70/augmentations-core.js'),'utf8');
function patch(source){
 const python=process.env.PYTHON||(process.platform==='win32'?'python':'python3');
 return spawnSync(python,['-c','import sys; sys.path.insert(0,sys.argv[1]); from v68_persistence import patch_persistence as previous; from v70_persistence import patch_persistence; sys.stdout.write(patch_persistence(previous(sys.stdin.read())))',path.resolve(__dirname,'../../tools')],{input:source,encoding:'utf8'});
}
const patchedResult=patch(original);assert.equal(patchedResult.status,0,patchedResult.stderr);
const patched=patchedResult.stdout;

function game(source) {
  const context = vm.createContext({console, performance: {now: () => 0},
    setTimeout() {}, queueMicrotask() {}, URL, Blob});
  vm.runInContext(`
    const clone=v=>JSON.parse(JSON.stringify(v));
    const localStorage={getItem(){return null},setItem(){},removeItem(){}};
    const window={__SOMA_DEBUG__:true,addEventListener(){}};
    const document={readyState:'loading',addEventListener(){},getElementById(){return null},body:{classList:{remove(){}}}};
    const keys=new Set(),touches=new Set();
    let spectre=false,fireCD=0,reloadLeft=0,recoil=0,muzzle=0,frameDebt=0,dialogueRevealToken=0,activeDialogue=null;
    const WORLD={zones:{'station-exterior':{}}},D={port:{}},WEAPONS=[{id:'pistol'}],WEATHER=[{}],CONTRACTS=[];
    const V27_EQUIPMENT={},V27_CHIPS={},V27_MODS={},V27_TALENTS={},V27_DATA={programs:[]},V25_DATA={order:[]};
    const V29_ITEM_IDS=new Set(),V29_BLUEPRINT_IDS=new Set(),V29_CONTAINER_IDS=new Set(),V29_EVENT_IDS=new Set();
    const shapes={
      30:{schema:30,inventory:{},durability:{},activeWeapon:'pistol',selectedItem:null,events:{},consequences:{},worldDrops:[],workshop:[]},
      31:{schema:31,items:{equipment:{},chips:{}},jobs:{},vehicles:{},market:{offers:{}},seized:[]},
      32:{schema:32,gigs:{},followingGig:null,redZones:{},combat:{kills:{}},zoneCombat:{},loot:{}},
      33:{schema:33,territories:{},enemyParts:{},pursuit:null}
    };
    for(const n of [30,31,32,33]){
      shapes[n].ui={open:false};
      let data=clone(shapes[n]);
      window['__SOMA_V'+n+'__']={freshState:()=>clone(shapes[n]),getState:()=>data,replaceState:v=>{data=v},
        snapshotCombat(){},captureRuntime(){},ensureRecords(){},itemDefs:{},weapons:['pistol'],events:{},jobs:{},markets:{},archetypes:{},gigs:[],factions:{}};
    }
    const domainNames=['BODY35','INFRA35','STORIES35','CHARACTERS35','COMMERCE36','BOSSES36','STORIES37','JUSTICE37'];
    for(const name of domainNames)window['__SOMA_'+name+'__']={fresh:()=>({}),normalize:clone,validate(){},getState:()=>({}),validateEnvelope(){}};
    let state={schema:'soma-urban/29',zone:'station-exterior',x:1,z:2,yaw:0,pitch:0,health:100,armor:0,debt:0,memory:0,tension:0,
      credits:25,time:8,weather:0,weapon:0,ammo:{pistol:{mag:1,reserve:2}},unlocked:['pistol'],settings:{sensitivity:.58,volume:.8,fov:67,v67Density:'standard'},
      city:{day:1},reputation:{},contracts:{},campaign25:{completed:[],unlocked:[],progress:{},active:null},campaign26:{plans:{},debriefs:{},bosses:{}},
      player27:{inventory:{equipment:[],chips:[],mods:[],programs:[]},talents:{},equipment:{},installedChips:[],weaponTiers:{},weaponMods:{},cyberdeck:{programs:[],selected:null}},
      player28:{},player29:{items:{},stash:{items:{}},blueprints:[],containers:{},events:{},weaponLoadout:['pistol']},
      v35Body:{},v35Infrastructure:{},v35Stories:{},v35Characters:{},v36Commerce:{},v36Bosses:{},v37Stories:{},v37Justice:{}};
    let zone=WORLD.zones['station-exterior'];
    const camera={x:1,z:2,yaw:0,pitch:0};
    const robustNormalize=clone,snapshotSave=()=>clone(state);
    function applySettings(){}
    function enterZone(id){zone=WORLD.zones[id];return !!zone}
    function stateValue(){return state}
    function addWorld(){state.v67={schema:'soma-v67/1',districtVisits:{port:7},conversations:{'civil:port-1':3},ambientSeen:{'port:rain':1},lastDistrict:'port'}}
  `, context);
  vm.runInContext(source, context, {filename: 'soma-v37-persistence.js'});
  return {context, run: code => vm.runInContext(code, context)};
}

function current(){
 const exposed=patched.replace('publicAPI.test={packagePayload,','publicAPI.test={validateCore37,packagePayload,');
 assert.notEqual(exposed,patched);
 const g=game(exposed);
 vm.runInContext(augSource,g.context,{filename:'augmentations-core.js'});
 g.run(`const A=globalThis.__SOMA_AUG70_CORE__;window.__SOMA_AUG70_CORE__=A;
   const P=window.__SOMA_V37_SAVE__;
   const activationContext={energy:100,health:100,onFoot:true,paused:false,channeling:false,driving:false,cyberspace:false,tension:0};
   let live=A.activate(A.initial(),'barrier',activationContext).state;
   let restored=[];
   window.__SOMA_V70__={restoreCampaign(raw){live=A.restore(raw);restored.push({absent:raw===undefined,driving:state.driving,lastOnFoot:state.lastOnFoot})}};`);
 return g;
}

test('the actual full saver round-trips cooldowns/trace/statistics and always clears active buffs',()=>{
 const g=current();
 g.run(`state.v70=A.serialize(live);const checkpoint=P.snapshot();P.validate(checkpoint);
   const before=JSON.stringify(checkpoint);state.v70.cooldowns.barrier=1;state.credits=0;P.test.applyEnvelope(checkpoint);`);
 assert.equal(g.run('state.credits'),25);
 assert.equal(g.run('state.v70.cooldowns.barrier'),24);
 assert.equal(g.run('live.cooldowns.barrier'),24);
 assert.equal(g.run('live.trace'),32);
 assert.equal(g.run('live.stats.barrier'),1);
 assert.equal(g.run('live.active.barrier'),0);
 assert.equal(g.run('live.barrierRemaining'),0);
 assert.equal(g.run('Object.hasOwn(checkpoint.payload.core.v70,"active")'),false);
 assert.equal(g.run('JSON.stringify(checkpoint)===before'),true);
 assert.equal(g.run('restored.length'),1);
 assert.equal(g.run('restored[0].driving===null&&restored[0].lastOnFoot===null'),true);
});

test('legacy campaigns without v70 remain valid and reset an already active augmentation',()=>{
 const g=current();
 g.run('const legacy=P.snapshot();P.validate(legacy);P.test.applyEnvelope(legacy);');
 assert.equal(g.run('Object.hasOwn(state,"v70")'),false);
 assert.equal(g.run('restored[0].absent'),true);
 assert.equal(g.run('live.active.barrier'),0);
 assert.equal(g.run('live.cooldowns.barrier'),0);
 assert.equal(g.run('live.trace'),0);
 assert.equal(fs.readFileSync(baseline,'utf8'),originalHTML);
});

test('only optional core v70 on edition37 is admitted, while future domains remain rejected',()=>{
 for(const key of ['v68','v69','v71','player70','campaign70']){
  const g=current();g.run(`state[${JSON.stringify(key)}]={}`);
  assert.throws(()=>g.run('P.snapshot()'),/incompatible/);
 }
 const g=current();g.run('state.v70=A.serialize(A.initial());');
 for(const edition of [34,35,36,38,70])assert.throws(()=>g.run(`P.test.validateCore37(state,${edition})`),/Personnage.v70.*incompatible/);
 g.run('P.test.validateCore37(state,37)');
});

test('semantic invalidity, unknown keys and active timer persistence are refused by the real saver',()=>{
 const edits=[
  'state.v70=null','state.v70=[]','state.v70.schema="soma-massilia/augmentations/2"',
  'state.v70.selected="flight"','delete state.v70.stats.focus','state.v70.extra=0',
  'state.v70.cooldowns.scan=12.001','state.v70.cooldowns.barrier=24.001','state.v70.cooldowns.focus=20.001',
  'state.v70.cooldowns.scan=-1','state.v70.trace=100.001','state.v70.trace=-1',
  'state.v70.stats.scan=0.5','state.v70.stats.activations=1000000001',
  'state.v70.stats.damageAbsorbed=NaN','state.v70.trace=Infinity','state.v70.cooldowns.focus=true',
  'state.v70=A.initial()','state.v70.active={scan:1,barrier:0,focus:0}',
  'state.v70.barrierRemaining=1','state.v70.cooldowns.unlimited=0'
 ];
 for(const edit of edits){const g=current();g.run('state.v70=A.serialize(A.initial());'+edit);assert.throws(()=>g.run('P.snapshot()'),/Personnage.v70/,edit);}
 const g=current();g.run('state.v70=A.serialize(A.initial());state.v70.stats.damageAbsorbed=0.5;P.validate(P.snapshot());');
});

test('the delegate rejects exotic prototypes, accessors and hidden/symbol fields without executing domain getters',()=>{
 for(const edit of [
  'state.v70=new Date()',
  'Object.setPrototypeOf(state.v70,{})',
  'Object.defineProperty(state.v70,"trace",{enumerable:true,get(){getterCalls++;return 0}})',
  'Object.defineProperty(state.v70,"extra",{value:0,enumerable:false})',
  'state.v70[Symbol("extra")]=0',
  'Object.defineProperty(state,"v70",{enumerable:true,get(){getterCalls++;return undefined}})',
  'Object.defineProperty(state,"v70",{value:state.v70,enumerable:false})'
 ]){
  const g=current();g.run('let getterCalls=0;state.v70=A.serialize(A.initial());'+edit);
  assert.throws(()=>g.run('P.test.validateCore37(state,37)'),/Personnage.v70/,edit);
  assert.equal(g.run('getterCalls'),0,edit);
 }
 const g=current();g.run('state.v70=Object.assign(Object.create(null),A.serialize(A.initial()));P.test.validateCore37(state,37)');
});

test('validation never defaults a present malformed domain or depends on the runtime adapter',()=>{
 const g=current();
 g.run('state.v70=A.serialize(A.initial());delete window.__SOMA_V70__;const checkpoint=P.snapshot();P.test.applyEnvelope(checkpoint)');
 assert.equal(g.run('state.v70.trace'),0);
 g.run('delete window.__SOMA_AUG70_CORE__');
 assert.throws(()=>g.run('P.snapshot()'),/Personnage.v70.*indisponible/);
 g.run('delete state.v70;P.snapshot()');
});

test('patching refuses drift/double application and retains the existing v67 domain validator',()=>{
 assert.notEqual(patch(patched).status,0);
 for(const old of ['function validateCore37(core,edition){','  const version=key.match(',
  'state=normalizeCore37(robustNormalize(clone(p.core)));state.driving=null;state.lastOnFoot=null;']){
  assert.notEqual(patch(original.replace(old,'drift')).status,0);
 }
 const g=current();g.run('addWorld();state.v70=A.serialize(A.initial());P.validate(P.snapshot())');
 assert.equal(g.run('state.v67.districtVisits.port'),7);
});
