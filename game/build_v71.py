#!/usr/bin/env python3
"""Build edition 0.71 over the verified, unchanged 0.70 sources and world."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import tempfile

import build_v70 as B70
from build_v68 import replace_once, rewrite_script

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / 'SOMA_MASSILIA_URBAIN_v0_71.html'
REPORT = ROOT / 'data/v71/BUILD_REPORT.json'
PARENT_SHA256 = 'c73fcd0b771d83aa1849130934ca432c3dcb70f40905e9638792eca4afc01c2a'
VERSION = '0.71.0'
EXTENSIONS = ('tools.v71_legacy_perception', 'tools.v71_architecture', 'tools.v71_route_viewer')
FROZEN_PARENT_SOURCES = {
    'build_v70.py': '4788f3e072f1708cecae0235aa5da5e88977a1a39c064537507db2126ee637ac',
    'tools/v70_persistence.py': 'a85888ed46be517d16bc0f6ae74fb8f068f81722c2d7ea3fb65ec0b9ead9bacf',
    'tools/v70_gameplay.py': 'e3c43c4f66089bc6de44859e6d675931551d0ed5bc7bebb95ca7460a84e5bf54',
    'src/v70/augmentations-core.js': 'ea05cae0a634513c932728313f229a3cc82d604ad6a234e37e338dcf12dad215',
    'src/v70/infiltration-core.js': 'f4ed8fec6f398ceba7677bf0423767fefe9ec18e5371c97eea5b90b7fc9ad220',
    'src/v70/material-extension-core.js': '3286a5209d51fbf8995580db14810be11522a08ed9485bd1ce71bc5cb7a1217b',
    'src/v70/perception-runtime.js': '7b691f45b3fba23e12d55a097e3ab7971e137daff47e99f41aba414fd5026c1a',
    'src/v70/runtime.js': 'c82e36b043c0f12158022949464cf41ee22387507abf5383873af7dc3c8ac9ee',
    'src/v70/world-index.js': '3a53b1ed0b788ae721fed5830af9affab1e20999889816001d373408c4b4fad5',
    'src/v70/route-preview-core.js': '3f1df2f74b4323e863b3ddc7734d4943e9d5e3ca3b8e7588645176c9f8c1c85f',
    'src/v70/viewer-runtime.js': '716fa63a501864a2c5e5ae5ace5c434ea9f7915eac33dca8fd738a4015910c25',
    'tools/build_metropole_viewer_v70.py': 'f8eb3cae73bcb1b46f950496ef0892974579383e89fd7dabe3a1f51e69e592a1',
    'tools/build_metropole_viewer.py': 'e6089c3541cb6452abcf15f1c14737cdc0f32fb01437abf7d8389e4177da28d7',
    'src/v69/metropole-viewer.html': '08528097b8e41057c23928d53fc91bed7d7a871cc2346afa0083f261e0533d19',
}
V71_TOOLS = ('build_v71.py', 'tools/build_metropole_viewer_v71.py', 'tools/serve_v71.py',
             *(name.replace('.', '/') + '.py' for name in EXTENSIONS))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def fingerprint(path):
    return B70.fingerprint(Path(path))


def extensions():
    """All extensions are required; a missing feature is a build error."""
    return tuple(importlib.import_module(name) for name in EXTENSIONS)


def module_names():
    names = []
    for extension in extensions():
        declared = extension.MODULES
        if not isinstance(declared, (tuple, list)) or not declared:
            raise ValueError('Déclaration de modules 0.71 vide ou invalide.')
        for name in declared:
            if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9-]*', name) or name in names:
                raise ValueError('Nom de module 0.71 invalide ou dupliqué.')
            names.append(name)
    return tuple(names)


def inputs():
    parent = B70.inputs()
    frozen = {relative: fingerprint(ROOT / relative) for relative in FROZEN_PARENT_SOURCES}
    for relative, found in frozen.items():
        if found['sha256'] != FROZEN_PARENT_SOURCES[relative]:
            raise ValueError('Source parent gelée différente : ' + relative)
    names = module_names()
    sources = (*V71_TOOLS, *(f'src/v71/{name}.js' for name in names))
    return {'parentInputs': parent, 'frozenParentSources': frozen, 'modules71': list(names),
            'sources71': {relative: fingerprint(ROOT / relative) for relative in sources}}


def source_scripts(snapshot):
    scripts = {}
    for name in snapshot['modules71']:
        if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9-]*', name) or name in scripts:
            raise ValueError('Nom de module 0.71 invalide ou dupliqué.')
        relative = f'src/v71/{name}.js'
        expected = snapshot['sources71'][relative]
        if expected['bytes'] > 2 * 1024 * 1024:
            raise ValueError('Module 0.71 trop volumineux : ' + name)
        raw = (ROOT / relative).read_bytes()
        if len(raw) != expected['bytes'] or digest(raw) != expected['sha256']:
            raise ValueError('Module 0.71 modifié pendant la lecture : ' + name)
        text = raw.decode('utf-8')
        if not text.strip() or '</script' in text.lower():
            raise ValueError('Contenu de script 0.71 vide ou fermeture interdite : ' + name)
        scripts[name] = text
    return scripts


EDITION_RUNTIME = r'''(function(root){
  'use strict';
  function setup(){
    if(!root.__SOMA_V70__?.ready){setTimeout(setup,100);return;}
    const version='0.71.0';
    root.__SOMA_V71__=Object.freeze({version,ephemeral:true,newGeographicCells:0,
      snapshot:()=>({version,ephemeral:true,newGeographicCells:0,
        legacyPerception:root.__SOMA_LEGACY_PERCEPTION71__?.snapshot?.()||null})});
    root.__SOMA__.version=version;
    document.title='SOMA//MASSILIA 0.71 — Marseille augmentée';
    for(const selector of ['.v34-edition span','.topbar .brand small']){
      const item=document.querySelector(selector);if(item)item.textContent='0.71';
    }
  }
  setup();
})(window);'''


def patch_edition(html):
    if 'id="soma-v71-edition"' in html:
        raise ValueError('Édition 0.71 déjà appliquée.')
    html = rewrite_script(html, 'soma-v69-world-runtime', lambda value: replace_once(value,
        "button.onclick=()=>location.assign('metropole-viewer-v70.html');",
        "button.onclick=()=>location.assign('metropole-viewer-v71.html');",
        'vrai bouton de survol 0.71'))
    # Historical map runtimes contain SVG <title> strings inside body scripts.
    # Only the document head owns the browser's title.
    head = re.search(r'<head>[\s\S]*?</head>', html)
    if head is None:
        raise ValueError('En-tête parent absent.')
    titles = list(re.finditer(r'<title>[\s\S]*?</title>', head[0]))
    if len(titles) != 1:
        raise ValueError('Titre parent absent ou dupliqué.')
    html = replace_once(html, titles[0][0],
                        '<title>SOMA//MASSILIA 0.71 — Marseille augmentée</title>', 'titre 0.71')
    return replace_once(html, '</body>',
        '\n<script id="soma-v71-edition">\n' + EDITION_RUNTIME + '\n</script>\n</body>',
        'version publique après les adaptateurs 0.70 et 0.71')


def patch_html(html, scripts):
    legacy, architecture, route = extensions()
    html = legacy.patch_html(html, scripts)
    html = architecture.patch_html(html, scripts)
    html = route.patch_html(html, scripts)
    return patch_edition(html)


def require_unchanged(before, after, label='reconstruction 0.71'):
    if before != after:
        changed = [key for key in sorted(set(before) | set(after)) if before.get(key) != after.get(key)]
        raise ValueError('Une entrée a changé pendant la ' + label + ' : ' + ', '.join(changed))


def build_release():
    before = inputs()
    parent, parent_report = B70.build_release()
    if digest(parent) != PARENT_SHA256:
        raise ValueError('Le parent 0.70 reconstruit diffère de son SHA256 gelé.')
    data = patch_html(parent.decode('utf-8'), source_scripts(before)).encode('utf-8')
    require_unchanged(before, inputs())
    report = {'version': VERSION, 'output': OUTPUT.name, 'bytes': len(data), 'sha256': digest(data),
              'parentVersion': '0.70.0', 'parentSHA256': PARENT_SHA256,
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
        raise ValueError('Chemin de sortie 0.71 invalide.')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.v71-', delete=False) as stream:
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
            raise ValueError('Le HTML 0.71 ne correspond pas aux sources actuelles.')
        if not REPORT.is_file() or REPORT.read_bytes() != encoded:
            raise ValueError('Le rapport 0.71 ne correspond pas aux entrées vérifiées.')
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
        parser.exit(1, f'Reconstruction 0.71 impossible : {error}\n')


if __name__ == '__main__':
    main()
