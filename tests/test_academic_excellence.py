"""Testes unitários dos módulos de excelência acadêmica: Malha IBGE, LISA, DLNM e Sócio-Ecologia."""

from __future__ import annotations

import numpy as np
import pandas as pd

from dengue.features.socio_ecologia import estimar_vulnerabilidade_hidrica_municipal, obter_anomalias_oceanicas_enso
from dengue.modelos.dlnm import ModeloDLNM, construir_cross_basis_dlnm
from dengue.validacao.espacial_lisa import calcular_lisa_local_moran, construir_vizinhanca_queen_geojson


def test_obter_anomalias_oceanicas_enso(tmp_path) -> None:
    """Verifica que a série de anomalias ENSO (Niño 3.4) cobre o período de estudo."""
    df_enso = obter_anomalias_oceanicas_enso(ano_inicio=2020, ano_fim=2022, diretorio_raw=tmp_path)
    assert len(df_enso) == 36
    assert "nino34_anomalia" in df_enso.columns
    assert "fase_enso" in df_enso.columns


def test_estimar_vulnerabilidade_hidrica() -> None:
    """Verifica cálculo do índice de vulnerabilidade hídrica domiciliar (IVHD) no semiárido."""
    df_mun = pd.DataFrame(
        {
            "municipio": ["250750", "251080"],
            "nome_municipio": ["João Pessoa", "Patos"],
            "mesorregiao": ["Mata Paraibana", "Sertao Paraibano"],
            "populacao": [833932, 103165],
        }
    )
    df_ivhd = estimar_vulnerabilidade_hidrica_municipal(df_mun)
    assert len(df_ivhd) == 2
    # Sertão tem maior vulnerabilidade de armazenamento doméstico do que a capital litorânea
    ivhd_patos = df_ivhd.loc[df_ivhd["municipio"] == "251080", "indice_vulnerabilidade_hidrica"].iloc[0]
    ivhd_jp = df_ivhd.loc[df_ivhd["municipio"] == "250750", "indice_vulnerabilidade_hidrica"].iloc[0]
    assert ivhd_patos > ivhd_jp


def test_dlnm_cross_basis_e_ajuste() -> None:
    """Verifica geração da cross-basis bidimensional e cálculo de risco relativo do DLNM."""
    temp = np.linspace(22.0, 31.0, 50)
    W, nomes = construir_cross_basis_dlnm(temp, lags=(1, 2, 4))
    assert W.shape[0] == 50
    assert len(nomes) > 0

    df_painel = pd.DataFrame(
        {
            "semana": pd.date_range("2023-01-01", periods=40, freq="W-SUN"),
            "se": range(1, 41),
            "temp_media": np.linspace(24.0, 29.0, 40),
            "casos": np.random.poisson(15, 40),
            "populacao": [500_000] * 40,
        }
    )
    dlnm = ModeloDLNM().fit(df_painel)
    df_rr = dlnm.calcular_superficie_risco_relativo(lags=(1, 2, 4))
    assert len(df_rr) > 0
    assert "risco_relativo_rr" in df_rr.columns
    assert (df_rr["risco_relativo_rr"] > 0).all()
