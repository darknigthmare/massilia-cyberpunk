'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const W=require('../../src/v70/world-index.js');
const V69=require('../../src/v69/metropole-viewer.js');
const O=[892951.6480966414,6247274.566415883];
const id=(x,y)=>Math.abs(x)<=2&&Math.abs(y)<=2?`V52-MC-${y+3}${x+3}`:
  `V52-MC-${x<0?'W':'E'}${String(Math.abs(x)).padStart(2,'0')}-${y<0?'N':'S'}${String(Math.abs(y)).padStart(2,'0')}`;
function tile(x,y,extra={}){
  const e=O[0]+x*250,n=O[1]-y*250;
  return{cellId:id(x,y),gridX:x,gridY:y,boundsL93:[e-125,n-125,e+125,n+125],
    contentSHA256:'a'.repeat(64),vector:{source:'QA fixture'},terrain:{complete:true},surfaces:null,navigation:null,...extra};
}
function manifest(tiles){
  return{schema:'soma-metropole/world-manifest/1',crs:'EPSG:2154',units:'m',origin:O.slice(),cellSize:250,
    tiles:tiles||Array.from({length:25},(_,i)=>tile(i%5-2,Math.floor(i/5)-2))};
}
function ring(w,s,e,n){return[[w,s],[e,s],[e,n],[w,n],[w,s]].map(([x,y])=>[O[0]+x,O[1]+y]);}
function commune(code='13055',polygons=[[ring(-1000,-1000,1000,1000)]],extra={}){
  return{code,name:'QA commune '+code,polygons,anchorL93:[O[0]+100,O[1]+100],anchorSource:'qa-source',...extra};
}

test('metric cell lookups preserve aliases, hemisphere signs and historical Math.round boundaries',()=>{
  const m=manifest(),index=W.createWorldIndex(m);
  assert.deepEqual(W.gridForId('V52-MC-41'),{x:-2,y:1});
  assert.deepEqual(W.gridForId('V52-MC-W123-N040'),{x:-123,y:-40});
  assert.equal(W.gridForId('V52-MC-E١٢-S00'),null);
  for(const dx of [-375,-125,0,125,375])for(const dy of [-375,-125,0,125,375]){
    const e=O[0]+dx,n=O[1]+dy,x=Math.round(dx/250),y=Math.round(-dy/250);
    assert.equal(index.cellAt(e,n),m.tiles.find(t=>t.gridX===x&&t.gridY===y)||null);
  }
  assert.equal(index.get('V52-MC-33'),m.tiles[12]);
  assert.equal(index.get('unknown'),null);
});

test('neighbour selection exactly matches the real v69 filter/sort, including distance ties',()=>{
  const m=manifest();m.tiles.reverse();m.tiles[3].terrain=null;
  const index=W.createWorldIndex(m,{instrument:true});
  for(const [e,n]of[[...O],[O[0]+250,O[1]-250],[O[0]-490,O[1]+110]]){
    for(const radius of [0,1,2,3])assert.deepEqual(index.desiredTiles(e,n,radius),V69.desiredTiles(m,e,n,radius));
  }
  const before=index.snapshot().queries.gridLookups;index.desiredTiles(...O);
  assert.equal(index.snapshot().queries.gridLookups-before,9);
  assert.throws(()=>index.desiredTiles(...O,4),/budget/);
});

test('missing cells stay absent and partial/terrain-only metadata never becomes a sampled elevation',()=>{
  const rows=[tile(0,0,{terrain:{complete:false}}),tile(1,0,{terrainOnly:true,vector:null,contentSHA256:null}),
    tile(2,0,{terrain:null})];
  const index=W.createWorldIndex(manifest(rows));
  assert.deepEqual(index.desiredTiles(...O).map(t=>t.cellId),[id(0,0),id(1,0)]);
  assert.equal(index.coverageAt(...O).terrain,'partial');
  const terrain=index.coverageAt(O[0]+250,O[1]);
  assert.equal(terrain.terrainOnly,true);assert.equal(terrain.hasVector,false);
  assert.deepEqual(terrain.flightLayers,['terrain']);assert.equal(terrain.pointTerrainSampled,false);
  const missing=index.coverageAt(O[0]+750,O[1]);assert.equal(missing.tile,null);assert.equal(missing.terrain,'missing');
  assert.equal(missing.pointTerrainSampled,false);assert.equal('height'in missing,false);assert.equal('readyFor3D'in missing,false);
});

