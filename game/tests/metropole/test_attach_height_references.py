"""Source-bound height attachment fixtures; no measured geography is invented."""
import copy
import gzip
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

GAME=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(GAME))
from tools.metropole import attach_height_references as attach

SOURCE='a'*64
CATALOGUE='b'*64
MATCHING='c'*64


def sealed(value,key):
    value[key]=attach.digest(attach.canonical({k:v for k,v in value.items() if k!=key}))
    return value


class Inputs:
    def __init__(self,root,count=2):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.paths={name:self.root/name/'manifest.json' for name in ('vectors','surfaces','heights')}
        for path in self.paths.values():path.parent.mkdir()
        self.records=[];self.surfaces=[];self.heights=[]
        self.v={'schema':'soma-metropole/vector-tiles/1','crs':'EPSG:2154','units':'m',
                'origin':attach.ORIGIN.copy(),'cellSize':250,'source':{'sha256':SOURCE},'tiles':[]}
        self.s={'schema':'soma-metropole/surface-tiles/1','crs':'EPSG:2154','units':'m',
                'sourcePbfSHA256':SOURCE,'sourceVectorManifest':{},'tiles':[],'report':{'newElevations':0}}
        self.h={'schema':'soma-metropole/building-height-sidecars/1','sourceSHA256':SOURCE,
                'catalogueSealSHA256':CATALOGUE,'sourceMatchingManifestSHA256':MATCHING,'tiles':[]}
        for i in range(count):
            identity=f'V52-MC-3{i+3}';e,n=attach.ORIGIN[0]+250*i,attach.ORIGIN[1]
            bounds=[e-125,n-125,e+125,n+125];canonical_id=f'osm/way/{i+1}'
            metric={'type':'Polygon','coordinates':[[[e,n],[e+10,n],[e+10,n+10],[e,n+10],[e,n]]]}
            geometry_sha=attach.digest(attach.canonical(metric))
            feature={'type':'Feature','id':canonical_id,'geometry':{'type':'Polygon','coordinates':[[
                [5.37,43.3],[5.3701,43.3],[5.3701,43.3001],[5.37,43.3001],[5.37,43.3]]]},
                'properties':{'canonical_id':canonical_id,'soma:layer':'buildings','building':'yes',
                    'soma:geometry_sha256':geometry_sha,'soma:metricGeometry':metric}}
            fc={'type':'FeatureCollection','features':[feature]};content=attach.digest(attach.canonical(fc))
            record={'schema':'soma-massilia/geodata-cell/4','cellId':identity,'boundsL93':bounds,
                    'grid':{'x':i,'y':0},'sourceReceipt':{'sha256':SOURCE},'contentSHA256':content,'featureCollection':fc}
            surface={'schema':'soma-metropole/surface-cell/1','cellId':identity,'boundsL93':bounds,
                    'sourcePbfSHA256':SOURCE,'contentSHA256':content,'cell':{'sourceSHA256':SOURCE,
                    'contentSHA256':content,'surfaces':{'road':[[[0,0],[1,0],[1,1]]],'walk':[]},'areaM2':{'road':.5,'walk':0}},
                    'buildings':{},'roadMetadata':{'osm/way/90':{'width':7.4,'widthSource':'osm-width'}},
                    'heightReferences':{'status':'explicitly-absent','count':0},'policy':{'markings':'no automatic stripes'}}
            row={'canonicalId':canonical_id,'geometrySHA256':geometry_sha,'sourceSHA256':SOURCE,
                'heightKind':'eaves','height':12.5,'groundAltitude':0,'iou':.95,'margin':.2,'reciprocalMargin':.3,
                'method':'footprint-iou-unique-reciprocal','decision':'accepted-conservative-match',
                'heightSource':'ign-bdtopo-height','ignId':f'IGN-QA-{i}'}
            height={'schema':'soma-metropole/building-height-cell/1','cellId':identity,'contentSHA256':content,
                    'sourceSHA256':SOURCE,'catalogueSealSHA256':CATALOGUE,'sourceMatchingManifestSHA256':MATCHING,
                    'heightKind':'eaves','matches':{attach.binding_key(canonical_id,geometry_sha,SOURCE):row}}
            self.records.append(record);self.surfaces.append(surface);self.heights.append(height)
            self.v['tiles'].append({'cellId':identity,'gridX':i,'gridY':0,'boundsL93':bounds})
            self.s['tiles'].append({'cellId':identity,'boundsL93':bounds,'cellHash':content})
            self.h['tiles'].append({'cellId':identity,'contentSHA256':content})
        self.save()

    def write_asset(self,kind,i,value):
        descriptor=attach.asset(self.paths[kind].parent,f'cell-{i}.json.gz',value)
        descriptor['decodedBytes']=len(attach.canonical(value))
        return descriptor

    def save(self):
        for i,record in enumerate(self.records):self.v['tiles'][i]['vector']=self.write_asset('vectors',i,record)
        self.paths['vectors'].write_bytes(attach.canonical(self.v)+b'\n')
        self.vsha=attach.file_hash(self.paths['vectors'])
        self.s['sourceVectorManifest']['sha256']=self.vsha;self.h['currentVectorManifestSHA256']=self.vsha
        for i,(surface,height) in enumerate(zip(self.surfaces,self.heights)):
            surface['sourceVectorManifestSHA256']=self.vsha
            height['currentVectorManifestSHA256']=self.vsha;height['vectorSHA256']=self.v['tiles'][i]['vector']['sha256']
            self.s['tiles'][i]['surface']=self.write_asset('surfaces',i,surface)
            descriptor=self.write_asset('heights',i,sealed(height,'proofSHA256'));descriptor.pop('encoding')
            self.h['tiles'][i].update(descriptor,matchedFragments=len(height['matches']))
        self.paths['surfaces'].write_bytes(attach.canonical(self.s)+b'\n')
        self.paths['heights'].write_bytes(attach.canonical(sealed(self.h,'manifestSHA256'))+b'\n')

    def prepare(self,name='out'):
        return attach.prepare(*(self.paths[k] for k in ('vectors','surfaces','heights')),self.root/name)

    def merge(self,record=None,surface=None,height=None):
        return attach.merge_cell(record or self.records[0],surface or self.surfaces[0],height or self.heights[0],
            vector_sha=self.v['tiles'][0]['vector']['sha256'],catalogue_sha=CATALOGUE,vector_manifest_sha=self.vsha)


class AttachHeightReferencesTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='fixture-height-attachment-')
        self.root=Path(self.temp.name);self.f=Inputs(self.root/'inputs')

    def tearDown(self):self.temp.cleanup()

    def assert_unpublished(self,f=None):
        f=f or self.f
        self.assertFalse((f.root/'out').exists())
        self.assertEqual(list(f.root.glob('.eave-surfaces-*')),[])

    def test_source_bound_eaves_attach_deterministically_without_changing_any_road_or_source_byte(self):
        original={p:p.read_bytes() for directory in self.f.paths.values() for p in directory.parent.iterdir()}
        result=self.f.prepare();second=self.f.prepare('second')
        self.assertEqual(result,second)
        self.assertEqual(result['heightReferences']['matchedFragments'],2)
        self.assertEqual(result['heightAttachment']['toolSHA256'],attach.file_hash(Path(attach.__file__)))
        for i,tile in enumerate(result['tiles']):
            merged=attach.read_asset(self.f.root/'out',tile['surface'],attach.MAX_SURFACE)
            before=self.f.surfaces[i]
            for key in before.keys()-{'buildings','heightReferences'}:self.assertEqual(merged[key],before[key])
            ref=merged['buildings'][f'osm/way/{i+1}']
            self.assertEqual((ref['height'],ref['groundAltitude']),(12.5,0))
            self.assertFalse(ref['roofSurveyed']);self.assertEqual(ref['heightKind'],'eaves')
            self.assertEqual(ref['cellContentSHA256'],self.f.records[i]['contentSHA256'])
            self.assertEqual(ref['sourceSHA256'],SOURCE)
            self.assertEqual(tile['surface']['sha256'],second['tiles'][i]['surface']['sha256'])
        for path,raw in original.items():self.assertEqual(path.read_bytes(),raw)

    def test_empty_height_sidecars_preserve_valid_surfaces_without_inventing_building_references(self):
        for height in self.f.heights:height['matches']={}
        self.f.save();result=self.f.prepare()
        self.assertEqual(result['heightReferences']['matchedFragments'],0)
        for tile in result['tiles']:
            merged=attach.read_asset(self.f.root/'out',tile['surface'],attach.MAX_SURFACE)
            self.assertEqual(merged['buildings'],{})

    def test_cell_source_content_and_proof_contradictions_are_refused(self):
        for kind,field,value in [
            ('surface','cellId','V52-MC-35'),('surface','sourcePbfSHA256','d'*64),
            ('surface','sourceVectorManifestSHA256','d'*64),('surface','contentSHA256','d'*64),
            ('height','cellId','V52-MC-35'),('height','sourceSHA256','d'*64),
            ('height','vectorSHA256','d'*64),('height','catalogueSealSHA256','d'*64),
            ('height','currentVectorManifestSHA256','d'*64),('height','contentSHA256','d'*64),
            ('height','heightKind','absolute-roof-z'),('height','proofSHA256','d'*64),
        ]:
            with self.subTest(kind=kind,field=field):
                surface=copy.deepcopy(self.f.surfaces[0]);height=copy.deepcopy(self.f.heights[0])
                (surface if kind=='surface' else height)[field]=value
                if kind=='height' and field!='proofSHA256':sealed(height,'proofSHA256')
                with self.assertRaises(ValueError):self.f.merge(surface=surface,height=height)

    def test_geometry_identity_and_minimum_evidence_remain_required_even_after_resealing(self):
        for field,value in [('geometrySHA256','d'*64),('canonicalId','osm/way/999'),('sourceSHA256','d'*64),
                            ('method','centroid-distance'),('decision','assumed'),('heightSource','unknown'),
                            ('ignId',' '),('iou',.899),('margin',.149),('reciprocalMargin',.149)]:
            with self.subTest(field=field):
                height=copy.deepcopy(self.f.heights[0]);next(iter(height['matches'].values()))[field]=value
                sealed(height,'proofSHA256')
                with self.assertRaises(ValueError):self.f.merge(height=height)
        record=copy.deepcopy(self.f.records[0]);record['featureCollection']['features'][0]['properties']['building']='changed'
        with self.assertRaisesRegex(ValueError,'content hash'):self.f.merge(record=record)

    def test_explicit_osm_height_parts_and_non_ground_buildings_always_keep_priority(self):
        for tags in [{'height':x} for x in ('12','unreadable','0')]+[
            {'building:part':'yes'},{'building':'roof'},{'min_height':'1'},{'building:min_level':'1'},
            {'layer':'1'},{'location':'underground'}]:
            with self.subTest(tags=tags):
                record=copy.deepcopy(self.f.records[0]);surface=copy.deepcopy(self.f.surfaces[0]);height=copy.deepcopy(self.f.heights[0])
                record['featureCollection']['features'][0]['properties'].update(tags)
                content=attach.digest(attach.canonical(record['featureCollection']));record['contentSHA256']=content
                surface['contentSHA256']=surface['cell']['contentSHA256']=height['contentSHA256']=content
                sealed(height,'proofSHA256')
                with self.assertRaisesRegex(ValueError,'OSM priority'):self.f.merge(record,surface,height)

    def test_nodata_invalid_numbers_and_absolute_altitudes_never_become_relative_heights(self):
        for field,value in [('height',None),('height',True),('height',-9999),('height',9999),('height',0),('height',.05),
                            ('groundAltitude',None),('groundAltitude',False),('groundAltitude',-9999),('groundAltitude',9999)]:
            with self.subTest(field=field,value=value):
                height=copy.deepcopy(self.f.heights[0]);next(iter(height['matches'].values()))[field]=value
                sealed(height,'proofSHA256')
                with self.assertRaises(ValueError):self.f.merge(height=height)
        for ground in (0,-2.47,9000):
            height=copy.deepcopy(self.f.heights[0]);row=next(iter(height['matches'].values()))
            row.update(groundAltitude=ground,height=.05000000001);sealed(height,'proofSHA256')
            merged,count=self.f.merge(height=height)
            self.assertEqual(count,1);self.assertEqual(merged['buildings']['osm/way/1']['groundAltitude'],ground)

    def test_duplicate_buildings_and_conflicting_existing_references_are_refused(self):
        record=copy.deepcopy(self.f.records[0]);record['featureCollection']['features']*=2
        record['contentSHA256']=attach.digest(attach.canonical(record['featureCollection']))
        surface=copy.deepcopy(self.f.surfaces[0]);height=copy.deepcopy(self.f.heights[0])
        surface['contentSHA256']=surface['cell']['contentSHA256']=height['contentSHA256']=record['contentSHA256'];sealed(height,'proofSHA256')
        with self.assertRaisesRegex(ValueError,'Duplicate building'):self.f.merge(record,surface,height)
        surface=copy.deepcopy(self.f.surfaces[0]);surface['buildings']['osm/way/1']={'height':99}
        with self.assertRaisesRegex(ValueError,'overwrite'):self.f.merge(surface=surface)

    def test_raw_manifest_sha_is_required_even_when_json_content_is_semantically_identical(self):
        path=self.f.paths['vectors'];path.write_text(json.dumps(self.f.v,indent=2))
        with self.assertRaisesRegex(ValueError,'inconsistent'):self.f.prepare()
        self.assert_unpublished()

    def test_manifests_require_matching_real_cell_sets_frames_and_indices(self):
        edits=[lambda f:f.s.update(crs='EPSG:4326'),lambda f:f.v.update(cellSize=True),
               lambda f:f.v['origin'].__setitem__(0,0),lambda f:f.v['tiles'][0].update(gridX=True),
               lambda f:f.v['tiles'][0]['boundsL93'].__setitem__(0,0),
               lambda f:f.s['tiles'][1].update(cellId=f.s['tiles'][0]['cellId']),
               lambda f:f.h['tiles'][1].update(cellId='V52-MC-35'),
               lambda f:f.s['tiles'][0].update(cellHash='d'*64),
               lambda f:f.h['tiles'][0].update(contentSHA256='d'*64)]
        for i,edit in enumerate(edits):
            with self.subTest(i=i):
                f=Inputs(self.root/f'bad-{i}');edit(f);f.save()
                with self.assertRaises(ValueError):f.prepare()
                self.assert_unpublished(f)

    def test_a_coherently_resealed_wrong_record_cell_cannot_hide_behind_a_valid_index(self):
        for value in (self.f.records[0],self.f.surfaces[0],self.f.heights[0]):value['cellId']='V52-MC-35'
        self.f.save()
        with self.assertRaisesRegex(ValueError,'indices disagree'):self.f.prepare()
        self.assert_unpublished()

    def test_source_asset_descriptors_enforce_hashes_encoding_paths_and_numeric_byte_types(self):
        descriptor=self.f.v['tiles'][0]['vector']
        for edit in [lambda d:d.update(bytes=True),lambda d:d.update(sha256='bad'),lambda d:d.update(encoding='json'),
                     lambda d:d.pop('encoding'),lambda d:d.update(path='../vectors/cell-0.json.gz'),
                     lambda d:d.update(path='/absolute.json.gz'),lambda d:d.update(decodedBytes=True)]:
            bad=copy.deepcopy(descriptor);edit(bad)
            with self.assertRaises(ValueError):attach.read_asset(self.f.paths['vectors'].parent,bad,attach.MAX_VECTOR)
        outside=self.root/'outside.json.gz';outside.write_bytes((self.f.paths['vectors'].parent/descriptor['path']).read_bytes())
        link=self.f.paths['vectors'].parent/'link.json.gz';link.symlink_to(outside)
        with self.assertRaisesRegex(ValueError,'escapes'):attach.read_asset(link.parent,{**descriptor,'path':link.name},attach.MAX_VECTOR)

    def test_a_failure_after_the_first_cell_keeps_output_unpublished_and_cleans_staging(self):
        next(iter(self.f.heights[1]['matches'].values()))['margin']=.1;self.f.save()
        with self.assertRaises(ValueError):self.f.prepare()
        self.assert_unpublished()

    def test_changes_to_an_already_read_asset_or_manifest_abort_atomic_publication(self):
        for kind in ('asset','manifest'):
            with self.subTest(kind=kind):
                f=Inputs(self.root/f'changing-{kind}');real=attach.asset;changed=False
                def writing(*args,**kwargs):
                    nonlocal changed
                    result=real(*args,**kwargs)
                    if not changed:
                        changed=True
                        path=(f.paths['vectors'].parent/f.v['tiles'][0]['vector']['path']) if kind=='asset' else f.paths['vectors']
                        path.write_bytes(path.read_bytes()+b' ')
                    return result
                with patch.object(attach,'asset',side_effect=writing):
                    with self.assertRaisesRegex(ValueError,'changed during'):f.prepare()
                self.assert_unpublished(f)

    def test_tool_hash_is_pinned_before_work_and_source_changes_abort_publication(self):
        tool=self.root/'copied-tool.py';tool.write_bytes(Path(attach.__file__).read_bytes());real=attach.asset
        def writing(*args,**kwargs):
            result=real(*args,**kwargs);tool.write_bytes(tool.read_bytes()+b'\n');return result
        with patch.object(attach,'__file__',str(tool)),patch.object(attach,'asset',side_effect=writing):
            with self.assertRaisesRegex(ValueError,'changed during'):self.f.prepare()
        self.assert_unpublished()

    def test_existing_or_concurrently_appearing_outputs_are_preserved(self):
        output=self.f.root/'out';output.mkdir();marker=output/'existing';marker.write_text('preserve')
        with self.assertRaisesRegex(ValueError,'Output exists'):self.f.prepare()
        self.assertEqual(marker.read_text(),'preserve');marker.unlink();output.rmdir()
        real=attach.asset
        def writing(*args,**kwargs):
            result=real(*args,**kwargs);output.mkdir(exist_ok=True);return result
        with patch.object(attach,'asset',side_effect=writing):
            with self.assertRaisesRegex(ValueError,'Output appeared'):self.f.prepare()
        self.assertTrue(output.is_dir());self.assertEqual(list(output.iterdir()),[])

    def test_cli_runs_with_python_S_and_standard_library_only(self):
        script=Path(attach.__file__);command=[sys.executable,'-S',str(script)]
        for key in ('vectors','surfaces','heights'):command.extend(['--'+key,str(self.f.paths[key])])
        command.extend(['--output',str(self.f.root/'cli')])
        result=subprocess.run(command,cwd=self.root,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['matchedFragments'],2)


if __name__=='__main__':unittest.main()
