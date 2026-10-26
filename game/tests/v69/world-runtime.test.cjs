'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const crypto=require('node:crypto');
const zlib=require('node:zlib');
const S=require('../../src/v69/streaming-core.js');
const game=path.resolve(__dirname,'../..');
const terrainSource=fs.readFileSync(path.join(game,'baseline/v66.html'),'utf8')
  .match(/<script\b[^>]*id="soma-v56-terrain-core"[^>]*>([\s\S]*?)<\/script>/)[1];
const runtime=fs.readFileSync(path.join(game,'src/v69/world-runtime.js'),'utf8');
const terrainContext=vm.createContext({Buffer,TextEncoder,Uint8Array,Float32Array,DataView,ArrayBuffer});
vm.runInContext(terrainSource,terrainContext);
const K=terrainContext.__SOMA_TERRAIN56_CORE__;
const id='V52-MC-33',sourceSHA='a'.repeat(64),packSHA='b'.repeat(64),contentSHA='c'.repeat(64);
const bounds=[S.ORIGIN[0]-125,S.ORIGIN[1]-125,S.ORIGIN[0]+125,S.ORIGIN[1]+125];
const digest=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');

function pack({area=bounds,step=25,sourceGridSHA256,change=()=>0,missing=[]}={}){
  const cols=(area[2]-area[0])/step+3,rows=(area[3]-area[1])/step+3;
  const header={boundsL93:area,cols,rows,crs:'EPSG:2154',x0:area[0]-step,n0:area[3]+step,step,
    units:'m',verticalDatum:'NGF-IGN69',haloNodes:1,interpolation:'fixed-diagonal-triangles',
    nodeRegistration:'grid-node',rowOrder:'north-to-south'};
  const data=Buffer.alloc(cols*rows*4),mask=Buffer.alloc(cols*rows,1);
  for(let row=0;row<rows;row++)for(let col=0;col<cols;col++){
    const e=header.x0+col*step,n=header.n0-row*step;
    data.writeFloatLE(20+(e-S.ORIGIN[0])/100+(n-S.ORIGIN[1])/50+change(col,row),4*(row*cols+col));
  }
  for(const index of missing)mask[index]=0;
  const gridHeader=JSON.stringify(header);
  return {schema:K.SCHEMA,encoding:'float32-le+valid-u8',gridHeader,
    dataBase64:data.toString('base64'),maskBase64:mask.toString('base64'),sha256:K.digest(gridHeader,data,mask),
    source:{truth:'Source raster declared for runtime QA',...(sourceGridSHA256?{sourceGridSHA256}: {})}};
}

function harness({downloaded=pack(),active=K.load(downloaded),baseline=active}={}){
  const tile={cellId:id,gridX:0,gridY:0,boundsL93:bounds,contentSHA256:contentSHA},files=new Map();
  const values={
    vector:{schema:'soma-massilia/geodata-cell/4',cellId:id,boundsL93:bounds,contentSHA256:contentSHA,
      sourceReceipt:{sha256:sourceSHA},featureCollection:{type:'FeatureCollection',features:[]}},
    terrain:downloaded,
    surfaces:{schema:'soma-metropole/surface-cell/1',cellId:id,sourcePbfSHA256:sourceSHA,contentSHA256:contentSHA,
      cell:{contentSHA256:contentSHA,sourceSHA256:sourceSHA,surfaces:{}}},
    navigation:{sourcePbfSHA256:sourceSHA,sourcePackSHA256:packSHA,cellHashes:{[id]:contentSHA}}
  };
  for(const layer of S.LAYERS){
    const bytes=zlib.gzipSync(Buffer.from(JSON.stringify(values[layer]))),file=`tiles/${id}.${layer}.json.gz`;
    tile[layer]={path:file,bytes:bytes.length,sha256:digest(bytes),encoding:'gzip-json'};files.set(file,bytes);
  }
  const manifest={schema:S.SCHEMA,crs:'EPSG:2154',units:'m',origin:S.ORIGIN,cellSize:250,
    source:{sha256:sourceSHA,license:'Runtime QA',attribution:'Runtime QA'},sourcePackSHA256:packSHA,
    target:{id:'200054807',boundarySHA256:null},coverageExplicitPartial:true,tiles:[tile]};
  const zone={v52CellId:id},record=values.vector,state={active,baseline,storeOptions:null,readError:null,baseEnters:0};
  const context=vm.createContext({URL,TextDecoder,TextEncoder,Response,console,setTimeout:()=>0,
    location:{href:'http://localhost/game.html'},document:{title:'',getElementById:()=>null,querySelector:()=>null},
    fetch:async()=>new Response(JSON.stringify(manifest)),zone});
  context.window=context;
  context.__SOMA__={};context.__SOMA_V68__={};
  context.__SOMA_V52__={district:{},records:()=>new Map([[id,record]]),zones:()=>new Map([[id,zone]])};
  context.__SOMA_V53_CORE__={metricCell:()=>({}),normalizeRecord:value=>value};
  context.__SOMA_NAV63_CORE__={validate:()=>true};
  context.__SOMA_V54__={enter:()=>{state.baseEnters++;return true;}};
  context.__SOMA_EXPLORE64__={catalog:()=>({sourcePbfSHA256:sourceSHA,sourcePackSHA256:packSHA})};
  context.__SOMA_TERRAIN56__={ready:true,core:K,get grid(){return state.baseline;},
    v69:{gridFor:()=>state.active,snapshot:()=>({})}};
  context.__SOMA_STREAM69_CORE__={...S,createTileStore(options){
    state.storeOptions=options;
    return S.createTileStore({...options,fetchBytes:async file=>{if(state.readError)throw Error(state.readError);return files.get(file);},
      decodeBytes:async bytes=>zlib.gunzipSync(bytes)});
  }};
  vm.runInContext(runtime,context,{filename:'actual-world-runtime69.js'});
  return {api:context.__SOMA_V69__,state,context,manifest,downloaded,files};
}

