"""Limpeza de notificações do SINAN com funil de exclusão documentado (REG-12) e agregação semanal."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

import numpy as np
import pandas as pd

from dengue.config import ANO_FIM, ANO_INICIO, CODIGO_DESCARTADO_SINAN
from dengue.ingestao.inmet import mapear_estacao_mais_proxima
from dengue.qualidade.contratos import (
    validar_contrato_notificacoes,
    validar_contrato_painel_semanal,
)


@dataclass
class EtapaFunil:
    """Registro auditável de uma etapa do funil de exclusão de dados (REG-12)."""

    etapa: str
    motivo: str
    registros_entrada: int
    registros_removidos: int
    registros_saida: int
    percentual_removido: float


def decodificar_idade_sinan(serie_nu_idade: pd.Series) -> pd.Series:
    """Converte o campo NU_IDADE_N do SINAN (1º dígito = unidade, 3 últimos = valor) para idade em anos."""
    valores = pd.to_numeric(serie_nu_idade, errors="coerce")
    unidade = np.floor(valores / 1000.0)
    quantidade = valores % 1000.0

    idade_anos = pd.Series(np.nan, index=serie_nu_idade.index, dtype="float64")
    # 1 = hora, 2 = dia, 3 = mês, 4 = ano
    idade_anos = np.where(unidade == 4, quantidade, idade_anos)
    idade_anos = np.where(unidade == 3, quantidade / 12.0, idade_anos)
    idade_anos = np.where(unidade == 2, quantidade / 365.25, idade_anos)
    idade_anos = np.where(unidade == 1, 0.0, idade_anos)
    return pd.Series(idade_anos, index=serie_nu_idade.index, dtype="float64")


def limpar_notificacoes_com_funil(
    df_bruto: pd.DataFrame,
    municipios_validos: Iterable[str],
    ano_inicio: int = ANO_INICIO,
    ano_fim: int = ANO_FIM,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Executa a limpeza das notificações do SINAN registrando cada etapa no funil de exclusão (REG-12).

    Retorna:
        (df_limpo, df_funil)
    """
    df = df_bruto.copy()
    funil: list[EtapaFunil] = []
    conjunto_municipios = {str(m) for m in municipios_validos}

    def _registrar_passo(df_antes: pd.DataFrame, mascara_manter: pd.Series, etapa: str, motivo: str) -> pd.DataFrame:
        n_in = len(df_antes)
        df_depois = df_antes.loc[mascara_manter].copy()
        n_out = len(df_depois)
        n_rem = n_in - n_out
        pct = round((100.0 * n_rem / n_in), 4) if n_in > 0 else 0.0
        funil.append(
            EtapaFunil(
                etapa=etapa,
                motivo=motivo,
                registros_entrada=n_in,
                registros_removidos=n_rem,
                registros_saida=n_out,
                percentual_removido=pct,
            )
        )
        return df_depois

    # Etapa 1: Duplicidades de ID_NOTIFIC ou linha exata
    if "ID_NOTIFIC" in df.columns:
        mascara_sem_dup = ~df.duplicated(subset=["ID_NOTIFIC"], keep="first")
    else:
        mascara_sem_dup = ~df.duplicated(keep="first")
    df = _registrar_passo(df, mascara_sem_dup, "1_duplicidades", "Registros duplicados (ID_NOTIFIC repetido)")

    # Etapa 2: Datas de primeiros sintomas e de notificação válidas e na janela temporal do estudo
    df["dt_sintomas"] = pd.to_datetime(df["DT_SIN_PRI"], errors="coerce")
    df["dt_notificacao"] = pd.to_datetime(df["DT_NOTIFIC"], errors="coerce")
    dt_min = pd.Timestamp(f"{ano_inicio}-01-01")
    dt_max = pd.Timestamp(f"{ano_fim}-12-31")

    mascara_datas = (
        df["dt_sintomas"].notna()
        & df["dt_notificacao"].notna()
        & (df["dt_sintomas"] >= dt_min)
        & (df["dt_sintomas"] <= dt_max)
        & (df["dt_notificacao"] >= df["dt_sintomas"])
        & ((df["dt_notificacao"] - df["dt_sintomas"]).dt.days <= 365)
    )
    df = _registrar_passo(
        df,
        mascara_datas,
        "2_datas_invalidas_ou_fora_janela",
        f"DT_SIN_PRI/DT_NOTIFIC inválidas, fora de {ano_inicio}-{ano_fim} ou atraso negativo/>365d",
    )

    # Etapa 3: Código de município pertencente à malha válida da UF piloto (PB)
    df["municipio"] = df["ID_MUNICIP"].astype(str).str.strip().str[:6]
    mascara_mun = df["municipio"].isin(conjunto_municipios)
    df = _registrar_passo(
        df,
        mascara_mun,
        "3_municipio_invalido",
        "Código IBGE municipal ausente ou fora da malha oficial da UF piloto",
    )

    # Etapa 4: Idade plausível [0, 120] anos
    df["idade_anos"] = decodificar_idade_sinan(df["NU_IDADE_N"])
    mascara_idade = df["idade_anos"].notna() & (df["idade_anos"] >= 0.0) & (df["idade_anos"] <= 120.0)
    df = _registrar_passo(
        df,
        mascara_idade,
        "4_idade_fora_da_faixa",
        "Idade decodificada ausente ou fora do intervalo biológico [0, 120] anos",
    )

    # Etapa 5: Exclusão de casos descartados (CLASSI_FIN == '5') -> Definição de Caso Provável (Seção 5.2)
    df["CLASSI_FIN"] = df["CLASSI_FIN"].astype(str).str.strip()
    mascara_caso_provavel = df["CLASSI_FIN"] != CODIGO_DESCARTADO_SINAN
    df = _registrar_passo(
        df,
        mascara_caso_provavel,
        "5_casos_descartados",
        f"Exclusão de notificações descartadas (CLASSI_FIN == '{CODIGO_DESCARTADO_SINAN}')",
    )

    # Cálculo do atraso de notificação em dias (REG-06) e semana epidemiológica de início de sintomas
    df["atraso_dias"] = (df["dt_notificacao"] - df["dt_sintomas"]).dt.days.astype(int)
    # Semana começando no domingo (W-SAT no pandas agrupa domingo..sábado e start_time é domingo)
    df["semana"] = df["dt_sintomas"].dt.to_period("W-SAT").dt.start_time

    df = validar_contrato_notificacoes(df)
    df_funil = pd.DataFrame([asdict(e) for e in funil])
    return df.reset_index(drop=True), df_funil


