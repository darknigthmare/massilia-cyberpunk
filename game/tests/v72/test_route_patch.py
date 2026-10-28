"""Exercise the actual inherited runtime, with strict derivation anchors."""
from pathlib import Path
import re
import sys
import unittest

GAME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GAME))
from tools import v71_route_viewer as parent
from tools import v72_routing as routing


class Route72PatchTests(unittest.TestCase):
    def test_runtime_keeps_the_lease_reader_and_source_axis_presentation(self):
        source = parent.runtime((GAME / 'src/v70/viewer-runtime.js').read_text())
        output = routing.runtime(source)
        for preserved in ['await current.lease?.release()', 'current.computeAbort?.abort()',
                          'await context.readRouteAsset(descriptor,options)',
                          'root.__SOMA_ROUTE71_RUNTIME__?.render(result)', 'if(inFlight)throw']:
            self.assertIn(preserved, output)
        self.assertIn('corridorStage=1', output)
        self.assertIn('canExpand=result.continuation?.available===true', output)
        self.assertIn('void controller.compute(request())', output)

    def test_duplicate_or_missing_anchors_fail_closed(self):
        source = parent.runtime((GAME / 'src/v70/viewer-runtime.js').read_text())
        anchor = "let choices=null,markedStart=null,markedWorld=null,arrivalKind='camera';"
        for changed in [source.replace(anchor, ''), source.replace(anchor, anchor * 2)]:
            with self.assertRaises(ValueError):
                routing.runtime(changed)
        for html in ['', '<script id="viewer-route-preview70"></script>' * 2]:
            with self.assertRaises(ValueError):
                routing.patch_viewer(html, {'route-corridor-core': 'valid'})

    def test_viewer_patch_leaves_campaign_bytes_unchanged(self):
        campaign = '<html>original campaign bytes</html>'
        self.assertEqual(routing.patch_html(campaign, {}), campaign)
        with self.assertRaises(ValueError):
            routing.patch_viewer('', {'route-corridor-core': '</script>'})


if __name__ == '__main__':
    unittest.main()
