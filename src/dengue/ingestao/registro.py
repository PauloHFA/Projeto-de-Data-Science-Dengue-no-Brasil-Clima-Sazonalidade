"""Registro de manifesto de dados brutos com hash SHA-256, data e origem (REG-08)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dengue.config import RAW_DIR


def calcular_sha256(caminho_arquivo: Path) -> str:
    """Calcula o hash SHA-256 de um arquivo em disco."""
    hasher = hashlib.sha256()
    with caminho_arquivo.open("rb") as f:
        for bloco in iter(lambda: f.read(65536), b""):
            hasher.update(bloco)
    return hasher.hexdigest()


def registrar_arquivo_manifesto(
    caminho_arquivo: Path,
    fonte: str,
    versao: str,
    metadados_extras: dict[str, Any] | None = None,
    caminho_manifesto: Path | None = None,
) -> dict[str, Any]:
    """Registra data, versão, origem e hash SHA-256 de um arquivo baixado (Seção 3 e REG-08)."""
    if caminho_manifesto is None:
        caminho_manifesto = RAW_DIR / "manifesto_hashes.json"

    caminho_manifesto.parent.mkdir(parents=True, exist_ok=True)

    registro: dict[str, Any] = {
        "arquivo": caminho_arquivo.name,
        "caminho_relativo": str(caminho_arquivo.name),
        "fonte": fonte,
        "versao": versao,
        "sha256": calcular_sha256(caminho_arquivo),
        "tamanho_bytes": caminho_arquivo.stat().st_size,
        "data_ingestao_utc": datetime.now(timezone.utc).isoformat(),
    }
    if metadados_extras:
        registro["metadados"] = metadados_extras

    manifesto: list[dict[str, Any]] = []
    if caminho_manifesto.exists():
        try:
            manifesto = json.loads(caminho_manifesto.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            manifesto = []

    # Atualiza caso o mesmo arquivo já conste no manifesto
    manifesto = [item for item in manifesto if item.get("arquivo") != caminho_arquivo.name]
    manifesto.append(registro)

    caminho_manifesto.write_text(
        json.dumps(manifesto, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return registro

