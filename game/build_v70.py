#!/usr/bin/env python3
"""Build the separate v0.70 gameplay layer over the byte-identical v0.69 world."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import tempfile

from build_v69 import build as build_v69, world_inputs, WORLD
from build_v68 import replace_once, rewrite_script
from tools.metropole.bootstrap import verify_world
from tools.v70_persistence import patch_persistence

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / 'SOMA_MASSILIA_URBAIN_v0_70.html'
REPORT = ROOT / 'data/v70/BUILD_REPORT.json'
PARENT_SHA256 = '8d0d68618ac2e9adde98e1a9a5cdfbc526af3a1af18841ac9e1ef4be83ebfd37'
ORIGINAL_MANIFEST_SHA256 = 'b2319570bad316607428f707765a512896871e97feff0d5512262b934ee8c9e1'
FROZEN69_SOURCES = {
    'build_v69.py': '74a20fbc6366c46253dbfef5ae8d3b732270d06cdb589d6305be51c96c62d7ee',
    'src/v69/building-parts.js': '14a8b2767f4b347a6daa76cde6f4a889ae10e400b644aa9f06db0b6387b224b3',
    'src/v69/height-references.js': 'fb2e12223d937c5f32c49b1d09da5da14485b9d7f3e59fcd7c53c0b713eb924c',
    'src/v69/metropole-viewer-core.js': 'f1f2df8692635c8c25acfe12aef1ca4277f1893528a8748260233e02534f61c1',
    'src/v69/metropole-viewer.js': 'ce8fe245f8a83767a200e28ed47959f3c3d0e72fb5284e906db9cdb40d944ab8',
    'src/v69/road-fidelity.js': '9d841f8c63223e521d0cfb6462e69b9224cbadedb236219d6c3e7a286a311d81',
    'src/v69/roof-core.js': '5c18fc4718f656ec372e89ce117095185dcec319517cdd3b92a060503259d3bd',
    'src/v69/streaming-core.js': '06995e1867257dca0e6ba2eed415326e16febbbd874ffa03a05a1028120f9ccc',
    'src/v69/world-runtime.js': 'c3ab96db2a08d6df24610745e64877beb218fc0141d9034ee26a86fa41e67819',
    'tools/v69_streaming.py': 'a8817848be92f5025968fcd984290ff434b25b449c27ee9295178e24a54e609f',
    'tools/v69_terrain.py': 'd92b224177326a64c6c6b3efe341e6f43e60fc35ab173055bcf4131ebae086a6',
    'tools/v69_depth.py': '01ec3f50adeb9997583dca9795e109b8d0590a4adece7255b6f22730040597e6',
    'tools/v69_heights.py': '169c87cb6456ce1b7ab04be0358a0587c45b8eabf4c1eb476d99af25b396c215',
}
MODULES = ('augmentations-core', 'infiltration-core', 'material-extension-core', 'perception-runtime', 'runtime')
V70_INPUTS = ('build_v70.py', 'tools/v70_persistence.py', 'tools/v70_gameplay.py',
              *(f'src/v70/{name}.js' for name in MODULES))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def fingerprint(path):
    checksum = hashlib.sha256()
    size = 0
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            size += len(block)
            checksum.update(block)
    return {'bytes': size, 'sha256': checksum.hexdigest()}


def originals():
    path = ROOT.parent / 'payload/manifest.json'
    raw = path.read_bytes()
    if digest(raw) != ORIGINAL_MANIFEST_SHA256:
        raise ValueError('Le manifeste des 27 fichiers originaux a changé.')
    manifest = json.loads(raw)
    entries = manifest.get('original_files')
    if manifest.get('format') != 1 or not isinstance(entries, dict) or len(entries) != 27:
        raise ValueError('Manifeste original invalide.')
    actual = {}
    for relative, expected in entries.items():
        target = ROOT / relative
        if Path(relative).is_absolute() or not target.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError('Chemin original hors livraison.')
        found = fingerprint(target)
        if found != {'bytes': expected['bytes'], 'sha256': expected['sha256']}:
            raise ValueError(f'Fichier original différent : {relative}')
        actual[relative] = found
    return actual


def inputs():
    preserved = originals()
    frozen = {relative: fingerprint(ROOT / relative) for relative in FROZEN69_SOURCES}
    for relative, value in frozen.items():
        if value['sha256'] != FROZEN69_SOURCES[relative]:
            raise ValueError(f'Source 0.69 gelée différente : {relative}')
    return {'originals': preserved, 'frozen69Sources': frozen,
            'sources70': {relative: fingerprint(ROOT / relative) for relative in V70_INPUTS},
            'reusedWorldManifest': fingerprint(WORLD / 'manifest.json')}


def source_scripts(snapshot):
    scripts = {}
    for name in MODULES:
        relative = f'src/v70/{name}.js'
        expected = snapshot['sources70'][relative]
        if expected['bytes'] > 2 * 1024 * 1024:
            raise ValueError(f'Module 0.70 trop volumineux : {name}')
        raw = (ROOT / relative).read_bytes()
        if len(raw) != expected['bytes'] or digest(raw) != expected['sha256']:
            raise ValueError(f'Module 0.70 modifié pendant la lecture : {name}')
        text = raw.decode('utf-8')
        if '</script' in text.lower():
            raise ValueError(f'Fermeture de script interdite dans {name}.')
        scripts[name] = text
    return scripts


def script(name, scripts):
    text = scripts[name]
    if not isinstance(text, str) or '</script' in text.lower():
        raise ValueError(f'Contenu de script 0.70 invalide : {name}')
    return f'\n<script id="soma-v70-{name}">\n{text}\n</script>\n'


def patch_html(html, scripts, gameplay_patch=None):
    if gameplay_patch is None:
        from tools.v70_gameplay import patch_gameplay
        gameplay_patch = patch_gameplay
    if 'id="soma-v70-' in html:
        raise ValueError('La couche 0.70 est déjà appliquée.')
    html = replace_once(html, '<head>', '<head>' + script('augmentations-core', scripts) +
                        script('infiltration-core', scripts), 'noyaux purs avant la continuité')
    html = rewrite_script(html, 'soma-v37-persistence', patch_persistence)
    html = rewrite_script(html, 'soma-v69-world-runtime', lambda value: replace_once(value,
        "button.onclick=()=>location.assign('metropole-viewer.html');",
        "button.onclick=()=>location.assign('metropole-viewer-v70.html');",
        'entrée du survol 0.70 sans réaffecter la campagne'))
    html = rewrite_script(html, 'soma-v68-building-renderer', lambda value: replace_once(value,
        'material = K.appearance(p, seed);',
        'material = (window.__SOMA_MATERIAL70_CORE__?.appearance || K.appearance)(p, seed);',
        'apparence source explicite 0.70'))
    html = replace_once(html, '<script id="soma-v68-building-renderer">',
        script('material-extension-core', scripts) + '<script id="soma-v68-building-renderer">',
        'matériaux après architecture et toits')
    html = gameplay_patch(html)
    html = replace_once(html, '</body>', script('perception-runtime', scripts) +
                        script('runtime', scripts) + '\n</body>', 'adaptateurs après le footer 0.69')
    for name in MODULES:
        if html.count(f'id="soma-v70-{name}"') != 1:
            raise ValueError(f'Module 0.70 absent ou dupliqué : {name}')
    return html


def build_release():
    before = inputs()
    parent = build_v69()
    if digest(parent) != PARENT_SHA256:
        raise ValueError('Le parent 0.69 reconstruit diffère de son SHA256 gelé.')
    world = verify_world(WORLD, world_inputs(parent))
    data = patch_html(parent.decode('utf-8'), source_scripts(before)).encode('utf-8')
    after = inputs()
    if before != after:
        changed = []
        for group in sorted(set(before) | set(after)):
            left, right = before.get(group), after.get(group)
            if left == right:
                continue
            if isinstance(left, dict) and isinstance(right, dict):
                changed.extend(group + '/' + key for key in sorted(set(left) | set(right))
                               if left.get(key) != right.get(key))
            else:
                changed.append(group)
        raise ValueError('Une entrée a changé pendant la reconstruction 0.70 : ' + ', '.join(changed))
    report = {'version': '0.70.0', 'output': OUTPUT.name, 'bytes': len(data), 'sha256': digest(data),
              'parentVersion': '0.69.0', 'parentSHA256': PARENT_SHA256,
              'originalFilesVerified': len(before['originals']), 'sourceGeometryUnchanged': True,
              'newGeographicCells': 0, 'geographicWorld': 'data/v69/world/manifest.json',
              'worldManifestSHA256': before['reusedWorldManifest']['sha256'],
              'preparedCells': len(world['tiles']), 'completeMetropole': False,
              'certifiedOneToOne': False, 'inputs': before}
    return data, report


def build():
    return build_release()[0]


def atomic_write(path, data):
    if path.is_symlink() or not path.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError('Chemin de sortie 0.70 invalide.')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.v70-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def prepare(*, verify=False):
    data, report = build_release()
    encoded = (json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')
    if verify:
        if not OUTPUT.is_file() or OUTPUT.read_bytes() != data:
            raise ValueError('Le HTML 0.70 ne correspond pas aux sources actuelles.')
        if not REPORT.is_file() or REPORT.read_bytes() != encoded:
            raise ValueError('Le rapport 0.70 ne correspond pas aux entrées vérifiées.')
    else:
        # Both outputs are generated assets. Existing versions/worlds are read
        # only, and no new geographic catalogue or terrain is prepared here.
        atomic_write(OUTPUT, data)
        atomic_write(REPORT, encoded)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    try:
        report = prepare(verify=args.verify)
        print(json.dumps({'version': report['version'], 'bytes': report['bytes'], 'sha256': report['sha256'],
                          'originalFilesVerified': report['originalFilesVerified'], 'newGeographicCells': 0,
                          'verified': args.verify}, ensure_ascii=False))
    except (OSError, ValueError, KeyError, TypeError, ImportError) as error:
        parser.exit(1, f'Reconstruction 0.70 impossible : {error}\n')


if __name__ == '__main__':
    main()
