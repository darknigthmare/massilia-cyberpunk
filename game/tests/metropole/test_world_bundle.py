"""Portable archive integrity, malicious metadata and atomic interruption cases."""
import copy
from dataclasses import replace
import gzip
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT=Path(__file__).resolve().parents[2]/'tools/metropole/world_bundle.py'
SPEC=importlib.util.spec_from_file_location('standalone_world_bundle',SCRIPT)
B=importlib.util.module_from_spec(SPEC);sys.modules[SPEC.name]=B;SPEC.loader.exec_module(B)


class Fixture:
    def __init__(self,root):
        self.root=Path(root);self.root.mkdir();self.blobs={}
        self.world={'schema':B.WORLD,'crs':'EPSG:2154','units':'m','origin':B.ORIGIN.copy(),'cellSize':250,
            'source':{'sha256':'a'*64,'license':'fixture-only','attribution':'QA fixtures; not real geographic coverage'},
            'sourcePackSHA256':'b'*64,'target':{'id':'200054807','boundarySHA256':None},
            'coverageExplicitPartial':True,'completeMetropole':False,'preparationOnly':True,'activationPerformed':False,'tiles':[]}
        for i,name in enumerate(('z','a')):
            cell=f'V52-MC-3{i+3}';e,n=B.ORIGIN[0]+250*i,B.ORIGIN[1]
            data=gzip.compress(B.canonical({'schema':'qa/source-cell','cellId':cell}),mtime=0)
            self.world['tiles'].append({'cellId':cell,'gridX':i,'gridY':0,'boundsL93':[e-125,n-125,e+125,n+125],
                'contentSHA256':str(i+1)*64,'vector':self.asset(f'tiles/{name}.json.gz',data,'gzip-json'),
                'terrain':None,'surfaces':None,'navigation':None})
        proof=b'{"scope":"fixture metadata; no genuine geography"}\n'
        self.world['buildingParts']={**self.asset('metadata/parts.json',proof,'json'),'sourcePbfSHA256':'a'*64,'proofSHA256':'c'*64}
        self.save()

    def asset(self,path,raw,encoding):
        p=self.root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw);self.blobs[B.digest(raw)]=raw
        return {'path':path,'bytes':len(raw),'sha256':B.digest(raw),'encoding':encoding}

    def save(self):
        self.world.pop('manifestContentSHA256',None);self.world['manifestContentSHA256']=B.seal(self.world)
        (self.root/'manifest.json').write_bytes(B.canonical(self.world)+b'\n')

    def forged(self,path,edit=None,header_edit=None):
        world=copy.deepcopy(self.world)
        if edit:edit(world)
        world.pop('manifestContentSHA256',None);world['manifestContentSHA256']=B.seal(world)
        raw=B.canonical(world)+b'\n';descriptions={}
        stack=[world]
        while stack:
            item=stack.pop()
            if isinstance(item,dict):
                if {'path','bytes','sha256','encoding'}<=item.keys():descriptions[item['path']]=item
                stack.extend(item.values())
            elif isinstance(item,list):stack.extend(item)
        payload=b''.join(self.blobs[d['sha256']] for p,d in sorted(descriptions.items()))
        head={'schema':B.SCHEMA,'worldManifestBytes':len(raw),'worldManifestSHA256':B.digest(raw),
            'manifestContentSHA256':world['manifestContentSHA256'],'sourcePbfSHA256':world['source']['sha256'],
            'sourcePackSHA256':world['sourcePackSHA256'],'assetCount':len(descriptions),'assetBytes':len(payload),
            'payloadBytes':len(raw)+len(payload),'toolSHA256':B.digest(SCRIPT.read_bytes())}
        if header_edit:header_edit(head)
        encoded=B.canonical(head);body=B.MAGIC+struct.pack('>I',len(encoded))+encoded+raw+payload
        path.write_bytes(body+B.FOOTER+bytes.fromhex(B.digest(body)))
        return path


class WorldBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='fixture-world-bundle-');self.base=Path(self.temp.name)
        self.f=Fixture(self.base/'world');self.archive=self.base/'cache.mwb';self.destination=self.base/'restored'

    def tearDown(self):self.temp.cleanup()

    def assert_clean(self):
        self.assertFalse(self.destination.exists());self.assertEqual(list(self.base.glob('.restored.bundle-import-*')),[])

    def test_deterministic_export_verify_import_and_exact_raw_world_bytes(self):
        before={p:p.read_bytes() for p in self.f.root.rglob('*') if p.is_file()}
        estimate=B.plan(self.f.root);receipt=B.export_bundle(self.f.root,self.archive)
        other=self.base/'other.mwb';self.assertEqual(B.export_bundle(self.f.root,other),receipt)
        self.assertEqual(self.archive.read_bytes(),other.read_bytes())
        self.assertEqual(estimate['archiveBytes'],self.archive.stat().st_size)
        self.assertEqual(receipt['archiveSHA256'],B.digest(self.archive.read_bytes()))
        self.assertEqual(B.verify_bundle(self.archive)['status'],'verified')
        installed=B.import_bundle(self.archive,self.destination);self.assertEqual(installed['status'],'installed')
        for p,data in before.items():
            self.assertEqual(p.read_bytes(),data);self.assertEqual((self.destination/p.relative_to(self.f.root)).read_bytes(),data)
        self.assertEqual(B.verify_world(self.destination)['assetCount'],3)
        self.assertEqual(list(self.destination.rglob('*.mwb')),[])

    def test_original_hardlinked_source_cache_is_never_mutated(self):
        clone=self.base/'clone';shutil.copytree(self.f.root,clone,copy_function=os.link)
        B.export_bundle(clone,self.archive);B.import_bundle(self.archive,self.destination)
        for source in self.f.root.rglob('*'):
            if source.is_file():
                restored=self.destination/source.relative_to(self.f.root)
                self.assertEqual(source.read_bytes(),restored.read_bytes());self.assertNotEqual(source.stat().st_ino,restored.stat().st_ino)

    def test_external_archive_manifest_and_receipt_pins_are_strict(self):
        receipt=B.export_bundle(self.f.root,self.archive)
        with self.assertRaises(B.BundleError):B.import_bundle(self.archive,self.destination,expected_sha256='0'*64)
        self.assert_clean()
        with self.assertRaises(B.BundleError):B.verify_bundle(self.archive,expected_manifest_sha256='0'*64)
        path=Path(str(self.archive)+'.receipt.json')
        for value in (True,float(receipt['assetCount'])):
            bad={**receipt,'assetCount':value};path.write_bytes(B.canonical(bad))
            with self.assertRaisesRegex(B.BundleError,'receipt'):B.verify_bundle(self.archive)
        self.assert_clean()

    def test_resealed_paths_cannot_traverse_escape_collide_or_create_windows_devices(self):
        for i,value in enumerate(('../outside','/absolute','tiles/../a','tiles\\a','tiles//a','tiles/%2e%2e/a',
                'manifest.json','Manifest.Json','CON','tiles/nul.json','tiles/COM1.gz','tiles/LPT9','tiles/a.',
                'tiles/'+'a'*256+'.json')):
            with self.subTest(path=value):
                bad=self.f.forged(self.base/f'path-{i}.mwb',lambda w:w['tiles'][0]['vector'].update(path=value))
                with self.assertRaises(B.BundleError):B.import_bundle(bad,self.destination)
                self.assert_clean();self.assertFalse((self.base/'outside').exists())
        for i,edit in enumerate((lambda w:w['tiles'][1]['vector'].update(path='tiles/Z.json.gz'),
                                lambda w:w['tiles'][1]['vector'].update(path='tiles/z.json.gz/child'))):
            bad=self.f.forged(self.base/f'collision-{i}.mwb',edit)
            with self.assertRaisesRegex(B.BundleError,'conflict|collid'):B.verify_bundle(bad)

    def test_non_ascii_ids_duplicate_cells_and_conflicting_shared_assets_are_refused(self):
        for i,edit in enumerate((lambda w:w['tiles'][0].update(cellId='V52-MC-E٠٠-S٠٠'),
            lambda w:w['tiles'][1].update(cellId='V52-MC-33'),
            lambda w:w['tiles'][1]['vector'].update(path='tiles/z.json.gz'),
            lambda w:w['tiles'][0]['vector'].update(decodedBytes=None))):
            bad=self.f.forged(self.base/f'ids-{i}.mwb',edit)
            with self.assertRaises(B.BundleError):B.verify_bundle(bad)

    def test_growing_and_excessive_header_manifest_payload_and_file_counts_are_bounded(self):
        attacks=[lambda h:h.update(worldManifestBytes=B.Limits.max_manifest_bytes+1),
                 lambda h:h.update(assetCount=B.Limits.max_assets+1),lambda h:h.update(assetCount=True),
                 lambda h:h.update(payloadBytes=B.Limits.max_total_bytes+1)]
        for i,edit in enumerate(attacks):
            bad=self.f.forged(self.base/f'header-{i}.mwb',header_edit=edit)
            with self.assertRaises(B.BundleError):B.import_bundle(bad,self.destination)
            self.assert_clean()
        bad=self.base/'huge-header.mwb';bad.write_bytes(B.MAGIC+struct.pack('>I',2**32-1))
        with self.assertRaisesRegex(B.BundleError,'header length'):B.verify_bundle(bad)
        for limits in (replace(B.Limits(),max_manifest_bytes=10),replace(B.Limits(),max_asset_bytes=1),
                       replace(B.Limits(),max_assets=1),replace(B.Limits(),max_total_bytes=10)):
            with self.assertRaises(B.BundleError):B.plan(self.f.root,limits=limits)

    def test_manifest_asset_footer_truncation_and_trailing_data_corruption_are_refused(self):
        B.export_bundle(self.f.root,self.archive);raw=self.archive.read_bytes()
        offset=len(B.MAGIC)+4;head_size=struct.unpack('>I',raw[len(B.MAGIC):offset])[0]
        head=json.loads(raw[offset:offset+head_size]);first_asset=offset+head_size+head['worldManifestBytes']
        changes=[raw[:first_asset]+bytes([raw[first_asset]^1])+raw[first_asset+1:],raw[:-1],raw[:10],raw+b'extra',
                 raw[:-1]+bytes([raw[-1]^1]),raw[:offset+head_size]+b' '+raw[offset+head_size+1:]]
        for i,data in enumerate(changes):
            bad=self.base/f'corrupt-{i}.mwb';bad.write_bytes(data)
            with self.assertRaises(B.BundleError):B.import_bundle(bad,self.destination)
            self.assert_clean()

    def test_valid_unsupported_source_or_broken_world_seal_never_installs(self):
        bad=self.f.forged(self.base/'source.mwb',lambda w:w.update(sourcePackSHA256='bad'))
        with self.assertRaises(B.BundleError):B.verify_bundle(bad)
        self.f.world['manifestContentSHA256']='f'*64;(self.f.root/'manifest.json').write_bytes(B.canonical(self.f.world))
        with self.assertRaisesRegex(B.BundleError,'seal'):B.export_bundle(self.f.root,self.archive)
        self.assertFalse(self.archive.exists())

    def test_existing_cache_archive_receipt_and_symlink_destinations_are_preserved(self):
        B.export_bundle(self.f.root,self.archive);old=self.archive.read_bytes()
        with self.assertRaises(B.BundleError):B.export_bundle(self.f.root,self.archive)
        self.assertEqual(self.archive.read_bytes(),old)
        self.destination.mkdir();marker=self.destination/'keep';marker.write_text('preserve')
        with self.assertRaises(B.BundleError):B.import_bundle(self.archive,self.destination)
        self.assertEqual(marker.read_text(),'preserve');marker.unlink();self.destination.rmdir()
        self.destination.symlink_to(self.f.root,target_is_directory=True)
        with self.assertRaisesRegex(B.BundleError,'Symlinks'):B.import_bundle(self.archive,self.destination)
        self.assertTrue(self.destination.is_symlink())

    def test_cache_asset_internal_symlink_and_archive_symlink_are_refused(self):
        source=self.f.root/'tiles/z.json.gz';copy_path=self.f.root/'tiles/copy.gz';copy_path.write_bytes(source.read_bytes())
        source.unlink();source.symlink_to(copy_path)
        with self.assertRaisesRegex(B.BundleError,'Symlinks'):B.plan(self.f.root)
        source.unlink();source.write_bytes(copy_path.read_bytes());B.export_bundle(self.f.root,self.archive)
        alias=self.base/'alias.mwb';alias.symlink_to(self.archive)
        with self.assertRaisesRegex(B.BundleError,'Symlinks'):B.verify_bundle(alias)

    def test_exports_cannot_write_inside_the_source_cache(self):
        with self.assertRaisesRegex(B.BundleError,'outside'):B.export_bundle(self.f.root,self.f.root/'new.mwb')
        self.assertFalse((self.f.root/'new.mwb').exists())

    def test_interruptions_leave_no_partial_archive_or_imported_cache(self):
        def interrupt(_):raise KeyboardInterrupt('fixture interruption')
        with self.assertRaises(KeyboardInterrupt):B.export_bundle(self.f.root,self.archive,progress=interrupt)
        self.assertFalse(self.archive.exists());self.assertFalse(Path(str(self.archive)+'.receipt.json').exists())
        self.assertEqual(list(self.base.glob('.cache.mwb.*')),[])
        B.export_bundle(self.f.root,self.archive)
        with self.assertRaises(KeyboardInterrupt):B.import_bundle(self.archive,self.destination,progress=interrupt)
        self.assert_clean();self.assertEqual(B.verify_bundle(self.archive)['status'],'verified')

    def test_input_mutations_abort_export_and_preserve_the_mutating_source(self):
        source=self.f.root/'metadata/parts.json';before=source.read_bytes();changed=False
        def mutate(row):
            nonlocal changed
            if not changed:changed=True;source.write_bytes(before[:-1]+b' ')
        with self.assertRaisesRegex(B.BundleError,'changed during export'):B.export_bundle(self.f.root,self.archive,progress=mutate)
        self.assertFalse(self.archive.exists());self.assertEqual(source.read_bytes(),before[:-1]+b' ')

    def test_verifier_honors_manifest_pins_and_detects_already_read_source_changes(self):
        with self.assertRaisesRegex(B.BundleError,'external fingerprint'):
            B.verify_world(self.f.root,expected_manifest_sha256='0'*64)
        source=self.f.root/'metadata/parts.json';before=source.read_bytes();changed=False
        def mutate(row):
            nonlocal changed
            if not changed:changed=True;source.write_bytes(before[:-1]+b' ')
        with self.assertRaisesRegex(B.BundleError,'changed during verification'):B.verify_world(self.f.root,progress=mutate)

    def test_exporter_code_or_manifest_changes_abort_before_publication(self):
        for kind in ('tool','manifest'):
            with self.subTest(kind=kind):
                temp_tool=self.base/f'{kind}-tool.py';temp_tool.write_bytes(SCRIPT.read_bytes())
                source=temp_tool if kind=='tool' else self.f.root/'manifest.json';before=source.read_bytes()
                def mutate(row):source.write_bytes(before+b' ')
                with patch.object(B,'__file__',str(temp_tool)):
                    with self.assertRaisesRegex(B.BundleError,'changed during export'):
                        B.export_bundle(self.f.root,self.archive,progress=mutate)
                self.assertFalse(self.archive.exists());self.assertFalse(Path(str(self.archive)+'.receipt.json').exists())
                if kind=='manifest':source.write_bytes(before)

    def test_cli_world_verification_cannot_silently_ignore_archive_or_manifest_pins(self):
        for options in (['--manifest-sha256','0'*64],['--sha256','0'*64],['--receipt',str(self.base/'missing.json')]):
            result=subprocess.run([sys.executable,'-S',str(SCRIPT),'verify','--world',str(self.f.root),*options],
                cwd=self.base,capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)

    def test_publication_failure_rolls_back_only_own_files_and_preserves_new_destination(self):
        real=B.publish_file
        def fail_archive(source,destination):
            if Path(destination)==self.archive:raise OSError('fixture failed publication')
            return real(source,destination)
        with patch.object(B,'publish_file',side_effect=fail_archive):
            with self.assertRaises(OSError):B.export_bundle(self.f.root,self.archive)
        self.assertFalse(self.archive.exists());self.assertFalse(Path(str(self.archive)+'.receipt.json').exists())
        B.export_bundle(self.f.root,self.archive)
        real_directory=B.publish_directory
        def race(source,destination):
            Path(destination).mkdir();(Path(destination)/'keep').write_text('concurrent')
            return real_directory(source,destination)
        with patch.object(B,'publish_directory',side_effect=race):
            with self.assertRaises(FileExistsError):B.import_bundle(self.archive,self.destination)
        self.assertEqual((self.destination/'keep').read_text(),'concurrent')

    def test_atomic_publication_never_replaces_even_an_empty_concurrent_directory(self):
        B.export_bundle(self.f.root,self.archive);real=B.publish_directory
        def race(source,destination):
            Path(destination).mkdir();return real(source,destination)
        with patch.object(B,'publish_directory',side_effect=race):
            with self.assertRaises(FileExistsError):B.import_bundle(self.archive,self.destination)
        self.assertTrue(self.destination.is_dir());self.assertEqual(list(self.destination.iterdir()),[])
        self.assertEqual(list(self.base.glob('.restored.bundle-import-*')),[])

    def test_concurrent_export_file_is_preserved_and_only_own_receipt_is_rolled_back(self):
        real=B.publish_file
        def race(source,destination):
            if Path(destination)==self.archive:self.archive.write_bytes(b'concurrent archive')
            return real(source,destination)
        with patch.object(B,'publish_file',side_effect=race):
            with self.assertRaises(FileExistsError):B.export_bundle(self.f.root,self.archive)
        self.assertEqual(self.archive.read_bytes(),b'concurrent archive')
        self.assertFalse(Path(str(self.archive)+'.receipt.json').exists())

    def test_no_free_disk_space_refuses_before_payload_writes(self):
        with patch.object(B.shutil,'disk_usage',return_value=shutil._ntuple_diskusage(1,1,0)):
            with self.assertRaisesRegex(B.BundleError,'disk space'):B.export_bundle(self.f.root,self.archive)
        self.assertFalse(self.archive.exists());B.export_bundle(self.f.root,self.archive)
        with patch.object(B.shutil,'disk_usage',return_value=shutil._ntuple_diskusage(1,1,0)):
            with self.assertRaisesRegex(B.BundleError,'disk space'):B.import_bundle(self.archive,self.destination)
        self.assert_clean()

    def test_import_accounts_for_small_file_allocation_and_filesystem_entry_limits(self):
        B.export_bundle(self.f.root,self.archive)
        estimate=B.plan(self.f.root)
        self.assertGreater(estimate['estimatedInstallAllocationBytes'],estimate['payloadBytes'])
        logical_only=estimate['payloadBytes']+B.RESERVE+1
        with patch.object(B.shutil,'disk_usage',return_value=shutil._ntuple_diskusage(logical_only,0,logical_only)):
            with self.assertRaisesRegex(B.BundleError,'disk space'):B.import_bundle(self.archive,self.destination)
        self.assert_clean()
        with patch.object(B,'allocation_info',return_value=(4096,1)):
            with self.assertRaisesRegex(B.BundleError,'filesystem entries'):B.import_bundle(self.archive,self.destination)
        self.assert_clean()

    def test_future_reachable_json_metadata_is_included_and_same_path_can_be_shared_exactly(self):
        self.f.world['notice']=self.f.asset('notes/info.json',b'{"known":"metadata"}','json')
        self.f.world['sameNotice']=copy.deepcopy(self.f.world['notice']);self.f.save()
        self.assertEqual(B.plan(self.f.root)['assetCount'],4)
        B.export_bundle(self.f.root,self.archive);B.import_bundle(self.archive,self.destination)
        self.assertEqual((self.destination/'notes/info.json').read_bytes(),b'{"known":"metadata"}')

    def test_standalone_copied_cli_works_under_python_S_without_project_modules(self):
        copied=self.base/'world_bundle.py';copied.write_bytes(SCRIPT.read_bytes())
        commands=[['plan','--world',str(self.f.root)],['export','--world',str(self.f.root),'--output',str(self.archive)],
                  ['verify','--bundle',str(self.archive)],['import','--bundle',str(self.archive),'--destination',str(self.destination)]]
        for command in commands:
            result=subprocess.run([sys.executable,'-S',str(copied),*command],cwd=self.base,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr);self.assertIsInstance(json.loads(result.stdout),dict)


if __name__=='__main__':unittest.main()
