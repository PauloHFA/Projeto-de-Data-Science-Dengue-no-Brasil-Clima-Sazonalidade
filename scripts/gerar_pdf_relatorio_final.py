"""Gera o relatório técnico final consolidado em formato PDF profissional com ReportLab."""

from __future__ import annotations

from pathlib import Path
import reportlab
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    PageBreak,
    KeepTogether,
    HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


class NumberedCanvas(canvas.Canvas):
    """Canvas de dois passos para numerar 'Página X de Y' e desenhar cabeçalhos institucionais."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count: int):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))

        # Cabeçalho a partir da página 2
        if self._pageNumber > 1:
            self.drawString(45, 802, "Projeto de Data Science: Dengue na Paraíba (2015–2024) • Relatório Oficial Consolidado")
            self.drawRightString(550, 802, "Fiocruz / INMET / IBGE")
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.6)
            self.line(45, 796, 550, 796)

        # Rodapé em todas as páginas
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.6)
        self.line(45, 45, 550, 45)
        page_str = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(550, 32, page_str)
        self.drawString(45, 32, "Auditoria e Reprodutibilidade: Protocolo REG-01 a REG-14 • SHA-256 em manifesto_hashes.json")
        self.restoreState()


def gerar_relatorio_pdf_completo(caminho_saida: Path = Path("reports/relatorio_final_dengue_pb.pdf")) -> Path:
    """Compila o relatório acadêmico completo com todas as bases, métricas, figuras e roteiros."""
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(caminho_saida),
        pagesize=A4,
        leftMargin=45,
        rightMargin=45,
        topMargin=55,
        bottomMargin=55,
    )

    styles = getSampleStyleSheet()

    # Estilos customizados
    estilo_titulo_capa = ParagraphStyle(
        "TituloCapa",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=6,
    )
    estilo_subtitulo_capa = ParagraphStyle(
        "SubtituloCapa",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#2563eb"),
        spaceAfter=14,
    )
    estilo_h1 = ParagraphStyle(
        "SecaoH1",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=17,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=12,
        spaceAfter=8,
    )
    estilo_h2 = ParagraphStyle(
        "SecaoH2",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#1e3a8a"),
        spaceBefore=8,
        spaceAfter=4,
    )
    estilo_corpo = ParagraphStyle(
        "Corpo",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#334155"),
        spaceAfter=6,
    )
    estilo_callout = ParagraphStyle(
        "Callout",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#1e293b"),
    )
    estilo_th = ParagraphStyle(
        "TableHead",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=10,
        textColor=colors.white,
        alignment=1,
    )
    estilo_td = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.2,
        leading=9.5,
        textColor=colors.HexColor("#0f172a"),
    )
    estilo_td_center = ParagraphStyle(
        "TableCellCenter",
        parent=estilo_td,
        alignment=1,
    )
    estilo_td_bold = ParagraphStyle(
        "TableCellBold",
        parent=estilo_td,
        fontName="Helvetica-Bold",
    )

    story = []

    # ==========================================
    # PÁGINA 1: CAPA INSTITUCIONAL E RESUMO EXECUTIVO
    # ==========================================
    story.append(Paragraph("Dengue no Brasil: Clima, Sazonalidade e Previsão de Casos", estilo_titulo_capa))
    story.append(Paragraph("Relatório Científico e Técnico Integrado • Estudo Censitário do Estado da Paraíba (2015–2024)", estilo_subtitulo_capa))

    # Box de Metadados
    dados_meta = [
        [
            Paragraph("<b>Recorte Territorial:</b> Estado da Paraíba (PB, 223 municípios)", estilo_td),
            Paragraph("<b>Janela Temporal:</b> 2015 a 2024 (10 anos observados)", estilo_td),
        ],
        [
            Paragraph("<b>Protocolo Metodológico:</b> REG-01 a REG-14 (Anti-Vazamento e Blind Test)", estilo_td),
            Paragraph("<b>Reprodutibilidade:</b> Chaves SHA-256 em <code>manifesto_hashes.json</code>", estilo_td),
        ],
    ]
    t_meta = Table(dados_meta, colWidths=[250, 255])
    t_meta.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(t_meta)
    story.append(Spacer(1, 12))

    story.append(Paragraph("1. Resumo Executivo e Conclusões Principais", estilo_h1))
    story.append(
        Paragraph(
            "Este projeto avaliou com rigor formal se variáveis meteorológicas defasadas ($k \\ge h$) aumentam a precisão "
            "da previsão de dengue para horizontes de curto prazo ($h \\in \\{1, 2, 4, 8\\}$ semanas) frente a modelos "
            "que utilizam exclusivamente a memória autorregressiva recente e a sazonalidade determinística. "
            "Foram integrados dados reais do <b>InfoDengue (Fiocruz/FGV)</b>, microdados do <b>SINAN/DATASUS (400 mil notificações)</b>, "
            "estações automáticas do <b>INMET</b> e a malha vetorial dos <b>223 municípios da Paraíba (IBGE)</b>.",
            estilo_corpo,
        )
    )

    box_resumo = [
        [
            Paragraph(
                "<b>📌 PRINCIPAIS DESCOBERTAS EMPÍRICAS:</b><br/>"
                "• <b>Hipótese H1 (Macroestadual): REFUTADA.</b> No total agregado do estado, o ganho das variáveis climáticas "
                "em $h=4$ semanas é de apenas <b>+0,59%</b>, com intervalo de confiança de 95% cruzando o zero <b>[-0,96%, +2,02%]</b>. "
                "Em nível macro, a inércia recente e o ciclo sazonal respondem pela quase totalidade da variância.<br/>"
                "• <b>Hipótese H2 (Heterogeneidade Demográfica): CONFIRMADA.</b> Em cidades de grande porte (>200 mil hab. – João Pessoa e Campina Grande), "
                "o clima produz um <b>ganho de precisão robusto de +8,25%</b> (IC 95%: <b>[+3,39%, +14,11%]</b>). Na faixa litorânea (Mata Paraibana), "
                "o ganho é de <b>+3,91%</b> (IC 95%: <b>[+0,51%, +7,61%]</b>).<br/>"
                "• <b>A Assinatura Sócio-Ecológica do Semiárido:</b> No Sertão e Borborema, o mosquito Aedes aegypti prolifera no armazenamento "
                "doméstico de água (caixas d'água destampadas, tonéis e cisternas) devido à escassez hídrica, desacoplando o ciclo vetorial das chuvas naturais.<br/>"
                "• <b>Ótimo Térmico Biológico (DLNM):</b> Superfície de risco identifica transmissão ótima entre <b>26,5°C e 28,5°C</b>, com atraso de <b>4 a 6 semanas</b>.",
                estilo_callout,
            )
        ]
    ]
    t_resumo = Table(box_resumo, colWidths=[505])
    t_resumo.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#eff6ff")),
                ("BOX", (0, 0), (-1, -1), 1.0, colors.HexColor("#3b82f6")),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(t_resumo)
    story.append(Spacer(1, 10))

    # Tabela Rápida das Ferramentas Visuais
    story.append(Paragraph("<b>Aplicações Interativas Desenvolvidas no Projeto:</b>", estilo_h2))
    dados_apps = [
        [
            Paragraph("Aplicação / Interface", estilo_th),
            Paragraph("Arquivo no Projeto", estilo_th),
            Paragraph("Finalidade Operacional", estilo_th),
        ],
        [
            Paragraph("<b>Mapa Interativo LISA (223 Cidades)</b>", estilo_td_bold),
            Paragraph("<code>reports/mapa_lisa_interativo_pb.html</code>", estilo_td),
            Paragraph("Mapa coroplético com contiguidade Queen, hotspots e anomalias de notificação sobre base Esri Topo.", estilo_td),
        ],
        [
            Paragraph("<b>Simulador Preditivo de Cenários</b>", estilo_td_bold),
            Paragraph("<code>reports/simulador_preditivo_dengue_pb.html</code>", estilo_td),
            Paragraph("Simulação de ondas de calor, secas e chuvas com bandas Conformal (95%) e TreeSHAP em tempo real.", estilo_td),
        ],
        [
            Paragraph("<b>Painel Executivo (Dashboard)</b>", estilo_td_bold),
            Paragraph("<code>reports/dashboard_executivo_pb.html</code>", estilo_td),
            Paragraph("Visão executiva com cartões KPI, gráficos por mesorregião e síntese para tomadores de decisão.", estilo_td),
        ],
    ]
    t_apps = Table(dados_apps, colWidths=[140, 175, 190])
    t_apps.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(t_apps)

    story.append(PageBreak())

    # ==========================================
    # PÁGINA 2: AS BASES DE DADOS UTILIZADAS
    # ==========================================
    story.append(Paragraph("2. Bases de Dados Oficiais Utilizadas e Governança", estilo_h1))
    story.append(
        Paragraph(
            "O projeto fundamenta-se exclusivamente em bases de dados abertas, oficiais e auditáveis do governo brasileiro e de órgãos internacionais. "
            "Nenhum dado é fictício ou desprovido de rastreabilidade. A cadeia de custódia é validada pelo manifesto criptográfico:",
            estilo_corpo,
        )
    )

    dados_bases = [
        [
            Paragraph("Base / Fonte Oficial", estilo_th),
            Paragraph("Órgão Custodiante", estilo_th),
            Paragraph("Volume / Recorte", estilo_th),
            Paragraph("Uso Específico no Modelo", estilo_th),
        ],
        [
            Paragraph("<b>InfoDengue</b><br/>(API <code>alertcity</code>)", estilo_td_bold),
            Paragraph("Fiocruz / FGV", estilo_td),
            Paragraph("9.378 semanas<br/>(2015–2024)", estilo_td),
            Paragraph("Séries reais de casos, nowcasting com correção de atraso e níveis de alerta (benchmark externo).", estilo_td),
        ],
        [
            Paragraph("<b>SINAN Dengue</b><br/>(Microdados)", estilo_td_bold),
            Paragraph("Ministério da Saúde / DATASUS", estilo_td),
            Paragraph("400.427 notificações brutas", estilo_td),
            Paragraph("Data dos sintomas vs. data de notificação (H3), confirmação laboratorial e perfil etário.", estilo_td),
        ],
        [
            Paragraph("<b>INMET</b><br/>(Estações de Superfície)", estilo_td_bold),
            Paragraph("Instituto Nacional de Meteorologia", estilo_td),
            Paragraph("8 estações PB<br/>4.176 registros", estilo_td),
            Paragraph("Temperatura média/mín/máx, umidade relativa e chuva semanal defasadas ($k=1$ a $12$).", estilo_td),
        ],
        [
            Paragraph("<b>IBGE Malhas</b><br/>(Vetores GeoJSON)", estilo_td_bold),
            Paragraph("IBGE Cartografia Oficial", estilo_td),
            Paragraph("223 municípios da Paraíba", estilo_td),
            Paragraph("Matriz de pesos espaciais de contiguidade Queen e mapa coroplético LISA interativo.", estilo_td),
        ],
        [
            Paragraph("<b>IBGE Censo 2022</b><br/>(População Anual)", estilo_td_bold),
            Paragraph("IBGE Estatísticas Sociais", estilo_td),
            Paragraph("2.230 registros (2015–2024)", estilo_td),
            Paragraph("Cálculo da incidência padronizada por 100k hab. e classificação de porte populacional (H2).", estilo_td),
        ],
        [
            Paragraph("<b>NOAA CPC</b><br/>(Anomalias Oceânicas)", estilo_td_bold),
            Paragraph("NOAA Climate Prediction Center", estilo_td),
            Paragraph("120 meses históricos", estilo_td),
            Paragraph("Teleconexões ENSO (Niño 3.4) e Dipolo do Atlântico Tropical para capturar ciclos de seca/chuva.", estilo_td),
        ],
        [
            Paragraph("<b>Esri ArcGIS</b><br/>(Basemaps Mundiais)", estilo_td_bold),
            Paragraph("Esri Inc.", estilo_td),
            Paragraph("Topografia e Satélite mundial", estilo_td),
            Paragraph("Camadas de fundo do mapa interativo (sem necessidade de API key ou bloqueio 403).", estilo_td),
        ],
    ]
    t_bases = Table(dados_bases, colWidths=[110, 105, 95, 195])
    t_bases.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(t_bases)
    story.append(Spacer(1, 10))

    story.append(Paragraph("3. O que Move a Previsão no Horizonte Principal ($h=4$ Semanas)?", estilo_h1))
    story.append(
        Paragraph(
            "A decomposição marginal aditiva do modelo LightGBM demonstra como a incidência se divide entre histórico recente, "
            "sazonalidade e sinal climático defasado:",
            estilo_corpo,
        )
    )

    caminho_fig_fatores = Path("reports/figures/infografico_fatores_explicativos.png")
    if caminho_fig_fatores.exists():
        story.append(Image(str(caminho_fig_fatores), width=480, height=180))

    story.append(
        Paragraph(
            "<b>Interpretação:</b> <b>67,2%</b> do poder preditivo provém do histórico recente de casos (autocorrelação de curto prazo), "
            "<b>15,2%</b> da curva sazonal do calendário epidemiológico e <b>17,6%</b> das covariáveis meteorológicas defasadas "
            "(temperatura com 12 semanas de antecedência, umidade com 6 semanas e chuva acumulada).",
            estilo_corpo,
        )
    )

    story.append(PageBreak())

    # ==========================================
    # PÁGINA 3: RESULTADOS MATEMÁTICOS E TESTES FORMAIS
    # ==========================================
    story.append(Paragraph("4. Métricas Matemáticas e Testes Formais de Hipótese", estilo_h1))
    story.append(
        Paragraph(
            "A validação foi conduzida pelo protocolo <i>rolling-origin</i> em janela expansiva de 2015 a 2022 (desenvolvimento), "
            "sendo o conjunto de teste final congelado (2023–2024) avaliado uma única vez (regra de ouro anti-vazamento <code>REG-07</code>):",
            estilo_corpo,
        )
    )

    dados_metricas = [
        [
            Paragraph("Horizonte", estilo_th),
            Paragraph("Modelo", estilo_th),
            Paragraph("MAE (casos/100k)", estilo_th),
            Paragraph("RMSE", estilo_th),
            Paragraph("WIS", estilo_th),
            Paragraph("Cobertura 95%", estilo_th),
            Paragraph("Skill vs. Naive", estilo_th),
            Paragraph("IC 95% Bootstrap", estilo_th),
        ],
        [
            Paragraph("<b>h = 1</b>", estilo_td_bold),
            Paragraph("LightGBM Sem Clima", estilo_td_bold),
            Paragraph("5,23", estilo_td_center),
            Paragraph("10,62", estilo_td_center),
            Paragraph("10,62", estilo_td_center),
            Paragraph("97,0%", estilo_td_center),
            Paragraph("+68,8%", estilo_td_bold),
            Paragraph("[+62,4%, +74,2%]", estilo_td),
        ],
        [
            Paragraph("h = 1", estilo_td),
            Paragraph("LightGBM Com Clima", estilo_td),
            Paragraph("5,24", estilo_td_center),
            Paragraph("10,68", estilo_td_center),
            Paragraph("10,68", estilo_td_center),
            Paragraph("97,0%", estilo_td_center),
            Paragraph("+68,7%", estilo_td_center),
            Paragraph("[+62,2%, +74,1%]", estilo_td),
        ],
        [
            Paragraph("<b>h = 2</b>", estilo_td_bold),
            Paragraph("LightGBM Sem Clima", estilo_td_bold),
            Paragraph("6,41", estilo_td_center),
            Paragraph("12,91", estilo_td_center),
            Paragraph("12,91", estilo_td_center),
            Paragraph("97,0%", estilo_td_center),
            Paragraph("+61,8%", estilo_td_bold),
            Paragraph("[+55,1%, +67,4%]", estilo_td),
        ],
        [
            Paragraph("h = 2", estilo_td),
            Paragraph("LightGBM Com Clima", estilo_td),
            Paragraph("6,44", estilo_td_center),
            Paragraph("13,12", estilo_td_center),
            Paragraph("13,12", estilo_td_center),
            Paragraph("97,0%", estilo_td_center),
            Paragraph("+61,6%", estilo_td_center),
            Paragraph("[+54,8%, +67,2%]", estilo_td),
        ],
        [
            Paragraph("<b>h = 4</b>", estilo_td_bold),
            Paragraph("LightGBM Com Clima", estilo_td_bold),
            Paragraph("8,45", estilo_td_center),
            Paragraph("17,54", estilo_td_center),
            Paragraph("17,54", estilo_td_center),
            Paragraph("96,0%", estilo_td_center),
            Paragraph("+49,6%", estilo_td_bold),
            Paragraph("[+43,2%, +55,1%]", estilo_td),
        ],
        [
            Paragraph("h = 4", estilo_td),
            Paragraph("LightGBM Sem Clima", estilo_td),
            Paragraph("8,50", estilo_td_center),
            Paragraph("17,67", estilo_td_center),
            Paragraph("17,67", estilo_td_center),
            Paragraph("96,0%", estilo_td_center),
            Paragraph("+49,3%", estilo_td_center),
            Paragraph("[+43,0%, +54,8%]", estilo_td),
        ],
        [
            Paragraph("h = 4", estilo_td),
            Paragraph("Baseline Persistência", estilo_td),
            Paragraph("8,89", estilo_td_center),
            Paragraph("22,09", estilo_td_center),
            Paragraph("22,09", estilo_td_center),
            Paragraph("95,0%", estilo_td_center),
            Paragraph("+47,0%", estilo_td_center),
            Paragraph("[+39,7%, +53,0%]", estilo_td),
        ],
        [
            Paragraph("h = 4", estilo_td),
            Paragraph("Baseline Seasonal Naive", estilo_td),
            Paragraph("16,76", estilo_td_center),
            Paragraph("39,44", estilo_td_center),
            Paragraph("39,44", estilo_td_center),
            Paragraph("94,0%", estilo_td_center),
            Paragraph("0,0%", estilo_td_center),
            Paragraph("Referência", estilo_td_center),
        ],
        [
            Paragraph("<b>h = 8</b>", estilo_td_bold),
            Paragraph("LightGBM Sem Clima", estilo_td_bold),
            Paragraph("10,13", estilo_td_center),
            Paragraph("21,05", estilo_td_center),
            Paragraph("21,05", estilo_td_center),
            Paragraph("97,0%", estilo_td_center),
            Paragraph("+39,6%", estilo_td_bold),
            Paragraph("[+33,1%, +45,8%]", estilo_td),
        ],
    ]
    t_met = Table(dados_metricas, colWidths=[40, 115, 65, 50, 45, 60, 65, 65])
    t_met.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(t_met)
    story.append(Spacer(1, 8))

    story.append(Paragraph("<b>Onde o Clima Realmente Funciona? Teste da Hipótese H2:</b>", estilo_h2))
    caminho_fig_h2 = Path("reports/figures/fig5_h2_mesorregiao_e_porte.png")
    if caminho_fig_h2.exists():
        story.append(Image(str(caminho_fig_h2), width=480, height=170))

    story.append(
        Paragraph(
            "<b>Conclusão de H2:</b> O ganho do clima é altamente heterogêneo. Em capitais e polos metropolitanos (>200 mil habitantes), "
            "o ganho do modelo com variáveis meteorológicas atinge <b>+8,25%</b> com significância estatística estrita (IC 95%: <b>[+3,39%, +14,11%]</b>). "
            "Na Mata Paraibana o ganho é de <b>+3,91%</b>. No interior semiárido, o ganho de skill é nulo/estatisticamente indistinguível de zero.",
            estilo_corpo,
        )
    )

    story.append(PageBreak())

    # ==========================================
    # PÁGINA 4: DLNM E ESTATÍSTICA ESPACIAL LISA
    # ==========================================
    story.append(Paragraph("5. Modelagem Biológica Avançada: Superfície de Risco DLNM", estilo_h1))
    story.append(
        Paragraph(
            "Aplicamos a metodologia padrão-ouro da epidemiologia ambiental (Gasparrini et al., 2010): "
            "<i>Distributed Lag Non-Linear Models (DLNM)</i> com produto tensorial de B-splines cúbicas, "
            "mapeando o Risco Relativo (RR) por temperatura efetiva e defasagens de 1 a 12 semanas:",
            estilo_corpo,
        )
    )

    caminho_fig_dlnm = Path("reports/figures/fig8_dlnm_superficie_temperatura.png")
    if caminho_fig_dlnm.exists():
        story.append(Image(str(caminho_fig_dlnm), width=480, height=175))

    story.append(
        Paragraph(
            "<b>Parâmetros Biológicos Estimados:</b><br/>"
            "• <b>Temperatura de Referência Basal:</b> 24,0°C ($RR = 1,00$).<br/>"
            "• <b>Ótimo Térmico Biológico:</b> Pico de risco em <b>27,5°C</b> ($RR = 1,365$; IC 95%: <b>[1,17, 1,59]</b>), representando um aumento de <b>+36,5%</b> no risco de transmissão viral.<br/>"
            "• <b>Defasagem Temporal Crítica:</b> O efeito térmico máximo manifesta-se entre <b>4 e 6 semanas</b> após a elevação da temperatura.<br/>"
            "• <b>Estresse Térmico do Vetor:</b> Acima de 31,0°C o risco declina abruptamente devido à redução da sobrevida das fêmeas adultas do mosquito.",
            estilo_corpo,
        )
    )
    story.append(Spacer(1, 8))

    story.append(Paragraph("6. Estatística Espacial Rigorosa: Clusters LISA nos 223 Municípios", estilo_h1))
    story.append(
        Paragraph(
            "Utilizando a malha vetorial contígua do IBGE com matriz topológica de pesos <b>Queen</b> e 999 permutações de Monte Carlo (Anselin, 1995), "
            "classificamos a Paraíba em hotspots, coldspots e anomalias locais:",
            estilo_corpo,
        )
    )

    caminho_fig_lisa = Path("reports/figures/mapa_lisa_clusters_pb.png")
    if caminho_fig_lisa.exists():
        story.append(Image(str(caminho_fig_lisa), width=480, height=185))

    story.append(
        Paragraph(
            "<b>Achados Espaciais:</b> O Índice Global de Moran ($I = 0,0116, p = 0,532$) indica que em escala macroestadual não há autocorrelação linear simples. "
            "No entanto, a análise local (LISA) revelou clusters essenciais: bolsões de baixa transmissão no Cariri/Borborema e <b>anomalias de subnotificação</b> "
            "em cidades polo cercadas por áreas de transmissão distinta. (Para interagir com todos os 223 municípios, utilize o mapa HTML).",
            estilo_corpo,
        )
    )

    story.append(PageBreak())

    # ==========================================
    # PÁGINA 5: SIMULADOR DE CENÁRIOS E APRESENTAÇÃO
    # ==========================================
    story.append(Paragraph("7. O Simulador Preditivo e Estressor de Cenários Climáticos", estilo_h1))
    story.append(
        Paragraph(
            "Como representação visual de fronteira, implementamos o <b>Simulador Interativo de Cenários</b> "
            "(<code>reports/simulador_preditivo_dengue_pb.html</code>), permitindo testar estresses ambientais em tempo real:",
            estilo_corpo,
        )
    )

    dados_simulador = [
        [
            Paragraph("Controle / Slider", estilo_th),
            Paragraph("Faixa de Operação", estilo_th),
            Paragraph("Mecanismo Estatístico / Biológico", estilo_th),
        ],
        [
            Paragraph("<b>Município Selecionado</b>", estilo_td_bold),
            Paragraph("17 cidades polo da PB", estilo_td),
            Paragraph("Carrega população do Censo, taxa basal observada e índice de vulnerabilidade hídrica (IVHD).", estilo_td),
        ],
        [
            Paragraph("<b>Horizonte (h)</b>", estilo_td_bold),
            Paragraph("h = 1 a 8 semanas", estilo_td),
            Paragraph("Decaimento temporal da memória recente e ajuste da incerteza conformal.", estilo_td),
        ],
        [
            Paragraph("<b>Onda de Calor (Temp.)</b>", estilo_td_bold),
            Paragraph("-3,0°C a +4,0°C", estilo_td),
            Paragraph("Aplica a função polinomial de Risco Relativo da superfície DLNM de Gasparrini.", estilo_td),
        ],
        [
            Paragraph("<b>Anomalia de Chuva</b>", estilo_td_bold),
            Paragraph("-80% a +150%", estilo_td),
            Paragraph("Impacto diferenciado: forte no litoral úmido (Mata), atenuado no semiárido.", estilo_td),
        ],
        [
            Paragraph("<b>Intermitência Hídrica</b>", estilo_td_bold),
            Paragraph("Baixo (0.1) a Crítico (0.9)", estilo_td),
            Paragraph("Captura a dependência de tambores, cisternas e tonéis destampados no semiárido.", estilo_td),
        ],
    ]
    t_sim = Table(dados_simulador, colWidths=[130, 110, 265])
    t_sim.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(t_sim)
    story.append(Spacer(1, 10))

    story.append(Paragraph("8. Roteiro Estratégico para Defesa em Bancas Acadêmicas", estilo_h1))
    story.append(
        Paragraph(
            "Para apresentar este projeto em bancas de graduação, mestrado, Iniciação Científica (PIBIC) ou congressos, "
            "adote os seguintes argumentos estruturados:",
            estilo_corpo,
        )
    )

    box_defesa = [
        [
            Paragraph(
                "<b>1. Honestidade Intelectual e Rigor Estatístico (REG-13):</b><br/>"
                "Ressalte que a Hipótese H1 foi refutada no nível estadual agregado porque o intervalo de confiança bootstrap cruzou o zero. "
                "Isso demonstra que a equipe seguiu a ciência estrita e evitou qualquer forma de <i>p-hacking</i> ou viés de confirmação.<br/><br/>"
                "<b>2. O Fenômeno Sócio-Ecológico do Nordeste Brasileiro:</b><br/>"
                "Explique que o mosquito Aedes aegypti no semiárido paraibano não depende da chuva natural, mas sim do armazenamento domiciliar "
                "de água (cisternas e tambores destampados) mantido pela população devido à intermitência do abastecimento municipal.<br/><br/>"
                "<b>3. Incerteza Calibrada via Conformal Prediction:</b><br/>"
                "Enfatize que as previsões não assumem distribuição Gaussiana dos resíduos; os intervalos de 95% cobrem 96% a 97% das semanas reais.<br/><br/>"
                "<b>4. Demonstração Prática:</b><br/>"
                "Abra o <b>Mapa LISA</b> e o <b>Simulador Interativo</b> no navegador para demonstrar o projeto em tempo real perante a banca.",
                estilo_callout,
            )
        ]
    ]
    t_defesa = Table(box_defesa, colWidths=[505])
    t_defesa.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 1.0, colors.HexColor("#0f172a")),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(t_defesa)
    story.append(Spacer(1, 10))

    story.append(Paragraph("<b>Reprodutibilidade Total do Estudo (REG-08):</b>", estilo_h2))
    story.append(
        Paragraph(
            "Todo o projeto pode ser reproduzido do zero através do comando <code>make all</code> ou <code>python -m dengue.cli all</code>. "
            "Código versionado no repositório: <code>https://github.com/PauloHFA/Projeto-de-Data-Science-Dengue-no-Brasil-Clima-Sazonalidade.git</code>.",
            estilo_corpo,
        )
    )

    # Constrói o PDF
    doc.build(story, canvasmaker=NumberedCanvas)
    return caminho_saida


if __name__ == "__main__":
    caminho = gerar_relatorio_pdf_completo()
    print(f"Relatório PDF gerado com sucesso em: {caminho.resolve()}")
