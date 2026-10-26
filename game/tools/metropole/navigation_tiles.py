#!/usr/bin/env python3
"""Build conservative source-node navigation assets for prepared vector tiles.

Only shared OSM node identities join ways. Cell-boundary points identify a
specific source way/segment/parameter, never a proximity or planar intersection.
The generated sidecar does not activate navigation in the historical game.
"""
from __future__ import annotations

import argparse
from collections import Counter, OrderedDict, defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

from pyproj import Transformer
from shapely.geometry import LineString, box, mapping, shape
from shapely.strtree import STRtree

try:
    from .import_tiles import canonical_json, digest, file_sha256, write_gzip_json
except ImportError:
    from import_tiles import canonical_json, digest, file_sha256, write_gzip_json

TO_METRIC = Transformer.from_crs('EPSG:4326','EPSG:2154',always_xy=True)
ALLOW = {'yes','designated','official','permissive'}
DENY = {'no','private','permit','customers','agricultural','forestry','delivery','destination','use_sidepath','dismount'}
FALSE_VALUES = {'','no','false','0'}
CAR_HIGHWAYS = {'motorway','motorway_link','trunk','trunk_link','primary','primary_link','secondary','secondary_link',
                'tertiary','tertiary_link','residential','unclassified','living_street','service','road','track'}
FOOT_HIGHWAYS = CAR_HIGHWAYS-{'motorway','motorway_link','trunk','trunk_link'} | {'footway','path','steps','pedestrian','bridleway','corridor'}
BIKE_HIGHWAYS = CAR_HIGHWAYS-{'motorway','motorway_link'} | {'cycleway','path','living_street'}
FOOT_BARRIERS = {'gate','lift_gate','swing_gate','chain','bollard','cycle_barrier','stile','kissing_gate','cattle_grid','kerb','entrance'}
SOLID_BARRIERS = {'wall','fence','hedge','retaining_wall','block','jersey_barrier','bus_trap'}
ACCESS_SCOPES = {'foot':('foot','access'),'car':('motorcar','motor_vehicle','vehicle','access'),
                 'bicycle':('bicycle','vehicle','access')}
TURN_KINDS = {'no_left_turn','no_right_turn','no_straight_on','no_u_turn','no_entry','no_exit',
              'only_left_turn','only_right_turn','only_straight_on','only_u_turn'}


class NavigationFailure(ValueError):
    pass


def asset_path(base: Path, relative: str) -> Path:
    if not isinstance(relative,str) or not relative or Path(relative).is_absolute():
        raise NavigationFailure('Asset paths must be nonempty relative paths.')
    path=(base/relative).resolve()
    if not path.is_relative_to(base.resolve()):
        raise NavigationFailure('Asset path escapes the vector package.')
    return path


def read_asset(base: Path, descriptor: dict, *, max_bytes=512*1024*1024):
    if not isinstance(descriptor,dict) or descriptor.get('encoding')!='gzip-json':
        raise NavigationFailure('Expected a gzip-json source asset.')
    path=asset_path(base,descriptor.get('path'))
    if path.stat().st_size!=descriptor.get('bytes') or file_sha256(path)!=descriptor.get('sha256'):
        raise NavigationFailure('Source asset checksum/size differs from its manifest.')
    with gzip.open(path,'rb') as stream:
        raw=stream.read(max_bytes+1)
    if len(raw)>max_bytes:
        raise NavigationFailure('Decoded source asset exceeds its budget.')
    if 'decodedBytes' in descriptor and len(raw)!=descriptor['decodedBytes']:
        raise NavigationFailure('Decoded source asset length differs from its manifest.')
    return json.loads(raw)


def value(tags,key):
    return str(tags.get(key,'')).strip().lower()


def conditional(tags,mode):
    keys={'access:conditional','barrier:conditional','locked:conditional'}
    if mode=='foot': keys|={'foot:conditional','oneway:foot:conditional'}
    elif mode=='car': keys|={'vehicle:conditional','motor_vehicle:conditional','motorcar:conditional',
                            'oneway:conditional','oneway:vehicle:conditional','oneway:motor_vehicle:conditional','oneway:motorcar:conditional'}
    else: keys|={'vehicle:conditional','bicycle:conditional','oneway:bicycle:conditional','oneway:vehicle:conditional','oneway:conditional'}
    keys.update(f'{scope}:{direction}:conditional' for scope in ACCESS_SCOPES[mode] for direction in ('forward','backward'))
    return any(value(tags,key) for key in keys)


