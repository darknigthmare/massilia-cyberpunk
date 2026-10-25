'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const src=fs.readFileSync(path.join(__dirname,'../../src/v69/building-parts.js'),'utf8');
function fixture(){
  const source='a'.repeat(64),geometry='b'.repeat(64),content='c'.repeat(64),part='d'.repeat(64);
  const mesh={sourcePartIndex:0,ringsL93:[[[100,200],[110,200],[110,210],[100,210]]],
    trianglesL93:[[[100,200],[110,200],[110,210]]],wallsL93:[[[100,200],[110,200]]],areaM2:100};
  const proof={schema:'soma-massilia/building-parts-proof/1',proofSHA256:'e'.repeat(64),parents:{parent:{
    sourceSHA256:source,parentGeometrySHA256:geometry,replaceParent:true,status:'derived-partial',residualAreaM2:100,
    residualByCell:{'V52-MC-33':{contentSHA256:content,meshes:[mesh]},'V52-MC-34':{contentSHA256:content,meshes:[]}}}},
    partParents:{part:{parentId:'parent',parentGeometrySHA256:geometry,geometrySHA256:part,sourceSHA256:source,
      cells:{'V52-MC-33':content}}},ambiguities:[]};
  const root={},context={window:root,document:{getElementById:()=>({textContent:JSON.stringify(proof)})}};
  vm.runInNewContext(src,context);
  const z={v50Record:{v53Validated:true,sourceReceipt:{sha256:source},cellId:'V52-MC-33',contentSHA256:content},
    v50Projector:{toLocal:([e,n])=>[e-100,200-n]}};
  return {api:root.__SOMA_PARTS69__,z,p:{'soma:geometry_sha256':geometry},child:{'soma:geometry_sha256':part},proof};
}
test('partial replacements are gated by source, geometry and exact cell content',()=>{
  const {api,z,p}=fixture();assert.equal(api.residualMeshes(z,p,'parent',0).length,1);
  const original=api.residualMeshes(z,p,'parent',0);z.v50Record.contentSHA256='f'.repeat(64);
  assert.equal(api.residualMeshes(z,p,'parent',0),null);assert.equal(original.length,1);
});
test('a fully covered cell yields an empty replacement instead of reviving the outline',()=>{
  const {api,z,p}=fixture();z.v50Record.cellId='V52-MC-34';assert.equal(api.meshes(z,p,'parent',0).length,0);
});
test('raw polygons and source walls are unchanged by projection and scoped rendering',()=>{
  const {api,z,p}=fixture(),mesh=api.residualMeshes(z,p,'parent',0)[0],before=JSON.stringify(mesh);
  assert.equal(api.geometryMesh(z,p,0),null);
  api.withMesh(z,p,0,mesh,()=>{const local=api.geometryMesh(z,p,0);assert.equal(local.rings[0][2][1],-10);assert.equal(local.v69Derived,true);});
  assert.equal(api.geometryMesh(z,p,0),null);assert.equal(JSON.stringify(mesh),before);
});
test('scope restores after failures and never leaks into a different feature',()=>{
  const {api,z,p}=fixture(),mesh=api.residualMeshes(z,p,'parent',0)[0];
  assert.throws(()=>api.withMesh(z,p,0,mesh,()=>{assert.equal(api.geometryMesh(z,{},0),null);throw Error('test');}));
  assert.equal(api.geometryMesh(z,p,0),null);
});
test('sight and visible rendering use the same validated residual meshes',()=>{
  const {api,z,p}=fixture(),original=[{original:true}];
  assert.equal(api.sourceMeshes(z,p,'parent',original).length,0);
  assert.equal(api.sourceMeshes(z,{},'parent',original),original);
});
test('a partial outline never becomes an invented local roof or invisible vertical obstacle',()=>{
  const {api,z,p}=fixture();
  assert.equal(api.meshes(z,p,'parent',0).length,0);
  assert.equal(api.sourceMeshes(z,p,'parent',[{}]).length,0);
  assert.equal(api.residualMeshes(z,p,'parent',0).length,1);
  assert.equal(api.parentStatus('parent').residualPolicy,'unresolved-footprint-only');
  assert.equal(api.parentStatus('parent').unknownFootprintAreaM2,100);
  assert.equal(api.summary().completeArchitecture,false);
});
test('parts share a datum only when all linked source identities match',()=>{
  const {api,z,child}=fixture();assert.equal(api.anchorId(z,child,'part'),'parent');
  assert.equal(api.anchorId(z,{},'part'),'part');z.v50Record.v53Synthetic=true;
  assert.equal(api.anchorId(z,child,'part'),'part');
});
