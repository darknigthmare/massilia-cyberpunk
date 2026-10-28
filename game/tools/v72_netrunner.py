"""Derived, narrowly scoped counterplay for the original v32 neural intrusion."""
from build_v68 import replace_once, rewrite_script

MODULES = ('netrunner-runtime',)
MARKER = '/* SOMA v72 netrunner: interruptible neural intrusion. */'


def once(text, old, new, label):
    return replace_once(text, old, new, 'v72 netrunner: ' + label)


def patch_v32(text):
    start = " else if(q.v32Role==='netrunner'){"
    end = " else if(q.v32Role==='medic'){"
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError('Ancre différente : v72 netrunner branche originale')
    a, b = text.index(start), text.index(end)
    branch = text[a:b]
    condition = '(p70?dist70:dist)<=a.range&&!lineBlocked(q.x,q.z,(p70?targetX70:camera.x),(p70?targetZ70:camera.z))&&mayAttack70&&q.attackClock<=0'
    branch = once(branch, 'if(' + condition + '){',
                  'if(window.__SOMA_NETRUNNER72__?window.__SOMA_NETRUNNER72__.advance(q,a,dt,mayAttack70):(' + condition + ')){',
                  'seule préparation du tisseur, effet original conservé')
    text = text[:a] + branch + text[b:]
    return once(text, 'function v32UpdateEnemies(dt){if(!zone)return;window.__SOMA_PERCEPTION70__?.beginEnemyFrame(dt);',
                MARKER + '\nfunction v32UpdateEnemies(dt){if(!zone)return;window.__SOMA_PERCEPTION70__?.beginEnemyFrame(dt);window.__SOMA_NETRUNNER72__?.beginEnemyFrame();',
                'annulation avant toute attaque tactique')


def patch_html(html, scripts):
    """Apply to reconstructed v71 (or v72 radio output), never to source inputs."""
    if MARKER in html or 'id="soma-v72-netrunner-runtime"' in html:
        raise ValueError('Contre-jeu netrunner v72 déjà appliqué.')
    text = scripts.get('netrunner-runtime')
    if not isinstance(text, str) or not text.strip() or '</script' in text.lower():
        raise ValueError('Module netrunner v72 invalide.')
    html = rewrite_script(html, 'soma-v32-patch', patch_v32)
    # Paused simulation never calls update(), including the original F8/F9
    # panels. The actual render loop therefore owns lifecycle cancellation.
    html = once(html, 'function loop(t){\n const P=window.__SOMA_PERF65__,',
                'function loop(t){window.__SOMA_NETRUNNER72__?.maintain();\n const P=window.__SOMA_PERF65__,',
                'pause et onglet masqué avant les retours de boucle')
    html = rewrite_script(html, 'soma-v70-perception-runtime', lambda value: once(value,
        'root.__SOMA_LEGACY_PERCEPTION71__?.reset?.();',
        'root.__SOMA_LEGACY_PERCEPTION71__?.reset?.();root.__SOMA_NETRUNNER72__?.reset?.();',
        'reset au vrai transfert et import de campagne'))
    return once(html, '</body>', '\n<script id="soma-v72-netrunner-runtime">\n' + text + '\n</script>\n</body>',
                'runtime après les propriétaires historiques')
