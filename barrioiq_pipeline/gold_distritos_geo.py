"""BairroIQ | Coordenadas oficiais dos 96 distritos de Sao Paulo.

Fonte: IBGE, Malha Distrital 2022, centroides metricos EPSG:31983
convertidos para EPSG:4326, com 8 casas decimais.

Arquivo versionado: distritos_centroides_ibge_2022.json

O modulo nao usa GeoPandas e nao executa DDL/DML. A unica operacao
sobre Spark e um JOIN em memoria com 96 registros da referencia.
"""

import hashlib
import json
import math
import re
import unicodedata
from pathlib import Path


REFERENCE_NAME = "distritos_centroides_ibge_2022.json"
EXPECTED_DISTRICTS = 96
EXPECTED_TABLE = "workspace.gold.distritos_wide"
EXPECTED_MUNICIPALITY = "3550308"
EXPECTED_SHAPE_SHA256 = (
    "8b444103cf01e1a9062f038b9c89bc27d6f75243b348dabf213dc8363e8c5684"
)
EXPECTED_CRS_SOURCE = "EPSG:4674"
EXPECTED_CRS_PROJECTED = "EPSG:31983"
EXPECTED_CRS_TARGET = "EPSG:4326"
GEO_COLUMNS = ("latitude", "longitude")


class GeoContractError(ValueError):
    """Contrato geoespacial invalido ou inconsistente com a Gold."""


def require(condition, message):
    if not condition:
        raise GeoContractError(message)


def normalize_name(value):
    require(isinstance(value, str) and value.strip(), "Nome de distrito invalido")
    text = "".join(
        char
        for char in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(char)
    )
    return re.sub(r"\s+", " ", text).strip().casefold()


def load_centroids(path=None):
    """Retorna (registros, hash_json) com 96 registros validos e ordenados.

    Somente leitura. Por padrao, o JSON deve estar na mesma pasta deste modulo.
    """
    reference_path = (
        Path(path) if path is not None
        else Path(__file__).resolve().with_name(REFERENCE_NAME)
    )

    require(reference_path.is_file(), f"Referencia nao encontrada: {reference_path}")
    raw = reference_path.read_bytes()
    sha_json = hashlib.sha256(raw).hexdigest()

    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GeoContractError(f"JSON geoespacial invalido: {exc}") from exc

    require(isinstance(document, dict), "Documento deve ser objeto JSON")

    expected_metadata = {
        "tabela_destino": EXPECTED_TABLE,
        "codigo_municipio": EXPECTED_MUNICIPALITY,
        "quantidade_distritos": EXPECTED_DISTRICTS,
        "crs_origem": EXPECTED_CRS_SOURCE,
        "crs_calculo": EXPECTED_CRS_PROJECTED,
        "crs_coordenadas": EXPECTED_CRS_TARGET,
        "sha256_malha": EXPECTED_SHAPE_SHA256,
        "precisao_decimal": 8,
    }

    for key, expected in expected_metadata.items():
        require(document.get(key) == expected, f"Metadado divergente: {key}")

    records = document.get("distritos")
    require(
        isinstance(records, list) and len(records) == EXPECTED_DISTRICTS,
        "JSON deve conter exatamente 96 distritos",
    )

    normalized = []
    seen_codes = set()
    seen_names = set()

    for index, row in enumerate(records):
        require(isinstance(row, dict), f"Registro {index}: objeto invalido")
        require(
            set(row) == {"CD_DIST", "NM_DIST", "latitude", "longitude", "metodo"},
            f"Registro {index}: campos inesperados ou ausentes",
        )

        code = row["CD_DIST"]
        name = row["NM_DIST"]
        lat = row["latitude"]
        lon = row["longitude"]
        method = row["metodo"]

        require(
            type(code) is int and 355030800 < code <= 355030899,
            f"Registro {index}: CD_DIST invalido",
        )
        require(code not in seen_codes, f"CD_DIST duplicado: {code}")
        seen_codes.add(code)

        clean_name = normalize_name(name)
        require(clean_name not in seen_names, f"NM_DIST duplicado: {name}")
        seen_names.add(clean_name)

        require(
            type(lat) in (int, float) and type(lon) in (int, float),
            f"Registro {index}: coordenadas nao numericas",
        )
        require(
            math.isfinite(lat) and math.isfinite(lon),
            f"Registro {index}: coordenadas nao finitas",
        )
        require(-24.0 <= lat <= -23.0, f"Latitude fora de Sao Paulo: {code}")
        require(-47.0 <= lon <= -46.0, f"Longitude fora de Sao Paulo: {code}")
        require(method == "CENTROIDE", f"Metodo inesperado: {code}: {method}")

        normalized.append({
            "CD_DIST": code,
            "NM_DIST": name,
            "latitude": float(lat),
            "longitude": float(lon),
        })

    normalized.sort(key=lambda record: record["CD_DIST"])

    require(
        len(seen_codes) == EXPECTED_DISTRICTS,
        "Referencia com quantidade incorreta de codigos unicos",
    )

    return normalized, sha_json


