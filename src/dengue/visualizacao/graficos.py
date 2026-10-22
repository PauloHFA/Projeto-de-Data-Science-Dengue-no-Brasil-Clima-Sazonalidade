"""Análises exploratórias (P2, P3, P4) e geração de gráficos científicos (Seções 5.3, 5.7 e 5.8)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.cluster import KMeans

from dengue.config import FIGURES_DIR, SEED
from dengue.ingestao.inmet import distancia_haversine_km

matplotlib.use("Agg")


def calcular_associacao_defasagens_p2(
    painel: pd.DataFrame,
    max_lag: int = 12,
) -> pd.DataFrame:
    """Responde P2: correlação de Spearman entre defasagens (k = 1..12) de temperatura/chuva e incidência."""
    df = painel.sort_values(["municipio", "semana"]).copy()
    resultados = []

    for k in range(1, max_lag + 1):
        temp_lag = df.groupby("municipio")["temp_media"].shift(k)
        chuva_lag = df.groupby("municipio")["chuva_acum"].shift(k)
        umid_lag = df.groupby("municipio")["umidade_media"].shift(k)

        mascara = temp_lag.notna() & chuva_lag.notna() & df["incidencia_100k"].notna()
        inc = df.loc[mascara, "incidencia_100k"]

        r_temp, p_temp = stats.spearmanr(temp_lag[mascara], inc)
        r_chuva, p_chuva = stats.spearmanr(chuva_lag[mascara], inc)
        r_umid, p_umid = stats.spearmanr(umid_lag[mascara], inc)

        resultados.append(
            {
                "defasagem_semanas": k,
                "spearman_temperatura": round(float(r_temp), 4),
                "pvalor_temperatura": float(p_temp),
                "spearman_chuva": round(float(r_chuva), 4),
                "pvalor_chuva": float(p_chuva),
                "spearman_umidade": round(float(r_umid), 4),
                "pvalor_umidade": float(p_umid),
            }
        )

    return pd.DataFrame(resultados)


def clusterizar_perfis_sazonais_p3(
    painel: pd.DataFrame,
    n_clusters: int = 3,
    seed: int = SEED,
) -> pd.DataFrame:
    """Responde P3: agrupa municípios da Paraíba por perfil sazonal normalizado (SE 1..52)."""
    df_se = (
        painel[painel["se"] <= 52]
        .groupby(["municipio", "nome_municipio", "mesorregiao", "se"], as_index=False)["incidencia_100k"]
        .mean()
    )
    tabela_pivo = df_se.pivot(index="municipio", columns="se", values="incidencia_100k").fillna(0.0)

    # Normaliza cada município pela sua própria média/desvio para comparar forma da curva sazonal
    medias = tabela_pivo.mean(axis=1)
    desvios = tabela_pivo.std(axis=1).replace(0.0, 1.0)
    curvas_norm = tabela_pivo.sub(medias, axis=0).div(desvios, axis=0)

    n_efetivo = min(n_clusters, len(curvas_norm))
    km = KMeans(n_clusters=n_efetivo, random_state=seed, n_init=10)
    rotulos = km.fit_predict(curvas_norm.to_numpy())

    se_pico = tabela_pivo.idxmax(axis=1).astype(int)
    inc_media = tabela_pivo.mean(axis=1)

    meta_mun = painel[["municipio", "nome_municipio", "mesorregiao"]].drop_duplicates(subset=["municipio"])
    resultado = pd.DataFrame(
        {
            "municipio": tabela_pivo.index,
            "cluster_sazonal": rotulos,
            "se_pico_medio": se_pico.values,
            "incidencia_media_semanal": np.round(inc_media.values, 2),
        }
    )
    return meta_mun.merge(resultado, on="municipio", how="inner").sort_values(["cluster_sazonal", "municipio"]).reset_index(drop=True)


def calcular_autocorrelacao_espacial_moran_p4(
    painel: pd.DataFrame,
    k_vizinhos: int = 4,
    n_permutacoes: int = 999,
    seed: int = SEED,
) -> dict[str, Any]:
    """Responde P4: calcula o Índice I de Moran global da incidência média municipal e significância por permutação."""
    resumo_mun = (
        painel.groupby(["municipio", "nome_municipio", "mesorregiao", "lat", "lon"], as_index=False)["incidencia_100k"]
        .mean()
        .sort_values("municipio")
        .reset_index(drop=True)
    )
    n = len(resumo_mun)
    if n < 4:
        return {"moran_i": 0.0, "valor_esperado": 0.0, "p_valor_permutacao": 1.0, "n_municipios": n}

    coords = resumo_mun[["lat", "lon"]].to_numpy(dtype=float)
    W = np.zeros((n, n), dtype=float)
    for i in range(n):
        dists = np.array(
            [
                distancia_haversine_km(coords[i, 0], coords[i, 1], coords[j, 0], coords[j, 1]) if i != j else np.inf
                for j in range(n)
            ]
        )
        vizinhos = np.argsort(dists)[: min(k_vizinhos, n - 1)]
        W[i, vizinhos] = 1.0

    # Simetriza e normaliza por linha (row-standardized weights)
    W = np.maximum(W, W.T)
    somas_linha = W.sum(axis=1, keepdims=True)
    somas_linha[somas_linha == 0.0] = 1.0
    W_norm = W / somas_linha

    y = resumo_mun["incidencia_100k"].to_numpy(dtype=float)
    z = y - np.mean(y)
    denom = float(np.sum(z**2))
    s0 = float(np.sum(W_norm))

    if denom <= 0.0 or s0 <= 0.0:
        return {"moran_i": 0.0, "valor_esperado": -1.0 / (n - 1), "p_valor_permutacao": 1.0, "n_municipios": n}

    moran_obs = float((n / s0) * (z @ W_norm @ z) / denom)

    rng = np.random.default_rng(seed)
    moran_perm = np.empty(n_permutacoes, dtype=float)
    for p in range(n_permutacoes):
        z_perm = rng.permutation(z)
        moran_perm[p] = float((n / s0) * (z_perm @ W_norm @ z_perm) / denom)

    esperado = -1.0 / (n - 1)
    p_val = float((np.sum(np.abs(moran_perm - esperado) >= np.abs(moran_obs - esperado)) + 1) / (n_permutacoes + 1))

    return {
        "moran_i": round(moran_obs, 4),
        "valor_esperado": round(esperado, 4),
        "p_valor_permutacao": round(p_val, 4),
        "n_municipios": n,
        "k_vizinhos": k_vizinhos,
    }


def gerar_figuras_relatorio(
    painel: pd.DataFrame,
    df_p2: pd.DataFrame,
    df_previsoes_h4: pd.DataFrame,
    df_shap: pd.DataFrame | None = None,
    df_h2: pd.DataFrame | None = None,
    df_notificacoes_limpas: pd.DataFrame | None = None,
    diretorio_figuras: Path = FIGURES_DIR,
) -> list[Path]:
    """Gera as figuras principais para o relatório Quarto em reports/figures/."""
    diretorio_figuras.mkdir(parents=True, exist_ok=True)
    caminhos: list[Path] = []

    # Figura 1: Série temporal agregada da Paraíba (incidência e precipitação)
    serie_uf = (
        painel.groupby("semana", as_index=False)
        .agg(
            casos=("casos", "sum"),
            populacao=("populacao", "sum"),
            chuva_media=("chuva_acum", "mean"),
        )
        .sort_values("semana")
    )
    serie_uf["incidencia_100k"] = (serie_uf["casos"] / serie_uf["populacao"]) * 100_000.0

    fig, ax1 = plt.subplots(figsize=(11, 4.5))
    ax1.plot(serie_uf["semana"], serie_uf["incidencia_100k"], color="#b91c1c", linewidth=1.6, label="Incidência (por 100 mil hab.)")
    ax1.axvline(pd.Timestamp("2023-01-01"), color="#1f2937", linestyle="--", linewidth=1.2, label="Início do Teste Final (2023–2024)")
    ax1.set_ylabel("Incidência de Dengue / 100k hab.", color="#b91c1c")
    ax1.set_xlabel("Semana Epidemiológica")
    ax1.set_title("Paraíba (PB): Série Histórica de Incidência de Dengue e Precipitação Semanal (2015–2024)")
    ax1.legend(loc="upper left")
    ax1.grid(alpha=0.25)

    ax2 = ax1.twinx()
    ax2.bar(serie_uf["semana"], serie_uf["chuva_media"], width=5.0, color="#2563eb", alpha=0.25, label="Precipitação média (mm)")
    ax2.set_ylabel("Precipitação Semanal Média (mm)", color="#2563eb")
    fig.tight_layout()
    cam1 = diretorio_figuras / "fig1_serie_temporal_pb.png"
    fig.savefig(cam1, dpi=150)
    plt.close(fig)
    caminhos.append(cam1)

    # Figura 2: Curvas de associação defasagem-resposta (P2)
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    ax.plot(df_p2["defasagem_semanas"], df_p2["spearman_temperatura"], marker="o", color="#dc2626", label="Temperatura Média")
    ax.plot(df_p2["defasagem_semanas"], df_p2["spearman_chuva"], marker="s", color="#2563eb", label="Precipitação Acumulada")
    ax.plot(df_p2["defasagem_semanas"], df_p2["spearman_umidade"], marker="^", color="#059669", label="Umidade Relativa")
    ax.axhline(0.0, color="gray", linestyle=":", linewidth=1.0)
    ax.set_xticks(range(1, len(df_p2) + 1))
    ax.set_xlabel("Defasagem k (semanas epidemiológicas)")
    ax.set_ylabel("Correlação de Spearman com a Incidência")
    ax.set_title("P2: Associação entre Variáveis Climáticas Defasadas e Incidência na Paraíba")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    cam2 = diretorio_figuras / "fig2_defasagem_clima_p2.png"
    fig.savefig(cam2, dpi=150)
    plt.close(fig)
    caminhos.append(cam2)

    # Figura 3: Previsão vs Observado com Intervalos de 80% e 95% para João Pessoa (250750) em h=4
    jp = df_previsoes_h4[
        (df_previsoes_h4["municipio"] == "250750")
        & (df_previsoes_h4["modelo"] == "LightGBM_Com_Clima")
    ].sort_values("semana")

    if len(jp) > 0:
        fig, ax = plt.subplots(figsize=(10.5, 4.5))
        ax.fill_between(jp["semana"], jp["li_95"], jp["ls_95"], color="#93c5fd", alpha=0.35, label="Intervalo Preditivo 95%")
        ax.fill_between(jp["semana"], jp["li_80"], jp["ls_80"], color="#3b82f6", alpha=0.45, label="Intervalo Preditivo 80%")
        ax.plot(jp["semana"], jp["y_true"], color="#111827", linewidth=1.6, label="Observado (João Pessoa - PB)")
        ax.plot(jp["semana"], jp["y_pred"], color="#dc2626", linewidth=1.5, linestyle="--", label="Previsto LightGBM + Clima (h=4)")
        ax.set_xlabel("Semana Epidemiológica")
        ax.set_ylabel("Incidência / 100k hab.")
        ax.set_title("João Pessoa (PB): Previsão h=4 Semanas com Intervalos Calibrados (80% e 95%)")
        ax.legend(loc="upper left")
        ax.grid(alpha=0.25)
        fig.tight_layout()
        cam3 = diretorio_figuras / "fig3_previsao_joao_pessoa_h4.png"
        fig.savefig(cam3, dpi=150)
        plt.close(fig)
        caminhos.append(cam3)

    # Figura 4: Importância de Atributos via TreeSHAP (Top 15 variáveis no horizonte h=4)
    if df_shap is not None and len(df_shap) > 0:
        top_shap = df_shap.head(15).iloc[::-1]
        cores_grupo = {
            "Clima Defasado": "#2563eb",
            "Histórico de Casos / Incidência": "#dc2626",
            "Sazonalidade": "#059669",
        }
        cores_barras = [cores_grupo.get(g, "#6b7280") for g in top_shap["grupo_variavel"]]

        fig, ax = plt.subplots(figsize=(9.5, 5.2))
        ax.barh(top_shap["atributo"], top_shap["shap_medio_absoluto"], color=cores_barras, alpha=0.88)
        ax.set_xlabel("Contribuição Marginal Absoluta Média |TreeSHAP| (incidência / 100k hab.)")
        ax.set_title("Fase 5: Top 15 Atributos por Importância TreeSHAP (LightGBM Com Clima, h=4)")
        ax.grid(axis="x", alpha=0.3)
        fig.tight_layout()
        cam4 = diretorio_figuras / "fig4_shap_importancia_h4.png"
        fig.savefig(cam4, dpi=150)
        plt.close(fig)
        caminhos.append(cam4)

    # Figura 5: Ganho Preditivo (Skill + IC 95%) por Mesorregião e Porte Populacional (H2)
    if df_h2 is not None and len(df_h2) > 0:
        fig, ax = plt.subplots(figsize=(9.5, 4.8))
        y_pos = np.arange(len(df_h2))
        rotulos = [f"{r.dimensao}: {r.estrato}" for r in df_h2.itertuples()]
        skills = df_h2["skill_clima_vs_sem_clima"].to_numpy() * 100.0
        err_inf = (df_h2["skill_clima_vs_sem_clima"] - df_h2["ic95_inf_vs_sem_clima"]).to_numpy() * 100.0
        err_sup = (df_h2["ic95_sup_vs_sem_clima"] - df_h2["skill_clima_vs_sem_clima"]).to_numpy() * 100.0

        ax.errorbar(
            skills,
            y_pos,
            xerr=[err_inf, err_sup],
            fmt="o",
            color="#1d4ed8",
            ecolor="#60a5fa",
            elinewidth=2.2,
            capsize=4,
            label="Skill Relativo (%) com IC 95% (Block Bootstrap)",
        )
        ax.axvline(0.0, color="#dc2626", linestyle="--", linewidth=1.1)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(rotulos)
        ax.set_xlabel("Ganho Relativo (Skill %) do Modelo Com Clima vs. Sem Clima (h=4)")
        ax.set_title("Hipótese H2: Ganho Preditivo do Clima por Mesorregião da PB e Porte Populacional")
        ax.legend(loc="lower right")
        ax.grid(alpha=0.3)
        fig.tight_layout()
        cam5 = diretorio_figuras / "fig5_h2_mesorregiao_e_porte.png"
        fig.savefig(cam5, dpi=150)
        plt.close(fig)
        caminhos.append(cam5)

    # Figura 6: Distribuição do Atraso de Notificação e Curva de Completude acumulada (REG-06 / H3)
    if df_notificacoes_limpas is not None and "atraso_dias" in df_notificacoes_limpas.columns:
        atrasos = df_notificacoes_limpas["atraso_dias"].clip(0, 35).to_numpy()
        dias_grid = np.arange(0, 36)
        ecdf = [float(np.mean(atrasos <= d)) * 100.0 for d in dias_grid]

        fig, ax1 = plt.subplots(figsize=(9.0, 4.2))
        ax1.hist(atrasos, bins=range(0, 36), density=True, color="#f59e0b", alpha=0.45, edgecolor="#b45309", label="Densidade do atraso (dias)")
        ax1.set_xlabel("Atraso de Notificação = DT_NOTIFIC − DT_SIN_PRI (dias)")
        ax1.set_ylabel("Densidade Relativa", color="#b45309")
        ax1.axvline(7, color="#dc2626", linestyle="--", linewidth=1.2, label="Corte de 7 dias (1 SE)")

        ax2 = ax1.twinx()
        ax2.plot(dias_grid, ecdf, color="#1d4ed8", linewidth=2.0, marker=".", label="Completude Acumulada (%)")
        ax2.set_ylabel("Notificações Digitadas Acumuladas (%)", color="#1d4ed8")
        ax2.set_ylim(0, 105)
        ax1.set_title("REG-06 / H3: Distribuição do Atraso de Notificação e Curva de Completude na Paraíba")
        ax1.legend(loc="center right")
        ax1.grid(alpha=0.25)
        fig.tight_layout()
        cam6 = diretorio_figuras / "fig6_atraso_notificacao_h3.png"
        fig.savefig(cam6, dpi=150)
        plt.close(fig)
        caminhos.append(cam6)

    return caminhos

