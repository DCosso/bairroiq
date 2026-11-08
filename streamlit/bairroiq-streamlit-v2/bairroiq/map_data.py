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


_BOUNDARIES_FILE = Path(__file__).with_name("district_boundaries.geojson")
_MAP_CENTER = {"lat": -23.56, "lon": -46.65}
DISTRICT_FILTERS = {
    "Empregos": ("formal_jobs_score", 75),
    "Segurança": ("safety_score", 75),
    "Iluminação LED": ("lighting_led", 80),
}
_SEARCH_INTENTS = {
    "safety_score": (("seguro", "segura", "seguranca"), 75),
    "mobility_score": (("metro", "mobilidade", "transporte"), 75),
    "trees_score": (("parque", "parques", "verde", "arborizacao"), 75),
    "formal_jobs_score": (("emprego", "empregos", "oportunidades"), 75),
    "affordability_score": (("barato", "barata", "custo", "economico"), 70),
    "lighting_led": (("iluminacao", "led", "iluminado"), 80),
}
@st.cache_data
def load_district_boundaries() -> dict[str, Any]:
    return json.loads(_BOUNDARIES_FILE.read_text(encoding="utf-8"))


def filter_districts(
    neighborhoods: pd.DataFrame,
    selected_names: list[str],
    search: str,
    quick_filters: list[str],
) -> pd.DataFrame:
    visible = neighborhoods[neighborhoods["neighborhood"].isin(selected_names)].copy()
    if search.strip():
        normalized_search = _normalize_search(search)
        matched_intents = [
            (column, minimum)
            for column, (keywords, minimum) in _SEARCH_INTENTS.items()
            if any(keyword in normalized_search.split() for keyword in keywords)
        ]
        matched_neighborhoods = [
            name
            for name in neighborhoods["neighborhood"].unique()
            if f" {_normalize_search(str(name))} " in f" {normalized_search} "
        ]
        if matched_neighborhoods:
            visible = visible[visible["neighborhood"].isin(matched_neighborhoods)]
        elif not matched_intents:
            visible = visible[
                visible["neighborhood"].str.contains(search.strip(), case=False, na=False)
            ]
        for column, minimum in matched_intents:
            visible = visible[visible[column] >= minimum]
    for filter_name in quick_filters:
        column, minimum = DISTRICT_FILTERS[filter_name]
        visible = visible[visible[column] >= minimum]
    return visible


