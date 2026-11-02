"""Make the existing paid Écho useful in the street; historical owners stay frozen."""
from build_v68 import replace_once, rewrite_script

MODULES = ('tactical-runtime',)
MARKER = '/* SOMA v73 tactical Écho: visible body readouts. */'


def once(text, old, new, label):
    return replace_once(text, old, new, 'v73 tactical: ' + label)


def patch_runtime(body):
    start = '  function scan(){'
    end = '  function open(){'
    if body.count(start) != 1 or body.count(end) != 1:
        raise ValueError('Ancre différente : v73 propriétaire du scan')
    a, b = body.index(start), body.index(end)
    body = body[:a] + '  function scan(){return root.__SOMA_TACTICAL73__?.scanTargets()||[];}\n' + body[b:]
    body = once(body, 'scanTargets:scanRows.map(v=>({...v}))', 'scanTargets:scan().map(v=>({...v}))', 'snapshot sans ancienne visibilité')
    body = once(body, "row.healthPercent+'%'+(row.electronic?' · système électronique':'')",
        "row.healthPercent+'% · '+row.roleLabel+' · '+row.hint+(row.electronic?' · système électronique':'')", 'détails lisibles dans le Cortex')
    return once(body, 'Lit les unités visibles pendant 5 s. Les obstacles restent opaques.',
        'Lit les corps dans votre champ de vue à 24 m pendant 5 s : rôle, intégrité et conseil tactique. Les obstacles restent opaques.', 'aide de la capacité existante')


def patch_hud_layout(body):
    # The authored combat status column can exceed a 720/768px viewport even
    # without the Écho live summary. The campaign objective belongs with the
    # existing navigation objectives; keep its original node and owner.
    body = once(body, "'#trackedObjective','#v42-city-hud'", "'#trackedObjective','#v45-tracker','#v42-city-hud'", 'objectif campagne dans navigation')
    return once(body, "'#v43-tracker','#v45-tracker','#v32-hud'", "'#v43-tracker','#v32-hud'", 'colonne statut conserve une hauteur jouable')


def patch_html(html, scripts):
    if MARKER in html or 'id="soma-v73-tactical-runtime"' in html:
        raise ValueError('Écho tactique v73 déjà appliqué.')
    text = scripts.get('tactical-runtime')
    if not isinstance(text, str) or not text.strip() or '</script' in text.lower():
        raise ValueError('Module tactique v73 invalide.')
    html = rewrite_script(html, 'soma-v70-runtime', patch_runtime)
    html = rewrite_script(html, 'soma-v72-hud-layout-runtime', patch_hud_layout)
    html = once(html, 'function loop(t){window.__SOMA_NETRUNNER72__?.maintain();',
        'function loop(t){window.__SOMA_NETRUNNER72__?.maintain();window.__SOMA_TACTICAL73__?.maintain();',
        'visibilité et annulation avant les retours de boucle')
    html = rewrite_script(html, 'soma-v70-perception-runtime', lambda body: once(body,
        'root.__SOMA_NETRUNNER72__?.reset?.();', 'root.__SOMA_NETRUNNER72__?.reset?.();root.__SOMA_TACTICAL73__?.reset?.();',
        'import et transfert de campagne'))
    return once(html, '</body>', '\n<script id="soma-v73-tactical-runtime">\n' + MARKER + '\n' + text + '\n</script>\n</body>', 'adaptateur après le propriétaire v70')


def patch_viewer(html, scripts):
    """Campaign readout: no scan, campaign state, or DOM injected into the viewer."""
    return html
