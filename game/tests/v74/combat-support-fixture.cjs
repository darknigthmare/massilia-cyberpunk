/* Strict extension of the real delivered parent; retain the actual v32 effect. */
'use strict';
const path=require('node:path'),cp=require('node:child_process');
const game=path.resolve(__dirname,'../..');
module.exports=JSON.parse(cp.execFileSync('python3',['-c',String.raw`
import json,re,sys
from pathlib import Path
game=Path(sys.argv[1]);sys.path.insert(0,str(game))
from tools.v74_combat import patch_html,MODULES
parent=(game/'SOMA_MASSILIA_URBAIN_v0_73.html').read_text()
patched=patch_html(parent,{name:(game/f'src/v74/{name}.js').read_text() for name in MODULES})
def script(name):return re.search(r'<script\b[^>]*id="'+name+r'"[^>]*>([\s\S]*?)</script>',patched)[1]
def part(text,start,end):
 a=text.index(start);return text[a:text.index(end,a+len(start))]
print(json.dumps({'v32':script('soma-v32-patch'),'v33':script('soma-v33-patch'),
 'persistence':script('soma-v37-persistence'),'perception70':script('soma-v70-perception-runtime'),
 'radio72':script('soma-v72-contact-sharing-runtime'),
 'runtime':script('soma-v74-combat-support-runtime'),'echo':script('soma-v73-tactical-runtime'),
 'loop':part(patched,'function loop(t){','function controls(){')}))
`,game],{encoding:'utf8',maxBuffer:8*1024*1024}));
