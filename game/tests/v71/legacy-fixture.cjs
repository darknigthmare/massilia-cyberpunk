/* Execute strict transforms of the actual protected historical scripts. */
'use strict';
const path=require('node:path'),cp=require('node:child_process');
const game=path.resolve(__dirname,'../..');
module.exports=JSON.parse(cp.execFileSync('python3',['-c',String.raw`
import json,re,sys
from pathlib import Path
game=Path(sys.argv[1]);sys.path.insert(0,str(game))
from tools.v70_gameplay import patch_gameplay
from tools.v71_legacy_perception import patch_html
base=(game/'baseline/v66.html').read_text();html=patch_gameplay(base)
for name in ['perception-runtime','runtime']:
 html=html.replace('</body>','<script id="soma-v70-'+name+'">'+(game/('src/v70/'+name+'.js')).read_text()+'</script></body>')
patched=patch_html(html,{'legacy-perception-runtime':(game/'src/v71/legacy-perception-runtime.js').read_text()})
def part(text,start,end):
 a=text.index(start);return text[a:text.index(end,a+len(start))]
def script(name):return re.search(r'<script\b[^>]*id="'+name+r'"[^>]*>([\s\S]*?)</script>',patched)[1]
print(json.dumps({'ai':part(patched,'function updateAI(dt){','\nfunction move(dt){'),
 'dispatch':part(patched,'function ensurePoliceResponse(force=false){','\nfunction updatePolice(dt){'),
 'police':part(patched,'function updatePolice(dt){','\n/* SOMA//MASSILIA 0.34'),
 'perception70':script('soma-v70-perception-runtime'),
 'legacy71':script('soma-v71-legacy-perception-runtime'),
 'sourceDamagePreserved':part(html,'function policeStunPlayer(source,amount=6){','\nfunction spawnRoadblock(){')==part(patched,'function policeStunPlayer(source,amount=6){','\nfunction spawnRoadblock(){')}))
`,game],{encoding:'utf8',maxBuffer:8*1024*1024}));
