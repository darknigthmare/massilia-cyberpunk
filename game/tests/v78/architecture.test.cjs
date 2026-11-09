'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const source=require('./architecture-source.json'),game=path.resolve(__dirname,'../..');
function model(extended){const c=vm.createContext({module:{exports:{}}});for(const name of['v68/architecture-core.js','v69/roof-core.js','v73/roof-fidelity-core.js',...(extended?['v78/architecture-roof-core.js']:[])])vm.runInContext(fs.readFileSync(path.join(game,'src',name),'utf8'),c);return {A:c.__SOMA_ARCH68_CORE__,X:c.__SOMA_ARCHITECTURE78_CORE__};}
const before=model(false),after=model(true),clone=x=>JSON.parse(JSON.stringify(x)),json=x=>JSON.stringify(x),area=ring=>Math.abs(ring.reduce((s,p,i)=>{const q=ring[(i+1)%ring.length];return s+p[0]*q[1]-p[1]*q[0];},0))/2;
const close=(a,b,t=1e-7)=>assert(Math.abs(a-b)<=t,`${a} != ${b}`),ref=ring=>({complete:true,outerCount:1,hasHoles:false,rings:[ring]});
test('six real explicit roofs gain only an inferred source-clipped pyramid, retaining all source values',()=>{
 const original=json(source.rows);for(const row of source.rows){const a=before.A.roofPlan(row.p,row.dim,row.reference),b=after.A.roofPlan(row.p,row.dim,row.reference);assert.equal(a.modelled,false);assert.equal(a.reason,'complete-convex-footprint-required');assert.equal(b.modelled,true);assert.equal(b.shape,'pyramidal');assert.equal(b.roofSurveyed,false);assert.equal(b.footprintPolicy,'retain-prepared-source-triangles-and-walls');assert.equal(b.derivedFrame78.entireBoundariesChecked,true);assert.equal(b.derivedFrame78.boundaryToleranceMeters,.01);close(b.heightAt(...b.apexL93),row.dim.height);close(b.eave,row.dim.height-parseFloat(row.p['roof:height']));assert(b.eave>=row.dim.minHeight);for(const p of b.derivedFrame78.ring)close(b.heightAt(...p),b.eave);}
 assert.equal(json(source.rows),original);
});
test('full-edge capsule coverage rejects diagonal shortcuts and a thin deep notch',()=>{
 const ring=[[0,0],[10,0],[10,10],[0,10]];assert(after.X.edgeNear([1,.009],[9,.009],ring,.01));assert(!after.X.edgeNear([0,0],[10,10],ring,.01));
 assert.equal(after.X.nearConvexFrame(ref([[0,0],[10,0],[10,10],[5.001,10],[5.001,1],[4.999,1],[4.999,10],[0,10]])),null);
 assert.equal(after.X.nearConvexFrame(ref([[0,0],[10,0],[10,8],[5,7.98],[0,8]])),null);
 assert(after.X.nearConvexFrame(ref([[0,0],[10,0],[10,8],[5,7.995],[0,8]])));
});
test('holes, incomplete boundaries, multiple outers and crossed rings remain refused',()=>{
 const r=clone(source.rows[2]);for(const change of[{complete:false},{outerCount:2},{hasHoles:true},{rings:[r.reference.rings[0],[[0,0],[1,0],[1,1]]]}])assert.equal(after.X.nearConvexFrame({...r.reference,...change}),null);
 assert.equal(after.X.nearConvexFrame(ref([[0,0],[10,10],[0,10],[10,0]])),null);
 assert.equal(after.X.nearConvexFrame(ref(Array.from({length:129},(_,i)=>[Math.cos(i),Math.sin(i)]))),null);
 const holes={...r.reference,hasHoles:true,rings:[...r.reference.rings,[[0,0],[1,0],[1,1]]]};assert.equal(after.A.roofPlan(r.p,r.dim,holes).modelled,false);
});
test('invalid heights, eave references, estimates and unsupported shape decisions are preserved',()=>{
 const r=source.rows[2];for(const [p,d]of[[{...r.p,height:undefined},r.dim],[r.p,{...r.dim,minHeight:r.dim.height-.1}],[r.p,{...r.dim,heightSource:'ign-bdtopo-height',heightKind:'eaves'}],[r.p,{...r.dim,heightSource:'estimated-levels'}],[{...r.p,'roof:shape':'mansard'},r.dim]]){
  const a=before.A.roofPlan(p,d,r.reference),b=after.A.roofPlan(p,d,r.reference);assert.equal(json(b),json(a));
 }
});
test('already supported convex profiles and existing other roof shapes remain identical',()=>{
 const r=source.rows[2],hull=after.X.nearConvexFrame(r.reference).ring;for(const shape of['pyramidal','flat','gabled','hipped','dome','skillion']){
  const p={...r.p,'roof:shape':shape,'roof:direction':'N'},reference=ref(clone(hull)),a=before.A.roofPlan(p,r.dim,reference),b=after.A.roofPlan(p,r.dim,reference);assert.equal(json(a),json(b));for(const q of hull)close(a.heightAt(...q),b.heightAt(...q));
 }
});
test('frame and apex are invariant to source ring order, orientation and metric translation',()=>{
 for(const r of source.rows){const original=after.A.roofPlan(r.p,r.dim,r.reference);for(const reverse of[false,true])for(const shift of[0,1,2]){
  const ring=clone(r.reference.rings[0]),ordered=reverse?ring.reverse():ring;const moved=[...ordered.slice(shift),...ordered.slice(0,shift)].map(p=>[p[0]-892000,p[1]-6247000]);const p=after.A.roofPlan(r.p,r.dim,ref(moved));assert(p.modelled);close(p.apexL93[0]+892000,original.apexL93[0],1e-6);close(p.apexL93[1]+6247000,original.apexL93[1],1e-6);close(p.derivedFrame78.sourceAreaM2,original.derivedFrame78.sourceAreaM2,1e-6);
 }}
});
test('roof facets retain the source notch and walls with no footprint expansion',()=>{
 const ring=[[0,0],[10,0],[10,8],[5,7.995],[0,8]],p={'roof:shape':'pyramidal',height:'12','roof:height':'3'},d={height:12,minHeight:0,heightSource:'osm-height',valid:true},plan=after.A.roofPlan(p,d,ref(ring));assert(plan.modelled);
 const input=[[ring[0],ring[1],ring[2]],[ring[0],ring[2],ring[3]],[ring[0],ring[3],ring[4]]],projector={toLocal:p=>p,toMetric:p=>p};const out=after.A.roofTriangles(input,plan,projector);close(out.reduce((s,t)=>s+area(t.map(p=>[p[0],p[2]])),0),area(ring));
 for(const t of out){for(const q of t){assert(q[1]>=9-1e-7&&q[1]<=12+1e-7);close(q[1],plan.heightAt(q[0],q[2]));}const center=[t.reduce((s,p)=>s+p[0],0)/3,t.reduce((s,p)=>s+p[2],0)/3];assert(center[1]<=8-Math.min(center[0],10-center[0])*.001+1e-7);}
 for(let i=0;i<ring.length;i++){const a=ring[i],b=ring[(i+1)%ring.length],walls=after.A.wallSegments(a,b,plan,projector);close(walls.reduce((s,w)=>s+Math.hypot(w.b[0]-w.a[0],w.b[1]-w.a[1]),0),Math.hypot(b[0]-a[0],b[1]-a[1]));for(const w of walls){close(w.topA,plan.heightAt(...w.a));close(w.topB,plan.heightAt(...w.b));}}
});
test('inspection explicitly labels the derived frame and keeps prior source and accuracy fields',()=>{
 const r=source.rows[2],p=after.A.roofPlan(r.p,r.dim,r.reference),facts={id:r.id,heightMeters:r.dim.height,architecturalOneToOneCertified:false,physicalAccessVerified:false};const f=after.X.facts(facts,p);assert.equal(facts.roofFrame78,undefined);assert.equal(f.roofFrame78.apexInferred,true);assert.equal(f.roofFrame78.roofSurveyed,false);assert.equal(f.roofFrame78.sourceFootprintRetained,true);assert.equal(f.physicalAccessVerified,false);assert.equal(after.X.facts(facts,{}),facts);assert.equal(after.X.snapshot().viewerOnly,true);
});
