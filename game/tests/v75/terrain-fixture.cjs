'use strict';
const fs=require('node:fs'),path=require('node:path'),cp=require('node:child_process'),vm=require('node:vm');
const game=path.resolve(__dirname,'../..');
const owners=JSON.parse(cp.execFileSync('python3',['-c',String.raw`
import json,re,sys
from pathlib import Path
g=Path(sys.argv[1]);h=(g/'SOMA_MASSILIA_URBAIN_v0_74.html').read_text()
sys.path.insert(0,str(g))
from tools.v75_terrain import patch_terrain
def s(n):return re.search(r'<script\b[^>]*id="'+n+r'"[^>]*>([\s\S]*?)</script>',h)[1]
def span(t,a,b):return t[t.index(a):t.index(b,t.index(a))]
terrain=patch_terrain(s('soma-v56-terrain-runtime'))
print(json.dumps({'core':s('soma-v56-terrain-core'),'geometry':s('soma-v53-core'),'sight':s('soma-v61-sight-core'),'legacy':json.loads(s('soma-v56-terrain')),
 'mosaic':span(terrain,'const v69Tiles=','const activeFor='),
 'validate':span(terrain,'function validatePack(p){','function dbOpen('),
 'install':span(terrain,'async function install(p,','function withMode('),
 'entry':span(terrain,' const oldEnter=enterZone;',' const oldActor=actorGeo;')}))
`,game],{encoding:'utf8',maxBuffer:8*1024*1024}));
function data(){const c={TextEncoder,Buffer,Uint8Array,Uint32Array,Float32Array,DataView};c.window=c;vm.createContext(c);vm.runInContext(owners.core,c);vm.runInContext(owners.sight,c);
 for(const n of ['a','b','c'])vm.runInContext(fs.readFileSync(path.join(game,'src/v75/terrain-data-'+n+'.js'),'utf8'),c);
 const pack=JSON.parse(c.__SOMA_TERRAIN75_PARTS__.join('')),K=c.__SOMA_TERRAIN56_CORE__;
 return {context:c,K,S:c.__SOMA_SIGHT61_CORE__,pack,native:K.load(pack),legacy:K.load(owners.legacy)};}
module.exports={game,owners,data};
