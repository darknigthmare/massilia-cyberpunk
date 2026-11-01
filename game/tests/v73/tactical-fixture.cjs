/* Apply the v73 transform to the delivered parent, then execute its real hooks. */
'use strict';
const path=require('node:path'),cp=require('node:child_process');
const game=path.resolve(__dirname,'../..');
module.exports=JSON.parse(cp.execFileSync('python3',['-c',String.raw`
import json,re,sys
from pathlib import Path
game=Path(sys.argv[1]);sys.path.insert(0,str(game))
from tools.v73_tactics import patch_html
parent=(game/'SOMA_MASSILIA_URBAIN_v0_72.html').read_text()
patched=patch_html(parent,{'tactical-runtime':(game/'src/v73/tactical-runtime.js').read_text()})
def script(name):return re.search(r'<script\b[^>]*id="'+name+r'"[^>]*>([\s\S]*?)</script>',patched)[1]
a=patched.index('function loop(t){');b=patched.index('function controls(){',a)
print(json.dumps({'owner':script('soma-v70-runtime'),'runtime':script('soma-v73-tactical-runtime'),
 'perception':script('soma-v70-perception-runtime'),'v42':script('soma-v42-recovery'),'loop':patched[a:b]}))
`,game],{encoding:'utf8',maxBuffer:8*1024*1024}));
