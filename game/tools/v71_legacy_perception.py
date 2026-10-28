"""Derived v71 hooks for the historical AI; v70 and original inputs are read-only."""
from build_v68 import replace_once, rewrite_script

MODULES = ('legacy-perception-runtime',)
MARKER = '/* SOMA v71 legacy perception: observed positions only. */'


def once(text, old, new, label):
    return replace_once(text, old, new, 'v71 legacy perception: ' + label)


def region(text, start, end, transform, label):
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError('Ancre différente : v71 legacy perception ' + label)
    a, b = text.index(start), text.index(end, text.index(start))
    return text[:a] + transform(text[a:b]) + text[b:]


def patch_ai(body):
    body = once(body, 'function updateAI(dt){',
                MARKER + '\nfunction updateAI(dt){window.__SOMA_LEGACY_PERCEPTION71__?.beginFrame(dt);', 'une observation par frame legacy')
    old = "dist=Math.hypot(dx,dz),chasing=!!n.police&&state.police.level>0&&(n.dispatch||Math.hypot(n.x-camera.x,n.z-camera.z)<24);if(chasing){n.targetX=camera.x;n.targetZ=camera.z;"
    new = "dist=Math.hypot(dx,dz),p71n=window.__SOMA_LEGACY_PERCEPTION71__?.observer('actor',n),chasing=!!n.police&&state.police.level>0&&!!p71n?.searchTarget;if(chasing){n.targetX=p71n.searchTarget[0];n.targetZ=p71n.searchTarget[1];"
    body = once(body, old, new, 'cible policière mémorisée')
    body = once(body, 'if(chasing&&dist<9&&!lineBlocked(', 'if(chasing&&p71n.canAttack&&dist<9&&!lineBlocked(', 'stun seulement avec contact confirmé')
    body = once(body, 'if(v.dispatch&&state.police.level>0&&!flying&&!isWaterVehicleKind(v.kind)){const pursuit=nearestRoutePoint(zone.vehicleRoutes,camera.x,camera.z);',
                "const p71v=window.__SOMA_LEGACY_PERCEPTION71__?.observer('vehicle',v);if(v.dispatch&&state.police.level>0&&p71v?.searchTarget&&!flying&&!isWaterVehicleKind(v.kind)){const pursuit=nearestRoutePoint(zone.vehicleRoutes,p71v.searchTarget[0],p71v.searchTarget[1]);", 'véhicule au dernier contact')
    body = once(body, 'if(flying&&v.dispatch&&state.police.level>0){',
                'if(flying&&v.dispatch&&state.police.level>0&&p71v?.searchTarget){', 'vol sans position télépathique')
    body = once(body, 'dx=camera.x-v.x,dz=camera.z-v.z,dist=Math.hypot(dx,dz),desired=Math.atan2(dx,dz)',
                'dx=p71v.searchTarget[0]-v.x,dz=p71v.searchTarget[1]-v.z,dist=Math.hypot(dx,dz),desired=Math.atan2(dx,dz)', 'cap aérien mémorisé')
    body = once(body, 'if(dist<18&&Math.abs((v.y||0)-targetY)<5&&state.police.level>=4',
                'if(p71v.canAttack&&dist<18&&Math.abs((v.y||0)-targetY)<5&&state.police.level>=4', 'pression aérienne avec contact réel')
    old = "if((q.kind==='security'||q.kind==='policeDrone')&&q.health>0){const active=(state.recoveryGrace||0)<=0&&(q.hostile||(q.kind==='policeDrone'&&state.police.level>0)),dist=Math.hypot(q.x-camera.x,q.z-camera.z);if(active){q.heading=Math.atan2(camera.x-q.x,camera.z-q.z);if(q.kind==='policeDrone'&&dist>3){const sp=state.police.level>=4?2.1:1.2,nx=q.x+(camera.x-q.x)/dist*sp*dt,nz=q.z+(camera.z-q.z)/dist*sp*dt;"
    # ICE in the actual v27 digital scene keeps its historical target model;
    # these are neural entities, not physical police/security observers.
    new = "if((q.kind==='security'||q.kind==='policeDrone')&&q.health>0&&!q.v32Enemy&&!q.v26BossId&&!q.v42Camera&&!window.__SOMA_BOSSES36__?.handles?.(q)){const p71r=q.v27ICE&&zone.type==='v27-cyber'?{searchTarget:[camera.x,camera.z],canAttack:true,canMove:true}:window.__SOMA_LEGACY_PERCEPTION71__?.observer('robot',q),active=(state.recoveryGrace||0)<=0&&(q.hostile||(q.kind==='policeDrone'&&state.police.level>0))&&!!p71r?.searchTarget,tx71=p71r?.searchTarget?.[0]??q.x,tz71=p71r?.searchTarget?.[1]??q.z,dist=Math.hypot(q.x-tx71,q.z-tz71);if(active){if(p71r.canMove)q.heading=Math.atan2(tx71-q.x,tz71-q.z);if(q.kind==='policeDrone'&&dist>3&&p71r.canMove){const sp=state.police.level>=4?2.1:1.2,nx=q.x+(tx71-q.x)/dist*sp*dt,nz=q.z+(tz71-q.z)/dist*sp*dt;"
    body = once(body, old, new, 'robots legacy hors propriétaires tactiques/boss')
    return once(body, 'if(dist<25&&!lineBlocked(q.x,q.z,camera.x,camera.z)&&q.phase%1.4<dt){',
                'if(p71r.canAttack&&dist<25&&!lineBlocked(q.x,q.z,camera.x,camera.z)&&q.phase%1.4<dt){', 'arme legacy sous perception et quickhacks')


