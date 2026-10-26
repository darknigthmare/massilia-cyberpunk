import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
SPEC = importlib.util.spec_from_file_location('viewer70_builder', ROOT / 'tools/build_metropole_viewer_v70.py')
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class Viewer70BuilderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.output = M.build().decode('utf-8')
        cls.original = M.V69.build().decode('utf-8')
        cls.controller = M.V69.script(cls.output, 'viewer-metropole-viewer')

    def test_whitelist_has_real_pinned_core_and_no_campaign_runtime(self):
        self.assertEqual(hashlib.sha256(M.V69.script(self.output, 'viewer-source-router63').encode()).hexdigest(), M.CORE_SHA256)
        for name in ['viewer-world-index70', 'viewer-material-extension70', 'viewer-route-preview70', 'viewer-runtime70']:
            self.assertTrue(M.V69.script(self.output, name))
        self.assertNotIn('<script src=', self.output)
        for marker in ['soma-v37-persistence', 'soma-v67-world-runtime', 'localStorage.', 'sessionStorage.', 'legacyState']:
            self.assertNotIn(marker, self.output)
        for identifier in ['viewer-geographic-core', 'viewer-terrain-core', 'viewer-dimension-core', 'viewer-architecture-core', 'viewer-roof-core', 'viewer-streaming-core']:
            self.assertEqual(M.V69.script(self.output, identifier), M.V69.script(self.original, identifier))

    def test_geometry_patch_changes_only_appearance_call(self):
        old = M.V69.script(self.original, 'viewer-metropole-viewer-core').strip('\n')
        new = M.V69.script(self.output, 'viewer-metropole-viewer-core').strip('\n')
        self.assertEqual(new, old.replace('const material=A.appearance(p,id),canonical=',
            'const material=root.__SOMA_MATERIAL70_CORE__.appearance(p,id),canonical=', 1))

    def test_version_return_link_and_source_receipts_are_explicit(self):
        data = json.loads(M.V69.script(self.output, 'soma-viewer-data', json_only=True))
        self.assertEqual(data['version'], '0.70.0')
        self.assertEqual(data['returnToGame'], 'SOMA_MASSILIA_URBAIN_v0_70.html')
        self.assertEqual(data['sourceHTML69SHA256'], hashlib.sha256(M.V69.SOURCE.read_bytes()).hexdigest())
        self.assertEqual(data['sourceViewerSHA256'], hashlib.sha256(self.original.encode()).hexdigest())
        self.assertIn('SURVOL MÉTROPOLITAIN · 0.70', self.output)
        self.assertIn('href="SOMA_MASSILIA_URBAIN_v0_70.html"', self.output)
        self.assertNotIn('href="SOMA_MASSILIA_URBAIN_v0_69.html"', self.output)

    def test_controller_uses_index_and_an_exclusive_drained_lease(self):
        for text in ['Index.createWorldIndex(', 'worldIndex.desiredTiles(', 'worldIndex?.cellAt(', 'worldIndex?.communeAt(', 'worldIndex?.destination(',
                     'narrowContext:()=>route70Context', 'await Promise.allSettled([...route70Reads])', 'if(route70Locked)return',
                     "blocked=route70Locked||", 'if(store&&!route70Locked&&', 'route70Locked||!Number.isFinite(e)',
                     'if(!route70Locked){buildOne();renderer.draw();']:
            self.assertIn(text, self.controller)
        self.assertNotIn('manifest.tiles.find(', self.controller)
        self.assertNotIn('manifest.tiles.filter(t=>flightLayers(t)).map(', self.controller)
        self.assertIn('root.__SOMA_METROPOLE_VIEWER__=root.__SOMA_METRO_VIEWER__', self.controller)
        self.assertIn('maxInFlight:2', self.controller)

    def test_route_controls_are_unique_and_not_auto_computed(self):
        for name in ['route70-open', 'route70-dialog', 'route70-form', 'route70-map', 'route70-compute', 'route70-close', 'route70-status', 'route70-mark-start', 'route70-summary']:
            self.assertEqual(self.output.count('id="' + name + '"'), 1)
        self.assertIn('Aucun lien entre les coordonnées saisies et les axes', self.output)
        self.assertIn('Les ponts, tunnels, voies couvertes', self.output)
        self.assertIn('required', self.output)
        details = re.search(r'<details\b([^>]*\bid="route70-precise"[^>]*)>([\s\S]*?)</details>', self.output)
        self.assertIsNotNone(details)
        self.assertNotIn('open', details[1])
        self.assertIn('Coordonnées précises (Lambert-93)', details[2])
        for name in ['route70-start-e', 'route70-start-n', 'route70-end-e', 'route70-end-n']:
            self.assertIn('id="'+name+'"', details[2])
        self.assertIn('Marquer le départ ici', self.output)
        self.assertIn('Analyser le trajet vers ici', self.output)

    def test_changed_or_duplicate_anchors_refuse_instead_of_silently_patching(self):
        source = M.V69.script(self.original, 'viewer-metropole-viewer')
        for text in [source.replace('wanted=desiredTiles(', 'wanted=otherTiles(', 1), source + source]:
            with self.assertRaisesRegex(ValueError, 'Ancre'):
                M.derive_controller(text)
        with self.assertRaisesRegex(ValueError, 'Ancre'):
            M.derive_controller(self.controller)
        with self.assertRaisesRegex(ValueError, 'Ancre'):
            M.replace_once('two two', 'two', 'one')

    def test_source_sha_and_frozen_core_are_required(self):
        with self.assertRaisesRegex(ValueError, 'SHA256'):
            M.build(expected_sha='0' * 64)
        with patch.object(M.V69, 'script', side_effect=lambda html, identifier, **kw: 'wrong' if identifier == 'soma-v63-nav-core' else ''):
            with patch.object(M.V69, 'build', return_value=b'<html></html>'):
                with self.assertRaisesRegex(ValueError, 'empreinte'):
                    M.build()

    def test_derived_modules_are_valid_javascript(self):
        for name in ['viewer-metropole-viewer', 'viewer-metropole-viewer-core', 'viewer-runtime70']:
            code = M.V69.script(self.output, name)
            checked = subprocess.run(['node', '--check'], input=code, text=True, capture_output=True)
            self.assertEqual(checked.returncode, 0, checked.stderr)


if __name__ == '__main__':
    unittest.main()
