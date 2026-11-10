"""Fonte local e imutável para a edição pública do Atlas Sampa.

Não consulta Databricks. Exige liberação explícita de conteúdo agregado,
com integridade SHA256, sem alterar o estado do Consumer V2 privado.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

import pandas as pd

from bairroiq.consumer_v2 import SNAPSHOT

PUBLIC_COLUMNS = (
    "snapshot_id", "cd_dist", "neighborhood", "latitude", "longitude",
    "formal_jobs_score", "safety_score", "mobility_score",
    "green_leisure_score", "public_services_score", "densidade_hab_km2",
    "robberies_per_1000", "perfil_id", "cluster", "tipo_territorio",
)
SCORE_COLUMNS = (
    "formal_jobs_score", "safety_score", "mobility_score",
    "green_leisure_score", "public_services_score",
)
NUMERIC_COLUMNS = (
    "latitude", "longitude", "densidade_hab_km2", "robberies_per_1000",
    *SCORE_COLUMNS,
)
HISTORY_COLUMNS = [
    "neighborhood", "year", "formal_jobs_score", "lighting_led", "safety_score",
]
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")


class PublicSnapshotProvider:
    """Lê exclusivamente o CSV público aprovado e versionado com o app."""

    def __init__(self, app_dir: Path | None = None) -> None:
        self._app_dir = app_dir or Path(__file__).resolve().parents[1]
        self._data_dir = self._app_dir / "data"

    def load_metrics(self) -> pd.DataFrame:
        manifest_path = self._data_dir / "public_release.json"
        csv_path = self._data_dir / "public_consumer_v2.csv"
        if not manifest_path.is_file() or not csv_path.is_file():
            raise PermissionError(
                "Snapshot público indisponível: falta arquivo de dados ou "
                "manifesto de liberação aprovado."
            )

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("aprovacao_explicita") is not True:
            raise PermissionError("Publicação não foi explicitamente autorizada")
        if not all(
            isinstance(manifest.get(field), str) and manifest[field].strip()
            for field in ("aprovado_por", "referencia_aprovacao", "aprovado_em_utc")
        ):
            raise PermissionError("Manifesto sem responsáveis e evidência de aprovação")
        if manifest.get("snapshot_id") != SNAPSHOT:
            raise ValueError("O manifesto não corresponde ao snapshot contratado")
        source_hash = str(manifest.get("fonte_payload_sha256", ""))
        file_hash = str(manifest.get("arquivo_sha256", ""))
        if not SHA256_PATTERN.fullmatch(source_hash) or not SHA256_PATTERN.fullmatch(file_hash):
            raise ValueError("Manifesto sem hashes SHA256 válidos")
        digest = hashlib.sha256(csv_path.read_bytes()).hexdigest()
        if digest != file_hash:
            raise ValueError("O CSV público foi alterado após a liberação")

        df = pd.read_csv(csv_path, float_precision="round_trip", dtype={
            "snapshot_id": "string", "neighborhood": "string",
            "perfil_id": "string", "cluster": "string", "tipo_territorio": "string",
        })
        if set(df.columns) != set(PUBLIC_COLUMNS):
            raise ValueError("Colunas divergentes do contrato público de 15 campos")
        if len(df) != 96 or df.isna().any().any():
            raise ValueError("Snapshot público deve conter exatamente 96 linhas sem nulos")
        if df["snapshot_id"].nunique() != 1 or not df["snapshot_id"].eq(SNAPSHOT).all():
            raise ValueError("Snapshot misto ou diferente da versão auditada")
        if df["tipo_territorio"].nunique() != 1 or not df["tipo_territorio"].eq("DISTRITO_IBGE").all():
            raise ValueError("Somente distritos oficiais podem ser publicados")
        if df["neighborhood"].duplicated().any():
            raise ValueError("Nomes de distritos duplicados")
        df["cd_dist"] = pd.to_numeric(df["cd_dist"], errors="raise")
        if df["cd_dist"].duplicated().any() or not df["cd_dist"].map(lambda x: float(x).is_integer()).all():
            raise ValueError("Códigos distritais duplicados ou inválidos")
        for column in NUMERIC_COLUMNS:
            df[column] = pd.to_numeric(df[column], errors="raise")
            if not df[column].map(math.isfinite).all():
                raise ValueError(f"Valor não finito: {column}")
        if any(not df[col].between(0, 100).all() for col in SCORE_COLUMNS):
            raise ValueError("Scores fora da escala 0 a 100")
        if not df["latitude"].between(-24, -23).all() or not df["longitude"].between(-47, -46).all():
            raise ValueError("Coordenadas fora da cidade de São Paulo")
        if (df[["densidade_hab_km2", "robberies_per_1000"]] < 0).any().any():
            raise ValueError("Densidades e taxas devem ser não negativas")
        if df["perfil_id"].nunique() != 9 or not df["perfil_id"].str.fullmatch(r"kmeans-k09-p0[1-9]").all():
            raise ValueError("Era esperado o catálogo K-Means de nove perfis")
        expected = {f"kmeans-k09-p{i:02d}": count for i, count in enumerate((9, 7, 6, 22, 7, 8, 12, 19, 6), start=1)}
        if df["perfil_id"].value_counts().to_dict() != expected:
            raise ValueError("Distribuição dos perfis difere do catálogo auditado")

        df = df.loc[:, PUBLIC_COLUMNS].sort_values("neighborhood").reset_index(drop=True)
        df["district_code"] = df["cd_dist"]
        df["robbery_index"] = df["robberies_per_1000"]
        return df

    def load_history(self) -> pd.DataFrame:
        """Snapshot não permite inventar uma série temporal anual."""
        return pd.DataFrame(columns=HISTORY_COLUMNS)
