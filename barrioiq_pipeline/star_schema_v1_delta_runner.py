"""BairroIQ | Delta v1: snapshots internos do Star Schema (7 tabelas).

--check: consulta somente leitura, nao executa DDL/DML.
apply_snapshot: somente com confirmacao explicita, nao e chamado pelo Bundle.

ATENCAO: o snapshot identifica a versao dos dados/modelo, NAO o periodo
real de origem de todas as fontes. Nao conceder grants ao frontend. Dado
exploratorio NAO homologado publicamente. Os sete Delta tables nao formam
uma transacao multi-tabela; dim_snapshot e o marcador de completude,
publicado por ultimo. O consumidor so pode considerar snapshots registrados.
"""
from __future__ import annotations

from collections import OrderedDict
import importlib.util
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

BASE = Path(__file__).resolve().parent
PREVIEW_SCRIPT = BASE / "star_schema_v1_preview.py"
CONFIG_PATH = BASE / "catalogo_perfis_v3_config.json"
CATALOG = "workspace"
SCHEMA = "gold"
PREFIX = "bairroiq_"
EXPECTED_HASH = "726091fefefa868fd5d0d2c6929b1d68c4849941f4c7510b4fee0d93a075d38b"
EXPECTED_VERSION = "v3.0.0-candidato"
STATUS = "PREVIA_DIMENSIONAL_NAO_PUBLICAVEL"
CONFIRMATION = "MATERIALIZAR_SNAPSHOT_INTERNO_SEM_PUBLICACAO"

# Campos fisicos e tipos Spark. dim_distrito acrescenta snapshot_id de proposito:
# preserva nome/centroide oficiais por versao, sem sobrescrever o passado.
# Todos os alvos tem snapshot_id; nenhuma data de origem foi inventada.
STRUCTURES = OrderedDict({
    "dim_distrito": [
        ("snapshot_id", "string"), ("CD_DIST", "long"),
        ("NM_DIST", "string"), ("latitude", "double"), ("longitude", "double"),
    ],
    "dim_perfil": [
        ("snapshot_id", "string"), ("perfil_sk", "string"),
        ("perfil_id", "string"), ("nome_provisorio", "string"),
        ("nome_exibicao_proposto", "string"), ("ressalva_especifica", "string"),
        ("qtd_distritos", "long"), ("disponivel_publicamente", "boolean"),
    ],
    "dim_indicador": [
        ("snapshot_id", "string"), ("indicador_sk", "string"),
        ("indicador_id", "string"), ("coluna_gold", "string"),
        ("rotulo", "string"), ("unidade", "string"),
        ("fonte", "string"), ("periodo_referencia_documentado", "string"),
        ("periodo_validado_na_gold", "boolean"),
    ],
    "fato_distrito_indicador": [
        ("snapshot_id", "string"), ("CD_DIST", "long"),
        ("indicador_sk", "string"), ("valor_numerico", "double"),
    ],
    "fato_distrito_perfil": [
        ("snapshot_id", "string"), ("CD_DIST", "long"),
        ("perfil_sk", "string"),
        ("representatividade_interna_0a100", "double"),
        ("silhouette_individual", "double"),
        ("distancia_ao_centro_do_perfil", "double"),
        ("tipo_pertencimento", "string"),
    ],
    "fato_prioridade_ocorrencias": [
        ("snapshot_id", "string"), ("CD_DIST", "long"),
        ("posicao_relativa_entre_96", "long"),
        ("percentil_relativo_roubos_0a100", "double"),
        ("percentil_relativo_furtos_0a100", "double"),
        ("indice_ordenacao_ocorrencias", "double"),
    ],
    # A dimensao de snapshot e registrada SEMPRE por ultimo.
    "dim_snapshot": [
        ("snapshot_id", "string"), ("catalogo_versao", "string"),
        ("sha256_gold", "string"), ("fonte_gold", "string"),
        ("status", "string"), ("disponivel_publicamente", "boolean"),
        ("ano_snapshot_fonte", "long"), ("aviso_temporal", "string"),
    ],
})

