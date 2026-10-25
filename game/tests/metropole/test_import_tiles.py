"""Source-preserving tiling tests; optional geodata venv, no network."""
from __future__ import annotations

import gzip
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import osmium
from shapely.geometry import LineString, Polygon, box, shape

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('metropole_import_tiles', ROOT/'tools/metropole/import_tiles.py')
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def read_gzip(path):
    with gzip.open(path,'rt',encoding='utf-8') as stream:
        return json.load(stream)


def fixture_pbf(directory):
    """A real binary OSM fixture: courtyard across a tile seam + native turn."""
    edge=M.cell_bounds(0,0)[2]
    n=M.ORIGIN[1]
    coords={1:(edge-10,n-10),2:(edge+10,n-10),3:(edge+10,n+10),4:(edge-10,n+10),
            5:(edge-3,n-3),6:(edge-3,n+3),7:(edge+3,n+3),8:(edge+3,n-3),
            20:(edge-30,n-30),21:(edge,n-30),22:(edge+30,n-30),23:(edge,n-50)}
    nodes=[]
    for node_id,(easting,northing) in coords.items():
        lon,lat=M.TO_WGS84.transform(easting,northing)
        tag='<tag k="barrier" v="bollard"/><tag k="foot" v="yes"/><tag k="motor_vehicle" v="no"/>' if node_id==21 else ''
        nodes.append(f'<node id="{node_id}" version="1" lat="{lat:.12f}" lon="{lon:.12f}">{tag}</node>')
    xml='''<?xml version="1.0" encoding="UTF-8"?><osm version="0.6" generator="metropole-tests">'''+''.join(nodes)+'''
      <way id="100" version="1"><nd ref="20"/><nd ref="21"/><nd ref="22"/><tag k="highway" v="residential"/><tag k="name" v="Rue test"/><tag k="oneway" v="yes"/></way>
      <way id="101" version="1"><nd ref="21"/><nd ref="23"/><tag k="highway" v="service"/></way>
      <way id="200" version="1"><nd ref="1"/><nd ref="2"/><nd ref="3"/><nd ref="4"/><nd ref="1"/></way>
      <way id="201" version="1"><nd ref="5"/><nd ref="6"/><nd ref="7"/><nd ref="8"/><nd ref="5"/></way>
      <way id="400" version="1"><nd ref="20"/><nd ref="21"/><nd ref="23"/><tag k="building" v="yes"/></way>
      <way id="401" version="1"><nd ref="20"/><nd ref="21"/><nd ref="23"/><nd ref="20"/><tag k="building:part" v="no"/></way>
      <relation id="300" version="1"><member type="way" ref="200" role="outer"/><member type="way" ref="201" role="inner"/><tag k="type" v="multipolygon"/><tag k="building" v="yes"/><tag k="height" v="12"/></relation>
      <relation id="301" version="1"><member type="way" ref="100" role="from"/><member type="node" ref="21" role="via"/><member type="way" ref="101" role="to"/><tag k="type" v="restriction"/><tag k="restriction" v="no_right_turn"/></relation>
    </osm>'''
    source=directory/'source.osm'
    source.write_text(xml,encoding='utf-8')
    pbf=directory/'source.osm.pbf'
    header=osmium.io.Header()
    header.set('generator','metropole-tests')
    header.set('osmosis_replication_timestamp','2026-09-18T23:00:00Z')
    lonslats=[M.TO_WGS84.transform(*point) for point in coords.values()]
    header.add_box(osmium.osm.Box(osmium.osm.Location(min(p[0] for p in lonslats),min(p[1] for p in lonslats)),
                                  osmium.osm.Location(max(p[0] for p in lonslats),max(p[1] for p in lonslats))))
    with osmium.SimpleWriter(str(pbf),header=header) as writer:
        for entity in osmium.FileProcessor(str(source)):
            writer.add(entity)
    return pbf


