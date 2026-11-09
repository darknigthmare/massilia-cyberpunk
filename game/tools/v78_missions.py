"""Keep escort guidance on the authored vehicle graph and repair the Port run endpoint."""
from build_v68 import replace_once, rewrite_script

MODULES = ('missions-runtime',)
MARKER = '/* SOMA v78 missions: existing vehicle routes and explicit authored endpoints. */'


def once(text, old, new, label):
    return replace_once(text, old, new, 'v78 missions: ' + label)


def patch_city(body, runtime):
    body = once(body, "const V45_RACE_TARGETS={port:'corniche-route'", "const V45_RACE_TARGETS={port:'corniche-exterior'", 'Port run ends on the existing Corniche street, not the disconnected upper road')
    body = once(body,
        "const guided=v77AutoDestination45(s.targetZone,`${call.title} · acheminement`,false,v77CallRoute45(call,s));showDialogue(call.title,[`${guided?'Le trajet est chargé dans le GPS.':'Destination GPS conservée.'} Rejoignez ${WORLD.zones[s.targetZone]?.title||s.targetZone} en véhicule.`],[{label:'Fermer'}],D[call.district]?.name||call.district,'ESCORTE');return true",
        'return v78EscortDialogue45(call,s)', 'escort uses vehicle-only graph and honest refusal')
    body = once(body,
        "call.type==='escort'&&v77RouteMatches45(s.targetZone,`${call.title} · acheminement`,false);",
        "call.type==='escort'&&(v77RouteMatches45(s.targetZone,`${call.title} · acheminement`,false)||v77RouteMatches45(s.targetZone,`${call.title} · acheminement`,true));",
        'recognize only the exact old and new escort destination tuples')
    body = once(body,
        "b.onclick=()=>{const s=V45.calls[b.dataset.v45TrackCall],c=V45_CALL_BY_ID[b.dataset.v45TrackCall];v45SetDestination(s.zone,c.title);closeModals()}",
        "b.onclick=()=>{if(v78TraceCall45(b.dataset.v45TrackCall))closeModals()}",
        'explicit active escort trace targets delivery instead of the original contact')
    body = once(body,
        "path=v45FindRoute(zone.id,target,true);if(path.length<2)return false;",
        "path=v45FindRoute(zone.id,target,true);if(path.length<2){announce('Run indisponible : aucune liaison routière vers son arrivée depuis ce secteur.',4);return false;}",
        'race refusal gives feedback without changing any state')
    return once(body, 'function v45Setup(){', MARKER + '\n' + runtime + '\nfunction v45Setup(){', 'helpers live inside the existing45 owner')


def patch_html(html, scripts):
    if MARKER in html:
        raise ValueError('Missions v78 déjà appliquées.')
    if html.count('id="soma-v77-edition"') != 1:
        raise ValueError('Parent v77 requis pour les missions v78.')
    runtime = scripts.get(MODULES[0])
    if not isinstance(runtime, str) or not runtime.strip() or '</script' in runtime.lower():
        raise ValueError('Module missions v78 invalide.')
    return rewrite_script(html, 'soma-v45-city', lambda body: patch_city(body, runtime))


def patch_viewer(html, scripts):
    return html
