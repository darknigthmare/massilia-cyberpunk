"""Keep read-only road candidates on the source sidewalk's declared side.

The independent flyover geometry and frozen native navigation are unchanged.
"""
from build_v68 import replace_once, rewrite_script

MODULES = ('navigation-core',)
MARKER = '/* Navigation77: directed source-side road inspection. */'


def patch_inspector(body):
    start = body.find('  function candidate(source,point,kind){')
    end = body.find('  function boxHit(', start)
    if start < 0 or end <= start or body.count('  function candidate(source,point,kind){') != 1:
        raise ValueError('Inspecteur voirie72 absent ou ambigu.')
    if MARKER in body:
        raise ValueError('Correction voirie77 déjà appliquée.')
    replacement = ('  function candidate(source,point,kind){\n'
                   '    ' + MARKER + '\n'
                   '    return root.__SOMA_NAVIGATION77_CORE__.candidate(source,point,kind);\n'
                   '  }\n')
    return body[:start] + replacement + body[end:]


def patch_html(html, scripts):
    return html


def patch_viewer(html, scripts):
    source = scripts.get('navigation-core')
    if not isinstance(source, str) or not source.strip() or '</script' in source.lower():
        raise ValueError('Module voirie77 absent ou invalide.')
    if 'id="viewer-navigation77-core"' in html:
        raise ValueError('Module voirie77 déjà appliqué.')
    html = rewrite_script(html, 'viewer-road72-core', patch_inspector)
    return replace_once(html, '<script id="viewer-road72-core">',
                        '<script id="viewer-navigation77-core">\n' + source + '\n</script>\n'
                        '<script id="viewer-road72-core">', 'voirie77 avant son inspecteur propriétaire')
