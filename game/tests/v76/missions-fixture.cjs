'use strict';
const path=require('node:path'),cp=require('node:child_process');
const game=path.resolve(__dirname,'../..');
module.exports=JSON.parse(cp.execFileSync('python3',['-c',String.raw`
import json,re,sys
from pathlib import Path
game=Path(sys.argv[1]);sys.path.insert(0,str(game))
from tools.v76_missions import patch_html
parent=(game/'SOMA_MASSILIA_URBAIN_v0_75.html').read_text()
patched=patch_html(parent,{'missions-runtime':(game/'src/v76/missions-runtime.js').read_text()})
def script(html,name):return re.search(r'<script\b[^>]*id="'+name+r'"[^>]*>([\s\S]*?)</script>',html)[1]
def declaration(name):
 start=parent.index('const '+name+'=');end=parent.index(';\n',start)
 return parent[start:end+1]
print(json.dumps({'production':script(patched,'soma-v43-production'),'parentProduction':script(parent,'soma-v43-production'),
 'city':script(patched,'soma-v45-city'),'saver':script(patched,'soma-v37-persistence'),'group':script(patched,'soma-v64-group-runtime'),'groupCore':script(patched,'soma-v64-group-core'),'geometry':script(patched,'soma-v57-core'),
 'random':re.search(r'const hash=s=>[^\n]+',parent)[0]+'\n'+re.search(r'function rng\([^\n]+',parent)[0],
 'placement':parent[parent.index('function v20ReachableInteractionCells('):parent.index('const v20BasePopulate=')],
 'authoredWorld':parent[parent.index('function zoneId('):parent.index('const WORLD=makeWorld();')],
 'annexWorld':parent[parent.index('function v21FreshZone('):parent.index('const V21_CLUSTER_PALETTES=')],
 'nightWorld':parent[parent.index('function extendNightWorld('):parent.index('\nfunction ',parent.index('function extendNightWorld(')+10)],
 'worldData':'\n'.join(declaration(name) for name in ['DISTRICTS','TYPES','TITLES','NIGHT_DATA','V21_DATA','V22_DATA','V23_DATA','V28_DATA','V29_DATA'])}))
`,game],{encoding:'utf8',maxBuffer:1024*1024}));