def _normalize_search(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    unaccented = "".join(character for character in normalized if not unicodedata.combining(character))
    return re.sub(r"[^a-z0-9]+", " ", unaccented).strip()


def selected_district_ranking(
    scored_neighborhoods: pd.DataFrame,
    selected_names: list[str],
) -> pd.DataFrame:
    return scored_neighborhoods[
        scored_neighborhoods["neighborhood"].isin(selected_names)
    ].copy()


def restrict_to_mapped_districts(
    neighborhoods: pd.DataFrame,
    boundaries: dict[str, Any],
) -> tuple[pd.DataFrame, list[str]]:
    """Keep map polygons that exist and report districts needing boundaries."""
    boundary_names = {
        feature["properties"]["neighborhood"]
        for feature in boundaries.get("features", [])
    }
    if "illustrative_boundary" in neighborhoods:
        illustrative_names = set(
            neighborhoods.loc[
                neighborhoods["illustrative_boundary"].fillna(False).astype(bool),
                "neighborhood",
            ]
        )
    else:
        illustrative_names = set()
    available_names = boundary_names | illustrative_names
    names = neighborhoods["neighborhood"].astype(str)
    mapped = neighborhoods[names.isin(available_names)].copy()
    missing = sorted(set(names).difference(available_names))
    return mapped, missing


def district_from_map_selection(
    points: list[dict[str, Any]],
    visible_names: list[str],
) -> str | None:
    if not points:
        return None
    neighborhood = points[-1].get("location")
    if isinstance(neighborhood, str) and neighborhood in visible_names:
        return neighborhood
    return None


def toggle_district_detail(
    active_district: str | None,
    clicked_district: str | None,
) -> str | None:
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
    coordinates = [
        position
        for feature in features
        for position in _positions(feature["geometry"]["coordinates"])
    ]
    if not coordinates:
        return _MAP_CENTER, 9.5

    longitudes, latitudes = zip(*coordinates)
    min_lon, max_lon = min(longitudes), max(longitudes)
    min_lat, max_lat = min(latitudes), max(latitudes)
    center = {
        "lon": (min_lon + max_lon) / 2,
        "lat": (min_lat + max_lat) / 2,
    }
    longitude_span = (max_lon - min_lon) * math.cos(math.radians(center["lat"]))
    latitude_span = max_lat - min_lat
    span = max(longitude_span, latitude_span, 0.012)
    zoom = min(12.2, max(9.0, math.log2(360 / (span * 1.75))))
    return center, zoom


def _illustrative_boundary(row: pd.Series) -> dict[str, Any]:
    latitude = float(row["latitude"])
    longitude = float(row["longitude"])
    half_width = 0.004
    half_height = 0.003
    ring = [
        [longitude - half_width, latitude - half_height],
        [longitude + half_width, latitude - half_height],
        [longitude + half_width, latitude + half_height],
        [longitude - half_width, latitude + half_height],
        [longitude - half_width, latitude - half_height],
    ]
    return {
        "type": "Feature",
        "properties": {
            "neighborhood": str(row["neighborhood"]),
            "illustrative": True,
        },
        "geometry": {"type": "Polygon", "coordinates": [ring]},
    }


def build_district_map(
    visible_neighborhoods: pd.DataFrame,
    boundaries: dict[str, Any],
    theme: str = "light",
    selectable: bool = False,
) -> go.Figure:
    visible_names = visible_neighborhoods["neighborhood"].tolist()
    features_by_name = {
        feature["properties"]["neighborhood"]: feature
        for feature in boundaries.get("features", [])
    }
    for _, row in visible_neighborhoods.iterrows():
        name = str(row["neighborhood"])
        illustrative_boundary = row.get("illustrative_boundary", False)
        if (
            name not in features_by_name
            and pd.notna(illustrative_boundary)
            and bool(illustrative_boundary)
        ):
            features_by_name[name] = _illustrative_boundary(row)
    missing = set(visible_names).difference(features_by_name)
    if missing:
        names = ", ".join(sorted(missing))
        raise ValueError(f"Não há limites geográficos cadastrados para: {names}.")

    selected_features = [features_by_name[name] for name in visible_names]
    figure = go.Figure()
    if visible_names:
        fill_opacity = 0.1 if theme == "light" else 0.45
        customdata = visible_neighborhoods[
            [
                "formal_jobs_score",
                "safety_score",
                "robbery_index",
                "lighting_led",
                "trees_score",
                "mobility_score",
                "affordability_score",
            ]
        ].to_numpy()
        figure.add_trace(
            go.Choroplethmap(
                geojson={
                    "type": "FeatureCollection",
                    "features": selected_features,
                },
                locations=visible_names,
                z=visible_neighborhoods["priority_score"],
                customdata=customdata,
                featureidkey="properties.neighborhood",
                colorscale=[
                    [
                        0,
                        f"rgba(26, 54, 93, {fill_opacity})"
                        if theme == "light"
                        else f"rgba(255, 255, 255, {fill_opacity})"
                    ],
                    [
                        1,
                        f"rgba(26, 54, 93, {fill_opacity})"
                        if theme == "light"
                        else f"rgba(255, 255, 255, {fill_opacity})"
                    ],
                ],
                zmin=0,
                zmax=100,
                showscale=False,
                marker={
                    "line": {"color": "rgba(0,0,0,0)", "width": 0},
                },
                hovertemplate=(
                    "<b>%{location}</b><br>"
                    "Aderência: %{z:.1f}/100<br>"
                    "Empregos formais: %{customdata[0]:.1f}<br>"
                    "Segurança: %{customdata[1]:.1f}<br>"
                    "Índice de roubos: %{customdata[2]:.1f}<br>"
                    "Iluminação LED: %{customdata[3]:.1f}<br>"
                    "Arborização: %{customdata[4]:.1f}<br>"
                    "Mobilidade: %{customdata[5]:.1f}<br>"
                    "Orçamento: %{customdata[6]:.1f}"
                    "<extra></extra>"
                ),
                name="Distritos selecionados",
            )
        )
        center, zoom = _map_view(selected_features)
    else:
        center, zoom = _MAP_CENTER, 9.5

    map_style = "carto-darkmatter" if theme == "dark" else "carto-voyager"
    map_background = "#0b1220" if theme == "dark" else "#dce7ef"
    figure.update_layout(
        map={"style": map_style, "center": center, "zoom": zoom},
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        paper_bgcolor=map_background,
        plot_bgcolor=map_background,
        showlegend=False,
        autosize=True,
        clickmode="event+select" if selectable else "event",
    )
    return figure


class DistrictMapService:
    """Reúne limites, filtros e interações usados pelas telas de mapa."""

    def __init__(self, boundaries: dict[str, Any] | None = None) -> None:
        self._boundaries = (
            load_district_boundaries() if boundaries is None else boundaries
        )

    @staticmethod
    def zone_for_neighborhood(row: pd.Series) -> str:
        latitude = float(row["latitude"])
        longitude = float(row["longitude"])
        if latitude >= -23.54:
            return "Norte"
        if latitude <= -23.58:
            return "Sul"
        if longitude <= -46.68:
            return "Oeste"
        if longitude >= -46.64:
            return "Leste"
        return "Centro"

    def filter_districts(
        self,
        neighborhoods: pd.DataFrame,
        selected_names: list[str],
        search: str,
        quick_filters: list[str],
    ) -> pd.DataFrame:
        return filter_districts(
            neighborhoods, selected_names, search, quick_filters
        )

    def selected_district_ranking(
        self, scored_neighborhoods: pd.DataFrame, selected_names: list[str]
    ) -> pd.DataFrame:
        return selected_district_ranking(scored_neighborhoods, selected_names)

    def restrict_to_mapped_districts(
        self, neighborhoods: pd.DataFrame
    ) -> tuple[pd.DataFrame, list[str]]:
        return restrict_to_mapped_districts(neighborhoods, self._boundaries)

    def build_map(
        self,
        visible_neighborhoods: pd.DataFrame,
        theme: str = "light",
        selectable: bool = False,
    ) -> go.Figure:
        return build_district_map(
            visible_neighborhoods,
            self._boundaries,
            theme=theme,
            selectable=selectable,
        )

    @staticmethod
    def district_from_selection(
        points: list[dict[str, Any]], visible_names: list[str]
    ) -> str | None:
        return district_from_map_selection(points, visible_names)

    @staticmethod
    def toggle_district_detail(
        active_district: str | None, clicked_district: str | None
    ) -> str | None:
        return toggle_district_detail(active_district, clicked_district)
