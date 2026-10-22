"""Testes das métricas epidemiológicas (MAE, RMSE, Skill, WIS, cobertura, bootstrap) e Baselines (REG-03, REG-04)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from dengue.modelos.baselines import ModeloPersistencia, ModeloSeasonalNaive
from dengue.validacao.metricas import (
    bootstrap_blocos_skill,
    calcular_cobertura_empirica,
    calcular_mae,
    calcular_rmse,
    calcular_skill_relativo,
    calcular_wis,
)


def test_metricas_pontuais_e_intervalares() -> None:
    """Verifica cálculo exato de MAE, RMSE, Skill, WIS e cobertura empírica (Seção 10, REG-04)."""
    y_true = np.array([10.0, 20.0, 30.0, 40.0])
    y_pred = np.array([12.0, 18.0, 33.0, 37.0])
    li_80 = y_pred - 4.0
    ls_80 = y_pred + 4.0
    li_95 = y_pred - 8.0
    ls_95 = y_pred + 8.0

    mae = calcular_mae(y_true, y_pred)
    rmse = calcular_rmse(y_true, y_pred)
    wis = calcular_wis(y_true, y_pred, li_80, ls_80, li_95, ls_95)
    cob80 = calcular_cobertura_empirica(y_true, li_80, ls_80)
    cob95 = calcular_cobertura_empirica(y_true, li_95, ls_95)

    assert np.isclose(mae, 2.5)
    assert rmse >= mae
    assert wis > 0.0
    assert np.isclose(cob80, 1.0)
    assert np.isclose(cob95, 1.0)
    assert np.isclose(calcular_skill_relativo(2.5, 5.0), 0.5)


def test_bootstrap_em_blocos_intervalo_confianca() -> None:
    """Verifica que o bootstrap em blocos produz IC 95% > 0 quando o modelo é consistentemente superior (REG-03)."""
    erros_mod = np.full(40, 2.0)
    erros_base = np.full(40, 5.0)
    res = bootstrap_blocos_skill(erros_mod, erros_base, tamanho_bloco=4, n_boot=200)
    assert np.isclose(res["skill_pontual"], 0.6)
    assert res["skill_ic95_inf"] > 0.5


def test_baselines_geram_intervalos_validos() -> None:
    """Verifica que Seasonal Naive e Persistência geram previsões e intervalos não negativos (REG-03, REG-04)."""
    semanas = pd.date_range("2021-01-03", periods=70, freq="W-SUN")
    df = pd.DataFrame(
        {
            "municipio": ["250750"] * len(semanas),
            "semana": semanas,
            "se": [int(s.isocalendar().week) for s in semanas],
            "incidencia_100k": np.linspace(5.0, 50.0, len(semanas)),
            "incidencia_100k_lag4": np.roll(np.linspace(5.0, 50.0, len(semanas)), 4),
        }
    )
    treino = df.iloc[:60].copy()
    teste = df.iloc[60:].copy()

    m_saz = ModeloSeasonalNaive(horizonte=4).fit(treino)
    p_saz = m_saz.predict(teste)
    assert (p_saz["li_95"] <= p_saz["li_80"]).all()
    assert (p_saz["li_80"] <= p_saz["y_pred"]).all()
    assert (p_saz["y_pred"] <= p_saz["ls_80"]).all()
    assert (p_saz["ls_80"] <= p_saz["ls_95"]).all()

    m_per = ModeloPersistencia(horizonte=4).fit(treino)
    p_per = m_per.predict(teste)
    assert len(p_per) == len(teste)
    assert (p_per["y_pred"] >= 0.0).all()

