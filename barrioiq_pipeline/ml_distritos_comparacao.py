"""BairroIQ | Experimento reproduzivel: K-Means x Aglomerativo Ward.

Apenas leitura dos dados. Nao executa CREATE/INSERT/MERGE/OVERWRITE.
Usos:
  # Em notebook Databricks, apos importar este modulo da branch do projeto:
  resultado = run_from_spark(spark)
  print(resultado['resumo'])

  # Em uma maquina local usando os dados do experimento exploratorio:
  python ml_distritos_comparacao.py --csv distritos_classificados.csv --output-dir ./resultados

Requer numpy, pandas, scikit-learn; para Databricks requer PySpark.
"""

from __future__ import annotations

import argparse
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
    silhouette_score,
)
from sklearn.preprocessing import StandardScaler


SOURCE_TABLE = "workspace.gold.distritos_wide"
GEO_REFERENCE = Path(__file__).resolve().with_name("distritos_centroides_ibge_2022.json")
N_DISTRICTS = 96
K_VALUES = range(2, 13)
TARGET_K = 10
MIN_CLUSTER = 5
SEED = 42
N_RESAMPLES = 100
SAMPLE_FRACTION = 0.8

# Contrato de schema auditado em docs/dicionario_gold_distritos_wide.json.
SOURCE_FIELDS = {
    "empregos": "obs_empregos_formais_no_municipio_total_86858d5b",
    "roubos": "ssp_registros_12m_roubo_art_157_41b94022_por_100mil_hab",
    "corredores_verdes": "geo_qtd_corredor_verde_por_10mil_hab",
    "metro": "geo_qtd_metro_por_10mil_hab",
    "onibus": "geo_qtd_onibus_por_10mil_hab",
    "trem": "geo_qtd_trem_por_10mil_hab",
}
RAW_COLUMNS = ("CD_DIST", "NM_DIST", "latitude", "longitude", *SOURCE_FIELDS)
FEATURE_AXES = ("empregos", "roubos", "verde", "mobilidade")
METHODS = ("kmeans", "ward")


def fail(message: str) -> None:
    raise ValueError("BAIRROIQ_ML_CONTRACT_FAILED: " + message)


def validate_data(data: pd.DataFrame) -> pd.DataFrame:
    """Valida contrato sem inventar dados nem imputar nulos."""
    missing = [c for c in RAW_COLUMNS if c not in data.columns]
    if missing:
        fail("Colunas ausentes: " + ", ".join(missing))

    frame = data.loc[:, RAW_COLUMNS].copy()
    if len(frame) != N_DISTRICTS:
        fail(f"Esperados {N_DISTRICTS} distritos; recebidos {len(frame)}")
    if frame.CD_DIST.isna().any() or frame.CD_DIST.nunique() != N_DISTRICTS:
        fail("CD_DIST deve ser nao nulo e unico")
    if frame.NM_DIST.isna().any() or (frame.NM_DIST.astype(str).str.strip() == "").any():
        fail("Nome distrital nulo ou vazio")

    numeric = ["latitude", "longitude", *SOURCE_FIELDS]
    for col in numeric:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    if frame[numeric].isna().any().any():
        fail("Indicadores/coordenadas com nulos: " + str(frame[numeric].isna().sum().to_dict()))
    if not np.isfinite(frame[numeric].to_numpy(dtype=float)).all():
        fail("Indicadores/coordenadas possuem NaN ou infinito")
    if not frame.latitude.between(-24.0, -23.0).all() or not frame.longitude.between(-47.0, -46.0).all():
        fail("Coordenadas fora da faixa de Sao Paulo")
    if (frame[list(SOURCE_FIELDS)] < 0).any().any():
        fail("Indicadores negativos inesperados")

    frame["CD_DIST"] = frame.CD_DIST.astype("int64")
    return frame.sort_values("CD_DIST").reset_index(drop=True)


def official_district_names(data: pd.DataFrame, reference: Path | None = None) -> pd.DataFrame:
    """Corrige nomes pela chave CD_DIST, nunca por similaridade textual.

    O JSON oficial ja existe no repositorio, junto do runner de ML.
    Se indisponivel, bloqueia somente nomes corrompidos: nao adivinha.
    """
    reference = reference if reference is not None else GEO_REFERENCE
    if not reference.is_file():
        if data["NM_DIST"].astype(str).str.contains("\ufffd", regex=False).any():
            fail(f"Nomes corrompidos e referencia IBGE ausente: {reference}")
        return data.copy()
    raw = json.loads(reference.read_text(encoding="utf-8"))
    rows = raw.get("distritos", [])
    mapping = {int(row["CD_DIST"]): str(row["NM_DIST"]) for row in rows}
    if len(mapping) != N_DISTRICTS or set(mapping) != set(data.CD_DIST):
        fail("Referencia IBGE nao cobre exatamente os 96 codigos da Gold")
    out = data.copy()
    out["NM_DIST"] = out.CD_DIST.map(mapping)
    return out


