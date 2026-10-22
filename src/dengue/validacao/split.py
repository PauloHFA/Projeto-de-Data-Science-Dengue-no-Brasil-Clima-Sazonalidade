"""Validação temporal rolling-origin (janela expansiva) e isolamento do teste final (REG-01, REG-02, REG-07)."""

from __future__ import annotations

from typing import Iterator

import pandas as pd

from dengue.config import DATA_INICIO_TESTE_FINAL


def separar_desenvolvimento_e_teste_final(
    painel: pd.DataFrame,
    data_inicio_teste_final: str = DATA_INICIO_TESTE_FINAL,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Separa cronologicamente o conjunto de desenvolvimento/validação e o conjunto de teste final único (REG-07)."""
    corte = pd.Timestamp(data_inicio_teste_final)
    dev = painel[painel["semana"] < corte].copy().reset_index(drop=True)
    teste_final = painel[painel["semana"] >= corte].copy().reset_index(drop=True)
    return dev, teste_final


def rolling_origin(
    painel: pd.DataFrame,
    inicio_teste: str | pd.Timestamp,
    horizonte: int = 4,
    passo: int = 1,
) -> Iterator[tuple[pd.DataFrame, pd.DataFrame]]:
    """Gerador de validação rolling-origin com janela expansiva (Seção 9.3, REG-01 e REG-02).

    Para cada semana alvo `corte`:
    - O conjunto de treino contém apenas registros com `semana <= corte - horizonte semanas`
      (rótulos efetivamente observados no momento de emissão da previsão).
    - O conjunto de teste contém os registros da semana alvo `semana == corte`.
    """
    if horizonte < 1:
        raise ValueError(f"O horizonte deve ser >= 1, recebido: {horizonte}")
    if passo < 1:
        raise ValueError(f"O passo deve ser >= 1, recebido: {passo}")

    semanas = sorted(pd.to_datetime(painel["semana"].unique()))
    ts_inicio = pd.Timestamp(inicio_teste)

    candidatas = [s for s in semanas if s >= ts_inicio]
    if not candidatas:
        raise ValueError(f"Nenhuma semana encontrada a partir de inicio_teste={inicio_teste}")

    idx_inicio = semanas.index(candidatas[0])
    cortes = semanas[idx_inicio::passo]

    for corte in cortes:
        limite_treino = corte - pd.Timedelta(weeks=horizonte)
        treino = painel[painel["semana"] <= limite_treino].copy()
        teste = painel[painel["semana"] == corte].copy()
        if len(treino) > 0 and len(teste) > 0:
            yield treino, teste

