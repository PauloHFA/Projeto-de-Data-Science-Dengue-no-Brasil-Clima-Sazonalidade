"""Módulos de validação temporal rolling-origin (REG-02), métricas (REG-03, REG-04) e robustez/interpretação (Fase 5)."""

from dengue.validacao.metricas import (
    bootstrap_blocos_skill,
    calcular_cobertura_empirica,
    calcular_erro_pico,
    calcular_mae,
    calcular_pinball_loss,
    calcular_rmse,
    calcular_skill_relativo,
    calcular_wis,
    resumir_metricas_modelo,
)
from dengue.validacao.robustez import (
    analisar_residuos_por_periodo_e_regiao,
    avaliar_hipotese_h2_regiao_e_porte,
    avaliar_hipotese_h3_atraso_notificacao,
    avaliar_sensibilidade_limpeza_e_pandemia,
    classificar_porte_populacional,
    extrair_importancia_shap_e_glm,
)
from dengue.validacao.split import rolling_origin, separar_desenvolvimento_e_teste_final

__all__ = [
    "rolling_origin",
    "separar_desenvolvimento_e_teste_final",
    "calcular_mae",
    "calcular_rmse",
    "calcular_skill_relativo",
    "calcular_pinball_loss",
    "calcular_wis",
    "calcular_cobertura_empirica",
    "calcular_erro_pico",
    "bootstrap_blocos_skill",
    "resumir_metricas_modelo",
    "classificar_porte_populacional",
    "avaliar_hipotese_h2_regiao_e_porte",
    "avaliar_hipotese_h3_atraso_notificacao",
    "extrair_importancia_shap_e_glm",
    "analisar_residuos_por_periodo_e_regiao",
    "avaliar_sensibilidade_limpeza_e_pandemia",
]
