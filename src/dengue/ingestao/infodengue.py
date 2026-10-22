"""Ingestão e benchmark externo via API pública do InfoDengue (Fiocruz/FGV) para a Paraíba (PB)."""

from __future__ import annotations

import io
import time
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests

from dengue.config import (
    ANO_FIM,
    ANO_INICIO,
    FIGURES_DIR,
    RAW_DIR,
    REPORTS_DIR,
    UF_PILOTO,
)
from dengue.ingestao.registro import registrar_arquivo_manifesto

BASE_URL_INFODENGUE = "https://info.dengue.mat.br/api/alertcity"


def baixar_serie_infodengue_municipio(
    geocode_ibge7: str | int,
    ano_inicio: int = ANO_INICIO,
    ano_fim: int = ANO_FIM,
    timeout: int = 20,
    max_retries: int = 3,
) -> pd.DataFrame | None:
    """Baixa a série histórica semanal do InfoDengue (Fiocruz/FGV) para um município pelo código IBGE de 7 dígitos."""
    params = {
        "geocode": str(geocode_ibge7),
        "disease": "dengue",
        "format": "csv",
        "ew_start": 1,
        "ew_end": 53,
        "ey_start": int(ano_inicio),
        "ey_end": int(ano_fim),
    }

    for tentativa in range(1, max_retries + 1):
        try:
            resp = requests.get(BASE_URL_INFODENGUE, params=params, timeout=timeout)
            if resp.status_code == 200 and len(resp.content) > 100:
                df = pd.read_csv(io.StringIO(resp.text))
                if "data_iniSE" in df.columns:
                    return df
            time.sleep(0.5 * tentativa)
        except Exception:
            time.sleep(1.0 * tentativa)

    return None


def carregar_ou_baixar_infodengue_pb(
    df_pop: pd.DataFrame,
    diretorio_raw: Path = RAW_DIR,
    forcar_download: bool = False,
    max_municipios: int | None = None,
    limite_municipios: int | None = None,
) -> pd.DataFrame:
    """Ingere e padroniza o benchmark do InfoDengue para municípios da Paraíba com registro SHA-256 (REG-08)."""
    diretorio_raw.mkdir(parents=True, exist_ok=True)
    caminho_parquet = diretorio_raw / "infodengue_benchmark_pb.parquet"

    if caminho_parquet.exists() and not forcar_download:
        return pd.read_parquet(caminho_parquet)

    limite = max_municipios if max_municipios is not None else limite_municipios
    muns = (
        df_pop[["municipio", "municipio_ibge7", "nome_municipio"]]
        .drop_duplicates(subset=["municipio"])
        .reset_index(drop=True)
    )
    if limite:
        muns = muns.head(limite)

    print(f"  -> Consultando API pública do InfoDengue para {len(muns)} municípios da Paraíba (2015–2024)...")
    dfs_brutos = []

    for idx, row in muns.iterrows():
        cod7 = str(row["municipio_ibge7"])
        cod6 = str(row["municipio"])
        nome = str(row["nome_municipio"])

        df_m = baixar_serie_infodengue_municipio(cod7)
        if df_m is not None and not df_m.empty:
            df_m["municipio"] = cod6
            df_m["municipio_ibge7"] = cod7
            df_m["nome_municipio"] = nome
            dfs_brutos.append(df_m)
            print(f"     [{idx+1}/{len(muns)}] {nome} ({cod7}): {len(df_m)} semanas baixadas.")
        else:
            print(f"     [{idx+1}/{len(muns)}] {nome} ({cod7}): sem resposta da API.")

    if dfs_brutos:
        df_concat = pd.concat(dfs_brutos, ignore_index=True)
        df_formatado = pd.DataFrame(
            {
                "municipio": df_concat["municipio"].astype(str),
                "municipio_ibge7": df_concat["municipio_ibge7"].astype(str),
                "nome_municipio": df_concat["nome_municipio"].astype(str),
                "semana": pd.to_datetime(df_concat["data_iniSE"]),
                "se": pd.to_numeric(df_concat["SE"], errors="coerce").fillna(1).astype(int),
                "casos_infodengue": pd.to_numeric(df_concat["casos"], errors="coerce").fillna(0).astype(int),
                "casos_est_nowcast": pd.to_numeric(df_concat["casos_est"], errors="coerce").fillna(0.0).astype(float),
                "casos_est_min": pd.to_numeric(df_concat["casos_est_min"], errors="coerce").fillna(0.0).astype(float),
                "casos_est_max": pd.to_numeric(df_concat["casos_est_max"], errors="coerce").fillna(0.0).astype(float),
                "nivel_alerta": pd.to_numeric(df_concat["nivel"], errors="coerce").fillna(1).astype(int),
                "temperatura_infodengue": pd.to_numeric(df_concat["tempmed"], errors="coerce").astype(float),
                "umidade_infodengue": pd.to_numeric(df_concat["umidmed"], errors="coerce").astype(float),
                "rt_transmissao": pd.to_numeric(df_concat.get("Rt", np.nan), errors="coerce").astype(float),
            }
        )
        fonte = "INFODENGUE_FIOCRUZ_FGV_API_PUBLICA"
    else:
        df_formatado = pd.DataFrame()
        fonte = "INFODENGUE_OFFLINE_PLACEHOLDER"

    df_formatado = df_formatado.sort_values(["municipio", "semana"]).reset_index(drop=True)
    df_formatado.to_parquet(caminho_parquet, index=False)

    registrar_arquivo_manifesto(
        caminho_arquivo=caminho_parquet,
        fonte=fonte,
        versao="alertcity_api_2015_2024",
        metadados_extras={
            "uf": UF_PILOTO,
            "municipios": muns["municipio"].tolist(),
            "n_registros": len(df_formatado),
        },
        caminho_manifesto=diretorio_raw / "manifesto_hashes.json",
    )
    return df_formatado


