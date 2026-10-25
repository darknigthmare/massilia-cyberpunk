#!/usr/bin/env python3
"""Build the source-bound metropolitan tools and architectural corrections."""
from pathlib import Path
import argparse
import hashlib
import json

from build_v68 import build as build_v68, replace_once, rewrite_script
from tools.metropole.bootstrap import embedded, prepare_world, verify_world, digest
from tools.metropole.building_parts import loadproof
from tools.metropole.road_surfaces import apply_to_html
from tools.v69_streaming import patch_streaming
from tools.v69_terrain import patch_terrain_runtime, patch_consumers
from tools.v69_depth import patch_depth
from tools.v69_heights import load_height_matches

ROOT=Path(__file__).resolve().parent
OUTPUT=ROOT/'SOMA_MASSILIA_URBAIN_v0_69.html'
WORLD=ROOT/'data/v69/world'


def json_script(identifier,value):
    data=json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False).replace('<','\\u003c')
    return f'\n<script type="application/json" id="{identifier}">{data}</script>\n'


def js_script(name):
    text=(ROOT/'src/v69'/f'{name}.js').read_text(encoding='utf-8')
    if '</script' in text.lower():
        raise ValueError(f'Fermeture de script dans {name}.')
    return f'\n<script id="soma-v69-{name}">\n{text}\n</script>\n'


def patch_buildings(script):
    signature='function addRealBuilding(z,g,rings,p,sourceId,index,partIndex=0){'
    wrapper='''function addRealBuilding(z,g,rings,p,sourceId,index,partIndex=0){
 const overlay=window.__SOMA_PARTS69__,meshes=overlay?.meshes(z,p,sourceId,partIndex);
 if(meshes===null||meshes===undefined)return addRealBuildingBase69(z,g,rings,p,sourceId,index,partIndex);
 let built=false;
 for(const mesh of meshes)if(overlay.withMesh(z,p,partIndex,mesh,()=>addRealBuildingBase69(z,g,rings,p,sourceId,index,partIndex)))built=true;
 return built;
}
function addRealBuildingBase69(z,g,rings,p,sourceId,index,partIndex=0){'''
    script=replace_once(script,signature,wrapper,'assemblage des parties avant fondations')
    script=replace_once(script,'function geometryMesh53(z,rings,p,partIndex=0){',
        'function geometryMesh53(z,rings,p,partIndex=0){\n const derived=window.__SOMA_PARTS69__?.geometryMesh(z,p,partIndex);if(derived)return derived;',
        'maillage résiduel partagé')
    for name,signature in [('route','function addArbitraryRoad(z,g,a,b,p,sourceId,index){'),
                           ('rail','function addRail(z,g,a,b,p,sourceId,index){')]:
        script=replace_once(script,signature,signature+'if(window.__SOMA_ROADS69__?.unsupported(p))return false;',f'ouvrage {name} non modélisé')
    return script


def patch_renderer(script):
    script=replace_once(script,'const dim = dimension(p, C50.buildingHeight(p, sourceId), heightReference(p, sourceId, z));',
        'const sourceReference = heightReference(p, sourceId, z);\n    const dim = dimension(p, C50.buildingHeight(p, sourceId), sourceReference);',
        'référence mesurée à l’égout conservée')
    script=replace_once(script,'const plan = K.roofPlan(p, dim, reference(p, sourceId, z.v50Record));',
        'const plan = {...K.roofPlan(p, dim, reference(p, sourceId, z.v50Record)),...window.__SOMA_HEIGHTS69__?.roofPolicy(p,sourceReference)};',
        'toiture inconnue au-dessus de la hauteur à l’égout')
    script=replace_once(script,"if (String(p['roof:shape'] || '').toLowerCase() !== 'skillion') return null;",
        "if (!['skillion','pyramidal','dome'].includes(String(p['roof:shape'] || '').toLowerCase())) return null;",'références de toit')
    script=replace_once(script,"String(feature.properties?.['roof:shape'] || '').toLowerCase() === 'skillion'",
        "['skillion','pyramidal','dome'].includes(String(feature.properties?.['roof:shape'] || '').toLowerCase())",'index limité aux toits utiles')
    script=replace_once(script,"geometrySource: z.v50Record.v53Validated ? 'declared-source' : 'legacy',",
        "geometrySource: mesh.v69Derived ? 'derived-building-parts' : z.v50Record.v53Validated ? 'declared-source' : 'legacy',",'provenance du maillage dérivé')
    return replace_once(script,'lightingSource: material.lightingSource}});',
        "lightingSource: material.lightingSource},v69:{roofGeometrySource:plan.geometrySource||null,accuracy:plan.accuracy||null,modelTessellationErrorM:plan.errorBoundM??null,heightKind:sourceReference?.heightKind||null,roofSurveyed:sourceReference?.roofSurveyed??null,heightReferenceProofSHA256:sourceReference?.proofSHA256||null,derivedBuildingParts:!!mesh.v69Derived,partParent:window.__SOMA_PARTS69__?.anchorId(z,p,sourceId)!==sourceId?window.__SOMA_PARTS69__.anchorId(z,p,sourceId):null}});",'précision paramétrique déclarée')


def patch_terrain(script):
    script=patch_terrain_runtime(script)
    old='anchors.get(String(id))'
    if script.count(old)!=2:
        raise ValueError('Les deux ancrages des parties ont changé.')
    return script.replace(old,'anchors.get(String(window.__SOMA_PARTS69__?.anchorId(z,p,id)??id))')


