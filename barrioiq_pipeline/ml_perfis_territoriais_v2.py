"""BairroIQ | ML v2: perfis territoriais explicaveis para escolha pelo usuario.

Sem escrita em tabelas, sem labels de qualidade de vida, sem ranking.
Fonte: workspace.gold.distritos_wide. Requer 96 distritos e 11 indicadores.
Compara K-Means e Ward em k=2..12; prepara perfis exploratorios para k=8,9,10.
Resultado exploratorio NAO e publicacao nem recomendacao validada.
"""
from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.metrics import (
    adjusted_rand_score,
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_samples,
    silhouette_score,
)
from sklearn.preprocessing import StandardScaler

SOURCE_TABLE = "workspace.gold.distritos_wide"
REFERENCE = Path(__file__).resolve().with_name("distritos_centroides_ibge_2022.json")
N_DISTRICTS = 96
K_RANGE = tuple(range(2, 13))
PRODUCT_K = (8, 9, 10)
METHODS = ("kmeans", "ward")
RANDOM_STATE = 42
MIN_GROUP_OPERATIONAL = 3  # criterio operacional, nao verdade cientifica
MAX_GROUP_FRACTION = 0.50  # guardrail de utilidade exploratorio
N_RESAMPLES = 40
FRACTION = 0.8
MODEL_VERSION = "v2.0.0-exploratorio"

