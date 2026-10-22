"""Gradient Boosting (LightGBM) com perda quantílica e calibração conformal (Seção 5.5, REG-04, REG-14)."""

from __future__ import annotations

from typing import Sequence

import lightgbm as lgb
import numpy as np
import pandas as pd

from dengue.config import SEED
from dengue.features.engenharia import EscalonadorPorDobra, verificar_features_respeitam_horizonte


class ModeloLightGBMQuantilico:
    """Modelo LightGBM com regressão quantílica para previsão pontual e intervalos de 80% e 95% (REG-04)."""

    QUANTIS: tuple[float, ...] = (0.025, 0.10, 0.50, 0.90, 0.975)

    def __init__(
        self,
        colunas_features: Sequence[str],
        horizonte: int = 4,
        n_estimators: int = 80,
        learning_rate: float = 0.06,
        num_leaves: int = 15,
        seed: int = SEED,
    ) -> None:
        verificar_features_respeitam_horizonte(colunas_features, horizonte=horizonte)
        self.colunas_features = list(colunas_features)
        self.horizonte = horizonte
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.num_leaves = num_leaves
        self.seed = seed
        self.escalonador = EscalonadorPorDobra()
        self.modelos_: dict[float, lgb.LGBMRegressor] = {}
        self.ajuste_conformal_80_: float = 0.0
        self.ajuste_conformal_95_: float = 0.0

    def fit(self, df_treino: pd.DataFrame) -> ModeloLightGBMQuantilico:
        """Treina os 5 regressores quantílicos e calibra as margens nas últimas 26 semanas do treino (REG-14)."""
        df = df_treino.dropna(subset=self.colunas_features + ["incidencia_100k"]).sort_values("semana").copy()

        # Separa os últimos 15% cronológicos do próprio treino para calibração conformal de intervalos (sem tocar no teste!)
        semanas_treino = sorted(df["semana"].unique())
        n_sem = len(semanas_treino)
        corte_cal = semanas_treino[max(1, int(0.85 * n_sem))]

        df_subtreino = df[df["semana"] < corte_cal]
        df_cal = df[df["semana"] >= corte_cal]
        if len(df_subtreino) < 50 or len(df_cal) < 10:
            df_subtreino = df
            df_cal = df

        X_sub = self.escalonador.fit_transform(df_subtreino, self.colunas_features)
        y_sub = df_subtreino["incidencia_100k"].to_numpy(dtype=float)

        self.modelos_ = {}
        for q in self.QUANTIS:
            reg = lgb.LGBMRegressor(
                objective="quantile",
                alpha=q,
                n_estimators=self.n_estimators,
                learning_rate=self.learning_rate,
                num_leaves=self.num_leaves,
                min_child_samples=15,
                subsample=0.85,
                colsample_bytree=0.85,
                random_state=self.seed + int(q * 1000),
                verbose=-1,
                n_jobs=1,
            )
            reg.fit(X_sub, y_sub)
            self.modelos_[q] = reg

        # Calibração conformal dividida (Split Conformal Quantile Regression - Romano et al., 2019) no bloco de calibração
        X_cal = self.escalonador.transform(df_cal)
        y_cal = df_cal["incidencia_100k"].to_numpy(dtype=float)
        q10 = np.maximum(0.0, self.modelos_[0.10].predict(X_cal))
        q90 = np.maximum(q10, self.modelos_[0.90].predict(X_cal))
        q025 = np.maximum(0.0, self.modelos_[0.025].predict(X_cal))
        q975 = np.maximum(q025, self.modelos_[0.975].predict(X_cal))

        escore_80 = np.maximum(q10 - y_cal, y_cal - q90)
        escore_95 = np.maximum(q025 - y_cal, y_cal - q975)
        self.ajuste_conformal_80_ = float(np.quantile(escore_80, 0.80))
        self.ajuste_conformal_95_ = float(np.quantile(escore_95, 0.95))

        # Reajusta com 100% do treino mantendo a correção conformal aprendida
        X_all = self.escalonador.fit_transform(df, self.colunas_features)
        y_all = df["incidencia_100k"].to_numpy(dtype=float)
        for q, reg in self.modelos_.items():
            reg.fit(X_all, y_all)

        return self

    def predict(self, df_teste: pd.DataFrame) -> pd.DataFrame:
        """Retorna mediana preditiva e intervalos calibrados de 80% e 95% sem cruzamento de quantis."""
        if not self.modelos_:
            raise RuntimeError("ModeloLightGBMQuantilico precisa ser ajustado com .fit() antes de .predict().")

        X_test = self.escalonador.transform(df_teste)
        preds = {q: np.maximum(0.0, reg.predict(X_test)) for q, reg in self.modelos_.items()}

        # Ordena quantis para evitar quantile crossing
        matriz_q = np.column_stack([preds[0.025], preds[0.10], preds[0.50], preds[0.90], preds[0.975]])
        matriz_q_ord = np.sort(matriz_q, axis=1)

        y_pred = matriz_q_ord[:, 2]
        li_80 = np.maximum(0.0, matriz_q_ord[:, 1] - self.ajuste_conformal_80_)
        ls_80 = np.maximum(y_pred, matriz_q_ord[:, 3] + self.ajuste_conformal_80_)
        li_95 = np.maximum(0.0, matriz_q_ord[:, 0] - self.ajuste_conformal_95_)
        ls_95 = np.maximum(ls_80, matriz_q_ord[:, 4] + self.ajuste_conformal_95_)

        return pd.DataFrame(
            {
                "municipio": df_teste["municipio"].to_numpy(),
                "semana": df_teste["semana"].to_numpy(),
                "se": df_teste["se"].to_numpy(),
                "y_true": df_teste["incidencia_100k"].to_numpy(dtype=float),
                "y_pred": y_pred,
                "li_80": li_80,
                "ls_80": ls_80,
                "li_95": li_95,
                "ls_95": ls_95,
            }
        )

    def importancia_atributos(self) -> pd.DataFrame:
        """Retorna a importância dos atributos do modelo mediano (alpha=0.50)."""
        if 0.50 not in self.modelos_:
            raise RuntimeError("Modelo mediano não ajustado.")
        imp = self.modelos_[0.50].feature_importances_
        return (
            pd.DataFrame({"atributo": self.colunas_features, "importancia_split": imp})
            .sort_values("importancia_split", ascending=False)
            .reset_index(drop=True)
        )

