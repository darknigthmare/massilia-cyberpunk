"""Extend the frozen campaign saver for the optional v67 world-state domain.

Only the reconstructed v68 document is patched. The original v66 baseline and
v67 sources keep their release checksums, and older campaigns remain valid.
"""

_ENTRY = "function validateCore37(core,edition){\n"
_GUARD = "  const version=key.match(/^(?:v|player|campaign)(\\d+)/);\n"
_MARKER = "/* SOMA 0.68: optional, validated v67 campaign extension. */"

_VALIDATOR = r"""/* SOMA 0.68: optional, validated v67 campaign extension. */
function validateWorld67(value){
 const path='Personnage.v67';
 const plain=(v,p)=>{
  if(!v||typeof v!=='object'||Array.isArray(v))fail(p,'objet simple attendu');
  const proto=Object.getPrototypeOf(v);
  if(proto!==null&&proto!==Object.prototype)fail(p,'objet simple attendu');
  return v;
 };
 const safeId=id=>typeof id==='string'&&id.length>0&&id.length<=200&&!forbidden.has(id)&&!/[\u0000-\u001f<>]/.test(id);
 plain(value,path);
 const fields=new Set(['schema','districtVisits','conversations','ambientSeen','lastDistrict']);
 knownKeys(value,fields,path);
 for(const field of fields)if(!Object.hasOwn(value,field))fail(path+'.'+field,'données manquantes');
 if(value.schema!=='soma-v67/1')fail(path+'.schema','version inconnue');
 for(const field of ['districtVisits','conversations','ambientSeen']){
  const counters=plain(value[field],path+'.'+field);
  if(Object.keys(counters).length>20000)fail(path+'.'+field,'trop de compteurs');
  for(const [id,n]of Object.entries(counters)){
   if(!safeId(id))fail(path+'.'+field,'identifiant invalide');
   number(n,0,1000000000,path+'.'+field+'.'+id,true);
  }
 }
 if(value.lastDistrict!==null&&!safeId(value.lastDistrict))fail(path+'.lastDistrict','identifiant invalide');
}
"""


def patch_persistence(script: str) -> str:
    """Return a saver with one explicit v67 extension; refuse source drift.

    Missing v67 data is accepted, as in historical campaigns. No data is
    migrated, removed or mutated: the existing saver already copies and reloads
    additional validated domains. Unknown future versioned domains keep the
    original rejection path.
    """
    if not isinstance(script, str):
        raise TypeError("Le script de continuité doit être une chaîne.")
    if _MARKER in script or "function validateWorld67(" in script:
        raise ValueError("La compatibilité de continuité v68 est déjà appliquée.")
    for label, anchor in (("validateur de campagne", _ENTRY), ("garde de version", _GUARD)):
        if script.count(anchor) != 1:
            raise ValueError(f"Continuité v37 inattendue : ancre {label} non unique.")
    updated = script.replace(_ENTRY, _VALIDATOR + _ENTRY, 1)
    return updated.replace(
        _GUARD,
        "  if(key==='v67'&&edition===37){validateWorld67(core.v67);continue;}\n" + _GUARD,
        1,
    )
