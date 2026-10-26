"""Routing publication binds sources and preserves immutable existing layers."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

GAME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GAME))
from tools.metropole import attach_world_navigation as N
from game.tests.metropole.test_attach_world_surfaces import Inputs as SurfaceInputs, NATIVE
from game.tests.metropole.test_attach_world_parts import SOURCE, PACK

CORE = N.CORE_SHA256


class Inputs:
    def __init__(self, base):
        original = SurfaceInputs(base)
        self.f, self.root = original.f, original.root
        self.source = Path(base) / 'navigation-input'
        self.source.mkdir()
        self.path = self.source / 'manifest.json'
        self.qa = self.source / 'qa.json'
        self.manifest = {'schema': 'soma-metropole/navigation-tiles/1', 'crs': 'EPSG:2154', 'units': 'm',
            'sourceVectorManifest': {'sha256': PACK}, 'sourcePbfSHA256': SOURCE, 'nativeTopologySHA256': NATIVE,
            'navigationCore': {'scriptId': 'soma-v63-nav-core', 'version': '0.63.0', 'sha256': CORE, 'baselineSHA256': N.BASELINE_SHA256},
            'physicalMovementReady': False, 'campaignRoutingActivated': False, 'tiles': []}
        self.graphs = []
        for tile in self.f.world['tiles'][:2]:
            e, n = tile['boundsL93'][0] + 5, tile['boundsL93'][1] + 5
            self.graphs.append({'schema': 'soma/navigation-source/1', 'sourcePbfSHA256': SOURCE, 'sourcePackSHA256': PACK,
                'nativeTopologySHA256': NATIVE, 'routingCoreSHA256': CORE, 'cellHashes': {tile['cellId']: tile['contentSHA256']},
                'sourceStatus': {'nodeTagsComplete': True, 'nativeNodeIdentity': True, 'vectorConstrained': True,
                    'physicalAccessibilityVerified': False, 'physicalMovementReady': False, 'campaignRoutingActivated': False},
                'nodes': [['n/1', e, n], ['n/2', e+1, n]], 'edges': [[0, 1, '1', 1, 3, 0, [tile['cellId']]]],
                'edgeSources': [{'wayId': '1', 'segmentIndex': 1, 't0': 0, 't1': 1, 'startNative': True, 'endNative': True}],
                'bicycleMasks': [3], 'nodeTags': {}, 'ways': {'1': {}}, 'turns': []})
            self.manifest['tiles'].append({'cellId': tile['cellId'], 'cellHash': tile['contentSHA256'], 'boundsL93': tile['boundsL93']})
        self.save()

    def save(self):
        for row, graph in zip(self.manifest['tiles'], self.graphs):
            row['navigation'] = N.checked.asset(self.source, f"tiles/{row['cellId']}.navigation.json.gz", graph)
            row['navigation']['decodedBytes'] = len(N.A.canonical(graph))
        self.path.write_bytes(N.A.canonical(self.manifest) + b'\n')
        self.refresh_qa()

    def refresh_qa(self):
        cells = sorted(row['cellId'] for row in self.manifest['tiles'])
        report = {'schema': 'soma-metropole/navigation-validation/1', 'status': 'passed',
            'navigationManifestSHA256': N.checked.file_hash(self.path), 'sourceVectorManifestSHA256': PACK,
            'sourcePbfSHA256': SOURCE, 'nativeTopologySHA256': NATIVE, 'navigationCore': self.manifest['navigationCore'],
            'routingCoreSHA256': CORE, 'baselineSHA256': N.BASELINE_SHA256, 'cellsValidated': len(cells),
            'cellSetSHA256': N.A.digest(N.A.canonical(cells)), 'toolSHA256': N.checked.file_hash(N.QA_TOOL),
            'sourceUnchanged': True, 'navigationUnchanged': True, 'physicalMovementReady': False,
            'campaignRoutingActivated': False, 'physicalAccessibilityVerified': False, 'completeMetropole': False,
            'checks': {k: len(cells) for k in ('cells', 'sourceAssetChecks', 'navigationAssetChecks', 'actualFrozenRouterValidatedGraphs')}}
        report['proofSHA256'] = N.A.digest(N.A.canonical(report))
        self.qa.write_bytes(N.A.canonical(report) + b'\n')


class NavigationAttachmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.i = Inputs(self.tmp.name)

    def reject(self):
        old = self.i.f.manifest.read_bytes()
        with self.assertRaises((ValueError, OSError, KeyError, TypeError)):
            N.attach(self.i.root, self.i.path, qa_report=self.i.qa)
        self.assertEqual(self.i.f.manifest.read_bytes(), old)
        self.assertFalse(list((self.i.root / 'layers').glob('navigation.*')) if (self.i.root / 'layers').exists() else [])

    def test_success_is_idempotent_and_leaves_existing_assets_untouched(self):
        before = {p: (p.stat().st_ino, p.read_bytes()) for p in self.i.root.rglob('*') if p.is_file() and p.name != 'manifest.json'}
        result = N.attach(self.i.root, self.i.path, qa_report=self.i.qa)
        self.assertEqual(result['coverage']['navigationCells'], 2)
        self.assertIsNone(result['tiles'][2]['navigation'])
        self.assertFalse(result['activationPerformed'])
        self.assertFalse(result['physicalMovementReady'])
        self.assertFalse(result['campaignRoutingActivated'])
        for p, (inode, data) in before.items():
            self.assertEqual((p.stat().st_ino, p.read_bytes()), (inode, data))
        raw = self.i.f.manifest.read_bytes()
        self.assertEqual(N.attach(self.i.root, self.i.path, qa_report=self.i.qa), result)
        self.assertEqual(self.i.f.manifest.read_bytes(), raw)

    def test_foreign_source_frames_and_core_are_refused(self):
        original = copy.deepcopy(self.i.manifest)
        for key, value in [('sourcePbfSHA256', 'f' * 64), ('nativeTopologySHA256', 'f' * 64),
                           ('sourceVectorManifest', {'sha256': 'f' * 64}), ('navigationCore', {'sha256': CORE}),
                           ('physicalMovementReady', True), ('campaignRoutingActivated', True)]:
            with self.subTest(key=key):
                self.i.manifest = copy.deepcopy(original)
                self.i.manifest[key] = value
                self.i.save()
                self.reject()

    def test_cell_set_and_bounds_are_exact(self):
        self.i.manifest['tiles'][0]['boundsL93'][0] += 1
        self.i.save()
        self.reject()
        self.i.manifest['tiles'].pop()
        self.i.save()
        self.reject()

    def test_graph_source_core_cell_and_native_bindings_are_checked(self):
        original = copy.deepcopy(self.i.graphs[0])
        for key, value in [('sourcePbfSHA256', 'f' * 64), ('sourcePackSHA256', 'f' * 64),
                           ('nativeTopologySHA256', 'f' * 64), ('routingCoreSHA256', 'f' * 64),
                           ('cellHashes', {'unknown': 'f' * 64})]:
            with self.subTest(key=key):
                self.i.graphs[0] = copy.deepcopy(original)
                self.i.graphs[0][key] = value
                self.i.save()
                self.reject()

    def test_physical_readiness_claims_and_invalid_edges_are_rejected(self):
        original = copy.deepcopy(self.i.graphs[0])
        for key in ('physicalAccessibilityVerified', 'physicalMovementReady', 'campaignRoutingActivated', 'nativeNodeIdentity'):
            self.i.graphs[0] = copy.deepcopy(original)
            self.i.graphs[0]['sourceStatus'][key] = False if key == 'nativeNodeIdentity' else True
            self.i.save()
            self.reject()
        self.i.graphs[0] = copy.deepcopy(original)
        self.i.graphs[0]['edges'][0][1] = 999
        self.i.save()
        self.reject()

    def test_bad_asset_hash_symlink_and_traversal_are_rejected(self):
        self.i.manifest['tiles'][0]['navigation']['sha256'] = 'f' * 64
        self.i.path.write_bytes(N.A.canonical(self.i.manifest))
        self.i.refresh_qa()
        self.reject()
        self.i.save()
        asset = self.i.source / self.i.manifest['tiles'][0]['navigation']['path']
        outside = Path(self.tmp.name) / 'outside.gz'
        outside.write_bytes(asset.read_bytes())
        asset.unlink()
        asset.symlink_to(outside)
        self.reject()
        asset.unlink()
        self.i.save()
        self.i.manifest['tiles'][0]['navigation']['path'] = '../outside.gz'
        self.i.path.write_bytes(N.A.canonical(self.i.manifest))
        self.i.refresh_qa()
        self.reject()

    def test_final_manifest_failure_rolls_back_only_new_navigation(self):
        replace = Path.replace
        def fail(source, target):
            if source.name.startswith('.navigation-manifest-'):
                raise OSError('simulated publication failure')
            return replace(source, target)
        with patch.object(Path, 'replace', fail):
            self.reject()
        self.assertTrue((self.i.root / 'metadata/existing-parts.json').exists())

    def test_source_manifest_mutation_during_copy_cannot_publish(self):
        original = N.A.copy_asset
        changed = False
        def mutate(*args, **kwargs):
            nonlocal changed
            result = original(*args, **kwargs)
            if not changed:
                self.i.path.write_bytes(self.i.path.read_bytes() + b'\n')
                changed = True
            return result
        with patch.object(N.A, 'copy_asset', side_effect=mutate):
            self.reject()

    def test_existing_layers_symlink_is_not_followed(self):
        outside = Path(self.tmp.name) / 'outside-layers'
        outside.mkdir()
        (self.i.root / 'layers').symlink_to(outside, target_is_directory=True)
        self.reject()
        self.assertEqual(list(outside.iterdir()), [])

    def test_altered_attached_asset_is_not_silently_reused(self):
        result = N.attach(self.i.root, self.i.path, qa_report=self.i.qa)
        asset = self.i.root / result['tiles'][0]['navigation']['path']
        asset.write_bytes(b'altered')
        before = self.i.f.manifest.read_bytes()
        with self.assertRaises(ValueError):
            N.attach(self.i.root, self.i.path, qa_report=self.i.qa)
        self.assertEqual(before, self.i.f.manifest.read_bytes())

    def test_independent_report_must_cover_exact_source_core_cells_and_checker(self):
        original = json.loads(self.i.qa.read_bytes())
        for key, value in [('navigationManifestSHA256', 'f'*64), ('cellSetSHA256', 'f'*64),
                           ('cellsValidated', 1), ('toolSHA256', 'f'*64), ('status', 'incomplete'),
                           ('sourceUnchanged', False), ('physicalMovementReady', True)]:
            with self.subTest(key=key):
                report = copy.deepcopy(original)
                report[key] = value
                report.pop('proofSHA256')
                report['proofSHA256'] = N.A.digest(N.A.canonical(report))
                self.i.qa.write_bytes(N.A.canonical(report))
                self.reject()

    def test_arbitrary_core_hash_is_refused_even_if_graph_and_report_agree(self):
        self.i.manifest['navigationCore']['sha256'] = '9'*64
        for graph in self.i.graphs:
            graph['routingCoreSHA256'] = '9'*64
        self.i.save()
        report = json.loads(self.i.qa.read_bytes())
        report['routingCoreSHA256'] = '9'*64
        report.pop('proofSHA256')
        report['proofSHA256'] = N.A.digest(N.A.canonical(report))
        self.i.qa.write_bytes(N.A.canonical(report))
        self.reject()

    def test_native_shape_is_required_in_addition_to_report(self):
        original = copy.deepcopy(self.i.graphs[0])
        for key, value in [('edgeSources', []), ('bicycleMasks', []), ('nodeTags', None),
                           ('nodes', [['1', 0, 0], ['2', 1, 0]])]:
            self.i.graphs[0] = copy.deepcopy(original)
            self.i.graphs[0][key] = value
            self.i.save()
            self.reject()

    def test_attached_validation_evidence_is_checked_on_reuse(self):
        result = N.attach(self.i.root, self.i.path, qa_report=self.i.qa)
        path = self.i.root / result['navigationValidation']['path']
        path.write_bytes(b'altered proof')
        with self.assertRaises(ValueError):
            N.attach(self.i.root, self.i.path, qa_report=self.i.qa)


if __name__ == '__main__':
    unittest.main()