def construir_painel_semanal(
    df_notificacoes_limpas: pd.DataFrame,
    df_pop: pd.DataFrame,
    df_clima: pd.DataFrame,
) -> pd.DataFrame:
    """Agrega casos prováveis por município e semana epidemiológica e cruza com população e clima (REG-05)."""
    mapa_est = mapear_estacao_mais_proxima(df_pop)

    # Malha completa de (município x semana) baseada nas semanas presentes na série meteorológica
    semanas_unicas = sorted(df_clima["semana"].unique())
    municipios_unicos = sorted(df_pop["municipio"].unique())
    grade = pd.MultiIndex.from_product(
        [municipios_unicos, semanas_unicas],
        names=["municipio", "semana"],
    ).to_frame().reset_index(drop=True)

    # Contagem semanal de casos prováveis e atraso mediano de notificação
    contagem = (
        df_notificacoes_limpas.groupby(["municipio", "semana"], as_index=False)
        .agg(
            casos=("ID_NOTIFIC", "count"),
            atraso_mediano_dias=("atraso_dias", "median"),
            casos_graves=("CLASSI_FIN", lambda s: int(s.isin(["11", "12"]).sum())),
        )
    )

    painel = grade.merge(contagem, on=["municipio", "semana"], how="left")
    painel["casos"] = painel["casos"].fillna(0).astype(int)
    painel["casos_graves"] = painel["casos_graves"].fillna(0).astype(int)
    painel["atraso_mediano_dias"] = painel["atraso_mediano_dias"].fillna(0.0).astype(float)

    painel["ano"] = painel["semana"].dt.year.astype(int)
    painel["se"] = painel["semana"].dt.isocalendar().week.astype(int)

    # Junta população (IBGE) e calcula incidência por 100 mil habitantes (REG-05)
    painel = painel.merge(
        df_pop[["municipio", "nome_municipio", "mesorregiao", "lat", "lon", "ano", "populacao"]],
        on=["municipio", "ano"],
        how="inner",
    )
    painel["incidencia_100k"] = round((painel["casos"] / painel["populacao"]) * 100_000.0, 4)

    # Junta estação meteorológica mais próxima e séries do INMET
    painel = painel.merge(mapa_est, on="municipio", how="left")
    painel = painel.merge(
        df_clima[["codigo_estacao", "semana", "temp_media", "temp_min", "temp_max", "chuva_acum", "umidade_media"]],
        on=["codigo_estacao", "semana"],
        how="inner",
    )

    # Sinaliza as 4 semanas mais recentes da série como sujeitas a truncamento por atraso de notificação (REG-06)
    ultima_semana = painel["semana"].max()
    painel["semana_recente_incompleta"] = painel["semana"] > (ultima_semana - pd.Timedelta(weeks=4))

    painel = painel.sort_values(["municipio", "semana"]).reset_index(drop=True)
    return validar_contrato_painel_semanal(painel)

