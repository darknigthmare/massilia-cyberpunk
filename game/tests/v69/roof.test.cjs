'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const Core=require('../../src/v69/roof-core.js');
const close=(a,b,epsilon=1e-6)=>assert.ok(Math.abs(a-b)<=epsilon,`${a} != ${b}`);
const projector={toMetric:([x,z])=>[891000+x,6246000-z],toLocal:([e,n])=>[e-891000,6246000-n]};
const ID='osm/way/1';

function reference(localRing) {
  const ring=localRing.map(point=>projector.toMetric(point));
  const p={canonical_id:ID,'soma:geometry_sha256':'test-source-geometry','soma:layer':'buildings',
    'soma:mesh53':[{ringsL93:[ring],wallsL93:ring.map((point,i)=>[point,ring[(i+1)%ring.length]])}]};
  return [...Core.referenceIndex([{sourceReceipt:{sha256:'test-pbf'},featureCollection:{features:[{id:ID,properties:p}]}}]).values()][0];
}
const square=[[-5,-5],[5,-5],[5,5],[-5,5]];
const squareTriangles=[[square[0],square[1],square[2]],[square[0],square[2],square[3]]];
const properties={'roof:shape':'pyramidal',height:'20','roof:height':'5'};
const dimensions={height:20,minHeight:0,valid:true};
const area=triangle=>Math.abs((triangle[1][0]-triangle[0][0])*(triangle[2][2]-triangle[0][2])-(triangle[2][0]-triangle[0][0])*(triangle[1][2]-triangle[0][2]))/2;

test('pyramids retain sourced dimensions and label inferred apex/profile explicitly',()=>{
  const ref=reference(square),snapshot=JSON.stringify(ref),plan=Core.roofPlan(properties,dimensions,ref);
  assert.equal(plan.modelled,true);assert.equal(plan.geometrySource,'osm-parametric');assert.equal(plan.accuracy,'inferred');
  assert.equal(plan.parameterSources.apex,'inferred-centroid');assert.equal(plan.parameterSources.height,'osm-height');
  close(plan.eave,15);close(plan.heightAt(...projector.toMetric([0,0])),20);
  for(const point of square)close(plan.heightAt(...projector.toMetric(point)),15);
  assert.equal(JSON.stringify(ref),snapshot);
});

test('pyramid roof clipping adds the real apex and preserves the entire source footprint',()=>{
  const plan=Core.roofPlan(properties,dimensions,reference(square));
  const triangles=Core.roofTriangles(squareTriangles,plan,projector);
  close(triangles.reduce((sum,t)=>sum+area(t),0),100);
  assert.ok(triangles.flat().some(([x,y,z])=>Math.abs(x)<1e-6&&Math.abs(z)<1e-6&&Math.abs(y-20)<1e-6));
  assert.ok(triangles.flat().every(([x,y,z])=>x>=-5-1e-6&&x<=5+1e-6&&z>=-5-1e-6&&z<=5+1e-6&&y>=15&&y<=20));
});

test('canonical pyramids match across cell fragments without changing source triangles',()=>{
  const plan=Core.roofPlan(properties,dimensions,reference(square));
  const left=[[[-5,-5],[0,-5],[0,5]],[[-5,-5],[0,5],[-5,5]]];
  const right=[[[0,-5],[5,-5],[5,5]],[[0,-5],[5,5],[0,5]]];
  const before=JSON.stringify([left,right]);
  const a=Core.roofTriangles(left,plan,projector),b=Core.roofTriangles(right,plan,projector);
  close([...a,...b].reduce((sum,t)=>sum+area(t),0),100);
  for(const point of [...a.flat(),...b.flat()].filter(([x])=>Math.abs(x)<1e-6))close(point[1],plan.heightAt(...projector.toMetric([point[0],point[2]])));
  assert.equal(JSON.stringify([left,right]),before);
});

test('pyramid wall segments retain the source wall and end at the declared eave',()=>{
  const plan=Core.roofPlan(properties,dimensions,reference(square));
  const wall=Core.wallSegments(square[0],square[1],plan,projector);
  assert.equal(wall.length,1);assert.deepEqual(wall[0].a,square[0]);assert.deepEqual(wall[0].b,square[1]);
  close(wall[0].topA,15);close(wall[0].topB,15);
});

function circle(points=16,rx=5,ry=5){return Array.from({length:points},(_,i)=>[rx*Math.cos(i*2*Math.PI/points),ry*Math.sin(i*2*Math.PI/points)]);}

