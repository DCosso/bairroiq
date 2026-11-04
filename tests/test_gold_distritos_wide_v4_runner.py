"""BairroIQ | Contratos Gold v4 (sem PySpark/sem Databricks).

Execucao na raiz do repositorio:
    python -m unittest discover -s tests -p 'test_gold_distritos_wide_v4_runner.py' -v
"""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from barrioiq_pipeline import gold_distritos_wide_v4_runner as v4


class FakeType:
    def __init__(self, name):
        self.name = name

    def simpleString(self):
        return self.name


class FakeFrame:
    def __init__(self, columns, rows):
        self.columns = list(columns)
        self.rows = list(rows)
        self.schema = [SimpleNamespace(
            name=name,
            dataType=FakeType("bigint" if name == "CD_DIST" else "double")
        ) for name in columns]

    def count(self):
        return len(self.rows)

    def select(self, *names):
        indices = [self.columns.index(name) for name in names]
        return FakeFrame(names, [tuple(row[i] for i in indices) for row in self.rows])

    def exceptAll(self, other):
        from collections import Counter
        difference = Counter(self.rows) - Counter(other.rows)
        return FakeFrame(self.columns, list(difference.elements()))

    def limit(self, number):
        return FakeFrame(self.columns, self.rows[:number])


class TestSchemaClassification(unittest.TestCase):
    def setUp(self):
        self.columns = ["CD_DIST", "NM_DIST"] + [
            f"feature_{i}" for i in range(250)
        ]
        self.base = FakeFrame(self.columns, [
            tuple([355030801, "Agua Rasa"] + [3.0] * 250),
        ])
        self.proposed = FakeFrame(self.columns + ["latitude", "longitude"], [
            self.base.rows[0] + (-23.5, -46.6)
        ])
        self.core = SimpleNamespace(
            same_schema=lambda a, b: [
                (x.name, x.dataType.simpleString()) for x in a.schema
            ] == [
                (x.name, x.dataType.simpleString()) for x in b.schema
            ],
            assert_exact_codes=Mock(),
        )

    def spark(self, current=None):
        return SimpleNamespace(
            catalog=SimpleNamespace(tableExists=lambda _: current is not None),
            table=lambda _: current,
        )

    def test_absent(self):
        status = v4.classify_target(self.spark(), self.core,
                                    self.base, self.proposed)
        self.assertEqual(status["state"], "ABSENT")

    def test_legacy_identical(self):
        status = v4.classify_target(self.spark(self.base), self.core,
                                    self.base, self.proposed)
        self.assertEqual(status["state"], "LEGACY_IDENTICAL")
        self.assertFalse(status["identical"])

    def test_legacy_stale(self):
        altered = FakeFrame(self.columns, [
            tuple([355030801, "Agua Rasa"] + [5.0] * 250)
        ])
        status = v4.classify_target(self.spark(altered), self.core,
                                    self.base, self.proposed)
        self.assertEqual(status["state"], "LEGACY_STALE")

    def test_geo_identical(self):
        status = v4.classify_target(self.spark(self.proposed), self.core,
                                    self.base, self.proposed)
        self.assertEqual(status["state"], "GEO_IDENTICAL")
        self.assertTrue(status["identical"])

    def test_geo_incomplete(self):
        partial = FakeFrame(self.proposed.columns, [
            self.base.rows[0] + (None, None)
        ])
        status = v4.classify_target(self.spark(partial), self.core,
                                    self.base, self.proposed)
        self.assertEqual(status["state"], "GEO_INCOMPLETE")

    def test_geo_stale(self):
        changed = FakeFrame(self.proposed.columns, [
            tuple([355030801, "Agua Rasa"] + [7.0] * 250) + (-23.5, -46.6)
        ])
        status = v4.classify_target(self.spark(changed), self.core,
                                    self.base, self.proposed)
        self.assertEqual(status["state"], "GEO_STALE")

    def test_rejects_extra_column(self):
        malformed = FakeFrame(self.proposed.columns + ["unexpected"], [
            self.proposed.rows[0] + (1,)
        ])
        with self.assertRaises(v4.MigrationError):
            v4.classify_target(self.spark(malformed), self.core,
                               self.base, self.proposed)


