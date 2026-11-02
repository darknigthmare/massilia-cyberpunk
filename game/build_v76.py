#!/usr/bin/env python3
"""Build edition 0.76 over the verified, unchanged 0.75 sources and world."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import tempfile

import build_v75 as B75
from build_v68 import replace_once, rewrite_script

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / 'SOMA_MASSILIA_URBAIN_v0_76.html'
REPORT = ROOT / 'data/v76/BUILD_REPORT.json'
PARENT_SHA256 = 'fe4ba1538007c85c14d4d39aca0017f5bb2ec090986f6181896ce46fa1cb9aad'
VERSION = '0.76.0'
EXTENSIONS = ('tools.v76_architecture', 'tools.v76_missions', 'tools.v76_combat', 'tools.v76_mobility')
FROZEN_PARENT_SOURCES = {
    **B75.FROZEN_PARENT_SOURCES,
    'build_v75.py': 'cdac75f767b32baf3ef16cb6c47f118077aa41fff12be4f674257fcb03888a9e',
    'tools/build_metropole_viewer_v75.py': '244e73f103133ee6e857f603e89f8401af674ad9a6207f1bfc7998c393e6d98c',
    'tools/serve_v75.py': '58cf571dc48085258c0930b4507a2fc5ab9a90e334d2926f7d2d3df474e603cb',
    'tools/launch_cache_v75.py': '06085247abb77cbb8eec8dbed652090581ce62065397060504a0e07f0470a839',
    'tools/v75_terrain.py': 'dbd5e83f766f4c6297b123beec42bc13136d395b29f907b8d85045ab4908b295',
    'tools/v75_missions.py': '600ba61befa19f29016b2ef094eb56f22a14011db7c2141fae538b26cc4b11cd',
    'tools/v75_combat.py': '9c706a6090f2e38ee21c830ee5d7ace5d8d7246b3d0d3ec99589e37b7eb48275',
    'tools/v75_vehicles.py': '85efe1cb0ba12e34938475c44130e17b24fde1ef1cd3329ad45d7a26a98d2423',
    'src/v75/terrain-footprint-core.js': 'a68ca0f7eee0fa9596097d41cd8825ff9d35be37f3ec54ea72214bd41c66782e',
    'src/v75/terrain-data-a.js': '371eb609ebfd0dd74aafd73bab4b8a99a1d1f749ba601a9a0bfb208fd09a655f',
    'src/v75/terrain-data-b.js': '6ef571453b5afc8443f8932eccc16c5af4d239ccf2f7ddfa00c94608db572112',
    'src/v75/terrain-data-c.js': '1c63df14fa2b7bdad59449687594fa91de2d5e49bfcece06bfb5ec75af4bfe62',
    'src/v75/terrain-runtime.js': 'e660a70aee59e146952ab378d5ffc706d70aa754af7fff9a540f597701fd171e',
    'src/v75/missions-runtime.js': '79cdc883053c20cb61ee4835f6105064be267c68931a3f7e4ac487b65171a276',
    'src/v75/combat-telegraph-runtime.js': '147688fef4841d455a134c55d98f12bed142d61cf86ec49d621f2bd22cda742e',
    'src/v75/vehicle-runtime.js': '63d37be0a619d40553108bace5c34a7596986154d3c674f0889a582c783cda1f',
    'data/v75/terrain-source.json': '837b637ac684bce0d2b67d0252554eca5ec3db4c7171563dc42484151cf78abf',
}
V76_TOOLS = ('build_v76.py', 'tools/build_metropole_viewer_v76.py', 'tools/serve_v76.py', 'tools/launch_cache_v76.py',
             *(name.replace('.', '/') + '.py' for name in EXTENSIONS))
SOURCE_DATA = ('data/v76/architecture-conflicts.json',)
ORIGINAL_ROOT_FILES = frozenset({
    'LANCER_JEU.cmd', 'MANIFEST_v67.json', 'README.md', 'README_v67.md',
    'RECONSTRUIRE_JEU.cmd', 'SOMA_MASSILIA_AUDIT_COMPLET_v0_67.md',
    'SOMA_MASSILIA_CHANGELOG_v0_67.md', 'SOMA_MASSILIA_RAPPORT_v0_67.html',
    'SOMA_MASSILIA_URBAIN_v0_67.html', 'SOMA_MASSILIA_VERIFICATION_v0_67.txt',
    'VERIFIER_ARCHIVE.cmd', 'build.py',
})


def digest(data):
    return hashlib.sha256(data).hexdigest()


def fingerprint(path):
    return B75.fingerprint(Path(path))


def source_path(relative):
    """Keep declared generation inputs inside the source tree without links."""
    relative = Path(relative)
    path = ROOT / relative
    if (relative.is_absolute() or '..' in relative.parts or not path.resolve().is_relative_to(ROOT.resolve()) or
            any((ROOT / Path(*relative.parts[:index])).is_symlink()
                for index in range(1, len(relative.parts) + 1))):
        raise ValueError('Chemin de source 0.76 invalide : ' + str(relative))
    return path


def extensions():
    """All extensions are required; a missing feature is a build error."""
    return tuple(importlib.import_module(name) for name in EXTENSIONS)


def module_names():
    names = []
    for extension in extensions():
        declared = extension.MODULES
        if not isinstance(declared, (tuple, list)) or not declared:
            raise ValueError('Déclaration de modules 0.76 vide ou invalide.')
        for name in declared:
            if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9-]*', name) or name in names:
                raise ValueError('Nom de module 0.76 invalide ou dupliqué.')
            names.append(name)
    return tuple(names)


def inputs():
    frozen = {relative: fingerprint(source_path(relative)) for relative in FROZEN_PARENT_SOURCES}
    for relative, found in frozen.items():
        if found['sha256'] != FROZEN_PARENT_SOURCES[relative]:
            raise ValueError('Source parent gelée différente : ' + relative)
    parent = B75.inputs()
    names = module_names()
    sources = (*V76_TOOLS, *(f'src/v76/{name}.js' for name in names), *SOURCE_DATA)
    return {'parentInputs': parent, 'frozenParentSources': frozen, 'modules76': list(names),
            'sources76': {relative: fingerprint(source_path(relative)) for relative in sources}}


def source_scripts(snapshot):
    scripts = {}
    for name in snapshot['modules76']:
        if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9-]*', name) or name in scripts:
            raise ValueError('Nom de module 0.76 invalide ou dupliqué.')
        relative = f'src/v76/{name}.js'
        expected = snapshot['sources76'][relative]
        if expected['bytes'] > 2 * 1024 * 1024:
            raise ValueError('Module 0.76 trop volumineux : ' + name)
        with source_path(relative).open('rb') as stream:
            raw = stream.read(2 * 1024 * 1024 + 1)
        if len(raw) != expected['bytes'] or digest(raw) != expected['sha256']:
            raise ValueError('Module 0.76 modifié pendant la lecture : ' + name)
        text = raw.decode('utf-8')
        if not text.strip() or '</script' in text.lower():
            raise ValueError('Contenu de script 0.76 vide ou fermeture interdite : ' + name)
        scripts[name] = text
    return scripts


EDITION_RUNTIME = r'''(function(root){
  'use strict';
  function setup(){
    if(!root.__SOMA_V70__?.ready||!root.__SOMA_V75__?.ready){setTimeout(setup,100);return;}
    const version='0.76.0';
    root.__SOMA_V76__=Object.freeze({version,ready:true,ephemeral:true,newGeographicCells:0,
      snapshot:()=>({version,ephemeral:true,newGeographicCells:0,
        architecture:root.__SOMA_ARCHITECTURE76__?.snapshot?.()||null,
        missions:root.__SOMA_MISSIONS76__?.snapshot?.()||null,
        combat:root.__SOMA_COMBAT76__?.snapshot?.()||null,
        mobility:root.__SOMA_MOBILITY76__?.snapshot?.()||null})});
    root.__SOMA__.version=version;
    document.title='SOMA//MASSILIA 0.76 — Marseille augmentée';
    for(const selector of ['.v34-edition span','.topbar .brand small']){
      const item=document.querySelector(selector);if(item)item.textContent='0.76';
    }
  }
  setup();
})(window);'''


def patch_edition(html):
    if 'id="soma-v76-edition"' in html:
        raise ValueError('Édition 0.76 déjà appliquée.')
    html = rewrite_script(html, 'soma-v69-world-runtime', lambda value: replace_once(value,
        "button.onclick=()=>location.assign('metropole-viewer-v75.html');",
        "button.onclick=()=>location.assign('metropole-viewer-v76.html');",
        'vrai bouton de survol 0.76'))
    # Historical map runtimes contain SVG <title> strings inside body scripts.
    # Only the document head owns the browser's title.
    head = re.search(r'<head>[\s\S]*?</head>', html)
    if head is None:
        raise ValueError('En-tête parent absent.')
    titles = list(re.finditer(r'<title>[\s\S]*?</title>', head[0]))
    if len(titles) != 1:
        raise ValueError('Titre parent absent ou dupliqué.')
    html = replace_once(html, titles[0][0],
                        '<title>SOMA//MASSILIA 0.76 — Marseille augmentée</title>', 'titre 0.76')
    return replace_once(html, '</body>',
        '\n<script id="soma-v76-edition">\n' + EDITION_RUNTIME + '\n</script>\n</body>',
        'version publique après les adaptateurs 0.75 et 0.76')


def patch_html(html, scripts):
    for extension in extensions():
        html = extension.patch_html(html, scripts)
    return patch_edition(html)


def require_unchanged(before, after, label='reconstruction 0.76'):
    if before != after:
        changed = [key for key in sorted(set(before) | set(after)) if before.get(key) != after.get(key)]
        raise ValueError('Une entrée a changé pendant la ' + label + ' : ' + ', '.join(changed))


def build_release():
    before = inputs()
    parent, parent_report = B75.build_release()
    if digest(parent) != PARENT_SHA256:
        raise ValueError('Le parent 0.75 reconstruit diffère de son SHA256 gelé.')
    data = patch_html(parent.decode('utf-8'), source_scripts(before)).encode('utf-8')
    require_unchanged(before, inputs())
    report = {'version': VERSION, 'output': OUTPUT.name, 'bytes': len(data), 'sha256': digest(data),
              'parentVersion': '0.75.0', 'parentSHA256': PARENT_SHA256,
              'originalFilesVerified': parent_report['originalFilesVerified'],
              'sourceGeometryUnchanged': True, 'sourceAssetsUnchanged': True,
              'renderingModified': True, 'renderedGeometryByteIdenticalToParent': False,
              'renderingChanges': ['atlas-source-conflict-inspection', 'heavy-preparation-telegraph',
                                   'authored-gig-objective-placement', 'native45-ui-defaults'],
              'campaignGeographicRenderingModified': False,
              'newGeographicCells': 0,
              'geographicWorld': parent_report['geographicWorld'],
              'worldManifestSHA256': parent_report['worldManifestSHA256'],
              'preparedCells': parent_report['preparedCells'], 'completeMetropole': False,
              'certifiedOneToOne': False, 'newPersistenceDomain': False,
              'campaignPersistenceDomain': 'core.v70', 'inputs': before}
    return data, report


def build():
    return build_release()[0]


def atomic_write(path, data):
    """Publish generated outputs only, preserving sources and every parent."""
    path = Path(path).absolute()
    try:
        relative = path.relative_to(ROOT)
    except ValueError as error:
        raise ValueError('Chemin de sortie 0.76 invalide.') from error
    if (not relative.parts or '..' in relative.parts or
            not path.resolve().is_relative_to(ROOT.resolve()) or
            any((ROOT / Path(*relative.parts[:index])).is_symlink()
                for index in range(1, len(relative.parts) + 1))):
        raise ValueError('Chemin de sortie 0.76 invalide.')
    protected_html = re.fullmatch(r'(?:SOMA_MASSILIA_URBAIN_v0_|metropole-viewer-v)([0-9]+)\.html', relative.name)
    generated_report = relative.parts in {('data', 'v76', 'BUILD_REPORT.json'),
                                          ('data', 'v76', 'VIEWER_BUILD_REPORT.json')}
    if (str(relative) in FROZEN_PARENT_SOURCES or str(relative) in V76_TOOLS or
            str(relative) in SOURCE_DATA or
            str(relative) in ORIGINAL_ROOT_FILES or
            relative.parts[0] in {'src', 'tools', 'baseline', 'docs', 'tests'} or
            (relative.parts[0] == 'data' and not generated_report) or
            relative.name == 'metropole-viewer.html' or
            (protected_html and int(protected_html[1]) < 76) or
            (not generated_report and (len(relative.parts) != 1 or path.suffix in
                                       {'.py', '.js', '.json', '.md', '.toml', '.ini', '.cfg'})) or
            path.is_dir()):
        raise ValueError('Une sortie 0.76 ne peut pas remplacer un parent gelé ou une source.')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.v76-', delete=False) as stream:
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
            raise ValueError('Le HTML 0.76 ne correspond pas aux sources actuelles.')
        if not REPORT.is_file() or REPORT.read_bytes() != encoded:
            raise ValueError('Le rapport 0.76 ne correspond pas aux entrées vérifiées.')
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
        parser.exit(1, f'Reconstruction 0.76 impossible : {error}\n')


if __name__ == '__main__':
    main()
