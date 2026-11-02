"""Source-clipped pitched roof frames layered over the frozen v72 edition."""
import re

MODULES = ('roof-fidelity-core',)


def _inject(html, scripts, parent, identifier):
    source = scripts.get(MODULES[0])
    if not isinstance(source, str) or not source.strip() or '</script' in source.lower():
        raise ValueError('Module de toiture v73 absent ou invalide.')
    if 'id="' + identifier + '"' in html:
        raise ValueError('Fidélité de toiture v73 déjà injectée.')
    pattern = r'<script id="' + re.escape(parent) + r'">[\s\S]*?</script>'
    matches = list(re.finditer(pattern, html))
    if len(matches) != 1:
        raise ValueError('Script de toiture parent absent ou dupliqué : ' + parent)
    end = matches[0].end()
    return html[:end] + '\n<script id="' + identifier + '">\n' + source + '\n</script>' + html[end:]


def patch_html(html, scripts):
    return _inject(html, scripts, 'soma-v69-roof-core', 'soma-roof-fidelity73-core')


def patch_viewer(html, scripts):
    return _inject(html, scripts, 'viewer-roof-core', 'viewer-roof-fidelity73-core')
