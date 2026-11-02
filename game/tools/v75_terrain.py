"""Source-only centre 5 m terrain pilot, derived from the installed IGN mosaic.

The optional derive command verifies every input tile and copies float32 nodes
and validity bytes without resampling, quantisation or NoData replacement.
Ordinary builds need only the small versioned JavaScript modules.
"""
import argparse
import base64
import gzip
import hashlib
import json
import sys
from pathlib import Path

if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_v68 import replace_once, rewrite_script

MODULES = ('terrain-footprint-core', 'terrain-data-a', 'terrain-data-b', 'terrain-data-c', 'terrain-runtime')
DATA_MODULES = ('terrain-data-a', 'terrain-data-b', 'terrain-data-c')
MARKER = '/* SOMA v75 terrain: explicit source-only 5 m centre pilot. */'


def once(text, old, new, label):
    return replace_once(text, old, new, 'v75 terrain : ' + label)


def patch_terrain(body):
    body = once(body, 'try{const next=validatePack(p);if(persist)await cacheWrite(p);activate(p,next);return true;}',
        'try{const next=validatePack(p);for(const tile of v69Tiles.values())v69CheckPair(next,tile.grid);if(persist)await cacheWrite(p);activate(p,next);return true;}',
        'aucun chemin public ne persiste un raccord refusé')
    body = once(body, 'const T={version:VERSION,ready:false,core:K,v69:v69API,',
        "function v75Preflight(p){const next=validatePack(p);for(const tile of v69Tiles.values())v69CheckPair(next,tile.grid);return true;}\nconst T={version:VERSION,ready:false,core:K,v69:v69API,v75Preflight,",
        'compatibilité avant écriture du cache existant')
    body = once(body,
        "   for(const mesh of p['soma:mesh53']||[])for(const ring of mesh.ringsL93||[])for(const q of ring){\n    const recordGrid=v69GridForRecord(record),h=recordGrid?recordGrid.sample(q[0],q[1]):null;if(h===null){item.missing=true;continue;}\n    item.max=Math.max(item.max,h);item.min=Math.min(item.min,h);item.n++;\n   }",
        "   for(const mesh of p['soma:mesh53']||[]){\n    const recordGrid=v69GridForRecord(record);\n    if(recordGrid?.step===5&&recordGrid.pack?.source?.truth==='IGN RGE ALTI native 5m-derived centre grid'){window.__SOMA_TERRAIN75_CORE__.accumulate(recordGrid,mesh.ringsL93||[],item,window.__SOMA_V53_CORE__.inPolygon);continue;}\n    for(const ring of mesh.ringsL93||[])for(const q of ring){\n     const h=recordGrid?recordGrid.sample(q[0],q[1]):null;if(h===null){item.missing=true;continue;}\n     item.max=Math.max(item.max,h);item.min=Math.min(item.min,h);item.n++;\n    }\n   }",
        'extrema sous emprise complète du pilote')
    body = once(body,
        'if(!pose||!footprintValid(target,pose.x,pose.z,.4)||blocked(target,pose.x,pose.z,.38)){',
        'if(!pose||!footprintValid(target,pose.x,pose.z,.4)||blocked(target,pose.x,pose.z,.38)||!(window.__SOMA_TERRAIN75__?.entrySupported(target,pose.x,pose.z)??true)){',
        'validation de la position restaurée')
    body = once(body,
        'if(footprintValid(target,q.x,q.z,.4)&&!blocked(target,q.x,q.z,.38)){safe=q;break;}',
        'if(footprintValid(target,q.x,q.z,.4)&&!blocked(target,q.x,q.z,.38)&&(window.__SOMA_TERRAIN75__?.entrySupported(target,q.x,q.z)??true)){safe=q;break;}',
        'point de repli soutenu')
    body = once(body, 'pose={...pose,...safe};',
        "pose={...pose,...safe};if(window.__SOMA_TERRAIN75__?.active())window.__SOMA_TERRAIN75__.relocated(target);",
        'repli explicite au chargement')
    body = once(body,
        "if(!safe){status='Entrée refusée : aucune position de sol connue et libre dans cette cellule.';refresh();return false;}",
        "if(!safe){status='Entrée refusée : aucune position de sol connue et libre dans cette cellule.';refresh();if(window.__SOMA_TERRAIN75__?.active())window.__SOMA_TERRAIN75__.refused(target);return false;}",
        'refus sans reprise silencieuse de la continuité')
    body = once(body, 'const r=oldEnter(...args);if(r){lastGround=0;poseCamera();}return r;',
        'const r=oldEnter(...args);if(r){window.__SOMA_TERRAIN75__?.entered();lastGround=0;poseCamera();}return r;',
        'entrée valide après un refus')
    return once(body, ' refresh();}\nasync function install(p,{persist=true}={}){',
        ' refresh();window.__SOMA_TERRAIN75__?.changed?.();}\nasync function install(p,{persist=true}={}){',
        'réconciliation du cache terrain existant')


