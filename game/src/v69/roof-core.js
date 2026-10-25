/* Source-parameterised roofs. Apex locations and curved profiles are inferred
 * model parameters, not surveyed architecture. Footprints are never changed.
 */
(function (root) {
  'use strict';
  const K = root.__SOMA_ARCH68_CORE__ ||
    (typeof require === 'function' ? require('../v68/architecture-core.js') : null);
  if (!K) throw new Error('Architecture core 0.68 must load before roof core 0.69.');
  const previousPlan = K.roofPlan, previousTriangles = K.roofTriangles;
  const EPS = 1e-7, DOME_ERROR = 0.05;

  const finitePoint = p => Array.isArray(p) && p.length >= 2 && Number.isFinite(p[0]) && Number.isFinite(p[1]);
  const cross = (a, b, c) => (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
  const interpolate = (a, b, t) => [a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t];
  const distance = (a, b) => Math.hypot(b[0]-a[0], b[1]-a[1]);

  function measure(value) {
    if (typeof value === 'number') return Number.isFinite(value) && value >= 0 ? value : null;
    if (typeof value !== 'string') return null;
    const text = value.trim().replace(',', '.');
    const feet = text.match(/^(\d+(?:\.\d+)?)\s*'\s*(\d+(?:\.\d+)?)\s*(?:"|in)?$/);
    if (feet) return +feet[1]*0.3048 + +feet[2]*0.0254;
    const m = text.match(/^(\d+(?:\.\d+)?)\s*(m|metres?|meters?|cm|ft|feet|'|in|inches?|\")?$/i);
    if (!m) return null;
    const unit = (m[2] || 'm').toLowerCase();
    return +m[1] * (unit === 'cm' ? 0.01 : /^(ft|feet|')$/.test(unit) ? 0.3048 : /^(in|inch|inches|\")$/.test(unit) ? 0.0254 : 1);
  }

  function area(polygon) {
    if (polygon.length < 3) return 0;
    const origin = polygon[0];
    return polygon.reduce((sum, p, i) => sum + cross(origin, p, polygon[(i+1)%polygon.length]), 0) / 2;
  }

  function clean(polygon) {
    const result = [];
    for (const p of polygon) {
      if (!result.length || distance(p, result[result.length-1]) > EPS) result.push(p.slice(0, 2));
    }
    if (result.length > 1 && distance(result[0], result[result.length-1]) <= EPS) result.pop();
    return result;
  }

  function convexRing(reference) {
    if (!reference?.complete || reference.outerCount !== 1 || reference.hasHoles || reference.rings?.length !== 1) return null;
    let ring = clean(reference.rings[0]);
    if (ring.length < 3 || !ring.every(finitePoint) || Math.abs(area(ring)) < 0.1) return null;
    if (area(ring) < 0) ring.reverse();
    // All vertices must lie on the inner side of every edge. This also rejects
    // crossing star-shaped boundaries that a turn-sign check alone would miss.
    for (let i=0; i<ring.length; i++) {
      const a=ring[i], b=ring[(i+1)%ring.length], length=distance(a,b);
      if (length <= EPS || ring.some(p => cross(a,b,p)/length < -EPS)) return null;
    }
    return ring;
  }

  function centroid(ring) {
    const origin=ring[0], points=ring.map(p => [p[0]-origin[0],p[1]-origin[1]]);
    let twiceArea=0, e=0, n=0;
    for (let i=0; i<points.length; i++) {
      const a=points[i], b=points[(i+1)%points.length], c=a[0]*b[1]-b[0]*a[1];
      twiceArea+=c; e+=(a[0]+b[0])*c; n+=(a[1]+b[1])*c;
    }
    return [origin[0]+e/(3*twiceArea),origin[1]+n/(3*twiceArea)];
  }

  function solve3(matrix, rhs) {
    const a=matrix.map((row,i) => [...row,rhs[i]]);
    for (let column=0;column<3;column++) {
      let pivot=column;
      for(let row=column+1;row<3;row++) if(Math.abs(a[row][column])>Math.abs(a[pivot][column]))pivot=row;
      [a[column],a[pivot]]=[a[pivot],a[column]];
      const divisor=a[column][column]; if(Math.abs(divisor)<1e-12)return null;
      a[column]=a[column].map(value=>value/divisor);
      for(let row=0;row<3;row++)if(row!==column){const factor=a[row][column];a[row]=a[row].map((value,i)=>value-factor*a[column][i]);}
    }
    return a.map((row,i)=>row[3]);
  }

  function circleFit(ring) {
    if(ring.length<8)return null;
    const origin=ring[0], points=ring.map(p=>[p[0]-origin[0],p[1]-origin[1]]);
    const vectors=points.map(([x,y])=>[x,y,1]), rhs=points.map(([x,y])=>-x*x-y*y);
    const matrix=Array.from({length:3},(_,i)=>Array.from({length:3},(_,j)=>vectors.reduce((sum,v)=>sum+v[i]*v[j],0)));
    const solution=solve3(matrix,Array.from({length:3},(_,i)=>vectors.reduce((sum,v,k)=>sum+v[i]*rhs[k],0)));
    if(!solution)return null;
    const x=-solution[0]/2,y=-solution[1]/2,radius=Math.sqrt(Math.max(0,x*x+y*y-solution[2]));
    if(!Number.isFinite(radius)||radius<0.05)return null;
    const residual=Math.max(...points.map(p=>Math.abs(Math.hypot(p[0]-x,p[1]-y)-radius)))/radius;
    const center=[origin[0]+x,origin[1]+y];
    if(residual>0.01||ring.some((a,i)=>cross(a,ring[(i+1)%ring.length],center)<-EPS))return null;
    return {center,radius,residual};
  }

  function domeDeviation(a,b,rise) {
    const f=t=>Math.sqrt(Math.max(0,1-t*t)), fa=f(a),fb=f(b),slope=(fb-fa)/(b-a);
    const peak=-slope/Math.sqrt(1+slope*slope);
    if(peak<=a||peak>=b)return 0;
    return Math.max(0,(f(peak)-(fa+(fb-fa)*(peak-a)/(b-a)))*rise);
  }

  function domeBands(rise) {
    const pending=[[0,1]],bands=[];
    while(pending.length){
      const [a,b]=pending.pop(),error=domeDeviation(a,b,rise);
      if(error>DOME_ERROR-1e-10){
        if(b-a<1e-12||pending.length+bands.length>4096)return null;
        const middle=(a+b)/2;pending.push([middle,b],[a,middle]);
      }else bands.push({from:a,to:b,errorM:error});
    }
    return bands.sort((a,b)=>a.from-b.from);
  }

  function roofPlan(properties={},dimensions={},reference=null) {
    const p=properties||{},dim=dimensions||{},shape=String(p['roof:shape']||'').trim().toLowerCase();
    if(!['pyramidal','dome'].includes(shape))return previousPlan(p,dim,reference);
    const fallback=reason=>({...previousPlan(p,dim,reference),reason});
    const total=dim.height,floor=dim.minHeight??0,height=measure(p.height),riseTag=measure(p['roof:height']);
    if(!Number.isFinite(total)||total<=0||total>1000||!Number.isFinite(floor)||floor<0||total<=floor+0.05||dim.valid===false)return fallback('invalid-dimensions');
    if(height===null||Math.abs(height-total)>1e-5)return fallback('explicit-total-height-required');
    if(riseTag===null||riseTag<=0||riseTag>total-floor+1e-5)return fallback('invalid-or-missing-roof-height');
    const ring=convexRing(reference);
    if(!ring)return fallback('complete-convex-footprint-required');
    const circle=shape==='dome'?circleFit(ring):null;
    if(shape==='dome'&&!circle)return fallback('dome-footprint-not-circular');
    const apex=circle?circle.center:centroid(ring),rise=Math.min(riseTag,total-floor),eave=total-rise;
    const edges=ring.map((a,i)=>{const b=ring[(i+1)%ring.length];return {a,b,centerDistance:cross(a,b,apex)};});
    if(edges.some(edge=>edge.centerDistance<=EPS))return fallback('degenerate-roof-reference');
    const rho=(e,n)=>Math.max(0,Math.min(1,Math.max(...edges.map(edge=>1-cross(edge.a,edge.b,[e,n])/edge.centerDistance))));
    const heightAt=shape==='dome'?(e,n)=>{
      const t=rho(e,n);return t>=1-1e-10?eave:eave+rise*Math.sqrt(Math.max(0,1-t*t));
    }:(e,n)=>eave+rise*(1-rho(e,n));
    const bands=shape==='dome'?domeBands(rise):[{from:0,to:1,errorM:0}];
    if(!bands)return fallback('roof-tessellation-budget-exceeded');
    const facets=[];
    for(let i=0;i<ring.length;i++)for(const band of bands){
      const a=ring[i],b=ring[(i+1)%ring.length];
      facets.push(clean([interpolate(apex,a,band.from),interpolate(apex,a,band.to),
        interpolate(apex,b,band.to),interpolate(apex,b,band.from)]));
    }
    return {
      shape,requestedShape:shape,modelled:true,reason:'osm-parametric-'+shape,
      eave,heightAt,breakLines:ring.map(point=>[apex.slice(),point.slice()]),
      geometrySource:'osm-parametric',accuracy:'inferred',
      parameterSources:{shape:'osm-roof-shape',height:'osm-height',roofHeight:'osm-roof-height',
        apex:circle?'inferred-circle-fit':'inferred-centroid',profile:'interpreted-roof-template'},
      apexL93:apex.slice(),apexHeight:total,
      profile:shape==='dome'?'polygon-conformed-ellipsoid':'centroid-pyramid',
      errorBoundM:Math.max(...bands.map(band=>band.errorM)),requestedErrorM:shape==='dome'?DOME_ERROR:0,
      lodBands:bands.map(band=>({...band})),circleResidual:circle?.residual??null,
      // Canonical facet domains are a separate derived model, never source rings.
      facetDomainsL93:facets
    };
  }

  function clipConvex(subject,clip) {
    let polygon=subject.map(point=>point.slice());
    for(let i=0;i<clip.length&&polygon.length;i++){
      const a=clip[i],b=clip[(i+1)%clip.length],length=distance(a,b);if(length<=EPS)continue;
      const output=[];let previous=polygon[polygon.length-1],before=cross(a,b,previous)/length;
      for(const point of polygon){
        const current=cross(a,b,point)/length,inside=current>=-EPS,was=before>=-EPS;
        if(inside!==was){const t=before/(before-current);output.push(interpolate(previous,point,t));}
        if(inside)output.push(point.slice());previous=point;before=current;
      }
      polygon=clean(output);
    }
    return polygon;
  }

  function roofTriangles(triangles,plan,projector) {
    if(plan?.geometrySource!=='osm-parametric')return previousTriangles(triangles,plan,projector);
    if(!Array.isArray(triangles)||typeof projector?.toMetric!=='function'||typeof projector?.toLocal!=='function')throw new TypeError('Parametric roofs require prepared triangles and reversible metric projection.');
    const output=[];
    for(const triangle of triangles){
      if(!Array.isArray(triangle)||triangle.length!==3||!triangle.every(finitePoint))throw new TypeError('Invalid prepared roof triangle.');
      const metric=triangle.map(point=>projector.toMetric(point.slice()));
      if(!metric.every(finitePoint))throw new TypeError('Invalid metric roof triangle.');
      for(const facet of plan.facetDomainsL93){
        const polygon=clipConvex(metric,facet);
        if(polygon.length<3||Math.abs(area(polygon))<1e-10)continue;
        for(let i=1;i+1<polygon.length;i++){
          const points=[polygon[0],polygon[i],polygon[i+1]];
          if(Math.abs(cross(...points))<1e-10)continue;
          output.push(points.map(point=>{
            const local=projector.toLocal(point.slice()),height=plan.heightAt(...point);
            if(!finitePoint(local)||!Number.isFinite(height))throw new TypeError('Invalid lifted roof coordinate.');
            return [local[0],height,local[1]];
          }));
          if(output.length>100000)throw new RangeError('Parametric roof exceeds the geometry budget.');
        }
      }
    }
    return output;
  }

  function wallSegments(a,b,plan,projector) {
    if(!finitePoint(a)||!finitePoint(b)||typeof projector?.toMetric!=='function'||typeof plan?.heightAt!=='function')throw new TypeError('Wall heights require source endpoints and a metric roof plan.');
    const ma=projector.toMetric(a.slice()),mb=projector.toMetric(b.slice());
    if(!finitePoint(ma)||!finitePoint(mb))throw new TypeError('Invalid metric wall coordinate.');
    const topA=plan.heightAt(...ma),topB=plan.heightAt(...mb);
    if(!Number.isFinite(topA)||!Number.isFinite(topB))throw new TypeError('Invalid wall roof height.');
    return [{a:a.slice(0,2),b:b.slice(0,2),topA,topB}];
  }

  Object.assign(K,{roofPlan,roofTriangles,wallSegments,roofCoreVersion:'0.69.0'});
  root.__SOMA_ARCH68_CORE__=K;root.__SOMA_ROOF69_CORE__=K;
  if(typeof module!=='undefined'&&module.exports)module.exports=K;
})(typeof window!=='undefined'?window:globalThis);
