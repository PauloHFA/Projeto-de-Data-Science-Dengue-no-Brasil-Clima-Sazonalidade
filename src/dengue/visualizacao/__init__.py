"""Módulos de visualização, análise espacial (P4) e agrupamento sazonal (P3)."""

from dengue.visualizacao.dashboard import (
    gerar_dashboard_interativo_html,
    gerar_graficos_visuais_leigos,
)
from dengue.visualizacao.graficos import (
    calcular_associacao_defasagens_p2,
    calcular_autocorrelacao_espacial_moran_p4,
    clusterizar_perfis_sazonais_p3,
    gerar_figuras_relatorio,
)

__all__ = [
    "calcular_associacao_defasagens_p2",
    "clusterizar_perfis_sazonais_p3",
    "calcular_autocorrelacao_espacial_moran_p4",
    "gerar_figuras_relatorio",
    "gerar_graficos_visuais_leigos",
    "gerar_dashboard_interativo_html",
]

