'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const H=require('./architecture-fixture.cjs'),fixture=require('./architecture-source.json');
const manifestPath=path.join(process.env.MASSILIA_ROOF_WORLD||path.join(H.game,'data/v69/metropole'),'manifest.json');
const close=(a,b,t=1e-5)=>assert(Math.abs(a-b)<=t,`${a} != ${b}`),area=t=>Math.abs((t[1][0]-t[0][0])*(t[2][1]-t[0][1])-(t[1][1]-t[0][1])*(t[2][0]-t[0][0]))/2;
test('six native source roofs change only their own rendered ranges, retaining footprints, NGF bases, walls and other scene geometry',
 {skip:!fs.existsSync(manifestPath)},()=>{
 const cells=[...new Set(fixture.rows.flatMap(r=>r.cells))],source=H.installed(cells),old=H.environment(false),now=H.environment(true),expected=fixture.rows.map(r=>r.id).sort();
 assert.equal(source.manifestSHA256,fixture.worldManifestSHA256);assert.equal(source.manifest.source.sha256,fixture.sourcePbfSHA256);
 const entries=new Map(source.entries.map(e=>[e.tile.cellId,e])),oldOptions=old.U.geometryOptions(entries,new Set(cells),old.A,source.parts),newOptions=now.U.geometryOptions(entries,new Set(cells),now.A,source.parts);
 assert.deepEqual([...oldOptions.canonicalDatumsMap],[...newOptions.canonicalDatumsMap]);assert.deepEqual([...oldOptions.missingCanonicalDatums],[...newOptions.missingCanonicalDatums]);
 const records=source.entries.map(e=>e.layers.vector),originalRecords=JSON.stringify(records),changed=new Set(),rows=[],cellRows=[],controlOccurrences=new Map(),courtyardControls=[];
 for(const entry of source.entries)for(const f of entry.layers.vector.featureCollection.features){
  const p=f.properties||{},ref=newOptions.references.get(now.A.referenceKey(p,f.id,entry.layers.vector));if(!ref)continue;
  const dim=now.A.roofDimensions(p,now.F.dimension(p,8)),plan=now.A.roofPlan(p,dim,ref);if(plan.derivedFrame78)changed.add(f.id);
 }
 assert.deepEqual([...changed].sort(),expected);
 function bytes(g,r){return Buffer.from(g.vertices.buffer,g.vertices.byteOffset+r.start*36,(r.end-r.start)*36);}
 function unchanged(g){const out=[];let previous=0;for(const r of g.architecture71.ranges.filter(r=>changed.has(r.facts.id))){out.push(Buffer.from(g.vertices.buffer,g.vertices.byteOffset+previous*36,(r.start-previous)*36));previous=r.end;}out.push(Buffer.from(g.vertices.buffer,g.vertices.byteOffset+previous*36,g.vertices.byteLength-previous*36));return Buffer.concat(out);}
 for(const entry of source.entries){
  const record=entry.layers.vector,projector=now.G.metricProjector(entry.tile.boundsL93),before=old.V.buildTile(entry,{geo:old.G,terrain:old.T,fidelity:old.F,architecture:old.A},oldOptions),after=now.V.buildTile(entry,{geo:now.G,terrain:now.T,fidelity:now.F,architecture:now.A},newOptions);
  assert(unchanged(before).equals(unchanged(after)),'All non-cohort rendered vertices remain byte-identical');assert.equal(after.counts.terrainTriangles,before.counts.terrainTriangles);assert.equal(after.counts.missingTerrainTriangles,before.counts.missingTerrainTriangles);assert.equal(after.counts.roadTriangles,before.counts.roadTriangles);
  assert(after.vertices.length/9<=600000);for(let i=0;i<after.vertices.length;i+=9){for(let j=0;j<9;j++)assert(Number.isFinite(after.vertices[i+j]));close(Math.hypot(...after.vertices.slice(i+3,i+6)),1,1e-6);}
  for(const r of after.architecture71.ranges){
   const previous=before.architecture71.ranges.find(p=>p.facts.id===r.facts.id);assert(previous);
   if(!changed.has(r.facts.id)){assert(bytes(before,previous).equals(bytes(after,r)));assert.equal(JSON.stringify(previous.facts),JSON.stringify(r.facts));if(!controlOccurrences.has(r.facts.id))controlOccurrences.set(r.facts.id,[]);controlOccurrences.get(r.facts.id).push(entry.tile.cellId);const f=record.featureCollection.features.find(f=>f.id===r.facts.id);if(f?.properties['soma:mesh53']?.some(m=>m.ringsL93.length>1))courtyardControls.push({id:r.facts.id,cell:entry.tile.cellId});continue;}
   assert(!bytes(before,previous).equals(bytes(after,r)));assert.equal(previous.facts.roof.displayedShape,'flat');assert.equal(r.facts.roof.displayedShape,'pyramidal');assert(r.facts.roofFrame78.apexInferred);assert.equal(previous.facts.baseAltitudeNGFMeters,r.facts.baseAltitudeNGFMeters);assert.equal(previous.facts.heightMeters,r.facts.heightMeters);assert.equal(previous.facts.minHeightMeters,r.facts.minHeightMeters);
   const f=record.featureCollection.features.find(f=>f.id===r.facts.id),p=f.properties,dim=now.A.roofDimensions(p,now.F.dimension(p,8)),plan=now.A.roofPlan(p,dim,newOptions.references.get(now.A.referenceKey(p,f.id,record))),sourceTriangles=[],roofTriangles=[],walls=[];
   let nativeArea=0,roofArea=0,minHeight=Infinity,maxHeight=-Infinity,sourceWallEaveOvershoot=0;
   for(const mesh of p['soma:mesh53']){
    sourceTriangles.push(...mesh.trianglesL93);nativeArea+=mesh.trianglesL93.reduce((s,t)=>s+area(t),0);
    for(const triangle of now.A.roofTriangles(mesh.trianglesL93.map(t=>t.map(projector.toLocal)),plan,projector)){
     const metric=triangle.map(q=>[...projector.toMetric([q[0],q[2]]),q[1]]);roofTriangles.push(metric);roofArea+=area(metric);const c=[metric.reduce((s,q)=>s+q[0],0)/3,metric.reduce((s,q)=>s+q[1],0)/3];assert(now.G.inPolygon(c,mesh.ringsL93));close(metric.reduce((s,q)=>s+q[2],0)/3,plan.heightAt(...c));
     for(const q of metric){minHeight=Math.min(minHeight,q[2]);maxHeight=Math.max(maxHeight,q[2]);assert(q[2]>=plan.eave-1e-7&&q[2]<=dim.height+1e-7);}
    }
    for(const [a,b]of mesh.wallsL93){const segments=now.A.wallSegments(projector.toLocal(a),projector.toLocal(b),plan,projector);close(segments.reduce((s,w)=>s+Math.hypot(w.b[0]-w.a[0],w.b[1]-w.a[1]),0),Math.hypot(b[0]-a[0],b[1]-a[1]));
     for(const w of segments){const aa=projector.toMetric(w.a),bb=projector.toMetric(w.b);close(w.topA,plan.heightAt(...aa));close(w.topB,plan.heightAt(...bb));assert(w.topA>=dim.minHeight&&w.topB>=dim.minHeight);walls.push({a:aa,b:bb,topA:w.topA,topB:w.topB});sourceWallEaveOvershoot=Math.max(sourceWallEaveOvershoot,w.topA-plan.eave,w.topB-plan.eave);}
    }
   }
   close(nativeArea,roofArea);close(maxHeight,dim.height);assert(maxHeight-minHeight>0.1);const ref=newOptions.references.get(now.A.referenceKey(p,f.id,record));rows.push({id:f.id,cellId:record.cellId,sourcePbfSHA256:record.sourceReceipt.sha256,cellContentSHA256:record.contentSHA256,geometrySHA256:p['soma:geometry_sha256'],baseAltitudeNGF:r.facts.baseAltitudeNGFMeters,totalHeightMeters:dim.height,minHeightMeters:dim.minHeight,openStructure:!!dim.openStructure,wallRecordsMeaning:'Source-wall profile segments; existing open canopies keep their native wall omission.',eaveHeightMeters:plan.eave,roofHeightTag:p['roof:height'],apexL93:Array.from(plan.apexL93),frame:JSON.parse(JSON.stringify(plan.derivedFrame78)),sourceRings:ref.rings,sourceTriangles,roofTriangles,walls,sourceAreaM2:nativeArea,roofProjectedAreaM2:roofArea,minRoofHeightMeters:minHeight,maxRoofHeightMeters:maxHeight,maximumSourceWallAboveFrameEaveMeters:sourceWallEaveOvershoot,allCoordinatesAndNormalsFinite:true,otherSourceValuesUnchanged:true,apexAndProfileInferred:true});
  }
  cellRows.push({cellId:entry.tile.cellId,beforeGeometryBytes:before.geometryBytes,afterGeometryBytes:after.geometryBytes,terrainTriangles:after.counts.terrainTriangles,roadTriangles:after.counts.roadTriangles,otherRenderedVerticesIdentical:true});
 }
 assert.deepEqual(rows.map(r=>r.id).sort(),expected);assert(courtyardControls.length>0);const boundaryControls=[...controlOccurrences].filter(([,ids])=>ids.length>1).map(([id,cells])=>({id,cells}));assert(boundaryControls.length>0);assert.equal(JSON.stringify(records),originalRecords);
 assert.equal(H.sha(fs.readFileSync(source.manifestPath)),source.manifestSHA256);for(const p of source.proofs)assert.equal(H.sha(fs.readFileSync(path.join(source.world,p.path))),p.sha256);
 const report={schema:'soma/architecture78-native-geometry/1',passed:true,worldManifestSHA256:source.manifestSHA256,sourcePbfSHA256:fixture.sourcePbfSHA256,sourceRecordsAndAssetsUnchanged:true,campaignGeographyChanged:false,geometryScope:'Independent metropolitan viewer only',newModelledRoofs:rows.length,cohort:rows,cells:cellRows,courtyardControls,boundaryControls,verifiedAssets:source.proofs,limits:['Convex frame, apex and pyramid profile are interpretations, not roof surveys.','The1cm bound concerns both complete source/frame boundaries, not vertical or survey accuracy.','Clipped source-wall eaves may differ slightly from the frame eave; this is recorded, not corrected by moving source geometry.']};
 if(process.env.MASSILIA_ARCHITECTURE78_REPORT)fs.writeFileSync(process.env.MASSILIA_ARCHITECTURE78_REPORT,JSON.stringify(report,null,2)+'\n');
});
