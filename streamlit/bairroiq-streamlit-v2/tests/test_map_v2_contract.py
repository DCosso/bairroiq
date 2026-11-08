"""Testes offline da compatibilidade territorial V2.

Usa somente dados sintéticos: não solicita credenciais e não distribui a Gold.
"""
from __future__ import annotations

import unittest

import pandas as pd

from bairroiq.map_data import (
    DISTRICT_FILTERS,
    build_district_map,
    district_from_map_selection,
    filter_districts,
    restrict_to_mapped_districts,
)


def synthetic_v2() -> pd.DataFrame:
    rows = []
    for index in range(96):
        rows.append({
            "neighborhood": f"Distrito de teste {index+1:02d}",
            "latitude": -23.4 - index / 1000,
            "longitude": -46.4 - index / 1000,
            "formal_jobs_score": float(index + 1),
            "safety_score": float(95 - index * .5),
            "mobility_score": float(index),
            "green_leisure_score": float(index),
            "public_services_score": float(95 - index),
            "densidade_hab_km2": float(1000 + index * 100),
            "robberies_per_1000": 2.5,
            "perfil_id": f"kmeans-k09-p{index % 9 + 1:02d}",
            "cluster": f"P{index % 9 + 1:02d} — Perfil sintético",
            "priority_score": 58.0,
        })
    return pd.DataFrame(rows)


def two_polygons(df: pd.DataFrame) -> dict:
    features = []
    for i in range(2):
        lon, lat = df.iloc[i][["longitude", "latitude"]]
        features.append({
            "type": "Feature", "properties": {"neighborhood": df.iloc[i]["neighborhood"]},
            "geometry": {"type": "Polygon", "coordinates": [[
                [lon-.001, lat-.001], [lon+.001, lat-.001],
                [lon+.001, lat+.001], [lon-.001, lat+.001],
                [lon-.001, lat-.001]
            ]]},
        })
    return {"type": "FeatureCollection", "features": features}


class TestMapV2Contract(unittest.TestCase):
    def setUp(self) -> None:
        self.df = synthetic_v2()

    def test_96_districts_displayed_without_creating_geometries(self) -> None:
        empty = {"type": "FeatureCollection", "features": []}
        visible, missing = restrict_to_mapped_districts(self.df, empty)
        self.assertEqual(len(visible), 96)
        self.assertEqual(missing, [])
        figure = build_district_map(visible, empty)
        self.assertEqual(len(figure.data), 1)
        self.assertEqual(figure.data[0].type, "scattermap")
        self.assertEqual(len(figure.data[0].lat), 96)
        self.assertNotIn("geojson", figure.data[0].to_plotly_json())

    def test_real_polygons_kept_and_rest_centroid_points(self) -> None:
        fig = build_district_map(self.df, two_polygons(self.df), selectable=True)
        self.assertEqual(len(fig.data), 2)
        self.assertEqual(fig.data[0].type, "choroplethmap")
        self.assertEqual(set(fig.data[0].locations), set(self.df.head(2).neighborhood))
        self.assertEqual(fig.data[1].type, "scattermap")
        self.assertEqual(len(fig.data[1].lat), 94)
        self.assertIn("Verde e lazer", fig.data[0].hovertemplate)
        self.assertIn("Serviços públicos", fig.data[1].hovertemplate)
        for trace in fig.data:
            self.assertNotIn("Orçamento", trace.hovertemplate)
            self.assertNotIn("Iluminação LED", trace.hovertemplate)
            self.assertNotIn("Arborização", trace.hovertemplate)
        self.assertEqual(fig.layout.clickmode, "event+select")

    def test_map_click_supports_centroid_and_polygon(self) -> None:
        names = self.df.neighborhood.tolist()
        self.assertEqual(district_from_map_selection([{"location": names[0]}], names), names[0])
        self.assertEqual(district_from_map_selection([{"customdata": [names[4], 40, 60]}], names), names[4])
        self.assertIsNone(district_from_map_selection([{"customdata": ["Outro distrito"]}], names))

    def test_quick_filters_use_real_v2_dimensions(self) -> None:
        self.assertEqual(DISTRICT_FILTERS["Verde e lazer"][0], "green_leisure_score")
        self.assertEqual(DISTRICT_FILTERS["Serviços públicos"][0], "public_services_score")
        self.assertNotIn("Iluminação LED", DISTRICT_FILTERS)
        selected = filter_districts(
            self.df, self.df.neighborhood.tolist(), "", ["Verde e lazer"]
        )
        self.assertEqual(len(selected), 21)

    def test_free_text_uses_real_fields_not_cost_or_led(self) -> None:
        matched = filter_districts(
            self.df, self.df.neighborhood.tolist(),
            "verde", [],
        )
        self.assertEqual(len(matched), 21)

    def test_sample_still_uses_original_boundary_rules(self) -> None:
        df = pd.DataFrame([{
            "neighborhood": "Bairro demonstração", "latitude": -23.55,
            "longitude": -46.65, "formal_jobs_score": 70.0,
            "safety_score": 88.0, "robbery_index": 1.2,
            "lighting_led": 80.0, "trees_score": 90.0,
            "mobility_score": 75.0, "affordability_score": 65.0,
            "priority_score": 75.0, "illustrative_boundary": True,
        }])
        visible, missing = restrict_to_mapped_districts(df, {"type":"FeatureCollection", "features": []})
        self.assertEqual(len(visible), 1)
        self.assertEqual(missing, [])
        fig = build_district_map(visible, {"type": "FeatureCollection", "features": []})
        self.assertEqual(fig.data[0].type, "choroplethmap")
        self.assertEqual(len(fig.data[0].locations), 1)
        self.assertIn("Arborização", fig.data[0].hovertemplate)


if __name__ == "__main__":
    unittest.main()
