#!/usr/bin/env python3
"""Build the independent 0.72 flyover from the byte-verified 0.71 viewer.

Missing generated parents are reconstructed entirely in memory (with the
existing bounded temporary source69 fallback). No parent output is published.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / 'tools') not in sys.path:
    sys.path.insert(0, str(ROOT / 'tools'))
import build_v72 as B72
import build_metropole_viewer_v71 as V71

OUTPUT = ROOT / 'metropole-viewer-v72.html'
REPORT = ROOT / 'data/v72/VIEWER_BUILD_REPORT.json'
PARENT_SHA256 = '2f06f5c2d0710af5ce9e96d12290e46672fb98c099951c8a7523c9dbafd69a54'
SOURCE_PARENT_SHA256 = V71.SOURCE_PARENT_SHA256
V69 = V71.V70.V69
replace_once = V71.V70.replace_once
replace_script = V71.V70.replace_script


def parent_viewer(source_html=None, expected_sha=None):
    expected_sha = SOURCE_PARENT_SHA256 if expected_sha is None else expected_sha
    if expected_sha != SOURCE_PARENT_SHA256:
        raise ValueError('Le SHA256 du HTML source 0.69 doit rester celui du parent gelé.')
    output = V71.build(source_html, expected_sha)
    if B72.digest(output) != PARENT_SHA256:
        raise ValueError('Le survol parent 0.71 reconstruit diffère de son SHA256 gelé.')
    return output


def patch_edition(html):
    html = replace_once(html,
        '<title>SOMA//MASSILIA 0.71 — Survol, itinéraire & architecture</title>',
        '<title>SOMA//MASSILIA 0.72 — Survol, itinéraire & inspection</title>')
    html = replace_once(html, 'SURVOL MÉTROPOLITAIN · 0.71', 'SURVOL MÉTROPOLITAIN · 0.72')
    html = replace_once(html, 'href="SOMA_MASSILIA_URBAIN_v0_71.html"',
                        'href="SOMA_MASSILIA_URBAIN_v0_72.html"')
    html = replace_once(html, '<h2 id="route70-title">Itinéraire local · 0.71</h2>',
                        '<h2 id="route70-title">Itinéraire par corridor · 0.72</h2>')
    route = V69.script(html, 'viewer-runtime70')
    route = replace_once(route, "version:'0.71.0',...state", "version:'0.72.0',...state")
    html = replace_script(html, 'viewer-runtime70', route)
    controller = V69.script(html, 'viewer-metropole-viewer')
    controller = replace_once(controller, "version:'0.71.0',worldIndex:", "version:'0.72.0',worldIndex:")
    html = replace_script(html, 'viewer-metropole-viewer', controller)
    metadata = json.loads(V69.script(html, 'soma-viewer-data', json_only=True))
    if metadata.get('version') != '0.71.0' or metadata.get('returnToGame') != 'SOMA_MASSILIA_URBAIN_v0_71.html':
        raise ValueError('Métadonnées du survol parent 0.71 absentes ou modifiées.')
    metadata.update(version=B72.VERSION, returnToGame=B72.OUTPUT.name,
                    parentViewer71SHA256=PARENT_SHA256, newGeographicCells=0,
                    newPersistenceDomain=False)
    matches = list(re.finditer(r'<script id="soma-viewer-data" type="application/json">[\s\S]*?</script>', html))
    if len(matches) != 1:
        raise ValueError('Métadonnées du survol absentes ou dupliquées.')
    encoded = json.dumps(metadata, ensure_ascii=False, separators=(',', ':'), allow_nan=False).replace('<', '\\u003c')
    return replace_once(html, matches[0][0],
        '<script id="soma-viewer-data" type="application/json">' + encoded + '</script>')


def patch_html(html, scripts):
    for extension in B72.extensions():
        patch = getattr(extension, 'patch_viewer', None)
        if patch is not None:
            html = patch(html, scripts)
    return patch_edition(html)


def build_release(source_html=None, expected_sha=None):
    before = B72.inputs()
    original = parent_viewer(source_html, expected_sha)
    output = patch_html(original.decode('utf-8'), B72.source_scripts(before)).encode('utf-8')
    B72.require_unchanged(before, B72.inputs(), 'construction du survol 0.72')
    report = {'version': B72.VERSION, 'output': OUTPUT.name, 'bytes': len(output),
              'sha256': B72.digest(output), 'parentVersion': '0.71.0',
              'parentSHA256': PARENT_SHA256, 'sourceHTML69SHA256': SOURCE_PARENT_SHA256,
              'originalFilesVerified': len(before['parentInputs']['parentInputs']['originals']),
              'sourceGeometryUnchanged': True, 'newGeographicCells': 0,
              'sourceAssetsUnchanged': True, 'renderingModified': True,
              'renderedGeometryByteIdenticalToParent': False,
              'validatedRenderingCorrections': [{
                  'kind': 'source-width-leading-dot', 'wayId': '1413045827',
                  'cellId': 'V52-MC-E12-N70', 'sourceWidthMeters': 0.5,
                  'parentRenderedWidthMeters': 1.8, 'appliedWhenSourceCellLoaded': True,
                  'sourceDataRewritten': False}],
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
            raise ValueError('Le survol 0.72 ne correspond pas aux sources actuelles.')
        if not REPORT.is_file() or REPORT.read_bytes() != encoded:
            raise ValueError('Le rapport du survol 0.72 ne correspond pas aux entrées vérifiées.')
    else:
        B72.atomic_write(target, data)
        B72.atomic_write(REPORT, encoded)
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
        parser.exit(1, 'Construction du survol 0.72 impossible : ' + str(error) + '\n')


if __name__ == '__main__':
    main()