def patch_html(html, scripts):
    if MARKER in html:
        raise ValueError('Terrain v75 déjà appliqué.')
    tags = []
    for name in MODULES:
        value = scripts.get(name)
        if not isinstance(value, str) or not value.strip() or '</script' in value.lower():
            raise ValueError('Module terrain v75 invalide : ' + name)
        tag = '<script id="soma-v75-' + name + '">\n' + value + '\n</script>'
        if name == 'terrain-footprint-core':
            html = once(html, '<script id="soma-v56-terrain-runtime">', tag + '\n<script id="soma-v56-terrain-runtime">', 'extrema disponibles avant activation du relief')
        else:
            tags.append(tag)
    html = rewrite_script(html, 'soma-v56-terrain-runtime', patch_terrain)
    return once(html, '</body>', '\n' + MARKER + '\n' + '\n'.join(tags) + '\n</body>', 'modules après propriétaires')


def patch_viewer(html, scripts):
    return html


def compact(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def derive(native_manifest, centre_manifest, output_root):
    """Verify the 168 centre tiles and reproduce the three data modules/proof."""
    native_manifest, centre_manifest = Path(native_manifest), Path(centre_manifest)
    native_raw, centre_raw = native_manifest.read_bytes(), centre_manifest.read_bytes()
    native, centre = json.loads(native_raw), json.loads(centre_raw)
    if native['crs'] != 'EPSG:2154' or native['verticalDatum'] != 'NGF-IGN69':
        raise ValueError('CRS/datum natif incompatible.')
    if len(centre['tiles']) != 168 or centre['completeMetropole']:
        raise ValueError('Le manifeste doit être le centre historique de 168 cellules.')
    lookup = {(t['gridX'], t['gridY']): t for t in native['tiles']}
    selected = []
    for cell in centre['tiles']:
        tile = lookup[(cell['gridX'], cell['gridY'])]
        if tile['boundsL93'] != cell['boundsL93'] or tile['terrain']['stepM'] != 5:
            raise ValueError('Emprise ou pas différent du centre.')
        selected.append((cell, tile))
    bounds = [min(c['boundsL93'][i] for c, _ in selected) for i in (0, 1)] + [max(c['boundsL93'][i] for c, _ in selected) for i in (2, 3)]
    step = 5
    cols, rows = round((bounds[2]-bounds[0])/step)+3, round((bounds[3]-bounds[1])/step)+3
    header = dict(boundsL93=bounds, cols=cols, rows=rows, crs='EPSG:2154',
        x0=bounds[0]-step, n0=bounds[3]+step, step=step, units='m',
        verticalDatum='NGF-IGN69', haloNodes=1, interpolation='fixed-diagonal-triangles',
        nodeRegistration='grid-node', rowOrder='north-to-south')
    data, mask, seen = bytearray(cols*rows*4), bytearray(cols*rows), bytearray(cols*rows)
    files, proofs, overlaps = {}, [], 0
    for cell, tile in selected:
        path = (native_manifest.parent/tile['terrain']['path']).resolve()
        if not path.is_relative_to(native_manifest.parent.resolve()):
            raise ValueError('Chemin de tuile hors manifeste.')
        raw = path.read_bytes()
        if len(raw) != tile['terrain']['bytes'] or sha(raw) != tile['terrain']['sha256']:
            raise ValueError('Tuile native altérée : '+cell['cellId'])
        pack = json.loads(gzip.decompress(raw)); h = json.loads(pack['gridHeader'])
        d, m = base64.b64decode(pack['dataBase64'], validate=True), base64.b64decode(pack['maskBase64'], validate=True)
        if sha(pack['gridHeader'].encode()+b'\0'+d+m) != pack['sha256'] or pack['sha256'] != tile['terrain']['gridSHA256']:
            raise ValueError('Empreinte de grille native incorrecte.')
        if h['cols'] != 53 or h['rows'] != 53 or h['step'] != 5 or len(d) != 53*53*4 or len(m) != 53*53 or any(x not in (0, 1) for x in m):
            raise ValueError('Carroyage natif incompatible.')
        for f in pack['source']['files']:
            files[f['name']] = f
        ox, oy = round((h['x0']-header['x0'])/step), round((header['n0']-h['n0'])/step)
        if abs(h['x0']-header['x0']-ox*step)>1e-6 or abs(header['n0']-h['n0']-oy*step)>1e-6:
            raise ValueError('Nœuds natifs non alignés.')
        for y in range(53):
            for x in range(53):
                i, j = y*53+x, (oy+y)*cols+ox+x
                if seen[j]:
                    overlaps += 1
                    if mask[j] != m[i] or data[j*4:j*4+4] != d[i*4:i*4+4]:
                        raise ValueError('Nœud partagé différent, y compris NoData.')
                else:
                    data[j*4:j*4+4], mask[j], seen[j] = d[i*4:i*4+4], m[i], 1
        proofs.append(dict(cellId=cell['cellId'], boundsL93=cell['boundsL93'], nativeCellId=tile['cellId'],
            tileSHA256=tile['terrain']['sha256'], gridSHA256=pack['sha256']))
    # Uncovered nodes in the bounding rectangle stay masked. No sea or missing
    # campaign cell is filled from a neighbouring raster implicitly.
    source = dict(native['source']); source['files'] = sorted(files.values(), key=lambda f:f['name'])
    source.update(truth='IGN RGE ALTI native 5m-derived centre grid',
        derivation='Exact float32 nodes and mask copied from 168 prepared strict-bilinear 5m tiles; no further resampling',
        nativeManifestSHA256=sha(native_raw), centreManifestSHA256=sha(centre_raw))
    hs = compact(header)
    pack = dict(schema='soma-massilia/terrain-grid/1', encoding='float32-le+valid-u8', gridHeader=hs,
        dataBase64=base64.b64encode(data).decode(), maskBase64=base64.b64encode(mask).decode(),
        source=source, sha256=sha(hs.encode()+b'\0'+data+mask))
    proof = dict(schema='soma-massilia/terrain75-source/1', campaignCells=168, newGeographicCells=0,
        nativeManifestSHA256=sha(native_raw), centreManifestSHA256=sha(centre_raw), gridSHA256=pack['sha256'],
        boundsL93=bounds, stepM=5, nodes=len(mask), validNodes=sum(mask), noDataNodes=len(mask)-sum(mask),
        sharedNodesVerifiedIdentical=overlaps, unprovidedNodes=sum(v == 0 for v in seen),
        source=source, tiles=proofs, pilot=True, certified=False)
    out = Path(output_root); (out/'src/v75').mkdir(parents=True, exist_ok=True); (out/'data/v75').mkdir(parents=True, exist_ok=True)
    encoded = compact(pack)
    parts = [encoded[i:i+1050000] for i in range(0, len(encoded), 1050000)]
    if len(parts) != 3:
        raise ValueError('Le budget du pack a changé ; revoir le découpage.')
    for letter, part in zip('abc', parts):
        value = '/* IGN centre 5m source fragment; regenerate with tools/v75_terrain.py --derive. */\n(window.__SOMA_TERRAIN75_PARTS__ ||= []).push('+json.dumps(part, ensure_ascii=False)+');\n'
        if len(value.encode()) >= 2*1024*1024:
            raise ValueError('Module supérieur au budget de 2 Mio.')
        (out/'src/v75'/('terrain-data-'+letter+'.js')).write_text(value)
    (out/'data/v75/terrain-source.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2)+'\n')
    return proof


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--derive', action='store_true')
    parser.add_argument('--native-manifest', type=Path)
    parser.add_argument('--centre-manifest', type=Path)
    parser.add_argument('--output-root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    if not args.derive or not args.native_manifest or not args.centre_manifest:
        parser.error('--derive --native-manifest et --centre-manifest sont requis')
    result = derive(args.native_manifest, args.centre_manifest, args.output_root)
    print(json.dumps({k:result[k] for k in ('gridSHA256', 'campaignCells', 'nodes', 'validNodes', 'noDataNodes', 'sharedNodesVerifiedIdentical')}))