def access_allowed(tags,mode,default,direction_name=None):
    for scope in ACCESS_SCOPES[mode]:
        keys=(f'{scope}:{direction_name}',scope) if direction_name else (scope,)
        for key in keys:
            if key not in tags:continue
            entry=value(tags,key)
            if entry in ALLOW:return True
            # Unknown and purpose-limited permissions cannot authorize public
            # through-routing without a destination/permission model.
            if entry in DENY or entry:return False
    return default


def direction(tags,mode):
    if mode=='foot': entries=['oneway:foot']
    elif mode=='car':entries=['oneway:motorcar','oneway:motor_vehicle','oneway:vehicle','oneway']
    else:entries=['oneway:bicycle','oneway:vehicle','oneway']
    raw=next((value(tags,key) for key in entries if key in tags),'')
    if raw in {'yes','true','1'}:return 1
    if raw=='-1':return -1
    if raw in {'no','false','0'}:return 0
    if raw:return None
    return 1 if mode!='foot' and (value(tags,'junction')=='roundabout' or value(tags,'highway')=='motorway') else 0


def structural(tags):
    if value(tags,'highway')=='corridor':return True
    try:
        if float(tags.get('layer',0))!=0:return True
    except (ValueError,TypeError):return True
    if any(value(tags,key) not in FALSE_VALUES for key in ['bridge','tunnel','covered','indoor']):return True
    return value(tags,'location') in {'underground','underwater','overground'}


def way_modes(tags):
    if structural(tags):return {'foot':(False,False),'car':(False,False),'bicycle':(False,False)},['unmodelled-structure']
    if value(tags,'highway') in {'construction','proposed','elevator'}:
        return {'foot':(False,False),'car':(False,False),'bicycle':(False,False)},['unbuilt-or-unmodelled-highway']
    defaults={'foot':value(tags,'highway') in FOOT_HIGHWAYS,'car':value(tags,'highway') in CAR_HIGHWAYS,
              'bicycle':value(tags,'highway') in BIKE_HIGHWAYS}
    out,refused={},[]
    for mode in defaults:
        one=direction(tags,mode)
        forward=access_allowed(tags,mode,defaults[mode],'forward') and one!=-1
        backward=access_allowed(tags,mode,defaults[mode],'backward') and one!=1
        if conditional(tags,mode) or one is None:
            forward=backward=False;refused.append(f'unsupported-{mode}-condition-or-direction')
        if mode!='foot' and value(tags,'highway')=='motorway_link' and not any(key in tags for key in ('oneway','oneway:vehicle',f'oneway:{mode}','oneway:motor_vehicle','oneway:motorcar')):
            forward=backward=False;refused.append(f'unknown-{mode}-motorway-link-direction')
        out[mode]=(forward,backward)
    return out,refused


def node_mode_allowed(tags,mode):
    if conditional(tags,mode) or structural(tags):return False
    if value(tags,'locked') not in FALSE_VALUES:return False
    barrier=value(tags,'barrier')
    if barrier in FALSE_VALUES:
        return access_allowed(tags,mode,True)
    if barrier in SOLID_BARRIERS:return False
    if barrier not in FOOT_BARRIERS:return False
    if value(tags,'opening_hours') not in {'','24/7'}:return False
    if barrier in {'bollard','cycle_barrier','stile','kissing_gate','kerb','cattle_grid'} and mode!='foot':
        # Generic access=yes cannot prove that a physical obstacle admits a
        # vehicle. Preserve explicit mode permissions; no clearance is claimed.
        specific=next((value(tags,key) for key in ACCESS_SCOPES[mode] if key!='access' and key in tags),'')
        if specific not in ALLOW:return False
    return access_allowed(tags,mode,mode=='foot')


def line_parts(geometry):
    if geometry.is_empty:return []
    if geometry.geom_type=='LineString':return [list(geometry.coords)]
    if geometry.geom_type in {'MultiLineString','GeometryCollection'}:
        return [line for part in geometry.geoms for line in line_parts(part)]
    return []


def source_intervals(a,b,lines,tolerance=.03):
    """Match clipped vector segments to their original source segment.

    The existing geodata validator allows 3 cm of projection correspondence.
    No line is snapped to another WAY: matches are considered only inside the
    same canonical source way, and every interval retains its segment index.
    """
    dx,dy=b[0]-a[0],b[1]-a[1]
    length=math.hypot(dx,dy)
    if length<=1e-8:return []
    length2=length*length
    intervals=[]
    for line in lines:
        for c,d in zip(line,line[1:]):
            p=((c[0]-a[0])*dx+(c[1]-a[1])*dy)/length2
            q=((d[0]-a[0])*dx+(d[1]-a[1])*dy)/length2
            c_distance=abs((c[0]-a[0])*dy-(c[1]-a[1])*dx)/length
            d_distance=abs((d[0]-a[0])*dy-(d[1]-a[1])*dx)/length
            if max(c_distance,d_distance)>tolerance:continue
            low=max(0,min(p,q));high=min(1,max(p,q))
            if (high-low)*length>1e-7:intervals.append((low,high))
    # Adjacent fragments of THIS source segment may join; unrelated source
    # nodes/ways never enter this parameter-space union.
    merged=[]
    for low,high in sorted(intervals):
        if merged and low<=merged[-1][1]+1e-12:merged[-1]=(merged[-1][0],max(high,merged[-1][1]))
        else:merged.append((low,high))
    return merged


