from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import pandas as pd


_REQUIRED_COLUMNS = {
    "neighborhood",
    "latitude",
    "longitude",
    "formal_jobs_score",
    "robbery_index",
    "mobility_score",
}
_SCENARIO_DIMENSIONS = (
    ("trees", "Arborização", "trees_score"),
    ("safety", "Segurança", "safety_score"),
    ("mobility", "Mobilidade", "mobility_score"),
    ("infrastructure", "Infraestrutura e serviços", "lighting_led"),
    ("jobs", "Empregos e oportunidades", "formal_jobs_score"),
    ("budget", "Custo acessível", "affordability_score"),
)


@dataclass(frozen=True)
class ScenarioInsight:
    leader_name: str
    leader_score: float
    dominant_priority: str | None
    dominant_weight: int
    recommended_name: str | None
    recommended_score: float | None


class ScenarioScoringService:
    """Calcula a aderência dos distritos e interpreta o cenário escolhido."""

    def score_neighborhoods(
        self, metrics: pd.DataFrame, weights: Mapping[str, int | float]
    ) -> pd.DataFrame:
        missing_columns = _REQUIRED_COLUMNS.difference(metrics.columns)
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(f"A tabela de bairros não contém as colunas: {missing}.")

        scored = metrics.copy()
        for column in ("lighting_led", "trees_score", "affordability_score"):
            if column not in scored:
                scored[column] = float("nan")

        robbery_index = pd.to_numeric(scored["robbery_index"], errors="coerce")
        derived_safety = (100 - robbery_index * 10).clip(0, 100)
        if "safety_score" in scored:
            supplied_safety = pd.to_numeric(scored["safety_score"], errors="coerce")
            scored["safety_score"] = supplied_safety.fillna(derived_safety)
        else:
            scored["safety_score"] = derived_safety

        dimension_columns = {
            "trees": "trees_score",
            "safety": "safety_score",
            "mobility": "mobility_score",
            "infrastructure": "lighting_led",
            "jobs": "formal_jobs_score",
            "budget": "affordability_score",
        }
        available_weights = {
            key: float(weight)
            for key, weight in weights.items()
            if key in dimension_columns
            and weight > 0
            and pd.to_numeric(scored[dimension_columns[key]], errors="coerce")
            .notna()
            .any()
        }
        if not available_weights:
            raise ValueError("Escolha ao menos uma prioridade com peso maior que zero.")

        weighted_scores = pd.Series(0.0, index=scored.index)
        row_weights = pd.Series(0.0, index=scored.index)
        for key, weight in available_weights.items():
            values = pd.to_numeric(scored[dimension_columns[key]], errors="coerce")
            weighted_scores += values.fillna(0) * weight
            row_weights += values.notna().astype(float) * weight
        scored["priority_score"] = weighted_scores.div(
            row_weights.where(row_weights > 0)
        )
        return scored.sort_values("priority_score", ascending=False).reset_index(
            drop=True
        )

    def build_scenario_insight(
        self,
        scored_neighborhoods: pd.DataFrame,
        weights: Mapping[str, int | float],
        selected_names: list[str] | None = None,
    ) -> ScenarioInsight:
        compared = scored_neighborhoods
        if selected_names:
            selected = scored_neighborhoods[
                scored_neighborhoods["neighborhood"].isin(selected_names)
            ]
            if not selected.empty:
                compared = selected

        leader = compared.sort_values("priority_score", ascending=False).iloc[0]
        active_dimensions = [
            dimension
            for dimension in _SCENARIO_DIMENSIONS
            if weights.get(dimension[0], 0) > 0
            and dimension[2] in compared
            and pd.to_numeric(compared[dimension[2]], errors="coerce").notna().any()
        ]
        if not active_dimensions:
            return ScenarioInsight(
                leader_name=str(leader["neighborhood"]),
                leader_score=float(leader["priority_score"]),
                dominant_priority=None,
                dominant_weight=0,
                recommended_name=None,
                recommended_score=None,
            )

        dominant = max(active_dimensions, key=lambda dimension: weights[dimension[0]])
        lowest = compared.sort_values(dominant[2], ascending=True).iloc[0]
        return ScenarioInsight(
            leader_name=str(leader["neighborhood"]),
            leader_score=float(leader["priority_score"]),
            dominant_priority=dominant[1],
            dominant_weight=int(weights[dominant[0]]),
            recommended_name=str(lowest["neighborhood"]),
            recommended_score=float(lowest[dominant[2]]),
        )


SCENARIO_SCORER = ScenarioScoringService()
