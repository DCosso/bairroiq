"""BairroIQ Delta v1: testes totalmente sinteticos, sem Databricks/Spark real."""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
from unittest.mock import patch
import unittest

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "barrioiq_pipeline" / "star_schema_v1_delta_runner.py"
spec = importlib.util.spec_from_file_location("bairroiq_delta_test", str(MODULE))
delta = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delta)
SID = f"{delta.EXPECTED_VERSION}|{delta.EXPECTED_HASH}"


def synthetic_preview():
    codes = list(range(355030801, 355030897))
    profiles = [f"kmeans-k09-p{i:02d}" for i in range(1, 10)]
    pis = [profiles[min(i // 11, 8)] for i in range(96)]
    indicators = list(("empregos", "roubos", "furtos", "metro", "onibus", "trem",
                       "pracas", "corredores_verdes", "escolas", "ubs", "densidade"))
    t = {}
    t["dim_snapshot"] = pd.DataFrame([dict(
        snapshot_id=SID, catalogo_versao=delta.EXPECTED_VERSION,
        sha256_gold=delta.EXPECTED_HASH,
        fonte_gold="workspace.gold.distritos_wide",
        status=delta.STATUS, disponivel_publicamente=False,
        ano_snapshot_fonte=None,
        aviso_temporal="Snapshot do modelo nao e o ano da fonte",
    )])
    t["dim_distrito"] = pd.DataFrame([
        dict(CD_DIST=cd, NM_DIST=f"Distrito Oficial Ficticio {i:02d}",
             latitude=-23.5-i/1000, longitude=-46.5-i/1000)
        for i, cd in enumerate(codes)
    ])
    t["dim_perfil"] = pd.DataFrame([
        dict(snapshot_id=SID, perfil_sk=f"{SID}|{p}", perfil_id=p,
             nome_provisorio=f"Perfil sintetico {i}",
             nome_exibicao_proposto=f"Perfil sintetico {i}",
             ressalva_especifica="Nao publicavel", qtd_distritos=11 if i<9 else 8,
             disponivel_publicamente=False)
        for i, p in enumerate(profiles, 1)
    ])
    t["dim_indicador"] = pd.DataFrame([
        dict(snapshot_id=SID, indicador_sk=f"{SID}|{a}", indicador_id=a,
             coluna_gold=f"fake_{a}", rotulo=f"Indicador {a}", unidade="quantidade",
             fonte="Fonte sintetica", periodo_referencia_documentado="nao_catalogado",
             periodo_validado_na_gold=False) for a in indicators
    ])
    t["fato_distrito_indicador"] = pd.DataFrame([
        dict(snapshot_id=SID, CD_DIST=cd, indicador_sk=f"{SID}|{a}",
             valor_numerico=float(100+i+j))
        for i, cd in enumerate(codes) for j, a in enumerate(indicators)
    ])
    t["fato_distrito_perfil"] = pd.DataFrame([
        dict(snapshot_id=SID, CD_DIST=cd, perfil_sk=f"{SID}|{pis[i]}",
             representatividade_interna_0a100=60.0,
             silhouette_individual=-0.01 if i<3 else 0.2,
             distancia_ao_centro_do_perfil=1.2,
             tipo_pertencimento="FRONTEIRA" if i<3 else "INTERMEDIARIO_OU_PERIFERICO")
        for i, cd in enumerate(codes)
    ])
    t["fato_prioridade_ocorrencias"] = pd.DataFrame([
        dict(snapshot_id=SID, CD_DIST=cd,
             posicao_relativa_entre_96=i+1,
             percentil_relativo_roubos_0a100=float(i+1),
             percentil_relativo_furtos_0a100=float(i+1),
             indice_ordenacao_ocorrencias=float(i+1))
        for i, cd in enumerate(codes)
    ])
    summary = dict(status=delta.STATUS, snapshot_id=SID,
                   sha256_gold=delta.EXPECTED_HASH, versao=delta.EXPECTED_VERSION,
                   alteracoes_gold="NENHUMA", publicacao_gold_autorizada=False,
                   auditoria_p04_condicao_editorial=True,
                   auditoria_p04_nome_homologado=False,
                   fatos_historicos_publicados=False, linhas={k:len(v) for k,v in t.items()})
    return {"tabelas": t, "resumo": summary}


class FakeWriter:
    def __init__(self, spark, rows):
        self.spark, self.rows = spark, rows
        self._mode = None
    def format(self, typ):
        assert typ == "delta"
        return self
    def mode(self, name):
        assert name in ("append", "errorifexists")
        self._mode = name
        return self
    def saveAsTable(self, name):
        assert self._mode
        if self._mode == "errorifexists":
            assert name not in self.spark.saved
            self.spark.saved[name] = list(self.rows)
        else:
            assert name in self.spark.saved
            self.spark.saved[name].extend(self.rows)
        self.spark.operations.append(name)

class FakeDF:
    def __init__(self, spark, rows):
        self.write = FakeWriter(spark, rows)

class FakeSpark:
    def __init__(self):
        self.saved, self.operations = {}, []
        self.catalog = self
    def tableExists(self, name):
        return name in self.saved
    def createDataFrame(self, records, schema):
        return FakeDF(self, records)


class TestDeltaContract(unittest.TestCase):
    def setUp(self):
        self.preview = synthetic_preview()
        self.payload = delta.prepare_snapshot(self.preview)

    def test_seven_tables_and_cardinalities(self):
        self.assertEqual(self.payload["rows"], delta.ROW_COUNTS)
        self.assertEqual(len(delta.TABLES), 7)
        self.assertEqual(list(delta.STRUCTURES)[-1], "dim_snapshot")

    def test_versioned_district_dimension(self):
        rows = self.payload["payloads"]["dim_distrito"]
        self.assertEqual(len(rows), 96)
        self.assertTrue(all(x["snapshot_id"] == SID for x in rows))
        self.assertTrue(all("NM_DIST" in x for x in rows))
        self.assertEqual(self.payload["payloads"]["dim_snapshot"][0]["ano_snapshot_fonte"], None)

    def test_reject_wrong_hash(self):
        self.preview["resumo"]["sha256_gold"] = "b"*64
        with self.assertRaisesRegex(delta.DeltaContractError, "Hash"):
            delta.prepare_snapshot(self.preview)

    def test_reject_partial_fact(self):
        self.preview["tabelas"]["fato_distrito_indicador"] = (
            self.preview["tabelas"]["fato_distrito_indicador"].iloc[:-1]
        )
        with self.assertRaisesRegex(delta.DeltaContractError, "DataFrames"):
            delta.prepare_snapshot(self.preview)

    def test_reject_duplicate_key(self):
        frame = self.preview["tabelas"]["dim_distrito"]
        self.preview["tabelas"]["dim_distrito"].loc[0, "CD_DIST"] = frame.loc[1,"CD_DIST"]
        with self.assertRaisesRegex(delta.DeltaContractError, "chave duplicada"):
            delta.prepare_snapshot(self.preview)

    def test_reject_changed_profile_fk(self):
        self.preview["tabelas"]["fato_distrito_perfil"].loc[0,"perfil_sk"] = SID + "|nao_existe"
        with self.assertRaisesRegex(delta.DeltaContractError, "FK de perfil"):
            delta.prepare_snapshot(self.preview)

    def test_reject_publication(self):
        self.preview["tabelas"]["dim_perfil"].loc[0, "disponivel_publicamente"] = True
        with self.assertRaisesRegex(delta.DeltaContractError, "publicamente"):
            delta.prepare_snapshot(self.preview)

    def test_reject_fake_source_date(self):
        self.preview["tabelas"]["dim_snapshot"].loc[0,"ano_snapshot_fonte"] = 2026
        with self.assertRaisesRegex(delta.DeltaContractError, "data de origem inventada"):
            delta.prepare_snapshot(self.preview)

    def test_reject_temporal_verification_in_gold(self):
        self.preview["tabelas"]["dim_indicador"].loc[0,"periodo_validado_na_gold"] = True
        with self.assertRaisesRegex(delta.DeltaContractError, "temporalmente"):
            delta.prepare_snapshot(self.preview)

    def test_reject_snapshot_metadata_mismatch(self):
        self.preview["tabelas"]["dim_snapshot"].loc[0, "fonte_gold"] = "tabela_invalida"
        with self.assertRaisesRegex(delta.DeltaContractError, "Metadados"):
            delta.prepare_snapshot(self.preview)

    def test_check_is_read_only(self):
        fake = FakeSpark()
        with patch.object(delta, "load_preview", return_value=self.preview):
            plan = delta.check(fake)
        self.assertFalse(fake.operations)
        self.assertFalse(plan["will_write_on_check"])

    def test_inspect_read_only(self):
        fake = FakeSpark()
        result = delta.inspect(fake, self.payload)
        self.assertFalse(fake.operations)
        self.assertTrue(all(x["action_if_applied"] == "APPEND_SNAPSHOT"
                            for x in result["tables"].values()))

    def test_apply_requires_confirmation_without_loading_data(self):
        fake = FakeSpark()
        with patch.object(delta, "load_preview", side_effect=AssertionError("should not load")):
            with self.assertRaisesRegex(delta.DeltaContractError, "Confirmacao"):
                delta.apply_snapshot(fake, confirmation="SIM",expected_hash=delta.EXPECTED_HASH)
        self.assertFalse(fake.operations)

    def test_apply_wrong_hash_rejected_without_loading_data(self):
        fake = FakeSpark()
        with patch.object(delta, "load_preview", side_effect=AssertionError("should not load")):
            with self.assertRaisesRegex(delta.DeltaContractError, "Hash"):
                delta.apply_snapshot(fake,confirmation=delta.CONFIRMATION,expected_hash="c"*64)
        self.assertFalse(fake.operations)

    def test_apply_snapshot_marker_last_and_idempotent(self):
        fake = FakeSpark()
        with patch.object(delta,"load_preview",return_value=self.preview), \
             patch.object(delta,"spark_schema",side_effect=lambda name:name), \
             patch.object(delta,"_validate_table",return_value=None), \
             patch.object(delta,"_existing_rows",side_effect=lambda spark,name,sid: spark.saved.get(delta.TABLES[name], [])):
            first = delta.apply_snapshot(fake, confirmation=delta.CONFIRMATION,
                                         expected_hash=delta.EXPECTED_HASH)
            self.assertEqual(first["action"], "MATERIALIZED_INTERNAL_SNAPSHOT")
            self.assertEqual(fake.operations, [delta.TABLES[x] for x in delta.STRUCTURES])
            self.assertEqual(fake.operations[-1], delta.TABLES["dim_snapshot"])
            again = delta.apply_snapshot(fake, confirmation=delta.CONFIRMATION,
                                         expected_hash=delta.EXPECTED_HASH)
            self.assertEqual(again["action"], "ALREADY_MATERIALIZED_AND_VERIFIED")
            self.assertEqual(len(fake.operations), 7)

    def test_partial_resume_without_duplicate(self):
        fake = FakeSpark()
        first_name = "dim_distrito"
        fake.saved[delta.TABLES[first_name]] = copy.deepcopy(self.payload["payloads"][first_name])
        with patch.object(delta,"load_preview",return_value=self.preview), \
             patch.object(delta,"spark_schema",side_effect=lambda name:name), \
             patch.object(delta,"_validate_table",return_value=None), \
             patch.object(delta,"_existing_rows",side_effect=lambda spark,name,sid: spark.saved.get(delta.TABLES[name], [])):
            output = delta.apply_snapshot(fake, confirmation=delta.CONFIRMATION,
                                          expected_hash=delta.EXPECTED_HASH)
            self.assertEqual(output["action"], "MATERIALIZED_INTERNAL_SNAPSHOT")
            self.assertEqual(len(fake.operations), 6)
            self.assertNotIn(delta.TABLES[first_name], fake.operations)

    def test_partial_mismatch_blocks_all_writes(self):
        fake = FakeSpark()
        altered = copy.deepcopy(self.payload["payloads"]["dim_distrito"])
        altered[0]["NM_DIST"] = "ALTERACAO DIVERGENTE"
        fake.saved[delta.TABLES["dim_distrito"]] = altered
        with patch.object(delta,"load_preview",return_value=self.preview), \
             patch.object(delta,"_validate_table",return_value=None), \
             patch.object(delta,"_existing_rows",side_effect=lambda spark,name,sid: spark.saved.get(delta.TABLES[name], [])):
            with self.assertRaisesRegex(delta.DeltaContractError, "conteudo diferente"):
                delta.apply_snapshot(fake,confirmation=delta.CONFIRMATION,
                                     expected_hash=delta.EXPECTED_HASH)
            self.assertEqual(len(fake.operations), 0)


if __name__ == "__main__":
    unittest.main()
