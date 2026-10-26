/* Read-only test fixture: transform the actual protected scripts in memory. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),cp=require('node:child_process');
const game=path.resolve(__dirname,'../..'),source=path.join(game,'baseline/v66.html');
if(!fs.existsSync(source))throw Error('Prepare the verified original payload before real-script integration tests.');
const scriptNames=['soma-v32-patch','soma-v33-patch','soma-v35-body','soma-v42-recovery','soma-v43-production','soma-v62-runtime','soma-v64-group-runtime'];
module.exports=JSON.parse(cp.execFileSync('python3',['-c',String.raw`
import json,re,sys
from pathlib import Path
game=Path(sys.argv[1]);sys.path.insert(0,str(game))
from tools.v70_gameplay import patch_gameplay
text=(game/'baseline/v66.html').read_text()
names=json.loads(sys.argv[2]);html=''.join(re.search(r'<script\b[^>]*id="'+name+r'"[^>]*>[\s\S]*?</script>',text)[0] for name in names)
main=next(m[2] for m in re.finditer(r'<script\b([^>]*)>([\s\S]*?)</script>',text) if 'function update(dt){move(dt);' in m[2])
html+='<script id="qa-main-gameplay">'+main+'</script>';names.append('qa-main-gameplay')
patched=patch_gameplay(html)
out={name:re.search(r'<script\b[^>]*id="'+name+r'"[^>]*>([\s\S]*?)</script>',patched)[1] for name in names}
out['qa-real-update']=re.search(r'function update\(dt\)\{[^\n]*',out['qa-main-gameplay'])[0]
print(json.dumps(out))
`,game,JSON.stringify(scriptNames)],{encoding:'utf8',maxBuffer:8*1024*1024}));
