"""Derive source-axis presentation; frozen v70 sources stay byte-identical."""
import re

MODULES = ('route-presentation-core', 'viewer-route-runtime')


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Ancre route71 absente ou dupliquée : ' + old[:90])
    return text.replace(old, new, 1)


def rewrite(html, identifier, transform):
    pattern = r'(<script id="' + re.escape(identifier) + r'">)([\s\S]*?)(</script>)'
    matches = list(re.finditer(pattern, html))
    if len(matches) != 1:
        raise ValueError('Script route71 absent ou dupliqué : ' + identifier)
    m = matches[0]
    body = transform(m[2])
    if '</script' in body.lower():
        raise ValueError('Fermeture de script route71 interdite.')
    return html[:m.start(2)] + body + html[m.end(2):]


CONTEXT = r'''
  let route71Record=null,route71Revision=0,route71Summary={renderedSpans:0,geometryBytes:0};
  function route71Set(result){
    route71Record=result?root.__SOMA_ROUTE71_PRESENTATION__.record(result,manifest):null;
    route71Revision++;renderer?.clearRoute71?.();route71Summary={renderedSpans:0,geometryBytes:0};
    const badge=$('route71-overlay-status');if(badge){badge.hidden=!route71Record;badge.textContent=route71Record?'Repères prêts au retour au survol.':'';}
  }
  function route71Span(b){
    if(!manifest)return false;
    const x0=Math.round((b.minE-manifest.origin[0])/250),x1=Math.round((b.maxE-manifest.origin[0])/250),
      y0=Math.round((manifest.origin[1]-b.maxN)/250),y1=Math.round((manifest.origin[1]-b.minN)/250);
    if(x1-x0>2||y1-y0>2)return false;
    for(let x=x0;x<=x1;x++)for(let y=y0;y<=y1;y++){
      const tile=worldIndex.cellAt(manifest.origin[0]+250*x,manifest.origin[1]-250*y);
      if(!tile||tile.terrain?.complete!==true||!targetIds.has(tile.cellId)||!renderer.registry.meshes.has(tile.cellId))return false;
    }
    return true;
  }
  function route71Terrain(b){
    if(!route71Span(b))return [];
    const triangles=[],x0=Math.round((b.minE-manifest.origin[0])/250),x1=Math.round((b.maxE-manifest.origin[0])/250),
      y0=Math.round((manifest.origin[1]-b.maxN)/250),y1=Math.round((manifest.origin[1]-b.minN)/250);
    for(let x=x0;x<=x1;x++)for(let y=y0;y<=y1;y++){
      const tile=worldIndex.cellAt(manifest.origin[0]+250*x,manifest.origin[1]-250*y),g=renderer.registry.meshes.get(tile.cellId).token.layers.terrain.grid;
      const left=Math.max(0,Math.round((tile.boundsL93[0]-g.x0)/g.step),Math.floor((b.minE-g.x0)/g.step)),
        right=Math.min(g.cols-2,Math.round((tile.boundsL93[2]-g.x0)/g.step)-1,Math.floor((b.maxE-g.x0)/g.step)),
        top=Math.max(0,Math.round((g.n0-tile.boundsL93[3])/g.step),Math.floor((g.n0-b.maxN)/g.step)),
        bottom=Math.min(g.rows-2,Math.round((g.n0-tile.boundsL93[1])/g.step)-1,Math.floor((g.n0-b.minN)/g.step));
      if(left>right||top>bottom)continue;
      const bounds=[g.x0+left*g.step,g.n0-(bottom+1)*g.step,g.x0+(right+1)*g.step,g.n0-top*g.step],
        e=(bounds[0]+bounds[2])/2,n=(bounds[1]+bounds[3])/2;
      g.cellTriangles(bounds,t=>triangles.push(t.map(p=>[e+p[0],n-p[2],p[1]])));
    }
    return triangles;
  }
'''

DRAW = r'''
      const routeKey=route71Revision+'|'+generation+'|'+[...registry.meshes.keys()].filter(id=>targetIds.has(id)).sort().join(',');
      if(routeKey!==route71Key){
        clearRoute71();route71Key=routeKey;
        if(route71Record){
          const shape=root.__SOMA_ROUTE71_PRESENTATION__.buildOverlay(route71Record,{terrainTriangles:route71Terrain,spanAvailable:route71Span});
          const {vertices,...summary}=shape;route71Summary=summary;
          if(vertices.length)route71Mesh={handle:driver.upload(vertices),center:shape.centerL93};
          const badge=$('route71-overlay-status');if(badge){badge.hidden=false;badge.textContent=Math.round(shape.renderedMeters)+' m de repères sur le relief affiché'+(shape.truncated?' · limite de repères atteinte':'')+(shape.omittedSpans?' · affichage partiel':'');}
        }
      }
      if(route71Mesh){const center=route71Mesh.center;gl.uniform3f(loc.tile,center[0]-origin[0],0,origin[1]-center[1]);
        gl.bindVertexArray(route71Mesh.handle.vao);gl.drawArrays(gl.TRIANGLES,0,route71Mesh.handle.count);}
'''


