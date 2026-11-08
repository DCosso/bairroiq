import unittest

import pandas as pd

from bairroiq.map_data import (
    DistrictMapService,
    build_district_map,
    district_from_map_selection,
    filter_districts,
    load_district_boundaries,
    restrict_to_mapped_districts,
    selected_district_ranking,
    toggle_district_detail,
)
from bairroiq.sample_data import SampleDataProvider
from bairroiq.scoring import SCENARIO_SCORER


class DistrictMapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scorer = SCENARIO_SCORER

    def test_map_service_composes_filter_boundaries_and_map(self) -> None:
        metrics = SampleDataProvider().load_metrics()
        scored = self.scorer.score_neighborhoods(
            metrics, {"trees": 70, "safety": 70, "mobility": 60, "budget": 45}
        )
        service = DistrictMapService()

        visible = service.filter_districts(
            scored, ["Vila Mariana"], "", []
        )
        mapped, missing = service.restrict_to_mapped_districts(visible)
        figure = service.build_map(mapped)

        self.assertEqual(mapped["neighborhood"].tolist(), ["Vila Mariana"])
        self.assertEqual(missing, [])
        self.assertEqual(list(figure.data[0].locations), ["Vila Mariana"])

    def test_selected_districts_and_filters_control_map_results(self) -> None:
        metrics = SampleDataProvider().load_metrics()
        scored = self.scorer.score_neighborhoods(
            metrics, {"trees": 70, "safety": 70, "mobility": 60, "budget": 45}
        )
        selected = ["Pinheiros", "Vila Mariana"]

        visible = filter_districts(scored, selected, "", [])
        safe = filter_districts(scored, selected, "", ["Segurança"])

        self.assertEqual(set(visible["neighborhood"]), set(selected))
        self.assertEqual(safe["neighborhood"].tolist(), ["Vila Mariana"])

    def test_natural_language_search_combines_indicator_preferences(self) -> None:
        metrics = SampleDataProvider().load_metrics()
        scored = self.scorer.score_neighborhoods(
            metrics, {"trees": 70, "safety": 70, "mobility": 60, "budget": 45}
        )

        visible = filter_districts(
            scored,
            metrics["neighborhood"].tolist(),
            "Bairro seguro perto de metrô e parques",
            [],
        )

        self.assertEqual(
            set(visible["neighborhood"]), {"Vila Mariana", "Moema"}
        )

    def test_map_contains_only_the_selected_district_polygons(self) -> None:
        metrics = SampleDataProvider().load_metrics()
        scored = self.scorer.score_neighborhoods(
            metrics, {"trees": 70, "safety": 70, "mobility": 60, "budget": 45}
        )
        selected_names = ["Pinheiros", "Vila Mariana"]
        selected = scored[scored["neighborhood"].isin(selected_names)]

        figure = build_district_map(selected, load_district_boundaries())

        self.assertEqual(len(figure.data), 1)
        trace = figure.data[0]
        self.assertEqual(set(trace.locations), set(selected_names))
        self.assertEqual(
            {
                feature["properties"]["neighborhood"]
                for feature in trace.geojson["features"]
            },
            set(selected_names),
        )
        self.assertIsNone(trace.marker.opacity)
        self.assertEqual(trace.marker.line.width, 0)
        self.assertEqual(trace.marker.line.color, "rgba(0,0,0,0)")
        self.assertIn("Arborização", trace.hovertemplate)
        self.assertIn("Mobilidade", trace.hovertemplate)
        self.assertIn("Orçamento", trace.hovertemplate)

    def test_demo_boundaries_contain_all_seven_districts(self) -> None:
        boundaries = load_district_boundaries()
        names = {
            feature["properties"]["neighborhood"] for feature in boundaries["features"]
        }

        self.assertEqual(
            names,
            {
                "Vila Mariana",
                "Pinheiros",
                "Moema",
                "Itaim Bibi",
                "Perdizes",
                "Santana",
                "Sé",
            },
        )
        self.assertTrue(
            all(
                feature["geometry"]["type"] == "MultiPolygon"
                for feature in boundaries["features"]
            )
        )

    def test_mock_neighborhoods_use_explicitly_illustrative_boundaries(self) -> None:
        metrics = SampleDataProvider().load_metrics()
        scored = self.scorer.score_neighborhoods(
            metrics, {"trees": 70, "safety": 70, "mobility": 60, "budget": 45}
        )

        figure = build_district_map(scored, load_district_boundaries())

        self.assertEqual(len(figure.data[0].locations), 10)
        illustrative = [
            feature
            for feature in figure.data[0].geojson["features"]
            if feature["properties"].get("illustrative")
        ]
        self.assertEqual(
            {feature["properties"]["neighborhood"] for feature in illustrative},
            {"Butantã", "Lapa", "Tatuapé"},
        )
        self.assertTrue(
            all(feature["geometry"]["type"] == "Polygon" for feature in illustrative)
        )

    def test_map_reports_missing_district_boundaries(self) -> None:
        selected = SampleDataProvider().load_metrics().head(1).copy()
        selected["priority_score"] = 80

        with self.assertRaisesRegex(ValueError, "limites geográficos"):
            build_district_map(selected, {"type": "FeatureCollection", "features": []})

    def test_map_filter_reports_districts_without_boundary_data(self) -> None:
        neighborhoods = pd.DataFrame(
            {"neighborhood": ["Vila Mariana", "Distrito sem polígono"]}
        )

        mapped, missing = restrict_to_mapped_districts(
            neighborhoods, load_district_boundaries()
        )

        self.assertEqual(mapped["neighborhood"].tolist(), ["Vila Mariana"])
        self.assertEqual(missing, ["Distrito sem polígono"])

    def test_map_base_style_follows_the_selected_theme(self) -> None:
        metrics = SampleDataProvider().load_metrics()
        scored = self.scorer.score_neighborhoods(
            metrics, {"trees": 70, "safety": 70, "mobility": 60, "budget": 45}
        )
        boundaries = load_district_boundaries()

        light_map = build_district_map(scored.head(1), boundaries, theme="light")
        dark_map = build_district_map(scored.head(1), boundaries, theme="dark")

        self.assertEqual(light_map.layout.map.style, "carto-voyager")
        self.assertEqual(dark_map.layout.map.style, "carto-darkmatter")
        self.assertEqual(
            light_map.data[0].colorscale[0][1], "rgba(26, 54, 93, 0.1)"
        )
        self.assertEqual(
            dark_map.data[0].colorscale[0][1], "rgba(255, 255, 255, 0.45)"
        )

    def test_map_selection_identifies_only_a_visible_neighborhood(self) -> None:
        self.assertEqual(
            district_from_map_selection(
                [{"location": "Vila Mariana", "point_number": 0}],
                ["Vila Mariana", "Pinheiros"],
            ),
            "Vila Mariana",
        )
        self.assertIsNone(
            district_from_map_selection(
                [{"location": "Moema", "point_number": 0}],
                ["Vila Mariana", "Pinheiros"],
            )
        )
        self.assertIsNone(district_from_map_selection([], ["Vila Mariana"]))

    def test_clicking_active_district_toggles_its_summary(self) -> None:
        self.assertIsNone(toggle_district_detail("Pinheiros", "Pinheiros"))
        self.assertEqual(
            toggle_district_detail("Pinheiros", "Vila Mariana"), "Vila Mariana"
        )
        self.assertEqual(toggle_district_detail("Pinheiros", None), "Pinheiros")

    def test_selectable_map_enables_polygon_click_selection(self) -> None:
        metrics = SampleDataProvider().load_metrics()
        scored = self.scorer.score_neighborhoods(
            metrics, {"trees": 70, "safety": 70, "mobility": 60, "budget": 45}
        )

        figure = build_district_map(
            scored.head(1), load_district_boundaries(), selectable=True
        )

        self.assertEqual(figure.layout.clickmode, "event+select")

    def test_ranking_contains_only_user_selected_districts(self) -> None:
        metrics = SampleDataProvider().load_metrics()
        scored = self.scorer.score_neighborhoods(
            metrics, {"trees": 70, "safety": 70, "mobility": 60, "budget": 45}
        )

        ranking = selected_district_ranking(scored, ["Pinheiros", "Vila Mariana"])

        self.assertEqual(
            set(ranking["neighborhood"]), {"Pinheiros", "Vila Mariana"}
        )
        self.assertTrue(ranking["priority_score"].is_monotonic_decreasing)


if __name__ == "__main__":
    unittest.main()
