#!/usr/bin/env python3
"""Bounded canonical OSM/IGN eaves-height matching, separate from the active game.

`match` consumes published vector/IGN manifests and readonly SQLite catalogues.
It closes spatial candidate neighbourhoods, reuses building_heights' strict
algorithm, and publishes canonical matches without synthetic runtime cell IDs.
`sidecars` binds those matches to verified, real imported vector cell contents.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict, dataclass
import gzip
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import sqlite3
import sys
import tempfile

_spec = importlib.util.spec_from_file_location('_soma_catalogue_height_core', Path(__file__).with_name('building_heights.py'))
core = importlib.util.module_from_spec(_spec);sys.modules[_spec.name] = core;_spec.loader.exec_module(core)
SCHEMA = 'soma-metropole/canonical-building-heights/1'


class CatalogueError(ValueError):
    pass


def canonical(value):
    return core.canonical(value)


def digest(value):
    return core.digest(value)


def save(path, value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def read_hashed(path, maximum=64*1024*1024):
    """Pin the bytes actually parsed, rather than reopening a mutable manifest."""
    path=Path(path)
    if path.stat().st_size>maximum:raise CatalogueError('Source JSON exceeds its byte budget.')
    with path.open('rb') as stream:raw=stream.read(maximum+1)
    if len(raw)>maximum:raise CatalogueError('Source JSON exceeds its byte budget.')
    try:value=json.loads(raw,parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except (ValueError,UnicodeError) as error:raise CatalogueError('Invalid or non-finite source JSON.') from error
    return value,hashlib.sha256(raw).hexdigest()


def read(path, maximum=64*1024*1024):
    return read_hashed(path,maximum)[0]


def asset(root, relative):
    if not isinstance(relative,str) or Path(relative).is_absolute():
        raise CatalogueError('Relative source asset path required.')
    p=(root/relative).resolve()
    if not p.is_relative_to(root.resolve()):
        raise CatalogueError('Source asset escaped manifest root.')
    return p


def readonly(path):
    path=Path(path).resolve()
    if not path.is_file() or (path.with_name(path.name+'-wal').exists() and path.with_name(path.name+'-wal').stat().st_size):
        raise CatalogueError('Published, checkpointed SQLite source required; never read a live import.')
    return sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1',uri=True)


@dataclass(frozen=True)
class Limits:
    step: int=1000
    max_partitions: int=10000
    max_osm: int=20000
    max_ign: int=20000
    max_candidates: int=512
    max_comparisons: int=2000000
    max_partition_bytes: int=64*1024*1024
    max_coordinates: int=100000

    def validate(self):
        if any(type(v) is not int or v<=0 for v in asdict(self).values()) or not 250<=self.step<=4000 or self.max_osm>50000 or self.max_ign>50000 or self.max_partition_bytes>128*1024*1024 or self.max_partitions>10000 or self.max_coordinates>100000 or self.max_candidates>512 or self.max_comparisons>10000000:
            raise CatalogueError('Invalid or excessive catalogue partition budget.')
        return self


def boundary_geometry(path, *, document=None):
    from pyproj import Transformer
    from shapely.geometry import shape
    from shapely.ops import transform
    doc=document if document is not None else read(path,16*1024*1024)
    if not isinstance(doc,dict) or doc.get('type')!='FeatureCollection' or len(doc.get('features',[]))!=1:
        raise CatalogueError('Single administrative union required.')
    geom=shape(doc['features'][0]['geometry'])
    if geom.is_empty or not geom.is_valid:raise CatalogueError('Invalid administrative geometry.')
    return transform(Transformer.from_crs('EPSG:4326','EPSG:2154',always_xy=True).transform,geom)


def source_coverage(manifest,boundary):
    """Conservative source-header polygon, intersected with import selection."""
    from pyproj import Transformer
    from shapely.geometry import Polygon,box
    from shapely.ops import transform
    bounds=manifest.get('sourceBoundsWGS84')
    if not isinstance(bounds,list) or len(bounds)!=4:raise CatalogueError('Source PBF header bounds required.')
    w,s,e,n=bounds
    if not all(isinstance(v,(float,int)) and math.isfinite(v) for v in bounds) or not(-180<=w<e<=180 and -90<=s<n<=90):raise CatalogueError('Invalid source-header bounds.')
    points=[]
    corners=[(w,s),(e,s),(e,n),(w,n),(w,s)]
    for a,b in zip(corners,corners[1:]):
        for i in range(256):points.append((a[0]+(b[0]-a[0])*i/256,a[1]+(b[1]-a[1])*i/256))
    points.append(points[0])
    projected=transform(Transformer.from_crs('EPSG:4326','EPSG:2154',always_xy=True).transform,Polygon(points))
    # A metre inward avoids claiming coverage on interpolated header edges.
    return projected.buffer(-1).intersection(box(*manifest['bounds'])).intersection(boundary)


def envelope_geometry(bounds):
    from shapely.geometry import box,LineString,Point
    w,s,e,n=bounds
    if w==e and s==n:return Point(w,s)
    if w==e or s==n:return LineString([(w,s),(e,n)])
    return box(w,s,e,n)


def proven_rejection_envelope(record):
    """Derive the envelope from every source ref, never close an open way."""
    from pyproj import Transformer
    if record.get('kind')!='way' or record.get('refsComplete') is not True or record.get('missingNodeRefs')!=[]:
        raise CatalogueError('Rejected building lacks a complete source-node envelope.')
    refs=record.get('nodeRefs');positions=record.get('nodePositionsWGS84')
    if not isinstance(refs,list) or not 2<=len(refs)<=1000000 or not isinstance(positions,dict) or set(refs)!=set(positions):
        raise CatalogueError('Rejected building source refs/positions are incomplete.')
    project=Transformer.from_crs('EPSG:4326','EPSG:2154',always_xy=True).transform;points=[]
    for ref in refs:
        point=positions[ref]
        if not isinstance(ref,str) or not ref.isdigit() or not isinstance(point,list) or len(point)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in point) or not(-180<=point[0]<=180 and -90<=point[1]<=90):
            raise CatalogueError('Rejected building source position is invalid.')
        points.append(project(*point))
    bounds=[min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points),max(p[1] for p in points)]
    declared=record.get('boundsL93')
    if not isinstance(declared,list) or len(declared)!=4 or any(type(v) not in (int,float) or not math.isfinite(v) for v in declared) or any(abs(a-b)>1e-7 for a,b in zip(bounds,declared)):
        raise CatalogueError('Rejected building envelope differs from resolved native nodes.')
    return bounds


def check_rejections(db,source_sha,pbf=None,*,envelope_proof=None,canonical_store_sha=None,boundary_sha=None,scope=None):
    """Proven invalid source envelopes block only affected neighbourhoods."""
    rejected=list(db.execute('SELECT id,reason FROM rejected'))
    if len(rejected)>10000:raise CatalogueError('Source rejection inspection budget exceeded.')
    tags={};unknown=set();records={}
    if envelope_proof is not None:
        proof=envelope_proof
        if not isinstance(proof,dict) or proof.get('schema')!='soma-metropole/osm-rejection-envelopes/1' or proof.get('proofSHA256')!=digest({k:v for k,v in proof.items() if k!='proofSHA256'}):
            raise CatalogueError('Rejected-source envelope proof checksum differs.')
        if proof.get('sourceSHA256')!=source_sha or proof.get('canonicalStoreSHA256')!=canonical_store_sha or proof.get('boundarySHA256')!=boundary_sha or proof.get('crs')!='EPSG:2154' or proof.get('units')!='m':
            raise CatalogueError('Rejected-source proof snapshot/frame differs.')
        rows=proof.get('records')
        if not isinstance(rows,list) or len(rows)!=len(rejected) or any(not isinstance(r,dict) for r in rows):raise CatalogueError('Rejected-source proof membership differs.')
        records={r.get('canonicalId'):r for r in rows}
        if len(records)!=len(rows) or set(records)!={r[0] for r in rejected}:raise CatalogueError('Rejected-source proof membership differs.')
    for identity,reason in rejected:
        kind,number=identity.split('/')[1:];table='source_relations' if kind=='relation' else 'source_ways'
        stored=db.execute('SELECT tags FROM '+table+' WHERE id=?',(int(number),)).fetchone()
        record=records.get(identity)
        if record is not None:
            if record.get('reason')!=reason or not isinstance(record.get('tags'),dict):raise CatalogueError('Rejected-source reason/tags differ.')
            if stored and json.loads(stored[0])!=record['tags']:raise CatalogueError('Rejected-source tags contradict the canonical snapshot.')
            tags[identity]=record['tags']
        elif stored:tags[identity]=json.loads(stored[0])
        else:unknown.add(identity)
    if unknown:
        if pbf is None or core.file_sha256(pbf)!=source_sha:raise CatalogueError('Rejected source objects lack tags/envelopes; supply the verified --osm-pbf or reject uncertain neighbourhoods.')
        import osmium
        class Rejections(osmium.SimpleHandler):
            def way(self,way):
                key='osm/way/'+str(way.id)
                if key in unknown:tags[key]=dict(way.tags)
            def relation(self,relation):
                key='osm/relation/'+str(relation.id)
                if key in unknown:tags[key]=dict(relation.tags)
        Rejections().apply_file(str(pbf))
    blockers=[];outside=[];non_building=0
    for identity,reason in rejected:
        t=tags.get(identity)
        if t is None:raise CatalogueError('Rejected source object has unknown tags: '+identity)
        if not core._active(t.get('building')) and not core._active(t.get('building:part')):non_building+=1;continue
        record=records.get(identity)
        if record is None:raise CatalogueError('Rejected/unknown OSM building has no proven neighbour envelope: '+identity)
        bounds=proven_rejection_envelope(record)
        entry={'canonicalId':identity,'boundsL93':bounds,'reason':reason,'recordSHA256':digest(record)}
        if scope is not None and not scope.intersects(envelope_geometry(bounds)):outside.append(entry)
        else:blockers.append(entry)
    return {'inspected':len(rejected),'allKnownOutsideBuildingLayer':non_building==len(rejected),'knownNonBuilding':non_building,'buildingEnvelopesOutsideScope':outside,'localBuildingBlockers':blockers,'classificationSHA256':digest(tags),'envelopeProofSHA256':envelope_proof.get('proofSHA256') if envelope_proof else None}



def verify_sources(osm_manifest,ign_index,boundary_path, *, snapshots=None):
    osm_manifest,ign_index,boundary_path=map(Path,(osm_manifest,ign_index,boundary_path))
    osm,osm_sha=read_hashed(osm_manifest);ign,ign_sha=read_hashed(ign_index,16*1024*1024)
    boundary,boundary_sha=read_hashed(boundary_path,16*1024*1024)
    if not isinstance(osm,dict) or not isinstance(ign,dict):raise CatalogueError('Source manifests must be objects.')
    if osm.get('schema')!='soma-metropole/vector-tiles/1' or osm.get('crs')!='EPSG:2154' or osm.get('units')!='m':raise CatalogueError('Published metric vector manifest required.')
    desc=osm.get('canonicalStore',{});osm_path=asset(osm_manifest.parent,desc.get('path'))
    if desc.get('encoding')!='sqlite3' or osm_path.stat().st_size!=desc.get('bytes') or core.file_sha256(osm_path)!=desc.get('sha256'):raise CatalogueError('OSM canonical store hash/size differs.')
    if ign.get('schema')!='soma-metropole/ign-bdtopo-source-index/1' or ign.get('crs')!='EPSG:2154' or ign.get('units')!='m' or ign.get('verticalDatum')!='NGF-IGN69' or ign.get('queryAcquisitionComplete') is not True or ign.get('sourceGeometryCoverageValidated') is not True:
        raise CatalogueError('Complete bounded IGN acquisition index with explicit units/datum required.')
    if ign.get('sourceSHA256')!=digest({k:v for k,v in ign.items() if k not in ('sourceSHA256','sqliteSHA256','sqliteBytes')}):raise CatalogueError('IGN source index checksum differs.')
    ign_path=ign_index.parent/'buildings.sqlite'
    if ign_path.stat().st_size!=ign.get('sqliteBytes') or core.file_sha256(ign_path)!=ign.get('sqliteSHA256'):raise CatalogueError('IGN catalogue hash differs.')
    core._receipt({**ign,'sha256':ign['sqliteSHA256']},ign_path)
    if not isinstance(ign.get('heightMeaning'),str) or not ign['heightMeaning'].strip() or ign.get('heightKind','eaves')!='eaves':raise CatalogueError('Explicit IGN eaves semantics required.')
    if boundary_sha!=ign.get('boundarySHA256'):raise CatalogueError('IGN coverage boundary hash differs.')
    if osm.get('boundary') and osm['boundary'].get('sha256')!=ign['boundarySHA256']:raise CatalogueError('OSM/IGN selection boundaries differ.')
    source_sha=osm.get('source',{}).get('sha256')
    if not isinstance(source_sha,str) or not core.HASH.fullmatch(source_sha):raise CatalogueError('Source PBF SHA256 required.')
    if snapshots is not None:
        snapshots.update(osmManifestSHA256=osm_sha,ignSourceIndexFileSHA256=ign_sha,
                         boundarySHA256=boundary_sha,boundaryDocument=boundary)
    return osm,ign,osm_path,ign_path


def native(row,limits):
    import shapely
    from shapely.geometry import mapping
    identity,properties,wkb,*_=row;p=json.loads(properties)
    if p.get('canonical_id')!=identity or p.get('soma:layer')!='buildings':raise CatalogueError('Canonical identity/layer differs.')
    geometry=shapely.from_wkb(wkb);mapped=mapping(geometry)
    core._metric_geometry(mapped,core.MatchLimits(max_geometry_coordinates=limits.max_coordinates))
    if digest(mapped)!=p.get('soma:geometry_sha256'):raise CatalogueError('Native geometry SHA256 differs; no repair/closing edge was invented.')
    return p,geometry,mapped


def internal_records(rows,source_sha,limits):
    """Native closed rings adapted privately; IDs below are never runtime cells."""
    from shapely.geometry import mapping
    for number,start in enumerate(range(0,len(rows),250)):
        features=[]
        for row in rows[start:start+250]:
            p,g,mapped=native(row,limits);meshes=[]
            polygons=list(g.geoms) if g.geom_type=='MultiPolygon' else [g]
            for polygon in polygons:
                rings=[list(polygon.exterior.coords)]+[list(r.coords) for r in polygon.interiors]
                meshes.append({'ringsL93':rings,'wallsL93':[[a,b] for ring in rings for a,b in zip(ring,ring[1:])]})
            p={**p,'soma:metricGeometry':mapped,'soma:mesh53':meshes}
            features.append({'type':'Feature','id':row[0],'properties':p,'geometry':mapped})
        collection={'type':'FeatureCollection','features':features}
        yield {'cellId':f'internal-native-catalogue-batch/{number}','contentSHA256':digest(collection),'sourceReceipt':{'sha256':source_sha},'featureCollection':collection,'meaning':'Internal native adapter; never a runtime cell binding.'}


def spatial_rows(db,bounds):
    w,s,e,n=bounds
    return db.execute("SELECT f.id,f.properties,f.geometry,f.minx,f.miny,f.maxx,f.maxy FROM feature_index i JOIN features f ON f.rowid=i.rowid WHERE f.layer='buildings' AND i.minx<=? AND i.maxx>=? AND i.miny<=? AND i.maxy>=? ORDER BY f.id",(e,w,n,s))


def match_catalogues(osm_manifest,ign_index,boundary_path,output,*,bounds=None,limits=None,osm_pbf=None,osm_rejection_proof=None,log=print):
    from shapely.geometry import box
    limits=(limits or Limits()).validate();output=Path(output)
    if output.exists():raise CatalogueError('Output exists; preserve the published catalogue.')
    snapshots={}
    osm,ign,osm_path,ign_path=verify_sources(osm_manifest,ign_index,boundary_path,snapshots=snapshots)
    osm_db=readonly(osm_path);ign_db=readonly(ign_path)
    try:
        scope=boundary_geometry(boundary_path,document=snapshots['boundaryDocument'])
        envelope_doc=None;envelope_file_sha=None
        if osm_rejection_proof is not None:envelope_doc,envelope_file_sha=read_hashed(osm_rejection_proof,16*1024*1024)
        rejection_proof=check_rejections(osm_db,osm['source']['sha256'],osm_pbf,envelope_proof=envelope_doc,canonical_store_sha=osm['canonicalStore']['sha256'],boundary_sha=snapshots['boundarySHA256'],scope=scope)
        local_blockers=[(row['canonicalId'],envelope_geometry(row['boundsL93'])) for row in rejection_proof['localBuildingBlockers']]
        coverage=source_coverage(osm,scope)
        selected_bounds=bounds or osm['bounds']
        if not isinstance(selected_bounds,(list,tuple)) or len(selected_bounds)!=4 or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in selected_bounds) or selected_bounds[0]>=selected_bounds[2] or selected_bounds[1]>=selected_bounds[3]:raise CatalogueError('Invalid matching selection bounds.')
        requested=box(*selected_bounds)
        if requested.is_empty or not requested.is_valid:raise CatalogueError('Invalid matching selection bounds.')
        w,s,e,n=requested.bounds;step=limits.step;gx0=math.floor(w/step);gy0=math.floor(s/step);gx1=math.ceil(e/step);gy1=math.ceil(n/step)
        if (gx1-gx0)*(gy1-gy0)>limits.max_partitions:raise CatalogueError('Partition count budget exceeded.')
        output.mkdir(parents=True)
        index=sqlite3.connect(output/'ign-spatial.sqlite');index.execute('CREATE VIRTUAL TABLE envelopes USING rtree(id,minx,maxx,miny,maxy)')
        # A separate derived index streams numeric envelopes; no million-object STRtree.
        with index:
            index.executemany('INSERT INTO envelopes VALUES(?,?,?,?,?)',ign_db.execute('SELECT rowid,min_x,max_x,min_y,max_y FROM objects'))
        matches_db=sqlite3.connect(output/'matches.sqlite');matches_db.executescript('CREATE TABLE matches(binding TEXT PRIMARY KEY,canonical_id TEXT UNIQUE,geometry_sha256 TEXT,source_sha256 TEXT,proof_json TEXT,minx REAL,miny REAL,maxx REAL,maxy REAL);CREATE TABLE rejected(canonical_id TEXT PRIMARY KEY,reason TEXT,detail TEXT);CREATE TABLE partitions(id TEXT PRIMARY KEY,proof_sha256 TEXT,seed_count INTEGER,osm_neighbours INTEGER,ign_candidates INTEGER);')
        statistics={'partitions':0,'seedBuildings':0,'accepted':0,'rejected':0,'peakOSMNeighbours':0,'peakIGNCandidates':0}
        try:
            for gy in range(gy0,gy1):
                for gx in range(gx0,gx1):
                    cell=box(gx*step,gy*step,(gx+1)*step,(gy+1)*step)
                    seeds={}
                    for row in spatial_rows(osm_db,cell.bounds):
                        cx=(row[3]+row[5])/2;cy=(row[4]+row[6])/2
                        if gx*step<=cx<(gx+1)*step and gy*step<=cy<(gy+1)*step and w<=cx<e and s<=cy<n:seeds[row[0]]=row
                    if not seeds:continue
                    if len(seeds)>limits.max_osm:raise CatalogueError('Seed partition budget exceeded; reduce --step.')
                    ign_ids=set();seed_ign={}
                    for identity,row in seeds.items():
                        a,b,c,d=row[3:]
                        ids=[v[0] for v in index.execute('SELECT id FROM envelopes WHERE minx<=? AND maxx>=? AND miny<=? AND maxy>=?',(c,a,d,b))]
                        if len(ids)>limits.max_candidates:raise CatalogueError('Per-building candidate budget exceeded.')
                        seed_ign[identity]=ids;ign_ids.update(ids)
                        if len(ign_ids)>limits.max_ign:raise CatalogueError('IGN partition budget exceeded; reduce --step.')
                    ign_rows=[];ign_geometries={};all_osm=dict(seeds);byte_count=0
                    for rowid in sorted(ign_ids):
                        row=ign_db.execute('SELECT ign_id,feature_json,content_sha256,min_x,min_y,max_x,max_y FROM objects WHERE rowid=?',(rowid,)).fetchone()
                        if row is None:raise CatalogueError('Derived IGN index identity differs.')
                        raw=row[1];byte_count+=len(raw.encode());feature=json.loads(raw)
                        if hashlib.sha256(raw.encode()).hexdigest()!=row[2]:raise CatalogueError('IGN native payload SHA differs.')
                        geometry=core._metric_geometry(feature['geometry'],core.MatchLimits(max_geometry_coordinates=limits.max_coordinates))
                        ign_geometries[rowid]=geometry;ign_rows.append(feature)
                        for neighbour in spatial_rows(osm_db,row[3:]):all_osm[neighbour[0]]=neighbour
                        if len(all_osm)>limits.max_osm or byte_count>limits.max_partition_bytes:raise CatalogueError('Neighbourhood partition budget exceeded; reduce --step.')
                    for row in all_osm.values():byte_count+=len(row[1].encode())+len(row[2])*4
                    if byte_count>limits.max_partition_bytes:raise CatalogueError('Native partition byte budget exceeded.')
                    unsafe={};unsafe_details={}
                    for identity,row in seeds.items():
                        _,g,_=native(row,limits)
                        if not coverage.covers(g) or any(not coverage.covers(ign_geometries[i]) for i in seed_ign[identity]):unsafe[identity]='neighbourhood-outside-proven-source-coverage'
                        conflicts=[key for key,envelope in local_blockers if g.intersects(envelope) or any(ign_geometries[i].intersects(envelope) for i in seed_ign[identity])]
                        if conflicts:unsafe[identity]='quarantined-source-building-neighbourhood';unsafe_details[identity]={'quarantinedSourceIds':conflicts}
                    with tempfile.TemporaryDirectory(prefix='match-partition-',dir=output) as temporary:
                        path=Path(temporary)/'ign.geojson';path.write_text(canonical({'type':'FeatureCollection','crs':{'type':'name','properties':{'name':'EPSG:2154'}},'features':ign_rows}))
                        receipt={k:ign[k] for k in ('license','date','units','verticalDatum','crs','fields')};receipt.update(sha256=core.file_sha256(path),id=ign['sourceSHA256'])
                        report=core.match_building_heights(internal_records(list(all_osm.values()),osm['source']['sha256'],limits),path,receipt,limits=core.MatchLimits(max_osm_buildings=limits.max_osm,max_ign_features=limits.max_ign,max_candidates_per_building=limits.max_candidates,max_comparisons=limits.max_comparisons,max_geometry_coordinates=limits.max_coordinates),scratch=temporary)
                        core.validate_matches(report)
                    accepted={r['canonicalId']:(key,r) for key,r in report['matches'].items() if r['canonicalId'] in seeds}
                    refused={r['canonicalId']:r for r in report['rejected'] if r['canonicalId'] in seeds}
                    partition=f'{gx}:{gy}'
                    with matches_db:
                        for identity,seed in seeds.items():
                            if identity in unsafe or identity not in accepted:
                                reason=unsafe.get(identity) or refused.get(identity,{}).get('reason','unresolved-source-neighbourhood')
                                matches_db.execute('INSERT INTO rejected VALUES(?,?,?)',(identity,reason,canonical({**refused.get(identity,{}),**unsafe_details.get(identity,{})})));statistics['rejected']+=1;continue
                            key,row=accepted[identity];proof={k:v for k,v in row.items() if k!='cells'}
                            ign_source=ign_db.execute('SELECT content_sha256 FROM objects WHERE ign_id=?',(row['ignId'],)).fetchone()
                            proof.update(heightKind='eaves',heightMeaning=ign['heightMeaning'],ignSourceSHA256=ign['sourceSHA256'],ignFeatureSHA256=ign_source[0],partition=partition,internalAlgorithmProofSHA256=report['proofSHA256'],runtimeCellBindingsPresent=False)
                            matches_db.execute('INSERT INTO matches VALUES(?,?,?,?,?,?,?,?,?)',(key,identity,row['geometrySHA256'],row['sourceSHA256'],canonical(proof),*seed[3:]));statistics['accepted']+=1
                        matches_db.execute('INSERT INTO partitions VALUES(?,?,?,?,?)',(partition,report['proofSHA256'],len(seeds),len(all_osm),len(ign_rows)))
                    statistics.update(partitions=statistics['partitions']+1,seedBuildings=statistics['seedBuildings']+len(seeds),peakOSMNeighbours=max(statistics['peakOSMNeighbours'],len(all_osm)),peakIGNCandidates=max(statistics['peakIGNCandidates'],len(ign_rows)))
                    log(json.dumps({'partition':partition,**statistics}))
            matches_db.execute('CREATE VIRTUAL TABLE match_index USING rtree(rowid,minx,maxx,miny,maxy)');matches_db.execute('INSERT INTO match_index SELECT rowid,minx,maxx,miny,maxy FROM matches');matches_db.commit()
        finally:
            matches_db.close();index.close()
        if core.file_sha256(osm_path)!=osm['canonicalStore']['sha256'] or core.file_sha256(ign_path)!=ign['sqliteSHA256']:raise CatalogueError('Source changed during matching; catalogue remains unsealed.')
        for path,key in ((osm_manifest,'osmManifestSHA256'),(ign_index,'ignSourceIndexFileSHA256'),(boundary_path,'boundarySHA256')):
            if core.file_sha256(path)!=snapshots[key]:raise CatalogueError('Source manifest/boundary changed during matching; catalogue remains unsealed.')
        if osm_rejection_proof is not None and core.file_sha256(osm_rejection_proof)!=envelope_file_sha:raise CatalogueError('Rejected-source proof changed during matching; catalogue remains unsealed.')
        seal={'schema':SCHEMA,'rejectionEnvelopeFileSHA256':envelope_file_sha,'osmManifestSHA256':snapshots['osmManifestSHA256'],'ignSourceIndexFileSHA256':snapshots['ignSourceIndexFileSHA256'],'sourceSHA256':osm['source']['sha256'],'osmCanonicalSHA256':osm['canonicalStore']['sha256'],'ignSourceSHA256':ign['sourceSHA256'],'ignSQLiteSHA256':ign['sqliteSHA256'],'boundarySHA256':snapshots['boundarySHA256'],'selectionBounds':list(requested.bounds),'limits':asdict(limits),'statistics':statistics,'sourceRejections':rejection_proof,'policy':{'minimumIoU':.90,'minimumMargin':.15,'minimumReciprocalMargin':.15,'completeCandidateClosure':True,'preserveExplicitOSMHeight':True,'excludeActiveOSMParts':True},'matches':{'path':'matches.sqlite','sha256':core.file_sha256(output/'matches.sqlite'),'bytes':(output/'matches.sqlite').stat().st_size},'derivedIGNIndex':{'path':'ign-spatial.sqlite','sha256':core.file_sha256(output/'ign-spatial.sqlite')},'heightKind':'eaves','matcherFileSHA256':core.file_sha256(Path(__file__).with_name('building_heights.py')),'adapterFileSHA256':core.file_sha256(Path(__file__)),'runtimeCellBindingsPresent':False,'matchingCompleteForSelectedOwners':True,'completeMetropole':False,'runtimeIntegrationPerformed':False}
        seal['sealSHA256']=digest(seal);save(output/'seal.json',seal);return seal
    finally:
        osm_db.close();ign_db.close()


def sidecars(seal_path,vector_manifest,output):
    seal_path,vector_manifest,output=map(Path,(seal_path,vector_manifest,output));seal,seal_file_sha=read_hashed(seal_path,16*1024*1024)
    if not isinstance(seal,dict):raise CatalogueError('Canonical height seal must be an object.')
    if seal.get('schema')!=SCHEMA or seal.get('sealSHA256')!=digest({k:v for k,v in seal.items() if k!='sealSHA256'}):raise CatalogueError('Canonical height seal differs.')
    dbpath=asset(seal_path.parent,seal['matches']['path'])
    if core.file_sha256(dbpath)!=seal['matches']['sha256']:raise CatalogueError('Canonical height catalogue hash differs.')
    manifest,vector_manifest_sha=read_hashed(vector_manifest)
    if not isinstance(manifest,dict):raise CatalogueError('Cell manifest must be an object.')
    if manifest.get('schema')!='soma-metropole/vector-tiles/1' or manifest.get('crs')!='EPSG:2154' or manifest.get('units')!='m' or manifest.get('source',{}).get('sha256')!=seal['sourceSHA256']:raise CatalogueError('Cell source snapshot/frame differs.')
    if output.exists():raise CatalogueError('Sidecar output exists.')
    output.mkdir(parents=True);db=readonly(dbpath);tiles=[];source_tiles={}
    try:
        for tile in manifest['tiles']:
            desc=tile['vector'];path=asset(vector_manifest.parent,desc['path'])
            if type(desc.get('bytes')) is not int or not 0<desc['bytes']<=16*1024*1024 or path.stat().st_size!=desc['bytes']:raise CatalogueError('Vector tile hash/size differs.')
            with path.open('rb') as stream:compressed=stream.read(16*1024*1024+1)
            if len(compressed)!=desc['bytes'] or hashlib.sha256(compressed).hexdigest()!=desc['sha256']:raise CatalogueError('Vector tile hash/size differs.')
            source_tiles[path]=desc['sha256']
            with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:raw=stream.read(16*1024*1024+1)
            if len(raw)>16*1024*1024 or len(raw)!=desc['decodedBytes']:raise CatalogueError('Decoded vector tile size differs.')
            record=json.loads(raw)
            if record.get('schema')!='soma-massilia/geodata-cell/4' or record.get('v53Synthetic') or record.get('v50Synthetic') or record.get('testOnly') or record.get('cellId')!=tile['cellId'] or record.get('sourceReceipt',{}).get('sha256')!=seal['sourceSHA256'] or record.get('contentSHA256')!=digest(record.get('featureCollection')):raise CatalogueError('Real cell content/source binding differs.')
            matches={}
            for feature in record['featureCollection']['features']:
                props=feature.get('properties',{})
                if props.get('soma:layer')!='buildings' or core._osm_priority(props):continue
                key=core.binding_key(props.get('canonical_id') or feature.get('id'),props.get('soma:geometry_sha256'),seal['sourceSHA256'])
                row=db.execute('SELECT proof_json FROM matches WHERE binding=?',(key,)).fetchone()
                if row:
                    proof=json.loads(row[0])
                    if proof.get('sourceSHA256')!=seal['sourceSHA256'] or proof.get('canonicalId')!=(props.get('canonical_id') or feature.get('id')) or proof.get('geometrySHA256')!=props.get('soma:geometry_sha256') or proof.get('heightKind')!='eaves':raise CatalogueError('Canonical height source/geometry binding differs.')
                    matches[key]=proof
            sidecar={'schema':'soma-metropole/building-height-cell/1','cellId':record['cellId'],'contentSHA256':record['contentSHA256'],'vectorSHA256':desc['sha256'],'sourceSHA256':seal['sourceSHA256'],'catalogueSealSHA256':seal['sealSHA256'],'sourceMatchingManifestSHA256':seal['osmManifestSHA256'],'currentVectorManifestSHA256':vector_manifest_sha,'heightKind':'eaves','matches':matches,'runtimeIntegrationPerformed':False}
            sidecar['proofSHA256']=digest(sidecar);encoded=canonical(sidecar).encode();relative='cells/'+record['cellId']+'.json.gz';target=asset(output,relative);target.parent.mkdir(exist_ok=True)
            with target.open('wb') as stream:
                with gzip.GzipFile(fileobj=stream,mode='wb',mtime=0,filename='') as archive:archive.write(encoded)
            tiles.append({'cellId':record['cellId'],'contentSHA256':record['contentSHA256'],'path':relative,'sha256':core.file_sha256(target),'bytes':target.stat().st_size,'matchedFragments':len(matches)})
    finally:db.close()
    for path,sha in [(seal_path,seal_file_sha),(vector_manifest,vector_manifest_sha),(dbpath,seal['matches']['sha256']),*source_tiles.items()]:
        if core.file_sha256(path)!=sha:raise CatalogueError('Source changed during sidecar preparation; manifest remains unpublished.')
    result={'schema':'soma-metropole/building-height-sidecars/1','sourceSHA256':seal['sourceSHA256'],'catalogueSealSHA256':seal['sealSHA256'],'sourceMatchingManifestSHA256':seal['osmManifestSHA256'],'currentVectorManifestSHA256':vector_manifest_sha,'vectorBindingPolicy':'Same source PBF, exact canonical identity/geometry and real cell content hashes; another verified tile partition is allowed.','tiles':tiles,'runtimeIntegrationPerformed':False};result['manifestSHA256']=digest(result);save(output/'manifest.json',result);return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    match=sub.add_parser('match');match.add_argument('--osm-manifest',type=Path,required=True);match.add_argument('--ign-index',type=Path,required=True);match.add_argument('--boundary',type=Path,required=True);match.add_argument('--osm-pbf',type=Path);match.add_argument('--osm-rejection-proof',type=Path);match.add_argument('--output',type=Path,required=True);match.add_argument('--bounds-l93',type=float,nargs=4);match.add_argument('--step',type=int,default=1000);match.add_argument('--max-osm',type=int,default=20000);match.add_argument('--max-ign',type=int,default=20000)
    cells=sub.add_parser('sidecars');cells.add_argument('--seal',type=Path,required=True);cells.add_argument('--vectors',type=Path,required=True);cells.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:
        result=match_catalogues(args.osm_manifest,args.ign_index,args.boundary,args.output,bounds=args.bounds_l93,limits=Limits(step=args.step,max_osm=args.max_osm,max_ign=args.max_ign),osm_pbf=args.osm_pbf,osm_rejection_proof=args.osm_rejection_proof,log=lambda v:print(v,flush=True)) if args.command=='match' else sidecars(args.seal,args.vectors,args.output)
        print(json.dumps(result.get('statistics',{'tiles':len(result.get('tiles',[]))})))
    except (OSError,ValueError,RuntimeError,sqlite3.Error,ImportError) as error:parser.exit(1,f'Catalogue height preparation refused: {error}\n')


if __name__=='__main__':main()