def controller(text):
    text = once(text, '  function multiply(a,b){', CONTEXT + '\n  function multiply(a,b){')
    text = once(text, '    camera:()=>({e:camera.e,n:camera.n,h:camera.h}),world:()=>manifest,',
                '    setRoutePresentation:route71Set,routePresentationSnapshot:()=>({...route71Summary,active:!!route71Record}),\n'
                '    camera:()=>({e:camera.e,n:camera.n,h:camera.h}),world:()=>manifest,')
    text = once(text, '    const registry=sceneRegistry(driver),errorCodes=[];',
                '    const registry=sceneRegistry(driver),errorCodes=[];let route71Mesh=null,route71Key="";\n'
                '    function clearRoute71(){if(route71Mesh)driver.release(route71Mesh.handle);route71Mesh=null;route71Key="";}')
    text = once(text, '    return {gl,registry,errorCodes,draw(){', '    return {gl,registry,errorCodes,clearRoute71,draw(){')
    text = once(text, '      renderedFrames++;collectErrors();', DRAW + '\n      renderedFrames++;collectErrors();')
    text = once(text, 'stop(){worldLoader.cancel();', 'stop(){route71Set(null);worldLoader.cancel();')
    return text


def runtime(text):
    text = once(text, "clear(){plot(canvas,null);$('route70-projections').textContent='';},",
                "clear(){plot(canvas,null);$('route70-projections').textContent='';root.__SOMA_ROUTE71_RUNTIME__?.clear();},")
    text = once(text, "option.textContent='Voie OSM '+q.wayId+' · '+q.distanceMeters.toFixed(2)+' m du point';",
                'option.textContent=root.__SOMA_ROUTE71_PRESENTATION__.choiceLabel(q);')
    text = once(text, '        plot(canvas,result);',
                '        plot(canvas,result);root.__SOMA_ROUTE71_RUNTIME__?.render(result);')
    text = once(text, "version:'0.70.0',...state", "version:'0.71.0',...state")
    return text


def script(name, scripts):
    text = scripts[name]
    if not isinstance(text, str) or '</script' in text.lower():
        raise ValueError('Script de présentation71 invalide.')
    return f'<script id="viewer-{name}71">\n{text}\n</script>\n'


def patch_html(html, scripts):
    """The route presentation belongs only to the independent flyover."""
    return html


def patch_viewer(html, scripts):
    html = rewrite(html, 'viewer-metropole-viewer', controller)
    html = rewrite(html, 'viewer-runtime70', runtime)
    html = rewrite(html, 'viewer-route-preview70', lambda text: once(text,
        'wayId:g.edges[q.edge][2],segmentIndex:g.edgeSources[q.edge].segmentIndex,',
        "wayId:g.edges[q.edge][2],name:typeof g.ways[g.edges[q.edge][2]].name==='string'?g.ways[g.edges[q.edge][2]].name:null,steps:g.edges[q.edge][5]===1,segmentIndex:g.edgeSources[q.edge].segmentIndex,"))
    html = once(html, '<script id="viewer-metropole-viewer">',
                script('route-presentation-core', scripts) + '<script id="viewer-metropole-viewer">')
    html = once(html, '</body>', script('viewer-route-runtime', scripts) + '</body>')
    html = once(html, '<h2 id="route70-title">Itinéraire local · 0.70</h2>',
                '<h2 id="route70-title">Itinéraire local · 0.71</h2>')
    html = once(html, '<canvas id="route70-map"', '<label><input id="route71-show3d" type="checkbox" checked> Afficher les repères du trajet en 3D</label>'
                '<p class="fine">Au retour au survol, seuls les axes situés sur du relief complet déjà affiché portent des repères cyan. Les secteurs absents ou partiels restent sans tracé ; aucun accès physique n’est certifié.</p>'
                '<h3>Voies empruntées</h3><ol id="route71-steps"></ol><canvas id="route70-map"')
    html = once(html, '<button id="route70-open"', '<button id="route71-clear" type="button" disabled>Effacer le trajet</button><button id="route70-open"')
    html = once(html, '<dialog id="help-dialog">', '<aside id="route71-overlay-status" hidden role="status" aria-live="polite"></aside><dialog id="help-dialog">')
    html = once(html, '</style>', '#route71-overlay-status{position:fixed;right:18px;bottom:18px;max-width:300px;padding:10px;background:#092027e8;border:1px solid #4b9e98;font:12px monospace;color:#8df1df;pointer-events:none}#route71-overlay-status[hidden]{display:none}#route71-steps{max-height:240px;overflow:auto;padding-left:24px}#route71-steps li{margin:7px 0}' + '</style>')
    return html