test('quasi-circular source domes are parameterised with a bounded model tessellation error',()=>{
  const ring=circle(),ref=reference(ring),plan=Core.roofPlan({...properties,'roof:shape':'dome'},dimensions,ref);
  assert.equal(plan.modelled,true);assert.equal(plan.accuracy,'inferred');assert.equal(plan.parameterSources.apex,'inferred-circle-fit');
  close(plan.heightAt(...projector.toMetric([0,0])),20);close(plan.eave,15);
  assert.ok(plan.errorBoundM<=0.05);assert.ok(plan.lodBands.length>1);
  for(const p of ring)close(plan.heightAt(...projector.toMetric(p)),15);
  for(const band of plan.lodBands){
    for(let i=0;i<=100;i++){
      const t=band.from+(band.to-band.from)*i/100;
      const actual=5*Math.sqrt(Math.max(0,1-t*t));
      const a=5*Math.sqrt(Math.max(0,1-band.from*band.from));
      const b=5*Math.sqrt(Math.max(0,1-band.to*band.to));
      const linear=a+(b-a)*(t-band.from)/(band.to-band.from);
      assert.ok(actual-linear<=plan.errorBoundM+1e-7);
    }
  }
});

test('dome clipping preserves the polygonal footprint and its sampled profile error bound',()=>{
  const ring=circle(8),plan=Core.roofPlan({...properties,'roof:shape':'dome'},dimensions,reference(ring));
  const prepared=ring.slice(1,-1).map((point,i)=>[ring[0],point,ring[i+2]]);
  const output=Core.roofTriangles(prepared,plan,projector);
  const target=prepared.reduce((sum,t)=>sum+area(t.map(([x,z])=>[x,0,z])),0);
  close(output.reduce((sum,t)=>sum+area(t),0),target,1e-4);
  assert.ok(output.length<10000);
  for(const t of output){
    const center=[t.reduce((sum,p)=>sum+p[0],0)/3,t.reduce((sum,p)=>sum+p[2],0)/3];
    const linear=t.reduce((sum,p)=>sum+p[1],0)/3;
    assert.ok(plan.heightAt(...projector.toMetric(center))-linear<=0.05+1e-6);
  }
});

test('unsupported, incomplete, concave and holed source shapes remain withheld',()=>{
  const ref=reference(square);
  for(const bad of [{...ref,complete:false},{...ref,hasHoles:true},{...ref,outerCount:2}])assert.equal(Core.roofPlan(properties,dimensions,bad).modelled,false);
  const concave=reference([[0,0],[5,0],[5,5],[2,2],[0,5]]);
  assert.equal(Core.roofPlan(properties,dimensions,concave).reason,'complete-convex-footprint-required');
  const elliptical=Core.roofPlan({...properties,'roof:shape':'dome'},dimensions,reference(circle(16,5,3)));
  assert.equal(elliptical.reason,'dome-footprint-not-circular');
  assert.equal(Core.roofPlan({...properties,'roof:shape':'gabled'},dimensions,ref).modelled,false);
  assert.equal(Core.roofPlan({...properties,height:undefined},dimensions,ref).reason,'explicit-total-height-required');
  assert.equal(Core.roofPlan({...properties,'roof:height':'21'},dimensions,ref).reason,'invalid-or-missing-roof-height');
});

test('roof-only pyramid parts and explicit imperial units preserve total height',()=>{
  const plan=Core.roofPlan({...properties,height:'40 ft','roof:height':'10 ft'},
    {height:12.192,minHeight:9.144,valid:true},reference(square));
  assert.equal(plan.modelled,true);close(plan.eave,9.144);close(plan.apexHeight,12.192);
});

test('skillion and flat plans still use the established core68 pipeline',()=>{
  const flat=Core.roofPlan({'roof:shape':'flat'},dimensions,reference(square));
  assert.equal(flat.reason,'osm-flat');
  const triangles=Core.roofTriangles(squareTriangles,flat,projector);
  assert.equal(triangles.length,2);assert.ok(triangles.flat().every(p=>p[1]===20));
  const skillion=Core.roofPlan({...properties,'roof:shape':'skillion','roof:direction':'90'},dimensions,reference(square));
  assert.equal(skillion.reason,'osm-skillion');
  close(Core.wallSegments(square[0],square[1],skillion,projector)[0].topA,20);
  close(Core.wallSegments(square[0],square[1],skillion,projector)[0].topB,15);
});

test('parametric helpers reject invalid projections and source triangles',()=>{
  const plan=Core.roofPlan(properties,dimensions,reference(square));
  assert.throws(()=>Core.roofTriangles(squareTriangles,plan,{toMetric:p=>p}),TypeError);
  assert.throws(()=>Core.roofTriangles([[[0,0],[1,0],[NaN,1]]],plan,projector),TypeError);
  assert.throws(()=>Core.wallSegments([0,0],[1,0],plan,{}),TypeError);
});