def patch_sight(script):
    script=replace_once(script,'sha=T().pack?.sha256;',
        'sha=T().v69?.revision??T().pack?.sha256;','révision des index de visée')
    script=replace_once(script,"for(const m of p['soma:mesh53']||[]){if(m.areaM2<.1)continue;",
        "for(const m of window.__SOMA_PARTS69__?.sourceMeshes(z,p,id,p['soma:mesh53']||[])||p['soma:mesh53']||[]){if(m.areaM2<.1)continue;",'mêmes volumes visibles et occultants')
    return replace_once(script,'K.terrain(T().grid,global,direction,range)',
        '(T().v69?T().v69.traceTerrain(global,direction,range,K):K.terrain(T().grid,global,direction,range))','visée à travers les tuiles terrain')


def build():
    html=build_v68().decode('utf-8')
    source_pack,_=embedded(html,'soma-v53-embedded-pack')
    proof=loadproof(ROOT/'data/v69/building-parts.json',records=source_pack['records'],source_sha=source_pack['sourceReceipt']['sha256'])
    heights=load_height_matches(ROOT/'data/v69/building-height-matches.json.gz',records=source_pack['records'],source_sha=source_pack['sourceReceipt']['sha256'])
    del source_pack
    road_patch=json.loads((ROOT/'data/v69/road-surfaces.json').read_text(encoding='utf-8'))
    html=apply_to_html(html,road_patch)
    html=patch_streaming(html)
    html=rewrite_script(html,'soma-v50-playable-truth-cells',patch_buildings)
    html=rewrite_script(html,'soma-v68-building-renderer',patch_renderer)
    html=rewrite_script(html,'soma-v56-terrain-runtime',patch_terrain)
    html=patch_consumers(html)
    html=rewrite_script(html,'soma-v61-sight-runtime',patch_sight)
    html=rewrite_script(html,'soma-v59-fidelity-runtime',lambda script:replace_once(script,
        'function heightReference(p,id,z){const v=DATA.buildings[id];return cell(z)&&K.canApplyHeight(p,v)?v:null;}',
        'function heightReference(p,id,z){const measured=window.__SOMA_HEIGHTS69__?.reference(p,id,z);if(measured)return measured;const v=DATA.buildings[id];return cell(z)&&K.canApplyHeight(p,v)?v:null;}',
        'hauteurs IGN liées aux emprises sources'))
    html=rewrite_script(html,'soma-v53-core',lambda script:replace_once(script,
        "function driveable(p){return window.__SOMA_V57_CORE__.sourceRoadAccess(p);}",
        "function driveable(p){return !window.__SOMA_ROADS69__?.unsupported(p)&&window.__SOMA_V57_CORE__.sourceRoadAccess(p);}",
        'raccords routiers cohérents avec les ouvrages exclus'))
    data=json_script('soma-v69-building-parts',proof)+json_script('soma-v69-building-height-matches',heights)
    modules=data+js_script('roof-core')+js_script('building-parts')+js_script('height-references')+js_script('road-fidelity')+js_script('streaming-core')
    html=replace_once(html,'<script id="soma-v68-building-renderer">',modules+'<script id="soma-v68-building-renderer">','modules géographiques 0.69')
    territory=json.loads((ROOT/'data/v69/territory.json').read_text(encoding='utf-8'))
    audit=json.loads((ROOT/'data/v69/FIDELITY_REPORT.json').read_text(encoding='utf-8'))
    # Only the compact correction report is put into the developer diagnostics.
    road_report={key:value for key,value in road_patch.items() if key not in ('cells','roadMetadata')}
    footer=json_script('soma-v69-territory',territory)+json_script('soma-v69-fidelity-audit',audit)+json_script('soma-v69-road-report',road_report)+js_script('world-runtime')
    html=replace_once(html,'</body>',footer+'\n</body>','entrée métropolitaine 0.69')
    html=patch_depth(html)
    return html.encode('utf-8')


def world_inputs(data):
    return {'htmlSHA256':digest(data),'terrainFileSHA256':digest((ROOT/'data/v58/terrain.ign.json').read_bytes()),
            'territoryFileSHA256':digest((ROOT/'data/v69/territory.json').read_bytes()),
            'bootstrapSourceSHA256':digest((ROOT/'tools/metropole/bootstrap.py').read_bytes()),
            'terrainTilerSourceSHA256':digest((ROOT/'tools/v69/terrain_tiles.py').read_bytes())}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify',action='store_true')
    args=parser.parse_args()
    try:
        data=build()
        if args.verify:
            if not OUTPUT.is_file() or OUTPUT.read_bytes()!=data:
                raise ValueError('Le HTML 0.69 ne correspond pas aux sources actuelles.')
            manifest=verify_world(WORLD,world_inputs(data))
        else:
            OUTPUT.write_bytes(data)
            manifest=prepare_world(data.decode('utf-8'),WORLD,ROOT/'data/v58/terrain.ign.json',ROOT/'data/v69/territory.json')
            report={'version':'0.69.0','output':OUTPUT.name,'bytes':len(data),'sha256':digest(data),
                    'worldManifestSHA256':digest((WORLD/'manifest.json').read_bytes()),
                    'coverage':manifest['coverage'],'completeMetropole':False,'certifiedOneToOne':False,
                    'inputs':world_inputs(data)}
            (ROOT/'data/v69/BUILD_REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'version':'0.69.0','bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),
                          'preparedCells':len(manifest['tiles']),'completeMetropole':False,'verified':args.verify},ensure_ascii=False))
    except (OSError,ValueError,KeyError,TypeError) as error:
        parser.exit(1,f'Reconstruction 0.69 impossible : {error}\n')


if __name__=='__main__':
    main()
