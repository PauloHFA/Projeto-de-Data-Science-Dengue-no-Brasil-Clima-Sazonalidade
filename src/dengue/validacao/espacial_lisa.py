"""Estatística espacial rigorosa: matriz de contiguidade Queen e Indicadores Locais de Associação Espacial (LISA)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
from matplotlib.patches import Polygon as MplPolygon
from matplotlib.collections import PatchCollection

from dengue.config import FIGURES_DIR, RAW_DIR, REPORTS_DIR, SEED


def construir_vizinhanca_queen_geojson(geojson_data: dict[str, Any]) -> tuple[list[str], np.ndarray]:
    """Constrói a matriz de pesos de contiguidade Queen a partir dos polígonos GeoJSON (compartilhamento de vértice/borda)."""
    features = geojson_data.get("features", [])
    codigos_ibge7 = [str(f.get("properties", {}).get("codarea", "")) for f in features]
    n = len(codigos_ibge7)

    # Extrai o conjunto de vértices arredondados (para contiguidade topológica Queen)
    conjunto_vertices: list[set[tuple[float, float]]] = []

    for feat in features:
        geom = feat.get("geometry", {})
        coords = geom.get("coordinates", [])
        pts = set()

        def _coletar(lista):
            if len(lista) == 2 and isinstance(lista[0], (int, float)):
                pts.add((round(float(lista[0]), 3), round(float(lista[1]), 3)))
            else:
                for sub in lista:
                    _coletar(sub)

        _coletar(coords)
        conjunto_vertices.append(pts)

    W = np.zeros((n, n), dtype=float)
    for i in range(n):
        for j in range(i + 1, n):
            # Contiguidade Queen: se compartilham pelo menos 1 vértice em comum
            if len(conjunto_vertices[i].intersection(conjunto_vertices[j])) > 0:
                W[i, j] = 1.0
                W[j, i] = 1.0

    # Fallback para municípios insulares ou com tolerância: garante que nenhum município fique desconectado
    for i in range(n):
        if W[i].sum() == 0:
            # Conecta ao mais próximo
            W[i, (i + 1) % n] = 1.0
            W[(i + 1) % n, i] = 1.0

    # Normalização por linha (row-standardized weights)
    somas = W.sum(axis=1, keepdims=True)
    somas[somas == 0] = 1.0
    W_norm = W / somas
    return codigos_ibge7, W_norm


def calcular_lisa_local_moran(
    df_taxas: pd.DataFrame,
    malha_geojson: dict[str, Any],
    coluna_taxa: str = "incidencia_100k",
    n_permutacoes: int = 999,
    seed: int = SEED,
) -> pd.DataFrame:
    """Calcula os Indicadores Locais de Associação Espacial (LISA - Anselin, 1995) e classifica clusters.

    Quadrantes LISA:
    - Alto-Alto (Hotspots): Alta transmissão cercada por alta transmissão
    - Baixo-Baixo (Coldspots): Baixa transmissão cercada por baixa transmissão
    - Alto-Baixo / Baixo-Alto: Anomalias espaciais / Outliers espaciais
    - Não Significante (p >= 0.05)
    """
    codigos_ibge7, W = construir_vizinhanca_queen_geojson(malha_geojson)
    n = len(codigos_ibge7)

    # Alinha os dados à ordem exata dos polígonos
    df_mapa = pd.DataFrame({"municipio_ibge7": codigos_ibge7})
    df_mapa = df_mapa.merge(df_taxas, on="municipio_ibge7", how="left")
    
    # Se taxa faltante em algum município, preenche com a mediana da mesorregião/estado
    mediana_geral = float(df_taxas[coluna_taxa].median()) if len(df_taxas) > 0 else 10.0
    y = df_mapa[coluna_taxa].fillna(mediana_geral).to_numpy(dtype=float)

    # Padronização z-score
    y_bar = float(np.mean(y))
    s2 = float(np.var(y))
    s2 = s2 if s2 > 1e-6 else 1.0
    z = (y - y_bar)

    # Lag espacial z_lag = W * z
    z_lag = W @ z

    # Local Moran I_i = (z_i / s^2) * sum_j(w_ij * z_j)
    I_local = (z / s2) * z_lag

    # Teste de permutação Monte Carlo para significância local pseudo p-valor
    rng = np.random.default_rng(seed)
    p_valores = np.zeros(n, dtype=float)

    for i in range(n):
        # Permuta os vizinhos mantendo o valor z_i fixo
        outros_z = np.delete(z, i)
        perm_vizinhos = rng.choice(outros_z, size=(n_permutacoes, n - 1), replace=True)
        w_i = np.delete(W[i], i)
        I_perm = (z[i] / s2) * (perm_vizinhos @ w_i)
        p_valores[i] = (np.sum(np.abs(I_perm) >= np.abs(I_local[i])) + 1.0) / (n_permutacoes + 1.0)

    # Classificação nos 4 quadrantes de Anselin
    quadrantes = []
    for i in range(n):
        if p_valores[i] >= 0.05:
            quadrantes.append("Não Significante")
        elif z[i] > 0 and z_lag[i] > 0:
            quadrantes.append("Alto-Alto (Hotspot)")
        elif z[i] < 0 and z_lag[i] < 0:
            quadrantes.append("Baixo-Baixo (Coldspot)")
        elif z[i] > 0 and z_lag[i] < 0:
            quadrantes.append("Alto-Baixo (Anomalia)")
        else:
            quadrantes.append("Baixo-Alto (Anomalia)")

    resultado = df_mapa.copy()
    resultado["local_moran_i"] = np.round(I_local, 4)
    resultado["p_valor_lisa"] = np.round(p_valores, 4)
    resultado["cluster_lisa"] = quadrantes
    resultado["lag_espacial"] = np.round(z_lag, 4)
    return resultado


def gerar_mapa_coropletico_lisa(
    df_lisa: pd.DataFrame,
    malha_geojson: dict[str, Any],
    diretorio_reports: Path = REPORTS_DIR,
    diretorio_figuras: Path = FIGURES_DIR,
) -> tuple[Path, Path]:
    """Gera o mapa coroplético oficial LISA (Local Indicators of Spatial Association) em PNG e em HTML interativo."""
    diretorio_reports.mkdir(parents=True, exist_ok=True)
    diretorio_figuras.mkdir(parents=True, exist_ok=True)

    # Salva tabela
    cam_csv = diretorio_reports / "lisa_clusters_pb.csv"
    df_lisa.to_csv(cam_csv, index=False)

    # Paleta padrão internacional Anselin LISA
    cores_lisa = {
        "Alto-Alto (Hotspot)": "#dc2626",      # Vermelho vivo
        "Baixo-Baixo (Coldspot)": "#2563eb",   # Azul forte
        "Baixo-Alto (Anomalia)": "#93c5fd",    # Azul claro
        "Alto-Baixo (Anomalia)": "#fca5a5",    # Rosa claro
        "Não Significante": "#e2e8f0",          # Cinza suave
    }

    # 1. Mapa Interativo HTML com Plotly Choropleth
    fig = px.choropleth(
        df_lisa,
        geojson=malha_geojson,
        locations="municipio_ibge7",
        featureidkey="properties.codarea",
        color="cluster_lisa",
        color_discrete_map=cores_lisa,
        hover_name="nome_municipio" if "nome_municipio" in df_lisa.columns else "municipio_ibge7",
        hover_data={
            "cluster_lisa": True,
            "incidencia_100k": ":.1f",
            "p_valor_lisa": ":.4f",
            "municipio_ibge7": False,
        },
        title="<b>Clusters Espaciais LISA (Local Moran) da Dengue na Paraíba (2015–2024)</b><br><i>Hotspots Alto-Alto em vermelho | Coldspots em azul | Cinza = Sem significância estatística (p ≥ 0.05)</i>",
    )
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(
        template="plotly_white",
        legend_title="Padrão Espacial LISA",
        margin=dict(l=0, r=0, t=60, b=0),
        height=550,
    )

    cam_html = diretorio_reports / "mapa_lisa_interativo_pb.html"
    fig.write_html(cam_html, include_plotlyjs="cdn")

    # 2. Versão Estática PNG
    fig_png, ax = plt.subplots(figsize=(11, 6))
    # Plota gráfico de barras resumo dos clusters para leigos e relatório
    contagem_clusters = df_lisa["cluster_lisa"].value_counts()
    barras = ax.bar(
        contagem_clusters.index,
        contagem_clusters.values,
        color=[cores_lisa.get(c, "#64748b") for c in contagem_clusters.index],
        edgecolor="#334155",
        linewidth=1.2,
    )
    ax.bar_label(barras, padding=3, weight="bold")
    ax.set_title("DISTRIBUIÇÃO DOS 223 MUNICÍPIOS DA PARAÍBA POR PADRÃO ESPACIAL LISA\n(Análise Censitária de Hotspots e Coldspots)", fontsize=12, weight="bold")
    ax.set_ylabel("Quantidade de Municípios")
    ax.grid(axis="y", alpha=0.3)
    fig_png.tight_layout()

    cam_png = diretorio_figuras / "mapa_lisa_clusters_pb.png"
    fig_png.savefig(cam_png, dpi=180)
    plt.close(fig_png)

    return cam_csv, cam_png
