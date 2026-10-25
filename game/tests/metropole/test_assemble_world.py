"""Assemble source-linked layers without mistaking file presence for readiness."""
from __future__ import annotations

import base64
import copy
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
SPEC=importlib.util.spec_from_file_location('metropole_assemble_world',ROOT/'tools/metropole/assemble_world.py')
A=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(A)
from tools.v69.terrain_tiles import validate_grid,tile_from_grid,grid_digest


def write_json(path,value):path.write_bytes(A.canonical(value)+b'\n')


def write_asset(path,value,**extra):
    raw=A.canonical(value);buffer=io.BytesIO()
    with gzip.GzipFile(fileobj=buffer,mode='wb',filename='',mtime=0) as stream:stream.write(raw)
    compressed=buffer.getvalue();path.write_bytes(compressed)
    return {'path':path.name,'encoding':'gzip-json','sha256':A.digest(compressed),'bytes':len(compressed),
            'decodedBytes':len(raw),**extra}


class AssemblyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.base=self.root/'sources';self.base.mkdir()
        self.bounds=[A.ORIGIN[0]-125,A.ORIGIN[1]-125,A.ORIGIN[0]+125,A.ORIGIN[1]+125]
        self.pbf='a'*64;self.cell='V52-MC-33';self.native='b'*64
        self.fc={'type':'FeatureCollection','features':[]};self.content=A.digest(A.canonical(self.fc))
        self.record={'schema':'soma-massilia/geodata-cell/4','cellId':self.cell,'boundsL93':self.bounds,'grid':{'x':0,'y':0},
                     'sourceReceipt':{'sha256':self.pbf},'v53Synthetic':False,'featureCollection':self.fc,'contentSHA256':self.content}
        self.vectors={'schema':'soma-metropole/vector-tiles/1','crs':'EPSG:2154','units':'m','origin':A.ORIGIN,'cellSize':250,
                      'source':{'sha256':self.pbf,'license':'ODbL-1.0','attribution':'QA source package, not a city survey'},
                      'nativeTopology':{'sha256':self.native},'coverageExplicitPartial':True,'completeMetropole':False,
                      'tiles':[{'cellId':self.cell,'gridX':0,'gridY':0,'boundsL93':self.bounds,
                                'vector':write_asset(self.base/'source-vector.gz',self.record)}]}
        self.vector_path=self.base/'vectors.json';write_json(self.vector_path,self.vectors)
        self.vector_sha=A.digest(self.vector_path.read_bytes())
        self.terrain_pack=json.loads((ROOT/'data/v58/terrain.ign.json').read_text())
        self.terrain=tile_from_grid(validate_grid(self.terrain_pack),self.bounds,self.terrain_pack['source'])
        grid=validate_grid(self.terrain,self.bounds)
        self.terrain_manifest={'schema':'soma-metropole/terrain-tiles/1','crs':'EPSG:2154','units':'m',
                               'origin':A.ORIGIN,'cellSize':250,'verticalDatum':'NGF-IGN69',
                               'tiles':[{'cellId':self.cell,'boundsL93':self.bounds,
                                         'terrain':write_asset(self.base/'source-terrain.gz',self.terrain,
                                                               gridSHA256=grid.sha256,complete=True,noDataNodes=0)}]}
        self.terrain_path=self.base/'terrain.json';write_json(self.terrain_path,self.terrain_manifest)
        self.surface={'schema':'soma-metropole/surface-cell/1','cellId':self.cell,'boundsL93':self.bounds,
                      'contentSHA256':self.content,'sourcePbfSHA256':self.pbf,'sourceVectorManifestSHA256':self.vector_sha,
                      'nativeTopologySHA256':self.native,'dimensionCoreSHA256':'c'*64,
                      'cell':{'contentSHA256':self.content,'sourceSHA256':self.pbf,'surfaces':{'road':[[[0,0],[1,0],[0,1]]]}}}
        self.surface_manifest={'schema':'soma-metropole/surface-tiles/1','crs':'EPSG:2154','units':'m',
                               'sourceVectorManifest':{'sha256':self.vector_sha},'sourcePbfSHA256':self.pbf,
                               'nativeTopologySHA256':self.native,'dimensionCore':{'sha256':'c'*64},
                               'tiles':[{'cellId':self.cell,'boundsL93':self.bounds,'cellHash':self.content,
                                         'surface':write_asset(self.base/'source-surface.gz',self.surface)}]}
        self.surface_path=self.base/'surfaces.json';write_json(self.surface_path,self.surface_manifest)
        self.graph={'schema':'soma/navigation-source/1','sourcePbfSHA256':self.pbf,'sourcePackSHA256':self.vector_sha,
                    'cellHashes':{self.cell:self.content},'nodes':[['n/1',A.ORIGIN[0],A.ORIGIN[1]],['n/2',A.ORIGIN[0]+5,A.ORIGIN[1]]],
                    'ways':{'10':{'name':'QA native source axis'}},'edges':[[0,1,'10',5,15,0,[self.cell],1]],'turns':[],
                    'sourceStatus':{'nodeTagsComplete':True,'nativeNodeIdentity':True,'vectorConstrained':True}}
        self.nav_manifest={'schema':'soma-metropole/navigation-tiles/1','crs':'EPSG:2154','units':'m',
                           'sourceVectorManifest':{'sha256':self.vector_sha},'sourcePbfSHA256':self.pbf,'nativeTopologySHA256':self.native,
                           'tiles':[{'cellId':self.cell,'boundsL93':self.bounds,'cellHash':self.content,
                                     'navigation':write_asset(self.base/'source-navigation.gz',self.graph)}]}
        self.nav_path=self.base/'navigation.json';write_json(self.nav_path,self.nav_manifest)
        self.territory=ROOT/'data/v69/territory.json'

    def tearDown(self):self.temp.cleanup()

    def assemble(self,name='world',**kwargs):
        defaults={'terrain':self.terrain_path,'surfaces':self.surface_path,'navigation':self.nav_path,'territory':self.territory}
        defaults.update(kwargs)
        return A.assemble_world(self.vector_path,self.root/name,**defaults)

    def test_all_layers_are_copied_checked_sealed_and_remain_preparation_only(self):
        world=self.assemble();tile=world['tiles'][0]
        self.assertEqual(world['sourcePackSHA256'],self.vector_sha)
        self.assertEqual(world['target']['id'],'200054807')
        self.assertEqual(world['target']['boundarySHA256'],json.loads(self.territory.read_bytes())['boundary']['sha256'])
        self.assertIsNone(world['coverage']['administrativeCoverageRatio'])
        self.assertFalse(world['activationPerformed']);self.assertTrue(world['preparationOnly']);self.assertFalse(world['completeMetropole'])
        self.assertEqual(world['coverage']['allLayersAvailableCells'],1)
        for layer in A.LAYERS:
            entry=tile[layer];path=self.root/'world'/entry['path']
            self.assertEqual(A.digest(path.read_bytes()),entry['sha256'])
            self.assertTrue(entry['path'].endswith(f'.{layer}.json.gz'))
        self.assertEqual(world['manifestContentSHA256'],A.digest(A.canonical({k:v for k,v in world.items() if k!='manifestContentSHA256'})))
        self.assertEqual(list((self.root/'world').rglob('*.sqlite')),[])
        self.assertFalse(tile['preparation']['activationPerformed'])

    def copy_boundary_reference(self):
        reference=self.root/'administrative-reference';reference.mkdir()
        shutil.copyfile(self.territory,reference/'territory.json')
        shutil.copytree(self.territory.parent/'acquisition',reference/'acquisition')
        self.territory=reference/'territory.json'
        return json.loads(self.territory.read_bytes())

    def test_boundary_reference_survives_relocation_with_only_relative_paths(self):
        reference=self.copy_boundary_reference()
        world=self.assemble()
        self.assertEqual(world['target']['boundarySHA256'],reference['boundary']['sha256'])
        self.assertFalse(world['completeMetropole'])
        self.assertIsNone(world['coverage']['administrativeCoverageRatio'])

    def test_boundary_hash_drift_refuses_assembly_without_leaving_output(self):
        reference=self.copy_boundary_reference();boundary=reference['boundary']
        for index,descriptor in enumerate((boundary,boundary['source'],boundary['rawReceipt'],boundary['validationReceipt'])):
            with self.subTest(path=descriptor['path']):
                path=self.territory.parent/descriptor['path'];original=path.read_bytes();path.write_bytes(original+b' ')
                try:
                    with self.assertRaisesRegex(A.AssemblyFailure,'Administrative boundary validation'):
                        self.assemble(f'boundary-drift-{index}')
                    self.assertFalse((self.root/f'boundary-drift-{index}').exists())
                finally:path.write_bytes(original)

    def test_boundary_path_traversal_and_external_symlinks_are_refused(self):
        reference=self.copy_boundary_reference();boundary=reference['boundary'];original=boundary['path']
        for index,path in enumerate(('../outside.geojson','/tmp/outside.geojson','acquisition/../outside.geojson')):
            boundary['path']=path;write_json(self.territory,reference)
            with self.assertRaisesRegex(A.AssemblyFailure,'Administrative boundary validation'):
                self.assemble(f'boundary-path-{index}')
        outside=self.root/'outside.geojson';outside.write_bytes((self.territory.parent/original).read_bytes())
        (self.territory.parent/'escape.geojson').symlink_to(outside)
        boundary['path']='escape.geojson';write_json(self.territory,reference)
        with self.assertRaisesRegex(A.AssemblyFailure,'Administrative boundary validation'):
            self.assemble('boundary-symlink')

    def test_a_resealed_validity_receipt_cannot_admit_repaired_or_invalid_source_geometry(self):
        reference=self.copy_boundary_reference();descriptor=reference['boundary']['validationReceipt']
        path=self.territory.parent/descriptor['path'];proof=json.loads(path.read_bytes())
        for index,changes in enumerate(({'geometryRepairApplied':True},{'unionValid':False},{'communeCodes':['99999']*92})):
            write_json(path,{**proof,**changes});raw=path.read_bytes();descriptor.update(bytes=len(raw),sha256=A.digest(raw))
            write_json(self.territory,reference)
            with self.assertRaisesRegex(A.AssemblyFailure,'reçu de validité'):
                self.assemble(f'invalid-boundary-proof-{index}')

    def test_absent_boundary_stays_null_without_administrative_coverage_claim(self):
        reference=self.copy_boundary_reference();reference['boundary']=None;write_json(self.territory,reference)
        world=self.assemble()
        self.assertIsNone(world['target']['boundarySHA256'])
        self.assertIsNone(world['coverage']['administrativeCoverageRatio'])
        self.assertFalse(world['completeMetropole'])

    def test_missing_layers_are_explicit_null_and_never_replaced_by_flat_terrain(self):
        world=self.assemble(terrain=None,surfaces=None,navigation=None)
        tile=world['tiles'][0]
        self.assertTrue(all(tile[layer] is None for layer in ['terrain','surfaces','navigation']))
        self.assertEqual(tile['preparation']['missingLayers'],['terrain','surfaces','navigation'])
        self.assertEqual(world['coverage']['allLayersAvailableCells'],0)

    def test_nodata_bytes_remain_invalid_and_are_not_advertised_as_complete(self):
        grid=validate_grid(self.terrain)
        mask=bytearray(grid.mask);mask[len(mask)//2]=0
        self.terrain['maskBase64']=base64.b64encode(mask).decode()
        self.terrain['sha256']=grid_digest(self.terrain['gridHeader'],grid.data,bytes(mask))
        self.terrain['stats']=validate_grid(self.terrain).stats
        self.terrain_manifest['tiles'][0]['terrain']=write_asset(self.base/'source-terrain.gz',self.terrain,complete=False,noDataNodes=1,
                                                                gridSHA256=self.terrain['sha256'])
        write_json(self.terrain_path,self.terrain_manifest)
        world=self.assemble();tile=world['tiles'][0]
        self.assertFalse(tile['terrain']['complete']);self.assertFalse(tile['preparation']['terrainComplete'])
        self.assertEqual(world['coverage']['terrainNoDataCells'],1)
        with gzip.open(self.root/'world'/tile['terrain']['path'],'rt') as stream:pack=json.load(stream)
        self.assertEqual(validate_grid(pack).mask[len(mask)//2],0)
        self.terrain_manifest['tiles'][0]['terrain']['complete']=True
        write_json(self.terrain_path,self.terrain_manifest)
        with self.assertRaisesRegex(A.AssemblyFailure,'completeness declaration'):
            self.assemble('false-complete')

    def test_foreign_sidecar_fingerprint_is_rejected_without_partial_output(self):
        self.nav_manifest['sourceVectorManifest']['sha256']='f'*64;write_json(self.nav_path,self.nav_manifest)
        with self.assertRaisesRegex(A.AssemblyFailure,'Foreign sidecar'):
            self.assemble()
        self.assertFalse((self.root/'world').exists())
        self.assertEqual(list(self.root.glob('.metropole-assemble-*')),[])

    def test_corrupt_asset_is_rejected_even_when_other_layers_are_present(self):
        p=self.base/'source-navigation.gz';p.write_bytes(p.read_bytes()+b'bad')
        with self.assertRaisesRegex(A.AssemblyFailure,'size'):
            self.assemble()
        self.assertFalse((self.root/'world').exists())

    def test_source_paths_cannot_traverse_or_escape_via_symlinks(self):
        for index,path in enumerate(['../outside.gz','/tmp/outside.gz','tiles/../../outside.gz']):
            self.vectors['tiles'][0]['vector']['path']=path;write_json(self.vector_path,self.vectors)
            with self.assertRaisesRegex(A.AssemblyFailure,'Unsafe source asset path'):
                self.assemble(f'world-{index}',terrain=None,surfaces=None,navigation=None)
        outside=self.root/'outside.gz';outside.write_bytes((self.base/'source-vector.gz').read_bytes())
        (self.base/'escape.gz').symlink_to(outside)
        self.vectors['tiles'][0]['vector']['path']='escape.gz';write_json(self.vector_path,self.vectors)
        with self.assertRaisesRegex(A.AssemblyFailure,'escaping'):
            self.assemble('world-symlink',terrain=None,surfaces=None,navigation=None)

    def test_wrong_surface_cell_link_is_not_hidden_by_a_valid_gzip_checksum(self):
        self.surface['contentSHA256']='e'*64
        self.surface_manifest['tiles'][0]['surface']=write_asset(self.base/'source-surface.gz',self.surface)
        write_json(self.surface_path,self.surface_manifest)
        with self.assertRaisesRegex(A.AssemblyFailure,'Surface layer'):
            self.assemble()

    def test_unknown_vertical_datum_is_refused_even_with_a_matching_grid_checksum(self):
        header=json.loads(self.terrain['gridHeader']);header['verticalDatum']='EPSG:5773'
        self.terrain['gridHeader']=A.canonical(header).decode()
        grid=validate_grid(tile_from_grid(validate_grid(self.terrain_pack),self.bounds,self.terrain_pack['source']))
        self.terrain['sha256']=grid_digest(self.terrain['gridHeader'],grid.data,grid.mask)
        self.terrain_manifest['tiles'][0]['terrain']=write_asset(self.base/'source-terrain.gz',self.terrain)
        write_json(self.terrain_path,self.terrain_manifest)
        with self.assertRaisesRegex(A.AssemblyFailure,'datum'):
            self.assemble()

    def test_compressed_and_decoded_byte_budgets_fail_before_publishing(self):
        with patch.object(A,'MAX_DECODED',64):
            with self.assertRaisesRegex(A.AssemblyFailure,'decoded-byte budget'):
                self.assemble('decoded-budget')
        self.assertFalse((self.root/'decoded-budget').exists())
        self.vectors['tiles'][0]['vector']['bytes']=A.MAX_COMPRESSED+1
        write_json(self.vector_path,self.vectors)
        with self.assertRaisesRegex(A.AssemblyFailure,'byte budget'):
            self.assemble('compressed-budget',terrain=None,surfaces=None,navigation=None)
        self.assertFalse((self.root/'compressed-budget').exists())

    def test_same_inputs_produce_identical_manifest_and_asset_bytes(self):
        first=self.assemble('first');second=self.assemble('second')
        self.assertEqual(first,second)
        for entry in first['tiles']:
            for layer in A.LAYERS:
                path=entry[layer]['path']
                self.assertEqual((self.root/'first'/path).read_bytes(),(self.root/'second'/path).read_bytes())

    def test_existing_output_and_duplicate_grid_positions_are_preserved_or_refused(self):
        existing=self.root/'existing';existing.mkdir();(existing/'user.txt').write_text('keep')
        with self.assertRaisesRegex(A.AssemblyFailure,'already exists'):self.assemble('existing')
        self.assertEqual((existing/'user.txt').read_text(),'keep')
        self.vectors['tiles'].append({**self.vectors['tiles'][0],'cellId':'V52-MC-E00-S00'})
        write_json(self.vector_path,self.vectors)
        with self.assertRaisesRegex(A.AssemblyFailure,'same historical grid'):
            self.assemble('duplicate',terrain=None,surfaces=None,navigation=None)

    def administrative_terrain(self,*,no_data=False,missing_asset=False):
        """Actual frozen IGN nodes with explicit administrative target definitions."""
        boundary=json.loads(self.territory.read_bytes())['boundary']['sha256']
        self.terrain_manifest.update(terrainOnly=True,vectorCoverageClaimed=False,
            targetDefinition={'schema':'soma-metropole/terrain-target-cells/1','boundarySHA256':boundary},
            source={'method':'node-copy-no-resampling','gridSHA256':self.terrain_pack['sha256'],
                    'crs':'EPSG:2154','units':'m','verticalDatum':'NGF-IGN69','receipt':self.terrain_pack['source']})
        self.terrain_manifest['tiles'][0].update(gridX=0,gridY=0)
        bounds=[v+250 if i in (0,2) else v for i,v in enumerate(self.bounds)]
        terrain=tile_from_grid(validate_grid(self.terrain_pack),bounds,self.terrain_pack['source'])
        if no_data:
            grid=validate_grid(terrain);mask=bytearray(grid.mask);mask[len(mask)//2]=0
            terrain['maskBase64']=base64.b64encode(mask).decode()
            terrain['sha256']=grid_digest(terrain['gridHeader'],grid.data,bytes(mask))
            terrain['stats']=validate_grid(terrain).stats
        grid=validate_grid(terrain)
        descriptor=None if missing_asset else write_asset(self.base/'extra-terrain.gz',terrain,
            gridSHA256=grid.sha256,complete=grid.stats['noData']==0,noDataNodes=grid.stats['noData'])
        self.terrain_manifest['tiles'].append({'cellId':'V52-MC-34','gridX':1,'gridY':0,
                                              'boundsL93':bounds,'terrain':descriptor})
        write_json(self.terrain_path,self.terrain_manifest)
        return terrain

    def test_explicit_terrain_only_cells_copy_real_dem_without_fabricating_vectors(self):
        self.administrative_terrain()
        with self.assertRaisesRegex(A.AssemblyFailure,'outside the vector edition'):
            self.assemble('default-still-strict')
        world=self.assemble(include_terrain_only=True)
        tiles={tile['cellId']:tile for tile in world['tiles']};tile=tiles['V52-MC-34']
        self.assertTrue(world['includeTerrainOnly']);self.assertTrue(tile['terrainOnly'])
        self.assertIsNone(tile['contentSHA256'])
        for layer in ('vector','surfaces','navigation'):self.assertIsNone(tile[layer])
        self.assertEqual(tile['preparation']['missingLayers'],['vector','surfaces','navigation'])
        self.assertFalse(tile['preparation']['allLayersAvailable'])
        self.assertFalse(tile['preparation']['activationPerformed'])
        self.assertNotIn('featureCollection',tile)
        self.assertEqual((self.root/'world'/tile['terrain']['path']).read_bytes(),(self.base/'extra-terrain.gz').read_bytes())
        self.assertEqual(world['coverage']['vectorCells'],1)
        self.assertEqual(world['coverage']['terrainOnlyCells'],1)
        self.assertEqual(world['coverage']['terrainCompleteCells'],2)
        self.assertEqual(world['coverage']['allLayersAvailableCells'],1)
        self.assertEqual(world['coverage']['terrainTargetCells'],2)
        self.assertEqual(world['coverage']['terrainTargetsWithoutAsset'],0)
        self.assertNotIn('terrainOnly',tiles[self.cell])

    def test_terrain_only_nodata_and_missing_assets_never_become_flat_ground(self):
        source=self.administrative_terrain(no_data=True)
        world=self.assemble(include_terrain_only=True);tile=world['tiles'][1]
        self.assertTrue(tile['terrainOnly']);self.assertFalse(tile['terrain']['complete'])
        self.assertEqual(world['coverage']['terrainNoDataCells'],1)
        self.assertEqual(world['coverage']['terrainCompleteCells'],1)
        with gzip.open(self.root/'world'/tile['terrain']['path'],'rt') as stream:copied=json.load(stream)
        self.assertEqual(validate_grid(copied).mask,validate_grid(source).mask)
        self.assertEqual(validate_grid(copied).data,validate_grid(source).data)
        self.terrain_manifest['tiles'][1]['terrain']=None;write_json(self.terrain_path,self.terrain_manifest)
        missing=self.assemble('missing-dem',include_terrain_only=True)
        self.assertEqual(len(missing['tiles']),1)
        self.assertEqual(missing['coverage']['terrainOnlyCells'],0)
        self.assertEqual(missing['coverage']['terrainTargetsWithoutAsset'],1)

    def test_terrain_only_boundary_frame_and_grid_are_checked_before_publication(self):
        self.administrative_terrain();original=copy.deepcopy(self.terrain_manifest)
        mutations=[lambda m:m['targetDefinition'].update(boundarySHA256='f'*64),
                   lambda m:m.update(origin=[A.ORIGIN[0]+1,A.ORIGIN[1]]),
                   lambda m:m['tiles'][1].update(gridX=2),
                   lambda m:m['tiles'][1].update(cellId='V52-MC-E00-S00',gridX=0,boundsL93=self.bounds),
                   lambda m:m.update(vectorCoverageClaimed=True)]
        for index,mutate in enumerate(mutations):
            candidate=copy.deepcopy(original);mutate(candidate);write_json(self.terrain_path,candidate)
            with self.subTest(index=index),self.assertRaises(A.AssemblyFailure):
                self.assemble(f'bad-dem-frame-{index}',include_terrain_only=True)
            self.assertFalse((self.root/f'bad-dem-frame-{index}').exists())
        self.assertEqual(list(self.root.glob('.metropole-assemble-*')),[])

    def test_terrain_only_requires_verified_boundary_dem_and_explicit_boolean(self):
        with self.assertRaisesRegex(A.AssemblyFailure,'explicit boolean'):
            self.assemble('not-boolean',include_terrain_only=1)
        with self.assertRaisesRegex(A.AssemblyFailure,'requires a terrain manifest'):
            self.assemble('no-dem',terrain=None,include_terrain_only=True)
        self.administrative_terrain()
        reference=self.copy_boundary_reference();reference['boundary']=None;write_json(self.territory,reference)
        with self.assertRaisesRegex(A.AssemblyFailure,'verified administrative boundary'):
            self.assemble('no-boundary',include_terrain_only=True)

    def test_terrain_only_refuses_corrupt_extra_assets_and_foreign_source_provenance(self):
        self.administrative_terrain();path=self.base/'extra-terrain.gz';original=path.read_bytes()
        path.write_bytes(original+b'changed')
        with self.assertRaisesRegex(A.AssemblyFailure,'size'):
            self.assemble('corrupt-extra',include_terrain_only=True)
        path.write_bytes(original)
        with gzip.open(path,'rt') as stream:pack=json.load(stream)
        pack['source']['sourceGridSHA256']='f'*64
        self.terrain_manifest['tiles'][1]['terrain']=write_asset(path,pack)
        write_json(self.terrain_path,self.terrain_manifest)
        with self.assertRaisesRegex(A.AssemblyFailure,'another source grid'):
            self.assemble('foreign-extra-source',include_terrain_only=True)
        self.assertFalse((self.root/'corrupt-extra').exists());self.assertFalse((self.root/'foreign-extra-source').exists())

    def test_terrain_only_checks_actual_geotiff_derivation_and_every_source_fingerprint(self):
        try:
            import numpy as np
            import rasterio
            from rasterio.transform import from_origin
        except ImportError:
            self.skipTest('Optional GIS development dependencies are not installed')
        from tools.v69.terrain_tiles import tiles_from_geotiff,TARGET_SCHEMA
        self.administrative_terrain()
        original=validate_grid(self.terrain_pack);source_path=self.root/'point-grid-derivative.tif'
        with rasterio.open(source_path,'w',driver='GTiff',count=1,width=original.cols,height=original.rows,
                dtype='float32',crs='EPSG:2154',nodata=-99999,
                transform=from_origin(original.x0-original.step/2,original.n0+original.step/2,original.step,original.step)) as raster:
            raster.write(np.frombuffer(original.data,dtype='<f4').reshape(original.rows,original.cols),1)
            raster.set_band_unit(1,'m');raster.update_tags(VERTICAL_DATUM='NGF-IGN69')
        targets={'schema':TARGET_SCHEMA,'crs':'EPSG:2154','origin':A.ORIGIN,'cellSize':250,
                 'boundarySHA256':self.terrain_manifest['targetDefinition']['boundarySHA256'],
                 'tiles':[{key:tile[key] for key in ('cellId','gridX','gridY','boundsL93')}
                          for tile in self.terrain_manifest['tiles']]}
        receipt={**self.terrain_pack['source'],'crs':'EPSG:2154','units':'m','verticalDatum':'NGF-IGN69'}
        raster_tiles=self.root/'raster-tiles'
        manifest=tiles_from_geotiff([source_path],targets,raster_tiles,25,receipt)
        self.terrain_path=raster_tiles/'manifest.json'
        world=self.assemble('raster-derived-world',include_terrain_only=True)
        self.assertEqual(world['coverage']['terrainOnlyCells'],1)
        self.assertEqual(world['coverage']['terrainCompleteCells'],2)
        link=manifest['tiles'][1]['terrain'];asset=raster_tiles/link['path']
        with gzip.open(asset,'rt') as stream:pack=json.load(stream)
        pack['source']['files'][0]['sha256']='f'*64
        changed=write_asset(asset,pack)
        changed['path']=link['path'];manifest['tiles'][1]['terrain']=changed
        write_json(self.terrain_path,manifest)
        with self.assertRaisesRegex(A.AssemblyFailure,'foreign source raster'):
            self.assemble('foreign-raster-source',include_terrain_only=True)
        self.assertFalse((self.root/'foreign-raster-source').exists())

    def test_terrain_only_cli_is_explicit_and_default_manifest_shape_is_unchanged(self):
        ordinary=self.assemble('ordinary')
        self.assertNotIn('includeTerrainOnly',ordinary)
        self.assertNotIn('terrainOnlyCells',ordinary['coverage'])
        self.assertNotIn('allLayersAvailable',ordinary['tiles'][0]['preparation'])
        self.administrative_terrain()
        result=subprocess.run([sys.executable,str(ROOT/'tools/metropole/assemble_world.py'),
            '--vectors',str(self.vector_path),'--terrain',str(self.terrain_path),'--territory',str(self.territory),
            '--output',str(self.root/'cli-world'),'--include-terrain-only'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['coverage']['terrainOnlyCells'],1)

    def test_streaming_core_loads_terrain_only_explicitly_and_never_grants_3d_readiness(self):
        self.administrative_terrain();self.assemble(include_terrain_only=True)
        code=r'''const fs=require('fs'),path=require('path'),zlib=require('zlib');
const S=require(process.argv[1]),root=process.argv[2],manifest=JSON.parse(fs.readFileSync(path.join(root,'manifest.json'),'utf8'));
S.validateManifest(manifest);
const store=S.createTileStore({manifest,maxResidentBytes:128*1024*1024,
fetchBytes:async rel=>new Uint8Array(fs.readFileSync(path.join(root,rel))),
decodeBytes:async bytes=>new Uint8Array(zlib.gunzipSync(bytes)),canActivate:()=>true});
(async()=>{const tile=await store.load('V52-MC-34',{layers:['terrain']});
let vectorRejected=false,physicalRejected=false;
try{await store.load('V52-MC-34')}catch(e){vectorRejected=true}
try{await store.load('V52-MC-34',{require3D:true})}catch(e){physicalRejected=true}
process.stdout.write(JSON.stringify({ready:tile.readyFor3D,layers:Object.keys(tile.layers),vectorRejected,physicalRejected}));
})().catch(e=>{console.error(e);process.exitCode=1});'''
        result=subprocess.run(['node','-e',code,str(ROOT/'src/v69/streaming-core.js'),str(self.root/'world')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout),{'ready':False,'layers':['terrain'],'vectorRejected':True,'physicalRejected':True})

    def test_actual_streaming_core_loads_assets_but_refuses_automatic_activation(self):
        self.assemble()
        code=r'''const fs=require('fs'),path=require('path'),zlib=require('zlib');
const S=require(process.argv[1]),root=process.argv[2];
const manifest=JSON.parse(fs.readFileSync(path.join(root,'manifest.json'),'utf8'));
S.validateManifest(manifest);
const store=S.createTileStore({manifest,maxResidentBytes:128*1024*1024,
  fetchBytes:async rel=>new Uint8Array(fs.readFileSync(path.join(root,rel))),
  decodeBytes:async bytes=>new Uint8Array(zlib.gunzipSync(bytes)),canActivate:()=>false});
(async()=>{const tile=await store.load('V52-MC-33',{require3D:true});
  process.stdout.write(JSON.stringify({ready:tile.readyFor3D,layers:Object.keys(tile.layers)}));})().catch(e=>{console.error(e);process.exitCode=1});'''
        result=subprocess.run(['node','-e',code,str(ROOT/'src/v69/streaming-core.js'),str(self.root/'world')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        status=json.loads(result.stdout);self.assertFalse(status['ready']);self.assertEqual(set(status['layers']),set(A.LAYERS))


if __name__=='__main__':unittest.main()
