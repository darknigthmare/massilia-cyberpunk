#!/usr/bin/env python3
"""Build edition 0.75 over the verified, unchanged 0.74 sources and world."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import tempfile

import build_v74 as B74
from build_v68 import replace_once, rewrite_script

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / 'SOMA_MASSILIA_URBAIN_v0_75.html'
REPORT = ROOT / 'data/v75/BUILD_REPORT.json'
PARENT_SHA256 = '1b776a1b8b3c2861093e1670d1b203025b158bd0fb0f464f0ab3d58086139330'
VERSION = '0.75.0'
EXTENSIONS = ('tools.v75_terrain', 'tools.v75_missions', 'tools.v75_combat', 'tools.v75_vehicles')
FROZEN_PARENT_SOURCES = {
    **B74.FROZEN_PARENT_SOURCES,
    'build_v74.py': '8a72befaabfddb3da5a7104f29bca2104f0b12aacf6daf77dac92ab13617daa5',
    'tools/build_metropole_viewer_v74.py': '5f5b98901386690d2150230f5fb9050f53397b5c12cd703ab0d49cf24aae001d',
    'tools/serve_v74.py': 'd1c442574562a60db76349a97bbaf842324980e5c52156758df61e2a9c890eb1',
    'tools/launch_cache_v74.py': 'd70c5b3e82c3226c164e0f09736d4c91c9b321ce0a74bffe8e04ed680720800b',
    'tools/v74_architecture.py': 'df04a3a527b97a319e89b7197ae6fd58eed978a403464d5e970a54bc62bfb6e2',
    'tools/v74_mobility.py': '8ad06bd940c602d9246d8be47b53124cb6e74d0a970cbab12c0f7199dbf526cf',
    'tools/v74_combat.py': '7219c290463fcba647f2091a16a07fb88c8c3678395246842aceb313099ffd1f',
    'tools/v74_progression.py': 'd829c3b4d20670e9a135b8197f078a64e8bcead8e94995a972fe31fd5ab71881',
    'src/v74/architecture-datum-core.js': '0da4bf20da44010ae4cfb4fe7cc12e9c85c9d70b550ad1d38a4a3916e0be6720',
    'src/v74/mobility-runtime.js': 'd9bce0eff2553a8c6c0a41a4cf5e32c9dc310b152e9e87b6880b6998fd54d59f',
    'src/v74/combat-support-runtime.js': '6dc6c8b4676fdb835ce3474978367b2fa04b5bb2cd8e44bc6a975c36c7e002aa',
    'src/v74/progression-runtime.js': '96d92a07a2cb0ad0367828a7be23a7e5a4e2f10851768009471e08a6cd596ffd',
}
V75_TOOLS = ('build_v75.py', 'tools/build_metropole_viewer_v75.py', 'tools/serve_v75.py', 'tools/launch_cache_v75.py',
             *(name.replace('.', '/') + '.py' for name in EXTENSIONS))
SOURCE_DATA = ('data/v75/terrain-source.json',)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def fingerprint(path):
    return B74.fingerprint(Path(path))


def source_path(relative):
    """Keep declared generation inputs inside the source tree without links."""
    relative = Path(relative)
    path = ROOT / relative
    if (relative.is_absolute() or not path.resolve().is_relative_to(ROOT.resolve()) or
            any((ROOT / Path(*relative.parts[:index])).is_symlink()
                for index in range(1, len(relative.parts) + 1))):
        raise ValueError('Chemin de source 0.75 invalide : ' + str(relative))
    return path


def extensions():
    """All extensions are required; a missing feature is a build error."""
    return tuple(importlib.import_module(name) for name in EXTENSIONS)


def module_names():
    names = []
    for extension in extensions():
        declared = extension.MODULES
        if not isinstance(declared, (tuple, list)) or not declared:
            raise ValueError('Déclaration de modules 0.75 vide ou invalide.')
        for name in declared:
            if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9-]*', name) or name in names:
                raise ValueError('Nom de module 0.75 invalide ou dupliqué.')
            names.append(name)
    return tuple(names)


def inputs():
    parent = B74.inputs()
    frozen = {relative: fingerprint(source_path(relative)) for relative in FROZEN_PARENT_SOURCES}
    for relative, found in frozen.items():
        if found['sha256'] != FROZEN_PARENT_SOURCES[relative]:
            raise ValueError('Source parent gelée différente : ' + relative)
    names = module_names()
    sources = (*V75_TOOLS, *(f'src/v75/{name}.js' for name in names), *SOURCE_DATA)
    return {'parentInputs': parent, 'frozenParentSources': frozen, 'modules75': list(names),
            'sources75': {relative: fingerprint(source_path(relative)) for relative in sources}}


def source_scripts(snapshot):
    scripts = {}
    for name in snapshot['modules75']:
        if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9-]*', name) or name in scripts:
            raise ValueError('Nom de module 0.75 invalide ou dupliqué.')
        relative = f'src/v75/{name}.js'
        expected = snapshot['sources75'][relative]
        if expected['bytes'] > 2 * 1024 * 1024:
            raise ValueError('Module 0.75 trop volumineux : ' + name)
        raw = source_path(relative).read_bytes()
        if len(raw) != expected['bytes'] or digest(raw) != expected['sha256']:
            raise ValueError('Module 0.75 modifié pendant la lecture : ' + name)
        text = raw.decode('utf-8')
        if not text.strip() or '</script' in text.lower():
            raise ValueError('Contenu de script 0.75 vide ou fermeture interdite : ' + name)
        scripts[name] = text
    return scripts


EDITION_RUNTIME = r'''(function(root){
  'use strict';
  function setup(){
    if(!root.__SOMA_V70__?.ready||!root.__SOMA_V74__?.ready){setTimeout(setup,100);return;}
    const version='0.75.0';
    root.__SOMA_V75__=Object.freeze({version,ready:true,ephemeral:true,newGeographicCells:0,
      snapshot:()=>({version,ephemeral:true,newGeographicCells:0,
        terrain:root.__SOMA_TERRAIN75__?.snapshot?.()||null,
        missions:root.__SOMA_MISSIONS75__?.snapshot?.()||null,
        combat:root.__SOMA_COMBAT75__?.snapshot?.()||null,
        vehicles:root.__SOMA_VEHICLES75__?.snapshot?.()||null})});
    root.__SOMA__.version=version;
    document.title='SOMA//MASSILIA 0.75 — Marseille augmentée';
    for(const selector of ['.v34-edition span','.topbar .brand small']){
      const item=document.querySelector(selector);if(item)item.textContent='0.75';
    }
  }
  setup();
})(window);'''


def patch_edition(html):
    if 'id="soma-v75-edition"' in html:
        raise ValueError('Édition 0.75 déjà appliquée.')
    html = rewrite_script(html, 'soma-v69-world-runtime', lambda value: replace_once(value,
        "button.onclick=()=>location.assign('metropole-viewer-v74.html');",
        "button.onclick=()=>location.assign('metropole-viewer-v75.html');",
        'vrai bouton de survol 0.75'))
    # Historical map runtimes contain SVG <title> strings inside body scripts.
    # Only the document head owns the browser's title.
    head = re.search(r'<head>[\s\S]*?</head>', html)
    if head is None:
        raise ValueError('En-tête parent absent.')
    titles = list(re.finditer(r'<title>[\s\S]*?</title>', head[0]))
    if len(titles) != 1:
        raise ValueError('Titre parent absent ou dupliqué.')
    html = replace_once(html, titles[0][0],
                        '<title>SOMA//MASSILIA 0.75 — Marseille augmentée</title>', 'titre 0.75')
    return replace_once(html, '</body>',
        '\n<script id="soma-v75-edition">\n' + EDITION_RUNTIME + '\n</script>\n</body>',
        'version publique après les adaptateurs 0.74 et 0.75')


def patch_html(html, scripts):
    for extension in extensions():
        html = extension.patch_html(html, scripts)
    return patch_edition(html)


def require_unchanged(before, after, label='reconstruction 0.75'):
    if before != after:
        changed = [key for key in sorted(set(before) | set(after)) if before.get(key) != after.get(key)]
        raise ValueError('Une entrée a changé pendant la ' + label + ' : ' + ', '.join(changed))


def build_release():
    before = inputs()
    parent, parent_report = B74.build_release()
    if digest(parent) != PARENT_SHA256:
        raise ValueError('Le parent 0.74 reconstruit diffère de son SHA256 gelé.')
    data = patch_html(parent.decode('utf-8'), source_scripts(before)).encode('utf-8')
    require_unchanged(before, inputs())
    report = {'version': VERSION, 'output': OUTPUT.name, 'bytes': len(data), 'sha256': digest(data),
              'parentVersion': '0.74.0', 'parentSHA256': PARENT_SHA256,
              'originalFilesVerified': parent_report['originalFilesVerified'],
              'sourceGeometryUnchanged': True, 'sourceAssetsUnchanged': True,
              'renderingModified': True, 'renderedGeometryByteIdenticalToParent': False,
              'renderingChanges': ['opt-in-centre-native-5m-terrain', 'sniper-preparation-telegraph'],
              'campaignGeographicRenderingModified': True,
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
    path = Path(path)
    if path.is_symlink() or not path.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError('Chemin de sortie 0.75 invalide.')
    relative = path.resolve().relative_to(ROOT.resolve())
    if not relative.parts:
        raise ValueError('Chemin de sortie 0.75 invalide.')
    protected_html = re.fullmatch(r'(?:SOMA_MASSILIA_URBAIN_v0_|metropole-viewer-v)([0-9]+)\.html', relative.name)
    if (str(relative) in FROZEN_PARENT_SOURCES or str(relative) in V75_TOOLS or
            str(relative) in SOURCE_DATA or
            relative.parts[0] in {'src', 'tools', 'baseline'} or
            (relative.parts[0] == 'data' and relative.parts[:2] != ('data', 'v75')) or
            relative.name == 'metropole-viewer.html' or
            (protected_html and int(protected_html[1]) < 75)):
        raise ValueError('Une sortie 0.75 ne peut pas remplacer un parent gelé.')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.v75-', delete=False) as stream:
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
            raise ValueError('Le HTML 0.75 ne correspond pas aux sources actuelles.')
        if not REPORT.is_file() or REPORT.read_bytes() != encoded:
            raise ValueError('Le rapport 0.75 ne correspond pas aux entrées vérifiées.')
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
        parser.exit(1, f'Reconstruction 0.75 impossible : {error}\n')


if __name__ == '__main__':
    main()
