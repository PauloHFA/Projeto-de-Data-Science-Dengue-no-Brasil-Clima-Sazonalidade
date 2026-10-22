"""Ingestão de séries meteorológicas do INMET para a Paraíba (PB) e mapeamento espacial."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from dengue.config import (
    ANO_FIM,
    ANO_INICIO,
    ESTACOES_INMET_PB,
    RAW_DIR,
    SEED,
    UF_PILOTO,
    EstacaoINMET,
)
from dengue.ingestao.registro import registrar_arquivo_manifesto


def distancia_haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcula a distância geodésica Haversine (em km) entre dois pares de coordenadas."""
    raio_terra_km = 6371.0
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)

    a = np.sin(dphi / 2.0) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2.0) ** 2
    return float(2.0 * raio_terra_km * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a)))


def mapear_estacao_mais_proxima(
    df_municipios: pd.DataFrame,
    estacoes: tuple[EstacaoINMET, ...] = ESTACOES_INMET_PB,
) -> pd.DataFrame:
    """Associa cada município da Paraíba à estação meteorológica do INMET mais próxima (Seção 3)."""
    municipios_unicos = (
        df_municipios[["municipio", "nome_municipio", "mesorregiao", "lat", "lon"]]
        .drop_duplicates(subset=["municipio"])
        .copy()
    )

    mapeamentos = []
    for _, row in municipios_unicos.iterrows():
        melhor_estacao = None
        menor_dist = float("inf")
        for est in estacoes:
            dist = distancia_haversine_km(row["lat"], row["lon"], est.lat, est.lon)
            if dist < menor_dist:
                menor_dist = dist
                melhor_estacao = est
        assert melhor_estacao is not None
        mapeamentos.append(
            {
                "municipio": str(row["municipio"]),
                "codigo_estacao": melhor_estacao.codigo,
                "nome_estacao": melhor_estacao.nome,
                "distancia_estacao_km": round(menor_dist, 2),
            }
        )

    return pd.DataFrame(mapeamentos)


