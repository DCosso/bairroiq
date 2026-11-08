from __future__ import annotations

import pandas as pd


_NEIGHBORHOODS = [
    {
        "neighborhood": "Vila Mariana",
        "latitude": -23.5899,
        "longitude": -46.6345,
        "formal_jobs_score": 87.5,
        "robbery_index": 1.5,
        "lighting_led": 88.5,
        "trees_score": 78.0,
        "mobility_score": 86.0,
        "affordability_score": 69.0,
    },
    {
        "neighborhood": "Pinheiros",
        "latitude": -23.5667,
        "longitude": -46.7011,
        "formal_jobs_score": 92.0,
        "robbery_index": 3.5,
        "lighting_led": 82.0,
        "trees_score": 73.0,
        "mobility_score": 91.0,
        "affordability_score": 62.0,
    },
    {
        "neighborhood": "Moema",
        "latitude": -23.6039,
        "longitude": -46.6658,
        "formal_jobs_score": 80.0,
        "robbery_index": 2.1,
        "lighting_led": 91.0,
        "trees_score": 88.0,
        "mobility_score": 79.0,
        "affordability_score": 57.0,
    },
    {
        "neighborhood": "Itaim Bibi",
        "latitude": -23.5858,
        "longitude": -46.6815,
        "formal_jobs_score": 96.0,
        "robbery_index": 3.2,
        "lighting_led": 85.0,
        "trees_score": 66.0,
        "mobility_score": 87.0,
        "affordability_score": 45.0,
    },
    {
        "neighborhood": "Perdizes",
        "latitude": -23.5388,
        "longitude": -46.6745,
        "formal_jobs_score": 76.0,
        "robbery_index": 1.8,
        "lighting_led": 84.0,
        "trees_score": 90.0,
        "mobility_score": 72.0,
        "affordability_score": 71.0,
    },
    {
        "neighborhood": "Santana",
        "latitude": -23.5015,
        "longitude": -46.6250,
        "formal_jobs_score": 72.0,
        "robbery_index": 2.4,
        "lighting_led": 76.0,
        "trees_score": 80.0,
        "mobility_score": 74.0,
        "affordability_score": 78.0,
    },
    {
        "neighborhood": "Sé",
        "latitude": -23.5505,
        "longitude": -46.6333,
        "formal_jobs_score": 90.0,
        "robbery_index": 5.8,
        "lighting_led": 74.0,
        "trees_score": 41.0,
        "mobility_score": 80.0,
        "affordability_score": 84.0,
    },
    {
        "neighborhood": "Butantã",
        "latitude": -23.5717,
        "longitude": -46.7081,
        "formal_jobs_score": 74.0,
        "robbery_index": 2.2,
        "lighting_led": 78.0,
        "trees_score": 85.0,
        "mobility_score": 70.0,
        "affordability_score": 76.0,
        "illustrative_boundary": True,
    },
    {
        "neighborhood": "Lapa",
        "latitude": -23.5228,
        "longitude": -46.7011,
        "formal_jobs_score": 78.0,
        "robbery_index": 2.6,
        "lighting_led": 81.0,
        "trees_score": 75.0,
        "mobility_score": 83.0,
        "affordability_score": 73.0,
        "illustrative_boundary": True,
    },
    {
        "neighborhood": "Tatuapé",
        "latitude": -23.5400,
        "longitude": -46.5765,
        "formal_jobs_score": 82.0,
        "robbery_index": 2.8,
        "lighting_led": 86.0,
        "trees_score": 70.0,
        "mobility_score": 88.0,
        "affordability_score": 68.0,
        "illustrative_boundary": True,
    },
]

_GROWTH = {
    "Vila Mariana": (1.8, 2.4),
    "Pinheiros": (2.0, 1.7),
    "Moema": (1.4, 2.0),
    "Itaim Bibi": (2.4, 1.9),
    "Perdizes": (1.2, 1.6),
    "Santana": (1.0, 1.8),
    "Sé": (0.8, 1.4),
    "Butantã": (1.3, 1.9),
    "Lapa": (1.5, 2.1),
    "Tatuapé": (1.7, 2.0),
}


class SampleDataProvider:
    """Deterministic demo data with the same shape as the Databricks provider."""

    def load_metrics(self) -> pd.DataFrame:
        return pd.DataFrame(_NEIGHBORHOODS)

    def load_history(self) -> pd.DataFrame:
        metrics = self.load_metrics()
        rows: list[dict[str, str | int | float]] = []
        for neighborhood in metrics.to_dict(orient="records"):
            jobs_growth, lighting_growth = _GROWTH[neighborhood["neighborhood"]]
            for year in range(2020, 2026):
                elapsed = year - 2020
                rows.append(
                    {
                        "neighborhood": neighborhood["neighborhood"],
                        "year": year,
                        "formal_jobs_score": min(
                            100.0, neighborhood["formal_jobs_score"] - jobs_growth * (5 - elapsed)
                        ),
                        "lighting_led": min(
                            100.0, neighborhood["lighting_led"] - lighting_growth * (5 - elapsed)
                        ),
                        "safety_score": max(
                            0.0, 100.0 - neighborhood["robbery_index"] * 10 + elapsed * 0.7
                        ),
                    }
                )
        return pd.DataFrame(rows)
