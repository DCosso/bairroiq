"""BairroIQ | Testes unitarios do executor Silver SSP espacial.

Executar a partir da raiz do repositorio:
    python -m unittest discover -s tests -v

Nao precisa de Spark, Databricks, GeoPandas, Pandas ou Numpy na CI.
Nao acessa arquivos do Volume nem grava tabelas.
"""

import ast
import inspect
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from barrioiq_pipeline import silver_ssp_spatial_runner as runner


# ============================================================
# 1. OBJETOS SINTETICOS (SEM SPARK/PANDAS)
# ============================================================


def make_row(bo="BO-001", district="355030801", name="Agua Rasa"):
    return (
        bo,
        "2026-01-01",
        "ROUBO",
        "CENTRO",
        -23.55,
        -46.65,
        district,
        name,
    )


class FakeFrame:
    """Minimo de um DataFrame para comparar multiconjuntos de linhas."""

    def __init__(self, rows, columns=None):
        self.rows = list(rows)
        self.columns = list(columns or runner.OUTPUT_COLUMNS)

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, columns):
        indexes = [self.columns.index(name) for name in columns]
        return FakeFrame(
            [tuple(row[index] for index in indexes) for row in self.rows],
            columns,
        )

    def itertuples(self, index=False, name=None):
        if index is not False or name is not None:
            raise AssertionError("Formato inesperado de iteracao")
        return iter(self.rows)

    def select(self, *columns):
        return self[list(columns)]

    def toPandas(self):
        return self


class FakeSpark:
    def __init__(self, existing, columns=None):
        self.existing = FakeFrame(existing, columns)
        self.queries = []

    def sql(self, query):
        self.queries.append(query)
        if query.startswith("SELECT * FROM ") and "VERSION AS OF" in query:
            return self.existing
        raise AssertionError("Consulta nao esperada: " + query)


# ============================================================
# 2. CONTRATO E EXECUCAO DA CLI
# ============================================================


class TestContractAndCLI(unittest.TestCase):
    def test_01_contrato_estatico_valido(self):
        with patch.object(runner, "emit") as events:
            runner.verify_contract()
        events.assert_called_once_with(
            "SSP_STATIC_VALIDATION_SUCCESS", read_only=True
        )

    def test_02_colunas_e_fontes_esperadas(self):
        self.assertEqual(len(runner.OUTPUT_COLUMNS), 8)
        self.assertEqual(runner.SOURCE_COLUMNS, runner.OUTPUT_COLUMNS[:6])
        self.assertEqual(runner.STATUS, "CONVERTIDA")
        self.assertEqual(runner.MUNICIPALITY, "3550308")
        self.assertEqual(runner.CRS, "EPSG:4674")
        self.assertEqual(runner.EXPECTED_DISTRICTS, 96)
        self.assertEqual(runner.TARGET, "workspace.silver.ssp_ocorrencias_distrito")

    def test_03_rejeita_origem_igual_ao_destino(self):
        with patch.object(runner, "SOURCE", runner.TARGET):
            with self.assertRaisesRegex(ValueError, "nao podem coincidir"):
                runner.verify_contract()

    def test_04_sem_argumentos_nao_acessa_spark(self):
        with (
            patch.object(sys, "argv", ["silver_ssp_spatial_runner.py"]),
            patch.object(runner, "run_check") as run_check,
            patch.object(runner, "emit") as emit,
        ):
            runner.main()
        run_check.assert_not_called()
        emit.assert_called_once_with("SSP_STATIC_VALIDATION_SUCCESS", read_only=True)

    def test_05_check_aciona_validacao(self):
        with (
            patch.object(sys, "argv", ["silver_ssp_spatial_runner.py", "--check"]),
            patch.object(runner, "run_check") as run_check,
            patch.object(runner, "emit"),
        ):
            runner.main()
        run_check.assert_called_once()

    def test_06_apply_e_proibido(self):
        with (
            patch.object(sys, "argv", ["silver_ssp_spatial_runner.py", "--apply"]),
            patch.object(runner, "run_check") as run_check,
        ):
            with self.assertRaises(SystemExit) as error:
                runner.main()
        self.assertEqual(error.exception.code, 2)
        run_check.assert_not_called()

    def test_07_bloqueia_codigo_de_publicacao(self):
        tree = ast.parse(inspect.getsource(runner))
        forbidden_attributes = {
            "saveAsTable", "insertInto", "save", "delete", "merge",
            "overwrite", "write", "writeTo", "execute",
        }
        used = {
            node.attr for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
        }
        self.assertFalse(
            used.intersection(forbidden_attributes),
            f"Operacoes potencialmente mutaveis: {used & forbidden_attributes}",
        )


