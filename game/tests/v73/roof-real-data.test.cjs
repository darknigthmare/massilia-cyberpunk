'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),zlib=require('node:zlib'),crypto=require('node:crypto');
const game=path.resolve(__dirname,'../..'),world=process.env.MASSILIA_ROOF_WORLD||path.join(game,'data/v69/metropole'),manifestPath=path.join(world,'manifest.json');
const CELLS=['V52-MC-41','V52-MC-42','V52-MC-43','V52-MC-52','V52-MC-W03-N01','V52-MC-W04-N01','V52-MC-W04-S00','V52-MC-W04-S01','V52-MC-W05-S01','V52-MC-W05-S02','V52-MC-W06-S02','V52-MC-W10-N71'];
const EXPECTED=['osm/relation/3564479','osm/way/264740443','osm/way/264740444','osm/way/264887605','osm/way/264887700','osm/way/265246760','osm/way/67536572','osm/way/67542474'];
const sha=b=>crypto.createHash('sha256').update(b).digest('hex'),close=(a,b,tol=1e-5)=>assert(Math.abs(a-b)<=tol,`${a} != ${b}`);
function extract(html,id){const match=html.match(new RegExp('<script[^>]*id="'+id+'"[^>]*>([\\s\\S]*?)<\\/script>'));assert(match,'Required parent script '+id);return match[1];}
function core(html,id){const c=vm.createContext({module:{exports:{}},TextEncoder,TextDecoder,atob:x=>Buffer.from(x,'base64').toString('binary')});vm.runInContext(extract(html,id),c);return c.module.exports;}
function architecture(extended){const c=vm.createContext({module:{exports:{}}});for(const f of ['v68/architecture-core.js','v69/roof-core.js',...(extended?['v73/roof-fidelity-core.js']:[])])vm.runInContext(fs.readFileSync(path.join(game,'src',f),'utf8'),c);return c.__SOMA_ARCH68_CORE__;}
const area=t=>Math.abs((t[1][0]-t[0][0])*(t[2][1]-t[0][1])-(t[2][0]-t[0][0])*(t[1][1]-t[0][1]))/2;
test('real AMP cohort: eight pitched roofs change on native terrain while all other source and rendered surfaces remain identical',
 {skip:!fs.existsSync(manifestPath)},()=>{
 const manifestRaw=fs.readFileSync(manifestPath),manifest=JSON.parse(manifestRaw),proofs=[];
 assert.equal(manifest.source.sha256,'258a6450ae90142b4c4c19c851e3983a5c82c0e216dbe5f4d6fcbda0b0646467');
 const html=fs.readFileSync(path.join(game,'metropole-viewer-v72.html'),'utf8'),F=core(html,'viewer-dimension-core'),G=core(html,'viewer-geographic-core'),T=core(html,'viewer-terrain-core');
 const A0=architecture(false),A1=architecture(true),D=require('../../src/v72/fidelity-core.js'),I=require('../../src/v72/road-inspector-core.js'),Arch=require('../../src/v71/architecture-inspector-core.js'),M=require('../../src/v70/material-extension-core.js');
 const c=vm.createContext({module:{exports:{}},Float32Array,__SOMA_FIDELITY72_CORE__:D,__SOMA_ROAD_INSPECTION72_CORE__:I,__SOMA_ARCHITECTURE71_CORE__:Arch,__SOMA_MATERIAL70_CORE__:M});
 vm.runInContext(extract(html,'viewer-metropole-viewer-core'),c);const V=c.module.exports;
 function checked(d){const raw=fs.readFileSync(path.join(world,d.path));assert.equal(raw.length,d.bytes);assert.equal(sha(raw),d.sha256);proofs.push(d);return JSON.parse(zlib.gunzipSync(raw));}
 const entries=CELLS.map(id=>{const tile=manifest.tiles.find(t=>t.cellId===id);assert(tile,'Required real source cell '+id);
  const vector=checked(tile.vector),surface=checked(tile.surfaces),terrain=checked(tile.terrain);return {tile,layers:{vector,surfaces:surface,terrain:{grid:T.load(terrain,tile.boundsL93),pack:terrain}}};});
 const records=entries.map(e=>e.layers.vector),refs=A1.referenceIndex(records),before=JSON.stringify(records),seen=new Set(),rows=[],changed=new Set(),cellRows=[],courtyardControls=[],fragmentControls=new Map();
 const vertices=(g,r)=>Buffer.from(g.vertices.buffer,g.vertices.byteOffset+r.start*36,(r.end-r.start)*36);
 function unchangedBuffer(g){const chunks=[],ranges=g.architecture71.ranges.filter(r=>changed.has(r.facts.id));let previous=0;
  for(const r of ranges){chunks.push(Buffer.from(g.vertices.buffer,g.vertices.byteOffset+previous*36,(r.start-previous)*36));previous=r.end;}
  chunks.push(Buffer.from(g.vertices.buffer,g.vertices.byteOffset+previous*36,g.vertices.byteLength-previous*36));return Buffer.concat(chunks);}
 for(const record of records)for(const f of record.featureCollection.features){
  const p=f.properties||{};if(!['gabled','hipped'].includes(p['roof:shape'])||!p.height||!p['roof:height']||seen.has(f.id))continue;seen.add(f.id);
  const d=A1.roofDimensions(p,F.dimension(p,8)),ref=refs.get(A1.referenceKey(p,f.id,record)),old=A0.roofPlan(p,d,ref),now=A1.roofPlan(p,d,ref);
  const row={id:f.id,cellId:record.cellId,sourcePbfSHA256:record.sourceReceipt.sha256,cellContentSHA256:record.contentSHA256,geometrySHA256:p['soma:geometry_sha256'],
   heightMeters:d.height,minHeightMeters:d.minHeight,roofHeightTag:p['roof:height'],before:old.reason,after:now.reason,modelledBefore:old.modelled,modelledAfter:now.modelled};
  if(now.frameOnly){assert.equal(old.modelled,false);changed.add(f.id);row.frame=now.frame;row.roofSurveyed=now.roofSurveyed;row.parameterSources=now.parameterSources;}
  rows.push(row);
 }
 assert.equal(rows.length,38);assert.equal(rows.filter(r=>r.modelledBefore).length,10);assert.equal(rows.filter(r=>r.modelledAfter).length,18);assert.deepEqual([...changed].sort(),EXPECTED);
 for(const e of entries){
  const record=e.layers.vector,P=G.metricProjector(e.tile.boundsL93),geometries=[];
  for(const f of record.featureCollection.features.filter(f=>changed.has(f.id))){
   const p=f.properties,d=A1.roofDimensions(p,F.dimension(p,8)),plan=A1.roofPlan(p,d,refs.get(A1.referenceKey(p,f.id,record)));
   let nativeArea=0,roofArea=0,wallPanels=0,min=Infinity,max=-Infinity;
   for(const mesh of p['soma:mesh53']){
    nativeArea+=mesh.trianglesL93.reduce((s,t)=>s+area(t),0);
    const out=A1.roofTriangles(mesh.trianglesL93.map(t=>t.map(P.toLocal)),plan,P);
    roofArea+=out.reduce((s,t)=>s+area(t.map(q=>[q[0],q[2]])),0);
    for(const t of out){const centroid=[t.reduce((s,q)=>s+q[0],0)/3,t.reduce((s,q)=>s+q[2],0)/3];
     close(t.reduce((s,q)=>s+q[1],0)/3,plan.heightAt(...P.toMetric(centroid)));
     assert(G.inPolygon(P.toMetric(centroid),mesh.ringsL93),'Roof triangle remains in source footprint, excluding holes');
     for(const q of t){min=Math.min(min,q[1]);max=Math.max(max,q[1]);assert(q[1]>=plan.eave-1e-6&&q[1]<=d.height+1e-6);}
    }
    for(const [aa,bb]of mesh.wallsL93){const a=P.toLocal(aa),b=P.toLocal(bb),walls=A1.wallSegments(a,b,plan,P);wallPanels+=walls.length;
     close(walls.reduce((s,w)=>s+Math.hypot(w.b[0]-w.a[0],w.b[1]-w.a[1]),0),Math.hypot(b[0]-a[0],b[1]-a[1]));
     for(const w of walls){close(w.topA,plan.heightAt(...P.toMetric(w.a)));close(w.topB,plan.heightAt(...P.toMetric(w.b)));assert(w.topA>=d.minHeight-1e-6&&w.topB>=d.minHeight-1e-6);}
    }
   }
   close(nativeArea,roofArea);assert(max-min>.1);geometries.push({id:f.id,nativeAreaM2:nativeArea,roofAreaM2:roofArea,minRoofHeightMeters:min,maxRoofHeightMeters:max,wallPanels});
  }
  const options={references:refs,details:false},deps={geo:G,terrain:T,fidelity:F};
  const old=V.buildTile(e,{...deps,architecture:A0},options),now=V.buildTile(e,{...deps,architecture:A1},options);
  assert(unchangedBuffer(old).equals(unchangedBuffer(now)),'All vertices outside changed source-building ranges remain byte-identical');
  for(const r of now.architecture71.ranges.filter(r=>!changed.has(r.facts.id))){const parent=old.architecture71.ranges.find(x=>x.facts.id===r.facts.id);assert(parent);assert(vertices(old,parent).equals(vertices(now,r)));
   const f=record.featureCollection.features.find(f=>f.id===r.facts.id),meshes=f.properties['soma:mesh53']||[];
   if(meshes.some(m=>m.ringsL93.length>1))courtyardControls.push({id:r.facts.id,cellId:e.tile.cellId,rings:meshes.reduce((s,m)=>s+m.ringsL93.length,0),renderedVerticesIdentical:true});
   if(!fragmentControls.has(r.facts.id))fragmentControls.set(r.facts.id,[]);fragmentControls.get(r.facts.id).push(e.tile.cellId);
  }
  cellRows.push({cellId:e.tile.cellId,beforeGeometryBytes:old.geometryBytes,afterGeometryBytes:now.geometryBytes,nativeTerrainTriangles:now.counts.terrainTriangles,
   otherRenderedVerticesIdentical:true,geometries});
 }
 const cellBoundaryControls=[...fragmentControls].filter(([,cells])=>cells.length>1).map(([id,cells])=>({id,cells,renderedVerticesIdentical:true}));
 assert(courtyardControls.length>0,'Real courtyard source controls are rendered unchanged');assert(cellBoundaryControls.length>0,'Real source fragments cross cell boundaries unchanged');
 assert.equal(JSON.stringify(records),before);assert.equal(sha(fs.readFileSync(manifestPath)),sha(manifestRaw));for(const d of proofs)assert.equal(sha(fs.readFileSync(path.join(world,d.path))),d.sha256);
 if(process.env.MASSILIA_ROOF_REPORT)fs.writeFileSync(process.env.MASSILIA_ROOF_REPORT,JSON.stringify({schema:'soma-massilia/roof-fidelity73-real-qa/1',passed:true,worldManifestSHA256:sha(manifestRaw),sourceAssetsUnchanged:true,
  nativeTerrain:true,cohortBefore:10,cohortAfter:18,newModelledRoofs:8,cohort:rows,cells:cellRows,courtyardControls,cellBoundaryControls,verifiedAssets:proofs,
  scope:'Inferred pitched profiles from explicit OSM shape, total height and roof rise. Source footprints, holes, source walls and native terrain retained. No surveyed-roof or physical-access certification.'},null,2)+'\n');
});
