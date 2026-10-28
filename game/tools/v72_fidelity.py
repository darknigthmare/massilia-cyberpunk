"""Source-bound road dimension correction and read-only rendered-road evidence."""
import re

MODULES = ('fidelity-core', 'road-inspector-core', 'road-inspector-runtime')
MARKER = '/* Fidelity72: isolated source width and rendered road ranges. */'


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Ancre fidélité routière absente ou dupliquée : ' + old[:80])
    return text.replace(old, new, 1)


def script(html, identifier):
    found = re.findall(r'<script id="' + re.escape(identifier) + r'">([\s\S]*?)</script>', html)
    if len(found) != 1:
        raise ValueError('Script fidélité absent ou dupliqué : ' + identifier)
    return found[0]


def replace_script(html, identifier, text):
    if '</script' in text.lower():
        raise ValueError('Fermeture de script interdite.')
    return replace_once(html, '<script id="' + identifier + '">' + script(html, identifier) + '</script>',
                        '<script id="' + identifier + '">\n' + text + '\n</script>')


def validated(scripts):
    for name in MODULES:
        if not isinstance(scripts.get(name), str) or not scripts[name].strip() or '</script' in scripts[name].lower():
            raise ValueError('Module fidélité absent ou invalide : ' + name)


def after_script(html, identifier, new_identifier, text):
    original = '<script id="' + identifier + '">' + script(html, identifier) + '</script>'
    return replace_once(html, original, original + '\n<script id="' + new_identifier + '">\n' + text + '\n</script>')


def patch_html(html, scripts):
    validated(scripts)
    if 'id="soma-fidelity72-core"' in html:
        raise ValueError('Correction fidélité déjà injectée.')
    return after_script(html, 'soma-v59-core', 'soma-fidelity72-core', scripts['fidelity-core'])


def patch_geometry(text):
    if MARKER in text:
        raise ValueError('Fidélité routière déjà appliquée.')
    text = replace_once(text, '    const counts=emptyCounts(),inspection71=[];',
                        '    const counts=emptyCounts(),inspection71=[],roads72=[];' + MARKER)
    text = replace_once(text, 'const features=record.featureCollection.features||[],sourceSurfaces=entry.layers.surfaces;',
                        'const features=record.featureCollection.features||[],sourceSurfaces=root.__SOMA_FIDELITY72_CORE__.deriveSurfaces(entry.layers.surfaces,record,projector);')
    old = '''      for(const [kind,triangles]of Object.entries(surfaceCell.surfaces||{}))for(const t of triangles){
        if(Array.isArray(t)&&t.length===3&&t.every(finitePoint))drape(t,colours[kind]||colours.road,levels[kind]||.06,'roadTriangles');
      }'''
    new = '''      for(const [kind,triangles]of Object.entries(surfaceCell.surfaces||{})){
        const start72=values.length/9;
        for(const t of triangles){
          if(Array.isArray(t)&&t.length===3&&t.every(finitePoint))drape(t,colours[kind]||colours.road,levels[kind]||.06,'roadTriangles');
        }
        if(values.length/9>start72)roads72.push({start:start72,end:values.length/9,kind,rendering:'prepared-union',sourceId:null});
      }'''
    text = replace_once(text, old, new)
    text = replace_once(text, '        for(const line of lines)for(let i=1;i<line.length;i++){',
                        '        const start72=values.length/9;\n        for(const line of lines)for(let i=1;i<line.length;i++){')
    text = replace_once(text, "      }else if(layer==='landuse'){",
                        "        if(layer==='roads'&&values.length/9>start72)roads72.push({start:start72,end:values.length/9,kind:profile.unsealed?'unsealed':profile.foot?'foot':'road',rendering:'axis-band',sourceId:id});\n      }else if(layer==='landuse'){")
    if text.count('return root.__SOMA_ARCHITECTURE71_CORE__.attach({vertices:') != 2:
        raise ValueError('Les deux géométries parentes inspectables sont requises.')
    text = text.replace('return root.__SOMA_ARCHITECTURE71_CORE__.attach({vertices:',
                        'return root.__SOMA_ROAD_INSPECTION72_CORE__.attach(root.__SOMA_ARCHITECTURE71_CORE__.attach({vertices:')
    text = replace_once(text, '},inspection71);',
                        '},inspection71),roads72,root.__SOMA_ROAD_INSPECTION72_CORE__.sources(record,useSurfaces?sourceSurfaces:null,F),!!entry.tile.navigation,sourceSurfaces?.fidelity72||[]);')
    return replace_once(text, '},[]);', '},[]),[],{items:[],truncated:false});')


