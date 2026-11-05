"""Testes artificiais do contrato dimensional: nunca representam dados reais de SP."""
from __future__ import annotations

import ast
import copy
import importlib.util
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "barrioiq_pipeline/star_schema_v1_preview.py"
spec = importlib.util.spec_from_file_location("star_schema_v1_test", str(SCRIPT))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

HASH = "a" * 64  # hash deliberadamente sintetico
VERSION = "v3.0.0-candidato"
SOURCES = {x: f"coluna_gold_{x}" for x in mod.INDICADORES}


def fixture():
    n = 96
    rng = np.random.default_rng(13)
    raw = pd.DataFrame({
        "CD_DIST": np.arange(355030801, 355030801+n, dtype="int64"),
        "NM_DIST": [f"Distrito TESTE {i:03d}" for i in range(n)],
        "latitude": -23.7 + rng.random(n) * .25,
        "longitude": -46.8 + rng.random(n) * .20,
    })
    for j, alias in enumerate(mod.INDICADORES):
        raw[alias] = (j + 1) * 3.0 + np.arange(n) / 11.0
    profiles = [f"kmeans-k09-p{k:02d}" for k in range(1, 10)]
    assignment = [profiles[i // 11] if i < 88 else profiles[8] for i in range(n)]
    # Grupos artificiais: P01..P08 11 integrantes, P09 8 integrantes.
    catalog = pd.DataFrame({
        "perfil_id": profiles,
        "nome_provisorio": [f"Perfil sintetico {p}" for p in profiles],
        "nome_exibicao_proposto": [f"Perfil sintetico {p}" for p in profiles],
        "nome_validado_para_publicacao": False,
        "disponivel_publicamente": False,
        "qtd_distritos": [11]*8 + [8],
        "ressalva_especifica": "Dados artificiais para testes",
    })
    ranked = raw[["CD_DIST", "NM_DIST"]].copy()
    ranked["perfil_id"] = assignment
    ranked["catalogo_versao"] = VERSION
    ranked["representatividade_interna_0a100"] = 65.0
    ranked["silhouette_individual"] = [.2 if i > 2 else -.01 for i in range(n)]
    ranked["distancia_ao_centro_do_perfil"] = .5
    ranked["tipo_pertencimento"] = ["FRONTEIRA" if i < 3 else "INTERMEDIARIO_OU_PERIFERICO"
                                   for i in range(n)]
    ranked["posicao_relativa_entre_96"] = range(1, 97)
    ranked["percentil_relativo_roubos_0a100"] = range(1, 97)
    ranked["percentil_relativo_furtos_0a100"] = range(1, 97)
    ranked["indice_ordenacao_ocorrencias"] = np.arange(1, 97, dtype=float)
    ranked["prioridade_id"] = "menos_roubos_furtos"
    ranked["status_prioridade"] = "EXPLORATORIO_NAO_HOMOLOGADO"
    results = {
        "catalogo": catalog,
        "distritos_priorizados": ranked,
        "resumo": {
            "status": "EXPLORATORIO_NAO_HOMOLOGADO",
            "publicacao_gold_autorizada": False,
            "alteracoes_gold": "NENHUMA",
            "sha256_gold": HASH,
            "catalogo_versao": VERSION,
        },
        "auditoria_p04": {
            "condicao_editorial_atendida": True,
            "nome_homologado": False,
        },
    }
    return raw, results


class TestStarPreview(unittest.TestCase):
    def setUp(self):
        self.raw, self.results = fixture()

    def preview(self):
        return mod.build_preview(self.raw, self.results, SOURCES, HASH)

    def test_dimensions_and_fact_cardinalities(self):
        output = self.preview()
        self.assertEqual(output["resumo"]["linhas"], {
            "dim_snapshot": 1, "dim_distrito": 96, "dim_perfil": 9,
            "dim_indicador": 11, "fato_distrito_indicador": 1056,
            "fato_distrito_perfil": 96, "fato_prioridade_ocorrencias": 96,
        })

    def test_model_snapshot_not_source_year(self):
        output = self.preview()
        snapshot = output["tabelas"]["dim_snapshot"].iloc[0]
        self.assertIsNone(snapshot.ano_snapshot_fonte)
        self.assertIn(HASH, snapshot.snapshot_id)
        indicators = output["tabelas"]["dim_indicador"].set_index("indicador_id")
        self.assertEqual(indicators.loc["empregos", "periodo_referencia_documentado"], "2021")
        self.assertFalse(indicators.periodo_validado_na_gold.any())
        self.assertIn("fim_nao_catalogado", indicators.loc["roubos", "periodo_referencia_documentado"])

    def test_no_publication_and_no_gold_writes(self):
        output = self.preview()
        self.assertFalse(output["resumo"]["publicacao_gold_autorizada"])
        self.assertEqual(output["resumo"]["alteracoes_gold"], "NENHUMA")
        self.assertTrue(output["tabelas"]["dim_perfil"].disponivel_publicamente.eq(False).all())

    def test_fact_grains_and_fk_integrity(self):
        output = self.preview()["tabelas"]
        pairs = output["fato_distrito_indicador"]
        self.assertFalse(pairs.duplicated(["snapshot_id", "CD_DIST", "indicador_sk"]).any())
        for name in ("fato_distrito_perfil", "fato_prioridade_ocorrencias"):
            self.assertFalse(output[name].duplicated(["snapshot_id", "CD_DIST"]).any())
        self.assertTrue(set(pairs.indicador_sk).issubset(set(output["dim_indicador"].indicador_sk)))
        self.assertTrue(set(output["fato_distrito_perfil"].perfil_sk).issubset(
            set(output["dim_perfil"].perfil_sk)))

    def test_values_preserved_exactly(self):
        output = self.preview()["tabelas"]
        long = output["fato_distrito_indicador"].merge(
            output["dim_indicador"][["indicador_sk", "indicador_id"]],
            on="indicador_sk", validate="many_to_one")
        for alias in mod.INDICADORES:
            observed = long.loc[long.indicador_id == alias].sort_values("CD_DIST").valor_numerico
            expected = self.raw.sort_values("CD_DIST")[alias]
            np.testing.assert_allclose(observed.to_numpy(dtype=float), expected.to_numpy(dtype=float))

    def test_deterministic_on_reordering(self):
        baseline = self.preview()["tabelas"]
        self.raw = self.raw.sample(frac=1, random_state=2)
        self.results["catalogo"] = self.results["catalogo"].sample(frac=1, random_state=2)
        self.results["distritos_priorizados"] = self.results["distritos_priorizados"].sample(frac=1, random_state=2)
        updated = self.preview()["tabelas"]
        for table in baseline:
            if table not in ("dim_indicador", "dim_snapshot"):
                pd.testing.assert_frame_equal(baseline[table], updated[table])

    def test_changed_hash_blocked(self):
        self.results["resumo"]["sha256_gold"] = "b"*64
        with self.assertRaisesRegex(ValueError, "Hash"):
            self.preview()

    def test_publication_blocked(self):
        self.results["catalogo"].loc[0, "disponivel_publicamente"] = True
        with self.assertRaisesRegex(ValueError, "publico"):
            self.preview()

    def test_missing_source_column_blocked(self):
        self.raw = self.raw.drop(columns=["furtos"])
        with self.assertRaisesRegex(ValueError, "colunas obrigatorias"):
            self.preview()

    def test_duplicate_district_blocked(self):
        self.results["distritos_priorizados"].loc[0, "CD_DIST"] = self.results["distritos_priorizados"].loc[1, "CD_DIST"]
        with self.assertRaisesRegex(ValueError, "duplicada"):
            self.preview()

    def test_missing_profile_assignment_blocked(self):
        self.results["distritos_priorizados"].loc[0, "perfil_id"] = "P00"
        with self.assertRaisesRegex(ValueError, "Perfis"):
            self.preview()

    def test_bad_profile_count_blocked(self):
        self.results["catalogo"].loc[0, "qtd_distritos"] = 999
        with self.assertRaisesRegex(ValueError, "Contagem por perfil"):
            self.preview()

    def test_ranking_global_incomplete_blocked(self):
        self.results["distritos_priorizados"].loc[0, "posicao_relativa_entre_96"] = 3
        with self.assertRaisesRegex(ValueError, "Ranking global"):
            self.preview()

    def test_negative_indicator_blocked(self):
        self.raw.loc[0, "empregos"] = -2
        with self.assertRaisesRegex(ValueError, "Indicadores negativos"):
            self.preview()

    def test_invalid_v3_version_blocked(self):
        self.results["resumo"]["catalogo_versao"] = "v4.0.0"
        with self.assertRaisesRegex(ValueError, "Versao v3"):
            self.preview()

    def test_source_indicator_contract_changes_blocked(self):
        with self.assertRaisesRegex(ValueError, "11 indicadores"):
            mod.build_preview(self.raw, self.results, {"furtos":"gold_furto"}, HASH)

    def test_export_local_only(self):
        import tempfile
        with tempfile.TemporaryDirectory(prefix="bairroiq_", dir="/tmp") as temp:
            mod.export_local(self.preview(), temp)
            self.assertEqual(len(list(Path(temp).glob("*.csv"))), 7)
            self.assertTrue((Path(temp) / "resumo_star_schema_v1.json").is_file())
        with self.assertRaisesRegex(ValueError, "somente para /tmp"):
            mod.export_local(self.preview(), "relative/path")

    def test_no_database_writers_in_script(self):
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        forbidden = {"saveAsTable", "insertInto", "writeTo", "sql", "execute", "save", "createOrReplaceTempView"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                self.assertNotIn(node.attr, forbidden)


if __name__ == "__main__":
    unittest.main()
