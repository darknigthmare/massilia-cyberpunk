'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),zlib=require('node:zlib'),crypto=require('node:crypto'),cp=require('node:child_process');
const game=path.resolve(__dirname,'../..'),world=process.env.MASSILIA_ROOF_WORLD||path.join(game,'data/v69/metropole'),manifestPath=path.join(world,'manifest.json');
const CELLS=['V52-MC-41','V52-MC-42','V52-MC-43','V52-MC-52','V52-MC-W03-N01','V52-MC-W04-N01','V52-MC-W04-S00','V52-MC-W04-S01','V52-MC-W05-S01','V52-MC-W05-S02','V52-MC-W06-S02','V52-MC-W10-N71'];
const ROOFS=['osm/way/264740443','osm/way/264740444'],BODY='osm/way/264740436',PARENT='osm/way/264740428';
const sha=b=>crypto.createHash('sha256').update(b).digest('hex'),clone=x=>JSON.parse(JSON.stringify(x)),close=(a,b,t=1e-5)=>assert(Math.abs(a-b)<=t,`${a} != ${b}`);
function extract(html,id){const m=html.match(new RegExp('<script id="'+id+'">([\\s\\S]*?)</script>'));assert(m,'Required parent '+id);return m[1];}
function runtime(html){
 const c=vm.createContext({module:{exports:{}},Float32Array,TextEncoder,TextDecoder,atob:x=>Buffer.from(x,'base64').toString('binary')});
 for(const id of ['viewer-geographic-core','viewer-terrain-core','viewer-dimension-core','viewer-fidelity72-core','viewer-architecture-core','viewer-roof-core','viewer-roof-fidelity73-core','viewer-material-extension70','viewer-architecture71-core','viewer-road72-core','viewer-metropole-viewer-core',...(html.includes('id="viewer-architecture74-core"')?['viewer-architecture74-core']:[]),'viewer-metropole-viewer'])vm.runInContext(extract(html,id),c);
 return {G:c.__SOMA_V53_CORE__,T:c.__SOMA_TERRAIN56_CORE__,F:c.__SOMA_FIDELITY59_CORE__,A:c.__SOMA_ARCH68_CORE__,V:c.__SOMA_METRO_VIEW_CORE__,U:c.__SOMA_METRO_VIEWER_UTILS__,D:c.__SOMA_ARCHITECTURE74__};
}
test('real native AMP: only reviewed roof datums rise; body, terrain, footprints, courtyard and cell-boundary controls remain identical',
 {skip:!fs.existsSync(manifestPath)||!fs.existsSync(path.join(game,'metropole-viewer-v73.html'))},()=>{
 const parent=fs.readFileSync(path.join(game,'metropole-viewer-v73.html'),'utf8');
 const patched=cp.execFileSync('python3',['-B','-c',"import sys;from pathlib import Path;sys.path.insert(0,'game');from tools import v74_architecture as a;print(a.patch_viewer(Path('game/metropole-viewer-v73.html').read_text(),{n:Path('game/src/v74',n+'.js').read_text() for n in a.MODULES}),end='')"],{cwd:path.dirname(game),maxBuffer:4*1024*1024}).toString();
 const old=runtime(parent),now=runtime(patched),manifestRaw=fs.readFileSync(manifestPath),manifest=JSON.parse(manifestRaw),assets=[];
 function checked(d,gzip=true){const raw=fs.readFileSync(path.join(world,d.path));assert.equal(raw.length,d.bytes);assert.equal(sha(raw),d.sha256);assets.push(d);return JSON.parse(gzip?zlib.gunzipSync(raw):raw);}
 const parts=checked(manifest.buildingParts,false),entries=new Map();
 for(const id of CELLS){const tile=manifest.tiles.find(t=>t.cellId===id);assert(tile);const raw=checked(tile.vector),pack=checked(tile.terrain),surfaces=checked(tile.surfaces);
  const vector=now.G.normalizeRecord(raw,id,{cells:[{id,boundsL93:tile.boundsL93}]}),grid=now.T.load(pack,tile.boundsL93);
  entries.set(id,{tile,layers:{vector,terrain:{grid,pack},surfaces}});}
 const originalRecords=JSON.stringify([...entries.values()].map(e=>e.layers.vector)),originalParts=JSON.stringify(parts);
 const optionStart=performance.now(),before=old.U.geometryOptions(entries,CELLS,old.A,parts),parentOptionsMilliseconds=performance.now()-optionStart;
 const extendedStart=performance.now(),after=now.U.geometryOptions(entries,CELLS,now.A,parts),extendedOptionsMilliseconds=performance.now()-extendedStart,snapshot=now.D.snapshot();
 assert.deepEqual(clone(snapshot.associations.map(x=>x.id)),ROOFS);assert.equal(snapshot.sourceResolutionIsNotSurveyAccuracy,true);
 close(before.canonicalDatumsMap.get(ROOFS[0]),1.3091010262756106);close(before.canonicalDatumsMap.get(ROOFS[1]),1.2997249733805174);
 close(after.canonicalDatumsMap.get(BODY),3.284224984173694);close(after.canonicalDatumsMap.get(PARENT),3.284224984173694);
 for(const [id,h]of before.canonicalDatumsMap)if(!ROOFS.includes(id))assert.equal(after.canonicalDatumsMap.get(id),h);
 const cells=[],roofs=[],courtyardControls=[],fragmentControls=new Map();let linkedPartControls=0;
 const rangeBytes=(g,r)=>Buffer.from(g.vertices.buffer,g.vertices.byteOffset+r.start*36,(r.end-r.start)*36);
 for(const [cellId,entry]of entries){
  const a=old.V.buildTile(entry,{geo:old.G,terrain:old.T,fidelity:old.F,architecture:old.A},{...before,details:false});
  const b=now.V.buildTile(entry,{geo:now.G,terrain:now.T,fidelity:now.F,architecture:now.A},{...after,details:false});
  assert.equal(a.vertices.length,b.vertices.length);assert.deepEqual(clone(a.counts),clone(b.counts));const changed=new Set();
  for(const r of b.architecture71.ranges){const prev=a.architecture71.ranges.find(x=>x.facts.id===r.facts.id);assert(prev);assert.equal(prev.start,r.start);assert.equal(prev.end,r.end);
   if(ROOFS.includes(r.facts.id)){
    const delta=r.facts.baseAltitudeNGFMeters-prev.facts.baseAltitudeNGFMeters;assert(delta>1.9);assert.equal(r.facts.datum74.osmRelation,false);assert.equal(r.facts.baseQuality,'derived-shared-source-foundation');
    let min=Infinity,max=-Infinity,beforeBelowBodyTop=0;
    for(let i=r.start*9;i<r.end*9;i+=9){changed.add(i+1);close(b.vertices[i+1]-a.vertices[i+1],delta);min=Math.min(min,b.vertices[i+1]);max=Math.max(max,b.vertices[i+1]);if(a.vertices[i+1]<after.canonicalDatumsMap.get(BODY)+20-1e-5)beforeBelowBodyTop++;}
    close(min,after.canonicalDatumsMap.get(BODY)+20);close(max,after.canonicalDatumsMap.get(BODY)+23);assert(beforeBelowBodyTop>0);
    roofs.push({id:r.facts.id,cellId,baseBeforeNGF:prev.facts.baseAltitudeNGFMeters,baseAfterNGF:r.facts.baseAltitudeNGFMeters,minRenderedNGF:min,maxRenderedNGF:max,beforeVerticesBelowBodyTop:beforeBelowBodyTop,afterVerticesBelowBodyTop:0,datum:r.facts.datum74});
   }else{assert(rangeBytes(a,prev).equals(rangeBytes(b,r)),'Unchanged body/part '+r.facts.id);if(parts.partParents[r.facts.id])linkedPartControls++;
    const f=entry.layers.vector.featureCollection.features.find(f=>f.id===r.facts.id);if(f?.properties['soma:mesh53']?.some(m=>m.ringsL93.length>1))courtyardControls.push({id:r.facts.id,cellId});
    if(!fragmentControls.has(r.facts.id))fragmentControls.set(r.facts.id,[]);fragmentControls.get(r.facts.id).push(cellId);}
  }
  for(let i=0;i<a.vertices.length;i++)if(!changed.has(i))assert.equal(b.vertices[i],a.vertices[i],'Only roof Y coordinates may change');
  cells.push({cellId,geometryBytes:b.geometryBytes,nativeTerrainTriangles:b.counts.terrainTriangles,unchangedTerrainRoadsBodyPartsAndColours:true});
 }
 assert.equal(roofs.length,2);assert(linkedPartControls>0);assert(courtyardControls.length>0);const cellBoundaryControls=[...fragmentControls].filter(([,v])=>v.length>1);assert(cellBoundaryControls.length>0);
 const sourceEntry=entries.get('V52-MC-41'),referenceIndex=now.A.referenceIndex([...entries.values()].map(e=>e.layers.vector));
 const reference=id=>{const f=sourceEntry.layers.vector.featureCollection.features.find(f=>f.id===id);return referenceIndex.get(now.A.referenceKey(f.properties,id,sourceEntry.layers.vector));};
 for(const id of ROOFS){assert(now.D.contained(reference(id),reference(PARENT)));assert.equal(now.D.contained(reference(id),reference(PARENT),0),false);}
 // Real corpus refusals: NoData, stale cells, synthetic records, wrong tags,
 // source-identity mismatch and an independently matching outline.
 function refused(mutate){const copies=new Map([...entries].map(([id,e])=>[id,{...e,layers:{...e.layers,vector:clone(e.layers.vector)}}]));mutate(copies);const out=now.U.geometryOptions(copies,CELLS,now.A,parts);assert.equal(out.architectureDatum74?.size||0,0);}
 refused(e=>{e.get('V52-MC-41').layers.vector.contentSHA256='f'.repeat(64);});
 refused(e=>{e.get('V52-MC-41').layers.vector.v53Synthetic=true;});
 refused(e=>{e.get('V52-MC-41').layers.vector.sourceReceipt.sha256='f'.repeat(64);});
 refused(e=>{for(const f of e.get('V52-MC-41').layers.vector.featureCollection.features)if(ROOFS.includes(f.id))f.properties.min_height='19';});
 refused(e=>{const r=e.get('V52-MC-41').layers.vector,f=clone(r.featureCollection.features.find(f=>f.id===PARENT));f.id=f.properties.canonical_id='osm/way/999999999';r.featureCollection.features.push(f);});
 refused(e=>{const r=e.get('V52-MC-41').layers.vector,f=clone(r.featureCollection.features.find(f=>f.id===PARENT));f.id=f.properties.canonical_id='osm/way/999999999';for(const mesh of f.properties['soma:mesh53'])mesh.wallsL93=[];r.featureCollection.features.push(f);});
 const noData=old.U.geometryOptions(entries,CELLS,old.A,parts);noData.missingCanonicalDatums.add(PARENT);now.D.reconcile([...entries.values()],now.A,parts,noData);assert.equal(now.D.snapshot().associations.length,0);
 assert.equal(JSON.stringify([...entries.values()].map(e=>e.layers.vector)),originalRecords);assert.equal(JSON.stringify(parts),originalParts);assert.equal(sha(fs.readFileSync(manifestPath)),sha(manifestRaw));for(const d of assets)assert.equal(sha(fs.readFileSync(path.join(world,d.path))),d.sha256);
 if(process.env.MASSILIA_ARCHITECTURE_REPORT)fs.writeFileSync(process.env.MASSILIA_ARCHITECTURE_REPORT,JSON.stringify({schema:'soma-massilia/architecture74-real-qa/1',passed:true,worldManifestSHA256:sha(manifestRaw),sourceAssetsUnchanged:true,nativeTerrain:true,sourceGeometryUnchanged:true,associations:snapshot.associations,roofs,cells,linkedPartControls,courtyardControls,cellBoundaryControls,verifiedAssets:assets,cpuOptions:{parentOptionsMilliseconds,extendedOptionsMilliseconds,samples:1,scope:'CPU geometry-options construction for the same 12 normalized native cells; single cold sample, not frame time or GPU performance.'},scope:'Two reviewed geometric associations; interpreted shared foundation, no asserted OSM relation, no surveyed roof or physical-access certification.'},null,2)+'\n');
});
