"""Clarify the IGN statistical fields in the existing, read-only Atlas audit.

The original geometry, reference sum and 77-object conflict cohort stay intact.
Derivation binds optional raw altitude fields to the already acquired IGN file;
it does not interpret a roof statistic as surveyed roof geometry.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_v68 import replace_once

MODULES = ('architecture-semantics-data', 'architecture-semantics-core', 'architecture-semantics-runtime')
SOURCE_DATA = ('data/v77/architecture-semantics.json',)
MARKER = '/* SOMA v77 architecture: distinguish calculated reference and IGN roof statistics. */'
DOCUMENT_SHA256 = '0542356dcf921bff5263043fe2af288a018d61d8e0f4d750005142f09cdb7331'
DOCUMENT_URL = 'https://data.geopf.fr/annexes/ressources/documentation/DC_BDTOPO_3-5.pdf'
FIELDS = ('hauteur', 'altitude_minimale_sol', 'altitude_maximale_sol', 'altitude_minimale_toit', 'altitude_maximale_toit')


def patch_html(html, scripts):
    if MARKER in html:
        raise ValueError('Architecture v77 déjà appliquée.')
    tags = []
    for name in MODULES:
        value = scripts.get(name)
        if not isinstance(value, str) or not value.strip() or '</script' in value.lower():
            raise ValueError('Module architecture v77 invalide : '+name)
        tags.append('<script id="soma-v77-'+name+'">\n'+value+'\n</script>')
    # Change the generated current inspector, never its frozen producer.
    old = "'<p>Sol minimal IGN : '+meters(row.groundAltitude)+' NGF · hauteur à l’égout : '+meters(row.eaveHeight)+' · égout de référence : '+meters(row.absoluteEaveNGF)+' NGF.<br>MNT sous l’emprise : '+meters(row.nativeFootprintMin)+' à '+meters(row.nativeFootprintMax)+' NGF · dépassement maximal : +'+meters(row.terrainAboveEave)+'.</p>'+"
    new = "(root.__SOMA_ARCHITECTURE77__?.paragraphs(row)||'<p>Interprétation des champs IGN indisponible.</p>')+"
    html = replace_once(html, old, new, 'cotes IGN distinctes v77')
    replacements = (
        ('<h3>Égouts IGN et relief sous les emprises</h3>', '<h3>Références IGN et relief sous les emprises</h3>'),
        ('Le maximum du MNT dépasse l’égout de référence de ces objets.', 'Le maximum du MNT dépasse la référence calculée sol minimal + hauteur de ces objets.'),
        ('<th scope="col">Égout NGF</th>', '<th scope="col">Sol minimal + hauteur NGF (calcul)</th>'),
        ('Façades et faîtage restent inconnus ; l’égout ne mesure pas la toiture.', 'Ces champs ne décrivent pas les façades ni une géométrie de toiture relevée.'),
    )
    for before, after in replacements:
        html = replace_once(html, before, after, 'terminologie IGN v77')
    return replace_once(html, '</body>', '\n'+MARKER+'\n'+'\n'.join(tags)+'\n</body>', 'interprétation IGN v77')


def patch_viewer(html, scripts):
    return html


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def verified(path, expected):
    raw = Path(path).read_bytes()
    if sha(raw) != expected:
        raise ValueError('Source différente : '+str(path))
    return raw


def derive(game, ign_root, document, output_root):
    game, ign_root, output_root = Path(game), Path(ign_root), Path(output_root)
    parent_raw = (game/'data/v76/architecture-conflicts.json').read_bytes()
    parent = json.loads(parent_raw)
    if parent['uniqueObjects'] != 77 or len(parent['rows']) != 77:
        raise ValueError('Cohorte parent différente.')
    provenance = parent['provenance']
    source_raw = verified(ign_root/'buildings.geojson', provenance['ignSourceSHA256'])
    receipt_raw = verified(ign_root/'source.json', provenance['ignReceiptSHA256'])
    verified(document, DOCUMENT_SHA256)
    features = {f['properties']['cleabs']: f['properties'] for f in json.loads(source_raw)['features']}
    rows = []
    for previous in parent['rows']:
        source = features[previous['ignId']]
        if source.get('hauteur') != previous['eaveHeight'] or source.get('altitude_minimale_sol') != previous['groundAltitude']:
            raise ValueError('Référence parent différente : '+previous['id'])
        fields = {key: source.get(key) for key in FIELDS}
        if any(value is not None and (type(value) not in (int, float) or not -1000 <= value <= 9000) for value in fields.values()):
            raise ValueError('Champ source incompatible.')
        rows.append(dict(id=previous['id'], ignId=previous['ignId'], geometrySHA256=previous['geometrySHA256'],
                         fields=fields, origin=source.get('origine_du_batiment'),
                         method=source.get('methode_d_acquisition_altimetrique'),
                         precisionM=source.get('precision_altimetrique')))
    result = dict(schema='soma-massilia/architecture-semantics77/1', geometryChanged=False,
                  referenceChanged=False, cohortChanged=False, units='m', verticalDatum='NGF-IGN69', rows=rows,
                  provenance=dict(parentCatalogueSHA256=sha(parent_raw), ignSourceSHA256=sha(source_raw),
                                  ignReceiptSHA256=sha(receipt_raw),
                                  document=dict(url=DOCUMENT_URL, sha256=DOCUMENT_SHA256, version='3.5',
                                                printedPages=[68, 76, 77, 78], date='2026-07'),
                                  authenticityLimit='Cached acquired source bytes and published content documentation; no independent survey or new building acquisition'))
    target = output_root/'data/v77/architecture-semantics.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    script = output_root/'src/v77/architecture-semantics-data.js'
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text('/* Raw IGN statistical fields, fixed77; regenerate with tools/v77_architecture.py --derive. */\nwindow.__SOMA_ARCHITECTURE77_DATA__='+json.dumps(result, ensure_ascii=False, separators=(',', ':'), sort_keys=True, allow_nan=False)+';\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--derive', action='store_true', required=True)
    parser.add_argument('--ign-root', type=Path, required=True)
    parser.add_argument('--document', type=Path, required=True)
    parser.add_argument('--game', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output-root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = derive(args.game, args.ign_root, args.document, args.output_root)
    print(json.dumps(dict(rows=len(result['rows']), geometryChanged=False, referenceChanged=False)))