class GeometryTests(unittest.TestCase):
    def test_historical_origin_and_extended_ids(self):
        self.assertEqual(M.cell_bounds(0,0), (892826.6480966414,6247149.566415883,893076.6480966414,6247399.566415883))
        self.assertEqual(M.cell_id(0,0),'V52-MC-33')
        self.assertEqual(M.cell_id(-2,1),'V52-MC-41')
        self.assertEqual(M.cell_id(-120,-210),'V52-MC-W120-N210')
        self.assertLess(M.cell_bounds(0,1)[1],M.cell_bounds(0,0)[1])

    def test_false_building_part_tags_do_not_create_buildings(self):
        for value in ['no','false','0','']:
            self.assertIsNone(M.polygon_layer({'building:part':value}))
        self.assertEqual(M.polygon_layer({'building':'cathedral','building:part':'no'}),'buildings')

    def test_clipping_preserves_courtyard_area_without_cut_cell_walls(self):
        polygon=Polygon([(0,0),(20,0),(20,20),(0,20)],holes=[[(7,7),(7,13),(13,13),(13,7)]])
        props={'canonical_id':'osm/relation/1','soma:layer':'buildings'}
        original=json.dumps(props,sort_keys=True)
        pieces=[M.clip_feature(polygon,props,box(-1,-1,10,21)),M.clip_feature(polygon,props,box(10,-1,21,21))]
        total=0
        for f in pieces:
            for mesh in f['properties']['soma:mesh53']:
                total+=mesh['areaM2']
                triangle_area=sum(Polygon(t).area for t in mesh['trianglesL93'])
                self.assertAlmostEqual(triangle_area,mesh['areaM2'],places=6)
                for a,b in mesh['wallsL93']:
                    self.assertTrue(polygon.boundary.covers(LineString([a,b])))
                    self.assertFalse(a[0]==b[0]==10,'No invented vertical cut-cell wall.')
        self.assertAlmostEqual(total,polygon.area,places=6)
        self.assertEqual(json.dumps(props,sort_keys=True),original)

    def test_declared_wgs84_boundary_rejects_projected_coordinate_input(self):
        with tempfile.TemporaryDirectory() as name:
            p=Path(name)/'boundary.json'
            p.write_text(json.dumps({'type':'Polygon','coordinates':[[[890000,6240000],[891000,6240000],[891000,6241000],[890000,6240000]]]}))
            with self.assertRaisesRegex(M.ImportFailure,'WGS84'):
                M.requested_extent(boundary_path=p)

    @unittest.skipUnless(shutil.which('node'), 'Node is needed to execute the frozen geographic validator.')
    def test_real_lambert93_numerical_sliver_passes_frozen_core_without_moving_source(self):
        # Published source cell V52-MC-E12-N62 / osm/way/92756305. Earcut's
        # redundant triangle had area 1.1824e-10 m² and altitude 3.22e-11 m;
        # its browser centroid rounded outside despite GEOS covering it.
        ring = [[895886.8283585871,6262832.060919123], [895886.9319777212,6262823.390080366],
            [895898.4282745603,6262823.742358627], [895898.4691290504,6262822.409146771],
            [895901.5456033865,6262822.503421944], [895901.3549461082,6262828.72507707],
            [895901.3209001664,6262829.836086888], [895898.2410248185,6262829.852912803],
            [895898.2470846501,6262832.299615311], [895886.8283585871,6262832.060919123]]
        polygon = Polygon(ring)
        original = polygon.wkb
        mesh = M.mesh_for_polygon(polygon, polygon.boundary)
        self.assertEqual(polygon.wkb, original)
        self.assertEqual(mesh['ringsL93'], [list(polygon.exterior.coords)])
        self.assertAlmostEqual(sum(Polygon(t).area for t in mesh['trianglesL93']), polygon.area, places=8)
        self.assertAlmostEqual(sum(LineString(w).length for w in mesh['wallsL93']), polygon.length, places=8)
        feature = {'type':'Feature','id':'osm/way/92756305',
            'geometry':M.mapping(M.transform(M.TO_WGS84.transform,polygon)),
            'properties':{'canonical_id':'osm/way/92756305','building':'yes','soma:layer':'buildings',
                'soma:metricGeometry':M.mapping(polygon),'soma:mesh53':[mesh]}}
        bounds = M.cell_bounds(12,-62)
        record = {'schema':M.CELL_SCHEMA,'cellId':M.cell_id(12,-62),'boundsL93':list(bounds),
            'boundsWGS84':M.bounds_wgs84(bounds),
            'sourceReceipt':{'id':'qa-real-precision-regression','sha256':'a'*64,'license':'QA fixture',
                'attribution':'QA regression using source polygon coordinates, not certified geographic coverage'},
            'featureCollection':{'type':'FeatureCollection','features':[feature]}}
        script = r"""const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync(process.argv[1],'utf8');
const source=html.match(/<script[^>]*id="soma-v53-core"[^>]*>([\s\S]*?)<\/script>/)[1];
const context=vm.createContext({module:{exports:{}}});vm.runInContext(source,context);
const core=context.module.exports,row=JSON.parse(fs.readFileSync(0,'utf8'));
const old=[[895901.5456033865,6262822.503421944],[895901.3549461082,6262828.72507707],[895901.3209001664,6262829.836086888]];
const centroid=[old.reduce((s,p)=>s+p[0],0)/3,old.reduce((s,p)=>s+p[1],0)/3];
assert.equal(core.inPolygon(centroid,row.featureCollection.features[0].properties['soma:mesh53'][0].ringsL93.map(r=>r.slice(0,-1))),false);
assert.doesNotThrow(()=>core.normalizeRecord(row,row.cellId,{cells:[{id:row.cellId,boundsL93:row.boundsL93}]}));"""
        result = subprocess.run(['node','-e',script,str(ROOT/'baseline/v66.html')],input=json.dumps(record),
            text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_small_real_triangles_are_not_removed_by_a_blanket_area_threshold(self):
        polygon=Polygon([(891000,6246000),(891000.001,6246000),(891000,6246000.001)])
        mesh=M.mesh_for_polygon(polygon,polygon.boundary)
        self.assertEqual(len(mesh['trianglesL93']),1)
        self.assertAlmostEqual(Polygon(mesh['trianglesL93'][0]).area,polygon.area,places=12)

    def test_non_degenerate_triangle_in_a_courtyard_is_quarantined(self):
        polygon=Polygon([(0,0),(10,0),(10,10),(0,10)],holes=[[(3,3),(3,7),(7,7),(7,3)]])
        with patch.object(M.mapbox_earcut,'triangulate_float64',return_value=M.np.asarray([0,1,2],dtype=M.np.uint32)):
            with self.assertRaisesRegex(M.ImportFailure,'centroid-outside-runtime-footprint'):
                M.mesh_for_polygon(polygon,polygon.boundary)


class BinaryPbfTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.root=Path(self.temporary.name)
        self.pbf=fixture_pbf(self.root)
        self.receipt={'id':'binary-test-fixture','license':'ODbL-1.0','attribution':'Synthetic QA fixture, not real metropolitan coverage'}

    def tearDown(self):
        self.temporary.cleanup()

    def prepare(self,name='world',**kwargs):
        return M.prepare_tiles(self.pbf,self.root/name,self.receipt,**kwargs)

    def test_binary_import_keeps_native_refs_turn_restriction_and_hole(self):
        manifest=self.prepare()
        self.assertEqual(manifest['schema'],'soma-metropole/vector-tiles/1')
        self.assertTrue(manifest['coverageExplicitPartial'])
        self.assertFalse(manifest['completeMetropole'])
        self.assertEqual(manifest['source']['sha256'],M.file_sha256(self.pbf))
        self.assertEqual(manifest['source']['date'],'2026-09-18T23:00:00Z')
        self.assertTrue(all(t['terrain'] is None and t['navigation'] is None for t in manifest['tiles']))
        features=[]
        for tile in manifest['tiles']:
            asset=self.root/'world'/tile['vector']['path']
            self.assertEqual(M.file_sha256(asset),tile['vector']['sha256'])
            record=read_gzip(asset)
            self.assertFalse(record['certification']['playable'])
            self.assertFalse(record['certification']['terrainAvailable'])
            features.extend(record['featureCollection']['features'])
        building=[f for f in features if f['id']=='osm/relation/300']
        self.assertEqual(len(building),2)
        self.assertTrue(all(f['properties']['soma:member_ways']==['200','201'] for f in building))
        # Compare to the binary source, not the ideal fixture before OSM PBF's
        # coordinate quantisation (normally 1e-7 degree).
        positions={}
        for entity in osmium.FileProcessor(str(self.pbf)):
            if isinstance(entity,osmium.osm.Node):
                positions[entity.id]=M.TO_METRIC.transform(entity.location.lon,entity.location.lat)
        expected=Polygon([positions[i] for i in [1,2,3,4]],holes=[[positions[i] for i in [5,6,7,8]]])
        self.assertAlmostEqual(sum(m['areaM2'] for f in building for m in f['properties']['soma:mesh53']),expected.area,places=6)
        topology=read_gzip(self.root/'world'/manifest['nativeTopology']['path'])
        way=next(w for w in topology['ways'] if w['id']=='100')
        self.assertEqual(way['nodeRefs'],['20','21','22'])
        self.assertEqual(way['tags']['oneway'],'yes')
        self.assertTrue(topology['nodeTagsComplete'])
        self.assertEqual(topology['nodeTags']['21']['barrier'],'bollard')
        self.assertEqual(topology['nodeTags']['21']['foot'],'yes')
        self.assertEqual(topology['nodeTags']['21']['motor_vehicle'],'no')
        turn=next(r for r in topology['relations'] if r['id']=='301')
        self.assertEqual(turn['tags']['restriction'],'no_right_turn')
        self.assertEqual(turn['members'][1],{'type':'node','ref':'21','role':'via'})
        report=json.loads((self.root/'world/IMPORT_REPORT.json').read_text())
        self.assertTrue(any(r['sourceId']=='osm/way/400' and r['reason']=='open-building-way' for r in report['rejected']))
        self.assertFalse(any(f['id']=='osm/way/401' for f in features))

    def test_tile_outputs_repeat_byte_identically(self):
        first=self.prepare('first')
        second=self.prepare('second')
        self.assertEqual(first,second)
        self.assertEqual((self.root/'first/manifest.json').read_bytes(),(self.root/'second/manifest.json').read_bytes())
        for tile in first['tiles']:
            path=tile['vector']['path']
            self.assertEqual((self.root/'first'/path).read_bytes(),(self.root/'second'/path).read_bytes())

    def test_existing_user_output_and_checksum_failures_are_preserved(self):
        target=self.root/'existing';target.mkdir();(target/'user.txt').write_text('keep')
        with self.assertRaisesRegex(M.ImportFailure,'already exists'):
            M.prepare_tiles(self.pbf,target,self.receipt)
        self.assertEqual((target/'user.txt').read_text(),'keep')
        with self.assertRaisesRegex(M.ImportFailure,'SHA256'):
            M.prepare_tiles(self.pbf,self.root/'bad-sha',{**self.receipt,'sha256':'0'*64})
        self.assertFalse((self.root/'bad-sha').exists())

    def test_budget_failure_never_publishes_a_partial_world(self):
        with self.assertRaisesRegex(M.ImportFailure,'budget|beyond'):
            self.prepare('too-small',max_features=1)
        self.assertFalse((self.root/'too-small').exists())
        self.assertEqual(list(self.root.glob('.metropole-import-*')),[])
        with self.assertRaisesRegex(M.ImportFailure,'decoded-byte budget'):
            self.prepare('byte-budget',max_tile_bytes=1)
        self.assertFalse((self.root/'byte-budget').exists())

    def test_runtime_geometry_violation_is_quarantined_before_any_world_is_published(self):
        with patch.object(M,'mesh_for_polygon',side_effect=M.ImportFailure('triangulation-centroid-outside-runtime-footprint')):
            with self.assertRaisesRegex(M.ImportFailure,r'Cell V52-MC-.*osm/relation/300.*centroid-outside-runtime-footprint'):
                self.prepare('invalid-runtime-mesh')
        self.assertFalse((self.root/'invalid-runtime-mesh').exists())
        self.assertEqual(list(self.root.glob('.metropole-import-*')),[])

    def test_requested_bounds_limit_tiles_without_claiming_source_coverage(self):
        b=M.cell_bounds(0,0)
        manifest=self.prepare(bounds_l93=[b[0]+1,b[1]+1,b[2]-1,b[3]-1])
        self.assertEqual(len(manifest['tiles']),1)
        self.assertEqual(manifest['tiles'][0]['cellId'],M.cell_id(0,0))
        self.assertTrue(manifest['coverageExplicitPartial'])
        self.assertIsNone(manifest['boundary'])
        self.assertIsNotNone(manifest['sourceBoundsWGS84'])

    def test_exact_tile_extent_does_not_emit_neighbours_that_only_touch_an_edge(self):
        manifest=self.prepare(bounds_l93=list(M.cell_bounds(0,0)))
        self.assertEqual([tile['cellId'] for tile in manifest['tiles']],[M.cell_id(0,0)])


if __name__=='__main__':
    unittest.main()
