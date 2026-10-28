"""Content-verified receipt for an already successful full launcher preparation.

This skips reconstruction, never integrity checks: sources, nine generated HTML
files, build reports and every centre-world asset are checked on each hit. The
large optional metropolitan edition is deliberately left to its bounded loader.
Only the launcher records a receipt after every builder succeeded; no Git, GIS,
timestamp trust or package outside Python's standard library is required.
"""
from __future__ import annotations

import hashlib
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = 'data/v72/LAUNCH_CACHE.json'
SCHEMA = 'soma-massilia/verified-launch-cache/1'
HTML_FILES = (
    'SOMA_MASSILIA_URBAIN_v0_68.html', 'SOMA_MASSILIA_URBAIN_v0_69.html',
    'SOMA_MASSILIA_URBAIN_v0_70.html', 'SOMA_MASSILIA_URBAIN_v0_71.html',
    'SOMA_MASSILIA_URBAIN_v0_72.html',
    'metropole-viewer.html', 'metropole-viewer-v70.html', 'metropole-viewer-v71.html',
    'metropole-viewer-v72.html',
)
REPORT_FILES = ('data/v68/BUILD_REPORT.json', 'data/v69/BUILD_REPORT.json',
                'data/v70/BUILD_REPORT.json', 'data/v71/BUILD_REPORT.json',
                'data/v72/BUILD_REPORT.json', 'data/v71/VIEWER_BUILD_REPORT.json',
                'data/v72/VIEWER_BUILD_REPORT.json')
PARENT_VIEWER71_SHA256 = '2f06f5c2d0710af5ce9e96d12290e46672fb98c099951c8a7523c9dbafd69a54'
GENERATED_NAMES = {'BUILD_REPORT.json', 'VIEWER_BUILD_REPORT.json', 'LAUNCH_CACHE.json',
                   'FEATURE_REPORT.json', 'METROPOLE_DELIVERY.json'}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def fingerprint(path):
    checksum = hashlib.sha256()
    size = 0
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            checksum.update(chunk)
            size += len(chunk)
    return {'bytes': size, 'sha256': checksum.hexdigest()}


def inside(root, relative):
    path = root / relative
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Chemin de validation hors livraison : ' + str(relative))
    return path


def document(path, maximum=2 * 1024 * 1024):
    with path.open('rb') as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError('Rapport de validation trop volumineux.')
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError('Rapport de validation invalide.')
    return value


def source_inputs(game=ROOT):
    """Conservative transitive input set, including dependencies absent in B72.inputs.

    The centre assets are verified separately, while the 27 original files and
    source PBF are verified by B72.inputs and the launcher's payload checks.
    """
    game = Path(game).resolve()
    paths = {p for p in game.glob('build*.py') if p.is_file()}
    for directory in ('src', 'tools', 'data'):
        base = game / directory
        for current, directories, files in os.walk(base):
            directories[:] = sorted(d for d in directories if d != '__pycache__' and
                                    not (directory == 'data' and d in {'world', 'metropole', 'source'}))
            for name in directories:
                if (Path(current) / name).is_symlink():
                    raise ValueError('Répertoire source lié non mis en cache.')
            for name in files:
                path = Path(current) / name
                if directory == 'src' and path.suffix not in {'.js', '.html'}:
                    continue
                if directory == 'tools' and path.suffix != '.py':
                    continue
                if directory == 'data' and (name in GENERATED_NAMES or name.endswith(('.pyc', '.tmp'))):
                    continue
                paths.add(path)
    # The payload manifest is itself pinned in B72.B71.B70.originals. Including it here
    # also makes the receipt explicitly local to the current original delivery.
    extras = {'../lancer.py': game.parent / 'lancer.py',
              '../payload/manifest.json': game.parent / 'payload/manifest.json'}
    result = {}
    for path in sorted(paths):
        relative = str(path.relative_to(game))
        result[relative] = fingerprint(inside(game, relative))
    for relative, path in extras.items():
        if path.is_symlink() or not path.resolve().is_relative_to(game.parent):
            raise ValueError('Entrée du lanceur hors livraison.')
        result[relative] = fingerprint(path)
    return result


def dependencies():
    # Imported only when the launcher has restored and checked the originals.
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import build_v72
    from tools.metropole.bootstrap import verify_world
    return build_v72, verify_world


