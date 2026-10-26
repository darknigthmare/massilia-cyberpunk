import dataclasses
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

TOOL = Path(__file__).resolve().parents[2]/'tools/metropole/acquire_bdtopo.py'
spec = importlib.util.spec_from_file_location('acquire_bdtopo_under_test', TOOL)
audit = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = audit
spec.loader.exec_module(audit)
try:
    import shapely
    from shapely.geometry import box, mapping
    from shapely.ops import transform
    from pyproj import Transformer
    GIS = True
except ImportError:
    GIS = False


def feature(ident='B01', height=12, west=893020):
    return {'type':'Feature','id':'batiment.'+ident,'properties':{'cleabs':ident,'hauteur':height,'altitude_minimale_sol':10},'geometry':{'type':'Polygon','coordinates':[[[west,6247020],[west+10,6247020],[west+10,6247030],[west,6247030],[west,6247020]]]}}


def page(features, matched=None, crs=audit.CRS):
    return audit.canonical({'type':'FeatureCollection','features':features,'numberMatched':len(features) if matched is None else matched,'numberReturned':len(features),'crs':None if crs is None else {'type':'name','properties':{'name':crs}}}).encode()


class PageProtocolTests(unittest.TestCase):
    def setUp(self):
        self.limits = audit.Limits(page_size=2, page_bytes=4096)

    def test_null_crs_is_only_admissible_for_empty_response(self):
        self.assertEqual(audit.parse_page(page([], crs=None),limit=self.limits)['numberMatched'],0)
        with self.assertRaisesRegex(audit.AcquisitionError,'nonempty'):
            audit.parse_page(page([feature()],crs=None),limit=self.limits)
        with self.assertRaisesRegex(audit.AcquisitionError,'Missing'):
            audit.parse_page(page([],matched=1,crs=None),limit=self.limits)

    def test_count_change_and_incomplete_page_sequence_are_refused(self):
        with self.assertRaisesRegex(audit.AcquisitionError,'count changed'):
            audit.parse_page(page([feature('B02')],matched=3),limit=self.limits,expected=2,seen={'B01'},previous='B01')
        with self.assertRaisesRegex(audit.AcquisitionError,'Missing'):
            audit.parse_page(page([],matched=2),limit=self.limits,expected=2,seen={'B01'})

    def test_duplicate_unsorted_and_overlapping_pages_are_refused(self):
        for raw,kwargs in [(page([feature(),feature()]),{}),(page([feature('B02'),feature('B01')]),{}),(page([feature('B01')],matched=2),{'seen':{'B01'},'previous':'B01'})]:
            with self.subTest(kwargs=kwargs),self.assertRaisesRegex(audit.AcquisitionError,'pagination identities'):
                audit.parse_page(raw,limit=self.limits,**kwargs)

    def test_wrong_crs_and_malformed_service_responses_are_refused(self):
        for raw in [b'<ExceptionReport/>',b'[]',b'{"type":"FeatureCollection","features":null}',page([feature()],crs='EPSG:4326'),page([{'type':'Feature','properties':None}])]:
            with self.subTest(raw=raw[:50]),self.assertRaises(audit.AcquisitionError):
                audit.parse_page(raw,limit=self.limits)
        data=json.loads(page([feature()]));data['numberReturned']=True
        with self.assertRaises(audit.AcquisitionError):
            audit.parse_page(json.dumps(data).encode(),limit=self.limits)

    def test_response_bytes_and_fixed_upper_budgets_are_enforced(self):
        with self.assertRaisesRegex(audit.AcquisitionError,'byte budget'):
            audit.parse_page(b' ' * 4097,limit=self.limits)
        for change in ({'workers':3},{'source_bytes':1500000001},{'max_requests':1001},{'step':0},{'page_bytes':16777217}):
            with self.subTest(change=change),self.assertRaises(audit.AcquisitionError):
                dataclasses.replace(self.limits,**change).validate()

    def test_unknown_source_datum_units_and_height_kind_are_refused(self):
        receipt = source_receipt()
        for field,value in [('units','ft'),('verticalDatum','unknown'),('heightKind','ridge'),('date','unknown')]:
            bad={**receipt,field:value}
            with self.subTest(field=field),self.assertRaises(audit.AcquisitionError):
                audit.source_metadata(bad)


def source_receipt():
    return {'provider':'IGN','product':'BD TOPO v3','license':'Licence Ouverte 2.0','attribution':'IGN','date':'2026-06-15','crs':'EPSG:2154','units':'m','verticalDatum':'NGF-IGN69','fields':audit.FIELDS,'heightKind':'eaves','heightMeaning':'Lowest ground to gutter; roof ridge unknown; zero unknown.','sourceMetadataSHA256':'a'*64,'sourceSpecificationSHA256':'b'*64}


