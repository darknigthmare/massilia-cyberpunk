/* Read-only, bounded source-conflict catalogue. It owns no world or save data. */
(function(root){
  'use strict';
  const VERSION='0.76.0',PAGE_SIZE=10,HASH=/^[a-f0-9]{64}$/;
  const freeze=value=>{if(value&&typeof value==='object'){for(const x of Object.values(value))freeze(x);Object.freeze(value);}return value;};
  function create(source){
    if(source?.schema!=='soma-massilia/architecture-conflicts76/1'||source.crs!=='EPSG:2154'||source.units!=='m'||source.verticalDatum!=='NGF-IGN69'||
      source.geometryChanged!==false||source.certified!==false||source.pilot!==true||source.thresholdM!==0||source.fragments!==77||source.uniqueObjects!==77||source.over3cm!==76||source.rows?.length!==77)throw Error('Catalogue de conflits incompatible');
    const data=JSON.parse(JSON.stringify(source)),seen=new Set(),byId=new Map();
    for(const key of ['parentAuditSHA256','gridSHA256','nativeManifestSHA256','heightProofSHA256','ignSourceSHA256','ignReceiptSHA256','osmSourceSHA256'])if(!HASH.test(data.provenance?.[key]||''))throw Error('Provenance de conflit absente');
    for(const r of data.rows){
      if(!/^osm\/(way|relation)\/\d+$/.test(r.id)||seen.has(r.id)||!/^V52-MC-[A-Z0-9-]+$/.test(r.cellId)||!/^BATIMENT\d+$/.test(r.ignId)||
        !HASH.test(r.geometrySHA256)||r.sourceSHA256!==data.provenance.osmSourceSHA256||!r.cells||!HASH.test(r.cells[r.cellId]||'')||
        Object.values(r.cells).some(v=>!HASH.test(v))||!['groundAltitude','eaveHeight','absoluteEaveNGF','nativeFootprintMin','nativeFootprintMax','terrainAboveEave'].every(k=>Number.isFinite(r[k]))||
        r.eaveHeight<=.05||r.eaveHeight>1000||r.terrainAboveEave<=0||r.nativeFootprintMin>r.nativeFootprintMax||
        Math.abs(r.absoluteEaveNGF-r.groundAltitude-r.eaveHeight)>1e-9||Math.abs(r.nativeFootprintMax-r.absoluteEaveNGF-r.terrainAboveEave)>1e-9||
        !Array.isArray(r.witnessL93)||r.witnessL93.length!==2||!r.witnessL93.every(Number.isFinite))throw Error('Référence de conflit invalide');
      seen.add(r.id);byId.set(r.id,r);
    }
    if(data.rows.filter(r=>r.terrainAboveEave>.03).length!==76||new Set(data.rows.map(r=>r.cellId)).size!==data.cells)throw Error('Comptage de conflits incohérent');
    freeze(data);
    function list({query='',cellId=null,over3cm=false,page=0}={}){
      const needle=String(query).trim().toLowerCase().slice(0,80);
      const rows=data.rows.filter(r=>(!cellId||r.cellId===cellId)&&(!over3cm||r.terrainAboveEave>.03)&&(!needle||[r.id,r.ignId,r.cellId].some(v=>v.toLowerCase().includes(needle))));
      const pages=Math.max(1,Math.ceil(rows.length/PAGE_SIZE)),current=Math.min(pages-1,Math.max(0,Math.floor(Number(page)||0)));
      return {total:rows.length,pages,page:current,rows:rows.slice(current*PAGE_SIZE,(current+1)*PAGE_SIZE)};
    }
    function bound(id,records,heightOwner){
      const row=byId.get(id);if(!row||!records?.get||typeof heightOwner?.reference!=='function')return false;
      const record=records.get(row.cellId);if(!record||record.contentSHA256!==row.cells[row.cellId])return false;
      const feature=record.featureCollection?.features?.find(f=>(f.properties?.canonical_id||f.id)===id);
      if(!feature)return false;
      const ref=heightOwner.reference(feature.properties,id,{v50Record:record});
      return !!ref&&ref.ignId===row.ignId&&ref.geometrySHA256===row.geometrySHA256&&ref.sourceSHA256===row.sourceSHA256&&
        ref.proofSHA256===data.provenance.heightProofSHA256&&ref.ignSourceSHA256===data.provenance.ignSourceSHA256&&ref.groundAltitude===row.groundAltitude&&ref.height===row.eaveHeight;
    }
    return Object.freeze({data,list,bound,get:id=>byId.get(id)||null});
  }
  const API=Object.freeze({VERSION,PAGE_SIZE,create});root.__SOMA_ARCHITECTURE76_CORE__=API;
  if(typeof module!=='undefined'&&module.exports)module.exports=API;
})(typeof globalThis!=='undefined'?globalThis:this);
