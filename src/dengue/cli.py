"""Interface de Linha de Comando (CLI) para execução reprodutível do pipeline de ponta a ponta (REG-08)."""

from __future__ import annotations

import json
import sys
from typing import Any

import numpy as np
import pandas as pd

from dengue.config import (
    DATA_INICIO_TESTE_FINAL,
    DATA_INICIO_VALIDACAO,
    HORIZONTE_PRINCIPAL,
    HORIZONTES,
    INTERIM_DIR,
    PROCESSED_DIR,
    RAW_DIR,
    REPORTS_DIR,
)
from dengue.features.engenharia import (
    construir_matriz_features_horizonte,
    listar_colunas_features,
)
from dengue.ingestao.ibge import carregar_ou_baixar_populacao_pb
from dengue.ingestao.infodengue import (
    carregar_ou_baixar_infodengue_pb,
    comparar_com_benchmark_infodengue,
)
from dengue.ingestao.inmet import carregar_ou_baixar_clima_pb
from dengue.ingestao.sinan import carregar_ou_baixar_sinan_pb
from dengue.modelos.baselines import ModeloPersistencia, ModeloSeasonalNaive
from dengue.modelos.estatisticos import ModeloGLMContagem
from dengue.modelos.ml import ModeloLightGBMQuantilico
from dengue.qualidade.contratos import validar_contrato_clima, validar_contrato_populacao
from dengue.qualidade.limpeza import construir_painel_semanal, limpar_notificacoes_com_funil
from dengue.validacao.metricas import bootstrap_blocos_skill, resumir_metricas_modelo
from dengue.validacao.robustez import (
    analisar_residuos_por_periodo_e_regiao,
    avaliar_hipotese_h2_regiao_e_porte,
    avaliar_hipotese_h3_atraso_notificacao,
    avaliar_sensibilidade_limpeza_e_pandemia,
    extrair_importancia_shap_e_glm,
)
from dengue.validacao.split import rolling_origin, separar_desenvolvimento_e_teste_final
from dengue.visualizacao.graficos import (
    calcular_associacao_defasagens_p2,
    calcular_autocorrelacao_espacial_moran_p4,
    clusterizar_perfis_sazonais_p3,
    gerar_figuras_relatorio,
)


def etapa_data() -> pd.DataFrame:
    """Fase 1: Ingestão de dados (PB), validação de contratos Pandera e limpeza com funil de exclusão."""
    print("[1/4] Executando ingestão e controle de qualidade (UF = PB)...")
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    df_pop = validar_contrato_populacao(carregar_ou_baixar_populacao_pb(RAW_DIR))
    df_clima = validar_contrato_clima(carregar_ou_baixar_clima_pb(RAW_DIR))
    df_sinan_bruto = carregar_ou_baixar_sinan_pb(df_pop=df_pop, df_clima=df_clima, diretorio_raw=RAW_DIR)

    municipios_pb = df_pop["municipio"].unique().tolist()
    df_limpo, df_funil = limpar_notificacoes_com_funil(df_sinan_bruto, municipios_validos=municipios_pb)

    df_limpo.to_parquet(INTERIM_DIR / "sinan_notificacoes_limpas_pb.parquet", index=False)
    df_funil.to_csv(INTERIM_DIR / "funil_exclusao_sinan_pb.csv", index=False)

    painel = construir_painel_semanal(df_limpo, df_pop=df_pop, df_clima=df_clima)
    painel.to_parquet(PROCESSED_DIR / "painel_semanal_pb.parquet", index=False)

    print(f"  -> Notificações brutas: {len(df_sinan_bruto)} | Casos prováveis limpos: {len(df_limpo)}")
    print(f"  -> Painel semanal salvo com {len(painel)} linhas ({painel['municipio'].nunique()} municípios da PB).")
    return painel


def etapa_features() -> dict[int, pd.DataFrame]:
    """Fase 3/4: Engenharia de atributos defasados sem vazamento temporal para h in {1, 2, 4, 8}."""
    print("[2/4] Construindo matrizes de atributos sem vazamento temporal (REG-01)...")
    caminho_painel = PROCESSED_DIR / "painel_semanal_pb.parquet"
    if not caminho_painel.exists():
        painel = etapa_data()
    else:
        painel = pd.read_parquet(caminho_painel)

    matrizes: dict[int, pd.DataFrame] = {}
    for h in HORIZONTES:
        df_feat = construir_matriz_features_horizonte(painel, horizonte=h)
        caminho_h = PROCESSED_DIR / f"painel_features_pb_h{h}.parquet"
        df_feat.to_parquet(caminho_h, index=False)
        matrizes[h] = df_feat
        print(f"  -> Horizonte h={h} semanas: {df_feat.shape[1]} colunas validadas contra vazamento.")
    return matrizes


