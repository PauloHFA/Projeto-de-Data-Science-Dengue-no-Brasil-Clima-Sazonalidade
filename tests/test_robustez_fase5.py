"""Testes unitários da Fase 5: H2 (região/porte), resíduos e classificação demográfica (REG-10)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from dengue.validacao.robustez import (
    analisar_residuos_por_periodo_e_regiao,
    avaliar_hipotese_h2_regiao_e_porte,
    classificar_porte_populacional,
)


def test_classificar_porte_populacional() -> None:
    """Verifica a estratificação demográfica pré-registrada para H2."""
    assert classificar_porte_populacional(22_000) == "1_Pequeno (<50k)"
    assert classificar_porte_populacional(103_000) == "2_Medio (50k-200k)"
    assert classificar_porte_populacional(833_932) == "3_Grande (>200k)"


def test_avaliar_h2_e_analisar_residuos() -> None:
    """Verifica que H2 e a análise de resíduos calculam métricas estratificadas sem erro."""
    semanas = pd.date_range("2023-01-01", periods=16, freq="W-SUN")
    painel_rows = []
    pred_rows = []

    municipios = [
        ("250750", "João Pessoa", "Mata Paraibana", 833_932),
        ("251080", "Patos", "Sertao Paraibano", 103_165),
        ("250110", "Areia", "Agreste Paraibano", 22_633),
    ]

    for mun, nome, meso, pop in municipios:
        for s in semanas:
            se = int(s.isocalendar().week)
            y_real = 25.0 + (10.0 if 12 <= se <= 24 else 0.0)
            painel_rows.append(
                {
                    "municipio": mun,
                    "nome_municipio": nome,
                    "mesorregiao": meso,
                    "populacao": pop,
                    "semana": s,
                    "se": se,
                    "incidencia_100k": y_real,
                }
            )
            for mod, erro in [
                ("LightGBM_Com_Clima", 2.0),
                ("LightGBM_Sem_Clima", 5.0),
                ("Baseline_SeasonalNaive", 8.0),
            ]:
                pred_rows.append(
                    {
                        "municipio": mun,
                        "semana": s,
                        "se": se,
                        "modelo": mod,
                        "y_true": y_real,
                        "y_pred": y_real - erro,
                        "li_80": y_real - 6.0,
                        "ls_80": y_real + 6.0,
                        "li_95": y_real - 10.0,
                        "ls_95": y_real + 10.0,
                    }
                )

    df_painel = pd.DataFrame(painel_rows)
    df_preds = pd.DataFrame(pred_rows)

    df_h2 = avaliar_hipotese_h2_regiao_e_porte(df_preds, df_painel)
    assert set(df_h2["dimensao"]) == {"Mesorregiao", "Porte_Populacional"}
    assert (df_h2["skill_clima_vs_sem_clima"] > 0.0).all()

    df_res = analisar_residuos_por_periodo_e_regiao(df_preds, df_painel)
    assert len(df_res) > 0
    assert np.allclose(df_res["mae"], 2.0)

