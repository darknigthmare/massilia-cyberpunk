"""Keep automatic authored mission guidance from replacing a manual GPS."""
from build_v68 import replace_once, rewrite_script

MODULES = ('missions-runtime', 'missions-route-runtime')
MARKER = '/* SOMA v77 missions: explicit guidance and conservative native GPS. */'


def once(text, old, new, label):
    return replace_once(text, old, new, 'v77 missions: ' + label)


def patch_production(body, runtime):
    body = once(body, 'function v43Setup(){', MARKER + '\n' + runtime + '\nfunction v43Setup(){', 'guidance inside authored43 owner')
    body = once(body, "detail:'Retour à Station Zéro · table de campagne'", "detail:'Station Zéro · intérieur A · table de campagne'", 'exact story hand-in interior')
    body = once(body, "`${D[m.district]?.name||m.district} · ${step.label}`", "`${WORLD.zones[step.zone]?.title||step.zone} · ${step.label}`", 'current source stage location')
    body = once(body, 'Acceptation et remise se font physiquement à Station Zéro.', 'Acceptation et remise : table de campagne de Station Zéro, intérieur A.', 'career story return location')
    for kind, content in [('story', 'm'), ('gig', 'g')]:
        old = f'<button data-v43-track="{kind}:${{{content}.id}}">Suivre</button>'
        new = old + f'<button data-v77-trace="{kind}:${{{content}.id}}">${{s.status===\'return\'?\'Tracer la remise\':\'Tracer l’objectif\'}}</button>'
        body = once(body, old, new, kind + ' explicit native GPS action')
    body = once(body, "root.innerHTML=nav+body;root.querySelectorAll('[data-v43-tab]')", "root.innerHTML=nav+body;root.querySelectorAll('[data-v77-trace]').forEach(b=>b.onclick=()=>{const [kind,id]=b.dataset.v77Trace.split(':');v77Trace43(kind,id)});root.querySelectorAll('[data-v43-tab]')", 'explicit trace callbacks preserve follow semantics')
    return body


def patch_city(body, runtime):
    body = once(body, 'function v45Setup(){', runtime + '\nfunction v45Setup(){', 'helpers inside native45 GPS owner')
    body = once(body, 'v45SetDestination(op.steps[0].zone,op.steps[0].label);', "v77AutoDestination45(op.steps[0].zone,op.steps[0].label,op.steps[0].kind==='drive');", 'accept preserves unrelated manual route')
    body = once(body, "window.__SOMA_V32__?.snapshotCombat?.();s.choice=choice??s.choice;", "const routeOwned=v77OperationStepRoute45(op,step);window.__SOMA_V32__?.snapshotCombat?.();s.choice=choice??s.choice;", 'recognize prior source step before transition')
    body = once(body, "v45SetDestination('station-exterior',`Remettre le dossier · ${op.title}`);", "v77AutoDestination45('station-exterior',`Remettre le dossier · ${op.title}`,false,routeOwned);", 'completion preserves manual GPS')
    body = once(body, "v45SetDestination(next.zone,next.label,next.kind==='drive');", "v77AutoDestination45(next.zone,next.label,next.kind==='drive',routeOwned);", 'next stage updates only matching prior route')
    body = once(body, 'v45RefreshOperationUnlocks();v45ClearDestination();', 'v45RefreshOperationUnlocks();v77ClearOperationRoute45(op);', 'hand-in clears only source return route')
    body = once(body, "v45SetDestination(s.zone,call.title,call.type==='escort');", "v77AutoDestination45(s.zone,call.title,call.type==='escort');", 'call acceptance preserves manual GPS')
    body = once(body, "if(V45.tracked?.kind==='call'&&V45.tracked.id===id)V45.tracked=null;v45ClearDestination();", "if(V45.tracked?.kind==='call'&&V45.tracked.id===id)V45.tracked=null;v77ClearCallRoute45(call,s);", 'call resolution clears only its own source route')
    body = once(body, "if(V45.tracked?.kind==='call'&&V45.tracked.id===id)V45.tracked=null;v45Save(true);v45RebuildCurrent();announce(`${call.title} · appel expiré`", "if(V45.tracked?.kind==='call'&&V45.tracked.id===id)V45.tracked=null;v77ClearCallRoute45(call,s);v45Save(true);v45RebuildCurrent();announce(`${call.title} · appel expiré`", 'expiry removes own stale guide only')
    body = once(body, "if(call.type==='escort'){v45SetDestination(s.targetZone,`${call.title} · acheminement`);showDialogue(call.title,[`Le trajet est chargé dans le GPS. Rejoignez ${WORLD.zones[s.targetZone]?.title||s.targetZone} en véhicule.`]", "if(call.type==='escort'){const guided=v77AutoDestination45(s.targetZone,`${call.title} · acheminement`,false,v77CallRoute45(call,s));showDialogue(call.title,[`${guided?'Le trajet est chargé dans le GPS.':'Destination GPS conservée.'} Rejoignez ${WORLD.zones[s.targetZone]?.title||s.targetZone} en véhicule.`]", 'escort objective respects the current manual guide and reports it honestly')
    body = once(body, 'v45SetDestination(path[1],`${run.title} · point 1/${path.length-1}`,true);', 'v77AutoDestination45(path[1],`${run.title} · point 1/${path.length-1}`,true);', 'race acceptance preserves the current manual destination')
    body = once(body, 'V45.raceActive=null;V45.tracked=null;v45ClearDestination();', 'V45.raceActive=null;V45.tracked=null;v77ClearRaceRoute45(active,active.path.length-1);', 'race finish clears only the source final checkpoint')
    body = once(body, "function v45FailRace(reason='Temps écoulé'){if(!V45.raceActive)return false;V45.raceActive=null;if(V45.tracked?.kind==='race')V45.tracked=null;v45ClearDestination();", "function v45FailRace(reason='Temps écoulé'){const active=V45.raceActive;if(!active)return false;V45.raceActive=null;if(V45.tracked?.kind==='race')V45.tracked=null;v77ClearRaceRoute45(active);", 'race timeout and abandonment preserve manual GPS')
    body = once(body, 'if(current!==expected||!state.driving)return;active.index++;', 'if(current!==expected||!state.driving)return;const routeOwned=v77RaceRoute45(active);active.index++;', 'recognize previous race checkpoint before mutation')
    body = once(body, "v45SetDestination(next,`${V45_RACES.find(x=>x.id===active.id)?.title||'Run'} · point ${active.index+1}/${active.path.length-1}`,true);", "v77AutoDestination45(next,`${V45_RACES.find(x=>x.id===active.id)?.title||'Run'} · point ${active.index+1}/${active.path.length-1}`,true,routeOwned);", 'race checkpoint updates only its previous source route')
    body = once(body, "?'Remettre le dossier à Station Zéro':", "?'Station Zéro · extérieur · centre des opérations':", 'disambiguate Act III hand-in')
    return body


def patch_html(html, scripts):
    if MARKER in html:
        raise ValueError('Missions v77 déjà appliquées.')
    if html.count('id="soma-v76-edition"') != 1:
        raise ValueError('Parent v76 requis pour les missions v77.')
    for name in MODULES:
        value = scripts.get(name)
        if not isinstance(value, str) or not value.strip() or '</script' in value.lower():
            raise ValueError('Module missions v77 invalide : ' + name)
    html = rewrite_script(html, 'soma-v43-production', lambda body: patch_production(body, scripts['missions-runtime']))
    return rewrite_script(html, 'soma-v45-city', lambda body: patch_city(body, scripts['missions-route-runtime']))


def patch_viewer(html, scripts):
    return html
