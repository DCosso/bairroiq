"""BairroIQ v3: contrato candidato, reproducibilidade e bloqueios (somente dados sinteticos)."""
from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import silhouette_samples

BASE = Path(__file__).resolve().parents[1]
SCRIPT = BASE / "barrioiq_pipeline" / "ml_catalogo_perfis_v3.py"
spec = importlib.util.spec_from_file_location("bairroiq_v3_test", str(SCRIPT))
v3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v3)
ml = v3.load_v2()
NONEXISTENT_REFERENCE = Path("/nonexistent/bairroiq_ref.json")


def fixture() -> pd.DataFrame:
    """96 linhas artificiais PARA TESTES; nunca representam a Gold real."""
    rng = np.random.default_rng(42)
    n = 96
    fake = pd.DataFrame({
        "CD_DIST": np.arange(355030801, 355030801 + n, dtype=int),
        "NM_DIST": [f"Distrito ficticio {i}" for i in range(n)],
        "latitude": -23.65 + rng.random(n) * .35,
        "longitude": -46.85 + rng.random(n) * .5,
    })
    latent = np.repeat(np.arange(8), 12)
    for i, name in enumerate(ml.SOURCE_FIELDS):
        if name == "empregos":
            fake[name] = 2500 + 1200 * latent + rng.uniform(1, 500, n)
        elif name == "densidade":
            fake[name] = 250 + 1000 * latent + rng.uniform(1, 500, n)
        else:
            fake[name] = np.maximum(.01, 1 + latent * .4 + rng.random(n) * (i + 1))
    return fake


def config_for_fixture(raw: pd.DataFrame) -> dict:
    """Config artificial consistente para testar o contrato sem dados reais."""
    data = ml.validate_and_prepare(raw, reference=NONEXISTENT_REFERENCE)
    X, _, _ = v3.robust_features(data, ml)
    labels = ml.predict("kmeans", X, 9)
    ids = ml.stable_ids(labels, data)
    sil = silhouette_samples(X, labels)
    config = copy.deepcopy(v3.load_config())
    config["sha256_gold_esperado"] = ml.fingerprint(data)
    m = ml.metrics(X, labels)
    config["resultados_observados"].update({
        "silhouette": m["silhouette"],
        "davies_bouldin": m["davies_bouldin"],
        "menor_grupo": m["menor_grupo"],
        "maior_grupo": m["maior_grupo"],
        "numero_distritos_silhouette_negativa": int(np.sum(sil < 0)),
    })
    for profile in config["perfis"]:
        cid = profile["cluster_id"]
        members = data.loc[ids == cid]
        profile["distritos_cd_dist"] = members.CD_DIST.astype(int).tolist()
        profile["qtd_distritos_esperada"] = len(members)
        profile["casos_silhouette_negativa_exploratoria"] = int(np.sum(sil[ids == cid] < 0))
        median = np.median(X[ids == cid], axis=0)
        defining = np.argsort(-np.abs(median))[:2]
        profile["eixos_definidores"] = [
            {"eixo": ml.AXES[int(axis)], "direcao": "acima" if median[axis] > 0 else "abaixo"}
            for axis in defining
        ]
    return config


class TestProductionConfig(unittest.TestCase):
    def test_real_config_has_nine_profiles_and_96_codes(self):
        config = v3.load_config()
        self.assertEqual(len(config["perfis"]), 9)
        ids = [cd for p in config["perfis"] for cd in p["distritos_cd_dist"]]
        self.assertEqual(len(ids), 96)
        self.assertEqual(len(set(ids)), 96)
        self.assertEqual(config["sha256_gold_esperado"],
                         "726091fefefa868fd5d0d2c6929b1d68c4849941f4c7510b4fee0d93a075d38b")

    def test_production_config_is_not_homologated(self):
        config = v3.load_config()
        self.assertEqual(config["status"], v3.STATUS)
        self.assertIs(config["publicacao_gold_autorizada"], False)
        self.assertEqual(config["modelo"]["metodo"], "kmeans")
        self.assertEqual(config["modelo"]["k"], 9)

    def test_missing_config_refused(self):
        with self.assertRaisesRegex(ValueError, "Catalogo nao encontrado"):
            v3.load_config("/nonexistent/config_v3.json")

    def test_config_duplicate_codes_refused(self):
        config = v3.load_config()
        with tempfile.TemporaryDirectory() as temp:
            invalid = copy.deepcopy(config)
            invalid["perfis"][1]["distritos_cd_dist"][0] = invalid["perfis"][0]["distritos_cd_dist"][0]
            path = Path(temp) / "config.json"
            path.write_text(json.dumps(invalid), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "96 codigos unicos"):
                v3.load_config(path)

    def test_cannot_authorize_publication_by_config(self):
        with tempfile.TemporaryDirectory() as temp:
            invalid = copy.deepcopy(v3.load_config())
            invalid["publicacao_gold_autorizada"] = True
            path = Path(temp) / "config.json"
            path.write_text(json.dumps(invalid), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "homologacao"):
                v3.load_config(path)


