"""Geometry/provenance fixtures, not an acquisition of metropolitan IGN data."""
import copy
from dataclasses import replace
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys

from game.tools.metropole.building_heights import (
    DEFAULT_FIELDS, HeightMatchError, MatchLimits, binding_key, canonical, digest,
    match_building_heights, records_from_manifest, validate_matches,
)

GIS_AVAILABLE = importlib.util.find_spec('shapely') is not None
SOURCE = 'a' * 64
CELL_HASH = 'b' * 64
EAST, NORTH = 892000, 6247000


def ring(west=0, south=0, east=10, north=10):
    return [[EAST+west,NORTH+south],[EAST+east,NORTH+south],
            [EAST+east,NORTH+north],[EAST+west,NORTH+north],[EAST+west,NORTH+south]]


def feature(identity='osm/way/1', outer=None, holes=None, tags=None, walls=None, geometry_hash=None):
    rings = [outer or ring()] + (holes or [])
    geometry = {'type':'Polygon','coordinates':rings}
    p = {'canonical_id':identity,'soma:layer':'buildings','building':'yes',
         'soma:geometry_sha256':geometry_hash or digest(geometry),
         'soma:metricGeometry':geometry,'soma:mesh53':[{'ringsL93':rings,
           'wallsL93':walls if walls is not None else [[a,b] for r in rings for a,b in zip(r,r[1:])]}]}
    p.update(tags or {})
    return {'type':'Feature','id':identity,'properties':p}


def record(features=None, cell='cell-1'):
    return {'cellId':cell,'contentSHA256':CELL_HASH,'sourceReceipt':{'sha256':SOURCE},
            'featureCollection':{'type':'FeatureCollection','features':features if features is not None else [feature()]}}


def ign_feature(identity='IGN-FIXTURE-1', outer=None, height=12.5, ground=7, holes=None, **properties):
    return {'type':'Feature','geometry':{'type':'Polygon','coordinates':[outer or ring()]+(holes or [])},
            'properties':{'CLEABS':identity,'HAUTEUR':height,'Z_MIN_SOL':ground,**properties}}


