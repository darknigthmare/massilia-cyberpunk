import hashlib
import importlib.util
import io
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout

ROOT=Path(__file__).resolve().parents[2]
SPEC=importlib.util.spec_from_file_location('viewer_builder',ROOT/'tools/build_metropole_viewer.py')
M=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(M)


class ViewerBuilderTests(unittest.TestCase):
    @staticmethod
    def canonical(value):
        return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')

    def seal_anchors(self,table,*,point_features=True):
        if point_features:
            descriptor=table['sources']['pointFeatures'];raw=self.canonical(descriptor['featureCollection'])
            descriptor.update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        table['proofSHA256']=hashlib.sha256(self.canonical({k:v for k,v in table.items() if k!='proofSHA256'})).hexdigest()
        return table

    def anchors_fixture(self):
        # Synthetic administrative boxes and a synthetic OSM node are test
        # evidence only. They are never written into production metadata.
        geometry=lambda x:{'type':'Polygon','coordinates':[[[x,43],[x+.02,43],[x+.02,43.02],[x,43.02],[x,43]]]}
        communes={'13001':{'name':'Commune QA alpha','geometry':geometry(5)},
            '13002':{'name':'Commune QA bêta','geometry':geometry(5.1)}}
        metric={'type':'Point','coordinates':[863997.7555285319,6214383.026653946]}
        geom_sha=hashlib.sha256(self.canonical(metric)).hexdigest()
        feature={'type':'Feature','id':'osm/node/123','geometry':{'type':'Point','coordinates':[5.01,43.01]},
            'properties':{'canonical_id':'osm/node/123','name':'Commune QA alpha','place':'village','ref:INSEE':'13001',
                'soma:layer':'pois','soma:metricGeometry':metric,'soma:geometry_sha256':geom_sha}}
        row={'code':'13001','name':'Commune QA alpha','status':'source-place','canonicalId':'osm/node/123','nodeId':123,
            'pointWGS84':[5.01,43.01],'pointL93':metric['coordinates'].copy(),'geometrySHA256':geom_sha,
            'sourcePbfSHA256':'a'*64,'vectorManifestSHA256':'b'*64,'cellId':'V52-MC-W116-S132',
            'contentSHA256':'c'*64,'cellContentSHA256':'c'*64,
            'evidence':{'canonicalId':'osm/node/123','nodeId':123,'matchedBy':'ref:INSEE','refINSEE':'13001',
                'place':'village','sourceName':'Commune QA alpha','withinCommune':True,'unique':True,
                'adminCentreRelations':[],'candidateIds':['osm/node/123']}}
        fallback={'code':'13002','name':'Commune QA bêta','status':'contour-fallback',
            'evidence':{'candidateIds':[],'reason':'no-unique-source-place','withinCommune':True}}
        table={'schema':'soma-metropole/settlement-anchors/1','version':'0.69.0','sourcePbfSHA256':'a'*64,
            'vectorManifestSHA256':'b'*64,'boundarySHA256':'d'*64,'territorySHA256':'e'*64,
            'certifiedOneToOne':False,'geometryModified':False,
            'coverage':{'communeCodes':['13001','13002'],'communeCount':2,'sourcePointCount':1,'contourFallbackCount':1},
            'sources':{'vectorManifest':{'sha256':'b'*64,'bytes':100,'receiptOnly':True},
                'canonicalStore':{'sha256':'f'*64,'bytes':200,'receiptOnly':True},
                'communeContours':{'path':'acquisition/communes-qa.geojson','sha256':'1'*64,'bytes':300},
                'pointFeatures':{'encoding':'inline-json','featureCollection':{'type':'FeatureCollection','features':[feature]}}},
            'anchors':{'13001':row,'13002':fallback}}
        return self.seal_anchors(table),communes,'d'*64

    def fixture(self,directory):
        path=directory/'source.html'
        path.write_text(''.join(f'<script id="{name}">/* pure fixture core */</script>'for name in
            ['soma-v53-core','soma-v56-terrain-core','soma-v59-core'])+
            '<script id="campaign-save">localStorage.setItem("NEVER_INCLUDE_CAMPAIGN_STORAGE","x")</script>')
        return path

    def test_builder_whitelists_only_pure_cores_and_never_includes_campaign_storage(self):
        with tempfile.TemporaryDirectory() as name:
            source=self.fixture(Path(name));metadata={'parts':{},'territory':{'communes':[]}}
            with patch.object(M,'metadata',return_value=metadata):
                output=M.build(source,hashlib.sha256(source.read_bytes()).hexdigest())
            self.assertNotIn(b'NEVER_INCLUDE_CAMPAIGN_STORAGE',output)
            self.assertNotIn(b'<script src=',output)
            self.assertNotIn(b'<!-- VIEWER_MODULES -->',output)
            self.assertIn(b'viewer-geographic-core',output)

    def test_source_hash_or_missing_core_refuses_build_before_writing_output(self):
        with tempfile.TemporaryDirectory() as name:
            source=self.fixture(Path(name))
            with self.assertRaisesRegex(ValueError,'SHA256'):M.build(source,'0'*64)
            source.write_text('<html></html>')
            with patch.object(M,'metadata',return_value={'parts':{}}):
                with self.assertRaisesRegex(ValueError,'Script absent'):M.build(source,M.sha(source.read_bytes()))

    def test_verify_does_not_rewrite_generated_file(self):
        with tempfile.TemporaryDirectory() as name:
            output=Path(name)/'viewer.html';output.write_bytes(b'existing');before=output.stat().st_mtime_ns
            with patch.object(M,'build',return_value=b'existing'),patch('sys.argv',['builder','--verify','--output',str(output)]),redirect_stdout(io.StringIO()):M.main()
            self.assertEqual(output.stat().st_mtime_ns,before)

    def test_derived_commune_anchor_stays_in_the_source_polygon_and_outside_holes(self):
        outer=[[0,0],[10,0],[10,10],[0,10],[0,0]];hole=[[3,3],[7,3],[7,7],[3,7],[3,3]]
        point=M.source_anchor({'type':'Polygon','coordinates':[outer,hole]})
        self.assertTrue(M.inside(point,outer));self.assertFalse(M.inside(point,hole))

    def test_audited_source_anchor_and_explicit_fallback_are_returned_without_mutation(self):
        table,communes,boundary=self.anchors_fixture();before=copy.deepcopy(table);before_communes=copy.deepcopy(communes)
        rows=M.audited_settlement_anchors(table,communes,boundary)
        self.assertEqual(rows,table['anchors']);self.assertEqual(table,before);self.assertEqual(communes,before_communes)
        self.assertEqual(rows['13001']['pointWGS84'],[5.01,43.01]);self.assertEqual(rows['13002']['status'],'contour-fallback')
        self.assertNotIn('pointWGS84',rows['13002']);self.assertNotIn('canonicalId',rows['13002'])
        multipolygon=copy.deepcopy(communes);polygon=multipolygon['13001']['geometry']
        multipolygon['13001']['geometry']={'type':'MultiPolygon','coordinates':[polygon['coordinates']]}
        self.assertEqual(M.audited_settlement_anchors(table,multipolygon,boundary),rows)
        by_name=copy.deepcopy(table);by_name['anchors']['13001']['evidence'].update(matchedBy='official-name-normalized',refINSEE=None)
        by_name['sources']['pointFeatures']['featureCollection']['features'][0]['properties'].pop('ref:INSEE')
        self.seal_anchors(by_name)
        self.assertEqual(M.audited_settlement_anchors(by_name,communes,boundary)['13001']['evidence']['matchedBy'],'official-name-normalized')

    def test_anchor_proof_seal_schema_boundary_and_exact_commune_set_are_required(self):
        for kind in ['seal','schema','boundary','code-set','coverage-count','coverage-source-count']:
            with self.subTest(kind=kind):
                table,communes,boundary=self.anchors_fixture()
                if kind=='seal':table['proofSHA256']='0'*64
                elif kind=='schema':table['schema']='wrong/1';self.seal_anchors(table)
                elif kind=='boundary':boundary='0'*64
                elif kind=='code-set':communes['13003']={'name':'Missing QA commune','geometry':communes['13002']['geometry']}
                elif kind=='coverage-count':table['coverage']['communeCount']=3;self.seal_anchors(table)
                else:table['coverage']['sourcePointCount']=2;self.seal_anchors(table)
                with self.assertRaises(ValueError):M.audited_settlement_anchors(table,communes,boundary)

    def test_resigned_anchor_code_name_node_and_canonical_identity_drift_are_rejected(self):
        patches=[{'code':'13002'},{'name':'Wrong QA name'},{'canonicalId':'osm/node/124'},{'nodeId':124},
            {'cellContentSHA256':'0'*64},{'sourcePbfSHA256':'0'*64},{'vectorManifestSHA256':'0'*64},
            {'geometrySHA256':'0'*64}]
        for patch in patches:
            with self.subTest(patch=patch):
                table,communes,boundary=self.anchors_fixture();table['anchors']['13001'].update(patch);self.seal_anchors(table)
                with self.assertRaises(ValueError):M.audited_settlement_anchors(table,communes,boundary)

    def test_inline_feature_source_receipts_and_metric_geometry_are_verified_beyond_the_table_seal(self):
        for kind in ['feature-hash','feature-bytes','manifest-receipt','store-receipt','contour-path','feature-id','feature-canonical',
            'feature-wgs','feature-l93','metric-hash','feature-place','feature-insee']:
            with self.subTest(kind=kind):
                table,communes,boundary=self.anchors_fixture();sources=table['sources'];descriptor=sources['pointFeatures']
                feature=descriptor['featureCollection']['features'][0];properties=feature['properties']
                if kind=='feature-hash':descriptor['sha256']='0'*64
                elif kind=='feature-bytes':descriptor['bytes']+=1
                elif kind=='manifest-receipt':sources['vectorManifest']['sha256']='0'*64
                elif kind=='store-receipt':sources['canonicalStore']['receiptOnly']=False
                elif kind=='contour-path':sources['communeContours']['path']='../communes.geojson'
                elif kind=='feature-id':feature['id']='osm/node/124'
                elif kind=='feature-canonical':properties['canonical_id']='osm/node/124'
                elif kind=='feature-wgs':feature['geometry']['coordinates'][0]+=.001
                elif kind=='feature-l93':properties['soma:metricGeometry']['coordinates'][0]+=1
                elif kind=='metric-hash':properties['soma:geometry_sha256']='0'*64
                elif kind=='feature-place':properties['place']='hamlet'
                else:properties['ref:INSEE']='13002'
                self.seal_anchors(table,point_features=kind not in ['feature-hash','feature-bytes'])
                with self.assertRaises(ValueError):M.audited_settlement_anchors(table,communes,boundary)

    def test_source_place_must_be_inside_the_official_commune_and_outside_holes(self):
        for geometry in [
            {'type':'Polygon','coordinates':[[[6,43],[6.02,43],[6.02,43.02],[6,43.02],[6,43]]]},
            {'type':'Polygon','coordinates':[[[5,43],[5.02,43],[5.02,43.02],[5,43.02],[5,43]],
                [[5.005,43.005],[5.015,43.005],[5.015,43.015],[5.005,43.015],[5.005,43.005]]]}]:
            table,communes,boundary=self.anchors_fixture();communes['13001']['geometry']=geometry
            with self.assertRaises(ValueError):M.audited_settlement_anchors(table,communes,boundary)

    def test_source_anchor_nonfinite_coordinates_and_ambiguous_evidence_are_rejected(self):
        for field,value in [('pointWGS84',[float('nan'),43.01]),('pointL93',[float('inf'),6214383]),
            ('pointWGS84',[None,43.01])]:
            table,communes,boundary=self.anchors_fixture();table['anchors']['13001'][field]=value
            with self.assertRaises(ValueError):M.audited_settlement_anchors(table,communes,boundary)
        for patch in [{'unique':False},{'withinCommune':False},{'canonicalId':'osm/node/999'},{'nodeId':999},
            {'matchedBy':'centroid'},{'matchedBy':'admin_centre-tiebreak','adminCentreRelations':[]}]:
            with self.subTest(patch=patch):
                table,communes,boundary=self.anchors_fixture();table['anchors']['13001']['evidence'].update(patch);self.seal_anchors(table)
                with self.assertRaises(ValueError):M.audited_settlement_anchors(table,communes,boundary)

    def test_contour_fallback_must_not_claim_an_unverified_source_identity_or_point(self):
        for patch in [{'canonicalId':'osm/node/999'},{'nodeId':999},{'pointWGS84':[5.11,43.01]},
            {'pointL93':[870000,6214000]},{'status':'source-place'}]:
            with self.subTest(patch=patch):
                table,communes,boundary=self.anchors_fixture();table['anchors']['13002'].update(patch);self.seal_anchors(table)
                with self.assertRaises(ValueError):M.audited_settlement_anchors(table,communes,boundary)

    def test_anchor_source_is_its_own_receipt_and_is_not_hardwired_to_the_current_world_pbf(self):
        table,communes,boundary=self.anchors_fixture();table['sourcePbfSHA256']='9'*64
        table['anchors']['13001']['sourcePbfSHA256']='9'*64;self.seal_anchors(table)
        self.assertEqual(M.audited_settlement_anchors(table,communes,boundary)['13001']['sourcePbfSHA256'],'9'*64)


if __name__=='__main__':unittest.main()
