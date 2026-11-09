#!/usr/bin/env python3
"""Build edition 0.78 over the verified, unchanged 0.77 sources and world."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import tempfile

import build_v77 as B77
from build_v68 import replace_once, rewrite_script

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / 'SOMA_MASSILIA_URBAIN_v0_78.html'
REPORT = ROOT / 'data/v78/BUILD_REPORT.json'
PARENT_SHA256 = '98bc42719f32d840e5577e6d5062ab9bcd6508969b149b2c0c53f7622ef1ae74'
VERSION = '0.78.0'
EXTENSIONS = ('tools.v78_architecture', 'tools.v78_missions', 'tools.v78_combat', 'tools.v78_world')
FROZEN_PARENT_SOURCES = {
    **B77.FROZEN_PARENT_SOURCES,
    'build_v77.py': '2996281640ed5fe32b54a17a884f1ec04b7d3f176cd306f18a3ab5740a98d454',
    'tools/build_metropole_viewer_v77.py': '253dad49bc4588d8ee17ca94fea223b441a8012c97a66657d2f4709deeed5a49',
    'tools/serve_v77.py': '84274b85d6d18850ec2845204f688287c4e078248e102ed961718bcffd5fa0dd',
    'tools/launch_cache_v77.py': '6bc7bc08720e115dfa1daf9a523eb51a464e8822ac71a3a834db0fb2825547fb',
    'tools/v77_architecture.py': '8e76120daee5d489ec050ab5f4ffbeb2e96ecf48b1a0bf16b352c6052cd1e658',
    'tools/v77_missions.py': '454e55c73e0770ed15243e9bd767cb8e704ba78c2aba2b0cb9149284aaf41e3f',
    'tools/v77_combat.py': '80145ebc64095fc5f6328e067ec87d36d5af38f759ce0128ea136f05e42135d8',
    'tools/v77_navigation.py': 'da8e6ad8aae6db9352928df350db02c1e8cfa977c9f8dcec1545a5cbea7c5de2',
    'src/v77/architecture-semantics-data.js': '788c81c510e5ef635360ce07bdadc83ab9a3bcccdad598031f1e4d2fdf3dddbe',
    'src/v77/architecture-semantics-core.js': 'e00e2534b1d64d2899c4b28e26b50a3d8b316505b04a6d827c259ce5c97ba7e8',
    'src/v77/architecture-semantics-runtime.js': 'd499dba7b6323c8b3af0f05ebd83c6ce63d992de2910b656a50d756ca1b17833',
    'src/v77/missions-runtime.js': '028b6c85dea5c83e6855f5a84c43ff2344a318d2c9e32fa79a3dbb1140006330',
    'src/v77/missions-route-runtime.js': '33729a6e865b4f11fce494def0251b9c1a9a9fddb7c8dd703f372d0a65419318',
    'src/v77/combat-reload-runtime.js': '7283595f33777812336b08036de4480657cfd51396f71a140a75c7d557b48f8c',
    'src/v77/navigation-core.js': '995baf75f2372b827b2c579e36a62b812c2566be5f3d3dd45b31290f9b847ace',
    'data/v77/architecture-semantics.json': 'a6a5d3537efe957a4c0c95d73ae72f7cf1f5410733cbbc03d479435e541fc737',
}
V78_TOOLS = ('build_v78.py', 'tools/build_metropole_viewer_v78.py', 'tools/serve_v78.py', 'tools/launch_cache_v78.py',
             *(name.replace('.', '/') + '.py' for name in EXTENSIONS))
SOURCE_DATA = ()
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
    return B77.fingerprint(Path(path))


def source_path(relative):
    """Keep declared generation inputs inside the source tree without links."""
    relative = Path(relative)
    path = ROOT / relative
    if (relative.is_absolute() or '..' in relative.parts or not path.resolve().is_relative_to(ROOT.resolve()) or
            any((ROOT / Path(*relative.parts[:index])).is_symlink()
                for index in range(1, len(relative.parts) + 1))):
        raise ValueError('Chemin de source 0.78 invalide : ' + str(relative))
    return path


def extensions():
    """All extensions are required; a missing feature is a build error."""
    return tuple(importlib.import_module(name) for name in EXTENSIONS)


def module_names():
    names = []
    for extension in extensions():
        declared = extension.MODULES
        if not isinstance(declared, (tuple, list)) or not declared:
            raise ValueError('Déclaration de modules 0.78 vide ou invalide.')
        for name in declared:
            if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9-]*', name) or name in names:
                raise ValueError('Nom de module 0.78 invalide ou dupliqué.')
            names.append(name)
    return tuple(names)


def inputs():
    frozen = {relative: fingerprint(source_path(relative)) for relative in FROZEN_PARENT_SOURCES}
    for relative, found in frozen.items():
        if found['sha256'] != FROZEN_PARENT_SOURCES[relative]:
            raise ValueError('Source parent gelée différente : ' + relative)
    parent = B77.inputs()
    names = module_names()
    sources = (*V78_TOOLS, *(f'src/v78/{name}.js' for name in names), *SOURCE_DATA)
    return {'parentInputs': parent, 'frozenParentSources': frozen, 'modules78': list(names),
            'sources78': {relative: fingerprint(source_path(relative)) for relative in sources}}


def source_scripts(snapshot):
    scripts = {}
    for name in snapshot['modules78']:
        if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9-]*', name) or name in scripts:
            raise ValueError('Nom de module 0.78 invalide ou dupliqué.')
        relative = f'src/v78/{name}.js'
        expected = snapshot['sources78'][relative]
        if expected['bytes'] > 2 * 1024 * 1024:
            raise ValueError('Module 0.78 trop volumineux : ' + name)
        with source_path(relative).open('rb') as stream:
            raw = stream.read(2 * 1024 * 1024 + 1)
        if len(raw) != expected['bytes'] or digest(raw) != expected['sha256']:
            raise ValueError('Module 0.78 modifié pendant la lecture : ' + name)
        text = raw.decode('utf-8')
        if not text.strip() or '</script' in text.lower():
            raise ValueError('Contenu de script 0.78 vide ou fermeture interdite : ' + name)
        scripts[name] = text
    return scripts


EDITION_RUNTIME = r'''(function(root){
  'use strict';
  function setup(){
    if(!root.__SOMA_V70__?.ready||!root.__SOMA_V77__?.ready){setTimeout(setup,100);return;}
    const version='0.78.0';
    root.__SOMA_V78__=Object.freeze({version,ready:true,ephemeral:true,newGeographicCells:0,
      snapshot:()=>({version,ephemeral:true,newGeographicCells:0})});
    root.__SOMA__.version=version;
    document.title='SOMA//MASSILIA 0.78 — Marseille augmentée';
    for(const selector of ['.v34-edition span','.topbar .brand small']){
      const item=document.querySelector(selector);if(item)item.textContent='0.78';
    }
  }
  setup();
})(window);'''


def patch_edition(html):
    if 'id="soma-v78-edition"' in html:
        raise ValueError('Édition 0.78 déjà appliquée.')
    html = rewrite_script(html, 'soma-v69-world-runtime', lambda value: replace_once(value,
        "button.onclick=()=>location.assign('metropole-viewer-v77.html');",
        "button.onclick=()=>location.assign('metropole-viewer-v78.html');",
        'vrai bouton de survol 0.78'))
    # Historical map runtimes contain SVG <title> strings inside body scripts.
    # Only the document head owns the browser's title.
    head = re.search(r'<head>[\s\S]*?</head>', html)
    if head is None:
        raise ValueError('En-tête parent absent.')
    titles = list(re.finditer(r'<title>[\s\S]*?</title>', head[0]))
    if len(titles) != 1:
        raise ValueError('Titre parent absent ou dupliqué.')
    html = replace_once(html, titles[0][0],
                        '<title>SOMA//MASSILIA 0.78 — Marseille augmentée</title>', 'titre 0.78')
    return replace_once(html, '</body>',
        '\n<script id="soma-v78-edition">\n' + EDITION_RUNTIME + '\n</script>\n</body>',
        'version publique après les adaptateurs 0.77 et 0.78')


def patch_html(html, scripts):
    for extension in extensions():
        html = extension.patch_html(html, scripts)
    return patch_edition(html)


def require_unchanged(before, after, label='reconstruction 0.78'):
    if before != after:
        changed = [key for key in sorted(set(before) | set(after)) if before.get(key) != after.get(key)]
        raise ValueError('Une entrée a changé pendant la ' + label + ' : ' + ', '.join(changed))


def build_release():
    before = inputs()
    parent, parent_report = B77.build_release()
    if digest(parent) != PARENT_SHA256:
        raise ValueError('Le parent 0.77 reconstruit diffère de son SHA256 gelé.')
    data = patch_html(parent.decode('utf-8'), source_scripts(before)).encode('utf-8')
    require_unchanged(before, inputs())
    report = {'version': VERSION, 'output': OUTPUT.name, 'bytes': len(data), 'sha256': digest(data),
              'parentVersion': '0.77.0', 'parentSHA256': PARENT_SHA256,
              'originalFilesVerified': parent_report['originalFilesVerified'],
              'sourceGeometryUnchanged': True, 'sourceAssetsUnchanged': True,
              'renderingModified': True, 'renderedGeometryByteIdenticalToParent': True,
              'renderingChanges': ['native45-vehicle-guidance'],
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
        raise ValueError('Chemin de sortie 0.78 invalide.') from error
    if (not relative.parts or '..' in relative.parts or
            not path.resolve().is_relative_to(ROOT.resolve()) or
            any((ROOT / Path(*relative.parts[:index])).is_symlink()
                for index in range(1, len(relative.parts) + 1))):
        raise ValueError('Chemin de sortie 0.78 invalide.')
    protected_html = re.fullmatch(r'(?:SOMA_MASSILIA_URBAIN_v0_|metropole-viewer-v)([0-9]+)\.html', relative.name)
    generated_report = relative.parts in {('data', 'v78', 'BUILD_REPORT.json'),
                                          ('data', 'v78', 'VIEWER_BUILD_REPORT.json')}
    if (str(relative) in FROZEN_PARENT_SOURCES or str(relative) in V78_TOOLS or
            str(relative) in SOURCE_DATA or
            str(relative) in ORIGINAL_ROOT_FILES or
            relative.parts[0] in {'src', 'tools', 'baseline', 'docs', 'tests'} or
            (relative.parts[0] == 'data' and not generated_report) or
            relative.name == 'metropole-viewer.html' or
            (protected_html and int(protected_html[1]) < int(VERSION.split('.')[1])) or
            (not generated_report and (len(relative.parts) != 1 or path.suffix in
                                       {'.py', '.js', '.json', '.md', '.toml', '.ini', '.cfg'})) or
            path.is_dir()):
        raise ValueError('Une sortie 0.78 ne peut pas remplacer un parent gelé ou une source.')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.v78-', delete=False) as stream:
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
            raise ValueError('Le HTML 0.78 ne correspond pas aux sources actuelles.')
        if not REPORT.is_file() or REPORT.read_bytes() != encoded:
            raise ValueError('Le rapport 0.78 ne correspond pas aux entrées vérifiées.')
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
        parser.exit(1, f'Reconstruction 0.78 impossible : {error}\n')


if __name__ == '__main__':
    main()
