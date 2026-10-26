#!/usr/bin/env python3
"""Deterministic, bounded and atomic offline transport of prepared world caches.

Version 1 stores a checked header, the exact sealed world manifest, and its
unique assets in sorted path order. Assets are already compressed; this format
never decompresses them. A footer seals every preceding byte. No archive entry
can create a link, and existing export/import destinations are never replaced.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import ctypes
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import sys
import tempfile

MAGIC=b'SOMA-METROPOLE-WORLD-BUNDLE\x00\x01\n'
FOOTER=b'SOMA-WORLD-END\x00\x01\n'
SCHEMA='soma-metropole/world-bundle/1'
RECEIPT='soma-metropole/world-bundle-receipt/1'
WORLD='soma-metropole/world-manifest/1'
ORIGIN=[892951.6480966414,6247274.566415883]
HASH=re.compile(r'[a-f0-9]{64}')
CELL=re.compile(r'V52-MC-(?:[1-5][1-5]|[EW][0-9]{2,4}-[NS][0-9]{2,4})')
LAYERS=('vector','terrain','surfaces','navigation')
CHUNK=1024*1024
RESERVE=64*1024*1024
WINDOWS_RESERVED={'CON','PRN','AUX','NUL'}|{f'{p}{i}' for p in ('COM','LPT') for i in range(1,10)}


class BundleError(ValueError):
    pass


@dataclass(frozen=True)
class Limits:
    max_manifest_bytes:int=128*1024*1024
    max_asset_bytes:int=16*1024*1024
    max_decoded_bytes:int=64*1024*1024
    max_assets:int=400001
    max_total_bytes:int=8*1024**3
    max_header_bytes:int=64*1024

    def validate(self):
        if any(type(n) is not int or n<=0 for n in vars(self).values()):
            raise BundleError('All byte/count budgets must be positive integers.')
        return self


@dataclass(frozen=True,slots=True)
class Asset:
    path:str
    size:int
    sha256:str
    encoding:str
    decoded:int|None


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')


def digest(raw):return hashlib.sha256(raw).hexdigest()
def valid_hash(value):return isinstance(value,str) and HASH.fullmatch(value) is not None
def absolute(path):return Path(os.path.abspath(os.fspath(path)))


def pairs(rows):
    result={}
    for key,value in rows:
        if key in result or key in {'__proto__','constructor','prototype'}:raise BundleError('Duplicate or forbidden JSON key.')
        result[key]=value
    return result


def parse(raw):
    try:
        value=json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(BundleError('Non-finite JSON literal.')))
    except (UnicodeError,ValueError,RecursionError) as error:
        raise BundleError('Invalid, excessive or non-finite JSON.') from error
    if not isinstance(value,dict):raise BundleError('A JSON object is required.')
    return value


def seal(value):
    checksum=hashlib.sha256()
    for part in json.JSONEncoder(sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).iterencode(value):
        checksum.update(part.encode('utf-8'))
    return checksum.hexdigest()


def relative_path(value):
    if (not isinstance(value,str) or len(value)>1000 or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]*',value) or
            any(len(p)>255 or p in ('','.','..') or p.endswith('.') or p.split('.')[0].upper() in WINDOWS_RESERVED for p in value.split('/'))):
        raise BundleError('Unsafe or nonportable asset path.')
    return value


def linked(info):
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info,'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0))


def no_links(path):
    path=absolute(path);cursor=Path(path.anchor)
    for component in path.parts[1:]:
        cursor/=component
        try:info=cursor.lstat()
        except FileNotFoundError:break
        if linked(info):raise BundleError('Symlinks and reparse points are not allowed.')
    return path


def fingerprint(info):return (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns)


@contextmanager
def regular(path):
    path=no_links(path);before=path.lstat()
    if not stat.S_ISREG(before.st_mode):raise BundleError('Only regular files are allowed.')
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_BINARY',0)|getattr(os,'O_NOFOLLOW',0))
    with os.fdopen(fd,'rb') as stream:
        info=os.fstat(stream.fileno())
        if fingerprint(info)!=fingerprint(before):raise BundleError('Source file changed while opening.')
        yield stream,info
        current=path.lstat()
        if linked(current) or fingerprint(current)!=fingerprint(info) or fingerprint(os.fstat(stream.fileno()))!=fingerprint(info):
            raise BundleError('Source file changed while reading.')


def read_bytes(path,maximum):
    with regular(path) as (stream,info):
        if not 0<info.st_size<=maximum:raise BundleError('JSON source exceeds its byte budget.')
        raw=stream.read(maximum+1)
        if len(raw)!=info.st_size:raise BundleError('JSON source changed or exceeded its byte budget.')
    return raw,fingerprint(info)


def read_json(path,maximum):
    raw,stamp=read_bytes(path,maximum)
    return raw,parse(raw),stamp


def inventory(raw,world,limits):
    source=world.get('source');target=world.get('target')
    if (world.get('schema')!=WORLD or world.get('crs')!='EPSG:2154' or world.get('units')!='m' or
            world.get('origin')!=ORIGIN or type(world.get('cellSize')) is not int or world['cellSize']!=250 or
            world.get('coverageExplicitPartial') is not True or world.get('completeMetropole') is not False or
            world.get('preparationOnly') is not True or world.get('activationPerformed') is not False or
            not isinstance(source,dict) or not valid_hash(source.get('sha256')) or
            any(not isinstance(source.get(k),str) or not source[k].strip() or len(source[k])>4000 for k in ('license','attribution')) or
            not valid_hash(world.get('sourcePackSHA256')) or not isinstance(target,dict) or target.get('id')!='200054807' or
            'boundarySHA256' not in target or target['boundarySHA256'] is not None and not valid_hash(target['boundarySHA256'])):
        raise BundleError('Unsupported source/frame/preparation world manifest.')
    if world.get('manifestContentSHA256')!=seal({k:v for k,v in world.items() if k!='manifestContentSHA256'}):
        raise BundleError('World manifest content seal differs from its actual metadata.')
    tiles=world.get('tiles')
    if not isinstance(tiles,list) or len(tiles)>100000:raise BundleError('World cell index exceeds its budget.')
    assets={};case_paths={};positions=set();ids=set();counts={layer:0 for layer in LAYERS}

    def add(value,encoding=None):
        if not isinstance(value,dict):raise BundleError('A complete asset descriptor is required.')
        path=relative_path(value.get('path'));size=value.get('bytes');decoded=value.get('decodedBytes')
        if (type(size) is not int or not 0<size<=limits.max_asset_bytes or not valid_hash(value.get('sha256')) or
                value.get('encoding') not in ('json','gzip-json') or encoding is not None and value['encoding']!=encoding or
                'decodedBytes' in value and (type(decoded) is not int or not 0<decoded<=limits.max_decoded_bytes)):
            raise BundleError('Invalid asset size/hash/encoding descriptor.')
        item=Asset(path,size,value['sha256'],value['encoding'],decoded)
        folded=path.casefold()
        if folded=='manifest.json' or folded in case_paths and case_paths[folded]!=path:
            raise BundleError('Asset path conflicts with the manifest or a portable filename.')
        if path in assets and assets[path]!=item:raise BundleError('Conflicting duplicate asset path.')
        assets[path]=item;case_paths[folded]=path
        if len(assets)>limits.max_assets:raise BundleError('Asset count exceeds its budget.')

    for tile in tiles:
        cell=tile.get('cellId') if isinstance(tile,dict) else None
        if not isinstance(cell,str) or not CELL.fullmatch(cell) or cell in ids:raise BundleError('Invalid or duplicate world cell.')
        ids.add(cell);legacy=re.fullmatch(r'V52-MC-([1-5])([1-5])',cell)
        modern=re.fullmatch(r'V52-MC-([EW])([0-9]{2,4})-([NS])([0-9]{2,4})',cell)
        x,y=((int(legacy[2])-3,int(legacy[1])-3) if legacy else
            (int(modern[2])*(-1 if modern[1]=='W' else 1),int(modern[4])*(-1 if modern[3]=='N' else 1)))
        if type(tile.get('gridX')) is not int or type(tile.get('gridY')) is not int or (tile['gridX'],tile['gridY'])!=(x,y) or (x,y) in positions:
            raise BundleError('Invalid or duplicated metric grid position.')
        positions.add((x,y));e,n=ORIGIN[0]+x*250,ORIGIN[1]-y*250
        if tile.get('boundsL93')!=[e-125,n-125,e+125,n+125]:raise BundleError('Shifted metric world cell.')
        if tile.get('terrainOnly') is True:
            if tile.get('vector') is not None or tile.get('contentSHA256') is not None or not tile.get('terrain') or any(tile.get(k) is not None for k in ('surfaces','navigation')):
                raise BundleError('Contradictory terrain-only cell.')
        elif not valid_hash(tile.get('contentSHA256')) or tile.get('vector') is None:
            raise BundleError('A real vector cell content binding is required.')
        for layer in LAYERS:
            if tile.get(layer) is not None:add(tile[layer],'gzip-json');counts[layer]+=1
    if world.get('buildingParts') is not None:
        value=world['buildingParts'];add(value,'json')
        if value.get('sourcePbfSHA256')!=source['sha256'] or not valid_hash(value.get('proofSHA256')):
            raise BundleError('Building-parts descriptor source/proof binding differs.')
        counts['buildingParts']=1
    # Include future checked JSON descriptors too, never silently omit a
    # manifest-reachable metadata asset from a supposedly complete cache.
    pending=[world]
    while pending:
        value=pending.pop()
        if isinstance(value,dict):
            if {'path','bytes','sha256','encoding'}<=value.keys():add(value)
            pending.extend(v for v in value.values() if isinstance(v,(dict,list)))
        elif isinstance(value,list):pending.extend(v for v in value if isinstance(v,(dict,list)))
    all_files=set(case_paths)|{'manifest.json'}
    for path in assets:
        pieces=path.casefold().split('/')
        if any('/'.join(pieces[:n]) in all_files for n in range(1,len(pieces))):
            raise BundleError('An asset file collides with a required directory.')
    ordered=tuple(assets[path] for path in sorted(assets));total=len(raw)+sum(a.size for a in ordered)
    if total>limits.max_total_bytes:raise BundleError('World payload exceeds its total-byte budget.')
    return ordered,counts,total


def header(raw,world,assets,total,tool_sha):
    return {'schema':SCHEMA,'worldManifestBytes':len(raw),'worldManifestSHA256':digest(raw),
        'manifestContentSHA256':world['manifestContentSHA256'],'sourcePbfSHA256':world['source']['sha256'],
        'sourcePackSHA256':world['sourcePackSHA256'],'assetCount':len(assets),'assetBytes':total-len(raw),
        'payloadBytes':total,'toolSHA256':tool_sha}


def bundle_size(head):return len(MAGIC)+4+len(canonical(head))+head['payloadBytes']+len(FOOTER)+32


def load_world(directory,limits):
    root=no_links(directory)
    if not root.is_dir():raise BundleError('A regular world-cache directory is required.')
    raw,world,stamp=read_json(root/'manifest.json',limits.max_manifest_bytes)
    assets,counts,total=inventory(raw,world,limits)
    for asset in assets:
        path=no_links(root/asset.path);info=path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size!=asset.size:raise BundleError('World asset missing, nonregular or of incorrect size.')
    return root,raw,world,assets,counts,total,stamp


def plan(world_dir,*,limits=None):
    limits=(limits or Limits()).validate();root,raw,world,assets,counts,total,stamp=load_world(world_dir,limits)
    head=header(raw,world,assets,total,digest(Path(__file__).read_bytes()))
    allocation=allocation_estimate(root,raw,assets)
    return {**head,'archiveBytes':bundle_size(head),'countsByLayer':counts,'assetsHashed':False,**allocation,
        'format':'versioned-uncompressed-stream; gzip assets retained byte-for-byte','copyBufferBytes':CHUNK,
        'metadataMemory':'Raw manifest, parsed JSON and inventory are retained; this is not a 1 MiB heap limit.'}


def ensure_space(directory,needed):
    if shutil.disk_usage(directory).free<needed+RESERVE:raise BundleError('Insufficient free disk space including the reserved margin.')


def allocation_info(directory):
    if hasattr(os,'statvfs'):
        info=os.statvfs(directory)
        return info.f_frsize or info.f_bsize,info.f_favail if info.f_files else None
    if os.name=='nt':
        sectors=ctypes.c_ulong();size=ctypes.c_ulong();free=ctypes.c_ulong();total=ctypes.c_ulong()
        call=ctypes.windll.kernel32.GetDiskFreeSpaceW
        call.argtypes=[ctypes.c_wchar_p,*([ctypes.POINTER(ctypes.c_ulong)]*4)];call.restype=ctypes.c_int
        if call(str(absolute(directory).anchor),ctypes.byref(sectors),ctypes.byref(size),ctypes.byref(free),ctypes.byref(total)):
            return sectors.value*size.value,None
    return 64*1024,None


def allocation_estimate(directory,raw,assets):
    unit,available_files=allocation_info(directory)
    if type(unit) is not int or not 0<unit<=16*1024*1024:raise BundleError('Unsupported filesystem allocation unit.')
    rounded=lambda size:((size+unit-1)//unit)*unit
    entries={'.':1}
    for asset in assets:
        pieces=asset.path.split('/');parent='.'
        for component in pieces[:-1]:
            child=component if parent=='.' else parent+'/'+component
            if child not in entries:entries[parent]=entries.get(parent,0)+1;entries[child]=0
            parent=child
        entries[parent]=entries.get(parent,0)+1
    required=len(assets)+1+len(entries)+2
    estimate=rounded(len(raw))+sum(rounded(asset.size) for asset in assets)
    estimate+=sum(rounded(max(unit,count*256)) for count in entries.values())+2*unit
    return {'estimatedInstallAllocationBytes':estimate,'allocationUnitBytes':unit,'requiredFilesystemEntries':required,
            'availableFilesystemEntries':available_files,'diskReserveBytes':RESERVE}


def publish_file(source,destination):
    if os.name=='nt':os.rename(source,destination)
    else:os.link(source,destination,follow_symlinks=False)


def publish_directory(source,destination):
    """Atomic publication which cannot replace even an empty existing folder."""
    if os.name=='nt':os.rename(source,destination);return
    if not sys.platform.startswith('linux'):raise BundleError('Atomic no-replace directory publication requires Linux or Windows.')
    libc=ctypes.CDLL(None,use_errno=True)
    try:rename=libc.renameat2
    except AttributeError as error:raise BundleError('This Linux libc lacks atomic renameat2 publication.') from error
    rename.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint];rename.restype=ctypes.c_int
    if rename(-100,os.fsencode(source),-100,os.fsencode(destination),1):
        code=ctypes.get_errno();raise OSError(code,os.strerror(code),str(destination))


def identity(path):
    info=path.lstat();return info.st_dev,info.st_ino


def remove_owned(path,owner):
    if path is None or owner is None:return
    try:
        info=path.lstat()
        if not linked(info) and (info.st_dev,info.st_ino)==owner:path.unlink()
    except FileNotFoundError:pass


class Writer:
    def __init__(self,stream):self.stream=stream;self.hash=hashlib.sha256();self.size=0
    def write(self,data):self.stream.write(data);self.hash.update(data);self.size+=len(data)


def export_bundle(world_dir,output,*,limits=None,progress=None):
    limits=(limits or Limits()).validate();tool=absolute(__file__);tool_sha=digest(tool.read_bytes())
    root,raw,world,assets,counts,total,manifest_stamp=load_world(world_dir,limits)
    root_id=identity(root);output=no_links(output);receipt_path=no_links(str(output)+'.receipt.json')
    if output.is_relative_to(root) or receipt_path.is_relative_to(root):raise BundleError('Export outputs must be outside the source cache.')
    if output.exists() or receipt_path.exists():raise BundleError('Export or receipt already exists; preserve the previous files.')
    output.parent.mkdir(parents=True,exist_ok=True);no_links(output.parent);parent_id=identity(output.parent)
    head=header(raw,world,assets,total,tool_sha);encoded=canonical(head)
    if len(encoded)>limits.max_header_bytes:raise BundleError('Bundle header exceeds its byte budget.')
    ensure_space(output.parent,bundle_size(head)+limits.max_header_bytes)
    archive_temp=receipt_temp=None;archive_owner=receipt_owner=None;committed=False;stamps={}
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent,prefix='.'+output.name+'.',delete=False) as stream:
            archive_temp=Path(stream.name);archive_owner=identity(archive_temp);writer=Writer(stream)
            writer.write(MAGIC);writer.write(struct.pack('>I',len(encoded)));writer.write(encoded);writer.write(raw)
            for number,asset in enumerate(assets,1):
                path=root/asset.path;checksum=hashlib.sha256();size=0
                with regular(path) as (source,info):
                    if info.st_size!=asset.size:raise BundleError('Source asset size differs from the world manifest.')
                    while size<asset.size:
                        chunk=source.read(min(CHUNK,asset.size-size))
                        if not chunk:raise BundleError('Truncated source asset.')
                        checksum.update(chunk);writer.write(chunk);size+=len(chunk)
                    if source.read(1) or checksum.hexdigest()!=asset.sha256:raise BundleError('Source asset SHA256 differs from the world manifest.')
                    stamps[path]=fingerprint(info)
                if progress:progress({'assets':number,'total':len(assets),'bytes':writer.size})
            prefix=writer.hash.digest();writer.write(FOOTER+prefix);stream.flush();os.fsync(stream.fileno())
        receipt={'schema':RECEIPT,'archiveSHA256':writer.hash.hexdigest(),'archiveBytes':writer.size,**{k:v for k,v in head.items() if k!='schema'}}
        with tempfile.NamedTemporaryFile(dir=output.parent,prefix='.'+output.name+'.receipt.',delete=False) as stream:
            receipt_temp=Path(stream.name);receipt_owner=identity(receipt_temp);stream.write(canonical(receipt)+b'\n');stream.flush();os.fsync(stream.fileno())
        no_links(root);no_links(output.parent)
        if identity(root)!=root_id or identity(output.parent)!=parent_id or fingerprint((root/'manifest.json').lstat())!=manifest_stamp:
            raise BundleError('Source cache or export path changed during export.')
        current_manifest,_=read_bytes(root/'manifest.json',limits.max_manifest_bytes)
        if digest(current_manifest)!=head['worldManifestSHA256'] or digest(tool.read_bytes())!=tool_sha:
            raise BundleError('World manifest or exporter code changed during export.')
        for path,expected in stamps.items():
            no_links(path)
            current=path.lstat()
            if linked(current) or fingerprint(current)!=expected:raise BundleError('Source asset changed during export.')
        no_links(output);no_links(receipt_path)
        if output.exists() or receipt_path.exists():raise BundleError('Export output appeared during preparation.')
        # Receipt first: SIGKILL may leave an orphan receipt, never a partial
        # visible archive or a complete archive without its external checksum.
        publish_file(receipt_temp,receipt_path);publish_file(archive_temp,output);committed=True
        return receipt
    finally:
        if not committed:remove_owned(output,archive_owner);remove_owned(receipt_path,receipt_owner)
        remove_owned(archive_temp,archive_owner);remove_owned(receipt_temp,receipt_owner)


class Reader:
    def __init__(self,stream):self.stream=stream;self.hash=hashlib.sha256();self.size=0
    def exact(self,size):
        pieces=[];remaining=size
        while remaining:
            chunk=self.stream.read(min(CHUNK,remaining))
            if not chunk:raise BundleError('Truncated bundle.')
            pieces.append(chunk);self.hash.update(chunk);self.size+=len(chunk);remaining-=len(chunk)
        return b''.join(pieces)


def pins(bundle,receipt,expected_sha256,expected_manifest_sha256):
    if expected_sha256 is not None and not valid_hash(expected_sha256):raise BundleError('Invalid expected archive SHA256.')
    if expected_manifest_sha256 is not None and not valid_hash(expected_manifest_sha256):raise BundleError('Invalid expected world-manifest SHA256.')
    candidate=absolute(receipt) if receipt is not None else Path(str(bundle)+'.receipt.json')
    saved=None
    if receipt is not None or candidate.exists() or candidate.is_symlink():
        raw,saved,stamp=read_json(candidate,64*1024)
        if (saved.get('schema')!=RECEIPT or any(type(saved.get(k)) is not int or saved[k]<0 for k in
                ('archiveBytes','worldManifestBytes','assetCount','assetBytes','payloadBytes')) or
                saved['archiveBytes']==0 or saved['worldManifestBytes']==0 or
                not all(valid_hash(saved.get(k)) for k in ('archiveSHA256','worldManifestSHA256','manifestContentSHA256',
                    'sourcePbfSHA256','sourcePackSHA256','toolSHA256'))):
            raise BundleError('Invalid external bundle receipt.')
        if expected_sha256 is not None and saved['archiveSHA256']!=expected_sha256:raise BundleError('Receipt and expected archive SHA256 differ.')
        if expected_manifest_sha256 is not None and saved['worldManifestSHA256']!=expected_manifest_sha256:raise BundleError('Receipt and expected manifest SHA256 differ.')
        expected_sha256=saved['archiveSHA256'];expected_manifest_sha256=saved['worldManifestSHA256']
    return saved,expected_sha256,expected_manifest_sha256


def scan(bundle,*,limits,receipt=None,expected_sha256=None,expected_manifest_sha256=None,sink=None,progress=None):
    bundle=no_links(bundle);saved,expected_sha256,expected_manifest_sha256=pins(bundle,receipt,expected_sha256,expected_manifest_sha256)
    with regular(bundle) as (stream,fileinfo):
        if fileinfo.st_size>limits.max_total_bytes+limits.max_header_bytes+len(MAGIC)+len(FOOTER)+36:
            raise BundleError('Bundle file exceeds its total-byte budget.')
        reader=Reader(stream)
        if reader.exact(len(MAGIC))!=MAGIC:raise BundleError('Unsupported bundle magic or format version.')
        length=struct.unpack('>I',reader.exact(4))[0]
        if not 0<length<=limits.max_header_bytes:raise BundleError('Bundle header length exceeds its budget.')
        head=parse(reader.exact(length))
        if (head.get('schema')!=SCHEMA or any(type(head.get(k)) is not int or head[k]<0 for k in ('worldManifestBytes','assetCount','assetBytes','payloadBytes')) or
                not 0<head['worldManifestBytes']<=limits.max_manifest_bytes or head['assetCount']>limits.max_assets or
                head['payloadBytes']>limits.max_total_bytes or head['assetBytes']+head['worldManifestBytes']!=head['payloadBytes'] or
                not all(valid_hash(head.get(k)) for k in ('worldManifestSHA256','manifestContentSHA256','sourcePbfSHA256','sourcePackSHA256','toolSHA256'))):
            raise BundleError('Invalid or excessive bundle header.')
        raw=reader.exact(head['worldManifestBytes'])
        if digest(raw)!=head['worldManifestSHA256'] or expected_manifest_sha256 is not None and digest(raw)!=expected_manifest_sha256:
            raise BundleError('Raw world-manifest SHA256 differs from its pinned edition.')
        world=parse(raw);assets,counts,total=inventory(raw,world,limits)
        expected=header(raw,world,assets,total,head['toolSHA256'])
        if head!=expected or fileinfo.st_size!=bundle_size(head):raise BundleError('Bundle header/index/physical size disagree.')
        if sink:sink(None,raw,total,assets)
        for number,asset in enumerate(assets,1):
            checksum=hashlib.sha256();remaining=asset.size
            target=sink(asset,None,None) if sink else None
            try:
                while remaining:
                    chunk=reader.exact(min(CHUNK,remaining));checksum.update(chunk);remaining-=len(chunk)
                    if target is not None:target.write(chunk)
                if checksum.hexdigest()!=asset.sha256:raise BundleError('Bundled asset SHA256 differs from the world manifest.')
            finally:
                if target is not None:target.close()
            if progress:progress({'assets':number,'total':len(assets),'bytes':reader.size})
        prefix=reader.hash.digest()
        if reader.exact(len(FOOTER))!=FOOTER or reader.exact(32)!=prefix:raise BundleError('Bundle footer SHA256 differs from its preceding bytes.')
        if stream.read(1):raise BundleError('Trailing data or additional archive entries are forbidden.')
        result={'schema':RECEIPT,'archiveSHA256':reader.hash.hexdigest(),'archiveBytes':reader.size,**{k:v for k,v in head.items() if k!='schema'}}
        if expected_sha256 is not None and result['archiveSHA256']!=expected_sha256:raise BundleError('Archive SHA256 differs from its external fingerprint.')
        if saved is not None and any(saved.get(k)!=v for k,v in result.items()):raise BundleError('External receipt contradicts the verified archive.')
    return result,raw,counts


def verify_bundle(bundle,*,limits=None,receipt=None,expected_sha256=None,expected_manifest_sha256=None,progress=None):
    limits=(limits or Limits()).validate()
    result,raw,counts=scan(bundle,limits=limits,receipt=receipt,expected_sha256=expected_sha256,
        expected_manifest_sha256=expected_manifest_sha256,progress=progress)
    return {**result,'status':'verified','countsByLayer':counts}


def verify_world(world_dir,*,limits=None,expected_manifest_sha256=None,progress=None):
    limits=(limits or Limits()).validate();root,raw,world,assets,counts,total,stamp=load_world(world_dir,limits)
    if expected_manifest_sha256 is not None and (not valid_hash(expected_manifest_sha256) or digest(raw)!=expected_manifest_sha256):
        raise BundleError('World manifest SHA256 differs from its external fingerprint.')
    stamps={};root_id=identity(root)
    for number,asset in enumerate(assets,1):
        checksum=hashlib.sha256();remaining=asset.size
        with regular(root/asset.path) as (stream,info):
            if info.st_size!=asset.size:raise BundleError('World asset size changed.')
            while remaining:
                chunk=stream.read(min(CHUNK,remaining))
                if not chunk:raise BundleError('Truncated world asset.')
                checksum.update(chunk);remaining-=len(chunk)
            if stream.read(1):raise BundleError('World asset grew during verification.')
            stamps[root/asset.path]=fingerprint(info)
        if checksum.hexdigest()!=asset.sha256:raise BundleError('World asset SHA256 differs from its manifest.')
        if progress:progress({'assets':number,'total':len(assets)})
    current_manifest,_=read_bytes(root/'manifest.json',limits.max_manifest_bytes)
    if digest(current_manifest)!=digest(raw):raise BundleError('World manifest changed during verification.')
    if identity(root)!=root_id:raise BundleError('World cache path changed during verification.')
    for path,expected in stamps.items():
        no_links(path)
        if fingerprint(path.lstat())!=expected:raise BundleError('World asset changed during verification.')
    return {'status':'verified','worldManifestSHA256':digest(raw),'assetCount':len(assets),'payloadBytes':total,'countsByLayer':counts}


def import_bundle(bundle,destination,*,limits=None,receipt=None,expected_sha256=None,expected_manifest_sha256=None,progress=None):
    limits=(limits or Limits()).validate();bundle=no_links(bundle);destination=no_links(destination)
    if destination.exists():raise BundleError('Import destination already exists; the current cache is preserved.')
    if bundle.is_relative_to(destination):raise BundleError('The archive must be outside the new cache destination.')
    destination.parent.mkdir(parents=True,exist_ok=True);no_links(destination.parent);parent_id=identity(destination.parent)
    with tempfile.TemporaryDirectory(dir=destination.parent,prefix='.'+destination.name+'.bundle-import-') as temporary:
        stage=Path(temporary)/'world';stage.mkdir()
        allocation={}
        def sink(asset,raw,total,assets=None):
            if asset is None:
                allocation.update(allocation_estimate(destination.parent,raw,assets))
                available=allocation['availableFilesystemEntries']
                if available is not None and available<allocation['requiredFilesystemEntries']:
                    raise BundleError('Insufficient free filesystem entries for the cache.')
                ensure_space(destination.parent,allocation['estimatedInstallAllocationBytes']);return None
            path=stage/asset.path;path.parent.mkdir(parents=True,exist_ok=True);no_links(path)
            return path.open('xb')
        result,raw,counts=scan(bundle,limits=limits,receipt=receipt,expected_sha256=expected_sha256,
            expected_manifest_sha256=expected_manifest_sha256,sink=sink,progress=progress)
        with (stage/'manifest.json').open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        no_links(destination);no_links(destination.parent)
        if identity(destination.parent)!=parent_id or destination.exists():raise BundleError('Import destination changed during preparation.')
        publish_directory(stage,destination)
    return {**result,'status':'installed','destination':str(destination),'countsByLayer':counts,**allocation}


def main():
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    planning=commands.add_parser('plan');planning.add_argument('--world',type=Path,required=True)
    exporting=commands.add_parser('export');exporting.add_argument('--world',type=Path,required=True)
    exporting.add_argument('--output',type=Path);exporting.add_argument('--plan',action='store_true')
    importing=commands.add_parser('import');importing.add_argument('--bundle',type=Path,required=True);importing.add_argument('--destination',type=Path,required=True)
    verifying=commands.add_parser('verify');choice=verifying.add_mutually_exclusive_group(required=True)
    choice.add_argument('--world',type=Path);choice.add_argument('--bundle',type=Path)
    for sub in (planning,exporting,importing,verifying):
        sub.add_argument('--max-total-bytes',type=int,default=Limits.max_total_bytes)
        sub.add_argument('--max-asset-bytes',type=int,default=Limits.max_asset_bytes)
        sub.add_argument('--max-assets',type=int,default=Limits.max_assets)
        sub.add_argument('--progress',action='store_true')
    for sub in (importing,verifying):
        sub.add_argument('--receipt',type=Path);sub.add_argument('--sha256');sub.add_argument('--manifest-sha256')
    args=parser.parse_args()
    limits=Limits(max_total_bytes=args.max_total_bytes,max_asset_bytes=args.max_asset_bytes,max_assets=args.max_assets)
    notify=(lambda row:print(json.dumps(row),file=sys.stderr,flush=True) if row['assets']%256==0 or row['assets']==row['total'] else None) if args.progress else None
    try:
        if args.command=='plan' or args.command=='export' and args.plan:result=plan(args.world,limits=limits)
        elif args.command=='export':
            if args.output is None:parser.error('export requires --output unless --plan is used')
            result=export_bundle(args.world,args.output,limits=limits,progress=notify)
        elif args.command=='verify' and args.world:
            if args.receipt is not None or args.sha256 is not None:parser.error('--receipt and --sha256 apply to --bundle; use --manifest-sha256 for --world')
            result=verify_world(args.world,limits=limits,expected_manifest_sha256=args.manifest_sha256,progress=notify)
        else:
            kwargs={'limits':limits,'receipt':args.receipt,'expected_sha256':args.sha256,'expected_manifest_sha256':args.manifest_sha256,'progress':notify}
            result=import_bundle(args.bundle,args.destination,**kwargs) if args.command=='import' else verify_bundle(args.bundle,**kwargs)
        print(json.dumps(result,ensure_ascii=False,sort_keys=True))
    except (OSError,ValueError,TypeError,KeyError,RecursionError) as error:parser.exit(1,f'World bundle refused: {error}\n')


if __name__=='__main__':main()
