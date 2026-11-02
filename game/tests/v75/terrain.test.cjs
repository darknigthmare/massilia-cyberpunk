'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),crypto=require('node:crypto'),zlib=require('node:zlib');
const {game,owners,data}=require('./terrain-fixture.cjs');
const D=data(),proof=JSON.parse(fs.readFileSync(path.join(game,'data/v75/terrain-source.json')));
const FOOT=require('../../src/v75/terrain-footprint-core.js');
const inRing=(p,r)=>{let inside=false;for(let i=0,j=r.length-1;i<r.length;j=i++){const a=r[i],b=r[j];if((a[1]>p[1])!==(b[1]>p[1])&&p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0])inside=!inside;}return inside;};
const inPolygon=(p,r)=>inRing(p,r[0])&&!r.slice(1).some(x=>inRing(p,x));
test('inferred foundations include a measured interior summit and exclude an open courtyard',()=>{
 const K=D.K,cols=5,heights=new Float32Array(25),mask=new Uint8Array(25).fill(1);heights[12]=12;
 const g=new K.Grid({cols,rows:cols,step:5,x0:0,n0:20},heights,mask,{},{}),outer=[[0,0],[20,0],[20,20],[0,20]],hole=[[4,4],[16,4],[16,16],[4,16]];
 const a=FOOT.accumulate(g,[outer],{min:Infinity,max:-Infinity,n:0,missing:false},inPolygon);assert.equal(a.max,12);assert.equal(a.min,0);assert.equal(a.missing,false);
 const b=FOOT.accumulate(g,[outer,hole],{min:Infinity,max:-Infinity,n:0,missing:false},inPolygon);assert.ok(b.max<3,'the courtyard summit is not a building support');
 const before=heights.slice();mask[0]=0;const c=FOOT.accumulate(g,[outer],{min:Infinity,max:-Infinity,n:0,missing:false},inPolygon);assert.equal(c.missing,true);assert.deepEqual(heights,before);
});
test('foundation extrema include exact diagonal-boundary intersections, beyond source vertices',()=>{
 const g=new D.K.Grid({cols:2,rows:2,step:5,x0:0,n0:5},new Float32Array([0,10,10,0]),new Uint8Array(4).fill(1),{},{});
 const ring=[[.2,4.8],[4.8,.2],[4.6,.2],[.2,4.6]],a=FOOT.accumulate(g,[ring],{min:Infinity,max:-Infinity,n:0,missing:false},inPolygon);
 assert.ok(a.max>9.99);assert.ok(Math.max(...ring.map(p=>g.sample(...p)))<9.3);
});
test('the delivered source-only 5 m grid retains exact datum, bounds and masked missing cell',()=>{
 assert.equal(D.native.step,5);assert.equal(D.native.cols,653);assert.equal(D.native.rows,653);
 assert.deepEqual(Array.from(D.native.boundsL93),Array.from(D.legacy.boundsL93));
 assert.equal(D.pack.sha256,proof.gridSHA256);assert.equal(proof.campaignCells,168);assert.equal(proof.newGeographicCells,0);
 assert.equal(D.native.stats.valid,424059);assert.equal(D.native.stats.noData,2350);
 assert.equal(D.pack.source.method,'strict-bilinear-at-grid-nodes');assert.equal(D.pack.source.receipt.sourceNoDataPolicy,'Preserved -99999; strict four-corner interpolation must reject any missing/NoData contributor. No sea-level filling.');
 assert.ok(proof.sharedNodesVerifiedIdentical>47000);assert.equal(D.native.verticalDatum,'NGF-IGN69');
 for(const n of ['a','b','c'])assert.ok(fs.statSync(path.join(game,'src/v75/terrain-data-'+n+'.js')).size<2*1024*1024);
});
test('every campaign cell emits 5000 real triangles with the same heights as contact and LOS',()=>{
 for(const cell of proof.tiles){let count=0;const b=cell.boundsL93,ce=(b[0]+b[2])/2,cn=(b[1]+b[3])/2;
  const r=D.native.cellTriangles(b,t=>{count++;if(count%127)return;for(const p of t){const e=ce+p[0],n=cn-p[2];assert.ok(Math.abs(p[1]-D.native.sample(e,n))<1e-7);}});
  assert.equal(count,5000,cell.cellId);assert.equal(r.missing,0);
 }
 const c=proof.tiles.find(x=>x.cellId==='V52-MC-11');let before=0;D.legacy.cellTriangles(c.boundsL93,()=>before++);assert.equal(before,200);
});
test('a measured ridge changes actual terrain LOS and contact, without a cosmetic overlay',()=>{
 const g=D.native,old=D.legacy,S=D.S;let evidence=null;
 for(let y=2;y<g.rows-2&&!evidence;y++)for(let x=2;x<g.cols-2&&!evidence;x++){
  const e=g.x0+x*5,n=g.n0-y*5,a=g.sample(e,n),b=old.sample(e,n);
  if(a===null||b===null||a-b<1)continue;
  const origin=[e,(a+b)/2,-n],dir=[0,1,0],hit=S.terrain(g,origin,dir,2);
  if(hit&&hit.kind==='terrain'&&!S.terrain(old,origin,dir,2))evidence={e,n,native:a,legacy:b,hit};
 }
 assert.ok(evidence,'native measured ridge occludes an eye point above the old grid');
 assert.equal(evidence.hit.distance,0);assert.ok(evidence.native>evidence.legacy+1);
});
test('source-only installed grid equals every original prepared tile node and mask when AMP is available',t=>{
 const manifest=process.env.MASSILIA_TERRAIN_NATIVE_MANIFEST||'/workspace/massilia-geodata-generated/terrain-amp-native5m-2022/manifest.json';
 if(!fs.existsSync(manifest))return t.skip('native AMP cache unavailable; delivered grid checks still run');
 const m=JSON.parse(fs.readFileSync(manifest)),by=new Map(m.tiles.map(x=>[x.cellId,x]));let checked=0;
 assert.equal(crypto.createHash('sha256').update(fs.readFileSync(manifest)).digest('hex'),proof.nativeManifestSHA256);
 for(const p of proof.tiles){const tile=by.get(p.nativeCellId),raw=fs.readFileSync(path.resolve(path.dirname(manifest),tile.terrain.path));
  assert.equal(crypto.createHash('sha256').update(raw).digest('hex'),p.tileSHA256);
  const g=D.K.load(JSON.parse(zlib.gunzipSync(raw))),ox=Math.round((g.x0-D.native.x0)/5),oy=Math.round((D.native.n0-g.n0)/5);
  for(let y=0;y<53;y++)for(let x=0;x<53;x++){const a=y*53+x,b=(oy+y)*653+ox+x;assert.equal(D.native.mask[b],g.mask[a]);assert.equal(D.native.heights[b],g.heights[a]);checked++;}
 }
 assert.equal(checked,168*53*53);
});
function runtime(){
 const c={console,Math,Number,Object,Array,Set,Map,JSON,timers:[],zone:{id:'historic'},state:{driving:null},camera:{x:0,z:0,y:1.72,yaw:0,pitch:0},paused:false,announcements:[],calls:[]};c.window=c;c.setTimeout=fn=>c.timers.push(fn);
 c.document={getElementById:n=>n==='soma-v56-terrain'?{textContent:JSON.stringify(owners.legacy)}:n==='boot'?{classList:{add:()=>c.title=true}}:null,querySelector:()=>null};
 c.__SOMA_V52__={open:()=>true};c.__SOMA_TERRAIN75_PARTS__=[JSON.stringify(D.pack)];
 c.__SOMA_TERRAIN56__={ready:true,pack:owners.legacy,grid:D.legacy,validatePack:()=>true,
  v75Preflight:()=>true,
  activeFor:z=>z?.id==='real',ground:()=>20,slope:()=>({e:.1,south:0}),poseCamera:()=>{c.camera.y=21.72;},
  install:async(p,o)=>{c.calls.push({p,o});c.__SOMA_TERRAIN56__.pack=p;c.__SOMA_TERRAIN56__.grid=p===owners.legacy?D.legacy:D.native;}};
 c.announce=s=>c.announcements.push(s);c.blocked=()=>false;c.enterZone=()=>false;c.__SOMA_SIGHT61__={clearCache:()=>c.cleared=true};
 vm.createContext(c);vm.runInContext(fs.readFileSync(path.join(game,'src/v75/terrain-runtime.js'),'utf8'),c);return c;
}
test('the explicit pilot uses the existing persistent terrain owner and refuses a switch in a physical cell',async()=>{
 const c=runtime(),P=c.__SOMA_TERRAIN75__;assert.equal(P.snapshot().selected,'legacy25m');
 assert.equal(await P.select('native5m'),true);assert.equal(c.calls[0].o.persist,true);assert.equal(P.snapshot().active,true);
 assert.equal(P.snapshot().sessionOnly,false);c.zone.id='real';assert.equal(await P.select('legacy25m'),false);assert.equal(c.calls.length,1);
 assert.equal(P.entrySupported(c.zone,0,0),true);c.__SOMA_TERRAIN56__.slope=()=>({e:1.2,south:0});assert.equal(P.entrySupported(c.zone,0,0),false);
 P.changed();assert.equal(c.paused,true);assert.equal(c.title,true);assert.equal(P.snapshot().entryRefused,true);
 c.zone.id='historic';assert.equal(await P.select('legacy25m'),true);assert.equal(c.calls[1].o.persist,true);
});
test('a compatible restored position keeps metric x/z and recomputes camera NGF on the current grid',async()=>{
 const c=runtime();await c.__SOMA_TERRAIN75__.select('native5m');c.zone.id='real';c.camera.x=3;c.camera.z=4;c.camera.y=999;
 c.__SOMA_TERRAIN75__.changed();assert.equal(c.camera.x,3);assert.equal(c.camera.z,4);assert.equal(c.camera.y,21.72);assert.equal(c.__SOMA_TERRAIN75__.snapshot().entryRefused,false);
});
test('an incompatible installed mosaic is refused before the existing terrain cache can be written',async()=>{
 const c=runtime(),before=c.__SOMA_TERRAIN56__.pack;c.__SOMA_TERRAIN56__.v75Preflight=()=>{throw Error('raccord LOD incompatible');};
 assert.equal(await c.__SOMA_TERRAIN75__.select('native5m'),false);assert.equal(c.calls.length,0);assert.equal(c.__SOMA_TERRAIN56__.pack,before);
 assert.match(c.__SOMA_TERRAIN75__.snapshot().message,/Changement refusé.*LOD/);
});
test('the actual public terrain import refuses incompatible LOD before any cache write',async()=>{
 const t=proof.tiles.find(x=>x.cellId==='V52-MC-11'),pack25=JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(game,'data/v69/world/tiles/V52-MC-11.terrain.json.gz'))));
 const c={console,Number,Math,Array,Object,Map,Set,JSON,K:D.K,EXPECTED:D.native.boundsL93,grid:D.legacy,loading:false,
  zone:{id:'historic'},isReal:z=>z?.id==='real',activate:()=>{c.activations++;},activations:0,cacheWrites:0,
  cacheWrite:async()=>{c.cacheWrites++;},pack25,bounds:t.boundsL93,nativePack:D.pack};c.window=c;vm.createContext(c);
 for(const source of [owners.mosaic,owners.validate,owners.install])vm.runInContext(source,c);
 assert.equal(vm.runInContext("v69Attach('V52-MC-11',pack25,bounds).complete",c),true);
 await assert.rejects(vm.runInContext('install(nativePack,{persist:true})',c),/LOD différents/);
 assert.equal(c.cacheWrites,0);assert.equal(c.activations,0);assert.equal(c.loading,false);
 // A compatible import still follows the existing cache/activation owner.
 await vm.runInContext('install(grid.pack,{persist:true})',c);assert.equal(c.cacheWrites,1);assert.equal(c.activations,1);
});
function actualEntry(c){
 c.WORLD={zones:{real:{id:'real',v52CellId:'source-cell',roads:[],static:true,spawn:{x:0,z:0,yaw:0}}}};
 c.isReal=z=>z?.id==='real';c.activeFor=c.__SOMA_TERRAIN56__.activeFor;c.v69GridFor=()=>D.native;
 c.footprintValid=()=>true;c.buildZone=()=>{};c.poseCamera=c.__SOMA_TERRAIN56__.poseCamera;c.lastGround=0;c.refresh=()=>{};
 c.enterZone=(id,via,pose)=>{c.receivedPose=pose;return true;};vm.runInContext('{'+owners.entry+'}',c);
}
test('actual terrain entry rejects an unsupported imported pose and preserves the title after modal close',async()=>{
 const c=runtime();await c.__SOMA_TERRAIN75__.select('native5m');actualEntry(c);
 c.__SOMA_TERRAIN56__.ground=()=>null;assert.equal(c.enterZone('real',null,{x:1,z:2}),false);
 assert.equal(c.__SOMA_TERRAIN75__.snapshot().entryRefused,true);assert.equal(c.paused,true);assert.equal(c.title,true);
 c.paused=false;c.title=false;for(const fn of c.timers)fn();assert.equal(c.paused,true);assert.equal(c.title,true);
 assert.match(c.__SOMA_TERRAIN75__.snapshot().message,/source-cell/);
});
test('actual terrain entry only replaces a rejected legacy position with a checked source-road point',async()=>{
 const c=runtime();await c.__SOMA_TERRAIN75__.select('native5m');actualEntry(c);
 c.WORLD.zones.real.roads=[{x:7,z:9,angle:1}];c.footprintValid=(z,x)=>x!==100;
 assert.equal(c.enterZone('real',null,{x:100,z:100,yaw:.5}),true);
 assert.equal(c.receivedPose.x,7);assert.equal(c.receivedPose.z,9);assert.equal(c.receivedPose.yaw,1);
 assert.equal(c.__SOMA_TERRAIN75__.snapshot().relocations,1);assert.equal(c.__SOMA_TERRAIN75__.snapshot().entryRefused,false);
});
test('a valid entry cancels the queued title suspension from a previous refusal',async()=>{
 const c=runtime();await c.__SOMA_TERRAIN75__.select('native5m');
 c.__SOMA_TERRAIN75__.refused({id:'unsupported'});c.__SOMA_TERRAIN75__.entered();c.paused=false;c.title=false;
 for(const fn of c.timers)fn();assert.equal(c.paused,false);assert.equal(c.title,false);assert.equal(c.__SOMA_TERRAIN75__.snapshot().entryRefused,false);
});
