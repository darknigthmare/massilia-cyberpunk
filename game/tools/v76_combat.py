"""Explicit heavy counterplay over unchanged v75 damage and warning owners."""
from build_v68 import replace_once, rewrite_script

MODULES = ('combat-heavy-runtime',)
MARKER = '/* SOMA v76 combat: paid, interruptible heavy preparation. */'


def once(text, old, new, label):
    return replace_once(text, old, new, 'v76 combat: ' + label)


def patch_v32(body):
    body = once(body, "else{const ideal=q.v32Role==='heavy'?11:q.v32Role==='drone'?13:16;if((p70?dist70:dist)>ideal+4)",
                "else{const preparing76=window.__SOMA_COMBAT76__?.isPreparing(q),ideal=q.v32Role==='heavy'?11:q.v32Role==='drone'?13:16;if(!preparing76&&(p70?dist70:dist)>ideal+4)", 'tenir la position pendant la salve')
    body = once(body, "else if((p70?dist70:dist)<ideal-4)", "else if(!preparing76&&(p70?dist70:dist)<ideal-4)", 'ne pas reculer pendant la salve')
    old = "if((p70?dist70:dist)<=a.range&&!lineBlocked(q.x,q.z,(p70?targetX70:camera.x),(p70?targetZ70:camera.z))&&mayAttack70&&q.attackClock<=0){v32DamagePlayer(a.damage*(q.v33AttackFactor??1),q.v32Role==='heavy'?'Salve lourde':'Tir hostile',q);q.attackClock=a.cooldown/Math.max(.1,q.v33AttackFactor??1)}"
    new = "if(window.__SOMA_COMBAT76__?.handles(q)){if(window.__SOMA_COMBAT76__.advance(q,a,dt,mayAttack70)){v32DamagePlayer(a.damage*(q.v33AttackFactor??1),'Salve lourde',q);q.attackClock=a.cooldown/Math.max(.1,q.v33AttackFactor??1)}}else{" + old + "}"
    body = once(body, old, new, 'seule préparation ; dégâts et récupération32 conservés')
    body = once(body, 'window.__SOMA_COMBAT75__?.beginEnemyFrame();', 'window.__SOMA_COMBAT75__?.beginEnemyFrame();window.__SOMA_COMBAT76__?.beginEnemyFrame();', 'annuler avant les branches32')
    body = once(body, 'window.__SOMA_COMBAT75__?.restoreRecovery(q,rec);', 'window.__SOMA_COMBAT75__?.restoreRecovery(q,rec);window.__SOMA_COMBAT76__?.restoreRecovery(q,rec);', 'restaurer recharge32')
    return once(body, 'v34BaseArmor:q.v34BaseArmor,...(window.__SOMA_COMBAT75__?.handles(q)?',
                'v34BaseArmor:q.v34BaseArmor,...(window.__SOMA_COMBAT76__?.handles(q)?{attackClock:window.__SOMA_COMBAT76__.recoveryForSave(q)}:{}),...(window.__SOMA_COMBAT75__?.handles(q)?', 'scalaire32 existant')


def patch_v33(body):
    body = once(body, 'if(window.__SOMA_COMBAT75__?.isPreparing(q)){q.vx=0;q.vz=0;}else followTarget(q,dt)',
                'if(window.__SOMA_COMBAT75__?.isPreparing(q)||window.__SOMA_COMBAT76__?.isPreparing(q)){q.vx=0;q.vz=0;}else followTarget(q,dt)', 'tenir visée75 et76 ; reprendre le chemin33')
    return once(body, '  return out;\n}',
                '  if(window.__SOMA_COMBAT76__?.handles(q))out.attackClock=window.__SOMA_COMBAT76__.recoveryForSave(q);\n  return out;\n}', 'recharge du roster33')


def patch_html(html, scripts):
    if MARKER in html or 'id="soma-v76-combat-heavy-runtime"' in html:
        raise ValueError('Combat v76 déjà appliqué.')
    source = scripts.get('combat-heavy-runtime')
    if not isinstance(source, str) or not source.strip() or '</script' in source.lower():
        raise ValueError('Module combat v76 invalide.')
    html = once(html, 'Réduit temporairement la précision des unités de sécurité proches.',
                'Masque votre présence visuelle aux robots proches pendant 10 secondes ; ils peuvent encore chercher aux bruits et aux derniers contacts.', 'description de la brume réellement appliquée')
    html = rewrite_script(html, 'soma-v32-patch', patch_v32)
    html = rewrite_script(html, 'soma-v33-patch', patch_v33)
    html = rewrite_script(html, 'soma-v72-netrunner-runtime', lambda body: once(body,
        "return [...neural,...(root.__SOMA_COMBAT75__?.visibleTelegraphs?.()||[])].slice(0,4);",
        "return [...neural,...(root.__SOMA_COMBAT75__?.visibleTelegraphs?.()||[]),...(root.__SOMA_COMBAT76__?.visibleTelegraphs?.()||[])].slice(0,4);", 'quatre lignes partagées72'))
    html = rewrite_script(html, 'soma-v73-tactical-runtime', lambda body: once(body,
        'const role=root.__SOMA_COMBAT75__?.describe(q)||', 'const role=root.__SOMA_COMBAT76__?.describe(q)||root.__SOMA_COMBAT75__?.describe(q)||', 'Écho lit la salve réelle'))
    html = once(html, 'function loop(t){window.__SOMA_COMBAT75__?.maintain();',
                'function loop(t){window.__SOMA_COMBAT76__?.maintain();window.__SOMA_COMBAT75__?.maintain();', 'pause et onglet masqué')
    html = rewrite_script(html, 'soma-v70-perception-runtime', lambda body: once(body,
        'root.__SOMA_COMBAT75__?.reset?.();', 'root.__SOMA_COMBAT75__?.reset?.();root.__SOMA_COMBAT76__?.reset?.();', 'vrai import et transfert'))
    html = rewrite_script(html, 'soma-v70-perception-runtime', lambda body: once(body,
        '  function visual(q,a,posture){', '  function visual(q,a,posture){\n    if(root.__SOMA_COMBAT76__?.isObscured(q))return\'blocked\';', 'brume28 masque la vue personnelle70'))
    html = rewrite_script(html, 'soma-v71-legacy-perception-runtime', lambda body: once(body,
        "    if(!available)return 'unknown';", "    if(!available)return 'unknown';\n    if(kind==='robot'&&root.__SOMA_COMBAT76__?.isObscured(q))return 'blocked';", 'brume28 masque les seuls robots71 concernés'))
    html = rewrite_script(html, 'soma-v45-city', lambda body: once(body,
        'window.__SOMA_COMBAT75__?.restoreRecovery(q,saved);', 'window.__SOMA_COMBAT75__?.restoreRecovery(q,saved);window.__SOMA_COMBAT76__?.restoreRecovery(q,saved);', 'rencontres45'))
    return once(html, '</body>', '\n<script id="soma-v76-combat-heavy-runtime">\n' + MARKER + '\n' + source + '\n</script>\n</body>', 'adaptateur après75')


def patch_viewer(html, scripts):
    return html
