"""Repair the existing grounded controller and local vehicle exits over frozen v73."""
from build_v68 import replace_once, rewrite_script

MODULES = ('mobility-runtime',)
MARKER = '/* SOMA v74 mobility: grounded steps and verified local dismounts. */'


def once(text, old, new, label):
    return replace_once(text, old, new, 'v74 mobilité : ' + label)


def patch_controller(html):
    old = "if(!blocked(zone,nx,camera.z,.38))camera.x=nx;if(!blocked(zone,camera.x,nz,.38))camera.z=nz;state.lastOnFoot={zone:zone.id,x:camera.x,z:camera.z,yaw:camera.yaw};"
    new = "if(window.__SOMA_TERRAIN56__?.activeFor(zone)&&window.__SOMA_MOBILITY74__?.ready){window.__SOMA_MOBILITY74__.walk(sx*speed*dt,sz*speed*dt);}else{if(!blocked(zone,nx,camera.z,.38))camera.x=nx;if(!blocked(zone,camera.x,nz,.38))camera.z=nz;}state.lastOnFoot={zone:zone.id,x:camera.x,z:camera.z,yaw:camera.yaw};"
    html = once(html, old, new, 'déplacement au propriétaire v20')
    html = once(html, 'function safeExitPoint(v){const spec=vehicleSpec(v);',
        "function safeExitPoint(v){if(window.__SOMA_TERRAIN56__?.activeFor(zone)&&!isFlyingVehicleKind(v.kind)&&!isWaterVehicleKind(v.kind))return window.__SOMA_MOBILITY74__?.exitPoint(v)||null;const spec=vehicleSpec(v);",
        'sortie locale au propriétaire véhicule')
    html = once(html, 'const p=safeExitPoint(v);v.speed=0;',
        "const p=safeExitPoint(v);if(!p){v.speed=0;v.pendingExit=false;if(!silent)announce('Sortie impossible ici : déplacez le véhicule vers un accès libre et stable.',3);return false;}v.speed=0;",
        'refus sans effacer la conduite ni sauvegarder une arrivée')
    html = once(html, "document.body.classList.toggle('flying',isFlyingVehicleKind(v.kind));announce(isFlyingVehicleKind(v.kind)?`Pilotage aérien",
        "document.body.classList.toggle('flying',isFlyingVehicleKind(v.kind));window.__SOMA_TERRAIN56__?.poseCamera?.();announce(isFlyingVehicleKind(v.kind)?`Pilotage aérien",
        'altitude NGF à la montée')
    html = once(html, "document.body.classList.remove('driving','flying');if(!silent)announce(isFlyingVehicleKind(v.kind)?'Appareil posé",
        "document.body.classList.remove('driving','flying');window.__SOMA_TERRAIN56__?.poseCamera?.();if(!silent)announce(isFlyingVehicleKind(v.kind)?'Appareil posé",
        'altitude NGF avant la sauvegarde de sortie')
    return html


def patch_terrain(body):
    body = once(body, ' move=function(dt){\n  const from=zone,before=',
        " move=function(dt){\n  if(activeFor(zone)){if(!Number.isFinite(dt)||dt<=0)return;dt=Math.min(dt,.1);}\n  const from=zone,before=",
        'temps borné avant les propriétaires du déplacement')
    body = once(body, 'if(b===null||(a!==null&&distance>1e-7&&Math.abs(b-a)>Math.max(.35,distance*.95)))',
        'if(b===null||(!window.__SOMA_MOBILITY74__?.ready&&a!==null&&distance>1e-7&&Math.abs(b-a)>Math.max(.35,distance*.95)))',
        'garde historique seulement sans contrôleur de sol v74')
    return once(body, 'camera.x=before.x;camera.z=before.z;stats.blockedSlope++;poseCamera();',
        'camera.x=before.x;camera.z=before.z;state.lastOnFoot={zone:zone.id,x:camera.x,z:camera.z,yaw:camera.yaw};stats.blockedSlope++;poseCamera();',
        'position à pied cohérente après refus hérité')


def patch_html(html, scripts):
    if MARKER in html or 'id="soma-v74-mobility-runtime"' in html:
        raise ValueError('Mobilité v74 déjà appliquée.')
    text = scripts.get('mobility-runtime')
    if not isinstance(text, str) or not text.strip() or '</script' in text.lower():
        raise ValueError('Module mobilité v74 invalide.')
    html = patch_controller(html)
    html = rewrite_script(html, 'soma-v56-terrain-runtime', patch_terrain)
    return once(html, '</body>', '\n<script id="soma-v74-mobility-runtime">\n' + MARKER + '\n' + text + '\n</script>\n</body>', 'adaptateur après les propriétaires')


def patch_viewer(html, scripts):
    return html
