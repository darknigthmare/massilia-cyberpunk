#!/usr/bin/env python3
"""Attach immutable source-bound part metadata to an unserved prepared world.

This stdlib step changes only the prepared manifest and its new metadata asset.
It neither activates legacy gameplay nor derives additional source geometry.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile

if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))

from tools.metropole import attach_height_references as checked
from tools.metropole import building_parts
from tools.metropole.bootstrap import ORIGIN,SCHEMA,TILE_ID,canonical,digest

MAX_PROOF=128*1024*1024
IDENTITY=re.compile(r'osm/(?:way|relation)/[1-9]\d*')


def identity(value):
    return isinstance(value,str) and IDENTITY.fullmatch(value) is not None


def safe_target(root,relative,*,existing=False):
    if (not isinstance(relative,str) or len(relative)>1000 or
            not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]*',relative) or
            any(part in ('','.','..') for part in relative.split('/'))):
        raise ValueError('Unsafe world metadata path.')
    path=root/relative
    cursor=root
    for part in Path(relative).parts:
        cursor=cursor/part
        if cursor.is_symlink():raise ValueError('World metadata target must not use symlinks.')
    if not path.resolve().is_relative_to(root) or existing and not path.is_file():
        raise ValueError('World metadata target escapes or is missing from the prepared world.')
    return path


def validate_world(world):
    if (world.get('schema')!=SCHEMA or world.get('crs')!='EPSG:2154' or world.get('units')!='m' or
            world.get('origin')!=ORIGIN or type(world.get('cellSize')) is not int or world['cellSize']!=250 or
            world.get('coverageExplicitPartial') is not True or world.get('completeMetropole') is not False or
            world.get('preparationOnly') is not True or world.get('activationPerformed') is not False or
            world.get('manifestContentSHA256')!=digest(canonical({k:v for k,v in world.items() if k!='manifestContentSHA256'})) or
            not isinstance(world.get('source'),dict) or not checked.valid_hash(world['source'].get('sha256')) or
            any(not isinstance(world['source'].get(key),str) or not world['source'][key].strip() for key in ('license','attribution')) or
            not isinstance(world.get('target'),dict) or world['target'].get('id')!='200054807' or
            world['target'].get('boundarySHA256') is not None and not checked.valid_hash(world['target']['boundarySHA256']) or
            not checked.valid_hash(world.get('sourcePackSHA256')) or not isinstance(world.get('sourceManifests'),dict) or
            world['sourceManifests'].get('vectors')!=world['sourcePackSHA256']):
        raise ValueError('A sealed, inactive source-bound prepared world is required.')
    index=checked.indexed(world.get('tiles'));positions=set()
    for tile in index.values():
        position=checked.metric_tile(tile)
        if position in positions:raise ValueError('Duplicate prepared-world grid position.')
        positions.add(position)
        if tile.get('terrainOnly') is True:
            if (tile.get('vector') is not None or tile.get('contentSHA256') is not None or not isinstance(tile.get('terrain'),dict) or
                    tile.get('surfaces') is not None or tile.get('navigation') is not None):
                raise ValueError('A terrain-only world cell has contradictory vector metadata.')
        elif not checked.valid_hash(tile.get('contentSHA256')) or not isinstance(tile.get('vector'),dict):
            raise ValueError('Prepared vector cell content binding is missing.')
    return index


def proof_bindings(proof,world,index):
    selection=proof.get('selectionProvenance')
    if (not isinstance(selection,dict) or selection.get('vectorManifestSHA256')!=world['sourcePackSHA256'] or
            not isinstance(selection.get('sourceCellHashes'),dict)):
        raise ValueError('Building proof selection belongs to another vector manifest.')
    parents=proof.get('parents');links=proof.get('partParents')
    if not isinstance(parents,dict) or not isinstance(links,dict):
        raise ValueError('Building proof parent indices must be objects.')
    required={};associated={}

    def cells(bindings,canonical_id=None,geometry_sha=None,part=False):
        if not isinstance(bindings,dict) or (canonical_id is not None and not bindings) or len(bindings)>100000:
            raise ValueError('Nonempty bounded real-cell bindings are required.')
        for cell,content in bindings.items():
            tile=index.get(cell)
            if (not isinstance(cell,str) or not TILE_ID.fullmatch(cell) or not checked.valid_hash(content) or
                    tile is None or tile.get('terrainOnly') is True or tile.get('vector') is None or
                    tile.get('contentSHA256')!=content or selection['sourceCellHashes'].get(cell)!=content):
                raise ValueError('Building proof uses a missing, terrain-only or stale real source cell.')
            if canonical_id is not None:
                expected=required.setdefault(cell,{})
                binding=(geometry_sha,part)
                if canonical_id in expected and expected[canonical_id]!=binding:
                    raise ValueError('Contradictory source building geometry or role.')
                expected[canonical_id]=binding

    # Includes cells read for withheld components; the proof cannot drift to a
    # different edition merely because those components produced no parent.
    cells(selection['sourceCellHashes'])
    for parent_id,parent in parents.items():
        if (not identity(parent_id) or not isinstance(parent,dict) or parent.get('parentId')!=parent_id or
                not checked.valid_hash(parent.get('parentGeometrySHA256')) or parent.get('sourceSHA256')!=world['source']['sha256'] or
                not isinstance(parent.get('parts'),list) or not parent['parts'] or len(parent['parts'])>100000):
            raise ValueError('Invalid canonical parent geometry binding.')
        cells(parent.get('cells'),parent_id,parent['parentGeometrySHA256'])
        if not parent.get('suppressParent') and (
                parent.get('status')!='derived-partial' or parent.get('remainingUnresolved') is not True or
                parent.get('residualPolicy')!='unresolved-footprint-only' or
                parent.get('residualVolumetric') is not False or parent.get('residualCollision') is not False):
            raise ValueError('Partial parent residuals must remain unresolved, non-volumetric footprints.')
        part_ids=[]
        for part in parent['parts']:
            if (not isinstance(part,dict) or not identity(part.get('id')) or part['id']==parent_id or
                    not checked.valid_hash(part.get('geometrySHA256')) or part['id'] in associated):
                raise ValueError('Duplicate, cyclic or invalid canonical building part.')
            part_id=part['id'];associated[part_id]=parent_id;part_ids.append(part_id)
            cells(part.get('cells'),part_id,part['geometrySHA256'],True)
            link=links.get(part_id)
            if (not isinstance(link,dict) or link.get('parentId')!=parent_id or
                    link.get('parentGeometrySHA256')!=parent['parentGeometrySHA256'] or
                    link.get('geometrySHA256')!=part['geometrySHA256'] or link.get('cells')!=part['cells'] or
                    link.get('association')!=part.get('association') or
                    link.get('sourceSHA256')!=world['source']['sha256']):
                raise ValueError('Building part has a missing or contradictory shared-parent link.')
        declared=parent.get('partIds');ground=parent.get('groundPartIds')
        if (not isinstance(declared,list) or len(declared)!=len(part_ids) or set(declared)!=set(part_ids) or
                not isinstance(ground,list) or len(ground)!=len(set(ground)) or not set(ground)<=set(part_ids)):
            raise ValueError('Parent part indices differ from their actual bindings.')
    if set(links)!=set(associated) or set(parents)&set(associated):
        raise ValueError('Shared-parent index is incomplete, extra or cyclic.')
    return required


def verify_real_cells(root,world,index,required):
    observed={}
    for cell,expected in sorted(required.items()):
        tile=index[cell]
        safe_target(root,tile['vector'].get('path'),existing=True)
        record=checked.read_asset(root,tile['vector'],checked.MAX_VECTOR,observed=observed)
        collection=record.get('featureCollection')
        if (record.get('schema')!='soma-massilia/geodata-cell/4' or record.get('cellId')!=cell or
                any(record.get(k) for k in ('v53Synthetic','v50Synthetic','testOnly')) or
                not isinstance(record.get('sourceReceipt'),dict) or record['sourceReceipt'].get('sha256')!=world['source']['sha256'] or
                record.get('boundsL93')!=tile['boundsL93'] or record.get('grid')!={'x':tile['gridX'],'y':tile['gridY']} or
                not isinstance(collection,dict) or collection.get('type')!='FeatureCollection' or
                not isinstance(collection.get('features'),list) or len(collection['features'])>12000 or
                record.get('contentSHA256')!=tile['contentSHA256'] or digest(canonical(collection))!=tile['contentSHA256']):
            raise ValueError('Actual world vector asset contradicts its source cell binding.')
        found=set()
        for feature in collection['features']:
            if not isinstance(feature,dict) or not isinstance(feature.get('properties'),dict):
                raise ValueError('Invalid real source feature.')
            p=feature['properties'];canonical_id=p.get('canonical_id') or feature.get('id')
            if canonical_id not in expected:continue
            geometry_sha,part=expected[canonical_id]
            active=lambda value:value is not None and str(value).strip().lower() not in building_parts.FALSE
            if (canonical_id in found or p.get('soma:layer')!='buildings' or
                    p.get('soma:geometry_sha256')!=geometry_sha or active(p.get('building:part'))!=part or
                    not part and (not active(p.get('building')) or str(p.get('building')).strip().lower()=='roof') or
                    not isinstance(p.get('soma:mesh53'),list) or not p['soma:mesh53']):
                raise ValueError('Actual source parent/part geometry or role differs from the proof.')
            found.add(canonical_id)
        if found!=set(expected):raise ValueError('A claimed parent/part is absent from its actual source cell.')
    return observed


def attach(world_dir,parts_path):
    tools={Path(__file__).resolve():None,Path(checked.__file__).resolve():None,Path(building_parts.__file__).resolve():None}
    tools={path:checked.file_hash(path) for path in tools}
    original_root=Path(world_dir).absolute();root=original_root.resolve()
    if original_root.is_symlink() or not root.is_dir():raise ValueError('A real prepared-world directory is required.')
    root_identity=(root.stat().st_dev,root.stat().st_ino)
    manifest_path=safe_target(root,'manifest.json',existing=True)
    world,world_sha=checked.read_json(manifest_path);index=validate_world(world)
    source_path=Path(parts_path).absolute();source_resolved=source_path.resolve()
    proof,raw_sha=checked.read_json(source_path,MAX_PROOF)
    with source_path.open('rb') as stream:raw=stream.read(MAX_PROOF+1)
    if len(raw)>MAX_PROOF or digest(raw)!=raw_sha:raise ValueError('Building proof changed while reading its exact bytes.')
    threshold=proof.get('fullSuppressionThreshold')
    if (proof.get('certified') is not False or isinstance(threshold,bool) or not isinstance(threshold,(int,float)) or
            not math.isfinite(threshold) or not building_parts.MIN_COVERAGE<=threshold<=1):
        raise ValueError('An uncertified proof with the strict suppression threshold is required.')
    try:building_parts.loadproof(proof,source_sha=world['source']['sha256'])
    except (AttributeError,TypeError,KeyError) as error:
        raise ValueError('Malformed building-parts proof.') from error
    required=proof_bindings(proof,world,index)
    observed=verify_real_cells(root,world,index,required)
    relative=f'metadata/building-parts.{raw_sha[:12]}.json'
    target=safe_target(root,relative)
    descriptor={'path':relative,'encoding':'json','bytes':len(raw),'sha256':raw_sha,
                'proofSHA256':proof['proofSHA256'],'sourcePbfSHA256':world['source']['sha256']}

    def stable():
        if (original_root.resolve()!=root or (root.stat().st_dev,root.stat().st_ino)!=root_identity or
                source_path.resolve()!=source_resolved or source_path.is_symlink() and not source_resolved.is_file()):
            raise ValueError('Source or prepared-world path drifted during attachment.')
        safe_target(root,'manifest.json',existing=True);safe_target(root,relative)
        for path,sha in [(manifest_path,world_sha),(source_path,raw_sha),*tools.items(),*observed.items()]:
            if checked.file_hash(path)!=sha:raise ValueError('World, proof, vector asset or tool changed during attachment.')

    existing=world.get('buildingParts')
    if existing is not None:
        if existing!=descriptor or world['sourceManifests'].get('buildingParts')!=raw_sha:
            raise ValueError('The world already has a different building-parts attachment.')
        if not target.is_file() or target.stat().st_size!=len(raw) or checked.file_hash(target)!=raw_sha:
            raise ValueError('Attached building-parts metadata was altered or removed.')
        stable();return world
    stable()
    metadata=root/'metadata'
    if metadata.exists() and not metadata.is_dir():raise ValueError('World metadata directory is not a directory.')
    metadata.mkdir(exist_ok=True)
    safe_target(root,relative)
    created=False;temporary=None;manifest_temporary=None;published=False
    try:
        if target.exists():
            if not target.is_file() or target.stat().st_size!=len(raw) or checked.file_hash(target)!=raw_sha:
                raise ValueError('Content-addressed metadata path already contains different bytes.')
        else:
            with tempfile.NamedTemporaryFile(dir=metadata,prefix='.building-parts-',delete=False) as stream:
                temporary=Path(stream.name);stream.write(raw);stream.flush();os.fsync(stream.fileno())
            safe_target(root,relative)
            os.link(temporary,target);created=True;temporary.unlink();temporary=None
        result=copy.deepcopy(world);result['buildingParts']=descriptor
        result['sourceManifests']['buildingParts']=raw_sha
        result['buildingPartsAttachment']={'toolSHA256':tools[Path(__file__).resolve()],
            'validationHelpersSHA256':{path.name:sha for path,sha in tools.items() if path!=Path(__file__).resolve()},
            'sourceWorldManifestSHA256':world_sha}
        result.pop('manifestContentSHA256',None);result['manifestContentSHA256']=digest(canonical(result))
        with tempfile.NamedTemporaryFile(dir=root,prefix='.parts-manifest-',delete=False) as stream:
            manifest_temporary=Path(stream.name);stream.write(canonical(result)+b'\n');stream.flush();os.fsync(stream.fileno())
        stable()
        if checked.file_hash(target)!=raw_sha:raise ValueError('Immutable metadata changed before world publication.')
        manifest_temporary.replace(manifest_path);manifest_temporary=None;published=True
        return result
    finally:
        for path in (temporary,manifest_temporary):
            if path is not None and path.resolve().is_relative_to(root):path.unlink(missing_ok=True)
        if created and not published and not target.is_symlink() and target.resolve().is_relative_to(root):
            target.unlink(missing_ok=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world',type=Path,required=True);parser.add_argument('--parts',type=Path,required=True)
    args=parser.parse_args()
    try:
        result=attach(args.world,args.parts)
        print(json.dumps(result['buildingParts']))
    except (OSError,ValueError,KeyError,TypeError) as error:parser.exit(1,f'Building-parts attachment refused: {error}\n')


if __name__=='__main__':main()