def endpoint(way_id,segment,refs,a,b,t):
    if abs(t)<1e-10:return 'n/'+refs[segment-1],a,0.0
    if abs(t-1)<1e-10:return 'n/'+refs[segment],b,1.0
    rounded=round(t,12)
    return f'clip/{way_id}/{segment}/{rounded:.12f}',(a[0]+(b[0]-a[0])*rounded,a[1]+(b[1]-a[1])*rounded),rounded


def topology_index(topology):
    if topology.get('schema')!='soma-metropole/native-topology/1' or topology.get('nodeTagsComplete') is not True:
        raise NavigationFailure('Complete source node/barrier tags are required; regenerate the vector source package.')
    if not isinstance(topology.get('nodeTags'),dict):raise NavigationFailure('Source node metadata missing.')
    ways,nodes,seen_ids={},{},set()
    for way in topology.get('ways',[]):
        way_id=str(way.get('id',''))
        if not re.fullmatch(r'[0-9]+',way_id) or way_id in seen_ids:raise NavigationFailure('Invalid/duplicate source way identity.')
        seen_ids.add(way_id)
        refs=way.get('nodeRefs');coords=way.get('coordinatesWGS84')
        if not isinstance(refs,list) or not isinstance(coords,list) or len(refs)!=len(coords) or len(refs)<2:
            raise NavigationFailure('Native node references and coordinates must match.')
        positions=[]
        for ref,coordinate in zip(refs,coords):
            if not isinstance(ref,str) or not re.fullmatch(r'[0-9]+',ref) or not isinstance(coordinate,list) or len(coordinate)!=2 or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in coordinate):
                raise NavigationFailure('Invalid native node coordinates/identity.')
            if not -180<=coordinate[0]<=180 or not -90<=coordinate[1]<=90:raise NavigationFailure('Source node is not WGS84.')
            metric=TO_METRIC.transform(*coordinate)
            if ref in nodes and math.dist(nodes[ref],metric)>1e-6:raise NavigationFailure('A native OSM node has conflicting source coordinates.')
            if ref not in nodes:nodes[ref]=metric
            positions.append(nodes[ref])
        if way.get('layer')!='roads':continue
        tags=way.get('tags',{})
        if not isinstance(tags,dict):raise NavigationFailure('Invalid source way tags.')
        modes,reasons=way_modes(tags)
        ways[way_id]={'id':way_id,'refs':refs,'positions':positions,'tags':tags,'modes':modes,'reasons':reasons,
                      'geometrySHA256':digest({'type':'LineString','coordinates':positions})}
    return ways,nodes


class SegmentCandidates:
    """Bounded lazy native-segment indexes; they select IDs, never join ways."""
    def __init__(self,max_ways=128,max_segments=100000):
        self.cache=OrderedDict();self.max_ways=max_ways;self.max_segments=max_segments;self.segments=0
        self.queries=self.selected=self.available=0

    def query(self,way,lines):
        count=len(way['positions'])-1
        self.queries+=1;self.available+=count
        if count<=32:
            selected=list(range(1,count+1))
        else:
            key=way['id']
            if key in self.cache:
                tree=self.cache.pop(key);self.cache[key]=tree
            else:
                tree=STRtree([LineString([a,b]) for a,b in zip(way['positions'],way['positions'][1:])])
                if count<=self.max_segments:
                    while self.cache and (len(self.cache)>=self.max_ways or self.segments+count>self.max_segments):
                        _,old=self.cache.popitem(last=False);self.segments-=len(old.geometries)
                    self.cache[key]=tree;self.segments+=count
            xs=[p[0] for line in lines for p in line];ys=[p[1] for line in lines for p in line]
            extent=box(min(xs)-.03,min(ys)-.03,max(xs)+.03,max(ys)+.03)
            selected=sorted(int(i)+1 for i in tree.query(extent))
        self.selected+=len(selected)
        return selected


