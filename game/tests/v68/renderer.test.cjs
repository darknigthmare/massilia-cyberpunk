'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const core = require('../../src/v68/architecture-core.js');
const source = fs.readFileSync(path.join(__dirname, '../../src/v68/building-renderer.js'), 'utf8');

function fixture(tags = {}) {
  const ring = [[0,0],[10,0],[10,10],[0,10]];
  const triangles = [[ring[0],ring[1],ring[2]], [ring[0],ring[2],ring[3]]];
  const walls = ring.map((a,i) => [a,ring[(i+1)%ring.length]]);
  const projector = {toMetric:([x,z]) => [1000+x,2000-z]};
  const properties = {building:'yes', height:'10', 'roof:shape':'skillion', 'roof:height':'4',
    'roof:direction':'90', 'soma:layer':'buildings', canonical_id:'osm/way/1',
    'soma:geometry_sha256':'a'.repeat(64), ...tags};
  properties['soma:mesh53'] = [{ringsL93:[ring.map(projector.toMetric)],
    wallsL93:walls.map(wall=>wall.map(projector.toMetric))}];
  let record = {v53Validated:true, sourceReceipt:{sha256:'b'.repeat(64)},
    featureCollection:{features:[{id:'osm/way/1', properties}]}};
  let indexCalls = 0;
  const root = {__SOMA_ARCH68_CORE__:{...core,referenceIndex(records){indexCalls++;return core.referenceIndex(records);}},
    __SOMA_V52__:{records:()=>new Map([['cell-1',record]])}};
  vm.runInNewContext(source,{window:root});
  const helper = {
    geometryMesh53:()=>({rings:[ring],triangles,walls,area:100}),
    addPolygonCollider(z,rings,tag){const c={rings,tag};z.colliders.push(c);return c;},
    C50:{stableHash:()=>42,buildingHeight:()=>10},C:{mul:(c,n)=>c.map(v=>v*n),
      mix:(a,b,t)=>a.map((v,i)=>v+(b[i]-v)*t)},
    inPolygon:()=>false, heightReference:()=>null,
    dimension:p=>({height:Number(p.height),minHeight:Number(p.min_height||0),valid:true,
      openStructure:p.building==='roof',heightSource:'osm-height',roofShape:p['roof:shape']})
  };
  function draw() {
    const z={v50Record:record,v50Projector:projector,v50Footprints:[],colliders:[]};
    const g={__v56:{kind:'rigid',height:20},triangles:[],quads:[],
      tri(...args){this.triangles.push(args);},quad(...args){this.quads.push(args);}};
    root.__SOMA_ARCH68__.beginCell(z);
    assert.equal(root.__SOMA_ARCH68__.render(z,g,[ring],properties,'osm/way/1',0,0,helper),true);
    return {z,g};
  }
  return {draw,properties,root,projector,triangles,walls,
    calls:()=>indexCalls,replaceRecord(){record={...record};}};
}

test('renderer keeps source triangles and walls, lifts slopes and retains outward roof normals',()=>{
  const f=fixture(), before=JSON.stringify(f.properties),{z,g}=f.draw();
  assert.equal(g.triangles.length,2);
  for(const [a,b,c,n] of g.triangles){
    assert(n[1]>0);
    for(const p of [a,b,c]) assert.equal(p[1],10-.4*p[0]);
  }
  assert.equal(z.colliders.length,1);
  assert.equal(z.v50Footprints[0].height,10);
  assert.equal(z.v68Architecture.slopingRoofs,1);
  assert.equal(JSON.stringify(f.properties),before);
  assert(g.quads.length>=f.walls.length);
  for(const [a,b] of f.walls){
    assert(g.quads.some(q=>[q[0],q[1],q[2],q[3]].some(p=>p[0]===a[0]&&p[2]===a[1]&&p[1]===10-.4*a[0])&&
      [q[0],q[1],q[2],q[3]].some(p=>p[0]===b[0]&&p[2]===b[1]&&p[1]===10-.4*b[0])));
  }
});

test('fresh Map views reuse the canonical index until a source record changes',()=>{
  const f=fixture();f.draw();f.draw();f.draw();assert.equal(f.calls(),1);
  f.replaceRecord();f.draw();assert.equal(f.calls(),2);
  f.root.__SOMA_ARCH68__.invalidate();f.draw();assert.equal(f.calls(),3);
});

test('flat and unknown roofs avoid unnecessary city indexing',()=>{
  const f=fixture({'roof:shape':'flat'});const {z,g}=f.draw();
  assert.equal(f.calls(),0);
  assert(g.triangles.every(t=>t.slice(0,3).every(p=>p[1]===10)));
  assert.equal(z.v68Architecture.unresolvedRoofs,0);
});

test('elevated roof-only parts keep terrain datum and conservative source collision volume',()=>{
  const f=fixture({min_height:'6'}),{z,g}=f.draw();
  assert.equal(z.colliders[0].v60Volume.bottom,26);
  assert.equal(z.colliders[0].v60Volume.top,30);
  assert.equal(z.v50Footprints[0].minHeight,6);
  assert(g.triangles.every(t=>t.slice(0,3).every(p=>p[1]>=6&&p[1]<=10)));
});

test('canopies retain open sides instead of gaining invented facade walls',()=>{
  const f=fixture({building:'roof',min_height:'6'}),{z,g}=f.draw();
  assert.equal(g.quads.length,0);
  assert.equal(z.colliders[0].v60Volume.kind,'canopy');
  assert.equal(z.v50Footprints[0].openStructure,true);
});

test('source colour provenance is counted separately from interpreted material',()=>{
  const f=fixture({'building:colour':'#ccddee','roof:material':'slate'}),{z}=f.draw();
  assert.equal(z.v68Architecture.sourceWalls,1);
  assert.equal(z.v68Architecture.sourceRoofs,1);
  assert.equal(z.v50Footprints[0].v68.wallSource,'osm-building-colour');
});

test('cyberpunk windows reuse facade panels and keep lighting separate from geographic provenance',()=>{
  const {z,g}=fixture().draw();
  assert(z.v68Architecture.litWindows>0);
  assert(z.v68Architecture.neonPanels>0);
  assert(g.quads.some(q=>Math.max(...q[5])>1.25));
  assert.equal(z.v50Footprints[0].v68.lightingSource,'interpreted-cyberpunk-lighting');
  assert.equal(z.v50Footprints[0].geometrySource,'declared-source');
  assert.equal(g.triangles.length,2);
  assert.equal(z.colliders.length,1);
});
