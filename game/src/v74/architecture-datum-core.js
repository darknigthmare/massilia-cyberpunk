/* Two reviewed source roofs share their documented body's interpreted ground
 * anchor. The 1 cm bound concerns OSM coordinate quantisation, not survey
 * accuracy. Native footprints, heights, DEM samples and holes are never edited.
 */
(function(root){
  'use strict';
  const VERSION='0.74.0',TOLERANCE_M=.01,EPS=1e-9,MAX_POINTS=128;
  const SOURCE='258a6450ae90142b4c4c19c851e3983a5c82c0e216dbe5f4d6fcbda0b0646467';
  const CELL='V52-MC-41',CONTENT='514718733a83674d4d826b9c5ea35991aab6216a49e2f3d6e4b780df5c804c07';
  const PARENT='osm/way/264740428',BODY='osm/way/264740436';
  const GEOMETRY=Object.freeze({
    [PARENT]:'53c11e979cc437a38f706a260d3d982514f1b71337c7d6f9e8fed8e8b84a7919',
    [BODY]:'4071550312116c466c168ec79bea627b36819d8aa22d45af1e4f02c6817522f1',
    'osm/way/264740443':'9c686f3bf278b1a433c62fdaaa5ee65c4e6bbadf3183fb3994a900d5ff7fb7e3',
    'osm/way/264740444':'e81288191ca6bb1ad08a8815cda77a1c978744debeab465ee820a24e62542cfe'});
  const ROOFS=Object.freeze({'osm/way/264740443':'hipped','osm/way/264740444':'gabled'});
  const active=v=>v!=null&&!['','no','false','0'].includes(String(v).trim().toLowerCase());
  const point=p=>Array.isArray(p)&&p.length===2&&p.every(Number.isFinite);
  const cross=(a,b)=>a[0]*b[1]-a[1]*b[0],dot=(a,b)=>a[0]*b[0]+a[1]*b[1];
  const sub=(a,b)=>[a[0]-b[0],a[1]-b[1]];
  function inside(p,ring){let yes=false;for(let i=0,j=ring.length-1;i<ring.length;j=i++){
    const a=ring[i],b=ring[j];if((a[1]>p[1])!==(b[1]>p[1])&&p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0])yes=!yes;
  }return yes;}
  function linearInterval(a,b,lo,hi){
    if(Math.abs(b)<1e-15)return a>=lo-EPS&&a<=hi+EPS?[0,1]:null;
    const x=(lo-a)/b,y=(hi-a)/b,l=Math.max(0,Math.min(x,y)),r=Math.min(1,Math.max(x,y));return l<=r+EPS?[l,r]:null;
  }
  function intersect(a,b){if(!a||!b)return null;const l=Math.max(a[0],b[0]),r=Math.min(a[1],b[1]);return l<=r+EPS?[l,r]:null;}
  function circleInterval(a,d,c,radius){
    const q=sub(a,c),aa=dot(d,d),bb=2*dot(q,d),cc=dot(q,q)-radius*radius;
    if(aa<1e-20)return cc<=0?[0,1]:null;
    const disc=bb*bb-4*aa*cc;if(disc<0)return null;
    const root=Math.sqrt(Math.max(0,disc));return intersect([(-bb-root)/(2*aa),(-bb+root)/(2*aa)],[0,1]);
  }
  // Exact parameter intervals inside each boundary segment's capsule. Together
  // with polygon-interior intervals this proves EVERY point of a source edge,
  // including excursions between its vertices; no sampling or vertex-only test.
  function edgeContained(a,b,ring,tolerance){
    const d=sub(b,a),cuts=[0,1],coverage=[];
    for(let i=0;i<ring.length;i++){
      const c=ring[i],e=ring[(i+1)%ring.length],v=sub(e,c),q=sub(a,c),len=Math.hypot(...v);if(len<1e-12)return false;
      const determinant=cross(d,v);
      if(Math.abs(determinant)>1e-12){const ca=sub(c,a),t=cross(ca,v)/determinant,u=cross(ca,d)/determinant;if(t>0&&t<1&&u>=0&&u<=1)cuts.push(t);}
      const along=linearInterval(dot(q,v)/len,dot(d,v)/len,0,len);
      const strip=linearInterval(cross(q,v)/len,cross(d,v)/len,-tolerance,tolerance);
      for(const interval of [intersect(along,strip),circleInterval(a,d,c,tolerance),circleInterval(a,d,e,tolerance)])if(interval)coverage.push(interval);
    }
    cuts.sort((x,y)=>x-y);
    for(let i=1;i<cuts.length;i++){
      const t=(cuts[i-1]+cuts[i])/2;if(inside([a[0]+d[0]*t,a[1]+d[1]*t],ring))coverage.push([cuts[i-1],cuts[i]]);
    }
    coverage.sort((x,y)=>x[0]-y[0]);let end=0;
    for(const [a,b]of coverage){if(a>end+EPS)return false;end=Math.max(end,b);if(end>=1-EPS)return true;}return false;
  }
  function ringOf(reference){
    return reference?.complete===true&&reference.outerCount===1&&reference.hasHoles===false&&reference.rings?.length===1&&
      reference.rings[0].length>=3&&reference.rings[0].length<=MAX_POINTS&&reference.rings[0].every(point)?reference.rings[0]:null;
  }
  function contained(reference,parent,tolerance=TOLERANCE_M){
    const ring=ringOf(reference),outline=ringOf(parent);return !!ring&&!!outline&&Number.isFinite(tolerance)&&tolerance>=0&&tolerance<=TOLERANCE_M&&
      ring.every((a,i)=>edgeContained(a,ring[(i+1)%ring.length],outline,tolerance));
  }
  function reconcile(entries,architecture,parts,options){
    last=[];
    if(!Array.isArray(entries)||entries.length>32||typeof architecture?.referenceIndex!=='function')return options;
    const records=entries.map(e=>e.layers?.vector).filter(Boolean),rows=new Map();
    for(const r of records){if(!r.v53Validated||r.v53Synthetic||r.v50Synthetic||r.testOnly||r.sourceReceipt?.sha256!==SOURCE)continue;
      for(const f of r.featureCollection?.features||[]){const p=f.properties||{},id=p.canonical_id||f.id;
        if(p['soma:layer']==='buildings'&&!rows.has(id))rows.set(id,{p,id,record:r});}}
    const roofRows=Object.keys(ROOFS).map(id=>rows.get(id)).filter(Boolean);if(!roofRows.length)return options;
    const bound=row=>!!row&&row.record.cellId===CELL&&row.record.contentSHA256===CONTENT&&row.p.canonical_id===row.id&&row.p['soma:geometry_sha256']===GEOMETRY[row.id];
    const parent=rows.get(PARENT),body=rows.get(BODY),parentProof=parts?.parents?.[PARENT],link=parts?.partParents?.[BODY];
    if(!bound(parent)||!bound(body)||parts?.sourceSHA256!==SOURCE||parentProof?.sourceSHA256!==SOURCE||
      parentProof.parentGeometrySHA256!==GEOMETRY[PARENT]||parentProof.cells?.[CELL]!==CONTENT||parentProof.sourceFootprintComplete!==true||
      !parentProof.replaceParent||link?.parentId!==PARENT||link.sourceSHA256!==SOURCE||link.geometrySHA256!==GEOMETRY[BODY]||
      link.parentGeometrySHA256!==GEOMETRY[PARENT]||link.cells?.[CELL]!==CONTENT||
      Number(body.p.height)!==20||!active(body.p['building:part'])||Number(body.p.min_height||0)!==0)return options;
    const parentBase=options.canonicalDatumsMap?.get(PARENT),bodyBase=options.canonicalDatumsMap?.get(BODY);
    if(!Number.isFinite(parentBase)||parentBase!==bodyBase||options.missingCanonicalDatums?.has(PARENT)||options.missingCanonicalDatums?.has(BODY))return options;
    const validBounds=b=>Array.isArray(b)&&b.length===4&&b.every(Number.isFinite)&&b[0]<b[2]&&b[1]<b[3];
    const mayContain=(bounds,roofBounds)=>!validBounds(bounds)||!validBounds(roofBounds)||
      bounds[0]<=roofBounds[0]+TOLERANCE_M&&bounds[1]<=roofBounds[1]+TOLERANCE_M&&bounds[2]>=roofBounds[2]-TOLERANCE_M&&bounds[3]>=roofBounds[3]-TOLERANCE_M;
    const outlines=[...rows.values()].filter(row=>active(row.p.building)&&!active(row.p['building:part'])&&row.p.building!=='roof'&&
      roofRows.some(roof=>mayContain(row.p['soma:sourceBoundsL93'],roof.p['soma:sourceBoundsL93'])));
    // The viewer already indexed the pitched roofs. Reuse those immutable
    // references and close only the support/potential outline wall graphs.
    // Missing native bounds retain a candidate, including incomplete outlines.
    const inherited=typeof options.references?.get==='function'?options.references:null;
    const needed=new Set([PARENT,BODY,...roofRows.map(row=>row.id),...outlines.map(row=>row.id)]);
    const references=architecture.referenceIndex(records.map(record=>({...record,featureCollection:{...record.featureCollection,
      features:(record.featureCollection?.features||[]).filter(f=>needed.has(f.properties?.canonical_id||f.id)&&
        !inherited?.get(architecture.referenceKey(f.properties,f.id,record)))}})));
    const reference=row=>{const key=architecture.referenceKey(row.p,row.id,row.record);return inherited?.get(key)||references.get(key);};
    if(!ringOf(reference(parent))||!ringOf(reference(body)))return options;
    const evidence=new Map();
    for(const roof of roofRows){
      const p=roof.p,oldBase=options.canonicalDatumsMap?.get(roof.id),ref=reference(roof);
      if(!bound(roof)||!active(p['building:part'])||p['roof:shape']!==ROOFS[roof.id]||Number(p.height)!==23||Number(p.min_height)!==20||Number(p['roof:height'])!==3||
        !Number.isFinite(oldBase)||parentBase<oldBase||options.missingCanonicalDatums?.has(roof.id)||!ringOf(ref))continue;
      const possible=outlines.filter(row=>mayContain(row.p['soma:sourceBoundsL93']||reference(row)?.bounds,ref.bounds));
      // An incomplete competing outline is uncertainty, not proof of uniqueness.
      if(possible.some(row=>!ringOf(reference(row))))continue;
      const candidates=possible.filter(row=>contained(ref,reference(row)));
      if(candidates.length!==1||candidates[0].id!==PARENT)continue;
      // The support must lie within the same outline and its sourced top must
      // equal the sourced roof minimum. No external building is lowered.
      if(!contained(reference(body),reference(parent),0))continue;
      options.canonicalDatumsMap.set(roof.id,parentBase);
      const item={id:roof.id,parentId:PARENT,supportId:BODY,association:'derived-source-boundary-containment',osmRelation:false,
        sourcePbfSHA256:SOURCE,geometrySHA256:GEOMETRY[roof.id],parentGeometrySHA256:GEOMETRY[PARENT],cellContentSHA256:CONTENT,
        boundaryToleranceMeters:TOLERANCE_M,toleranceMeaning:'OSM-coordinate-quantisation-bound-not-survey-accuracy',
        beforeBaseAltitudeNGFMeters:oldBase,baseAltitudeNGFMeters:parentBase,minHeightMeters:20,totalHeightMeters:23,roofRiseMeters:3,
        verticalSemantics:'OSM-total-and-minimum-heights-relative-to-interpreted-shared-foundation',surveyed:false};
      evidence.set(roof.id,item);last.push(item);
    }
    return {...options,architectureDatum74:evidence};
  }
  function facts(previous,evidence){return evidence?{...previous,baseQuality:'derived-shared-source-foundation',datum74:{...evidence}}:previous;}
  let last=[];
  function snapshot(){return {version:VERSION,scope:'reviewed-AMP-source-roofs-443-444',boundaryToleranceMeters:TOLERANCE_M,
    sourceResolutionIsNotSurveyAccuracy:true,associations:last.map(x=>({...x})),sourceGeometryUnchanged:true,certifiedArchitecture:false};}
  const API=Object.freeze({VERSION,TOLERANCE_M,GEOMETRY,contained,reconcile,facts,snapshot});root.__SOMA_ARCHITECTURE74__=API;
  if(typeof module!=='undefined'&&module.exports)module.exports=API;
})(typeof window!=='undefined'?window:globalThis);