def prepare_axes(data: pd.DataFrame, excluded: str | None = None) -> tuple[np.ndarray, pd.DataFrame]:
    """Mesmo pre-processamento para ambos os modelos.

    1. log1p em empregos e taxa de roubos, reduzindo a influencia de extremos;
    2. z-score individual nos tres indicadores de transporte;
    3. media simples dos tres z-scores = uma unica dimensao mobilidade;
    4. z-score final em todas as dimensoes selecionadas.
    O objeto StandardScaler e ajustado novamente a cada subamostra em estabilidade.
    """
    if excluded is not None and excluded not in FEATURE_AXES:
        fail(f"Dimensao desconhecida para ablation: {excluded}")

    transport = StandardScaler().fit_transform(data[["metro", "onibus", "trem"]])
    axes = pd.DataFrame(
        {
            "empregos": np.log1p(data["empregos"].to_numpy(dtype=float)),
            "roubos": np.log1p(data["roubos"].to_numpy(dtype=float)),
            "verde": data["corredores_verdes"].to_numpy(dtype=float),
            "mobilidade": transport.mean(axis=1),
        }
    )
    if excluded is not None:
        axes = axes.drop(columns=excluded)
    if (axes.nunique() <= 1).any():
        fail("Dimensao sem variacao: " + str(axes.nunique().to_dict()))
    x = StandardScaler().fit_transform(axes)
    if not np.isfinite(x).all():
        fail("Features transformadas invalidas")
    return x, axes


def fit_labels(method: str, x: np.ndarray, k: int) -> np.ndarray:
    if method == "kmeans":
        model = KMeans(n_clusters=k, random_state=SEED, n_init=20, max_iter=500)
    elif method == "ward":
        model = AgglomerativeClustering(n_clusters=k, linkage="ward")
    else:
        fail(f"Metodo desconhecido: {method}")
    return model.fit_predict(x)


def evaluate_labels(x: np.ndarray, labels: np.ndarray) -> dict[str, Any]:
    group_sizes = sorted(int(n) for n in np.bincount(labels) if n > 0)
    return {
        "silhouette": round(float(silhouette_score(x, labels)), 6),
        "davies_bouldin": round(float(davies_bouldin_score(x, labels)), 6),
        "calinski_harabasz": round(float(calinski_harabasz_score(x, labels)), 6),
        "menor_grupo": min(group_sizes),
        "maior_grupo": max(group_sizes),
        "maior_grupo_pct": round(100 * max(group_sizes) / len(labels), 4),
        "distribuicao": group_sizes,
        "elegivel_min_5": min(group_sizes) >= MIN_CLUSTER,
        "grupos_unitarios": group_sizes.count(1),
        "grupos_ate_2": sum(size <= 2 for size in group_sizes),
    }


def choose_k(df: pd.DataFrame, method: str) -> int:
    """Criterio exploratorio: Silhouette maximo sujeito a min 5 por grupo."""
    eligible = df[(df.metodo == method) & (df.elegivel_min_5)]
    if eligible.empty:
        fail(f"Nenhuma configuracao elegivel para {method}")
    return int(eligible.sort_values(["silhouette", "k"], ascending=[False, True]).iloc[0]["k"])


def subsample_stability(data: pd.DataFrame, baseline: np.ndarray, method: str, k: int) -> dict:
    """Comparacao com a classificacao base na mesma subamostra (ARI).

    Amostragem sem reposicao, 80% das observacoes, com recomputacao dos
    scalers. Mede sensibilidade a composicao da amostra; nao mede acuracia.
    """
    rng = np.random.default_rng(SEED)
    n = len(data)
    sample_size = int(n * SAMPLE_FRACTION)
    scores = []
    for _ in range(N_RESAMPLES):
        indices = np.sort(rng.choice(n, size=sample_size, replace=False))
        subsample = data.iloc[indices].reset_index(drop=True)
        x_sub, _ = prepare_axes(subsample)
        alternative = fit_labels(method, x_sub, k)
        scores.append(float(adjusted_rand_score(baseline[indices], alternative)))
    return {
        "amostras": N_RESAMPLES,
        "fracao_amostra": SAMPLE_FRACTION,
        "ari_mediana": round(float(np.median(scores)), 6),
        "ari_media": round(float(np.mean(scores)), 6),
        "ari_p10": round(float(np.quantile(scores, 0.1)), 6),
        "ari_p90": round(float(np.quantile(scores, 0.9)), 6),
    }


