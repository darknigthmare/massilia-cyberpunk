"""Checked surface attachment preserves already verified hardlinked base assets."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

GAME=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(GAME))
from tools.metropole import attach_world_surfaces as S
from game.tests.metropole.test_attach_world_parts import Fixture,seal,SOURCE,PACK

NATIVE='d'*64
DIMENSION='e'*64


class Inputs:
    def __init__(self,base):
        self.f=Fixture(base);self.root=self.f.root;self.source=self.f.base/'surface-input';self.source.mkdir()
        self.path=self.source/'surface-manifest.json';self.packs=[]
        self.f.world['nativeTopologySHA256']=NATIVE
        for i,tile in enumerate(self.f.world['tiles']):
            p=self.root/f'immutable-dem-{i}';p.write_bytes(b'Already verified DEM, deliberately never parsed by this tool.')
            tile['terrain']={'path':p.name,'bytes':p.stat().st_size,'sha256':S.checked.file_hash(p),'encoding':'gzip-json','complete':True}
        e,n=S.P.ORIGIN[0]+500,S.P.ORIGIN[1]
        p=self.root/'immutable-dem-only';p.write_bytes(b'Already verified NoData DEM.')
        self.f.world['tiles'].append({'cellId':'V52-MC-35','gridX':2,'gridY':0,'boundsL93':[e-125,n-125,e+125,n+125],
            'terrainOnly':True,'vector':None,'contentSHA256':None,'surfaces':None,'navigation':None,
            'terrain':{'path':p.name,'bytes':p.stat().st_size,'sha256':S.checked.file_hash(p),'encoding':'gzip-json','complete':False}})
        self.f.world['buildingParts']={'path':'metadata/existing-parts.json','encoding':'json','bytes':12,'sha256':'f'*64}
        (self.root/'metadata').mkdir();(self.root/'metadata/existing-parts.json').write_bytes(b'untouched parts')
        self.f.world['sourceManifests']['buildingParts']='f'*64
        for tile in self.f.world['tiles']:tile['preparation']=S.preparation(tile)
        self.f.world['coverage'].update(S.counters(self.f.world));self.f.save()
        self.manifest={'schema':'soma-metropole/surface-tiles/1','crs':'EPSG:2154','units':'m',
            'sourceVectorManifest':{'sha256':PACK},'sourcePbfSHA256':SOURCE,'nativeTopologySHA256':NATIVE,
            'dimensionCore':{'sha256':DIMENSION},'heightReferences':{'status':'source-bound-eaves-matches',
            'heightKind':'eaves','roofSurveyed':False,'catalogueSealSHA256':'1'*64,'heightSidecarManifestSHA256':'2'*64,
            'matchedFragments':2},'tiles':[]}
        for tile in self.f.world['tiles'][:2]:
            self.packs.append({'schema':'soma-metropole/surface-cell/1','cellId':tile['cellId'],'boundsL93':tile['boundsL93'],
                'contentSHA256':tile['contentSHA256'],'sourcePbfSHA256':SOURCE,'sourceVectorManifestSHA256':PACK,
                'nativeTopologySHA256':NATIVE,'dimensionCoreSHA256':DIMENSION,
                'cell':{'contentSHA256':tile['contentSHA256'],'sourceSHA256':SOURCE,
                    'surfaces':{'road':[[[0,0],[2,0],[0,2]]],'walk':[]},'areaM2':{'road':2,'walk':0}},
                'buildings':{'osm/way/1':{'heightKind':'eaves','height':12,'roofSurveyed':False}},'roadMetadata':{'widthSource':'OSM'}})
            self.manifest['tiles'].append({'cellId':tile['cellId'],'boundsL93':tile['boundsL93'],'cellHash':tile['contentSHA256']})
        self.save()

    def save(self):
        for i,pack in enumerate(self.packs):
            desc=S.checked.asset(self.source,f'{i}.json.gz',pack);desc['decodedBytes']=len(S.A.canonical(pack))
            self.manifest['tiles'][i]['surface']=desc
        self.path.write_bytes(S.A.canonical(self.manifest)+b'\n')


class AttachWorldSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='fixture-world-surfaces-');self.base=Path(self.temp.name)
        self.i=Inputs(self.base/'inputs')

    def tearDown(self):self.temp.cleanup()

    def assert_unpublished(self,inputs=None):
        i=inputs or self.i
        self.assertEqual(list(i.root.glob('layers/surfaces.*')),[])
        self.assertEqual(list(i.root.glob('.surface-attach-*')),[])
        self.assertEqual(list(i.root.glob('.surfaces-manifest-*')),[])

    def test_surface_assets_are_checked_and_attached_without_reading_or_modifying_immutable_layers(self):
        before={p:p.read_bytes() for p in self.i.root.rglob('*') if p.is_file()};calls=[];real=S.A.read_asset
        def reading(base,description):
            self.assertEqual(Path(base),self.i.source);calls.append(description['path']);return real(base,description)
        with patch.object(S.A,'read_asset',side_effect=reading),patch.object(S.P,'verify_real_cells',side_effect=AssertionError('No vector reread')):
            result=S.attach(self.i.root,self.i.path)
        self.assertEqual(len(calls),2);self.assertEqual(result['coverage']['surfaceCells'],2)
        self.assertEqual(result['coverage']['allLayersAvailableCells'],0)
        self.assertEqual(result['coverage']['terrainCompleteCells'],2);self.assertEqual(result['coverage']['terrainNoDataCells'],1)
        self.assertEqual(result['coverage']['terrainOnlyCells'],1)
        self.assertEqual(result['heightReferences'],self.i.manifest['heightReferences'])
        self.assertEqual(result['buildingParts'],self.i.f.world['buildingParts']);self.assertFalse(result['activationPerformed'])
        self.assertNotIn('readyFor3D',result)
        for tile,old in zip(result['tiles'],self.i.f.world['tiles']):
            for layer in ('vector','terrain','navigation'):self.assertEqual(tile[layer],old[layer])
            self.assertIn('navigation',tile['preparation']['missingLayers'])
            if old.get('terrainOnly'):
                self.assertIsNone(tile['surfaces']);self.assertFalse(tile['preparation']['allLayersAvailable'])
            else:
                copied=self.i.root/tile['surfaces']['path'];source=self.i.source/self.i.manifest['tiles'][tile['gridX']]['surface']['path']
                self.assertEqual(copied.read_bytes(),source.read_bytes())
                self.assertNotIn('surfaces',tile['preparation']['missingLayers'])
        for path,raw in before.items():
            if path!=self.i.f.manifest:self.assertEqual(path.read_bytes(),raw)
        S.P.validate_world(result)

    def test_hardlinked_clone_never_changes_the_base_manifest_or_any_shared_inode(self):
        clone=self.base/'clone';shutil.copytree(self.i.root,clone,copy_function=os.link)
        before={p:p.read_bytes() for p in self.i.root.rglob('*') if p.is_file()}
        vector=self.i.f.world['tiles'][0]['vector']['path'];inode=(self.i.root/vector).stat().st_ino
        S.attach(clone,self.i.path)
        for path,raw in before.items():self.assertEqual(path.read_bytes(),raw)
        self.assertEqual((clone/vector).stat().st_ino,inode)
        self.assertNotEqual((clone/'manifest.json').stat().st_ino,self.i.f.manifest.stat().st_ino)

    def test_source_frame_native_dimension_cell_and_triangle_contradictions_are_refused(self):
        edits=[lambda i:i.manifest.update(units='ft'),lambda i:i.manifest.update(nativeTopologySHA256='f'*64),
               lambda i:i.manifest['sourceVectorManifest'].update(sha256='f'*64),
               lambda i:i.packs[0].update(dimensionCoreSHA256='f'*64),
               lambda i:i.packs[0].update(contentSHA256='f'*64),lambda i:i.packs[0].update(sourcePbfSHA256='f'*64),
               lambda i:i.manifest['tiles'][0].update(cellHash='f'*64),
               lambda i:i.packs[0]['cell']['surfaces']['road'][0][0].__setitem__(0,126),
               lambda i:i.packs[0]['cell']['surfaces']['road'][0][0].__setitem__(0,True)]
        for n,edit in enumerate(edits):
            with self.subTest(n=n):
                i=Inputs(self.base/f'bad-{n}');old=i.f.manifest.read_bytes();edit(i);i.save()
                with self.assertRaises(ValueError):S.attach(i.root,i.path)
                self.assertEqual(i.f.manifest.read_bytes(),old);self.assert_unpublished(i)

    def test_index_must_cover_exactly_vector_cells_without_terrain_only_extras(self):
        self.i.manifest['tiles'][1]['cellId']='V52-MC-35';self.i.save()
        with self.assertRaisesRegex(ValueError,'index/source'):S.attach(self.i.root,self.i.path)
        self.assert_unpublished()

    def test_source_bytes_hash_decoding_budget_and_symlinks_are_checked(self):
        desc=self.i.manifest['tiles'][0]['surface'];path=self.i.source/desc['path'];raw=path.read_bytes()
        path.write_bytes(raw+b'x')
        with self.assertRaises(ValueError):S.attach(self.i.root,self.i.path)
        path.write_bytes(raw);copy_path=self.i.source/'copy.gz';copy_path.write_bytes(raw);path.unlink();path.symlink_to(copy_path)
        with self.assertRaisesRegex(ValueError,'symlinks'):S.attach(self.i.root,self.i.path)
        self.assert_unpublished()

    def test_bad_source_descriptors_and_height_provenance_are_refused(self):
        for n,edit in enumerate([lambda m:m['tiles'][0]['surface'].update(bytes=True),
            lambda m:m['tiles'][0]['surface'].update(sha256='bad'),
            lambda m:m['tiles'][0]['surface'].update(decodedBytes=S.A.MAX_DECODED+1),
            lambda m:m['heightReferences'].update(roofSurveyed=True),lambda m:m['heightReferences'].update(heightKind='absolute-roof-z')]):
            i=Inputs(self.base/f'desc-{n}');edit(i.manifest);i.path.write_bytes(S.A.canonical(i.manifest))
            with self.assertRaises(ValueError):S.attach(i.root,i.path)
            self.assert_unpublished(i)

    def test_same_source_is_idempotent_without_decompression_and_different_source_is_refused(self):
        result=S.attach(self.i.root,self.i.path);raw=self.i.f.manifest.read_bytes();mtime=self.i.f.manifest.stat().st_mtime_ns
        with patch.object(S.A,'read_asset',side_effect=AssertionError('No repeated decompression')):
            self.assertEqual(S.attach(self.i.root,self.i.path),result)
        self.assertEqual(self.i.f.manifest.read_bytes(),raw);self.assertEqual(self.i.f.manifest.stat().st_mtime_ns,mtime)
        self.i.manifest['edition']='different';self.i.save()
        with self.assertRaisesRegex(ValueError,'different surface edition'):S.attach(self.i.root,self.i.path)
        self.assertEqual(self.i.f.manifest.read_bytes(),raw)

    def test_altered_attached_surface_is_refused_on_idempotent_call(self):
        result=S.attach(self.i.root,self.i.path);p=self.i.root/result['tiles'][0]['surfaces']['path'];p.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'altered'):S.attach(self.i.root,self.i.path)

    def test_world_source_asset_manifest_or_tool_change_rolls_back_without_replacing_manifest(self):
        for kind in ('world','source','asset','tool'):
            with self.subTest(kind=kind):
                i=Inputs(self.base/f'changing-{kind}');old=i.f.manifest.read_bytes();real=S.A.copy_asset
                fake_tool=i.f.base/'copied-tool.py';fake_tool.write_bytes(Path(S.__file__).read_bytes())
                changed=False
                def copying(*args,**kwargs):
                    nonlocal changed
                    result=real(*args,**kwargs)
                    if not changed:
                        changed=True;path={'world':i.f.manifest,'source':i.path,'asset':i.source/i.manifest['tiles'][0]['surface']['path'],'tool':fake_tool}[kind]
                        path.write_bytes(path.read_bytes()+b' ')
                    return result
                with patch.object(S,'__file__',str(fake_tool)),patch.object(S.A,'copy_asset',side_effect=copying):
                    with self.assertRaisesRegex(ValueError,'changed during'):S.attach(i.root,i.path)
                self.assertEqual(i.f.manifest.read_bytes(),old+(b' ' if kind=='world' else b''));self.assert_unpublished(i)

    def test_atomic_manifest_replace_failure_removes_only_its_new_surface_directory(self):
        old=self.i.f.manifest.read_bytes();vectors={p:p.read_bytes() for p in self.i.root.rglob('*') if p.is_file()}
        with patch.object(S.os,'replace',side_effect=OSError('fixture atomic replacement failure')):
            with self.assertRaises(OSError):S.attach(self.i.root,self.i.path)
        self.assertEqual(self.i.f.manifest.read_bytes(),old);self.assert_unpublished()
        for path,raw in vectors.items():self.assertEqual(path.read_bytes(),raw)

    def test_layers_target_symlink_and_preexisting_directory_are_preserved(self):
        outside=self.base/'outside';outside.mkdir();marker=outside/'keep';marker.write_text('keep')
        (self.i.root/'layers').symlink_to(outside,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'symlinks'):S.attach(self.i.root,self.i.path)
        self.assertEqual(list(outside.iterdir()),[marker]);(self.i.root/'layers').unlink()
        target=self.i.root/f'layers/surfaces.{S.checked.file_hash(self.i.path)[:12]}';target.mkdir(parents=True)
        with self.assertRaisesRegex(ValueError,'already exists'):S.attach(self.i.root,self.i.path)
        self.assertTrue(target.is_dir())

    def test_cli_runs_with_standard_library_only(self):
        result=subprocess.run([sys.executable,'-S',str(Path(S.__file__)),'--world',str(self.i.root),'--surfaces',str(self.i.path)],
            cwd=self.base,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(json.loads(result.stdout)['surfaceCells'],2)


if __name__=='__main__':unittest.main()
