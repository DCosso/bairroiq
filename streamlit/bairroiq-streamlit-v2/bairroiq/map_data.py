"""Mapa territorial BairroIQ.

Mantém a interface de mapas da Laís. Para o Consumer V2, regiões sem
polígonos cadastrados são representadas por *centroides reais* (pontos),
sem inventar contornos ou omitir distritos. O GeoJSON original é intocado.
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from bairroiq.ux_labels import nome_perfil


_BOUNDARIES_FILE = Path(__file__).with_name("district_boundaries.geojson")
_MAP_CENTER = {"lat": -23.56, "lon": -46.65}
DISTRICT_FILTERS = {
    "Empregos": ("formal_jobs_score", 75),
    "Segurança": ("safety_score", 75),
    "Mobilidade": ("mobility_score", 75),
    "Verde e lazer": ("green_leisure_score", 75),
    "Serviços públicos": ("public_services_score", 75),
}
_SEARCH_INTENTS_REAL = {
    "safety_score": (("seguro", "segura", "seguranca"), 75),
    "mobility_score": (("metro", "mobilidade", "transporte", "trem", "onibus"), 75),
    "green_leisure_score": (("parque", "parques", "verde", "praca", "pracas", "lazer"), 75),
    "public_services_score": (("escola", "escolas", "ubs", "servicos", "saude"), 75),
    "formal_jobs_score": (("emprego", "empregos", "oportunidades", "trabalho"), 75),
}
_SEARCH_INTENTS_SAMPLE = {
    "safety_score": (("seguro", "segura", "seguranca"), 75),
    "mobility_score": (("metro", "mobilidade", "transporte"), 75),
    "trees_score": (("parque", "parques", "verde", "arborizacao"), 75),
    "formal_jobs_score": (("emprego", "empregos", "oportunidades"), 75),
    "affordability_score": (("barato", "barata", "custo", "economico"), 70),
    "lighting_led": (("iluminacao", "led", "iluminado"), 80),
}


def _real_v2(df: pd.DataFrame) -> bool:
    return {"green_leisure_score", "public_services_score", "densidade_hab_km2"}.issubset(df.columns)


@st.cache_data
def load_district_boundaries() -> dict[str, Any]:
    return json.loads(_BOUNDARIES_FILE.read_text(encoding="utf-8"))


def _normalize_search(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    unaccented = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", unaccented).strip()


def filter_districts(
    neighborhoods: pd.DataFrame,
    selected_names: list[str],
    search: str,
    quick_filters: list[str],
) -> pd.DataFrame:
    """Mantém a busca e os filtros originais, com vocabulário V2 quando real."""
    visible = neighborhoods[neighborhoods["neighborhood"].isin(selected_names)].copy()
    if search.strip():
        normalized_search = _normalize_search(search)
        # A busca sugerida por estilo deve filtrar pelo estilo real, e não
        # por uma palavra incidental como "transporte".
        profile_names = set()
        if _real_v2(neighborhoods) and "cluster" in neighborhoods.columns:
            profile_names = set(neighborhoods["cluster"].map(nome_perfil).map(_normalize_search))
        if normalized_search in profile_names:
            visible = visible[
                visible["cluster"].map(nome_perfil).map(_normalize_search) == normalized_search
            ]
        else:
            intents = _SEARCH_INTENTS_REAL if _real_v2(neighborhoods) else _SEARCH_INTENTS_SAMPLE
            matched_intents = [
                (column, minimum)
                for column, (keywords, minimum) in intents.items()
                if any(keyword in normalized_search.split() for keyword in keywords)
            ]
            matched_neighborhoods = [
                name for name in neighborhoods["neighborhood"].unique()
                if f" {_normalize_search(str(name))} " in f" {normalized_search} "
            ]
            if matched_neighborhoods:
                visible = visible[visible["neighborhood"].isin(matched_neighborhoods)]
            elif not matched_intents:
                visible = visible[
                    visible["neighborhood"].str.contains(search.strip(), case=False, na=False, regex=False)
                ]
            for column, minimum in matched_intents:
                visible = visible[visible[column] >= minimum]
    for filter_name in quick_filters:
        if filter_name not in DISTRICT_FILTERS:
            # Um filtro antigo pode permanecer na sessão depois da atualização.
            continue
        column, minimum = DISTRICT_FILTERS[filter_name]
        if column in visible.columns:
            visible = visible[visible[column] >= minimum]
    return visible


def selected_district_ranking(
    scored_neighborhoods: pd.DataFrame, selected_names: list[str]
) -> pd.DataFrame:
    return scored_neighborhoods[
        scored_neighborhoods["neighborhood"].isin(selected_names)
    ].copy()


def restrict_to_mapped_districts(
    neighborhoods: pd.DataFrame, boundaries: dict[str, Any]
) -> tuple[pd.DataFrame, list[str]]:
    """V2: todos os distritos, com pontos se faltar polígono.

    Sample: conserva o comportamento original das geometrias demonstrativas.
    """
    if _real_v2(neighborhoods):
        return neighborhoods.copy(), []
    boundary_names = {
        feature["properties"]["neighborhood"]
        for feature in boundaries.get("features", [])
    }
    if "illustrative_boundary" in neighborhoods:
        illustrative_names = set(neighborhoods.loc[
            neighborhoods["illustrative_boundary"].fillna(False).astype(bool),
            "neighborhood",
        ])
    else:
        illustrative_names = set()
    available_names = boundary_names | illustrative_names
    names = neighborhoods["neighborhood"].astype(str)
    mapped = neighborhoods[names.isin(available_names)].copy()
    missing = sorted(set(names).difference(available_names))
    return mapped, missing


def district_from_map_selection(
    points: list[dict[str, Any]], visible_names: list[str]
) -> str | None:
    """Reconhece seleção de polígonos (location) ou pontos (customdata)."""
    for point in reversed(points):
        candidate = point.get("location")
        if not isinstance(candidate, str):
            data = point.get("customdata")
            candidate = data[0] if isinstance(data, (tuple, list)) and data else data
        if not isinstance(candidate, str):
            candidate = point.get("text")
        if isinstance(candidate, str) and candidate in visible_names:
            return candidate
    return None


def toggle_district_detail(active_district: str | None, clicked_district: str | None) -> str | None:
    if clicked_district is None:
        return active_district
    return None if active_district == clicked_district else clicked_district


def _positions(coordinates: Any) -> Iterator[tuple[float, float]]:
    if (
        isinstance(coordinates, (list, tuple))
        and len(coordinates) >= 2
        and isinstance(coordinates[0], (int, float))
        and isinstance(coordinates[1], (int, float))
    ):
        yield float(coordinates[0]), float(coordinates[1])
        return
    if isinstance(coordinates, (list, tuple)):
        for item in coordinates:
            yield from _positions(item)


def _map_view(features: list[dict[str, Any]]) -> tuple[dict[str, float], float]:
    coords = [pos for feature in features for pos in _positions(feature["geometry"]["coordinates"])]
    if not coords:
        return _MAP_CENTER, 9.5
    longitudes, latitudes = zip(*coords)
    min_lon, max_lon = min(longitudes), max(longitudes)
    min_lat, max_lat = min(latitudes), max(latitudes)
    center = {"lon": (min_lon + max_lon) / 2, "lat": (min_lat + max_lat) / 2}
    longitude_span = (max_lon - min_lon) * math.cos(math.radians(center["lat"]))
    latitude_span = max_lat - min_lat
    span = max(longitude_span, latitude_span, 0.012)
    zoom = min(12.2, max(9.0, math.log2(360 / (span * 1.75))))
    return center, zoom


def _points_view(frame: pd.DataFrame) -> tuple[dict[str, float], float]:
    if frame.empty:
        return _MAP_CENTER, 9.5
    min_lat, max_lat = frame["latitude"].min(), frame["latitude"].max()
    min_lon, max_lon = frame["longitude"].min(), frame["longitude"].max()
    center = {"lat": float((min_lat + max_lat) / 2), "lon": float((min_lon + max_lon) / 2)}
    lon_span = (max_lon - min_lon) * math.cos(math.radians(center["lat"]))
    span = max(float(max_lat - min_lat), float(lon_span), .015)
    return center, min(12.2, max(9.0, math.log2(360 / (span * 1.75))))


def _illustrative_boundary(row: pd.Series) -> dict[str, Any]:
    latitude = float(row["latitude"])
    longitude = float(row["longitude"])
    half_width, half_height = .004, .003
    ring = [
        [longitude - half_width, latitude - half_height],
        [longitude + half_width, latitude - half_height],
        [longitude + half_width, latitude + half_height],
        [longitude - half_width, latitude + half_height],
        [longitude - half_width, latitude - half_height],
    ]
    return {"type": "Feature", "properties": {"neighborhood": str(row["neighborhood"]), "illustrative": True}, "geometry": {"type": "Polygon", "coordinates": [ring]}}


def build_district_map(
    visible_neighborhoods: pd.DataFrame,
    boundaries: dict[str, Any],
    theme: str = "light",
    selectable: bool = False,
) -> go.Figure:
    """Polígonos existentes + centroides reais para os demais distritos V2."""
    real = _real_v2(visible_neighborhoods)
    visible_names = visible_neighborhoods["neighborhood"].tolist()
    features_by_name = {
        feature["properties"]["neighborhood"]: feature
        for feature in boundaries.get("features", [])
    }
    for _, row in visible_neighborhoods.iterrows():
        name = str(row["neighborhood"])
        illustrative = row.get("illustrative_boundary", False)
        if not real and name not in features_by_name and pd.notna(illustrative) and bool(illustrative):
            features_by_name[name] = _illustrative_boundary(row)
    missing = set(visible_names).difference(features_by_name)
    if missing and not real:
        names = ", ".join(sorted(missing))
        raise ValueError(f"Não há limites geográficos cadastrados para: {names}.")

    polygon_rows = visible_neighborhoods[
        visible_neighborhoods["neighborhood"].isin(features_by_name)
    ].copy()
    if real and not polygon_rows.empty:
        polygon_rows["nome_perfil_publico"] = polygon_rows["cluster"].map(nome_perfil)
    selected_features = [features_by_name[name] for name in polygon_rows["neighborhood"]]
    figure = go.Figure()

    if not polygon_rows.empty:
        fill_opacity = (
            (0.84 if theme == "light" else 0.76)
            if real else (0.1 if theme == "light" else 0.45)
        )
        if real:
            custom_columns = [
                "formal_jobs_score", "safety_score", "robberies_per_1000",
                "green_leisure_score", "mobility_score", "public_services_score",
                "densidade_hab_km2", "nome_perfil_publico",
            ]
            hover = (
                "<b>%{location}</b><br>"
                "Combina com suas escolhas: %{z:.1f}/100<br>"
                "Empregos formais: %{customdata[0]:.1f}/100<br>"
                "Segurança: %{customdata[1]:.1f}/100<br>"
                "Roubos: %{customdata[2]:.2f} por 1.000 hab.<br>"
                "Verde e lazer: %{customdata[3]:.1f}/100<br>"
                "Mobilidade: %{customdata[4]:.1f}/100<br>"
                "Serviços públicos: %{customdata[5]:.1f}/100<br>"
                "Densidade: %{customdata[6]:.0f} hab./km²<br>"
                "Estilo da região: %{customdata[7]}<extra></extra>"
            )
        else:
            custom_columns = [
                "formal_jobs_score", "safety_score", "robbery_index", "lighting_led",
                "trees_score", "mobility_score", "affordability_score",
            ]
            hover = (
                "<b>%{location}</b><br>Aderência: %{z:.1f}/100<br>"
                "Empregos formais: %{customdata[0]:.1f}<br>"
                "Segurança: %{customdata[1]:.1f}<br>"
                "Índice de roubos: %{customdata[2]:.1f}<br>"
                "Iluminação LED: %{customdata[3]:.1f}<br>"
                "Arborização: %{customdata[4]:.1f}<br>"
                "Mobilidade: %{customdata[5]:.1f}<br>"
                "Orçamento: %{customdata[6]:.1f}<extra></extra>"
            )
        figure.add_trace(go.Choroplethmap(
            geojson={"type": "FeatureCollection", "features": selected_features},
            locations=polygon_rows["neighborhood"].tolist(),
            z=polygon_rows["priority_score"],
            customdata=polygon_rows[custom_columns].to_numpy(),
            featureidkey="properties.neighborhood",
            colorscale=(
                [[0, f"rgba(209, 80, 89, {fill_opacity})"],
                 [0.5, f"rgba(241, 192, 86, {fill_opacity})"],
                 [1, f"rgba(36, 159, 115, {fill_opacity})"]]
                if real else [
                    [0, f"rgba(26, 54, 93, {fill_opacity})" if theme == "light"
                     else f"rgba(255, 255, 255, {fill_opacity})"],
                    [1, f"rgba(26, 54, 93, {fill_opacity})" if theme == "light"
                     else f"rgba(255, 255, 255, {fill_opacity})"],
                ]
            ),
            zmin=0, zmax=100, showscale=real,
            colorbar={"title": {"text": "Afinidade"}, "x": 0.015,
                      "y": 0.40, "len": 0.55, "thickness": 12,
                      "tickvals": [0, 50, 100], "outlinewidth": 0,
                      "tickfont": {"size": 10}} if real else None,
            marker={"line": {"color": "rgba(255,255,255,0.35)" if real else "rgba(0,0,0,0)",
                             "width": 0.6 if real else 0}},
            hovertemplate=hover,
            name="Distritos com polígonos",
        ))

    if real:
        centroid_rows = visible_neighborhoods[
            ~visible_neighborhoods["neighborhood"].isin(features_by_name)
        ].copy()
        if not centroid_rows.empty:
            centroid_rows["nome_perfil_publico"] = centroid_rows["cluster"].map(nome_perfil)
            columns = [
                "neighborhood", "formal_jobs_score", "safety_score", "robberies_per_1000",
                "green_leisure_score", "mobility_score", "public_services_score",
                "densidade_hab_km2", "nome_perfil_publico", "priority_score",
            ]
            figure.add_trace(go.Scattermap(
                lat=centroid_rows["latitude"], lon=centroid_rows["longitude"],
                mode="markers", text=centroid_rows["neighborhood"],
                customdata=centroid_rows[columns].to_numpy(),
                marker={"size": 12, "color": centroid_rows["priority_score"],
                        "colorscale": "Viridis", "cmin": 0, "cmax": 100,
                        "showscale": False, "opacity": .9},
                hovertemplate=(
                    "<b>%{customdata[0]}</b> · localização do distrito<br>"
                    "Combina com suas escolhas: %{customdata[9]:.1f}/100<br>"
                    "Empregos: %{customdata[1]:.1f}/100<br>"
                    "Segurança: %{customdata[2]:.1f}/100<br>"
                    "Roubos: %{customdata[3]:.2f} por 1.000 hab.<br>"
                    "Verde e lazer: %{customdata[4]:.1f}/100<br>"
                    "Mobilidade: %{customdata[5]:.1f}/100<br>"
                    "Serviços públicos: %{customdata[6]:.1f}/100<br>"
                    "Densidade: %{customdata[7]:.0f} hab./km²<br>"
                    "Estilo da região: %{customdata[8]}<br>"
                    "Localização aproximada da região"
                    "<extra></extra>"
                ),
                name="Centroides distritais",
            ))
        center, zoom = _points_view(visible_neighborhoods)
    elif selected_features:
        center, zoom = _map_view(selected_features)
    else:
        center, zoom = _MAP_CENTER, 9.5

    style = "carto-darkmatter" if theme == "dark" else "carto-voyager"
    background = "#0b1220" if theme == "dark" else "#dce7ef"
    figure.update_layout(
        map={"style": style, "center": center, "zoom": zoom},
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        paper_bgcolor=background, plot_bgcolor=background,
        showlegend=False, autosize=True,
        clickmode="event+select" if selectable else "event",
    )
    return figure


class DistrictMapService:
    """Reúne limites, filtros e interações usados nas telas de mapa."""

    def __init__(self, boundaries: dict[str, Any] | None = None) -> None:
        self._boundaries = load_district_boundaries() if boundaries is None else boundaries

    @staticmethod
    def zone_for_neighborhood(row: pd.Series) -> str:
        latitude, longitude = float(row["latitude"]), float(row["longitude"])
        if latitude >= -23.54:
            return "Norte"
        if latitude <= -23.58:
            return "Sul"
        if longitude <= -46.68:
            return "Oeste"
        if longitude >= -46.64:
            return "Leste"
        return "Centro"

    def filter_districts(self, neighborhoods: pd.DataFrame, selected_names: list[str], search: str, quick_filters: list[str]) -> pd.DataFrame:
        return filter_districts(neighborhoods, selected_names, search, quick_filters)

    def selected_district_ranking(self, scored_neighborhoods: pd.DataFrame, selected_names: list[str]) -> pd.DataFrame:
        return selected_district_ranking(scored_neighborhoods, selected_names)

    def restrict_to_mapped_districts(self, neighborhoods: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
        return restrict_to_mapped_districts(neighborhoods, self._boundaries)

    def build_map(self, visible_neighborhoods: pd.DataFrame, theme: str = "light", selectable: bool = False) -> go.Figure:
        return build_district_map(visible_neighborhoods, self._boundaries, theme=theme, selectable=selectable)

    @staticmethod
    def district_from_selection(points: list[dict[str, Any]], visible_names: list[str]) -> str | None:
        return district_from_map_selection(points, visible_names)

    @staticmethod
    def toggle_district_detail(active_district: str | None, clicked_district: str | None) -> str | None:
        return toggle_district_detail(active_district, clicked_district)
