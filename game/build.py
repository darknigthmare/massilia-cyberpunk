from pathlib import Path
import hashlib
ROOT=Path(__file__).resolve().parent
BASE=ROOT/'baseline/v66.html'
OUT=ROOT/'SOMA_MASSILIA_URBAIN_v0_67.html'
EXPECTED='f1a6ce4b5957f634ff9fdbfaccfcf11c9e0d22159d01758dd56e29513581a014'
raw=BASE.read_bytes()
if hashlib.sha256(raw).hexdigest()!=EXPECTED: raise SystemExit('baseline v66 mismatch')
html=raw.decode('utf-8')
module=(ROOT/'src/v67/world-runtime.js').read_text('utf-8')
insert='\n<script id="soma-v67-world-runtime">'+module+'</script>\n'
if '</body>' not in html: raise SystemExit('body closing tag missing')
html=html.replace('</body>',insert+'</body>',1)
OUT.write_text(html,encoding='utf-8',newline='\n')
print(OUT, OUT.stat().st_size, hashlib.sha256(OUT.read_bytes()).hexdigest())
