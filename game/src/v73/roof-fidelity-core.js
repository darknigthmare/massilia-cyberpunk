/* Source-clipped pitched roofs. The enclosing rectangle is an inferred frame;
 * it never replaces prepared footprints, courtyard holes or source walls.
 */
(function(root){
  'use strict';
  const K=root.__SOMA_ARCH68_CORE__||(typeof require==='function'?require('../v69/roof-core.js'):null);
  if(!K||typeof K.roofPlan!=='function'||K.roofCoreVersion!=='0.69.0')throw new Error('Roof core 0.69 must load before roof fidelity 0.73.');
  const previousPlan=K.roofPlan,EPS=1e-7,MAX_AREA_DEFICIT=.01,MAX_POINTS=512;
  const point=p=>Array.isArray(p)&&p.length>=2&&Number.isFinite(p[0])&&Number.isFinite(p[1]);
  const cross=(a,b,c)=>(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
  const area=ring=>ring.reduce((sum,p,i)=>sum+cross(ring[0],p,ring[(i+1)%ring.length]),0)/2;
  function enclosingFrame(reference){
    if(reference?.complete!==true||reference.outerCount!==1||!Array.isArray(reference.rings)||!reference.rings.length||
      reference.rings.some(r=>!Array.isArray(r)||r.length<3||r.length>MAX_POINTS||!r.every(point)))return null;
    const ring=reference.rings.reduce((a,b)=>Math.abs(area(a))>=Math.abs(area(b))?a:b),footprintAreaM2=Math.abs(area(ring));
    if(footprintAreaM2<.1)return null;
    // Searching the bounded set of source edge directions yields an enclosing
    // rectangle without requiring exact convexity
    // of the surveyed/tagged outline. Small re-entrant wall details stay intact.
    // A translated, sorted origin makes the frame independent of cell/ring order.
    const origin=ring.reduce((a,b)=>a[0]<b[0]||a[0]===b[0]&&a[1]<=b[1]?a:b);
    let best=null;
    for(let i=0;i<ring.length;i++){
      const a=ring[i],b=ring[(i+1)%ring.length],length=Math.hypot(b[0]-a[0],b[1]-a[1]);if(length<=EPS)continue;
      let u=[(b[0]-a[0])/length,(b[1]-a[1])/length];
      if(u[0]<-EPS||Math.abs(u[0])<=EPS&&u[1]<0)u=u.map(x=>-x);
      const v=[-u[1],u[0]],points=ring.map(p=>[(p[0]-origin[0])*u[0]+(p[1]-origin[1])*u[1],(p[0]-origin[0])*v[0]+(p[1]-origin[1])*v[1]]);
      const bounds=[Math.min(...points.map(p=>p[0])),Math.min(...points.map(p=>p[1])),Math.max(...points.map(p=>p[0])),Math.max(...points.map(p=>p[1]))];
      const size=(bounds[2]-bounds[0])*(bounds[3]-bounds[1]),bearing=Math.atan2(u[1],u[0]);
      if(!best||size<best.size-1e-8||Math.abs(size-best.size)<=1e-8&&bearing<best.bearing)best={u,v,bounds,size,bearing};
    }
    if(!best||best.size<=.1)return null;
    const deficit=1-footprintAreaM2/best.size;
    if(deficit< -1e-8||deficit>MAX_AREA_DEFICIT)return null;
    const {u,v,bounds}=best,toMetric=(s,t)=>[origin[0]+u[0]*s+v[0]*t,origin[1]+u[1]*s+v[1]*t];
    return {ring:[toMetric(bounds[0],bounds[1]),toMetric(bounds[2],bounds[1]),toMetric(bounds[2],bounds[3]),toMetric(bounds[0],bounds[3])],
      rectangleAreaM2:best.size,footprintAreaM2,rectangleAreaError:Math.max(0,deficit)};
  }
  function roofPlan(properties={},dimensions={},reference=null){
    const parent=previousPlan(properties,dimensions,reference),shape=String(properties?.['roof:shape']||'').trim().toLowerCase();
    // Keep all parent decisions, including explicit direction conflicts, datum
    // semantics and height validation. Only the exact-convexity refusal changes.
    if(!['gabled','hipped'].includes(shape)||parent.modelled||parent.reason!=='complete-near-rectangular-footprint-required'||
      dimensions?.heightSource!=='osm-height'||dimensions.heightKind==='eaves')return parent;
    const frame=enclosingFrame(reference);if(!frame)return parent;
    const derivedReference={complete:true,outerCount:1,hasHoles:false,rings:[frame.ring]};
    const plan=previousPlan(properties,dimensions,derivedReference);if(!plan.modelled)return {...parent,reason:plan.reason};
    return {...plan,reason:'osm-parametric-'+shape+'-source-clipped-frame',
      parameterSources:{...plan.parameterSources,footprintFrame:'inferred-enclosing-rectangle-from-complete-source-boundary'},
      frame:{...plan.frame,rectangleAreaError:frame.rectangleAreaError,rectangleAreaM2:frame.rectangleAreaM2,footprintAreaM2:frame.footprintAreaM2},
      footprintPolicy:'retain-prepared-source-triangles-and-holes',frameOnly:true,roofSurveyed:false};
  }
  K.roofPlan=roofPlan;
  const API=Object.freeze({VERSION:'0.73.0',MAX_AREA_DEFICIT,MAX_POINTS,enclosingFrame,roofPlan});
  root.__SOMA_ROOF_FIDELITY73_CORE__=API;
  if(typeof module!=='undefined'&&module.exports)module.exports=API;
})(typeof window!=='undefined'?window:globalThis);
