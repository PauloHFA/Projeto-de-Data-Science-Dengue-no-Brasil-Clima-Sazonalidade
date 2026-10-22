"""Testes da validação rolling-origin e isolamento do teste final (REG-01, REG-02, REG-07)."""

from __future__ import annotations

import pandas as pd

from dengue.validacao.split import rolling_origin, separar_desenvolvimento_e_teste_final


def test_rolling_origin_respeita_horizonte_e_ordem_cronologica() -> None:
    """Verifica que em cada corte do rolling-origin o treino termina em <= corte - horizonte (REG-02)."""
    semanas = pd.date_range("2021-01-03", periods=40, freq="W-SUN")
    painel = pd.DataFrame(
        {
            "municipio": ["250750"] * len(semanas),
            "semana": semanas,
            "incidencia_100k": range(len(semanas)),
        }
    )

    horizonte = 4
    inicio_teste = semanas[20]
    dobras = list(rolling_origin(painel, inicio_teste=inicio_teste, horizonte=horizonte, passo=2))

    assert len(dobras) > 0
    tamanho_treino_anterior = 0

    for treino, teste in dobras:
        corte_atual = teste["semana"].min()
        max_treino = treino["semana"].max()
        assert max_treino <= corte_atual - pd.Timedelta(weeks=horizonte)
        # Janela expansiva: o conjunto de treino cresce monotonicamente a cada passo
        assert len(treino) > tamanho_treino_anterior
        tamanho_treino_anterior = len(treino)


def test_separacao_desenvolvimento_e_teste_final_sem_sobreposicao() -> None:
    """Garante que o conjunto de desenvolvimento e o teste final são estritamente disjuntos no tempo (REG-07)."""
    semanas = pd.date_range("2022-06-05", periods=60, freq="W-SUN")
    painel = pd.DataFrame({"municipio": ["250750"] * len(semanas), "semana": semanas})

    dev, teste_final = separar_desenvolvimento_e_teste_final(painel, data_inicio_teste_final="2023-01-01")
    assert dev["semana"].max() < pd.Timestamp("2023-01-01")
    assert teste_final["semana"].min() >= pd.Timestamp("2023-01-01")
    assert len(dev) + len(teste_final) == len(painel)

