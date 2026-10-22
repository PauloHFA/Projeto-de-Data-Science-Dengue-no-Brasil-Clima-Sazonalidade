"""Testes do funil de exclusão (REG-12) e manifesto SHA-256 (REG-08)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from dengue.ingestao.registro import calcular_sha256, registrar_arquivo_manifesto
from dengue.qualidade.limpeza import limpar_notificacoes_com_funil


def test_funil_exclusao_contabiliza_todas_etapas() -> None:
    """Verifica que cada etapa de limpeza documenta exatamente os registros removidos (REG-12)."""
    df_bruto = pd.DataFrame(
        {
            "ID_NOTIFIC": ["N1", "N1", "N2", "N3", "N4", "N5", "N6"],
            "DT_SIN_PRI": [
                "2023-03-01",
                "2023-03-01",  # Duplicata de N1
                "2099-99-99",  # Data inválida
                "2023-03-05",  # Município inválido
                "2023-03-10",  # Idade inválida (>120 anos)
                "2023-03-12",  # Descartado (CLASSI_FIN == '5')
                "2023-03-15",  # Válido
            ],
            "DT_NOTIFIC": [
                "2023-03-04",
                "2023-03-04",
                "2023-03-05",
                "2023-03-08",
                "2023-03-12",
                "2023-03-15",
                "2023-03-18",
            ],
            "ID_MUNICIP": ["250750", "250750", "250750", "999999", "250400", "250750", "250400"],
            "NU_IDADE_N": [4030, 4030, 4025, 4040, 4150, 4020, 4035],
            "CLASSI_FIN": ["10", "10", "10", "10", "10", "5", "10"],
        }
    )

    df_limpo, df_funil = limpar_notificacoes_com_funil(
        df_bruto,
        municipios_validos=["250750", "250400"],
    )

    assert len(df_limpo) == 2
    assert set(df_limpo["ID_NOTIFIC"]) == {"N1", "N6"}
    assert len(df_funil) == 5
    assert int(df_funil["registros_removidos"].sum()) == len(df_bruto) - len(df_limpo)


def test_registro_manifesto_sha256(tmp_path: Path) -> None:
    """Verifica geração e persistência do hash SHA-256 no manifesto (REG-08)."""
    arq = tmp_path / "amostra.parquet"
    df = pd.DataFrame({"a": [1, 2, 3]})
    df.to_parquet(arq, index=False)

    manifesto_path = tmp_path / "manifesto_hashes.json"
    reg = registrar_arquivo_manifesto(
        caminho_arquivo=arq,
        fonte="TESTE_UNITARIO",
        versao="v1",
        caminho_manifesto=manifesto_path,
    )

    assert manifesto_path.exists()
    assert len(reg["sha256"]) == 64
    assert reg["sha256"] == calcular_sha256(arq)

