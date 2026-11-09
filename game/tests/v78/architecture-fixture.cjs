'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),zlib=require('node:zlib'),crypto=require('node:crypto'),{execFileSync}=require('node:child_process');
const game=path.resolve(__dirname,'../..'),root=path.dirname(game),sha=b=>crypto.createHash('sha256').update(b).digest('hex');
function extract(html,id){const m=html.match(new RegExp('<script[^>]*id="'+id+'"[^>]*>([\\s\\S]*?)<\\/script>'));if(!m)throw Error('Missing native script '+id);return m[1];}
function html(extended){
  if(!extended)return fs.readFileSync(path.join(game,'metropole-viewer-v77.html'),'utf8');
  return execFileSync('python3',['-B','-S','-c',"import pathlib,sys;sys.path.insert(0,'game');from tools import v78_architecture as P;print(P.patch_viewer(pathlib.Path('game/metropole-viewer-v77.html').read_text(),{'architecture-roof-core':pathlib.Path('game/src/v78/architecture-roof-core.js').read_text()}),end='')"],{cwd:root,encoding:'utf8',maxBuffer:4*1024*1024,env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'}});
}
function environment(extended){
  const h=html(extended),c=vm.createContext({module:{exports:{}},Float32Array,Set,Map,TextEncoder,TextDecoder,URL,AbortController,atob:s=>Buffer.from(s,'base64').toString('binary')});
  for(const id of[...h.matchAll(/<script[^>]*id="([^"]+)"/g)].map(m=>m[1])){
    if(id==='soma-viewer-data'||id==='soma-viewer-parts')continue;
    vm.runInContext(extract(h,id),c,{filename:id});
    if(id==='viewer-metropole-viewer')break;
  }
  return {c,A:c.__SOMA_ARCH68_CORE__,F:c.__SOMA_FIDELITY59_CORE__,G:c.__SOMA_V53_CORE__,T:c.__SOMA_TERRAIN56_CORE__,V:c.__SOMA_METRO_VIEW_CORE__,U:c.__SOMA_METRO_VIEWER_UTILS__,X:c.__SOMA_ARCHITECTURE78_CORE__};
}
function installed(cells){
  const world=process.env.MASSILIA_ROOF_WORLD||path.join(game,'data/v69/metropole'),manifestPath=path.join(world,'manifest.json');
  const raw=fs.readFileSync(manifestPath),manifest=JSON.parse(raw),proofs=[];
  function read(d){const bytes=fs.readFileSync(path.join(world,d.path));if(bytes.length!==d.bytes||sha(bytes)!==d.sha256)throw Error('Source asset mismatch '+d.path);proofs.push(d);return JSON.parse(d.encoding==='gzip-json'?zlib.gunzipSync(bytes):bytes);}
  const deps=environment(false),entries=cells.map(id=>{const tile=manifest.tiles.find(t=>t.cellId===id);if(!tile)throw Error('Native cell absent '+id);const terrain=read(tile.terrain);return {tile,layers:{vector:read(tile.vector),surfaces:read(tile.surfaces),terrain:{pack:terrain,grid:deps.T.load(terrain,tile.boundsL93)}}};});
  const parts=manifest.buildingParts?read(manifest.buildingParts):JSON.parse(extract(html(false),'soma-viewer-parts'));
  return {world,manifestPath,manifest,manifestSHA256:sha(raw),entries,parts,proofs};
}
module.exports={game,root,sha,extract,environment,installed};
