"""Estatística espacial rigorosa: matriz de contiguidade Queen e Indicadores Locais de Associação Espacial (LISA)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
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

        def _coletar(lista: list[Any]) -> None:
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

    # Converte códigos para string para merge limpo
    df_taxas_copia = df_taxas.copy()
    df_taxas_copia["municipio_ibge7"] = df_taxas_copia["municipio_ibge7"].astype(str)

    # Alinha os dados à ordem exata dos polígonos
    df_mapa = pd.DataFrame({"municipio_ibge7": codigos_ibge7})
    df_mapa = df_mapa.merge(df_taxas_copia, on="municipio_ibge7", how="left")

    # Se taxa faltante em algum município, preenche com a mediana da mesorregião/estado
    mediana_geral = float(df_taxas[coluna_taxa].median()) if len(df_taxas) > 0 else 10.0
    y = df_mapa[coluna_taxa].fillna(mediana_geral).to_numpy(dtype=float)

    # Padronização z-score
    y_bar = float(np.mean(y))
    s2 = float(np.var(y))
    s2 = s2 if s2 > 1e-6 else 1.0
    z = y - y_bar

    # Lag espacial z_lag = W * z
    z_lag = W @ z

    # Local Moran I_i = (z_i / s^2) * sum_j(w_ij * z_j)
    I_local = (z / s2) * z_lag

    # Teste de permutação Monte Carlo para significância local pseudo p-valor
    rng = np.random.default_rng(seed)
    p_valores = np.zeros(n, dtype=float)

    for i in range(n):
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


def _obter_cor_incidencia(taxa: float) -> str:
    """Retorna cor de gradiente para incidência contínua por 100k hab."""
    if taxa < 5.0:
        return "#10b981"  # Verde esmeralda (Baixo)
    if taxa < 12.0:
        return "#84cc16"  # Verde lima (Moderado)
    if taxa < 20.0:
        return "#eab308"  # Amarelo (Atenção)
    if taxa < 30.0:
        return "#f97316"  # Laranja (Alto)
    return "#dc2626"      # Vermelho (Crítico)


def gerar_mapa_coropletico_lisa(
    df_lisa: pd.DataFrame,
    malha_geojson: dict[str, Any],
    diretorio_reports: Path = REPORTS_DIR,
    diretorio_figuras: Path = FIGURES_DIR,
) -> tuple[Path, Path]:
    """Gera mapa espacial interativo de alta precisão em Leaflet.js e imagem estática bicompartimentada."""
    diretorio_reports.mkdir(parents=True, exist_ok=True)
    diretorio_figuras.mkdir(parents=True, exist_ok=True)

    df_lisa_copia = df_lisa.copy()
    df_lisa_copia["municipio_ibge7"] = df_lisa_copia["municipio_ibge7"].astype(str)

    # Garante enriquecimento com metadados demográficos oficiais do Censo IBGE
    caminho_pop = RAW_DIR / "ibge_populacao_pb_223_municipios.parquet"
    if caminho_pop.exists():
        df_pop = pd.read_parquet(caminho_pop)
        df_pop["municipio_ibge7"] = df_pop["municipio_ibge7"].astype(str)
        df_pop_2024 = df_pop[df_pop["ano"] == 2024][["municipio_ibge7", "nome_municipio", "mesorregiao", "populacao"]].drop_duplicates()
        cols_drop = [c for c in ["nome_municipio", "mesorregiao", "populacao"] if c in df_lisa_copia.columns]
        df_lisa_copia = df_lisa_copia.drop(columns=cols_drop, errors="ignore").merge(
            df_pop_2024, on="municipio_ibge7", how="left"
        )

    # Preenche eventuais nulos
    df_lisa_copia["nome_municipio"] = df_lisa_copia["nome_municipio"].fillna("Município PB")
    df_lisa_copia["mesorregiao"] = df_lisa_copia["mesorregiao"].fillna("Paraíba")
    df_lisa_copia["populacao"] = df_lisa_copia["populacao"].fillna(15000).astype(int)
    df_lisa_copia["incidencia_100k"] = df_lisa_copia["incidencia_100k"].fillna(12.0).round(1)

    # Salva CSV oficial de clusters LISA
    cam_csv = diretorio_reports / "lisa_clusters_pb.csv"
    df_lisa_copia.to_csv(cam_csv, index=False, encoding="utf-8")

    # Mapeamento de cores oficiais Anselin LISA
    cores_lisa = {
        "Alto-Alto (Hotspot)": "#dc2626",      # Vermelho vivo
        "Baixo-Baixo (Coldspot)": "#2563eb",   # Azul royal
        "Baixo-Alto (Anomalia)": "#0284c7",    # Azul celeste / ciano
        "Alto-Baixo (Anomalia)": "#ea580c",    # Laranja vibrante
        "Não Significante": "#f1f5f9",          # Cinza suave translúcido
    }

    # Diagnósticos para leigos e gestores de saúde
    def _gerar_diagnostico(cluster: str, inc: float) -> str:
        if cluster == "Alto-Alto (Hotspot)":
            return f"ÁREA CRÍTICA REGIONAL: Taxa elevada ({inc:.1f}/100k) cercada por vizinhos também em alta. Recomenda-se envio imediato de fumacê e bloqueio vetorial."
        if cluster == "Baixo-Baixo (Coldspot)":
            return f"ZONA PROTEGIDA: Baixa incidência ({inc:.1f}/100k) contígua a áreas calmas. Manter vigilância rotineira de reservatórios domiciliares."
        if cluster == "Baixo-Alto (Anomalia)":
            return f"POTENCIAL SUBNOTIFICAÇÃO: Taxa mais baixa ({inc:.1f}/100k) que os vizinhos ao redor. Recomenda-se auditar fluxo de digitação de fichas no Sinan."
        if cluster == "Alto-Baixo (Anomalia)":
            return f"POLO EMISSOR / SURTO ISOLADO: Pico elevado ({inc:.1f}/100k) cercado por cidades com menor transmissão. Risco de irradiação regional."
        return f"PADRÃO INDEPENDENTE: Incidência ({inc:.1f}/100k) sem correlação espacial significante com os municípios vizinhos imediatos."

    # Prepara propriedades no GeoJSON em memória
    mapa_dados = df_lisa_copia.set_index("municipio_ibge7").to_dict(orient="index")
    features_geojson = []

    for feat in malha_geojson.get("features", []):
        cod7 = str(feat.get("properties", {}).get("codarea", ""))
        info = mapa_dados.get(cod7, {})
        nome = info.get("nome_municipio", f"IBGE {cod7}")
        meso = info.get("mesorregiao", "Paraíba")
        pop = int(info.get("populacao", 15000))
        inc = float(info.get("incidencia_100k", 12.0))
        cluster = str(info.get("cluster_lisa", "Não Significante"))
        pval = float(info.get("p_valor_lisa", 0.99))
        cor_lisa = cores_lisa.get(cluster, "#f1f5f9")
        cor_inc = _obter_cor_incidencia(inc)
        diag = _gerar_diagnostico(cluster, inc)

        feat_novo = {
            "type": "Feature",
            "geometry": feat.get("geometry"),
            "properties": {
                "codarea": cod7,
                "nome": nome,
                "meso": meso,
                "pop": f"{pop:,}".replace(",", "."),
                "inc": inc,
                "inc_fmt": f"{inc:.1f}".replace(".", ","),
                "cluster": cluster,
                "p_val": pval,
                "p_val_fmt": f"{pval:.3f}".replace(".", ","),
                "significante": bool(pval < 0.05),
                "cor_lisa": cor_lisa,
                "cor_inc": cor_inc,
                "diagnostico": diag,
            },
        }
        features_geojson.append(feat_novo)

    geojson_final = {"type": "FeatureCollection", "features": features_geojson}
    geojson_json_str = json.dumps(geojson_final, ensure_ascii=False)

    # 1. GERAÇÃO DO MAPA INTERATIVO LEAFLET.JS (Alta performance, fluido e legível)
    contagens = df_lisa_copia["cluster_lisa"].value_counts().to_dict()
    n_hotspots = contagens.get("Alto-Alto (Hotspot)", 0)
    n_coldspots = contagens.get("Baixo-Baixo (Coldspot)", 0)
    n_anomalias_ba = contagens.get("Baixo-Alto (Anomalia)", 0)
    n_anomalias_ab = contagens.get("Alto-Baixo (Anomalia)", 0)
    n_nao_sig = contagens.get("Não Significante", 0)

    html_template = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Clusters Espaciais LISA (Local Moran) - Dengue na Paraíba</title>
  
  <!-- Leaflet CSS -->
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin="" />
  
  <style>
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: #f8fafc;
      color: #0f172a;
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
    }}
    header {{
      background: #0f172a;
      color: #ffffff;
      padding: 12px 20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      box-shadow: 0 2px 8px rgba(0,0,0,0.2);
      z-index: 1000;
      flex-wrap: wrap;
      gap: 10px;
    }}
    .header-titles h1 {{
      font-size: 1.15rem;
      font-weight: 700;
      letter-spacing: -0.02em;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .header-titles p {{
      font-size: 0.78rem;
      color: #94a3b8;
      margin-top: 2px;
    }}
    .controls {{
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
    }}
    .btn {{
      padding: 6px 12px;
      border-radius: 6px;
      border: 1px solid #334155;
      background: #1e293b;
      color: #f1f5f9;
      font-size: 0.8rem;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.15s ease-in-out;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }}
    .btn:hover {{
      background: #334155;
      color: #ffffff;
      border-color: #475569;
    }}
    .btn.active {{
      background: #2563eb;
      border-color: #3b82f6;
      color: #ffffff;
      font-weight: 600;
      box-shadow: 0 0 0 2px rgba(37,99,235,0.3);
    }}
    #map {{
      flex: 1;
      width: 100%;
      height: 100%;
      background: #e2e8f0;
      position: relative;
    }}
    /* Floating HUD (Painel informativo dinâmico) */
    .hud-panel {{
      position: absolute;
      top: 15px;
      right: 15px;
      width: 320px;
      max-width: 90vw;
      background: rgba(255, 255, 255, 0.96);
      backdrop-filter: blur(8px);
      border: 1px solid #cbd5e1;
      border-radius: 10px;
      padding: 14px 16px;
      box-shadow: 0 10px 25px rgba(0,0,0,0.12);
      z-index: 1000;
      pointer-events: none;
      transition: all 0.15s ease-out;
    }}
    .hud-panel h2 {{
      font-size: 1.05rem;
      font-weight: 700;
      color: #0f172a;
      margin-bottom: 2px;
    }}
    .hud-panel .badge-meso {{
      display: inline-block;
      font-size: 0.7rem;
      font-weight: 600;
      background: #f1f5f9;
      color: #475569;
      padding: 2px 8px;
      border-radius: 4px;
      margin-bottom: 10px;
    }}
    .hud-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      margin-bottom: 10px;
    }}
    .hud-item {{
      background: #f8fafc;
      padding: 6px 8px;
      border-radius: 6px;
      border: 1px solid #e2e8f0;
    }}
    .hud-item .label {{
      font-size: 0.65rem;
      text-transform: uppercase;
      font-weight: 600;
      color: #64748b;
    }}
    .hud-item .val {{
      font-size: 0.95rem;
      font-weight: 700;
      color: #0f172a;
      margin-top: 1px;
    }}
    .hud-diag {{
      background: #eff6ff;
      border-left: 3px solid #2563eb;
      padding: 8px 10px;
      border-radius: 4px;
      font-size: 0.74rem;
      color: #1e3a8a;
      line-height: 1.35;
    }}
    /* Legenda Flutuante */
    .legend-panel {{
      position: absolute;
      bottom: 25px;
      left: 15px;
      background: rgba(255, 255, 255, 0.95);
      backdrop-filter: blur(6px);
      border: 1px solid #cbd5e1;
      border-radius: 8px;
      padding: 10px 14px;
      box-shadow: 0 4px 15px rgba(0,0,0,0.1);
      z-index: 1000;
      font-size: 0.75rem;
      max-width: 280px;
    }}
    .legend-panel h3 {{
      font-size: 0.78rem;
      font-weight: 700;
      color: #334155;
      margin-bottom: 6px;
      text-transform: uppercase;
      letter-spacing: 0.03em;
    }}
    .legend-row {{
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 4px;
      color: #1e293b;
    }}
    .legend-box {{
      width: 14px;
      height: 14px;
      border-radius: 3px;
      border: 1px solid rgba(0,0,0,0.2);
      flex-shrink: 0;
    }}
    footer {{
      background: #ffffff;
      border-top: 1px solid #e2e8f0;
      padding: 8px 16px;
      font-size: 0.75rem;
      color: #64748b;
      display: flex;
      justify-content: space-between;
      align-items: center;
      z-index: 1000;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .badge-count {{
      font-weight: 700;
      color: #0f172a;
    }}
  </style>
</head>
<body>

  <header>
    <div class="header-titles">
      <h1>🗺️ Mapa Espacial Interativo: Dengue na Paraíba (2015–2024)</h1>
      <p>Análise Censitária dos 223 Municípios • Contiguidade Queen • Indicadores Locais de Associação Espacial (LISA)</p>
    </div>
    <div class="controls">
      <button id="btn-lisa" class="btn active" onclick="definirModo('lisa')">🎯 Clusters LISA</button>
      <button id="btn-inc" class="btn" onclick="definirModo('inc')">🌡️ Taxa de Incidência</button>
      <button id="btn-sig" class="btn" onclick="definirModo('sig')">🚨 Apenas Críticos (p &lt; 0.05)</button>
      <button class="btn" onclick="resetarZoom()">🔄 Enquadrar Paraíba</button>
    </div>
  </header>

  <div id="map">
    <!-- Floating HUD -->
    <div id="hud" class="hud-panel">
      <h2 id="hud-nome">Passe o mouse no mapa</h2>
      <span id="hud-meso" class="badge-meso">Estado da Paraíba</span>
      <div class="hud-grid">
        <div class="hud-item">
          <div class="label">População</div>
          <div id="hud-pop" class="val">--</div>
        </div>
        <div class="hud-item">
          <div class="label">Incidência Anual</div>
          <div id="hud-inc" class="val">--</div>
        </div>
        <div class="hud-item">
          <div class="label">Padrão LISA</div>
          <div id="hud-lisa" class="val">--</div>
        </div>
        <div class="hud-item">
          <div class="label">p-valor Local</div>
          <div id="hud-pval" class="val">--</div>
        </div>
      </div>
      <div id="hud-diag" class="hud-diag">
        Explore visualmente os 223 municípios da Paraíba. O mapa identifica hotspots de transmissão contínua, áreas calmas e anomalias de notificação.
      </div>
    </div>

    <!-- Floating Legend -->
    <div id="legend" class="legend-panel">
      <!-- Injetada via JS -->
    </div>
  </div>

  <footer>
    <div>
      <b>Síntese Operacional:</b>
      <span class="badge-count">223</span> municípios |
      <span style="color:#dc2626; font-weight:700;">{n_hotspots} Hotspots</span> |
      <span style="color:#2563eb; font-weight:700;">{n_coldspots} Coldspots</span> |
      <span style="color:#0284c7; font-weight:700;">{n_anomalias_ba} Baixo-Alto</span> |
      <span style="color:#ea580c; font-weight:700;">{n_anomalias_ab} Alto-Baixo</span> |
      <span style="color:#64748b; font-weight:700;">{n_nao_sig} Sem Significância</span>
    </div>
    <div>Rigor Científico: <i>Anselin (1995) • InfoDengue Fiocruz/FGV • Censo IBGE</i></div>
  </footer>

  <!-- Leaflet JS -->
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>

  <script>
    // Dados GeoJSON dos 223 municípios enriquecidos
    const dadosGeoJSON = {geojson_json_str};

    // Inicialização do Mapa Leaflet
    const map = L.map('map', {{
      zoomControl: true,
      attributionControl: false
    }});

    // Camada Base: CartoDB Positron (Limpo, profissional e com nomes de ruas/cidades)
    const cartoPositron = L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
      maxZoom: 19,
      subdomains: 'abcd'
    }}).addTo(map);

    let camadaGeoJSON;
    let modoAtual = 'lisa';
    const boundsPB = [[-8.31, -38.78], [-6.02, -34.78]];

    // Função de estilo dinâmico de cada polígono
    function obterEstilo(feature) {{
      const props = feature.properties;
      let corPreenchimento = props.cor_lisa;
      let opacidade = 0.85;
      let pesoBorda = 0.8;
      let corBorda = '#475569';

      if (modoAtual === 'inc') {{
        corPreenchimento = props.cor_inc;
        opacidade = 0.85;
        pesoBorda = 0.8;
      }} else if (modoAtual === 'sig') {{
        if (props.significante) {{
          corPreenchimento = props.cor_lisa;
          opacidade = 0.95;
          pesoBorda = 1.5;
          corBorda = '#0f172a';
        }} else {{
          corPreenchimento = '#cbd5e1';
          opacidade = 0.15;
          pesoBorda = 0.4;
          corBorda = '#94a3b8';
        }}
      }} else {{
        // Modo LISA
        if (!props.significante) {{
          corPreenchimento = '#f1f5f9';
          opacidade = 0.55;
          corBorda = '#94a3b8';
        }}
      }}

      return {{
        fillColor: corPreenchimento,
        weight: pesoBorda,
        opacity: 1,
        color: corBorda,
        fillOpacity: opacidade
      }};
    }}

    // Interações de Mouse
    function destacarElemento(e) {{
      const layer = e.target;
      layer.setStyle({{
        weight: 2.8,
        color: '#0f172a',
        fillOpacity: 0.95
      }});
      if (!L.Browser.ie && !L.Browser.opera && !L.Browser.edge) {{
        layer.bringToFront();
      }}
      atualizarHUD(layer.feature.properties);
    }}

    function restaurarElemento(e) {{
      camadaGeoJSON.resetStyle(e.target);
    }}

    function darZoomElemento(e) {{
      map.fitBounds(e.target.getBounds());
    }}

    // Atualiza Painel HUD Superior
    function atualizarHUD(props) {{
      document.getElementById('hud-nome').innerText = props.nome;
      document.getElementById('hud-meso').innerText = props.meso + ' (IBGE ' + props.codarea + ')';
      document.getElementById('hud-pop').innerText = props.pop + ' hab.';
      document.getElementById('hud-inc').innerText = props.inc_fmt + ' /100k';
      document.getElementById('hud-lisa').innerText = props.cluster;
      document.getElementById('hud-pval').innerText = props.p_val_fmt;

      const diagEl = document.getElementById('hud-diag');
      diagEl.innerText = props.diagnostico;

      if (props.cluster.includes('Hotspot')) {{
        diagEl.style.borderLeftColor = '#dc2626';
        diagEl.style.background = '#fef2f2';
        diagEl.style.color = '#991b1b';
      }} else if (props.cluster.includes('Coldspot')) {{
        diagEl.style.borderLeftColor = '#2563eb';
        diagEl.style.background = '#eff6ff';
        diagEl.style.color = '#1e3a8a';
      }} else if (props.cluster.includes('Anomalia')) {{
        diagEl.style.borderLeftColor = '#ea580c';
        diagEl.style.background = '#fff7ed';
        diagEl.style.color = '#9a3412';
      }} else {{
        diagEl.style.borderLeftColor = '#94a3b8';
        diagEl.style.background = '#f8fafc';
        diagEl.style.color = '#475569';
      }}
    }}

    // Cria e Renderiza a camada GeoJSON
    function renderizarCamada() {{
      if (camadaGeoJSON) {{
        map.removeLayer(camadaGeoJSON);
      }}

      camadaGeoJSON = L.geoJSON(dadosGeoJSON, {{
        style: obterEstilo,
        onEachFeature: function(feature, layer) {{
          layer.on({{
            mouseover: destacarElemento,
            mouseout: restaurarElemento,
            click: darZoomElemento
          }});
          
          // Popup informativo ao clicar
          const p = feature.properties;
          const popupContent = `
            <div style="font-family: inherit; font-size: 0.85rem; line-height: 1.4;">
              <h3 style="margin: 0 0 4px 0; font-size: 1rem; color: #0f172a;">${{p.nome}}</h3>
              <p style="color: #64748b; margin-bottom: 8px;">${{p.meso}} | IBGE ${{p.codarea}}</p>
              <hr style="border: 0; border-top: 1px solid #e2e8f0; margin-bottom: 8px;" />
              <b>População:</b> ${{p.pop}} hab.<br>
              <b>Incidência Anual:</b> ${{p.inc_fmt}} casos por 100k hab.<br>
              <b>Padrão LISA:</b> <span style="font-weight:700;">${{p.cluster}}</span><br>
              <b>Significância (p):</b> ${{p.p_val_fmt}}<br>
              <div style="margin-top: 8px; padding: 6px; background: #f8fafc; border-radius: 4px; font-size: 0.75rem;">
                ${{p.diagnostico}}
              </div>
            </div>
          `;
          layer.bindPopup(popupContent);
        }}
      }}).addTo(map);

      atualizarLegenda();
    }}

    // Atualiza Legenda Dinâmica
    function atualizarLegenda() {{
      const legEl = document.getElementById('legend');
      if (modoAtual === 'inc') {{
        legEl.innerHTML = `
          <h3>Taxa de Incidência (100k hab.)</h3>
          <div class="legend-row"><div class="legend-box" style="background:#10b981;"></div> Abaixo de 5,0 (Muito Baixa)</div>
          <div class="legend-row"><div class="legend-box" style="background:#84cc16;"></div> 5,0 a 12,0 (Moderada)</div>
          <div class="legend-row"><div class="legend-box" style="background:#eab308;"></div> 12,0 a 20,0 (Alerta)</div>
          <div class="legend-row"><div class="legend-box" style="background:#f97316;"></div> 20,0 a 30,0 (Alta)</div>
          <div class="legend-row"><div class="legend-box" style="background:#dc2626;"></div> Acima de 30,0 (Crítica)</div>
        `;
      }} else {{
        legEl.innerHTML = `
          <h3>Clusters Espaciais LISA</h3>
          <div class="legend-row"><div class="legend-box" style="background:#dc2626;"></div> Alto-Alto (Hotspots Críticos)</div>
          <div class="legend-row"><div class="legend-box" style="background:#2563eb;"></div> Baixo-Baixo (Coldspots Protegidos)</div>
          <div class="legend-row"><div class="legend-box" style="background:#0284c7;"></div> Baixo-Alto (Anomalia / Subnotificação)</div>
          <div class="legend-row"><div class="legend-box" style="background:#ea580c;"></div> Alto-Baixo (Polo Emissor / Surto)</div>
          <div class="legend-row"><div class="legend-box" style="background:#f1f5f9; border-color:#94a3b8;"></div> Sem Significância (p &ge; 0.05)</div>
        `;
      }}
    }}

    // Alternar Modos de Visualização
    function definirModo(novoModo) {{
      modoAtual = novoModo;
      document.querySelectorAll('.controls .btn').forEach(b => b.classList.remove('active'));
      if (novoModo === 'lisa') document.getElementById('btn-lisa').classList.add('active');
      if (novoModo === 'inc') document.getElementById('btn-inc').classList.add('active');
      if (novoModo === 'sig') document.getElementById('btn-sig').classList.add('active');
      renderizarCamada();
    }}

    function resetarZoom() {{
      map.fitBounds(boundsPB, {{ padding: [20, 20] }});
    }}

    // Inicia enquadrado perfeitamente na Paraíba
    resetarZoom();
    renderizarCamada();
  </script>
</body>
</html>
"""

    cam_html = diretorio_reports / "mapa_lisa_interativo_pb.html"
    cam_html.write_text(html_template, encoding="utf-8")

    # 2. VERSÃO ESTÁTICA BICOMPARTIMENTADA PNG (Mapa Real + Gráfico de Barras)
    fig, (ax_mapa, ax_barras) = plt.subplots(1, 2, figsize=(14, 6.5), gridspec_kw={"width_ratios": [2.2, 1.0]})

    # Polígonos reais da Paraíba no ax_mapa
    patches_por_cor: dict[str, list[MplPolygon]] = {c: [] for c in cores_lisa.values()}
    
    for feat in malha_geojson.get("features", []):
        cod7 = str(feat.get("properties", {}).get("codarea", ""))
        info = mapa_dados.get(cod7, {})
        cluster = str(info.get("cluster_lisa", "Não Significante"))
        cor = cores_lisa.get(cluster, "#f1f5f9")

        geom = feat.get("geometry", {})
        coords = geom.get("coordinates", [])
        geom_type = geom.get("type", "Polygon")

        if geom_type == "Polygon":
            for ring in coords:
                if len(ring) > 2:
                    patches_por_cor[cor].append(MplPolygon(ring, closed=True))
        elif geom_type == "MultiPolygon":
            for poly in coords:
                for ring in poly:
                    if len(ring) > 2:
                        patches_por_cor[cor].append(MplPolygon(ring, closed=True))

    for cor, patch_list in patches_por_cor.items():
        if patch_list:
            edge_color = "#334155" if cor != "#f1f5f9" else "#94a3b8"
            lw = 0.8 if cor != "#f1f5f9" else 0.4
            pc = PatchCollection(patch_list, facecolor=cor, edgecolor=edge_color, linewidth=lw, alpha=0.9)
            ax_mapa.add_collection(pc)

    # Anotações dos principais polos regionais
    cidades_polo = {
        "João Pessoa": (-34.86, -7.12),
        "Campina Grande": (-35.88, -7.22),
        "Patos": (-37.28, -7.02),
        "Sousa": (-38.23, -6.76),
        "Cajazeiras": (-38.56, -6.89),
        "Guarabira": (-35.49, -6.85),
    }
    for nome, (lon, lat) in cidades_polo.items():
        ax_mapa.plot(lon, lat, marker="o", color="#0f172a", markersize=4, zorder=5)
        ax_mapa.text(lon, lat + 0.08, nome, fontsize=8, weight="bold", ha="center", color="#0f172a",
                     bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.8, edgecolor="#cbd5e1", lw=0.5))

    ax_mapa.autoscale()
    ax_mapa.set_aspect("equal")
    ax_mapa.set_xlim(-38.9, -34.7)
    ax_mapa.set_ylim(-8.4, -5.9)
    ax_mapa.set_title("CLUSTERS ESPACIAIS LISA NA PARAÍBA (223 MUNICÍPIOS)\nContiguidade Queen • Padrão Anselin Local Moran", fontsize=11, weight="bold")
    ax_mapa.axis("off")

    # Gráfico de Barras no ax_barras
    ordem_clusters = [
        "Alto-Alto (Hotspot)",
        "Baixo-Baixo (Coldspot)",
        "Baixo-Alto (Anomalia)",
        "Alto-Baixo (Anomalia)",
        "Não Significante",
    ]
    valores = [contagens.get(c, 0) for c in ordem_clusters]
    cores_barras = [cores_lisa[c] for c in ordem_clusters]

    barras = ax_barras.barh(ordem_clusters, valores, color=cores_barras, edgecolor="#334155", linewidth=1.0)
    ax_barras.bar_label(barras, padding=4, weight="bold", fontsize=9)
    ax_barras.invert_yaxis()
    ax_barras.set_title("DISTRIBUIÇÃO DOS MUNICÍPIOS\n(Contagem por Categoria)", fontsize=11, weight="bold")
    ax_barras.set_xlabel("Quantidade de Municípios")
    ax_barras.grid(axis="x", alpha=0.3)
    ax_barras.set_axisbelow(True)

    fig.tight_layout()
    cam_png = diretorio_figuras / "mapa_lisa_clusters_pb.png"
    fig.savefig(cam_png, dpi=200)
    plt.close(fig)

    return cam_csv, cam_png
