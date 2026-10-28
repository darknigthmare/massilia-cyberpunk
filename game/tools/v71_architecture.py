"""Read-only architectural evidence, derived from the frozen v70 flyover."""
import re


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Ancre architecturale absente ou dupliquée : ' + old[:80])
    return text.replace(old, new, 1)


def replace_script(html, identifier, text):
    if '</script' in text.lower():
        raise ValueError('Fermeture de script interdite : ' + identifier)
    pattern = r'<script id="' + re.escape(identifier) + r'">[\s\S]*?</script>'
    if len(re.findall(pattern, html)) != 1:
        raise ValueError('Script architectural absent ou dupliqué : ' + identifier)
    return re.sub(pattern, lambda _: '<script id="' + identifier + '">\n' + text + '\n</script>', html)

MODULES = ('architecture-inspector-core', 'architecture-inspector-runtime')
MARKER = '/* Architecture71: rendered triangles retain source evidence. */'


def patch_html(html, scripts):
    """Campaign geometry and persistence are deliberately unchanged."""
    return html


def _script(html, identifier):
    pattern = r'<script id="' + re.escape(identifier) + r'">([\s\S]*?)</script>'
    matches = re.findall(pattern, html)
    if len(matches) != 1:
        raise ValueError('Script architectural absent ou dupliqué : ' + identifier)
    return matches[0]


def patch_geometry(text):
    if MARKER in text:
        raise ValueError('Métadonnées architecturales déjà appliquées.')
    text = replace_once(text, '    const counts=emptyCounts();',
                        '    const counts=emptyCounts(),inspection71=[];' + MARKER)
    text = replace_once(text, "        for(const mesh of meshes){\n          const triangles=mesh.trianglesL93.map(t=>t.map(local));",
                        "        const startVertex71=values.length/9;\n        for(const mesh of meshes){\n          const triangles=mesh.trianglesL93.map(t=>t.map(local));")
    text = replace_once(text, '}counts.buildings++;',
                        '}if(values.length/9>startVertex71)inspection71.push({start:startVertex71,end:values.length/9,facts:root.__SOMA_ARCHITECTURE71_CORE__.facts(p,dim,plan,material,record,base)});counts.buildings++;')
    text = replace_once(text,
                        'return {vertices:new Float32Array(values),counts,boundsL93:bounds,centerL93,geometryBytes:values.length*4,',
                        'return root.__SOMA_ARCHITECTURE71_CORE__.attach({vertices:new Float32Array(values),counts,boundsL93:bounds,centerL93,geometryBytes:values.length*4,')
    text = replace_once(text, 'not a water-level survey\'};', "not a water-level survey'},inspection71);")
    text = replace_once(text,
                        'return {vertices:new Float32Array(values),counts,boundsL93:bounds.slice(),centerL93,geometryBytes:values.length*4,',
                        'return root.__SOMA_ARCHITECTURE71_CORE__.attach({vertices:new Float32Array(values),counts,boundsL93:bounds.slice(),centerL93,geometryBytes:values.length*4,')
    return replace_once(text, "facadePolicy:'No vector coverage: buildings, roads and facades are not modelled'};",
                        "facadePolicy:'No vector coverage: buildings, roads and facades are not modelled'},[]);")


CONTEXT = '''
  function architecture71Context(){return Object.freeze({
    available:()=>!!manifest&&!route70Locked,
    acquire:route70Acquire,onWorldChange:route70Context.onWorldChange,
    inspect:()=>root.__SOMA_ARCHITECTURE71_CORE__.pickScene({camera:{...camera},
      meshes:[...renderer.registry.meshes].map(([id,item])=>({id,geometry:item.geometry})),visibleCellIds:new Set(targetIds)})
  });}
'''

PANEL = '''
<dialog id="architecture71-dialog" aria-labelledby="architecture71-name">
<button id="architecture71-close" class="close" type="button">Fermer</button><h2 id="architecture71-name">Inspecter un bâtiment</h2>
<p id="architecture71-status" role="status" aria-live="polite">Visez une façade ou un toit visible, puis utilisez I ou le bouton d’inspection.</p>
<dl id="architecture71-facts"></dl>
<a id="architecture71-source" class="button" href="https://www.openstreetmap.org/" target="_blank" rel="noopener noreferrer" hidden>Voir l’objet sur OpenStreetMap</a>
<details><summary>Tags présents dans la source OSM</summary><table><tbody id="architecture71-tags"></tbody></table></details>
<p class="fine">Cette fiche décrit le modèle affiché et ses sources. La précision architecturale 1:1, les façades, les détails de toiture et l’accès physique ne sont pas certifiés. L’inspection ne modifie ni la géographie ni les sauvegardes.</p>
</dialog>'''
STYLE = '''
#architecture71-dialog{width:750px;line-height:1.5}#architecture71-facts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}#architecture71-facts>div{background:#102630;border:1px solid #34545c;padding:12px}#architecture71-facts dt{color:#89dcd0;font-weight:600}#architecture71-facts dd{margin:7px 0 0}#architecture71-facts small{display:block;color:#a4bdb8;font-size:12px;margin-top:5px}#architecture71-dialog details{margin-top:20px}#architecture71-dialog summary{cursor:pointer}#architecture71-dialog table{width:100%;margin:12px 0;border-collapse:collapse;font-size:12px}#architecture71-dialog th,#architecture71-dialog td{text-align:left;padding:6px;border-bottom:1px solid #25434b;overflow-wrap:anywhere}#architecture71-dialog th{font-weight:500;color:#8db8b0}#architecture71-source[hidden]{display:none}@media(max-width:650px){#architecture71-facts{grid-template-columns:1fr}}
'''


def patch_viewer(html, scripts):
    if 'id="viewer-architecture71-core"' in html:
        raise ValueError('Inspecteur architectural déjà injecté.')
    for name in MODULES:
        if name not in scripts or '</script' in scripts[name].lower():
            raise ValueError('Module architectural absent ou invalide : ' + name)
    geometry = patch_geometry(_script(html, 'viewer-metropole-viewer-core'))
    controller = _script(html, 'viewer-metropole-viewer')
    controller = replace_once(controller, '  function multiply(a,b){', CONTEXT + '\n  function multiply(a,b){')
    controller = replace_once(controller, '        narrowContext:()=>route70Context,',
                              '        architectureContext:architecture71Context,narrowContext:()=>route70Context,')
    html = replace_script(html, 'viewer-metropole-viewer-core', geometry)
    html = replace_script(html, 'viewer-metropole-viewer', controller)
    html = replace_once(html, '<script id="viewer-metropole-viewer-core">',
                        '<script id="viewer-architecture71-core">\n' + scripts[MODULES[0]] + '\n</script>\n<script id="viewer-metropole-viewer-core">')
    html = replace_once(html, '</body>', '<script id="viewer-architecture71-runtime">\n' + scripts[MODULES[1]] + '\n</script>\n</body>')
    html = replace_once(html, '<button id="open-help">', '<button id="architecture71-open" type="button" title="Inspecter le bâtiment sous le réticule · I">Inspecter le bâtiment</button><button id="open-help">')
    html = replace_once(html, '<dialog id="help-dialog">', PANEL + '\n<dialog id="help-dialog">')
    return replace_once(html, '</style>', STYLE + '</style>')
