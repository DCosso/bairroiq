from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

import pandas as pd
import streamlit as st

from bairroiq.databricks import DatabricksConfig, DatabricksDataProvider
from bairroiq.public_snapshot import PublicSnapshotProvider
from bairroiq.sample_data import SampleDataProvider


class DataProvider(Protocol):
    def load_metrics(self) -> pd.DataFrame: ...

    def load_history(self) -> pd.DataFrame: ...


class DataProviderFactory:
    """Preserva os modos privado e demonstrativo; adiciona o snapshot público."""

    @staticmethod
    def create(
        provider_name: str | None = None,
        secrets: Mapping[str, object] | None = None,
    ) -> DataProvider:
        selected_provider = (
            provider_name or os.getenv("BAIRROIQ_DATA_PROVIDER", "sample")
        ).strip().lower()
        if selected_provider == "sample":
            return SampleDataProvider()
        if selected_provider == "public_snapshot":
            return PublicSnapshotProvider()
        if selected_provider != "databricks":
            raise ValueError(
                "BAIRROIQ_DATA_PROVIDER deve ser 'sample', "
                "'databricks' ou 'public_snapshot'."
            )

        if secrets is None:
            # No Streamlit Community Cloud st.secrets existe mesmo sem arquivo
            # local; no ambiente privado a conexão segue as regras atuais.
            try:
                secrets = dict(st.secrets)
            except FileNotFoundError:
                secrets = {}
        return DatabricksDataProvider(DatabricksConfig.from_sources(secrets))


@st.cache_resource
def get_provider() -> DataProvider:
    return DataProviderFactory.create()


@st.cache_data(ttl=300)
def load_metrics() -> pd.DataFrame:
    return get_provider().load_metrics()


@st.cache_data(ttl=300)
def load_history() -> pd.DataFrame:
    return get_provider().load_history()
