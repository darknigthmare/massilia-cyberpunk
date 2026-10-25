import dataclasses
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

TOOL=Path(__file__).resolve().parents[2]/'tools/metropole/match_catalogues.py'
spec=importlib.util.spec_from_file_location('catalogue_match_under_test',TOOL);tool=importlib.util.module_from_spec(spec);sys.modules[spec.name]=tool;spec.loader.exec_module(tool)
try:
 import shapely
 from shapely.geometry import box,mapping
 from shapely.ops import transform
 from pyproj import Transformer
 GIS=True
except ImportError:GIS=False


@unittest.skipUnless(GIS,'Optional GIS environment required')
class CatalogueNeighbourhoodTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.osm_root=self.root/'osm';self.osm_root.mkdir();self.ign_root=self.root/'ign';self.ign_root.mkdir()
  self.source_sha='a'*64;self.boundary=self.root/'boundary.geojson'
  inverse=Transformer.from_crs('EPSG:2154','EPSG:4326',always_xy=True).transform
  boundary=box(892000,6246000,894000,6249000)
  self.boundary.write_text(tool.canonical({'type':'FeatureCollection','features':[{'type':'Feature','properties':{},'geometry':mapping(transform(inverse,boundary))}]}))
  self.bounds=[893000.5,6247000,893100,6247100]
  self.seed=box(892991,6247020,893011,6247040)
  self.reference=box(892990,6247020,893010,6247040)
  self.metadata={'license':'Licence Ouverte 2.0','date':'2026-06-15','units':'m','verticalDatum':'NGF-IGN69','crs':'EPSG:2154','fields':{'ignId':'cleabs','height':'hauteur','groundAltitude':'altitude_minimale_sol'},'heightMeaning':'Ground to gutter, not ridge; zero unknown.'}
  self.limits=tool.Limits(step=1000,max_osm=100,max_ign=100)

 def sources(self,objects,ign=None):
  dbpath=self.osm_root/'canonical.sqlite';db=sqlite3.connect(dbpath)
  db.executescript('CREATE TABLE features(id TEXT PRIMARY KEY,layer TEXT,properties TEXT,geometry BLOB,minx REAL,miny REAL,maxx REAL,maxy REAL);CREATE VIRTUAL TABLE feature_index USING rtree(rowid,minx,maxx,miny,maxy);CREATE TABLE rejected(id TEXT,reason TEXT,detail TEXT);CREATE TABLE source_ways(id INTEGER,tags TEXT);CREATE TABLE source_relations(id INTEGER,tags TEXT);')
  self.properties={}
  for identity,g,props in objects:
   props={**props,'canonical_id':identity,'soma:layer':'buildings','soma:geometry_sha256':tool.digest(mapping(g))};self.properties[identity]=props
   db.execute('INSERT INTO features VALUES(?,?,?,?,?,?,?,?)',(identity,'buildings',tool.canonical(props),sqlite3.Binary(shapely.to_wkb(g)),*g.bounds))
  db.execute('INSERT INTO feature_index SELECT rowid,minx,maxx,miny,maxy FROM features');db.commit();db.close()
  self.manifest=self.osm_root/'manifest.json'
  m={'schema':'soma-metropole/vector-tiles/1','crs':'EPSG:2154','units':'m','bounds':[892000,6246000,894000,6249000],'sourceBoundsWGS84':[5,43,6,44],'source':{'sha256':self.source_sha},'canonicalStore':{'path':'canonical.sqlite','sha256':tool.core.file_sha256(dbpath),'bytes':dbpath.stat().st_size,'encoding':'sqlite3'},'boundary':None,'tiles':[]}
  tool.save(self.manifest,m)
  path=self.ign_root/'buildings.sqlite';db=sqlite3.connect(path)
  db.execute('CREATE TABLE objects(ign_id TEXT PRIMARY KEY,content_sha256 TEXT,geometry_sha256 TEXT,feature_json TEXT,min_x REAL,min_y REAL,max_x REAL,max_y REAL,geometry_valid INTEGER)')
  for number,g in enumerate(ign or [self.reference]):
   feature={'type':'Feature','properties':{'cleabs':f'IGN{number}','hauteur':15,'altitude_minimale_sol':10},'geometry':mapping(g)};raw=tool.canonical(feature)
   db.execute('INSERT INTO objects VALUES(?,?,?,?,?,?,?,?,?)',(f'IGN{number}',hashlib.sha256(raw.encode()).hexdigest(),tool.digest(mapping(g)),raw,*g.bounds,1))
  db.commit();db.close()
  source={'schema':'soma-metropole/ign-bdtopo-source-index/1',**self.metadata,'queryAcquisitionComplete':True,'sourceGeometryCoverageValidated':True,'boundarySHA256':tool.core.file_sha256(self.boundary)}
  source['sourceSHA256']=tool.digest(source);source.update(sqliteSHA256=tool.core.file_sha256(path),sqliteBytes=path.stat().st_size)
  self.ign_index=self.ign_root/'source-index.json';tool.save(self.ign_index,source)

 def run_match(self,**kwargs):
  output=self.root/'matched';result=tool.match_catalogues(self.manifest,self.ign_index,self.boundary,output,bounds=self.bounds,limits=kwargs.get('limits',self.limits),log=lambda v:None)
  return result,output

 def test_reciprocal_rival_outside_owner_partition_blocks_false_positive(self):
  self.sources([('osm/way/1',self.seed,{'building':'yes'}),('osm/way/2',self.reference,{'building':'yes'})])
  result,output=self.run_match();self.assertEqual(result['statistics']['seedBuildings'],1);self.assertEqual(result['statistics']['accepted'],0)
  with sqlite3.connect(output/'matches.sqlite') as db:
   self.assertEqual(db.execute('SELECT reason FROM rejected').fetchone()[0],'ambiguous-reciprocal-osm-candidates')
  self.assertEqual(result['statistics']['peakOSMNeighbours'],2)

 def test_explicit_height_rival_still_contests_reciprocity(self):
  self.sources([('osm/way/1',self.seed,{'building':'yes'}),('osm/way/2',self.reference,{'building':'yes','height':'15'})])
  result,_=self.run_match();self.assertEqual(result['statistics']['accepted'],0)

 def test_active_parts_are_excluded_with_same_core_policy(self):
  self.sources([('osm/way/1',self.seed,{'building':'yes','building:part':'yes'})])
  result,output=self.run_match();self.assertEqual(result['statistics']['accepted'],0)
  with sqlite3.connect(output/'matches.sqlite') as db:self.assertEqual(db.execute('SELECT reason FROM rejected').fetchone()[0],'active-osm-building-part')

 def test_matches_bind_native_sources_and_never_publish_internal_cell_ids(self):
  self.sources([('osm/way/1',self.seed,{'building':'yes'})])
  before=[tool.core.file_sha256(p) for p in (self.osm_root/'canonical.sqlite',self.ign_root/'buildings.sqlite')]
  result,output=self.run_match();self.assertEqual(result['statistics']['accepted'],1)
  with sqlite3.connect(output/'matches.sqlite') as db:row=json.loads(db.execute('SELECT proof_json FROM matches').fetchone()[0])
  self.assertNotIn('cells',row);self.assertEqual(row['heightKind'],'eaves');self.assertFalse(row['runtimeCellBindingsPresent'])
  self.assertEqual(row['geometrySHA256'],self.properties['osm/way/1']['soma:geometry_sha256'])
  self.assertEqual(row['sourceSHA256'],self.source_sha);self.assertGreaterEqual(row['reciprocalMargin'],.15)
  self.assertEqual(before,[tool.core.file_sha256(p) for p in (self.osm_root/'canonical.sqlite',self.ign_root/'buildings.sqlite')])
  self.assertEqual(result['sealSHA256'],tool.digest({k:v for k,v in result.items() if k!='sealSHA256'}))

 def test_manifest_hashes_capture_parsed_bytes_and_not_reserialized_json(self):
  self.sources([('osm/way/1',self.seed,{'building':'yes'})])
  raw=self.manifest.read_bytes();value,sha=tool.read_hashed(self.manifest)
  self.assertEqual(sha,hashlib.sha256(raw).hexdigest())
  self.manifest.write_bytes(raw+b' \n')
  same,changed_sha=tool.read_hashed(self.manifest)
  self.assertEqual(same,value);self.assertNotEqual(changed_sha,sha)

 def test_manifest_or_boundary_drift_during_matching_never_publishes_a_seal(self):
  self.sources([('osm/way/1',self.seed,{'building':'yes'})])
  for number,path in enumerate((self.manifest,self.ign_index,self.boundary)):
   original=path.read_bytes();output=self.root/f'drift-{number}'
   def mutate_after_partition(_):path.write_bytes(original+b' \n')
   try:
    with self.subTest(path=path.name),self.assertRaisesRegex(tool.CatalogueError,'changed during matching'):
     tool.match_catalogues(self.manifest,self.ign_index,self.boundary,output,bounds=self.bounds,limits=self.limits,log=mutate_after_partition)
    self.assertFalse((output/'seal.json').exists())
   finally:path.write_bytes(original)

 def test_coverage_boundary_rejects_otherwise_good_match(self):
  self.sources([('osm/way/1',self.seed,{'building':'yes'})])
  document=tool.read(self.boundary)
  inverse=Transformer.from_crs('EPSG:2154','EPSG:4326',always_xy=True).transform
  document['features'][0]['geometry']=mapping(transform(inverse,box(893000,6246000,894000,6249000)))
  tool.save(self.boundary,document)
  index=tool.read(self.ign_index);index['boundarySHA256']=tool.core.file_sha256(self.boundary)
  index['sourceSHA256']=tool.digest({k:v for k,v in index.items() if k not in ('sourceSHA256','sqliteSHA256','sqliteBytes')});tool.save(self.ign_index,index)
  result,output=self.run_match();self.assertEqual(result['statistics']['accepted'],0)
  with sqlite3.connect(output/'matches.sqlite') as db:self.assertEqual(db.execute('SELECT reason FROM rejected').fetchone()[0],'neighbourhood-outside-proven-source-coverage')

 def test_budget_failure_does_not_publish_partial_seal(self):
  self.sources([('osm/way/1',self.seed,{'building':'yes'}),('osm/way/2',self.reference,{'building':'yes'})])
  with self.assertRaisesRegex(tool.CatalogueError,'partition budget'):
   self.run_match(limits=dataclasses.replace(self.limits,max_osm=1))
  self.assertFalse((self.root/'matched/seal.json').exists())

 def rejection_proof(self,points,complete=True):
  path=self.osm_root/'canonical.sqlite'
  with sqlite3.connect(path) as db:db.execute('INSERT INTO rejected VALUES(?,?,?)',('osm/way/99','open-building-way',''))
  manifest=tool.read(self.manifest);manifest['canonicalStore'].update(sha256=tool.core.file_sha256(path),bytes=path.stat().st_size);tool.save(self.manifest,manifest)
  inverse=Transformer.from_crs('EPSG:2154','EPSG:4326',always_xy=True).transform
  forward=Transformer.from_crs('EPSG:4326','EPSG:2154',always_xy=True).transform
  positions={str(i+1):list(inverse(*point)) for i,point in enumerate(points)};metric=[forward(*point) for point in positions.values()]
  record={'canonicalId':'osm/way/99','kind':'way','reason':'open-building-way','tags':{'building':'yes'},'nodeRefs':list(positions),'nodePositionsWGS84':positions,'refsComplete':complete,'missingNodeRefs':[] if complete else ['missing'],'boundsL93':[min(p[0] for p in metric),min(p[1] for p in metric),max(p[0] for p in metric),max(p[1] for p in metric)]}
  proof={'schema':'soma-metropole/osm-rejection-envelopes/1','sourceSHA256':self.source_sha,'canonicalStoreSHA256':manifest['canonicalStore']['sha256'],'boundarySHA256':tool.core.file_sha256(self.boundary),'crs':'EPSG:2154','units':'m','records':[record]};proof['proofSHA256']=tool.digest(proof);path=self.root/'rejection-proof.json';tool.save(path,proof);return path

 def test_resolved_open_way_blocks_reciprocal_candidate_locally(self):
  distant=box(893050,6247060,893070,6247080)
  self.sources([('osm/way/1',self.seed,{'building':'yes'}),('osm/way/2',distant,{'building':'yes'})],ign=[self.reference,distant])
  proof=self.rejection_proof([(892990.2,6247025),(892990.7,6247025),(892990.4,6247030)])
  result=tool.match_catalogues(self.manifest,self.ign_index,self.boundary,self.root/'matched',bounds=self.bounds,limits=self.limits,osm_rejection_proof=proof,log=lambda v:None)
  self.assertEqual(result['statistics']['accepted'],1);self.assertEqual(len(result['sourceRejections']['localBuildingBlockers']),1)
  with sqlite3.connect(self.root/'matched/matches.sqlite') as db:
   self.assertEqual(db.execute('SELECT canonical_id FROM matches').fetchall(),[('osm/way/2',)])
   refused=db.execute('SELECT reason,detail FROM rejected WHERE canonical_id=?',('osm/way/1',)).fetchone();self.assertEqual(refused[0],'quarantined-source-building-neighbourhood');self.assertEqual(json.loads(refused[1])['quarantinedSourceIds'],['osm/way/99'])

 def test_proven_outside_rejection_does_not_block_matching(self):
  self.sources([('osm/way/1',self.seed,{'building':'yes'})]);proof=self.rejection_proof([(894100,6247020),(894110,6247030)])
  result=tool.match_catalogues(self.manifest,self.ign_index,self.boundary,self.root/'matched',bounds=self.bounds,limits=self.limits,osm_rejection_proof=proof,log=lambda v:None)
  self.assertEqual(result['statistics']['accepted'],1);self.assertEqual(len(result['sourceRejections']['buildingEnvelopesOutsideScope']),1);self.assertEqual(result['sourceRejections']['localBuildingBlockers'],[])

 def test_missing_source_ref_or_false_envelope_is_never_repaired(self):
  for failure in ('missing','false-envelope'):
   with self.subTest(failure=failure):
    self.sources([('osm/way/1',self.seed,{'building':'yes'})]);proof=self.rejection_proof([(893000,6247020),(893005,6247030)],complete=failure!='missing')
    if failure=='false-envelope':
     document=tool.read(proof);document['records'][0]['boundsL93'][0]+=5;document['proofSHA256']=tool.digest({k:v for k,v in document.items() if k!='proofSHA256'});tool.save(proof,document)
    with self.assertRaisesRegex(tool.CatalogueError,'envelope'):tool.match_catalogues(self.manifest,self.ign_index,self.boundary,self.root/'matched',bounds=self.bounds,limits=self.limits,osm_rejection_proof=proof,log=lambda v:None)
    self.assertFalse((self.root/'matched/seal.json').exists())
    for p in [self.osm_root/'canonical.sqlite',self.ign_root/'buildings.sqlite']:p.unlink()

 def test_unknown_rejected_source_object_refuses_uncertain_neighbourhood(self):
  self.sources([('osm/way/1',self.seed,{'building':'yes'})])
  path=self.osm_root/'canonical.sqlite'
  with sqlite3.connect(path) as db:db.execute('INSERT INTO rejected VALUES(?,?,?)',('osm/way/99','unassembled-source-area',''))
  m=tool.read(self.manifest);m['canonicalStore'].update(sha256=tool.core.file_sha256(path),bytes=path.stat().st_size);tool.save(self.manifest,m)
  with self.assertRaisesRegex(tool.CatalogueError,'lack tags/envelopes'):self.run_match()

 def test_hash_mismatch_and_live_wal_source_are_refused(self):
  self.sources([('osm/way/1',self.seed,{'building':'yes'})])
  m=tool.read(self.manifest);m['canonicalStore']['sha256']='b'*64;tool.save(self.manifest,m)
  with self.assertRaisesRegex(tool.CatalogueError,'hash/size'):self.run_match()
  wal=self.osm_root/'canonical.sqlite-wal';wal.write_bytes(b'live')
  with self.assertRaisesRegex(tool.CatalogueError,'live import'):tool.readonly(self.osm_root/'canonical.sqlite')

 def prepare_vector(self,bad_content=False,explicit_height=False):
  props=dict(self.properties['osm/way/1'])
  if explicit_height:props['height']='20'
  collection={'type':'FeatureCollection','features':[{'type':'Feature','id':'osm/way/1','properties':props,'geometry':mapping(self.seed)}]}
  record={'schema':'soma-massilia/geodata-cell/4','cellId':'REAL-CELL-01','sourceReceipt':{'sha256':self.source_sha},'featureCollection':collection,'contentSHA256':tool.digest(collection)}
  if bad_content:record['contentSHA256']='0'*64
  raw=tool.canonical(record).encode();compressed=gzip.compress(raw,mtime=0);p=self.osm_root/'real.json.gz';p.write_bytes(compressed)
  m=tool.read(self.manifest);m['tiles']=[{'cellId':'REAL-CELL-01','vector':{'path':p.name,'encoding':'gzip-json','bytes':len(compressed),'decodedBytes':len(raw),'sha256':tool.core.file_sha256(p)}}];tool.save(self.manifest,m)
  return record

 def test_sidecars_bind_real_cell_content_and_source_without_mutating_inputs(self):
  self.sources([('osm/way/1',self.seed,{'building':'yes'})]);seal,output=self.run_match();record=self.prepare_vector()
  result=tool.sidecars(output/'seal.json',self.manifest,self.root/'sidecars');self.assertEqual(result['tiles'][0]['matchedFragments'],1)
  side=json.loads(gzip.decompress((self.root/'sidecars'/result['tiles'][0]['path']).read_bytes()))
  self.assertEqual(side['cellId'],'REAL-CELL-01');self.assertEqual(side['contentSHA256'],record['contentSHA256'])
  self.assertEqual(side['proofSHA256'],tool.digest({k:v for k,v in side.items() if k!='proofSHA256'}));self.assertFalse(side['runtimeIntegrationPerformed'])
  self.assertEqual(result['sourceMatchingManifestSHA256'],seal['osmManifestSHA256'])
  self.assertEqual(result['currentVectorManifestSHA256'],tool.core.file_sha256(self.manifest))
  self.assertNotEqual(result['sourceMatchingManifestSHA256'],result['currentVectorManifestSHA256'])
  self.assertEqual(side['sourceMatchingManifestSHA256'],result['sourceMatchingManifestSHA256'])
  self.assertEqual(side['currentVectorManifestSHA256'],result['currentVectorManifestSHA256'])

 def test_source_drift_during_sidecar_reading_never_publishes_a_manifest(self):
  self.sources([('osm/way/1',self.seed,{'building':'yes'})]);_,catalogue=self.run_match();self.prepare_vector()
  seal_path=catalogue/'seal.json';vector=self.osm_root/'real.json.gz';binding=tool.core.binding_key
  for number,path in enumerate((self.manifest,seal_path,vector)):
   original=path.read_bytes();output=self.root/f'sidecar-drift-{number}'
   def mutate_while_matching(*args):
    key=binding(*args);path.write_bytes(original+b' ');return key
   try:
    with patch.object(tool.core,'binding_key',side_effect=mutate_while_matching):
     with self.subTest(path=path.name),self.assertRaisesRegex(tool.CatalogueError,'changed during sidecar preparation'):
      tool.sidecars(seal_path,self.manifest,output)
    self.assertFalse((output/'manifest.json').exists())
   finally:path.write_bytes(original)

 def test_sidecars_refuse_foreign_frame_and_all_synthetic_flags(self):
  self.sources([('osm/way/1',self.seed,{'building':'yes'})]);_,catalogue=self.run_match();record=self.prepare_vector()
  original=tool.read(self.manifest)
  for index,change in enumerate(({'crs':'EPSG:4326'},{'units':'ft'})):
   tool.save(self.manifest,{**original,**change})
   with self.assertRaisesRegex(tool.CatalogueError,'snapshot/frame'):
    tool.sidecars(catalogue/'seal.json',self.manifest,self.root/f'foreign-frame-{index}')
  tool.save(self.manifest,original)
  record['v50Synthetic']=True;raw=tool.canonical(record).encode();compressed=gzip.compress(raw,mtime=0)
  path=self.osm_root/'real.json.gz';path.write_bytes(compressed)
  original['tiles'][0]['vector'].update(bytes=len(compressed),decodedBytes=len(raw),sha256=hashlib.sha256(compressed).hexdigest());tool.save(self.manifest,original)
  with self.assertRaisesRegex(tool.CatalogueError,'Real cell content/source binding'):
   tool.sidecars(catalogue/'seal.json',self.manifest,self.root/'synthetic-v50')

 def test_sidecars_refuse_false_content_binding_and_preserve_explicit_osm_height(self):
  self.sources([('osm/way/1',self.seed,{'building':'yes'})]);_,output=self.run_match();self.prepare_vector(bad_content=True)
  with self.assertRaisesRegex(tool.CatalogueError,'content/source binding'):tool.sidecars(output/'seal.json',self.manifest,self.root/'bad-sidecars')
  self.prepare_vector(explicit_height=True);result=tool.sidecars(output/'seal.json',self.manifest,self.root/'preserved-sidecars');self.assertEqual(result['tiles'][0]['matchedFragments'],0)


if __name__=='__main__':unittest.main()