test('actual runtime admits a matching validated grid and an exact copy derived from the active baseline',async()=>{
  const direct=harness();
  assert.equal((await direct.api.load(id,{require3D:true})).readyFor3D,true);
  const baseline=K.load(pack({area:[bounds[0]-250,bounds[1]-250,bounds[2]+250,bounds[3]+250]}));
  const derived=harness({active:baseline,baseline,downloaded:pack({sourceGridSHA256:baseline.pack.sha256})});
  assert.equal((await derived.api.load(id,{require3D:true})).readyFor3D,true);
});

test('active terrain must exist, be complete and belong to the downloaded edition',async()=>{
  const downloaded=pack(),different=K.load(pack({change:()=>1}));
  const hole=K.load(pack({missing:[6*13+6]}));
  for(const active of [null,different,hole]){
    const h=harness({downloaded,active,baseline:active});
    assert.equal((await h.api.load(id,{require3D:true})).readyFor3D,false);
    await assert.rejects(h.api.enter(id),/liaisons de jeu/);
    assert.equal(h.state.baseEnters,0);
  }
});

test('a declared sourceGridSHA does not certify changed elevations, including cell edges',async()=>{
  const baseline=K.load(pack());
  for(const [col,row] of [[6,6],[1,1],[11,11]]){
    const downloaded=pack({sourceGridSHA256:baseline.pack.sha256,change:(x,y)=>x===col&&y===row?.01:0});
    const h=harness({downloaded,active:baseline,baseline});
    assert.equal((await h.api.load(id,{require3D:true})).readyFor3D,false);
  }
});

test('a sourceGridSHA derivation is admitted only against the active baseline, with matching step and datum',async()=>{
  const active=K.load(pack({area:[bounds[0]-250,bounds[1]-250,bounds[2]+250,bounds[3]+250]}));
  const otherBaseline=K.load(pack({change:()=>2}));
  const unrelated=harness({active,baseline:otherBaseline,downloaded:pack({sourceGridSHA256:active.pack.sha256})});
  assert.equal((await unrelated.api.load(id,{require3D:true})).readyFor3D,false);
  for(const mutation of [g=>g.step=5,g=>g.verticalDatum='ELLIPSOID',g=>g.crs='EPSG:4326',g=>g.units='ft']){
    const candidate=K.load(pack());mutation(candidate);
    const h=harness({active:candidate,baseline:candidate});
    assert.equal((await h.api.load(id,{require3D:true})).readyFor3D,false);
  }
});

test('one metre terrain is bounded to 251 by 251 interior nodes and still checks the far cell corner',async()=>{
  const downloaded=pack({step:1}),active=K.load(downloaded),h=harness({downloaded,active});
  const entry=await h.api.load(id,{require3D:true});
  assert.equal(entry.readyFor3D,true);
  active.heights[251*253+251]+=.1;
  assert.equal(h.state.storeOptions.canActivate(entry),false);
});

test('rechecking the same mutable active Grid detects altered heights and masks despite retained hashes',async()=>{
  for(const mutate of [g=>g.heights[6*13+6]+=.1,g=>g.mask[6*13+6]=0]){
    const h=harness(),entry=await h.api.load(id,{require3D:true});
    assert.equal(entry.readyFor3D,true);
    mutate(h.state.active);
    assert.equal(h.state.storeOptions.canActivate(entry),false);
  }
});

test('downloaded NoData is rejected, and load errors are recorded then cleared after successful retry',async()=>{
  const partial=harness({downloaded:pack({missing:[6*13+6]})});
  await assert.rejects(partial.api.load(id,{require3D:true}),/Relief incomplet/);
  assert.match(partial.api.snapshot().lastError,/Relief incomplet/);
  const h=harness();h.state.readError='HTTP 404 asset unavailable';
  await assert.rejects(h.api.load(id,{require3D:true}),/HTTP 404/);
  assert.match(h.api.snapshot().lastError,/HTTP 404/);
  h.state.readError=null;
  assert.equal((await h.api.load(id,{require3D:true})).readyFor3D,true);
  assert.equal(h.api.snapshot().lastError,'');
});
