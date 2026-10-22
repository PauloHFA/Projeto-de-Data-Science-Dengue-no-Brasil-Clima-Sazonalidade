"""Métricas de avaliação pontual, intervalar (WIS, cobertura) e bootstrap em blocos (REG-03, REG-04, Seção 10)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from dengue.config import SEED


def calcular_mae(y_true: np.ndarray | pd.Series, y_pred: np.ndarray | pd.Series) -> float:
    """Erro Absoluto Médio (MAE) em unidades de incidência por 100 mil habitantes."""
    yt = np.asarray(y_true, dtype=float)
    yp = np.asarray(y_pred, dtype=float)
    return float(np.mean(np.abs(yt - yp)))


def calcular_rmse(y_true: np.ndarray | pd.Series, y_pred: np.ndarray | pd.Series) -> float:
    """Raiz do Erro Quadrático Médio (RMSE), penalizando erros em semanas de pico."""
    yt = np.asarray(y_true, dtype=float)
    yp = np.asarray(y_pred, dtype=float)
    return float(np.sqrt(np.mean((yt - yp) ** 2)))


def calcular_skill_relativo(mae_modelo: float, mae_baseline: float) -> float:
    """Skill relativo = 1 - MAE_modelo / MAE_baseline (Seção 10). Valor > 0 indica ganho."""
    if mae_baseline <= 0.0:
        return 0.0
    return float(1.0 - (mae_modelo / mae_baseline))


def calcular_pinball_loss(
    y_true: np.ndarray | pd.Series,
    y_quantil: np.ndarray | pd.Series,
    alpha: float,
) -> float:
    """Perda quantílica (Pinball Loss) para o nível quantílico alpha in (0, 1)."""
    yt = np.asarray(y_true, dtype=float)
    yq = np.asarray(y_quantil, dtype=float)
    erro = yt - yq
    perda = np.maximum(alpha * erro, (alpha - 1.0) * erro)
    return float(np.mean(perda))


def calcular_score_intervalo(
    y_true: np.ndarray | pd.Series,
    limite_inferior: np.ndarray | pd.Series,
    limite_superior: np.ndarray | pd.Series,
    cobertura_nominal: float = 0.80,
) -> np.ndarray:
    """Interval Score de Gneiting & Raftery (2007) para um intervalo central (1 - alpha)."""
    yt = np.asarray(y_true, dtype=float)
    li = np.asarray(limite_inferior, dtype=float)
    ls = np.asarray(limite_superior, dtype=float)
    alpha = 1.0 - cobertura_nominal

    largura = np.maximum(0.0, ls - li)
    penalidade_abaixo = (2.0 / alpha) * np.maximum(0.0, li - yt)
    penalidade_acima = (2.0 / alpha) * np.maximum(0.0, yt - ls)
    return largura + penalidade_abaixo + penalidade_acima


def calcular_wis(
    y_true: np.ndarray | pd.Series,
    mediana: np.ndarray | pd.Series,
    li_80: np.ndarray | pd.Series,
    ls_80: np.ndarray | pd.Series,
    li_95: np.ndarray | pd.Series,
    ls_95: np.ndarray | pd.Series,
) -> float:
    """Weighted Interval Score (WIS) conforme Bracher et al. (2021) para mediana + IC 80% + IC 95% (REG-04)."""
    yt = np.asarray(y_true, dtype=float)
    med = np.asarray(mediana, dtype=float)

    # Pesos padrão w_0 = 0.5 e w_k = alpha_k / 2 para K = 2 intervalos (80% -> alpha=0.20, 95% -> alpha=0.05)
    alpha_80 = 0.20
    alpha_95 = 0.05
    is_80 = calcular_score_intervalo(yt, li_80, ls_80, cobertura_nominal=0.80)
    is_95 = calcular_score_intervalo(yt, li_95, ls_95, cobertura_nominal=0.95)

    numerador = 0.5 * np.abs(yt - med) + (alpha_80 / 2.0) * is_80 + (alpha_95 / 2.0) * is_95
    denominador = 0.5 + (alpha_80 / 2.0) + (alpha_95 / 2.0)
    return float(np.mean(numerador / denominador))


def calcular_cobertura_empirica(
    y_true: np.ndarray | pd.Series,
    limite_inferior: np.ndarray | pd.Series,
    limite_superior: np.ndarray | pd.Series,
) -> float:
    """Fração empírica de observações contidas no intervalo preditivo [limite_inferior, limite_superior] (REG-04)."""
    yt = np.asarray(y_true, dtype=float)
    li = np.asarray(limite_inferior, dtype=float)
    ls = np.asarray(limite_superior, dtype=float)
    dentro = (yt >= li) & (yt <= ls)
    return float(np.mean(dentro))


def calcular_erro_pico(df_previsoes: pd.DataFrame) -> dict[str, float]:
    """Calcula o erro absoluto médio na magnitude do pico anual e na semana epidemiológica do pico (Seção 10)."""
    erros_mag: list[float] = []
    erros_se: list[float] = []

    df = df_previsoes.copy()
    if "ano" not in df.columns:
        df["ano"] = pd.to_datetime(df["semana"]).dt.year
    if "se" not in df.columns:
        df["se"] = pd.to_datetime(df["semana"]).dt.isocalendar().week.astype(int)

    for (_mun, _ano), grupo in df.groupby(["municipio", "ano"]):
        if len(grupo) < 4:
            continue
        idx_real = grupo["y_true"].idxmax()
        idx_pred = grupo["y_pred"].idxmax()

        pico_real = float(grupo.loc[idx_real, "y_true"])
        pico_pred = float(grupo.loc[idx_pred, "y_pred"])
        se_real = int(grupo.loc[idx_real, "se"])
        se_pred = int(grupo.loc[idx_pred, "se"])

        erros_mag.append(abs(pico_real - pico_pred))
        diff_se = abs(se_real - se_pred)
        erros_se.append(float(min(diff_se, 52 - diff_se)))

    return {
        "erro_magnitude_pico": float(np.mean(erros_mag)) if erros_mag else 0.0,
        "erro_semana_pico": float(np.mean(erros_se)) if erros_se else 0.0,
    }


def bootstrap_blocos_skill(
    erros_abs_modelo: np.ndarray | pd.Series,
    erros_abs_baseline: np.ndarray | pd.Series,
    tamanho_bloco: int = 4,
    n_boot: int = 1000,
    seed: int = SEED,
) -> dict[str, float]:
    """Calcula o Intervalo de Confiança de 95% para o Skill Relativo via Moving Block Bootstrap (REG-03)."""
    em = np.asarray(erros_abs_modelo, dtype=float)
    eb = np.asarray(erros_abs_baseline, dtype=float)
    n = len(em)
    if n == 0 or len(eb) != n:
        raise ValueError("Vetores de erro devem ter o mesmo tamanho não vazio.")

    skill_pontual = calcular_skill_relativo(float(np.mean(em)), float(np.mean(eb)))
    b_len = max(1, min(tamanho_bloco, n))
    n_blocos = int(np.ceil(n / b_len))
    rng = np.random.default_rng(seed)

    skills_boot = np.empty(n_boot, dtype=float)
    max_inicio = max(1, n - b_len + 1)

    for b in range(n_boot):
        inicios = rng.integers(0, max_inicio, size=n_blocos)
        indices = np.concatenate([np.arange(ini, ini + b_len) for ini in inicios])[:n]
        mae_m = float(np.mean(em[indices]))
        mae_b = float(np.mean(eb[indices]))
        skills_boot[b] = calcular_skill_relativo(mae_m, mae_b)

    ic_inf, ic_sup = np.percentile(skills_boot, [2.5, 97.5])
    return {
        "skill_pontual": round(skill_pontual, 4),
        "skill_ic95_inf": round(float(ic_inf), 4),
        "skill_ic95_sup": round(float(ic_sup), 4),
    }


def resumir_metricas_modelo(
    df_previsoes: pd.DataFrame,
    erros_baseline_referencia: np.ndarray | None = None,
) -> dict[str, Any]:
    """Consolida todas as métricas obrigatórias da Seção 10 e REG-03/REG-04 para um conjunto de previsões."""
    yt = df_previsoes["y_true"].to_numpy(dtype=float)
    yp = df_previsoes["y_pred"].to_numpy(dtype=float)
    li80 = df_previsoes["li_80"].to_numpy(dtype=float)
    ls80 = df_previsoes["ls_80"].to_numpy(dtype=float)
    li95 = df_previsoes["li_95"].to_numpy(dtype=float)
    ls95 = df_previsoes["ls_95"].to_numpy(dtype=float)

    mae = calcular_mae(yt, yp)
    rmse = calcular_rmse(yt, yp)
    wis = calcular_wis(yt, yp, li80, ls80, li95, ls95)
    cob80 = calcular_cobertura_empirica(yt, li80, ls80)
    cob95 = calcular_cobertura_empirica(yt, li95, ls95)
    picos = calcular_erro_pico(df_previsoes)

    resumo: dict[str, Any] = {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "wis": round(wis, 4),
        "cobertura_80": round(cob80, 4),
        "cobertura_95": round(cob95, 4),
        "erro_magnitude_pico": round(picos["erro_magnitude_pico"], 4),
        "erro_semana_pico": round(picos["erro_semana_pico"], 4),
    }

    if erros_baseline_referencia is not None:
        erros_mod = np.abs(yt - yp)
        boot = bootstrap_blocos_skill(erros_mod, erros_baseline_referencia)
        resumo.update(boot)
    else:
        resumo["skill_pontual"] = 0.0
        resumo["skill_ic95_inf"] = 0.0
        resumo["skill_ic95_sup"] = 0.0

    return resumo