CONTEXT = '''
  function roadInspection72Context(){return Object.freeze({
    available:()=>!!manifest&&!route70Locked,
    acquire:route70Acquire,onWorldChange:route70Context.onWorldChange,
    inspect:()=>root.__SOMA_ROAD_INSPECTION72_CORE__.pickScene({camera:{...camera},
      meshes:[...renderer.registry.meshes].map(([id,item])=>({id,geometry:item.geometry})),visibleCellIds:new Set(targetIds)})
  });}
'''
PANEL = '''
<dialog id="road72-dialog" aria-labelledby="road72-name">
<button id="road72-close" class="close" type="button">Fermer</button><h2 id="road72-name">Inspecter la voirie</h2>
<p id="road72-status" role="status" aria-live="polite">Visez une surface routière visible.</p>
<p id="road72-surface"></p><p id="road72-navigation"></p><div id="road72-candidates"></div>
<p class="fine">Les largeurs déclarées restent des tags source ; les autres largeurs sont des estimations. Les tags d’accès ne certifient ni un passage physique ni un itinéraire autorisé. Ponts, tunnels et accès verticaux non modélisés restent exclus. L’inspection ne charge aucun graphe NAV et ne modifie pas les sauvegardes.</p>
</dialog>'''
STYLE = '''
#road72-dialog{width:750px;line-height:1.5}#road72-candidates{display:grid;gap:14px}#road72-candidates article{background:#102630;border:1px solid #34545c;padding:14px}#road72-candidates h3{margin-top:0}#road72-candidates p{overflow-wrap:anywhere}#road72-candidates table{width:100%;margin:12px 0;border-collapse:collapse;font-size:12px}#road72-candidates th,#road72-candidates td{text-align:left;padding:6px;border-bottom:1px solid #25434b;overflow-wrap:anywhere}#road72-candidates th{font-weight:500;color:#8db8b0}#road72-candidates a{display:inline-block;margin-top:12px;color:#8de2dd;text-underline-offset:3px}#road72-candidates summary{cursor:pointer}
'''


def patch_viewer(html, scripts):
    validated(scripts)
    if 'id="viewer-fidelity72-core"' in html:
        raise ValueError('Inspecteur routier déjà injecté.')
    html = after_script(html, 'viewer-dimension-core', 'viewer-fidelity72-core', scripts['fidelity-core'])
    geometry = patch_geometry(script(html, 'viewer-metropole-viewer-core'))
    controller = script(html, 'viewer-metropole-viewer')
    controller = replace_once(controller, '  function multiply(a,b){', CONTEXT + '\n  function multiply(a,b){')
    controller = replace_once(controller, '        architectureContext:architecture71Context,',
                              '        roadInspectionContext:roadInspection72Context,architectureContext:architecture71Context,')
    html = replace_script(html, 'viewer-metropole-viewer-core', geometry)
    html = replace_script(html, 'viewer-metropole-viewer', controller)
    html = replace_once(html, '<script id="viewer-metropole-viewer-core">',
                        '<script id="viewer-road72-core">\n' + scripts['road-inspector-core'] + '\n</script>\n<script id="viewer-metropole-viewer-core">')
    html = replace_once(html, '</body>', '<script id="viewer-road72-runtime">\n' + scripts['road-inspector-runtime'] + '\n</script>\n</body>')
    html = replace_once(html, '<button id="open-help">', '<button id="road72-open" type="button" title="Inspecter la surface routière sous le réticule · J">Inspecter la voirie</button><button id="open-help">')
    html = replace_once(html, '<dialog id="help-dialog">', PANEL + '\n<dialog id="help-dialog">')
    return replace_once(html, '</style>', STYLE + '</style>')
