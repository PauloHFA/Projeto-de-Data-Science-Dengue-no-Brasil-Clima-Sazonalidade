"""Modelos estatísticos interpretáveis: GLM Binomial Negativa / Poisson via statsmodels (Seção 5.5)."""

from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd
import statsmodels.api as sm

from dengue.features.engenharia import EscalonadorPorDobra, verificar_features_respeitam_horizonte


class ModeloGLMContagem:
    """Regressão Binomial Negativa / Poisson com offset demográfico e intervalos preditivos calibrados."""

    def __init__(self, colunas_features: Sequence[str], horizonte: int = 4, alpha_disp: float = 0.5) -> None:
        verificar_features_respeitam_horizonte(colunas_features, horizonte=horizonte)
        # Remove médias móveis (_mm4_) que são combinações lineares exatas dos lags individuais (evita matriz singular no GLM)
        cols_nao_colineares = [c for c in colunas_features if "_mm4_" not in c]
        self.colunas_features = cols_nao_colineares if cols_nao_colineares else list(colunas_features)
        self.horizonte = horizonte
        self.alpha_disp = alpha_disp
        self.escalonador = EscalonadorPorDobra()
        self.resultado_glm_: Any = None
        self.q80_rel_: float = 0.45
        self.q95_rel_: float = 0.85
        self.q80_abs_: float = 3.0
        self.q95_abs_: float = 6.0

    def fit(self, df_treino: pd.DataFrame) -> ModeloGLMContagem:
        """Ajusta o GLM nos casos contados com offset log(populacao / 100_000) exclusivamente no treino."""
        df = df_treino.dropna(subset=self.colunas_features + ["casos", "populacao"]).copy()
        X_scaled = self.escalonador.fit_transform(df, self.colunas_features)
        X_design = sm.add_constant(X_scaled, has_constant="add")

        offset = np.log(np.maximum(1.0, df["populacao"].to_numpy(dtype=float)) / 100_000.0)
        y_casos = df["casos"].to_numpy(dtype=float)

        familia = sm.families.NegativeBinomial(alpha=self.alpha_disp)
        modelo = sm.GLM(y_casos, X_design, family=familia, offset=offset)
        self.resultado_glm_ = modelo.fit(maxiter=100, disp=False)

        # Calibra quantis residuais no próprio treino para intervalos 80% e 95%
        casos_hat = np.clip(self.resultado_glm_.predict(X_design, offset=offset), 0.0, 1e6)
        inc_hat = (casos_hat / df["populacao"].to_numpy(dtype=float)) * 100_000.0
        inc_real = df["incidencia_100k"].to_numpy(dtype=float)
        erros_abs = np.abs(inc_real - inc_hat)
        escala = np.maximum(2.0, np.sqrt(inc_hat + 1.0))
        erros_norm = erros_abs / escala

        self.q80_rel_ = float(np.quantile(erros_norm, 0.80))
        self.q95_rel_ = float(np.quantile(erros_norm, 0.95))
        self.q80_abs_ = float(np.quantile(erros_abs, 0.80))
        self.q95_abs_ = float(np.quantile(erros_abs, 0.95))
        return self

    def predict(self, df_teste: pd.DataFrame) -> pd.DataFrame:
        """Gera previsão pontual de incidência e intervalos de 80% e 95% para df_teste."""
        if self.resultado_glm_ is None:
            raise RuntimeError("ModeloGLMContagem deve ser ajustado com .fit() antes de .predict().")

        X_scaled = self.escalonador.transform(df_teste)
        X_design = sm.add_constant(X_scaled, has_constant="add")
        pop = np.maximum(1.0, df_teste["populacao"].to_numpy(dtype=float))
        offset = np.log(pop / 100_000.0)

        casos_pred = np.clip(self.resultado_glm_.predict(X_design, offset=offset), 0.0, 1e6)
        y_pred = (casos_pred / pop) * 100_000.0

        escala = np.maximum(2.0, np.sqrt(y_pred + 1.0))
        margem_80 = np.maximum(0.5 * self.q80_abs_, self.q80_rel_ * escala)
        margem_95 = np.maximum(0.5 * self.q95_abs_, self.q95_rel_ * escala)

        return pd.DataFrame(
            {
                "municipio": df_teste["municipio"].to_numpy(),
                "semana": df_teste["semana"].to_numpy(),
                "se": df_teste["se"].to_numpy(),
                "y_true": df_teste["incidencia_100k"].to_numpy(dtype=float),
                "y_pred": y_pred,
                "li_80": np.maximum(0.0, y_pred - margem_80),
                "ls_80": y_pred + margem_80,
                "li_95": np.maximum(0.0, y_pred - margem_95),
                "ls_95": y_pred + margem_95,
            }
        )

    def extrair_coeficientes(self) -> pd.DataFrame:
        """Retorna os coeficientes padronizados e intervalos de confiança do GLM para interpretação (Seção 5.7)."""
        if self.resultado_glm_ is None:
            raise RuntimeError("Modelo não ajustado.")
        params = self.resultado_glm_.params
        pvals = self.resultado_glm_.pvalues
        ic = self.resultado_glm_.conf_int()
        df_coef = pd.DataFrame(
            {
                "variavel": params.index,
                "coeficiente": params.values,
                "razao_taxas_irr": np.exp(params.values),
                "ic95_inf": ic[0].values,
                "ic95_sup": ic[1].values,
                "p_valor": pvals.values,
            }
        )
        return df_coef.reset_index(drop=True)