# ============================================================
# 3. VERSIONAMENTO DELTA E IDENTIDADE DA MALHA
# ============================================================


class TestSnapshotsAndShapefile(unittest.TestCase):
    def test_08_identifica_versao_delta(self):
        spark = SimpleNamespace(sql=Mock(return_value=SimpleNamespace(
            first=lambda: {"version": 12}
        )))
        self.assertEqual(runner.delta_version(spark, runner.SOURCE), 12)
        spark.sql.assert_called_once_with(
            f"DESCRIBE HISTORY {runner.SOURCE} LIMIT 1"
        )

    def test_09_rejeita_historico_vazio(self):
        spark = SimpleNamespace(sql=lambda query: SimpleNamespace(first=lambda: None))
        with self.assertRaisesRegex(ValueError, "Historico Delta ausente"):
            runner.delta_version(spark, runner.TARGET)

    def _write_shape_components(self, folder):
        shp = Path(folder) / "distritos.shp"
        for suffix in runner.SHAPE_COMPONENTS:
            shp.with_suffix(suffix).write_bytes(suffix.encode("ascii"))
        return shp

    def test_10_hash_da_malha_e_deterministico(self):
        with tempfile.TemporaryDirectory() as folder:
            shp = self._write_shape_components(folder)
            with patch.object(runner, "SHAPEFILE", shp):
                a = runner.hash_shapefile()
                b = runner.hash_shapefile()
        self.assertEqual(a, b)
        self.assertEqual(len(a), 64)

    def test_11_hash_muda_com_componentes(self):
        with tempfile.TemporaryDirectory() as folder:
            shp = self._write_shape_components(folder)
            with patch.object(runner, "SHAPEFILE", shp):
                before = runner.hash_shapefile()
                shp.with_suffix(".dbf").write_bytes(b"alteracao")
                after = runner.hash_shapefile()
        self.assertNotEqual(before, after)

    def test_12_arquivo_ausente_bloqueia_check(self):
        with tempfile.TemporaryDirectory() as folder:
            shp = self._write_shape_components(folder)
            shp.with_suffix(".prj").unlink()
            with patch.object(runner, "SHAPEFILE", shp):
                with self.assertRaisesRegex(ValueError, "Arquivo da malha ausente"):
                    runner.hash_shapefile()


# ============================================================
# 4. COMPARACAO EXATA DE REGISTROS
# ============================================================


class TestRowComparison(unittest.TestCase):
    def setUp(self):
        # JSON aceita esses valores sintéticos sem NumPy ou Pandas.
        self.normalizer = patch.object(runner, "canonical_value", side_effect=lambda x: x)
        self.normalizer.start()
        self.addCleanup(self.normalizer.stop)

    def test_13_ordem_nao_altera_multiconjunto(self):
        rows = [make_row("A"), make_row("B")]
        self.assertEqual(
            runner.row_multiset(FakeFrame(rows)),
            runner.row_multiset(FakeFrame(list(reversed(rows)))),
        )

    def test_14_duplicados_sao_preservados(self):
        one = runner.row_multiset(FakeFrame([make_row("A")]))
        two = runner.row_multiset(FakeFrame([make_row("A"), make_row("A")]))
        self.assertNotEqual(one, two)
        self.assertEqual(sum(two.values()), 2)

    def test_15_mudanca_de_distrito_e_detectada(self):
        before = runner.row_multiset(FakeFrame([make_row("A")]))
        after = runner.row_multiset(FakeFrame([
            make_row("A", "355030802", "Alto de Pinheiros")
        ]))
        self.assertNotEqual(before, after)

    def test_16_schema_incompleto_e_bloqueado(self):
        incomplete = FakeFrame(
            [make_row("A")[:7]], runner.OUTPUT_COLUMNS[:7]
        )
        with self.assertRaisesRegex(ValueError, "Colunas ausentes"):
            runner.row_multiset(incomplete)

    def test_17_silver_identica_aprovada(self):
        rows = [make_row("A"), make_row("B"), make_row("B")]
        spark = FakeSpark(list(reversed(rows)))
        with patch.object(runner, "emit") as emit:
            runner.compare_target(spark, None, FakeFrame(rows), 3)
        self.assertIn("SSP_ROWSET_MATCH", [c.args[0] for c in emit.call_args_list])
        self.assertEqual(
            spark.queries, [f"SELECT * FROM {runner.TARGET} VERSION AS OF 3"]
        )

    def test_18_distrito_errado_bloqueia_comparacao(self):
        spark = FakeSpark([make_row("A")])
        changed = FakeFrame([make_row("A", "355030802", "Alto de Pinheiros")])
        with patch.object(runner, "emit") as emit:
            with self.assertRaisesRegex(ValueError, "nao e identica"):
                runner.compare_target(spark, None, changed, 3)
        events = [call.args[0] for call in emit.call_args_list]
        self.assertIn("ROWSET_COMPARISON", events)
        self.assertNotIn("SSP_ROWSET_MATCH", events)

    def test_19_quantidade_divergente_bloqueia(self):
        spark = FakeSpark([make_row("A")])
        with self.assertRaisesRegex(ValueError, "Quantidade divergente"):
            runner.compare_target(
                spark, None, FakeFrame([make_row("A"), make_row("B")]), 3
            )

    def test_20_schema_diferente_bloqueia(self):
        spark = FakeSpark(
            [make_row("A")[:7]], columns=runner.OUTPUT_COLUMNS[:7]
        )
        with self.assertRaisesRegex(ValueError, "Schema da Silver"):
            runner.compare_target(spark, None, FakeFrame([make_row("A")]), 3)

    def test_21_multiplicidade_divergente_bloqueia(self):
        spark = FakeSpark([make_row("A"), make_row("A"), make_row("B")])
        proposed = FakeFrame([make_row("A"), make_row("B"), make_row("B")])
        with self.assertRaisesRegex(ValueError, "nao e identica"):
            runner.compare_target(spark, None, proposed, 3)


