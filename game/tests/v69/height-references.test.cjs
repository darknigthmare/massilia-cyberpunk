'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const game=path.resolve(__dirname,'../..');
const source=fs.readFileSync(path.join(game,'src/v69/height-references.js'),'utf8');
const frozen=fs.readFileSync(path.join(game,'baseline/v66.html'),'utf8');
const dimensions=frozen.match(/<script\b[^>]*id="soma-v59-core"[^>]*>([\s\S]*?)<\/script>/)[1];
const architecture=fs.readFileSync(path.join(game,'src/v68/architecture-core.js'),'utf8');
const roofs=fs.readFileSync(path.join(game,'src/v69/roof-core.js'),'utf8');
const SHA='a'.repeat(64),GEOM='b'.repeat(64),CELL='c'.repeat(64),SECOND='d'.repeat(64),id='osm/way/1';
const clone=v=>JSON.parse(JSON.stringify(v));

function fixture(){
  const p={canonical_id:id,building:'yes','soma:layer':'buildings','soma:geometry_sha256':GEOM};
  const record=(cell,sha)=>({cellId:cell,contentSHA256:sha,v53Validated:true,sourceReceipt:{sha256:SHA},
    featureCollection:{type:'FeatureCollection',features:[{type:'Feature',id,properties:clone(p)}]}});
  const records=new Map([['V52-MC-33',record('V52-MC-33',CELL)],['V52-MC-34',record('V52-MC-34',SECOND)]]);
  const row={canonicalId:id,sourceSHA256:SHA,geometrySHA256:GEOM,cells:{'V52-MC-33':CELL,'V52-MC-34':SECOND},
    height:12.5,groundAltitude:8.2,iou:.99,margin:.9,reciprocalMargin:.8,ignId:'IGN-QA-1',
    decision:'accepted-conservative-match',heightSource:'ign-bdtopo-height'};
  const proof={schema:'soma-metropole/building-height-matches/1',sourceSHA256:SHA,proofSHA256:'e'.repeat(64),
    parentMatchingProofSHA256:'f'.repeat(64),crs:'EPSG:2154',units:'m',verticalDatum:'NGF-IGN69',
    heightKind:'eaves',accuracy:'source-match-not-certified',roofSurveyed:false,newHeightAcquisition:false,certifiedBuildings:0,
    roofGeometryPolicy:'flat-approximation-without-explicit-osm-total-height',
    ignSource:{sha256:'9'.repeat(64),date:'2026-06-15'},
    policy:{preserveExplicitOSMHeight:true,excludeActiveOSMParts:true,deriveHeightFromAbsoluteRoofZ:false,
      minimumIoU:.9,minimumMargin:.15,minimumReciprocalMargin:.15},
    matches:{[JSON.stringify([SHA,id,GEOM])]:row}};
  return {proof,records};
}

function run(f=fixture()){
  const context=vm.createContext({document:{getElementById:()=>({textContent:JSON.stringify(f.proof)})},
    __SOMA_V52__:{records:()=>f.records}});
  context.window=context;vm.runInContext(source,context,{filename:'actual-height-references69.js'});
  const z={v50Record:f.records.get('V52-MC-33')},p=z.v50Record.featureCollection.features[0].properties;
  return {...f,H:context.__SOMA_HEIGHTS69__,context,z,p};
}

test('eave and ground references preserve bindings and explicit non-certification without changing raw records',()=>{
  const f=fixture(),before=JSON.stringify([...f.records]),h=run(f),ref=h.H.reference(h.p,id,h.z);
  assert.equal(ref.height,12.5);assert.equal(ref.eaveHeight,12.5);assert.equal(ref.groundAltitude,8.2);
  assert.equal(ref.heightKind,'eaves');assert.equal(ref.accuracy,'source-match-not-certified');assert.equal(ref.roofSurveyed,false);
  assert.equal(ref.verificationScope,'source-hash-and-footprint-match-only');assert.equal(ref.roofApproximation.modelled,false);
  assert.equal(h.H.summary().measuredReferences,1);assert.equal(JSON.stringify([...f.records]),before);
  ref.height=999;ref.cells['V52-MC-33']='0'.repeat(64);
  assert.equal(h.H.reference(h.p,id,h.z).height,12.5);assert.equal(h.H.reference(h.p,id,h.z).cells['V52-MC-33'],CELL);
});

