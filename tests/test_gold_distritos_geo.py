"""BairroIQ | Testes de compatibilidade de nomes IBGE com U+FFFD.

Executar na raiz do repositorio:
    python -m unittest discover -s tests -p 'test_gold_distritos_geo.py' -v

Nao requer Spark. Nao altera arquivos nem tabelas.
"""

import unittest

from barrioiq_pipeline import gold_distritos_geo as geo


class TestCompatibilidadeNomesIBGE(unittest.TestCase):
    def test_mesmo_nome_com_acentuacao(self):
        self.assertTrue(geo.compatible_ibge_name("ÁGUA RASA", "Água Rasa"))
        self.assertTrue(geo.compatible_ibge_name("Agua Rasa", "Água Rasa"))

    def test_caractere_acentuado_substituido(self):
        casos = (
            ("�gua Rasa", "Água Rasa"),
            ("Bel�m", "Belém"),
            ("Br�s", "Brás"),
            ("Brasil�ndia", "Brasilândia"),
            ("Butant�", "Butantã"),
            ("S�o Paulo", "São Paulo"),
            ("Jardim S�o Lu�s", "Jardim São Luís"),
        )
        for silver, official in casos:
            with self.subTest(silver=silver, official=official):
                self.assertTrue(geo.compatible_ibge_name(silver, official))

    def test_maiusculas_espacos_e_unicode(self):
        self.assertTrue(geo.compatible_ibge_name("  VILA   S�NIA  ", "Vila Sônia"))
        self.assertTrue(geo.compatible_ibge_name("Vila So\u0301nia", "Vila Sônia"))

    def test_nao_permite_nome_diferente(self):
        self.assertFalse(geo.compatible_ibge_name("Vila Mariana", "Vila Prudente"))
        self.assertFalse(geo.compatible_ibge_name("Alto de Pinheiros", "Alto da Lapa"))

    def test_nao_permite_comprimento_diferente(self):
        self.assertFalse(geo.compatible_ibge_name("�gua", "Água Rasa"))
        self.assertFalse(geo.compatible_ibge_name("A�ua Rasa a", "Água Rasa"))

    def test_coringa_somente_silver(self):
        self.assertFalse(geo.compatible_ibge_name("Agua Rasa", "�gua Rasa"))

    def test_caractere_errado_nao_corrompido(self):
        self.assertFalse(geo.compatible_ibge_name("Água Rosa", "Água Rasa"))
        self.assertFalse(geo.compatible_ibge_name("Belam", "Belém"))

    def test_nome_vazio_e_rejeitado(self):
        with self.assertRaises(geo.GeoContractError):
            geo.compatible_ibge_name("", "Água Rasa")
        with self.assertRaises(geo.GeoContractError):
            geo.compatible_ibge_name("Água Rasa", "")


if __name__ == "__main__":
    unittest.main()
