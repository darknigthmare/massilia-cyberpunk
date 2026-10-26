"""Optional WebGL regression using Playwright and Chromium, on a fresh save."""
from pathlib import Path
import argparse
import json
import shutil
import sys
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8765/SOMA_MASSILIA_URBAIN_v0_68.html')
    parser.add_argument('--version', choices=['0.68','0.69'], default='0.68')
    parser.add_argument('--chromium', default=shutil.which('chromium'))
    parser.add_argument('--screenshots', type=Path)
    args = parser.parse_args()
    with sync_playwright() as p:
        launch = {'headless':True, 'args':['--no-sandbox', '--enable-webgl',
                  '--use-angle=swiftshader', '--enable-unsafe-swiftshader']}
        if args.chromium:
            launch['executable_path'] = args.chromium
        browser = p.chromium.launch(**launch)
        context = browser.new_context(viewport={'width':1440, 'height':1000})
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        response = page.goto(args.url, wait_until='domcontentloaded', timeout=90000)
        assert response.status == 200
        page.wait_for_function('window.__SOMA_V68__ && window.__SOMA_TERRAIN56__?.grid && window.__SOMA_GROUP64__?.ready', timeout=90000)
        if args.version=='0.69':
            page.wait_for_function('window.__SOMA_V69__',timeout=90000)
        assert args.version in page.title()
        assert 'Marseille augmentée' in page.title()
        assert page.evaluate("window.__SOMA_V68__.ambience()") == 'cyberpunk'
        assert page.locator('body').evaluate("node => node.classList.contains('soma-cyberpunk68') && !node.classList.contains('soma-wasteland68')")
        print(f'Chargement v{args.version} réussi.', file=sys.stderr, flush=True)

        page.get_by_role('button', name='Explorer Marseille réelle', exact=True).click(timeout=90000)
        page.wait_for_function('zone?.v52District && zone.static && zone.v68Architecture?.buildings > 0', timeout=90000)
        street = page.evaluate('''() => ({
          zone:zone.id, buildings:zone.v68Architecture.buildings, roads:zone.roads.length,
          size:[zone.w,zone.h], source:window.__SOMA_V54__.snapshot().source.sha256,
          terrain:window.__SOMA_TERRAIN56__.pack.sha256,
          status:window.__SOMA_V37_SAVE__.getStatus(), architecture:window.__SOMA_V68__.snapshot(),
          activeArchitecture:zone.v68Architecture,
          shaderLinked:renderer.gl.getProgramParameter(renderer.p,renderer.gl.LINK_STATUS)
        })''')
        assert street['buildings'] > 0 and street['roads'] > 0
        assert street['size'] == [250, 250]
        assert street['source'] == '0d16c8cd7c77945b22cb0a018f19a7d0bd1b3a2cbf05c137fa62e3aa8fd56d82'
        assert street['terrain'] == '38eadcbdf00a64384e00923a85ce9886ec4d9a420d610dc9ccfd4449c41f344b'
        assert not street['status']['blocked'], street['status']
        assert street['shaderLinked'], 'The modified emissive shader must compile and link in WebGL.'
        assert street['activeArchitecture']['litWindows'] > 0
        assert street['activeArchitecture']['neonPanels'] > 0
        if args.version=='0.69':
            measured=page.evaluate('''() => ({
              summary:window.__SOMA_HEIGHTS69__.summary(),
              rendered:zone.v50Footprints.filter(f=>f.v69?.heightKind==='eaves').map(f=>({
                height:f.height,ground:f.groundAltitude,roofSurveyed:f.v69.roofSurveyed,
                roofGeometrySource:f.v69.roofGeometrySource,roofModelled:f.v68.roofModelled}))
            })''')
            assert measured['summary']['measuredReferences']==14279 and measured['rendered'],measured
            assert all(f['height']>0 and f['ground'] is not None and f['roofSurveyed'] is False
                       and f['roofGeometrySource']=='flat-approximation' and f['roofModelled'] is False
                       for f in measured['rendered']),measured
        print('Exploration réelle et sources vérifiées.', file=sys.stderr, flush=True)
        if args.screenshots:
            args.screenshots.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(args.screenshots/'street-v68.png'))

        # Open the in-game options, then use its actual new control.
        page.evaluate("openModal('options')")
        select = page.locator('[data-v68-ambience]')
        select.select_option('neutral')
        assert page.locator('#gl').evaluate("node => getComputedStyle(node).filter") == 'none'
        select.select_option('cyberpunk')
        assert page.locator('body').evaluate("node => node.classList.contains('soma-cyberpunk68')")
        visual_only = page.evaluate('''() => {
          const key='soma-massilia-v68-visual';
          const otherKeys=()=>JSON.stringify(Object.keys(localStorage).filter(k=>k!==key).sort().map(k=>[k,localStorage.getItem(k)]));
          const campaign=JSON.stringify(state.v67), others=otherKeys();
          const control=document.querySelector('[data-v68-ambience]');
          control.value='neutral';control.dispatchEvent(new Event('change',{bubbles:true}));
          control.value='cyberpunk';control.dispatchEvent(new Event('change',{bubbles:true}));
          return {campaignUnchanged:JSON.stringify(state.v67)===campaign,otherKeysUnchanged:otherKeys()===others};
        }''')
        assert visual_only['campaignUnchanged'] and visual_only['otherKeysUnchanged']
        page.evaluate('closeModals()')

        # Exercise the real grouped campaign exporter, importer and final saver.
        save = page.evaluate('''async () => {
          paused=true;
          const G=window.__SOMA_GROUP64__, text=G.exportText();
          const before=JSON.parse(JSON.stringify(state.v67)), credits=state.credits;
          G.validate(text); state.credits+=17;
          const restored=await G.importText(text,true);
          const valid=window.__SOMA_V37_SAVE__.snapshot();
          window.__SOMA_V37_SAVE__.validate(valid);
          return {restored, credits:state.credits, expectedCredits:credits,
            retainedSchema:state.v67.schema, retainedConversation:JSON.stringify(before.conversations)===JSON.stringify(state.v67.conversations),
            status:window.__SOMA_V37_SAVE__.getStatus()};
        }''')
        assert save['restored']['ok'], save
        assert save['credits'] == save['expectedCredits'] and save['retainedConversation']
        assert save['retainedSchema'] == 'soma-v67/1' and not save['status']['blocked']
        print('Sauvegarde groupée exportée, restaurée et validée.', file=sys.stderr, flush=True)

        # Inspect a genuine fully tagged sloping roof from the supplied OSM pack.
        assert page.evaluate("() => window.__SOMA_V54__.enter('V52-MC-W04-S01')")
        roof = page.evaluate('''() => {
          const f=zone.v50Footprints.find(b=>b.sourceId==='osm/way/265248513');
          return {zone:zone.id, footprint:f, architecture:zone.v68Architecture};
        }''')
        assert roof['footprint']['v68']['roofModelled'], roof
        assert roof['footprint']['v68']['roofShape'] == 'skillion'
        assert roof['footprint']['height'] == 9 and roof['footprint']['minHeight'] == 6
        print('Toit incliné OSM réel vérifié.', file=sys.stderr, flush=True)

        metropole=None
        if args.version=='0.69':
            metropole=page.evaluate('''async () => {
              const M=window.__SOMA_V69__,entry=await M.load('V52-MC-33',{require3D:true});
              return {snapshot:M.snapshot(),readyFor3D:entry.readyFor3D,layers:Object.keys(entry.layers)};
            }''')
            assert metropole['readyFor3D'],metropole
            assert len(metropole['layers'])==4 and metropole['snapshot']['target']['communes']==92
            assert metropole['snapshot']['target']['boundaryAvailable'] is True
            assert metropole['snapshot']['heightReferences']['measuredReferences']==14279
            assert metropole['snapshot']['completeMetropole'] is False
            assert page.evaluate("() => window.__SOMA_V54__.enter('V52-MC-W04-N01')")
            landmark=page.evaluate('''() => {
              const p=window.__SOMA_PARTS69__.parentStatus('osm/relation/1069937');
              return {parent:{status:p.status,coverage:p.coverageRatio,residualArea:p.residualAreaM2,residualPolicy:p.residualPolicy},
                derivedFragments:zone.v50Footprints.filter(f=>f.v69?.derivedBuildingParts).length,
                linkedParts:zone.v50Footprints.filter(f=>f.v69?.partParent).length,
                modelledRoofs:zone.v50Footprints.filter(f=>f.v69?.roofGeometrySource==='osm-parametric').length,
                sight:window.__SOMA_SIGHT61__.sourceIndex(zone).boxes.length,
                terrain:window.__SOMA_TERRAIN56__.v69.snapshot()};
            }''')
            assert landmark['parent']['status']=='derived-partial' and landmark['parent']['residualArea']>800
            assert landmark['parent']['residualPolicy']=='unresolved-footprint-only'
            assert landmark['derivedFragments']==0 and landmark['linkedParts']>0 and landmark['modelledRoofs']>0 and landmark['sight']>0,landmark
            metropole['landmark']=landmark
            if args.screenshots:
                page.screenshot(path=str(args.screenshots/'major-v69.png'))
            print('Métropole : quatre couches validées, parties de la Major et visée vérifiées.',file=sys.stderr,flush=True)

        # Reopening the same browser storage must restore a valid campaign.
        page.reload(wait_until='domcontentloaded', timeout=90000)
        page.wait_for_function('window.__SOMA_V68__ && window.__SOMA_GROUP64__?.ready', timeout=90000)
        if args.version=='0.69':
            page.wait_for_function('window.__SOMA_V69__',timeout=90000)
        reloaded = page.evaluate('''() => ({status:window.__SOMA_V37_SAVE__.getStatus(),
          schema:state.v67.schema, ambience:window.__SOMA_V68__.ambience()})''')
        assert not reloaded['status']['blocked'], reloaded
        assert reloaded['schema'] == 'soma-v67/1' and reloaded['ambience'] == 'cyberpunk'

        # A deliberate ungraded preference survives reload in the actual game.
        page.evaluate("openModal('options')")
        page.locator('[data-v68-ambience]').select_option('neutral')
        page.reload(wait_until='domcontentloaded',timeout=90000)
        page.wait_for_function('window.__SOMA_V68__ && window.__SOMA_GROUP64__?.ready',timeout=90000)
        assert page.evaluate("window.__SOMA_V68__.ambience()") == 'neutral'
        assert page.locator('#gl').evaluate("node => getComputedStyle(node).filter") == 'none'

        # Legacy preference is seeded once via storage state, not re-injected on reload.
        parsed=urlsplit(args.url)
        origin=f'{parsed.scheme}://{parsed.netloc}'
        legacy_context=browser.new_context(storage_state={'cookies':[], 'origins':[{
            'origin':origin,'localStorage':[{'name':'soma-massilia-v68-visual','value':'wasteland'},
                                          {'name':'qa-unrelated-visual','value':'preserved'}]}]})
        legacy_page=legacy_context.new_page()
        legacy_page.on('pageerror',lambda error:errors.append(str(error)))
        legacy_page.goto(args.url,wait_until='domcontentloaded',timeout=90000)
        legacy_page.wait_for_function('window.__SOMA_V68__',timeout=90000)
        migration=legacy_page.evaluate('''() => ({ambience:window.__SOMA_V68__.ambience(),
          stored:localStorage.getItem('soma-massilia-v68-visual'),
          unrelated:localStorage.getItem('qa-unrelated-visual'),
          oldClass:document.body.classList.contains('soma-wasteland68')})''')
        assert migration == {'ambience':'cyberpunk','stored':'cyberpunk','unrelated':'preserved','oldClass':False}
        legacy_context.close()
        assert not errors, errors
        print(json.dumps({'passed':True, 'webgl':True, 'street':street,
                          'groupedSave':save, 'roof':roof, 'reload':reloaded,
                          'visualOnly':visual_only,'legacyMigration':migration,
                          'metropole':metropole,
                          'pageErrors':errors}, ensure_ascii=False))
        browser.close()


if __name__ == '__main__':
    main()
