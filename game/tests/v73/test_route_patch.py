"""Strict v73 derivation preserves the actual inherited viewer lifecycle."""
from pathlib import Path
import re
import sys
import unittest

GAME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GAME))
from tools import v71_route_viewer, v72_routing, v73_routing


def parent_runtime():
    return v72_routing.runtime(v71_route_viewer.runtime((GAME / 'src/v70/viewer-runtime.js').read_text()))


class Route73PatchTests(unittest.TestCase):
    def test_lifecycle_and_source_presentation_are_preserved(self):
        output = v73_routing.runtime(parent_runtime())
        for preserved in ['await current.lease?.release()', 'current.computeAbort?.abort()',
                          'await context.readRouteAsset(descriptor,options)',
                          'root.__SOMA_ROUTE71_RUNTIME__?.render(result)', 'if(inFlight)throw',
                          'corridorStage=1', 'canExpand=result.continuation?.available===true']:
            self.assertIn(preserved, output)
        for addition in ['q.corridorGuide={e:guide.e,n:guide.n}', "setPoint('guide',markedGuide)",
                         'guideWorld!==context.world()', 'guideIsRouteWaypoint:false',
                         "$('route73-mark-guide').onclick", "$('route73-clear-guide').onclick"]:
            self.assertIn(addition, output)

    def test_changed_or_duplicate_derivation_anchor_fails_closed(self):
        source = parent_runtime()
        for anchor in ["arrivalKind='camera',corridorStage=0,canExpand=false;",
                       '    function fill(request){', "    $('route72-expand').onclick=()=>"]:
            for changed in [source.replace(anchor, ''), source.replace(anchor, anchor * 2)]:
                with self.assertRaises(ValueError):
                    v73_routing.runtime(changed)
        for html in ['', '<script id="viewer-route-preview70"></script>' * 2]:
            with self.assertRaises(ValueError):
                v73_routing.patch_viewer(html, {'route-guided-core': 'valid'})

    def test_campaign_is_pass_through_and_script_close_is_rejected(self):
        html = '<html>campaign unchanged</html>'
        self.assertEqual(v73_routing.patch_html(html, {}), html)
        with self.assertRaises(ValueError):
            v73_routing.patch_viewer('', {'route-guided-core': '</ScRiPt>'})

    def test_viewer_markup_explains_selection_and_has_accessible_optional_fields(self):
        source = '<script id="viewer-route-preview70">old</script><script id="viewer-runtime70">' + parent_runtime() + '</script>'
        source += '<form id="route70-form"></form><p>Le corridor conserve les deux extrémités et charge au plus 96 cellules</p>'
        output = v73_routing.patch_viewer(source, {'route-guided-core': 'const derived73=true;'})
        self.assertEqual(output.count('id="route73-mark-guide"'), 1)
        self.assertEqual(output.count('id="route73-clear-guide"'), 1)
        self.assertIn('ce n’est pas une étape imposée au trajet', output)
        self.assertIn('aucun raccord n’est créé', output)
        self.assertIn('au plus 96 cellules', output)
        for axis in ['e', 'n']:
            self.assertRegex(output, '<label>[^<]*<input id="route70-guide-' + axis + '" type="number" step="any"></label>')


if __name__ == '__main__':
    unittest.main()
