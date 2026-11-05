"""BairroIQ | Preview dimensional v1, SEM escritas Delta ou publicacao.

Le uma unica fotografia da Gold, reutiliza o pipeline ML v3 + preferencia v1,
e constroi sete DataFrames pandas com chaves, graos e FKs validados.

ATENCAO: a v3 nao esta homologada publicamente. Nao criar tabelas,
nao conceder acesso ao front e nao confundir snapshot ML com periodo da fonte.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
PRIORIDADE = BASE / "prioridade_roubos_furtos_v1.py"
CATALOGO_CONFIG = BASE / "catalogo_perfis_v3_config.json"
SOURCE = "workspace.gold.distritos_wide"
STATUS = "PREVIA_DIMENSIONAL_NAO_PUBLICAVEL"
N_DISTRICTS = 96
N_PROFILES = 9

# Os 11 nomes abaixo sao os aliases presentes em v2.SOURCE_FIELDS.
# Sem fabricar indicadores adicionais ou unidades espaciais.
INDICADORES = {
    "empregos": ("Empregos formais - total", "vinculos", "ObservaSampa", "2021"),
    "roubos": ("Roubos registrados", "por_100mil_hab", "SSP-SP", "janela_12m_fim_nao_catalogado"),
    "furtos": ("Furtos registrados", "por_100mil_hab", "SSP-SP", "janela_12m_fim_nao_catalogado"),
    "metro": ("Equipamentos de metro", "por_10mil_hab", "GeoSampa", "nao_catalogado"),
    "onibus": ("Equipamentos de onibus", "por_10mil_hab", "GeoSampa", "nao_catalogado"),
    "trem": ("Equipamentos de trem", "por_10mil_hab", "GeoSampa", "nao_catalogado"),
    "pracas": ("Pracas e largos cadastrados", "por_10mil_hab", "GeoSampa", "nao_catalogado"),
    "corredores_verdes": ("Corredores verdes cadastrados", "por_10mil_hab", "GeoSampa", "nao_catalogado"),
    "escolas": ("Escolas publicas cadastradas", "por_10mil_hab", "GeoSampa", "nao_catalogado"),
    "ubs": ("UBS cadastradas", "por_10mil_hab", "GeoSampa", "nao_catalogado"),
    "densidade": ("Densidade populacional", "habitantes_km2", "IBGE/Gold", "nao_catalogado"),
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError("BAIRROIQ_STAR_V1_BLOCKED: " + message)


def _require_columns(data: pd.DataFrame, names: list[str], entity: str) -> None:
    missing = [name for name in names if name not in data.columns]
    require(not missing, f"{entity}: colunas obrigatorias ausentes: {missing}")


def _unique(data: pd.DataFrame, cols: list[str], n: int, label: str) -> None:
    require(len(data) == n, f"{label}: cardinalidade {len(data)} difere de {n}")
    require(data[cols].notna().all().all(), f"{label}: chave nula")
    require(not data.duplicated(cols).any(), f"{label}: chave duplicada {cols}")


def _fk(child: pd.DataFrame, parent: pd.DataFrame, key: str, label: str) -> None:
    require(child[key].notna().all(), f"{label}: FK nula {key}")
    require(set(child[key]).issubset(set(parent[key])), f"{label}: FK orfa {key}")


def build_preview(
    raw: pd.DataFrame,
    resultados: dict[str, Any],
    source_fields: dict[str, str],
    expected_hash: str,
) -> dict[str, Any]:
    """Transformacao pura: dados em memoria -> dimensoes e fatos em memoria.

    O chamador de producao deve ter executado as validacoes de hash e modelo
    de `prioridade_roubos_furtos_v1.build_priority` sobre este MESMO `raw`.
    """
    require(set(source_fields) == set(INDICADORES), "Contrato de 11 indicadores mudou")
    require(len(set(source_fields.values())) == len(INDICADORES), "Fontes Gold duplicadas")
    require(len(expected_hash) == 64, "Hash de referencia invalido")
    resumo = resultados.get("resumo", {})
    require(resumo.get("status") == "EXPLORATORIO_NAO_HOMOLOGADO", "Prioridade nao exploratoria")
    require(resumo.get("publicacao_gold_autorizada") is False, "Publicacao indevidamente autorizada")
    require(resumo.get("alteracoes_gold") == "NENHUMA", "Possivel escrita Gold")
    require(resumo.get("sha256_gold") == expected_hash, "Hash de entrada difere da Gold congelada")
    version = resumo.get("catalogo_versao")
    require(isinstance(version, str) and version.startswith("v3."), "Versao v3 ausente")
    snapshot_id = f"{version}|{expected_hash}"

    required_raw = ["CD_DIST", "NM_DIST", "latitude", "longitude", *INDICADORES]
    _require_columns(raw, required_raw, "raw Gold")
    _unique(raw, ["CD_DIST"], N_DISTRICTS, "raw Gold")
    require(raw.NM_DIST.notna().all() and raw.NM_DIST.astype(str).str.strip().ne("").all(),
            "Nomes territoriais vazios")
    require(raw[["latitude", "longitude"]].notna().all().all(), "Coordenadas ausentes")
    require(np.isfinite(raw[["latitude", "longitude"]].to_numpy(dtype=float)).all(),
            "Coordenadas invalidas")
    vals = raw[list(INDICADORES)].apply(pd.to_numeric, errors="coerce")
    require(vals.notna().all().all(), "Indicadores nulos")
    require(np.isfinite(vals.to_numpy(dtype=float)).all(), "Indicadores nao finitos")
    require((vals >= 0).all().all(), "Indicadores negativos")
    raw = raw.copy()
    raw.loc[:, list(INDICADORES)] = vals

    catalogo = resultados.get("catalogo")
    ranked = resultados.get("distritos_priorizados")
    require(isinstance(catalogo, pd.DataFrame) and isinstance(ranked, pd.DataFrame),
            "Resultados do pipeline v3 ausentes")
    _require_columns(catalogo, ["perfil_id", "nome_provisorio", "nome_exibicao_proposto",
                               "nome_validado_para_publicacao", "qtd_distritos",
                               "ressalva_especifica", "disponivel_publicamente"], "catalogo")
    _require_columns(ranked, ["CD_DIST", "NM_DIST", "perfil_id", "catalogo_versao",
                              "representatividade_interna_0a100", "silhouette_individual",
                              "distancia_ao_centro_do_perfil", "tipo_pertencimento",
                              "posicao_relativa_entre_96", "percentil_relativo_roubos_0a100",
                              "percentil_relativo_furtos_0a100", "indice_ordenacao_ocorrencias",
                              "prioridade_id", "status_prioridade"], "classificacoes")
    _unique(catalogo, ["perfil_id"], N_PROFILES, "dim_perfil candidata")
    _unique(ranked, ["CD_DIST"], N_DISTRICTS, "atribuição distrital")
    require(set(ranked.CD_DIST) == set(raw.CD_DIST), "Distritos fonte/classificacao diferem")
    require(set(ranked.perfil_id) == set(catalogo.perfil_id), "Perfis sem atribuicao")
    require(ranked.catalogo_versao.eq(version).all(), "Versao de distrito nao coincide")
    require(ranked.status_prioridade.eq("EXPLORATORIO_NAO_HOMOLOGADO").all(),
            "Status de preferencia inesperado")
    require(ranked.prioridade_id.eq("menos_roubos_furtos").all(), "Prioridade desconhecida")
    require(catalogo.disponivel_publicamente.eq(False).all()
            and catalogo.nome_validado_para_publicacao.eq(False).all(),
            "Catalogo marcado como publico")
    count_by_profile = ranked.groupby("perfil_id").size().to_dict()
    require(all(int(p.qtd_distritos) == count_by_profile[p.perfil_id]
                for p in catalogo.itertuples(index=False)), "Contagem por perfil difere")
    require(set(ranked.posicao_relativa_entre_96) == set(range(1, N_DISTRICTS + 1)),
            "Ranking global incompleto")
    require(ranked.representatividade_interna_0a100.between(0, 100).all(),
            "Representatividade fora de escala")
    require(ranked.percentil_relativo_roubos_0a100.between(0, 100).all()
            and ranked.percentil_relativo_furtos_0a100.between(0, 100).all(),
            "Percentis de ocorrencias invalidos")
    # Os nomes em classificacao e Gold devem ser iguais apos normalizacao IBGE.
    names = raw.set_index("CD_DIST").NM_DIST
    require(all(names.loc[row.CD_DIST] == row.NM_DIST
                for row in ranked.itertuples(index=False)),
            "Nomes de distrito divergentes entre fatos e dimensao")

    dim_snapshot = pd.DataFrame([{
        "snapshot_id": snapshot_id, "catalogo_versao": version,
        "sha256_gold": expected_hash, "fonte_gold": SOURCE,
        "status": STATUS, "disponivel_publicamente": False,
        "ano_snapshot_fonte": None,
        "aviso_temporal": "Snapshot do modelo NAO e ano de referencia das fontes",
    }])
    dim_distrito = (raw[["CD_DIST", "NM_DIST", "latitude", "longitude"]]
                   .sort_values("CD_DIST").reset_index(drop=True))
    dim_perfil = catalogo[["perfil_id", "nome_provisorio", "nome_exibicao_proposto",
                           "ressalva_especifica", "qtd_distritos", "disponivel_publicamente"]].copy()
    dim_perfil.insert(0, "snapshot_id", snapshot_id)
    dim_perfil.insert(1, "perfil_sk", dim_perfil.perfil_id.map(
        lambda x: f"{snapshot_id}|{x}"))
    dim_perfil = dim_perfil.sort_values("perfil_id").reset_index(drop=True)

    dim_indicador = pd.DataFrame([{
        "snapshot_id": snapshot_id,
        "indicador_sk": f"{snapshot_id}|{alias}",
        "indicador_id": alias,
        "coluna_gold": source_fields[alias],
        "rotulo": details[0], "unidade": details[1],
        "fonte": details[2], "periodo_referencia_documentado": details[3],
        "periodo_validado_na_gold": False,
    } for alias, details in INDICADORES.items()])

    long = raw[["CD_DIST", *INDICADORES]].melt(
        id_vars=["CD_DIST"], var_name="indicador_id", value_name="valor_numerico")
    long["snapshot_id"] = snapshot_id
    long["indicador_sk"] = long.indicador_id.map(lambda x: f"{snapshot_id}|{x}")
    fato_indicador = long[["snapshot_id", "CD_DIST", "indicador_sk", "valor_numerico"]]
    fato_indicador = fato_indicador.sort_values(
        ["CD_DIST", "indicador_sk"]).reset_index(drop=True)

    fato_perfil = ranked[["CD_DIST", "perfil_id", "representatividade_interna_0a100",
                          "silhouette_individual", "distancia_ao_centro_do_perfil",
                          "tipo_pertencimento"]].copy()
    fato_perfil.insert(0, "snapshot_id", snapshot_id)
    fato_perfil.insert(2, "perfil_sk", fato_perfil.perfil_id.map(
        lambda x: f"{snapshot_id}|{x}"))
    fato_perfil = fato_perfil.drop(columns="perfil_id").sort_values("CD_DIST").reset_index(drop=True)

    fato_ocorrencias = ranked[["CD_DIST", "posicao_relativa_entre_96",
                               "percentil_relativo_roubos_0a100",
                               "percentil_relativo_furtos_0a100",
                               "indice_ordenacao_ocorrencias"]].copy()
    fato_ocorrencias.insert(0, "snapshot_id", snapshot_id)
    fato_ocorrencias = fato_ocorrencias.sort_values("CD_DIST").reset_index(drop=True)

    tabelas = {
        "dim_snapshot": dim_snapshot, "dim_distrito": dim_distrito,
        "dim_perfil": dim_perfil, "dim_indicador": dim_indicador,
        "fato_distrito_indicador": fato_indicador,
        "fato_distrito_perfil": fato_perfil,
        "fato_prioridade_ocorrencias": fato_ocorrencias,
    }
    _unique(dim_snapshot, ["snapshot_id"], 1, "dim_snapshot")
    _unique(dim_distrito, ["CD_DIST"], 96, "dim_distrito")
    _unique(dim_perfil, ["perfil_sk"], 9, "dim_perfil")
    _unique(dim_indicador, ["indicador_sk"], 11, "dim_indicador")
    _unique(fato_indicador, ["snapshot_id", "CD_DIST", "indicador_sk"], 1056,
            "fato_distrito_indicador")
    _unique(fato_perfil, ["snapshot_id", "CD_DIST"], 96, "fato_distrito_perfil")
    _unique(fato_ocorrencias, ["snapshot_id", "CD_DIST"], 96, "fato_prioridade_ocorrencias")
    for name, fact in tabelas.items():
        if name.startswith("fato_"):
            _fk(fact, dim_snapshot, "snapshot_id", name)
            _fk(fact, dim_distrito, "CD_DIST", name)
    _fk(fato_indicador, dim_indicador, "indicador_sk", "fato_indicador")
    _fk(fato_perfil, dim_perfil, "perfil_sk", "fato_perfil")
    require(fato_indicador.valor_numerico.notna().all(), "Valores da fato_indicador nulos")
    require(fato_perfil.tipo_pertencimento.eq("FRONTEIRA").sum() == 3,
            "Numero de distritos de fronteira divergente do snapshot v3")

    return {
        "tabelas": tabelas,
        "resumo": {
            "status": STATUS, "snapshot_id": snapshot_id,
            "fonte": SOURCE, "sha256_gold": expected_hash,
            "versao": version,
            "linhas": {k: len(v) for k, v in tabelas.items()},
            "fatos_historicos_publicados": False,
            "publicacao_gold_autorizada": False,
            "alteracoes_gold": "NENHUMA",
            "auditoria_p04_condicao_editorial": resultados["auditoria_p04"]["condicao_editorial_atendida"],
            "auditoria_p04_nome_homologado": resultados["auditoria_p04"]["nome_homologado"],
            "observacao": "Modelo dimensional validado apenas em memoria; tabelas Delta nao existem",
        },
    }


def run_from_spark(spark_session: Any) -> dict[str, Any]:
    """Uma leitura Spark, nenhuma escrita. Fail-closed no hash do catalogo v3."""
    require(PRIORIDADE.is_file(), f"Modulo nao encontrado: {PRIORIDADE}")
    require(CATALOGO_CONFIG.is_file(), f"Configuracao nao encontrada: {CATALOGO_CONFIG}")
    spec = importlib.util.spec_from_file_location("bairroiq_prioridade_para_star", str(PRIORIDADE))
    require(spec is not None and spec.loader is not None, "Modulo de prioridade invalido")
    priority = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(priority)
    v3 = priority.load_v3()
    ml = v3.load_v2()
    config = v3.load_config(CATALOGO_CONFIG)
    cols = [*ml.IDENTIFIERS, *ml.SOURCE_FIELDS.values()]
    raw = spark_session.table(ml.SOURCE_TABLE).select(*cols).toPandas()
    raw = raw.rename(columns={source: alias for alias, source in ml.SOURCE_FIELDS.items()})

    # A v3 resolve NM_DIST pelo CD_DIST usando a referencia oficial IBGE.
    # A dimensao de distritos precisa usar exatamente a mesma convencao:
    # nao compare o texto bruto da Gold com o nome ja canonizado na v3.
    # Preserva todos os guardrails de codigo, hash e composicao do ML.
    raw = ml.validate_and_prepare(raw)

    resultados = priority.build_priority(raw)
    return build_preview(raw, resultados, ml.SOURCE_FIELDS,
                         config["sha256_gold_esperado"])


def export_local(preview: dict[str, Any], output_dir: str | Path) -> None:
    """Escreve apenas CSV/JSON em caminho LOCAL explicito, nunca Delta/DBFS."""
    out = Path(output_dir)
    require(out.is_absolute() and str(out).startswith("/tmp/"),
            "Exportacao somente para /tmp/ local")
    out.mkdir(parents=True, exist_ok=True)
    for name, frame in preview["tabelas"].items():
        frame.to_csv(out / f"{name}.csv", index=False, encoding="utf-8-sig")
    (out / "resumo_star_schema_v1.json").write_text(
        json.dumps(preview["resumo"], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