test('invalid identities, duplicate positions, foreign origins and shifted geometry fail before indexing',()=>{
  for(const edit of[m=>m.origin[0]++,m=>m.tiles[0].gridX++,m=>m.tiles[0].boundsL93[0]++,
    m=>m.tiles.push({...m.tiles[12],cellId:'V52-MC-E00-S00'}),m=>m.tiles[0].cellId='V52-MC-E١٢-N00',
    m=>Object.assign(m.tiles[0],{terrainOnly:true})]){
    const m=manifest();edit(m);assert.throws(()=>W.createWorldIndex(m));
  }
});

test('non-finite and extreme query coordinates stay bounded and do not generate coverage',()=>{
  const index=W.createWorldIndex(manifest());
  for(const point of[[NaN,0],[Infinity,0],[1e308,1e308],[-1e308,0]]){
    assert.equal(index.cellAt(...point),null);assert.deepEqual(index.desiredTiles(...point),[]);
    assert.equal(index.nearestTile(...point),null);assert.equal(index.communeAt(...point),null);
  }
  assert.deepEqual(W.createWorldIndex(manifest(),{maxRadius:0}).desiredTiles(...O),[manifest().tiles[12]]);
});

test('commune buckets retain holes, islands, overlaps, concavities and source boundary parity',()=>{
  const a=commune('13001',[[ring(-1000,-1000,1000,1000),ring(-100,-100,100,100)],[ring(5000,0,5500,500)]]);
  const b=commune('13002',[[ring(-100,-100,100,100)]]);
  const c=commune('13003',[[ring(1000,-1000,2000,1000)]]);
  const index=W.createWorldIndex(manifest(),{communes:[a,b,c],instrument:true});
  assert.equal(index.communeAt(O[0]+500,O[1]),a);assert.equal(index.communeAt(...O),b);
  assert.equal(index.communeAt(O[0]+5250,O[1]+250),a);assert.equal(index.communeAt(O[0]+1000,O[1]),c);
  assert.equal(index.communeAt(O[0]+3000,O[1]),null);
  const before=index.snapshot().queries.polygonTests;index.communeAt(O[0]+1e5,O[1]+1e5);
  assert.equal(index.snapshot().queries.polygonTests,before);
  const l=commune('13004',[[[[0,0],[1000,0],[1000,200],[200,200],[200,1000],[0,1000],[0,0]].map(([x,y])=>[O[0]+x,O[1]+y])]],{anchorL93:[O[0]+100,O[1]+100]});
  assert.equal(W.createWorldIndex(manifest(),{communes:[l]}).communeAt(O[0]+500,O[1]+500),null);
});

test('WGS84 contours require explicit projection, and source geometry is never modified',()=>{
  const c={code:'13055',name:'QA source',geometry:{type:'Polygon',coordinates:[[[5,43],[5.1,43],[5.1,43.1],[5,43.1],[5,43]]]},anchorWGS84:[5.01,43.01]};
  const input=JSON.stringify(c);assert.throws(()=>W.createWorldIndex(manifest(),{communes:[c]}),/projection/);
  const project=p=>[O[0]+(p[0]-5)*10000,O[1]+(p[1]-43)*10000];
  const index=W.createWorldIndex(manifest(),{communes:[c],projectWGS84:project});
  assert.equal(index.communeAt(...project([5.01,43.01])),c);assert.equal(JSON.stringify(c),input);
  assert.equal(index.destination(c.code).available,true);
});

test('destination anchors are retained when their real flight tile exists',()=>{
  const c=commune('13055',undefined,{anchorL93:[O[0]+51,O[1]+72],anchorSource:'osm-place-node'});
  const index=W.createWorldIndex(manifest(),{communes:[c]});const d=index.destination(c.code);
  assert.deepEqual(d.point,c.anchorL93);assert.equal(d.fallback,false);assert.equal(d.displacementM,0);
  assert.equal(d.anchorSource,'osm-place-node');assert.equal(d.pointTerrainSampled,false);
  assert(Object.isFrozen(d));assert(Object.isFrozen(d.point));assert.equal(index.destination('unknown'),null);
});

test('a missing-anchor cell uses only the nearest existing cell in the same source commune within 2km',()=>{
  const c=commune('13055',[[ring(-50,-50,50,50)],[ring(700,-50,800,50)]],{anchorL93:O.slice()});
  const rows=[tile(1,0),tile(3,0,{terrain:{complete:false}})],m=manifest(rows);
  const d=W.createWorldIndex(m,{communes:[c]}).destination(c.code);
  assert.equal(d.available,true);assert.deepEqual(d.point,[O[0]+750,O[1]]);assert.equal(d.tile,rows[1]);
  assert.equal(d.fallback,true);assert.equal(d.displacementM,750);assert.equal(d.terrain,'partial');
  assert.equal(d.pointTerrainSampled,false);
});

