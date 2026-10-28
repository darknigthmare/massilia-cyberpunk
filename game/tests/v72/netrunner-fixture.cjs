/* Execute strict v72 transforms against the actual delivered v71 scripts. */
'use strict';
const path=require('node:path'),cp=require('node:child_process');
const game=path.resolve(__dirname,'../..');
module.exports=JSON.parse(cp.execFileSync('python3',['-c',String.raw`
import json,re,sys
from pathlib import Path
game=Path(sys.argv[1]);sys.path.insert(0,str(game))
from tools.v72_netrunner import patch_html
parent=(game/'SOMA_MASSILIA_URBAIN_v0_71.html').read_text()
patched=patch_html(parent,{'netrunner-runtime':(game/'src/v72/netrunner-runtime.js').read_text()})
def script(name):return re.search(r'<script\b[^>]*id="'+name+r'"[^>]*>([\s\S]*?)</script>',patched)[1]
def part(text,start,end):
 a=text.index(start);return text[a:text.index(end,a+len(start))]
print(json.dumps({'v32':script('soma-v32-patch'),'v33':script('soma-v33-patch'),
 'v42':script('soma-v42-recovery'),'perception70':script('soma-v70-perception-runtime'),
 'runtime':script('soma-v72-netrunner-runtime'),'loop':part(patched,'function loop(t){','function controls(){')}))
`,game],{encoding:'utf8',maxBuffer:8*1024*1024}));
