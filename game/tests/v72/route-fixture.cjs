'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {createHash}=require('node:crypto'),{gzipSync}=require('node:zlib'),path=require('node:path');
const Preview=require('../../src/v72/route-corridor-core.js');
const baseline=fs.readFileSync(path.join(__dirname,'../../baseline/v66.html'),'utf8');
const source=baseline.match(/<script[^>]+id="soma-v63-nav-core"[^>]*>([\s\S]*?)<\/script>/)[1];
const hash=v=>createHash('sha256').update(v).digest('hex'),mod={exports:{}};
assert.equal(hash(source),Preview.CORE_SHA256);assert.equal(hash(baseline),Preview.BASELINE_SHA256);
vm.runInNewContext(source,{module:mod});const core=mod.exports;
const ORIGIN=[892951.6480966414,6247274.566415883],PBF='a'.repeat(64),PACK='b'.repeat(64),TOPO='c'.repeat(64),GEOM='d'.repeat(64);
const pt=(e,n=0)=>({e:ORIGIN[0]+e,n:ORIGIN[1]+n}),clone=v=>JSON.parse(JSON.stringify(v));
function tile(x=0,y=0){return {cellId:x===0&&y===0?'V52-MC-33':`V52-MC-${x>=0?'E':'W'}${Math.abs(x).toString().padStart(2,'0')}-${y<=0?'N':'S'}${Math.abs(y).toString().padStart(2,'0')}`,
 gridX:x,gridY:y,contentSHA256:hash(`${x}:${y}`),boundsL93:[ORIGIN[0]+x*250-125,ORIGIN[1]-y*250-125,ORIGIN[0]+x*250+125,ORIGIN[1]-y*250+125]};}
function graph(t,nodes,edgeRows,turns=[]){
 const ways=Object.fromEntries(edgeRows.map(e=>[e[2],{name:'Rue native '+e[2],geometrySHA256:GEOM}]));
 const edges=edgeRows.map(e=>[e[0],e[1],e[2],Math.hypot(nodes[e[0]][1]-nodes[e[1]][1],nodes[e[0]][2]-nodes[e[1]][2]),e[3]??15,e[4]??0,[t.cellId],e[5]??1]);
 return {schema:'soma/navigation-source/1',version:'0.69.0',sourcePbfSHA256:PBF,sourcePackSHA256:PACK,nativeTopologySHA256:TOPO,routingCoreSHA256:Preview.CORE_SHA256,
  nodes:nodes.map(n=>[n[0],...Object.values(pt(n[1],n[2]))]),edges,ways,turns,cellHashes:{[t.cellId]:t.contentSHA256},nodeTags:{},
  edgeSources:edgeRows.map((e,i)=>({wayId:e[2],segmentIndex:e[5]??1,t0:e[6]??0,t1:e[7]??1,startNative:nodes[e[0]][0].startsWith('n/'),endNative:nodes[e[1]][0].startsWith('n/')})),
  bicycleMasks:edges.map(()=>3),sourceStatus:{nativeNodeIdentity:true,vectorConstrained:true,nodeTagsComplete:true,physicalAccessibilityVerified:false,physicalMovementReady:false,campaignRoutingActivated:false}};
}
function setup(specs,{mutateWorld,budgets,loadAsset,decode,now,mutateGraph}={}){
 const assets=new Map(),tiles=[],graphs=[];
 for(let i=0;i<specs.length;i++){
  const [t,g]=specs[i];if(mutateGraph)mutateGraph(g,i);
  const raw=Buffer.from(JSON.stringify(g)),data=gzipSync(raw);
  t.navigation={path:t.cellId+'.json.gz',bytes:data.length,decodedBytes:raw.length,sha256:hash(data),encoding:'gzip-json'};
  tiles.push(t);graphs.push(g);assets.set(t.navigation.path,data);
 }
 const world={schema:'soma-metropole/world-manifest/1',crs:'EPSG:2154',units:'m',cellSize:250,origin:ORIGIN,source:{sha256:PBF},sourcePackSHA256:PACK,nativeTopologySHA256:TOPO,
  navigationCore:{scriptId:'soma-v63-nav-core',version:'0.63.0',sha256:Preview.CORE_SHA256,baselineSHA256:Preview.BASELINE_SHA256},
  coverageExplicitPartial:true,physicalMovementReady:false,campaignRoutingActivated:false,tiles};
 mutateWorld?.(world);
 const requests=[];
 const api=Preview.create({world,routerCore:core,routerCoreSHA256:Preview.CORE_SHA256,budgets,decode,now,
  loadAsset:loadAsset||(async(d,options)=>{requests.push({d,options});return assets.get(d.path);})});
 return {api,world,assets,requests,graphs};
}
function simple(options){const t=tile();return setup([[t,graph(t,[['n/1',-100,0],['n/2',100,0]],[[0,1,'100']])]],options);}
function seam(options){const a=tile(),b=tile(1);return setup([
 [a,graph(a,[['n/1',-50,0],['clip/100/1/0.500000000000',125,0]],[[0,1,'100',15,0,1,0,.5]])],
 [b,graph(b,[['clip/100/1/0.500000000000',125,0],['n/2',300,0]],[[0,1,'100',15,0,1,.5,1]])]],options);}


module.exports={Preview,core,pt,tile,graph,setup,simple,seam,hash,ORIGIN};