test('fallback distance is strict, deterministic and never crosses a missing contour or terrain',()=>{
  const rows=[tile(3,0),tile(-3,0)],index=W.createWorldIndex(manifest(rows));
  assert.equal(index.nearestTile(...O),rows[0]);
  assert.equal(W.createWorldIndex(manifest([tile(8,0)])).nearestTile(...O,{radiusM:2000}),null);
  const noContour=commune('13055',[],{anchorL93:O.slice()});
  assert.equal(W.createWorldIndex(manifest(rows),{communes:[noContour]}).destination('13055').available,false);
  const noAnchor=commune('13056',undefined,{anchorL93:null});
  assert.equal(W.createWorldIndex(manifest(),{communes:[noAnchor]}).destination('13056').reason,'missing-projected-anchor');
  assert.throws(()=>index.nearestTile(...O,{radiusM:1e9}),/budget/);
});

test('commune input/bucket budgets reject malformed or astronomically large geometry before loops',()=>{
  for(const options of[{communes:[commune(),commune()]},{maxCommuneBucketReferences:1,communes:[commune()]},
    {communes:[commune('13055',[[[[1e308,1e308],[1e308,1e308],[1e308,1e308],[1e308,1e308]]]])]},
    {communes:[commune('13055',[[ring(0,0,100,100).slice(0,-1)]])]}])assert.throws(()=>W.createWorldIndex(manifest(),options));
});

test('index construction and queries do not serialize, clone or mutate the heavy source metadata',()=>{
  const m=manifest(),before=JSON.stringify(m);m.toJSON=()=>{throw Error('Unexpected full manifest serialization');};
  const index=W.createWorldIndex(m);assert.equal(index.cellAt(...O),m.tiles[12]);index.desiredTiles(...O).pop();
  assert.equal(index.desiredTiles(...O).length,9);delete m.toJSON;assert.equal(JSON.stringify(m),before);
});

test('target sets keep tickets for retained cells but revoke exits and later reentries',()=>{
  const index=W.createWorldIndex(manifest()),tracker=W.createTargetTracker(index),a=id(0,0),b=id(1,0),c=id(-1,0);
  const first=tracker.update([a,b]);assert.equal(first.generation,1);
  const ta=tracker.capture(a),tb=tracker.capture(b);assert(tracker.accepts(ta));
  const same=tracker.update([a,b]);assert.equal(same.changed,false);assert.equal(same.generation,1);
  const ordered=tracker.update([b,a]);assert.equal(ordered.changed,false);assert.equal(ordered.orderChanged,true);
  const changed=tracker.update([b,c]);assert.deepEqual(changed.entering,[c]);assert.deepEqual(changed.leaving,[a]);assert.deepEqual(changed.retained,[b]);
  assert(tracker.accepts(tb));assert.equal(tracker.accepts(ta),false);
  tracker.update([a,b]);assert.equal(tracker.accepts(ta),false);assert(tracker.accepts(tracker.capture(a)));
});

test('forced transitions, reset and another tracker/world invalidate opaque old tickets',()=>{
  const index=W.createWorldIndex(manifest()),tracker=W.createTargetTracker(index),other=W.createTargetTracker(index),a=id(0,0);
  tracker.update([a]);const old=tracker.capture(a);other.update([a]);assert.equal(other.accepts(old),false);
  assert.equal(tracker.accepts({...old}),false);
  const forced=tracker.update([a],{force:true});assert.equal(forced.changed,true);assert.equal(tracker.accepts(old),false);
  const current=tracker.capture(a);tracker.reset();assert.equal(tracker.accepts(current),false);
  tracker.update([a]);assert.equal(tracker.accepts(current),false);
});

test('empty target motion avoids cancellation churn and exposed arrays cannot mutate protected state',()=>{
  const index=W.createWorldIndex(manifest()),tracker=W.createTargetTracker(index),a=id(0,0);
  tracker.update([a]);const diff=tracker.update([]);assert.equal(diff.changed,true);
  assert.equal(tracker.update([]).changed,false);assert.equal(tracker.capture(a),null);
  const result=tracker.update([a]);result.ids.length=0;tracker.snapshot().ids.length=0;
  assert.deepEqual(tracker.snapshot().ids,[a]);
  assert.throws(()=>tracker.update([a,a]),/duplicate/);assert.throws(()=>tracker.update(['V52-MC-E99-S99']),/unknown/);
  assert.throws(()=>tracker.update([a],{force:'false'}),/boolean/);
  assert.throws(()=>W.createTargetTracker(index,{maxTargets:257}),/tracker/);
});
