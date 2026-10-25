"""Atomic, source-bound metadata publication into unserved generated worlds."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

GAME=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(GAME))
from tools.metropole import attach_world_parts as W

SOURCE='a'*64
PACK='b'*64


def seal(value,key):
    value.pop(key,None);value[key]=W.digest(W.canonical(value));return value


class Fixture:
    def __init__(self,base):
        self.base=Path(base);self.root=self.base/'world';self.root.mkdir(parents=True)
        self.parts=self.base/'building-parts.json';self.manifest=self.root/'manifest.json'
        self.records=[];tiles=[];hashes={}
        for i in range(2):
            cell=f'V52-MC-3{i+3}';e,n=W.ORIGIN[0]+i*250,W.ORIGIN[1];bounds=[e-125,n-125,e+125,n+125]
            features=[]
            for number,part in ((1,False),(i+2,True)):
                p={'canonical_id':f'osm/way/{number}','soma:layer':'buildings',
                    'soma:geometry_sha256':str(number)*64,'height':'20','soma:mesh53':[{'ringsL93':[[
                    [e,n],[e+1,n],[e+1,n+1],[e,n]]]}]}
                p['building:part' if part else 'building']='yes'
                features.append({'type':'Feature','id':p['canonical_id'],'properties':p,
                    'geometry':{'type':'Polygon','coordinates':[[[5.37,43.3],[5.371,43.3],[5.371,43.301],[5.37,43.3]]]}})
            fc={'type':'FeatureCollection','features':features};content=W.digest(W.canonical(fc));hashes[cell]=content
            record={'schema':'soma-massilia/geodata-cell/4','cellId':cell,'boundsL93':bounds,'grid':{'x':i,'y':0},
                    'sourceReceipt':{'sha256':SOURCE},'contentSHA256':content,'featureCollection':fc}
            descriptor=W.checked.asset(self.root,f'tiles/{cell}.json.gz',record)
            descriptor['decodedBytes']=len(W.canonical(record));self.records.append(record)
            tiles.append({'cellId':cell,'gridX':i,'gridY':0,'boundsL93':bounds,'contentSHA256':content,
                          'vector':descriptor,'terrain':None,'surfaces':None,'navigation':None})
        self.world={'schema':W.SCHEMA,'crs':'EPSG:2154','units':'m','origin':W.ORIGIN.copy(),'cellSize':250,
            'source':{'sha256':SOURCE,'license':'fixture','attribution':'QA fixtures only'},'sourcePackSHA256':PACK,
            'sourceManifests':{'vectors':PACK,'surfaces':None},'coverageExplicitPartial':True,'completeMetropole':False,
            'target':{'id':'200054807','boundarySHA256':None},
            'preparationOnly':True,'activationPerformed':False,'tiles':tiles,
            'coverage':{'allLayersAvailableCells':0},'meaning':'Fixture, never geographic coverage.'}
        parts=[];links={}
        for number,cell in ((2,'V52-MC-33'),(3,'V52-MC-34')):
            p={'id':f'osm/way/{number}','geometrySHA256':str(number)*64,'cells':{cell:hashes[cell]},
               'association':'unique-source-containment','groundCoverage':True}
            parts.append(p);links[p['id']]={'parentId':'osm/way/1','parentGeometrySHA256':'1'*64,
                'geometrySHA256':p['geometrySHA256'],'sourceSHA256':SOURCE,'cells':p['cells'],
                'association':p['association']}
        parent={'parentId':'osm/way/1','parentGeometrySHA256':'1'*64,'sourceSHA256':SOURCE,
            'parentAreaM2':20,'coveredAreaM2':20,'residualAreaM2':0,'coverageRatio':1,'areaConservationErrorM2':0,
            'suppressParent':True,'verticalEnvelopeConsistent':True,'artificialCutWalls':False,'cells':hashes.copy(),
            'parts':parts,'partIds':[p['id'] for p in parts],'groundPartIds':[p['id'] for p in parts]}
        self.proof={'schema':W.building_parts.SCHEMA,'sourceSHA256':SOURCE,'certified':False,
            'fullSuppressionThreshold':.995,'parents':{'osm/way/1':parent},'partParents':links,
            'selectionProvenance':{'vectorManifestSHA256':PACK,'sourceCellHashes':hashes.copy()},
            'completeMetropole':False,'runtimeIntegrationPerformed':False}
        self.save()

    def save(self):
        self.manifest.write_bytes(W.canonical(seal(self.world,'manifestContentSHA256'))+b'\n')
        self.parts.write_text(json.dumps(seal(self.proof,'proofSHA256'),sort_keys=True,indent=2)+'\n')

    def target(self):return self.root/f'metadata/building-parts.{W.checked.file_hash(self.parts)[:12]}.json'


class WorldPartsAttachmentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='fixture-world-parts-');self.base=Path(self.temp.name)
        self.f=Fixture(self.base/'inputs')

    def tearDown(self):self.temp.cleanup()

    def assert_no_metadata(self,f=None):
        f=f or self.f
        self.assertEqual(list(f.root.glob('metadata/building-parts.*.json')),[])
        self.assertEqual(list(f.root.glob('.parts-manifest-*')),[])

    def test_exact_proof_bytes_attach_once_without_changing_any_vector_or_readiness(self):
        before={p:p.read_bytes() for p in self.f.root.rglob('*') if p.is_file()};raw=self.f.parts.read_bytes()
        result=W.attach(self.f.root,self.f.parts);descriptor=result['buildingParts'];target=self.f.root/descriptor['path']
        self.assertEqual(target.read_bytes(),raw)
        self.assertEqual(descriptor,{'path':self.f.target().relative_to(self.f.root).as_posix(),'encoding':'json',
            'bytes':len(raw),'sha256':W.digest(raw),'proofSHA256':self.f.proof['proofSHA256'],'sourcePbfSHA256':SOURCE})
        self.assertEqual(result['sourceManifests']['buildingParts'],W.digest(raw))
        self.assertEqual(result['tiles'],self.f.world['tiles']);self.assertFalse(result['activationPerformed'])
        self.assertEqual(result['coverage'],self.f.world['coverage']);self.assertNotIn('readyFor3D',result)
        W.validate_world(result)
        for path,data in before.items():
            if path!=self.f.manifest:self.assertEqual(path.read_bytes(),data)
        manifest_bytes=self.f.manifest.read_bytes();mtime=self.f.manifest.stat().st_mtime_ns;asset_mtime=target.stat().st_mtime_ns
        self.assertEqual(W.attach(self.f.root,self.f.parts),result)
        self.assertEqual(self.f.manifest.read_bytes(),manifest_bytes);self.assertEqual(self.f.manifest.stat().st_mtime_ns,mtime)
        self.assertEqual(target.stat().st_mtime_ns,asset_mtime)

    def test_seal_source_pack_pbf_and_inactive_preparation_are_required(self):
        edits=[lambda f:f.world.update(manifestContentSHA256='f'*64),lambda f:f.world['source'].update(sha256='f'*64),
               lambda f:f.world.update(sourcePackSHA256='f'*64),lambda f:f.proof['selectionProvenance'].update(vectorManifestSHA256='f'*64),
               lambda f:f.world.update(preparationOnly=False),lambda f:f.world.update(activationPerformed=True),
               lambda f:f.world.update(units='ft'),lambda f:f.world['tiles'][1].update(gridX=0)]
        for i,edit in enumerate(edits):
            with self.subTest(i=i):
                f=Fixture(self.base/f'bad-{i}');edit(f)
                if i!=0:f.save()
                else:f.manifest.write_bytes(W.canonical(f.world))
                original=f.manifest.read_bytes()
                with self.assertRaises(ValueError):W.attach(f.root,f.parts)
                self.assertEqual(f.manifest.read_bytes(),original);self.assert_no_metadata(f)

    def test_resealed_stale_missing_and_terrain_only_cell_bindings_are_refused(self):
        for i,cell in enumerate(('V52-MC-33','V52-MC-35')):
            f=Fixture(self.base/f'stale-{i}');parent=f.proof['parents']['osm/way/1'];parent['cells'][cell]='f'*64;f.save()
            with self.assertRaisesRegex(ValueError,'stale real source cell'):W.attach(f.root,f.parts)
            self.assert_no_metadata(f)
        f=Fixture(self.base/'terrain-only');tile=f.world['tiles'][0];tile.update(terrainOnly=True,vector=None,contentSHA256=None);f.save()
        with self.assertRaisesRegex(ValueError,'terrain-only'):W.attach(f.root,f.parts)
        self.assert_no_metadata(f)

    def test_all_part_parent_links_must_match_nested_geometry_cells_association_and_source(self):
        edits=[lambda p:p['partParents'].pop('osm/way/2'),
               lambda p:p['partParents']['osm/way/2'].update(parentId='osm/way/9'),
               lambda p:p['partParents']['osm/way/2'].update(geometrySHA256='f'*64),
               lambda p:p['partParents']['osm/way/2'].update(association='invented'),
               lambda p:p['partParents']['osm/way/2'].update(sourceSHA256='f'*64),
               lambda p:p['parents']['osm/way/1']['partIds'].append('osm/way/99'),
               lambda p:p['parents']['osm/way/1']['groundPartIds'].append('osm/way/99')]
        for i,edit in enumerate(edits):
            with self.subTest(i=i):
                f=Fixture(self.base/f'links-{i}');edit(f.proof);f.save()
                with self.assertRaises(ValueError):W.attach(f.root,f.parts)
                self.assert_no_metadata(f)

    def test_geometry_claims_are_checked_against_actual_world_vectors(self):
        self.f.proof['parents']['osm/way/1']['parentGeometrySHA256']='f'*64
        for link in self.f.proof['partParents'].values():link['parentGeometrySHA256']='f'*64
        self.f.save()
        with self.assertRaisesRegex(ValueError,'Actual source parent/part geometry'):W.attach(self.f.root,self.f.parts)
        self.assert_no_metadata()

    def test_partial_residuals_remain_unresolved_footprints_without_volume_or_collision(self):
        parent=self.f.proof['parents']['osm/way/1']
        parent.update(suppressParent=False,status='derived-partial',remainingUnresolved=True,
                      residualAreaM2=2,coveredAreaM2=18,coverageRatio=.9,
                      residualPolicy='unresolved-footprint-only',residualVolumetric=False,residualCollision=False)
        self.f.save();before=self.f.manifest.read_bytes()
        parent['residualVolumetric']=True;self.f.save()
        with self.assertRaisesRegex(ValueError,'non-volumetric'):W.attach(self.f.root,self.f.parts)
        self.assert_no_metadata()
        parent['residualVolumetric']=False;self.f.save()
        result=W.attach(self.f.root,self.f.parts)
        attached=json.loads((self.f.root/result['buildingParts']['path']).read_bytes())
        self.assertFalse(attached['parents']['osm/way/1']['residualVolumetric'])
        self.assertNotIn('readyFor3D',result)

    def test_corrupted_or_swapped_vector_bytes_are_refused_before_metadata_copy(self):
        path=self.f.root/self.f.world['tiles'][0]['vector']['path'];path.write_bytes(path.read_bytes()+b'x')
        with self.assertRaisesRegex(ValueError,'size differs'):W.attach(self.f.root,self.f.parts)
        self.assert_no_metadata()

    def test_world_vector_symlinks_cannot_drift_to_another_source_asset(self):
        path=self.f.root/self.f.world['tiles'][0]['vector']['path'];copy_path=path.with_name('copied.json.gz')
        copy_path.write_bytes(path.read_bytes());path.unlink();path.symlink_to(copy_path)
        with self.assertRaisesRegex(ValueError,'symlinks'):W.attach(self.f.root,self.f.parts)
        self.assert_no_metadata()

    def test_source_proof_checksum_and_strict_non_boolean_threshold_are_required(self):
        self.f.proof['fullSuppressionThreshold']=True;self.f.save()
        with self.assertRaisesRegex(ValueError,'strict suppression'):W.attach(self.f.root,self.f.parts)
        self.assert_no_metadata()
        self.f.proof['fullSuppressionThreshold']=.995;self.f.save()
        proof=json.loads(self.f.parts.read_bytes());proof['proofSHA256']='f'*64;self.f.parts.write_text(json.dumps(proof))
        with self.assertRaisesRegex(ValueError,'checksum'):W.attach(self.f.root,self.f.parts)

    def test_metadata_directory_target_and_manifest_symlinks_are_never_followed(self):
        outside=self.base/'outside';outside.mkdir();marker=outside/'keep';marker.write_text('keep')
        (self.f.root/'metadata').symlink_to(outside,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'symlinks'):W.attach(self.f.root,self.f.parts)
        self.assertEqual(list(outside.iterdir()),[marker]);(self.f.root/'metadata').unlink()
        (self.f.root/'metadata').mkdir();self.f.target().symlink_to(marker)
        with self.assertRaisesRegex(ValueError,'symlinks'):W.attach(self.f.root,self.f.parts)
        self.assertEqual(marker.read_text(),'keep');self.f.target().unlink()
        copied=outside/'manifest.json';copied.write_bytes(self.f.manifest.read_bytes());self.f.manifest.unlink();self.f.manifest.symlink_to(copied)
        with self.assertRaisesRegex(ValueError,'symlinks'):W.attach(self.f.root,self.f.parts)

    def test_existing_content_addressed_bytes_are_verified_and_never_overwritten(self):
        target=self.f.target();target.parent.mkdir();target.write_bytes(b'keep')
        with self.assertRaisesRegex(ValueError,'different bytes'):W.attach(self.f.root,self.f.parts)
        self.assertEqual(target.read_bytes(),b'keep')

    def test_source_asset_manifest_proof_or_tool_changes_abort_manifest_publication(self):
        for kind in ('vector','manifest','proof','tool'):
            with self.subTest(kind=kind):
                f=Fixture(self.base/f'changing-{kind}');original=f.manifest.read_bytes();real=W.os.link
                fake_tool=self.base/f'copied-{kind}.py';fake_tool.write_bytes(Path(W.__file__).read_bytes())
                paths={'vector':f.root/f.world['tiles'][0]['vector']['path'],'manifest':f.manifest,'proof':f.parts,'tool':fake_tool}
                def linking(*args,**kwargs):
                    result=real(*args,**kwargs);p=paths[kind];p.write_bytes(p.read_bytes()+b' ');return result
                with patch.object(W,'__file__',str(fake_tool)),patch.object(W.os,'link',side_effect=linking):
                    with self.assertRaisesRegex(ValueError,'changed during'):W.attach(f.root,f.parts)
                self.assertEqual(f.manifest.read_bytes(),original+(b' ' if kind=='manifest' else b''))
                self.assert_no_metadata(f)

    def test_replace_failure_leaves_the_previous_manifest_and_no_partial_attachment(self):
        before=self.f.manifest.read_bytes()
        with patch.object(W.os,'replace',side_effect=OSError('fixture failed atomic rename')):
            with self.assertRaises(OSError):W.attach(self.f.root,self.f.parts)
        self.assertEqual(self.f.manifest.read_bytes(),before);self.assert_no_metadata()

    def test_idempotent_attachment_still_verifies_the_immutable_asset(self):
        W.attach(self.f.root,self.f.parts);self.f.target().write_bytes(b'changed')
        before=self.f.manifest.read_bytes()
        with self.assertRaisesRegex(ValueError,'altered'):W.attach(self.f.root,self.f.parts)
        self.assertEqual(self.f.manifest.read_bytes(),before)

    def test_cli_is_standard_library_only(self):
        result=subprocess.run([sys.executable,'-S',str(Path(W.__file__)),'--world',str(self.f.root),'--parts',str(self.f.parts)],
            cwd=self.base,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(json.loads(result.stdout)['sourcePbfSHA256'],SOURCE)


if __name__=='__main__':unittest.main()
