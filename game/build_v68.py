#!/usr/bin/env python3
"""Rebuild v0.68 from the verified v0.67 release, without changing its sources."""
from pathlib import Path
import argparse
import hashlib
import json
import re

from tools.v68_persistence import patch_persistence

ROOT = Path(__file__).resolve().parent
ORIGINAL = ROOT / 'SOMA_MASSILIA_URBAIN_v0_67.html'
OUTPUT = ROOT / 'SOMA_MASSILIA_URBAIN_v0_68.html'
ORIGINAL_SHA256 = 'f4f30ee5d08c9596398a5762c79287c7e67ccebf0796150f52d552156331294f'


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def replace_once(text, old, new, label):
    if text.count(old) != 1:
        raise ValueError(f'Ancre de reconstruction différente : {label}')
    return text.replace(old, new, 1)


def rewrite_script(html, script_id, rewrite):
    pattern = re.compile(r'(<script\b[^>]*\bid="' + re.escape(script_id) + r'"[^>]*>)(.*?)(</script>)', re.S)
    if len(pattern.findall(html)) != 1:
        raise ValueError(f'Script absent ou dupliqué : {script_id}')
    return pattern.sub(lambda match: match[1] + rewrite(match[2]) + match[3], html, count=1)


def architecture_patch(script):
    original = 'function addRealBuilding55(z,g,rings,p,sourceId,index,partIndex=0){'
    wrapper = '''function addRealBuilding55(z,g,rings,p,sourceId,index,partIndex=0){
 if(!z.v50Record?.v53Validated||z.v50Record.v53Synthetic||!z.v50Projector.toMetric)return addRealBuildingLegacy68(z,g,rings,p,sourceId,index,partIndex);
 return window.__SOMA_ARCH68__.render(z,g,rings,p,sourceId,index,partIndex,{
  geometryMesh53,addPolygonCollider,C50,C,inPolygon:window.__SOMA_V53_CORE__.inPolygon,
  dimension:window.__SOMA_FIDELITY59_CORE__.dimension,heightReference:window.__SOMA_FIDELITY59__.heightReference
 });
}
function addRealBuildingLegacy68(z,g,rings,p,sourceId,index,partIndex=0){'''
    script = replace_once(script, original, wrapper, 'bâtiments réels')
    return replace_once(script, 'function resetZoneArrays(z){',
                        'function resetZoneArrays(z){window.__SOMA_ARCH68__.beginCell(z);', 'compteurs architecture')


def lighting_patch(html):
    # RGB above 1.25 marks only interpreted emissive surfaces. Source wall and
    # roof colours remain in [0,1] and keep the existing directional lighting.
    # This is self-emission, not a dynamic light or a bloom postprocess.
    return replace_once(
        html, 'vColor=aColor*li;vPos=aPos;',
        'float emission=step(1.25,max(aColor.r,max(aColor.g,aColor.b)));'
        'vColor=mix(aColor*li,clamp(aColor,0.0,1.0),emission);vPos=aPos;',
        'surfaces lumineuses cyberpunk',
    )


def source_script(name):
    text = (ROOT / 'src' / 'v68' / name).read_text(encoding='utf-8')
    if '</script' in text.lower():
        raise ValueError(f'Fermeture de script interdite dans {name}')
    return text


def build():
    raw = ORIGINAL.read_bytes()
    if sha256(raw) != ORIGINAL_SHA256:
        raise ValueError('Livraison v0.67 différente. Préparer la base originale avec python3 lancer.py --prepare-only.')
    html = raw.decode('utf-8')
    html = rewrite_script(html, 'soma-v37-persistence', patch_persistence)
    html = rewrite_script(html, 'soma-v50-playable-truth-cells', architecture_patch)
    html = lighting_patch(html)
    modules = ''.join(f'\n<script id="soma-v68-{name}">\n{source_script(name + ".js")}\n</script>\n'
                      for name in ('architecture-core', 'building-renderer'))
    html = replace_once(html, '<script id="soma-v50-playable-truth-cells">',
                        modules + '<script id="soma-v50-playable-truth-cells">', 'modules architecture')
    html = replace_once(html, '</body>', '\n<script id="soma-v68-world-runtime">\n' +
                        source_script('world-runtime.js') + '\n</script>\n</body>', 'module ambiance')
    for script_id in ('soma-v68-architecture-core', 'soma-v68-building-renderer', 'soma-v68-world-runtime'):
        if html.count(f'id="{script_id}"') != 1:
            raise ValueError(f'Module de reconstruction dupliqué : {script_id}')
    return html.encode('utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true', help='comparer le HTML aux sources sans le remplacer')
    args = parser.parse_args()
    try:
        data = build()
        if args.verify:
            if not OUTPUT.is_file() or OUTPUT.read_bytes() != data:
                raise ValueError('Le HTML v0.68 ne correspond pas aux sources actuelles ; reconstruire avec game/build_v68.py.')
            print(f'v0.68 reproductible : {len(data)} octets, SHA256 {sha256(data)}')
        else:
            # An explicit development build replaces only this generated output.
            OUTPUT.write_bytes(data)
            report = {'version':'0.68.0', 'baselineSHA256':ORIGINAL_SHA256,
                      'output':OUTPUT.name, 'bytes':len(data), 'sha256':sha256(data),
                      'sourceGeometryUnchanged':True, 'newGeographicCells':0,
                      'sources':{str(path.relative_to(ROOT)):sha256(path.read_bytes())
                                 for path in [Path(__file__), ROOT/'tools/v68_persistence.py',
                                              *sorted((ROOT/'src/v68').glob('*.js'))]}}
            report_dir = ROOT/'data/v68'
            report_dir.mkdir(parents=True, exist_ok=True)
            (report_dir/'BUILD_REPORT.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
            print(f'{OUTPUT.name} : {len(data)} octets, SHA256 {sha256(data)}')
        return 0
    except (OSError, ValueError) as error:
        parser.exit(1, f'Reconstruction v0.68 impossible : {error}\n')


if __name__ == '__main__':
    raise SystemExit(main())