test('every source cell, geometry, hash and canonical identity is required',()=>{
  const changes=[
    h=>h.z.v50Record.sourceReceipt.sha256='0'.repeat(64),
    h=>h.p['soma:geometry_sha256']='0'.repeat(64),
    h=>h.p.canonical_id='osm/way/2',
    h=>h.z.v50Record.contentSHA256='0'.repeat(64),
    h=>h.z.v50Record.v53Synthetic=true,
    h=>h.z.v50Record.v53Validated=false,
    h=>h.records.delete('V52-MC-34'),
    h=>h.records.get('V52-MC-34').contentSHA256='0'.repeat(64),
    h=>h.records.get('V52-MC-34').featureCollection.features[0].properties['soma:geometry_sha256']='0'.repeat(64),
    h=>h.records.get('V52-MC-34').featureCollection.features[0].properties.height='malformed'
  ];
  for(const change of changes){const h=run();change(h);assert.equal(h.H.reference(h.p,id,h.z),null);}
});

test('nonempty OSM heights, active parts, elevated bases and non-ground structures remain prioritary',()=>{
  const tags=[...['12','malformed','0',0,false].map(height=>({height})),{'building:part':'yes'},
    {building:'roof'},{layer:'1'},{layer:'bad'},{layer:'  '},{layer:'0x0'},{min_height:'2'},
    {min_height:'unknown'},{'building:min_level':'1'},{location:'underground'}];
  for(const properties of tags){const h=run();Object.assign(h.p,properties);assert.equal(h.H.reference(h.p,id,h.z),null,JSON.stringify(properties));}
  for(const part of ['no','false','0',false,0]){const h=run();h.p['building:part']=part;assert(h.H.reference(h.p,id,h.z));}
});

test('unknown units, weak matching policy and low evidence are refused',()=>{
  for(const change of [f=>f.proof.verticalDatum='ELLIPSOID',f=>f.proof.heightKind='ridge',
    f=>f.proof.roofSurveyed=true,f=>f.proof.policy.minimumIoU=.1,
    f=>Object.values(f.proof.matches)[0].iou=.89,f=>Object.values(f.proof.matches)[0].groundAltitude=NaN]){
    const f=fixture();change(f);const h=run(f);assert.equal(h.H.reference(h.p,id,h.z),null);
  }
});

test('actual dimensions use relative eaves and never turn absolute ground into building height or a parametric roof',()=>{
  const h=run(),ref=h.H.reference(h.p,id,h.z);
  vm.runInContext(dimensions,h.context);vm.runInContext(architecture,h.context);vm.runInContext(roofs,h.context);
  const dim=h.context.__SOMA_FIDELITY59_CORE__.dimension(h.p,50,ref);
  assert.equal(dim.height,12.5);assert.equal(dim.groundAltitude,8.2);assert.equal(dim.heightSource,'ign-bdtopo-height');
  for(const shape of ['skillion','dome','pyramidal']){
    const p={...h.p,'roof:shape':shape,'roof:height':'3','roof:direction':'90'};
    const plan=h.context.__SOMA_ARCH68_CORE__.roofPlan(p,dim,null);
    assert.equal(plan.shape,'flat');assert.equal(plan.modelled,false);assert.equal(plan.heightAt(0,0),12.5);
    assert.equal(h.H.roofPolicy(p,ref).accuracy,'approximate');assert.equal(h.H.roofPolicy(p,ref).roofSurveyed,false);
  }
  assert.equal(h.H.roofPolicy({...h.p,'roof:shape':'flat'},ref).modelled,false);
});