def ablation_sensitivity(data: pd.DataFrame, baseline: np.ndarray, method: str, k: int) -> dict:
    """Retira uma dimensao por vez e mede ARI contra o modelo original."""
    result = {}
    for axis in FEATURE_AXES:
        x_without, _ = prepare_axes(data, excluded=axis)
        labels = fit_labels(method, x_without, k)
        result[axis] = round(float(adjusted_rand_score(baseline, labels)), 6)
    return result


def stable_cluster_ids(labels: np.ndarray, data: pd.DataFrame) -> np.ndarray:
    """IDs de apresentacao deterministicos; nao sao ordinal de qualidade.

    Ordena clusters por mediana de empregos DESC. Em empate, pelo menor CD_DIST.
    Isso evita tratar IDs aleatorios da biblioteca como significado de negocio.
    """
    uniques = sorted(set(int(v) for v in labels))
    ordered = sorted(
        uniques,
        key=lambda group: (
            -float(np.median(data.loc[labels == group, "empregos"])),
            int(data.loc[labels == group, "CD_DIST"].min()),
        ),
    )
    mapping = {label: i + 1 for i, label in enumerate(ordered)}
    return np.array([mapping[int(label)] for label in labels], dtype=int)


def dataset_fingerprint(data: pd.DataFrame) -> str:
    values = data.loc[:, RAW_COLUMNS].to_csv(index=False, float_format="%.12g")
    return hashlib.sha256(values.encode("utf-8")).hexdigest()


def compare_models(raw_data: pd.DataFrame) -> dict[str, Any]:
    data = official_district_names(validate_data(raw_data))
    x, axes = prepare_axes(data)
    rows = []
    fitted = {}
    for method in METHODS:
        for k in K_VALUES:
            labels = fit_labels(method, x, k)
            fitted[(method, k)] = labels
            rows.append({"metodo": method, "k": k, **evaluate_labels(x, labels)})
    evaluation = pd.DataFrame(rows)
    winners = {}
    assignment = data[["CD_DIST", "NM_DIST", "latitude", "longitude"]].copy()
    profile_rows = []
    for method in METHODS:
        best_k = choose_k(evaluation, method)
        labels = fitted[(method, best_k)]
        target_labels = fitted[(method, TARGET_K)]
        # Os melhores K estatisticamente e o K solicitado pelo produto
        # sao cenarios diferentes; publicar somente apos homologacao.
        scenarios = (
            ("exploratorio", best_k, labels, f"{method}_cluster"),
            ("produto_k10", TARGET_K, target_labels, f"{method}_cluster_k10"),
        )
        for scenario, k, scenario_labels, output_column in scenarios:
            stable_ids = stable_cluster_ids(scenario_labels, data)
            assignment[output_column] = stable_ids
            for cluster_id in sorted(set(stable_ids)):
                current = data.loc[stable_ids == cluster_id]
                profile_rows.append({
                    "metodo": method,
                    "cenario": scenario,
                    "k": k,
                    "cluster": int(cluster_id),
                    "distritos": len(current),
                    **{f"mediana_{col}": round(float(current[col].median()), 6)
                       for col in SOURCE_FIELDS},
                })
        target_metrics = evaluate_labels(x, target_labels)
        winners[method] = {
            "k_escolhido_exploratorio": best_k,
            "metricas_exploratorias": evaluate_labels(x, labels),
            "estabilidade_exploratoria": subsample_stability(data, labels, method, best_k),
            "sensibilidade_exploratoria_ari": ablation_sensitivity(data, labels, method, best_k),
            "cenario_produto_k10": {
                "k": TARGET_K,
                "metricas": target_metrics,
                "estabilidade_subamostras": subsample_stability(data, target_labels, method, TARGET_K),
                "sensibilidade_retirada_dimensoes_ari": ablation_sensitivity(data, target_labels, method, TARGET_K),
                "aprovado_publicacao": False,
                "motivos_pendencia": (
                    ["clusters_com_menos_de_5_distritos"] if not target_metrics["elegivel_min_5"]
                    else []
                ) + ["revisao_territorial_e_semantica_pendente"],
            },
        }

    k1 = winners["kmeans"]["k_escolhido_exploratorio"]
    k2 = winners["ward"]["k_escolhido_exploratorio"]
    agreement = float(adjusted_rand_score(fitted[("kmeans", k1)], fitted[("ward", k2)]))
    conclusion = {
        "concordancia_exploratoria_ari": round(agreement, 6),
        "concordancia_k10_ari": round(float(adjusted_rand_score(
            fitted[("kmeans", TARGET_K)], fitted[("ward", TARGET_K)]
        )), 6),
        "decisao": "PENDENTE_REVISAO_DOS_CRITERIOS_DE_NEGOCIO",
        "alerta": "K=10 e objetivo do produto, nao prova de 10 agrupamentos naturais; Silhouette nao mede acuracia",
    }
    summary = {
        "experimento": "BairroIQ - comparacao de algoritmos de clusterizacao",
        "fonte": SOURCE_TABLE,
        "sha256_dataset_de_entrada": dataset_fingerprint(data),
        "amostras": len(data),
        "campos_de_origem": SOURCE_FIELDS,
        "dimensoes_modelo": list(FEATURE_AXES),
        "pre_processamento": "log1p empregos e roubos; z-score transporte e media; z-score final",
        "k_explorados": list(K_VALUES),
        "k_objetivo_produto": TARGET_K,
        "min_grupo_para_selecao_exploratoria": MIN_CLUSTER,
        "random_state": SEED,
        "subamostragem_sem_reposicao": f"{N_RESAMPLES}x{round(SAMPLE_FRACTION*100)}%",
        "versoes": {"python": platform.python_version(), "numpy": np.__version__,
                    "pandas": pd.__version__, "scikit_learn": sklearn.__version__},
        "metodos": winners,
        **conclusion,
        "alteracoes_gold": "NENHUMA",
    }
    return {"metricas": evaluation, "atribuicoes": assignment,
            "perfis": pd.DataFrame(profile_rows), "features_transformadas": axes,
            "resumo": summary}


