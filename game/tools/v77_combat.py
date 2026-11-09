"""Bind the existing27 reload to its live weapon, scene and ammunition record."""
from build_v68 import replace_once, rewrite_script

MODULES = ('combat-reload-runtime',)
MARKER = '/* SOMA v77 combat: native ammunition, ephemeral reload identity. */'


def once(text, old, new, label):
    return replace_once(text, old, new, 'v77 combat: ' + label)


def patch_html(html, scripts):
    if MARKER in html or 'id="soma-v77-combat-reload-runtime"' in html:
        raise ValueError('Combat v77 déjà appliqué.')
    source = scripts.get(MODULES[0])
    if not isinstance(source, str) or not source.strip() or '</script' in source.lower():
        raise ValueError('Module combat v77 invalide.')
    html = once(html,
        'b.onclick=()=>{state.weapon=i;announce(`${w.name} équipée`);renderArsenal();save()}',
        'b.onclick=()=>{if(state.weapon!==i)window.__SOMA_RELOAD77__?.cancel();state.weapon=i;announce(`${w.name} équipée`);renderArsenal();save()}',
        'annuler depuis le bouton arsenal27')
    html = once(html,
        'if(idx>=0)state.weapon=idx}save();return{ok:true,reason:',
        'if(idx>=0){window.__SOMA_RELOAD77__?.cancel();state.weapon=idx}}save();return{ok:true,reason:',
        'annuler le dépôt de l’arme active29')
    html = once(html, 'state.weapon=n;announce(WEAPONS[n].name)',
        'if(state.weapon!==n)window.__SOMA_RELOAD77__?.cancel();state.weapon=n;announce(WEAPONS[n].name)',
        'annuler les anciens raccourcis directs')
    html = once(html, 'function loop(t){window.__SOMA_COMBAT76__?.maintain();',
        'function loop(t){window.__SOMA_RELOAD77__?.maintain();window.__SOMA_COMBAT76__?.maintain();',
        'vérifier même pendant le rendu en pause')
    html = rewrite_script(html, 'soma-v37-persistence', lambda body: once(body,
        'function clearScene(){\n', 'function clearScene(){\n window.__SOMA_RELOAD77__?.reset();\n',
        'import37 annule l’identité temporaire'))
    return once(html, '</body>', '\n<script id="soma-v77-combat-reload-runtime">\n' + MARKER + '\n' + source + '\n</script>\n</body>',
        'installer après les propriétaires existants')


def patch_viewer(html, scripts):
    return html
