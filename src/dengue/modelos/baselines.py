"""Baselines honestos para previsão de incidência semanal de dengue (Seção 5.5, REG-03 e REG-04)."""

from __future__ import annotations

import numpy as np
import pandas as pd


class ModeloSeasonalNaive:
    """Baseline 1: Seasonal Naive (mesma Semana Epidemiológica do ano anterior / perfil sazonal histórico).

    Gera intervalos preditivos de 80% e 95% baseados nos quantis empíricos dos resíduos absolutos no treino (REG-14).
    """

    def __init__(self, horizonte: int = 4) -> None:
        self.horizonte = horizonte
        self.perfil_se_mun_: pd.DataFrame | None = None
        self.q80_mun_: dict[str, float] = {}
        self.q95_mun_: dict[str, float] = {}
        self.q80_global_: float = 5.0
        self.q95_global_: float = 10.0

    def fit(self, df_treino: pd.DataFrame) -> ModeloSeasonalNaive:
        """Ajusta os valores de referência sazonal e quantis de erro exclusivamente no conjunto de treino."""
        df = df_treino.sort_values(["municipio", "semana"]).copy()
        df["lag_52"] = df.groupby("municipio")["incidencia_100k"].shift(52)

        # Média sazonal histórica por (municipio, se) no treino como fallback para o primeiro ano
        perfil = (
            df.groupby(["municipio", "se"], as_index=False)["incidencia_100k"]
            .median()
            .rename(columns={"incidencia_100k": "mediana_se"})
        )
        # Último valor observado na mesma SE no treino
        ultimo_se = (
            df.groupby(["municipio", "se"], as_index=False)["incidencia_100k"]
            .last()
            .rename(columns={"incidencia_100k": "ultimo_valor_se"})
        )
        self.perfil_se_mun_ = perfil.merge(ultimo_se, on=["municipio", "se"], how="left")

        valido = df.dropna(subset=["lag_52"])
        if len(valido) > 0:
            residuos_abs = np.abs(valido["incidencia_100k"] - valido["lag_52"])
            self.q80_global_ = float(np.quantile(residuos_abs, 0.80))
            self.q95_global_ = float(np.quantile(residuos_abs, 0.95))
            for mun, grp in valido.groupby("municipio"):
                erros_m = np.abs(grp["incidencia_100k"] - grp["lag_52"])
                self.q80_mun_[str(mun)] = float(np.quantile(erros_m, 0.80))
                self.q95_mun_[str(mun)] = float(np.quantile(erros_m, 0.95))
        return self

    def predict(self, df_teste: pd.DataFrame) -> pd.DataFrame:
        """Retorna previsões pontuais e intervalos de 80% e 95% para o conjunto de teste."""
        if self.perfil_se_mun_ is None:
            raise RuntimeError("ModeloSeasonalNaive precisa ser ajustado com .fit() antes de .predict().")

        df = df_teste[["municipio", "semana", "se", "incidencia_100k"]].copy()
        df = df.merge(self.perfil_se_mun_, on=["municipio", "se"], how="left")

        y_pred = df["ultimo_valor_se"].fillna(df["mediana_se"]).fillna(0.0).clip(lower=0.0).to_numpy(dtype=float)
        raios_80 = np.array([self.q80_mun_.get(str(m), self.q80_global_) for m in df["municipio"]], dtype=float)
        raios_95 = np.array([self.q95_mun_.get(str(m), self.q95_global_) for m in df["municipio"]], dtype=float)

        return pd.DataFrame(
            {
                "municipio": df["municipio"].to_numpy(),
                "semana": df["semana"].to_numpy(),
                "se": df["se"].to_numpy(),
                "y_true": df["incidencia_100k"].to_numpy(dtype=float),
                "y_pred": y_pred,
                "li_80": np.maximum(0.0, y_pred - raios_80),
                "ls_80": y_pred + raios_80,
                "li_95": np.maximum(0.0, y_pred - raios_95),
                "ls_95": y_pred + raios_95,
            }
        )


class ModeloPersistencia:
    """Baseline 2: Persistência (último valor conhecido no momento da previsão: lag = horizonte)."""

    def __init__(self, horizonte: int = 4) -> None:
        self.horizonte = horizonte
        self.col_lag = f"incidencia_100k_lag{horizonte}"
        self.q80_mun_: dict[str, float] = {}
        self.q95_mun_: dict[str, float] = {}
        self.q80_global_: float = 5.0
        self.q95_global_: float = 10.0

    def fit(self, df_treino: pd.DataFrame) -> ModeloPersistencia:
        """Estima a dispersão empírica dos erros de persistência no horizonte h usando apenas o treino (REG-14)."""
        df = df_treino.dropna(subset=[self.col_lag, "incidencia_100k"]).copy()
        if len(df) > 0:
            residuos_abs = np.abs(df["incidencia_100k"] - df[self.col_lag])
            self.q80_global_ = float(np.quantile(residuos_abs, 0.80))
            self.q95_global_ = float(np.quantile(residuos_abs, 0.95))
            for mun, grp in df.groupby("municipio"):
                erros_m = np.abs(grp["incidencia_100k"] - grp[self.col_lag])
                self.q80_mun_[str(mun)] = float(np.quantile(erros_m, 0.80))
                self.q95_mun_[str(mun)] = float(np.quantile(erros_m, 0.95))
        return self

    def predict(self, df_teste: pd.DataFrame) -> pd.DataFrame:
        """Retorna previsões pontuais (y_{t-h}) e intervalos de 80% e 95%."""
        y_pred = df_teste[self.col_lag].fillna(0.0).clip(lower=0.0).to_numpy(dtype=float)
        raios_80 = np.array([self.q80_mun_.get(str(m), self.q80_global_) for m in df_teste["municipio"]], dtype=float)
        raios_95 = np.array([self.q95_mun_.get(str(m), self.q95_global_) for m in df_teste["municipio"]], dtype=float)

        return pd.DataFrame(
            {
                "municipio": df_teste["municipio"].to_numpy(),
                "semana": df_teste["semana"].to_numpy(),
                "se": df_teste["se"].to_numpy(),
                "y_true": df_teste["incidencia_100k"].to_numpy(dtype=float),
                "y_pred": y_pred,
                "li_80": np.maximum(0.0, y_pred - raios_80),
                "ls_80": y_pred + raios_80,
                "li_95": np.maximum(0.0, y_pred - raios_95),
                "ls_95": y_pred + raios_95,
            }
        )

