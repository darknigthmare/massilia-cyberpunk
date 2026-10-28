/* Architectural evidence and picking against the actual rendered triangles.
 * This layer adds no geometry, heights, texture claims or collision surfaces.
 */
(function(root){
  'use strict';
  const VERSION='0.71.0',MAX_VERTICES=600000,MAX_RANGES=5000;
  const text=(v,max=200)=>typeof v==='string'?v.slice(0,max):null;
  const finite=n=>typeof n==='number'&&Number.isFinite(n);
  const copy=v=>JSON.parse(JSON.stringify(v));
  const unit=v=>finite(v)?v:null;
  const TAGS=['name','building','building:part','height','min_height','building:levels','building:min_level','roof:shape','roof:height','roof:levels','roof:direction','roof:ridge:direction','roof:orientation','building:colour','building:color','building:material','building:facade:material','roof:colour','roof:color','roof:material','heritage','historic'];
  function facts(properties={},dimensions={},plan={},appearance={},record={},base=null){
    const p=properties||{},d=dimensions||{},r=plan||{},a=appearance||{},id=String(p.canonical_id||'');
    const match=id.match(/^osm\/(way|relation|node)\/([1-9]\d{0,19})$/),tags={};
    for(const key of TAGS)if(typeof p[key]==='string'||finite(p[key]))tags[key]=String(p[key]).slice(0,240);
    const heightSource=text(d.heightSource)||'unknown',eaves=d.heightKind==='eaves'||r.reason==='ign-eaves-flat-roof-approximation';
    return {id:id.slice(0,120),name:text(p.name)||null,osmURL:match?'https://www.openstreetmap.org/'+match[1]+'/'+match[2]:null,
      heightMeters:unit(d.height),minHeightMeters:unit(d.minHeight),baseAltitudeNGFMeters:unit(base),heightSource,
      heightQuality:heightSource==='osm-height'?'declared':heightSource==='ign-bdtopo-height'?'matched-reference':'estimated',
      heightKind:eaves?'eaves':'model-total',baseQuality:d.heightSource==='ign-bdtopo-height'&&finite(d.groundAltitude)&&finite(base)&&Math.abs(d.groundAltitude-base)<1e-5?'matched-source-base':'derived-from-valid-dem',
      roof:{requestedShape:text(p['roof:shape'])||null,displayedShape:text(r.shape)||'unknown',modelled:r.modelled===true,
        reason:text(r.reason)||null,quality:eaves?'unsurveyed-eaves-approximation':r.modelled&&r.shape!=='flat'?'inferred-parametric':'unsurveyed',surveyed:false},
      appearance:{wallSource:text(a.wallSource)||'unknown',roofSource:text(a.roofSource)||'unknown',lightingSource:'interpreted-cyberpunk',facadeSurveyed:false},
      footprint:{source:'prepared-osm-triangles',geometrySHA256:text(p['soma:geometry_sha256'],64),cellId:text(record.cellId,120),
        sourcePbfSHA256:text(record.sourceReceipt?.sha256,64),clippedToCell:true,accuracyCertified:false},
      sourceTags:tags,architecturalOneToOneCertified:false,physicalAccessVerified:false};
  }
  function attach(geometry,ranges=[]){
    const vertices=geometry?.vertices;
    if(!(vertices instanceof Float32Array)||vertices.length%27||vertices.length/9>MAX_VERTICES||!Array.isArray(ranges)||ranges.length>MAX_RANGES)
      throw new TypeError('Bounded rendered triangle geometry required.');
    const selected=[];let previous=0;
    for(const r of ranges){
      if(!Number.isSafeInteger(r.start)||!Number.isSafeInteger(r.end)||r.start%3||r.end%3||r.start<previous||r.end<=r.start||r.end>vertices.length/9||!r.facts||typeof r.facts.id!=='string')
        throw new TypeError('Ordered source-building triangle ranges required.');
      selected.push({start:r.start,end:r.end,facts:copy(r.facts)});previous=r.end;
    }
    const box=[Infinity,Infinity,Infinity,-Infinity,-Infinity,-Infinity];
    for(let i=0;i<vertices.length;i+=9)for(let axis=0;axis<3;axis++){
      const v=vertices[i+axis];if(!finite(v))throw new TypeError('Non-finite rendered vertex.');box[axis]=Math.min(box[axis],v);box[axis+3]=Math.max(box[axis+3],v);
    }
    return {...geometry,architecture71:{ranges:selected,bounds:vertices.length?box:null}};
  }
  function rayBox(origin,direction,box,limit){
    let near=.5,far=limit;
    for(let a=0;a<3;a++){
      if(Math.abs(direction[a])<1e-12){if(origin[a]<box[a]-1e-5||origin[a]>box[a+3]+1e-5)return null;continue;}
      let left=(box[a]-origin[a])/direction[a],right=(box[a+3]-origin[a])/direction[a];if(left>right)[left,right]=[right,left];
      near=Math.max(near,left);far=Math.min(far,right);if(far<near)return null;
    }
    return near;
  }
  function rayTriangle(o,d,v,i,limit){
    const ax=v[i],ay=v[i+1],az=v[i+2],ux=v[i+9]-ax,uy=v[i+10]-ay,uz=v[i+11]-az,
      vx=v[i+18]-ax,vy=v[i+19]-ay,vz=v[i+20]-az;
    const px=d[1]*vz-d[2]*vy,py=d[2]*vx-d[0]*vz,pz=d[0]*vy-d[1]*vx,det=ux*px+uy*py+uz*pz;
    // The viewer culls back faces. The pick must obey the same winding.
    if(det<=1e-10)return null;
    const tx=o[0]-ax,ty=o[1]-ay,tz=o[2]-az,u=(tx*px+ty*py+tz*pz)/det;if(u< -1e-7||u>1+1e-7)return null;
    const qx=ty*uz-tz*uy,qy=tz*ux-tx*uz,qz=tx*uy-ty*ux,w=(d[0]*qx+d[1]*qy+d[2]*qz)/det;
    if(w< -1e-7||u+w>1+1e-7)return null;
    const distance=(vx*qx+vy*qy+vz*qz)/det;return distance>=.5&&distance<=limit?distance:null;
  }
  function rangeAt(ranges,vertex){
    let lo=0,hi=ranges.length-1;
    while(lo<=hi){const mid=(lo+hi)>>1,r=ranges[mid];if(vertex<r.start)hi=mid-1;else if(vertex>=r.end)lo=mid+1;else return r;}
    return null;
  }
  function pickScene({camera,meshes,visibleCellIds,maxDistance=1500,maxTriangles=600000}={}){
    if(!camera||!['e','n','h','yaw','pitch'].every(k=>finite(camera[k]))||Math.abs(camera.pitch)>Math.PI/2||
      !Array.isArray(meshes)||meshes.length>32||!(visibleCellIds instanceof Set)||!finite(maxDistance)||maxDistance<.5||maxDistance>3000||
      !Number.isSafeInteger(maxTriangles)||maxTriangles<1||maxTriangles>2000000)throw new TypeError('Bounded camera and rendered scene required.');
    const direction=[Math.sin(camera.yaw)*Math.cos(camera.pitch),Math.sin(camera.pitch),-Math.cos(camera.yaw)*Math.cos(camera.pitch)],candidates=[];
    for(const item of meshes){
      if(!visibleCellIds.has(item.id))continue;
      const g=item.geometry;if(!g?.architecture71)throw new TypeError('Rendered geometry lacks inspection metadata.');
      if(!g.architecture71.bounds)continue;
      const origin=[camera.e-g.centerL93[0],camera.h,g.centerL93[1]-camera.n],near=rayBox(origin,direction,g.architecture71.bounds,maxDistance);
      if(near!==null)candidates.push({id:item.id,g,origin,near});
    }
    candidates.sort((a,b)=>a.near-b.near||String(a.id).localeCompare(String(b.id)));
    let tested=0,nearest=null,limit=maxDistance;
    for(const item of candidates){
      if(item.near>limit)break;
      const v=item.g.vertices;
      for(let i=0;i<v.length;i+=27){
        if(tested>=maxTriangles)return {status:'budget',selection:null,testedTriangles:tested,maxTriangles,maxDistanceMeters:maxDistance};
        tested++;const distance=rayTriangle(item.origin,direction,v,i,limit);
        if(distance===null||nearest&&distance>=limit-1e-7)continue;
        limit=distance;nearest={...item,vertex:i/9,distance};
      }
    }
    if(!nearest)return {status:'empty',selection:null,testedTriangles:tested,maxTriangles,maxDistanceMeters:maxDistance};
    const range=rangeAt(nearest.g.architecture71.ranges,nearest.vertex);
    if(!range)return {status:'occluded',selection:null,testedTriangles:tested,maxTriangles,maxDistanceMeters:maxDistance};
    return {status:'building',selection:{...copy(range.facts),distanceMeters:nearest.distance,selectedCellId:nearest.id,
      hitL93:{e:camera.e+direction[0]*nearest.distance,n:camera.n-direction[2]*nearest.distance,h:camera.h+direction[1]*nearest.distance}},
      testedTriangles:tested,maxTriangles,maxDistanceMeters:maxDistance};
  }
  const API=Object.freeze({VERSION,facts,attach,pickScene});root.__SOMA_ARCHITECTURE71_CORE__=API;
  if(typeof module!=='undefined'&&module.exports)module.exports=API;
})(typeof window!=='undefined'?window:globalThis);
