#!/usr/bin/env python3
"""Build the independent offline flyover, without modifying the campaign build."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'SOMA_MASSILIA_URBAIN_v0_69.html'
TEMPLATE = ROOT/'src/v69/metropole-viewer.html'
OUTPUT = ROOT/'metropole-viewer.html'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def script(html, identifier, *, json_only=False):
    matches = [match[2] for match in re.finditer(
        r'<script\b([^>]*\bid="'+re.escape(identifier)+r'"[^>]*)>([\s\S]*?)</script>',html)
        if not json_only or re.search(r'\btype="application/json"',match[1])]
    if len(matches) != 1:
        raise ValueError(f'Script absent ou dupliqué : {identifier}')
    return matches[0]


def safe_relative(value):
    return isinstance(value,str) and bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]*',value)) and all(p not in ('','.','..') for p in value.split('/'))


def inside(point, ring):
    result = False
    for a,b in zip(ring,ring[1:]+ring[:1]):
        if (a[1]>point[1]) != (b[1]>point[1]) and point[0] < (b[0]-a[0])*(point[1]-a[1])/(b[1]-a[1])+a[0]:
            result = not result
    return result


def json_bytes(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')


def audited_settlement_anchors(table, communes, boundary_sha):
    """Audit a small sealed copy of real place features, independently of the
    currently selected world's PBF. No external catalogue is read at launch.
    """
    def fail():raise ValueError('Table des destinations incohérente avec ses preuves géographiques.')
    def hashed(value):return isinstance(value,str) and re.fullmatch('[a-f0-9]{64}',value) is not None
    def receipt(value):return isinstance(value,dict) and hashed(value.get('sha256')) and type(value.get('bytes')) is int and value['bytes']>0
    def point(value):return isinstance(value,list) and len(value)==2 and all(type(v) in (int,float) and math.isfinite(v) for v in value)
    def normalized(value):
        value=unicodedata.normalize('NFKD',str(value).casefold().replace('œ','oe').replace('æ','ae'))
        return ''.join(c for c in value if c.isalnum() and not unicodedata.combining(c))
    def contains(coordinates,geometry):
        polygons=[geometry['coordinates']] if geometry['type']=='Polygon' else geometry['coordinates']
        return any(inside(coordinates,p[0]) and not any(inside(coordinates,hole)for hole in p[1:]) for p in polygons)
    if not isinstance(table,dict) or table.get('schema')!='soma-metropole/settlement-anchors/1':fail()
    if not hashed(table.get('proofSHA256')) or sha(json_bytes({k:v for k,v in table.items()if k!='proofSHA256'}))!=table['proofSHA256']:fail()
    if table.get('boundarySHA256')!=boundary_sha or not hashed(table.get('sourcePbfSHA256')) or not hashed(table.get('vectorManifestSHA256')):fail()
    anchors=table.get('anchors');coverage=table.get('coverage',{});sources=table.get('sources',{})
    if not isinstance(anchors,dict) or set(anchors)!=set(communes) or coverage.get('communeCodes')!=sorted(communes) or coverage.get('communeCount')!=len(communes):fail()
    contours=sources.get('communeContours',{});vectors=sources.get('vectorManifest',{});catalogue=sources.get('canonicalStore',{})
    if not receipt(contours) or not safe_relative(contours.get('path')) or not receipt(vectors) or vectors.get('receiptOnly') is not True or vectors['sha256']!=table['vectorManifestSHA256'] or not receipt(catalogue) or catalogue.get('receiptOnly') is not True:fail()
    payload=sources.get('pointFeatures',{});collection=payload.get('featureCollection',{})
    if payload.get('encoding')!='inline-json' or not receipt(payload) or collection.get('type')!='FeatureCollection' or not isinstance(collection.get('features'),list):fail()
    encoded=json_bytes(collection)
    if len(encoded)!=payload['bytes'] or sha(encoded)!=payload['sha256']:fail()
    features={}
    for feature in collection['features']:
        identity=feature.get('id')
        if feature.get('type')!='Feature' or not isinstance(identity,str) or identity in features:fail()
        features[identity]=feature
    used=set();source_count=0
    for code,row in anchors.items():
        if not isinstance(row,dict) or row.get('code')!=code or row.get('name')!=communes[code]['name']:fail()
        evidence=row.get('evidence',{})
        if row.get('status')=='contour-fallback':
            if not isinstance(evidence.get('reason'),str) or not evidence['reason'] or any(row.get(k)is not None for k in ('canonicalId','nodeId','pointWGS84','pointL93')):fail()
            continue
        if row.get('status')!='source-place':fail()
        identity=row.get('canonicalId');node=row.get('nodeId');ll=row.get('pointWGS84');l93=row.get('pointL93')
        if type(node)is not int or node<=0 or identity!='osm/node/'+str(node) or identity in used or not point(ll) or not point(l93) or not(-180<=ll[0]<=180 and -90<=ll[1]<=90):fail()
        if row.get('sourcePbfSHA256')!=table['sourcePbfSHA256'] or row.get('vectorManifestSHA256')!=table['vectorManifestSHA256'] or not isinstance(row.get('cellId'),str) or not re.fullmatch(r'V52-MC-(?:[1-5][1-5]|[EW]\d{2,4}-[NS]\d{2,4})',row['cellId']):fail()
        if not hashed(row.get('cellContentSHA256')) or row.get('contentSHA256')!=row['cellContentSHA256'] or not hashed(row.get('geometrySHA256')):fail()
        feature=features.get(identity,{})
        properties=feature.get('properties',{});geometry=feature.get('geometry',{});metric=properties.get('soma:metricGeometry',{})
        if properties.get('canonical_id')!=identity or geometry.get('type')!='Point' or geometry.get('coordinates')!=ll or metric.get('type')!='Point' or metric.get('coordinates')!=l93 or properties.get('soma:geometry_sha256')!=row['geometrySHA256'] or sha(json_bytes(metric))!=row['geometrySHA256']:fail()
        if evidence.get('canonicalId')!=identity or evidence.get('nodeId')!=node or evidence.get('withinCommune') is not True or evidence.get('unique') is not True or not contains(ll,communes[code]['geometry']):fail()
        place=properties.get('place');ref=properties.get('ref:INSEE');name_match=any(normalized(properties.get(key,''))==normalized(row['name'])for key in ('name','official_name'))
        candidates=evidence.get('candidateIds');method=evidence.get('matchedBy')
        if place not in ('city','town','village') or evidence.get('place')!=place or evidence.get('sourceName')!=properties.get('name') or evidence.get('refINSEE')!=ref or ref is not None and ref!=code:fail()
        if not isinstance(candidates,list) or len(candidates)!=len(set(candidates)) or identity not in candidates:fail()
        if method=='ref:INSEE':
            if ref!=code or len(candidates)!=1:fail()
        elif method=='official-name-normalized':
            if not name_match or len(candidates)!=1:fail()
        elif method=='admin_centre-tiebreak':
            if not(ref==code or name_match) or len(candidates)<2 or not evidence.get('adminCentreRelations'):fail()
        else:fail()
        used.add(identity);source_count+=1
    if set(features)!=used or coverage.get('sourcePointCount')!=source_count or coverage.get('contourFallbackCount')!=len(communes)-source_count:fail()
    return anchors


def source_anchor(geometry):
    polygons = [geometry['coordinates']] if geometry['type']=='Polygon' else geometry['coordinates']
    def area(ring):
        o=ring[0]
        return sum((a[0]-o[0])*(b[1]-o[1])-(b[0]-o[0])*(a[1]-o[1]) for a,b in zip(ring,ring[1:]))/2
    polygon = max(polygons,key=lambda p:abs(area(p[0])))
    ring = polygon[0]
    west,south,east,north = min(p[0]for p in ring),min(p[1]for p in ring),max(p[0]for p in ring),max(p[1]for p in ring)
    def valid(p):return inside(p,ring) and not any(inside(p,hole)for hole in polygon[1:])
    center=[(west+east)/2,(south+north)/2]
    if valid(center):return center
    for n in (5,11,21,41):
        candidates=([west+(east-west)*(x+.5)/n,south+(north-south)*(y+.5)/n]for y in range(n)for x in range(n))
        candidates=sorted(candidates,key=lambda p:(p[0]-center[0])**2+(p[1]-center[1])**2)
        for point in candidates:
            if valid(point):return point
    raise ValueError('Aucun repère intérieur ne peut être dérivé du contour de commune.')


def metadata(html):
    territory_path=ROOT/'data/v69/territory.json'
    territory=json.loads(territory_path.read_text(encoding='utf-8'))
    descriptor=territory.get('boundary',{}).get('source',{})
    communes=[]
    if descriptor:
        relative=descriptor.get('path')
        if not safe_relative(relative):raise ValueError('Chemin du contour administratif invalide.')
        raw=(territory_path.parent/relative).read_bytes()
        if len(raw)!=descriptor.get('bytes') or sha(raw)!=descriptor.get('sha256'):raise ValueError('Le contour administratif ne correspond pas à son reçu.')
        collection=json.loads(raw)
        names={str(row['code']):row['nom']for row in territory['communes']}
        for feature in collection['features']:
            code=str(feature['properties']['code'])
            if code not in names:raise ValueError('Commune hors composition administrative déclarée.')
            communes.append({'code':code,'name':names[code],'anchorWGS84':source_anchor(feature['geometry']),
                'anchorSource':'administrative-contour-fallback','geometry':feature['geometry']})
        if len(communes)!=len(names):raise ValueError('Liste de communes et contours incohérente.')
    for row in territory['communes']:
        if not any(c['code']==str(row['code'])for c in communes):
            communes.append({'code':str(row['code']),'name':row['nom'],'anchorWGS84':None,'geometry':None})
    table=json.loads((ROOT/'data/v69/settlement-anchors.json').read_text(encoding='utf-8'))
    if table.get('territorySHA256')!=sha(territory_path.read_bytes()) or table.get('sources',{}).get('communeContours',{})!={key:descriptor[key]for key in ('path','sha256','bytes')}:raise ValueError('Les destinations proviennent d’une autre édition des communes.')
    anchors=audited_settlement_anchors(table,{c['code']:{'name':c['name'],'geometry':c['geometry']}for c in communes},territory['boundary']['sha256'])
    for commune in communes:
        anchor=anchors[commune['code']]
        if anchor['status']=='source-place':
            commune.update(anchorWGS84=anchor['pointWGS84'],anchorL93=anchor['pointL93'],anchorSource='osm-place-node',
                anchorCanonicalId=anchor['canonicalId'],anchorSourceSHA256=anchor['sourcePbfSHA256'],
                anchorEvidence={'cellId':anchor['cellId'],'cellContentSHA256':anchor['cellContentSHA256'],
                    'geometrySHA256':anchor['geometrySHA256'],'matchedBy':anchor['evidence']['matchedBy']})
        else:commune['anchorFallbackReason']=anchor['evidence']['reason']
    parts=json.loads(script(html,'soma-v69-building-parts',json_only=True))
    return {'territory':{'name':territory['name'],'communes':sorted(communes,key=lambda c:c['name']),
        'source':descriptor,'completeGeometry':False,'settlementAnchors':{'proofSHA256':table['proofSHA256'],
            'sourcePbfSHA256':table['sourcePbfSHA256'],'coverage':table['coverage']}},'parts':parts,
        'defaultWorld':'data/v69/metropole/manifest.json','fallbackWorld':'data/v69/world/manifest.json',
        'returnToGame':SOURCE.name}


def build(source_html=SOURCE, expected_sha=None):
    source_html=Path(source_html)
    raw=source_html.read_bytes()
    if expected_sha is None:
        report=json.loads((ROOT/'data/v69/BUILD_REPORT.json').read_text(encoding='utf-8'))
        expected_sha=report['sha256']
    if not re.fullmatch('[a-f0-9]{64}',expected_sha) or sha(raw)!=expected_sha:
        raise ValueError('Le HTML 0.69 ne correspond pas au SHA256 de sa reconstruction vérifiée.')
    html=raw.decode('utf-8');data=metadata(html)
    modules=[('geographic-core',script(html,'soma-v53-core')),
        ('terrain-core',script(html,'soma-v56-terrain-core')),('dimension-core',script(html,'soma-v59-core'))]
    for relative in ['v68/architecture-core.js','v69/roof-core.js','v69/streaming-core.js','v69/metropole-viewer-core.js']:
        modules.append((Path(relative).stem,(ROOT/'src'/relative).read_text(encoding='utf-8')))
    modules.append(('metropole-viewer',(ROOT/'src/v69/metropole-viewer.js').read_text(encoding='utf-8')))
    fragments=[]
    for identifier,text in modules:
        if '</script' in text.lower():raise ValueError(f'Fermeture de script interdite : {identifier}')
        fragments.append(f'<script id="viewer-{identifier}">\n{text}\n</script>')
    def json_script(identifier,value):
        text=json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False).replace('<','\\u003c')
        return f'<script id="{identifier}" type="application/json">{text}</script>'
    data_script=json_script('soma-viewer-data',{k:v for k,v in data.items() if k!='parts'})
    data_script+=json_script('soma-viewer-parts',data['parts'])
    template=TEMPLATE.read_text(encoding='utf-8')
    for marker in ('<!-- VIEWER_DATA -->','<!-- VIEWER_MODULES -->'):
        if template.count(marker)!=1:raise ValueError(f'Ancre de template invalide : {marker}')
    output=template.replace('<!-- VIEWER_DATA -->',data_script).replace('<!-- VIEWER_MODULES -->','\n'.join(fragments))
    return output.encode('utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-html',type=Path,default=SOURCE)
    parser.add_argument('--source-sha256')
    parser.add_argument('--output',type=Path,default=OUTPUT)
    parser.add_argument('--verify',action='store_true')
    args=parser.parse_args()
    try:
        data=build(args.source_html,args.source_sha256)
        if args.verify:
            if not args.output.is_file() or args.output.read_bytes()!=data:raise ValueError('Explorateur non synchronisé avec ses sources.')
        else:
            args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_bytes(data)
        print(json.dumps({'output':str(args.output),'bytes':len(data),'sha256':sha(data),'verified':args.verify,
            'campaignPersistenceLoaded':False,'networkDependencies':False},ensure_ascii=True))
    except (OSError,ValueError,KeyError) as error:
        parser.exit(1,f'Construction du survol impossible : {error}\n')


if __name__=='__main__':main()