def restriction_rules(topology,ways):
    rules,removed,refused=[],{},[]
    def remove(ids,modes):
        for way_id in ids:
            if way_id in ways:removed.setdefault(way_id,set()).update(modes)
    for relation in topology.get('relations',[]):
        tags=relation.get('tags',{})
        if tags.get('type')!='restriction':continue
        members=relation.get('members',[])
        involved={str(m.get('ref')) for m in members if m.get('type')=='way'}
        from_ids=[str(m['ref']) for m in members if m.get('role')=='from' and m.get('type')=='way']
        to_ids=[str(m['ref']) for m in members if m.get('role')=='to' and m.get('type')=='way']
        vias=[m for m in members if m.get('role')=='via']
        exceptions={v.strip().lower() for v in str(tags.get('except','')).replace(',',';').split(';') if v.strip()}
        car_kind=next((tags[key] for key in ('restriction:motorcar','restriction:motor_vehicle','restriction:vehicle','restriction') if key in tags),None)
        if {'motorcar','motor_vehicle','vehicle'} & exceptions:car_kind=None
        unsupported_modes=set()
        if tags.get('restriction:foot') or tags.get('restriction:foot:conditional'):unsupported_modes.add('foot')
        # Bicycle turns cannot be represented by the historical foot/car router.
        # Withhold affected bicycle edges rather than silently omit a rule.
        bike_kind=next((tags[key] for key in ('restriction:bicycle','restriction:vehicle','restriction') if key in tags),None)
        if 'bicycle' not in exceptions and (bike_kind or tags.get('restriction:bicycle:conditional')):unsupported_modes.add('bicycle')
        conditional_keys=[k for k in tags if k.startswith('restriction') and k.endswith(':conditional')]
        if any(k in {'restriction:conditional','restriction:vehicle:conditional','restriction:motorcar:conditional','restriction:motor_vehicle:conditional'} for k in conditional_keys):unsupported_modes|={'car','bicycle'}
        if any(k in tags for k in ['day_on','day_off','hour_on','hour_off']):unsupported_modes|={'car','bicycle'}
        valid_members=len(from_ids)==len(to_ids)==1 and len(vias)==1 and vias[0].get('type')=='node'
        incident=(valid_members and from_ids[0] in ways and to_ids[0] in ways
                  and all(str(vias[0].get('ref')) in ways[way_id]['refs'] for way_id in (from_ids[0],to_ids[0])))
        if car_kind is not None and (not incident or not isinstance(car_kind,str) or car_kind not in TURN_KINDS):
            unsupported_modes|={'car','bicycle'}
        if unsupported_modes:
            remove(involved,unsupported_modes)
            refused.append({'relationId':str(relation.get('id')),'reason':'unsupported-conditional-mode-or-via',
                            'ways':sorted(involved),'removedModes':sorted(unsupported_modes),'sourceTags':tags,'sourceMembers':members})
        if car_kind is not None and incident and 'car' not in unsupported_modes:
            # core63 treats *_u_turn as reversal of the SAME graph edge. OSM
            # also uses distinct ways for divided carriageways. Preserve the
            # source kind while representing that explicit from->to transition.
            kind=car_kind
            if from_ids[0]!=to_ids[0] and car_kind in {'no_u_turn','only_u_turn'}:
                kind='no_source_transition' if car_kind=='no_u_turn' else 'only_source_transition'
            rules.append({'id':str(relation.get('id')),'from':from_ids[0],'to':to_ids[0],
                          'via':'n/'+str(vias[0]['ref']),'kind':kind,'sourceKind':car_kind,'mode':'car'})
    return rules,removed,refused


def way_metadata(way):
    tags=way['tags']
    return {'name':tags.get('name') or tags.get('ref') or tags.get('highway') or 'Voie OSM '+way['id'],
            'highway':tags.get('highway'),'oneway':tags.get('oneway'),'geometrySHA256':way['geometrySHA256'],
            'access':{k:v for k,v in tags.items() if k in {'access','vehicle','motor_vehicle','motorcar','foot','bicycle'} or k.endswith(':conditional')},
            'bicycleProfile':{'forward':way['modes']['bicycle'][0],'backward':way['modes']['bicycle'][1],
                              'meaning':'Source mode metadata only; the legacy router supports foot/car.'},
            'sourceTags':tags}