@unittest.skipUnless(GIS_AVAILABLE, 'Run in the optional geodata venv with Shapely 2.1.2.')
class BuildingHeightMatchingTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='fixture-building-heights-')
        self.path = Path(self.directory.name)/'fixture-ign.geojson'

    def tearDown(self):
        self.directory.cleanup()

    def source(self, features, **metadata):
        source = {'type':'FeatureCollection','crs':{'type':'name','properties':{'name':'EPSG:2154'}},'features':features}
        source.update(metadata)
        raw = canonical(source).encode();self.path.write_bytes(raw)
        receipt = {'id':'fixture-only-no-acquisition','sha256':hashlib.sha256(raw).hexdigest(),
                   'license':'Licence Ouverte 2.0 (test fixture)','date':'2026-09-23',
                   'crs':'EPSG:2154','units':'m','verticalDatum':'NGF-IGN69','fields':DEFAULT_FIELDS.copy()}
        return receipt

    def match(self, records=None, features=None, **kwargs):
        receipt = self.source(features if features is not None else [ign_feature()])
        return match_building_heights(records if records is not None else [record()],self.path,receipt,**kwargs)

    def test_exact_match_has_complete_triple_binding_and_does_not_mutate_sources(self):
        records = [record()];before = copy.deepcopy(records)
        receipt = self.source([ign_feature()]);file_before = self.path.read_bytes();receipt_before = copy.deepcopy(receipt)
        report = match_building_heights(records,self.path,receipt)
        key = binding_key('osm/way/1',records[0]['featureCollection']['features'][0]['properties']['soma:geometry_sha256'],SOURCE)
        row = report['matches'][key]
        self.assertEqual(row['height'],12.5);self.assertEqual(row['groundAltitude'],7)
        self.assertEqual(row['ignId'],'IGN-FIXTURE-1')
        self.assertEqual(row['iou'],1);self.assertEqual(row['margin'],1);self.assertEqual(row['reciprocalMargin'],1)
        self.assertEqual(row['cells'],{'cell-1':CELL_HASH})
        self.assertFalse(report['newHeightAcquisition']);self.assertEqual(report['certifiedBuildings'],0)
        self.assertEqual(records,before);self.assertEqual(receipt,receipt_before);self.assertEqual(self.path.read_bytes(),file_before)
        self.assertEqual(validate_matches(report),report)

    def test_multicell_fragments_join_before_matching_without_a_cut_wall(self):
        full = {'type':'Polygon','coordinates':[ring()]};sha = digest(full)
        left, right = ring(0,0,5,10), ring(5,0,10,10)
        left_walls = [[a,b] for a,b in zip(left,left[1:]) if not (a[0]==b[0]==EAST+5)]
        right_walls = [[a,b] for a,b in zip(right,right[1:]) if not (a[0]==b[0]==EAST+5)]
        records = [record([feature(outer=left,walls=left_walls,geometry_hash=sha)],'left'),
                   record([feature(outer=right,walls=right_walls,geometry_hash=sha)],'right')]
        report = self.match(records)
        self.assertEqual(report['statistics']['osmBuildings'],1)
        self.assertEqual(report['statistics']['accepted'],1)
        self.assertEqual(next(iter(report['matches'].values()))['cells'],{'left':CELL_HASH,'right':CELL_HASH})

    def test_osm_explicit_height_is_never_overridden_even_when_malformed(self):
        for height in ['10','12 ft','0','unreadable']:
            with self.subTest(height=height):
                report = self.match([record([feature(tags={'height':height})])])
                self.assertFalse(report['matches'])
                self.assertEqual(report['rejected'][0]['reason'],'explicit-osm-height-preserved')

    def test_active_parts_are_excluded_but_the_string_no_is_not_a_part(self):
        for part, expected in [('yes',0),('roof',0),('no',1),('false',1)]:
            with self.subTest(part=part):
                report = self.match([record([feature(tags={'building:part':part})])])
                self.assertEqual(report['statistics']['accepted'],expected)

    def test_nearby_centroid_is_not_sufficient_without_footprint_iou(self):
        report = self.match(features=[ign_feature(outer=ring(1,0,11,10))])
        self.assertFalse(report['matches'])
        self.assertEqual(report['rejected'][0]['reason'],'insufficient-footprint-iou')

    def test_two_similar_ign_footprints_are_withheld_as_ambiguous(self):
        report = self.match(features=[ign_feature('IGN-A'),ign_feature('IGN-B',outer=ring(0,0,10.4,10))])
        self.assertFalse(report['matches'])
        self.assertEqual(report['rejected'][0]['reason'],'ambiguous-ign-candidates')
        self.assertLess(report['rejected'][0]['margin'],.15)

    def test_bad_metadata_candidate_is_not_dropped_to_make_a_good_one_unique(self):
        report = self.match(features=[ign_feature('IGN-A'),ign_feature('IGN-B',height=None)])
        self.assertFalse(report['matches'])
        self.assertEqual(report['rejected'][0]['reason'],'ambiguous-ign-candidates')

    def test_reciprocal_duplicate_osm_outlines_are_both_withheld(self):
        report = self.match([record([feature('osm/way/1'),feature('osm/way/2')])])
        self.assertFalse(report['matches'])
        self.assertEqual(report['statistics']['rejectedByReason'],{'ambiguous-reciprocal-osm-candidates':2})

    def test_an_explicit_height_outline_still_contests_an_unknown_duplicate(self):
        report = self.match([record([feature('osm/way/1',tags={'height':'10'}),feature('osm/way/2')])])
        self.assertFalse(report['matches'])
        self.assertEqual(report['statistics']['rejectedByReason'],{
            'explicit-osm-height-preserved':1,'ambiguous-reciprocal-osm-candidates':1})

    def test_nodata_and_missing_ground_or_relative_height_never_create_a_reference(self):
        for height,ground in [(None,7),(-9999,7),(12,None),(12,-9999),(True,7),(12,False)]:
            with self.subTest(height=height,ground=ground):
                report = self.match(features=[ign_feature(height=height,ground=ground)])
                self.assertFalse(report['matches'])
                self.assertEqual(report['rejected'][0]['reason'],'unusable-ign-height-reference')
        self.assertEqual(self.match(features=[ign_feature(ground=0)])['statistics']['accepted'],1)
        self.assertEqual(self.match(features=[ign_feature(ground=-2.47)])['statistics']['accepted'],1)

    def test_absolute_roof_z_is_not_substituted_for_a_relative_height(self):
        report = self.match(features=[ign_feature(height=None,Z_MAX_TOIT=38)])
        self.assertFalse(report['matches'])
        self.assertFalse(report['policy']['deriveHeightFromAbsoluteRoofZ'])

    def test_receipt_hash_date_units_crs_datum_and_license_are_required(self):
        valid = self.source([ign_feature()])
        for patch in [{'sha256':'0'*64},{'units':'ft'},{'crs':'EPSG:4326'},
                      {'verticalDatum':'ellipsoid'},{'date':'unknown'},{'license':''}]:
            with self.subTest(patch=patch):
                with self.assertRaises(HeightMatchError):
                    match_building_heights([record()],self.path,{**valid,**patch})

    def test_conflicting_geojson_crs_is_rejected(self):
        receipt = self.source([ign_feature()],crs={'type':'name','properties':{'name':'EPSG:4326'}})
        with self.assertRaises(HeightMatchError):
            match_building_heights([record()],self.path,receipt)

    def test_explicit_field_mapping_accepts_known_export_schema_without_guessing(self):
        ign = ign_feature();ign['properties']={'ID':'IGN-MAPPED','height_m':8,'ground_m':3}
        receipt = self.source([ign]);receipt['fields']={'ignId':'ID','height':'height_m','groundAltitude':'ground_m'}
        row = next(iter(match_building_heights([record()],self.path,receipt)['matches'].values()))
        self.assertEqual((row['height'],row['groundAltitude'],row['ignId']),(8,3,'IGN-MAPPED'))

    def test_courtyard_holes_are_part_of_the_matching_footprint(self):
        hole = ring(3,3,7,7)
        osm = [record([feature(holes=[hole])])]
        self.assertFalse(self.match(osm)['matches'])
        self.assertEqual(self.match(osm,features=[ign_feature(holes=[hole])])['statistics']['accepted'],1)

    def test_invalid_ign_geometry_blocks_a_nearby_apparently_unique_match(self):
        bowtie = [[EAST,NORTH],[EAST+10,NORTH+10],[EAST+10,NORTH],[EAST,NORTH+10],[EAST,NORTH]]
        report = self.match(features=[ign_feature('IGN-GOOD'),ign_feature('IGN-INVALID',outer=bowtie)])
        self.assertFalse(report['matches'])
        self.assertEqual(report['rejected'][0]['reason'],'unverifiable-ign-neighbour-geometry')
        self.assertEqual(report['statistics']['invalidIGNGeometry'],1)

    def test_an_incomplete_osm_neighbour_cannot_make_a_second_outline_look_unique(self):
        incomplete = feature('osm/way/1')
        incomplete['properties']['soma:mesh53'][0]['wallsL93'].pop()
        report = self.match([record([incomplete,feature('osm/way/2')])])
        self.assertFalse(report['matches'])
        self.assertIn('unverifiable-reciprocal-osm-neighbour',report['statistics']['rejectedByReason'])

    def test_candidate_comparison_and_source_size_budgets_are_enforced(self):
        features = [ign_feature('A'),ign_feature('B')]
        report = self.match(features=features,limits=replace(MatchLimits(),max_candidates_per_building=1))
        self.assertEqual(report['rejected'][0]['reason'],'candidate-budget-exceeded')
        for limits in [replace(MatchLimits(),max_comparisons=1),replace(MatchLimits(),max_ign_features=1)]:
            with self.subTest(limits=limits):
                with self.assertRaises(HeightMatchError):
                    self.match(features=features,limits=limits)
        with self.assertRaises(HeightMatchError):
            self.match(limits=replace(MatchLimits(),max_osm_buildings=0))
        with self.assertRaises(HeightMatchError):
            self.match(limits=replace(MatchLimits(),max_building_bytes=1))
        with self.assertRaises(HeightMatchError):
            self.match(limits=replace(MatchLimits(),max_spool_bytes=1))

    def test_duplicate_ign_ids_conflicting_osm_fragments_and_weakened_policy_are_refused(self):
        with self.assertRaises(HeightMatchError):
            self.match(features=[ign_feature('SAME'),ign_feature('SAME')])
        records = [record(),record([feature(tags={'height':'12'})],cell='other')]
        with self.assertRaises(HeightMatchError):
            self.match(records)
        with self.assertRaises(HeightMatchError):
            self.match(min_iou=.8)
        with self.assertRaises(HeightMatchError):
            self.match(min_margin=.1)

    def test_source_receipts_cannot_mix_osm_snapshots(self):
        other = record([feature('osm/way/2',outer=ring(20,0,30,10))],cell='other')
        other['sourceReceipt']['sha256']='f'*64
        with self.assertRaises(HeightMatchError):
            self.match([record(),other])

    def test_saved_evidence_rejects_tampering_and_recomputed_inconsistent_bindings(self):
        report = self.match()
        changed = copy.deepcopy(report);next(iter(changed['matches'].values()))['height']=9999
        with self.assertRaises(HeightMatchError):validate_matches(changed)
        changed['proofSHA256']=digest({key:value for key,value in changed.items()if key!='proofSHA256'})
        with self.assertRaises(HeightMatchError):validate_matches(changed)

    def test_cli_generates_only_a_fixture_derived_report_and_never_overwrites_it(self):
        receipt=self.source([ign_feature()])
        directory=Path(self.directory.name)
        records_path=directory/'fixture-records.json';records_path.write_text(canonical([record()]))
        receipt_path=directory/'fixture-receipt.json';receipt_path.write_text(canonical(receipt))
        output=directory/'fixture-matches.json'
        script=Path(__file__).resolve().parents[2]/'tools/metropole/building_heights.py'
        command=[sys.executable,str(script),'--records',str(records_path),'--ign',str(self.path),
                 '--receipt',str(receipt_path),'--output',str(output)]
        result=subprocess.run(command,cwd=directory,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        report=json.loads(output.read_text());validate_matches(report)
        self.assertEqual(report['statistics']['accepted'],1)
        self.assertFalse(report['newHeightAcquisition'])
        before=output.read_bytes()
        repeated=subprocess.run(command,cwd=directory,capture_output=True,text=True)
        self.assertNotEqual(repeated.returncode,0)
        self.assertIn('Output already exists',repeated.stderr)
        self.assertEqual(output.read_bytes(),before)
        changed=copy.deepcopy(report);next(iter(changed['matches'].values()))['geometrySHA256']='0'*64
        changed['proofSHA256']=digest({key:value for key,value in changed.items()if key!='proofSHA256'})
        with self.assertRaises(HeightMatchError):validate_matches(changed)


class ManifestAndMetadataTests(unittest.TestCase):
    def test_source_manifest_assets_require_checksums_and_safe_relative_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);raw=canonical(record()).encode();data=gzip.compress(raw,mtime=0)
            (base/'tile.json.gz').write_bytes(data)
            manifest={'schema':'soma-metropole/vector-tiles/1','crs':'EPSG:2154','units':'m','source':{'sha256':SOURCE},
                      'tiles':[{'cellId':'cell-1','vector':{'path':'tile.json.gz','encoding':'gzip-json',
                        'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'decodedBytes':len(raw)}}]}
            path=base/'manifest.json';path.write_text(canonical(manifest))
            self.assertEqual(list(records_from_manifest(path)),[record()])
            manifest['tiles'][0]['vector']['sha256']='0'*64;path.write_text(canonical(manifest))
            with self.assertRaises(HeightMatchError):list(records_from_manifest(path))
            manifest['tiles'][0]['vector']['path']='../escape.json.gz';path.write_text(canonical(manifest))
            with self.assertRaises(HeightMatchError):list(records_from_manifest(path))

    def test_untrusted_or_unbound_saved_metadata_is_rejected_without_gis(self):
        with self.assertRaises(HeightMatchError):validate_matches({'schema':'wrong'})
        with self.assertRaises(HeightMatchError):binding_key('osm/way/1','missing',SOURCE)
        with self.assertRaises(HeightMatchError):binding_key('unscoped',SOURCE,SOURCE)


if __name__ == '__main__':
    unittest.main()
