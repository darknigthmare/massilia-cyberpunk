"""Patch only the reconstructed v70 saver for its optional augmentation domain.

The actual pure augmentation core owns the persistence schema. It is injected
before the frozen saver and called directly, avoiding a second validator.
"""

_ENTRY = "function validateCore37(core,edition){\n"
_GUARD = "  const version=key.match(/^(?:v|player|campaign)(\\d+)/);\n"
_APPLY = "  state=normalizeCore37(robustNormalize(clone(p.core)));state.driving=null;state.lastOnFoot=null;"
_MARKER = "/* SOMA 0.70: optional augmentation state; active buffs never persist. */"
_VALIDATE = r"""/* SOMA 0.70: optional augmentation state; active buffs never persist. */
 if(Object.hasOwn(core,'v70')){
  if(edition!==37)fail('Personnage.v70','domaine incompatible avec cette édition');
  const entry=Object.getOwnPropertyDescriptor(core,'v70');
  if(!entry||!Object.hasOwn(entry,'value')||!entry.enumerable)fail('Personnage.v70','donnée simple attendue');
  const augmentations=window.__SOMA_AUG70_CORE__;
  if(typeof augmentations?.validatePersistence!=='function')fail('Personnage.v70','validateur indisponible');
  try{augmentations.validatePersistence(entry.value)}catch(error){fail('Personnage.v70',error.message)}
 }
"""


def patch_persistence(script: str) -> str:
    """Keep old campaigns valid and future domains rejected; refuse patch drift."""
    if not isinstance(script, str):
        raise TypeError("Le script de continuité doit être une chaîne.")
    if _MARKER in script or "restoreCampaign?.(state.v70)" in script:
        raise ValueError("La continuité 0.70 est déjà appliquée.")
    for label, anchor in (("validation", _ENTRY), ("garde de version", _GUARD), ("restauration", _APPLY)):
        if script.count(anchor) != 1:
            raise ValueError(f"Continuité v37 inattendue : ancre {label} non unique.")
    script = script.replace(_ENTRY, _ENTRY + _VALIDATE, 1)
    script = script.replace(_GUARD, "  if(key==='v70'&&edition===37)continue;\n" + _GUARD, 1)
    return script.replace(_APPLY, _APPLY + "\n  window.__SOMA_V70__?.restoreCampaign?.(state.v70);", 1)
