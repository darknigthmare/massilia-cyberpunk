"""Bounded endpoint-preserving source corridors for the independent viewer."""
import re

MODULES = ('route-corridor-core',)


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Ancre route72 absente ou dupliquée : ' + old[:90])
    return text.replace(old, new, 1)


def rewrite(html, identifier, transform):
    pattern = r'(<script id="' + re.escape(identifier) + r'">)([\s\S]*?)(</script>)'
    matches = list(re.finditer(pattern, html))
    if len(matches) != 1:
        raise ValueError('Script route72 absent ou dupliqué : ' + identifier)
    match = matches[0]
    body = transform(match[2])
    if '</script' in body.lower():
        raise ValueError('Fermeture de script route72 interdite.')
    return html[:match.start(2)] + body + html[match.end(2):]


def runtime(text):
    text = once(text, "let choices=null,markedStart=null,markedWorld=null,arrivalKind='camera';",
                "let choices=null,markedStart=null,markedWorld=null,arrivalKind='camera',corridorStage=0,canExpand=false;")
    text = once(text, "function resetChoices(){choices=null;",
                "function resetChoices(){corridorStage=0;canExpand=false;$('route72-expand').hidden=true;choices=null;")
    text = once(text, "const busy=s.busy||s.phase==='closing';",
                "const busy=s.busy||s.phase==='closing';$('route72-expand').disabled=busy||!canExpand;")
    text = once(text, '        choices=result.axisChoices||null;',
                "        canExpand=result.continuation?.available===true;$('route72-expand').hidden=!canExpand;\n"
                "        choices=result.axisChoices||null;")
    text = once(text, "const q={mode:$('route70-mode').value,avoidSteps:$('route70-avoid-steps').checked};",
                "const q={mode:$('route70-mode').value,avoidSteps:$('route70-avoid-steps').checked,corridorStage};")
    text = once(text, "$('route70-example').onclick=()=>",
                "$('route72-expand').onclick=()=>{if(!canExpand)return;corridorStage=1;canExpand=false;$('route72-expand').hidden=true;void controller.compute(request());};\n    $('route70-example').onclick=()=>")
    text = once(text, "no_route_in_loaded_network:'Aucun itinéraire relié dans le secteur chargé. Le réseau extérieur ou les ouvrages exclus peuvent interrompre ce trajet.',",
                "no_route_in_loaded_network:'Aucun trajet trouvé dans ce corridor source complet. Un détour extérieur ou un ouvrage exclu reste possible.',\n"
                "    corridor_incomplete:'Couverture du corridor limitée : aucun trajet trouvé dans les cellules chargées. Le budget ne permet pas de conclure à une absence de trajet.',\n"
                "    corridor_cell_budget:'Le corridor entre les deux points dépasse le budget de cellules. Élargir le budget ou rapprocher les points.',")
    text = once(text, "if(omitted||missing)$('route70-status').textContent+=' '+omitted+' secteurs hors limite, '+missing+' indisponibles. Rapprocher les points.';",
                "if(omitted||missing)$('route70-status').textContent+=' '+omitted+' cellules hors budget, '+missing+' indisponibles.';\n"
                "        if(canExpand)$('route70-status').textContent+=' Une nouvelle analyse élargie est disponible.';")
    text = once(text, "+count+' secteurs analysés. Couverture locale partielle.'",
                "+count+' cellules analysées dans le corridor. Couverture métropolitaine partielle.'")
    text = once(text, "time_budget:'Analyse interrompue : délai maximal atteint.',",
                "route_output_budget:'Analyse interrompue : budget de restitution des segments atteint.',\n    time_budget:'Analyse interrompue : délai maximal atteint.',")
    return text


def patch_html(html, scripts):
    """The campaign does not acquire a routing reader or state."""
    return html


def patch_viewer(html, scripts):
    source = scripts['route-corridor-core']
    if not isinstance(source, str) or '</script' in source.lower():
        raise ValueError('Script route72 invalide.')
    html = rewrite(html, 'viewer-route-preview70', lambda _: '\n' + source + '\n')
    html = rewrite(html, 'viewer-runtime70', runtime)
    html = once(html, '<button id="route70-cancel"',
                '<button id="route72-expand" type="button" hidden>Élargir le corridor et réessayer</button><button id="route70-cancel"')
    html = once(html, '<canvas id="route70-map"',
                '<p class="fine">Le corridor conserve les deux extrémités et charge au plus 96 cellules ; « Élargir » lance une nouvelle analyse bornée à 192 cellules. Les budgets de mémoire, de fichiers et de recherche restent actifs. Un échec local ne prouve aucune déconnexion du réseau AMP.</p><canvas id="route70-map"')
    return html
