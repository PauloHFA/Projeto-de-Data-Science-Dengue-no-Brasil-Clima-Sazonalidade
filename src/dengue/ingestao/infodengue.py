"""Módulo de ingestão e benchmark externo via API pública do InfoDengue (Fiocruz/FGV) para a Paraíba (PB)."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from dengue.config import ANO_FIM, ANO_INICIO, RAW_DIR, UF_PILOTO
from dengue.ingestao.registro import registrar_arquivo_manifesto

BASE_URL_INFODENGUE = "https://info.dengue.mat.br/api/alertcity"


def baixar_serie_infodengue_municipio(
    geocode_ibge7: str | int,
    ano_inicio: int = ANO_INICIO,
    ano_fim: int = ANO_FIM,
    timeout: int = 15,
) -> pd.DataFrame | None:
    """Baixa a série histórica semanal do InfoDengue (Fiocruz/FGV) para um município pelo código IBGE de 7 dígitos.
    
    A API retorna dados epidemiológicos e climáticos processados pelo InfoDengue:
    - casos, casos_est (nowcasting), temperatura, umidade, nível de alerta (1=verde a 4=vermelho).
    """
    params = {
        "geocode": str(geocode_ibge7),
        "disease": "dengue",
        "format": "csv",
        "ew_start": 1,
        "ew_end": 53,
        "ey_start": ano_inicio,
        "ey_end": ano_fim,
    }
    try:
        resp = requests.get(BASE_URL_INFODENGUE, params=params, timeout=timeout)
        if resp.status_code == 200 and len(resp.content) > 50:
            df = pd.read_csv(io.StringIO(resp.text))
            return df
        return None
    except Exception:
        return None


def carregar_ou_baixar_infodengue_pb(
    df_pop: pd.DataFrame,
    diretorio_raw: Path = RAW_DIR,
    limite_municipios: int | None = 5,
    forcar_download: bool = False,
) -> pd.DataFrame:
    """Baixa ou consolida o benchmark do InfoDengue para municípios polo da Paraíba (PB).
    
    Conforme Seção 3 e 5.7:
    'InfoDengue: Estimativas e nowcasting de casos (Fiocruz/FGV). Usar como benchmark externo, não como verdade.'
    """
    diretorio_raw.mkdir(parents=True, exist_ok=True)
    caminho_parquet = diretorio_raw / "infodengue_benchmark_pb.parquet"

    if caminho_parquet.exists() and not forcar_download:
        return pd.read_parquet(caminho_parquet)

    # Identifica municípios de referência com código IBGE 7
    muns = df_pop[["municipio", "municipio_ibge7", "nome_municipio"]].drop_duplicates()
    if limite_municipios:
        muns = muns.head(limite_municipios)

    dfs_infodengue = []
    for _, row in muns.iterrows():
        cod7 = row["municipio_ibge7"]
        df_mun = baixar_serie_infodengue_municipio(cod7)
        if df_mun is not None and not df_mun.empty:
            df_mun["municipio"] = str(row["municipio"])
            df_mun["nome_municipio"] = row["nome_municipio"]
            dfs_infodengue.append(df_mun)

    if dfs_infodengue:
        df_consolidado = pd.concat(dfs_infodengue, ignore_index=True)
        fonte = "INFODENGUE_FIOCRUZ_FGV_API_PUBLICA"
    else:
        # Fallback estruturado caso a API pública esteja indisponível ou offline
        df_consolidado = pd.DataFrame(
            columns=[
                "municipio",
                "nome_municipio",
                "SE",
                "casos",
                "casos_est",
                "tempmed",
                "umidmed",
                "nivel",
            ]
        )
        fonte = "INFODENGUE_OFFLINE_PLACEHOLDER"

    df_consolidado.to_parquet(caminho_parquet, index=False)

    registrar_arquivo_manifesto(
        caminho_arquivo=caminho_parquet,
        fonte=fonte,
        versao="v1_alertcity",
        metadados_extras={
            "uf": UF_PILOTO,
            "municipios_consultados": muns["municipio"].tolist(),
            "n_registros": len(df_consolidado),
        },
        caminho_manifesto=diretorio_raw / "manifesto_hashes.json",
    )
    return df_consolidado
