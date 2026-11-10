"""Valida exportação original do Databricks e gera snapshot público aprovado.

Exemplo, a partir da raiz do subprojeto Streamlit:
    python scripts/preparar_snapshot_publico.py --entrada export_consumer.csv
    python scripts/preparar_snapshot_publico.py --entrada export_consumer.csv --aprovacao aprovacao.json

A execução sem --aprovacao apenas inspeciona e não publica nada.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

APP_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_ROOT))

from bairroiq.consumer_v2 import SNAPSHOT  # noqa: E402
from bairroiq.databricks import _verify_audited_result  # noqa: E402
from bairroiq.public_snapshot import PUBLIC_COLUMNS  # noqa: E402


def verificar_fonte(path: Path) -> tuple[pd.DataFrame, str]:
    raw = pd.read_csv(path, float_precision="round_trip", dtype={
        "snapshot_id": "string", "neighborhood": "string",
        "perfil_id": "string", "cluster": "string", "tipo_territorio": "string",
        "payload_sha256": "string", "sql_sha256": "string",
        "versao_contrato": "string",
    })
    if raw["payload_sha256"].nunique() != 1:
        raise ValueError("A fonte deve conter um único hash auditado")
    source_sha = str(raw["payload_sha256"].iloc[0])
    # Libera apenas verificação local. A permissão do preview privado
    # NÃO é transferida para o aplicativo público.
    validated = _verify_audited_result(raw, internal_preview=True)
    if validated["snapshot_id"].iloc[0] != SNAPSHOT:
        raise ValueError("Snapshot incorreto")
    return validated, source_sha


def publicar(entrada: Path, aprovacao: Path | None) -> None:
    data, source_sha = verificar_fonte(entrada)
    print("SNAPSHOT_VALIDO | distritos=96 | perfis=9")
    print("FONTE_PAYLOAD_SHA256 |", source_sha)
    if aprovacao is None:
        print("INSPECAO_APENAS | Nada foi autorizado ou publicado")
        print("Crie uma aprovação formal antes de usar --aprovacao")
        return
    approval = json.loads(aprovacao.read_text(encoding="utf-8"))
    if approval.get("aprovacao_explicita") is not True:
        raise PermissionError("A publicação depende de aprovação explícita")
    if approval.get("snapshot_id") != SNAPSHOT or approval.get("fonte_payload_sha256") != source_sha:
        raise PermissionError("A aprovação não corresponde à versão auditada")
    for field in ("aprovado_por", "referencia_aprovacao", "aprovado_em_utc"):
        if not isinstance(approval.get(field), str) or not approval[field].strip():
            raise PermissionError(f"Preencha a aprovação: {field}")
    # Somente as 15 colunas de consumo; o flag do Consumer privado não é
    # alterado nem transferido. A aprovação formal vale para este release.
    output_dir = APP_ROOT / "data"
    output_dir.mkdir(parents=True, exist_ok=True)
    public_data = data.loc[:, PUBLIC_COLUMNS].sort_values("cd_dist")
    csv_path = output_dir / "public_consumer_v2.csv"
    tmp_csv = csv_path.with_suffix(".tmp")
    public_data.to_csv(tmp_csv, index=False, float_format="%.17g", encoding="utf-8")
    os.replace(tmp_csv, csv_path)
    file_sha = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    release = {
        "aprovacao_explicita": True,
        "aprovado_por": approval["aprovado_por"],
        "referencia_aprovacao": approval["referencia_aprovacao"],
        "aprovado_em_utc": approval["aprovado_em_utc"],
        "snapshot_id": SNAPSHOT,
        "fonte_payload_sha256": source_sha,
        "arquivo_sha256": file_sha,
        "gerado_em_utc": datetime.now(timezone.utc).isoformat(),
        "linhas": len(public_data),
        "colunas": len(PUBLIC_COLUMNS),
    }
    release_path = output_dir / "public_release.json"
    tmp_release = release_path.with_suffix(".tmp")
    tmp_release.write_text(json.dumps(release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp_release, release_path)
    print("RELEASE_PRONTO |", csv_path)
    print("MANIFESTO_PUBLICO |", release_path)
    print("ARQUIVO_SHA256 |", file_sha)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--entrada", required=True, type=Path)
    parser.add_argument("--aprovacao", type=Path)
    args = parser.parse_args()
    publicar(args.entrada, args.aprovacao)
