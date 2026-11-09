'use strict';
const cp=require('node:child_process'),path=require('node:path');
const old=require('../v76/missions-fixture.cjs'),game=path.resolve(__dirname,'../..');
const next=JSON.parse(cp.execFileSync('python3',['-B','-c',String.raw`
import json,re,sys
from pathlib import Path
game=Path(sys.argv[1]);sys.path.insert(0,str(game))
from tools.v77_missions import patch_html,MODULES
parent=(game/'SOMA_MASSILIA_URBAIN_v0_76.html').read_text()
patched=patch_html(parent,{n:(game/'src/v77'/f'{n}.js').read_text() for n in MODULES})
def script(html,name):return re.search(r'<script\b[^>]*id="'+name+r'"[^>]*>([\s\S]*?)</script>',html)[1]
print(json.dumps({k:script(html,name) for k,html,name in [('production',patched,'soma-v43-production'),('city',patched,'soma-v45-city'),('parentProduction',parent,'soma-v43-production'),('parentCity',parent,'soma-v45-city')]}))
`,game],{encoding:'utf8',maxBuffer:2*1024*1024}));
module.exports={...old,...next};