class ModeloSARIMAX:
    """Modelo clássico SARIMAX com variáveis exógenas defasadas (Seção 5.5, referência clássica de séries)."""

    def __init__(
        self,
        colunas_features: Sequence[str] | None = None,
        horizonte: int = 4,
        order: tuple[int, int, int] = (1, 1, 1),
    ) -> None:
        if colunas_features is not None:
            verificar_features_respeitam_horizonte(colunas_features, horizonte=horizonte)
            cols_nao_colineares = [c for c in colunas_features if "_mm4_" not in c]
            self.colunas_features = cols_nao_colineares if cols_nao_colineares else list(colunas_features)
        else:
            self.colunas_features = []
        self.horizonte = horizonte
        self.order = order
        self.escalonador = EscalonadorPorDobra()
        self.modelos_mun_: dict[str, Any] = {}
        self.q80_global_: float = 5.0
        self.q95_global_: float = 10.0

    def fit(self, df_treino: pd.DataFrame) -> ModeloSARIMAX:
        """Ajusta modelos SARIMAX rápidos por município com variáveis exógenas no treino (REG-14)."""
        from statsmodels.tsa.statespace.sarimax import SARIMAX

        df = df_treino.sort_values(["municipio", "semana"]).copy()
        if self.colunas_features:
            self.escalonador.fit(df, self.colunas_features)

        erros_treino = []
        for mun, grp in df.groupby("municipio"):
            y_s = grp["incidencia_100k"].to_numpy(dtype=float)
            exog = None
            if self.colunas_features:
                exog = self.escalonador.transform(grp).to_numpy(dtype=float)

            try:
                # Usa SARIMAX com enforce_stationarity=False e solver lbfgs para velocidade e convergência robusta
                mod = SARIMAX(
                    y_s,
                    exog=exog,
                    order=self.order,
                    enforce_stationarity=False,
                    enforce_invertibility=False,
                )
                res = mod.fit(disp=False, maxiter=25)
                self.modelos_mun_[str(mun)] = res
                residuos = np.abs(res.resid)
                erros_treino.extend(residuos[~np.isnan(residuos)].tolist())
            except Exception:
                self.modelos_mun_[str(mun)] = None

        if erros_treino:
            self.q80_global_ = float(np.quantile(erros_treino, 0.80))
            self.q95_global_ = float(np.quantile(erros_treino, 0.95))

        return self

    def predict(self, df_teste: pd.DataFrame) -> pd.DataFrame:
        """Gera previsões pontuais e intervalos de 80% e 95% para df_teste."""
        preds = []
        for _, row in df_teste.iterrows():
            mun = str(row["municipio"])
            res = self.modelos_mun_.get(mun)
            exog_row = None
            if self.colunas_features:
                exog_row = self.escalonador.transform(pd.DataFrame([row])).to_numpy(dtype=float)

            y_hat = 0.0
            if res is not None:
                try:
                    f = res.forecast(steps=1, exog=exog_row)
                    y_hat = float(max(0.0, f[0]))
                except Exception:
                    y_hat = float(max(0.0, row.get(f"incidencia_100k_lag{self.horizonte}", 0.0)))
            else:
                y_hat = float(max(0.0, row.get(f"incidencia_100k_lag{self.horizonte}", 0.0)))

            preds.append(y_hat)

        y_pred = np.array(preds, dtype=float)
        return pd.DataFrame(
            {
                "municipio": df_teste["municipio"].to_numpy(),
                "semana": df_teste["semana"].to_numpy(),
                "se": df_teste["se"].to_numpy(),
                "y_true": df_teste["incidencia_100k"].to_numpy(dtype=float),
                "y_pred": y_pred,
                "li_80": np.maximum(0.0, y_pred - self.q80_global_),
                "ls_80": y_pred + self.q80_global_,
                "li_95": np.maximum(0.0, y_pred - self.q95_global_),
                "ls_95": y_pred + self.q95_global_,
            }
        )


