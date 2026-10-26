#!/usr/bin/env python3
"""Attach source-bound routing preparation to an unserved immutable world clone.

Existing vector, DEM, surfaces and part assets are not rewritten. This publishes
prepared native topology; it does not certify physical access or activate play.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.metropole import attach_world_surfaces as S

A, P, checked = S.A, S.P, S.checked
CORE_SHA256 = 'd2dc3ea29f653a066e3a812b7db3b79c0c8bb81cb97319ad888618048f37d9ae'
BASELINE_SHA256 = 'f1a6ce4b5957f634ff9fdbfaccfcf11c9e0d22159d01758dd56e29513581a014'
QA_TOOL = Path(__file__).with_name('navigation_qa.py')


def core_header(manifest):
    core = manifest.get('navigationCore')
    if (not isinstance(core, dict) or core.get('scriptId') != 'soma-v63-nav-core'
            or core.get('version') != '0.63.0'
            or core.get('sha256') != CORE_SHA256 or core.get('baselineSHA256') != BASELINE_SHA256):
        raise ValueError('A pinned native routing core and baseline are required.')
    if manifest.get('physicalMovementReady') is not False or manifest.get('campaignRoutingActivated') is not False:
        raise ValueError('Routing preparation must not claim physical access or campaign activation.')
    return copy.deepcopy(core)


def validation_report(path, world, nav_sha, core, cells):
    path = Path(path).absolute()
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError('Navigation validation report exceeds its metadata budget.')
    report, sha = checked.read_json(path)
    proof = copy.deepcopy(report)
    claim = proof.pop('proofSHA256', None)
    expected = {'navigationManifestSHA256': nav_sha, 'sourceVectorManifestSHA256': world['sourcePackSHA256'],
        'sourcePbfSHA256': world['source']['sha256'], 'nativeTopologySHA256': world['nativeTopologySHA256'],
        'navigationCore': core, 'routingCoreSHA256': CORE_SHA256, 'baselineSHA256': BASELINE_SHA256,
        'cellsValidated': len(cells), 'cellSetSHA256': A.digest(A.canonical(sorted(cells))),
        'toolSHA256': checked.file_hash(QA_TOOL)}
    checks = report.get('checks', {})
    if (report.get('schema') != 'soma-metropole/navigation-validation/1' or report.get('status') != 'passed'
            or not checked.valid_hash(claim) or claim != A.digest(A.canonical(proof))
            or any(report.get(k) != v for k, v in expected.items())
            or type(report.get('cellsValidated')) is not int
            or not isinstance(checks, dict)
            or any(type(checks.get(k)) is not int or checks[k] != len(cells) for k in
                   ('cells', 'sourceAssetChecks', 'navigationAssetChecks', 'actualFrozenRouterValidatedGraphs'))
            or any(report.get(k) is not True for k in ('sourceUnchanged', 'navigationUnchanged'))
            or any(report.get(k) is not False for k in
                   ('physicalMovementReady', 'campaignRoutingActivated', 'physicalAccessibilityVerified', 'completeMetropole'))):
        raise ValueError('A complete independently validated, source/core/cell-bound navigation report is required.')
    with path.open('rb') as stream:
        raw = stream.read(16 * 1024 * 1024 + 1)
    if len(raw) > 16 * 1024 * 1024 or A.digest(raw) != sha:
        raise ValueError('Navigation validation report changed during reading.')
    return report, sha, raw


def native_structure(graph, tile):
    nodes, edges = graph['nodes'], graph['edges']
    sources, bikes, tags = graph.get('edgeSources'), graph.get('bicycleMasks'), graph.get('nodeTags')
    if (not isinstance(sources, list) or len(sources) != len(edges)
            or not isinstance(bikes, list) or len(bikes) != len(edges) or not isinstance(tags, dict)
            or any(type(mask) is not int or not 0 <= mask <= 3 for mask in bikes)):
        raise ValueError('Native edge provenance, bicycle masks and source-node tags are required.')
    names = {row[0] for row in nodes}
    bounds = tile['boundsL93']
    for name, e, n in nodes:
        if (not re.fullmatch(r'(?:n/[1-9]\d*|clip/[1-9]\d*/[1-9]\d*/[01]\.\d{12})', name)
                or not bounds[0]-.05 <= e <= bounds[2]+.05 or not bounds[1]-.05 <= n <= bounds[3]+.05):
            raise ValueError('A navigation node lacks native identity or lies outside its vector cell.')
    if any(k not in names or not k.startswith('n/') or not isinstance(v, dict) for k, v in tags.items()):
        raise ValueError('Source-node tags are not tied to native graph nodes.')
    for edge, source in zip(edges, sources):
        if (not isinstance(source, dict) or source.get('wayId') != edge[2]
                or not isinstance(edge[2], str) or not re.fullmatch(r'[1-9]\d*', edge[2])
                or type(source.get('segmentIndex')) is not int or source['segmentIndex'] < 1
                or any(type(source.get(k)) is not bool for k in ('startNative', 'endNative'))
                or not all(A.finite(source.get(k)) for k in ('t0', 't1'))
                or not 0 <= source['t0'] < source['t1'] <= 1):
            raise ValueError('Navigation edge lacks a bounded native segment provenance.')


def counters(world):
    return {**S.counters(world), 'navigationCells': sum(t.get('navigation') is not None for t in world['tiles'])}


def attach(world_dir, navigation_manifest, *, qa_report, progress=None):
    if progress is not None and not callable(progress):
        raise ValueError('Progress must be callable.')
    tools = {Path(__file__).resolve(), Path(S.__file__).resolve(), Path(A.__file__).resolve(),
             Path(P.__file__).resolve(), Path(checked.__file__).resolve(), QA_TOOL.resolve()}
    tool_hashes = {path: checked.file_hash(path) for path in tools}
    original_root = Path(world_dir).absolute()
    root = original_root.resolve()
    if original_root.is_symlink() or not root.is_dir():
        raise ValueError('A real unserved prepared-world clone is required.')
    identity = (root.stat().st_dev, root.stat().st_ino)
    manifest_path = P.safe_target(root, 'manifest.json', existing=True)
    world, world_sha = checked.read_json(manifest_path)
    index = P.validate_world(world)
    native = world.get('nativeTopologySHA256')
    if not checked.valid_hash(native) or not isinstance(world.get('coverage'), dict):
        raise ValueError('A verified native-topology edition and coverage are required.')
    source_path = Path(navigation_manifest).absolute()
    source_resolved = source_path.resolve()
    nav, nav_sha = checked.read_json(source_path)
    entries = A.validate_frame(nav, 'soma-metropole/navigation-tiles/1')
    vectors = {cell: tile for cell, tile in index.items() if tile.get('vector') is not None}
    if (set(entries) != set(vectors) or nav.get('sourceVectorManifest', {}).get('sha256') != world['sourcePackSHA256']
            or nav.get('sourcePbfSHA256') != world['source']['sha256'] or nav.get('nativeTopologySHA256') != native):
        raise ValueError('Navigation/vector/native-topology source edition differs from the world.')
    core = core_header(nav)
    qa_path = Path(qa_report).absolute()
    qa_resolved = qa_path.resolve()
    qa, qa_sha, qa_raw = validation_report(qa_path, world, nav_sha, core, vectors)
    cell_hashes = {cell: tile['contentSHA256'] for cell, tile in vectors.items()}
    relative = f'layers/navigation.{nav_sha[:12]}'
    target = P.safe_target(root, relative)
    observed = {}

    def stable():
        if (original_root.resolve() != root or (root.stat().st_dev, root.stat().st_ino) != identity
                or source_path.resolve() != source_resolved or qa_path.resolve() != qa_resolved):
            raise ValueError('World or navigation source path changed during attachment.')
        P.safe_target(root, 'manifest.json', existing=True)
        P.safe_target(root, relative)
        for path, sha in [(manifest_path, world_sha), (source_path, nav_sha), (qa_path, qa_sha), *tool_hashes.items(), *observed.items()]:
            if checked.file_hash(path) != sha:
                raise ValueError('A world, source, asset or tool changed during attachment.')

    previous = world['sourceManifests'].get('navigation')
    if previous is not None:
        if (previous != nav_sha or world.get('navigationAttachment', {}).get('navigationManifestSHA256') != nav_sha
                or world.get('navigationCore') != core
                or world.get('navigationAttachment', {}).get('validationReportSHA256') != qa_sha):
            raise ValueError('A different navigation edition is already attached.')
        for cell, tile in sorted(vectors.items()):
            expected = S.descriptor(entries[cell].get('navigation'))
            actual = S.descriptor(tile.get('navigation'))
            if (actual.get('path') != f'{relative}/tiles/{cell}.navigation.json.gz'
                    or any(actual.get(k) != expected.get(k) for k in ('bytes', 'sha256', 'encoding'))
                    or 'decodedBytes' in expected and actual.get('decodedBytes') != expected['decodedBytes']
                    or not A.bounds_equal(entries[cell].get('boundsL93'), tile['boundsL93'])
                    or entries[cell].get('cellHash') != tile['contentSHA256']):
                raise ValueError('Attached navigation metadata differs from its source.')
            path = P.safe_target(root, actual['path'], existing=True)
            if path.stat().st_size != actual['bytes'] or checked.file_hash(path) != actual['sha256']:
                raise ValueError('An attached navigation asset was altered or removed.')
        if (any(world['coverage'].get(k) != v for k, v in counters(world).items())
                or any(t.get('preparation') != S.preparation(t) for t in world['tiles'])
                or world.get('physicalMovementReady') is not False or world.get('campaignRoutingActivated') is not False):
            raise ValueError('Attached navigation counters or readiness have drifted.')
        descriptor = world.get('navigationValidation', {})
        if (descriptor.get('path') != relative + '/validation.json' or descriptor.get('sha256') != qa_sha
                or descriptor.get('bytes') != len(qa_raw) or descriptor.get('encoding') != 'json'
                or descriptor.get('proofSHA256') != qa['proofSHA256']
                or checked.file_hash(P.safe_target(root, descriptor['path'], existing=True)) != qa_sha):
            raise ValueError('Attached independent validation evidence was altered.')
        stable()
        return world
    if any(t.get('navigation') is not None for t in world['tiles']) or target.exists():
        raise ValueError('A clone without navigation assets is required; preserve the existing edition.')
    layers = root / 'layers'
    P.safe_target(root, 'layers')
    layers.mkdir(exist_ok=True)
    published = False
    target_identity = None
    temporary_manifest = None
    try:
        with tempfile.TemporaryDirectory(prefix='.navigation-attach-', dir=root) as temporary:
            stage = Path(temporary) / 'navigation'
            stage.mkdir()
            for number, (cell, tile) in enumerate(sorted(vectors.items()), 1):
                link = entries[cell]
                if not A.bounds_equal(link.get('boundsL93'), tile['boundsL93']) or link.get('cellHash') != tile['contentSHA256']:
                    raise ValueError('Navigation cell bounds/content differ from the vector edition.')
                desc = S.descriptor(link.get('navigation'))
                asset = P.safe_target(source_resolved.parent, desc.get('path'), existing=True)
                raw, graph, nbytes = A.read_asset(source_resolved.parent, desc)
                observed[asset] = desc['sha256']
                A.validate_navigation(graph, tile, tile['contentSHA256'], world['source']['sha256'], world['sourcePackSHA256'], cell_hashes)
                native_structure(graph, tile)
                status = graph.get('sourceStatus', {})
                if (graph.get('routingCoreSHA256') != core['sha256'] or graph.get('nativeTopologySHA256') != native
                        or any(status.get(k) is not False for k in ('physicalAccessibilityVerified', 'physicalMovementReady', 'campaignRoutingActivated'))):
                    raise ValueError('Navigation core/topology differs or physical readiness is unjustified.')
                copied = A.copy_asset(stage, cell, 'navigation', desc, raw, nbytes)
                copied['path'] = relative + '/' + copied['path']
                tile['navigation'] = copied
                if progress and number % 256 == 0:
                    progress({'cells': number, 'total': len(vectors)})
            for tile in world['tiles']:
                tile['preparation'] = S.preparation(tile)
            world['coverage'].update(counters(world))
            world['sourceManifests']['navigation'] = nav_sha
            world.update(navigationCore=core, physicalMovementReady=False, campaignRoutingActivated=False)
            (stage / 'validation.json').write_bytes(qa_raw)
            world['navigationValidation'] = {'path': relative + '/validation.json', 'bytes': len(qa_raw),
                'sha256': qa_sha, 'encoding': 'json', 'proofSHA256': qa['proofSHA256']}
            world['navigationAttachment'] = {'navigationManifestSHA256': nav_sha, 'sourceWorldManifestSHA256': world_sha,
                'toolSHA256': tool_hashes[Path(__file__).resolve()], 'sourcePbfSHA256': world['source']['sha256'],
                'validationReportSHA256': qa_sha, 'validationProofSHA256': qa['proofSHA256']}
            world.pop('manifestContentSHA256', None)
            world['manifestContentSHA256'] = A.digest(A.canonical(world))
            stable()
            if target.exists():
                raise ValueError('Navigation output appeared during attachment.')
            stage.rename(target)
            target_identity = (target.stat().st_dev, target.stat().st_ino)
            with tempfile.NamedTemporaryFile(dir=root, prefix='.navigation-manifest-', delete=False) as stream:
                temporary_manifest = Path(stream.name)
                stream.write(A.canonical(world) + b'\n')
                stream.flush()
                os.fsync(stream.fileno())
            stable()
            temporary_manifest.replace(manifest_path)
            temporary_manifest = None
            published = True
        return world
    finally:
        if temporary_manifest is not None:
            temporary_manifest.unlink(missing_ok=True)
        if (not published and target_identity is not None and not target.is_symlink() and target.is_dir()
                and target.resolve().is_relative_to(root) and (target.stat().st_dev, target.stat().st_ino) == target_identity):
            shutil.rmtree(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world', type=Path, required=True)
    parser.add_argument('--navigation', type=Path, required=True)
    parser.add_argument('--qa', type=Path, required=True)
    parser.add_argument('--progress', action='store_true')
    args = parser.parse_args()
    try:
        notify = (lambda item: print(json.dumps(item), file=sys.stderr, flush=True)) if args.progress else None
        result = attach(args.world, args.navigation, qa_report=args.qa, progress=notify)
        print(json.dumps({'navigationCells': result['coverage']['navigationCells'], 'physicalMovementReady': False}))
    except (ValueError, OSError, KeyError, TypeError, EOFError) as error:
        parser.exit(1, f'Navigation attachment refused: {error}\n')


if __name__ == '__main__':
    main()
