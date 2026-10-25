"""Named settlement destinations, never bus-stop names or invented addresses."""
from __future__ import annotations
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import sys
import unittest

GAME=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(GAME))
from tools.metropole import settlement_anchors as S
from tools.metropole import building_parts as B


def candidate(identity='osm/node/1',**tags):
    return {'canonicalId':identity,'properties':{'name':'Aix-en-Provence','place':'city',**tags}}


def in_ring(point,ring):
    x,y=point;inside=False
    for i in range(len(ring)):
        a,b=ring[i-1],ring[i]
        if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:inside=not inside
    return inside


def within(point,geometry):
    polygons=[geometry['coordinates']] if geometry['type']=='Polygon' else geometry['coordinates']
    return any(in_ring(point,poly[0]) and not any(in_ring(point,hole) for hole in poly[1:]) for poly in polygons)


class SettlementSelectionTests(unittest.TestCase):
    def test_normalization_handles_accents_apostrophes_and_hyphens_without_semantic_aliases(self):
        self.assertEqual(S.normalized("Berre-l'Étang"),S.normalized('BERRE L’ETANG'))
        self.assertEqual(S.normalized('Ensuès-la-Redonne'),S.normalized('Ensues la Redonne'))
        self.assertNotEqual(S.normalized('Saint-Paul-lès-Durance'),S.normalized('Saint-Paul-lez-Durance'))

    def test_bus_stops_and_foreign_insee_codes_never_become_settlement_anchors(self):
        bus=candidate('osm/node/9',place=None,highway='bus_stop')
        foreign=candidate('osm/node/8',**{'ref:INSEE':'13055'})
        chosen,eligible=S.choose_anchor('13001','Aix-en-Provence',[bus,foreign],{})
        self.assertIsNone(chosen);self.assertEqual(eligible,[])
        city=candidate();chosen,eligible=S.choose_anchor('13001','Aix-en-Provence',[bus,city],{})
        self.assertEqual(chosen[0]['canonicalId'],'osm/node/1')

    def test_ref_insee_is_exact_and_a_unique_admin_centre_can_resolve_real_ambiguity(self):
        a=candidate();b=candidate('osm/node/2')
        chosen,eligible=S.choose_anchor('13001','Aix-en-Provence',[a,b],{})
        self.assertIsNone(chosen);self.assertEqual(len(eligible),2)
        chosen,_=S.choose_anchor('13001','Aix-en-Provence',[a,b],{'osm/node/2':['osm/relation/70279']})
        self.assertEqual(chosen[0]['canonicalId'],'osm/node/2');self.assertEqual(chosen[1],'admin_centre-tiebreak')
        chosen,_=S.choose_anchor('13001','Aix-en-Provence',[a,b],{'osm/node/1':[], 'osm/node/2':[]})
        self.assertIsNone(chosen)
        c=candidate(name='Different source spelling',**{'ref:INSEE':'13001'})
        chosen,_=S.choose_anchor('13001','Aix-en-Provence',[c],{})
        self.assertEqual(chosen[1],'ref:INSEE')


class ShippedSettlementEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table=json.loads((GAME/'data/v69/settlement-anchors.json').read_bytes())
        cls.territory=json.loads((GAME/'data/v69/territory.json').read_bytes())
        cls.contours=json.loads((GAME/'data/v69/acquisition/amp-communes-2026-10-25.geojson').read_bytes())

    def test_seal_and_inline_source_feature_receipt_bind_exact_json_bytes(self):
        r=self.table
        self.assertEqual(r['schema'],S.SCHEMA)
        self.assertEqual(r['proofSHA256'],B.digest({k:v for k,v in r.items() if k!='proofSHA256'}))
        descriptor=r['sources']['pointFeatures'];raw=B.canonical(descriptor['featureCollection']).encode('utf-8')
        self.assertEqual(descriptor['bytes'],len(raw));self.assertEqual(descriptor['sha256'],hashlib.sha256(raw).hexdigest())
        changed=deepcopy(r);changed['anchors']['13001']['canonicalId']='osm/node/999'
        self.assertNotEqual(r['proofSHA256'],B.digest({k:v for k,v in changed.items() if k!='proofSHA256'}))

    def test_all_92_codes_and_source_point_count_are_honest(self):
        r=self.table;codes=sorted(c['code'] for c in self.territory['communes'])
        self.assertEqual(sorted(r['anchors']),codes);self.assertEqual(r['coverage']['communeCodes'],codes)
        points=[row for row in r['anchors'].values() if row['status']=='source-place']
        fallback=[row for row in r['anchors'].values() if row['status']=='contour-fallback']
        self.assertEqual(len(points),r['coverage']['sourcePointCount']);self.assertEqual(len(fallback),r['coverage']['contourFallbackCount'])
        self.assertEqual(len(points),91);self.assertEqual(len(fallback),1)
        self.assertEqual(fallback[0]['name'],'Saint-Paul-lès-Durance')
        self.assertNotIn('canonicalId',fallback[0]);self.assertNotIn('pointWGS84',fallback[0]);self.assertNotIn('pointL93',fallback[0])

    def test_every_source_anchor_uses_a_real_settlement_feature_inside_its_exact_commune(self):
        table=self.table
        features={f['properties']['canonical_id']:f for f in table['sources']['pointFeatures']['featureCollection']['features']}
        contours={f['properties']['code']:f['geometry'] for f in self.contours['features']}
        for code,row in table['anchors'].items():
            if row['status']!='source-place':continue
            with self.subTest(code=code):
                f=features[row['canonicalId']];p=f['properties']
                self.assertEqual(p['place'],row['evidence']['place']);self.assertIn(p['place'],S.PLACES)
                self.assertEqual(f['geometry']['type'],'Point');self.assertEqual(f['geometry']['coordinates'],row['pointWGS84'])
                self.assertEqual(p['soma:metricGeometry']['coordinates'],row['pointL93'])
                self.assertEqual(B.digest(p['soma:metricGeometry']),row['geometrySHA256'])
                self.assertEqual(p['soma:geometry_sha256'],row['geometrySHA256'])
                self.assertEqual(row['evidence']['canonicalId'],row['canonicalId']);self.assertEqual(row['evidence']['nodeId'],row['nodeId'])
                self.assertEqual(row['sourcePbfSHA256'],table['sourcePbfSHA256']);self.assertEqual(row['vectorManifestSHA256'],table['vectorManifestSHA256'])
                self.assertEqual(row['contentSHA256'],row['cellContentSHA256'])
                self.assertTrue(row['evidence']['unique']);self.assertTrue(within(row['pointWGS84'],contours[code]))
                self.assertTrue(all(math.isfinite(v) for v in row['pointWGS84']+row['pointL93']))
                for key in ('sourcePbfSHA256','vectorManifestSHA256','contentSHA256','geometrySHA256'):
                    self.assertRegex(row[key],r'^[a-f0-9]{64}$')

    def test_aix_marseille_berre_and_pertuis_use_the_expected_named_source_nodes(self):
        expected={'13001':('osm/node/26686595',[897890.3102053261,6273152.373484382]),
                  '13055':('osm/node/26761400',[893038.9292475197,6247043.487106511]),
                  '13014':('osm/node/26691897',[875432.205018042,6266477.0718302615]),
                  '84089':('osm/node/26691956',[901817.6529634602,6291656.386013931])}
        for code,(identity,point) in expected.items():
            self.assertEqual(self.table['anchors'][code]['canonicalId'],identity)
            self.assertEqual(self.table['anchors'][code]['pointL93'],point)
        aix=self.table['anchors']['13001']['pointL93']
        self.assertGreater(math.dist(aix,[893055.26,6273689.61]),4000)


if __name__=='__main__':unittest.main()
