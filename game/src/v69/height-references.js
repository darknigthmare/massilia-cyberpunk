/* IGN eaves and ground references bound to immutable source geometry/cells.
 * Matching evidence does not certify surveyed roofs or whole buildings. */
(function(root){
  'use strict';
  const raw=root.document?.getElementById('soma-v69-building-height-matches')?.textContent||'{}';
  const proof=JSON.parse(raw),rows=proof.matches||{},HASH=/^[a-f0-9]{64}$/;
  const FALSE=new Set(['','no','false','0']);
  const nonempty=value=>value!==null&&value!==undefined&&String(value).trim()!=='';
  const active=value=>value!==null&&value!==undefined&&
    (typeof value==='object'||!FALSE.has(String(value).trim().toLowerCase()));
  function zero(value){
    if(value===null||value===undefined||value===''||value===false)return true;
    if(typeof value==='number')return Number.isFinite(value)&&value===0;
    if(typeof value!=='string'||!/^[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[-+]?\d+)?$/i.test(value.trim()))return false;
    return Number(value)===0;
  }
  function priority(p){
    return active(p['building:part'])||String(p.building||'').trim().toLowerCase()==='roof'||nonempty(p.height)||
      !zero(p.layer)||!zero(p.min_height)||!zero(p['building:min_level'])||
      ['underground','underwater','overground'].includes(String(p.location||'').trim().toLowerCase());
  }
  const enabled=proof.schema==='soma-metropole/building-height-matches/1'&&proof.crs==='EPSG:2154'&&proof.units==='m'&&
    proof.verticalDatum==='NGF-IGN69'&&proof.heightKind==='eaves'&&proof.roofSurveyed===false&&
    proof.accuracy==='source-match-not-certified'&&HASH.test(proof.sourceSHA256||'')&&HASH.test(proof.proofSHA256||'')&&
    HASH.test(proof.ignSource?.sha256||'')&&proof.newHeightAcquisition===false&&proof.certifiedBuildings===0&&
    proof.policy?.preserveExplicitOSMHeight===true&&proof.policy?.excludeActiveOSMParts===true&&
    proof.policy?.deriveHeightFromAbsoluteRoofZ===false&&
    [['minimumIoU',.9],['minimumMargin',.15],['minimumReciprocalMargin',.15]].every(([key,min])=>
      Number.isFinite(proof.policy[key])&&proof.policy[key]>=min&&proof.policy[key]<=1);
  const identity=f=>f?.properties?.canonical_id||f?.id;
  const real=(record,sha)=>record?.v53Validated&&!record.v53Synthetic&&!record.v50Synthetic&&!record.testOnly&&record.sourceReceipt?.sha256===sha;

  function roofPolicy(p,reference){
    return reference?.heightKind==='eaves'&&!nonempty(p?.height)?{
      shape:'flat',modelled:false,reason:'eave-height-is-not-a-surveyed-roof',geometrySource:'flat-approximation',
      accuracy:'approximate',roofSurveyed:false,heightKind:'eaves'}:null;
  }

  function reference(p,id,z){
    const record=z?.v50Record;
    if(!enabled||!p||priority(p)||!real(record,proof.sourceSHA256)||
      (p.canonical_id&&p.canonical_id!==id)||!HASH.test(p['soma:geometry_sha256']||''))return null;
    const row=rows[JSON.stringify([record.sourceReceipt.sha256,id,p['soma:geometry_sha256']])];
    if(!row||row.canonicalId!==id||row.sourceSHA256!==proof.sourceSHA256||row.geometrySHA256!==p['soma:geometry_sha256']||
      row.cells?.[record.cellId]!==record.contentSHA256||row.decision!=='accepted-conservative-match'||
      row.heightSource!=='ign-bdtopo-height'||!Number.isFinite(row.height)||row.height<=.05||row.height>1000||
      !Number.isFinite(row.groundAltitude)||row.groundAltitude< -1000||row.groundAltitude>9000||
      !Number.isFinite(row.iou)||row.iou<proof.policy.minimumIoU||row.iou>1||
      !Number.isFinite(row.margin)||row.margin<proof.policy.minimumMargin||row.margin>1||
      !Number.isFinite(row.reciprocalMargin)||row.reciprocalMargin<proof.policy.minimumReciprocalMargin||row.reciprocalMargin>1)return null;
    const records=root.__SOMA_V52__?.records?.();
    if(!records)return null;
    for(const [cell,sha]of Object.entries(row.cells)){
      const candidate=records.get(cell);
      if(!real(candidate,row.sourceSHA256)||!HASH.test(sha)||candidate.contentSHA256!==sha)return null;
      const fragments=candidate.featureCollection?.features?.filter(f=>identity(f)===id);
      if(!fragments?.length||fragments.some(f=>f.properties?.['soma:layer']!=='buildings'||
        f.properties?.['soma:geometry_sha256']!==row.geometrySHA256||priority(f.properties)))return null;
    }
    return {...row,cells:{...row.cells},height:row.height,eaveHeight:row.height,minHeight:0,
      heightKind:'eaves',heightSource:'ign-bdtopo-height',source:'ign-bdtopo',verified:true,
      verificationScope:'source-hash-and-footprint-match-only',accuracy:'source-match-not-certified',
      roofSurveyed:false,roofGeometryPolicy:proof.roofGeometryPolicy,roofApproximation:roofPolicy(p,{heightKind:'eaves'}),
      ignSourceSHA256:proof.ignSource.sha256,proofSHA256:proof.proofSHA256};
  }

  function summary(){return {schema:proof.schema,proofSHA256:proof.proofSHA256,
    parentMatchingProofSHA256:proof.parentMatchingProofSHA256,sourceSHA256:proof.sourceSHA256,
    ignSourceSHA256:proof.ignSource?.sha256,sourceDate:proof.ignSource?.date,
    measuredReferences:enabled?Object.keys(rows).length:0,heightKind:'eaves',accuracy:'source-match-not-certified',
    roofSurveyed:false,certifiedBuildings:0,roofGeometryPolicy:proof.roofGeometryPolicy};}
  root.__SOMA_HEIGHTS69__={reference,roofPolicy,summary};
})(typeof window!=='undefined'?window:globalThis);
