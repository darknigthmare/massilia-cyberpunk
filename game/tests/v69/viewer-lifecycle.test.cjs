const test=require('node:test'),assert=require('node:assert/strict');
const V=require('../../src/v69/metropole-viewer.js');

test('viewer manifest URLs are relative same-origin paths, not scripts or directory escapes',()=>{
  assert.equal(V.safeWorldPath('data/v69/metropole/manifest.json'),true);
  assert.equal(V.safeWorldPath('data/v69/world/manifest.json'),true);
  for(const path of ['https://example.com/a.json','//example.com/a.json','../manifest.json','data/../manifest.json','/data/manifest.json','javascript:alert(1)','data/world.json?x=1','data//world.json','data/%2e%2e/a.json'])assert.equal(V.safeWorldPath(path),false);
});
test('GPU lifecycle frees superseded, detached and unprotected geometry',()=>{
  let serial=0;const freed=[];const driver={upload:()=>++serial,release:handle=>freed.push(handle)},registry=V.sceneRegistry(driver,216);
  const geometry={vertices:new Float32Array(27),geometryBytes:108};
  registry.attach('a',geometry,{});registry.attach('b',geometry,{});assert.equal(registry.snapshot().bytes,216);
  registry.attach('a',geometry,{});assert.deepEqual(freed,[1]);assert.equal(registry.snapshot().meshes,2);
  registry.prune(new Set(['a']));assert.deepEqual(freed,[1,2]);assert.equal(registry.snapshot().bytes,108);
  registry.clear();assert.deepEqual(freed,[1,2,3]);assert.equal(registry.snapshot().bytes,0);
});
test('GPU budget refusal preserves previously attached geometry without leaking a buffer',()=>{
  let uploads=0;const registry=V.sceneRegistry({upload:()=>++uploads,release(){}},108),geometry={vertices:new Float32Array(27),geometryBytes:108};
  registry.attach('a',geometry,{});assert.throws(()=>registry.attach('b',geometry,{}),RangeError);
  assert.equal(uploads,1);assert.equal(registry.snapshot().meshes,1);
});
test('survol requires only vector and terrain descriptors and does not require navigation',()=>{
  const manifest={origin:[0,0],tiles:[
    {cellId:'center',gridX:0,gridY:0,vector:{},terrain:{},navigation:null},
    {cellId:'missing',gridX:1,gridY:0,vector:{},terrain:null},
    {cellId:'far',gridX:5,gridY:5,vector:{},terrain:{}}]};
  assert.deepEqual(V.desiredTiles(manifest,0,0).map(t=>t.cellId),['center']);
});

test('mixed flight targets admit explicitly typed terrain-only cells without vector coverage',()=>{
  const tiles=[{cellId:'vector',gridX:0,gridY:0,vector:{},terrain:{}},
    {cellId:'dem',gridX:1,gridY:0,terrainOnly:true,vector:null,terrain:{}},
    {cellId:'ambiguous',gridX:0,gridY:1,vector:null,terrain:{}},
    {cellId:'contradictory',gridX:1,gridY:1,terrainOnly:true,vector:{},terrain:{}}];
  assert.deepEqual(V.desiredTiles({origin:[0,0],tiles},0,0).map(t=>t.cellId),['vector','dem']);
  assert.deepEqual(V.flightLayers(tiles[0]),['vector','terrain']);
  assert.deepEqual(V.flightLayers(tiles[1]),['terrain']);
  assert.equal(V.flightLayers(tiles[2]),null);assert.equal(V.flightLayers(tiles[3]),null);
});

