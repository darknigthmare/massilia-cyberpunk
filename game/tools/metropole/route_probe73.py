#!/usr/bin/env python3
"""Compare three geographic guided corridors with frozen v72 on real AMP NAV.

Uses standard-library Python and Node builtins. Reads the pinned external world;
never prepares, edits or installs source assets. Reports remain outside Git.
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
const Preview=require(game+'/src/v73/route-guided-core.js'),Previous=require(game+'/src/v72/route-corridor-core.js');
const world=JSON.parse(fs.readFileSync(base+'/manifest.json'));
const baseline=fs.readFileSync(game+'/baseline/v66.html'),source=baseline.toString().match(/<script[^>]+id="soma-v63-nav-core"[^>]*>([\s\S]*?)<\/script>/)[1];
if(hash(source)!==Preview.CORE_SHA256||hash(baseline)!==Preview.BASELINE_SHA256)throw Error('Frozen core mismatch');
const mod={exports:{}};vm.runInNewContext(source,{module:mod});
const start={e:892990.7467568527,n:6247192.082113549};
const cases=[
 {name:'Belsunce → axe OSM 122195441 (footway)',end:{e:892503.4562404741,n:6243512.18291101},endAxisKey:'["122195441",3,0,1]',corridorGuide:{e:893738.447676212,n:6245220.858919124}},
 {name:'Belsunce → Rue Paul Coxe',end:{e:892985.1532743336,n:6252557.397066671},endAxisKey:'["182028210",2,0,1]',corridorGuide:{e:894487.9492004478,n:6249876.303378871}},
 {name:'Belsunce → axe OSM 1513089848 (path)',end:{e:893491.7492604799,n:6252530.6531054005},endAxisKey:'["1513089848",10,0,1]',corridorGuide:{e:894734.6860439508,n:6249721.214711661}}
];
let reads=0,inFlight=0,maxConcurrentReads=0;const assets=new Map();
function create(Core){return Core.create({world,routerCore:mod.exports,routerCoreSHA256:Core.CORE_SHA256,
 decode:async(data,_encoding,options)=>z.gunzipSync(data,{maxOutputLength:options.maxDecodedBytes}),
 loadAsset:async(d,options)=>{reads++;inFlight++;maxConcurrentReads=Math.max(maxConcurrentReads,inFlight);
 try{if(options.signal.aborted)throw Error('Unexpected aborted read');const data=fs.readFileSync(base+'/'+d.path);
  if(hash(data)!==d.sha256||data.length!==d.bytes)throw Error('NAV file source mismatch');
  assets.set(d.path,{path:d.path,sha256:d.sha256,bytes:d.bytes});return data;}finally{inFlight--;}}});}
(async()=>{
 const begun=performance.now(),preview=create(Preview),catalogueMilliseconds=performance.now()-begun,previous=create(Previous),results=[];
 for(const item of cases){const request={start,end:item.end,endAxisKey:item.endAxisKey,maxAxisDistanceM:.01,mode:'foot',corridorStage:1};reads=0;
  const legacy=await previous.preview(request),legacyReads=reads;reads=0;
  const direct=await preview.preview(request),directReads=reads;reads=0;
  const guidedRequest={...request,corridorGuide:item.corridorGuide},guided=await preview.preview(guidedRequest),guidedReads=reads;
  if(legacy.code!=='no_route_in_loaded_network'||direct.code!==legacy.code||legacy.route||direct.route)throw Error('Before case changed');
  if(guided.status!=='route'||!guided.route.completeBetweenAnchors||guided.route.lengthMeters<5000)throw Error('Guided native detour regression: '+guided.reason);
  if(guided.coverage.guideIsRouteWaypoint!==false||guided.coverage.loadedCells.length>192||guided.resources.nodes>48000||guided.resources.edges>64000||guided.resources.elapsedMilliseconds>6000||guided.resources.accountedResidentBytes>128*1024*1024)throw Error('Guided budget regression');
  if(guided.physicalAccessibilityVerified!==false||guided.campaignRoutingActivated!==false||guided.globalDisconnectionProven!==false||preview.snapshot().residentGraphs!==0||preview.snapshot().busy)throw Error('Claim/retention regression');
  results.push({name:item.name,request:guidedRequest,legacy,direct,guided,reads:{legacy:legacyReads,direct:directReads,guided:guidedReads},processMemoryAfter:process.memoryUsage()});
 }
 for(const asset of assets.values()){const data=fs.readFileSync(base+'/'+asset.path);if(hash(data)!==asset.sha256||data.length!==asset.bytes)throw Error('NAV source changed');}
 process.stdout.write(JSON.stringify({catalogueMilliseconds,catalogue:preview.snapshot(),maximumConcurrentNAVReads:maxConcurrentReads,
  sourceCoreSHA256:hash(source),sourceBaselineSHA256:hash(baseline),nodeVersion:process.version,platform:process.platform,
  memoryMeasurementLimit:'Accounted owned memory follows the core contract. processMemoryAfter is a boundary sample, not peak heap/GPU memory.',
  authenticatedAssetsUnchanged:true,authenticatedAssets:[...assets.values()],results}));
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
    if report.is_relative_to(world) or report.is_relative_to(GAME.parent):
        raise ValueError('Report must be outside the source world and Git repository.')
    paths = {'worldManifest': world / 'manifest.json', 'runtime73': GAME / 'src/v73/route-guided-core.js',
             'runtime72': GAME / 'src/v72/route-corridor-core.js', 'baseline66': GAME / 'baseline/v66.html'}
    before = {name: sha(path) for name, path in paths.items()}
    if before['worldManifest'] != WORLD_SHA:
        raise ValueError('Expected the pinned AMP world 881a3fec…')
    begun = time.monotonic()
    run = subprocess.run(['node', '-e', NODE_PROBE, str(GAME), str(world)],
                         check=True, capture_output=True, text=True, timeout=90)
    after = {name: sha(path) for name, path in paths.items()}
    if before != after:
        raise ValueError('A frozen source changed during the read-only probe.')
    output = {'schema': 'soma-metropole/route-guided-proof/1', 'version': '0.73.0',
              'sourceSHA256': before, 'sourceFilesUnchanged': True, 'sourceWorld': str(world),
              'toolSHA256': sha(Path(__file__).resolve()), 'elapsedSeconds': round(time.monotonic() - begun, 3),
              'scope': 'Three selected source-axis routes in bounded guided corridors; no physical or global connectivity claim.',
              'physicalMovementReady': False, 'physicalAccessibilityVerified': False,
              'campaignRoutingActivated': False, **json.loads(run.stdout)}
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world', type=Path, default=Path('/workspace/massilia-geodata-generated/world-amp-navigation-2026-10-26'))
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    output = probe(args.world, args.report)
    print(json.dumps({'report': str(args.report), 'sourceFilesUnchanged': output['sourceFilesUnchanged'],
                     'maximumConcurrentNAVReads': output['maximumConcurrentNAVReads'],
                     'routes': [{'name': r['name'], 'before': r['legacy']['code'], 'after': r['guided']['code'],
                                 'meters': r['guided']['route']['lengthMeters'], 'cells': len(r['guided']['coverage']['loadedCells']),
                                 'milliseconds': r['guided']['resources']['elapsedMilliseconds'],
                                 'accountedResidentBytes': r['guided']['resources']['accountedResidentBytes']}
                                for r in output['results']]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
