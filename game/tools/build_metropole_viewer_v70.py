#!/usr/bin/env python3
"""Derive the independent 0.70 flyover from the verified 0.69 builder.

Only metadata queries, declared appearance and an optional local route analysis
are extended. The frozen controller, geometry, campaign and sources stay intact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_metropole_viewer as V69

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'metropole-viewer-v70.html'
CORE_SHA256 = 'd2dc3ea29f653a066e3a812b7db3b79c0c8bb81cb97319ad888618048f37d9ae'


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Ancre 0.69 absente, dupliquée ou modifiée : ' + old[:90])
    return text.replace(old, new, 1)


# This lease owns only the independent flyover. Before NAV may read a file,
# scene requests (including surface upgrades) must have completely drained.
# While held, no movement, teleport, world switch or target update can start
# another scene request. Release awaits aborted readers before movement resumes.
CONTEXT = r'''
  let route70Locked=false,route70Lease=null,route70Ready=false;
  const route70Reads=new Set(),world70Listeners=new Set();
  const route70Abort=()=>Object.assign(new Error('Analyse locale annulée.'),{name:'AbortError'});
  async function route70Acquire({signal}={}){
    if(route70Locked)throw new Error('Une analyse locale possède déjà le survol.');
    const token={};route70Locked=true;route70Lease=token;route70Ready=false;releaseMouse();
    let abort;
    const cancelled=new Promise((_,reject)=>{abort=()=>reject(route70Abort());signal?.addEventListener('abort',abort,{once:true});});
    try{
      if(signal?.aborted)throw route70Abort();
      await Promise.race([worldPromise.then(()=>requestPromise),cancelled]);
      if(signal?.aborted||route70Lease!==token)throw route70Abort();
      while(store&&(store.snapshot().running||store.snapshot().queued)){
        if(signal?.aborted||route70Lease!==token)throw route70Abort();
        await Promise.race([new Promise(resolve=>setTimeout(resolve,25)),cancelled]);
      }
      const stats=store?.snapshot();
      if(!store||!manifest||stats.running||stats.queued)throw new Error('Les chargements de la scène ne sont pas encore terminés.');
      route70Ready=true;
      return Object.freeze({async release(){
        if(route70Lease!==token)return;
        route70Ready=false;await Promise.allSettled([...route70Reads]);
        if(route70Lease===token){route70Lease=null;route70Locked=false;keys.clear();lastUpdate=performance.now();}
      }});
    }catch(error){if(route70Lease===token){route70Lease=null;route70Locked=false;route70Ready=false;}throw error;}
    finally{signal?.removeEventListener('abort',abort);}
  }
  async function route70Read(descriptor,settings){
    if(!route70Locked||!route70Ready||route70Reads.size)throw new Error('Lecture NAV hors de son créneau exclusif.');
    const stats=store?.snapshot();if(!stats||stats.running||stats.queued)throw new Error('La scène utilise encore le réseau.');
    const base=new URL('.',manifestURL),url=new URL(descriptor.path,base);
    if(!['http:','https:'].includes(base.protocol)||url.origin!==base.origin||!url.pathname.startsWith(base.pathname))throw new Error('Fichier NAV hors du monde courant.');
    const task=readBytes(url,settings.maxEncodedBytes,{signal:settings.signal});route70Reads.add(task);
    try{return await task;}finally{route70Reads.delete(task);}
  }
  const route70Context=Object.freeze({
    camera:()=>({e:camera.e,n:camera.n,h:camera.h}),world:()=>manifest,manifestURL:()=>manifestURL,index:()=>worldIndex,
    whenSceneStable:()=>worldPromise.then(()=>requestPromise),acquireRouteLease:route70Acquire,readRouteAsset:route70Read,
    onWorldChange(listener){if(typeof listener!=='function')throw new TypeError('Écouteur requis.');world70Listeners.add(listener);return()=>world70Listeners.delete(listener);},
    snapshot:()=>({locked:route70Locked,sceneStable:route70Ready,navigationReads:route70Reads.size,
      sceneRunning:store?.snapshot().running||0,sceneQueued:store?.snapshot().queued||0,maximumGlobalRequests:2})
  });
'''


def derive_controller(text):
    edits = [
        ('Geometry=root.__SOMA_METRO_VIEW_CORE__;', 'Geometry=root.__SOMA_METRO_VIEW_CORE__,Index=root.__SOMA_WORLD70_INDEX__;'),
        ("let store=null,manifest=null,manifestURL=null,mode=''", "let worldIndex=null;\n  let store=null,manifest=null,manifestURL=null,mode=''"),
        ('  function multiply(a,b){', CONTEXT + '\n  function multiply(a,b){'),
        ('function cellAt(e,n){const x=Math.round((e-manifest.origin[0])/250),y=Math.round((manifest.origin[1]-n)/250);return manifest.tiles.find(t=>t.gridX===x&&t.gridY===y)||null;}',
         'function cellAt(e,n){return worldIndex?.cellAt(e,n)||null;}'),
        ('    if(!store)return Promise.resolve();', '    if(!store||route70Locked)return requestPromise;'),
        ('wanted=desiredTiles(manifest,camera.e,camera.n)', 'wanted=worldIndex.desiredTiles(camera.e,camera.n)'),
        ('function inCommune(e,n,commune){return commune.polygons.some(poly=>inside([e,n],poly[0])&&!poly.slice(1).some(r=>inside([e,n],r)));}',
         'function inCommune(e,n,commune){return worldIndex?.containsCommune(commune.code,e,n)||false;}'),
        ('function communeAt(e,n){return communes.find(c=>inCommune(e,n,c));}', 'function communeAt(e,n){return worldIndex?.communeAt(e,n)||null;}'),
        ('    if(!Number.isFinite(e)||!Number.isFinite(n))return false;', '    if(route70Locked||!Number.isFinite(e)||!Number.isFinite(n))return false;'),
        ("      if(!safeWorldPath(relative))throw new Error('Le chemin du manifeste doit être un fichier JSON relatif sûr.');",
         "      if(route70Locked)throw new Error('Fermer l’itinéraire local avant de changer de monde.');\n      if(!safeWorldPath(relative))throw new Error('Le chemin du manifeste doit être un fichier JSON relatif sûr.');"),
        ('      const nextManifest=S.validateManifest(raw),nextParts=await loadBuildingParts(nextManifest,url.href,',
         '      const nextManifest=S.validateManifest(raw),nextIndex=Index.createWorldIndex(nextManifest,{communes,projectWGS84:G.forward,instrument:true}),nextParts=await loadBuildingParts(nextManifest,url.href,'),
        ("      const start=available.slice().sort((a,b)=>Math.hypot((a.boundsL93[0]+a.boundsL93[2])/2-892100,(a.boundsL93[1]+a.boundsL93[3])/2-6247000)-Math.hypot((b.boundsL93[0]+b.boundsL93[2])/2-892100,(b.boundsL93[1]+b.boundsL93[3])/2-6247000))[0];",
         '      const start=nextIndex.nearestTile(892100,6247000,{radiusM:4000})||available[0];'),
        ('return {nextManifest,nextParts,nextStore,start,url:url.href,sourceMode};', 'return {nextManifest,nextIndex,nextParts,nextStore,start,url:url.href,sourceMode};'),
        ('      manifest=next.nextManifest;parts=next.nextParts;', '      manifest=next.nextManifest;worldIndex=next.nextIndex;parts=next.nextParts;'),
        ('      return {request:requestPromise};', '      for(const listener of world70Listeners)listener();\n      return {request:requestPromise};'),
        ("blocked=$('map-dialog').open||$('help-dialog').open||$('error').hidden===false;", "blocked=route70Locked||$('map-dialog').open||$('help-dialog').open||$('error').hidden===false;"),
        ('    if(store&&now-lastCellUpdate>180)', '    if(store&&!route70Locked&&now-lastCellUpdate>180)'),
        ('    buildOne();renderer.draw();if(store)hud(now);frame=requestAnimationFrame(animate);',
         '    if(!route70Locked){buildOne();renderer.draw();if(store)hud(now);}frame=requestAnimationFrame(animate);'),
        ("navigationRequired:false,campaignPersistenceLoaded:false,webglError:", "version:'0.70.0',worldIndex:worldIndex?.snapshot()||null,routeAnalysis:route70Context.snapshot(),navigationRequired:false,campaignPersistenceLoaded:false,webglError:"),
        ('        teleportCommune,refresh:()=>updateTarget(true),ready:', '        narrowContext:()=>route70Context,teleportCommune,refresh:()=>updateTarget(true),ready:'),
        ("      function lock(){if($('error').hidden!==false)", "      function lock(){if(!route70Locked&&$('error').hidden!==false)"),
        ("root.addEventListener('mousemove',event=>{if(document.pointerLockElement===$('scene')||dragging)", "root.addEventListener('mousemove',event=>{if(!route70Locked&&(document.pointerLockElement===$('scene')||dragging))"),
        ("root.addEventListener('keydown',event=>{if(event.code==='Escape')", "root.addEventListener('keydown',event=>{if(route70Locked)return;if(event.code==='Escape')"),
    ]
    for old, new in edits:
        text = replace_once(text, old, new)
    start = text.index('  function teleportCommune(code){')
    end = text.index('  function nearestRoad(){', start)
    old = text[start:end]
    if old.count('manifest.tiles.filter(') != 1 or old.count('if(teleportMetric(...point))') != 1:
        raise ValueError('La destination de commune 0.69 a changé.')
    text = replace_once(text, old, '''  function teleportCommune(code){
    if(route70Locked)return false;
    const destination=worldIndex?.destination(code),commune=destination?.commune;
    if(!destination?.available){$('map-description').textContent='Aucun secteur de survol disponible près de cette localité.';return false;}
    $('map-description').textContent=(commune.anchorSource==='osm-place-node'?'Localité OSM vérifiée : ':'Repère de contour : ')+commune.name+
      (destination.fallback?' · cellule source voisine dans la même commune.':'.');
    if(teleportMetric(...destination.point)){$('map-dialog').close();return true;}return false;
  }
''')
    return text


def replace_script(html, identifier, text):
    if '</script' in text.lower():
        raise ValueError('Fermeture de script interdite : ' + identifier)
    pattern = r'<script id="' + re.escape(identifier) + r'">[\s\S]*?</script>'
    if len(re.findall(pattern, html)) != 1:
        raise ValueError('Script de survol absent ou dupliqué : ' + identifier)
    return re.sub(pattern, lambda _: f'<script id="{identifier}">\n{text}\n</script>', html)


PANEL = '''
<dialog id="route70-dialog" aria-labelledby="route70-title">
<button id="route70-close" class="close" type="button">Fermer</button><h2 id="route70-title">Itinéraire local · 0.70</h2>
<p>Analyse des axes OSM du secteur chargé. L’accès physique, les trottoirs et les dégagements ne sont pas vérifiés.</p>
<p id="route70-summary" aria-live="polite">Marquer le départ ici, puis voler jusqu’à l’arrivée.</p>
<button id="route70-mark-start" type="button">Marquer le départ ici</button><p class="fine">Le panneau se ferme pour vous laisser voler. À sa prochaine ouverture, l’arrivée sera votre nouvelle position.</p>
<form id="route70-form"><details id="route70-precise"><summary>Coordonnées précises (Lambert-93)</summary><fieldset><legend>Points à projeter sur les axes · mètres</legend>
<div class="route70-row"><label>Départ · Est<input id="route70-start-e" type="number" step="any" required></label><label>Nord<input id="route70-start-n" type="number" step="any" required></label><button id="route70-camera-start" type="button">Depuis la caméra</button></div>
<div class="route70-row"><label>Arrivée · Est<input id="route70-end-e" type="number" step="any" required></label><label>Nord<input id="route70-end-n" type="number" step="any" required></label><button id="route70-camera-end" type="button">Depuis la caméra</button></div>
</fieldset></details>
<div class="route70-row"><label>Mode<select id="route70-mode"><option value="foot">Marche</option><option value="car">Voiture</option></select></label><label><input id="route70-avoid-steps" type="checkbox"> Éviter les escaliers</label></div>
<div id="route70-choices" hidden><label>Axe de départ<select id="route70-start-axis"></select></label><label>Axe d’arrivée<select id="route70-end-axis"></select></label></div>
<div class="actions"><button id="route70-compute" type="submit">Analyser le trajet vers ici</button><button id="route70-cancel" type="button" disabled>Annuler le calcul</button><button id="route70-example" type="button">Exemple Belsunce → République</button></div></form>
<p id="route70-status" role="status" aria-live="polite">Aucune navigation chargée.</p><p id="route70-projections"></p>
<canvas id="route70-map" width="820" height="300" role="img" aria-label="Aperçu 2D des seuls axes de l’itinéraire"></canvas>
<p class="fine">Vert : départ sur l’axe. Ambre : arrivée sur l’axe. Aucun lien entre les coordonnées saisies et les axes n’est tracé. Les ponts, tunnels, voies couvertes et conditions non résolues restent exclus. Analyse limitée à 36 secteurs ; le réseau extérieur peut contenir d’autres trajets.</p>
</dialog>'''

STYLE = '''
#route70-dialog{width:900px;line-height:1.45}#route70-dialog fieldset{border:1px solid #36565c;margin:12px 0}#route70-dialog label{display:flex;flex-direction:column;gap:5px}#route70-dialog input,#route70-dialog select{background:#102630;border:1px solid #45615f;padding:8px;min-width:0}#route70-dialog input[type=checkbox]{width:auto}#route70-dialog .route70-row{display:flex;align-items:end;gap:12px;flex-wrap:wrap;margin:12px 0}#route70-dialog summary{cursor:pointer;color:#9dbdb7;margin:12px 0}#route70-summary{color:#d6e9d3}#route70-choices label{margin:10px 0}#route70-map{width:100%;height:300px;background:#061119;border:1px solid #25434b}#route70-status{color:#91ddd0;min-height:2em}#route70-projections{font-size:12px;color:#bacac6}@media(max-width:700px){#route70-dialog{padding:16px}#route70-dialog input[type=number]{width:145px}#route70-map{height:230px}}
'''


def build(source_html=V69.SOURCE, expected_sha=None):
    original = V69.build(source_html, expected_sha)
    output = original.decode('utf-8')
    source = Path(source_html).read_text(encoding='utf-8')
    core = V69.script(source, 'soma-v63-nav-core')
    if hashlib.sha256(core.encode()).hexdigest() != CORE_SHA256:
        raise ValueError('Le vrai moteur NAV 0.63 ne correspond pas à son empreinte gelée.')
    controller = derive_controller(V69.script(output, 'viewer-metropole-viewer'))
    geometry = replace_once(V69.script(output, 'viewer-metropole-viewer-core'),
        'const material=A.appearance(p,id),canonical=',
        'const material=root.__SOMA_MATERIAL70_CORE__.appearance(p,id),canonical=')
    output = replace_script(output, 'viewer-metropole-viewer-core', geometry)
    output = replace_script(output, 'viewer-metropole-viewer', controller)
    modules = []
    for identifier, text in [
        ('world-index70', (ROOT/'src/v70/world-index.js').read_text()),
        ('material-extension70', (ROOT/'src/v70/material-extension-core.js').read_text()),
        ('source-router63', core),
        ('route-preview70', (ROOT/'src/v70/route-preview-core.js').read_text()),
    ]:
        if '</script' in text.lower():
            raise ValueError('Fermeture de script interdite : ' + identifier)
        # Keep the original router body byte-identical, including its own
        # final newline, so the embedded script itself has the pinned SHA256.
        body = text if identifier == 'source-router63' else '\n'+text+'\n'
        modules.append(f'<script id="viewer-{identifier}">{body}</script>')
    output = replace_once(output, '<script id="viewer-metropole-viewer-core">', '\n'.join(modules)+'\n<script id="viewer-metropole-viewer-core">')
    runtime = (ROOT/'src/v70/viewer-runtime.js').read_text(encoding='utf-8')
    if '</script' in runtime.lower():
        raise ValueError('Fermeture de script interdite dans le runtime 0.70.')
    output = replace_once(output, '</body>', f'<script id="viewer-runtime70">\n{runtime}\n</script>\n</body>')
    output = replace_once(output, '</style>', STYLE + '</style>')
    output = replace_once(output, '<button id="open-help">', '<button id="route70-open" type="button">Itinéraire local</button><button id="open-help">')
    output = replace_once(output, '<dialog id="help-dialog">', PANEL+'\n<dialog id="help-dialog">')
    output = replace_once(output, '<title>SOMA//MASSILIA — Survol métropolitain</title>', '<title>SOMA//MASSILIA 0.70 — Survol & itinéraire local</title>')
    output = replace_once(output, 'SURVOL MÉTROPOLITAIN · 0.69', 'SURVOL MÉTROPOLITAIN · 0.70')
    output = replace_once(output, 'href="SOMA_MASSILIA_URBAIN_v0_69.html"', 'href="SOMA_MASSILIA_URBAIN_v0_70.html"')
    data = json.loads(V69.script(output, 'soma-viewer-data', json_only=True))
    data.update(returnToGame='SOMA_MASSILIA_URBAIN_v0_70.html', version='0.70.0',
        sourceViewerSHA256=hashlib.sha256(original).hexdigest(),
        sourceHTML69SHA256=hashlib.sha256(Path(source_html).read_bytes()).hexdigest())
    old = re.search(r'<script id="soma-viewer-data" type="application/json">[\s\S]*?</script>', output)
    if old is None:
        raise ValueError('Métadonnées du survol absentes.')
    encoded = json.dumps(data, ensure_ascii=False, separators=(',', ':'), allow_nan=False).replace('<', '\\u003c')
    output = replace_once(output, old[0], '<script id="soma-viewer-data" type="application/json">'+encoded+'</script>')
    return output.encode('utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-html', type=Path, default=V69.SOURCE)
    parser.add_argument('--source-sha256')
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    try:
        data = build(args.source_html, args.source_sha256)
        if args.verify:
            if not args.output.is_file() or args.output.read_bytes() != data:
                raise ValueError('Survol 0.70 non synchronisé avec ses sources.')
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(data)
        print(json.dumps({'output':str(args.output),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),
            'verified':args.verify,'version':'0.70.0','campaignPersistenceLoaded':False,'navigationLoadedOnDemand':True}))
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, 'Construction du survol 0.70 impossible : '+str(error)+'\n')


if __name__ == '__main__':
    main()
