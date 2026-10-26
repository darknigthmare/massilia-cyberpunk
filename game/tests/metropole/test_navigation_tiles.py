"""Real legacy router validation of conservative native-source tiled graphs."""
from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from shapely.geometry import LineString, box, mapping

ROOT=Path(__file__).resolve().parents[2]
TOOLS=ROOT/'tools/metropole'
sys.path.insert(0,str(TOOLS))
import import_tiles as V
import navigation_tiles as N
import navigation_qa as Q


def read_gzip(path):
    with gzip.open(path,'rt',encoding='utf-8') as stream:return json.load(stream)


def package(root,nodes,ways,*,cells=((0,0),),node_tags=None,relations=None,complete=True):
    """Source fixture in the same native-topology and vector-cell formats."""
    root.mkdir()
    wgs={str(key):list(V.TO_WGS84.transform(*position)) for key,position in nodes.items()}
    projected={key:V.TO_METRIC.transform(*position) for key,position in wgs.items()}
    source_ways=[]
    for way_id,refs,tags in ways:
        source_ways.append({'id':str(way_id),'layer':'roads','tags':{'highway':'residential',**tags},
                           'nodeRefs':[str(ref) for ref in refs],
                           'coordinatesWGS84':[wgs[str(ref)] for ref in refs]})
    topology={'schema':'soma-metropole/native-topology/1','ways':source_ways,
              'relations':relations or [],'nodeTags':node_tags or {},'nodeTagsComplete':complete}
    topology_descriptor=V.write_gzip_json(root/'native-topology.json.gz',topology)
    tiles=[]
    for x,y in cells:
        bounds=V.cell_bounds(x,y);features=[]
        for way in source_ways:
            geometry=LineString([projected[ref] for ref in way['nodeRefs']])
            properties={**way['tags'],'canonical_id':'osm/way/'+way['id'],'soma:layer':'roads',
                        'soma:geometry_sha256':V.digest(mapping(geometry))}
            feature=V.clip_feature(geometry,properties,box(*bounds))
            if feature is not None:features.append(feature)
        if not features:continue
        record={'schema':'soma-massilia/geodata-cell/4','cellId':V.cell_id(x,y),'grid':{'x':x,'y':y},
                'boundsL93':list(bounds),'sourceReceipt':{'sha256':'a'*64},
                'featureCollection':{'type':'FeatureCollection','features':features}}
        record['contentSHA256']=V.digest(record['featureCollection'])
        descriptor=V.write_gzip_json(root/(record['cellId']+'.json.gz'),record)
        tiles.append({'cellId':record['cellId'],'gridX':x,'gridY':y,'boundsL93':list(bounds),
                      'vector':descriptor,'terrain':None,'navigation':None})
    manifest={'schema':'soma-metropole/vector-tiles/1','version':'0.69.0','crs':'EPSG:2154','units':'m',
              'origin':list(V.ORIGIN),'cellSize':250,'source':{'sha256':'a'*64},
              'tiles':tiles,'nativeTopology':topology_descriptor,'coverageExplicitPartial':True,'completeMetropole':False}
    (root/'manifest.json').write_text(V.canonical_json(manifest)+'\n',encoding='utf-8')
    return root/'manifest.json'


class NavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core_temp=tempfile.TemporaryDirectory()
        html=(ROOT/'baseline/v66.html').read_text(encoding='utf-8')
        source=re.search(r'<script[^>]+id="soma-v63-nav-core"[^>]*>(.*?)</script>',html,re.S)
        if not source:raise RuntimeError('Prepare the verified original baseline before running navigation tests.')
        cls.core=Path(cls.core_temp.name)/'legacy-nav.cjs'
        cls.core.write_text(source[1],encoding='utf-8')

    @classmethod
    def tearDownClass(cls):cls.core_temp.cleanup()

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.e,self.n=V.ORIGIN

    def tearDown(self):self.temp.cleanup()

    def prepare(self,source,name='nav',**kwargs):
        result=N.prepare_navigation(source,self.root/name,**kwargs)
        graphs=[read_gzip(self.root/name/t['navigation']['path']) for t in result['tiles']]
        report=json.loads((self.root/name/'NAVIGATION_REPORT.json').read_text())
        return result,graphs,report

    def legacy(self,graph,start=None,end=None,mode='foot'):
        javascript='''const fs=require('fs'),N=require(process.argv[1]);
          const q=JSON.parse(fs.readFileSync(0,'utf8'));N.validate(q.graph);
          const route=q.start?N.createRouter(q.graph).route(q.start,q.end,{mode:q.mode,maxSnap:.1}):null;
          process.stdout.write(JSON.stringify({valid:true,route}));'''
        value={'graph':graph,'start':start,'end':end,'mode':mode}
        result=subprocess.run(['node','-e',javascript,str(self.core)],input=json.dumps(value),capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        return json.loads(result.stdout)

    def road(self,tags=None,node_tags=None,complete=True):
        nodes={'1':(self.e-50,self.n),'2':(self.e+50,self.n)}
        source=package(self.root/'source',nodes,[('100',['1','2'],tags or {})],node_tags=node_tags,complete=complete)
        return source,nodes

    def rewrite_native(self,source,change):
        manifest=json.loads(source.read_text());path=source.parent/manifest['nativeTopology']['path']
        native=read_gzip(path);change(native);path.unlink()
        manifest['nativeTopology']=V.write_gzip_json(path,native)
        source.write_text(V.canonical_json(manifest)+'\n')

    def test_legacy_router_accepts_graph_and_mode_directions_remain_source_native(self):
        source,nodes=self.road({'oneway':'yes','bicycle':'yes','oneway:bicycle':'no'})
        result,graphs,_=self.prepare(source)
        graph=graphs[0]
        self.assertEqual(graph['sourcePackSHA256'],V.file_sha256(source))
        self.assertEqual(graph['sourcePbfSHA256'],'a'*64)
        self.assertEqual(graph['edges'][0][4],7)
        self.assertEqual(graph['bicycleMasks'],[3])
        self.assertTrue(all(n[0].startswith('n/') for n in graph['nodes']))
        start={'e':nodes['1'][0],'n':nodes['1'][1]};end={'e':nodes['2'][0],'n':nodes['2'][1]}
        self.assertTrue(self.legacy(graph,start,end,'car')['route']['ok'])
        self.assertFalse(self.legacy(graph,end,start,'car')['route']['ok'])
        self.assertTrue(self.legacy(graph,end,start,'foot')['route']['ok'])
        self.assertFalse(result['completeMetropole'])

    def test_coincident_planar_crossing_never_creates_a_native_junction(self):
        nodes={'1':(self.e-40,self.n),'2':(self.e+40,self.n),
               '3':(self.e,self.n-40),'4':(self.e,self.n+40)}
        source=package(self.root/'source',nodes,[('100',['1','2'],{}),('200',['3','4'],{})])
        _,graphs,_=self.prepare(source);graph=graphs[0]
        self.assertEqual(len(graph['nodes']),4)
        route=self.legacy(graph,{'e':nodes['1'][0],'n':nodes['1'][1]},
                          {'e':nodes['4'][0],'n':nodes['4'][1]})['route']
        self.assertFalse(route['ok'])

    def test_cell_clips_merge_by_source_segment_identity_without_moving_native_nodes(self):
        edge=V.cell_bounds(0,0)[2]
        nodes={'1':(edge-80,self.n),'2':(edge+80,self.n)}
        source=package(self.root/'source',nodes,[('100',['1','2'],{'oneway':'yes'})],cells=((0,0),(1,0)))
        _,graphs,_=self.prepare(source)
        self.assertEqual(len(graphs),2)
        clips=[{n[0] for n in graph['nodes'] if n[0].startswith('clip/')} for graph in graphs]
        self.assertEqual(len(clips[0]&clips[1]),1)
        before=json.dumps(graphs,sort_keys=True)
        merged=N.merge_graphs(graphs)
        self.assertEqual(len(merged['nodes']),3)
        self.assertEqual(json.dumps(graphs,sort_keys=True),before)
        route=self.legacy(merged,{'e':nodes['1'][0],'n':nodes['1'][1]},
                          {'e':nodes['2'][0],'n':nodes['2'][1]},'car')['route']
        self.assertTrue(route['ok']);self.assertAlmostEqual(route['lengthMeters'],160,places=5)
        self.assertEqual(set(route['cells']),{'V52-MC-33','V52-MC-34'})

    def test_native_barriers_remove_car_access_but_keep_explicit_foot_permission(self):
        source,nodes=self.road(node_tags={'2':{'barrier':'bollard','foot':'yes','motor_vehicle':'no'}})
        _,graphs,report=self.prepare(source);graph=graphs[0]
        self.assertEqual(graph['edges'][0][4],3)
        self.assertEqual(report['cells'][0]['nodeModeRefusals'][0]['nodeId'],'2')
        self.assertIn('car',report['cells'][0]['nodeModeRefusals'][0]['removedModes'])
        self.assertTrue(self.legacy(graph)['valid'])

    def test_unknown_barrier_is_conservatively_closed_even_with_unverified_generic_access(self):
        source,_=self.road(node_tags={'2':{'barrier':'unknown_machine','access':'yes'}})
        _,graphs,report=self.prepare(source)
        self.assertEqual(graphs[0]['edges'],[])
        self.assertGreater(report['cells'][0]['counts']['footBarrierExcludedSegments'],0)
        self.assertTrue(self.legacy(graphs[0])['valid'])

    def test_missing_node_barrier_source_is_a_precondition_failure(self):
        source,_=self.road(complete=False)
        with self.assertRaisesRegex(N.NavigationFailure,'node/barrier'):
            self.prepare(source)
        self.assertFalse((self.root/'nav').exists())

    def test_structures_and_conditionals_are_excluded_per_affected_mode(self):
        for index,tags in enumerate([{'bridge':'yes'},{'tunnel':'building_passage'},{'covered':'arcade'},
                                     {'indoor':'yes'},{'layer':'1'},{'highway':'corridor'}]):
            source=package(self.root/f'source-{index}',{'1':(self.e-20,self.n),'2':(self.e+20,self.n)},[('100',['1','2'],tags)])
            _,graphs,_=self.prepare(source,f'nav-{index}')
            self.assertEqual(graphs[0]['edges'],[],tags)
        source=package(self.root/'conditional',{'1':(self.e-20,self.n),'2':(self.e+20,self.n)},
                       [('100',['1','2'],{'motor_vehicle:conditional':'yes @ (08:00-18:00)'})])
        _,graphs,report=self.prepare(source,'conditional-nav')
        self.assertEqual(graphs[0]['edges'][0][4],3)
        self.assertTrue(report['cells'][0]['excludedWays'])

    def test_specific_foot_permission_and_motorcar_direction_restrictions_survive(self):
        source,_=self.road({'access':'private','foot':'yes','motor_vehicle':'yes','motorcar:forward':'no'})
        _,graphs,_=self.prepare(source)
        self.assertEqual(graphs[0]['edges'][0][4],11)
        self.assertEqual(graphs[0]['ways']['100']['access']['foot'],'yes')

    def test_locked_and_scheduled_barriers_close_modes_even_with_explicit_access(self):
        for index,tags in enumerate(({'barrier':'gate','locked':'yes','foot':'yes'},
                                    {'barrier':'gate','opening_hours':'08:00-18:00','access':'yes'},
                                    {'barrier':'gate','locked:conditional':'no @ (sunrise-sunset)','access':'yes'})):
            source=package(self.root/f'locked-{index}',{'1':(self.e-20,self.n),'2':(self.e+20,self.n)},
                           [('100',['1','2'],{})],node_tags={'2':tags})
            _,graphs,_=self.prepare(source,f'locked-nav-{index}')
            self.assertEqual(graphs[0]['edges'],[])

    def test_generic_access_cannot_prove_a_rising_bollard_passes_a_car(self):
        source,_=self.road(node_tags={'2':{'barrier':'bollard','bollard':'rising','access':'yes'}})
        _,graphs,_=self.prepare(source)
        self.assertEqual(graphs[0]['edges'][0][4],3)

    def test_implicit_motorway_oneway_and_unbuilt_axis_refusals(self):
        source,_=self.road({'highway':'motorway'})
        result,graphs,_=self.prepare(source)
        self.assertEqual(graphs[0]['edges'][0][4],4)
        self.assertFalse(result['physicalMovementReady']);self.assertFalse(result['campaignRoutingActivated'])
        self.assertEqual(graphs[0]['routingCoreSHA256'],result['navigationCore']['sha256'])
        for index,tags in enumerate(({'highway':'construction','foot':'yes'}, {'highway':'proposed','access':'yes'},
                                    {'highway':'motorway_link'})):
            candidate=package(self.root/f'unbuilt-{index}',{'1':(self.e-20,self.n),'2':(self.e+20,self.n)},[('100',['1','2'],tags)])
            _,items,_=self.prepare(candidate,f'unbuilt-nav-{index}')
            self.assertEqual(items[0]['edges'],[])

    def test_directional_conditionals_close_affected_mode_and_specific_permission_can_open_one_direction(self):
        source,_=self.road({'motor_vehicle:forward:conditional':'yes @ (08:00-18:00)'})
        _,graphs,_=self.prepare(source)
        self.assertEqual(graphs[0]['edges'][0][4],3)
        candidate=package(self.root/'foot-forward',{'1':(self.e-20,self.n),'2':(self.e+20,self.n)},
                          [('100',['1','2'],{'access':'private','foot:forward':'yes'})])
        _,items,_=self.prepare(candidate,'foot-forward-nav')
        self.assertEqual(items[0]['edges'][0][4],1)

    def turn_fixture(self,*,unsupported=False,cross_cell=False):
        center=V.cell_bounds(0,0)[2] if cross_cell else self.e
        nodes={'1':(center-50,self.n),'2':(center,self.n),'3':(center+50,self.n+40)}
        via=[{'type':'node','ref':'2','role':'via'}]
        if unsupported:via=[{'type':'way','ref':'10','role':'via'}]
        relation={'id':'900','tags':{'type':'restriction','restriction':'no_left_turn'},
                  'members':[{'type':'way','ref':'10','role':'from'},*via,{'type':'way','ref':'20','role':'to'}]}
        source=package(self.root/'source',nodes,[('10',['1','2'],{'oneway':'yes'}),('20',['2','3'],{'oneway':'yes'})],
                       relations=[relation],cells=((0,0),(1,0)) if cross_cell else ((0,0),))
        return source,nodes

    def test_via_node_turn_restriction_is_enforced_by_the_actual_legacy_router(self):
        source,nodes=self.turn_fixture()
        _,graphs,_=self.prepare(source);graph=graphs[0]
        self.assertEqual(graph['turns'][0]['via'],'n/2')
        start={'e':nodes['1'][0],'n':nodes['1'][1]};end={'e':nodes['3'][0],'n':nodes['3'][1]}
        self.assertFalse(self.legacy(graph,start,end,'car')['route']['ok'])
        self.assertTrue(self.legacy(graph,start,end,'foot')['route']['ok'])

    def test_boundary_turn_rule_survives_merging_with_neighbouring_way_metadata(self):
        source,nodes=self.turn_fixture(cross_cell=True)
        _,graphs,_=self.prepare(source)
        merged=N.merge_graphs(graphs)
        self.assertEqual(len(merged['turns']),1)
        self.assertTrue(all('10' in graph['ways'] and '20' in graph['ways'] for graph in graphs))
        route=self.legacy(merged,{'e':nodes['1'][0],'n':nodes['1'][1]},
                          {'e':nodes['3'][0],'n':nodes['3'][1]},'car')['route']
        self.assertFalse(route['ok'])

    def test_distinct_way_u_turn_is_blocked_by_the_real_core_and_source_kind_retained(self):
        source,nodes=self.turn_fixture()
        self.rewrite_native(source,lambda native:native['relations'][0]['tags'].update(restriction='no_u_turn'))
        _,graphs,_=self.prepare(source);graph=graphs[0]
        self.assertEqual(graph['turns'][0]['kind'],'no_source_transition')
        self.assertEqual(graph['turns'][0]['sourceKind'],'no_u_turn')
        self.assertFalse(self.legacy(graph,{'e':nodes['1'][0],'n':nodes['1'][1]},
                                     {'e':nodes['3'][0],'n':nodes['3'][1]},'car')['route']['ok'])

    def test_vehicle_restrictions_and_unavailable_via_are_never_silently_ignored(self):
        source,nodes=self.turn_fixture()
        self.rewrite_native(source,lambda native:native['relations'][0].update(tags={'type':'restriction','restriction:vehicle':'no_left_turn'}))
        _,graphs,_=self.prepare(source)
        self.assertFalse(self.legacy(graphs[0],{'e':nodes['1'][0],'n':nodes['1'][1]},
                                     {'e':nodes['3'][0],'n':nodes['3'][1]},'car')['route']['ok'])
        self.rewrite_native(source,lambda native:native['relations'][0]['members'][1].update(ref='999'))
        _,graphs,report=self.prepare(source,'invalid-via')
        self.assertEqual(graphs[0]['turns'],[])
        self.assertTrue(all(edge[4]==3 for edge in graphs[0]['edges']))
        self.assertTrue(report['refusedRestrictions'])

    def test_vehicle_conditional_and_explicit_foot_turn_restrictions_remove_only_prudent_modes(self):
        source,_=self.turn_fixture()
        self.rewrite_native(source,lambda native:native['relations'][0].update(tags={'type':'restriction','restriction:vehicle:conditional':'no_left_turn @ (Mo-Fr)'}))
        _,graphs,_=self.prepare(source)
        self.assertTrue(all(edge[4]==3 for edge in graphs[0]['edges']))
        self.rewrite_native(source,lambda native:native['relations'][0].update(tags={'type':'restriction','restriction:foot':'no_left_turn'}))
        _,graphs,_=self.prepare(source,'foot-turn-nav')
        self.assertTrue(all(edge[4]==4 for edge in graphs[0]['edges']))

    def test_unsupported_via_way_restriction_removes_car_modes_and_reports_refusal(self):
        source,_=self.turn_fixture(unsupported=True)
        _,graphs,report=self.prepare(source)
        self.assertTrue(all(edge[4]==3 for edge in graphs[0]['edges']))
        self.assertEqual(graphs[0]['turns'],[])
        self.assertEqual(report['refusedRestrictions'][0]['relationId'],'900')
        self.assertIn('car',report['refusedRestrictions'][0]['removedModes'])

    def test_assets_are_repeatable_link_source_hashes_and_fail_closed_on_corruption(self):
        source,_=self.road()
        a,graphs,_=self.prepare(source,'first');b,other,_=self.prepare(source,'second')
        self.assertEqual(a,b);self.assertEqual(graphs,other)
        manifest=json.loads(source.read_text());path=source.parent/manifest['nativeTopology']['path']
        path.write_bytes(path.read_bytes()+b'corrupt')
        with self.assertRaisesRegex(N.NavigationFailure,'checksum/size'):
            self.prepare(source,'bad')
        self.assertFalse((self.root/'bad').exists())

    def test_geometry_budgets_and_different_source_graphs_never_merge_silently(self):
        source,_=self.road()
        with self.assertRaisesRegex(N.NavigationFailure,'budget'):
            self.prepare(source,'too-small',max_nodes=1)
        self.assertFalse((self.root/'too-small').exists())
        _,graphs,_=self.prepare(source)
        changed=json.loads(json.dumps(graphs[0]));changed['sourcePackSHA256']='b'*64
        with self.assertRaisesRegex(N.NavigationFailure,'different source'):
            N.merge_graphs([graphs[0],changed])

    def test_native_geometry_tags_and_pbf_receipt_drift_fail_before_publication(self):
        for index,mutation in enumerate(('geometry','tags','receipt')):
            source=package(self.root/f'drift-{index}',{'1':(self.e-20,self.n),'2':(self.e+20,self.n)},[('100',['1','2'],{})])
            manifest=json.loads(source.read_text());descriptor=manifest['tiles'][0]['vector'];path=source.parent/descriptor['path'];record=read_gzip(path)
            if mutation=='receipt':record['sourceReceipt']['sha256']='b'*64
            elif mutation=='geometry':record['featureCollection']['features'][0]['properties']['soma:geometry_sha256']='b'*64
            else:record['featureCollection']['features'][0]['properties']['access']='yes'
            record['contentSHA256']=V.digest(record['featureCollection']);path.unlink();manifest['tiles'][0]['vector']=V.write_gzip_json(path,record)
            source.write_text(V.canonical_json(manifest)+'\n')
            with self.assertRaises(N.NavigationFailure):self.prepare(source,f'drift-nav-{index}')
            self.assertFalse((self.root/f'drift-nav-{index}').exists())

    def test_duplicate_way_identity_is_rejected_even_when_first_is_not_a_road(self):
        source,_=self.road()
        self.rewrite_native(source,lambda native:native['ways'].insert(0,{**native['ways'][0],'layer':'rail'}))
        with self.assertRaisesRegex(N.NavigationFailure,'duplicate'):self.prepare(source)

    def test_lazy_segment_index_matches_unindexed_reference_and_reduces_candidates(self):
        nodes={str(i):(self.e-2500+i*25,self.n+10*math.sin(i/8)) for i in range(201)}
        source=package(self.root/'long-axis',nodes,[('100',list(nodes),{})],cells=((0,0),(1,0)))
        result,graphs,_=self.prepare(source)
        self.assertLess(result['report']['nativeSegmentCandidates'],result['report']['nativeSegmentsConsidered'])
        manifest=json.loads(source.read_text());native=N.read_asset(source.parent,manifest['nativeTopology']);ways,_=N.topology_index(native);rules,removed,_=N.restriction_rules(native,ways)
        for tile,expected in zip(manifest['tiles'],graphs):
            record=N.read_asset(source.parent,tile['vector'])
            reference,_=N.build_cell_graph(record,native,ways,rules,removed,V.file_sha256(source),'a'*64,
                                           core_sha=result['navigationCore']['sha256'],topology_sha=manifest['nativeTopology']['sha256'])
            self.assertEqual(reference,expected)

    def test_source_manifest_drift_during_generation_refuses_publication(self):
        source,_=self.road()
        def mutate(event):
            if event['phase']=='native-topology-ready':source.write_bytes(source.read_bytes()+b'\n')
        with self.assertRaisesRegex(N.NavigationFailure,'manifest changed'):
            N.prepare_navigation(source,self.root/'changed-manifest',progress=mutate)
        self.assertFalse((self.root/'changed-manifest').exists())

    def test_independent_qa_binds_native_evidence_and_refuses_a_fabricated_node_identity(self):
        source,_=self.road()
        self.prepare(source)
        nav_path=self.root/'nav/manifest.json'
        proof=Q.validate_navigation(source,nav_path,self.root/'QA.json',max_seconds=30)
        self.assertEqual(proof['status'],'passed')
        self.assertEqual(proof['cellsValidated'],1)
        self.assertEqual(proof['checks']['actualFrozenRouterValidatedGraphs'],1)
        declared=proof.pop('proofSHA256')
        self.assertEqual(declared,hashlib.sha256(Q.canonical(proof).encode('utf-8')).hexdigest())
        manifest=json.loads(nav_path.read_text());path=nav_path.parent/manifest['tiles'][0]['navigation']['path']
        graph=read_gzip(path);graph['nodes'][0][0]='1';path.unlink()
        manifest['tiles'][0]['navigation']=V.write_gzip_json(path,graph)
        nav_path.write_text(V.canonical_json(manifest)+'\n')
        with self.assertRaises(Q.NavigationQAError):
            Q.validate_navigation(source,nav_path,self.root/'QA-fabricated.json',max_seconds=30)
        self.assertFalse((self.root/'QA-fabricated.json').exists())


if __name__=='__main__':unittest.main()
