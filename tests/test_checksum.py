
import unittest

from src.barrioiq.checksum import calcular_sha256


class TestChecksum(unittest.TestCase):

    def test_hash_conhecido(self):
        resultado = calcular_sha256(b"abc")

        esperado = (
            "ba7816bf8f01cfea414140de5dae2223"
            "b00361a396177a9cb410ff61f20015ad"
        )

        self.assertEqual(resultado, esperado)

    def test_hash_deterministico(self):
        conteudo = b"BarrioIQ"

        self.assertEqual(
            calcular_sha256(conteudo),
            calcular_sha256(conteudo)
        )


if __name__ == "__main__":
    unittest.main()
