'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const K=require('../../src/v69/roof-core.js');
const close=(a,b,eps=1e-6)=>assert(Math.abs(a-b)<=eps,`${a} != ${b}`);
const P={toMetric:([x,z])=>[892951.6480966414+x,6247274.566415883-z],toLocal:([e,n])=>[e-892951.6480966414,6247274.566415883-n]};
const rectangle=[[-10,-5],[10,-5],[10,5],[-10,5]],hole=[[-2,-2],[-2,2],[2,2],[2,-2]];
const triangles=ring=>[[ring[0],ring[1],ring[2]],[ring[0],ring[2],ring[3]]];
const footprintArea=t=>Math.abs((t[1][0]-t[0][0])*(t[2][2]-t[0][2])-(t[2][0]-t[0][0])*(t[1][2]-t[0][2]))/2;
const p={height:'20','roof:height':'5','roof:shape':'gabled'},dim={height:20,minHeight:0,valid:true};

function reference(rings=[rectangle]){
  const metric=rings.map(r=>r.map(P.toMetric)),properties={canonical_id:'osm/way/42','soma:layer':'buildings','soma:geometry_sha256':'source-sha',
    'soma:mesh53':[{ringsL93:metric,wallsL93:metric.flatMap(r=>r.map((a,i)=>[a,r[(i+1)%r.length]]))}]};
  return [...K.referenceIndex([{sourceReceipt:{sha256:'source-pbf'},featureCollection:{features:[{id:'osm/way/42',properties}]}}]).values()][0];
}

function assertAffineRoof(output,plan,area){
  close(output.reduce((sum,t)=>sum+footprintArea(t),0),area,1e-5);
  for(const triangle of output){
    const center=[triangle.reduce((s,q)=>s+q[0],0)/3,triangle.reduce((s,q)=>s+q[2],0)/3];
    close(triangle.reduce((s,q)=>s+q[1],0)/3,plan.heightAt(...P.toMetric(center)),1e-6);
    assert(triangle.every(q=>q[1]>=15-1e-7&&q[1]<=20+1e-7));
  }
}

test('gabled roofs retain explicit source heights and disclose the centered inferred ridge',()=>{
  const ref=reference(),before=JSON.stringify([ref,p,dim]),plan=K.roofPlan(p,dim,ref);
  assert.equal(plan.modelled,true);assert.equal(plan.geometrySource,'osm-parametric');assert.equal(plan.accuracy,'inferred');assert.equal(plan.roofSurveyed,false);
  assert.equal(plan.parameterSources.ridgeDirection,'inferred-long-footprint-axis');
  close(plan.heightAt(...P.toMetric([0,0])),20);close(plan.heightAt(...P.toMetric([10,0])),20);close(plan.heightAt(...P.toMetric([0,5])),15);
  close(plan.heightAt(...P.toMetric([0,2.5])),17.5);assertAffineRoof(K.roofTriangles(triangles(rectangle),plan,P),plan,200);
  assert.equal(JSON.stringify([ref,p,dim]),before);
});

test('source across orientation and OSM downslope direction rotate the ridge rather than its footprint',()=>{
  const across=K.roofPlan({...p,'roof:orientation':'across'},dim,reference());
  assert.equal(across.modelled,true);assert.equal(across.parameterSources.ridgeDirection,'osm-roof-orientation');
  close(across.heightAt(...P.toMetric([0,5])),20);close(across.heightAt(...P.toMetric([10,0])),15);
  assertAffineRoof(K.roofTriangles(triangles(rectangle),across,P),across,200);
  const direction=K.roofPlan({...p,'roof:direction':'E'},dim,reference());
  close(direction.heightAt(...P.toMetric([0,5])),20);assert.equal(direction.parameterSources.ridgeDirection,'osm-roof-direction-perpendicular');
});

test('hipped source rectangles receive four exact planes with explicitly inferred equal pitch',()=>{
  const plan=K.roofPlan({...p,'roof:shape':'hipped'},dim,reference());
  assert.equal(plan.modelled,true);assert.equal(plan.parameterSources.profile,'inferred-equal-pitch-four-plane');
  close(plan.heightAt(...P.toMetric([-5,0])),20);close(plan.heightAt(...P.toMetric([5,0])),20);
  for(const point of rectangle)close(plan.heightAt(...P.toMetric(point)),15);
  close(plan.heightAt(...P.toMetric([7.5,0])),17.5);close(plan.heightAt(...P.toMetric([0,2.5])),17.5);
  const result=K.roofTriangles(triangles(rectangle),plan,P);assertAffineRoof(result,plan,200);
  for(const ridge of plan.ridgeL93)assert(result.flat().some(q=>Math.hypot(...P.toMetric([q[0],q[2]]).map((v,i)=>v-ridge[i]))<1e-6&&Math.abs(q[1]-20)<1e-6));
});

