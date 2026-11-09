/* Rendered road unions retain ambiguous attribution. A source sidewalk only
 * extends its own side of the directed Lambert-93 axis; it creates no access,
 * geometry, navigation edge or proof of ownership of the selected surface.
 */
(function(root){
  'use strict';
  function inside(point,ring){
    let yes=false;
    for(let i=0,j=ring.length-1;i<ring.length;j=i++){
      const a=ring[i],b=ring[j];
      if((a[1]>point[1])!==(b[1]>point[1])&&point[0]<(b[0]-a[0])*(point[1]-a[1])/(b[1]-a[1])+a[0])yes=!yes;
    }
    return yes;
  }
  function candidate(source,point,kind){
    const mg=source.geometry,polygon=rings=>inside(point,rings[0])&&!rings.slice(1).some(r=>inside(point,r));
    if(mg.type==='Polygon')return polygon(mg.coordinates)?0:null;
    if(mg.type==='MultiPolygon')return mg.coordinates.some(polygon)?0:null;
    const lines=mg.type==='LineString'?[mg.coordinates]:mg.coordinates,side=source.profile.sidewalk||{};
    let distance=Infinity;
    for(const line of lines)for(let i=1;i<line.length;i++){
      const a=line[i-1],b=line[i],dx=b[0]-a[0],dy=b[1]-a[1],square=dx*dx+dy*dy;
      if(!square)continue;
      const t=((point[0]-a[0])*dx+(point[1]-a[1])*dy)/square;
      // Preserve the source band's flat ends and the existing 3 cm tolerance.
      if(t< -1e-6||t>1+1e-6)continue;
      const signed=dx*(point[1]-a[1])-dy*(point[0]-a[0]),name=signed>0?'left':'right';
      const walk=kind==='walk'&&side[name]?side[name+'Width']||0:0;
      const current=Math.hypot(point[0]-a[0]-t*dx,point[1]-a[1]-t*dy);
      if(current<=source.profile.width/2+walk+.03)distance=Math.min(distance,current);
    }
    return Number.isFinite(distance)?distance:null;
  }
  const API=Object.freeze({VERSION:'0.77.0',candidate,
    policy:'Directed source-side compatibility only; union ownership and physical access remain unverified.'});
  root.__SOMA_NAVIGATION77_CORE__=API;
  if(typeof module!=='undefined'&&module.exports)module.exports=API;
})(typeof window!=='undefined'?window:globalThis);