def patch_dispatch(body):
    anchor = 'targetX:camera.x,targetZ:camera.z'
    if body.count(anchor) != 2:
        raise ValueError('Ancre différente : v71 legacy police spawn')
    return body.replace(anchor, 'targetX:p.x,targetZ:p.z')


def patch_html(html, scripts):
    """Apply once to reconstructed v70; caller supplies verified module text."""
    if MARKER in html or 'id="soma-v71-legacy-perception-runtime"' in html:
        raise ValueError('Perception legacy v71 déjà appliquée.')
    html = region(html, 'function updateAI(dt){', '\nfunction move(dt){', patch_ai, 'IA historique')
    html = region(html, 'function ensurePoliceResponse(force=false){', '\nfunction updatePolice(dt){', patch_dispatch, 'dispatch sans cible inventée')
    html = once(html, "n=>n.police&&Math.hypot(n.x-camera.x,n.z-camera.z)<4&&!lineBlocked(n.x,n.z,camera.x,camera.z)",
                "n=>n.police&&window.__SOMA_LEGACY_PERCEPTION71__?.observer('actor',n)?.canTrackCurrent&&Math.hypot(n.x-camera.x,n.z-camera.z)<4&&!lineBlocked(n.x,n.z,camera.x,camera.z)", 'interpellation volontaire réellement vue')
    html = rewrite_script(html, 'soma-v70-perception-runtime', lambda s: once(once(s,
        "pending.push({id:'v70-sound:'+ ++serial,kind,position:position.slice(),radiusM,strength,duration});",
        "pending.push({id:'v70-sound:'+ ++serial,kind,position:position.slice(),radiusM,strength,duration});root.__SOMA_LEGACY_PERCEPTION71__?.reportNoise?.(pending[pending.length-1]);", 'sons réels partagés'),
        'snapshotHUD,snapshot,reset:()=>{reset();activeZone=zoneNow();}',
        'snapshotHUD,snapshot,reset:()=>{reset();activeZone=zoneNow();root.__SOMA_LEGACY_PERCEPTION71__?.reset?.();}', 'reset public lié aux transferts et imports'))
    text = scripts['legacy-perception-runtime']
    if not isinstance(text, str) or '</script' in text.lower():
        raise ValueError('Module legacy v71 invalide.')
    return once(html, '</body>', '\n<script id="soma-v71-legacy-perception-runtime">\n' + text + '\n</script>\n</body>', 'module legacy après son noyau70')
