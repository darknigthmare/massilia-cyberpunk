'use strict';
const fs=require('node:fs'),path=require('node:path'),zlib=require('node:zlib'),vm=require('node:vm');
const {game,owners,data}=require('./terrain-fixture.cjs'),D=data(),F=require(game+'/src/v75/terrain-footprint-core.js');
const m=JSON.parse(fs.readFileSync(game+'/data/v69/world/manifest.json')),proof=JSON.parse(zlib.gunzipSync(fs.readFileSync(game+'/data/v69/building-height-matches.json.gz'))),records=new Map();
for(const t of m.tiles){const r=JSON.parse(zlib.gunzipSync(fs.readFileSync(game+'/data/v69/world/'+t.vector.path)));r.v53Validated=true;records.set(r.cellId,r);}
D.context.document={getElementById:()=>({textContent:JSON.stringify(proof)})};D.context.__SOMA_V52__={records:()=>records};
vm.runInContext(fs.readFileSync(game+'/src/v69/height-references.js','utf8'),D.context);
vm.runInContext(owners.geometry,D.context);
const geom=D.context.__SOMA_V53_CORE__,fresh=()=>({min:Infinity,max:-Infinity,n:0,missing:false});
let fragments=0,sourceRefs=0,missing=0,inferredAdjusted=0,fullAboveVertices=0,maxDifference=0,buildingTime=performance.now();
const uniqueObjects=new Set(),uniqueRefs=new Set();
const largest=[],fixedSourceConflicts=[],fixedSourceUnderEaveConflicts=[],courtyards=[];
for(const [cellId,r]of records)for(const f of r.featureCollection.features){
 const p=f.properties||{};if(p['soma:layer']!=='buildings')continue;
 const id=p.canonical_id||f.id,full=fresh(),vertex=fresh(),old=fresh();fragments++;uniqueObjects.add(id);
 for(const mesh of p['soma:mesh53']||[]){F.accumulate(D.native,mesh.ringsL93||[],full,geom.inPolygon);
  if(mesh.ringsL93.length>1&&courtyards.length<8)courtyards.push({id,cellId,rings:mesh.ringsL93.length});
  for(const ring of mesh.ringsL93||[])for(const q of ring){for(const [g,a]of [[D.native,vertex],[D.legacy,old]]){const h=g.sample(...q);if(h===null){a.missing=true;continue;}a.max=Math.max(a.max,h);a.min=Math.min(a.min,h);a.n++;}}
 }
 if(full.missing||!full.n){missing++;continue;}
 const ref=D.context.__SOMA_HEIGHTS69__.reference(p,id,{v50Record:r});
 const delta=full.max-vertex.max;if(delta>1e-5)fullAboveVertices++;
 if(!ref){if(Math.abs(full.max-old.max)>1e-5)inferredAdjusted++;maxDifference=Math.max(maxDifference,Math.abs(full.max-old.max));
  largest.push({id,cellId,legacyBase:old.max,nativeContourVertexMax:vertex.max,nativeFullFootprintMax:full.max,nativeFullFootprintMin:full.min,insideSummitAboveContour:delta,baseShift:full.max-old.max});
 }else{sourceRefs++;uniqueRefs.add(id);const excess=full.max-ref.groundAltitude;
  if(excess>.03)fixedSourceConflicts.push({id,cellId,groundAltitude:ref.groundAltitude,eaveHeight:ref.height,nativeFootprintMin:full.min,nativeFootprintMax:full.max,terrainAboveFixedBase:excess});
  if(excess>ref.height)fixedSourceUnderEaveConflicts.push({id,cellId,groundAltitude:ref.groundAltitude,eaveHeight:ref.height,nativeFootprintMax:full.max,terrainAboveEave:excess-ref.height});
 }
}
largest.sort((a,b)=>b.insideSummitAboveContour-a.insideSummitAboveContour);fixedSourceConflicts.sort((a,b)=>b.terrainAboveFixedBase-a.terrainAboveFixedBase);
const g=D.native,S=D.S;let ray=null;
for(let y=2;y<g.rows-2&&!ray;y++)for(let x=2;x<g.cols-2&&!ray;x++){
 const e=g.x0+x*5,n=g.n0-y*5,a=g.sample(e,n),b=D.legacy.sample(e,n);if(a===null||b===null||a-b<1)continue;
 const o=[e,(a+b)/2,-n],d=[0,1,0],h=S.terrain(g,o,d,2);if(h?.kind==='terrain'&&!S.terrain(D.legacy,o,d,2))ray={easting:e,northing:n,nativeGroundNGF:a,legacyGroundNGF:b,originNGF:o[1],direction:d,rangeM:2,nativeHit:h,legacyHit:null};
}
const sampleCell=m.tiles.find(x=>x.cellId==='V52-MC-11'),b=sampleCell.boundsL93,e=(b[0]+b[2])/2,n=(b[1]+b[3])/2;
const report={schema:'soma-terrain75-numeric-source-audit/1',gridSHA256:D.pack.sha256,sourceOnly:true,
 scope:'All 168 delivered centre vector cells; geometry and source IGN-ground/eave matching owner unchanged. Numeric support audit, not complete rendered architectural fidelity or campaign access certification.',
 fragments,uniqueObjects:uniqueObjects.size,sourceRefs,uniqueSourceRefs:uniqueRefs.size,missing,inferredAdjusted,fullAboveVertices,maxInferredBaseDifferenceM:maxDifference,elapsedCPUWallMs:performance.now()-buildingTime,
 foundationPolicy:'5m pilot uses exact measured terrain extrema over complete source footprints excluding courtyard interiors; existing eligible IGN building ground references retain their fixed source altitude.',
 fixedSourceBaseThresholdM:.03,fixedSourceEaveThresholdM:0,
 fixedSourceBasesWithTerrainAboveBase:fixedSourceConflicts.length,fixedSourceEavesWithTerrainAboveEave:fixedSourceUnderEaveConflicts.length,
 uniqueFixedSourceEavesWithTerrainAboveEave:new Set(fixedSourceUnderEaveConflicts.map(x=>x.id)).size,
 fixedSourceEavesWithTerrainAboveEave3cm:fixedSourceUnderEaveConflicts.filter(x=>x.terrainAboveEave>.03).length,
 largestInteriorSummitCorrections:largest.slice(0,12),largestFixedSourceBaseConflicts:fixedSourceConflicts.slice(0,12),fixedSourceUnderEaveConflicts,courtyardControls:courtyards,
 terrainRidgeRayEvidence:ray,sampleCell:{cellId:sampleCell.cellId,localX:0,localZ:0,easting:e,northing:n,nativeGroundNGF:g.sample(e,n),legacyGroundNGF:D.legacy.sample(e,n)},
 limits:['NoData is never filled. The bounding rectangle has 169 positions but only 168 campaign cells; its unprovided corner remains masked.',
 'Fixed IGN source building bases may conflict with a different-source DTM. Their source datum is not moved or falsely declared reconciled.',
 'CPU duration is an offline support audit and is not an in-game GPU/frame-time measurement.']};
const output=path.resolve(process.argv[2]||'test-results/v75-terrain/numeric-source-audit.json');fs.mkdirSync(path.dirname(output),{recursive:true});
fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({output,fragments,uniqueObjects:uniqueObjects.size,sourceRefs,uniqueSourceRefs:uniqueRefs.size,
 fixedSourceBasesWithTerrainAboveBase:report.fixedSourceBasesWithTerrainAboveBase,fixedSourceEavesWithTerrainAboveEave:report.fixedSourceEavesWithTerrainAboveEave,
 uniqueFixedSourceEavesWithTerrainAboveEave:report.uniqueFixedSourceEavesWithTerrainAboveEave,fixedSourceEavesWithTerrainAboveEave3cm:report.fixedSourceEavesWithTerrainAboveEave3cm}));
