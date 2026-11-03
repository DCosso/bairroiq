
"""
BairroIQ | Testes estaticos da Silver IBGE.

Valida o contrato SQL versionado sem acessar Databricks,
executar Spark ou modificar tabelas.

Os testes de qualidade dos dados reais permanecem separados.
"""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]

SQL_PATH = (
    ROOT
    / "barrioiq_pipeline"
    / "sql"
    / "silver"
    / "001_ibge_agregados_basicos.sql"
)

SOURCE = "workspace.bronze.ibge_agregados_basico_v2"
TARGET = "workspace.silver.ibge_agregados_basicos_v2"

EXPECTED_COLUMNS = [
    "CD_DIST",
    "NM_DIST",
    "CD_MUN",
    "NM_MUN",
    "area_km2",
    "total_pessoas",
    "total_domicilios",
    "total_domicilios_particulares",
    "total_domicilios_coletivos",
    "media_moradores_domicilios_ocupados",
    "percentual_domicilios_ocupados_imputados",
    "total_domicilios_particulares_ocupados",
    "total_domicilios_uso_ocasional",
    "total_domicilios_permanentes_vagos",
]

SOURCE_MAPPING = {
    "area_km2": "AREA_KM2",
    "total_pessoas": "V0001",
    "total_domicilios": "V0002",
    "total_domicilios_particulares": "V0003",
    "total_domicilios_coletivos": "V0004",
    "media_moradores_domicilios_ocupados": "V0005",
    "percentual_domicilios_ocupados_imputados": "V0006",
    "total_domicilios_particulares_ocupados": "V0007",
    "total_domicilios_uso_ocasional": "V0008",
    "total_domicilios_permanentes_vagos": "V0009",
}


def read_sql():
    text = SQL_PATH.read_text(encoding="utf-8-sig")

    # Remove comentarios de linha.
    text = re.sub(
        r"(?m)^[ \t]*--[^\r\n]*",
        "",
        text,
    )

    return re.sub(r"\s+", " ", text).strip()


def split_projection(projection):
    """Separa colunas sem dividir argumentos de funcoes."""

    parts = []
    buffer = []
    depth = 0
    in_string = False
    index = 0

    while index < len(projection):
        char = projection[index]

        if char == "'":
            buffer.append(char)

            if in_string and index + 1 < len(projection):
                if projection[index + 1] == "'":
                    buffer.append("'")
                    index += 2
                    continue

            in_string = not in_string

        elif not in_string and char == "(":
            depth += 1
            buffer.append(char)

        elif not in_string and char == ")":
            depth -= 1

            if depth < 0:
                raise ValueError("Parenteses invalidos")

            buffer.append(char)

        elif not in_string and char == "," and depth == 0:
            parts.append("".join(buffer).strip())
            buffer = []

        else:
            buffer.append(char)

        index += 1

    if depth != 0 or in_string:
        raise ValueError("Expressao SQL incompleta")

    parts.append("".join(buffer).strip())

    return parts


def extract_columns(sql):
    match = re.search(
        rf"\bAS\s+SELECT\s+(.*?)\s+"
        rf"FROM\s+{re.escape(SOURCE)}\s+WHERE\b",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if not match:
        raise ValueError("SELECT Silver nao encontrado")

    expressions = split_projection(match.group(1))
    result = {}

    for expression in expressions:
        alias = re.search(
            r"\bAS\s+([a-zA-Z_][a-zA-Z0-9_]*)$",
            expression,
            flags=re.IGNORECASE,
        )

        name = (
            alias.group(1)
            if alias
            else expression.strip()
        )

        key = name.lower()

        if key in result:
            raise ValueError(f"Coluna duplicada: {name}")

        result[key] = expression

    return result


class TestSilverIBGESQL(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.sql = read_sql()
        cls.columns = extract_columns(cls.sql)

    def test_01_single_sql_statement(self):
        self.assertEqual(
            self.sql.count(";"),
            1,
            "Esperada uma unica instrucao SQL",
        )

        self.assertTrue(
            self.sql.endswith(";"),
            "SQL deve terminar com ponto e virgula",
        )


    def test_02_expected_target(self):
        pattern = (
            rf"^CREATE\s+OR\s+REPLACE\s+TABLE\s+"
            rf"{re.escape(TARGET)}\s+"
            rf"USING\s+DELTA\s+AS\s+SELECT\b"
        )

        self.assertRegex(
            self.sql,
            re.compile(pattern, flags=re.IGNORECASE),
        )


    def test_03_expected_source(self):
        self.assertRegex(
            self.sql,
            rf"\bFROM\s+{re.escape(SOURCE)}\b",
        )

    def test_04_municipality_filter(self):
        self.assertRegex(
            self.sql,
            r"(?i)\bWHERE\s+CD_MUN\s*=\s*'3550308'\s*;$",
        )

    def test_05_expected_columns(self):
        self.assertEqual(
            list(self.columns),
            [name.lower() for name in EXPECTED_COLUMNS],
        )

    def test_06_source_mapping(self):
        for output, source in SOURCE_MAPPING.items():
            with self.subTest(column=output):
                expression = self.columns[output.lower()]

                self.assertRegex(
                    expression.upper(),
                    rf"\bTRIM\s*\(\s*{source}\s*\)",
                )

                self.assertIn(
                    "TRY_CAST(",
                    expression.upper(),
                )

                # Impede que uma coluna calculada utilize
                # outra variavel V000X por engano.
                if source.startswith("V"):
                    referenced = set(
                        re.findall(
                            r"\bV[0-9]{4}\b",
                            expression.upper(),
                        )
                    )

                    self.assertEqual(
                        referenced,
                        {source},
                    )

    def test_07_percent_conversion(self):
        expression = self.columns[
            "percentual_domicilios_ocupados_imputados"
        ]

        self.assertRegex(
            expression.upper(),
            r"\)\s*\*\s*100\s+AS\s+"
            r"PERCENTUAL_DOMICILIOS_OCUPADOS_IMPUTADOS$",
        )

    def test_08_no_additional_destructive_commands(self):
        forbidden = (
            r"\b("
            r"DROP|TRUNCATE|DELETE|MERGE|INSERT|"
            r"UPDATE|ALTER|GRANT|REVOKE|VACUUM"
            r")\b"
        )

        self.assertNotRegex(
            self.sql.upper(),
            forbidden,
        )

    def test_09_no_select_all(self):
        self.assertNotRegex(
            self.sql.upper(),
            r"\bSELECT\s+\*",
        )

    def test_10_required_null_handling(self):
        for output in SOURCE_MAPPING:
            with self.subTest(column=output):
                expression = self.columns[output.lower()]

                self.assertIn(
                    "NULLIF(",
                    expression.upper(),
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
