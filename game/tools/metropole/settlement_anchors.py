#!/usr/bin/env python3
"""Source-place destinations inside official commune contours, never addresses.

Only city/town/village OSM point features qualify. Contour fallback stays explicit
when a named place is absent, ambiguous, outside its commune or unpublished.
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
import unicodedata

GAME=Path(__file__).resolve().parents[2]
if str(GAME) not in sys.path:sys.path.insert(0,str(GAME))
from tools.metropole import building_parts as B
from tools.metropole import match_catalogues as C
from tools.metropole.bootstrap import load_territory_reference

SCHEMA='soma-metropole/settlement-anchors/1'
PLACES={'city','town','village'}
MAX_TILE=16*1024*1024


def normalized(value):
    text=unicodedata.normalize('NFKD',str(value).casefold().replace('œ','oe').replace('æ','ae'))
    return ''.join(c for c in text if c.isalnum() and not unicodedata.combining(c))


def choose_anchor(code,name,candidates,admin_centres):
    """All candidates supplied here have passed the point-inside-commune check."""
    eligible=[]
    for candidate in candidates:
        p=candidate['properties'];ref=p.get('ref:INSEE')
        if p.get('place') not in PLACES or ref is not None and ref!=code:continue
        by_ref=ref==code
        by_name=any(normalized(p.get(key,''))==normalized(name) for key in ('name','official_name'))
        if by_ref or by_name:eligible.append((candidate,'ref:INSEE' if by_ref else 'official-name-normalized'))
    if len(eligible)==1:return eligible[0],eligible
    if len(eligible)>1:
        linked=[pair for pair in eligible if pair[0]['canonicalId'] in admin_centres]
        if len(linked)==1:return (linked[0][0],'admin_centre-tiebreak'),eligible
    return None,eligible


def build_anchors(manifest_path,territory_path,contours_path,output_path):
    import shapely
    from shapely.geometry import shape,mapping
    from tools.metropole import import_tiles as I
    manifest_path,territory_path,contours_path,output_path=map(Path,(manifest_path,territory_path,contours_path,output_path))
    if output_path.exists():raise ValueError('Settlement table already exists; preserve its published evidence.')
    manifest,manifest_sha=C.read_hashed(manifest_path)
    territory,territory_sha,boundary_sha=load_territory_reference(territory_path)
    contours,contours_sha=C.read_hashed(contours_path,8*1024*1024)
    if contours_sha!=territory['boundary']['source']['sha256']:raise ValueError('Commune contour source hash differs from the administrative receipt.')
    if (manifest.get('schema')!='soma-metropole/vector-tiles/1' or manifest.get('crs')!='EPSG:2154' or
            manifest.get('units')!='m' or manifest.get('origin')!=list(I.ORIGIN) or manifest.get('cellSize')!=250):raise ValueError('Published historical source vector tiles required.')
    source_sha=manifest.get('source',{}).get('sha256')
    if not isinstance(source_sha,str) or not re.fullmatch('[a-f0-9]{64}',source_sha):raise ValueError('Source PBF SHA256 required.')
    communes={row['code']:row for row in territory['communes']}
    polygons={feature['properties']['code']:shape(feature['geometry']) for feature in contours['features']}
    if len(polygons)!=92 or set(polygons)!=set(communes) or any(p.is_empty or not p.is_valid for p in polygons.values()):raise ValueError('Exactly 92 valid official commune geometries required.')
    descriptor=manifest['canonicalStore'];native_path=C.asset(manifest_path.parent,descriptor['path'])
    if native_path.stat().st_size!=descriptor['bytes'] or B._file_sha256(native_path)!=descriptor['sha256']:raise ValueError('Published native catalogue size/SHA differs.')
    tiles={tile['cellId']:tile for tile in manifest['tiles']};db=C.readonly(native_path)
    try:
        candidates=[]
        for identity,encoded,wkb in db.execute("SELECT id,properties,geometry FROM features WHERE json_extract(properties,'$.place') IN ('city','town','village') ORDER BY id"):
            p=json.loads(encoded);g=shapely.from_wkb(wkb)
            if not re.fullmatch(r'osm/node/[1-9]\d*',identity) or g.geom_type!='Point' or g.is_empty:continue
            if p.get('canonical_id')!=identity or p.get('soma:geometry_sha256')!=B.digest(mapping(g)):raise ValueError('Native settlement geometry identity differs.')
            candidates.append({'canonicalId':identity,'properties':p,'geometry':g})
            if len(candidates)>10000:raise ValueError('Source place candidate budget exceeded.')
        centres={code:{} for code in communes}
        for relation_id,tags,members in db.execute("SELECT id,tags,members FROM source_relations WHERE json_extract(tags,'$.boundary')='administrative' AND json_extract(tags,'$.admin_level')='8'"):
            tags=json.loads(tags);code=tags.get('ref:INSEE')
            if code not in communes:continue
            for member in json.loads(members):
                if member.get('type') in ('node','n') and member.get('role')=='admin_centre':
                    centres[code].setdefault('osm/node/'+str(member['ref']),[]).append('osm/relation/'+str(relation_id))
        anchors={};features={};assets={}
        for code,commune in sorted(communes.items()):
            name=commune['nom'];polygon=polygons[code]
            # This inverse is used only to test candidates against the contour.
            # Delivered WGS84 coordinates are copied from the real vector feature.
            inside=[c for c in candidates if polygon.contains(shape({'type':'Point','coordinates':I.TO_WGS84.transform(c['geometry'].x,c['geometry'].y)}))]
            selected,eligible=choose_anchor(code,name,inside,centres[code])
            fallback={'code':code,'name':name,'status':'contour-fallback','evidence':{
                'reason':'ambiguous-source-place' if eligible else 'no-unique-source-place',
                'candidateIds':[pair[0]['canonicalId'] for pair in eligible], 'withinCommune':True}}
            if selected is None:anchors[code]=fallback;continue
            candidate,method=selected;identity=candidate['canonicalId'];point=candidate['geometry'];p=candidate['properties']
            x,y=next(iter(I.grid_cells(point.bounds)));cell=I.cell_id(x,y);tile=tiles.get(cell)
            if tile is None:
                fallback['evidence']['reason']='source-point-cell-unpublished';anchors[code]=fallback;continue
            desc=tile['vector'];path=C.asset(manifest_path.parent,desc['path'])
            if desc.get('encoding')!='gzip-json' or type(desc.get('bytes')) is not int or not 0<desc['bytes']<=MAX_TILE or path.stat().st_size!=desc['bytes']:raise ValueError('Settlement source cell size/encoding differs.')
            packed=path.read_bytes()
            if hashlib.sha256(packed).hexdigest()!=desc['sha256']:raise ValueError('Settlement source cell SHA256 differs.')
            with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:raw=stream.read(MAX_TILE+1)
            if len(raw)>MAX_TILE or len(raw)!=desc['decodedBytes']:raise ValueError('Settlement source cell exceeds its decoded byte budget.')
            record=json.loads(raw);collection=record.get('featureCollection')
            if (record.get('cellId')!=cell or record.get('sourceReceipt',{}).get('sha256')!=source_sha or
                    any(record.get(k) for k in ('testOnly','v53Synthetic','v50Synthetic')) or
                    record.get('contentSHA256')!=B.digest(collection)):raise ValueError('Settlement source cell content/source binding differs.')
            found=[f for f in collection['features'] if (f.get('properties',{}).get('canonical_id') or f.get('id'))==identity]
            if len(found)!=1:raise ValueError('Settlement node must occur exactly once in its real source cell.')
            feature=found[0];fp=feature['properties'];g=feature.get('geometry',{});metric=fp.get('soma:metricGeometry',{})
            ll=g.get('coordinates');l93=metric.get('coordinates')
            if (g.get('type')!='Point' or metric.get('type')!='Point' or not isinstance(ll,list) or len(ll)!=2 or
                    not isinstance(l93,list) or len(l93)!=2 or any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in ll+l93) or
                    fp.get('soma:geometry_sha256')!=p['soma:geometry_sha256'] or B.digest(metric)!=p['soma:geometry_sha256'] or
                    l93!=[point.x,point.y] or fp.get('place') not in PLACES or fp.get('place')!=p.get('place') or
                    fp.get('name')!=p.get('name') or not polygon.contains(shape(g))):raise ValueError('Settlement real point geometry/name/place differs from the native source or commune.')
            node_id=int(identity.rsplit('/',1)[1]);relations=centres[code].get(identity,[])
            anchors[code]={'code':code,'name':name,'status':'source-place','canonicalId':identity,'nodeId':node_id,
                'pointWGS84':ll,'pointL93':l93,'sourcePbfSHA256':source_sha,'vectorManifestSHA256':manifest_sha,
                'cellId':cell,'contentSHA256':record['contentSHA256'],'cellContentSHA256':record['contentSHA256'],
                'geometrySHA256':p['soma:geometry_sha256'],'evidence':{'canonicalId':identity,'nodeId':node_id,'matchedBy':method,
                    'refINSEE':p.get('ref:INSEE'),'place':p['place'],'sourceName':p.get('name'),
                    'withinCommune':True,'unique':True,'adminCentreRelations':relations,
                    'candidateIds':[pair[0]['canonicalId'] for pair in eligible]}}
            features[identity]=feature;assets[path]=desc['sha256']
        for path,sha in [(manifest_path,manifest_sha),(native_path,descriptor['sha256']),(contours_path,contours_sha),
                         (territory_path,territory_sha),*assets.items()]:
            if B._file_sha256(path)!=sha:raise ValueError('Settlement source changed during preparation; no table published.')
        feature_collection={'type':'FeatureCollection','features':[features[key] for key in sorted(features)]}
        feature_bytes=B.canonical(feature_collection).encode('utf-8')
        count=sum(row['status']=='source-place' for row in anchors.values())
        result={'schema':SCHEMA,'version':'0.69.0','sourcePbfSHA256':source_sha,'vectorManifestSHA256':manifest_sha,
                'boundarySHA256':boundary_sha,'territorySHA256':territory_sha,
                'sources':{'communeContours':{'path':'acquisition/'+contours_path.name,'sha256':contours_sha,'bytes':contours_path.stat().st_size},
                    'vectorManifest':{'sha256':manifest_sha,'bytes':manifest_path.stat().st_size,'receiptOnly':True},
                    'canonicalStore':{'sha256':descriptor['sha256'],'bytes':descriptor['bytes'],'receiptOnly':True},
                    'pointFeatures':{'encoding':'inline-json','sha256':hashlib.sha256(feature_bytes).hexdigest(),'bytes':len(feature_bytes),'featureCollection':feature_collection}},
                'anchors':anchors,'coverage':{'communeCodes':sorted(communes),'communeCount':len(communes),
                    'sourcePointCount':count,'contourFallbackCount':len(communes)-count},
                'selectionPolicy':'Only city/town/village nodes inside the official commune; exact ref:INSEE or normalized official name; unique admin_centre may resolve ambiguity.',
                'meaning':'Named settlement point destinations, not street addresses or surveyed urban centres. Missing/ambiguous points use an explicit administrative-contour fallback.',
                'geometryModified':False,'certifiedOneToOne':False}
        result['proofSHA256']=B.digest(result)
        output_path.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.NamedTemporaryFile('w',dir=output_path.parent,encoding='utf-8',delete=False,prefix=output_path.name+'.') as stream:
            temporary=Path(stream.name);stream.write(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n')
        try:temporary.replace(output_path)
        finally:temporary.unlink(missing_ok=True)
        return result
    finally:db.close()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--territory',type=Path,default=GAME/'data/v69/territory.json')
    p.add_argument('--contours',type=Path,default=GAME/'data/v69/acquisition/amp-communes-2026-10-25.geojson')
    p.add_argument('--output',type=Path,default=GAME/'data/v69/settlement-anchors.json');a=p.parse_args()
    r=build_anchors(a.manifest,a.territory,a.contours,a.output)
    print(json.dumps({'coverage':r['coverage'],'proofSHA256':r['proofSHA256']},ensure_ascii=False))


if __name__=='__main__':main()
