"""Engenharia de atributos defasados, médias móveis e sazonalidade sem vazamento (REG-01, REG-14)."""

from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd

from dengue.config import MAX_LAG_CASOS, MAX_LAG_CLIMA


def verificar_features_respeitam_horizonte(
    colunas_de_features: Sequence[str],
    horizonte: int,
) -> None:
    """Garante que nenhum atributo defasado use informação posterior a t - horizonte (REG-01, Seção 9.4)."""
    if horizonte < 1:
        raise ValueError(f"O horizonte de previsão deve ser >= 1, recebido: {horizonte}")

    for nome in colunas_de_features:
        if "_lag" in nome:
            sufixo = nome.split("_lag")[1].split("_")[0]
            k = int(sufixo)
            if k < horizonte:
                raise ValueError(
                    f"Violação de REG-01 (vazamento temporal): '{nome}' usa lag={k} < horizonte={horizonte}"
                )


def adicionar_defasagens(
    painel: pd.DataFrame,
    colunas: Sequence[str],
    defasagens: Sequence[int],
    horizonte: int | None = None,
) -> pd.DataFrame:
    """Adiciona colunas defasadas por município (Seção 9.2), bloqueando lags < horizonte (REG-01)."""
    if len(defasagens) == 0:
        raise ValueError("A sequência de defasagens não pode ser vazia.")

    min_lag = min(defasagens)
    if min_lag < 1:
        raise ValueError(f"Toda defasagem deve ser k >= 1 (passado). Recebido k={min_lag}.")
    if horizonte is not None and min_lag < horizonte:
        raise ValueError(
            f"Violação de REG-01: defasagem mínima k={min_lag} é menor que o horizonte h={horizonte}."
        )

    df = painel.sort_values(["municipio", "semana"]).copy()
    agrupado = df.groupby("municipio", sort=False)

    for col in colunas:
        for k in defasagens:
            df[f"{col}_lag{k}"] = agrupado[col].shift(k)

    return df


def adicionar_atributos_sazonais(painel: pd.DataFrame) -> pd.DataFrame:
    """Adiciona harmônicos sazonais (seno e cosseno da Semana Epidemiológica) e tendência determinística."""
    df = painel.copy()
    se_num = df["se"].astype(float)
    df["sen_se_1"] = np.sin(2.0 * np.pi * se_num / 52.18)
    df["cos_se_1"] = np.cos(2.0 * np.pi * se_num / 52.18)
    df["sen_se_2"] = np.sin(4.0 * np.pi * se_num / 52.18)
    df["cos_se_2"] = np.cos(4.0 * np.pi * se_num / 52.18)
    return df


def construir_matriz_features_horizonte(
    painel: pd.DataFrame,
    horizonte: int = 4,
    max_lag_casos: int = MAX_LAG_CASOS,
    max_lag_clima: int = MAX_LAG_CLIMA,
) -> pd.DataFrame:
    """Constrói a matriz de atributos estritamente admissível para o horizonte h (REG-01).

    Para horizonte h:
    - Atributos autorregressivos de incidência e casos usam lags k in [h, max(h + 4, max_lag_casos)].
    - Atributos climáticos usam lags k in [h, max_lag_clima].
    - Médias móveis de 4 semanas são calculadas a partir do lag h (isto é, cobrindo t - h - 3 até t - h).
    """
    if horizonte < 1:
        raise ValueError(f"Horizonte deve ser >= 1, recebido: {horizonte}")

    limite_casos = max(horizonte + 4, max_lag_casos)
    limite_clima = max(horizonte + 4, max_lag_clima)

    lags_casos = list(range(horizonte, limite_casos + 1))
    lags_clima = list(range(horizonte, limite_clima + 1))

    df = adicionar_atributos_sazonais(painel)
    df = adicionar_defasagens(
        df,
        colunas=["incidencia_100k", "casos"],
        defasagens=lags_casos,
        horizonte=horizonte,
    )
    df = adicionar_defasagens(
        df,
        colunas=["temp_media", "chuva_acum", "umidade_media"],
        defasagens=lags_clima,
        horizonte=horizonte,
    )

    # Médias móveis ancoradas em k = horizonte (usa apenas lags >= horizonte)
    cols_mm_inc = [f"incidencia_100k_lag{k}" for k in range(horizonte, min(horizonte + 4, limite_casos + 1))]
    cols_mm_temp = [f"temp_media_lag{k}" for k in range(horizonte, min(horizonte + 4, limite_clima + 1))]
    cols_mm_chuva = [f"chuva_acum_lag{k}" for k in range(horizonte, min(horizonte + 4, limite_clima + 1))]

    df[f"incidencia_mm4_lag{horizonte}"] = df[cols_mm_inc].mean(axis=1)
    df[f"temp_media_mm4_lag{horizonte}"] = df[cols_mm_temp].mean(axis=1)
    df[f"chuva_acum_mm4_lag{horizonte}"] = df[cols_mm_chuva].sum(axis=1)

    # Verifica formalmente que todas as features geradas respeitam REG-01
    cols_sem_clima, cols_com_clima = listar_colunas_features(df, horizonte=horizonte)
    verificar_features_respeitam_horizonte(cols_com_clima, horizonte=horizonte)
    verificar_features_respeitam_horizonte(cols_sem_clima, horizonte=horizonte)

    return df