function mixedFixture(){
  const K=require('../../src/v69/streaming-core.js'),zlib=require('node:zlib'),crypto=require('node:crypto'),files=new Map();
  const source='a'.repeat(64),manifest={schema:K.SCHEMA,crs:'EPSG:2154',units:'m',origin:K.ORIGIN.slice(),cellSize:250,
    source:{sha256:source,license:'QA fixture only',attribution:'Not geographic coverage'},
    target:{id:'200054807',boundarySHA256:null},coverageExplicitPartial:true,tiles:[]};
  for(let x=0;x<3;x++){
    const cellId=x?`V52-MC-E0${x}-S00`:'V52-MC-33',e=K.ORIGIN[0]+250*x,n=K.ORIGIN[1],bounds=[e-125,n-125,e+125,n+125];
    const tile={cellId,gridX:x,gridY:0,boundsL93:bounds,vector:null,terrain:null,surfaces:null,navigation:null,contentSHA256:null};
    if(x)tile.terrainOnly=true;
    for(const layer of x?['terrain']:['vector','terrain']){
      const value=layer==='terrain'?{schema:'qa/terrain',cellId}:{schema:'soma-massilia/geodata-cell/4',cellId,boundsL93:bounds,
        sourceReceipt:{sha256:source},featureCollection:{type:'FeatureCollection',features:[]}};
      const bytes=zlib.gzipSync(Buffer.from(JSON.stringify(value))),path=`tiles/${cellId}/${layer}.json.gz`;files.set(path,bytes);
      tile[layer]={path,bytes:bytes.length,sha256:crypto.createHash('sha256').update(bytes).digest('hex'),encoding:'gzip-json'};
    }manifest.tiles.push(tile);
  }
  return{K,manifest,files};
}

test('real mixed stream fetches no vector for DEM targets and cached targets keep their verified layers',async()=>{
  const f=mixedFixture(),reads=[],attached=[],store=f.K.createTileStore({manifest:f.manifest,
    fetchBytes:async(path,settings)=>{reads.push([settings.tile.cellId,settings.layer]);return f.files.get(path);},
    onAttach:(id,entry)=>attached.push(entry)});
  const results=await V.requestFlightTiles(store,f.manifest.tiles.slice(0,2));
  assert(results.every(r=>r.status==='fulfilled'));
  const before=store.get(f.manifest.tiles[0].cellId),count=reads.length;
  const cached=await V.requestFlightTiles(store,f.manifest.tiles.slice(0,2));
  assert(cached.every(r=>r.status==='fulfilled'));assert.equal(reads.length,count);
  const after=store.get(before.cellId);assert.notEqual(before,after,'Cached wrappers change identity.');
  assert.equal(after.layers.vector,before.layers.vector);
  assert.equal(store.get(f.manifest.tiles[1].cellId).layers.vector,undefined);
  assert.deepEqual(reads.filter(([id])=>id===f.manifest.tiles[1].cellId),[[f.manifest.tiles[1].cellId,'terrain']]);
  assert.deepEqual(store.snapshot().readyFor3D,[]);assert.equal(attached.length,2);
});

test('mixed target changes cancel stale DEM attachment and respect the real cache budget',async()=>{
  const f=mixedFixture(),old=f.manifest.tiles[1],next=f.manifest.tiles[2],attached=[];
  let release;const gate=new Promise(resolve=>release=resolve);
  const store=f.K.createTileStore({manifest:f.manifest,maxResidentBytes:80,memoryFactor:1,
    fetchBytes:async(path,settings)=>{if(settings.tile.cellId===old.cellId)await gate;return f.files.get(path);},
    onAttach:id=>{attached.push(id);}});
  const stale=V.requestFlightTiles(store,[old]);
  const current=await V.requestFlightTiles(store,[next]);assert.equal(current[0].status,'fulfilled');
  release();const cancelled=await stale;assert.equal(cancelled[0].status,'rejected');
  assert.equal(cancelled[0].reason.name,'AbortError');assert.deepEqual(attached,[next.cellId]);
  await V.requestFlightTiles(store,[old]);
  const stats=store.snapshot();assert(stats.accountedBytes<=80);assert(stats.cancelled>0);assert(stats.evictions>0);
  assert.deepEqual(stats.residentIds,[old.cellId]);assert.deepEqual(stats.readyFor3D,[]);
});

test('manifest reads count UTF-8 bytes and cancel their stream on budget overflow',async()=>{
  let cancelled=false;
  const source=new TextEncoder().encode('{"nom":"métropole"}');
  const response=()=>new Response(new ReadableStream({start(c){c.enqueue(source);},cancel(){cancelled=true;}}));
  await assert.rejects(V.readJSON('qa.json',source.byteLength-1,async()=>response()),/budget/);assert.equal(cancelled,true);
  const complete=()=>new Response(new ReadableStream({start(c){c.enqueue(source);c.close();}}));
  assert.deepEqual(await V.readJSON('qa.json',source.byteLength,async()=>complete()),{nom:'métropole'});
  await assert.rejects(V.readJSON('qa.json',100,async()=>new Response('{"__proto__":{}}')),/interdite/);
});