class TestCandidateCatalog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = fixture()
        cls.config = config_for_fixture(cls.raw)
        cls.result = v3.build_catalog(cls.raw, config=cls.config, reference=NONEXISTENT_REFERENCE)

    def test_complete_96_district_assignment(self):
        self.assertEqual(len(self.result["distritos"]), 96)
        self.assertEqual(self.result["distritos"].CD_DIST.nunique(), 96)
        self.assertEqual(self.result["distritos"].perfil_id.nunique(), 9)
        self.assertEqual(len(self.result["catalogo"]), 9)
        self.assertEqual(self.result["catalogo"].qtd_distritos.sum(), 96)

    def test_no_authorized_publication(self):
        self.assertTrue(self.result["catalogo"].status.eq(v3.STATUS).all())
        self.assertTrue(self.result["distritos"].status.eq(v3.STATUS).all())
        self.assertFalse(self.result["resumo"]["publicacao_gold_autorizada"])
        self.assertEqual(self.result["resumo"]["alteracoes_gold"], "NENHUMA")

    def test_deterministic_results(self):
        another = v3.build_catalog(self.raw.sample(frac=1, random_state=3),
                                   config=self.config, reference=NONEXISTENT_REFERENCE)
        pd.testing.assert_frame_equal(self.result["catalogo"], another["catalogo"])
        pd.testing.assert_frame_equal(self.result["distritos"], another["distritos"])

    def test_relative_representativity_is_internal(self):
        districts = self.result["distritos"]
        self.assertTrue(districts.representatividade_interna_0a100.between(0, 100).all())
        for _, rows in districts.groupby("perfil_id"):
            self.assertAlmostEqual(float(rows.representatividade_interna_0a100.max()), 100)
            self.assertAlmostEqual(float(rows.representatividade_interna_0a100.min()), 0)
        self.assertTrue(set(districts.tipo_pertencimento).issubset({
            "FRONTEIRA", "CENTRAL_NO_PERFIL", "INTERMEDIARIO_OU_PERIFERICO"
        }))

    def test_explanation_evidence_has_real_values_in_fixture(self):
        for _, row in self.result["catalogo"].iterrows():
            self.assertTrue(row.nome_provisorio)
            self.assertTrue(row.ressalva_especifica)
            evidence = json.loads(row.evidencias_json)
            self.assertEqual(len(evidence), 3)
            self.assertEqual(len(json.loads(row.exemplos_distritos_json)), 3)

    def test_change_of_gold_value_blocks(self):
        changed = self.raw.copy()
        changed.loc[0, "densidade"] += 20
        with self.assertRaisesRegex(ValueError, "Hash da Gold mudou"):
            v3.build_catalog(changed, config=self.config, reference=NONEXISTENT_REFERENCE)

    def test_changed_membership_blocks_even_with_matching_hash(self):
        bad = copy.deepcopy(self.config)
        a, b = bad["perfis"][:2]
        a["distritos_cd_dist"][0], b["distritos_cd_dist"][0] = (
            b["distritos_cd_dist"][0], a["distritos_cd_dist"][0]
        )
        with self.assertRaisesRegex(ValueError, "Composicao do perfil"):
            v3.build_catalog(self.raw, config=bad, reference=NONEXISTENT_REFERENCE)

    def test_misleading_axis_direction_blocks(self):
        bad = copy.deepcopy(self.config)
        first = bad["perfis"][0]["eixos_definidores"][0]
        first["direcao"] = "abaixo" if first["direcao"] == "acima" else "acima"
        with self.assertRaisesRegex(ValueError, "deixou de ser distintivo"):
            v3.build_catalog(self.raw, config=bad, reference=NONEXISTENT_REFERENCE)

    def test_no_auto_homologation_accepted_by_build(self):
        bad = copy.deepcopy(self.config)
        bad["status"] = "HOMOLOGADO"
        with self.assertRaisesRegex(ValueError, "nao autorizado"):
            v3.build_catalog(self.raw, config=bad, reference=NONEXISTENT_REFERENCE)

    def test_invalid_inputs_block(self):
        with self.assertRaisesRegex(ValueError, "96 distritos"):
            v3.build_catalog(self.raw.iloc[:-1], config=self.config,
                             reference=NONEXISTENT_REFERENCE)

    def test_export_local_only(self):
        with tempfile.TemporaryDirectory() as temp:
            v3.export(self.result, temp)
            paths = {p.name for p in Path(temp).iterdir()}
            self.assertEqual(paths, {
                "catalogo_perfis_v3.csv", "distritos_por_perfil_v3.csv", "resumo_catalogo_v3.json"
            })
            self.assertEqual(len(pd.read_csv(Path(temp) / "distritos_por_perfil_v3.csv")), 96)


if __name__ == "__main__":
    unittest.main()
