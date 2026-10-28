/* A decimal without a leading zero is a dimension, not a class estimate.
 * The one baked surface correction is source-bound and keeps the native DEM.
 */
(function(root){
  'use strict';
  const PROOF=Object.freeze({id:'osm/way/1413045827',cellId:'V52-MC-E12-N70',
    cellSHA256:'fedad18605b82aeb7fc4d6cb71b9cc3ab10080b03b0e390c61cdaddb94ca2cd5',
    geometrySHA256:'c5e421c54872e5b250108efedf5690d8b528aef730de3b8ead1b4a415ec9ed95',
    sourceSHA256:'258a6450ae90142b4c4c19c851e3983a5c82c0e216dbe5f4d6fcbda0b0646467',
    previousWidth:1.8,width:.5});
  const installed=new WeakSet();
  function normalizedWidth(value){
    if(typeof value!=='string')return value;
    const s=value.trim();
    return /^\.\d+\s*(?:m|metres?|meters?|cm|ft|feet|'|in|inches?|\")?$/i.test(s)?'0'+s:value;
  }
  function profile(properties,original){
    const p=properties||{},width=normalizedWidth(p.width),estimate=normalizedWidth(p.est_width);
    return original(width===p.width&&estimate===p.est_width?p:{...p,width,est_width:estimate});
  }
  function install(core=root.__SOMA_FIDELITY59_CORE__){
    if(!core||typeof core.roadProfile!=='function')return false;
    if(!installed.has(core)){const original=core.roadProfile;core.roadProfile=p=>profile(p,original);installed.add(core);}
    return true;
  }
  function deriveSurfaces(surface,record,projector){
    const q=PROOF;
    if(record?.cellId!==q.cellId||record.contentSHA256!==q.cellSHA256||record.sourceReceipt?.sha256!==q.sourceSHA256||
      surface?.schema!=='soma-metropole/surface-cell/1'||surface.cellId!==q.cellId||surface.contentSHA256!==q.cellSHA256||
      surface.sourcePbfSHA256!==q.sourceSHA256||surface.cell?.contentSHA256!==q.cellSHA256||surface.cell.sourceSHA256!==q.sourceSHA256)return surface;
    const p=record.featureCollection?.features?.find(f=>(f.properties?.canonical_id||f.id)===q.id)?.properties,
      old=surface.roadMetadata?.[q.id],triangles=surface.cell.surfaces?.unsealed,mg=p?.['soma:metricGeometry'];
    if(!p||p.width!=='.5'||p['soma:geometry_sha256']!==q.geometrySHA256||mg?.type!=='LineString'||mg.coordinates?.length!==2||
      old?.geometrySHA256!==q.geometrySHA256||old.width!==q.previousWidth||old.widthSource!=='estimated-from-class'||old.invalidWidth!==true||
      old.structural||!Array.isArray(triangles)||triangles.length!==2||typeof projector?.toLocal!=='function')return surface;
    const a=projector.toLocal(mg.coordinates[0]),b=projector.toLocal(mg.coordinates[1]),length=Math.hypot(b[0]-a[0],b[1]-a[1]);
    if(!Number.isFinite(length)||length<.01)return surface;
    const u=[(b[0]-a[0])/length,(b[1]-a[1])/length],n=[-u[1],u[0]],corners=new Set(),triangleCorners=[];
    let area=0;
    for(const t of triangles){
      if(!Array.isArray(t)||t.length!==3)return surface;
      const keys=new Set();for(const v of t){
        if(!Array.isArray(v)||v.length!==2||!v.every(Number.isFinite))return surface;
        const along=(v[0]-a[0])*u[0]+(v[1]-a[1])*u[1],across=(v[0]-a[0])*n[0]+(v[1]-a[1])*n[1];
        if(Math.min(Math.abs(along),Math.abs(along-length))>1e-6||Math.abs(Math.abs(across)-q.previousWidth/2)>1e-6)return surface;
        const key=(along>length/2?'1':'0')+(across>0?'+':'-');corners.add(key);keys.add(key);
      }
      if(keys.size!==3)return surface;triangleCorners.push(keys);
      area+=Math.abs((t[1][0]-t[0][0])*(t[2][1]-t[0][1])-(t[1][1]-t[0][1])*(t[2][0]-t[0][0]))/2;
    }
    // Both complete triangles must describe this isolated old-width rectangle.
    // Clipped, occluded, merged or overlapping surfaces are left untouched.
    const diagonal=[...triangleCorners[0]].filter(key=>triangleCorners[1].has(key));
    if(corners.size!==4||diagonal.length!==2||diagonal[0][0]===diagonal[1][0]||diagonal[0][1]===diagonal[1][1]||Math.abs(area-length*q.previousWidth)>1e-6)return surface;
    const narrowed=triangles.map(t=>t.map(v=>{
      const along=(v[0]-a[0])*u[0]+(v[1]-a[1])*u[1],across=((v[0]-a[0])*n[0]+(v[1]-a[1])*n[1])*q.width/q.previousWidth;
      return[a[0]+along*u[0]+across*n[0],a[1]+along*u[1]+across*n[1]];
    }));
    const correction={id:q.id,previousWidthMeters:q.previousWidth,widthMeters:q.width,
      previousAreaM2:area,areaM2:length*q.width,method:'isolated-source-rectangle-contraction',nativeDemDrape:true};
    return {...surface,cell:{...surface.cell,surfaces:{...surface.cell.surfaces,unsealed:narrowed},
      areaM2:{...surface.cell.areaM2,unsealed:length*q.width}},roadMetadata:{...surface.roadMetadata,
      [q.id]:{...old,width:q.width,widthSource:'osm-width',invalidWidth:false,correction72:correction}},fidelity72:[correction]};
  }
  const API=Object.freeze({VERSION:'0.72.0',PROOF,normalizedWidth,profile,install,deriveSurfaces});
  root.__SOMA_FIDELITY72_CORE__=API;if(typeof module!=='undefined'&&module.exports)module.exports=API;
  install();
})(typeof window!=='undefined'?window:globalThis);
