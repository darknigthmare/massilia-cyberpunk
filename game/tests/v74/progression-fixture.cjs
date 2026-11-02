'use strict';
const path=require('node:path'),cp=require('node:child_process');
const game=path.resolve(__dirname,'../..');
module.exports=JSON.parse(cp.execFileSync('python3',['-c',String.raw`
import json,re,sys
from pathlib import Path
game=Path(sys.argv[1]);sys.path.insert(0,str(game))
from tools.v74_progression import patch_html
parent=(game/'SOMA_MASSILIA_URBAIN_v0_73.html').read_text()
patched=patch_html(parent,{'progression-runtime':(game/'src/v74/progression-runtime.js').read_text()})
def script(html,name):return re.search(r'<script\b[^>]*id="'+name+r'"[^>]*>([\s\S]*?)</script>',html)[1]
def declaration(name):
 start=parent.index('const '+name+'=');end=parent.index(';\n',start)
 return parent[start:end+1]
world=parent[parent.index('function zoneId('):parent.index('const WORLD=makeWorld();')]
print(json.dumps({'city':script(patched,'soma-v45-city'),'saver':script(patched,'soma-v37-persistence'),
 'parentCity':script(parent,'soma-v45-city'),'parentSaver':script(parent,'soma-v37-persistence'),
 'combat32':script(patched,'soma-v32-patch'),'authoredWorld':world,
 'worldData':'\n'.join(declaration(name) for name in ['DISTRICTS','TYPES','TITLES']),
 'nightLinks':parent[parent.index('function extendNightWorld('):parent.index('function nightVenue(')]}))
`,game],{encoding:'utf8',maxBuffer:1024*1024}));
