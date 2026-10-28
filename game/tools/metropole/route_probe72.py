#!/usr/bin/env python3
"""Measure v72 bounded source corridors on the frozen AMP world with Node.

Only Python's standard library and Node builtins are required. Every NAV read
is checked by the actual source-routing core. The world is never rewritten.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

GAME = Path(__file__).resolve().parents[2]
WORLD_SHA = '881a3fec8837fe7922801102f5fa8c33ffa85ea743ed726e7d1f71dcb8ab0bfe'
NODE_PROBE = r'''
const fs=require('node:fs'),vm=require('node:vm'),crypto=require('node:crypto'),z=require('node:zlib');
const [game,base]=process.argv.slice(1),hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const Preview=require(game+'/src/v72/route-corridor-core.js'),Previous=require(game+'/src/v70/route-preview-core.js');
const bytes=fs.readFileSync(base+'/manifest.json'),world=JSON.parse(bytes);
const baseline=fs.readFileSync(game+'/baseline/v66.html'),source=baseline.toString().match(/<script[^>]+id="soma-v63-nav-core"[^>]*>([\s\S]*?)<\/script>/)[1];
if(hash(source)!==Preview.CORE_SHA256||hash(baseline)!==Preview.BASELINE_SHA256)throw Error('Frozen core mismatch');
const mod={exports:{}};vm.runInNewContext(source,{module:mod});
const start={e:892990.7467568527,n:6247192.082113549};
const cases=[
 {name:'Belsunce → Boulevard Gillibert',end:{e:895371.6176442051,n:6243517.547924213},expectDirectRoute:true},
 {name:'Belsunce → Rue de la Boiseraie',end:{e:896610.0993810829,n:6247245.398502776},expectExpandedRoute:true},
 {name:'Belsunce → secteur nord',end:{e:892986.6455046574,n:6251030.197988294},expectExpandedRoute:true}
];
let reads=0,inFlight=0,maxConcurrentReads=0;
function create(Core){return Core.create({world,routerCore:mod.exports,routerCoreSHA256:Core.CORE_SHA256,
 decode:async data=>z.gunzipSync(data),loadAsset:async d=>{reads++;inFlight++;maxConcurrentReads=Math.max(maxConcurrentReads,inFlight);
 try{return fs.readFileSync(base+'/'+d.path);}finally{inFlight--;}}});}
(async()=>{
 const begun=performance.now(),preview=create(Preview),catalogueMilliseconds=performance.now()-begun,previous=create(Previous),results=[];
 for(const item of cases){const request={start,end:item.end,maxAxisDistanceM:.01,mode:'foot'};reads=0;
  const initial=await preview.preview(request),initialReads=reads;reads=0;
  const expanded=await preview.preview({...request,corridorStage:1}),expandedReads=reads;reads=0;
  const legacy=await previous.preview(request),legacyReads=reads;
  if(item.expectDirectRoute&&(initial.status!=='route'||initial.coverage.loadedCells.length<=36))throw Error('Long corridor regression');
  if(item.expectExpandedRoute&&(initial.status==='route'||!initial.continuation.available||expanded.status!=='route'))throw Error('Explicit expansion regression');
  for(const r of [initial,expanded])if(r.resources.accountedResidentBytes>r.resources.maxResidentBytes||r.physicalAccessibilityVerified!==false||r.campaignRoutingActivated!==false)throw Error('Resource/activation regression');
  if(preview.snapshot().residentGraphs!==0||preview.snapshot().busy)throw Error('Graph retention regression');
  results.push({name:item.name,request,initial,expanded,legacy:{status:legacy.status,code:legacy.code,coverage:legacy.coverage,resources:legacy.resources},reads:{initial:initialReads,expanded:expandedReads,legacy:legacyReads}});
 }
 process.stdout.write(JSON.stringify({catalogueMilliseconds,catalogue:preview.snapshot(),maximumConcurrentNAVReads:maxConcurrentReads,
 sourceCoreSHA256:hash(source),sourceBaselineSHA256:hash(baseline),results}));
})().catch(error=>{process.stderr.write(String(error.stack));process.exitCode=1;});
'''


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def probe(world, report):
    world, report = world.resolve(), report.resolve()
    if report.is_relative_to(world):
        raise ValueError('The measurement report must be outside the frozen source world.')
    manifest = world / 'manifest.json'
    before = sha(manifest)
    if before != WORLD_SHA:
        raise ValueError('The world must be the exact frozen AMP manifest 881a3fec…')
    runtime = GAME / 'src/v72/route-corridor-core.js'
    legacy_runtime = GAME / 'src/v70/route-preview-core.js'
    runtime_before, legacy_before = sha(runtime), sha(legacy_runtime)
    started = time.monotonic()
    result = subprocess.run(['node', '-e', NODE_PROBE, str(GAME), str(world)],
                            check=True, capture_output=True, text=True, timeout=90)
    measurements = json.loads(result.stdout)
    after = sha(manifest)
    if after != before:
        raise ValueError('Source world changed during the read-only probe.')
    if sha(runtime) != runtime_before or sha(legacy_runtime) != legacy_before:
        raise ValueError('A routing runtime changed during the probe.')
    output = {
        'schema': 'soma-metropole/route-corridor-proof/1', 'version': '0.72.0',
        'worldManifestSHA256': before, 'worldManifestUnchanged': after == before,
        'sourceWorld': str(world), 'runtimeSHA256': runtime_before,
        'legacyRuntimeSHA256': legacy_before,
        'toolSHA256': sha(Path(__file__).resolve()), 'elapsedSeconds': round(time.monotonic() - started, 3),
        'scope': 'Bounded source corridors; no global connectivity or physical accessibility claim.',
        'physicalMovementReady': False, 'physicalAccessibilityVerified': False,
        'campaignRoutingActivated': False, **measurements,
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world', type=Path, default=Path('/workspace/massilia-geodata-generated/world-amp-navigation-2026-10-26'))
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    output = probe(args.world, args.report)
    print(json.dumps({'report': str(args.report), 'worldManifestUnchanged': output['worldManifestUnchanged'],
        'maximumConcurrentNAVReads': output['maximumConcurrentNAVReads'],
        'routes': [{'name': r['name'], 'initial': r['initial']['code'], 'expanded': r['expanded']['code'],
                    'initialMeters': r['initial']['route']['lengthMeters'] if r['initial']['route'] else None,
                    'expandedMeters': r['expanded']['route']['lengthMeters'] if r['expanded']['route'] else None,
                    'initialCells': len(r['initial']['coverage']['loadedCells']),
                    'expandedCells': len(r['expanded']['coverage']['loadedCells'])} for r in output['results']]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
