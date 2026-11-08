"""Contrato da malha oficial: independência de credenciais e dados de produção."""
from __future__ import annotations
import unittest
import pandas as pd
from bairroiq.map_data import build_district_map, load_district_boundaries, DistrictMapService

class OfficialBoundariesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.coll=load_district_boundaries()
        cls.features=cls.coll['features']

    def test_count_codes_names_and_no_illustrative(self):
        self.assertEqual(self.coll['type'],'FeatureCollection')
        self.assertEqual(len(self.features),96)
        codes=[f['properties']['cd_dist'] for f in self.features]
        names=[f['properties']['neighborhood'] for f in self.features]
        self.assertEqual(len(set(codes)),96)
        self.assertEqual(len(set(names)),96)
        self.assertTrue(all(len(c)==9 and c.startswith('3550308') for c in codes))
        self.assertFalse(any(f['properties'].get('illustrative') for f in self.features))

    def test_provenance_wgs84(self):
        meta=self.coll['bairroiq_metadata']
        self.assertEqual(meta['source_epsg'],'EPSG:31983')
        self.assertEqual(meta['output_epsg'],'EPSG:4326')
        self.assertEqual(meta['publication_status'],'INTERNO_NAO_PUBLICAVEL')
        self.assertTrue(all(f['geometry']['type'] in ('Polygon','MultiPolygon') for f in self.features))
        for f in self.features:
            c=f['geometry']['coordinates'][0][0]
            self.assertTrue(-47<c[0]<-46)
            self.assertTrue(-25<c[1]<-23)

    def test_real_map_is_96_polygons_no_fallback_points(self):
        rows=[]
        for f in self.features:
            c=f['geometry']['coordinates'][0][0]
            rows.append({'neighborhood':f['properties']['neighborhood'],
            'longitude':c[0],'latitude':c[1], 'formal_jobs_score':60.,
            'safety_score':70.,'mobility_score':80.,'green_leisure_score':50.,
            'public_services_score':90.,'densidade_hab_km2':4500.,
            'robberies_per_1000':2.,'cluster':'P01 — perfil teste',
            'priority_score':70.})
        fig=build_district_map(pd.DataFrame(rows),self.coll,selectable=True)
        self.assertEqual(len(fig.data),1)
        self.assertEqual(fig.data[0].type,'choroplethmap')
        self.assertEqual(len(fig.data[0].locations),96)
        self.assertEqual(len(fig.data[0].geojson['features']),96)
        self.assertIn('Serviços públicos',fig.data[0].hovertemplate)
        self.assertNotIn('Orçamento',fig.data[0].hovertemplate)
        self.assertEqual(fig.layout.clickmode,'event+select')

    def test_service_reads_official_file(self):
        self.assertEqual(len(DistrictMapService()._boundaries['features']),96)

if __name__=='__main__': unittest.main()
