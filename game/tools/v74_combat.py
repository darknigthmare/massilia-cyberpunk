"""Prepare the real v32 restoration without replacing its effect or damage owners."""
from build_v68 import replace_once, rewrite_script

MODULES = ('combat-support-runtime',)
MARKER = '/* SOMA v74 combat: interruptible local medical support. */'


def once(text, old, new, label):
    return replace_once(text, old, new, 'v74 combat: ' + label)


def patch_v32(body):
    start = " else if(q.v32Role==='medic'){"
    end = "\n else{const ideal=q.v32Role==='heavy'?"
    if body.count(start) != 1 or body.count(end) != 1:
        raise ValueError('Ancre différente : v74 branche médicale v32')
    a, b = body.index(start), body.index(end)
    branch = body[a:b]
    old = "const ally=(zone.robots||[]).filter(x=>x.v32Enemy&&x.health>0&&x.health<x.maxHealth).sort((x,y)=>x.health-y.health)[0];if(ally&&Math.hypot(ally.x-q.x,ally.z-q.z)<16&&q.attackClock<=0){"
    new = "const support74=window.__SOMA_COMBAT_SUPPORT74__,managed74=!!support74?.handles(q),ally=managed74?support74.advance(q,dt):(zone.robots||[]).filter(x=>x.v32Enemy&&x.health>0&&x.health<x.maxHealth).sort((x,y)=>x.health-y.health)[0];if(managed74?!!ally:ally&&Math.hypot(ally.x-q.x,ally.z-q.z)<16&&q.attackClock<=0){"
    branch = once(branch, old, new, 'sélection et préparation ; effet +18 original')
    branch = once(branch, "}else if((p70?dist70:dist)<=a.range", "}else if(!(managed74&&support74.isPreparing(q))&&(p70?dist70:dist)<=a.range", 'pas de tir pendant les soins')
    body = body[:a] + branch + body[b:]
    body = once(body, "if(q.state==='combat'){", "if(q.state==='combat'||window.__SOMA_COMBAT_SUPPORT74__?.isPreparing(q)){",
                'seule continuation des soins en recherche, sans permission de tir')
    body = once(body, 'const rec=zoneCombatState(zoneId).enemies[q.id];if(!rec)return;',
                'const rec=zoneCombatState(zoneId).enemies[q.id];if(!rec)return;window.__SOMA_COMBAT_SUPPORT74__?.restoreRecovery(q,rec);',
                'recharge du médecin dans la restauration originale')
    body = once(body, 'v34BaseArmor:q.v34BaseArmor};st.lastSeen=Date.now();save32()',
                'v34BaseArmor:q.v34BaseArmor,...(window.__SOMA_COMBAT_SUPPORT74__?.handles(q)?{attackClock:window.__SOMA_COMBAT_SUPPORT74__.recoveryForSave(q)}:{})};st.lastSeen=Date.now();save32()',
                'même scalaire de recharge dans le propriétaire des étages')
    return once(body, 'window.__SOMA_NETRUNNER72__?.beginEnemyFrame();',
                'window.__SOMA_NETRUNNER72__?.beginEnemyFrame();window.__SOMA_COMBAT_SUPPORT74__?.beginEnemyFrame();',
                'budget et invalidation avant la boucle ennemie')


def patch_v33(body):
    return once(body, 'out.health=Math.max(0,finite(out.health));\n  return out;',
                'out.health=Math.max(0,finite(out.health));\n  if(window.__SOMA_COMBAT_SUPPORT74__?.handles(q))out.attackClock=window.__SOMA_COMBAT_SUPPORT74__.recoveryForSave(q);\n  return out;',
                'préparation non restaurée dans le roster territorial')


def patch_persistence(body):
    anchor = "number(e.health,0,1e7,'Santé ennemie');"
    return once(body, anchor, anchor + "if(e.attackClock!==undefined)number(e.attackClock,0,3600,'Recharge ennemie');", 'valeur optionnelle de recharge ennemie')


def patch_echo(body):
    body = once(body, "const role=q.v26BossId?", "const role=root.__SOMA_COMBAT_SUPPORT74__?.describe(q)||(q.v26BossId?", 'lecture de la préparation réelle')
    return once(body, "['Signal local','Observez ses déplacements.']);", "['Signal local','Observez ses déplacements.']));", 'fin de la lecture de rôle')


def patch_html(html, scripts):
    if MARKER in html or 'id="soma-v74-combat-support-runtime"' in html:
        raise ValueError('Soutien médical v74 déjà appliqué.')
    source = scripts.get('combat-support-runtime')
    if not isinstance(source, str) or not source.strip() or '</script' in source.lower():
        raise ValueError('Module combat v74 invalide.')
    html = rewrite_script(html, 'soma-v32-patch', patch_v32)
    html = rewrite_script(html, 'soma-v33-patch', patch_v33)
    html = rewrite_script(html, 'soma-v37-persistence', patch_persistence)
    html = rewrite_script(html, 'soma-v73-tactical-runtime', patch_echo)
    html = once(html, 'function loop(t){window.__SOMA_NETRUNNER72__?.maintain();',
                'function loop(t){window.__SOMA_COMBAT_SUPPORT74__?.maintain();window.__SOMA_NETRUNNER72__?.maintain();',
                'annulation avant les retours pause/onglet')
    html = rewrite_script(html, 'soma-v70-perception-runtime', lambda body: once(body,
        'root.__SOMA_TACTICAL73__?.reset?.();',
        'root.__SOMA_TACTICAL73__?.reset?.();root.__SOMA_COMBAT_SUPPORT74__?.reset?.();', 'vrai import et transfert'))
    return once(html, '</body>', '\n<script id="soma-v74-combat-support-runtime">\n' + MARKER + '\n' + source + '\n</script>\n</body>', 'runtime après les propriétaires historiques')


def patch_viewer(html, scripts):
    """Medical combat is campaign-only; the metropolitan viewer is untouched."""
    return html