def listar_colunas_features(
    df: pd.DataFrame,
    horizonte: int,
) -> tuple[list[str], list[str]]:
    """Retorna (features_sem_clima, features_com_clima) para comparação controlada de H1."""
    sazonais = ["sen_se_1", "cos_se_1", "sen_se_2", "cos_se_2"]
    lags_inc = [
        c
        for c in df.columns
        if (c.startswith("incidencia_100k_lag") or c.startswith("incidencia_mm4_lag"))
    ]
    lags_clima = [
        c
        for c in df.columns
        if (
            c.startswith("temp_media_lag")
            or c.startswith("chuva_acum_lag")
            or c.startswith("umidade_media_lag")
            or c.startswith("temp_media_mm4_lag")
            or c.startswith("chuva_acum_mm4_lag")
        )
    ]

    features_sem_clima = sazonais + lags_inc
    features_com_clima = features_sem_clima + lags_clima

    verificar_features_respeitam_horizonte(features_com_clima, horizonte=horizonte)
    return features_sem_clima, features_com_clima


class EscalonadorPorDobra:
    """Pré-processador que aprende média, desvio-padrão e mediana de imputação apenas no treino (REG-14)."""

    def __init__(self) -> None:
        self.medianas_: pd.Series | None = None
        self.medias_: pd.Series | None = None
        self.desvios_: pd.Series | None = None
        self.colunas_: list[str] = []

    def fit(self, df_treino: pd.DataFrame, colunas: Sequence[str]) -> EscalonadorPorDobra:
        """Ajusta estatísticas exclusivamente na partição de treino da dobra atual (REG-14)."""
        self.colunas_ = list(colunas)
        sub = df_treino[self.colunas_].astype(float)
        self.medianas_ = sub.median(axis=0).fillna(0.0)
        preenchido = sub.fillna(self.medianas_)
        self.medias_ = preenchido.mean(axis=0)
        desvios = preenchido.std(axis=0, ddof=0)
        self.desvios_ = desvios.replace(0.0, 1.0).fillna(1.0)
        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Aplica imputação e padronização usando apenas os parâmetros aprendidos no treino."""
        if self.medianas_ is None or self.medias_ is None or self.desvios_ is None:
            raise RuntimeError("EscalonadorPorDobra deve ser ajustado com .fit(df_treino) antes de .transform().")

        sub = df[self.colunas_].astype(float).fillna(self.medianas_)
        escalonado = (sub - self.medias_) / self.desvios_
        return escalonado

    def fit_transform(self, df_treino: pd.DataFrame, colunas: Sequence[str]) -> pd.DataFrame:
        """Ajusta no treino e retorna os atributos transformados do próprio treino."""
        return self.fit(df_treino, colunas).transform(df_treino)

