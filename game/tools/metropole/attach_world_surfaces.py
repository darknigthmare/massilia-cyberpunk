#!/usr/bin/env python3
"""Attach checked surfaces to an unserved clone without rereading its DEM/vectors.

The caller supplies an already verified, preparation-only world. New surface
assets and the manifest are published atomically; immutable existing layers,
building-parts metadata and activation state are preserved.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))

from tools.metropole import assemble_world as A
from tools.metropole import attach_world_parts as P
from tools.metropole import attach_height_references as checked


def height_header(manifest):
    value=manifest.get('heightReferences','explicitly-absent')
    if value=='explicitly-absent':return value
    if (not isinstance(value,dict) or value.get('status')!='source-bound-eaves-matches' or
            value.get('heightKind')!='eaves' or value.get('roofSurveyed') is not False or
            not checked.valid_hash(value.get('catalogueSealSHA256')) or
            not checked.valid_hash(value.get('heightSidecarManifestSHA256')) or
            type(value.get('matchedFragments')) is not int or value['matchedFragments']<0):
        raise ValueError('Surface height-reference header is contradictory or unbound.')
    return copy.deepcopy(value)


def descriptor(value):
    if (not isinstance(value,dict) or value.get('encoding')!='gzip-json' or not checked.valid_hash(value.get('sha256')) or
            type(value.get('bytes')) is not int or not 0<value['bytes']<=A.MAX_COMPRESSED or
            'decodedBytes' in value and (type(value['decodedBytes']) is not int or not 0<value['decodedBytes']<=A.MAX_DECODED)):
        raise ValueError('Invalid bounded surface asset descriptor.')
    return value


def counters(world):
    tiles=world['tiles']
    values={'vectorCells':sum(tile.get('vector') is not None for tile in tiles),
        'surfaceCells':sum(tile.get('surfaces') is not None for tile in tiles),
        'allLayersAvailableCells':sum(all(tile.get(layer) is not None for layer in A.LAYERS) for tile in tiles),
        'terrainCompleteCells':sum(bool(tile.get('terrain') and tile['terrain'].get('complete') is True) for tile in tiles),
        'terrainNoDataCells':sum(bool(tile.get('terrain') and tile['terrain'].get('complete') is False) for tile in tiles)}
    if 'terrainOnlyCells' in world.get('coverage',{}) or any(tile.get('terrainOnly') is True for tile in tiles):
        values['terrainOnlyCells']=sum(tile.get('terrainOnly') is True for tile in tiles)
    return values


def preparation(tile):
    value={**tile.get('preparation',{}),'missingLayers':[layer for layer in A.LAYERS if tile.get(layer) is None],
        'terrainComplete':bool(tile.get('terrain') and tile['terrain'].get('complete') is True),'activationPerformed':False}
    if tile.get('terrainOnly') is True or 'allLayersAvailable' in value:
        value['allLayersAvailable']=tile.get('terrainOnly') is not True and all(tile.get(layer) is not None for layer in A.LAYERS)
    return value


def attach(world_dir,surface_manifest,progress=None):
    if progress is not None and not callable(progress):raise ValueError('Progress callback must be callable.')
    tools={Path(__file__).resolve(),Path(A.__file__).resolve(),Path(P.__file__).resolve(),Path(checked.__file__).resolve()}
    tools={path:checked.file_hash(path) for path in tools}
    original_root=Path(world_dir).absolute();root=original_root.resolve()
    if original_root.is_symlink() or not root.is_dir():raise ValueError('A real unserved prepared-world clone is required.')
    root_identity=(root.stat().st_dev,root.stat().st_ino)
    manifest_path=P.safe_target(root,'manifest.json',existing=True)
    world,world_sha=checked.read_json(manifest_path);index=P.validate_world(world)
    native=world.get('nativeTopologySHA256')
    if not checked.valid_hash(native) or not isinstance(world.get('coverage'),dict):
        raise ValueError('Verified native topology and preparation coverage metadata are required.')
    source_path=Path(surface_manifest).absolute();source_resolved=source_path.resolve()
    surface,source_sha=checked.read_json(source_path)
    entries=A.validate_frame(surface,'soma-metropole/surface-tiles/1')
    vectors={cell:tile for cell,tile in index.items() if tile.get('vector') is not None}
    if (set(entries)!=set(vectors) or not isinstance(surface.get('sourceVectorManifest'),dict) or
            surface['sourceVectorManifest'].get('sha256')!=world['sourcePackSHA256'] or
            surface.get('sourcePbfSHA256')!=world['source']['sha256'] or surface.get('nativeTopologySHA256')!=native or
            not isinstance(surface.get('dimensionCore'),dict) or not checked.valid_hash(surface['dimensionCore'].get('sha256'))):
        raise ValueError('Surface index/source/vector/native-topology edition differs from the prepared world.')
    references=height_header(surface)
    relative=f'layers/surfaces.{source_sha[:12]}'
    target=P.safe_target(root,relative)
    observed={}

    def stable():
        if original_root.resolve()!=root or (root.stat().st_dev,root.stat().st_ino)!=root_identity or source_path.resolve()!=source_resolved:
            raise ValueError('World or surface source path drifted during attachment.')
        P.safe_target(root,'manifest.json',existing=True);P.safe_target(root,relative)
        for path,sha in [(manifest_path,world_sha),(source_path,source_sha),*tools.items(),*observed.items()]:
            if checked.file_hash(path)!=sha:raise ValueError('World, surface source, asset or tool changed during attachment.')

    previous=world['sourceManifests'].get('surfaces')
    if previous is not None:
        if previous!=source_sha or world.get('surfaceAttachment',{}).get('surfaceManifestSHA256')!=source_sha:
            raise ValueError('The prepared world already contains a different surface edition.')
        for cell,tile in sorted(vectors.items()):
            expected=descriptor(entries[cell].get('surface'));actual=descriptor(tile.get('surfaces'))
            expected_path=f'{relative}/tiles/{cell}.surfaces.json.gz'
            if (actual.get('path')!=expected_path or any(actual.get(key)!=expected.get(key) for key in ('bytes','sha256','encoding')) or
                    not A.bounds_equal(entries[cell].get('boundsL93'),tile['boundsL93']) or entries[cell].get('cellHash')!=tile['contentSHA256']):
                raise ValueError('Attached surface metadata differs from its pinned source edition.')
            path=P.safe_target(root,expected_path,existing=True)
            if path.stat().st_size!=actual['bytes'] or checked.file_hash(path)!=actual['sha256']:
                raise ValueError('Attached surface asset was altered or removed.')
        if (world.get('heightReferences')!=references or any(world['coverage'].get(k)!=v for k,v in counters(world).items()) or
                any(tile.get('preparation')!=preparation(tile) for tile in world['tiles'])):
            raise ValueError('Attached surface preparation counters or height provenance have drifted.')
        stable();return world
    if any(tile.get('surfaces') is not None for tile in world['tiles']):
        raise ValueError('A base clone with no previous surface assets is required.')
    if target.exists():raise ValueError('Surface output directory already exists; preserve its immutable edition.')
    layers=root/'layers'
    if layers.exists() and not layers.is_dir():raise ValueError('Surface layers target is not a directory.')
    layers.mkdir(exist_ok=True)
    published=False;target_identity=None;manifest_temporary=None
    try:
        with tempfile.TemporaryDirectory(prefix='.surface-attach-',dir=root) as temporary:
            stage=Path(temporary)/'surfaces';stage.mkdir()
            for number,(cell,tile) in enumerate(sorted(vectors.items()),1):
                link=entries[cell]
                if not A.bounds_equal(link.get('boundsL93'),tile['boundsL93']) or link.get('cellHash')!=tile['contentSHA256']:
                    raise ValueError('Surface cell bounds/content differ from the verified vector metadata.')
                desc=descriptor(link.get('surface'))
                source_asset=P.safe_target(source_resolved.parent,desc.get('path'),existing=True)
                raw,value,nbytes=A.read_asset(source_resolved.parent,desc)
                observed[source_asset]=desc['sha256']
                A.validate_surface(value,tile,tile['contentSHA256'],world['source']['sha256'],world['sourcePackSHA256'],native)
                if value.get('dimensionCoreSHA256')!=surface['dimensionCore']['sha256']:
                    raise ValueError('Surface dimension core differs from its source manifest.')
                copied=A.copy_asset(stage,cell,'surfaces',desc,raw,nbytes)
                copied['path']=relative+'/'+copied['path'];tile['surfaces']=copied
                if progress and number%256==0:progress({'cells':number,'total':len(vectors)})
            for tile in world['tiles']:tile['preparation']=preparation(tile)
            world['coverage'].update(counters(world));world['sourceManifests']['surfaces']=source_sha
            world['heightReferences']=references
            world['surfaceAttachment']={'surfaceManifestSHA256':source_sha,'sourceWorldManifestSHA256':world_sha,
                'toolSHA256':tools[Path(__file__).resolve()],'assemblerSourceSHA256':tools[Path(A.__file__).resolve()],
                'validationHelpersSHA256':{path.name:sha for path,sha in tools.items() if path not in (Path(__file__).resolve(),Path(A.__file__).resolve())}}
            world.pop('manifestContentSHA256',None);world['manifestContentSHA256']=A.digest(A.canonical(world))
            stable()
            if target.exists():raise ValueError('Surface target appeared during preparation; preserve it.')
            stage.rename(target);target_identity=(target.stat().st_dev,target.stat().st_ino)
            with tempfile.NamedTemporaryFile(dir=root,prefix='.surfaces-manifest-',delete=False) as stream:
                manifest_temporary=Path(stream.name);stream.write(A.canonical(world)+b'\n');stream.flush();os.fsync(stream.fileno())
            stable()
            manifest_temporary.replace(manifest_path);manifest_temporary=None;published=True
        return world
    finally:
        if manifest_temporary is not None and manifest_temporary.resolve().is_relative_to(root):manifest_temporary.unlink(missing_ok=True)
        if (not published and target_identity is not None and not target.is_symlink() and target.is_dir() and
                target.resolve().is_relative_to(root) and (target.stat().st_dev,target.stat().st_ino)==target_identity):
            shutil.rmtree(target)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world',type=Path,required=True);parser.add_argument('--surfaces',type=Path,required=True)
    parser.add_argument('--progress',action='store_true');args=parser.parse_args()
    try:
        notify=(lambda item:print(json.dumps(item),file=sys.stderr,flush=True)) if args.progress else None
        result=attach(args.world,args.surfaces,progress=notify)
        print(json.dumps({'surfaceCells':result['coverage']['surfaceCells'],'surfaceManifestSHA256':result['sourceManifests']['surfaces']}))
    except (OSError,ValueError,KeyError,TypeError,EOFError) as error:
        parser.exit(1,f'Surface attachment refused: {error}\n')


if __name__=='__main__':main()
