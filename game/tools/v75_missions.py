"""Keep the authored Act III trace in its existing v45 owner and travel mode."""
from build_v68 import replace_once, rewrite_script

MODULES = ('missions-runtime',)
MARKER = '/* SOMA v75 missions: authored operation guidance. */'


def once(text, old, new, label):
    return replace_once(text, old, new, 'v75 missions: ' + label)


def patch_city(body, runtime):
    body = once(body, 'function v45Setup(){', MARKER + '\n' + runtime + '\nfunction v45Setup(){', 'helpers in the existing city owner')
    body = once(body, "action:()=>v45SetDestination(active.steps[s.step].zone,active.steps[s.step].label)",
                "action:()=>v75TraceOperation(active.id)", 'command console preserves required driving')
    body = once(body, "action:()=>v45SetDestination(step.zone,step.label)",
                "action:()=>v75TraceOperation(op.id)", 'objective console preserves required driving')
    body = once(body, "const op=V45_OPERATION_BY_ID[b.dataset.v45TrackOp],s=v45OperationState(op.id);v45SetDestination(op.steps[s.step].zone,op.steps[s.step].label);closeModals()",
                "v75TraceOperation(b.dataset.v45TrackOp);closeModals()", 'dossier preserves required driving')
    body = once(body,
                "const op=V45_OPERATION_BY_ID[o.operationId],s=op&&v45OperationState(op.id),step=op?.steps[o.step],proof=v74StepProof(o);if(!op||!s||!step||!proof)return false;",
                "const op=V45_OPERATION_BY_ID[o?.operationId],s=op&&v45OperationState(op.id),step=op?.steps[o.step];if(!op||!s||!step||!v74Point(o,'v45OperationNode'))return false;",
                'inactive authored nodes retain their physical feedback')
    body = once(body,
                "if(step.kind==='channel')return v45BeginChannel('operation',op.id,o,step.duration||2.6,",
                "const proof=v74StepProof(o);if(!proof)return false;\n  if(step.kind==='channel')return v45BeginChannel('operation',op.id,o,step.duration||2.6,",
                'active objectives still require the unchanged v74 proof')
    body = once(body, 'v45MakeUI();if(!V45.director.activeCall',
                'for(const z of Object.values(WORLD.zones))if(z.static)v75ReconcileHotspotEnemies(z);v45MakeUI();if(!V45.director.activeCall',
                'restore the earlier production owner after its first setup')
    return body


def patch_production(body):
    body = once(body, 'const V43_HOTSPOT_BY_ZONE=Object.fromEntries(V43_HOTSPOTS.map(x=>[x.zone,x]));',
                "const V43_HOTSPOT_BY_ZONE=Object.fromEntries(V43_HOTSPOTS.map(x=>[x.zone,x]));\n// Content identities are published before setup43 and the deferred validator37.\nwindow.__SOMA_MISSIONS75_CONTENT__=Object.freeze(V43_HOTSPOTS.map(h=>Object.freeze({id:h.id,zone:h.zone,count:h.count})));",
                'immutable source43 identities before owner setup')
    return once(body, '    z.robots.push(q);out.push(q);',
                '    window.__SOMA_MISSIONS75__?.restoreHotspotEnemy(q,z);z.robots.push(q);out.push(q);',
                'restore only the exact source43 hotspot definitions')


def patch_saver(body):
    body = once(body, "function enemyIdKnown(id,k,zoneId=null){if(typeof id==='string'&&id.startsWith('v45-'))",
                "function enemyIdKnown(id,k,zoneId=null){if(typeof id==='string'&&id.startsWith('v43-'))return k.edition>=37&&window.__SOMA_MISSIONS75__?.knownHotspotEnemy(id,zoneId)===true;if(typeof id==='string'&&id.startsWith('v45-'))",
                'exact source43 hotspot identities, zone and count')
    return once(body, "window.__SOMA_PROGRESSION74__?.legacyLootRole(id,l.zone,l.role)||l.role",
                "window.__SOMA_MISSIONS75__?.legacyLootRole(id,l.zone,l.role)||window.__SOMA_PROGRESSION74__?.legacyLootRole(id,l.zone,l.role)||l.role",
                'exact historical source43 blade loot compatibility')


def patch_html(html, scripts):
    if MARKER in html:
        raise ValueError('Missions v75 déjà appliquées.')
    if html.count('id="soma-v74-edition"') != 1:
        raise ValueError('Parent v74 requis pour les missions v75.')
    runtime = scripts.get('missions-runtime')
    if not isinstance(runtime, str) or not runtime.strip() or '</script' in runtime.lower():
        raise ValueError('Module missions v75 invalide.')
    html = rewrite_script(html, 'soma-v43-production', patch_production)
    html = rewrite_script(html, 'soma-v37-persistence', patch_saver)
    return rewrite_script(html, 'soma-v45-city', lambda body: patch_city(body, runtime))


def patch_viewer(html, scripts):
    return html
