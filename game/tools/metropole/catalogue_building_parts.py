#!/usr/bin/env python3
"""Prepare complete, source-bound building/part components without loading a city.

The native catalogue closes all possible parent associations first. Each connected
component reads only its real footprint cells; incomplete components are withheld.
No generic parent, missing wall, repaired polygon or residual volume is generated.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict, dataclass
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import sys
import tempfile

GAME=Path(__file__).resolve().parents[2]
if str(GAME) not in sys.path:sys.path.insert(0,str(GAME))
from tools.metropole import building_parts as parts
from tools.metropole import match_catalogues as catalogues


class PartsCatalogueError(ValueError):
    pass


@dataclass(frozen=True)
class Limits:
    max_components:int=20000
    max_objects_per_component:int=10000
    max_cells_per_component:int=2048
    max_decoded_bytes_per_component:int=128*1024*1024
    max_tile_bytes:int=16*1024*1024

    def validate(self):
        if any(type(v) is not int or v<=0 for v in asdict(self).values()):raise PartsCatalogueError('Positive component budgets required.')
        return self


def active(value):return value is not None and str(value).strip().lower() not in parts.FALSE
def is_part(p):return active(p.get('building:part'))
def is_parent(p):return active(p.get('building')) and str(p.get('building')).strip().lower()!='roof' and not is_part(p)


def relations(db,pbf,source_sha):
    rows=[{'id':identity,'tags':json.loads(tags),'members':json.loads(members)}
          for identity,tags,members in db.execute("SELECT id,tags,members FROM source_relations WHERE json_extract(tags,'$.type')='building' ORDER BY id")]
    def normalized(items):
        types={'w':'way','r':'relation','n':'node','way':'way','relation':'relation','node':'node'}
        return [{'id':int(row['id']),'tags':row['tags'],'members':[
            {'type':types[m['type']],'ref':str(m['ref']),'role':m['role']} for m in row['members']]} for row in sorted(items,key=lambda r:int(r['id']))]
    rows=normalized(rows)
    if pbf is not None:
        if parts._file_sha256(pbf)!=source_sha:raise PartsCatalogueError('Relation PBF SHA256 differs from the vector source.')
        if normalized(parts._read_building_relations(pbf))!=rows:raise PartsCatalogueError('Canonical building relations differ from the original PBF.')
    return rows


def prepare_parts(manifest_path,output_path,*,pbf=None,bounds=None,part_ids=None,parent_ids=None,limits=None,
                  osm_rejection_proof=None,boundary_path=None,log=print):
    from shapely import from_wkb
    from shapely.geometry import Polygon,box,mapping
    from shapely.ops import unary_union
    from tools.metropole.import_tiles import ORIGIN,cell_id,grid_cells,cell_bounds
    limits=(limits or Limits()).validate();manifest_path=Path(manifest_path);output_path=Path(output_path)
    if output_path.exists():raise PartsCatalogueError('Output exists; preserve the published building proof.')
    manifest,manifest_sha=catalogues.read_hashed(manifest_path)
    if (manifest.get('schema')!='soma-metropole/vector-tiles/1' or manifest.get('crs')!='EPSG:2154' or
            manifest.get('units')!='m' or manifest.get('origin')!=list(ORIGIN) or manifest.get('cellSize')!=250):
        raise PartsCatalogueError('Published historical metric vector tiles required.')
    source_sha=manifest.get('source',{}).get('sha256');desc=manifest.get('canonicalStore',{})
    if not isinstance(source_sha,str) or not catalogues.core.HASH.fullmatch(source_sha):raise PartsCatalogueError('Source PBF SHA256 required.')
    native_path=catalogues.asset(manifest_path.parent,desc.get('path'))
    if desc.get('encoding')!='sqlite3' or native_path.stat().st_size!=desc.get('bytes') or parts._file_sha256(native_path)!=desc.get('sha256'):
        raise PartsCatalogueError('Native catalogue hash/size differs.')
    db=catalogues.readonly(native_path)
    try:
        scope=None;boundary_sha=None;boundary_file=None;envelope_doc=None;envelope_file_sha=None
        boundary=manifest.get('boundary')
        if boundary is not None:
            boundary_file=Path(boundary_path or boundary['path'])
            if not boundary_file.is_absolute():boundary_file=catalogues.asset(manifest_path.parent,str(boundary_file))
            boundary_doc,boundary_sha=catalogues.read_hashed(boundary_file,16*1024*1024)
            if boundary_sha!=boundary.get('sha256'):raise PartsCatalogueError('Administrative selection boundary SHA256 differs.')
            scope=catalogues.boundary_geometry(boundary_file,document=boundary_doc)
        if osm_rejection_proof is not None:
            envelope_doc,envelope_file_sha=catalogues.read_hashed(osm_rejection_proof,16*1024*1024)
            if scope is None or envelope_doc.get('osmManifestSHA256')!=manifest_sha:
                raise PartsCatalogueError('Rejected-source proof must bind this exact manifest and administrative boundary.')
        rejection_proof=catalogues.check_rejections(db,source_sha,pbf,envelope_proof=envelope_doc,
            canonical_store_sha=desc['sha256'],boundary_sha=boundary_sha,scope=scope)
        local_blockers=[(row['canonicalId'],catalogues.envelope_geometry(row['boundsL93']))
                        for row in rejection_proof['localBuildingBlockers']]
        relation_rows=relations(db,pbf,source_sha)
        links,unused=parts._relation_links(relation_rows)
        ambiguous_relations={}
        for relation in relation_rows:
            outlines=[m for m in relation['members'] if m['role']=='outline' and m['type'] in ('way','relation')]
            if len(outlines)>1:
                for member in relation['members']:
                    if member['role']=='part' and member['type'] in ('way','relation'):
                        ambiguous_relations.setdefault('osm/'+member['type']+'/'+member['ref'],[]).append(relation['id'])
        parent_parts={}
        for identity,parents in links.items():
            for parent in parents:parent_parts.setdefault(parent,set()).add(identity)
        tiles={tile['cellId']:tile for tile in manifest['tiles']}
        if len(tiles)!=len(manifest['tiles']):raise PartsCatalogueError('Duplicate real cell identity.')
        cache={}
        def native(identity):
            if identity in cache:return cache[identity]
            row=db.execute("SELECT properties,geometry FROM features WHERE id=? AND layer='buildings'",(identity,)).fetchone()
            if row is None:raise PartsCatalogueError('Missing native building/part required by the component: '+identity)
            p=json.loads(row[0]);geometry=from_wkb(row[1])
            if (p.get('canonical_id')!=identity or geometry.geom_type not in ('Polygon','MultiPolygon') or
                    geometry.is_empty or not geometry.is_valid or parts.digest(mapping(geometry))!=p.get('soma:geometry_sha256')):
                raise PartsCatalogueError('Unverifiable native footprint: '+identity)
            cache[identity]=(p,geometry);return p,geometry
        def neighbours(geometry,*,part):
            w,s,e,n=geometry.bounds
            for identity,encoded in db.execute("SELECT f.id,f.properties FROM features f JOIN feature_index i ON f.rowid=i.rowid WHERE f.layer='buildings' AND i.minx<=? AND i.maxx>=? AND i.miny<=? AND i.maxy>=? ORDER BY f.id",(e,w,n,s)):
                p=json.loads(encoded)
                if is_part(p) if part else is_parent(p):yield identity
        selected=set(part_ids or [])|set(parent_ids or [])
        if bounds is not None:
            if len(bounds)!=4 or any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in bounds) or bounds[0]>=bounds[2] or bounds[1]>=bounds[3]:raise PartsCatalogueError('Invalid seed-selection bounds.')
            selection=box(*bounds)
            if scope is not None:selection=selection.intersection(scope)
        else:selection=scope
        if not selected:
            for identity,encoded in db.execute("SELECT id,properties FROM features WHERE layer='buildings' AND json_extract(properties,'$.\"building:part\"') IS NOT NULL ORDER BY id"):
                if is_part(json.loads(encoded)) and (selection is None or native(identity)[1].intersects(selection)):selected.add(identity)
        proof={'schema':parts.SCHEMA,'sourceSHA256':source_sha,'certified':False,'fullSuppressionThreshold':parts.MIN_COVERAGE,
               'parents':{},'partParents':{},'ambiguities':[],'withheldGeometry':[],
               'relationsEvidenceSHA256':parts.digest(relation_rows),'relationsSourceSHA256':source_sha}
        seen=set();components=[];all_cells={};source_assets={};peak_cells=peak_bytes=0
        for seed in sorted(selected):
            if seed in seen:continue
            if len(components)>=limits.max_components:raise PartsCatalogueError('Component count budget exceeded.')
            cache.clear();component=set();pending=[seed]
            try:
                while pending:
                    identity=pending.pop()
                    if identity in component:continue
                    component.add(identity)
                    if len(component)>limits.max_objects_per_component:raise PartsCatalogueError('Native component object budget exceeded.')
                    p,geometry=native(identity)
                    conflicts=[key for key,envelope in local_blockers
                               if geometry.intersects(envelope) or geometry.envelope.intersects(envelope)]
                    if conflicts:raise PartsCatalogueError('Source component touches unclosed-building envelope: '+','.join(conflicts))
                    if is_part(p):
                        if identity in ambiguous_relations:raise PartsCatalogueError('Ambiguous explicit building-relation outlines for '+identity)
                        candidates=set(links.get(identity,()))
                        for candidate in candidates:
                            if not is_parent(native(candidate)[0]):raise PartsCatalogueError('Explicit relation outline is not an eligible native parent: '+candidate)
                        candidates.update(candidate for candidate in neighbours(geometry,part=False) if native(candidate)[1].covers(geometry))
                    elif is_parent(p):
                        candidates=set(parent_parts.get(identity,()))
                        candidates.update(candidate for candidate in neighbours(geometry,part=True) if geometry.covers(native(candidate)[1]))
                    else:raise PartsCatalogueError('Seed is neither a source building parent nor an active part: '+identity)
                    pending.extend(candidates-component)
                seen.update(component)
                needed=set()
                for identity in component:
                    geometry=native(identity)[1]
                    for x,y in grid_cells(geometry.bounds):
                        if geometry.intersection(box(*cell_bounds(x,y))).area>1e-8:needed.add(cell_id(x,y))
                if len(needed)>limits.max_cells_per_component:raise PartsCatalogueError('Real footprint cell budget exceeded.')
                records=[];views=[];byte_count=0;fragments={identity:[] for identity in component}
                for cell in sorted(needed):
                    tile=tiles.get(cell)
                    if tile is None:raise PartsCatalogueError('A complete native footprint cell is not published: '+cell)
                    descriptor=tile['vector'];path=catalogues.asset(manifest_path.parent,descriptor['path'])
                    if (descriptor.get('encoding')!='gzip-json' or type(descriptor.get('bytes')) is not int or
                            not 0<descriptor['bytes']<=limits.max_tile_bytes or path.stat().st_size!=descriptor['bytes']):raise PartsCatalogueError('Source cell encoding/size budget differs.')
                    compressed=path.read_bytes()
                    if hashlib.sha256(compressed).hexdigest()!=descriptor['sha256']:raise PartsCatalogueError('Source cell SHA256 differs.')
                    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:raw=stream.read(limits.max_tile_bytes+1)
                    byte_count+=len(raw)
                    if len(raw)>limits.max_tile_bytes or len(raw)!=descriptor['decodedBytes'] or byte_count>limits.max_decoded_bytes_per_component:raise PartsCatalogueError('Decoded source component byte budget exceeded.')
                    record=json.loads(raw);collection=record.get('featureCollection')
                    if (record.get('schema')!='soma-massilia/geodata-cell/4' or record.get('cellId')!=cell or
                            record.get('sourceReceipt',{}).get('sha256')!=source_sha or
                            any(record.get(k) for k in ('v53Synthetic','v50Synthetic','testOnly')) or
                            record.get('contentSHA256')!=parts.digest(collection) or record.get('boundsL93')!=tile['boundsL93']):raise PartsCatalogueError('Real source cell/content/geometry binding differs.')
                    chosen=[]
                    for feature in collection['features']:
                        p=feature.get('properties',{});identity=p.get('canonical_id') or feature.get('id')
                        if identity not in component:continue
                        if p.get('soma:geometry_sha256')!=native(identity)[0].get('soma:geometry_sha256'):raise PartsCatalogueError('Clipped source feature geometry identity differs.')
                        for mesh in p.get('soma:mesh53',[]):
                            rings=mesh.get('ringsL93',[])
                            if not rings:raise PartsCatalogueError('Source footprint mesh missing.')
                            polygon=Polygon(rings[0],rings[1:])
                            if polygon.is_empty or not polygon.is_valid:raise PartsCatalogueError('Source footprint fragment invalid.')
                            fragments[identity].append(polygon)
                        chosen.append(feature)
                    records.append(record)
                    views.append({**record,'featureCollection':{'type':'FeatureCollection','features':chosen},'sourceRecordView':'selected native component; contentSHA256 binds the unmodified full source cell'})
                    all_cells[cell]=record['contentSHA256'];source_assets[path]=descriptor['sha256']
                for identity,polygons in fragments.items():
                    if not polygons:raise PartsCatalogueError('Native component has no real source footprint: '+identity)
                    actual=unary_union(polygons);expected=native(identity)[1]
                    if not actual.is_valid or actual.symmetric_difference(expected).area>max(.001,expected.area*1e-8) or actual.hausdorff_distance(expected)>1e-5:
                        raise PartsCatalogueError('Native footprint is not completely represented by the selected real cells: '+identity)
                child=parts.generate_parts(views,source_sha=source_sha,relations=relation_rows,relations_source_sha=source_sha)
                # Missing candidate geometry must never make another parent look unique.
                if child['withheldGeometry']:raise PartsCatalogueError('Strict footprint-completeness proof refused source component geometry.')
                parts.loadproof(child,records=records,source_sha=source_sha)
                for key in ('parents','partParents'):proof[key].update(child[key])
                for key in ('ambiguities','withheldGeometry'):proof[key].extend(child[key])
                peak_cells=max(peak_cells,len(records));peak_bytes=max(peak_bytes,byte_count)
                components.append({'seed':seed,'objects':len(component),'cells':len(needed),'status':'source-bound','parentCount':len(child['parents'])})
            except (PartsCatalogueError,ValueError) as error:
                seen.update(component);proof['withheldGeometry'].append({'id':seed,'reason':'incomplete-or-unverifiable-source-component','detail':str(error)})
                components.append({'seed':seed,'objects':len(component),'status':'withheld','reason':str(error)})
            log(json.dumps(components[-1]))
        if parts._file_sha256(native_path)!=desc['sha256'] or parts._file_sha256(manifest_path)!=manifest_sha:raise PartsCatalogueError('Source catalogue/manifest changed; proof remains unpublished.')
        if pbf is not None and parts._file_sha256(pbf)!=source_sha:raise PartsCatalogueError('Original relation PBF changed; proof remains unpublished.')
        if boundary_file is not None and parts._file_sha256(boundary_file)!=boundary_sha:raise PartsCatalogueError('Administrative boundary changed; proof remains unpublished.')
        if osm_rejection_proof is not None and parts._file_sha256(osm_rejection_proof)!=envelope_file_sha:raise PartsCatalogueError('Rejected-source proof changed; proof remains unpublished.')
        for path,sha in source_assets.items():
            if parts._file_sha256(path)!=sha:raise PartsCatalogueError('Source tile changed; proof remains unpublished.')
        for parent in proof['parents'].values():
            parent.update(residualPolicy='unresolved-footprint-only',residualVolumetric=False,residualCollision=False)
        proof['statistics']={'fullParents':sum(p['suppressParent'] for p in proof['parents'].values()),
                             'partialParents':sum(not p['suppressParent'] for p in proof['parents'].values()),'associatedParts':len(proof['partParents']),
                             'groundParts':sum(len(p['groundPartIds']) for p in proof['parents'].values())}
        proof['selectionProvenance']={'vectorManifestSHA256':manifest_sha,'canonicalStoreSHA256':desc['sha256'],
            'boundarySHA256':boundary_sha,'rejectionEnvelopeFileSHA256':envelope_file_sha,
            'selectionToolSHA256':parts._file_sha256(Path(__file__)),
            'buildingPartsToolSHA256':parts._file_sha256(Path(parts.__file__)),
            'selectionBoundsL93':bounds,'seedIds':sorted(selected),'components':components,'sourceCellHashes':all_cells,
            'nativeNeighbourClosure':'all source-containment and explicit-relation candidates, repeated for every parent and part',
            'fullNativeFootprintsChecked':all(c['status']=='source-bound' for c in components),
            'acceptedComponentsHaveCompleteNativeFootprints':True,'recordsValidatedPerComponent':True,'sourceRejections':rejection_proof,
            'relationsOrigin':'PBF verified against complete canonical source_relations' if pbf else 'complete canonical source_relations',
            'limits':asdict(limits),'peakLoadedCells':peak_cells,'peakDecodedCellBytes':peak_bytes}
        proof.update(residualPolicy='unresolved-footprint-only',completeMetropole=False,certifiedOneToOne=False,runtimeIntegrationPerformed=False)
        proof['proofSHA256']=parts.digest(proof);parts.loadproof(proof,source_sha=source_sha)
        output_path.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=output_path.parent,delete=False,prefix=output_path.name+'.') as stream:
            temporary=Path(stream.name);stream.write(json.dumps(proof,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n')
        try:
            if output_path.exists():raise PartsCatalogueError('Output appeared during preparation; preserve it.')
            temporary.rename(output_path)
        finally:temporary.unlink(missing_ok=True)
        return proof
    finally:db.close()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--pbf',type=Path);p.add_argument('--bounds-l93',type=float,nargs=4);p.add_argument('--part-id',action='append');p.add_argument('--parent-id',action='append')
    p.add_argument('--osm-rejection-proof',type=Path);p.add_argument('--boundary',type=Path)
    a=p.parse_args()
    result=prepare_parts(a.manifest,a.output,pbf=a.pbf,bounds=a.bounds_l93,part_ids=a.part_id,parent_ids=a.parent_id,
                         osm_rejection_proof=a.osm_rejection_proof,boundary_path=a.boundary,log=lambda value:print(value,flush=True))
    print(json.dumps({'output':str(a.output),'proofSHA256':result['proofSHA256'],**result['statistics']}))


if __name__=='__main__':main()
