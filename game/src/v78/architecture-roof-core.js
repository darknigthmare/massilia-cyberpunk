/* A convex frame is a bounded interpretation of nearly convex source roofs.
 * Original source triangles/walls remain the clipping domain, never the frame.
 */
(function(root){
  'use strict';
  const K=root.__SOMA_ARCH68_CORE__,VERSION='0.78.0',MAX_POINTS=128,TOLERANCE_M=.01,MAX_AREA_DEFICIT=.01,EPS=1e-9;
  if(!K||!root.__SOMA_ROOF_FIDELITY73_CORE__||typeof K.roofPlan!=='function')throw new Error('Architecture73 must load before architecture78.');
  const parentPlan=K.roofPlan,point=p=>Array.isArray(p)&&p.length===2&&p.every(Number.isFinite);
  const sub=(a,b)=>[a[0]-b[0],a[1]-b[1]],dot=(a,b)=>a[0]*b[0]+a[1]*b[1],cross=(a,b)=>a[0]*b[1]-a[1]*b[0];
  const area=ring=>ring.reduce((sum,p,i)=>sum+cross(sub(p,ring[0]),sub(ring[(i+1)%ring.length],ring[0])),0)/2;
  function interval(a,b,low,high){
    if(Math.abs(b)<1e-15)return a>=low-EPS&&a<=high+EPS?[0,1]:null;
    const x=(low-a)/b,y=(high-a)/b,l=Math.max(0,Math.min(x,y)),r=Math.min(1,Math.max(x,y));return l<=r+EPS?[l,r]:null;
  }
  function intersection(a,b){if(!a||!b)return null;const lo=Math.max(a[0],b[0]),hi=Math.min(a[1],b[1]);return lo<=hi+EPS?[lo,hi]:null;}
  function circleInterval(a,d,c,radius){
    const q=sub(a,c),aa=dot(d,d),bb=2*dot(q,d),cc=dot(q,q)-radius*radius;
    if(aa<1e-20)return cc<=0?[0,1]:null;
    const discriminant=bb*bb-4*aa*cc;if(discriminant<0)return null;
    const r=Math.sqrt(discriminant);return intersection([(-bb-r)/(2*aa),(-bb+r)/(2*aa)],[0,1]);
  }
  // Union of exact segment-capsule intervals covers every point of an edge.
  // A vertex-only test would admit a thin but arbitrarily deep notch.
  function edgeNear(a,b,boundary,tolerance){
    const d=sub(b,a),coverage=[];
    for(let i=0;i<boundary.length;i++){
      const c=boundary[i],e=boundary[(i+1)%boundary.length],v=sub(e,c),q=sub(a,c),length=Math.hypot(...v);if(length<1e-12)return false;
      const along=interval(dot(q,v)/length,dot(d,v)/length,0,length),strip=interval(cross(q,v)/length,cross(d,v)/length,-tolerance,tolerance);
      for(const part of[intersection(along,strip),circleInterval(a,d,c,tolerance),circleInterval(a,d,e,tolerance)])if(part)coverage.push(part);
    }
    coverage.sort((a,b)=>a[0]-b[0]);let end=0;
    for(const [lo,hi]of coverage){if(lo>end+EPS)return false;end=Math.max(end,hi);if(end>=1-EPS)return true;}return false;
  }
  function simple(ring){
    const on=(p,a,b)=>Math.abs(cross(sub(b,a),sub(p,a)))<EPS&&dot(sub(p,a),sub(p,b))<=EPS;
    for(let i=0;i<ring.length;i++)for(let j=i+1;j<ring.length;j++){
      if(j===i+1||i===0&&j===ring.length-1)continue;
      const a=ring[i],b=ring[(i+1)%ring.length],c=ring[j],d=ring[(j+1)%ring.length];
      const ac=cross(sub(b,a),sub(c,a)),ad=cross(sub(b,a),sub(d,a)),ca=cross(sub(d,c),sub(a,c)),cb=cross(sub(d,c),sub(b,c));
      if(ac*ad<0&&ca*cb<0||on(a,c,d)||on(b,c,d)||on(c,a,b)||on(d,a,b))return false;
    }return true;
  }
  function hullOf(ring){
    const points=ring.map(p=>p.slice()).sort((a,b)=>a[0]-b[0]||a[1]-b[1]),chain=[];
    for(const p of points){while(chain.length>=2&&cross(sub(chain.at(-1),chain.at(-2)),sub(p,chain.at(-1)))<=EPS)chain.pop();chain.push(p);}
    const lower=chain.length;
    for(let i=points.length-2;i>=0;i--){const p=points[i];while(chain.length>lower&&cross(sub(chain.at(-1),chain.at(-2)),sub(p,chain.at(-1)))<=EPS)chain.pop();chain.push(p);}
    chain.pop();return chain;
  }
  function inside(p,ring){
    let result=false;for(let i=0,j=ring.length-1;i<ring.length;j=i++){
      const a=ring[i],b=ring[j];if((a[1]>p[1])!==(b[1]>p[1])&&p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0])result=!result;
    }return result;
  }
  function nearConvexFrame(reference){
    if(reference?.complete!==true||reference.outerCount!==1||reference.hasHoles!==false||reference.rings?.length!==1)return null;
    const source=reference.rings[0];if(!Array.isArray(source)||source.length<3||source.length>MAX_POINTS||!source.every(point))return null;
    const ring=[];for(const p of source)if(!ring.length||Math.hypot(...sub(p,ring.at(-1)))>EPS)ring.push(p.slice());
    if(ring.length>1&&Math.hypot(...sub(ring[0],ring.at(-1)))<=EPS)ring.pop();
    if(ring.length<3||!simple(ring))return null;
    const sourceArea=Math.abs(area(ring)),hull=hullOf(ring),frameArea=Math.abs(area(hull));
    if(sourceArea<.1||hull.length<3||frameArea<sourceArea-1e-8||frameArea<=0||1-sourceArea/frameArea>MAX_AREA_DEFICIT)return null;
    if(!ring.every((a,i)=>edgeNear(a,ring[(i+1)%ring.length],hull,TOLERANCE_M))||
       !hull.every((a,i)=>edgeNear(a,hull[(i+1)%hull.length],ring,TOLERANCE_M)))return null;
    return {ring:hull,sourceAreaM2:sourceArea,frameAreaM2:frameArea,boundaryToleranceMeters:TOLERANCE_M,
      areaDeficit:Math.max(0,1-sourceArea/frameArea),entireBoundariesChecked:true};
  }
  function roofPlan(properties={},dimensions={},reference=null){
    const previous=parentPlan(properties,dimensions,reference);
    if(String(properties['roof:shape']||'').trim().toLowerCase()!=='pyramidal'||previous.modelled||previous.reason!=='complete-convex-footprint-required'||
       dimensions.heightSource!=='osm-height'||dimensions.heightKind==='eaves')return previous;
    const frame=nearConvexFrame(reference);if(!frame)return previous;
    const derived={complete:true,outerCount:1,hasHoles:false,rings:[frame.ring]},plan=parentPlan(properties,dimensions,derived);
    if(!plan.modelled||!inside(plan.apexL93,reference.rings[0]))return previous;
    return {...plan,reason:'osm-parametric-pyramidal-source-clipped-convex-frame',roofSurveyed:false,
      parameterSources:{...plan.parameterSources,footprintFrame:'inferred-convex-frame-with-bounded-source-boundary',apex:'inferred-convex-frame-centroid'},
      footprintPolicy:'retain-prepared-source-triangles-and-walls',derivedFrame78:frame};
  }
  function facts(previous,plan){
    const frame=plan?.derivedFrame78;
    return frame?{...previous,roofFrame78:{boundaryToleranceMeters:frame.boundaryToleranceMeters,sourceAreaM2:frame.sourceAreaM2,
      frameAreaM2:frame.frameAreaM2,sourceFootprintRetained:true,entireBoundariesChecked:true,apexInferred:true,roofSurveyed:false}}:previous;
  }
  K.roofPlan=roofPlan;
  const API=Object.freeze({VERSION,TOLERANCE_M,MAX_POINTS,MAX_AREA_DEFICIT,edgeNear,nearConvexFrame,roofPlan,facts,
    snapshot:()=>({version:VERSION,viewerOnly:true,boundaryToleranceMeters:TOLERANCE_M,sourceFootprintsChanged:false,apexAndProfileInferred:true})});
  root.__SOMA_ARCHITECTURE78_CORE__=API;
  if(typeof module!=='undefined'&&module.exports)module.exports=API;
})(typeof window!=='undefined'?window:globalThis);
