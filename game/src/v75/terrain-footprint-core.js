/* Extrema of the measured, fixed-diagonal terrain inside a source footprint.
 * A piecewise linear surface reaches extrema at a mesh vertex or a boundary
 * intersection. No raster value, footprint or measured IGN building datum is
 * changed. Courtyard interiors do not belong to the supporting footprint. */
(function(root){
  'use strict';
  function accumulate(grid,rings,item,inPolygon){
    const s=grid.step,add=(e,n)=>{const h=grid.sample(e,n);if(h===null){item.missing=true;return;}item.min=Math.min(item.min,h);item.max=Math.max(item.max,h);item.n++;};
    if(!Array.isArray(rings)||!rings.length)return item;
    let minE=Infinity,maxE=-Infinity,minN=Infinity,maxN=-Infinity;
    for(const ring of rings)for(let i=0;i<ring.length;i++){
      const a=ring[i],b=ring[(i+1)%ring.length],de=b[0]-a[0],dn=b[1]-a[1];
      minE=Math.min(minE,a[0]);maxE=Math.max(maxE,a[0]);minN=Math.min(minN,a[1]);maxN=Math.max(maxN,a[1]);
      add(a[0],a[1]);
      // The two square-grid families and the actual fixed-diagonal family.
      for(const [u,d] of [[(a[0]-grid.x0)/s,de/s],[(grid.n0-a[1])/s,-dn/s],[(a[0]-grid.x0+grid.n0-a[1])/s,(de-dn)/s]]){
        if(Math.abs(d)<1e-12)continue;
        for(let k=Math.ceil(Math.min(u,u+d));k<=Math.floor(Math.max(u,u+d));k++){
          const t=(k-u)/d;if(t>1e-9&&t<1-1e-9)add(a[0]+de*t,a[1]+dn*t);
        }
      }
    }
    const x0=Math.max(0,Math.ceil((minE-grid.x0)/s)),x1=Math.min(grid.cols-1,Math.floor((maxE-grid.x0)/s)),
      y0=Math.max(0,Math.ceil((grid.n0-maxN)/s)),y1=Math.min(grid.rows-1,Math.floor((grid.n0-minN)/s));
    // Each validated campaign mesh is clipped to one 250 m cell. Keep a
    // bounded failure for an incompatible external mesh rather than hanging.
    if((x1-x0+1)*(y1-y0+1)>3000){item.missing=true;return item;}
    for(let y=y0;y<=y1;y++)for(let x=x0;x<=x1;x++){
      const e=grid.x0+x*s,n=grid.n0-y*s;
      if(inPolygon([e,n],rings))add(e,n);
    }
    return item;
  }
  const api=Object.freeze({accumulate});root.__SOMA_TERRAIN75_CORE__=api;
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof globalThis!=='undefined'?globalThis:this);
