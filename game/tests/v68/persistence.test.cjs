'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {spawnSync} = require('node:child_process');

const baseline = path.resolve(__dirname, '../../baseline/v66.html');
const html = fs.readFileSync(baseline, 'utf8');
const match = html.match(/<script\b[^>]*\bid=["']soma-v37-persistence["'][^>]*>([\s\S]*?)<\/script>/);
assert(match, 'Prepare the original release with python3 lancer.py --prepare-only first.');
const original = match[1];
const python = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
function patch(script) {
  return spawnSync(python, ['-c',
    'import sys; sys.path.insert(0, sys.argv[1]); from v68_persistence import patch_persistence; sys.stdout.write(patch_persistence(sys.stdin.read()))',
    path.resolve(__dirname, '../../tools')], {input: script, encoding: 'utf8'});
}
const result = patch(original);
assert.equal(result.status, 0, result.stderr);
const patched = result.stdout;
assert.notEqual(patched, original);
assert.equal(fs.readFileSync(baseline, 'utf8'), html, 'The verified baseline must stay untouched.');
assert.notEqual(patch(patched).status, 0, 'Double patching must be refused.');
assert.notEqual(patch(original.replace('function validateCore37(core,edition){', 'function unexpected(){')).status, 0);
assert.notEqual(patch(original + '\nfunction validateCore37(core,edition){\n').status, 0);
assert.notEqual(patch(original.replace('  const version=key.match(', ' const version=key.match(')).status, 0);

// Execute the ACTUAL full frozen saver, with its original snapshot, validator,
// normalizer and reload path. Only external game systems and DOM are fixtures.
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
let checks = 5;
const regression = game(original);
regression.run('addWorld()');
assert.throws(() => regression.run('window.__SOMA_V37_SAVE__.snapshot()'), /Personnage\.v67.*incompatible/);
checks++;

const current = game(patched);
current.run('addWorld()');
current.run('const P=window.__SOMA_V37_SAVE__; const checkpoint=P.snapshot(); P.validate(checkpoint);');
assert.equal(current.run('checkpoint.payload.core.v67.districtVisits.port'), 7);
current.run('state.v67.conversations["civil:port-1"]=99; state.credits=0; P.test.applyEnvelope(checkpoint);');
assert.equal(current.run('state.v67.conversations["civil:port-1"]'), 3);
assert.equal(current.run('state.credits'), 25);
assert.equal(current.run('P.snapshot().payload.core.v67.ambientSeen["port:rain"]'), 1);
checks++;

const legacy = game(patched);
assert.doesNotThrow(() => legacy.run('const P=window.__SOMA_V37_SAVE__; const checkpoint=P.snapshot(); P.validate(checkpoint); P.test.applyEnvelope(checkpoint);'));
assert.equal(legacy.run('Object.hasOwn(state,"v67")'), false, 'Legacy imports do not invent progress.');
checks++;

current.run('const unchanged=JSON.stringify(checkpoint); P.validate(checkpoint);');
assert.equal(current.run('JSON.stringify(checkpoint)===unchanged'), true);
checks++;

function refuses(edit, pattern = /Personnage\.v67/) {
  const fixture = game(patched);
  fixture.run('addWorld()');
  fixture.run(edit);
  assert.throws(() => fixture.run('window.__SOMA_V37_SAVE__.snapshot()'), pattern, edit);
  checks++;
}
refuses('state.v68={}', /Personnage\.v68.*incompatible/);
refuses('state.player99={}', /Personnage\.player99.*incompatible/);
refuses('state.v67.schema="soma-v67/2"');
refuses('delete state.v67.ambientSeen');
refuses('state.v67.extra=true');
refuses('state.v67.districtVisits=[]');
refuses('state.v67.conversations={a:-1}');
refuses('state.v67.conversations={a:1.5}');
refuses('state.v67.conversations={a:1000000001}');
refuses('state.v67.conversations=JSON.parse(\'{"__proto__":1}\')');
refuses('state.v67.conversations={"<script>":1}');
refuses('state.v67.lastDistrict={}');
refuses('state.v67.lastDistrict=""');

// Direct import validation also rejects exotic object prototypes, which cannot
// arise from a JSON reload but must not be accepted via the public API.
current.run('const exotic=clone(checkpoint); exotic.payload.core.v67.conversations=new Date(); exotic.checksum=P.test.packagePayload(exotic.payload).checksum;');
assert.throws(() => current.run('P.validate(exotic)'), /Personnage\.v67.*objet simple/);
checks++;

console.log(JSON.stringify({passed: true, checks, campaignRoundTrip: true, legacyCompatible: true}));
