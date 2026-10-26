"""Strict, derived-document gameplay hooks; frozen scripts remain untouched."""
import re

from build_v68 import replace_once, rewrite_script

MARKER = '/* SOMA v70 perception: fixed emissions and last known contact. */'


def _once(text, old, new, label):
    return replace_once(text, old, new, 'v70 gameplay: ' + label)


def _region(text, start, end, transform, label):
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError('Ancre de reconstruction différente : v70 ' + label)
    a, b = text.index(start), text.index(end, text.index(start))
    return text[:a] + transform(text[a:b]) + text[b:]


def patch_v32(script):
    if MARKER in script:
        raise ValueError('Perception v70 déjà appliquée.')

    def enemy(body):
        body = _once(body, 'function v32UpdateEnemies(dt){if(!zone)return;',
                     MARKER + '\nfunction v32UpdateEnemies(dt){if(!zone)return;window.__SOMA_PERCEPTION70__?.beginEnemyFrame(dt);', 'frame IA')
        body = _once(body, "crouched=!state.driving&&(keys.has('ControlLeft')||keys.has('ControlRight'))",
                     "crouched=(window.__SOMA_V42__?.isCrouched?.()??(!state.driving&&(keys.has('ControlLeft')||keys.has('ControlRight'))))", 'posture canonique')
        body = _once(body, "continue;const a=ARCHETYPES[q.v32Role]||ARCHETYPES.rifle,",
                     "continue;const p70=window.__SOMA_PERCEPTION70__?.observer(q.id),target70=p70?.searchTarget,targetX70=target70?.[0]??q.x,targetZ70=target70?.[1]??q.z,dx70=targetX70-q.x,dz70=targetZ70-q.z,dist70=Math.hypot(dx70,dz70)||.01,desired70=target70?Math.atan2(dx70,dz70):(q.heading||0),mayAttack70=!p70||p70.canAttack;const a=ARCHETYPES[q.v32Role]||ARCHETYPES.rifle,", 'observation par unité')
        old = "if(visible||heard){q.detect=clamp((q.detect||0)+dt*(visible?1.4:.8),0,1.2);q.searchClock=5;if(q.detect>=1){q.state='combat';v32RaiseAlarm(visible?'contact visuel':'détonation')}}else{q.detect=Math.max(0,(q.detect||0)-dt*.34);q.searchClock=Math.max(0,(q.searchClock||0)-dt);if(q.state==='combat'&&q.searchClock<=0)q.state='search'}"
        new = "if(p70){if(['patrol','search','combat'].includes(q.state)){q.detect=p70.suspicion;q.searchClock=p70.memoryRemaining;q.state=p70.phase==='combat'?'combat':p70.phase==='unaware'?'patrol':'search';if(p70.phase==='combat')v32RaiseAlarm(p70.lastSense==='visual'?'contact visuel':'contact signalé')}window.__SOMA_PERCEPTION70__.applied(q)}else{" + old + "}"
        body = _once(body, old, new, 'mémoire perceptive')

        def combat(part):
            # Without a known location the movement target is the unit itself.
            # This preserves independent medic healing while attacks stay gated.
            for token, replacement in [('desired', 'desired70'), ('dx', 'dx70'), ('dz', 'dz70'), ('dist', 'dist70')]:
                part = re.sub(r'\b' + token + r'\b', replacement, part)
            # Keep the exact original behavior when the new adapter is absent.
            part = part.replace('desired70', '(p70?desired70:desired)').replace('dx70', '(p70?dx70:dx)').replace('dz70', '(p70?dz70:dz)').replace('dist70', '(p70?dist70:dist)')
            part = part.replace('camera.x,camera.z', '(p70?targetX70:camera.x),(p70?targetZ70:camera.z)')
            part = _once(part, 'else if(q.attackClock<=0){v32DamagePlayer', 'else if(mayAttack70&&q.attackClock<=0){v32DamagePlayer', 'attaque mêlée visible')
            anchor = '&&q.attackClock<=0){'
            # Four ranged attacks, the guarded blade and the independent medic
            # healing branch. Healing must not acquire a player-visibility gate.
            if part.count(anchor) != 6 or part.count(')&&q.attackClock<=0){') != 4:
                raise ValueError('Ancre de reconstruction différente : v70 attaques à distance')
            # The blade branch already carries mayAttack70; adding it again is
            # harmless but would obscure the source transformation.
            part = part.replace(')&&q.attackClock<=0){', ')&&mayAttack70&&q.attackClock<=0){')
            return part
        body = _region(body, "if(q.state==='combat'){", " }else if(q.state==='patrol'||q.state==='search'){", combat, 'mouvement de combat')
        old_patrol = "}else if(q.state==='patrol'||q.state==='search'){const covers=zone.v32CoverPoints||[],p=covers.length?covers[q.patrolIndex%covers.length]:{x:q.homeX,z:q.homeZ};if(Math.hypot(p.x-q.x,p.z-q.z)<.8)q.patrolIndex=(q.patrolIndex+1)%Math.max(1,covers.length);else enemyMove(q,p.x,p.z,a.speed*.45,dt)}"
        new_patrol = "}else if(q.state==='patrol'||q.state==='search'){if(p70?.searchTarget){const p=p70.searchTarget;if(Math.hypot(p[0]-q.x,p[1]-q.z)>.8)enemyMove(q,p[0],p[1],a.speed*.45,dt)}else{const covers=zone.v32CoverPoints||[],p=covers.length?covers[q.patrolIndex%covers.length]:{x:q.homeX,z:q.homeZ};if(Math.hypot(p.x-q.x,p.z-q.z)<.8)q.patrolIndex=(q.patrolIndex+1)%Math.max(1,covers.length);else enemyMove(q,p.x,p.z,a.speed*.45,dt)}}"
        return _once(body, old_patrol, new_patrol, 'recherche du dernier contact')

    script = _region(script, 'function v32DamagePlayer(amount,label,source){', '\nfunction enemyMove(',
                     _patch_scaled_incoming, 'noyau dégâts v32 après défense')
    script = _region(script, 'function v32UpdateEnemies(dt){', '\nlet snapshotClock=0;', enemy, 'fonction ennemis')
    return _once(script, 'S.lastShotAt=performance.now()/1000;',
                 'S.lastShotAt=performance.now()/1000;window.__SOMA_PERCEPTION70__?.recordShot();', 'émission de tir accepté')


