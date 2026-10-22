"""Testes anti-vazamento temporal (REG-01 e REG-14, Seção 9.4)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from dengue.features.engenharia import (
    EscalonadorPorDobra,
    adicionar_defasagens,
    construir_matriz_features_horizonte,
    listar_colunas_features,
    verificar_features_respeitam_horizonte,
)


def _criar_painel_sintetico() -> pd.DataFrame:
    datas = pd.date_range("2022-01-02", periods=30, freq="W-SUN")
    linhas = []
    for mun in ("250750", "250400"):
        for idx, dt in enumerate(datas):
            linhas.append(
                {
                    "municipio": mun,
                    "semana": dt,
                    "ano": dt.year,
                    "se": int(dt.isocalendar().week),
                    "casos": 10 + idx,
                    "populacao": 400_000,
                    "incidencia_100k": float(10 + idx) * 0.25,
                    "temp_media": 25.0 + 0.1 * idx,
                    "chuva_acum": 15.0 + idx,
                    "umidade_media": 75.0,
                }
            )
    return pd.DataFrame(linhas)


@pytest.mark.parametrize("horizonte", [1, 2, 4, 8])
def test_features_respeitam_horizonte(horizonte: int) -> None:
    """Verifica que todas as features geradas para o horizonte h usam apenas lags k >= h (REG-01, Seção 9.4)."""
    painel = _criar_painel_sintetico()
    df_feat = construir_matriz_features_horizonte(painel, horizonte=horizonte)
    cols_sem_clima, cols_com_clima = listar_colunas_features(df_feat, horizonte=horizonte)

    for nome in cols_com_clima:
        if "_lag" in nome:
            k = int(nome.split("_lag")[1].split("_")[0])
            assert k >= horizonte, f"{nome} usa informação posterior ao momento da previsão (k={k} < h={horizonte})"

    assert len(cols_com_clima) > len(cols_sem_clima)


def test_bloqueio_explicito_de_lag_menor_que_horizonte() -> None:
    """Garante que tentar criar ou validar lag < horizonte dispara ValueError (REG-01)."""
    painel = _criar_painel_sintetico()
    with pytest.raises(ValueError, match="REG-01"):
        adicionar_defasagens(painel, ["incidencia_100k"], defasagens=[1, 2, 3], horizonte=4)

    with pytest.raises(ValueError, match="REG-01"):
        verificar_features_respeitam_horizonte(["temp_media_lag2", "chuva_acum_lag4"], horizonte=4)


def test_escalonador_por_dobra_nao_vaza_estatisticas_do_teste() -> None:
    """Garante que o pré-processamento ajusta parâmetros apenas no treino de cada dobra (REG-14)."""
    df_treino = pd.DataFrame({"x": [10.0, 20.0, 30.0], "y": [1.0, 2.0, np.nan]})
    # Teste possui valores extremos (10000) que jamais podem alterar a média/desvio do escalonador
    df_teste = pd.DataFrame({"x": [10000.0, 20000.0], "y": [np.nan, 500.0]})

    esc = EscalonadorPorDobra()
    esc.fit(df_treino, colunas=["x", "y"])

    assert np.isclose(esc.medias_["x"], 20.0)
    assert np.isclose(esc.medianas_["y"], 1.5)

    teste_transformado = esc.transform(df_teste)
    # Em y, o NaN no teste deve ser imputado com a mediana do treino (1.5), resultando em z-score 0.0
    assert np.isclose(teste_transformado.loc[0, "y"], 0.0)