def attach_coordinates(spark, base, path=None):
    """Adiciona latitude/longitude DOUBLE aos 96 distritos em memoria.

    Nao cria, atualiza nem altera tabela alguma. Mantem a ordem original
    das colunas do DataFrame base, acrescentando latitude e longitude ao fim.
    """
    from pyspark.sql import functions as F
    from pyspark.sql.types import DoubleType, LongType, StructField, StructType

    require("CD_DIST" in base.columns, "Base nao contem CD_DIST")
    require("NM_DIST" in base.columns, "Base nao contem NM_DIST")
    require(
        not set(GEO_COLUMNS).intersection(base.columns),
        "Base ja contem colunas geograficas",
    )

    rows, sha_json = load_centroids(path)

    base_rows = base.select("CD_DIST", "NM_DIST").collect()
    require(len(base_rows) == EXPECTED_DISTRICTS, "Base deve ter 96 distritos")

    base_codes = {}
    for row in base_rows:
        code = row["CD_DIST"]
        require(code is not None, "Base contem CD_DIST nulo")
        key = int(code)
        require(key not in base_codes, f"Base tem CD_DIST duplicado: {key}")
        base_codes[key] = normalize_name(row["NM_DIST"])

    geo_by_code = {row["CD_DIST"]: row for row in rows}
    require(
        set(base_codes) == set(geo_by_code),
        "Codigos do arquivo e da Gold proposta nao coincidem",
    )

    wrong_names = [
        code
        for code, name in base_codes.items()
        if name != normalize_name(geo_by_code[code]["NM_DIST"])
    ]
    require(not wrong_names, f"Nomes de distritos divergentes: {wrong_names}")

    schema = StructType([
        StructField("CD_DIST", LongType(), False),
        StructField("latitude", DoubleType(), False),
        StructField("longitude", DoubleType(), False),
    ])

    geo = spark.createDataFrame(
        [
            (row["CD_DIST"], row["latitude"], row["longitude"])
            for row in rows
        ],
        schema=schema,
    )

    enriched = base.join(F.broadcast(geo), on="CD_DIST", how="left")

    require(
        enriched.count() == EXPECTED_DISTRICTS,
        "JOIN geoespacial alterou quantidade de distritos",
    )
    require(
        enriched.filter(
            F.col("latitude").isNull() | F.col("longitude").isNull()
        ).limit(1).count() == 0,
        "JOIN geoespacial produziu coordenadas nulas",
    )
    require(
        enriched.columns == [*base.columns, *GEO_COLUMNS],
        "JOIN geoespacial alterou ordem do schema",
    )

    return enriched, {
        "distritos_geolocalizados": EXPECTED_DISTRICTS,
        "metodo": "CENTROIDE",
        "crs": EXPECTED_CRS_TARGET,
        "sha256_json": sha_json,
        "sha256_malha": EXPECTED_SHAPE_SHA256,
    }