def patch_v33(script):
    def cover(body):
        body = _once(body, 'function chooseCover(q,order,reserved){',
                     "function chooseCover(q,order,reserved){const p70=window.__SOMA_PERCEPTION70__?.observer(q.id);if(window.__SOMA_PERCEPTION70__&&!p70?.searchTarget)return null;const target70=p70?{x:p70.searchTarget[0],z:p70.searchTarget[1]}:camera;", 'cible tactique connue')
        # The fallback initializer must keep camera; all actual tactical queries
        # use the observed/memorised position rather than the hidden player.
        return body.replace('camera.x', 'target70.x').replace('camera.z', 'target70.z')
    script = _region(script, 'function chooseCover(q,order,reserved){', '\nfunction assignTactics(){', cover, 'couvert escouade')
    return _once(script, 'if(q.v33Target&&q._v33Old&&!window.__SOMA_BOSSES36__?.handles(q)',
                 'if(q.v33Target&&q._v33Old&&(!window.__SOMA_PERCEPTION70__||window.__SOMA_PERCEPTION70__.observer(q.id)?.searchTarget)&&!window.__SOMA_BOSSES36__?.handles(q)', 'déplacement tactique sans voyance')


def patch_v42(script):
    script = _once(script, 'if(paused||!v42OnFoot()||v42Channel)return false;',
                   'if(paused||!v42OnFoot()||v42Channel||window.__SOMA_V70__?.blocksHacking?.())return false;', 'exclusion canal/augment')
    script = _once(script, 'if(q.v42Detect>.8){for(const g of zone.robots||[])',
                   "if(q.v42Detect>.8){window.__SOMA_PERCEPTION70__?.reportContact(q.id,{x:camera.x,z:camera.z},'camera');for(const g of zone.robots||[])", 'contact caméra réellement observé')
    script = _once(script, 'if(r){v42SanitizeDriving();',
                   'if(r){window.__SOMA_PERCEPTION70__?.reset();v42SanitizeDriving();', 'réinitialisation perception au transfert physique')
    return _once(script, 'isCrouched:v42Crouched,toggleCrouch:',
                 "isCrouched:v42Crouched,isMachine:v42Machine,isChanneling:()=>!!v42Channel,channelStatus:()=>v42Channel?Object.freeze({type:v42Channel.type,program:v42Channel.program,targetId:v42Channel.targetId,elapsed:v42Channel.elapsed,duration:v42Channel.duration}):null,debitEnergy:v42DeckDebit,canUseOnFoot:v42OnFoot,toggleCrouch:", 'API canal v42 réelle')


