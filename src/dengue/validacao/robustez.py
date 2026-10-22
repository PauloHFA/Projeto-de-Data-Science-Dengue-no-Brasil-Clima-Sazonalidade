"""Interpretação, robustez, SHAP (TreeSHAP nativo LightGBM), resíduos, sensibilidade e testes de H2 e H3 (Seção 5.7)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from dengue.config import DATA_INICIO_TESTE_FINAL, HORIZONTE_PRINCIPAL, SEED
from dengue.features.engenharia import (
    construir_matriz_features_horizonte,
    listar_colunas_features,
)
from dengue.modelos.estatisticos import ModeloGLMContagem
from dengue.modelos.ml import ModeloLightGBMQuantilico
from dengue.validacao.metricas import bootstrap_blocos_skill, calcular_mae, calcular_rmse


def classificar_porte_populacional(populacao: int | float) -> str:
    """Classifica o porte demográfico do município conforme pré-registrado no plano de análise (H2)."""
    if populacao < 50_000:
        return "1_Pequeno (<50k)"
    if populacao <= 200_000:
        return "2_Medio (50k-200k)"
    return "3_Grande (>200k)"


def avaliar_hipotese_h2_regiao_e_porte(
    df_previsoes_h4: pd.DataFrame,
    painel: pd.DataFrame,
) -> pd.DataFrame:
    """Avalia H2: variação do ganho preditivo do clima por mesorregião paraibana e porte populacional."""
    meta_mun = (
        painel.groupby("municipio", as_index=False)
        .agg(
            nome_municipio=("nome_municipio", "first"),
            mesorregiao=("mesorregiao", "first"),
            populacao_media=("populacao", "mean"),
        )
    )
    meta_mun["porte_populacional"] = meta_mun["populacao_media"].apply(classificar_porte_populacional)

    p_com = df_previsoes_h4[df_previsoes_h4["modelo"] == "LightGBM_Com_Clima"].merge(
        meta_mun, on="municipio", how="left"
    )
    p_sem = df_previsoes_h4[df_previsoes_h4["modelo"] == "LightGBM_Sem_Clima"].merge(
        meta_mun, on="municipio", how="left"
    )
    p_base = df_previsoes_h4[df_previsoes_h4["modelo"] == "Baseline_SeasonalNaive"].merge(
        meta_mun, on="municipio", how="left"
    )

    chave_ordem = ["municipio", "semana"]
    p_com = p_com.sort_values(chave_ordem).reset_index(drop=True)
    p_sem = p_sem.sort_values(chave_ordem).reset_index(drop=True)
    p_base = p_base.sort_values(chave_ordem).reset_index(drop=True)

    registros: list[dict[str, Any]] = []

    for dimensao, col_estrato in [("Mesorregiao", "mesorregiao"), ("Porte_Populacional", "porte_populacional")]:
        for estrato, grp_com in p_com.groupby(col_estrato):
            idx = grp_com.index
            grp_sem = p_sem.loc[idx]
            grp_base = p_base.loc[idx]

            err_com = np.abs(grp_com["y_true"].to_numpy() - grp_com["y_pred"].to_numpy())
            err_sem = np.abs(grp_sem["y_true"].to_numpy() - grp_sem["y_pred"].to_numpy())
            err_base = np.abs(grp_base["y_true"].to_numpy() - grp_base["y_pred"].to_numpy())

            boot_vs_sem = bootstrap_blocos_skill(err_com, err_sem, tamanho_bloco=4, n_boot=1000, seed=SEED)
            boot_vs_base = bootstrap_blocos_skill(err_com, err_base, tamanho_bloco=4, n_boot=1000, seed=SEED)

            registros.append(
                {
                    "dimensao": dimensao,
                    "estrato": str(estrato),
                    "n_municipios": int(grp_com["municipio"].nunique()),
                    "n_observacoes": len(grp_com),
                    "mae_baseline_sazonal": round(float(np.mean(err_base)), 4),
                    "mae_lgbm_sem_clima": round(float(np.mean(err_sem)), 4),
                    "mae_lgbm_com_clima": round(float(np.mean(err_com)), 4),
                    "skill_clima_vs_sem_clima": boot_vs_sem["skill_pontual"],
                    "ic95_inf_vs_sem_clima": boot_vs_sem["skill_ic95_inf"],
                    "ic95_sup_vs_sem_clima": boot_vs_sem["skill_ic95_sup"],
                    "skill_clima_vs_baseline": boot_vs_base["skill_pontual"],
                    "ganho_significativo_ic95": bool(boot_vs_sem["skill_ic95_inf"] > 0.0),
                }
            )

    return pd.DataFrame(registros).sort_values(["dimensao", "estrato"]).reset_index(drop=True)


def avaliar_hipotese_h3_atraso_notificacao(
    df_notificacoes_limpas: pd.DataFrame,
    painel: pd.DataFrame,
    horizontes_curtos: tuple[int, ...] = (1, 2),
) -> pd.DataFrame:
    """Avalia H3: efeito do truncamento por atraso de notificação e ganho da correção de nowcasting (REG-06, REG-14).

    Para cada horizonte curto h in {1, 2}:
    - Na semana de emissão t_emissao = t_alvo - h, os casos da semana t_emissao sofrem censura à direita:
      apenas notificações com atraso_dias <= 7 (uma semana após o início da SE) já foram digitadas.
    - Estima-se a fração de completude f_completude exclusivamente nos dados de treino (< 2023-01-01) por município
      (REG-14: sem vazamento do teste!).
    - Compara-se a previsão no teste final (2023-2024) usando:
      (a) Atributo recente censurado sem correção;
      (b) Atributo recente corrigido pelo fator de nowcasting (casos_censurados / f_completude_treino).
    """
    corte_teste = pd.Timestamp(DATA_INICIO_TESTE_FINAL)

    # Calcula, para cada município e semana, quantos casos foram notificados em até 7 dias e em até 14 dias
    notific = df_notificacoes_limpas.copy()
    notific["notificado_7d"] = (notific["atraso_dias"] <= 7).astype(int)
    notific["notificado_14d"] = (notific["atraso_dias"] <= 14).astype(int)

    agregado_atraso = (
        notific.groupby(["municipio", "semana"], as_index=False)
        .agg(
            casos_7d=("notificado_7d", "sum"),
            casos_14d=("notificado_14d", "sum"),
        )
    )

    painel_atraso = painel.merge(agregado_atraso, on=["municipio", "semana"], how="left")
    painel_atraso["casos_7d"] = painel_atraso["casos_7d"].fillna(0.0)
    painel_atraso["casos_14d"] = painel_atraso["casos_14d"].fillna(0.0)
    painel_atraso["inc_trunc_7d"] = (painel_atraso["casos_7d"] / painel_atraso["populacao"]) * 100_000.0
    painel_atraso["inc_trunc_14d"] = (painel_atraso["casos_14d"] / painel_atraso["populacao"]) * 100_000.0

    # Estima completude empírica APENAS no conjunto de treino (< 2023-01-01) (REG-14)
    treino_hist = painel_atraso[painel_atraso["semana"] < corte_teste]
    fator_7d_mun = (
        treino_hist.groupby("municipio")
        .apply(lambda g: float(np.clip(g["casos_7d"].sum() / max(1.0, g["casos"].sum()), 0.30, 0.98)), include_groups=False)
        .to_dict()
    )
    fator_14d_mun = (
        treino_hist.groupby("municipio")
        .apply(lambda g: float(np.clip(g["casos_14d"].sum() / max(1.0, g["casos"].sum()), 0.50, 0.99)), include_groups=False)
        .to_dict()
    )

    resultados_h3: list[dict[str, Any]] = []

    for h in horizontes_curtos:
        df_feat = construir_matriz_features_horizonte(painel_atraso, horizonte=h)
        _, cols_com_clima = listar_colunas_features(df_feat, horizonte=h)

        # Ajusta o modelo no treino histórico (< 2023)
        df_treino = df_feat[df_feat["semana"] < corte_teste].copy()
        df_teste_real = df_feat[df_feat["semana"] >= corte_teste].copy()

        modelo = ModeloLightGBMQuantilico(cols_com_clima, horizonte=h)
        modelo.fit(df_treino)

        # Constrói a visão em tempo real no teste (com truncamento de digitação nas últimas 2 semanas conhecidas)
        df_teste_censurado = df_teste_real.copy()
        df_teste_nowcast = df_teste_real.copy()

        lag_recente_1 = f"incidencia_100k_lag{h}"
        lag_recente_2 = f"incidencia_100k_lag{h + 1}"

        # Série truncada em lag h (apenas 7 dias de oportunidade de digitação) e lag h+1 (14 dias)
        inc_7d_lag_h = df_feat.groupby("municipio")["inc_trunc_7d"].shift(h).loc[df_teste_real.index]
        inc_14d_lag_h1 = df_feat.groupby("municipio")["inc_trunc_14d"].shift(h + 1).loc[df_teste_real.index]

        df_teste_censurado[lag_recente_1] = inc_7d_lag_h
        df_teste_censurado[lag_recente_2] = inc_14d_lag_h1

        # Recalcula a média móvel de 4 semanas sob censura
        cols_mm = [f"incidencia_100k_lag{k}" for k in range(h, h + 4)]
        df_teste_censurado[f"incidencia_mm4_lag{h}"] = df_teste_censurado[cols_mm].mean(axis=1)

        # Aplica correção de nowcasting usando apenas os fatores aprendidos no treino (REG-14)
        pesos_7d = df_teste_nowcast["municipio"].map(fator_7d_mun).to_numpy(dtype=float)
        pesos_14d = df_teste_nowcast["municipio"].map(fator_14d_mun).to_numpy(dtype=float)

        df_teste_nowcast[lag_recente_1] = inc_7d_lag_h.to_numpy(dtype=float) / pesos_7d
        df_teste_nowcast[lag_recente_2] = inc_14d_lag_h1.to_numpy(dtype=float) / pesos_14d
        df_teste_nowcast[f"incidencia_mm4_lag{h}"] = df_teste_nowcast[cols_mm].mean(axis=1)

        pred_cens = modelo.predict(df_teste_censurado)
        pred_now = modelo.predict(df_teste_nowcast)

        err_cens = np.abs(pred_cens["y_true"].to_numpy() - pred_cens["y_pred"].to_numpy())
        err_now = np.abs(pred_now["y_true"].to_numpy() - pred_now["y_pred"].to_numpy())

        boot = bootstrap_blocos_skill(err_now, err_cens, tamanho_bloco=4, n_boot=1000, seed=SEED)

        resultados_h3.append(
            {
                "horizonte": h,
                "completude_media_7d_treino": round(float(np.mean(list(fator_7d_mun.values()))), 4),
                "mae_sem_correcao_atraso": round(float(np.mean(err_cens)), 4),
                "mae_com_nowcasting_atraso": round(float(np.mean(err_now)), 4),
                "skill_nowcasting": boot["skill_pontual"],
                "ic95_inf": boot["skill_ic95_inf"],
                "ic95_sup": boot["skill_ic95_sup"],
                "h3_suportada_ic95": bool(boot["skill_ic95_inf"] > 0.0),
            }
        )

    return pd.DataFrame(resultados_h3)


def extrair_importancia_shap_e_glm(
    painel: pd.DataFrame,
    horizonte: int = HORIZONTE_PRINCIPAL,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Calcula valores exatos de TreeSHAP (via pred_contrib do LightGBM) e IRRs do GLM no horizonte principal."""
    df_feat = construir_matriz_features_horizonte(painel, horizonte=horizonte)
    _, cols_com_clima = listar_colunas_features(df_feat, horizonte=horizonte)

    corte_teste = pd.Timestamp(DATA_INICIO_TESTE_FINAL)
    df_treino = df_feat[df_feat["semana"] < corte_teste].dropna(subset=cols_com_clima + ["incidencia_100k"]).copy()
    df_teste = df_feat[df_feat["semana"] >= corte_teste].dropna(subset=cols_com_clima + ["incidencia_100k"]).copy()

    # 1. TreeSHAP exato do LightGBM mediano (alpha = 0.50)
    mod_lgbm = ModeloLightGBMQuantilico(cols_com_clima, horizonte=horizonte).fit(df_treino)
    X_teste_scaled = mod_lgbm.escalonador.transform(df_teste)
    booster_mediano = mod_lgbm.modelos_[0.50]

    # pred_contrib=True retorna matriz (n_amostras, n_features + 1) com os valores exatos de TreeSHAP
    contribuicoes_shap = np.asarray(booster_mediano.predict(X_teste_scaled, pred_contrib=True))
    shap_features = contribuicoes_shap[:, :-1]
    media_abs_shap = np.mean(np.abs(shap_features), axis=0)

    def _categorizar_atributo(nome: str) -> str:
        if nome.startswith(("temp_", "chuva_", "umidade_")):
            return "Clima Defasado"
        if nome.startswith(("sen_se", "cos_se")):
            return "Sazonalidade"
        return "Histórico de Casos / Incidência"

    df_shap = (
        pd.DataFrame(
            {
                "atributo": cols_com_clima,
                "grupo_variavel": [_categorizar_atributo(c) for c in cols_com_clima],
                "shap_medio_absoluto": np.round(media_abs_shap, 4),
                "importancia_split": booster_mediano.feature_importances_,
            }
        )
        .sort_values("shap_medio_absoluto", ascending=False)
        .reset_index(drop=True)
    )
    soma_shap = float(df_shap["shap_medio_absoluto"].sum())
    df_shap["participacao_pct"] = np.round(100.0 * df_shap["shap_medio_absoluto"] / max(1e-9, soma_shap), 2)

    # 2. Coeficientes e Razão de Taxas de Incidência (IRR) do GLM Binomial Negativa
    mod_glm = ModeloGLMContagem(cols_com_clima, horizonte=horizonte).fit(df_treino)
    df_coef_glm = mod_glm.extrair_coeficientes()

    return df_shap, df_coef_glm