def export_results(results: dict[str, Any], output_dir: str | Path) -> None:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    results["metricas"].to_csv(output / "metricas_modelos.csv", index=False)
    results["atribuicoes"].to_csv(output / "distritos_clusters_comparados.csv", index=False, encoding="utf-8-sig")
    results["perfis"].to_csv(output / "perfis_clusters.csv", index=False)
    (output / "resumo_experimento.json").write_text(
        json.dumps(results["resumo"], indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def read_gold(spark_session: Any) -> pd.DataFrame:
    selected = ["CD_DIST", "NM_DIST", "latitude", "longitude", *SOURCE_FIELDS.values()]
    result = spark_session.table(SOURCE_TABLE).select(*selected).toPandas()
    return result.rename(columns={value: key for key, value in SOURCE_FIELDS.items()})


def run_from_spark(spark_session: Any) -> dict[str, Any]:
    """Ler Gold sem modificacao; resultados em memoria para notebook."""
    result = compare_models(read_gold(spark_session))
    result["resumo"]["origem_da_execucao"] = "GOLD_DATABRICKS_DIRETO"
    return result


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, help="CSV diagnostico com 96 distritos e 6 indicadores")
    parser.add_argument("--output-dir", required=True, help="Diretorio de saida: somente arquivos locais")
    args = parser.parse_args(argv)
    result = compare_models(pd.read_csv(args.csv))
    result["resumo"]["origem_da_execucao"] = "CSV_EXPORTADO_DO_DATABRICKS"
    export_results(result, args.output_dir)
    print("=" * 65)
    print("BAIRROIQ | COMPARACAO DE MODELOS | APENAS LEITURA")
    print("=" * 65)
    print(result["metricas"].to_string(index=False))
    print("\nResumo dos cenarios:")
    for name, details in result["resumo"]["metodos"].items():
        product = details["cenario_produto_k10"]
        print(name, "K exploratorio:", details["k_escolhido_exploratorio"],
              "K produto:", product["k"],
              "Silhouette K10:", product["metricas"]["silhouette"],
              "Menor cluster K10:", product["metricas"]["menor_grupo"],
              "Publicacao aprovada:", product["aprovado_publicacao"])
    print("Concordancia K10 (ARI):", result["resumo"]["concordancia_k10_ari"])
    print("Tabelas Gold alteradas: NENHUMA")
    print("BAIRROIQ_ML_COMPARISON_SUCCESS")


if __name__ == "__main__":
    main()