def patch_v43(script):
    modifier = '(window.__SOMA_V70__?.modifiers?.().recoil??1)'
    script = _once(script, 'recoil*=crouch?.82:ads>.55?.78:1;',
                   'recoil*=(crouch?.82:ads>.55?.78:1)*' + modifier + ';', 'recul visuel focus')
    return _once(script, "kick=Math.min(.013,.0025+(Number(w?.damage)||20)/6500)*(crouch?.82:1)*(ads>.55?.72:1)",
                 "kick=Math.min(.013,.0025+(Number(w?.damage)||20)/6500)*(crouch?.82:1)*(ads>.55?.72:1)*" + modifier, 'angle de recul focus')


def _patch_scaled_incoming(script):
    original = "const before=state.health,incoming=amount*(typeof v27Stats==='function'?clamp(v27Stats().damageTakenMult,.35,1.75):1);let dmg=incoming;"
    replacement = "const before=state.health,unmitigated70=amount*(typeof v27Stats==='function'?clamp(v27Stats().damageTakenMult,.35,1.75):1),incoming=window.__SOMA_V70__?.mitigateIncoming?.(unmitigated70)??unmitigated70;let dmg=incoming;"
    return _once(script, original, replacement, 'impact après garde/défense avant armure')


def patch_legacy_damage(html):
    """Reduce guarded physical impacts before their original armour/health writes.

    These historical owners retain their body callbacks and consequences. Each
    calls the common reducer once; no path is rerouted through another owner.
    Police damage has already passed the original v35 wrapper's guards and stat
    multiplier when its base kernel is reached. Neural/environmental paths are
    deliberately outside these three exact, scoped anchors.
    """
    html = _region(html, 'function v26DamagePlayer(amount,label,source){',
                   '\nfunction v26SpawnBossMinion(', _patch_scaled_incoming, 'noyau dégâts boss26')
    html = _region(html, 'function policeStunPlayer(source,amount=6){',
                   '\nfunction spawnRoadblock(){', lambda s: _once(
                       s, 'source.arrestCooldown=1.5;let dmg=amount;',
                       'source.arrestCooldown=1.5;let dmg=window.__SOMA_V70__?.mitigateIncoming?.(amount)??amount;',
                       'impact policier après cooldown et wrapper corporel'), 'noyau stun police')
    original = "let dmg=7*(typeof v27Stats==='function'?clamp(v27Stats().damageTakenMult,.35,1.75):1);"
    return _region(html, 'function updateAI(dt){', '\nfunction move(dt){', lambda s: _once(
        s, original, original + 'dmg=window.__SOMA_V70__?.mitigateIncoming?.(dmg)??dmg;',
        'impact sentinelle historique après garde et multiplicateur'), 'ancienne IA sentinelle')


def patch_gameplay(html):
    """Patch reconstructed v69 only; fail on missing, duplicated or drifted anchors."""
    html = patch_legacy_damage(html)
    html = _once(html, 'function update(dt){move(dt);',
                 'function update(dt){window.__SOMA_V70__?.tick?.(dt);move(dt);', 'horloge unique des augments')
    for script_id, patch in [('soma-v32-patch', patch_v32), ('soma-v33-patch', patch_v33),
                             ('soma-v42-recovery', patch_v42), ('soma-v43-production', patch_v43)]:
        html = rewrite_script(html, script_id, patch)
    html = rewrite_script(html, 'soma-v62-runtime', lambda s: _once(
        s, 'window.__SOMA_V42__?.state?.().channel', 'window.__SOMA_V42__?.isChanneling?.()', 'verrou sauvegarde parcours'))
    return rewrite_script(html, 'soma-v64-group-runtime', lambda s: _once(
        s, 'api(42)?.state()?.channel', 'api(42)?.isChanneling?.()', 'verrou transfert groupe'))
