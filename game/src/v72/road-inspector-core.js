/* Read-only road inspection against rendered triangles. Prepared road unions
 * retain ambiguity: a nearby source axis is a candidate, never an access proof.
 */
(function(root){
  'use strict';
  const finite=n=>typeof n==='number'&&Number.isFinite(n),copy=x=>JSON.parse(JSON.stringify(x));
  const TAGS=['name','ref','highway','surface','smoothness','width','est_width','width:carriageway','lanes','lanes:forward','lanes:backward',
    'oneway','junction','sidewalk','sidewalk:left','sidewalk:right','sidewalk:both','bridge','tunnel','covered','indoor','layer','location',
    'access','foot','bicycle','vehicle','motor_vehicle','motorcar','wheelchair','horse','informal','service','maxspeed'];
  function facts(p,profile={}){
    const id=String(p.canonical_id||''),match=id.match(/^osm\/(way|relation)\/([1-9]\d{0,19})$/),tags={};
    for(const key of [...TAGS,...Object.keys(p).filter(k=>/^(?:access|foot|bicycle|vehicle|motor_vehicle|motorcar):/.test(k)).slice(0,30)])
      if(typeof p[key]==='string'||finite(p[key]))tags[key]=String(p[key]).slice(0,240);
    return {id:id.slice(0,120),name:typeof p.name==='string'?p.name.slice(0,200):null,osmURL:match?'https://www.openstreetmap.org/'+match[1]+'/'+match[2]:null,
      widthMeters:finite(profile.width)?profile.width:null,widthSource:String(profile.widthSource||'unknown'),
      widthQuality:profile.widthSource==='osm-width'?'declared':profile.widthSource==='osm-est-width'?'declared-estimate':'estimated',
      lanes:finite(profile.lanes)?profile.lanes:null,surface:String(profile.surface||p.surface||'unknown'),
      correction:profile.correction72?copy(profile.correction72):null,sourceTags:tags,
      physicalAccessibilityVerified:false,campaignRoutingActivated:false};
  }
  function sources(record,surface,F){
    const out=[];let points=0,truncated=false;
    for(const f of record?.featureCollection?.features||[]){
      const p=f.properties||{};if(p['soma:layer']!=='roads')continue;
      const id=String(p.canonical_id||f.id),mg=p['soma:metricGeometry'];
      if(!['LineString','MultiLineString','Polygon','MultiPolygon'].includes(mg?.type))continue;
      const raw=surface?.roadMetadata?.[id],bound=raw?.geometrySHA256===p['soma:geometry_sha256'];
      const profile=bound?raw:F.roadProfile(p);if(profile.structural||profile.v69Withheld)continue;
      const count=JSON.stringify(mg.coordinates).length;
      if(out.length>=2000||points+count>1000000){truncated=true;continue;}points+=count;
      out.push({facts:facts({...p,canonical_id:id},profile),geometry:copy(mg),profile:{width:profile.width,sidewalk:copy(profile.sidewalk||{})}});
    }
    return {items:out,truncated};
  }
  function attach(geometry,ranges=[],evidence={items:[],truncated:false},navigationPrepared=false,corrections=[]){
    const v=geometry?.vertices;if(!(v instanceof Float32Array)||v.length%27||v.length/9>600000||ranges.length>5000)throw new TypeError('Bounded road geometry required.');
    let end=0;for(const r of ranges){if(!Number.isSafeInteger(r.start)||!Number.isSafeInteger(r.end)||r.start%3||r.end%3||r.start<end||r.end<=r.start||r.end>v.length/9)throw new TypeError('Ordered road triangle ranges required.');end=r.end;}
    const bounds=[Infinity,Infinity,Infinity,-Infinity,-Infinity,-Infinity];
    for(let i=0;i<v.length;i+=9)for(let a=0;a<3;a++){if(!finite(v[i+a]))throw new TypeError('Finite road vertices required.');bounds[a]=Math.min(bounds[a],v[i+a]);bounds[a+3]=Math.max(bounds[a+3],v[i+a]);}
    return {...geometry,roads72:{ranges:copy(ranges),sources:evidence.items,sourceEvidenceTruncated:evidence.truncated===true,
      bounds:v.length?bounds:null,navigation:{sectorPrepared:navigationPrepared===true,graphRead:false,wayMembershipVerified:false,
        physicalAccessibilityVerified:false,campaignRoutingActivated:false},corrections:copy(corrections)}};
  }
  function inside(p,ring){let yes=false;for(let i=0,j=ring.length-1;i<ring.length;j=i++){
    const a=ring[i],b=ring[j];if((a[1]>p[1])!==(b[1]>p[1])&&p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0])yes=!yes;}return yes;}
  function candidate(source,point,kind){
    const mg=source.geometry,polygon=rings=>inside(point,rings[0])&&!rings.slice(1).some(r=>inside(point,r));
    if(mg.type==='Polygon')return polygon(mg.coordinates)?0:null;
    if(mg.type==='MultiPolygon')return mg.coordinates.some(polygon)?0:null;
    const lines=mg.type==='LineString'?[mg.coordinates]:mg.coordinates;let distance=Infinity;
    for(const line of lines)for(let i=1;i<line.length;i++){
      const a=line[i-1],b=line[i],dx=b[0]-a[0],dy=b[1]-a[1],l=dx*dx+dy*dy;if(!l)continue;
      const t=((point[0]-a[0])*dx+(point[1]-a[1])*dy)/l;
      // Flat source-band ends: no round extrapolated access beyond endpoints.
      if(t< -1e-6||t>1+1e-6)continue;
      distance=Math.min(distance,Math.hypot(point[0]-a[0]-t*dx,point[1]-a[1]-t*dy));
    }
    const side=source.profile.sidewalk||{},walk=kind==='walk'?Math.max(side.left?side.leftWidth||0:0,side.right?side.rightWidth||0:0):0;
    return distance<=source.profile.width/2+walk+.03?distance:null;
  }
  function boxHit(o,d,b,limit){let near=.5,far=limit;for(let a=0;a<3;a++){
    if(Math.abs(d[a])<1e-12){if(o[a]<b[a]-1e-5||o[a]>b[a+3]+1e-5)return null;continue;}
    let l=(b[a]-o[a])/d[a],r=(b[a+3]-o[a])/d[a];if(l>r)[l,r]=[r,l];near=Math.max(near,l);far=Math.min(far,r);if(far<near)return null;}return near;}
  function triangleHit(o,d,v,i,limit){
    const ax=v[i],ay=v[i+1],az=v[i+2],ux=v[i+9]-ax,uy=v[i+10]-ay,uz=v[i+11]-az,vx=v[i+18]-ax,vy=v[i+19]-ay,vz=v[i+20]-az,
      px=d[1]*vz-d[2]*vy,py=d[2]*vx-d[0]*vz,pz=d[0]*vy-d[1]*vx,det=ux*px+uy*py+uz*pz;
    if(det<=1e-10)return null;
    const tx=o[0]-ax,ty=o[1]-ay,tz=o[2]-az,u=(tx*px+ty*py+tz*pz)/det;if(u< -1e-7||u>1+1e-7)return null;
    const qx=ty*uz-tz*uy,qy=tz*ux-tx*uz,qz=tx*uy-ty*ux,w=(d[0]*qx+d[1]*qy+d[2]*qz)/det;if(w< -1e-7||u+w>1+1e-7)return null;
    const distance=(vx*qx+vy*qy+vz*qz)/det;return distance>=.5&&distance<=limit?distance:null;
  }
  function rangeAt(ranges,vertex){let lo=0,hi=ranges.length-1;while(lo<=hi){const mid=(lo+hi)>>1,r=ranges[mid];if(vertex<r.start)hi=mid-1;else if(vertex>=r.end)lo=mid+1;else return r;}return null;}
  function pickScene({camera,meshes,visibleCellIds,maxDistance=1500,maxTriangles=600000}={}){
    if(!camera||!['e','n','h','yaw','pitch'].every(k=>finite(camera[k]))||Math.abs(camera.pitch)>Math.PI/2||!Array.isArray(meshes)||meshes.length>32||
      !(visibleCellIds instanceof Set)||!finite(maxDistance)||maxDistance<.5||maxDistance>3000||!Number.isSafeInteger(maxTriangles)||maxTriangles<1||maxTriangles>2000000)throw new TypeError('Bounded rendered road scene required.');
    const direction=[Math.sin(camera.yaw)*Math.cos(camera.pitch),Math.sin(camera.pitch),-Math.cos(camera.yaw)*Math.cos(camera.pitch)],candidates=[];
    for(const item of meshes){if(!visibleCellIds.has(item.id))continue;const g=item.geometry;
      if(!g?.roads72)throw new TypeError('Road inspection metadata absent.');if(!g.roads72.bounds)continue;
      const origin=[camera.e-g.centerL93[0],camera.h,g.centerL93[1]-camera.n],near=boxHit(origin,direction,g.roads72.bounds,maxDistance);
      if(near!==null)candidates.push({id:item.id,g,origin,near});}
    candidates.sort((a,b)=>a.near-b.near||String(a.id).localeCompare(String(b.id)));
    let tested=0,nearest=null,limit=maxDistance;
    for(const item of candidates){if(item.near>limit)break;for(let i=0;i<item.g.vertices.length;i+=27){
      if(tested>=maxTriangles)return {status:'budget',selection:null,testedTriangles:tested};tested++;
      const distance=triangleHit(item.origin,direction,item.g.vertices,i,limit);if(distance===null||nearest&&distance>=limit-1e-7)continue;
      limit=distance;nearest={...item,vertex:i/9,distance};}}
    if(!nearest)return {status:'empty',selection:null,testedTriangles:tested};
    const r=rangeAt(nearest.g.roads72.ranges,nearest.vertex);if(!r)return {status:'occluded',selection:null,testedTriangles:tested};
    const hit={e:camera.e+direction[0]*nearest.distance,n:camera.n-direction[2]*nearest.distance,h:camera.h+direction[1]*nearest.distance};
    const selected=[];for(const source of nearest.g.roads72.sources){
      if(r.sourceId&&source.facts.id!==r.sourceId)continue;
      const distance=candidate(source,[hit.e,hit.n],r.kind);if(distance===null)continue;
      selected.push({...copy(source.facts),axisDistanceMeters:distance});}
    selected.sort((a,b)=>a.axisDistanceMeters-b.axisDistanceMeters||a.id.localeCompare(b.id));
    return {status:'road',testedTriangles:tested,selection:{surfaceKind:r.kind,rendering:r.rendering,
      selectedCellId:nearest.id,distanceMeters:nearest.distance,hitL93:hit,candidates:selected.slice(0,8),candidateCount:selected.length,
      sourceAttribution:r.sourceId?'source-axis-band':'compatible-source-geometries',sourceEvidenceTruncated:nearest.g.roads72.sourceEvidenceTruncated,
      navigation:copy(nearest.g.roads72.navigation),physicalAccessibilityVerified:false,campaignRoutingActivated:false}};
  }
  const API=Object.freeze({VERSION:'0.72.0',facts,sources,attach,pickScene});root.__SOMA_ROAD_INSPECTION72_CORE__=API;
  if(typeof module!=='undefined'&&module.exports)module.exports=API;
})(typeof window!=='undefined'?window:globalThis);
