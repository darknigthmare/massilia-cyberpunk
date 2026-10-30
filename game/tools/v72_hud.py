"""Compose the current campaign HUD without modifying its frozen owners."""
from build_v68 import replace_once

MODULES = ('hud-layout-runtime',)
SCRIPT_ID = 'soma-v72-hud-layout-runtime'


def patch_html(html, scripts):
    if f'id="{SCRIPT_ID}"' in html:
        raise ValueError('Disposition du HUD v72 déjà appliquée.')
    text = scripts.get(MODULES[0])
    if not isinstance(text, str) or not text.strip() or '</script' in text.lower():
        raise ValueError('Module de disposition du HUD v72 invalide.')
    if html.count('<div class="hud">') != 1:
        raise ValueError('Conteneur du HUD parent absent ou ambigu.')
    return replace_once(html, '</body>',
        f'\n<script id="{SCRIPT_ID}">\n' + text + '\n</script>\n</body>',
        'disposition du HUD v72 après ses propriétaires')
