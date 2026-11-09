"""Make the existing metric55 handoff roll back before releasing its lock."""
from build_v68 import replace_once, rewrite_script

MODULES = ('world-transaction-runtime',)
MARKER = '/* SOMA v78 world: metric55 failure restores the original physical scene. */'


def once(text, old, new, label):
    return replace_once(text, old, new, 'v78 monde : ' + label)


def patch_handoff(body):
    if MARKER in body:
        raise ValueError('Transaction monde v78 déjà appliquée.')
    old = "const driving=state.driving,fromVehicles=from.vehicles,oldLast=state.lastOnFoot?{...state.lastOnFoot}:null;transitioning=true;\n if(car){from.vehicles=from.vehicles.filter(v=>v!==car);state.driving=null;}remember(from);\n try{"
    new = "const driving=state.driving,fromVehicles=from.vehicles,oldLast=state.lastOnFoot?{...state.lastOnFoot}:null;\n " + MARKER + "\n const transaction78=window.__SOMA_WORLD78__.capture({from,to,car,stats,memory,layer:v52().state(),state,camera,body:document.body});transitioning=true;\n try{\n  if(car){from.vehicles=from.vehicles.filter(v=>v!==car);state.driving=null;}remember(from);"
    body = once(body, old, new, 'inclure retrait et snapshot source dans try/finally')
    body = once(body, 'v52().save();window.__SOMA_V45__?.registerVehicle(car);',
                'v52().save();transaction78.registrationAttempted=true;window.__SOMA_V45__?.registerVehicle(car);',
                'borner la compensation aux inscriptions effectivement tentées')
    old = "}catch(e){zone=from;state.zone=from.id;from.vehicles=fromVehicles;state.driving=driving;Object.assign(camera,pose);state.lastOnFoot=oldLast;window.__SOMA_V54__.refreshScene();stats.lastFailure=String(e.message||e);return false;}"
    new = """}catch(e){
  zone=from;state.zone=from.id;from.vehicles=fromVehicles;state.driving=driving;Object.assign(camera,pose);state.lastOnFoot=oldLast;
  window.__SOMA_WORLD78__.restore(transaction78);stats.lastFailure=String(e.message||e);
  // Only the existing owners may compensate an already-written observation.
  // Durable I/O failure can still prevent persistence; physical rollback stands.
  window.__SOMA_WORLD78__.compensateFleet(transaction78);
  saveStats();try{v52().save();}catch{}try{save();}catch{}
  try{window.__SOMA_V54__.refreshScene();}catch{}
  window.__SOMA_WORLD78__.restoreBody(transaction78);return false;
 }"""
    return once(body, old, new, 'restaurer identité, coordonnées, appartenances et mémoire')


def patch_html(html, scripts):
    if MARKER in html or 'id="soma-v78-world-transaction-runtime"' in html:
        raise ValueError('Monde v78 déjà appliqué.')
    source = scripts.get(MODULES[0])
    if not isinstance(source, str) or not source.strip() or '</script' in source.lower():
        raise ValueError('Module monde v78 invalide.')
    html = rewrite_script(html, 'soma-v55-runtime', patch_handoff)
    return once(html, '</body>', '\n<script id="soma-v78-world-transaction-runtime">\n' + source + '\n</script>\n</body>',
                'helper local après les propriétaires natifs')


def patch_viewer(html, scripts):
    return html