function partsFixture(){
  const crypto=require('node:crypto'),K=require('../../src/v69/streaming-core.js');
  const source='a'.repeat(64),pack='b'.repeat(64),proofHash='c'.repeat(64);
  const proof={schema:'soma-massilia/building-parts-proof/1',sourceSHA256:source,proofSHA256:proofHash,
    selectionProvenance:{vectorManifestSHA256:pack},parents:{},partParents:{},meaning:'Fixture mémoire — aucune couverture géographique'};
  const fixture={proof,manifest:{source:{sha256:source},sourcePackSHA256:pack},url:'https://viewer.example/data/world/manifest.json',sha256:K.sha256};
  fixture.setBytes=bytes=>{
    fixture.bytes=Buffer.from(bytes);
    fixture.manifest.buildingParts={path:'proofs/building-parts.json',encoding:'json',bytes:fixture.bytes.length,
      sha256:crypto.createHash('sha256').update(fixture.bytes).digest('hex'),proofSHA256:proofHash,sourcePbfSHA256:source};
  };
  fixture.setBytes(JSON.stringify(proof));
  fixture.fetcher=async()=>new Response(fixture.bytes);
  fixture.load=options=>V.loadBuildingParts(fixture.manifest,fixture.url,{fetcher:fixture.fetcher,sha256:fixture.sha256,...options});
  return fixture;
}

test('world building-parts metadata binds verified UTF-8 bytes to the PBF and vector manifest',async()=>{
  const f=partsFixture(),requests=[],controller=new AbortController(),before=JSON.stringify(f.manifest);
  const proof=await f.load({signal:controller.signal,fetcher:async(url,settings)=>{
    requests.push([String(url),settings]);return new Response(f.bytes);
  }});
  assert.deepEqual(proof,f.proof);assert.equal(JSON.stringify(f.manifest),before);
  assert.equal(requests.length,1);assert.equal(requests[0][0],'https://viewer.example/data/world/proofs/building-parts.json');
  assert.equal(requests[0][1].signal,controller.signal);assert.equal(requests[0][1].credentials,'same-origin');
  assert.equal(requests[0][1].redirect,'error');
});

test('without building-parts metadata only an embedded proof from the same PBF is retained',async()=>{
  const source='a'.repeat(64),embeddedProof={sourceSHA256:source,parents:{legacy:{}}},manifest={source:{sha256:source}};
  const fetcher=async()=>{throw new Error('No proof asset should be fetched.');};
  assert.equal(await V.loadBuildingParts(manifest,'https://viewer.example/world.json',{embeddedProof,fetcher}),embeddedProof);
  assert.equal(await V.loadBuildingParts({source:{sha256:'b'.repeat(64)}},'https://viewer.example/world.json',{embeddedProof,fetcher}),null);
  assert.equal(await V.loadBuildingParts(manifest,'https://viewer.example/world.json',{fetcher}),null);
});

test('proof descriptors reject unsafe paths, encodings, hashes and source drift before fetching',async()=>{
  const invalid=[{path:'https://elsewhere.example/proof.json'},{path:'//elsewhere.example/proof.json'},{path:'../proof.json'},
    {path:'proofs/../proof.json'},{path:'/proof.json'},{path:'proofs//proof.json'},{path:'proofs/%2e%2e/proof.json'},
    {path:'proof.json?cache=1'},{path:'proof.json#fragment'},{encoding:'gzip-json'},{bytes:0},{bytes:-1},{bytes:1.5},
    {bytes:64*1024*1024+1},{bytes:NaN},{sha256:'bad'},{proofSHA256:'bad'},{sourcePbfSHA256:'bad'},
    {sourcePbfSHA256:'d'.repeat(64)}];
  for(const patch of invalid){
    const f=partsFixture();Object.assign(f.manifest.buildingParts,patch);let fetched=false;
    await assert.rejects(f.load({fetcher:async()=>{fetched=true;return new Response(f.bytes);}}),JSON.stringify(patch));
    assert.equal(fetched,false,JSON.stringify(patch));
  }
  const noHash=partsFixture();await assert.rejects(noHash.load({sha256:undefined}));
});

