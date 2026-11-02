"""Derive optional geographic corridor guidance from the frozen v72 viewer.

The guide selects authenticated NAV files. It never inserts a graph edge or
requires the returned source route to pass through the guide position.
"""
import re

MODULES = ('route-guided-core',)


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Ancre route73 absente ou dupliquée : ' + old[:90])
    return text.replace(old, new, 1)


def rewrite(html, identifier, transform):
    pattern = r'(<script id="' + re.escape(identifier) + r'">)([\s\S]*?)(</script>)'
    matches = list(re.finditer(pattern, html))
    if len(matches) != 1:
        raise ValueError('Script route73 absent ou dupliqué : ' + identifier)
    match = matches[0]
    body = transform(match[2])
    if '</script' in body.lower():
        raise ValueError('Fermeture de script route73 interdite.')
    return html[:match.start(2)] + body + html[match.end(2):]


def runtime(text):
    text = once(text, "arrivalKind='camera',corridorStage=0,canExpand=false;",
                "arrivalKind='camera',corridorStage=0,canExpand=false,markedGuide=null,guideWorld=null;")
    text = once(text, "    const validPoints=()=>validPoint(readPoint('start'))&&validPoint(readPoint('end'));",
                "    function readGuide(){return ['e','n'].every(axis=>$('route70-guide-'+axis).value.trim()==='')?null:readPoint('guide');}\n"
                "    const validGuide=()=>readGuide()===null||validPoint(readGuide());\n"
                "    const validPoints=()=>validPoint(readPoint('start'))&&validPoint(readPoint('end'))&&validGuide();")
    text = once(text, "+(b?' · '+b:'');", "+(b?' · '+b:'')+(readGuide()?' · guide du corridor '+(validGuide()?(place(readGuide())||'défini'):'invalide'):' · corridor direct');")
    text = once(text, "    function fill(request){", "    function fill(request){\n      markedGuide=null;guideWorld=null;setPoint('guide',null);")
    text = once(text, "['route70-mark-start','route70-example','route70-camera-start','route70-camera-end']",
                "['route70-mark-start','route70-example','route70-camera-start','route70-camera-end','route73-mark-guide','route73-clear-guide']")
    text = once(text, "['route70-start-e','route70-start-n','route70-end-e','route70-end-n','route70-mode'",
                "['route70-guide-e','route70-guide-n','route70-start-e','route70-start-n','route70-end-e','route70-end-n','route70-mode'")
    text = once(text, "        if(markedWorld!==context.world()){markedStart=null;markedWorld=null;}",
                "        if(markedWorld!==context.world()){markedStart=null;markedWorld=null;}\n"
                "        if(guideWorld!==context.world()){markedGuide=null;guideWorld=null;}setPoint('guide',markedGuide);")
    text = once(text, "      markedStart={e:p.e,n:p.n};markedWorld=context.world();setPoint('start',markedStart);",
                "      markedGuide=null;guideWorld=null;setPoint('guide',null);\n"
                "      markedStart={e:p.e,n:p.n};markedWorld=context.world();setPoint('start',markedStart);")
    text = once(text, "avoidSteps:$('route70-avoid-steps').checked,corridorStage};",
                "avoidSteps:$('route70-avoid-steps').checked,corridorStage};\n      const guide=readGuide();if(guide)q.corridorGuide={e:guide.e,n:guide.n};")
    text = once(text, "    $('route72-expand').onclick=()=>",
                "    $('route73-mark-guide').onclick=()=>{const p=context.camera();if(!validPoint(p))return;markedGuide={e:p.e,n:p.n};guideWorld=context.world();setPoint('guide',markedGuide);resetChoices();updateSummary();void controller.close();};\n"
                "    $('route73-clear-guide').onclick=()=>{markedGuide=null;guideWorld=null;setPoint('guide',null);resetChoices();updateSummary();};\n"
                "    for(const axis of ['e','n'])$('route70-guide-'+axis).oninput=()=>{markedGuide=readGuide();guideWorld=context.world();resetChoices();updateSummary();};\n"
                "    $('route72-expand').onclick=()=>")
    text = once(text, "markers:{start:markedStart?{...markedStart}:null,arrival:",
                "markers:{corridorGuide:markedGuide?{...markedGuide}:null,guideIsRouteWaypoint:false,start:markedStart?{...markedStart}:null,arrival:")
    return text


GUIDE_UI = '''<fieldset><legend>Guider le corridor (facultatif)</legend>
<button id="route73-mark-guide" type="button">Guider le corridor par ici</button><button id="route73-clear-guide" type="button">Retirer le guide</button>
<p class="fine">Pour explorer un détour, volez près du secteur souhaité puis marquez ce guide. Le panneau se ferme ; volez ensuite à l’arrivée. Le guide infléchit le corridor des cellules analysées : ce n’est pas une étape imposée au trajet et aucun raccord n’est créé.</p>
<div class="route70-row"><label>Guide · Est (Lambert-93)<input id="route70-guide-e" type="number" step="any"></label><label>Nord<input id="route70-guide-n" type="number" step="any"></label></div></fieldset>'''


def patch_html(html, scripts):
    """Campaign remains byte-identical; routing belongs to the flyover."""
    return html


def patch_viewer(html, scripts):
    source = scripts['route-guided-core']
    if not isinstance(source, str) or '</script' in source.lower():
        raise ValueError('Script route73 invalide.')
    html = rewrite(html, 'viewer-route-preview70', lambda _: '\n' + source + '\n')
    html = rewrite(html, 'viewer-runtime70', runtime)
    html = once(html, '<form id="route70-form">', GUIDE_UI + '<form id="route70-form">')
    html = once(html, 'Le corridor conserve les deux extrémités et charge au plus 96 cellules',
                'Le corridor direct ou guidé conserve les deux extrémités et charge au plus 96 cellules')
    return html