def comparar_com_benchmark_infodengue(
    painel: pd.DataFrame,
    df_infodengue: pd.DataFrame,
    df_previsoes_h4: pd.DataFrame | None = None,
    diretorio_reports: Path = REPORTS_DIR,
    diretorio_figuras: Path = FIGURES_DIR,
) -> tuple[pd.DataFrame, list[Path]]:
    """Compara as contagens e previsões do pipeline com as estimativas oficiais do InfoDengue (Seção 5.7)."""
    diretorio_reports.mkdir(parents=True, exist_ok=True)
    diretorio_figuras.mkdir(parents=True, exist_ok=True)

    cruzado = painel.merge(
        df_infodengue,
        on=["municipio", "semana"],
        how="inner",
        suffixes=("", "_info"),
    )

    resultados_mun: list[dict[str, Any]] = []

    for mun, grp in cruzado.groupby("municipio"):
        nome = str(grp["nome_municipio"].iloc[0])
        n_sem = len(grp)
        if n_sem < 20:
            continue

        r_spear_casos = float(grp["casos"].corr(grp["casos_infodengue"], method="spearman"))
        r_spear_nowcast = float(grp["casos"].corr(grp["casos_est_nowcast"], method="spearman"))
        r_pearson = float(grp["casos"].corr(grp["casos_infodengue"], method="pearson"))
        mae_contagem = float(np.mean(np.abs(grp["casos"] - grp["casos_infodengue"])))

        resultados_mun.append(
            {
                "municipio": str(mun),
                "nome_municipio": nome,
                "n_semanas_comparadas": n_sem,
                "spearman_casos_pipeline_vs_infodengue": round(r_spear_casos, 4),
                "spearman_casos_pipeline_vs_nowcast": round(r_spear_nowcast, 4),
                "pearson_casos": round(r_pearson, 4),
                "mae_diferenca_casos": round(mae_contagem, 2),
                "alerta_maximo_observado": int(grp["nivel_alerta"].max()),
            }
        )

    df_comp = pd.DataFrame(resultados_mun).sort_values("municipio").reset_index(drop=True)
    df_comp.to_csv(diretorio_reports / "comparacao_infodengue_pb.csv", index=False)

    caminhos_fig: list[Path] = []
    muns_plot = ["250750", "250400"]
    sub_plot = cruzado[cruzado["municipio"].isin(muns_plot)].sort_values(["municipio", "semana"])

    if len(sub_plot) > 0:
        fig, axes = plt.subplots(len(muns_plot), 1, figsize=(11, 7.5), sharex=True)
        if len(muns_plot) == 1:
            axes = [axes]

        for ax, cod_mun in zip(axes, muns_plot):
            dados_m = sub_plot[sub_plot["municipio"] == cod_mun]
            nome_m = dados_m["nome_municipio"].iloc[0]

            ax.plot(
                dados_m["semana"],
                dados_m["casos"],
                color="#111827",
                linewidth=1.4,
                label="Pipeline (Casos Prováveis)",
            )
            ax.plot(
                dados_m["semana"],
                dados_m["casos_infodengue"],
                color="#059669",
                linewidth=1.2,
                linestyle="--",
                label="InfoDengue (Casos Notificados)",
            )
            ax.plot(
                dados_m["semana"],
                dados_m["casos_est_nowcast"],
                color="#dc2626",
                linewidth=1.2,
                linestyle=":",
                label="InfoDengue Nowcasting (casos_est)",
            )

            ax.set_ylabel(f"Casos / Semana ({nome_m})")
            ax.legend(loc="upper left")
            ax.grid(alpha=0.3)

        axes[-1].set_xlabel("Semana Epidemiológica (2015–2024)")
        fig.suptitle("Benchmark Externo: Comparação Pipeline SINAN-PB vs InfoDengue (Fiocruz/FGV)", fontsize=13)
        fig.tight_layout()

        cam_fig7 = diretorio_figuras / "fig7_benchmark_infodengue_vs_pipeline.png"
        fig.savefig(cam_fig7, dpi=150)
        plt.close(fig)
        caminhos_fig.append(cam_fig7)

    return df_comp, caminhos_fig