def snapshot(game=ROOT):
    game = Path(game).resolve()
    B72, verify_world = dependencies()
    inputs = B72.inputs()
    sources = source_inputs(game)
    reports = {relative: document(inside(game, relative)) for relative in REPORT_FILES}
    artifacts = {relative: fingerprint(inside(game, relative)) for relative in (*HTML_FILES, *REPORT_FILES)}
    for version in ('68', '69', '70', '71', '72'):
        report = reports[f'data/v{version}/BUILD_REPORT.json']
        name = f'SOMA_MASSILIA_URBAIN_v0_{version}.html'
        if (report.get('version') != f'0.{version}.0' or report.get('output') != name or
                artifacts[name] != {key: report.get(key) for key in ('bytes', 'sha256')}):
            raise ValueError('HTML et rapport de build divergents : ' + name)
    for version in ('71', '72'):
        viewer = reports[f'data/v{version}/VIEWER_BUILD_REPORT.json']
        name = f'metropole-viewer-v{version}.html'
        if (viewer.get('version') != f'0.{version}.0' or viewer.get('output') != name or
                artifacts[name] != {key: viewer.get(key) for key in ('bytes', 'sha256')}):
            raise ValueError('Survol et rapport de build divergents : ' + name)
    parent_inputs = inputs['parentInputs']
    for version, expected in (('72', inputs), ('71', parent_inputs), ('70', parent_inputs['parentInputs'])):
        if reports[f'data/v{version}/BUILD_REPORT.json'].get('inputs') != expected:
            raise ValueError('Rapports construits avec d’autres entrées.')
        if version in ('71', '72') and reports[f'data/v{version}/VIEWER_BUILD_REPORT.json'].get('inputs') != expected:
            raise ValueError('Rapports du survol construits avec d’autres entrées.')
    if (artifacts['SOMA_MASSILIA_URBAIN_v0_69.html']['sha256'] != B72.B71.B70.PARENT_SHA256 or
            artifacts['SOMA_MASSILIA_URBAIN_v0_70.html']['sha256'] != B72.B71.PARENT_SHA256 or
            artifacts['SOMA_MASSILIA_URBAIN_v0_71.html']['sha256'] != B72.PARENT_SHA256 or
            artifacts['metropole-viewer-v71.html']['sha256'] != PARENT_VIEWER71_SHA256):
        raise ValueError('Édition parente différente du parent gelé.')
    # Reuse the authoritative centre verifier. It checks manifest content,
    # administrative references and the SHA of all four layer assets per cell.
    expected = {'htmlSHA256': B72.B71.B70.PARENT_SHA256,
                'terrainFileSHA256': fingerprint(inside(game, 'data/v58/terrain.ign.json'))['sha256'],
                'territoryFileSHA256': fingerprint(inside(game, 'data/v69/territory.json'))['sha256'],
                'bootstrapSourceSHA256': fingerprint(inside(game, 'tools/metropole/bootstrap.py'))['sha256'],
                'terrainTilerSourceSHA256': fingerprint(inside(game, 'tools/v69/terrain_tiles.py'))['sha256']}
    world_root = inside(game, 'data/v69/world')
    world = verify_world(world_root, expected, territory_path=inside(game, 'data/v69/territory.json'))
    if reports['data/v72/BUILD_REPORT.json'].get('worldManifestSHA256') != fingerprint(world_root / 'manifest.json')['sha256']:
        raise ValueError('Rapport et manifeste du centre divergents.')
    # Detect a simultaneous edit while this validation was running. Sources are
    # small; original files are independently pinned again by B72.inputs.
    if inputs != B72.inputs() or sources != source_inputs(game):
        raise ValueError('Une entrée a changé pendant la validation du lancement.')
    return {'python': list(sys.version_info[:3]), 'inputs': inputs, 'sources': sources,
            'artifacts': artifacts, 'worldCells': len(world['tiles']),
            'worldManifest': fingerprint(world_root / 'manifest.json')}


def try_ready(game=ROOT):
    started = time.perf_counter()
    try:
        game = Path(game).resolve()
        receipt = document(inside(game, RECEIPT))
        body = {key: value for key, value in receipt.items() if key != 'contentSHA256'}
        if receipt.get('schema') != SCHEMA or receipt.get('contentSHA256') != digest(canonical(body)):
            raise ValueError('Reçu de lancement absent ou incohérent.')
        current = snapshot(game)
        if body != {'schema': SCHEMA, 'snapshot': current}:
            raise ValueError('Entrées ou sorties différentes du lancement préparé.')
        return {'ready': True, 'reason': 'content-verified', 'seconds': time.perf_counter() - started,
                'worldCells': current['worldCells']}
    except (OSError, ValueError, KeyError, TypeError, ImportError, AttributeError) as error:
        return {'ready': False, 'reason': str(error), 'seconds': time.perf_counter() - started}


def record_prepared(expected_sources, game=ROOT):
    """Record only after the complete launcher build chain returned success.

    expected_sources is captured before that chain; it prevents recording a
    successful preparation against concurrently changed transitive inputs.
    """
    game = Path(game).resolve()
    current = snapshot(game)
    if current['sources'] != expected_sources:
        raise ValueError('Sources modifiées pendant la préparation complète.')
    body = {'schema': SCHEMA, 'snapshot': current}
    encoded = canonical({**body, 'contentSHA256': digest(canonical(body))}) + b'\n'
    target = inside(game, RECEIPT)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.launch72-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(encoded)
        os.replace(temporary, target)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {'ready': True, 'worldCells': current['worldCells'], 'receipt': RECEIPT}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='contrôler le reçu sans reconstruire ni écrire')
    parser.parse_args()
    result = try_ready()
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result['ready'] else 1)