def analisar_residuos_por_periodo_e_regiao(
    df_previsoes_h4: pd.DataFrame,
    painel: pd.DataFrame,
) -> pd.DataFrame:
    """Analisa resíduos (viés, MAE, RMSE, sub/sobreprevisão) por mesorregião e por estação epidemiológica."""
    meta_mun = painel[["municipio", "nome_municipio", "mesorregiao"]].drop_duplicates(subset=["municipio"])
    df = (
        df_previsoes_h4[df_previsoes_h4["modelo"] == "LightGBM_Com_Clima"]
        .merge(meta_mun, on="municipio", how="left")
        .copy()
    )
    df["residuo"] = df["y_true"] - df["y_pred"]
    df["erro_abs"] = np.abs(df["residuo"])
    df["periodo_sazonal"] = np.where(
        df["se"].between(12, 24),
        "Alta_Transmissao (SE 12-24)",
        "Baixa_Transmissao (Demais SE)",
    )

    linhas: list[dict[str, Any]] = []
    for (meso, periodo), grp in df.groupby(["mesorregiao", "periodo_sazonal"]):
        linhas.append(
            {
                "mesorregiao": str(meso),
                "periodo_sazonal": str(periodo),
                "n_semanas_mun": len(grp),
                "incidencia_observada_media": round(float(grp["y_true"].mean()), 2),
                "incidencia_prevista_media": round(float(grp["y_pred"].mean()), 2),
                "vies_medio_residuo": round(float(grp["residuo"].mean()), 4),
                "mae": round(calcular_mae(grp["y_true"], grp["y_pred"]), 4),
                "rmse": round(calcular_rmse(grp["y_true"], grp["y_pred"]), 4),
                "cobertura_80": round(float(((grp["y_true"] >= grp["li_80"]) & (grp["y_true"] <= grp["ls_80"])).mean()), 4),
                "cobertura_95": round(float(((grp["y_true"] >= grp["li_95"]) & (grp["y_true"] <= grp["ls_95"])).mean()), 4),
            }
        )

    return pd.DataFrame(linhas).sort_values(["mesorregiao", "periodo_sazonal"]).reset_index(drop=True)


