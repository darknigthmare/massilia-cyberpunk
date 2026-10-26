/* Verified visual partitioning of building outlines and explicitly associated parts.
 * Raw OSM features remain immutable; unaccounted parent geometry is retained.
 */
(function(root){
  'use strict';
  const node=document.getElementById('soma-v69-building-parts');
  const proof=JSON.parse(node?.textContent||'{}');
  const parents=proof.parents||{}, links=proof.partParents||{};
  let scope=null;
  function parent(z,p,id){
    const r=z?.v50Record,row=parents[id];
    if(!r?.v53Validated||r.v53Synthetic||!row||row.sourceSHA256!==r.sourceReceipt?.sha256||
       row.parentGeometrySHA256!==p['soma:geometry_sha256'])return null;
    const cell=row.residualByCell?.[r.cellId];
    return cell?.contentSHA256===r.contentSHA256?{row,cell}:null;
  }
  function residualMeshes(z,p,id,index){
    const found=parent(z,p,id);
    if(!found||!found.row.replaceParent)return null;
    return found.cell.meshes.filter(mesh=>mesh.sourcePartIndex===index);
  }
  function meshes(z,p,id,index){
    const found=parent(z,p,id);
    if(!found||!found.row.replaceParent)return null;
    // An outline's total height is not a measurement of a local residual.
    // Retain its footprint as unknown data, not an invented vertical volume.
    if(found.row.status==='derived-partial'||found.row.remainingUnresolved)return [];
    return residualMeshes(z,p,id,index);
  }
  function localMesh(z,raw){
    const local=q=>z.v50Projector.toLocal(q);
    return {rings:raw.ringsL93.map(r=>r.map(local)),triangles:raw.trianglesL93.map(t=>t.map(local)),
      walls:raw.wallsL93.map(w=>w.map(local)),area:raw.areaM2,v69Derived:true};
  }
  function geometryMesh(z,p,index){
    return scope&&scope.z===z&&scope.p===p&&scope.index===index?localMesh(z,scope.mesh):null;
  }
  function withMesh(z,p,index,mesh,fn){
    const previous=scope;scope={z,p,index,mesh};
    try{return fn();}finally{scope=previous;}
  }
  function sourceMeshes(z,p,id,original){
    const found=parent(z,p,id);
    if(!found||!found.row.replaceParent)return original;
    return found.row.status==='derived-partial'||found.row.remainingUnresolved?[]:found.cell.meshes;
  }
  function anchorId(z,p,id){
    const r=z?.v50Record,link=links[id];
    if(!r?.v53Validated||r.v53Synthetic||!link||link.sourceSHA256!==r.sourceReceipt?.sha256||
       link.geometrySHA256!==p['soma:geometry_sha256'])return id;
    const row=parents[link.parentId];
    if(!row||row.parentGeometrySHA256!==link.parentGeometrySHA256||!row.replaceParent)return id;
    return link.cells?.[r.cellId]===r.contentSHA256?link.parentId:id;
  }
  function parentStatus(id){
    if(!parents[id])return null;
    const row=JSON.parse(JSON.stringify(parents[id]));
    if(row.status==='derived-partial'||row.remainingUnresolved){
      row.residualPolicy='unresolved-footprint-only';row.geometryComplete=false;
      row.unknownFootprintAreaM2=row.residualAreaM2;
    }
    return row;
  }
  function summary(){return {schema:proof.schema,proofSHA256:proof.proofSHA256,
    parents:Object.keys(parents).length,linkedParts:Object.keys(links).length,
    partialParents:Object.values(parents).filter(p=>p.status==='derived-partial').length,
    unresolvedParents:(proof.ambiguities||[]).length,
    unknownOutlineFootprintAreaM2:Object.values(parents).reduce((sum,p)=>sum+(p.residualAreaM2||0),0),
    residualPolicy:'unresolved-footprint-only',completeArchitecture:false};}
  root.__SOMA_PARTS69__={meshes,residualMeshes,geometryMesh,withMesh,sourceMeshes,anchorId,summary,parentStatus};
})(typeof window!=='undefined'?window:globalThis);
