/* Interpret source fields without changing the geometry or its reference sum. */
(function(root){
  'use strict';
  const VERSION='0.77.0',HASH=/^[a-f0-9]{64}$/;
  const FIELDS=Object.freeze(['hauteur','altitude_minimale_sol','altitude_maximale_sol','altitude_minimale_toit','altitude_maximale_toit']);
  const freeze=value=>{if(value&&typeof value==='object'){for(const x of Object.values(value))freeze(x);Object.freeze(value);}return value;};
  function meaning(key,value){
    if(!FIELDS.includes(key))throw Error('Champ IGN inconnu');
    if(value===null)return 'absent';
    if(!Number.isFinite(value)||value< -1000||value>9000)throw Error('Cote IGN invalide');
    // Zero is a sentinel for hauteur only. Zero NGF is a valid altitude.
    return key==='hauteur'&&value===0?'unknown-or-insignificant':'present';
  }
  function create(source){
    if(source?.schema!=='soma-massilia/architecture-semantics77/1'||source.geometryChanged!==false||source.referenceChanged!==false||
      source.cohortChanged!==false||source.units!=='m'||source.verticalDatum!=='NGF-IGN69'||source.rows?.length!==77)throw Error('Interprétation IGN incompatible');
    const data=JSON.parse(JSON.stringify(source)),byId=new Map();
    for(const key of ['parentCatalogueSHA256','ignSourceSHA256','ignReceiptSHA256'])if(!HASH.test(data.provenance?.[key]||''))throw Error('Provenance IGN absente');
    const doc=data.provenance.document;
    if(doc?.url!=='https://data.geopf.fr/annexes/ressources/documentation/DC_BDTOPO_3-5.pdf'||doc.sha256!=='0542356dcf921bff5263043fe2af288a018d61d8e0f4d750005142f09cdb7331'||doc.version!=='3.5')throw Error('Définition IGN incompatible');
    for(const row of data.rows){
      if(!/^osm\/(way|relation)\/\d+$/.test(row.id)||byId.has(row.id)||!/^BATIMENT\d+$/.test(row.ignId)||!HASH.test(row.geometrySHA256)||
        !row.fields||Object.keys(row.fields).length!==FIELDS.length||FIELDS.some(key=>!Object.hasOwn(row.fields,key)))throw Error('Liaison IGN invalide');
      for(const key of FIELDS)meaning(key,row.fields[key]);
      if(row.fields.hauteur===null||row.fields.altitude_minimale_sol===null||row.fields.hauteur<=0||
        ![row.origin,row.method].every(v=>v===null||typeof v==='string')||
        !(row.precisionM===null||Number.isFinite(row.precisionM)&&row.precisionM>=0))throw Error('Référence IGN invalide');
      byId.set(row.id,row);
    }
    freeze(data);
    function describe(id){
      const row=byId.get(id);if(!row)return null;
      const f=row.fields,sum=f.altitude_minimale_sol+f.hauteur;
      return Object.freeze({row,calculatedReferenceNGF:sum,minimumRoofMinusReferenceM:f.altitude_minimale_toit===null?null:f.altitude_minimale_toit-sum,
        maximumRoofAvailable:f.altitude_maximale_toit!==null,geometryChanged:false,referenceChanged:false});
    }
    function compatible(parent){
      const row=byId.get(parent?.id);return !!row&&row.ignId===parent.ignId&&row.geometrySHA256===parent.geometrySHA256&&
        row.fields.hauteur===parent.eaveHeight&&row.fields.altitude_minimale_sol===parent.groundAltitude&&
        Math.abs(parent.absoluteEaveNGF-row.fields.hauteur-row.fields.altitude_minimale_sol)<1e-9;
    }
    return Object.freeze({data,describe,compatible});
  }
  const API=Object.freeze({VERSION,FIELDS,meaning,create});root.__SOMA_ARCHITECTURE77_CORE__=API;
  if(typeof module!=='undefined'&&module.exports)module.exports=API;
})(typeof globalThis!=='undefined'?globalThis:this);
