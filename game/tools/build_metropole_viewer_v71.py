#!/usr/bin/env python3
"""Build the independent 0.71 flyover from the byte-verified 0.70 viewer.

The 0.69 source HTML may be reconstructed in a temporary file when generated
parent HTML files are absent. No parent output or geographic asset is written.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / 'tools') not in sys.path:
    sys.path.insert(0, str(ROOT / 'tools'))
import build_v71 as B71
import build_metropole_viewer_v70 as V70

OUTPUT = ROOT / 'metropole-viewer-v71.html'
REPORT = ROOT / 'data/v71/VIEWER_BUILD_REPORT.json'
PARENT_SHA256 = 'c7c8b4ed748609332527a3c0bc72afc80aef42a239d647831e0ed9ff9110b03c'
SOURCE_PARENT_SHA256 = B71.B70.PARENT_SHA256


def parent_viewer(source_html=None, expected_sha=None):
    expected_sha = SOURCE_PARENT_SHA256 if expected_sha is None else expected_sha
    if expected_sha != SOURCE_PARENT_SHA256:
        raise ValueError('Le SHA256 du HTML source 0.69 doit rester celui du parent gelé.')
    explicit = source_html is not None
    source = Path(source_html) if explicit else V70.V69.SOURCE
    temporary = None
    try:
        if not source.is_file() and not explicit:
            parent = B71.B70.build_v69()
            if B71.digest(parent) != SOURCE_PARENT_SHA256:
                raise ValueError('Le HTML source 0.69 reconstruit diffère de son SHA256 gelé.')
            with tempfile.NamedTemporaryFile(prefix='soma-v71-parent69-', suffix='.html', delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(parent)
            source = temporary
        output = V70.build(source, expected_sha)
        if B71.digest(output) != PARENT_SHA256:
            raise ValueError('Le survol parent 0.70 reconstruit diffère de son SHA256 gelé.')
        return output
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def patch_edition(html):
    html = V70.replace_once(html,
        '<title>SOMA//MASSILIA 0.70 — Survol & itinéraire local</title>',
        '<title>SOMA//MASSILIA 0.71 — Survol, itinéraire & architecture</title>')
    html = V70.replace_once(html, 'SURVOL MÉTROPOLITAIN · 0.70', 'SURVOL MÉTROPOLITAIN · 0.71')
    html = V70.replace_once(html, 'href="SOMA_MASSILIA_URBAIN_v0_70.html"',
                          'href="SOMA_MASSILIA_URBAIN_v0_71.html"')
    controller = V70.V69.script(html, 'viewer-metropole-viewer')
    controller = V70.replace_once(controller, "version:'0.70.0',worldIndex:", "version:'0.71.0',worldIndex:")
    html = V70.replace_script(html, 'viewer-metropole-viewer', controller)
    metadata = json.loads(V70.V69.script(html, 'soma-viewer-data', json_only=True))
    if metadata.get('version') != '0.70.0' or metadata.get('returnToGame') != 'SOMA_MASSILIA_URBAIN_v0_70.html':
        raise ValueError('Métadonnées du survol parent 0.70 absentes ou modifiées.')
    metadata.update(version=B71.VERSION, returnToGame=B71.OUTPUT.name,
                    parentViewer70SHA256=PARENT_SHA256, newGeographicCells=0,
                    newPersistenceDomain=False)
    matches = list(re.finditer(r'<script id="soma-viewer-data" type="application/json">[\s\S]*?</script>', html))
    if len(matches) != 1:
        raise ValueError('Métadonnées du survol absentes ou dupliquées.')
    encoded = json.dumps(metadata, ensure_ascii=False, separators=(',', ':'), allow_nan=False).replace('<', '\\u003c')
    return V70.replace_once(html, matches[0][0],
        '<script id="soma-viewer-data" type="application/json">' + encoded + '</script>')


def patch_html(html, scripts):
    _legacy, architecture, route = B71.extensions()
    html = architecture.patch_viewer(html, scripts)
    html = route.patch_viewer(html, scripts)
    return patch_edition(html)


def build_release(source_html=None, expected_sha=None):
    before = B71.inputs()
    original = parent_viewer(source_html, expected_sha)
    output = patch_html(original.decode('utf-8'), B71.source_scripts(before)).encode('utf-8')
    B71.require_unchanged(before, B71.inputs(), 'construction du survol 0.71')
    report = {'version': B71.VERSION, 'output': OUTPUT.name, 'bytes': len(output),
              'sha256': B71.digest(output), 'parentVersion': '0.70.0',
              'parentSHA256': PARENT_SHA256, 'sourceHTML69SHA256': SOURCE_PARENT_SHA256,
              'originalFilesVerified': len(before['parentInputs']['originals']),
              'sourceGeometryUnchanged': True, 'newGeographicCells': 0,
              'newPersistenceDomain': False, 'campaignPersistenceLoaded': False,
              'navigationLoadedOnDemand': True, 'completeMetropole': False,
              'certifiedOneToOne': False, 'inputs': before}
    return output, report


def build(source_html=None, expected_sha=None):
    return build_release(source_html, expected_sha)[0]


def prepare(*, verify=False, source_html=None, expected_sha=None, output=None):
    target = OUTPUT if output is None else Path(output)
    data, report = build_release(source_html, expected_sha)
    report = dict(report, output=target.name)
    encoded = (json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')
    if verify:
        if not target.is_file() or target.read_bytes() != data:
            raise ValueError('Le survol 0.71 ne correspond pas aux sources actuelles.')
        if not REPORT.is_file() or REPORT.read_bytes() != encoded:
            raise ValueError('Le rapport du survol 0.71 ne correspond pas aux entrées vérifiées.')
    else:
        B71.atomic_write(target, data)
        B71.atomic_write(REPORT, encoded)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-html', type=Path)
    parser.add_argument('--source-sha256')
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    try:
        report = prepare(verify=args.verify, source_html=args.source_html,
                         expected_sha=args.source_sha256, output=args.output)
        print(json.dumps({key: report[key] for key in ('version', 'output', 'bytes', 'sha256',
            'campaignPersistenceLoaded', 'navigationLoadedOnDemand')} | {'verified': args.verify}, ensure_ascii=False))
    except (OSError, ValueError, KeyError, TypeError, ImportError, AttributeError) as error:
        parser.exit(1, 'Construction du survol 0.71 impossible : ' + str(error) + '\n')


if __name__ == '__main__':
    main()
