"""Close real native building components before selecting their actual cells."""
from __future__ import annotations
from copy import deepcopy
import gzip
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

GAME=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(GAME))
from tools.metropole import catalogue_building_parts as C
from tools.metropole import building_parts as B
GIS=all(importlib.util.find_spec(name) for name in ('shapely','pyproj','osmium','mapbox_earcut','numpy'))
if GIS:
    import shapely
    from shapely.geometry import box,mapping
    from shapely.ops import transform
    from tools.metropole import import_tiles as I


@unittest.skipUnless(GIS,'Use the optional GIS venv for source geometry fixtures.')
class CataloguePartsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.base=self.root/'vectors';self.base.mkdir();(self.base/'tiles').mkdir()
        self.edge=I.cell_bounds(0,0)[2];self.n=I.ORIGIN[1];self.source='a'*64

    def sources(self,*,rival=False,relation=False,partial=False,far=False):
        e,n=self.edge,self.n
        objects=[('osm/way/1',box(e-10,n-10,e+10,n+10),{'building':'yes','height':'20'}),
                 ('osm/way/2',box(e-10,n-10,e+(6 if partial else 0),n+10),{'building:part':'yes','height':'20'})]
        if not partial:objects.append(('osm/way/3',box(e,n-10,e+10,n+10),{'building:part':'yes','height':'20'}))
        if rival:objects.append(('osm/way/4',box(e-20,n-20,e+20,n+20),{'building':'yes','height':'20'}))
        if far:objects.append(('osm/way/99',box(e+10000,n,e+10020,n+20),{'building':'yes'}))
        dbpath=self.base/'canonical.sqlite';db=sqlite3.connect(dbpath)
        db.executescript('CREATE TABLE features(id TEXT PRIMARY KEY,layer TEXT,properties TEXT,geometry BLOB,minx REAL,miny REAL,maxx REAL,maxy REAL);CREATE VIRTUAL TABLE feature_index USING rtree(rowid,minx,maxx,miny,maxy);CREATE TABLE rejected(id TEXT,reason TEXT);CREATE TABLE source_relations(id INTEGER,tags TEXT,members TEXT);CREATE TABLE source_ways(id INTEGER,tags TEXT);')
        prepared=[]
        for identity,g,tags in objects:
            p={**tags,'canonical_id':identity,'soma:layer':'buildings','soma:geometry_sha256':B.digest(mapping(g))}
            db.execute('INSERT INTO features VALUES(?,?,?,?,?,?,?,?)',(identity,'buildings',B.canonical(p),sqlite3.Binary(shapely.to_wkb(g)),*g.bounds));prepared.append((p,g))
        if relation:
            members=[{'type':'way','ref':'1','role':'outline'},{'type':'way','ref':'2','role':'part'},{'type':'way','ref':'3','role':'part'}]
            db.execute('INSERT INTO source_relations VALUES(?,?,?)',(10,B.canonical({'type':'building'}),B.canonical(members)))
        db.execute('INSERT INTO feature_index SELECT rowid,minx,maxx,miny,maxy FROM features');db.commit();db.close()
        cells=set()
        for p,g in prepared:
            for x,y in I.grid_cells(g.bounds):
                if g.intersection(box(*I.cell_bounds(x,y))).area>1e-8:cells.add((x,y))
        tiles=[]
        for x,y in sorted(cells):
            bounds=list(I.cell_bounds(x,y));cell=I.cell_id(x,y);geometry=box(*bounds)
            features=[]
            for p,g in prepared:
                feature=I.clip_feature(g,p,geometry)
                if feature:features.append(feature)
            collection={'type':'FeatureCollection','features':features}
            record={'schema':'soma-massilia/geodata-cell/4','cellId':cell,'grid':{'x':x,'y':y},'boundsL93':bounds,
                    'sourceReceipt':{'sha256':self.source},'contentSHA256':B.digest(collection),'featureCollection':collection}
            raw=B.canonical(record).encode();compressed=gzip.compress(raw,mtime=0);p=self.base/'tiles'/f'{cell}.json.gz';p.write_bytes(compressed)
            tiles.append({'cellId':cell,'gridX':x,'gridY':y,'boundsL93':bounds,'vector':{'path':p.relative_to(self.base).as_posix(),
              'encoding':'gzip-json','bytes':len(compressed),'decodedBytes':len(raw),'sha256':B._file_sha256(p)}})
        self.manifest=self.base/'manifest.json'
        self.data={'schema':'soma-metropole/vector-tiles/1','crs':'EPSG:2154','units':'m','origin':list(I.ORIGIN),'cellSize':250,
                   'source':{'sha256':self.source},'canonicalStore':{'path':dbpath.name,'sha256':B._file_sha256(dbpath),'bytes':dbpath.stat().st_size,'encoding':'sqlite3'},'tiles':tiles}
        self.save()

    def save(self):self.manifest.write_text(B.canonical(self.data))
    def run_parts(self,name='parts.json',**kw):
        defaults={'part_ids':['osm/way/2'],'log':lambda v:None};defaults.update(kw)
        return C.prepare_parts(self.manifest,self.root/name,**defaults)

    def rejection_proof(self,envelope,*,building=True):
        identity='osm/way/500';reason='open-building-way';tags={'building':'yes'} if building else {'landuse':'forest'}
        path=self.base/'canonical.sqlite'
        with sqlite3.connect(path) as db:
            db.execute('INSERT INTO rejected VALUES(?,?)',(identity,reason))
            db.execute('INSERT INTO source_ways VALUES(?,?)',(500,B.canonical(tags)))
        self.data['canonicalStore'].update(sha256=B._file_sha256(path),bytes=path.stat().st_size)
        g=box(self.edge-1000,self.n-1000,self.edge+1000,self.n+1000)
        boundary=self.base/'boundary.geojson';boundary.write_text(B.canonical({'type':'FeatureCollection','features':[
            {'type':'Feature','properties':{},'geometry':mapping(transform(I.TO_WGS84.transform,g))}]}))
        self.data['boundary']={'path':str(boundary),'sha256':B._file_sha256(boundary)};self.save()
        w,s,e,n=envelope;positions={str(i+1):list(I.TO_WGS84.transform(*p)) for i,p in enumerate(((w,s),(e,s),(e,n)))}
        resolved=[I.TO_METRIC.transform(*p) for p in positions.values()]
        actual=[min(p[0] for p in resolved),min(p[1] for p in resolved),max(p[0] for p in resolved),max(p[1] for p in resolved)]
        record={'canonicalId':identity,'reason':reason,'tags':tags,'kind':'way','nodeRefs':list(positions),
                'nodePositionsWGS84':positions,'refsComplete':True,'missingNodeRefs':[],'boundsL93':actual}
        proof={'schema':'soma-metropole/osm-rejection-envelopes/1','sourceSHA256':self.source,
               'canonicalStoreSHA256':self.data['canonicalStore']['sha256'],'boundarySHA256':self.data['boundary']['sha256'],
               'osmManifestSHA256':B._file_sha256(self.manifest),'crs':'EPSG:2154','units':'m','records':[record]}
        proof['proofSHA256']=B.digest(proof);file=self.root/'rejection-proof.json';file.write_text(B.canonical(proof));return file

    def test_native_component_closes_sibling_parts_across_cells_without_reading_unrelated_city(self):
        self.sources(far=True)
        far=next(t for t in self.data['tiles'] if t['gridX']>10);(self.base/far['vector']['path']).write_bytes(b'not a readable source cell')
        before={p:p.read_bytes() for p in self.base.rglob('*') if p.is_file()}
        proof=self.run_parts();parent=proof['parents']['osm/way/1']
        self.assertTrue(parent['suppressParent']);self.assertEqual(set(parent['partIds']),{'osm/way/2','osm/way/3'})
        self.assertEqual(set(proof['selectionProvenance']['sourceCellHashes']),{'V52-MC-33','V52-MC-34'})
        self.assertEqual(proof['selectionProvenance']['peakLoadedCells'],2)
        self.assertEqual(before,{p:p.read_bytes() for p in before})
        self.assertFalse(proof['runtimeIntegrationPerformed']);self.assertEqual(B.loadproof(proof),proof)

    def test_every_native_parent_candidate_is_retained_for_uniqueness(self):
        self.sources(rival=True)
        proof=self.run_parts()
        self.assertEqual(proof['parents'],{})
        self.assertTrue(any(r['reason']=='ambiguous-geometric-parent' for r in proof['ambiguities']))
        self.assertTrue(all(c['objects']==4 for c in proof['selectionProvenance']['components']))

    def test_source_building_relation_is_bound_to_same_native_snapshot(self):
        self.sources(rival=True,relation=True)
        proof=self.run_parts()
        self.assertEqual(proof['partParents']['osm/way/2']['parentId'],'osm/way/1')
        self.assertEqual(proof['parents']['osm/way/1']['association'],['osm-building-relation'])
        self.assertEqual(proof['relationsSourceSHA256'],self.source)

    def test_ambiguous_or_missing_explicit_relation_outline_never_falls_back_to_a_convenient_parent(self):
        self.sources(rival=True,relation=True);path=self.base/'canonical.sqlite'
        with sqlite3.connect(path) as db:
            members=json.loads(db.execute('SELECT members FROM source_relations').fetchone()[0])
            members.append({'type':'way','ref':'4','role':'outline'})
            db.execute('UPDATE source_relations SET members=?',(B.canonical(members),))
        self.data['canonicalStore'].update(sha256=B._file_sha256(path),bytes=path.stat().st_size);self.save()
        proof=self.run_parts();self.assertFalse(proof['parents']);self.assertIn('Ambiguous explicit',proof['withheldGeometry'][0]['detail'])
        with sqlite3.connect(path) as db:
            members=[{'type':'way','ref':'999','role':'outline'},{'type':'way','ref':'2','role':'part'}]
            db.execute('UPDATE source_relations SET members=?',(B.canonical(members),))
        self.data['canonicalStore'].update(sha256=B._file_sha256(path),bytes=path.stat().st_size);self.save()
        proof=self.run_parts('missing-outline.json');self.assertFalse(proof['parents']);self.assertIn('Missing native',proof['withheldGeometry'][0]['detail'])

    def test_incomplete_footprint_and_corrupt_cell_withhold_the_whole_component(self):
        self.sources()
        right=next(t for t in self.data['tiles'] if t['cellId']=='V52-MC-34')
        path=self.base/right['vector']['path'];record=json.loads(gzip.decompress(path.read_bytes()))
        record['featureCollection']['features']=[f for f in record['featureCollection']['features'] if f['properties']['canonical_id']!='osm/way/1']
        record['contentSHA256']=B.digest(record['featureCollection']);raw=B.canonical(record).encode();compressed=gzip.compress(raw,mtime=0);path.write_bytes(compressed)
        right['vector'].update(bytes=len(compressed),decodedBytes=len(raw),sha256=B._file_sha256(path));self.save()
        proof=self.run_parts()
        self.assertFalse(proof['parents']);self.assertEqual(proof['selectionProvenance']['components'][0]['status'],'withheld')
        self.assertIn('completely represented',proof['withheldGeometry'][0]['detail'])
        path.write_bytes(compressed+b'corrupt')
        proof=self.run_parts('corrupt.json');self.assertFalse(proof['parents']);self.assertTrue(proof['withheldGeometry'])

    def test_partial_residual_is_an_unknown_footprint_without_volume_or_collision(self):
        self.sources(partial=True);proof=self.run_parts();parent=proof['parents']['osm/way/1']
        self.assertEqual(parent['status'],'derived-partial');self.assertFalse(parent['suppressParent'])
        self.assertEqual(parent['residualPolicy'],'unresolved-footprint-only');self.assertFalse(parent['residualVolumetric']);self.assertFalse(parent['residualCollision'])
        self.assertGreater(parent['residualAreaM2'],0);self.assertFalse(parent['artificialCutWalls'])

    def test_component_budgets_and_missing_published_cells_never_invent_complete_coverage(self):
        self.sources()
        proof=self.run_parts(limits=C.Limits(max_cells_per_component=1))
        self.assertFalse(proof['parents']);self.assertIn('budget',proof['withheldGeometry'][0]['detail'])
        self.data['tiles']=[t for t in self.data['tiles'] if t['cellId']=='V52-MC-33'];self.save()
        proof=self.run_parts('missing.json');self.assertFalse(proof['parents']);self.assertIn('not published',proof['withheldGeometry'][0]['detail'])

    def test_changed_source_manifest_never_publishes_and_existing_proof_is_preserved(self):
        self.sources();original=self.manifest.read_bytes()
        def change(_):self.manifest.write_bytes(original+b' ')
        with self.assertRaisesRegex(C.PartsCatalogueError,'changed'):
            self.run_parts(log=change)
        self.assertFalse((self.root/'parts.json').exists());self.manifest.write_bytes(original)
        output=self.root/'keep.json';output.write_text('keep')
        with self.assertRaisesRegex(C.PartsCatalogueError,'Output exists'):self.run_parts('keep.json')
        self.assertEqual(output.read_text(),'keep')

    def test_local_rejected_building_blocks_only_touching_parent_part_components(self):
        self.sources();e,n=self.edge,self.n
        file=self.rejection_proof([e-9,n-5,e-8,n-4])
        proof=self.run_parts(osm_rejection_proof=file)
        self.assertFalse(proof['parents']);self.assertIn('unclosed-building envelope',proof['withheldGeometry'][0]['detail'])
        self.assertEqual(len(proof['selectionProvenance']['sourceRejections']['localBuildingBlockers']),1)

    def test_local_blocker_outside_component_does_not_disable_good_associations(self):
        self.sources();e,n=self.edge,self.n
        file=self.rejection_proof([e+100,n+100,e+110,n+110])
        proof=self.run_parts(osm_rejection_proof=file)
        self.assertIn('osm/way/1',proof['parents'])
        self.assertEqual(proof['selectionProvenance']['rejectionEnvelopeFileSHA256'],B._file_sha256(file))

    def test_building_envelope_outside_amp_is_reported_without_blocking_inside_components(self):
        self.sources();e,n=self.edge,self.n
        file=self.rejection_proof([e+5000,n+5000,e+5010,n+5010])
        proof=self.run_parts(osm_rejection_proof=file)
        self.assertIn('osm/way/1',proof['parents'])
        rejection=proof['selectionProvenance']['sourceRejections']
        self.assertEqual(len(rejection['buildingEnvelopesOutsideScope']),1);self.assertEqual(rejection['localBuildingBlockers'],[])

    def test_nonbuilding_rejection_never_blocks_even_when_its_envelope_overlaps(self):
        self.sources();e,n=self.edge,self.n;file=self.rejection_proof([e-10,n-10,e+10,n+10],building=False)
        proof=self.run_parts(osm_rejection_proof=file)
        self.assertIn('osm/way/1',proof['parents']);self.assertEqual(proof['selectionProvenance']['sourceRejections']['knownNonBuilding'],1)

    def test_incomplete_or_wrong_snapshot_rejection_proof_is_refused_before_components(self):
        self.sources();e,n=self.edge,self.n;file=self.rejection_proof([e+100,n+100,e+110,n+110])
        original=json.loads(file.read_bytes())
        for index,change in enumerate((lambda d:d.update(osmManifestSHA256='0'*64),
                                      lambda d:d['records'][0].update(refsComplete=False),
                                      lambda d:d['records'][0].update(boundsL93=[0,0,1,1]))):
            bad=deepcopy(original);change(bad);bad['proofSHA256']=B.digest({k:v for k,v in bad.items() if k!='proofSHA256'});file.write_text(B.canonical(bad))
            with self.assertRaises(ValueError):self.run_parts(f'bad-proof-{index}.json',osm_rejection_proof=file)
            self.assertFalse((self.root/f'bad-proof-{index}.json').exists())

    def test_rejection_proof_drift_prevents_publication_after_good_component(self):
        self.sources();e,n=self.edge,self.n;file=self.rejection_proof([e+100,n+100,e+110,n+110]);raw=file.read_bytes()
        def change(_):file.write_bytes(raw+b' ')
        with self.assertRaisesRegex(C.PartsCatalogueError,'Rejected-source proof changed'):
            self.run_parts(osm_rejection_proof=file,log=change)
        self.assertFalse((self.root/'parts.json').exists())


if __name__=='__main__':unittest.main()