test('proof payload rejects schema, proof hash, PBF or vector-manifest mismatches after byte validation',async()=>{
  for(const patch of [{schema:'wrong-proof/1'},{proofSHA256:'d'.repeat(64)},{sourceSHA256:'d'.repeat(64)},
    {selectionProvenance:{vectorManifestSHA256:'d'.repeat(64)}},{selectionProvenance:{}},
    {selectionProvenance:{vectorManifestSHA256:'bad'}}]){
    const f=partsFixture();f.setBytes(JSON.stringify({...f.proof,...patch}));await assert.rejects(f.load(),JSON.stringify(patch));
  }
  for(const pack of [undefined,null,'bad']){
    const f=partsFixture();f.manifest.sourcePackSHA256=pack;await assert.rejects(f.load());
  }
});

test('proof HTTP failure, redirects, byte drift and invalid JSON never fall back to embedded evidence',async()=>{
  const embeddedProof={sourceSHA256:'a'.repeat(64),parents:{mustNotReplaceFailedDescriptor:{}}};
  for(const status of [404,500]){
    const f=partsFixture();await assert.rejects(f.load({embeddedProof,fetcher:async()=>new Response('',{status})}));
  }
  const redirect=partsFixture();await assert.rejects(redirect.load({fetcher:async()=>{
    const response=new Response(redirect.bytes);Object.defineProperty(response,'redirected',{value:true});return response;
  }}));
  const oversize=partsFixture();await assert.rejects(oversize.load({fetcher:async()=>new Response(Buffer.concat([oversize.bytes,Buffer.from(' ')]))}));
  const short=partsFixture();await assert.rejects(short.load({fetcher:async()=>new Response(short.bytes.subarray(1))}));
  const mismatch=partsFixture(),altered=Buffer.from(mismatch.bytes);altered[altered.length-3]^=1;
  await assert.rejects(mismatch.load({fetcher:async()=>new Response(altered)}));
  const malformed=partsFixture();malformed.setBytes('{not-json}');await assert.rejects(malformed.load());
});

test('proof JSON refuses prototype-related keys and malformed UTF-8 even with a matching asset hash',async()=>{
  for(const key of ['__proto__','prototype','constructor']){
    const f=partsFixture();f.setBytes('{"nested":{"'+key+'":{}},'+JSON.stringify(f.proof).slice(1));await assert.rejects(f.load(),key);
  }
  const f=partsFixture();f.setBytes(Buffer.from([123,34,120,34,58,34,0xc3,0x28,34,125]));await assert.rejects(f.load());
});

test('proof and manifest readers propagate an aborted signal before publishing data',async()=>{
  const controller=new AbortController();controller.abort();let reads=0;
  const f=partsFixture();await assert.rejects(f.load({signal:controller.signal,fetcher:async()=>{reads++;return new Response(f.bytes);}}),{name:'AbortError'});
  await assert.rejects(V.readJSON('qa.json',100,async()=>{reads++;return new Response('{}');},controller.signal),{name:'AbortError'});
  assert.equal(reads,0);
});

test('aborting a blocked manifest or proof body cancels its stream and releases the reader',async()=>{
  for(const kind of ['manifest','parts']){
    const f=partsFixture(),controller=new AbortController(),blocked=deferred();let cancelled=0,cancelReason,published=false;
    const body=new ReadableStream({start(stream){stream.enqueue(f.bytes.subarray(0,16));},
      cancel(reason){cancelled++;cancelReason=reason;}});
    const getReader=body.getReader.bind(body);
    body.getReader=(...args)=>{const reader=getReader(...args),read=reader.read.bind(reader);let reads=0;
      reader.read=()=>{const result=read();if(++reads===2)blocked.resolve();return result;};return reader;};
    const fetcher=async()=>new Response(body);
    const pending=(kind==='manifest'?V.readJSON('qa.json',f.bytes.length,fetcher,controller.signal):
      f.load({signal:controller.signal,fetcher})).then(value=>{published=true;return value;});
    const rejected=assert.rejects(pending,{name:'AbortError'});
    await blocked.promise;assert.equal(body.locked,true,`${kind}: reader holds the pending second read`);
    controller.abort();await rejected;
    assert.equal(cancelled,1,`${kind}: underlying body cancelled exactly once`);
    assert.equal(cancelReason.name,'AbortError');assert.equal(body.locked,false,`${kind}: reader lock released`);
    assert.equal(published,false,`${kind}: incomplete JSON never published`);
  }
});

