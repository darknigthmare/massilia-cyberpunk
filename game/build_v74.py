#!/usr/bin/env python3
"""Build edition 0.74 over the verified, unchanged 0.73 sources and world."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import tempfile

import build_v73 as B73
from build_v68 import replace_once, rewrite_script

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / 'SOMA_MASSILIA_URBAIN_v0_74.html'
REPORT = ROOT / 'data/v74/BUILD_REPORT.json'
PARENT_SHA256 = 'b629b30434dddb8eee66402afc1f5c9eaf47389b60a3fe9125f039cdc3f4e0f2'
VERSION = '0.74.0'
EXTENSIONS = ('tools.v74_architecture', 'tools.v74_mobility', 'tools.v74_combat', 'tools.v74_progression')
FROZEN_PARENT_SOURCES = {
    **B73.FROZEN_PARENT_SOURCES,
    'build_v73.py': 'f88f0747830f6cbde0885713d73fbe7052f72e75b80b2d0dd04f7922d0991225',
    'tools/build_metropole_viewer_v73.py': '178914b22da01217bba2442dd5a2e2696a8ffd552f1b16aa07b2eae35a54ef84',
    'tools/serve_v73.py': '0189cc65df87f2445d09830da976f2f4dadbb66319dea656caf6687ec66cd4fb',
    'tools/launch_cache_v73.py': '852ef39dc0cb5fc18c7e070fbc7b18aa1edfa9f349482ebb9979010e925bf2ec',
    'tools/v73_fidelity.py': 'ccf75b794063e02b5b52d22f75783e14828b4f02ab4c94b3dfd63b8393d4f943',
    'tools/v73_tactics.py': 'e111327f345c7f16c61399aa481235107c31fa458f0a58db197d4fa0b225763d',
    'tools/v73_routing.py': '6a619863589749e098356b35455ee982c88ec56efcf3d8aaa1f28e2daeacd601',
    'src/v73/roof-fidelity-core.js': '357a41b0f2a63c3576d3d4bd17bcc6595289a6584f34348b46f837d01adb9bac',
    'src/v73/tactical-runtime.js': 'ae517fc439dc52eb8916f3ee06568ae3a3be6a38e792dee3978e44e9819b640d',
    'src/v73/route-guided-core.js': 'e1353d48476c066d309184962979c8f298f1786e62ea7e987a5cadae98fa152b',
}
V74_TOOLS = ('build_v74.py', 'tools/build_metropole_viewer_v74.py', 'tools/serve_v74.py', 'tools/launch_cache_v74.py',
             *(name.replace('.', '/') + '.py' for name in EXTENSIONS))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def fingerprint(path):
    return B73.fingerprint(Path(path))


def extensions():
    """All extensions are required; a missing feature is a build error."""
    return tuple(importlib.import_module(name) for name in EXTENSIONS)


def module_names():
    names = []
    for extension in extensions():
        declared = extension.MODULES
        if not isinstance(declared, (tuple, list)) or not declared:
            raise ValueError('Déclaration de modules 0.74 vide ou invalide.')
        for name in declared:
            if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9-]*', name) or name in names:
                raise ValueError('Nom de module 0.74 invalide ou dupliqué.')
            names.append(name)
    return tuple(names)


def inputs():
    parent = B73.inputs()
    frozen = {relative: fingerprint(ROOT / relative) for relative in FROZEN_PARENT_SOURCES}
    for relative, found in frozen.items():
        if found['sha256'] != FROZEN_PARENT_SOURCES[relative]:
            raise ValueError('Source parent gelée différente : ' + relative)
    names = module_names()
    sources = (*V74_TOOLS, *(f'src/v74/{name}.js' for name in names))
    return {'parentInputs': parent, 'frozenParentSources': frozen, 'modules74': list(names),
            'sources74': {relative: fingerprint(ROOT / relative) for relative in sources}}


def source_scripts(snapshot):
    scripts = {}
    for name in snapshot['modules74']:
        if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9-]*', name) or name in scripts:
            raise ValueError('Nom de module 0.74 invalide ou dupliqué.')
        relative = f'src/v74/{name}.js'
        expected = snapshot['sources74'][relative]
        if expected['bytes'] > 2 * 1024 * 1024:
            raise ValueError('Module 0.74 trop volumineux : ' + name)
        raw = (ROOT / relative).read_bytes()
        if len(raw) != expected['bytes'] or digest(raw) != expected['sha256']:
            raise ValueError('Module 0.74 modifié pendant la lecture : ' + name)
        text = raw.decode('utf-8')
        if not text.strip() or '</script' in text.lower():
            raise ValueError('Contenu de script 0.74 vide ou fermeture interdite : ' + name)
        scripts[name] = text
    return scripts


EDITION_RUNTIME = r'''(function(root){
  'use strict';
  function setup(){
    if(!root.__SOMA_V70__?.ready||!root.__SOMA_V73__?.ready){setTimeout(setup,100);return;}
    const version='0.74.0';
    root.__SOMA_V74__=Object.freeze({version,ready:true,ephemeral:true,newGeographicCells:0,
      snapshot:()=>({version,ephemeral:true,newGeographicCells:0,
        architecture:root.__SOMA_ARCHITECTURE74__?.snapshot?.()||null,
        mobility:root.__SOMA_MOBILITY74__?.snapshot?.()||null,
        combat:root.__SOMA_COMBAT_SUPPORT74__?.snapshot?.()||null,
        progression:root.__SOMA_PROGRESSION74__?.snapshot?.()||null})});
    root.__SOMA__.version=version;
    document.title='SOMA//MASSILIA 0.74 — Marseille augmentée';
    for(const selector of ['.v34-edition span','.topbar .brand small']){
      const item=document.querySelector(selector);if(item)item.textContent='0.74';
    }
  }
  setup();
})(window);'''


def patch_edition(html):
    if 'id="soma-v74-edition"' in html:
        raise ValueError('Édition 0.74 déjà appliquée.')
    html = rewrite_script(html, 'soma-v69-world-runtime', lambda value: replace_once(value,
        "button.onclick=()=>location.assign('metropole-viewer-v73.html');",
        "button.onclick=()=>location.assign('metropole-viewer-v74.html');",
        'vrai bouton de survol 0.74'))
    # Historical map runtimes contain SVG <title> strings inside body scripts.
    # Only the document head owns the browser's title.
    head = re.search(r'<head>[\s\S]*?</head>', html)
    if head is None:
        raise ValueError('En-tête parent absent.')
    titles = list(re.finditer(r'<title>[\s\S]*?</title>', head[0]))
    if len(titles) != 1:
        raise ValueError('Titre parent absent ou dupliqué.')
    html = replace_once(html, titles[0][0],
                        '<title>SOMA//MASSILIA 0.74 — Marseille augmentée</title>', 'titre 0.74')
    return replace_once(html, '</body>',
        '\n<script id="soma-v74-edition">\n' + EDITION_RUNTIME + '\n</script>\n</body>',
        'version publique après les adaptateurs 0.73 et 0.74')


def patch_html(html, scripts):
    for extension in extensions():
        html = extension.patch_html(html, scripts)
    return patch_edition(html)


def require_unchanged(before, after, label='reconstruction 0.74'):
    if before != after:
        changed = [key for key in sorted(set(before) | set(after)) if before.get(key) != after.get(key)]
        raise ValueError('Une entrée a changé pendant la ' + label + ' : ' + ', '.join(changed))


def build_release():
    before = inputs()
    parent, parent_report = B73.build_release()
    if digest(parent) != PARENT_SHA256:
        raise ValueError('Le parent 0.73 reconstruit diffère de son SHA256 gelé.')
    data = patch_html(parent.decode('utf-8'), source_scripts(before)).encode('utf-8')
    require_unchanged(before, inputs())
    report = {'version': VERSION, 'output': OUTPUT.name, 'bytes': len(data), 'sha256': digest(data),
              'parentVersion': '0.73.0', 'parentSHA256': PARENT_SHA256,
              'originalFilesVerified': parent_report['originalFilesVerified'],
              'sourceGeometryUnchanged': True, 'sourceAssetsUnchanged': True,
              'renderingModified': True, 'renderedGeometryByteIdenticalToParent': False,
              'renderingChanges': ['tactical-support-description'],
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
    path = Path(path)
    if path.is_symlink() or not path.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError('Chemin de sortie 0.74 invalide.')
    relative = path.resolve().relative_to(ROOT.resolve())
    if not relative.parts:
        raise ValueError('Chemin de sortie 0.74 invalide.')
    protected_html = re.fullmatch(r'(?:SOMA_MASSILIA_URBAIN_v0_|metropole-viewer-v)([0-9]+)\.html', relative.name)
    if (str(relative) in FROZEN_PARENT_SOURCES or
            relative.parts[0] in {'src', 'tools', 'baseline'} or
            (relative.parts[0] == 'data' and relative.parts[:2] != ('data', 'v74')) or
            relative.name == 'metropole-viewer.html' or
            (protected_html and int(protected_html[1]) < 74)):
        raise ValueError('Une sortie 0.74 ne peut pas remplacer un parent gelé.')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.v74-', delete=False) as stream:
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
            raise ValueError('Le HTML 0.74 ne correspond pas aux sources actuelles.')
        if not REPORT.is_file() or REPORT.read_bytes() != encoded:
            raise ValueError('Le rapport 0.74 ne correspond pas aux entrées vérifiées.')
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
        parser.exit(1, f'Reconstruction 0.74 impossible : {error}\n')


if __name__ == '__main__':
    main()