ROW_COUNTS = {
    "dim_distrito": 96, "dim_perfil": 9, "dim_indicador": 11,
    "fato_distrito_indicador": 1056, "fato_distrito_perfil": 96,
    "fato_prioridade_ocorrencias": 96, "dim_snapshot": 1,
}
KEYS = {
    "dim_distrito": ("snapshot_id", "CD_DIST"),
    "dim_perfil": ("perfil_sk",),
    "dim_indicador": ("indicador_sk",),
    "fato_distrito_indicador": ("snapshot_id", "CD_DIST", "indicador_sk"),
    "fato_distrito_perfil": ("snapshot_id", "CD_DIST"),
    "fato_prioridade_ocorrencias": ("snapshot_id", "CD_DIST"),
    "dim_snapshot": ("snapshot_id",),
}
TABLES = {key: f"{CATALOG}.{SCHEMA}.{PREFIX}{key}" for key in STRUCTURES}


class DeltaContractError(ValueError):
    """Bloqueio fail-closed da materializacao Delta."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DeltaContractError("BAIRROIQ_DELTA_V1_BLOCKED: " + message)


def _py(v: Any) -> Any:
    """Converte escalares pandas/numpy; NaN so permitido no campo temporal nulo."""
    if v is None:
        return None
    if hasattr(v, "item") and callable(v.item):
        try:
            v = v.item()
        except (ValueError, TypeError):
            pass
    if not isinstance(v, (str, dict, list)):
        try:
            if pd.isna(v):
                return None
        except (TypeError, ValueError):
            pass
    return v


def _cast(v: Any, typ: str, *, nullable: bool = False) -> Any:
    v = _py(v)
    if v is None:
        require(nullable, f"NULL indevido em campo {typ}")
        return None
    if typ == "string":
        require(isinstance(v, str) and bool(v.strip()), "String vazia/invalida")
        return v
    if typ == "boolean":
        require(isinstance(v, bool), "Booleano invalido")
        return v
    if typ == "long":
        require(isinstance(v, (int, float)) and not isinstance(v, bool), "Inteiro invalido")
        require(math.isfinite(float(v)) and int(v) == float(v), "Inteiro fracionario/infinito")
        return int(v)
    if typ == "double":
        require(isinstance(v, (float, int)) and not isinstance(v, bool), "Numero invalido")
        f = float(v)
        require(math.isfinite(f), "Numero nao finito")
        return f
    raise AssertionError(typ)


def prepare_snapshot(preview: dict[str, Any]) -> dict[str, Any]:
    """Contratos de 7 relacoes e versionamento, sem Spark nem escrita."""
    summary = preview.get("resumo", {})
    tables = preview.get("tabelas", {})
    require(summary.get("sha256_gold") == EXPECTED_HASH, "Hash da Gold nao autorizado")
    require(summary.get("versao") == EXPECTED_VERSION, "Versao do catalogo nao autorizada")
    require(summary.get("status") == STATUS, "Status de preview nao autorizado")
    require(summary.get("alteracoes_gold") == "NENHUMA", "Gold previamente modificada")
    require(summary.get("publicacao_gold_autorizada") is False, "Publicacao indevida")
    require(summary.get("auditoria_p04_condicao_editorial") is True, "P04 ainda sem auditoria")
    require(summary.get("auditoria_p04_nome_homologado") is False, "P04 deve estar nao homologado")
    require(summary.get("fatos_historicos_publicados") is False, "Historico declarado sem evidencia")
    snapshot_id = f"{EXPECTED_VERSION}|{EXPECTED_HASH}"
    require(summary.get("snapshot_id") == snapshot_id, "Snapshot inesperado")
    require(set(tables) == set(STRUCTURES) and summary.get("linhas") == ROW_COUNTS,
            "Estruturas ou cardinalidades do preview divergentes")
    require(all(isinstance(tables[k], pd.DataFrame) and len(tables[k]) == ROW_COUNTS[k]
                for k in STRUCTURES), "DataFrames de entrada ausentes/incompletos")

    payloads = {}
    for name, spec in STRUCTURES.items():
        frame = tables[name].copy()
        if name == "dim_distrito":
            require("snapshot_id" not in frame.columns,
                    "dim_distrito deve vir da referencia sem versao do preview")
            frame.insert(0, "snapshot_id", snapshot_id)
        columns = [c for c, _ in spec]
        require(set(frame.columns) == set(columns), f"Campos desconhecidos/ausentes em {name}")
        require(frame["snapshot_id"].eq(snapshot_id).all(), f"{name}: mistura de snapshots")
        require(not frame.duplicated(list(KEYS[name])).any(), f"{name}: chave duplicada")
        rows = []
        for row in frame[columns].itertuples(index=False, name=None):
            record = {}
            for (column, typ), v in zip(spec, row):
                record[column] = _cast(v, typ, nullable=(name == "dim_snapshot" and column == "ano_snapshot_fonte"))
            rows.append(record)
        payloads[name] = rows
    # Guardrails adicionais nao sao confiados somente ao modulo preview.
    snap = payloads["dim_snapshot"][0]
    require(snap["disponivel_publicamente"] is False
            and snap["status"] == STATUS
            and snap["ano_snapshot_fonte"] is None,
            "Snapshot apresenta publicacao ou data de origem inventada")
    require(snap["snapshot_id"] == snapshot_id
            and snap["sha256_gold"] == EXPECTED_HASH
            and snap["catalogo_versao"] == EXPECTED_VERSION
            and snap["fonte_gold"] == "workspace.gold.distritos_wide",
            "Metadados do snapshot divergentes da fonte validada")
    require(all(p["disponivel_publicamente"] is False for p in payloads["dim_perfil"]),
            "Perfil disponivel publicamente")
    require(all(p["periodo_validado_na_gold"] is False for p in payloads["dim_indicador"]),
            "Indicadores declarados temporalmente validados sem evidencia")
    require(set(p["CD_DIST"] for p in payloads["dim_distrito"])
            == set(p["CD_DIST"] for p in payloads["fato_distrito_perfil"]),
            "FK de distrito diferente entre dimensao e perfil")
    require(set(p["perfil_sk"] for p in payloads["fato_distrito_perfil"])
            .issubset(set(p["perfil_sk"] for p in payloads["dim_perfil"])),
            "FK de perfil orfa")
    require(set(p["indicador_sk"] for p in payloads["fato_distrito_indicador"])
            == set(p["indicador_sk"] for p in payloads["dim_indicador"]),
            "FK de indicador divergente")
    require(set(p["CD_DIST"] for p in payloads["fato_prioridade_ocorrencias"])
            == set(p["CD_DIST"] for p in payloads["dim_distrito"]),
            "FK de ocorrencias divergente")
    require(set(p["posicao_relativa_entre_96"] for p in payloads["fato_prioridade_ocorrencias"])
            == set(range(1, 97)), "Ranking 1..96 invalido")
    require(sum(p["tipo_pertencimento"] == "FRONTEIRA"
                for p in payloads["fato_distrito_perfil"]) == 3,
            "Tres distritos de fronteira esperados")
    require(all(0 <= p["representatividade_interna_0a100"] <= 100
                for p in payloads["fato_distrito_perfil"]),
            "Representatividade fora de escala")
    require(all(0 <= p["percentil_relativo_roubos_0a100"] <= 100
                and 0 <= p["percentil_relativo_furtos_0a100"] <= 100
                for p in payloads["fato_prioridade_ocorrencias"]),
            "Percentis fora de escala")
    return {"snapshot_id": snapshot_id, "payloads": payloads,
            "rows": {k: len(v) for k, v in payloads.items()}}


def load_preview(spark_session: Any) -> dict[str, Any]:
    require(PREVIEW_SCRIPT.is_file(), f"Modulo nao implantado: {PREVIEW_SCRIPT}")
    require(CONFIG_PATH.is_file(), f"Catalogo nao implantado: {CONFIG_PATH}")
    spec = importlib.util.spec_from_file_location("bairroiq_star_preview_para_delta", str(PREVIEW_SCRIPT))
    require(spec is not None and spec.loader is not None, "Modulo preview invalido")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.run_from_spark(spark_session)


def spark_schema(name: str):
    """Schema explicito; evita erro no campo ano_snapshot_fonte inteiramente NULL."""
    from pyspark.sql.types import (StructType, StructField, StringType,
                                   LongType, DoubleType, BooleanType)
    types = {"string": StringType, "long": LongType,
             "double": DoubleType, "boolean": BooleanType}
    return StructType([StructField(c, types[typ](), True) for c, typ in STRUCTURES[name]])


def _payload_hash(rows: list[dict[str, Any]], key: str) -> str:
    import hashlib
    ordered = sorted(rows, key=lambda x: tuple(str(x[c]) for c in KEYS[key]))
    serialized = json.dumps(ordered, ensure_ascii=False, sort_keys=True,
                            separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _existing_rows(spark, name: str, snapshot_id: str) -> list[dict[str, Any]]:
    from pyspark.sql import functions as F
    df = spark.table(TABLES[name]).where(F.col("snapshot_id") == snapshot_id)
    return [{k: _cast(row[k], typ, nullable=(name == "dim_snapshot" and k == "ano_snapshot_fonte"))
             for k, typ in STRUCTURES[name]} for row in df.collect()]


def _validate_table(spark, name: str) -> None:
    table = TABLES[name]
    current = spark.table(table)
    observed = [(f.name, f.dataType.simpleString()) for f in current.schema]
    require(observed == STRUCTURES[name], f"Schema divergente da tabela {table}: {observed}")
    details = spark.sql(f"DESCRIBE DETAIL {table}").first().asDict()
    require(str(details.get("format", "")).lower() == "delta",
            f"Destino {table} nao e Delta")


def inspect(spark, prepared: dict[str, Any]) -> dict[str, Any]:
    """Plano totalmente read-only; verifica tabelas e snapshots existentes."""
    sid = prepared["snapshot_id"]
    result = OrderedDict()
    for name in STRUCTURES:
        target = TABLES[name]
        exists = bool(spark.catalog.tableExists(target))
        count = 0
        if exists:
            _validate_table(spark, name)
            current = _existing_rows(spark, name, sid)
            count = len(current)
            if count:
                require(count == ROW_COUNTS[name], f"{name}: snapshot parcial/duplicado")
                require(_payload_hash(current, name)
                        == _payload_hash(prepared["payloads"][name], name),
                        f"{name}: snapshot ja existente com conteudo diferente")
        result[name] = {"table": target, "table_exists": exists,
                        "rows_in_snapshot": count,
                        "action_if_applied": "KEEP_VERIFIED" if count else "APPEND_SNAPSHOT"}
    if result["dim_snapshot"]["rows_in_snapshot"]:
        require(all(result[k]["rows_in_snapshot"] == ROW_COUNTS[k]
                    for k in STRUCTURES),
                "Marcador de snapshot existe mas ha tabelas incompletas")
    return {"snapshot_id": sid, "target_schema": f"{CATALOG}.{SCHEMA}",
            "tables": result, "will_write_on_check": False,
            "publicacao_gold_autorizada": False}


def check(spark) -> dict[str, Any]:
    """Ponto de entrada seguro para o notebook e CI de integracao."""
    prepared = prepare_snapshot(load_preview(spark))
    return inspect(spark, prepared)


def _write_one(spark, name: str, rows: list[dict[str, Any]], exists: bool) -> None:
    frame = spark.createDataFrame(rows, schema=spark_schema(name))
    writer = frame.write.format("delta")
    if exists:
        writer.mode("append").saveAsTable(TABLES[name])
    else:
        writer.mode("errorifexists").saveAsTable(TABLES[name])


def apply_snapshot(spark, *, confirmation: str, expected_hash: str) -> dict[str, Any]:
    """Escrita manual explicita. NUNCA chamar no CI/CD/job automatico.

    Nao existe transacao ACID envolvendo as sete tabelas por padrao.
    dim_snapshot e registrada por ultimo como marcador de completude.
    Um commit parcial pode ser retomado apenas se o conteudo for IDENTICO.
    Um processo concorrente no mesmo snapshot NAO e suportado.
    """
    require(confirmation == CONFIRMATION, "Confirmacao de escrita invalida")
    require(expected_hash == EXPECTED_HASH, "Hash de autorizacao divergente")
    prepared = prepare_snapshot(load_preview(spark))
    before = inspect(spark, prepared)
    if before["tables"]["dim_snapshot"]["rows_in_snapshot"]:
        return {"action": "ALREADY_MATERIALIZED_AND_VERIFIED", "before": before,
                "after": before, "published": False}
    for name in STRUCTURES:
        item = before["tables"][name]
        if item["rows_in_snapshot"]:
            continue  # retomada estrita com hash identico de conteudo
        _write_one(spark, name, prepared["payloads"][name],
                   exists=item["table_exists"])
        # Verificar imediatamente o mesmo snapshot apos cada append.
        current = _existing_rows(spark, name, prepared["snapshot_id"])
        require(len(current) == ROW_COUNTS[name], f"{name}: pos-escrita incompleta")
        require(_payload_hash(current, name) == _payload_hash(prepared["payloads"][name], name),
                f"{name}: pos-escrita divergente")
    after = inspect(spark, prepared)
    require(all(after["tables"][k]["rows_in_snapshot"] == ROW_COUNTS[k]
                for k in STRUCTURES), "Materializacao incompleta")
    return {"action": "MATERIALIZED_INTERNAL_SNAPSHOT", "before": before,
            "after": after, "published": False}
