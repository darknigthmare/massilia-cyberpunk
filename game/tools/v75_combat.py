"""Sniper counterplay over the unchanged v74 combat and shared warning owners."""
from build_v68 import replace_once, rewrite_script

MODULES = ('combat-telegraph-runtime',)
MARKER = '/* SOMA v75 combat: paid, interruptible sniper preparation. */'


def once(text, old, new, label):
    return replace_once(text, old, new, 'v75 combat: ' + label)


def patch_v32(body):
    old = "if((p70?dist70:dist)<=a.range&&!lineBlocked(q.x,q.z,(p70?targetX70:camera.x),(p70?targetZ70:camera.z))&&mayAttack70&&q.attackClock<=0){q.charge=(q.charge||0)+dt;if(q.charge>1.05){v32DamagePlayer(a.damage*(q.v33AttackFactor??1),'Tir de précision',q);q.attackClock=a.cooldown/Math.max(.1,q.v33AttackFactor??1);q.charge=0}}"
    new = "if(window.__SOMA_COMBAT75__?.handles(q)){if(window.__SOMA_COMBAT75__.advance(q,a,dt,mayAttack70)){v32DamagePlayer(a.damage*(q.v33AttackFactor??1),'Tir de précision',q);q.attackClock=a.cooldown/Math.max(.1,q.v33AttackFactor??1)}}else{" + old + "}"
    body = once(body, old, new, 'préparation seule, dégâts et recharge v32 conservés')
    body = once(body, 'window.__SOMA_COMBAT_SUPPORT74__?.beginEnemyFrame();',
                'window.__SOMA_COMBAT_SUPPORT74__?.beginEnemyFrame();window.__SOMA_COMBAT75__?.beginEnemyFrame();', 'annulation avant les branches v32')
    body = once(body, 'window.__SOMA_COMBAT_SUPPORT74__?.restoreRecovery(q,rec);',
                'window.__SOMA_COMBAT_SUPPORT74__?.restoreRecovery(q,rec);window.__SOMA_COMBAT75__?.restoreRecovery(q,rec);', 'restauration recharge32')
    return once(body, 'v34BaseArmor:q.v34BaseArmor,...(window.__SOMA_COMBAT_SUPPORT74__?.handles(q)?',
                'v34BaseArmor:q.v34BaseArmor,...(window.__SOMA_COMBAT75__?.handles(q)?{attackClock:window.__SOMA_COMBAT75__.recoveryForSave(q)}:{}),...(window.__SOMA_COMBAT_SUPPORT74__?.handles(q)?', 'scalaire recharge32 existant')


def patch_v33(body):
    body = once(body, 'q.x=q._v33Old.x;q.z=q._v33Old.z;followTarget(q,dt)',
                'q.x=q._v33Old.x;q.z=q._v33Old.z;if(window.__SOMA_COMBAT75__?.isPreparing(q)){q.vx=0;q.vz=0;}else followTarget(q,dt)',
                'tenir la visée pendant le seul canal sniper ; reprise du chemin hors canal')
    return once(body, '  return out;\n}',
                '  if(window.__SOMA_COMBAT75__?.handles(q))out.attackClock=window.__SOMA_COMBAT75__.recoveryForSave(q);\n  return out;\n}', 'recharge payée dans le roster33')


def patch_warning(body):
    body = once(body, 'return [...channels].filter(([q])=>playerSees(q)).slice(0,4).map(([q,row])=>({',
                'const neural=[...channels].filter(([q])=>playerSees(q)).slice(0,4).map(([q,row])=>({', 'lignes neurales existantes')
    body = once(body, 'remainingSeconds:Math.max(0,CONFIG.chargeSeconds-row.elapsed)}));',
                'remainingSeconds:Math.max(0,CONFIG.chargeSeconds-row.elapsed)}));\n    return [...neural,...(root.__SOMA_COMBAT75__?.visibleTelegraphs?.()||[])].slice(0,4);', 'quatre lignes partagées maximum')
    body = once(body, "hint:telegraphs.length?'Touchez le tisseur ou coupez la ligne de vue.':'',",
                "hint:[...new Set(telegraphs.map(row=>row.hint||'Touchez le tisseur ou coupez la ligne de vue.'))].join(' '),", 'conseil selon les préparations réelles')
    body = once(body, '[row.label,Math.floor(row.progress*20)]', '[row.title||\'neural\',row.label,Math.floor(row.progress*20)]', 'actualisation du type de menace')
    body = once(body, "title.textContent='INTRUSION EN PRÉPARATION · '+Math.floor(row.progress*100)+' %';",
                "title.textContent=(row.title||'INTRUSION EN PRÉPARATION')+' · '+Math.floor(row.progress*100)+' %';", 'titre spécifique dans le panneau conservé')
    body = once(body, "meter.setAttribute('aria-label','Préparation de l’intrusion neurale');",
                "meter.setAttribute('aria-label',row.meterLabel||'Préparation de l’intrusion neurale');", 'nom accessible spécifique')
    return once(body, "hint.textContent='Touchez le tisseur ou coupez la ligne de vue.';",
                "hint.textContent=[...new Set(rows.map(row=>row.hint||'Touchez le tisseur ou coupez la ligne de vue.'))].join(' ');", 'conseil visible spécifique')


def patch_html(html, scripts):
    if MARKER in html or 'id="soma-v75-combat-telegraph-runtime"' in html:
        raise ValueError('Combat v75 déjà appliqué.')
    source = scripts.get('combat-telegraph-runtime')
    if not isinstance(source, str) or not source.strip() or '</script' in source.lower():
        raise ValueError('Module combat v75 invalide.')
    html = rewrite_script(html, 'soma-v32-patch', patch_v32)
    html = rewrite_script(html, 'soma-v33-patch', patch_v33)
    html = rewrite_script(html, 'soma-v72-netrunner-runtime', patch_warning)
    html = rewrite_script(html, 'soma-v73-tactical-runtime', lambda body: once(body,
        'const role=root.__SOMA_COMBAT_SUPPORT74__?.describe(q)||',
        'const role=root.__SOMA_COMBAT75__?.describe(q)||root.__SOMA_COMBAT_SUPPORT74__?.describe(q)||', 'Écho lit la préparation réelle'))
    html = once(html, 'function loop(t){window.__SOMA_COMBAT_SUPPORT74__?.maintain();',
                'function loop(t){window.__SOMA_COMBAT75__?.maintain();window.__SOMA_COMBAT_SUPPORT74__?.maintain();', 'avant pause et onglet masqué')
    html = rewrite_script(html, 'soma-v70-perception-runtime', lambda body: once(body,
        'root.__SOMA_COMBAT_SUPPORT74__?.reset?.();', 'root.__SOMA_COMBAT_SUPPORT74__?.reset?.();root.__SOMA_COMBAT75__?.reset?.();', 'vrai import et transfert'))
    html = rewrite_script(html, 'soma-v45-city', lambda body: once(body,
        'if(!saved||!Number.isFinite(saved.health))return q;',
        'if(!saved||!Number.isFinite(saved.health))return q;window.__SOMA_COMBAT75__?.restoreRecovery(q,saved);', 'recharge des vrais ennemis45'))
    return once(html, '</body>', '\n<script id="soma-v75-combat-telegraph-runtime">\n' + MARKER + '\n' + source + '\n</script>\n</body>', 'adaptateur après propriétaires74')


def patch_viewer(html, scripts):
    return html