def _avaliar_horizonte_rolling_origin(
    df_feat: pd.DataFrame,
    horizonte: int,
    inicio_avaliacao: str,
    passo_semanas: int = 4,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Executa avaliação rolling-origin para todos os modelos em um horizonte específico."""
    cols_sem_clima, cols_com_clima = listar_colunas_features(df_feat, horizonte=horizonte)

    # Passo de 4 semanas no rolling-origin para reajuste periódico eficiente mantendo avaliação de todas as semanas
    semanas = sorted(pd.to_datetime(df_feat["semana"].unique()))
    ts_ini = pd.Timestamp(inicio_avaliacao)
    semanas_alvo = [s for s in semanas if s >= ts_ini]

    blocos_previsoes: list[pd.DataFrame] = []

    for idx_bloco in range(0, len(semanas_alvo), passo_semanas):
        corte = semanas_alvo[idx_bloco]
        janelas_teste = semanas_alvo[idx_bloco : idx_bloco + passo_semanas]
        limite_treino = corte - pd.Timedelta(weeks=horizonte)

        df_treino = df_feat[df_feat["semana"] <= limite_treino].copy()
        df_teste = df_feat[df_feat["semana"].isin(janelas_teste)].copy()
        if len(df_treino) < 100 or len(df_teste) == 0:
            continue

        modelos = {
            "Baseline_SeasonalNaive": ModeloSeasonalNaive(horizonte=horizonte),
            "Baseline_Persistencia": ModeloPersistencia(horizonte=horizonte),
            "GLM_Sem_Clima": ModeloGLMContagem(cols_sem_clima, horizonte=horizonte),
            "GLM_Com_Clima": ModeloGLMContagem(cols_com_clima, horizonte=horizonte),
            "LightGBM_Sem_Clima": ModeloLightGBMQuantilico(cols_sem_clima, horizonte=horizonte),
            "LightGBM_Com_Clima": ModeloLightGBMQuantilico(cols_com_clima, horizonte=horizonte),
        }

        for nome_mod, mod in modelos.items():
            mod.fit(df_treino)
            pred = mod.predict(df_teste)
            pred["modelo"] = nome_mod
            pred["horizonte"] = horizonte
            blocos_previsoes.append(pred)

    df_preds = pd.concat(blocos_previsoes, ignore_index=True)

    # Identifica o melhor baseline no horizonte para cálculo de Skill e IC 95% (REG-03)
    preds_b1 = df_preds[df_preds["modelo"] == "Baseline_SeasonalNaive"]
    preds_b2 = df_preds[df_preds["modelo"] == "Baseline_Persistencia"]
    mae_b1 = float(np.mean(np.abs(preds_b1["y_true"] - preds_b1["y_pred"])))
    mae_b2 = float(np.mean(np.abs(preds_b2["y_true"] - preds_b2["y_pred"])))
    melhor_base_df = preds_b1 if mae_b1 <= mae_b2 else preds_b2
    erros_melhor_base = np.abs(melhor_base_df["y_true"].to_numpy() - melhor_base_df["y_pred"].to_numpy())

    # Também calcula ganho direto Clima vs Sem Clima (H1)
    resumos = []
    for nome_mod, grp in df_preds.groupby("modelo", sort=False):
        metricas = resumir_metricas_modelo(grp, erros_baseline_referencia=erros_melhor_base)
        metricas["horizonte"] = horizonte
        metricas["modelo"] = nome_mod
        resumos.append(metricas)

    df_resumo = pd.DataFrame(resumos).sort_values(["horizonte", "mae"]).reset_index(drop=True)
    return df_resumo, df_preds


def etapa_train() -> pd.DataFrame:
    """Fase 3/4: Treinamento e validação rolling-origin e avaliação única no teste final (2023-2024)."""
    print("[3/4] Executando validação rolling-origin e comparação de modelos (REG-02, REG-03, REG-04)...")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    todas_metricas_val: list[pd.DataFrame] = []
    todas_metricas_teste: list[pd.DataFrame] = []
    preds_h4_teste: pd.DataFrame | None = None
    comparacoes_h1: list[dict[str, Any]] = []

    for h in HORIZONTES:
        caminho_h = PROCESSED_DIR / f"painel_features_pb_h{h}.parquet"
        if not caminho_h.exists():
            etapa_features()
        df_feat = pd.read_parquet(caminho_h)

        # 1. Validação Rolling-Origin no conjunto de desenvolvimento (2019–2022)
        df_dev, _ = separar_desenvolvimento_e_teste_final(df_feat, DATA_INICIO_TESTE_FINAL)
        res_val, _ = _avaliar_horizonte_rolling_origin(
            df_dev,
            horizonte=h,
            inicio_avaliacao=DATA_INICIO_VALIDACAO,
            passo_semanas=8,
        )
        res_val["particao"] = "validacao_2019_2022"
        todas_metricas_val.append(res_val)

        # 2. Avaliação no Conjunto de Teste Final (2023–2024) usando rolling-origin
        res_teste, preds_teste = _avaliar_horizonte_rolling_origin(
            df_feat,
            horizonte=h,
            inicio_avaliacao=DATA_INICIO_TESTE_FINAL,
            passo_semanas=8,
        )
        res_teste["particao"] = "teste_final_2023_2024"
        todas_metricas_teste.append(res_teste)

        if h == HORIZONTE_PRINCIPAL:
            preds_h4_teste = preds_teste
            preds_teste.to_parquet(PROCESSED_DIR / "previsoes_teste_final_pb_h4.parquet", index=False)

        # Teste formal da Hipótese H1: LightGBM_Com_Clima vs LightGBM_Sem_Clima e GLM_Com_Clima vs GLM_Sem_Clima
        for familia in ("LightGBM", "GLM"):
            p_com = preds_teste[preds_teste["modelo"] == f"{familia}_Com_Clima"]
            p_sem = preds_teste[preds_teste["modelo"] == f"{familia}_Sem_Clima"]
            err_com = np.abs(p_com["y_true"].to_numpy() - p_com["y_pred"].to_numpy())
            err_sem = np.abs(p_sem["y_true"].to_numpy() - p_sem["y_pred"].to_numpy())
            boot_h1 = bootstrap_blocos_skill(err_com, err_sem)
            comparacoes_h1.append(
                {
                    "horizonte": h,
                    "familia": familia,
                    "mae_sem_clima": round(float(np.mean(err_sem)), 4),
                    "mae_com_clima": round(float(np.mean(err_com)), 4),
                    "skill_clima_vs_sem_clima": boot_h1["skill_pontual"],
                    "ic95_inf": boot_h1["skill_ic95_inf"],
                    "ic95_sup": boot_h1["skill_ic95_sup"],
                    "h1_suportada_ic95": bool(boot_h1["skill_ic95_inf"] > 0.0),
                }
            )

        print(f"  -> Horizonte h={h} concluído (Teste Final 2023-2024):")
        for _, r in res_teste.iterrows():
            print(
                f"     {r['modelo']:24s} | MAE={r['mae']:6.2f} | WIS={r['wis']:6.2f} "
                f"| Cob80={r['cobertura_80']:.2f} | Cob95={r['cobertura_95']:.2f} "
                f"| Skill={r['skill_pontual']:+.3f} [{r['skill_ic95_inf']:+.3f}, {r['skill_ic95_sup']:+.3f}]"
            )

    df_consolidado = pd.concat(todas_metricas_val + todas_metricas_teste, ignore_index=True)
    df_consolidado.to_csv(REPORTS_DIR / "metricas_modelos_pb.csv", index=False)

    df_h1 = pd.DataFrame(comparacoes_h1)
    df_h1.to_csv(REPORTS_DIR / "teste_hipotese_h1_pb.csv", index=False)
    return df_consolidado


def etapa_infodengue() -> pd.DataFrame:
    """Passo B: Baixa a série histórica do InfoDengue (Fiocruz/FGV) e compara com o pipeline (Seção 3 e 5.7)."""
    print("[Passo B] Executando ingestão e benchmark do InfoDengue (Fiocruz/FGV)...")
    df_pop = carregar_ou_baixar_populacao_pb(RAW_DIR)
    df_infodengue = carregar_ou_baixar_infodengue_pb(df_pop=df_pop, diretorio_raw=RAW_DIR, forcar_download=True)
    
    caminho_painel = PROCESSED_DIR / "painel_semanal_pb.parquet"
    if caminho_painel.exists() and not df_infodengue.empty:
        painel = pd.read_parquet(caminho_painel)
        df_comp, caminhos_fig = comparar_com_benchmark_infodengue(painel, df_infodengue)
        print(f"  -> Benchmark comparado para {len(df_comp)} municípios. Relatório salvo em reports/comparacao_infodengue_pb.csv.")
        if caminhos_fig:
            print(f"  -> Gráfico salvo em {caminhos_fig[0]}.")
    return df_infodengue


def etapa_report() -> None:
    """Fase 5/6: Análises P2, P3, P4, H2, H3, TreeSHAP, GLM IRRs, resíduos, sensibilidade e figuras."""
    print("[4/4] Executando Fase 5 (Interpretação, Robustez, H2, H3, SHAP, Resíduos, Sensibilidade) e Relatório...")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    caminho_painel = PROCESSED_DIR / "painel_semanal_pb.parquet"
    if not caminho_painel.exists():
        etapa_data()
    painel = pd.read_parquet(caminho_painel)
    df_limpo = pd.read_parquet(INTERIM_DIR / "sinan_notificacoes_limpas_pb.parquet")
    df_pop = pd.read_parquet(RAW_DIR / "ibge_populacao_pb_2015_2024.parquet")
    df_clima = pd.read_parquet(RAW_DIR / "inmet_clima_semanal_pb_2015_2024.parquet")

    caminho_preds_h4 = PROCESSED_DIR / "previsoes_teste_final_pb_h4.parquet"
    if not caminho_preds_h4.exists():
        etapa_train()
    preds_h4 = pd.read_parquet(caminho_preds_h4)

    # P2, P3 e P4
    df_p2 = calcular_associacao_defasagens_p2(painel)
    df_p2.to_csv(REPORTS_DIR / "analise_defasagens_p2_pb.csv", index=False)

    df_p3 = clusterizar_perfis_sazonais_p3(painel)
    df_p3.to_csv(REPORTS_DIR / "clusters_sazonais_p3_pb.csv", index=False)

    moran_p4 = calcular_autocorrelacao_espacial_moran_p4(painel)
    (REPORTS_DIR / "autocorrelacao_moran_p4_pb.json").write_text(
        json.dumps(moran_p4, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Fase 5: Hipótese H2 (Mesorregião e Porte Populacional)
    df_h2 = avaliar_hipotese_h2_regiao_e_porte(preds_h4, painel)
    df_h2.to_csv(REPORTS_DIR / "teste_hipotese_h2_pb.csv", index=False)

    # Fase 5: Hipótese H3 (Atraso de Notificação e Nowcasting em h=1, 2)
    df_h3 = avaliar_hipotese_h3_atraso_notificacao(df_limpo, painel, horizontes_curtos=(1, 2))
    df_h3.to_csv(REPORTS_DIR / "teste_hipotese_h3_pb.csv", index=False)

    # Fase 5: Importância de Atributos (TreeSHAP LightGBM e Coeficientes IRR GLM)
    df_shap, df_coef_glm = extrair_importancia_shap_e_glm(painel, horizonte=HORIZONTE_PRINCIPAL)
    df_shap.to_csv(REPORTS_DIR / "importancia_shap_lightgbm_pb.csv", index=False)
    df_coef_glm.to_csv(REPORTS_DIR / "coeficientes_glm_pb.csv", index=False)

    # Fase 5: Diagnóstico de Resíduos por Mesorregião e Estação Sazonal
    df_residuos = analisar_residuos_por_periodo_e_regiao(preds_h4, painel)
    df_residuos.to_csv(REPORTS_DIR / "analise_residuos_pb.csv", index=False)

    # Fase 5: Análise de Sensibilidade (Limpeza e Pandemia COVID-19)
    df_sens = avaliar_sensibilidade_limpeza_e_pandemia(
        df_notificacoes_limpas=df_limpo,
        df_pop=df_pop,
        df_clima=df_clima,
        painel_padrao=painel,
        horizonte=HORIZONTE_PRINCIPAL,
    )
    df_sens.to_csv(REPORTS_DIR / "analise_sensibilidade_pb.csv", index=False)

    caminhos_fig = gerar_figuras_relatorio(
        painel=painel,
        df_p2=df_p2,
        df_previsoes_h4=preds_h4,
        df_shap=df_shap,
        df_h2=df_h2,
        df_notificacoes_limpas=df_limpo,
    )
    print(f"  -> {len(caminhos_fig)} figuras geradas em {REPORTS_DIR / 'figures'}.")
    print(f"  -> Índice I de Moran (P4 - PB): I = {moran_p4['moran_i']} (p = {moran_p4['p_valor_permutacao']}).")
    print(f"  -> Tabelas de Fase 5 salvas: H2 ({len(df_h2)} estratos), H3 ({len(df_h3)} horizontes), SHAP ({len(df_shap)} features), Resíduos ({len(df_residuos)} células) e Sensibilidade ({len(df_sens)} cenários).")


def main(argv: list[str] | None = None) -> int:
    """Ponto de entrada principal da CLI."""
    args = argv if argv is not None else sys.argv[1:]
    comando = args[0].lower() if args else "all"

    if comando == "data":
        etapa_data()
    elif comando == "infodengue":
        etapa_infodengue()
    elif comando == "features":
        etapa_features()
    elif comando == "train":
        etapa_train()
    elif comando == "report":
        etapa_report()
    elif comando == "all":
        etapa_data()
        etapa_features()
        etapa_train()
        etapa_report()
    else:
        print(f"Comando desconhecido: {comando}. Use: data | features | train | report | all")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

