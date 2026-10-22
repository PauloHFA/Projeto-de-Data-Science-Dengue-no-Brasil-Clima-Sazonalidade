"""Testes unitários para ModeloSARIMAX e Ingestão InfoDengue (REG-10)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from dengue.ingestao.infodengue import carregar_ou_baixar_infodengue_pb
from dengue.modelos.estatisticos import ModeloSARIMAX


def test_modelo_sarimax_ajuste_e_previsao() -> None:
    """Verifica que o ModeloSARIMAX roda e gera intervalos 80% e 95% sem erro."""
    semanas = pd.date_range("2022-01-02", periods=30, freq="W-SUN")
    dados = []
    for dt in semanas:
        dados.append(
            {
                "municipio": "250750",
                "semana": dt,
                "se": int(dt.isocalendar().week),
                "incidencia_100k": float(np.random.uniform(5, 40)),
                "temp_media_lag4": 26.5,
                "chuva_acum_lag5": 12.0,
            }
        )
    df = pd.DataFrame(dados)
    treino = df.iloc[:24]
    teste = df.iloc[24:]

    mod = ModeloSARIMAX(colunas_features=["temp_media_lag4", "chuva_acum_lag5"], horizonte=4)
    mod.fit(treino)
    pred = mod.predict(teste)

    assert len(pred) == len(teste)
    assert (pred["y_pred"] >= 0.0).all()
    assert (pred["li_80"] <= pred["ls_80"]).all()
    assert (pred["li_95"] <= pred["ls_95"]).all()


def test_carregar_infodengue_pb(tmp_path) -> None:
    """Verifica chamada e persistência do benchmark InfoDengue."""
    df_pop = pd.DataFrame(
        {
            "municipio": ["250750"],
            "municipio_ibge7": ["2507507"],
            "nome_municipio": ["João Pessoa"],
        }
    )
    df_info = carregar_ou_baixar_infodengue_pb(df_pop, diretorio_raw=tmp_path, limite_municipios=1)
    assert isinstance(df_info, pd.DataFrame)
    assert (tmp_path / "infodengue_benchmark_pb.parquet").exists()