def avaliar_sensibilidade_limpeza_e_pandemia(
    df_notificacoes_limpas: pd.DataFrame,
    df_pop: pd.DataFrame,
    df_clima: pd.DataFrame,
    painel_padrao: pd.DataFrame,
    horizonte: int = HORIZONTE_PRINCIPAL,
) -> pd.DataFrame:
    """Avalia a sensibilidade dos resultados a escolhas de limpeza e ao período pandêmico (Seção 5.7 e 11).

    Compara 3 cenários no conjunto de teste final (2023-2024):
    1. Cenario_1_Padrao: Casos prováveis (CLASSI_FIN != '5'), treino completo (2015-2022).
    2. Cenario_2_Sem_Pandemia_COVID: Exclui do treino os anos pandêmicos 2020 e 2021 (Seção 11).
    3. Cenario_3_Apenas_Confirmados: Exclui também casos inconclusivos (CLASSI_FIN == '8'), mantendo apenas 10, 11 e 12.
    """
    from dengue.qualidade.limpeza import construir_painel_semanal

    corte_teste = pd.Timestamp(DATA_INICIO_TESTE_FINAL)
    cenarios_resultados: list[dict[str, Any]] = []

    # Prepara painel do Cenário 3 (apenas confirmados 10, 11, 12)
    notific_confirmados = df_notificacoes_limpas[
        df_notificacoes_limpas["CLASSI_FIN"].isin(["10", "11", "12"])
    ].copy()
    painel_confirmados = construir_painel_semanal(notific_confirmados, df_pop=df_pop, df_clima=df_clima)

    definicoes_cenarios = [
        ("1_Padrao_Casos_Provaveis_2015_2022", painel_padrao, False),
        ("2_Excluindo_Pandemia_COVID_2020_2021", painel_padrao, True),
        ("3_Restrito_Confirmados_Sem_Inconclusivos", painel_confirmados, False),
    ]

    for nome_cenario, painel_cen, excluir_covid in definicoes_cenarios:
        df_feat = construir_matriz_features_horizonte(painel_cen, horizonte=horizonte)
        cols_sem_clima, cols_com_clima = listar_colunas_features(df_feat, horizonte=horizonte)

        df_treino = df_feat[df_feat["semana"] < corte_teste].copy()
        if excluir_covid:
            df_treino = df_treino[~df_treino["ano"].isin([2020, 2021])].copy()

        df_teste = df_feat[df_feat["semana"] >= corte_teste].copy()

        mod_com = ModeloLightGBMQuantilico(cols_com_clima, horizonte=horizonte).fit(df_treino)
        mod_sem = ModeloLightGBMQuantilico(cols_sem_clima, horizonte=horizonte).fit(df_treino)

        pred_com = mod_com.predict(df_teste)
        pred_sem = mod_sem.predict(df_teste)

        err_com = np.abs(pred_com["y_true"].to_numpy() - pred_com["y_pred"].to_numpy())
        err_sem = np.abs(pred_sem["y_true"].to_numpy() - pred_sem["y_pred"].to_numpy())
        boot = bootstrap_blocos_skill(err_com, err_sem, tamanho_bloco=4, n_boot=1000, seed=SEED)

        cenarios_resultados.append(
            {
                "cenario": nome_cenario,
                "horizonte": horizonte,
                "n_linhas_treino": len(df_treino),
                "mae_sem_clima": round(float(np.mean(err_sem)), 4),
                "mae_com_clima": round(float(np.mean(err_com)), 4),
                "skill_clima_vs_sem_clima": boot["skill_pontual"],
                "ic95_inf": boot["skill_ic95_inf"],
                "ic95_sup": boot["skill_ic95_sup"],
                "conclusao_h1_robusta": bool(boot["skill_ic95_inf"] > 0.0),
            }
        )

    return pd.DataFrame(cenarios_resultados)

