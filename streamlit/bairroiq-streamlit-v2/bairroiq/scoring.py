"""Pontuação de distritos no Atlas Sampa / BairroIQ.

Há dois contratos de entrada:

* `sample_data.py`: demonstração histórica da interface, com indicadores
  ilustrativos que não são utilizados para classificar o Consumer V2.
* `consumer_v2.py`: snapshot V2 real e auditado com verde/lazer, segurança,
  mobilidade e serviços públicos. Empregos e densidade são descritivos, não
  influenciam a pontuação personalizada V2.

Os pesos V2 adotam as chaves já utilizadas nas páginas da Laís:
`trees` (verde e lazer), `safety`, `mobility` e `infrastructure`
(serviços públicos). As antigas chaves `jobs` e `budget` não entram no
ranking V2 e serão retiradas dos controles durante a etapa visual.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import pandas as pd


_REQUIRED_COLUMNS = {
    "neighborhood",
    "latitude",
    "longitude",
    "formal_jobs_score",
    "mobility_score",
}
_REAL_INDICATORS = (
    "green_leisure_score",
    "safety_score",
    "mobility_score",
    "public_services_score",
)

# Metadados para a apresentação das prioridades, em sua ordem de exibição.
_SCENARIO_DIMENSIONS_REAL = (
    ("trees", "Verde e lazer", "green_leisure_score"),
    ("safety", "Segurança", "safety_score"),
    ("mobility", "Mobilidade", "mobility_score"),
    ("infrastructure", "Serviços públicos", "public_services_score"),
)
_SCENARIO_DIMENSIONS_SAMPLE = (
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
    """Calcula rankings e interpreta o cenário mantendo a API da interface."""

    @staticmethod
    def _is_real_contract(metrics: pd.DataFrame) -> bool:
        # Não converter um dataframe de dados reais incompleto para 'sample'.
        markers = {"perfil_id", "cluster", "snapshot_id", "public_services_score",
                   "green_leisure_score"}
        return bool(markers.intersection(metrics.columns))

    @classmethod
    def _dimensions(cls, metrics: pd.DataFrame):
        return (
            _SCENARIO_DIMENSIONS_REAL
            if cls._is_real_contract(metrics)
            else _SCENARIO_DIMENSIONS_SAMPLE
        )

    def score_neighborhoods(
        self, metrics: pd.DataFrame, weights: Mapping[str, int | float]
    ) -> pd.DataFrame:
        missing = _REQUIRED_COLUMNS.difference(metrics.columns)
        if missing:
            names = ", ".join(sorted(missing))
            raise ValueError(f"A tabela de bairros não contém as colunas: {names}.")
        if metrics.empty:
            raise ValueError("Não há distritos para classificar.")

        scored = metrics.copy()
        real = self._is_real_contract(scored)
        if real:
            missing_real = set(_REAL_INDICATORS).difference(scored.columns)
            if missing_real:
                raise ValueError(
                    "Consumer V2 sem indicadores obrigatórios: "
                    + ", ".join(sorted(missing_real))
                )
            for column in _REAL_INDICATORS:
                scored[column] = pd.to_numeric(scored[column], errors="coerce")
                if scored[column].isna().any() or not scored[column].between(0, 100).all():
                    raise ValueError(f"Indicador V2 nulo ou fora de 0–100: {column}")
            # Importante: segurança vem do Consumer, não de fórmula baseada em roubos.
        else:
            for column in ("lighting_led", "trees_score", "affordability_score"):
                if column not in scored:
                    scored[column] = float("nan")

            if "safety_score" in scored:
                supplied = pd.to_numeric(scored["safety_score"], errors="coerce")
            else:
                supplied = pd.Series(float("nan"), index=scored.index)
            if supplied.isna().any():
                if "robbery_index" not in scored:
                    raise ValueError("Demonstração sem safety_score ou robbery_index.")
                robbery = pd.to_numeric(scored["robbery_index"], errors="coerce")
                derived = (100 - robbery * 10).clip(0, 100)
                supplied = supplied.fillna(derived)
            scored["safety_score"] = supplied

        dimensions = self._dimensions(scored)
        active = [
            (key, column, float(weights.get(key, 0)))
            for key, _label, column in dimensions
            if float(weights.get(key, 0)) > 0
            and pd.to_numeric(scored[column], errors="coerce").notna().any()
        ]
        if not active:
            raise ValueError("Escolha ao menos uma prioridade com peso maior que zero.")

        weighted_scores = pd.Series(0.0, index=scored.index)
        row_weights = pd.Series(0.0, index=scored.index)
        for _key, column, weight in active:
            values = pd.to_numeric(scored[column], errors="coerce")
            weighted_scores += values.fillna(0) * weight
            row_weights += values.notna().astype(float) * weight

        scored["priority_score"] = weighted_scores.div(
            row_weights.where(row_weights > 0)
        )
        if real and scored["priority_score"].isna().any():
            raise ValueError("Consumer V2 gerou prioridade nula.")
        return scored.sort_values(
            "priority_score", ascending=False, kind="stable"
        ).reset_index(drop=True)

    def build_scenario_insight(
        self,
        scored_neighborhoods: pd.DataFrame,
        weights: Mapping[str, int | float],
        selected_names: list[str] | None = None,
    ) -> ScenarioInsight:
        if scored_neighborhoods.empty:
            raise ValueError("Não há distritos para interpretar.")
        compared = scored_neighborhoods
        if selected_names:
            selected = scored_neighborhoods[
                scored_neighborhoods["neighborhood"].isin(selected_names)
            ]
            if not selected.empty:
                compared = selected

        leader = compared.sort_values("priority_score", ascending=False).iloc[0]
        dimensions = self._dimensions(compared)
        active_dimensions = [
            dimension
            for dimension in dimensions
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

        dominant = max(
            active_dimensions, key=lambda dimension: float(weights[dimension[0]])
        )
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
