"""BairroIQ: contrato editorial de nomes simples e sem promessas indevidas."""
from pathlib import Path
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "barrioiq_pipeline" / "catalogo_perfis_v3_config.json"


class TestEditorialProfiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads(CFG.read_text(encoding="utf-8"))
        cls.profiles = {int(p["cluster_id"]): p for p in cls.config["perfis"]}

    def test_nine_unique_names_are_present(self):
        self.assertEqual(set(self.profiles), set(range(1, 10)))
        names = [p["nome_provisorio"] for p in self.profiles.values()]
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue(all(len(name) <= 50 for name in names))
        self.assertTrue(all(p["interesse_usuario"] for p in self.profiles.values()))

    def test_generic_activity_and_intensity_names_removed(self):
        forbidden = {"Atividade em Destaque", "Áreas de Menor Intensidade", "Vida Urbana Compacta"}
        self.assertTrue(forbidden.isdisjoint(
            {p["nome_provisorio"] for p in self.profiles.values()}
        ))

    def test_p04_name_not_automatically_claim_both_rates_below(self):
        p04 = self.profiles[4]
        self.assertEqual(p04["nome_provisorio"], "Menos Ocorrências Registradas")
        self.assertEqual(p04["nome_alternativo_condicional"], "Menos Roubos e Furtos")
        self.assertEqual(p04["revisao_editorial"]["pendencia_critica"],
                         "AUDITAR_MEDIANAS_ROUBOS_E_FURTOS_SEPARADAMENTE")
        self.assertIn("não comprova", p04["ressalva_especifica"])

    def test_p07_never_claims_local_job_opportunity(self):
        p07 = self.profiles[7]
        self.assertEqual(p07["nome_provisorio"], "Empregos em Destaque")
        self.assertEqual(p07["revisao_editorial"]["titulo_para_cartao"], "Empregos em Destaque")
        self.assertEqual(p07["revisao_editorial"]["pendencia_critica"],
                         "AUDITAR_GRANULARIDADE_GEOGRAFICA_DE_EMPREGOS")

    def test_release_is_globally_blocked(self):
        self.assertFalse(self.config["publicacao_gold_autorizada"])
        self.assertTrue(all(not p["revisao_editorial"]["disponivel_publicamente"]
                            for p in self.profiles.values()))


if __name__ == "__main__":
    unittest.main()
