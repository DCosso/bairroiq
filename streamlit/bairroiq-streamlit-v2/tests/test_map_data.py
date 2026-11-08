"""Testes do mapa atualizados de sete polígonos demo para a malha oficial de 96.

Preserva os fluxos sample legados e valida filtros, seleção e temas.
"""
from __future__ import annotations
import unittest
import pandas as pd
from bairroiq.map_data import (
    DistrictMapService, build_district_map, district_from_map_selection,
    filter_districts, load_district_boundaries, restrict_to_mapped_districts,
    selected_district_ranking, toggle_district_detail,
)

def sample():
    return pd.DataFrame([
        {'neighborhood':'Vila Mariana','latitude':-23.59,'longitude':-46.64,
         'formal_jobs_score':82.,'safety_score':90.,'robbery_index':1.5,
         'lighting_led':95.,'trees_score':86.,'mobility_score':90.,
         'affordability_score':55.,'priority_score':85.},
        {'neighborhood':'Pinheiros','latitude':-23.56,'longitude':-46.69,
         'formal_jobs_score':95.,'safety_score':62.,'robbery_index':2.,
         'lighting_led':78.,'trees_score':77.,'mobility_score':84.,
         'affordability_score':38.,'priority_score':69.},
    ])

class DistrictMapTests(unittest.TestCase):
    def setUp(self):
        self.df=sample()
        self.boundaries=load_district_boundaries()

    def test_service_map_filter_and_polygons(self):
        service=DistrictMapService()
        visible=service.filter_districts(self.df,['Vila Mariana'],'',[])
        mapped,missing=service.restrict_to_mapped_districts(visible)
        fig=service.build_map(mapped)
        self.assertEqual(missing,[])
        self.assertEqual(list(fig.data[0].locations),['Vila Mariana'])
        self.assertEqual(fig.data[0].type,'choroplethmap')

    def test_filters_work_and_ignore_stale_ui_values(self):
        names=self.df.neighborhood.tolist()
        self.assertEqual(len(filter_districts(self.df,names,'',[])),2)
        self.assertEqual(filter_districts(self.df,names,'',['Segurança']).neighborhood.tolist(),['Vila Mariana'])
        self.assertEqual(len(filter_districts(self.df,names,'',['Iluminação LED'])),2)

    def test_natural_language_legacy_data_search(self):
        names=self.df.neighborhood.tolist()
        self.assertEqual(filter_districts(self.df,names,'seguro',[]).neighborhood.tolist(),['Vila Mariana'])
        self.assertEqual(filter_districts(self.df,names,'metrô',[]).neighborhood.tolist(),['Vila Mariana','Pinheiros'])

    def test_geojson_now_has_96_official_boundaries(self):
        self.assertEqual(len(self.boundaries['features']),96)
        names={f['properties']['neighborhood'] for f in self.boundaries['features']}
        self.assertTrue({'Vila Mariana','Pinheiros','Moema','Sé','Cangaiba','Cidade Lider','Jaguara'}.issubset(names))

    def test_polygon_hover_and_theme(self):
        light=build_district_map(self.df,self.boundaries,theme='light')
        dark=build_district_map(self.df,self.boundaries,theme='dark')
        self.assertEqual(set(light.data[0].locations),set(self.df.neighborhood))
        self.assertIn('Arborização',light.data[0].hovertemplate)
        self.assertEqual(light.layout.map.style,'carto-voyager')
        self.assertEqual(dark.layout.map.style,'carto-darkmatter')
        self.assertEqual(light.data[0].colorscale[0][1],'rgba(26, 54, 93, 0.1)')
        self.assertEqual(dark.data[0].colorscale[0][1],'rgba(255, 255, 255, 0.45)')

    def test_sample_illustrative_only_for_unknown_name(self):
        frame=sample().head(1).copy()
        frame.loc[frame.index[0],'neighborhood']='Bairro Sintético Fora da Fonte'
        frame['illustrative_boundary']=True
        fig=build_district_map(frame,self.boundaries)
        self.assertTrue(fig.data[0].geojson['features'][0]['properties']['illustrative'])

    def test_unknown_district_has_no_invented_boundary(self):
        frame=pd.DataFrame({'neighborhood':['Vila Mariana','Não Existe']})
        mapped,missing=restrict_to_mapped_districts(frame,self.boundaries)
        self.assertEqual(mapped.neighborhood.tolist(),['Vila Mariana'])
        self.assertEqual(missing,['Não Existe'])
        with self.assertRaisesRegex(ValueError,'limites geográficos'):
            build_district_map(self.df.head(1),{'type':'FeatureCollection','features':[]})

    def test_map_selection_and_toggle(self):
        names=self.df.neighborhood.tolist()
        self.assertEqual(district_from_map_selection([{'location':'Vila Mariana'}],names),'Vila Mariana')
        self.assertIsNone(district_from_map_selection([{'location':'Moema'}],names))
        self.assertIsNone(toggle_district_detail('Pinheiros','Pinheiros'))
        self.assertEqual(toggle_district_detail('Pinheiros','Vila Mariana'),'Vila Mariana')
        self.assertEqual(toggle_district_detail('Pinheiros',None),'Pinheiros')
        fig=build_district_map(self.df,self.boundaries,selectable=True)
        self.assertEqual(fig.layout.clickmode,'event+select')

    def test_selected_ranking(self):
        df=self.df.sort_values('priority_score',ascending=False)
        selected=selected_district_ranking(df,['Pinheiros'])
        self.assertEqual(selected.neighborhood.tolist(),['Pinheiros'])

if __name__=='__main__':unittest.main()
