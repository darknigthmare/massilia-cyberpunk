#!/usr/bin/env python3
"""Build edition 0.72 over the verified, unchanged 0.71 sources and world."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import tempfile

import build_v71 as B71
from build_v68 import replace_once, rewrite_script

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / 'SOMA_MASSILIA_URBAIN_v0_72.html'
REPORT = ROOT / 'data/v72/BUILD_REPORT.json'
PARENT_SHA256 = '6bd174abf56504640edbc8c92a4d9279fb76f0d6b079f3d4ae4bbb5a948c333d'
VERSION = '0.72.0'
EXTENSIONS = ('tools.v72_fidelity', 'tools.v72_routing',
              'tools.v72_contact_sharing', 'tools.v72_netrunner')
FROZEN_PARENT_SOURCES = {
    'build.py': '94c6966abaa2e11f85af578ec14d6deba8ac7b400572a6747ba248f3276454cf',
    'build_v68.py': '04e6ac1adde4e656166710176a52597a65202b87ecd33ea7e1f15ab9eb55a1c0',
    'build_v69.py': '74a20fbc6366c46253dbfef5ae8d3b732270d06cdb589d6305be51c96c62d7ee',
    'build_v70.py': '4788f3e072f1708cecae0235aa5da5e88977a1a39c064537507db2126ee637ac',
    'build_v71.py': 'b051415237c2e2d2234d2996e25e1decd768f98ea6a75965bd109d9889953cd4',
    'src/v67/world-runtime.js': '443146ea95abd6e70df221407a3b590827bf63235efcaf7ad2ef8a01fd397f43',
    'src/v68/architecture-core.js': '60acf299e9a8cc49a33491b24c6c00e906234f74869c828d7a4d7c1672c8fd01',
    'src/v68/building-renderer.js': '92837c8b37f321d8182b3edf8c9cb130ec4c254703973a78cc7f753e8dc13221',
    'src/v68/world-runtime.js': '9294390e7071d10ec125043ef899fa92ebfeece23ce87b06b5662c51b5a42b42',
    'src/v69/building-parts.js': '14a8b2767f4b347a6daa76cde6f4a889ae10e400b644aa9f06db0b6387b224b3',
    'src/v69/height-references.js': 'fb2e12223d937c5f32c49b1d09da5da14485b9d7f3e59fcd7c53c0b713eb924c',
    'src/v69/metropole-viewer-core.js': 'f1f2df8692635c8c25acfe12aef1ca4277f1893528a8748260233e02534f61c1',
    'src/v69/metropole-viewer.html': '08528097b8e41057c23928d53fc91bed7d7a871cc2346afa0083f261e0533d19',
    'src/v69/metropole-viewer.js': 'ce8fe245f8a83767a200e28ed47959f3c3d0e72fb5284e906db9cdb40d944ab8',
    'src/v69/road-fidelity.js': '9d841f8c63223e521d0cfb6462e69b9224cbadedb236219d6c3e7a286a311d81',
    'src/v69/roof-core.js': '5c18fc4718f656ec372e89ce117095185dcec319517cdd3b92a060503259d3bd',
    'src/v69/streaming-core.js': '06995e1867257dca0e6ba2eed415326e16febbbd874ffa03a05a1028120f9ccc',
    'src/v69/world-runtime.js': 'c3ab96db2a08d6df24610745e64877beb218fc0141d9034ee26a86fa41e67819',
    'src/v70/augmentations-core.js': 'ea05cae0a634513c932728313f229a3cc82d604ad6a234e37e338dcf12dad215',
    'src/v70/infiltration-core.js': 'f4ed8fec6f398ceba7677bf0423767fefe9ec18e5371c97eea5b90b7fc9ad220',
    'src/v70/material-extension-core.js': '3286a5209d51fbf8995580db14810be11522a08ed9485bd1ce71bc5cb7a1217b',
    'src/v70/perception-runtime.js': '7b691f45b3fba23e12d55a097e3ab7971e137daff47e99f41aba414fd5026c1a',
    'src/v70/route-preview-core.js': '3f1df2f74b4323e863b3ddc7734d4943e9d5e3ca3b8e7588645176c9f8c1c85f',
    'src/v70/runtime.js': 'c82e36b043c0f12158022949464cf41ee22387507abf5383873af7dc3c8ac9ee',
    'src/v70/viewer-runtime.js': '716fa63a501864a2c5e5ae5ace5c434ea9f7915eac33dca8fd738a4015910c25',
    'src/v70/world-index.js': '3a53b1ed0b788ae721fed5830af9affab1e20999889816001d373408c4b4fad5',
    'src/v71/architecture-inspector-core.js': 'b580c8852ef7a9b1878581927f32966b1003243a9bd614cc2c3d04e526b77ab1',
    'src/v71/architecture-inspector-runtime.js': '6ee6fe26e9b8679a01daef6ec4c0b7d9335d1b809c4cac23135fc3819d8d6335',
    'src/v71/legacy-perception-runtime.js': '905922773f083111f86de348d86588dcad97ba738b605b9d3bb5315a31b7c05f',
    'src/v71/route-presentation-core.js': '0825b1ac9f60d236a61016d4e6582141f58d7a96cb1b7e01dd63c1181047d59e',
    'src/v71/viewer-route-runtime.js': '1ae45800ea7a72c16a5f7f6d406d2357d4120f3dd2c35315818662830b10527b',
    'tools/build_metropole_viewer.py': 'e6089c3541cb6452abcf15f1c14737cdc0f32fb01437abf7d8389e4177da28d7',
    'tools/build_metropole_viewer_v70.py': 'f8eb3cae73bcb1b46f950496ef0892974579383e89fd7dabe3a1f51e69e592a1',
    'tools/build_metropole_viewer_v71.py': '149df6d6fd2ac80dd36d0e9f1200c7c2b11d4e94ef23e38a189e9f7b389540ea',
    'tools/launch_cache_v71.py': 'cd63c0df89faf568aa0b9276a67e5b6bb98962330abaa4f76f027c5666d23fb1',
    'tools/metropole/acquire_bdtopo.py': 'a436fd8287457cc8a339afee4276baf817984f2cce26a049aabb1eb8564a3ecf',
    'tools/metropole/assemble_world.py': '66cdad0ed481fbb840f05f1b524b1656683de97b895f5756e81358650f74d80b',
    'tools/metropole/attach_height_references.py': 'b7829f700e7567adf832e14b1b0c78906eaa6f86233af7c735fe7835562905d9',
    'tools/metropole/attach_world_navigation.py': '3f917febc0819bde52d8984210ee550a580840fcb9a96ea8f76780cc2a2c5bf9',
    'tools/metropole/attach_world_parts.py': '2111492be9cf344d997a1a0337ee40caabafa4fe31e985befb003c66975c108c',
    'tools/metropole/attach_world_surfaces.py': 'd19fccf58b90b13336db0f61bf9a791bdb9b73e3b893bb4ea23121c094d25b98',
    'tools/metropole/bootstrap.py': 'fe9d5d993871067a90bf0a99f28192dfee7e15a4dc39c8a3ce04e190de425b80',
    'tools/metropole/building_heights.py': '35a84932181935ee6b3977124a24168b4c01c326c6c9a91abeb0e73a853aa573',
    'tools/metropole/building_parts.py': 'e9a5abb2caadc3e23d355876b8c93aa994c4e9cd880040fbeab387f9635dd13d',
    'tools/metropole/catalogue_building_parts.py': '5cb22216add539b3693836ba9e36470d69b9fbb9c6bd52e7102fd39cd09140b7',
    'tools/metropole/import_tiles.py': 'c360642b6c15b3342ed24700468b58f59aceb259a927dcf45f89f825f618ef2a',
    'tools/metropole/match_catalogues.py': 'bedcf23f66f1fd9a77c6061c78dbc00b86dc553785a15eff1d754060a29c3030',
    'tools/metropole/navigation_qa.py': 'cb783d8eb718340aa4451ae93d8ddf0b346d3bd014213dd4e0d4a46969f50ead',
    'tools/metropole/navigation_tiles.py': '01c43588515c693296afc2ffe9d152ab9ef956513397da5757c21d628cea13be',
    'tools/metropole/road_surfaces.py': 'bc671261254571cddad9a9afa636d4d40a93a2d2530267ddb3fc4ccb7da46300',
    'tools/metropole/settlement_anchors.py': '14b3aff91b9d0155d85cacf048b357bd0db0d7ac605a0dca768c336a139074af',
    'tools/metropole/surface_tiles.py': '478f2cd53b73c2599e11100dd8ae6a72a5df6614323c33063fb96b3350e80647',
    'tools/metropole/world_bundle.py': '26a04b8d7e9308cee114f15546076216b1433250b809c5b937013b0c5f2c6875',
    'tools/serve_game.py': 'cc26f315c7fc52d3cb457bec2cf376a9dd965c2f0b4e1d5496c7c56ab9b56d0a',
    'tools/serve_v68.py': 'ada46a7b257e5364c01ad750bbdaa0607068f2dc0800d8f10d7a1b916aae9c72',
    'tools/serve_v69.py': 'a316f69c1a6e8676c50f97fc5d456a747545dc3eac566ed52dbeb851427c925e',
    'tools/serve_v70.py': '30487a4269cf79e24b8916f8ca398388c5b6f517ecb2738740f2121560b85807',
    'tools/serve_v71.py': '12d2963d3fa79e27577cd52eefbd7b9acac69074590379a6152a927a873dbca1',
    'tools/v68_persistence.py': '467adfc30c19e78ddb2d3b6f09355dba7c628025f057b712b8708bb3bccdbcf6',
    'tools/v69/acquire_terrain.py': 'e16ec65d9b9eb06942424dd2cc2dd3a8a9eee409d386391b0681f08f83e5e230',
    'tools/v69/build_terrain_coverage.py': 'ecb1e9c3cc8e59b43066e3438004069fbc1dea25caec5acc16258ea967bc7460',
    'tools/v69/diagnose_terrain_coverage.py': 'eb30d03fde331a79609ff8fb878067ae2a7e187e083d58322011700d4614b193',
    'tools/v69/fidelity_audit.py': 'cfbc9932e19241e24767b86b5bf275af5e3402f2ca962ab661ac311227cbc8d9',
    'tools/v69/terrain_tiles.py': '97eefd4802e45fa32f37d9da8863cdb2d5a25f06d65370ce782f269d98846c09',
    'tools/v69_depth.py': '01ec3f50adeb9997583dca9795e109b8d0590a4adece7255b6f22730040597e6',
    'tools/v69_heights.py': '169c87cb6456ce1b7ab04be0358a0587c45b8eabf4c1eb476d99af25b396c215',
    'tools/v69_streaming.py': 'a8817848be92f5025968fcd984290ff434b25b449c27ee9295178e24a54e609f',
    'tools/v69_terrain.py': 'd92b224177326a64c6c6b3efe341e6f43e60fc35ab173055bcf4131ebae086a6',
    'tools/v70_gameplay.py': 'e3c43c4f66089bc6de44859e6d675931551d0ed5bc7bebb95ca7460a84e5bf54',
    'tools/v70_persistence.py': 'a85888ed46be517d16bc0f6ae74fb8f068f81722c2d7ea3fb65ec0b9ead9bacf',
    'tools/v71_architecture.py': '5bd9a12e5d55bd91769151dae9c9547d188a21a16c576233ab26d0874eee97a0',
    'tools/v71_legacy_perception.py': '58a59285431b4c6240de6c5258022608915b428848c01a86cb03bd878257487b',
    'tools/v71_route_viewer.py': '794ec5779f42613aa98266439bafcf72e06b3b9fdfc6bab7be2216178afa4163',
    'tools/verify_release.py': '046ea5be4b7ed202f942be46a9382f6f8609a1bc266ea99a7b4e561c48c24fd2',
}
V72_TOOLS = ('build_v72.py', 'tools/build_metropole_viewer_v72.py', 'tools/serve_v72.py', 'tools/launch_cache_v72.py',
             *(name.replace('.', '/') + '.py' for name in EXTENSIONS))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def fingerprint(path):
    return B71.fingerprint(Path(path))


def extensions():
    """All extensions are required; a missing feature is a build error."""
    return tuple(importlib.import_module(name) for name in EXTENSIONS)


def module_names():
    names = []
    for extension in extensions():
        declared = extension.MODULES
        if not isinstance(declared, (tuple, list)) or not declared:
            raise ValueError('Déclaration de modules 0.72 vide ou invalide.')
        for name in declared:
            if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9-]*', name) or name in names:
                raise ValueError('Nom de module 0.72 invalide ou dupliqué.')
            names.append(name)
    return tuple(names)


def inputs():
    parent = B71.inputs()
    frozen = {relative: fingerprint(ROOT / relative) for relative in FROZEN_PARENT_SOURCES}
    for relative, found in frozen.items():
        if found['sha256'] != FROZEN_PARENT_SOURCES[relative]:
            raise ValueError('Source parent gelée différente : ' + relative)
    names = module_names()
    sources = (*V72_TOOLS, *(f'src/v72/{name}.js' for name in names))
    return {'parentInputs': parent, 'frozenParentSources': frozen, 'modules72': list(names),
            'sources72': {relative: fingerprint(ROOT / relative) for relative in sources}}


def source_scripts(snapshot):
    scripts = {}
    for name in snapshot['modules72']:
        if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9-]*', name) or name in scripts:
            raise ValueError('Nom de module 0.72 invalide ou dupliqué.')
        relative = f'src/v72/{name}.js'
        expected = snapshot['sources72'][relative]
        if expected['bytes'] > 2 * 1024 * 1024:
            raise ValueError('Module 0.72 trop volumineux : ' + name)
        raw = (ROOT / relative).read_bytes()
        if len(raw) != expected['bytes'] or digest(raw) != expected['sha256']:
            raise ValueError('Module 0.72 modifié pendant la lecture : ' + name)
        text = raw.decode('utf-8')
        if not text.strip() or '</script' in text.lower():
            raise ValueError('Contenu de script 0.72 vide ou fermeture interdite : ' + name)
        scripts[name] = text
    return scripts


EDITION_RUNTIME = r'''(function(root){
  'use strict';
  function setup(){
    if(!root.__SOMA_V70__?.ready||!root.__SOMA_V71__){setTimeout(setup,100);return;}
    const version='0.72.0';
    root.__SOMA_V72__=Object.freeze({version,ready:true,ephemeral:true,newGeographicCells:0,
      snapshot:()=>({version,ephemeral:true,newGeographicCells:0,
        contactSharing:root.__SOMA_CONTACT_SHARING72__?.snapshot?.()||null,
        netrunner:root.__SOMA_NETRUNNER72__?.snapshot?.()||null})});
    root.__SOMA__.version=version;
    document.title='SOMA//MASSILIA 0.72 — Marseille augmentée';
    for(const selector of ['.v34-edition span','.topbar .brand small']){
      const item=document.querySelector(selector);if(item)item.textContent='0.72';
    }
  }
  setup();
})(window);'''


def patch_edition(html):
    if 'id="soma-v72-edition"' in html:
        raise ValueError('Édition 0.72 déjà appliquée.')
    html = rewrite_script(html, 'soma-v69-world-runtime', lambda value: replace_once(value,
        "button.onclick=()=>location.assign('metropole-viewer-v71.html');",
        "button.onclick=()=>location.assign('metropole-viewer-v72.html');",
        'vrai bouton de survol 0.72'))
    # Historical map runtimes contain SVG <title> strings inside body scripts.
    # Only the document head owns the browser's title.
    head = re.search(r'<head>[\s\S]*?</head>', html)
    if head is None:
        raise ValueError('En-tête parent absent.')
    titles = list(re.finditer(r'<title>[\s\S]*?</title>', head[0]))
    if len(titles) != 1:
        raise ValueError('Titre parent absent ou dupliqué.')
    html = replace_once(html, titles[0][0],
                        '<title>SOMA//MASSILIA 0.72 — Marseille augmentée</title>', 'titre 0.72')
    return replace_once(html, '</body>',
        '\n<script id="soma-v72-edition">\n' + EDITION_RUNTIME + '\n</script>\n</body>',
        'version publique après les adaptateurs 0.71 et 0.72')


def patch_html(html, scripts):
    for extension in extensions():
        html = extension.patch_html(html, scripts)
    return patch_edition(html)


def require_unchanged(before, after, label='reconstruction 0.72'):
    if before != after:
        changed = [key for key in sorted(set(before) | set(after)) if before.get(key) != after.get(key)]
        raise ValueError('Une entrée a changé pendant la ' + label + ' : ' + ', '.join(changed))


def build_release():
    before = inputs()
    parent, parent_report = B71.build_release()
    if digest(parent) != PARENT_SHA256:
        raise ValueError('Le parent 0.71 reconstruit diffère de son SHA256 gelé.')
    data = patch_html(parent.decode('utf-8'), source_scripts(before)).encode('utf-8')
    require_unchanged(before, inputs())
    report = {'version': VERSION, 'output': OUTPUT.name, 'bytes': len(data), 'sha256': digest(data),
              'parentVersion': '0.71.0', 'parentSHA256': PARENT_SHA256,
              'originalFilesVerified': parent_report['originalFilesVerified'],
              'sourceGeometryUnchanged': True, 'newGeographicCells': 0,
              'geographicWorld': parent_report['geographicWorld'],
              'worldManifestSHA256': parent_report['worldManifestSHA256'],
              'preparedCells': parent_report['preparedCells'], 'completeMetropole': False,
              'certifiedOneToOne': False, 'newPersistenceDomain': False, 'inputs': before}
    return data, report


def build():
    return build_release()[0]


def atomic_write(path, data):
    path = Path(path)
    if path.is_symlink() or not path.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError('Chemin de sortie 0.72 invalide.')
    relative = path.resolve().relative_to(ROOT.resolve())
    if not relative.parts:
        raise ValueError('Chemin de sortie 0.72 invalide.')
    protected_html = re.fullmatch(r'(?:SOMA_MASSILIA_URBAIN_v0_|metropole-viewer-v)([0-9]+)\.html', relative.name)
    if (str(relative) in FROZEN_PARENT_SOURCES or
            relative.parts[0] in {'src', 'tools', 'baseline'} or
            (relative.parts[0] == 'data' and relative.parts[:2] != ('data', 'v72')) or
            relative.name == 'metropole-viewer.html' or
            (protected_html and int(protected_html[1]) < 72)):
        raise ValueError('Une sortie 0.72 ne peut pas remplacer un parent gelé.')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.v72-', delete=False) as stream:
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
            raise ValueError('Le HTML 0.72 ne correspond pas aux sources actuelles.')
        if not REPORT.is_file() or REPORT.read_bytes() != encoded:
            raise ValueError('Le rapport 0.72 ne correspond pas aux entrées vérifiées.')
    else:
        atomic_write(OUTPUT, data)
        atomic_write(REPORT, encoded)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    try:
        report = prepare(verify=args.verify)
        print(json.dumps({key: report[key] for key in ('version', 'bytes', 'sha256',
            'originalFilesVerified', 'newGeographicCells')} | {'verified': args.verify}, ensure_ascii=False))
    except (OSError, ValueError, KeyError, TypeError, ImportError, AttributeError) as error:
        parser.exit(1, f'Reconstruction 0.72 impossible : {error}\n')


if __name__ == '__main__':
    main()
