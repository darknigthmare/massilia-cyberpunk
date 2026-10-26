#!/usr/bin/env python3
"""Attach verified eave references to road surface assets without changing roads.

This optional stdlib preparation step binds canonical height matches to real
vector cells. It does not change the PBF, terrain, routing or campaign state.
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

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.metropole.bootstrap import ORIGIN, TILE_ID, canonical, digest, asset
from tools.metropole.building_heights import HASH, _osm_priority, binding_key
from tools.v69_heights import _parse

MAX_MANIFEST = 128 * 1024 * 1024
MAX_VECTOR = 16 * 1024 * 1024
MAX_SURFACE = 64 * 1024 * 1024


def valid_hash(value):
    return isinstance(value,str) and HASH.fullmatch(value) is not None


def file_hash(path):
    checksum=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            checksum.update(chunk)
    return checksum.hexdigest()


def read_json(path, maximum=MAX_MANIFEST):
    path=Path(path)
    if path.stat().st_size>maximum:
        raise ValueError('Source JSON exceeds its byte budget.')
    with path.open('rb') as stream:
        raw=stream.read(maximum+1)
    if len(raw)>maximum:
        raise ValueError('Source JSON exceeds its byte budget.')
    value=_parse(raw)
    if not isinstance(value,dict):
        raise ValueError('A source manifest must be a JSON object.')
    return value,digest(raw)


def read_asset(directory, descriptor, maximum, *, observed=None, implicit_gzip=False):
    if not isinstance(descriptor,dict):
        raise ValueError('A checked asset descriptor is required.')
    relative=descriptor.get('path')
    if (not isinstance(relative,str) or len(relative)>1000 or
            not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]*',relative) or
            any(part in ('','.','..') for part in relative.split('/'))):
        raise ValueError('A relative asset path is required.')
    if descriptor.get('encoding')!='gzip-json' and not (implicit_gzip and 'encoding' not in descriptor):
        raise ValueError('A gzip-json asset is required.')
    size=descriptor.get('bytes')
    if type(size) is not int or not 0<size<=maximum or not valid_hash(descriptor.get('sha256')):
        raise ValueError('Asset size or SHA256 descriptor is invalid.')
    path=(Path(directory)/relative).resolve()
    if not path.is_relative_to(Path(directory).resolve()):
        raise ValueError('Asset path escapes its source directory.')
    if path.stat().st_size!=size:
        raise ValueError('Asset size differs from its descriptor.')
    with path.open('rb') as stream:
        raw=stream.read(maximum+1)
    if len(raw)!=size:
        raise ValueError('Asset size changed while reading.')
    if digest(raw)!=descriptor.get('sha256'):
        raise ValueError('Asset SHA256 differs from its descriptor.')
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
        decoded=stream.read(maximum+1)
    if len(decoded)>maximum or ('decodedBytes' in descriptor and (
            type(descriptor['decodedBytes']) is not int or descriptor['decodedBytes']!=len(decoded))):
        raise ValueError('Decoded asset size exceeds or differs from its descriptor.')
    if observed is not None:
        if path in observed and observed[path]!=descriptor['sha256']:
            raise ValueError('One source asset has contradictory SHA256 descriptors.')
        observed[path]=descriptor['sha256']
    value=_parse(decoded)
    if not isinstance(value,dict):
        raise ValueError('An asset must contain a JSON object.')
    return value


def indexed(rows):
    result={}
    if not isinstance(rows,list) or len(rows)>100000:
        raise ValueError('Invalid or excessive source cell index.')
    for row in rows:
        if not isinstance(row,dict):
            raise ValueError('A source cell index entry must be an object.')
        identity=row.get('cellId')
        if not isinstance(identity,str) or not TILE_ID.fullmatch(identity) or identity in result:
            raise ValueError('Invalid or duplicate source cell identity.')
        result[identity]=row
    return result


def metric_tile(tile):
    identity=tile['cellId']
    legacy=re.fullmatch(r'V52-MC-([1-5])([1-5])',identity)
    modern=re.fullmatch(r'V52-MC-([EW])(\d{2,4})-([NS])(\d{2,4})',identity)
    x,y=((int(legacy[2])-3,int(legacy[1])-3) if legacy else
         ((-1 if modern[1]=='W' else 1)*int(modern[2]),(-1 if modern[3]=='N' else 1)*int(modern[4])))
    if type(tile.get('gridX')) is not int or type(tile.get('gridY')) is not int or (tile['gridX'],tile['gridY'])!=(x,y):
        raise ValueError('Vector grid indices disagree with their cell identity.')
    e,n=ORIGIN[0]+x*250,ORIGIN[1]-y*250
    expected=[e-125,n-125,e+125,n+125]
    bounds=tile.get('boundsL93')
    if (not isinstance(bounds,list) or len(bounds)!=4 or any(
            isinstance(a,bool) or not isinstance(a,(int,float)) or not math.isfinite(a) or abs(a-b)>1e-6
            for a,b in zip(bounds,expected))):
        raise ValueError('Vector bounds disagree with the historical metric grid.')
    return x,y


def merge_cell(record,surface,height,*,vector_sha,catalogue_sha,vector_manifest_sha):
    if (not isinstance(record,dict) or record.get('schema')!='soma-massilia/geodata-cell/4' or
            any(record.get(key) for key in ('v53Synthetic','v50Synthetic','testOnly')) or
            not isinstance(record.get('cellId'),str) or not TILE_ID.fullmatch(record['cellId']) or
            not isinstance(record.get('sourceReceipt'),dict) or not valid_hash(record['sourceReceipt'].get('sha256')) or
            not valid_hash(record.get('contentSHA256')) or not isinstance(record.get('featureCollection'),dict) or
            record['featureCollection'].get('type')!='FeatureCollection' or
            not isinstance(record['featureCollection'].get('features'),list) or len(record['featureCollection']['features'])>12000 or
            not all(valid_hash(value) for value in (vector_sha,catalogue_sha,vector_manifest_sha))):
        raise ValueError('A bounded real vector cell and exact source hashes are required.')
    identity=record['cellId'];source=record['sourceReceipt']['sha256'];content=record['contentSHA256']
    if content!=digest(canonical(record['featureCollection'])):
        raise ValueError('Vector content hash differs from its actual features.')
    if (not isinstance(surface,dict) or not isinstance(surface.get('cell'),dict) or
            not isinstance(surface.get('buildings'),dict) or
            surface.get('schema')!='soma-metropole/surface-cell/1' or surface.get('cellId')!=identity or
            surface.get('boundsL93')!=record.get('boundsL93') or
            surface.get('sourcePbfSHA256')!=source or surface.get('contentSHA256')!=content or
            surface.get('cell',{}).get('sourceSHA256')!=source or surface['cell'].get('contentSHA256')!=content or
            surface.get('sourceVectorManifestSHA256')!=vector_manifest_sha):
        raise ValueError('Surface is bound to another vector cell or edition.')
    if (not isinstance(height,dict) or height.get('schema')!='soma-metropole/building-height-cell/1' or height.get('cellId')!=identity or
            height.get('sourceSHA256')!=source or height.get('contentSHA256')!=content or
            height.get('vectorSHA256')!=vector_sha or height.get('catalogueSealSHA256')!=catalogue_sha or
            height.get('currentVectorManifestSHA256')!=vector_manifest_sha or height.get('heightKind')!='eaves' or
            height.get('proofSHA256')!=digest(canonical({k:v for k,v in height.items() if k!='proofSHA256'}))):
        raise ValueError('Height sidecar proof differs from its actual vector cell.')
    features={};identities=set()
    for feature in record['featureCollection']['features']:
        if not isinstance(feature,dict) or feature.get('type')!='Feature' or not isinstance(feature.get('properties'),dict):
            raise ValueError('A real vector feature is required.')
        p=feature.get('properties',{})
        if p.get('soma:layer')=='buildings':
            canonical_id=p.get('canonical_id') or feature.get('id')
            key=binding_key(canonical_id,p.get('soma:geometry_sha256'),source)
            if key in features or canonical_id in identities:
                raise ValueError('Duplicate building identity in vector cell.')
            features[key]=p;identities.add(canonical_id)
    additions={}
    rows=height.get('matches')
    if not isinstance(rows,dict):
        raise ValueError('Height sidecar matches must be an object.')
    for key,row in rows.items():
        p=features.get(key)
        if (not isinstance(row,dict) or p is None or _osm_priority(p) or key!=binding_key(row.get('canonicalId'),row.get('geometrySHA256'),source) or
                row.get('sourceSHA256')!=source or row.get('heightKind')!='eaves' or
                row.get('decision')!='accepted-conservative-match' or row.get('heightSource')!='ign-bdtopo-height' or
                row.get('method')!='footprint-iou-unique-reciprocal' or
                not isinstance(row.get('ignId'),str) or not row['ignId'].strip()):
            raise ValueError('Height reference violates source geometry or OSM priority.')
        for field,low,high in [('height',.05,1000),('groundAltitude',-1000,9000),
                               ('iou',.9,1),('margin',.15,1),('reciprocalMargin',.15,1)]:
            value=row.get(field)
            if (isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value) or
                    not low<=value<=high or field=='height' and value<=.05):
                raise ValueError('Height reference has invalid measurement or matching evidence.')
        addition={**row,'cellContentSHA256':content,'heightKind':'eaves','runtimeCellBindingsPresent':True,
            'roofSurveyed':False,'accuracy':'source-match-not-certified','proofSHA256':height['proofSHA256']}
        if row['canonicalId'] in surface['buildings'] and surface['buildings'][row['canonicalId']]!=addition:
            raise ValueError('A height reference would overwrite a different existing building reference.')
        additions[row['canonicalId']]=addition
    # No surface triangle, road dimension or area is rewritten here.
    return {**surface,'buildings':{**surface.get('buildings',{}),**additions},
            'heightReferences':{'status':'source-bound-eaves-matches','count':len(additions),
                'catalogueSealSHA256':catalogue_sha,'cellProofSHA256':height['proofSHA256'],
                'heightKind':'eaves','roofSurveyed':False}},len(additions)


def prepare(vectors,surfaces,heights,output,progress=None):
    vectors,surfaces,heights,output=map(Path,(vectors,surfaces,heights,output))
    if output.exists():
        raise ValueError('Output exists; preserve the previous edition.')
    tool_path=Path(__file__).resolve();tool_sha=file_hash(tool_path)
    v,vsha=read_json(vectors);s,ssha=read_json(surfaces);h,hsha=read_json(heights)
    if (v.get('schema')!='soma-metropole/vector-tiles/1' or v.get('crs')!='EPSG:2154' or v.get('units')!='m' or
            v.get('origin')!=ORIGIN or type(v.get('cellSize')) is not int or v['cellSize']!=250 or
            not isinstance(v.get('source'),dict) or not valid_hash(v['source'].get('sha256')) or
            s.get('schema')!='soma-metropole/surface-tiles/1' or not isinstance(s.get('sourceVectorManifest'),dict) or
            s['sourceVectorManifest'].get('sha256')!=vsha or
            s.get('crs')!='EPSG:2154' or s.get('units')!='m' or
            s.get('sourcePbfSHA256')!=v.get('source',{}).get('sha256') or
            h.get('schema')!='soma-metropole/building-height-sidecars/1' or h.get('currentVectorManifestSHA256')!=vsha or
            h.get('sourceSHA256')!=v['source']['sha256'] or not valid_hash(h.get('catalogueSealSHA256')) or
            not valid_hash(h.get('sourceMatchingManifestSHA256')) or
            h.get('manifestSHA256')!=digest(canonical({k:x for k,x in h.items() if k!='manifestSHA256'}))):
        raise ValueError('Source manifests belong to inconsistent vector/height editions.')
    vi,si,hi=map(indexed,(v.get('tiles'),s.get('tiles'),h.get('tiles')))
    if set(vi)!=set(si) or set(vi)!=set(hi):
        raise ValueError('Height and surface indices must cover the same real vector cells.')
    positions=set()
    for tile in vi.values():
        position=metric_tile(tile)
        if position in positions:
            raise ValueError('Duplicate vector grid position.')
        positions.add(position)
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.eave-surfaces-',dir=output.parent) as temporary:
        stage=Path(temporary)/'surfaces';stage.mkdir();tiles=[];fragments=0;observed={}
        for number,(identity,tile) in enumerate(sorted(vi.items()),1):
            record=read_asset(vectors.parent,tile['vector'],MAX_VECTOR,observed=observed)
            surface=read_asset(surfaces.parent,si[identity]['surface'],MAX_SURFACE,observed=observed)
            height=read_asset(heights.parent,hi[identity],MAX_VECTOR,observed=observed,implicit_gzip=True)
            merged,count=merge_cell(record,surface,height,vector_sha=tile['vector']['sha256'],
                catalogue_sha=h['catalogueSealSHA256'],vector_manifest_sha=vsha)
            if (record.get('cellId')!=identity or record.get('sourceReceipt',{}).get('sha256')!=v['source']['sha256'] or
                    record.get('boundsL93')!=tile['boundsL93'] or record.get('grid')!={'x':tile['gridX'],'y':tile['gridY']} or
                    si[identity].get('boundsL93')!=tile['boundsL93'] or si[identity].get('cellHash')!=record.get('contentSHA256') or
                    hi[identity].get('contentSHA256')!=record.get('contentSHA256') or
                    type(hi[identity].get('matchedFragments')) is not int or
                    not isinstance(height.get('matches'),dict) or hi[identity]['matchedFragments']!=len(height['matches'])):
                raise ValueError('Source indices disagree with the actual vector cell or height matches.')
            if height.get('sourceMatchingManifestSHA256')!=h['sourceMatchingManifestSHA256']:
                raise ValueError('Height sidecar refers to another canonical matching edition.')
            descriptor=asset(stage,f'{identity}.json.gz',merged)
            descriptor['decodedBytes']=len(canonical(merged))
            tiles.append({**si[identity],'surface':descriptor});fragments+=count
            if progress and number%256==0:progress({'cells':number,'total':len(vi),'matchedFragments':fragments})
        for path,expected in [(vectors,vsha),(surfaces,ssha),(heights,hsha),(tool_path,tool_sha),*observed.items()]:
            if file_hash(path)!=expected:
                raise ValueError('Source manifest, asset or tool changed during height attachment.')
        result={**s,'tiles':tiles,'heightReferences':{'status':'source-bound-eaves-matches',
            'catalogueSealSHA256':h['catalogueSealSHA256'],'heightSidecarManifestSHA256':hsha,
            'matchedFragments':fragments,'heightKind':'eaves','roofSurveyed':False},
            'heightAttachment':{'surfaceManifestSHA256':ssha,'vectorManifestSHA256':vsha,
                'heightSidecarManifestSHA256':hsha,'toolSHA256':tool_sha}}
        (stage/'surface-manifest.json').write_bytes(canonical(result)+b'\n')
        if output.exists():
            raise ValueError('Output appeared during preparation; preserve the existing edition.')
        stage.rename(output)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('vectors','surfaces','heights','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    try:
        result=prepare(args.vectors,args.surfaces,args.heights,args.output,
            progress=lambda item:print(json.dumps(item),flush=True))
        print(json.dumps({'cells':len(result['tiles']),**result['heightReferences']}))
    except (OSError,ValueError,KeyError,TypeError,EOFError) as error:
        parser.exit(1,f'Height attachment refused: {error}\n')


if __name__=='__main__':main()