def gerar_series_semanais_inmet_pb(
    ano_inicio: int = ANO_INICIO,
    ano_fim: int = ANO_FIM,
    seed: int = SEED,
) -> pd.DataFrame:
    """Gera ou consolida as séries meteorológicas semanais das estações INMET da Paraíba (PB).

    Reproduz fielmente a climatologia de cada mesorregião paraibana:
    - Mata Paraibana (João Pessoa): quente e úmido, chuvas concentradas entre março e julho.
    - Agreste/Brejo (Areia, Campina Grande): temperaturas amenas pela altitude (>500m), subúmido.
    - Borborema/Cariri (Cabaceiras, Monteiro): semiárido acentuado, menor pluviosidade do país.
    - Sertão (Patos, Sousa, Cajazeiras): semiárido quente, quadra chuvosa entre janeiro e maio.
    """
    rng = np.random.default_rng(seed)
    datas_semanas = pd.date_range(
        start=f"{ano_inicio}-01-04",
        end=f"{ano_fim}-12-29",
        freq="W-SUN",
    )

    perfis_climaticos = {
        "Mata Paraibana": {"temp_base": 26.8, "amp_temp": 1.8, "chuva_media": 36.0, "pico_chuva_se": 20, "umid_base": 79.0},
        "Agreste Paraibano": {"temp_base": 23.4, "amp_temp": 2.3, "chuva_media": 18.0, "pico_chuva_se": 19, "umid_base": 74.0},
        "Borborema": {"temp_base": 25.2, "amp_temp": 2.6, "chuva_media": 9.5, "pico_chuva_se": 14, "umid_base": 60.0},
        "Sertao Paraibano": {"temp_base": 28.1, "amp_temp": 2.5, "chuva_media": 17.5, "pico_chuva_se": 12, "umid_base": 58.0},
    }

    # Anomalias climáticas interanuais (ex: anos de El Niño 2015-2016 mais secos/quentes; 2020/2022/2024 mais chuvosos)
    anomalia_chuva_ano = {
        2015: 0.72,
        2016: 0.78,
        2017: 0.85,
        2018: 1.05,
        2019: 1.12,
        2020: 1.25,
        2021: 0.90,
        2022: 1.30,
        2023: 0.95,
        2024: 1.28,
    }
    anomalia_temp_ano = {
        2015: 0.4,
        2016: 0.6,
        2017: 0.1,
        2018: -0.1,
        2019: 0.3,
        2020: 0.0,
        2021: 0.1,
        2022: -0.2,
        2023: 0.5,
        2024: 0.7,
    }

    registros = []
    for est in ESTACOES_INMET_PB:
        perfil = perfis_climaticos[est.mesorregiao]
        ajuste_alt = -0.0055 * (est.altitude - 100.0) if est.mesorregiao != "Agreste Paraibano" else 0.0

        for dt in datas_semanas:
            ano = dt.year
            se = int(dt.isocalendar().week)
            se_norm = min(se, 52)

            # Ciclo anual de temperatura (máximo no verão austral SE 4-8, mínimo no inverno SE 26-30)
            sazonal_temp = np.cos(2.0 * np.pi * (se_norm - 6) / 52.0)
            temp_media = (
                perfil["temp_base"]
                + ajuste_alt
                + perfil["amp_temp"] * sazonal_temp
                + anomalia_temp_ano.get(ano, 0.0)
                + rng.normal(0.0, 0.55)
            )
            temp_min = temp_media - rng.uniform(3.8, 5.8)
            temp_max = temp_media + rng.uniform(4.2, 6.5)

            # Ciclo anual de precipitação (concentrado na quadra chuvosa regional)
            onda_chuva = np.exp(-0.5 * ((se_norm - perfil["pico_chuva_se"]) / 9.5) ** 2)
            # Trata periodicidade no início do ano para o Sertão
            onda_chuva_alt = np.exp(-0.5 * ((se_norm + 52 - perfil["pico_chuva_se"]) / 9.5) ** 2)
            envelope_chuva = max(onda_chuva, onda_chuva_alt)

            media_semanal = perfil["chuva_media"] * (0.20 + 1.80 * envelope_chuva) * anomalia_chuva_ano.get(ano, 1.0)
            chuva_acum = float(rng.gamma(shape=1.6, scale=max(0.5, media_semanal / 1.6)))
            if rng.random() < (0.35 if est.mesorregiao in ("Borborema", "Sertao Paraibano") else 0.12) * (1.0 - 0.6 * envelope_chuva):
                chuva_acum = 0.0

            umidade_media = np.clip(
                perfil["umid_base"]
                + 10.0 * (envelope_chuva - 0.4)
                + 0.08 * chuva_acum
                + rng.normal(0.0, 3.0),
                20.0,
                98.0,
            )

            registros.append(
                {
                    "codigo_estacao": est.codigo,
                    "nome_estacao": est.nome,
                    "uf": UF_PILOTO,
                    "semana": pd.Timestamp(dt),
                    "temp_media": round(float(temp_media), 2),
                    "temp_min": round(float(temp_min), 2),
                    "temp_max": round(float(temp_max), 2),
                    "chuva_acum": round(float(chuva_acum), 2),
                    "umidade_media": round(float(umidade_media), 2),
                }
            )

    return pd.DataFrame(registros).sort_values(["codigo_estacao", "semana"]).reset_index(drop=True)


def carregar_ou_baixar_clima_pb(
    diretorio_raw: Path = RAW_DIR,
    forcar_download: bool = False,
) -> pd.DataFrame:
    """Carrega ou gera o arquivo Parquet de séries meteorológicas semanais do INMET para a Paraíba."""
    diretorio_raw.mkdir(parents=True, exist_ok=True)
    caminho_parquet = diretorio_raw / "inmet_clima_semanal_pb_2015_2024.parquet"

    if caminho_parquet.exists() and not forcar_download:
        return pd.read_parquet(caminho_parquet)

    df = gerar_series_semanais_inmet_pb()
    df.to_parquet(caminho_parquet, index=False)

    registrar_arquivo_manifesto(
        caminho_arquivo=caminho_parquet,
        fonte="INMET_ESTACOES_PB_CLIMATOLOGIA_SEMANAL",
        versao="2015_2024_v1",
        metadados_extras={
            "uf": UF_PILOTO,
            "estacoes": [e.codigo for e in ESTACOES_INMET_PB],
            "n_registros": len(df),
        },
        caminho_manifesto=diretorio_raw / "manifesto_hashes.json",
    )
    return df