# Nomes de origem auditados no dicionario da Gold. Nao inventar colunas.
SOURCE_FIELDS = {
    "empregos": "obs_empregos_formais_no_municipio_total_86858d5b",
    "roubos": "ssp_registros_12m_roubo_art_157_41b94022_por_100mil_hab",
    "furtos": "ssp_registros_12m_furto_art_155_2c3ca8b1_por_100mil_hab",
    "metro": "geo_qtd_metro_por_10mil_hab",
    "onibus": "geo_qtd_onibus_por_10mil_hab",
    "trem": "geo_qtd_trem_por_10mil_hab",
    "pracas": "geo_qtd_praca_largo_por_10mil_hab",
    "corredores_verdes": "geo_qtd_corredor_verde_por_10mil_hab",
    "escolas": "geo_qtd_escolas_publicas_por_10mil_hab",
    "ubs": "geo_qtd_ubs_por_10mil_hab",
    "densidade": "densidade_habitantes_km2",
}
IDENTIFIERS = ("CD_DIST", "NM_DIST", "latitude", "longitude")
RAW_COLUMNS = (*IDENTIFIERS, *SOURCE_FIELDS)
AXES = (
    "atividade", "ocorrencias", "mobilidade",
    "verde_lazer", "servicos_publicos", "densidade",
)
LABELS = {
    "atividade": ("Indicador de empregos formais mais elevado", "Indicador de empregos formais mais baixo"),
    "ocorrencias": ("Mais ocorrências registradas", "Menos ocorrências registradas"),
    "mobilidade": ("Mais equipamentos de transporte por habitante", "Menos equipamentos de transporte por habitante"),
    "verde_lazer": ("Mais praças e corredores verdes", "Menos praças e corredores verdes"),
    "servicos_publicos": ("Mais escolas e UBS por habitante", "Menos escolas e UBS por habitante"),
    "densidade": ("Maior densidade populacional", "Menor densidade populacional"),
}
DISCLAIMERS = (
    "Os perfis sao semelhantes estatisticamente; nao sao rankings de qualidade de vida.",
    "Empregos: indicador denominado 'no municipio'; a granularidade requer auditoria semantica.",
    "Corredores verdes e pracas nao equivalem a cobertura arborea.",
    "Registros de crimes patrimoniais nao equivalem a risco individual.",
    "Transporte por habitante nao informa tempo de deslocamento.",
    "Custo de vida nao e medido neste modelo.",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError("BAIRROIQ_ML_V2_CONTRACT_FAILED: " + message)


def validate_and_prepare(frame: pd.DataFrame, reference: Path | None = None) -> pd.DataFrame:
    missing = [c for c in RAW_COLUMNS if c not in frame]
    require(not missing, f"Colunas ausentes: {missing}")
    data = frame.loc[:, RAW_COLUMNS].copy()
    require(len(data) == N_DISTRICTS, "A Gold deve possuir exatamente 96 distritos")
    require(data.CD_DIST.notna().all() and data.CD_DIST.nunique() == N_DISTRICTS,
            "CD_DIST nulo ou duplicado")
    require(data.NM_DIST.notna().all() and data.NM_DIST.astype(str).str.strip().ne("").all(),
            "NM_DIST vazio")
    for col in ("CD_DIST", "latitude", "longitude", *SOURCE_FIELDS):
        data[col] = pd.to_numeric(data[col], errors="coerce")
    require(data[["CD_DIST", "latitude", "longitude", *SOURCE_FIELDS]].notna().all().all(),
            "Codigo, coordenadas ou indicadores nulos/nao numericos")
    require(np.isfinite(data[["latitude", "longitude", *SOURCE_FIELDS]].to_numpy(dtype=float)).all(),
            "Indicadores ou coordenadas infinitos")
    require((data[list(SOURCE_FIELDS)] >= 0).all().all(), "Indicadores negativos inesperados")
    require(data.latitude.between(-24, -23).all() and data.longitude.between(-47, -46).all(),
            "Coordenadas fora da area de Sao Paulo")
    require((data.CD_DIST % 1 == 0).all(), "Codigos distritais nao inteiros")
    data.CD_DIST = data.CD_DIST.astype("int64")
    data = data.sort_values("CD_DIST").reset_index(drop=True)
    reference = REFERENCE if reference is None else reference
    if reference.is_file():
        obj = json.loads(reference.read_text(encoding="utf-8"))
        mapping = {int(d["CD_DIST"]): d["NM_DIST"] for d in obj["distritos"]}
        require(len(mapping) == N_DISTRICTS and set(mapping) == set(data.CD_DIST),
                "Referencia oficial IBGE nao cobre os 96 distritos")
        data.NM_DIST = data.CD_DIST.map(mapping)
    else:
        require(not data.NM_DIST.astype(str).str.contains("\ufffd", regex=False).any(),
                "Nomes corrompidos e referencia IBGE ausente")
    return data


def z(df: pd.DataFrame) -> np.ndarray:
    require(all(df[c].nunique() > 1 for c in df),
            "Uma ou mais dimensoes nao possuem variacao")
    return StandardScaler().fit_transform(df)


def features(data: pd.DataFrame, without_axis: str | None = None) -> tuple[np.ndarray, pd.DataFrame]:
    if without_axis is not None:
        require(without_axis in AXES, "Eixo desconhecido: " + str(without_axis))
    # Escala individual antes de combinar indicadores na mesma dimensao.
    crime = z(pd.DataFrame({
        "roubos": np.log1p(data.roubos), "furtos": np.log1p(data.furtos)
    })).mean(axis=1)
    transport = z(pd.DataFrame({
        key: np.log1p(data[key]) for key in ("metro", "onibus", "trem")
    })).mean(axis=1)
    green = z(pd.DataFrame({
        key: np.log1p(data[key]) for key in ("pracas", "corredores_verdes")
    })).mean(axis=1)
    public = z(pd.DataFrame({
        key: np.log1p(data[key]) for key in ("escolas", "ubs")
    })).mean(axis=1)
    axes = pd.DataFrame({
        "atividade": np.log1p(data.empregos.to_numpy()),
        "ocorrencias": crime,
        "mobilidade": transport,
        "verde_lazer": green,
        "servicos_publicos": public,
        "densidade": np.log1p(data.densidade.to_numpy()),
    })
    if without_axis is not None:
        axes = axes.drop(columns=without_axis)
    X = z(axes)
    require(np.isfinite(X).all(), "Variaveis transformadas invalidas")
    return X, axes


def predict(method: str, X: np.ndarray, k: int) -> np.ndarray:
    require(method in METHODS, f"Metodo invalido: {method}")
    require(2 <= k < len(X), "K fora da faixa valida")
    if method == "kmeans":
        return KMeans(n_clusters=k, random_state=RANDOM_STATE,
                      n_init=20, max_iter=500).fit_predict(X)
    return AgglomerativeClustering(n_clusters=k, linkage="ward").fit_predict(X)


def metrics(X: np.ndarray, labels: np.ndarray) -> dict[str, Any]:
    sizes = sorted(int(n) for n in np.unique(labels, return_counts=True)[1])
    share = max(sizes) / len(labels)
    silhouette_individual = silhouette_samples(X, labels)
    return {
        "silhouette": round(float(silhouette_score(X, labels)), 6),
        "davies_bouldin": round(float(davies_bouldin_score(X, labels)), 6),
        "calinski_harabasz": round(float(calinski_harabasz_score(X, labels)), 6),
        "menor_grupo": min(sizes),
        "maior_grupo": max(sizes),
        "maior_grupo_pct": round(100 * share, 4),
        "distribuicao": sizes,
        "grupos_unitarios": sizes.count(1),
        "grupos_ate_2": sum(n <= 2 for n in sizes),
        "silhouette_negativa_pct": round(float(100 * np.mean(silhouette_individual < 0)), 4),
        "elegivel_operacional": min(sizes) >= MIN_GROUP_OPERATIONAL and share <= MAX_GROUP_FRACTION,
    }


def stability(data: pd.DataFrame, baseline: np.ndarray, method: str, k: int,
              repetitions: int = N_RESAMPLES) -> dict[str, float | int]:
    require(repetitions > 0, "Repeticoes de estabilidade devem ser positivas")
    rng = np.random.default_rng(RANDOM_STATE)
    scores = []
    n = len(data)
    n_sample = int(n * FRACTION)
    for _ in range(repetitions):
        indices = np.sort(rng.choice(n, size=n_sample, replace=False))
        sub = data.iloc[indices].reset_index(drop=True)
        X, _ = features(sub)
        scores.append(float(adjusted_rand_score(baseline[indices], predict(method, X, k))))
    return {"reamostragens": repetitions, "fracao": FRACTION,
            "ari_mediana": round(float(np.median(scores)), 6),
            "ari_p10": round(float(np.quantile(scores, 0.1)), 6)}


def sensitivity(data: pd.DataFrame, labels: np.ndarray, method: str, k: int) -> dict[str, float]:
    out = {}
    for axis in AXES:
        X, _ = features(data, without_axis=axis)
        out[axis] = round(float(adjusted_rand_score(labels, predict(method, X, k))), 6)
    return out


def stable_ids(labels: np.ndarray, data: pd.DataFrame) -> np.ndarray:
    """Ordenacao deterministica sem significar qualidade ou preferencia."""
    order = sorted(np.unique(labels), key=lambda label: (
        int(data.loc[labels == label, "CD_DIST"].min())
    ))
    mapping = {value: i + 1 for i, value in enumerate(order)}
    return np.asarray([mapping[v] for v in labels], dtype=int)


def explain_profiles(data: pd.DataFrame, X: np.ndarray, labels: np.ndarray,
                     method: str, k: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    ids = stable_ids(labels, data)
    profile_rows = []
    assignment_rows = []
    used = set()
    for cluster in sorted(set(ids)):
        chosen = ids == cluster
        medians = np.median(X[chosen], axis=0)
        strongest = np.argsort(-np.abs(medians))
        # Duas dimensoes mais distintas, com diferenca absoluta >=0.35 DP;
        # um eixo alternativo e utilizado quando o perfil e pouco contrastante.
        qualifying = [i for i in strongest if abs(medians[i]) >= 0.35][:2]
        if not qualifying:
            qualifying = [int(strongest[0])]
        terms = [LABELS[AXES[i]][0 if medians[i] > 0 else 1] for i in qualifying]
        name = " / ".join(terms)
        if name in used:
            name += f" (perfil {cluster:02d})"
        used.add(name)
        evidence = []
        for index in strongest[:3]:
            axis = AXES[index]
            evidence.append({"eixo": axis,
                             "mediana_z": round(float(medians[index]), 4),
                             "direcao": "acima" if medians[index] > 0 else "abaixo"})
        warnings = []
        if sum(chosen) <= 2:
            warnings.append("GRUPO_DE_ATE_2_DISTRITOS")
        if sum(chosen) == 1:
            warnings.append("PERFIL_SINGULAR_REVISAR_OUTLIER")
        warnings.append("NOME_PROVISORIO_SUJEITO_A_VALIDACAO_HUMANA")
        pid = f"{method}-k{k:02d}-p{cluster:02d}"
        example = data.loc[chosen]
        row = {
            "perfil_id": pid, "metodo": method, "k": k,
            "cluster_id": int(cluster), "perfil_nome_provisorio": name,
            "perfil_descricao_provisoria": (
                "Perfil territorial com destaque relativo em " + ", ".join(terms)
                + ". Caracteristicas referentes ao conjunto de 96 distritos, nao a uma nota geral."
            ),
            "qtd_distritos": int(sum(chosen)),
            "evidencias_json": json.dumps(evidence, ensure_ascii=False),
            "alertas_json": json.dumps(warnings, ensure_ascii=False),
            "status": "EXPLORATORIO_NAO_HOMOLOGADO",
            "modelo_versao": MODEL_VERSION,
        }
        for col in SOURCE_FIELDS:
            row[f"mediana_{col}"] = round(float(example[col].median()), 6)
        profile_rows.append(row)
        for _, district in example.iterrows():
            assignment_rows.append({
                "CD_DIST": int(district.CD_DIST), "NM_DIST": district.NM_DIST,
                "latitude": float(district.latitude), "longitude": float(district.longitude),
                "metodo": method, "k": k, "cluster_id": int(cluster),
                "perfil_id": pid, "perfil_nome_provisorio": name,
                "modelo_versao": MODEL_VERSION,
                "status": "EXPLORATORIO_NAO_HOMOLOGADO",
            })
    return pd.DataFrame(profile_rows), pd.DataFrame(assignment_rows)


def fingerprint(data: pd.DataFrame) -> str:
    csv = data.loc[:, RAW_COLUMNS].to_csv(index=False, float_format="%.12g")
    return hashlib.sha256(csv.encode("utf-8")).hexdigest()


def compare(raw: pd.DataFrame, repetitions: int = N_RESAMPLES,
            reference: Path | None = None) -> dict[str, Any]:
    data = validate_and_prepare(raw, reference=reference)
    X, axes = features(data)
    evaluation_rows, all_labels = [], {}
    for method in METHODS:
        for k in K_RANGE:
            labels = predict(method, X, k)
            all_labels[method, k] = labels
            evaluation_rows.append({"metodo": method, "k": k, **metrics(X, labels)})
    evaluation = pd.DataFrame(evaluation_rows)
    selected, profiles, assignments = [], [], []
    for method in METHODS:
        candidate = evaluation[
            (evaluation.metodo == method) & (evaluation.k.isin(PRODUCT_K))
            & evaluation.elegivel_operacional
        ].sort_values(["k", "silhouette"], ascending=[False, False])
        # Se nao passar no guardrail: nao homologar nenhuma opcao automaticamente.
        candidate_k = int(candidate.iloc[0]["k"]) if not candidate.empty else None
        for k in PRODUCT_K:
            labels = all_labels[method, k]
            m = metrics(X, labels)
            prof, assign = explain_profiles(data, X, labels, method, k)
            profiles.append(prof)
            assignments.append(assign)
            selected.append({
                "metodo": method, "k": k,
                "candidato_operacional": k == candidate_k,
                "guardrail_aceito": m["elegivel_operacional"],
                "metricas": m,
                "estabilidade": stability(data, labels, method, k, repetitions),
                "sensibilidade_ari": sensitivity(data, labels, method, k),
                "status_publicacao": "PENDENTE_SEMANTICA_INTERPRETACAO_APROVACAO",
            })
    return {
        "metricas": evaluation,
        "perfis": pd.concat(profiles, ignore_index=True),
        "atribuicoes": pd.concat(assignments, ignore_index=True),
        "eixos": axes,
        "resumo": {
            "experimento": "BAIRROIQ_ML_PERFIS_V2",
            "modelo_versao": MODEL_VERSION,
            "fonte": SOURCE_TABLE,
            "distritos": len(data),
            "sha256_gold": fingerprint(data),
            "campos_origem": SOURCE_FIELDS,
            "eixos": AXES,
            "algoritmos": METHODS,
            "k_testados": K_RANGE,
            "k_alvo_produto": PRODUCT_K,
            "minimo_operacional_por_grupo": MIN_GROUP_OPERATIONAL,
            "maximo_operacional_fracao": MAX_GROUP_FRACTION,
            "metodologia_selecao": "preferir K mais proximo de 10 entre candidatos com min 3 e maior grupo <= 50%; nenhuma homologacao automatica",
            "variacoes": selected,
            "versoes": {"python": platform.python_version(), "numpy": np.__version__,
                        "pandas": pd.__version__, "sklearn": sklearn.__version__},
            "ressalvas": DISCLAIMERS,
            "status": "EXPLORATORIO_NAO_HOMOLOGADO",
            "alteracoes_gold": "NENHUMA",
        },
    }


def run_from_spark(spark_session: Any, repetitions: int = N_RESAMPLES) -> dict[str, Any]:
    selected = [*IDENTIFIERS, *SOURCE_FIELDS.values()]
    frame = spark_session.table(SOURCE_TABLE).select(*selected).toPandas()
    frame = frame.rename(columns={actual: alias for alias, actual in SOURCE_FIELDS.items()})
    result = compare(frame, repetitions=repetitions)
    result["resumo"]["origem_execucao"] = "GOLD_DATABRICKS_DIRETO"
    return result


def export(results: dict[str, Any], output_dir: str | Path) -> None:
    """Exporta apenas arquivos locais, sem publicar nenhuma tabela Delta."""
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    results["metricas"].to_csv(path / "metricas_v2.csv", index=False)
    results["perfis"].to_csv(path / "perfis_v2.csv", index=False, encoding="utf-8-sig")
    results["atribuicoes"].to_csv(path / "distritos_perfis_v2.csv", index=False, encoding="utf-8-sig")
    (path / "resumo_v2.json").write_text(
        json.dumps(results["resumo"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
