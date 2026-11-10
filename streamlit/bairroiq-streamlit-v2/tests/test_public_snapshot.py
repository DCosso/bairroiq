"""Teste offline do modo publico, sem Databricks e sem dados reais."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from bairroiq.consumer_v2 import SNAPSHOT
from bairroiq.public_snapshot import PUBLIC_COLUMNS, PublicSnapshotProvider


def _fixture() -> pd.DataFrame:
    rows = []
    distribution = (9, 7, 6, 22, 7, 8, 12, 19, 6)
    perfil_ids = [p for p, count in enumerate(distribution, start=1) for _ in range(count)]
    for idx in range(96):
        rows.append({
            "snapshot_id": SNAPSHOT,
            "cd_dist": 355030801 + idx,
            "neighborhood": f"Distrito Ficticio {idx+1:03d}",
            "latitude": -23.50 - idx / 1000,
            "longitude": -46.50 - idx / 1000,
            "formal_jobs_score": 50.0,
            "safety_score": 60.0,
            "mobility_score": 70.0,
            "green_leisure_score": 55.0,
            "public_services_score": 65.0,
            "densidade_hab_km2": 1000.0 + idx,
            "robberies_per_1000": 1.5,
            "perfil_id": f"kmeans-k09-p{perfil_ids[idx]:02d}",
            "cluster": f"P{perfil_ids[idx]:02d} Perfil Ficticio",
            "tipo_territorio": "DISTRITO_IBGE",
        })
    return pd.DataFrame(rows, columns=PUBLIC_COLUMNS)


class SnapshotPublicoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = self.root / "data"
        self.data.mkdir()
        self.provider = PublicSnapshotProvider(app_dir=self.root)
        self.csv_file = self.data / "public_consumer_v2.csv"
        self.manifest_file = self.data / "public_release.json"

    def _release(self, df: pd.DataFrame, *, approved: bool = True) -> None:
        df.to_csv(self.csv_file, index=False)
        manifest = {
            "aprovacao_explicita": approved,
            "aprovado_por": "Responsavel pelo projeto",
            "referencia_aprovacao": "Aprovacao de teste, dados sinteticos",
            "aprovado_em_utc": "2026-11-10T15:00:00Z",
            "snapshot_id": SNAPSHOT,
            "fonte_payload_sha256": "a" * 64,
            "arquivo_sha256": hashlib.sha256(self.csv_file.read_bytes()).hexdigest(),
        }
        self.manifest_file.write_text(json.dumps(manifest), encoding="utf-8")

    def test_sem_manifesto_recusa(self) -> None:
        with self.assertRaises(PermissionError):
            self.provider.load_metrics()

    def test_sem_aprovacao_recusa(self) -> None:
        self._release(_fixture(), approved=False)
        with self.assertRaises(PermissionError):
            self.provider.load_metrics()

    def test_snapshot_valido_carrega_96_e_aliases(self) -> None:
        self._release(_fixture())
        result = self.provider.load_metrics()
        self.assertEqual(len(result), 96)
        self.assertEqual(result["perfil_id"].nunique(), 9)
        self.assertIn("district_code", result.columns)
        self.assertIn("robbery_index", result.columns)
        self.assertNotIn("publicacao_autorizada", result.columns)
        self.assertTrue(self.provider.load_history().empty)

    def test_csv_adulterado_e_bloqueado(self) -> None:
        self._release(_fixture())
        data = self.csv_file.read_text(encoding="utf-8")
        self.csv_file.write_text(data.replace("Distrito Ficticio 001", "Distrito Outra"), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "alterado"):
            self.provider.load_metrics()

    def test_95_distritos_e_bloqueado(self) -> None:
        self._release(_fixture().iloc[:-1])
        with self.assertRaisesRegex(ValueError, "96 linhas"):
            self.provider.load_metrics()


if __name__ == "__main__":
    unittest.main()