function deferred(){let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return{promise,resolve,reject};}

test('atomic world loading commits only the newest prepared world when an older request resolves late',async()=>{
  const old=deferred(),signals=[],commits=[];
  const loader=V.atomicWorldLoader({prepare:async(argument,context)=>{signals.push([argument,context]);return argument==='old'?old.promise:{world:argument};},
    commit:(prepared,argument)=>{commits.push([prepared,argument]);return 'committed-'+argument;}});
  const stale=loader.load('old'),rejected=assert.rejects(stale,{name:'AbortError'});
  assert.equal(await loader.load('new'),'committed-new');
  assert.equal(signals[0][1].signal.aborted,true);assert.equal(signals[1][1].signal.aborted,false);
  assert.ok(signals[1][1].nonce>signals[0][1].nonce);
  old.resolve({world:'old'});await rejected;assert.deepEqual(commits,[[{world:'new'},'new']]);
});

test('atomic world prepare failure preserves the previously committed world',async()=>{
  let current='initial',commits=0;const failure=new Error('Proof provenance rejected');
  const loader=V.atomicWorldLoader({prepare:async argument=>{if(argument==='bad')throw failure;return argument;},
    commit:prepared=>{current=prepared;commits++;return current;}});
  assert.equal(await loader.load('first'),'first');await assert.rejects(loader.load('bad'),error=>error===failure);
  assert.equal(current,'first');assert.equal(commits,1);
});

test('atomic cancel stops late publication even when preparation ignores abort',async()=>{
  const gate=deferred(),commits=[];let signal;
  const loader=V.atomicWorldLoader({prepare:async(argument,context)=>{signal=context.signal;return gate.promise;},commit:prepared=>commits.push(prepared)});
  const pending=loader.load('cancelled'),rejected=assert.rejects(pending,{name:'AbortError'});loader.cancel();
  assert.equal(signal.aborted,true);gate.resolve('late-data');await rejected;assert.deepEqual(commits,[]);
});

function geometryHistoryFixture(){
  const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),crypto=require('node:crypto');
  const html=fs.readFileSync(path.resolve(__dirname,'../../baseline/v66.html'),'utf8');
  function core(id){const source=html.match(new RegExp('<script[^>]*id="'+id+'"[^>]*>([\\s\\S]*?)<\\/script>'))[1],context=vm.createContext({module:{exports:{}},TextEncoder,TextDecoder,atob:x=>Buffer.from(x,'base64').toString('binary')});vm.runInContext(source,context);return context.module.exports;}
  const G=core('soma-v53-core'),T=core('soma-v56-terrain-core'),F=core('soma-v59-core'),A=require('../../src/v69/roof-core.js');
  const Geometry=require('../../src/v69/metropole-viewer-core.js'),K=require('../../src/v69/streaming-core.js');
  const origin=K.ORIGIN,id='osm/way/777',geometrySHA='1'.repeat(64),sourceSHA='2'.repeat(64);
  function fragment(west,east,cut){
    const south=origin[1]-10,north=origin[1]+10,ring=[[west,south],[east,south],[east,north],[west,north],[west,south]];
    const walls=ring.slice(1).map((q,i)=>[ring[i],q]).filter((_,i)=>i!==cut);
    return{id,properties:{canonical_id:id,'soma:layer':'buildings','soma:geometry_sha256':geometrySHA,
      building:'apartments',height:'12','roof:shape':'skillion','roof:height':'2','roof:direction':'90',
      'soma:sourceBoundsL93':[origin[0]+350,south,origin[0]+400,north],
      'soma:mesh53':[{ringsL93:[ring],trianglesL93:[[ring[0],ring[1],ring[2]],[ring[0],ring[2],ring[3]]],wallsL93:walls,areaM2:(east-west)*20}]}};
  }
  function entry(x,y,height=10,missing=false){
    const cellId=`V52-MC-${y+3}${x+3}`,e=origin[0]+x*250,n=origin[1]-y*250,bounds=[e-125,n-125,e+125,n+125];
    const features=x===1&&y===0?[fragment(origin[0]+350,origin[0]+375,1)]:x===2&&y===0?[fragment(origin[0]+375,origin[0]+400,3)]:[];
    const grid=new T.Grid({x0:bounds[0],n0:bounds[3],step:125,cols:3,rows:3},new Float32Array(9).fill(height),new Uint8Array(9).fill(missing?0:1),{},{});
    return{cellId,tile:{boundsL93:bounds},layers:{vector:{cellId,boundsL93:bounds,v53Validated:true,v53Synthetic:false,
      sourceReceipt:{sha256:sourceSHA},contentSHA256:crypto.createHash('sha256').update(cellId).digest('hex'),featureCollection:{type:'FeatureCollection',features}},terrain:{grid,pack:{}}}};
  }
  const entries=new Map();for(let y=-1;y<=1;y++)for(let x=-1;x<=1;x++){const value=entry(x,y);entries.set(value.cellId,value);}
  return{entries,targetIds:[...entries.keys()],outside:entry(2,0,100),outsideNoData:entry(2,0,100,true),id,
    deps:{geo:G,terrain:T,fidelity:F,architecture:A},Geometry,A};
}

