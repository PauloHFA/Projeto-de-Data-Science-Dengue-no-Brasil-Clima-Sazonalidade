"""Módulos de ingestão de dados e versionamento por hash SHA-256 (REG-08)."""

from dengue.ingestao.ibge import carregar_ou_baixar_populacao_pb
from dengue.ingestao.infodengue import carregar_ou_baixar_infodengue_pb
from dengue.ingestao.inmet import carregar_ou_baixar_clima_pb, mapear_estacao_mais_proxima
from dengue.ingestao.registro import calcular_sha256, registrar_arquivo_manifesto
from dengue.ingestao.sinan import carregar_ou_baixar_sinan_pb

__all__ = [
    "calcular_sha256",
    "registrar_arquivo_manifesto",
    "carregar_ou_baixar_populacao_pb",
    "carregar_ou_baixar_clima_pb",
    "mapear_estacao_mais_proxima",
    "carregar_ou_baixar_sinan_pb",
    "carregar_ou_baixar_infodengue_pb",
]

