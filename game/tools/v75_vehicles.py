"""Keep terrestrial swept contact and local ground supports over frozen v74."""
from build_v68 import replace_once

MODULES = ('vehicle-runtime',)
MARKER = '/* SOMA v75 vehicles: bounded body sweep and local ground support. */'


def patch_html(html, scripts):
    if MARKER in html or 'id="soma-v75-vehicle-runtime"' in html:
        raise ValueError('Véhicules v75 déjà appliqués.')
    if 'id="soma-v74-mobility-runtime"' not in html:
        raise ValueError('Les propriétaires de mobilité v74 sont requis.')
    text = scripts.get('vehicle-runtime')
    if not isinstance(text, str) or not text.strip() or '</script' in text.lower():
        raise ValueError('Module véhicules v75 invalide.')
    old = 'if(vehicleBlockedAt(v,nx,nz,v.heading)){collided=true;impact=Math.max(impact,Math.abs(old));v.heading=previousHeading57;'
    new = 'if(window.__SOMA_VEHICLES75__?.ready?window.__SOMA_VEHICLES75__.pathBlocked(v,nx,nz,v.heading,previousHeading57):vehicleBlockedAt(v,nx,nz,v.heading)){collided=true;impact=Math.max(impact,Math.abs(old));v.heading=previousHeading57;'
    html = replace_once(html, old, new, 'v75 véhicules : contact dans le propriétaire de mécanique')
    return replace_once(html, '</body>', '\n<script id="soma-v75-vehicle-runtime">\n' + MARKER + '\n' + text + '\n</script>\n</body>', 'v75 véhicules : adaptateur après les propriétaires')


def patch_viewer(html, scripts):
    return html