@unittest.skipUnless(GIS,'Optional Shapely/pyproj GIS environment required')
class RealGeometryAndResumeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.boundary=self.root/'boundary.geojson';self.receipt=self.root/'source.json';self.output=self.root/'output'
        polygon=box(893000,6247000,893100,6247100)
        inverse=Transformer.from_crs('EPSG:2154','EPSG:4326',always_xy=True).transform
        self.boundary.write_text(json.dumps({'type':'FeatureCollection','features':[{'type':'Feature','properties':{},'geometry':mapping(transform(inverse,polygon))}]}))
        self.receipt.write_text(json.dumps(source_receipt()))
        self.limits=audit.Limits(workers=1,page_size=1,page_bytes=4096,source_bytes=65536)

    def acquire(self,fetch,resume=False,limits=None):
        return audit.acquire(self.boundary,self.receipt,self.output,limits=limits or self.limits,resume=resume,fetch=fetch,log=lambda v:None)

    def transport(self,features,calls,fail_at=None):
        def fetch(url,maximum,timeout):
            from urllib.parse import parse_qs,urlsplit
            params=parse_qs(urlsplit(url).query);start=int(params['STARTINDEX'][0]);calls.append(start)
            if fail_at==start:raise RuntimeError('simulated interrupted public service')
            raw=page(features[start:start+1],matched=len(features),crs=audit.CRS if features else None)
            return raw,{'status':200,'contentType':'application/json'}
        return fetch

    def test_resume_after_failure_keeps_first_page_and_continues_sorted_sequence(self):
        features=[feature('B01'),feature('B02',west=893050)];first=[]
        with self.assertRaisesRegex(RuntimeError,'interrupted'):
            self.acquire(self.transport(features,first,fail_at=1))
        self.assertEqual(first,[0,1])
        saved_page=self.output/'pages/q000-000-p000.geojson';saved_hash=audit.file_sha(saved_page)
        second=[];result=self.acquire(self.transport(features,second),resume=True)
        self.assertEqual(second,[1]);self.assertEqual(result['uniqueIntersectingObjects'],2)
        self.assertEqual(audit.file_sha(saved_page),saved_hash)
        self.assertTrue(result['queryAcquisitionComplete']);self.assertFalse(result['runtimeIntegrationPerformed'])
        third=[];again=self.acquire(self.transport(features,third),resume=True)
        self.assertEqual(third,[]);self.assertEqual(again['sourceSHA256'],result['sourceSHA256'])

    def test_full_crossing_geometry_is_retained_and_outside_feature_filtered(self):
        crossing=feature('B01',west=892995);outside=feature('B02',west=894000);calls=[]
        result=self.acquire(self.transport([crossing,outside],calls))
        self.assertEqual(result['uniqueIntersectingObjects'],1)
        with sqlite3.connect(self.output/'buildings.sqlite') as db:
            stored=json.loads(db.execute('SELECT feature_json FROM objects').fetchone()[0])
        self.assertEqual(stored,crossing);self.assertFalse(result['geometriesClipped'])

    def test_conflicting_duplicate_id_is_refused_including_changed_outside_geometry(self):
        db=sqlite3.connect(':memory:');self.addCleanup(db.close);db.executescript(audit.DDL)
        boundary=box(893000,6247000,893100,6247100)
        self.assertEqual(audit.insert_feature(db,feature(),'p1',boundary),'inserted')
        self.assertEqual(audit.insert_feature(db,feature(),'p2',boundary),'duplicate')
        for changed in [feature(height=14),feature(west=894000)]:
            with self.assertRaisesRegex(audit.AcquisitionError,'Conflicting source identity'):
                audit.insert_feature(db,changed,'p3',boundary)
        self.assertEqual(db.execute('SELECT count(*) FROM objects').fetchone()[0],1)
        self.assertEqual(db.execute('SELECT count(*) FROM object_pages').fetchone()[0],2)

    def test_resume_refuses_modified_page_or_changed_limits_before_network(self):
        features=[feature('B01'),feature('B02')];calls=[]
        with self.assertRaises(RuntimeError):
            self.acquire(self.transport(features,calls,fail_at=1))
        with self.assertRaisesRegex(audit.AcquisitionError,'budgets differ'):
            self.acquire(self.transport(features,[]),resume=True,limits=dataclasses.replace(self.limits,max_requests=999))
        path=self.output/'pages/q000-000-p000.geojson';path.write_bytes(path.read_bytes()+b' ')
        calls=[]
        with self.assertRaisesRegex(audit.AcquisitionError,'checksum differs'):
            self.acquire(self.transport(features,calls),resume=True)
        self.assertEqual(calls,[])

    def test_byte_budget_stops_before_next_request_and_leaves_resumable_state(self):
        calls=[];limit=dataclasses.replace(self.limits,source_bytes=4096)
        with self.assertRaisesRegex(audit.AcquisitionError,'budget reached'):
            self.acquire(self.transport([feature('B01'),feature('B02')],calls),limits=limit)
        self.assertEqual(calls,[0])
        progress=json.loads((self.output/'progress.json').read_text())
        self.assertEqual(progress['status'],'stopped-incomplete');self.assertEqual(progress['completedPages'],1)
        self.assertFalse((self.output/'source-index.json').exists())

    def test_empty_null_crs_response_can_complete_real_acquisition(self):
        calls=[];result=self.acquire(self.transport([],calls))
        self.assertEqual(calls,[0]);self.assertEqual(result['uniqueIntersectingObjects'],0)
        self.assertEqual(result['pages'][0]['numberMatched'],0)

    def test_completed_resume_checks_saved_boundary_provenance(self):
        self.acquire(self.transport([],[]))
        path=self.output/'boundary.geojson';path.write_bytes(path.read_bytes()+b' ')
        calls=[]
        with self.assertRaisesRegex(audit.AcquisitionError,'boundary/source metadata differs'):
            self.acquire(self.transport([],calls),resume=True)
        self.assertEqual(calls,[])

    def test_explicit_request_budget_and_existing_output_are_protected(self):
        calls=[]
        with self.assertRaisesRegex(audit.AcquisitionError,'budget reached'):
            self.acquire(self.transport([feature('B01'),feature('B02')],calls),limits=dataclasses.replace(self.limits,max_requests=1))
        with self.assertRaisesRegex(audit.AcquisitionError,'Output exists'):
            self.acquire(self.transport([],[]))


if __name__=='__main__':
    unittest.main()
