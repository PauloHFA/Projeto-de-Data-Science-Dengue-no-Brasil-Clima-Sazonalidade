"""Módulos de engenharia de atributos sem vazamento temporal (REG-01, REG-14)."""

from dengue.features.engenharia import (
    EscalonadorPorDobra,
    adicionar_atributos_sazonais,
    adicionar_defasagens,
    construir_matriz_features_horizonte,
    listar_colunas_features,
    verificar_features_respeitam_horizonte,
)

__all__ = [
    "adicionar_defasagens",
    "adicionar_atributos_sazonais",
    "construir_matriz_features_horizonte",
    "listar_colunas_features",
    "verificar_features_respeitam_horizonte",
    "EscalonadorPorDobra",
]