test('pitched roofs preserve real courtyard holes by lifting only source triangles',()=>{
  const prepared=[...triangles([[-10,-5],[10,-5],[10,-2],[-10,-2]]),...triangles([[-10,2],[10,2],[10,5],[-10,5]]),
    ...triangles([[-10,-2],[-2,-2],[-2,2],[-10,2]]),...triangles([[2,-2],[10,-2],[10,2],[2,2]])];
  const ref=reference([rectangle,hole]);assert.equal(ref.complete,true);assert.equal(ref.hasHoles,true);
  for(const shape of ['gabled','hipped']){
    const plan=K.roofPlan({...p,'roof:shape':shape},dim,ref);assert.equal(plan.modelled,true);
    const snapshot=JSON.stringify(prepared),out=K.roofTriangles(prepared,plan,P);assertAffineRoof(out,plan,184);
    for(const triangle of out){const x=triangle.reduce((s,q)=>s+q[0],0)/3,z=triangle.reduce((s,q)=>s+q[2],0)/3;assert(!(Math.abs(x)<2-1e-7&&Math.abs(z)<2-1e-7));}
    assert.equal(JSON.stringify(prepared),snapshot);
  }
});

test('source gable walls split at the actual model ridge without adding or moving their endpoints',()=>{
  const plan=K.roofPlan(p,dim,reference()),a=[10,-5],b=[10,5],segments=K.wallSegments(a,b,plan,P);
  assert.equal(segments.length,2);assert.deepEqual(segments[0].a,a);assert.deepEqual(segments[1].b,b);
  close(segments[0].topA,15);close(segments[0].topB,20);close(segments[1].topA,20);close(segments[1].topB,15);
  close(segments.reduce((s,w)=>s+Math.hypot(w.b[0]-w.a[0],w.b[1]-w.a[1]),0),10);
  const reversed=K.wallSegments(b,a,plan,P);assert.deepEqual(reversed[0].a,b);assert.deepEqual(reversed[1].b,a);
  assert(segments.every(w=>w.derivedSplit));
  const hip=K.roofPlan({...p,'roof:shape':'hipped'},dim,reference()),inner=K.wallSegments([-9,-3],[9,-3],hip,P);
  assert.equal(inner.length,3);
  for(const w of inner){const middle=w.a.map((x,i)=>(x+w.b[i])/2);close((w.topA+w.topB)/2,hip.heightAt(...P.toMetric(middle)));}
});

test('rotated footprints and canonical neighbouring fragments keep one continuous source-wide roof',()=>{
  const angle=37*Math.PI/180,rotated=rectangle.map(([x,z])=>[x*Math.cos(angle)-z*Math.sin(angle),x*Math.sin(angle)+z*Math.cos(angle)]);
  const plan=K.roofPlan(p,dim,reference([rotated]));assert.equal(plan.modelled,true);assertAffineRoof(K.roofTriangles(triangles(rotated),plan,P),plan,200);
  const shared=K.roofPlan(p,dim,reference()),left=triangles([[-10,-5],[0,-5],[0,5],[-10,5]]),right=triangles([[0,-5],[10,-5],[10,5],[0,5]]);
  const a=K.roofTriangles(left,shared,P),b=K.roofTriangles(right,shared,P);assertAffineRoof([...a,...b],shared,200);
  const seam=result=>[...new Set(result.flat().filter(q=>Math.abs(q[0])<1e-6).map(q=>q.map(x=>Math.round(x*1e6)/1e6).join(',')))].sort();
  assert.deepEqual(seam(a),seam(b));
});