class TestMetadata(unittest.TestCase):
    def test_describe_extended_and_properties(self):
        fields = ["CD_DIST", "NM_DIST", "valor"]
        metadata = {
            "columns": [{"name": name, "comment": f"descricao de {name}"}
                        for name in fields],
            "comment": "Gold comentada",
        }

        def sql(command):
            if command.startswith("DESCRIBE"):
                return SimpleNamespace(first=lambda: (json.dumps(metadata),))
            if command.startswith("SHOW TBLPROPERTIES"):
                return SimpleNamespace(collect=lambda: [("bairroiq.a", "ok")])
            raise AssertionError(command)

        got = v4.metadata_snapshot(SimpleNamespace(sql=sql), fields)
        self.assertEqual(got["table_comment"], "Gold comentada")
        self.assertEqual(got["properties"], {"bairroiq.a": "ok"})
        self.assertEqual(len(got["comments"]), 3)

    def test_rejects_missing_original_comment(self):
        metadata = {"columns": [{"name": "CD_DIST", "comment": None}]}
        spark = SimpleNamespace(sql=lambda _: SimpleNamespace(
            first=lambda: (json.dumps(metadata),)))
        with self.assertRaises(v4.MigrationError):
            v4.metadata_snapshot(spark, ["CD_DIST"])


class TestMigrationGuards(unittest.TestCase):
    def test_reject_legacy_stale_before_writing(self):
        spark = SimpleNamespace(sql=Mock())
        with self.assertRaises(v4.MigrationError):
            v4.migrate_coordinates(
                spark, None, None, None, None, {}, "x",
                {"state": "LEGACY_STALE"},
            )
        spark.sql.assert_not_called()

    def test_reject_missing_target_before_writing(self):
        spark = SimpleNamespace(sql=Mock())
        with self.assertRaises(v4.MigrationError):
            v4.migrate_coordinates(
                spark, None, None, None, None, {}, "x",
                {"state": "ABSENT"},
            )
        spark.sql.assert_not_called()

    def test_noop_when_already_identical(self):
        spark = SimpleNamespace(sql=Mock())
        with patch.object(v4, "emit") as emit:
            v4.migrate_coordinates(
                spark, None, None, None, None, {}, "x",
                {"state": "GEO_IDENTICAL"},
            )
        spark.sql.assert_not_called()
        emit.assert_called_once()


class TestWritePath(unittest.TestCase):
    def test_merge_updates_only_lat_lon(self):
        selected = SimpleNamespace(createOrReplaceTempView=Mock())
        proposed = SimpleNamespace(select=Mock(return_value=selected))
        spark = SimpleNamespace(
            sql=Mock(return_value=SimpleNamespace(collect=lambda: [])),
            catalog=SimpleNamespace(dropTempView=Mock()),
        )
        v4.merge_coordinates(spark, None, proposed)
        query = spark.sql.call_args.args[0].lower()
        self.assertIn("when matched then update set", query)
        self.assertIn("t.latitude = s.latitude", query)
        self.assertIn("t.longitude = s.longitude", query)
        self.assertNotIn("when not matched", query)
        self.assertNotIn("delete", query)
        selected.createOrReplaceTempView.assert_called_once()
        spark.catalog.dropTempView.assert_called_once()

    def test_migration_adds_schema_and_merges_with_audits(self):
        columns = ["CD_DIST", "NM_DIST"] + [f"field_{i}" for i in range(250)]
        base = SimpleNamespace(columns=columns)
        proposed = SimpleNamespace()
        core = SimpleNamespace(
            delta_version=Mock(side_effect=[100, 100, 101, 102]),
            same_schema=Mock(return_value=True),
            target_status=Mock(return_value={"identical": True}),
        )
        spark = SimpleNamespace(
            sql=Mock(return_value=SimpleNamespace(collect=lambda: [])),
            table=Mock(return_value=SimpleNamespace(select=lambda *_: None)),
        )
        with patch.object(v4, "metadata_snapshot", return_value={
            "comments": {c: "documentado" for c in columns},
            "table_comment": "Gold",
            "properties": {"bairroiq.a": "1"},
        }), patch.object(v4, "ensure_metadata_preserved") as audit, \
             patch.object(v4, "ensure_new_column_comments") as new_comments, \
             patch.object(v4, "sources_unchanged") as sources, \
             patch.object(v4, "coordinates_reference_unchanged") as geo_ref, \
             patch.object(v4, "identical_rows", return_value=True), \
             patch.object(v4, "merge_coordinates") as merge, \
             patch.object(v4, "emit") as emit:
            v4.migrate_coordinates(
                spark, core, None, base, proposed,
                {"silver": 2}, "hash", {"state": "LEGACY_IDENTICAL"}
            )
        self.assertIn("ADD COLUMNS", spark.sql.call_args_list[0].args[0])
        self.assertIn("latitude DOUBLE COMMENT", spark.sql.call_args_list[0].args[0])
        self.assertIn("longitude DOUBLE COMMENT", spark.sql.call_args_list[0].args[0])
        merge.assert_called_once()
        self.assertEqual(audit.call_count, 3)
        self.assertEqual(new_comments.call_count, 3)
        self.assertEqual(sources.call_count, 2)
        self.assertEqual(geo_ref.call_count, 2)
        self.assertEqual(emit.call_args_list[-1].args[0],
                         "GOLD_COORDINATES_MIGRATION_SUCCESS")

    def test_recovery_merges_without_second_add_columns(self):
        columns = ["CD_DIST", "NM_DIST"] + [f"field_{i}" for i in range(250)]
        base = SimpleNamespace(columns=columns)
        core = SimpleNamespace(
            delta_version=Mock(side_effect=[200, 200, 200, 201]),
            same_schema=Mock(return_value=True),
            target_status=Mock(return_value={"identical": True}),
        )
        spark = SimpleNamespace(
            sql=Mock(),
            table=Mock(return_value=SimpleNamespace(select=lambda *_: None)),
        )
        with patch.object(v4, "metadata_snapshot", return_value={}), \
             patch.object(v4, "ensure_metadata_preserved"), \
             patch.object(v4, "ensure_new_column_comments"), \
             patch.object(v4, "sources_unchanged"), \
             patch.object(v4, "coordinates_reference_unchanged"), \
             patch.object(v4, "identical_rows", return_value=True), \
             patch.object(v4, "merge_coordinates") as merge, \
             patch.object(v4, "emit"):
            v4.migrate_coordinates(
                spark, core, None, base, None,
                {"silver": 2}, "hash", {"state": "GEO_INCOMPLETE"}
            )
        spark.sql.assert_not_called()
        merge.assert_called_once()


