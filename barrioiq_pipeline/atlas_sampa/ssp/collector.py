"""Coletor oficial SSP-SP: HEAD somente leitura ou GET + versionamento Raw.

Não escreve em tabelas Delta, não transforma registros e não agenda execuções.
Execute: python -m atlas_sampa.ssp.collector --year 2026 --check
         python -m atlas_sampa.ssp.collector --year 2026 --apply
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import uuid4
from zipfile import is_zipfile

from .excel_reader import validate_excel

RAW_DEFAULT = Path("/Volumes/workspace/bronze/raw/ssp")
MAX_FILE_BYTES = 350 * 1024 * 1024
CHUNK_BYTES = 4 * 1024 * 1024


def source_url(year: int) -> str:
    if not 2020 <= year <= 2100:
        raise ValueError("Ano fora da faixa suportada")
    return (
        "https://www.ssp.sp.gov.br/assets/estatistica/transparencia/spDados/"
        f"SPDadosCriminais_{year}.xlsx"
    )


def _request(url: str, method: str) -> Request:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "www.ssp.sp.gov.br":
        raise ValueError("Fonte fora do domínio SSP-SP autorizado")
    return Request(
        url,
        method=method,
        headers={"User-Agent": "AtlasSampa-Ingestion/1.0"},
    )


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for piece in iter(lambda: f.read(CHUNK_BYTES), b""):
            digest.update(piece)
    return digest.hexdigest()


def check_remote(year: int, timeout: int = 60) -> dict:
    """HEAD somente leitura. Metadados não provam igualdade de conteúdo."""
    url = source_url(year)
    with urlopen(_request(url, "HEAD"), timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"HEAD SSP retornou HTTP {response.status}")
        return {
            "status": "HTTP_ACESSIVEL_SEM_DOWNLOAD",
            "url": url,
            "etag": response.headers.get("ETag"),
            "last_modified": response.headers.get("Last-Modified"),
            "content_length": response.headers.get("Content-Length"),
            "publicado": False,
        }


def save_version(
    downloaded: Path,
    raw: Path,
    year: int,
    sha256: str,
    rows_per_sheet: dict[str, int],
    response_headers: dict,
) -> dict:
    """Persistência protegida da versão pelo hash, sem sobrescrever a antiga.

    Necessário serializar invocações do futuro Job (max_concurrent_runs=1).
    """
    folder = raw / "versions" / str(year)
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / f"{sha256}.xlsx"
    metadata_path = folder / f"{sha256}.json"
    if destination.exists():
        if _file_sha256(destination) != sha256:
            raise RuntimeError("Arquivo versionado existente com hash divergente")
        status = "VERSAO_JA_EXISTENTE"
    else:
        pending = folder / f".{sha256}.{uuid4().hex}.partial"
        try:
            shutil.copyfile(downloaded, pending)
            if _file_sha256(pending) != sha256:
                raise RuntimeError("Cópia para Volume Raw diverge do SHA256 baixado")
            if destination.exists():
                if _file_sha256(destination) != sha256:
                    raise RuntimeError("Conflito: destino já existe com hash diferente")
                status = "VERSAO_JA_EXISTENTE"
            else:
                os.replace(pending, destination)
                status = "NOVA_VERSAO_INGERIDA"
        finally:
            pending.unlink(missing_ok=True)

    # Não substituímos metadados existentes, inclusive os da coleta manual.
    if not metadata_path.exists():
        metadata = {
            "produto": "Atlas Sampa",
            "source_url": source_url(year),
            "source_sha256": sha256,
            "year": year,
            "bytes": downloaded.stat().st_size,
            "etag": response_headers.get("ETag"),
            "last_modified": response_headers.get("Last-Modified"),
            "coletado_em_utc": datetime.now(timezone.utc).isoformat(),
            "rows_per_sheet": rows_per_sheet,
            "total_rows": sum(rows_per_sheet.values()),
            "colunas_validadas": 30,
            "status": status,
        }
        temp_metadata = folder / f".{sha256}.{uuid4().hex}.json.partial"
        try:
            with temp_metadata.open("w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            if not metadata_path.exists():
                os.replace(temp_metadata, metadata_path)
        finally:
            temp_metadata.unlink(missing_ok=True)

    return {
        "status": status,
        "arquivo": str(destination),
        "metadados": str(metadata_path),
        "sha256": sha256,
        "bytes": downloaded.stat().st_size,
        "rows_per_sheet": rows_per_sheet,
        "total_rows": sum(rows_per_sheet.values()),
        "bronze_alterada": False,
        "silver_alterada": False,
        "gold_alterada": False,
    }


def apply_collection(year: int, raw: Path = RAW_DEFAULT, timeout: int = 120) -> dict:
    """Baixa e valida o XLSX antes de escrever uma versão na Raw."""
    if not raw.is_dir():
        raise FileNotFoundError(f"Volume SSP não existe: {raw}")
    url = source_url(year)
    with tempfile.TemporaryDirectory(prefix="atlas_sampa_ssp_") as temp_dir:
        downloaded = Path(temp_dir) / "source.xlsx"
        digest = hashlib.sha256()
        size = 0
        with urlopen(_request(url, "GET"), timeout=timeout) as response:
            if response.status != 200:
                raise RuntimeError(f"GET SSP retornou HTTP {response.status}")
            content_type = response.headers.get("Content-Type", "").lower()
            if not any(x in content_type for x in ("spreadsheetml", "octet-stream")):
                raise RuntimeError(f"Content-Type inesperado: {content_type}")
            length = response.headers.get("Content-Length")
            expected = int(length) if length else None
            if expected is not None and expected > MAX_FILE_BYTES:
                raise RuntimeError("Arquivo remoto ultrapassou tamanho máximo")
            response_headers = dict(response.headers.items())
            with downloaded.open("wb") as f:
                while True:
                    chunk = response.read(CHUNK_BYTES)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > MAX_FILE_BYTES:
                        raise RuntimeError("Download ultrapassou limite máximo")
                    digest.update(chunk)
                    f.write(chunk)
        if expected is not None and expected != size:
            raise RuntimeError("Download incompleto segundo Content-Length")
        if not is_zipfile(downloaded):
            raise RuntimeError("Conteúdo não é um arquivo XLSX/ZIP válido")
        rows_per_sheet = validate_excel(downloaded, year)
        return save_version(
            downloaded, raw, year, digest.hexdigest(), rows_per_sheet, response_headers
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Atlas Sampa: coletor SSP-SP versionado")
    parser.add_argument("--year", type=int, required=True, help="Ano da publicação SSP")
    parser.add_argument("--raw", type=Path, default=RAW_DEFAULT)
    parser.add_argument("--timeout", type=int, default=120)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="HEAD; não grava arquivos")
    mode.add_argument("--apply", action="store_true", help="Baixa e versiona na Raw")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout deve ser positivo")
    result = (
        check_remote(args.year, args.timeout)
        if args.check else apply_collection(args.year, args.raw, args.timeout)
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