# ============================================================
# 5. EXECUCAO READ-ONLY E CONTROLE DE CONCORRENCIA
# ============================================================


class TestCheckFlow(unittest.TestCase):
    def fake_modules(self):
        sql = ModuleType("pyspark.sql")
        sql.SparkSession = SimpleNamespace(
            builder=SimpleNamespace(getOrCreate=lambda: object())
        )
        spark = ModuleType("pyspark")
        spark.sql = sql
        return {
            "geopandas": ModuleType("geopandas"),
            "numpy": ModuleType("numpy"),
            "pandas": ModuleType("pandas"),
            "pyspark": spark,
            "pyspark.sql": sql,
        }

    def test_22_check_valido_sem_escrita(self):
        with (
            patch.dict(sys.modules, self.fake_modules()),
            patch.object(runner, "delta_version", side_effect=[5, 2, 7, 5, 2, 7]) as versions,
            patch.object(runner, "hash_shapefile", side_effect=["SHA", "SHA"]) as checksum,
            patch.object(runner, "load_districts", return_value=object()) as load_districts,
            patch.object(runner, "load_source", return_value=object()) as load_source,
            patch.object(runner, "build_spatial_result", return_value=FakeFrame([make_row()])) as build,
            patch.object(runner, "compare_target") as compare,
            patch.object(runner, "emit") as emit,
        ):
            runner.run_check()
        self.assertEqual(versions.call_count, 6)
        self.assertEqual(checksum.call_count, 2)
        load_districts.assert_called_once()
        load_source.assert_called_once()
        build.assert_called_once()
        compare.assert_called_once()
        self.assertIn(
            "SSP_SPATIAL_CHECK_SUCCESS",
            [call.args[0] for call in emit.call_args_list],
        )

    def test_23_detecta_alteracao_concorrente_na_fonte(self):
        with (
            patch.dict(sys.modules, self.fake_modules()),
            patch.object(runner, "delta_version", side_effect=[5, 2, 7, 6]),
            patch.object(runner, "hash_shapefile", return_value="SHA"),
            patch.object(runner, "load_districts", return_value=object()),
            patch.object(runner, "load_source", return_value=object()),
            patch.object(runner, "build_spatial_result", return_value=FakeFrame([make_row()])),
            patch.object(runner, "compare_target"),
        ):
            with self.assertRaisesRegex(ValueError, "Origem SSP mudou"):
                runner.run_check()

    def test_24_detecta_alteracao_da_malha(self):
        with (
            patch.dict(sys.modules, self.fake_modules()),
            patch.object(runner, "delta_version", side_effect=[5, 2, 7, 5, 2, 7]),
            patch.object(runner, "hash_shapefile", side_effect=["SHA_ANTIGO", "SHA_NOVO"]),
            patch.object(runner, "load_districts", return_value=object()),
            patch.object(runner, "load_source", return_value=object()),
            patch.object(runner, "build_spatial_result", return_value=FakeFrame([make_row()])),
            patch.object(runner, "compare_target"),
        ):
            with self.assertRaisesRegex(ValueError, "Malha SHP mudou"):
                runner.run_check()


if __name__ == "__main__":
    unittest.main(verbosity=2)
