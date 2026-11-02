"""Validate native-pilot entries with the existing standing and vehicle bodies."""
from build_v68 import replace_once, rewrite_script

MODULES = ('entry-runtime',)
MARKER = '/* SOMA v76 mobility: native entries respect standing and parked bodies. */'


def once(text, old, new, label):
    return replace_once(text, old, new, 'v76 mobilité : ' + label)


def patch_terrain(body):
    body = once(body, '   let pose=args[2]||target.spawn;',
        '   const entry76=window.__SOMA_MOBILITY76__,native76=window.__SOMA_TERRAIN75__?.active()&&entry76?.ready;\n   let pose=args[2]||target.spawn;',
        'garde réservée au pilote natif')
    body = once(body,
        'if(!pose||!footprintValid(target,pose.x,pose.z,.4)||blocked(target,pose.x,pose.z,.38)||!(window.__SOMA_TERRAIN75__?.entrySupported(target,pose.x,pose.z)??true)){',
        'if(!pose||(native76?!entry76.valid(target,pose.x,pose.z):(!footprintValid(target,pose.x,pose.z,.4)||blocked(target,pose.x,pose.z,.38)||!(window.__SOMA_TERRAIN75__?.entrySupported(target,pose.x,pose.z)??true)))){',
        'pose restaurée debout et hors carrosseries')
    return once(body,
        'if(footprintValid(target,q.x,q.z,.4)&&!blocked(target,q.x,q.z,.38)&&(window.__SOMA_TERRAIN75__?.entrySupported(target,q.x,q.z)??true)){safe=q;break;}',
        'if(native76?entry76.valid(target,q.x,q.z):(footprintValid(target,q.x,q.z,.4)&&!blocked(target,q.x,q.z,.38)&&(window.__SOMA_TERRAIN75__?.entrySupported(target,q.x,q.z)??true))){safe=q;break;}',
        'même garde sur les centres source existants')


def patch_cache_reconcile(body):
    return once(body,
        'if(entrySupported(zone,pose.x,pose.z)&&!blocked(zone,pose.x,pose.z,.38)){',
        'if(!state.driving&&root.__SOMA_MOBILITY76__?.ready?root.__SOMA_MOBILITY76__.valid(zone,pose.x,pose.z):(entrySupported(zone,pose.x,pose.z)&&!blocked(zone,pose.x,pose.z,.38))){',
        'reprise du cache natif réconciliée par les mêmes corps à pied')


def patch_html(html, scripts):
    if MARKER in html or 'id="soma-v76-entry-runtime"' in html:
        raise ValueError('Mobilité v76 déjà appliquée.')
    value = scripts.get('entry-runtime')
    if not isinstance(value, str) or not value.strip() or '</script' in value.lower():
        raise ValueError('Module mobilité v76 invalide.')
    html = rewrite_script(html, 'soma-v56-terrain-runtime', patch_terrain)
    html = rewrite_script(html, 'soma-v75-terrain-runtime', patch_cache_reconcile)
    return once(html, '</body>', '\n<script id="soma-v76-entry-runtime">\n' + MARKER + '\n' + value + '\n</script>\n</body>', 'garde après les propriétaires')


def patch_viewer(html, scripts):
    return html