def build_cell_graph(record,topology,ways,rules,removed,source_pack_sha,source_pbf_sha,*,max_nodes=250000,max_edges=500000,
                     segments=None,rules_by_node=None,core_sha=None,topology_sha=None):
    cell_id=record['cellId'];cell_hash=record['contentSHA256']
    if record.get('sourceReceipt',{}).get('sha256')!=source_pbf_sha:raise NavigationFailure('Vector cell source PBF receipt differs.')
    if digest(record['featureCollection'])!=cell_hash:raise NavigationFailure('Vector cell content hash differs from its source features.')
    node_tags=topology['nodeTags']
    visible={}
    for feature in record['featureCollection']['features']:
        p=feature.get('properties',{})
        if p.get('soma:layer')!='roads':continue
        canonical=str(p.get('canonical_id') or feature.get('id',''))
        if not canonical.startswith('osm/way/'):continue
        way_id=canonical.rsplit('/',1)[1]
        metric=p.get('soma:metricGeometry')
        if not metric:raise NavigationFailure('A mapped road lacks prepared metric geometry.')
        lines=line_parts(shape(metric))
        if lines and p.get('area')!='yes':
            way=ways.get(way_id)
            if way is None:raise NavigationFailure(f'Mapped way {way_id} has no native source topology.')
            if p.get('soma:geometry_sha256')!=way['geometrySHA256']:
                raise NavigationFailure(f'Native source geometry SHA differs: {way_id}')
            if {key:entry for key,entry in p.items() if not key.startswith('soma:') and key!='canonical_id'}!=way['tags']:
                raise NavigationFailure(f'Native and clipped road source tags differ: {way_id}')
            visible.setdefault(way_id,[]).extend(lines)
    node_positions,edges,metadata,edge_sources,bicycle_masks={},[],{},[],[]
    counts=Counter();excluded=[];node_refusals={}
    for way_id,lines in sorted(visible.items(),key=lambda item:int(item[0])):
        way=ways.get(way_id)
        if way is None:
            raise NavigationFailure(f'Mapped way {way_id} has no native source topology.')
        metadata[way_id]=way_metadata(way)
        if way['reasons']:excluded.append({'wayId':way_id,'reasons':way['reasons']})
        base_modes={mode:directions for mode,directions in way['modes'].items()}
        for mode in removed.get(way_id,set()):base_modes[mode]=(False,False)
        selected=segments.query(way,lines) if segments else range(1,len(way['positions']))
        for segment in selected:
            a,b=way['positions'][segment-1:segment+1]
            intervals=source_intervals(a,b,lines)
            if not intervals:continue
            allowed={mode:directions for mode,directions in base_modes.items()}
            for ref in [way['refs'][segment-1],way['refs'][segment]]:
                tags=node_tags.get(ref,{})
                for mode in allowed:
                    if not node_mode_allowed(tags,mode):
                        if any(allowed[mode]):
                            counts[f'{mode}BarrierExcludedSegments']+=1
                            node_refusals.setdefault(ref,{'nodeId':ref,'barrier':tags.get('barrier'),'sourceTags':tags,
                                                         'removedModes':set()})['removedModes'].add(mode)
                        allowed[mode]=(False,False)
            mask=(1 if allowed['foot'][0] else 0)|(2 if allowed['foot'][1] else 0)|(4 if allowed['car'][0] else 0)|(8 if allowed['car'][1] else 0)
            if mask==0:continue
            for low,high in intervals:
                id_a,pos_a,t0=endpoint(way_id,segment,way['refs'],a,b,low)
                id_b,pos_b,t1=endpoint(way_id,segment,way['refs'],a,b,high)
                if id_a==id_b or math.dist(pos_a,pos_b)<1e-8:continue
                node_positions[id_a]=pos_a;node_positions[id_b]=pos_b
                edges.append([id_a,id_b,way_id,math.dist(pos_a,pos_b),mask,1 if way['tags'].get('highway')=='steps' else 0,[cell_id],segment])
                edge_sources.append({'wayId':way_id,'segmentIndex':segment,'t0':t0,'t1':t1,
                                     'startNative':id_a.startswith('n/'),'endNative':id_b.startswith('n/')})
                bicycle_masks.append((1 if allowed['bicycle'][0] else 0)|(2 if allowed['bicycle'][1] else 0))
                metadata[way_id]=way_metadata(way)
    if len(node_positions)>max_nodes or len(edges)>max_edges:raise NavigationFailure('Per-cell navigation graph exceeds its budget.')
    turns=[]
    local_rules=(rule for node_id in node_positions for rule in rules_by_node.get(node_id,[])) if rules_by_node is not None else (rule for rule in rules if rule['via'] in node_positions)
    for rule in local_rules:
        # A boundary turn may refer to a neighbouring way without an edge in
        # this tile. Retain its metadata so neighbouring assets can be merged.
        metadata.setdefault(rule['from'],way_metadata(ways[rule['from']]))
        metadata.setdefault(rule['to'],way_metadata(ways[rule['to']]))
        turns.append(rule)
    ordered=sorted(node_positions)
    indexes={node_id:i for i,node_id in enumerate(ordered)}
    for edge in edges:edge[0]=indexes[edge[0]];edge[1]=indexes[edge[1]]
    graph={'schema':'soma/navigation-source/1','version':'0.69.0','sourcePackSHA256':source_pack_sha,
           'sourcePbfSHA256':source_pbf_sha,'attribution':'© contributeurs OpenStreetMap — ODbL 1.0',
           'cellHashes':{cell_id:cell_hash},'nodes':[[node_id,*node_positions[node_id]] for node_id in ordered],
           'nodeTags':{node_id:node_tags[node_id[2:]] for node_id in ordered if node_id.startswith('n/') and node_id[2:] in node_tags},
           'edges':edges,'ways':dict(sorted(metadata.items())),'turns':sorted(turns,key=lambda r:(r['id'],r['via'])),
           'edgeSources':edge_sources,'bicycleMasks':bicycle_masks,
           'policy':{'joins':'Only shared native OSM IDs, or identical source way/segment clip parameters.',
                     'structure':'Bridges, tunnels, covered/indoor and nonzero layers withheld until vertical access is modelled.',
                     'unsupported':'Conditional, unknown barrier and multi-via permissions remove affected modes conservatively.',
                     'meaning':'Mapped source-axis guidance, not surveyed walkable pavements or a physical clearance guarantee.',
                     'clipCorrespondenceToleranceM':.03,'clipParameterDecimals':12,
                     'supportedRouteModes':['foot','car'],'bicycle':'Source direction/access metadata retained; no bicycle router is claimed.'},
           'sourceStatus':{'nodeTagsComplete':True,'nativeNodeIdentity':True,'vectorConstrained':True,
                           'partialCoverage':True,'completeMetropole':False,'physicalAccessibilityVerified':False,
                           'physicalMovementReady':False,'campaignRoutingActivated':False},
           'nativeTopologySHA256':topology_sha,'routingCoreSHA256':core_sha}
    return graph,{'cellId':cell_id,'nodes':len(ordered),'edges':len(edges),'turns':len(turns),
                  'excludedWays':excluded,'counts':dict(counts),
                  'nodeModeRefusals':[{**entry,'removedModes':sorted(entry['removedModes'])} for _,entry in sorted(node_refusals.items())]}


