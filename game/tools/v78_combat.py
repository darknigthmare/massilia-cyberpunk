"""Cancel obsolete native30 chamber clearing without moving its timer or wear."""
from build_v68 import replace_once, rewrite_script

MODULES = ('combat-chamber-runtime',)
MARKER = '/* SOMA v78 combat: material30 owns chamber clearing. */'


def once(text, old, new, label):
    return replace_once(text, old, new, 'v78 combat: ' + label)


def patch_html(html, scripts):
    if MARKER in html:
        raise ValueError('Combat v78 déjà appliqué.')
    source = scripts.get(MODULES[0])
    if not isinstance(source, str) or not source.strip() or '</script' in source.lower():
        raise ValueError('Module combat v78 invalide.')
    html = once(html, 'function clearJam(){\n',
        'function clearJam(){\n if(!zone||state.health<=0||state.recovery?.pending)return false;\n',
        'refuser une nouvelle action sans corps valide')
    html = once(html, 'materialJamTask={weapon:w,record:d,left:.9};',
        'materialJamTask={weapon:w,record:d,left:.9,core:state,scene:zone,zoneId:zone.id};',
        'capturer les identités éphémères')
    html = once(html, 'let materialJamTask=null;\n',
        'let materialJamTask=null;\n' + MARKER + '\n' + source + '\n',
        'installer dans la portée du propriétaire30')
    html = once(html, 'update=function(dt){materialBaseUpdate(dt);if(!materialJamTask||paused)return;',
        'update=function(dt){materialBaseUpdate(dt);window.__SOMA_CHAMBER78__?.maintain();if(!materialJamTask||paused)return;',
        'contrôler avant le transfert natif')
    html = once(html, 'function loop(t){window.__SOMA_RELOAD77__?.maintain();',
        'function loop(t){window.__SOMA_CHAMBER78__?.maintain();window.__SOMA_RELOAD77__?.maintain();',
        'invalider même pendant la pause')
    html = once(html,
        'if(state.weapon!==i)window.__SOMA_RELOAD77__?.cancel();state.weapon=i;',
        'if(state.weapon!==i){window.__SOMA_RELOAD77__?.cancel();window.__SOMA_CHAMBER78__?.cancel()}state.weapon=i;',
        'annuler depuis le bouton arsenal27')
    html = once(html,
        'if(idx>=0){window.__SOMA_RELOAD77__?.cancel();state.weapon=idx}',
        'if(idx>=0){window.__SOMA_RELOAD77__?.cancel();window.__SOMA_CHAMBER78__?.cancel();state.weapon=idx}',
        'annuler le dépôt de l’arme active29')
    html = once(html,
        'if(state.weapon!==n)window.__SOMA_RELOAD77__?.cancel();state.weapon=n;',
        'if(state.weapon!==n){window.__SOMA_RELOAD77__?.cancel();window.__SOMA_CHAMBER78__?.cancel()}state.weapon=n;',
        'annuler les anciens raccourcis directs')
    html = rewrite_script(html, 'soma-v37-persistence', lambda body: once(body,
        'function clearScene(){\n window.__SOMA_RELOAD77__?.reset();',
        'function clearScene(){\n window.__SOMA_CHAMBER78__?.reset();\n window.__SOMA_RELOAD77__?.reset();',
        'annuler avant remplacement de scène par37'))
    return rewrite_script(html, 'soma-v64-group-runtime', lambda body: once(body,
        'if(reloadLeft>0||state.night?.listening||api(42)?.isChanneling?.()',
        'if(reloadLeft>0||window.__SOMA_CHAMBER78__?.snapshot?.()?.active||state.night?.listening||api(42)?.isChanneling?.()',
        'refuser le transfert groupé pendant le dégagement actif'))


def patch_viewer(html, scripts):
    return html