test('missing, conflicting or unsupported source parameters keep the established flat approximation',()=>{
  for(const [properties,referenceValue] of [[{...p,height:undefined},reference()],[{...p,'roof:height':undefined},reference()],
    [{...p,'roof:height':'30'},reference()],[p,{...reference(),complete:false}],
    [{...p,'roof:orientation':'diagonal'},reference()],[{...p,'roof:orientation':'along','roof:direction':'E'},reference()],
    [{...p,'roof:ridge:direction':'N','roof:direction':'N'},reference()],
    [{...p,'roof:shape':'hipped','roof:orientation':'across'},reference()],
    [p,reference([[[-5,-5],[5,-5],[5,5],[-5,5]]])],
    [p,reference([[[0,0],[10,0],[10,10],[6,6],[0,10]]])]]){
    assert.equal(K.roofPlan(properties,dim,referenceValue).modelled,false);
  }
  const explicitSquare=K.roofPlan({...p,'roof:direction':'N'},dim,reference([[[-5,-5],[5,-5],[5,5],[-5,5]]]));
  assert.equal(explicitSquare.modelled,true);
});

test('roof-only canopy bases derive from explicit OSM total and roof rise without mutating source dimensions',()=>{
  const properties={building:'roof',height:'10','roof:height':'.5','roof:shape':'hipped',wall:'no'};
  const original={height:10,minHeight:9.8,heightSource:'osm-height',accuracy:'source-declared',valid:true,openStructure:true};
  const snapshot=JSON.stringify([properties,original]),adjusted=K.roofDimensions(properties,original);
  close(adjusted.minHeight,9.5);assert.equal(adjusted.openStructure,true);assert.equal(adjusted.valid,true);
  assert.equal(adjusted.minHeightSource,'derived-osm-total-minus-roof-rise');assert.equal(adjusted.minHeightAccuracy,'inferred');assert.equal(adjusted.accuracy,'source-declared');assert.equal(adjusted.roofSurveyed,false);
  assert.equal(K.roofPlan(properties,original,reference()).modelled,false);
  assert.equal(K.roofPlan(properties,adjusted,reference()).modelled,true);
  assert.equal(JSON.stringify([properties,original]),snapshot);
});

test('every declared base, including zero or malformed values, stays prioritary over a derived canopy base',()=>{
  const properties={building:'roof',height:'10','roof:height':'0.5'},original={height:10,minHeight:9.8,heightSource:'osm-height',valid:true};
  for(const key of ['min_height','building:min_level'])for(const value of [0,'0','2',null,'',undefined,'invalid']){
    assert.equal(K.roofDimensions({...properties,[key]:value},original),original);
  }
  for(const change of [{building:'yes'},{height:undefined},{height:'invalid'},{'roof:height':undefined},{'roof:height':'11'},
    {'roof:height':'0'},{'roof:height':'0.01'}])assert.equal(K.roofDimensions({...properties,...change},original),original);
  for(const change of [{heightSource:'ign-bdtopo-height'},{heightSource:'estimated-from-levels'},{heightSource:'procedural-estimate'},
    {height:11},{heightKind:'eaves'}]){const dim={...original,...change};assert.equal(K.roofDimensions(properties,dim),dim);}
  const feet=K.roofDimensions({building:'roof',height:'10 ft','roof:height':'2 ft'},
    {height:3.048,minHeight:2.848,heightSource:'osm-height',valid:true});close(feet.minHeight,2.4384);
});

test('the real Ombrière source outline accepts its shallow hipped canopy while retaining its exact nonrectangular footprint',()=>{
  // Native OSM way200273945 in the published PACA snapshot. These are source
  // Lambert-93 corners; the pitch profile remains an inferred model.
  const metric=[[892753.1697167107,6246864.870952721],[892732.144602373,6246859.245052813],
    [892743.5231954376,6246814.489403855],[892764.6397338406,6246820.051359087]];
  const local=metric.map(P.toLocal),ref=reference([local]),snapshot=JSON.stringify(metric);
  const properties={building:'roof',height:'10','roof:height':'0.5','roof:shape':'hipped',wall:'no'};
  const dimensions=K.roofDimensions(properties,{height:10,minHeight:9.8,heightSource:'osm-height',valid:true,openStructure:true});
  const plan=K.roofPlan(properties,dimensions,ref),out=K.roofTriangles(triangles(local),plan,P);
  assert.equal(plan.modelled,true);assert.equal(plan.shape,'hipped');assert.equal(plan.accuracy,'inferred');
  assert.equal(dimensions.openStructure,true);close(dimensions.minHeight,9.5);assert.equal(properties.wall,'no');
  assert(plan.frame.rectangleAreaError>0&&plan.frame.rectangleAreaError<.01);
  close(out.reduce((sum,t)=>sum+footprintArea(t),0),1007.6189271117983,1e-5);
  assert(out.every(t=>t.every(q=>q[1]>=9.5-1e-7&&q[1]<=10+1e-7)));
  assert.equal(JSON.stringify(metric),snapshot);
});
