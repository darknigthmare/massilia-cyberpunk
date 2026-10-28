"""Strict hooks on the real protected viewer, without geographic rebuilds."""
from pathlib import Path
import sys
import unittest

GAME=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(GAME))
sys.path.insert(0,str(GAME/'tools'))
from tools import build_metropole_viewer_v70 as V70
from tools import v71_route_viewer as P


class RoutePatchTests(unittest.TestCase):
    def test_real_controller_owns_gpu_lifecycle_and_complete_resident_terrain(self):
        original=(GAME/'src/v69/metropole-viewer.js').read_text()
        parent=V70.derive_controller(original)
        derived=P.controller(parent)
        self.assertIn('route71Span',derived)
        self.assertIn('tile.terrain?.complete!==true',derived)
        self.assertIn('!targetIds.has(tile.cellId)||!renderer.registry.meshes.has(tile.cellId)',derived)
        self.assertIn('if(route71Mesh)driver.release(route71Mesh.handle)',derived)
        self.assertIn('stop(){route71Set(null);worldLoader.cancel();',derived)
        self.assertIn('route70Reads.add(task)',derived)
        self.assertEqual((GAME/'src/v69/metropole-viewer.js').read_text(),original)

    def test_real_runtime_keeps_lease_cancellation_and_enriches_existing_ui(self):
        parent=(GAME/'src/v70/viewer-runtime.js').read_text();derived=P.runtime(parent)
        self.assertIn('root.__SOMA_ROUTE71_RUNTIME__?.render(result)',derived)
        self.assertIn('root.__SOMA_ROUTE71_PRESENTATION__.choiceLabel(q)',derived)
        self.assertIn('await current.lease?.release()',derived)
        self.assertIn('current.computeAbort?.abort()',derived)
        self.assertIn('current.abort.signal.aborted',derived)

    def test_anchor_drift_and_duplicate_fail_instead_of_silently_skipping(self):
        parent=V70.derive_controller((GAME/'src/v69/metropole-viewer.js').read_text())
        for changed in [parent.replace('      renderedFrames++;collectErrors();',''),parent.replace('      renderedFrames++;collectErrors();','      renderedFrames++;collectErrors();'*2)]:
            with self.assertRaises(ValueError):P.controller(changed)
        with self.assertRaises(ValueError):P.runtime('changed runtime')
        with self.assertRaises(ValueError):P.script('bad',{'bad':'</script>'})

    def test_viewer_only_extension_preserves_campaign_bytes(self):
        campaign='<html>existing campaign</html>'
        self.assertEqual(P.patch_html(campaign,{}),campaign)


if __name__=='__main__':unittest.main()
