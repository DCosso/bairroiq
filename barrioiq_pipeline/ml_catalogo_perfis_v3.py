"""BairroIQ | Catalogo candidato de nove perfis territoriais (v3).

Prepara um contrato de consumo EXPLORATORIO a partir da Gold real.
Nao grava tabelas, nao homologa nomes e nao gera recomendacao personalizada.
A versao v2 e reutilizada; a v1/v2 nao sao modificadas.

Invariantes de seguranca:
  - 96 distritos oficiais; dados completos e hash Gold auditado;
  - modelo K-Means K=9, winsorizacao P10-P90 APENAS no eixo densidade;
  - composicao por CD_DIST exatamente igual ao resultado real congelado;
  - metricas e evidencia descritiva revisadas, com falha fechada;
  - todos os perfis permanecem CANDIDATO_REVISAO_SEMANTICA.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import platform
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn
from sklearn.metrics import silhouette_samples

BASE = Path(__file__).resolve().parent
CONFIG_PATH = BASE / "catalogo_perfis_v3_config.json"
V2_PATH = BASE / "ml_perfis_territoriais_v2.py"
K = 9
P_DENSIDADE = 0.10
METHOD = "kmeans"
STATUS = "CANDIDATO_REVISAO_SEMANTICA"


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError("BAIRROIQ_CATALOGO_V3_BLOCKED: " + message)


def load_v2():
    require(V2_PATH.is_file(), f"Modulo v2 ausente: {V2_PATH}")
    spec = importlib.util.spec_from_file_location("bairroiq_v2_para_v3", str(V2_PATH))
    require(spec is not None and spec.loader is not None, "Falha ao localizar modulo v2")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_config(path: str | Path = CONFIG_PATH) -> dict[str, Any]:
    path = Path(path)
    require(path.is_file(), f"Catalogo nao encontrado: {path}")
    raw = path.read_text(encoding="utf-8")
    config = json.loads(raw)
    require(isinstance(config, dict), "Config deve ser um objeto JSON")
    require(config.get("status") == STATUS, "Status invalido de publicacao")
    require(config.get("publicacao_gold_autorizada") is False,
            "A homologacao da Gold nao pode ser autorizada neste modulo")
    require(config.get("modelo", {}).get("metodo") == METHOD, "Metodo divergente")
    require(config["modelo"].get("k") == K, "K divergente")
    require(config["modelo"].get("densidade_winsor_p_inferior") == P_DENSIDADE,
            "Percentil de densidade divergente")
    require(len(config.get("sha256_gold_esperado", "")) == 64, "Hash esperado invalido")
    profiles = config.get("perfis", [])
    require(isinstance(profiles, list) and len(profiles) == K,
            "Catalogo deve ter exatamente nove perfis")
    ids = [p.get("cluster_id") for p in profiles]
    require(sorted(ids) == list(range(1, K + 1)), "IDs de perfil invalidos")
    all_codes: list[int] = []
    for p in profiles:
        cid = p["cluster_id"]
        require(p.get("perfil_id") == f"kmeans-k09-p{cid:02d}",
                f"ID sem contrato no perfil {cid}")
        for field in ("nome_provisorio", "descricao_provisoria", "interesse_usuario",
                      "ressalva_especifica"):
            require(isinstance(p.get(field), str) and p[field].strip(),
                    f"Campo vazio {field} no perfil {cid}")
        codes = p.get("distritos_cd_dist", [])
        require(isinstance(codes, list), f"Codigos invalidos no perfil {cid}")
        require(len(codes) == p.get("qtd_distritos_esperada") and len(codes) >= 3,
                f"Tamanho do perfil divergente {cid}")
        require(all(type(n) is int for n in codes), f"CD_DIST invalido no perfil {cid}")
        definers = p.get("eixos_definidores", [])
        require(len(definers) == 2, f"Eixos definidores ausentes no perfil {cid}")
        for item in definers:
            require(item.get("eixo") in (
                "atividade", "ocorrencias", "mobilidade", "verde_lazer",
                "servicos_publicos", "densidade"), f"Eixo desconhecido no perfil {cid}")
            require(item.get("direcao") in ("acima", "abaixo"),
                    f"Direcao invalida no perfil {cid}")
        all_codes.extend(codes)
    require(len(all_codes) == 96 and len(set(all_codes)) == 96,
            "Catalogo deve cobrir exatamente 96 codigos unicos")
    return config


def robust_features(data: pd.DataFrame, ml) -> tuple[np.ndarray, pd.DataFrame, dict[str, float]]:
    _, axes = ml.features(data)
    axes = axes.copy()
    lower = float(axes["densidade"].quantile(P_DENSIDADE))
    upper = float(axes["densidade"].quantile(1 - P_DENSIDADE))
    require(lower < upper, "Densidade sem amplitude apos quantis")
    axes["densidade"] = axes["densidade"].clip(lower=lower, upper=upper)
    X = ml.z(axes)
    require(X.shape == (96, 6), "Formato da matriz de treino invalido")
    return X, axes, {"p10_log1p": lower, "p90_log1p": upper}


def _validate_stats(config: dict[str, Any], ml, X: np.ndarray,
                    labels: np.ndarray, ids: np.ndarray,
                    silhouettes: np.ndarray) -> dict[str, Any]:
    m = ml.metrics(X, labels)
    expected = config["resultados_observados"]
    for key in ("silhouette", "davies_bouldin"):
        require(abs(float(m[key]) - float(expected[key])) <= 0.0002,
                f"Metrica {key} mudou: {m[key]} vs {expected[key]}")
    require(m["menor_grupo"] == expected["menor_grupo"]
            and m["maior_grupo"] == expected["maior_grupo"],
            "Tamanho de grupos difere do experimento auditado")
    require(m["elegivel_operacional"], "Cenario fora dos criterios operacionais")
    require(int(np.sum(silhouettes < 0)) == expected["numero_distritos_silhouette_negativa"],
            "Numero de casos de fronteira mudou")
    require(set(ids) == set(range(1, K + 1)), "IDs modelados invalidos")
    return m


def build_catalog(raw: pd.DataFrame, config: dict[str, Any] | None = None,
                  reference: str | Path | None = None) -> dict[str, Any]:
    """Executa somente processamento em memoria e falha se a fotografia mudar.

    `reference` existe apenas para usar o mesmo contrato IBGE em testes locais.
    A execucao Spark utiliza a referencia oficial incluida no Bundle.
    """
    ml = load_v2()
    config = load_config() if config is None else config
    # Mesma validacao do arquivo de configuracao para configuracoes fornecidas no teste.
    # Os parametros e a politica de nao-publicacao nao sao editaveis pelo chamador.
    require(config.get("status") == STATUS and config.get("publicacao_gold_autorizada") is False,
            "Catalogo nao autorizado para uso exploratorio")
    require(config.get("modelo", {}).get("metodo") == METHOD
            and config["modelo"].get("k") == K
            and config["modelo"].get("densidade_winsor_p_inferior") == P_DENSIDADE,
            "Parametros do modelo divergem")
    data = ml.validate_and_prepare(
        raw, reference=Path(reference) if reference is not None else None
    )
    current_hash = ml.fingerprint(data)
    require(current_hash == config["sha256_gold_esperado"],
            f"Hash da Gold mudou: {current_hash}; aprovado somente {config['sha256_gold_esperado']}")

    X, axes, density_limits = robust_features(data, ml)
    labels = ml.predict(METHOD, X, K)
    ids = ml.stable_ids(labels, data)
    silhouettes = silhouette_samples(X, labels)
    m = _validate_stats(config, ml, X, labels, ids, silhouettes)

    profiles_config = config["perfis"]
    require(len(profiles_config) == K, "Quantidade de perfis invalida")
    config_by_id = {int(p["cluster_id"]): p for p in profiles_config}
    require(set(config_by_id) == set(range(1, K + 1)), "IDs repetidos ou ausentes")

    all_codes = set(data.CD_DIST.astype(int).tolist())
    reference_codes = set()
    for cid in range(1, K + 1):
        profile = config_by_id[cid]
        observed = set(data.loc[ids == cid, "CD_DIST"].astype(int).tolist())
        expected = set(profile["distritos_cd_dist"])
        require(observed == expected,
                f"Composicao do perfil {cid} mudou; nao publicar nem renomear: "
                f"faltam={sorted(expected-observed)}, sobram={sorted(observed-expected)}")
        require(len(observed) == profile["qtd_distritos_esperada"],
                f"Tamanho do perfil {cid} nao confere")
        reference_codes.update(expected)
    require(reference_codes == all_codes and len(reference_codes) == 96,
            "Cobertura oficial dos distritos divergente")

    catalog_rows: list[dict[str, Any]] = []
    district_rows: list[dict[str, Any]] = []
    for cid in range(1, K + 1):
        profile = config_by_id[cid]
        where = np.flatnonzero(ids == cid)
        cluster_x = X[where]
        median = np.median(cluster_x, axis=0)
        center = np.mean(cluster_x, axis=0)
        distances = np.linalg.norm(cluster_x - center, axis=1)
        # Empate resolvido pela chave territorial; ranking APENAS de centralidade no grupo.
        sorted_local = sorted(range(len(where)),
                              key=lambda i: (float(distances[i]), int(data.iloc[where[i]].CD_DIST)))
        rank = {local: position for position, local in enumerate(sorted_local)}
        evidence = []
        for i in np.argsort(-np.abs(median))[:3]:
            evidence.append({
                "eixo": ml.AXES[int(i)],
                "mediana_z": round(float(median[i]), 4),
                "direcao": "acima" if median[i] > 0 else "abaixo",
            })
        for define in profile["eixos_definidores"]:
            index = ml.AXES.index(define["eixo"])
            actual_direction = "acima" if median[index] > 0 else "abaixo"
            require(actual_direction == define["direcao"] and abs(median[index]) >= .35,
                    f"Eixo descritivo do perfil {cid} deixou de ser distintivo")

        cluster_sil = silhouettes[where]
        neg = int(np.sum(cluster_sil < 0))
        require(neg == profile["casos_silhouette_negativa_exploratoria"],
                f"Fronteiras do perfil {cid} mudaram")
        exemplar_indexes = [where[i] for i in sorted_local[:3]]
        exemplar_names = [str(data.iloc[pos].NM_DIST) for pos in exemplar_indexes]
        originals = {key: round(float(np.median(data.iloc[where][key])), 6)
                     for key in ml.SOURCE_FIELDS}
        catalog_rows.append({
            "perfil_id": profile["perfil_id"],
            "cluster_id": cid,
            "nome_provisorio": profile["nome_provisorio"],
            "descricao_provisoria": profile["descricao_provisoria"],
            "interesse_usuario": profile["interesse_usuario"],
            "ressalva_especifica": profile["ressalva_especifica"],
            "disponivel_publicamente": False,
            "pendencia_critica_editorial": profile.get("revisao_editorial", {}).get("pendencia_critica"),
            "qtd_distritos": len(where),
            "exemplos_distritos_json": json.dumps(exemplar_names, ensure_ascii=False),
            "evidencias_json": json.dumps(evidence, ensure_ascii=False),
            "medianas_originais_json": json.dumps(originals, ensure_ascii=False),
            "silhouette_mediana": round(float(np.median(cluster_sil)), 6),
            "distritos_silhouette_negativa": neg,
            "metodo": METHOD,
            "k": K,
            "catalogo_versao": config["versao_catalogo"],
            "sha256_gold": current_hash,
            "status": STATUS,
            "publicacao_gold_autorizada": False,
        })
        for local, position in enumerate(where):
            district = data.iloc[position]
            # 100 = mais proximo do centroide de seu proprio grupo; 0 = o mais afastado.
            # NAO e qualidade de vida, afinidade com preferencias, nem probabilidade.
            pct = 100 * (len(where) - 1 - rank[local]) / (len(where) - 1)
            sil = float(silhouettes[position])
            category = ("FRONTEIRA" if sil < 0 else
                        "CENTRAL_NO_PERFIL" if rank[local] < max(1, int(np.ceil(len(where)/3)))
                        else "INTERMEDIARIO_OU_PERIFERICO")
            district_rows.append({
                "CD_DIST": int(district.CD_DIST),
                "NM_DIST": str(district.NM_DIST),
                "latitude": float(district.latitude),
                "longitude": float(district.longitude),
                "perfil_id": profile["perfil_id"],
                "cluster_id": cid,
                "nome_provisorio": profile["nome_provisorio"],
                "disponivel_publicamente": False,
                "distancia_ao_centro_do_perfil": round(float(distances[local]), 6),
                "representatividade_interna_0a100": round(float(pct), 2),
                "silhouette_individual": round(sil, 6),
                "tipo_pertencimento": category,
                "metodo": METHOD,
                "k": K,
                "catalogo_versao": config["versao_catalogo"],
                "sha256_gold": current_hash,
                "status": STATUS,
            })
    cat = pd.DataFrame(catalog_rows).sort_values("cluster_id").reset_index(drop=True)
    districts = pd.DataFrame(district_rows).sort_values("CD_DIST").reset_index(drop=True)
    require(len(cat) == K and len(districts) == 96
            and districts.CD_DIST.nunique() == 96
            and cat.qtd_distritos.sum() == 96,
            "Saida nao cobre os 96 distritos exatamente uma vez")
    require(int(districts.tipo_pertencimento.eq("FRONTEIRA").sum()) == config["resultados_observados"]["numero_distritos_silhouette_negativa"],
            "Casos de fronteira mudaram")
    summary = {
        "experimento": "BAIRROIQ_CATALOGO_PERFIS_V3",
        "fonte": config["fonte"],
        "sha256_gold": current_hash,
        "sha256_configuracao": hashlib.sha256(json.dumps(config,sort_keys=True,
                         ensure_ascii=False).encode("utf-8")).hexdigest(),
        "versao": config["versao_catalogo"],
        "metodo": METHOD, "k": K, "densidade_winsor": "P10-P90 no eixo log1p",
        "densidade_limites": density_limits,
        "metricas_reproduzidas": m,
        "estabilidade_observada_v2_ari_mediana": config["resultados_observados"]["ari_replicacoes_mediana"],
        "estabilidade_observada_v2_ari_p10": config["resultados_observados"]["ari_replicacoes_p10"],
        "silhouette_individual_negativa": int((silhouettes < 0).sum()),
        "distritos": len(districts), "perfis": len(cat),
        "notas": ["As atribuicoes foram reproduzidas e conferidas por CD_DIST.",
                  "Os nomes sao editoriais, sustentados por eixos observados, mas nao homologados.",
                  "Proximidade ao centro mede representatividade DENTRO do grupo; nao recomendacao pessoal.",
                  "Silhouette e ARI nao medem acuracia, qualidade de vida ou satisfacao do usuario."],
        "revisoes_pendentes": config["revisoes_pendentes"],
        "versoes_libraries": {"python": platform.python_version(),
                             "numpy": np.__version__, "pandas": pd.__version__,
                             "scikit_learn": sklearn.__version__},
        "status": STATUS,
        "publicacao_gold_autorizada": False,
        "alteracoes_gold": "NENHUMA",
    }
    return {"catalogo": cat, "distritos": districts, "resumo": summary}


def run_from_spark(spark_session: Any) -> dict[str, Any]:
    """Le a tabela oficial e produz apenas DataFrames pandas em memoria."""
    ml = load_v2()
    cols = [*ml.IDENTIFIERS, *ml.SOURCE_FIELDS.values()]
    raw = spark_session.table(ml.SOURCE_TABLE).select(*cols).toPandas()
    raw = raw.rename(columns={source: alias for alias, source in ml.SOURCE_FIELDS.items()})
    results = build_catalog(raw)
    results["resumo"]["origem_execucao"] = "GOLD_DATABRICKS_DIRETO"
    return results


def export(results: dict[str, Any], output_dir: str | Path) -> None:
    """Exporta arquivos locais opcionais; jamais cria/escreve tabelas Delta."""
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    results["catalogo"].to_csv(path / "catalogo_perfis_v3.csv", index=False, encoding="utf-8-sig")
    results["distritos"].to_csv(path / "distritos_por_perfil_v3.csv", index=False, encoding="utf-8-sig")
    (path / "resumo_catalogo_v3.json").write_text(
        json.dumps(results["resumo"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
