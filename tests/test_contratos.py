"""Testes de contratos de dados com Pandera (REG-09)."""

from __future__ import annotations

import pandas as pd
import pandera.pandas as pa
import pytest

from dengue.qualidade.contratos import (
    validar_contrato_clima,
    validar_contrato_notificacoes,
    validar_contrato_populacao,
)


def test_contrato_notificacoes_rejeita_caso_descartado_e_municipio_fora_pb() -> None:
    """Garante que CLASSI_FIN == '5' ou município fora da PB (25xxxx) falham no contrato (REG-09)."""
    df_valido = pd.DataFrame(
        {
            "ID_NOTIFIC": ["PB1", "PB2"],
            "municipio": ["250750", "250400"],
            "dt_sintomas": pd.to_datetime(["2023-03-10", "2023-04-12"]),
            "dt_notificacao": pd.to_datetime(["2023-03-14", "2023-04-15"]),
            "CLASSI_FIN": ["10", "11"],
            "idade_anos": [28.0, 45.0],
            "atraso_dias": [4, 3],
        }
    )
    validado = validar_contrato_notificacoes(df_valido)
    assert len(validado) == 2

    df_com_descartado = df_valido.copy()
    df_com_descartado.loc[0, "CLASSI_FIN"] = "5"
    with pytest.raises(pa.errors.SchemaErrors):
        validar_contrato_notificacoes(df_com_descartado)

    df_mun_invalido = df_valido.copy()
    df_mun_invalido.loc[0, "municipio"] = "355030"  # São Paulo em vez de PB (25xxxx)
    with pytest.raises(pa.errors.SchemaErrors):
        validar_contrato_notificacoes(df_mun_invalido)


def test_contrato_clima_rejeita_valores_fisicamente_impossiveis() -> None:
    """Garante que chuva negativa ou temperatura fora de [-5, 45] °C são barradas (REG-09)."""
    df_clima = pd.DataFrame(
        {
            "codigo_estacao": ["A320"],
            "semana": pd.to_datetime(["2023-05-07"]),
            "temp_media": [27.2],
            "temp_min": [22.5],
            "temp_max": [31.0],
            "chuva_acum": [42.0],
            "umidade_media": [78.0],
        }
    )
    assert len(validar_contrato_clima(df_clima)) == 1

    df_invalido = df_clima.copy()
    df_invalido["chuva_acum"] = -5.0
    with pytest.raises(pa.errors.SchemaErrors):
        validar_contrato_clima(df_invalido)


def test_contrato_populacao_rejeita_populacao_nao_positiva() -> None:
    """Garante que população zero ou negativa falha no contrato demográfico (REG-05, REG-09)."""
    df_pop = pd.DataFrame(
        {
            "municipio": ["250750"],
            "nome_municipio": ["João Pessoa"],
            "ano": [2022],
            "populacao": [833932],
            "lat": [-7.1195],
            "lon": [-34.8450],
        }
    )
    assert len(validar_contrato_populacao(df_pop)) == 1

    df_pop_zero = df_pop.copy()
    df_pop_zero["populacao"] = 0
    with pytest.raises(pa.errors.SchemaErrors):
        validar_contrato_populacao(df_pop_zero)