def merge_graphs(graphs,max_nodes=250000,max_edges=500000):
    """Reference merge for neighbouring assets; no coordinate-based joins."""
    graphs=list(graphs)
    if not graphs:raise NavigationFailure('At least one source graph is required.')
    source=graphs[0]
    nodes,ways,hashes,edge_map,turns,node_tags={}, {}, {}, {}, {}, {}
    for graph in graphs:
        if graph.get('schema')!='soma/navigation-source/1':raise NavigationFailure('Incompatible source navigation schema.')
        if graph['sourcePackSHA256']!=source['sourcePackSHA256'] or graph['sourcePbfSHA256']!=source['sourcePbfSHA256']:
            raise NavigationFailure('Graphs from different source packages cannot be merged.')
        if any(graph.get(key)!=source.get(key) for key in ('nativeTopologySHA256','routingCoreSHA256')):
            raise NavigationFailure('Graphs with different native topology or routing core cannot be merged.')
        for cell_id,cell_hash in graph['cellHashes'].items():
            if cell_id in hashes and hashes[cell_id]!=cell_hash:raise NavigationFailure('Conflicting cell source hashes.')
            hashes[cell_id]=cell_hash
        for node_id,e,n in graph['nodes']:
            if node_id in nodes and math.dist(nodes[node_id],(e,n))>1e-6:raise NavigationFailure('Conflicting native/clip node coordinates.')
            nodes[node_id]=(e,n)
        for node_id,tags in graph.get('nodeTags',{}).items():
            if node_id in node_tags and node_tags[node_id]!=tags:raise NavigationFailure('Conflicting source node tags.')
            node_tags[node_id]=tags
        for way_id,metadata in graph['ways'].items():
            if way_id in ways and ways[way_id]!=metadata:raise NavigationFailure('Conflicting source way metadata.')
            ways[way_id]=metadata
        for i,edge in enumerate(graph['edges']):
            a=graph['nodes'][edge[0]][0];b=graph['nodes'][edge[1]][0]
            origin=graph['edgeSources'][i]
            key=(a,b,edge[2],origin['segmentIndex'],origin['t0'],origin['t1'])
            if key in edge_map:
                previous=edge_map[key]
                if previous[0][4:6]!=edge[4:6] or previous[2]!=graph['bicycleMasks'][i]:raise NavigationFailure('Conflicting source edge modes.')
                previous[0][6]=sorted(set(previous[0][6])|set(edge[6]))
            else:edge_map[key]=([a,b,*edge[2:]],origin,graph['bicycleMasks'][i])
        for rule in graph['turns']:turns[canonical_json(rule)]=rule
    if len(nodes)>max_nodes or len(edge_map)>max_edges:raise NavigationFailure('Merged navigation graph exceeds the legacy router budget.')
    ordered=sorted(nodes);indexes={key:i for i,key in enumerate(ordered)}
    edges=[];origins=[];bike=[]
    for key,(edge,origin,bicycle) in sorted(edge_map.items()):
        edges.append([indexes[edge[0]],indexes[edge[1]],*edge[2:]]);origins.append(origin);bike.append(bicycle)
    return {**source,'nodes':[[key,*nodes[key]] for key in ordered],'edges':edges,'ways':dict(sorted(ways.items())),
            'nodeTags':dict(sorted(node_tags.items())),
            'cellHashes':dict(sorted(hashes.items())),'turns':[turns[key] for key in sorted(turns)],
            'edgeSources':origins,'bicycleMasks':bike}