test('geometry options and all nine target buffers ignore higher or NoData fragments outside the target set',()=>{
  const f=geometryHistoryFixture(),before=JSON.stringify([...f.entries.values()].map(e=>e.layers.vector)),orders=[];
  const architecture={...f.A,referenceIndex(records){const rows=[...records];orders.push(rows.map(r=>r.cellId));return f.A.referenceIndex(rows);}};
  const baseline=V.geometryOptions(f.entries,f.targetIds,architecture),render=(entries,options)=>f.targetIds.slice().sort().map(id=>f.Geometry.buildTile(entries.get(id),f.deps,{...options,details:false}));
  const expected=render(f.entries,baseline);assert.equal(expected.length,9);assert.equal(baseline.canonicalDatumsMap.get(f.id),10);
  assert.equal([...baseline.references.values()][0].complete,false,'Only the source fragment inside the target is available.');
  assert.equal(baseline.maxVertices,600000);assert.equal(baseline.maxWindowRows,3);
  for(const outside of [f.outside,f.outsideNoData]){
    const cached=new Map([...f.entries,[outside.cellId,outside]]),reverse=new Map([...cached].reverse());
    for(const [entries,targets]of [[cached,f.targetIds],[reverse,new Set(f.targetIds.slice().reverse())]]){
      const options=V.geometryOptions(entries,targets,architecture),actual=render(entries,options);
      assert.deepEqual(options,baseline,'Non-target residents must not affect datums, NoData, roofs or proof options.');
      for(let i=0;i<9;i++){
        assert.deepEqual(actual[i].vertices,expected[i].vertices,`Exact Float32 buffer for ${f.targetIds.slice().sort()[i]}`);
        assert.equal(actual[i].geometryBytes,expected[i].geometryBytes);assert.deepEqual(actual[i].counts,expected[i].counts);
      }
    }
  }
  assert(orders.every(order=>JSON.stringify(order)===JSON.stringify(f.targetIds.slice().sort())),'Reference records are always selected in sorted target order.');
  const explicitEntries=new Map([...f.entries,[f.outside.cellId,f.outside]]),explicit=V.geometryOptions(explicitEntries,[...f.targetIds,f.outside.cellId],f.A);
  assert(Math.abs(explicit.canonicalDatumsMap.get(f.id)-100)<1e-9,'The outside fragment must affect the datum when deliberately included as a target.');
  assert.equal([...explicit.references.values()][0].complete,true,'The second source fragment closes the canonical roof boundary.');
  const changed=render(explicitEntries,explicit);assert(changed.some((value,i)=>!Buffer.from(value.vertices.buffer).equals(Buffer.from(expected[i].vertices.buffer))),'The fixture must detect the original geometry-changing aggregation bug.');
  const missingEntries=new Map([...f.entries,[f.outsideNoData.cellId,f.outsideNoData]]),missing=V.geometryOptions(missingEntries,[...f.targetIds,f.outsideNoData.cellId],f.A);
  assert.equal(missing.missingCanonicalDatums.has(f.id),true,'NoData propagates only when that fragment is explicitly targeted.');
  assert.equal(JSON.stringify([...f.entries.values()].map(e=>e.layers.vector)),before,'No source feature is mutated.');
});
