"""Deliver measured eaves only for unchanged source footprints and cell hashes."""
from copy import deepcopy
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

GAME=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(GAME))
from tools import v69_heights as H
from tools.metropole.building_heights import binding_key, canonical, digest, HeightMatchError
from tools.metropole.bootstrap import embedded

SOURCE='a'*64
GEOMETRY='b'*64
CONTENT='c'*64
PARENT='d'*64
CELL='V52-MC-33'


def fixture():
    p={'canonical_id':'osm/way/1','soma:layer':'buildings','building':'yes','soma:geometry_sha256':GEOMETRY}
    records=[{'cellId':CELL,'contentSHA256':CONTENT,'sourceReceipt':{'sha256':SOURCE},
              'featureCollection':{'type':'FeatureCollection','features':[{'type':'Feature','id':'osm/way/1','properties':p}]}}]
    row={'canonicalId':'osm/way/1','sourceSHA256':SOURCE,'geometrySHA256':GEOMETRY,'cells':{CELL:CONTENT},
         'height':12.5,'groundAltitude':8.2,'iou':.99,'margin':.9,'reciprocalMargin':.8,'ignId':'IGN-TEST-1',
         'decision':'accepted-conservative-match','heightSource':'ign-bdtopo-height','method':'footprint-iou-unique-reciprocal'}
    proof={'schema':'soma-metropole/building-height-matches/1','sourceSHA256':SOURCE,'crs':'EPSG:2154','units':'m','verticalDatum':'NGF-IGN69',
           'ignSource':{'sha256':'e'*64,'crs':'EPSG:2154','units':'m','verticalDatum':'NGF-IGN69'},
           'policy':{'minimumIoU':.9,'minimumMargin':.15,'minimumReciprocalMargin':.15,'preserveExplicitOSMHeight':True,
                     'excludeActiveOSMParts':True,'deriveHeightFromAbsoluteRoofZ':False},
           'matches':{binding_key('osm/way/1',GEOMETRY,SOURCE):row},'statistics':{'accepted':1,'rejected':2},
           'parentMatchingProofSHA256':PARENT,'parentProofContentSHA256':'f'*64,'rejectedRowsOmitted':2,
           'heightKind':'eaves','accuracy':'source-match-not-certified','roofSurveyed':False,'roofGeometryPolicy':H.ROOF_POLICY,
           'newHeightAcquisition':False,'certifiedBuildings':0}
    proof['proofSHA256']=digest(proof)
    return proof,records


def reseal(proof):
    proof['proofSHA256']=digest({k:v for k,v in proof.items() if k!='proofSHA256'})
    return proof


