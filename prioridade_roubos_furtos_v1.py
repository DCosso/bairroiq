"""BairroIQ | Preferencia de busca: menores registros de roubos e furtos.

A classificacao dos 9 clusters NAO e alterada. A prioridade funciona em TODOS os
96 distritos, antes ou depois da escolha do perfil territorial.

ATENCAO: taxas de ocorrencias registradas nao sao notas de seguranca, risco
individual, recomendacao de residencia, nem previsoes de violencia. Somente
comparacao relativa com a fotografia auditada da Gold, sem gravar tabelas.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
V3_PATH = BASE / "ml_catalogo_perfis_v3.py"
N_DISTRICTS = 96
P04_ID = "kmeans-k09-p04"
P04_MIN_SHARE_BOTH_BELOW = 0.60  # criterio editorial, nao medida cientifica
PRIORITY_ID = "menos_roubos_furtos"
STATUS = "EXPLORATORIO_NAO_HOMOLOGADO"
DISCLAIMER = (
    "Comparacao das taxas de registros de roubo e furto por 100 mil habitantes; "
    "nao mede seguranca individual, subnotificacao, outros crimes ou risco futuro. "
    "A cobertura temporal e o tratamento das ocorrencias devem ser mostrados na interface."
)


def require(valid: bool, message: str) -> None:
    if not valid:
        raise ValueError("BAIRROIQ_PREFERENCIA_OCORRENCIAS_BLOCKED: " + message)


def load_v3():
    require(V3_PATH.is_file(), f"Modulo v3 nao encontrado: {V3_PATH}")
    spec = importlib.util.spec_from_file_location("bairroiq_catalogo_v3_seguranca", str(V3_PATH))
    require(spec is not None and spec.loader is not None, "Falha ao importar catalogo v3")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ensure_valid_rates(data: pd.DataFrame) -> pd.DataFrame:
    required = ("CD_DIST", "NM_DIST", "roubos", "furtos")
    missing = [name for name in required if name not in data]
    require(not missing, "Campos obrigatorios ausentes: " + str(missing))
    frame = data.loc[:, required].copy()
    require(len(frame) == N_DISTRICTS, "Esperados 96 distritos")
    require(frame.CD_DIST.notna().all() and frame.CD_DIST.nunique() == N_DISTRICTS,
            "CD_DIST nulo ou repetido")
    for name in ("roubos", "furtos"):
        frame[name] = pd.to_numeric(frame[name], errors="coerce")
    require(frame[["roubos", "furtos"]].notna().all().all(),
            "Taxas de roubo/furto nulas ou nao numericas")
    require(np.isfinite(frame[["roubos", "furtos"]].to_numpy(dtype=float)).all(),
            "Taxas de roubo/furto nao finitas")
    require((frame[["roubos", "furtos"]] >= 0).all().all(),
            "Taxas de roubo/furto negativas")
    require(frame.NM_DIST.notna().all(), "Nome de distrito nulo")
    return frame.sort_values("CD_DIST").reset_index(drop=True)


def audit_p04(crime: pd.DataFrame, p04_codes: list[int]) -> dict[str, Any]:
    """Nao homologa nenhum nome; so produz evidencia da condicao editorial.

    A comparacao e entre medianas distritais nao ponderadas de taxas por 100 mil.
    Cada distrito e uma observacao, nao um habitante. Taxas agregadas municipais
    exigem contagens originais e denominadores, nao calculados por media simples.
    """
    data = _ensure_valid_rates(crime)
    codes = set(int(x) for x in p04_codes)
    require(len(codes) >= 3 and codes.issubset(set(data.CD_DIST.astype(int))),
            "Codigos do P04 invalidos")
    members = data[data.CD_DIST.isin(codes)]
    require(len(members) == len(codes), "P04 sem correspondencia exata")
    medians_all = data[["roubos", "furtos"]].median()
    medians_p04 = members[["roubos", "furtos"]].median()
    both_below = (
        (members.roubos < medians_all["roubos"]) &
        (members.furtos < medians_all["furtos"])
    )
    share = float(both_below.mean())
    # Evita o rotulo quando ha casos que parecem baixos somente no eixo medio.
    cond = bool(
        medians_p04["roubos"] < medians_all["roubos"]
        and medians_p04["furtos"] < medians_all["furtos"]
        and share >= P04_MIN_SHARE_BOTH_BELOW
    )
    return {
        "perfil_id": P04_ID,
        "mediana_roubos_96": round(float(medians_all["roubos"]), 6),
        "mediana_furtos_96": round(float(medians_all["furtos"]), 6),
        "mediana_roubos_p04": round(float(medians_p04["roubos"]), 6),
        "mediana_furtos_p04": round(float(medians_p04["furtos"]), 6),
        "distritos_p04": len(members),
        "distritos_ambos_abaixo_mediana_96": int(both_below.sum()),
        "fracao_ambos_abaixo_mediana_96": round(share, 6),
        "condicao_editorial_atendida": cond,
        "nome_homologado": False,
        "referencia_comparacao": "Mediana dos 96 distritos (nao taxa agregada municipal)",
    }


def build_priority(raw: pd.DataFrame, config: dict[str, Any] | None = None,
                   reference: str | Path | None = None) -> dict[str, Any]:
    """Reproduz v3 e calcula ordem relativa independente do perfil escolhido."""
    v3 = load_v3()
    config = v3.load_config() if config is None else config
    base = v3.build_catalog(raw, config=config, reference=reference)
    ml = v3.load_v2()
    data = ml.validate_and_prepare(
        raw, reference=Path(reference) if reference is not None else None
    )
    crime = _ensure_valid_rates(data)

    # A v3 ja bloqueou qualquer mudanca de hash e composicao territorial.
    districts = base["distritos"]
    require(len(districts) == N_DISTRICTS and districts.CD_DIST.nunique() == N_DISTRICTS,
            "Catalogo sem 96 distritos unicos")
    enriched = districts.merge(crime[["CD_DIST", "roubos", "furtos"]], on="CD_DIST",
                               how="inner", validate="one_to_one")
    require(len(enriched) == N_DISTRICTS, "Chaves de ocorrencias nao cobrem o catalogo")

    # Rankings sao internos aos 96 distritos, com peso 50/50; nunca uma nota
    # universal de 'seguranca'. Taxas originais seguem no resultado para auditoria.
    enriched["percentil_relativo_roubos_0a100"] = (
        enriched.roubos.rank(method="average", pct=True) * 100
    ).round(2)
    enriched["percentil_relativo_furtos_0a100"] = (
        enriched.furtos.rank(method="average", pct=True) * 100
    ).round(2)
    enriched["indice_ordenacao_ocorrencias"] = (
        enriched["percentil_relativo_roubos_0a100"] +
        enriched["percentil_relativo_furtos_0a100"]
    ) / 2
    enriched["pior_percentil_entre_roubo_e_furto"] = enriched[[
        "percentil_relativo_roubos_0a100", "percentil_relativo_furtos_0a100"
    ]].max(axis=1)
    enriched = enriched.sort_values(
        ["indice_ordenacao_ocorrencias", "pior_percentil_entre_roubo_e_furto", "CD_DIST"],
        ascending=[True, True, True], kind="stable"
    ).reset_index(drop=True)
    enriched["posicao_relativa_entre_96"] = np.arange(1, N_DISTRICTS + 1, dtype=int)
    enriched["prioridade_id"] = PRIORITY_ID
    enriched["criterio_comparacao"] = "Menores taxas registradas de roubos e furtos (peso igual)"
    enriched["status_prioridade"] = STATUS

    p04 = next((p for p in config["perfis"] if p.get("cluster_id") == 4), None)
    require(p04 is not None, "Perfil P04 nao encontrado")
    audit = audit_p04(crime, p04["distritos_cd_dist"])
    catalog = base["catalogo"].copy()
    catalog["nome_exibicao_proposto"] = catalog["nome_provisorio"]
    # O nome de crimes so e sugerido quando os DOIS indicadores passam; de todo
    # modo permanece candidato editorial e requer revisao humana posterior.
    conditional_name = p04.get("nome_alternativo_condicional", "Menos Roubos e Furtos")
    if audit["condicao_editorial_atendida"]:
        catalog.loc[catalog.perfil_id == P04_ID, "nome_exibicao_proposto"] = conditional_name
    catalog["nome_validado_para_publicacao"] = False
    catalog["ressalva_ocorrencias"] = DISCLAIMER

    return {
        "catalogo": catalog,
        "distritos_priorizados": enriched,
        "auditoria_p04": audit,
        "resumo": {
            "fonte": ml.SOURCE_TABLE,
            "sha256_gold": base["resumo"]["sha256_gold"],
            "catalogo_versao": base["resumo"]["versao"],
            "criterio": "50% percentil relativo de roubos + 50% percentil relativo de furtos",
            "universo_comparacao": "96 distritos oficiais, taxas registradas por 100 mil habitantes",
            "prioridade_id": PRIORITY_ID,
            "aviso": DISCLAIMER,
            "perfil_04_apto_a_revisao_do_nome": audit["condicao_editorial_atendida"],
            "status": STATUS,
            "publicacao_gold_autorizada": False,
            "alteracoes_gold": "NENHUMA",
        },
    }


def filter_priority(results: dict[str, Any], perfil_id: str | None = None,
                    limit: int | None = 20) -> pd.DataFrame:
    """Filtra por perfil SEM refazer o ranking global dos 96 distritos."""
    require(results.get("resumo", {}).get("status") == STATUS,
            "Resultado nao esta em modo exploratorio")
    frame = results["distritos_priorizados"]
    if perfil_id is not None:
        valid = set(results["catalogo"].perfil_id)
        require(perfil_id in valid, "Perfil desconhecido")
        frame = frame[frame.perfil_id == perfil_id]
    if limit is not None:
        require(type(limit) is int and limit > 0, "Limite invalido")
        frame = frame.head(limit)
    return frame.reset_index(drop=True).copy()


def run_from_spark(spark_session: Any) -> dict[str, Any]:
    """Consulta uma unica fotografia dos 96 distritos, sem gravacao Spark."""
    v3 = load_v3()
    ml = v3.load_v2()
    cols = [*ml.IDENTIFIERS, *ml.SOURCE_FIELDS.values()]
    raw = spark_session.table(ml.SOURCE_TABLE).select(*cols).toPandas()
    raw = raw.rename(columns={source: alias for alias, source in ml.SOURCE_FIELDS.items()})
    results = build_priority(raw)
    results["resumo"]["origem_execucao"] = "GOLD_DATABRICKS_DIRETO"
    return results


def export(results: dict[str, Any], output_dir: str | Path) -> None:
    """Exporta arquivos locais, nunca altera a Gold."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    results["catalogo"].to_csv(out / "catalogo_com_prioridade_ocorrencias.csv", index=False, encoding="utf-8-sig")
    results["distritos_priorizados"].to_csv(out / "distritos_prioridade_ocorrencias.csv", index=False, encoding="utf-8-sig")
    (out / "auditoria_nome_p04.json").write_text(
        json.dumps(results["auditoria_p04"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out / "resumo_prioridade_ocorrencias.json").write_text(
        json.dumps(results["resumo"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
