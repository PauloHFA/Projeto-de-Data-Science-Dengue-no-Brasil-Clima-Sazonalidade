"""Contratos de dados automatizados com Pandera (REG-09)."""

from __future__ import annotations

import pandas as pd
import pandera.pandas as pa
from pandera.pandas import Check, Column, DataFrameSchema

from dengue.config import ANO_FIM, ANO_INICIO

# 1. Contrato de notificações limpas do SINAN (PB)
SCHEMA_NOTIFICACOES_LIMPAS = DataFrameSchema(
    columns={
        "ID_NOTIFIC": Column(str, nullable=False),
        "municipio": Column(
            str,
            checks=[
                Check.str_matches(r"^25\d{4}$", error="Código IBGE municipal deve ter 6 dígitos iniciando em 25 (PB)"),
            ],
            nullable=False,
        ),
        "dt_sintomas": Column(
            "datetime64[ns]",
            checks=[
                Check.ge(pd.Timestamp(f"{ANO_INICIO}-01-01")),
                Check.le(pd.Timestamp(f"{ANO_FIM}-12-31")),
            ],
            nullable=False,
        ),
        "dt_notificacao": Column(
            "datetime64[ns]",
            checks=[
                Check.ge(pd.Timestamp(f"{ANO_INICIO}-01-01")),
            ],
            nullable=False,
        ),
        "CLASSI_FIN": Column(
            str,
            checks=[
                Check.ne("5", error="Casos descartados (CLASSI_FIN == '5') não podem permanecer na base limpa"),
            ],
            nullable=False,
        ),
        "idade_anos": Column(
            float,
            checks=[
                Check.ge(0.0),
                Check.le(120.0),
            ],
            nullable=False,
        ),
        "atraso_dias": Column(
            int,
            checks=[
                Check.ge(0),
                Check.le(365),
            ],
            nullable=False,
        ),
    },
    strict=False,
    coerce=True,
)

# 2. Contrato de séries meteorológicas semanais (INMET)
SCHEMA_CLIMA_SEMANAL = DataFrameSchema(
    columns={
        "codigo_estacao": Column(str, nullable=False),
        "semana": Column("datetime64[ns]", nullable=False),
        "temp_media": Column(float, checks=[Check.ge(-5.0), Check.le(45.0)], nullable=False),
        "temp_min": Column(float, checks=[Check.ge(-10.0), Check.le(40.0)], nullable=False),
        "temp_max": Column(float, checks=[Check.ge(0.0), Check.le(50.0)], nullable=False),
        "chuva_acum": Column(float, checks=[Check.ge(0.0), Check.le(1000.0)], nullable=False),
        "umidade_media": Column(float, checks=[Check.ge(5.0), Check.le(100.0)], nullable=False),
    },
    strict=False,
    coerce=True,
)

# 3. Contrato de população municipal (IBGE)
SCHEMA_POPULACAO = DataFrameSchema(
    columns={
        "municipio": Column(str, checks=[Check.str_matches(r"^25\d{4}$")], nullable=False),
        "nome_municipio": Column(str, nullable=False),
        "ano": Column(int, checks=[Check.ge(ANO_INICIO), Check.le(ANO_FIM)], nullable=False),
        "populacao": Column(int, checks=[Check.gt(0)], nullable=False),
        "lat": Column(float, checks=[Check.ge(-9.0), Check.le(-5.5)], nullable=False),
        "lon": Column(float, checks=[Check.ge(-39.5), Check.le(-34.0)], nullable=False),
    },
    strict=False,
    coerce=True,
)

# 4. Contrato do painel consolidado (Município x Semana Epidemiológica)
SCHEMA_PAINEL_SEMANAL = DataFrameSchema(
    columns={
        "municipio": Column(str, checks=[Check.str_matches(r"^25\d{4}$")], nullable=False),
        "semana": Column("datetime64[ns]", nullable=False),
        "ano": Column(int, checks=[Check.ge(ANO_INICIO), Check.le(ANO_FIM)], nullable=False),
        "se": Column(int, checks=[Check.ge(1), Check.le(53)], nullable=False),
        "casos": Column(int, checks=[Check.ge(0)], nullable=False),
        "populacao": Column(int, checks=[Check.gt(0)], nullable=False),
        "incidencia_100k": Column(float, checks=[Check.ge(0.0)], nullable=False),
        "temp_media": Column(float, checks=[Check.ge(-5.0), Check.le(45.0)], nullable=False),
        "chuva_acum": Column(float, checks=[Check.ge(0.0), Check.le(1000.0)], nullable=False),
        "umidade_media": Column(float, checks=[Check.ge(5.0), Check.le(100.0)], nullable=False),
    },
    strict=False,
    coerce=True,
)


def validar_contrato_notificacoes(df: pd.DataFrame) -> pd.DataFrame:
    """Valida o DataFrame de notificações limpas contra o contrato Pandera (REG-09)."""
    return SCHEMA_NOTIFICACOES_LIMPAS.validate(df, lazy=True)


def validar_contrato_clima(df: pd.DataFrame) -> pd.DataFrame:
    """Valida o DataFrame climático semanal contra o contrato Pandera (REG-09)."""
    return SCHEMA_CLIMA_SEMANAL.validate(df, lazy=True)


def validar_contrato_populacao(df: pd.DataFrame) -> pd.DataFrame:
    """Valida o DataFrame de população municipal contra o contrato Pandera (REG-09)."""
    return SCHEMA_POPULACAO.validate(df, lazy=True)


def validar_contrato_painel_semanal(df: pd.DataFrame) -> pd.DataFrame:
    """Valida o painel consolidado semanal (município x SE) contra o contrato Pandera (REG-09)."""
    return SCHEMA_PAINEL_SEMANAL.validate(df, lazy=True)

