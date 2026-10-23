from pathlib import Path
import json,hashlib,sys
ROOT=Path(__file__).resolve().parents[1]
M=ROOT/'MANIFEST_v67.json'
if not M.is_file(): raise SystemExit('MANIFEST_v67.json absent')
manifest=json.loads(M.read_text('utf-8'))
errors=[]
for rel,exp in manifest['files'].items():
 p=ROOT/rel
 if not p.is_file(): errors.append(f'absent: {rel}');continue
 h=hashlib.sha256(p.read_bytes()).hexdigest()
 if h!=exp['sha256'] or p.stat().st_size!=exp['bytes']: errors.append(f'mismatch: {rel}')
print(json.dumps({'files':len(manifest['files']),'errors':errors},ensure_ascii=False))
raise SystemExit(1 if errors else 0)
