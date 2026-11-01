#!/usr/bin/env python3
"""Build edition 0.73 over the verified, unchanged 0.72 sources and world."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import tempfile

import build_v72 as B72
from build_v68 import replace_once, rewrite_script

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / 'SOMA_MASSILIA_URBAIN_v0_73.html'
REPORT = ROOT / 'data/v73/BUILD_REPORT.json'
PARENT_SHA256 = '77f09426c0c68ec2702f8ce8cc46b75d5005d468d2988416f6cbe92155ae1c50'
VERSION = '0.73.0'
EXTENSIONS = ('tools.v73_fidelity', 'tools.v73_tactics', 'tools.v73_routing')
FROZEN_PARENT_SOURCES = {
    **B72.FROZEN_PARENT_SOURCES,
    'build_v72.py': 'fdeedbaae1582b0dc8651c2ca586093443980fe721b438d8fc94346f787abbbb',
    'src/v72/contact-sharing-runtime.js': '097f637521d341982efcad126ec4158f9040c17d5d23b556e43d0fbaf2c8d9d1',
    'src/v72/fidelity-core.js': 'c1d0ae947a3a26d3d7bdb76ecb5d5fd28cf290bb30697d230a6b9df49419fd9d',
    'src/v72/hud-layout-runtime.js': 'e2642dd13d23927d79b61e5bff95878dcee15263af2c610777cc946c5a16c589',
    'src/v72/netrunner-runtime.js': '1962944f6309b19ed86ca0bc8ce0fe4bd26e22f1f7889738ae7ea6b806d83c60',
    'src/v72/road-inspector-core.js': '0e96e167eb383ebc59e6e29b61c5de725b8b6cd6f0bf218da46f6267e52d981b',
    'src/v72/road-inspector-runtime.js': '2d418a64b29e39ced264416da9cad6ac66698ec71e7fb8bfbeb2d61ba7a34905',
    'src/v72/route-corridor-core.js': 'c2b7164d5151b6f4fb063e428dfae24f9e964190426757e2cbd8f15d6b48b8ec',
    'tools/build_metropole_viewer_v72.py': '32a36522281beac29fd2496bb3d73275ed423d1d6e22218188e20c11ab4b46b6',
    'tools/launch_cache_v72.py': 'c4e27194359fe6766b2c7fcf8bc686396b76e6359e036aa4c0f3418ebb7401f4',
    'tools/serve_v72.py': '6cdcde15b4a2b3db941110dce6a0f8616081add4491086d7e8a15ce73a11bfca',
    'tools/v72_contact_sharing.py': 'a25cfb7426c98ddc313ef431d15565b8f94fe71c55fd710152b1a7b561e944cb',
    'tools/v72_fidelity.py': 'c9719d69001ef63625f543fe3f4e455d6ebb671b742e63e26b5cf04433c1d966',
    'tools/v72_hud.py': '1137e850ec9635ac4c35f623d1bf4c641c9cb9747cb422c8657fbe4c10a4df3e',
    'tools/v72_netrunner.py': '35ed993af5c57c89c1f5ac480e83da332a7245e9caf88d47427c4283be2db553',
    'tools/v72_routing.py': '68d08b8a28d10da504705507778b9fc58c240fd27fb932eca01c46b7840a69fd',
}
V73_TOOLS = ('build_v73.py', 'tools/build_metropole_viewer_v73.py', 'tools/serve_v73.py', 'tools/launch_cache_v73.py',
             *(name.replace('.', '/') + '.py' for name in EXTENSIONS))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def fingerprint(path):
    return B72.fingerprint(Path(path))


def extensions():
    """All extensions are required; a missing feature is a build error."""
    return tuple(importlib.import_module(name) for name in EXTENSIONS)


def module_names():
    names = []
    for extension in extensions():
        declared = extension.MODULES
        if not isinstance(declared, (tuple, list)) or not declared:
            raise ValueError('Déclaration de modules 0.73 vide ou invalide.')
        for name in declared:
            if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9-]*', name) or name in names:
                raise ValueError('Nom de module 0.73 invalide ou dupliqué.')
            names.append(name)
    return tuple(names)


def inputs():
    parent = B72.inputs()
    frozen = {relative: fingerprint(ROOT / relative) for relative in FROZEN_PARENT_SOURCES}
    for relative, found in frozen.items():
        if found['sha256'] != FROZEN_PARENT_SOURCES[relative]:
            raise ValueError('Source parent gelée différente : ' + relative)
    names = module_names()
    sources = (*V73_TOOLS, *(f'src/v73/{name}.js' for name in names))
    return {'parentInputs': parent, 'frozenParentSources': frozen, 'modules73': list(names),
            'sources73': {relative: fingerprint(ROOT / relative) for relative in sources}}


def source_scripts(snapshot):
    scripts = {}
    for name in snapshot['modules73']:
        if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9-]*', name) or name in scripts:
            raise ValueError('Nom de module 0.73 invalide ou dupliqué.')
        relative = f'src/v73/{name}.js'
        expected = snapshot['sources73'][relative]
        if expected['bytes'] > 2 * 1024 * 1024:
            raise ValueError('Module 0.73 trop volumineux : ' + name)
        raw = (ROOT / relative).read_bytes()
        if len(raw) != expected['bytes'] or digest(raw) != expected['sha256']:
            raise ValueError('Module 0.73 modifié pendant la lecture : ' + name)
        text = raw.decode('utf-8')
        if not text.strip() or '</script' in text.lower():
            raise ValueError('Contenu de script 0.73 vide ou fermeture interdite : ' + name)
        scripts[name] = text
    return scripts


EDITION_RUNTIME = r'''(function(root){
  'use strict';
  function setup(){
    if(!root.__SOMA_V70__?.ready||!root.__SOMA_V72__?.ready){setTimeout(setup,100);return;}
    const version='0.73.0';
    root.__SOMA_V73__=Object.freeze({version,ready:true,ephemeral:true,newGeographicCells:0,
      snapshot:()=>({version,ephemeral:true,newGeographicCells:0,
        roofFidelityVersion:root.__SOMA_ROOF_FIDELITY73_CORE__?.VERSION||null,
        tactics:root.__SOMA_TACTICAL73__?.snapshot?.()||null})});
    root.__SOMA__.version=version;
    document.title='SOMA//MASSILIA 0.73 — Marseille augmentée';
    for(const selector of ['.v34-edition span','.topbar .brand small']){
      const item=document.querySelector(selector);if(item)item.textContent='0.73';
    }
  }
  setup();
})(window);'''


def patch_edition(html):
    if 'id="soma-v73-edition"' in html:
        raise ValueError('Édition 0.73 déjà appliquée.')
    html = rewrite_script(html, 'soma-v69-world-runtime', lambda value: replace_once(value,
        "button.onclick=()=>location.assign('metropole-viewer-v72.html');",
        "button.onclick=()=>location.assign('metropole-viewer-v73.html');",
        'vrai bouton de survol 0.73'))
    # Historical map runtimes contain SVG <title> strings inside body scripts.
    # Only the document head owns the browser's title.
    head = re.search(r'<head>[\s\S]*?</head>', html)
    if head is None:
        raise ValueError('En-tête parent absent.')
    titles = list(re.finditer(r'<title>[\s\S]*?</title>', head[0]))
    if len(titles) != 1:
        raise ValueError('Titre parent absent ou dupliqué.')
    html = replace_once(html, titles[0][0],
                        '<title>SOMA//MASSILIA 0.73 — Marseille augmentée</title>', 'titre 0.73')
    return replace_once(html, '</body>',
        '\n<script id="soma-v73-edition">\n' + EDITION_RUNTIME + '\n</script>\n</body>',
        'version publique après les adaptateurs 0.72 et 0.73')


def patch_html(html, scripts):
    for extension in extensions():
        html = extension.patch_html(html, scripts)
    return patch_edition(html)


def require_unchanged(before, after, label='reconstruction 0.73'):
    if before != after:
        changed = [key for key in sorted(set(before) | set(after)) if before.get(key) != after.get(key)]
        raise ValueError('Une entrée a changé pendant la ' + label + ' : ' + ', '.join(changed))


def build_release():
    before = inputs()
    parent, parent_report = B72.build_release()
    if digest(parent) != PARENT_SHA256:
        raise ValueError('Le parent 0.72 reconstruit diffère de son SHA256 gelé.')
    data = patch_html(parent.decode('utf-8'), source_scripts(before)).encode('utf-8')
    require_unchanged(before, inputs())
    report = {'version': VERSION, 'output': OUTPUT.name, 'bytes': len(data), 'sha256': digest(data),
              'parentVersion': '0.72.0', 'parentSHA256': PARENT_SHA256,
              'originalFilesVerified': parent_report['originalFilesVerified'],
              'sourceGeometryUnchanged': True, 'sourceAssetsUnchanged': True,
              'renderingModified': True, 'renderedGeometryByteIdenticalToParent': False,
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
        raise ValueError('Chemin de sortie 0.73 invalide.')
    relative = path.resolve().relative_to(ROOT.resolve())
    if not relative.parts:
        raise ValueError('Chemin de sortie 0.73 invalide.')
    protected_html = re.fullmatch(r'(?:SOMA_MASSILIA_URBAIN_v0_|metropole-viewer-v)([0-9]+)\.html', relative.name)
    if (str(relative) in FROZEN_PARENT_SOURCES or
            relative.parts[0] in {'src', 'tools', 'baseline'} or
            (relative.parts[0] == 'data' and relative.parts[:2] != ('data', 'v73')) or
            relative.name == 'metropole-viewer.html' or
            (protected_html and int(protected_html[1]) < 73)):
        raise ValueError('Une sortie 0.73 ne peut pas remplacer un parent gelé.')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.v73-', delete=False) as stream:
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
            raise ValueError('Le HTML 0.73 ne correspond pas aux sources actuelles.')
        if not REPORT.is_file() or REPORT.read_bytes() != encoded:
            raise ValueError('Le rapport 0.73 ne correspond pas aux entrées vérifiées.')
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
        parser.exit(1, f'Reconstruction 0.73 impossible : {error}\n')


if __name__ == '__main__':
    main()
