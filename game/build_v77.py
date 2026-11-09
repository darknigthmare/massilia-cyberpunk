#!/usr/bin/env python3
"""Build edition 0.77 over the verified, unchanged 0.76 sources and world."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import tempfile

import build_v76 as B76
from build_v68 import replace_once, rewrite_script

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / 'SOMA_MASSILIA_URBAIN_v0_77.html'
REPORT = ROOT / 'data/v77/BUILD_REPORT.json'
PARENT_SHA256 = 'f3fd9d42c17db7835e95a33034ca25a442c7e3909121877795004142acf6d97a'
VERSION = '0.77.0'
EXTENSIONS = ('tools.v77_architecture', 'tools.v77_missions', 'tools.v77_combat', 'tools.v77_navigation')
FROZEN_PARENT_SOURCES = {
    **B76.FROZEN_PARENT_SOURCES,
    'build_v76.py': 'fde44d40d1b74320211145eea20d8c33a0ba5af4a10694cdb850143a52472f2f',
    'tools/build_metropole_viewer_v76.py': '7cdaef07601f17af4ad2a0de0674a7eedbd19e42b01177fe41a861570af21048',
    'tools/serve_v76.py': '5fd3c12b98af42d5682e502a70c275dd09c89bce1b4dbda9c3cb4e6e0392fef0',
    'tools/launch_cache_v76.py': '19607c5c586fab8622732f829a0aba15a9f2523accd196c060166f72320b4723',
    'tools/v76_architecture.py': 'efa9ec704e927214dd5bddb7e8c53eafb2f2578d147d1c8faf084fd792c933c6',
    'tools/v76_missions.py': '0cfd99ef6f55296f8de81cc0753f49fa0a5c06667b7462b0c5aee11fe04c30eb',
    'tools/v76_combat.py': 'aa1a74bc3da5ba91cb7f260053bdb4c0829c9d4f08d9b310578bdef0f7ca6e4b',
    'tools/v76_mobility.py': 'fcb63b79b1ecb7e09560ec4ed7a18d351ddfb25b2017327bf87deaf84645d64b',
    'src/v76/architecture-conflicts-data.js': '010f24f020537a0fc3e16756fed6fe7eedff8ef2a488a4807c89db0858a6f240',
    'src/v76/architecture-conflicts-core.js': '91d14cbfbf480ae2e2279cab927c68297e5c254a71b17e9f8bc29b7b1b51f00b',
    'src/v76/architecture-conflicts-runtime.js': '9e277068be03dcf7ea1c128d12682fc75d0e2d21050bf9ffe703b67ec8423ea2',
    'src/v76/missions-runtime.js': '35461fbbaff2e4a8fa289f66b3d524a08215bc62f319091a65a0a5ee22937d37',
    'src/v76/combat-heavy-runtime.js': '8613d5f887edefda7d9f690309474afa68abe6ce7533fc0449d58a753644385a',
    'src/v76/entry-runtime.js': 'e3abfad0c83264dca6afc8e0d750ac9c94e40953dc95dab5f5ca995c3809ce4d',
    'data/v76/architecture-conflicts.json': 'ee2d7c4d8be1f48df4689eac937d1a53f28307c300d851c9eeaf8290bb660829',
}
V77_TOOLS = ('build_v77.py', 'tools/build_metropole_viewer_v77.py', 'tools/serve_v77.py', 'tools/launch_cache_v77.py',
             *(name.replace('.', '/') + '.py' for name in EXTENSIONS))
SOURCE_DATA = ('data/v77/architecture-semantics.json',)
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
    return B76.fingerprint(Path(path))


def source_path(relative):
    """Keep declared generation inputs inside the source tree without links."""
    relative = Path(relative)
    path = ROOT / relative
    if (relative.is_absolute() or '..' in relative.parts or not path.resolve().is_relative_to(ROOT.resolve()) or
            any((ROOT / Path(*relative.parts[:index])).is_symlink()
                for index in range(1, len(relative.parts) + 1))):
        raise ValueError('Chemin de source 0.77 invalide : ' + str(relative))
    return path


def extensions():
    """All extensions are required; a missing feature is a build error."""
    return tuple(importlib.import_module(name) for name in EXTENSIONS)


def module_names():
    names = []
    for extension in extensions():
        declared = extension.MODULES
        if not isinstance(declared, (tuple, list)) or not declared:
            raise ValueError('Déclaration de modules 0.77 vide ou invalide.')
        for name in declared:
            if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9-]*', name) or name in names:
                raise ValueError('Nom de module 0.77 invalide ou dupliqué.')
            names.append(name)
    return tuple(names)


def inputs():
    frozen = {relative: fingerprint(source_path(relative)) for relative in FROZEN_PARENT_SOURCES}
    for relative, found in frozen.items():
        if found['sha256'] != FROZEN_PARENT_SOURCES[relative]:
            raise ValueError('Source parent gelée différente : ' + relative)
    parent = B76.inputs()
    names = module_names()
    sources = (*V77_TOOLS, *(f'src/v77/{name}.js' for name in names), *SOURCE_DATA)
    return {'parentInputs': parent, 'frozenParentSources': frozen, 'modules77': list(names),
            'sources77': {relative: fingerprint(source_path(relative)) for relative in sources}}


def source_scripts(snapshot):
    scripts = {}
    for name in snapshot['modules77']:
        if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9-]*', name) or name in scripts:
            raise ValueError('Nom de module 0.77 invalide ou dupliqué.')
        relative = f'src/v77/{name}.js'
        expected = snapshot['sources77'][relative]
        if expected['bytes'] > 2 * 1024 * 1024:
            raise ValueError('Module 0.77 trop volumineux : ' + name)
        with source_path(relative).open('rb') as stream:
            raw = stream.read(2 * 1024 * 1024 + 1)
        if len(raw) != expected['bytes'] or digest(raw) != expected['sha256']:
            raise ValueError('Module 0.77 modifié pendant la lecture : ' + name)
        text = raw.decode('utf-8')
        if not text.strip() or '</script' in text.lower():
            raise ValueError('Contenu de script 0.77 vide ou fermeture interdite : ' + name)
        scripts[name] = text
    return scripts


EDITION_RUNTIME = r'''(function(root){
  'use strict';
  function setup(){
    if(!root.__SOMA_V70__?.ready||!root.__SOMA_V76__?.ready){setTimeout(setup,100);return;}
    const version='0.77.0';
    root.__SOMA_V77__=Object.freeze({version,ready:true,ephemeral:true,newGeographicCells:0,
      snapshot:()=>({version,ephemeral:true,newGeographicCells:0,
        architecture:root.__SOMA_ARCHITECTURE77__?.snapshot?.()||null,
        missions:root.__SOMA_GUIDANCE77__?.snapshot?.()||null,
        combat:root.__SOMA_RELOAD77__?.snapshot?.()||null,
        routes:root.__SOMA_ROUTE77__?.snapshot?.()||null})});
    root.__SOMA__.version=version;
    document.title='SOMA//MASSILIA 0.77 — Marseille augmentée';
    for(const selector of ['.v34-edition span','.topbar .brand small']){
      const item=document.querySelector(selector);if(item)item.textContent='0.77';
    }
  }
  setup();
})(window);'''


def patch_edition(html):
    if 'id="soma-v77-edition"' in html:
        raise ValueError('Édition 0.77 déjà appliquée.')
    html = rewrite_script(html, 'soma-v69-world-runtime', lambda value: replace_once(value,
        "button.onclick=()=>location.assign('metropole-viewer-v76.html');",
        "button.onclick=()=>location.assign('metropole-viewer-v77.html');",
        'vrai bouton de survol 0.77'))
    # Historical map runtimes contain SVG <title> strings inside body scripts.
    # Only the document head owns the browser's title.
    head = re.search(r'<head>[\s\S]*?</head>', html)
    if head is None:
        raise ValueError('En-tête parent absent.')
    titles = list(re.finditer(r'<title>[\s\S]*?</title>', head[0]))
    if len(titles) != 1:
        raise ValueError('Titre parent absent ou dupliqué.')
    html = replace_once(html, titles[0][0],
                        '<title>SOMA//MASSILIA 0.77 — Marseille augmentée</title>', 'titre 0.77')
    return replace_once(html, '</body>',
        '\n<script id="soma-v77-edition">\n' + EDITION_RUNTIME + '\n</script>\n</body>',
        'version publique après les adaptateurs 0.76 et 0.77')


def patch_html(html, scripts):
    for extension in extensions():
        html = extension.patch_html(html, scripts)
    return patch_edition(html)


def require_unchanged(before, after, label='reconstruction 0.77'):
    if before != after:
        changed = [key for key in sorted(set(before) | set(after)) if before.get(key) != after.get(key)]
        raise ValueError('Une entrée a changé pendant la ' + label + ' : ' + ', '.join(changed))


def build_release():
    before = inputs()
    parent, parent_report = B76.build_release()
    if digest(parent) != PARENT_SHA256:
        raise ValueError('Le parent 0.76 reconstruit diffère de son SHA256 gelé.')
    data = patch_html(parent.decode('utf-8'), source_scripts(before)).encode('utf-8')
    require_unchanged(before, inputs())
    report = {'version': VERSION, 'output': OUTPUT.name, 'bytes': len(data), 'sha256': digest(data),
              'parentVersion': '0.76.0', 'parentSHA256': PARENT_SHA256,
              'originalFilesVerified': parent_report['originalFilesVerified'],
              'sourceGeometryUnchanged': True, 'sourceAssetsUnchanged': True,
              'renderingModified': True, 'renderedGeometryByteIdenticalToParent': True,
              'renderingChanges': ['source-height-semantics-inspection', 'native43-route-guidance'],
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
        raise ValueError('Chemin de sortie 0.77 invalide.') from error
    if (not relative.parts or '..' in relative.parts or
            not path.resolve().is_relative_to(ROOT.resolve()) or
            any((ROOT / Path(*relative.parts[:index])).is_symlink()
                for index in range(1, len(relative.parts) + 1))):
        raise ValueError('Chemin de sortie 0.77 invalide.')
    protected_html = re.fullmatch(r'(?:SOMA_MASSILIA_URBAIN_v0_|metropole-viewer-v)([0-9]+)\.html', relative.name)
    generated_report = relative.parts in {('data', 'v77', 'BUILD_REPORT.json'),
                                          ('data', 'v77', 'VIEWER_BUILD_REPORT.json')}
    if (str(relative) in FROZEN_PARENT_SOURCES or str(relative) in V77_TOOLS or
            str(relative) in SOURCE_DATA or
            str(relative) in ORIGINAL_ROOT_FILES or
            relative.parts[0] in {'src', 'tools', 'baseline', 'docs', 'tests'} or
            (relative.parts[0] == 'data' and not generated_report) or
            relative.name == 'metropole-viewer.html' or
            (protected_html and int(protected_html[1]) < 77) or
            (not generated_report and (len(relative.parts) != 1 or path.suffix in
                                       {'.py', '.js', '.json', '.md', '.toml', '.ini', '.cfg'})) or
            path.is_dir()):
        raise ValueError('Une sortie 0.77 ne peut pas remplacer un parent gelé ou une source.')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.v77-', delete=False) as stream:
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
            raise ValueError('Le HTML 0.77 ne correspond pas aux sources actuelles.')
        if not REPORT.is_file() or REPORT.read_bytes() != encoded:
            raise ValueError('Le rapport 0.77 ne correspond pas aux entrées vérifiées.')
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
        parser.exit(1, f'Reconstruction 0.77 impossible : {error}\n')


if __name__ == '__main__':
    main()
