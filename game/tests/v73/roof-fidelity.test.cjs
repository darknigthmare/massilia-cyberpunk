'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const K=require('../../src/v69/roof-core.js'),parentPlan=K.roofPlan;
const R=require('../../src/v73/roof-fidelity-core.js');
const P={toMetric:([x,z])=>[892950+x,6247270-z],toLocal:([e,n])=>[e-892950,6247270-n]};
const outer=[[-10,-5],[10,-5],[10,5],[1,5],[1,4.95],[-1,4.95],[-1,5],[-10,5]],hole=[[-2,-2],[-2,2],[2,2],[2,-2]];
const p={height:'20','roof:height':'5','roof:shape':'gabled'},d={height:20,minHeight:0,heightSource:'osm-height',valid:true};
const close=(a,b,tol=1e-6)=>assert(Math.abs(a-b)<=tol,`${a} != ${b}`);
const rect=(a,b,c,e)=>[[a,b,c],[a,c,e]],source=[...rect([-10,-5],[10,-5],[10,-2],[-10,-2]),...rect([-10,2],[10,2],[10,4.95],[-10,4.95]),
 ...rect([-10,-2],[-2,-2],[-2,2],[-10,2]),...rect([2,-2],[10,-2],[10,2],[2,2]),
 ...rect([-10,4.95],[-1,4.95],[-1,5],[-10,5]),...rect([1,4.95],[10,4.95],[10,5],[1,5])];
