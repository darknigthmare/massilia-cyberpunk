#!/usr/bin/env python3
"""Assemble checked vector/terrain/surface/navigation assets for runtime paging.

Assembly prepares files only. It neither activates a game catalogue nor proves
metropolitan coverage or a certified architectural reproduction.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import re
import sys
import tempfile

GAME=Path(__file__).resolve().parents[2]
if str(GAME) not in sys.path:sys.path.insert(0,str(GAME))
from tools.v69.terrain_tiles import validate_grid
from tools.metropole.bootstrap import load_territory_reference

SCHEMA='soma-metropole/world-manifest/1'
ORIGIN=[892951.6480966414,6247274.566415883]
LAYERS=('vector','terrain','surfaces','navigation')
HASH=re.compile(r'^[a-f0-9]{64}$')
TILE_ID=re.compile(r'^V52-MC-(?:[1-5][1-5]|[EW][0-9]{2,4}-[NS][0-9]{2,4})$')
PATH=re.compile(r'^[A-Za-z0-9][A-Za-z0-9._/-]*$')
MAX_MANIFEST=128*1024*1024
MAX_COMPRESSED=16*1024*1024
MAX_DECODED=64*1024*1024
FORBIDDEN={'__proto__','prototype','constructor'}


class AssemblyFailure(ValueError):
    pass


def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')


def digest(raw):return hashlib.sha256(raw).hexdigest()


def finite(value):return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


def object_pairs(pairs):
    result={}
    for key,value in pairs:
        if key in FORBIDDEN or key in result:raise AssemblyFailure('Forbidden or duplicate JSON key.')
        result[key]=value
    return result


def parse(raw):
    value=json.loads(raw,object_pairs_hook=object_pairs)
    if not isinstance(value,dict):raise AssemblyFailure('A JSON object is required.')
    return value


def read_manifest(path):
    path=Path(path).resolve()
    if not path.is_file() or path.stat().st_size>MAX_MANIFEST:raise AssemblyFailure('Manifest missing or beyond its byte budget.')
    raw=path.read_bytes()
    return parse(raw),digest(raw),path.parent


def safe_asset_path(base,relative):
    if (not isinstance(relative,str) or not relative or len(relative)>1000 or not PATH.fullmatch(relative)
            or any(part in ('','.','..') for part in relative.split('/'))):
        raise AssemblyFailure('Unsafe source asset path.')
    base=Path(base).resolve();path=(base/relative).resolve()
    if not path.is_relative_to(base) or not path.is_file():raise AssemblyFailure('Source asset missing or escaping its source directory.')
    return path


def read_asset(base,descriptor):
    if not isinstance(descriptor,dict) or descriptor.get('encoding')!='gzip-json':raise AssemblyFailure('A gzip-json asset descriptor is required.')
    size=descriptor.get('bytes')
    if not isinstance(size,int) or isinstance(size,bool) or not 0<size<=MAX_COMPRESSED or not HASH.fullmatch(descriptor.get('sha256','')):
        raise AssemblyFailure('Invalid source asset byte budget or SHA256.')
    path=safe_asset_path(base,descriptor.get('path'))
    if path.stat().st_size!=size:raise AssemblyFailure('Source asset size differs from its manifest.')
    raw=path.read_bytes()
    if digest(raw)!=descriptor['sha256']:raise AssemblyFailure('Source asset SHA256 differs from its manifest.')
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
            decoded=stream.read(MAX_DECODED+1)
    except (OSError,EOFError) as error:raise AssemblyFailure('Invalid gzip asset.') from error
    if len(decoded)>MAX_DECODED:raise AssemblyFailure('Source asset exceeds its decoded-byte budget.')
    if 'decodedBytes' in descriptor and descriptor['decodedBytes']!=len(decoded):raise AssemblyFailure('Source decoded-byte declaration differs from its data.')
    return raw,parse(decoded),len(decoded)


def grid_for_id(cell_id):
    if not isinstance(cell_id,str) or not TILE_ID.fullmatch(cell_id):raise AssemblyFailure('Invalid cell identity.')
    legacy=re.fullmatch(r'V52-MC-([1-5])([1-5])',cell_id)
    if legacy:return int(legacy[2])-3,int(legacy[1])-3
    match=re.fullmatch(r'V52-MC-([EW])(\d{2,4})-([NS])(\d{2,4})',cell_id)
    return int(match[2])*(-1 if match[1]=='W' else 1),int(match[4])*(-1 if match[3]=='N' else 1)


def bounds_equal(a,b):
    return (isinstance(a,list) and isinstance(b,list) and len(a)==len(b)==4 and all(finite(v) for v in a+b)
            and a[0]<a[2] and a[1]<a[3] and all(abs(x-y)<=1e-6 for x,y in zip(a,b)))


def validate_grid_entry(tile):
    if not isinstance(tile,dict):raise AssemblyFailure('Cell descriptor must be an object.')
    x,y=grid_for_id(tile.get('cellId'))
    if tile.get('gridX')!=x or tile.get('gridY')!=y or isinstance(tile.get('gridX'),bool) or isinstance(tile.get('gridY'),bool):
        raise AssemblyFailure('Cell identity differs from its grid coordinates.')
    e,n=ORIGIN[0]+x*250,ORIGIN[1]-y*250
    if not bounds_equal(tile.get('boundsL93'),[e-125,n-125,e+125,n+125]):raise AssemblyFailure('Cell is shifted from the historical metric grid.')


def validate_frame(manifest,expected_schema,*,grid=False):
    if manifest.get('schema')!=expected_schema or manifest.get('crs')!='EPSG:2154' or manifest.get('units')!='m':
        raise AssemblyFailure('Layer schema/CRS/units differ from the expected source format.')
    if grid and (manifest.get('origin')!=ORIGIN or manifest.get('cellSize')!=250):raise AssemblyFailure('Layer uses a foreign grid origin or cell size.')
    tiles=manifest.get('tiles')
    if not isinstance(tiles,list) or len(tiles)>100000:raise AssemblyFailure('Layer tile index exceeds its budget.')
    seen=set()
    for tile in tiles:
        cell_id=tile.get('cellId') if isinstance(tile,dict) else None
        grid_for_id(cell_id)
        if cell_id in seen:raise AssemblyFailure('Duplicate layer cell identity.')
        seen.add(cell_id)
    return {tile['cellId']:tile for tile in tiles}


def validate_vector(record,tile,pbf_sha):
    if (record.get('schema')!='soma-massilia/geodata-cell/4' or record.get('cellId')!=tile['cellId']
            or not bounds_equal(record.get('boundsL93'),tile['boundsL93']) or record.get('grid')!={'x':tile['gridX'],'y':tile['gridY']}
            or record.get('sourceReceipt',{}).get('sha256')!=pbf_sha
            or any(record.get(key) for key in ('testOnly','v53Synthetic','v50Synthetic'))):
        raise AssemblyFailure('Vector record is synthetic or tied to a foreign cell/source.')
    collection=record.get('featureCollection')
    if not isinstance(collection,dict) or collection.get('type')!='FeatureCollection' or not isinstance(collection.get('features'),list) or len(collection['features'])>12000:
        raise AssemblyFailure('Invalid vector feature collection or feature budget.')
    content=record.get('contentSHA256','')
    if not HASH.fullmatch(content) or digest(canonical(collection))!=content:raise AssemblyFailure('Vector contentSHA256 differs from its features.')
    return content


def validate_terrain(pack,tile,descriptor):
    source=pack.get('source')
    receipt=source.get('receipt',{}) if isinstance(source,dict) else {}
    if (pack.get('testOnly') or not isinstance(pack.get('source'),dict)
            or not isinstance(receipt,dict) or source.get('testOnly') or receipt.get('testOnly')
            or re.search(r'fixture|synthetic',str(pack['source'].get('truth','')),re.I)):
        raise AssemblyFailure('A synthetic terrain fixture is not a geographic terrain layer.')
    try:grid=validate_grid(pack,tile['boundsL93'])
    except ValueError as error:raise AssemblyFailure('Terrain schema/grid/datum validation failed: '+str(error)) from error
    if isinstance(pack.get('stats'),dict) and any(pack['stats'].get(key)!=grid.stats[key] for key in ('nodes','valid','noData')):
        raise AssemblyFailure('Terrain statistics contradict the actual source mask.')
    complete=grid.stats['noData']==0
    if 'gridSHA256' in descriptor and descriptor['gridSHA256']!=grid.sha256:raise AssemblyFailure('Terrain grid hash differs from its asset descriptor.')
    if 'complete' in descriptor and descriptor['complete'] is not complete:raise AssemblyFailure('Terrain NoData contradicts its completeness declaration.')
    if 'noDataNodes' in descriptor and descriptor['noDataNodes']!=grid.stats['noData']:raise AssemblyFailure('Terrain NoData count differs from its bytes.')
    return {'gridSHA256':grid.sha256,'stepM':grid.step,'complete':complete,
            'noDataNodes':grid.stats['noData'],'validNodes':grid.stats['valid'],'nodes':grid.stats['nodes']}


def validate_surface(pack,tile,content,pbf_sha,source_pack_sha,native_sha):
    if (pack.get('schema')!='soma-metropole/surface-cell/1' or pack.get('cellId')!=tile['cellId']
            or not bounds_equal(pack.get('boundsL93'),tile['boundsL93']) or pack.get('contentSHA256')!=content
            or pack.get('sourcePbfSHA256')!=pbf_sha or pack.get('sourceVectorManifestSHA256')!=source_pack_sha
            or pack.get('nativeTopologySHA256')!=native_sha or pack.get('cell',{}).get('contentSHA256')!=content
            or pack.get('cell',{}).get('sourceSHA256')!=pbf_sha):
        raise AssemblyFailure('Surface layer is tied to another cell/vector/source edition.')
    for layer in ('road','unsealed','paved','foot','walk','mark'):
        triangles=pack.get('cell',{}).get('surfaces',{}).get(layer,[])
        if (not isinstance(triangles,list) or len(triangles)>400000 or any(
                not isinstance(triangle,list) or len(triangle)!=3 or any(
                    not isinstance(point,list) or len(point)!=2 or not all(finite(v) and abs(v)<=125.001 for v in point)
                    for point in triangle) for triangle in triangles)):
            raise AssemblyFailure('Surface mesh is outside its metric cell or geometry budget.')


def validate_navigation(graph,tile,content,pbf_sha,source_pack_sha,cell_hashes):
    if (graph.get('schema')!='soma/navigation-source/1' or graph.get('sourcePbfSHA256')!=pbf_sha
            or graph.get('sourcePackSHA256')!=source_pack_sha or graph.get('cellHashes',{}).get(tile['cellId'])!=content):
        raise AssemblyFailure('Navigation layer is tied to another source/vector/cell edition.')
    status=graph.get('sourceStatus',{})
    if not isinstance(status,dict) or any(status.get(key) is not True for key in ('nodeTagsComplete','nativeNodeIdentity','vectorConstrained')):
        raise AssemblyFailure('Native navigation source/barrier completeness is not established.')
    if not isinstance(graph.get('cellHashes'),dict) or any(cell_hashes.get(key)!=value for key,value in graph['cellHashes'].items()):
        raise AssemblyFailure('Navigation references an unavailable or foreign vector cell hash.')
    nodes,edges,turns,ways=graph.get('nodes'),graph.get('edges'),graph.get('turns'),graph.get('ways')
    if (not isinstance(nodes,list) or len(nodes)>250000 or not isinstance(edges,list) or len(edges)>500000
            or not isinstance(turns,list) or len(turns)>50000 or not isinstance(ways,dict)):
        raise AssemblyFailure('Navigation graph exceeds its type/geometry budget.')
    seen=set()
    for node in nodes:
        if not isinstance(node,list) or len(node)!=3 or not isinstance(node[0],str) or node[0] in seen or not all(finite(v) for v in node[1:]):
            raise AssemblyFailure('Invalid or duplicate navigation node.')
        seen.add(node[0])
    for edge in edges:
        if (not isinstance(edge,list) or len(edge)<7 or not all(isinstance(v,int) and not isinstance(v,bool) for v in edge[:2])
                or min(edge[:2])<0 or max(edge[:2])>=len(nodes) or edge[0]==edge[1] or edge[2] not in ways
                or not finite(edge[3]) or edge[3]<=0 or not isinstance(edge[4],int) or isinstance(edge[4],bool) or not 1<=edge[4]<=15
                or not isinstance(edge[5],int) or isinstance(edge[5],bool) or edge[5] not in (0,1) or not isinstance(edge[6],list) or not edge[6]
                or any(cell not in graph['cellHashes'] for cell in edge[6])):
            raise AssemblyFailure('Invalid navigation source segment.')
    for rule in turns:
        if (not isinstance(rule,dict) or rule.get('via') not in seen or rule.get('from') not in ways or rule.get('to') not in ways
                or not isinstance(rule.get('kind'),str) or not rule['kind'].startswith(('no_','only_'))):
            raise AssemblyFailure('Invalid navigation turn restriction.')


def copy_asset(stage,cell_id,layer,descriptor,raw,decoded_bytes,**extra):
    relative=f'tiles/{cell_id}.{layer}.json.gz'
    destination=stage/relative
    if not destination.resolve().is_relative_to(stage.resolve()):raise AssemblyFailure('Output asset escapes its staged world.')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open('xb') as stream:stream.write(raw)
    return {**descriptor,'path':relative,'decodedBytes':decoded_bytes,**extra}


def read_sidecar(path,layer,source_sha,pbf_sha,native_sha,vector_ids,*,include_terrain_only=False):
    if path is None:return None
    manifest,manifest_sha,base=read_manifest(path)
    schemas={'terrain':'soma-metropole/terrain-tiles/1','surfaces':'soma-metropole/surface-tiles/1','navigation':'soma-metropole/navigation-tiles/1'}
    entries=validate_frame(manifest,schemas[layer],grid=layer=='terrain')
    if not set(entries).issubset(vector_ids) and not (layer=='terrain' and include_terrain_only):
        raise AssemblyFailure('Sidecar references cells outside the vector edition.')
    if layer=='terrain':
        if manifest.get('verticalDatum')!='NGF-IGN69':raise AssemblyFailure('Terrain sidecar vertical datum is unsupported.')
    elif (manifest.get('sourceVectorManifest',{}).get('sha256')!=source_sha or manifest.get('sourcePbfSHA256')!=pbf_sha
          or manifest.get('nativeTopologySHA256')!=native_sha):
        raise AssemblyFailure('Foreign sidecar source/vector/topology edition.')
    return {'manifest':manifest,'sha256':manifest_sha,'base':base,'entries':entries}


def terrain_only_source(sidecar,boundary_sha):
    """Admit explicitly administrative DEM targets, without vector identities."""
    if sidecar is None:raise AssemblyFailure('Terrain-only preparation requires a terrain manifest.')
    manifest=sidecar['manifest'];definition=manifest.get('targetDefinition',{})
    if (not isinstance(boundary_sha,str) or not HASH.fullmatch(boundary_sha)
            or not isinstance(definition,dict) or definition.get('schema')!='soma-metropole/terrain-target-cells/1'
            or definition.get('boundarySHA256')!=boundary_sha):
        raise AssemblyFailure('Terrain target boundary differs from the verified administrative boundary.')
    if manifest.get('terrainOnly') is not True or manifest.get('vectorCoverageClaimed') is not False:
        raise AssemblyFailure('Terrain targets must explicitly avoid a vector coverage claim.')
    source=manifest.get('source');receipt=source.get('receipt') if isinstance(source,dict) else None
    if (not isinstance(source,dict) or not isinstance(receipt,dict) or source.get('testOnly') or receipt.get('testOnly')
            or not isinstance(source.get('method'),str) or not source['method'].strip()
            or any(source.get(key)!=value for key,value in (('crs','EPSG:2154'),('units','m'),('verticalDatum','NGF-IGN69')))
            or not all(isinstance(receipt.get(key),str) and receipt[key].strip() for key in ('provider','product','license','attribution'))
            or re.search(r'fixture|synthetic',str(source.get('truth',''))+' '+str(receipt.get('truth','')),re.I)):
        raise AssemblyFailure('Terrain-only source provenance, datum or metric units are incomplete.')
    for key,value in (('crs','EPSG:2154'),('units','m'),('verticalDatum','NGF-IGN69')):
        if key in receipt and receipt[key]!=value:raise AssemblyFailure('Terrain source receipt contradicts its declared datum or units.')
    files=source.get('files');known_files={}
    if files is not None:
        if not isinstance(files,list) or not files or len(files)>10000:raise AssemblyFailure('Terrain source raster fingerprints are missing or beyond budget.')
        for item in files:
            if (not isinstance(item,dict) or not isinstance(item.get('name'),str) or not re.fullmatch(r'[A-Za-z0-9_.-]+',item['name'])
                    or not isinstance(item.get('sha256'),str) or not HASH.fullmatch(item['sha256'])
                    or not isinstance(item.get('bytes'),int) or isinstance(item.get('bytes'),bool) or item['bytes']<=0
                    or item['name'] in known_files):
                raise AssemblyFailure('Invalid or duplicate terrain source raster fingerprint.')
            known_files[item['name']]={key:item[key] for key in ('name','bytes','sha256')}
    elif not isinstance(source.get('gridSHA256'),str) or not HASH.fullmatch(source['gridSHA256']):
        raise AssemblyFailure('Terrain source grid/raster fingerprint is missing.')
    positions=set()
    for tile in sidecar['entries'].values():
        validate_grid_entry(tile)
        position=(tile['gridX'],tile['gridY'])
        if position in positions:raise AssemblyFailure('Multiple terrain cells occupy the same historical grid position.')
        positions.add(position)
    return {'source':source,'receipt':receipt,'files':known_files}


def validate_terrain_source(pack,proof):
    source=pack.get('source',{});expected=proof['source']
    if (source.get('method')!=expected['method'] or source.get('receipt')!=proof['receipt']
            or any(source.get(key)!=expected[key] for key in ('crs','units','verticalDatum'))):
        raise AssemblyFailure('Terrain asset is tied to another source receipt or derivation.')
    if proof['files']:
        files=source.get('files')
        if (not isinstance(files,list) or not files or any(not isinstance(item,dict)
                or proof['files'].get(item.get('name'))!={key:item.get(key) for key in ('name','bytes','sha256')} for item in files)):
            raise AssemblyFailure('Terrain asset references an unavailable or foreign source raster.')
    elif source.get('sourceGridSHA256')!=expected['gridSHA256']:
        raise AssemblyFailure('Terrain asset references another source grid.')


def assemble_world(vectors,output,*,terrain=None,surfaces=None,navigation=None,territory=None,include_terrain_only=False):
    if not isinstance(include_terrain_only,bool):raise AssemblyFailure('include_terrain_only must be an explicit boolean.')
    output=Path(output).absolute()
    if output.exists() or output.is_symlink():raise AssemblyFailure('Output already exists; preserve it and choose a new world output directory.')
    source,source_sha,source_base=read_manifest(vectors)
    vector_entries=validate_frame(source,'soma-metropole/vector-tiles/1',grid=True)
    pbf=source.get('source')
    if (not isinstance(pbf,dict) or not HASH.fullmatch(pbf.get('sha256',''))
            or not all(isinstance(pbf.get(key),str) and pbf[key].strip() for key in ('license','attribution'))):
        raise AssemblyFailure('Vector source receipt is incomplete.')
    native_sha=source.get('nativeTopology',{}).get('sha256')
    if not HASH.fullmatch(native_sha or ''):raise AssemblyFailure('Vector native topology fingerprint is missing.')
    positions=set()
    for tile in vector_entries.values():
        validate_grid_entry(tile)
        key=(tile['gridX'],tile['gridY'])
        if key in positions:raise AssemblyFailure('Multiple cells occupy the same historical grid position.')
        positions.add(key)
    territory_path=Path(territory) if territory is not None else GAME/'data/v69/territory.json'
    # Retain strict JSON/budget validation, then verify the acquired boundary
    # through its exact source bytes and pinned validity receipt (standard library).
    read_manifest(territory_path)
    try:target,territory_sha,boundary_sha=load_territory_reference(territory_path)
    except (ValueError,OSError,KeyError,TypeError) as error:
        raise AssemblyFailure('Administrative boundary validation failed: '+str(error)) from error
    sidecars={name:read_sidecar(path,name,source_sha,pbf['sha256'],native_sha,set(vector_entries),include_terrain_only=include_terrain_only)
              for name,path in [('terrain',terrain),('surfaces',surfaces),('navigation',navigation)]}
    terrain_proof=terrain_only_source(sidecars['terrain'],boundary_sha) if include_terrain_only else None
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.metropole-assemble-',dir=output.parent) as temporary:
        stage=Path(temporary)/'world';stage.mkdir()
        cells=[];hashes={}
        for cell_id,tile in sorted(vector_entries.items()):
            raw,record,nbytes=read_asset(source_base,tile.get('vector'))
            content=validate_vector(record,tile,pbf['sha256']);hashes[cell_id]=content
            cell={key:tile[key] for key in ('cellId','gridX','gridY','boundsL93')}
            cell.update(contentSHA256=content,vector=copy_asset(stage,cell_id,'vector',tile['vector'],raw,nbytes),
                        terrain=None,surfaces=None,navigation=None)
            cells.append(cell)
        if include_terrain_only:
            for cell_id,tile in sorted(sidecars['terrain']['entries'].items()):
                if cell_id in vector_entries or tile.get('terrain') is None:continue
                cell={key:tile[key] for key in ('cellId','gridX','gridY','boundsL93')}
                cell.update(terrainOnly=True,contentSHA256=None,vector=None,terrain=None,surfaces=None,navigation=None)
                cells.append(cell)
        no_data_cells=0
        for cell in cells:
            for layer,sidecar in sidecars.items():
                if sidecar is None:continue
                link=sidecar['entries'].get(cell['cellId'])
                descriptor=link.get('surface' if layer=='surfaces' else layer) if link else None
                if descriptor is None:continue
                if not bounds_equal(link.get('boundsL93'),cell['boundsL93']):raise AssemblyFailure('Sidecar cell bounds differ from its vector tile.')
                if layer in ('surfaces','navigation') and link.get('cellHash')!=cell['contentSHA256']:
                    raise AssemblyFailure('Sidecar cell content hash differs from its vector source.')
                raw,value,nbytes=read_asset(sidecar['base'],descriptor)
                extra={}
                if layer=='terrain':
                    extra=validate_terrain(value,cell,descriptor)
                    if terrain_proof:validate_terrain_source(value,terrain_proof)
                    no_data_cells+=not extra['complete']
                elif layer=='surfaces':
                    validate_surface(value,cell,cell['contentSHA256'],pbf['sha256'],source_sha,native_sha)
                    if value.get('dimensionCoreSHA256')!=sidecar['manifest'].get('dimensionCore',{}).get('sha256'):
                        raise AssemblyFailure('Surface dimension core hash differs from its sidecar.')
                else:validate_navigation(value,cell,cell['contentSHA256'],pbf['sha256'],source_sha,hashes)
                cell[layer]=copy_asset(stage,cell['cellId'],layer,descriptor,raw,nbytes,**extra)
            cell['preparation']={'missingLayers':[layer for layer in LAYERS if cell[layer] is None],
                                 'terrainComplete':bool(cell['terrain'] and cell['terrain']['complete']),
                                 'activationPerformed':False}
            if cell.get('terrainOnly'):
                cell['preparation']['allLayersAvailable']=False
        manifest={'schema':SCHEMA,'version':'0.69.0','edition':'imported-source-preparation-0.69',
                  'crs':'EPSG:2154','units':'m','origin':ORIGIN,'cellSize':250,
                  'source':pbf,'sourcePackSHA256':source_sha,'nativeTopologySHA256':native_sha,
                  'target':{'id':target['id'],'name':target.get('name'),'communeCount':92,
                            'territorySHA256':territory_sha,'boundarySHA256':boundary_sha},
                  'coverageExplicitPartial':True,'completeMetropole':False,'certifiedOneToOne':False,
                  'preparationOnly':True,'activationPerformed':False,'tiles':cells,
                  'sourceManifests':{'vectors':source_sha,**{k:v['sha256'] if v else None for k,v in sidecars.items()}},
                  'coverage':{'vectorCells':len(vector_entries),'areaOfGridCellsKm2':len(cells)*.0625,
                              'allLayersAvailableCells':sum(all(cell[layer] is not None for layer in LAYERS) for cell in cells),
                              'terrainCompleteCells':sum(bool(cell['terrain'] and cell['terrain']['complete']) for cell in cells),
                              'terrainNoDataCells':no_data_cells,'administrativeCoverageRatio':None},
                  'buildInputs':{'assemblerSourceSHA256':digest(Path(__file__).read_bytes()),'territorySHA256':territory_sha},
                  'meaning':'Checked preparation assets only. Missing layers stay null; NoData stays invalid. Catalogue migration, physical access and complete metropolitan fidelity are not activated or certified.'}
        if include_terrain_only:
            manifest['includeTerrainOnly']=True
            manifest['coverage'].update(terrainOnlyCells=sum(cell.get('terrainOnly') is True for cell in cells),
                                        terrainTargetCells=len(sidecars['terrain']['entries']),
                                        terrainTargetsWithoutAsset=sum(tile.get('terrain') is None for tile in sidecars['terrain']['entries'].values()))
        manifest['manifestContentSHA256']=digest(canonical(manifest))
        (stage/'manifest.json').write_bytes(canonical(manifest)+b'\n')
        stage.rename(output)
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vectors',type=Path,required=True)
    parser.add_argument('--terrain',type=Path)
    parser.add_argument('--surfaces',type=Path)
    parser.add_argument('--navigation',type=Path)
    parser.add_argument('--territory',type=Path,default=GAME/'data/v69/territory.json')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--include-terrain-only',action='store_true',help='prepare real DEM cells outside the vector edition, without fabricating vectors or navigation')
    args=parser.parse_args()
    try:
        result=assemble_world(args.vectors,args.output,terrain=args.terrain,surfaces=args.surfaces,navigation=args.navigation,territory=args.territory,
                              include_terrain_only=args.include_terrain_only)
        print(json.dumps({'status':'prepared','manifest':str(args.output/'manifest.json'),'coverage':result['coverage'],
                          'activationPerformed':False,'completeMetropole':False},ensure_ascii=False))
    except (OSError,ValueError,KeyError,TypeError) as error:
        parser.exit(1,f'World assembly refused: {error}\n')


if __name__=='__main__':main()