def navigation_core(baseline=None):
    baseline=Path(baseline) if baseline else Path(__file__).resolve().parents[2]/'baseline/v66.html'
    sources=re.findall(r'<script\b[^>]*\bid="soma-v63-nav-core"[^>]*>(.*?)</script>',baseline.read_text(encoding='utf-8'),re.S)
    if len(sources)!=1:raise NavigationFailure('Exactly one frozen source-node navigation core is required.')
    node=shutil.which('node')
    if not node:raise NavigationFailure('Node is required to verify the frozen navigation contract.')
    runner="const fs=require('fs'),vm=require('vm'),m={exports:{}};vm.runInNewContext(fs.readFileSync(0,'utf8'),{module:m});const c=m.exports;if(typeof c.validate!=='function'||typeof c.createRouter!=='function')throw Error('Unsupported navigation contract');c.validate({schema:'soma/navigation-source/1',nodes:[],edges:[],turns:[],ways:{},cellHashes:{}});"
    checked=subprocess.run([node,'-e',runner],input=sources[0],text=True,capture_output=True,timeout=30)
    if checked.returncode:raise NavigationFailure('Frozen navigation core contract failed: '+checked.stderr[:1500])
    return {'scriptId':'soma-v63-nav-core','version':'0.63.0','sha256':hashlib.sha256(sources[0].encode()).hexdigest(),
            'baselineSHA256':file_sha256(baseline)}


