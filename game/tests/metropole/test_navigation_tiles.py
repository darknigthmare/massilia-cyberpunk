"""Real legacy router validation of conservative native-source tiled graphs."""
from __future__ import annotations

import gzip
import importlib.util
import json
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
                'boundsL93':list(bounds),'featureCollection':{'type':'FeatureCollection','features':features}}
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


if __name__=='__main__':unittest.main()
