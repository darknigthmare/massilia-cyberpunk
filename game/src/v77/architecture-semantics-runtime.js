/* The existing Atlas owns selection, filtering and source binding. */
(function(root){
  'use strict';
  let model=null,problem='';
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const meters=value=>Number(value).toFixed(3)+' m';
  function paragraphs(parent){
    if(!model?.compatible(parent))return '<p>Interprétation des champs IGN indisponible pour cette référence ; aucune cote n’est substituée.</p>';
    const description=model.describe(parent.id),row=description.row,f=row.fields;
    const altitude=key=>f[key]===null?'non renseignée':meters(f[key])+' NGF';
    const delta=description.minimumRoofMinusReferenceM;
    return '<div data-architecture77-semantics><p>Sol minimal IGN : '+altitude('altitude_minimale_sol')+' · hauteur IGN (point haut de gouttière − sol bas) : '+meters(f.hauteur)+'.<br>'+
      '<strong>Référence du modèle calculée (sol minimal + hauteur) : '+meters(description.calculatedReferenceNGF)+' NGF.</strong> Cette somme reste la cote utilisée par le modèle et par la liste des 77 conflits.</p>'+
      '<p><strong>Champs altimétriques IGN distincts</strong><br>Altitude minimale toit : '+altitude('altitude_minimale_toit')+'.'+
      (delta===null?'': ' Écart avec la référence calculée : '+(Math.abs(delta)<1e-9?'0,000 m':(delta>0?'+':'')+meters(delta))+'.')+
      '<br>Altitude maximale toit : '+altitude('altitude_maximale_toit')+' · altitude maximale sol : '+altitude('altitude_maximale_sol')+'.</p>'+
      '<p>La cote minimale toit est un attribut calculé : pour le bâti unifié du cadastre, interpolation médiane du bâti voisin ; après amélioration par MNS, selon la zone, 2,5e à 4e décile du MNS. Elle ne désigne pas le faîte. La cote maximale toit représente le faîte par le 9e décile du MNS, hors cheminées ; sa fiabilité est moindre sur les petits bâtiments et constructions légères. Ces statistiques ne donnent ni une forme de toit relevée ni un point de faîtage localisé.</p>'+
      '<p>Origine déclarée : '+esc(row.origin??'non renseignée')+' · méthode altimétrique : '+esc(row.method??'non renseignée')+'. Un champ absent reste inconnu. La valeur zéro de « hauteur » signifie inconnue ou non significative ; zéro NGF reste une altitude valide. La précision déclarée est une propriété de la source, pas une tolérance permettant de déplacer le modèle. L’écart de champs n’établit pas sa cause.</p>'+
      '<p>MNT sous l’emprise : '+meters(parent.nativeFootprintMin)+' à '+meters(parent.nativeFootprintMax)+' NGF · dépassement de la référence calculée : +'+meters(parent.terrainAboveEave)+'. Géométrie, cotes de référence et cohorte inchangées.</p>'+
      '<p>Définitions : <a style="color:#8fffe8" href="'+model.data.provenance.document.url+'" target="_blank" rel="noopener noreferrer">IGN, BD TOPO 3.5, juillet 2026</a>, pages imprimées 68 et 76–78. <small style="overflow-wrap:anywhere">PDF vérifié SHA-256 : '+model.data.provenance.document.sha256+'.</small></p></div>';
  }
  function snapshot(){return {version:'0.77.0',ready:!!model,ephemeral:true,geometryChanged:false,referenceChanged:false,cohortChanged:false,
    rows:model?.data.rows.length||0,minimumRoofAvailable:model?.data.rows.filter(r=>r.fields.altitude_minimale_toit!==null).length||0,
    maximumRoofAvailable:model?.data.rows.filter(r=>r.fields.altitude_maximale_toit!==null).length||0,
    differentMinimumRoof:model?.data.rows.filter(r=>Math.abs(model.describe(r.id).minimumRoofMinusReferenceM??0)>1e-9).length||0,problem};}
  try{model=root.__SOMA_ARCHITECTURE77_CORE__.create(root.__SOMA_ARCHITECTURE77_DATA__);delete root.__SOMA_ARCHITECTURE77_DATA__;}
  catch(error){problem=String(error.message||error);}
  root.__SOMA_ARCHITECTURE77__=Object.freeze({snapshot,describe:id=>model?.describe(id)||null,paragraphs});
})(window);
