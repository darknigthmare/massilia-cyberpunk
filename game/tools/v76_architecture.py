"""Source-bound Atlas audit of the 77 fixed IGN eave/5 m terrain conflicts.

No geometry, source datum, active terrain or campaign state is changed. The
optional derive command independently clips the source building triangles
against the terrain triangles; it never calls the v75 footprint accumulator.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import sys

if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_v68 import replace_once

MODULES = ('architecture-conflicts-data', 'architecture-conflicts-core', 'architecture-conflicts-runtime')
MARKER = '/* SOMA v76 architecture: source-bound Atlas conflict audit. */'
PARENT_AUDIT_SHA256 = 'a6bce341d89ad37654b2938624a546b7e9d9d86c0eb21bd395e43afebdaaa2ac'


def patch_html(html, scripts):
    if MARKER in html:
        raise ValueError('Architecture v76 déjà appliquée.')
    tags = []
    for name in MODULES:
        value = scripts.get(name)
        if not isinstance(value, str) or not value.strip() or '</script' in value.lower():
            raise ValueError('Module architecture v76 invalide : ' + name)
        tags.append('<script id="soma-v76-' + name + '">\n' + value + '\n</script>')
    return replace_once(html, '</body>', '\n' + MARKER + '\n' + '\n'.join(tags) + '\n</body>', 'audit architecture v76')


def patch_viewer(html, scripts):
    return html


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def compact(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def read_verified(path, expected):
    raw = Path(path).read_bytes()
    if sha(raw) != expected:
        raise ValueError('Source différente : ' + str(path))
    return raw


def cross(a, b, p):
    return (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])


def clip_triangle(subject, triangle):
    """Sutherland-Hodgman clipping, translated metric coordinates."""
    orientation = 1 if cross(*triangle) > 0 else -1
    for i, a in enumerate(triangle):
        b = triangle[(i+1) % 3]
        output = []
        if not subject:
            break
        previous = subject[-1]
        before = orientation*cross(a, b, previous)
        for current in subject:
            after = orientation*cross(a, b, current)
            if (before >= -1e-9) != (after >= -1e-9):
                t = before/(before-after)
                output.append([previous[j]+t*(current[j]-previous[j]) for j in (0, 1)])
            if after >= -1e-9:
                output.append(current)
            previous, before = current, after
        subject = output
    return subject


def triangle_extrema(meshes, header, heights, mask):
    """Intersect source triangles with both measured triangles of every square.

    Each linear patch reaches its extrema at an intersection vertex. Clipping
    uses grid-relative coordinates to avoid cancellation of Lambert-93 values.
    Source triangulation already excludes courtyard interiors.
    """
    cols, rows, step = header['cols'], header['rows'], header['step']
    low, high, witness, intersections = math.inf, -math.inf, None, 0
    for mesh in meshes:
        for source in mesh['trianglesL93']:
            triangle = [[(q[0]-header['x0'])/step, (header['n0']-q[1])/step] for q in source]
            if abs(cross(*triangle)) < 1e-12:
                continue
            x0, x1 = max(0, math.floor(min(q[0] for q in triangle))), min(cols-2, math.floor(max(q[0] for q in triangle)))
            y0, y1 = max(0, math.floor(min(q[1] for q in triangle))), min(rows-2, math.floor(max(q[1] for q in triangle)))
            for y in range(y0, y1+1):
                for x in range(x0, x1+1):
                    for corners in ([(x,y),(x+1,y),(x,y+1)], [(x+1,y+1),(x,y+1),(x+1,y)]):
                        intersection = clip_triangle(list(triangle), corners)
                        if not intersection:
                            continue
                        indices = [cy*cols+cx for cx, cy in corners]
                        if any(not mask[i] for i in indices):
                            raise ValueError('NoData sous une emprise source.')
                        denom = cross(*corners)
                        for point in intersection:
                            weights = [cross(corners[1], corners[2], point)/denom,
                                       cross(corners[2], corners[0], point)/denom,
                                       cross(corners[0], corners[1], point)/denom]
                            altitude = sum(heights[i]*w for i, w in zip(indices, weights))
                            low = min(low, altitude)
                            if altitude > high:
                                high = altitude
                                witness = [header['x0']+point[0]*step, header['n0']-point[1]*step]
                            intersections += 1
    if not intersections:
        raise ValueError('Emprise sans intersection mesurable.')
    return dict(min=low, max=high, witnessL93=witness, clippedVertices=intersections)


def derive(game, parent_audit, ign_root, output_root):
    game, ign_root, output_root = Path(game), Path(ign_root), Path(output_root)
    parent_raw = read_verified(parent_audit, PARENT_AUDIT_SHA256)
    parent = json.loads(parent_raw)
    cohort = parent['fixedSourceUnderEaveConflicts']
    if len(cohort) != 77 or len({r['id'] for r in cohort}) != 77:
        raise ValueError('Cohorte parent différente des 77 objets fixes.')
    source_proof = json.loads((game/'data/v75/terrain-source.json').read_bytes())
    parts = []
    for letter in 'abc':
        text = (game/f'src/v75/terrain-data-{letter}.js').read_text()
        parts.append(json.loads(re.search(r'\.push\((.*)\);\s*$', text)[1]))
    pack = json.loads(''.join(parts))
    header = json.loads(pack['gridHeader'])
    grid_raw, mask = base64.b64decode(pack['dataBase64']), base64.b64decode(pack['maskBase64'])
    if sha(pack['gridHeader'].encode()+b'\0'+grid_raw+mask) != source_proof['gridSHA256'] or pack['sha256'] != parent['gridSHA256']:
        raise ValueError('Grille parent différente.')
    heights = struct.unpack('<'+'f'*(len(grid_raw)//4), grid_raw)
    matches_raw = (game/'data/v69/building-height-matches.json.gz').read_bytes()
    matches = json.loads(gzip.decompress(matches_raw))
    references = {r['canonicalId']:r for r in matches['matches'].values()}
    receipt_raw = read_verified(ign_root/'source.json', matches['acquisitionValidation']['ignReceiptSHA256'])
    receipt = json.loads(receipt_raw)
    ign_raw = read_verified(ign_root/'buildings.geojson', matches['ignSource']['sha256'])
    ign_features = {f['properties']['cleabs']:f['properties'] for f in json.loads(ign_raw)['features']}
    manifest = json.loads((game/'data/v69/world/manifest.json').read_bytes())
    tiles = {t['cellId']:t for t in manifest['tiles']}
    records, rows, discrepancies = {}, [], []
    for previous in cohort:
        identity, cell_id = previous['id'], previous['cellId']
        ref, tile = references[identity], tiles[cell_id]
        if cell_id not in records:
            raw = read_verified(game/'data/v69/world'/tile['vector']['path'], tile['vector']['sha256'])
            records[cell_id] = json.loads(gzip.decompress(raw))
        record = records[cell_id]
        feature = next(f for f in record['featureCollection']['features'] if (f['properties'].get('canonical_id') or f['id']) == identity)
        p, ign = feature['properties'], ign_features[ref['ignId']]
        if (record['contentSHA256'] != ref['cells'][cell_id] or p['soma:geometry_sha256'] != ref['geometrySHA256'] or
                record['sourceReceipt']['sha256'] != ref['sourceSHA256'] or
                ign['altitude_minimale_sol'] != ref['groundAltitude'] or ign['hauteur'] != ref['height'] or
                ref['groundAltitude'] != previous['groundAltitude'] or ref['height'] != previous['eaveHeight']):
            raise ValueError('Liaison de source différente : '+identity)
        extrema = triangle_extrema(p['soma:mesh53'], header, heights, mask)
        discrepancy = abs(extrema['max']-previous['nativeFootprintMax'])
        discrepancies.append(discrepancy)
        if discrepancy > 1e-6:
            raise ValueError('Désaccord avec audit parent : '+identity)
        # Retain the parent float values so the published strict-positive
        # threshold has exactly the same meaning as v75, including 4.1 mm.
        row = dict(previous, ignId=ref['ignId'], geometrySHA256=ref['geometrySHA256'],
                   sourceSHA256=ref['sourceSHA256'], cells=ref['cells'],
                   absoluteEaveNGF=ref['groundAltitude']+ref['height'],
                   nativeFootprintMin=extrema['min'], witnessL93=extrema['witnessL93'],
                   iou=ref['iou'], margin=ref['margin'], reciprocalMargin=ref['reciprocalMargin'],
                   sourceAltitudePrecisionM=ign.get('precision_altimetrique'),
                   sourceAltitudeMethod=ign.get('methode_d_acquisition_altimetrique'),
                   sourceModificationDate=ign.get('date_modification'))
        rows.append(row)
    rows.sort(key=lambda r:(-r['terrainAboveEave'],r['id']))
    result = dict(schema='soma-massilia/architecture-conflicts76/1', crs='EPSG:2154', units='m',
                  verticalDatum='NGF-IGN69', pilot=True, certified=False, geometryChanged=False,
                  thresholdM=0, fragments=77, uniqueObjects=77, over3cm=76,
                  cells=len({r['cellId'] for r in rows}), rows=rows,
                  provenance=dict(parentAuditSHA256=sha(parent_raw), gridSHA256=pack['sha256'],
                      nativeManifestSHA256=source_proof['nativeManifestSHA256'],
                      heightProofSHA256=matches['proofSHA256'], compressedHeightFileSHA256=sha(matches_raw),
                      ignSourceSHA256=matches['ignSource']['sha256'], ignReceiptSHA256=sha(receipt_raw),
                      osmSourceSHA256=matches['sourceSHA256'], ignDate=matches['ignSource']['date'],
                      ignFields=matches['ignSource']['fields'], terrainSource=pack['source']['truth'],
                      terrainMethod=pack['source']['method'], terrainFiles=pack['source']['files'],
                      terrainArchiveVintage='2022-12', sourceContractBugFound=False,
                      investigation='All77 fixed ground/eave values exactly equal raw IGN altitude_minimale_sol/hauteur; source geometry/cell bindings verified; independent clipping reproduces terrain maxima. Different source vintages and source precision do not justify moving measured references.',
                      independentCheck='Python triangle-triangle clipping; source mesh triangles exclude courtyard interiors; no v75 accumulator called',
                      maximumIndependentDifferenceM=max(discrepancies),
                      sourceAuthenticityLimit='Stored source-file integrity and acquired receipt checked; no independent survey or new acquisition'))
    target = output_root/'data/v76/architecture-conflicts.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    script = output_root/'src/v76/architecture-conflicts-data.js'
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text('/* Source-bound fixed77; regenerate with tools/v76_architecture.py --derive. */\nwindow.__SOMA_ARCHITECTURE76_DATA__='+compact(result)+';\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--derive', action='store_true')
    parser.add_argument('--parent-audit', type=Path, required=True)
    parser.add_argument('--ign-root', type=Path, required=True)
    parser.add_argument('--game', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output-root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    if not args.derive:
        parser.error('--derive requis')
    result = derive(args.game, args.parent_audit, args.ign_root, args.output_root)
    print(json.dumps({k:result[k] for k in ('fragments','uniqueObjects','over3cm','cells')}))