function reference(rings=[outer,hole]){
 const metric=rings.map(r=>r.map(P.toMetric)),properties={canonical_id:'osm/way/73','soma:layer':'buildings','soma:geometry_sha256':'geometry',
  'soma:mesh53':[{ringsL93:metric,wallsL93:metric.flatMap(r=>r.map((a,i)=>[a,r[(i+1)%r.length]]))}]};
 return [...K.referenceIndex([{sourceReceipt:{sha256:'source'},featureCollection:{features:[{id:'osm/way/73',properties}]}}]).values()][0];
}
const surfaceArea=t=>Math.abs((t[1][0]-t[0][0])*(t[2][2]-t[0][2])-(t[2][0]-t[0][0])*(t[1][2]-t[0][2]))/2;
test('small real-outline concavities get an inferred pitched frame while source triangles and courtyard remain intact',()=>{
 const ref=reference(),before=JSON.stringify([ref,source,p,d]);
 for(const shape of ['gabled','hipped']){
  const properties={...p,'roof:shape':shape};assert.equal(parentPlan(properties,d,ref).modelled,false);
  const plan=K.roofPlan(properties,d,ref);assert.equal(plan.modelled,true);assert.equal(plan.frameOnly,true);
  assert.equal(plan.roofSurveyed,false);assert.equal(plan.accuracy,'inferred');assert.equal(plan.parameterSources.ridgeDirection,'inferred-long-footprint-axis');
  close(plan.frame.rectangleAreaM2,200);close(plan.frame.footprintAreaM2,199.9);close(plan.frame.rectangleAreaError,.0005);
  const out=K.roofTriangles(source,plan,P);close(out.reduce((sum,t)=>sum+surfaceArea(t),0),183.9);
  assert(out.flat().some(q=>q[1]<19));assert(out.flat().some(q=>q[1]>19));
  for(const t of out){
   const x=t.reduce((s,q)=>s+q[0],0)/3,z=t.reduce((s,q)=>s+q[2],0)/3;
   assert(!(Math.abs(x)<2-1e-7&&Math.abs(z)<2-1e-7));assert(!(Math.abs(x)<1-1e-7&&z>4.95+1e-7));
   close(t.reduce((s,q)=>s+q[1],0)/3,plan.heightAt(...P.toMetric([x,z])));
   for(const q of t)assert(q[1]>=15-1e-7&&q[1]<=20+1e-7);
  }
  for(const ring of [outer,hole])for(let i=0;i<ring.length;i++){
   const a=ring[i],b=ring[(i+1)%ring.length],segments=K.wallSegments(a,b,plan,P);
   assert.deepEqual(segments[0].a,a);assert.deepEqual(segments.at(-1).b,b);
   close(segments.reduce((s,w)=>s+Math.hypot(w.b[0]-w.a[0],w.b[1]-w.a[1]),0),Math.hypot(b[0]-a[0],b[1]-a[1]));
   for(const w of segments){close(w.topA,plan.heightAt(...P.toMetric(w.a)));close(w.topB,plan.heightAt(...P.toMetric(w.b)));}
  }
 }
 assert.equal(JSON.stringify([ref,source,p,d]),before);
});
test('source-wide frame is stable under reversed rings and source-triangle cell partition',()=>{
 const first=K.roofPlan(p,d,reference()),reverse=K.roofPlan(p,d,reference([[...outer].reverse(),[...hole].reverse()]));
 for(const q of [[0,0],[0,4],[-7,2],[8,-3]])close(first.heightAt(...P.toMetric(q)),reverse.heightAt(...P.toMetric(q)));
 const left=rect([-10,-2],[-2,-2],[-2,2],[-10,2]),right=rect([2,-2],[10,-2],[10,2],[2,2]);
 close(K.roofTriangles([...left,...right],first,P).reduce((s,t)=>s+surfaceArea(t),0),64);
 assert.deepEqual(K.roofTriangles([...left,...right],first,P),[...K.roofTriangles(left,first,P),...K.roofTriangles(right,first,P)]);
 const a=K.roofTriangles(rect([-10,-5],[0,-5],[0,-2],[-10,-2]),first,P),b=K.roofTriangles(rect([0,-5],[10,-5],[10,-2],[0,-2]),first,P);
 const seam=out=>[...new Set(out.flat().filter(q=>Math.abs(q[0])<1e-6).map(q=>q.map(v=>Math.round(v*1e6)/1e6).join(',')))].sort();
 assert.deepEqual(seam(a),seam(b));assert(seam(a).length>=2);
});
test('missing or incoherent source dimensions, broad concavity, invalid references and direction conflicts stay refused',()=>{
 const ref=reference();
 for(const [properties,dimensions,r] of [[{...p,height:undefined},d,ref],[{...p,'roof:height':undefined},d,ref],[{...p,'roof:height':'30'},d,ref],
  [p,{...d,heightSource:'ign-bdtopo-height'},ref],[p,{...d,heightKind:'eaves'},ref],[p,{...d,heightSource:'estimated-from-levels'},ref],
  [p,d,{...ref,complete:false}],[p,d,{...ref,outerCount:2}],[p,d,{...ref,rings:[[[0,0],[Infinity,0],[0,1]]]}],
  [p,d,reference([[[-10,-5],[10,-5],[10,5],[1,5],[1,0],[-1,0],[-1,5],[-10,5]]])],
  [{...p,'roof:orientation':'diagonal'},d,ref],[{...p,'roof:orientation':'along','roof:direction':'E'},d,ref],
  [{...p,'roof:shape':'hipped','roof:orientation':'across'},d,ref]])assert.equal(K.roofPlan(properties,dimensions,r).modelled,false);
 assert.equal(R.enclosingFrame({...ref,rings:[Array.from({length:513},()=>[0,0])]}),null);
});
test('parent modelled roofs and unrelated shapes keep exactly the same parent plan',()=>{
 for(const shape of ['flat','skillion','gabled','hipped','dome','pyramidal','mansard']){
  const properties={...p,'roof:shape':shape,'roof:direction':'N'},ref=reference([[[-10,-5],[10,-5],[10,5],[-10,5]]]);
  const parent=parentPlan(properties,d,ref),next=K.roofPlan(properties,d,ref);
  assert.equal(next.reason,parent.reason);assert.equal(next.modelled,parent.modelled);
  for(const q of [[0,0],[8,2],[-3,4]])close(next.heightAt(...P.toMetric(q)),parent.heightAt(...P.toMetric(q)));
 }
});
test('browser module requires the existing roof owner before installation',()=>{
 const source=fs.readFileSync(path.join(__dirname,'../../src/v73/roof-fidelity-core.js'),'utf8');
 assert.throws(()=>vm.runInNewContext(source,{}),/Roof core 0.69/);
});