def prepare_navigation(manifest_path,output,*,max_nodes=250000,max_edges=500000,baseline=None,progress=None):
    manifest_path=Path(manifest_path).resolve();output=Path(output).absolute()
    if output.exists():raise NavigationFailure('Output already exists; choose a new navigation output directory.')
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('schema')!='soma-metropole/vector-tiles/1' or manifest.get('crs')!='EPSG:2154' or manifest.get('units')!='m':
        raise NavigationFailure('A metric source vector manifest is required.')
    source_sha=file_sha256(manifest_path)
    pbf_sha=manifest.get('source',{}).get('sha256','')
    if not re.fullmatch(r'[a-f0-9]{64}',pbf_sha):raise NavigationFailure('Source PBF fingerprint is missing.')
    if not 1<=max_nodes<=250000 or not 1<=max_edges<=500000:raise NavigationFailure('Navigation limits must fit the frozen router budget.')
    started=time.monotonic()
    def notify(phase,**details):
        if progress:
            import resource
            progress({'phase':phase,'elapsedSeconds':round(time.monotonic()-started,3),
                      'peakRssMiB':round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,1),**details})
    core=navigation_core(baseline)
    topology=read_asset(manifest_path.parent,manifest.get('nativeTopology'))
    ways,native_nodes=topology_index(topology)
    native_node_count=len(native_nodes);del native_nodes
    topology.pop('ways',None)  # No full WGS84 JSON survives projection/identity checks.
    rules,removed,refused=restriction_rules(topology,ways)
    restriction_sources=[r for r in topology.get('relations',[]) if r.get('tags',{}).get('type')=='restriction']
    topology.pop('relations',None)
    rules_by_node=defaultdict(list)
    for rule in rules:rules_by_node[rule['via']].append(rule)
    segments=SegmentCandidates()
    notify('native-topology-ready',ways=len(ways),nativeNodes=native_node_count,carRules=len(rules),refusedRestrictions=len(refused))
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.metropole-navigation-',dir=output.parent) as temporary:
        stage=Path(temporary)/'navigation';stage.mkdir()
        tiles=[];reports=[];seen=set();total_edges=total_nodes=0
        for number,tile in enumerate(manifest.get('tiles',[]),1):
            record=read_asset(manifest_path.parent,tile['vector'],max_bytes=16*1024*1024)
            cell_id=record.get('cellId');bounds=record.get('boundsL93')
            if (not isinstance(cell_id,str) or not re.fullmatch(r'V52-MC-[A-Za-z0-9-]+',cell_id) or cell_id in seen
                    or cell_id!=tile.get('cellId') or bounds!=tile.get('boundsL93')):
                raise NavigationFailure('Vector tile identity/bounds differ from the source manifest.')
            if (not isinstance(bounds,list) or len(bounds)!=4 or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in bounds)
                    or abs(bounds[2]-bounds[0]-250)>1e-6 or abs(bounds[3]-bounds[1]-250)>1e-6):
                raise NavigationFailure('A complete 250m metric vector cell is required.')
            seen.add(cell_id)
            graph,report=build_cell_graph(record,topology,ways,rules,removed,source_sha,pbf_sha,max_nodes=max_nodes,max_edges=max_edges,
                                          segments=segments,rules_by_node=rules_by_node,core_sha=core['sha256'],topology_sha=manifest['nativeTopology']['sha256'])
            descriptor=write_gzip_json(stage/f'{record["cellId"]}.json.gz',graph,max_decoded_bytes=64*1024*1024)
            tiles.append({'cellId':record['cellId'],'boundsL93':record['boundsL93'],'cellHash':record['contentSHA256'],'navigation':descriptor})
            reports.append(report)
            total_nodes+=len(graph['nodes']);total_edges+=len(graph['edges'])
            if number%256==0:notify('prepare-cells',completed=number,total=len(manifest['tiles']),nodes=total_nodes,edges=total_edges,
                                    selectedNativeSegments=segments.selected,availableNativeSegments=segments.available)
        result={'schema':'soma-metropole/navigation-tiles/1','version':'0.69.0','crs':'EPSG:2154','units':'m',
                'sourceVectorManifest':{'path':str(manifest_path),'sha256':source_sha},'sourcePbfSHA256':pbf_sha,
                'nativeTopologySHA256':manifest['nativeTopology']['sha256'],'navigationCore':core,'tiles':tiles,
                'coverageExplicitPartial':True,'completeMetropole':False,
                'readiness':False,'activation':False,'physicalMovementReady':False,'campaignRoutingActivated':False,
                'sourceCellsComplete':len(tiles)==len(manifest['tiles']),
                'report':{'cells':len(tiles),'nodeOccurrences':total_nodes,'edgeOccurrences':total_edges,
                          'carRules':len(rules),'refusedRestrictions':len(refused),
                          'carRestrictionRefusals':sum('car' in r['removedModes'] for r in refused),
                          'footRestrictionRefusals':sum('foot' in r['removedModes'] for r in refused),
                          'bicycleRestrictionRefusals':sum('bicycle' in r['removedModes'] for r in refused),
                          'nativeSegmentCandidates':segments.selected,'nativeSegmentsConsidered':segments.available,
                          'maximumCellNodes':max((r['nodes'] for r in reports),default=0),'maximumCellEdges':max((r['edges'] for r in reports),default=0)},
                'meaning':'Prepared source-axis navigation sidecars. No historical game routing or metro coverage is activated.'}
        if file_sha256(manifest_path)!=source_sha:raise NavigationFailure('Source vector manifest changed during navigation preparation.')
        (stage/'manifest.json').write_text(canonical_json(result)+'\n',encoding='utf-8')
        (stage/'NAVIGATION_REPORT.json').write_text(canonical_json({'schema':'soma-metropole/navigation-report/1','cells':reports,
            'refusedRestrictions':refused,'restrictionSources':restriction_sources,'sourceNodeTagsComplete':True,
            'sourceVectorManifestSHA256':source_sha,'nativeTopologySHA256':manifest['nativeTopology']['sha256'],'navigationCore':core})+'\n',encoding='utf-8')
        stage.rename(output)
    notify('published',completed=len(tiles),manifest=str(output/'manifest.json'),**result['report'])
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--max-nodes',type=int,default=250000)
    parser.add_argument('--max-edges',type=int,default=500000)
    parser.add_argument('--baseline',type=Path)
    parser.add_argument('--progress',action='store_true')
    args=parser.parse_args()
    try:
        progress=(lambda event:print(json.dumps(event),file=sys.stderr,flush=True)) if args.progress else None
        result=prepare_navigation(args.manifest,args.output,max_nodes=args.max_nodes,max_edges=args.max_edges,baseline=args.baseline,progress=progress)
        print(json.dumps({'status':'prepared','tiles':len(result['tiles']),'manifest':str(args.output/'manifest.json'),
                          'coverageExplicitPartial':True,'completeMetropole':False},ensure_ascii=False))
    except (OSError,ValueError,RuntimeError) as error:
        parser.exit(1,f'Navigation preparation refused: {error}\n')


if __name__=='__main__':main()