class HeightDeliveryTests(unittest.TestCase):
    def test_reference_is_eaves_not_ridge_and_does_not_mutate_source_records(self):
        proof,records=fixture();before=deepcopy(records)
        self.assertIs(H.validate_height_bindings(proof,records,source_sha=SOURCE,expected_parent_sha=PARENT),proof)
        self.assertEqual(records,before)
        self.assertEqual(proof['heightKind'],'eaves');self.assertFalse(proof['roofSurveyed'])

    def test_geometry_source_and_every_fragment_cell_are_required(self):
        proof,records=fixture()
        changes=[lambda r:r[0]['sourceReceipt'].update(sha256='9'*64),
                 lambda r:r[0].update(contentSHA256='9'*64),
                 lambda r:r[0]['featureCollection']['features'][0]['properties'].update({'soma:geometry_sha256':'9'*64}),
                 lambda r:r[0]['featureCollection'].update(features=[]),
                 lambda r:r[0].update(v53Synthetic=True)]
        for change in changes:
            candidate=deepcopy(records);change(candidate)
            with self.assertRaises(HeightMatchError):H.validate_height_bindings(proof,candidate,expected_parent_sha=PARENT)
        changed=deepcopy(proof);next(iter(changed['matches'].values()))['cells']['V52-MC-34']='9'*64;reseal(changed)
        with self.assertRaisesRegex(HeightMatchError,'incomplete'):H.validate_height_bindings(changed,records,expected_parent_sha=PARENT)

    def test_osm_nonempty_height_parts_and_non_ground_structures_remain_prioritary(self):
        proof,records=fixture()
        tags=[{'height':v} for v in ('12','bad','0',0,False)]+[
            {'building:part':'yes'},{'building':'roof'},{'min_height':'2'},{'min_height':'unknown'},
            {'building:min_level':'1'},{'layer':'-1'},{'layer':'bad'},{'location':'underground'}]
        for properties in tags:
            candidate=deepcopy(records);candidate[0]['featureCollection']['features'][0]['properties'].update(properties)
            with self.subTest(properties=properties),self.assertRaisesRegex(HeightMatchError,'source policy'):
                H.validate_height_bindings(proof,candidate,expected_parent_sha=PARENT)
        for part in ('no','false','0',False,0):
            candidate=deepcopy(records);candidate[0]['featureCollection']['features'][0]['properties']['building:part']=part
            H.validate_height_bindings(proof,candidate,expected_parent_sha=PARENT)

    def test_compaction_preserves_metadata_and_reseals_only_accepted_rows(self):
        proof,_=fixture();parent={k:v for k,v in proof.items() if k not in {
            'parentMatchingProofSHA256','parentProofContentSHA256','rejectedRowsOmitted','proofSHA256'}}
        parent['rejected']=[{'reason':'fixture-1'},{'reason':'fixture-2'}];reseal(parent)
        with tempfile.TemporaryDirectory() as name:
            path=Path(name)/'original.json';raw=canonical(parent).encode();path.write_bytes(raw)
            sha=H.hashlib.sha256(raw).hexdigest();compact=H.compact_matches(path,expected_sha=sha)
            self.assertNotIn('rejected',compact);self.assertEqual(compact['matches'],parent['matches'])
            self.assertEqual(compact['statistics'],parent['statistics']);self.assertEqual(compact['policy'],parent['policy'])
            self.assertEqual(compact['parentMatchingProofSHA256'],sha)
            self.assertEqual(path.read_bytes(),raw)
            self.assertEqual(H.encoded_proof(compact),H.encoded_proof(compact))
            self.assertEqual(H.encoded_proof(compact)[4:8],b'\0'*4)
            with self.assertRaisesRegex(HeightMatchError,'pinned source'):H.compact_matches(path,expected_sha='0'*64)

    def test_gzip_loader_checks_proof_origin_and_both_byte_budgets(self):
        proof,records=fixture()
        with tempfile.TemporaryDirectory() as name:
            path=Path(name)/'height.json.gz';path.write_bytes(H.encoded_proof(proof))
            self.assertEqual(H.load_height_matches(path,records=records,expected_parent_sha=PARENT),proof)
            with self.assertRaises(HeightMatchError):H.load_height_matches(path,records=records,expected_parent_sha='0'*64)
            with patch.object(H,'MAX_COMPRESSED',10),self.assertRaisesRegex(HeightMatchError,'Compressed'):
                H.load_height_matches(path,records=records,expected_parent_sha=PARENT)
            with patch.object(H,'MAX_DECODED',10),self.assertRaisesRegex(HeightMatchError,'Decoded'):
                H.load_height_matches(path,records=records,expected_parent_sha=PARENT)
            changed=deepcopy(proof);next(iter(changed['matches'].values()))['height']=999;path.write_bytes(H.encoded_proof(changed))
            with self.assertRaisesRegex(HeightMatchError,'checksum'):H.load_height_matches(path,records=records,expected_parent_sha=PARENT)

    def test_shipped_matches_bind_to_all_original_records_without_gis(self):
        html=(GAME/'baseline/v66.html').read_text(encoding='utf-8');pack,_=embedded(html,'soma-v53-embedded-pack')
        proof=H.load_height_matches(GAME/'data/v69/building-height-matches.json.gz',records=pack['records'],source_sha=pack['sourceReceipt']['sha256'])
        self.assertEqual(len(proof['matches']),14279)
        self.assertEqual(proof['parentMatchingProofSHA256'],H.EXPECTED_PARENT_SHA256)


if __name__=='__main__':unittest.main()