class TestExecuteReadOnly(unittest.TestCase):
    def test_check_never_writes_and_flags_migration(self):
        base = FakeFrame(["CD_DIST", "NM_DIST"] +
                         [f"feature_{i}" for i in range(250)],
                         [tuple([355030801 + i, f"Distrito {i}"] + [3.0] * 250)
                          for i in range(96)])
        proposed = FakeFrame(base.columns + ["latitude", "longitude"], [
            row + (-23.5, -46.6) for row in base.rows
        ])
        names = ["IBGE", "GEO", "OBS", "SSP", "IMOVEIS", "DEPARA"]
        core = SimpleNamespace(
            IBGE=names[0], GEO=names[1], OBS=names[2],
            SSP=names[3], IMOVEIS=names[4], DEPARA=names[5],
            delta_version=lambda *_: 1,
            build=lambda *_: (base, {"imoveis": {"bairros_mapeados": 93}}),
            source_versions_unchanged=lambda *_: True,
            update_target=Mock(),
        )
        geo = SimpleNamespace(
            load_centroids=lambda *_: ([], "sha256"),
            attach_coordinates=lambda *_: (proposed, {"distritos_geolocalizados": 96}),
        )
        spark = SimpleNamespace(
            catalog=SimpleNamespace(tableExists=lambda _: True),
            sql=Mock(),
        )
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "centroides.json"
            path.write_text("{}")
            with patch.object(v4, "GEO_REFERENCE", path), \
                 patch.object(v4, "load_dependencies", return_value=(core, geo)), \
                 patch.object(v4, "classify_target", return_value={
                     "state": "LEGACY_IDENTICAL", "identical": False,
                 }), \
                 patch.object(v4, "emit") as emit:
                result = v4.execute(spark)
        self.assertEqual(result["target_status"]["state"], "LEGACY_IDENTICAL")
        spark.sql.assert_not_called()
        core.update_target.assert_not_called()
        self.assertEqual(emit.call_args_list[-1].args[0],
                         "GOLD_DISTRICTS_CHECK_SUCCESS")
        self.assertTrue(emit.call_args_list[-1].kwargs["migration_required"])
        self.assertFalse(emit.call_args_list[-1].kwargs["changed_tables"])


if __name__ == "__main__":
    unittest.main()
