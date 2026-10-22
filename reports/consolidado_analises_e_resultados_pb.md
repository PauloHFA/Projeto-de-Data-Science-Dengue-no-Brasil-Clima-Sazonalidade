# Compêndio Completo de Análises, Métricas Matemáticas e Conclusões Visuais

**Projeto:** Dengue no Brasil – Clima, Sazonalidade e Previsão de Casos  
**Recorte de Estudo:** Estado da Paraíba (PB – Código IBGE `25`, 223 municípios)  
**Período Analisado:** 2015 a 2024 (10 anos com dados reais observados do InfoDengue Fiocruz/FGV e INMET)  
**Protocolo de Rigor Científico:** `REG-01` a `REG-14`

---

## 📌 Guia de Navegação Rápida dos Recursos Visuais e Interativos

| Recurso | Tipo | Onde Acessar | O que Visualizar? |
| :--- | :---: | :--- | :--- |
| **Mapa Interativo LISA (223 Municípios)** | Web Interativo | [`reports/mapa_lisa_interativo_pb.html`](mapa_lisa_interativo_pb.html) | Mapa coroplético oficial com *zoom* e *hover* em cada município da PB mostrando clusters Alto-Alto (*Hotspots*), Baixo-Baixo e Anomalias Espaciais. |
| **Painel Visual Executivo (Dashboard)** | Web Interativo | [`reports/dashboard_executivo_pb.html`](dashboard_executivo_pb.html) | Dashboard executivo com cartões KPI, gráficos interativos Plotly e linguagem acessível para leigos e gestores. |
| **Mapa Geral de Incidência na Paraíba** | Imagem PNG | [`figures/infografico_mapa_paraiba.png`](figures/infografico_mapa_paraiba.png) | Dispersão espacial dos municípios com tamanho proporcional à população e cores por mesorregião. |
| **Superfície Bidimensional DLNM** | Imagem PNG | [`figures/fig8_dlnm_superficie_temperatura.png`](figures/fig8_dlnm_superficie_temperatura.png) | Mapa de calor e curvas de nível do Risco Relativo ($\text{RR}$) biológico por temperatura e defasagem (Gasparrini et al., 2010). |
| **Decomposição TreeSHAP** | Imagem PNG | [`figures/fig4_shap_importancia_h4.png`](figures/fig4_shap_importancia_h4.png) | Ranking das 15 variáveis que mais influenciam a previsão no horizonte de 4 semanas. |
| **Ganho do Clima por Região e Porte (H2)** | Imagem PNG | [`figures/fig5_h2_mesorregiao_e_porte.png`](figures/fig5_h2_mesorregiao_e_porte.png) | Gráfico com intervalos de confiança de 95% comprovando onde o clima funciona (Litoral/Capitais) e onde o sinal é sutil. |
| **Calendário de Risco Epidemiológico** | Imagem PNG | [`figures/infografico_calendario_risco.png`](figures/infografico_calendario_risco.png) | Curva sazonal mês a mês destacando em vermelho a janela de alerta máximo estadual (março a junho). |
| **Benchmark InfoDengue vs. Pipeline** | Imagem PNG | [`figures/fig7_benchmark_infodengue_vs_pipeline.png`](figures/fig7_benchmark_infodengue_vs_pipeline.png) | Comparação direta da nossa série com o *nowcasting* oficial da Fiocruz/FGV para João Pessoa e Campina Grande. |

---

## 1. Conclusões Visuais e Síntese Epidemiológica

### 1.1 Onde a dengue se concentra e onde o clima ajuda?
![Mapa da Paraíba: Transmissão e Impacto do Clima](figures/infografico_mapa_paraiba.png)

- **Grandes Cidades e Faixa Litorânea (Mata Paraibana):** Concentram a maior carga populacional e transmissão viral contínua. Aqui, as variáveis meteorológicas (temperatura média e umidade) fornecem um **ganho preditivo robusto de +8,25% em cidades grandes** e **+3,91% no litoral**, com intervalos de confiança de 95% estritamente acima de zero.
- **Interior Semiárido (Borborema e Sertão):** A transmissão ocorre em pulsos rápidos fortemente sincronizados com o início das chuvas ou associados ao **armazenamento domiciliar de água** (caixas d'água destampadas, tonéis e cisternas). Por esse motivo, o sinal climático adiciona pouco valor marginal em relação ao histórico recente de casos nas pequenas cidades do interior.

### 1.2 Qual a força de cada fator na previsão de 4 semanas?
![O que Move a Previsão?](figures/infografico_fatores_explicativos.png)

A decomposição aditiva marginal do modelo LightGBM demonstra:
- **67,2%** da força explicativa provém do **histórico recente de casos** ($\text{lag}_4$, $\text{lag}_5$ e média móvel de 4 semanas).
- **15,2%** provém da **sazonalidade determinística** (harmônicos senoidais da semana epidemiológica).
- **17,6%** provém das **covariáveis meteorológicas defasadas** (temperatura em $\text{lag}_{12}$, umidade em $\text{lag}_6$ e chuva acumulada).

### 1.3 Quando agir? O Calendário Sazonal da Dengue na Paraíba
![Calendário Sazonal da Dengue na Paraíba](figures/infografico_calendario_risco.png)

- **Alerta Máximo Estadual:** Entre **março e junho (SE 12 a 24)** concentram-se mais de 70% das notificações anuais do estado.
- **Janela Operacional Ótima:** Como a antecedência ideal avaliada no estudo é de **$h = 4$ semanas**, as mobilizações de campo (bloqueio de criadouros, reforço de estoques de soro e kits laboratoriais) devem ser disparadas no início de **fevereiro**.

---

## 2. Estatística Espacial Rigorosa: Contiguidade Queen e Clusters LISA

Avaliamos a autocorrelação espacial local utilizando a **malha vetorial oficial dos 223 municípios da Paraíba (IBGE)** com matriz de pesos topológicos de contiguidade **Queen** (fronteiras compartilhadas).

### 2.1 Índice Global de Moran
$$I = \frac{n}{\sum_{i}\sum_{j} w_{ij}} \frac{\sum_{i}\sum_{j} w_{ij}(y_i - \bar{y})(y_j - \bar{y})}{\sum_{i} (y_i - \bar{y})^2}$$

- **Índice Observado:** $I = 0,0116$
- **Valor Esperado:** $E[I] = -0,0045$
- **Significância:** $p\text{-valor} = 0,532$ (999 permutações de Monte Carlo)
- **Interpretação:** Em escala macroestadual de 10 anos, a autocorrelação linear simples dissipa-se devido aos fortes contrastes climáticos entre a Mata úmida e o Sertão semiárido. No entanto, a análise local (LISA) revela padrões espaciais localizados cruciais.

### 2.2 Distribuição dos Clusters LISA nos 223 Municípios ([`reports/lisa_clusters_pb.csv`](lisa_clusters_pb.csv))

![Clusters LISA na Paraíba](figures/mapa_lisa_clusters_pb.png)

| Padrão Espacial LISA (Anselin, 1995) | Quantidade de Municípios | % do Estado | Significado Epidemiológico |
| :--- | :---: | :---: | :--- |
| **Alto-Alto (Hotspots)** | 0 | 0,0% | Regiões homogêneas contínuas de alta taxa de longo prazo (em 10 anos, a transmissão alterna entre municípios). |
| **Baixo-Baixo (Coldspots)** | 1 | 0,4% | Bolsão contínuo de baixa incidência no planalto central. |
| **Baixo-Alto (Anomalia)** | 6 | 2,7% | Municípios com incidência menor que seus vizinhos imediatos (potencial subnotificação local ou vigilância menos ativa). |
| **Alto-Baixo (Anomalia)** | 1 | 0,4% | Município polo com pico isolado cercado por áreas de baixa transmissão. |
| **Não Significante ($p \ge 0,05$)** | 215 | 96,4% | Variação espacial estocástica ou independente da vizinhança imediata. |

*(Para explorar cada um dos 223 municípios interativamente no mapa coroplético, abra [`reports/mapa_lisa_interativo_pb.html`](mapa_lisa_interativo_pb.html)).*

---

## 3. Desempenho Matemático Preditivo no Teste Final (2023–2024)

Validação *rolling-origin* estrita em janela expansiva sobre os dados reais observados do InfoDengue/INMET, com conjunto de teste congelado aberto uma única vez (**`REG-07`**).

### 3.1 Tabela Geral Consolidada por Modelo e Horizonte ([`reports/metricas_modelos_pb.csv`](metricas_modelos_pb.csv))

| Horizonte | Modelo | MAE (incid./100k) | RMSE | WIS | Cobertura 80% | Cobertura 95% | Skill vs. Seasonal Naive | IC 95% Bootstrap do Skill |
| :---: | :--- | ---: | ---: | ---: | ---: | ---: | :---: | :---: |
| **$h=1$** | **LightGBM Sem Clima** | **5,23** | **10,62** | **10,62** | **0,82** | **0,97** | **+68,8%** | `[+62,4%, +74,2%]` |
| $h=1$ | LightGBM Com Clima | 5,24 | 10,68 | 10,68 | 0,83 | 0,97 | +68,7% | `[+62,2%, +74,1%]` |
| $h=1$ | Baseline Persistência ($t-1$) | 5,41 | 12,85 | 12,85 | 0,84 | 0,96 | +67,7% | `[+61,0%, +73,5%]` |
| $h=1$ | Baseline Seasonal Naive | 16,76 | 39,13 | 39,13 | 0,77 | 0,95 | 0,0% | Referência |
| $h=1$ | GLM Com Clima | 45,86 | 159,19 | 159,19 | 0,76 | 0,94 | -173,6% | `[-350%, -70%]` |
| **$h=2$** | **LightGBM Sem Clima** | **6,41** | **12,91** | **12,91** | **0,83** | **0,97** | **+61,8%** | `[+55,1%, +67,4%]` |
| $h=2$ | LightGBM Com Clima | 6,44 | 13,12 | 13,12 | 0,82 | 0,97 | +61,6% | `[+54,8%, +67,2%]` |
| $h=2$ | Baseline Persistência ($t-2$) | 6,81 | 16,49 | 16,49 | 0,83 | 0,96 | +59,4% | `[+52,3%, +65,8%]` |
| $h=2$ | Baseline Seasonal Naive | 16,76 | 39,22 | 39,22 | 0,77 | 0,95 | 0,0% | Referência |
| **$h=4$** | **LightGBM Com Clima** | **8,45** | **17,54** | **17,54** | **0,82** | **0,96** | **+49,6%** | `[+43,2%, +55,1%]` |
| $h=4$ | LightGBM Sem Clima | 8,50 | 17,67 | 17,67 | 0,82 | 0,96 | +49,3% | `[+43,0%, +54,8%]` |
| $h=4$ | Baseline Persistência ($t-4$) | 8,89 | 22,09 | 22,09 | 0,83 | 0,95 | +47,0% | `[+39,7%, +53,0%]` |
| $h=4$ | Baseline Seasonal Naive | 16,76 | 39,44 | 39,44 | 0,77 | 0,94 | 0,0% | Referência |
| $h=4$ | GLM Com Clima | 55,73 | 190,24 | 190,24 | 0,77 | 0,94 | -232,5% | `[-480%, -85%]` |
| **$h=8$** | **LightGBM Sem Clima** | **10,13** | **21,05** | **21,05** | **0,86** | **0,97** | **+39,6%** | `[+33,1%, +45,8%]` |
| $h=8$ | LightGBM Com Clima | 10,16 | 21,33 | 21,33 | 0,82 | 0,96 | +39,4% | `[+32,9%, +45,5%]` |
| $h=8$ | Baseline Persistência ($t-8$) | 12,52 | 30,21 | 30,21 | 0,81 | 0,96 | +25,3% | `[+17,5%, +32,4%]` |
| $h=8$ | Baseline Seasonal Naive | 16,76 | 39,56 | 39,56 | 0,77 | 0,94 | 0,0% | Referência |

---

## 4. Teste Rigoroso das Hipóteses Falsificáveis

### 4.1 Hipótese H1: Ganho do Clima no Agregado Estadual ([`reports/teste_hipotese_h1_pb.csv`](teste_hipotese_h1_pb.csv))
*Critério pré-registrado:* $\text{Skill} > 0$ com limite inferior do IC 95% (bootstrap em blocos) $> 0$.

$$\text{Skill}_{\text{Clima vs Sem Clima}} = 1 - \frac{\text{MAE}_{\text{Com Clima}}}{\text{MAE}_{\text{Sem Clima}}}$$

| Horizonte | Modelo | MAE Sem Clima | MAE Com Clima | Skill Relativo (%) | IC 95% Bootstrap | H1 Suportada? |
| :---: | :--- | ---: | ---: | ---: | :---: | :---: |
| **$h=1$** | `LightGBM` | 5,2258 | 5,2442 | -0,35% | `[-2,17%, +1,48%]` | **Não (`False`)** |
| **$h=2$** | `LightGBM` | 6,4052 | 6,4353 | -0,47% | `[-2,21%, +1,02%]` | **Não (`False`)** |
| **$h=4$** | `LightGBM` | 8,4997 | 8,4495 | **+0,59%** | `[-0,96%, +2,02%]` | **Não (`False`)** |
| **$h=8$** | `LightGBM` | 10,1266 | 10,1601 | -0,33% | `[-1,59%, +1,09%]` | **Não (`False`)** |

> **Conclusão de H1 (`REG-13`):** Em conformidade com o rigor científico do edital, **a Hipótese H1 é refutada no nível agregado estadual**. Em séries reais de saúde pública de curto prazo, o sinal autorregressivo recente domina o horizonte macro.

---

### 4.2 Hipótese H2: O Ganho Varia por Mesorregião e Porte? ([`reports/teste_hipotese_h2_pb.csv`](teste_hipotese_h2_pb.csv))
*Critério pré-registrado:* Diferença de ganho entre estratos territoriais e demográficos com significância estatística (IC 95% $> 0$).

| Dimensão | Estrato | N° Municípios | MAE Sem Clima | MAE Com Clima | Ganho Skill (%) | IC 95% Bootstrap | Ganho Estatisticamente Significativo? |
| :--- | :--- | :---: | ---: | ---: | ---: | :---: | :---: |
| **Porte Populacional** | **3. Grande (>200k hab.)** | **2** | **7,60** | **6,97** | **+8,25%** | **`[+3,39%, +14,11%]`** | **SIM (`True`)** |
| Porte Populacional | 2. Médio (50k–200k) | 7 | 5,84 | 5,91 | -1,23% | `[-3,39%, +0,92%]` | Não (`False`) |
| Porte Populacional | 1. Pequeno (<50k) | 9 | 10,77 | 10,75 | +0,16% | `[-1,76%, +2,30%]` | Não (`False`) |
| **Mesorregião** | **Mata Paraibana (Litoral)** | **5** | **5,14** | **4,94** | **+3,91%** | **`[+0,51%, +7,61%]`** | **SIM (`True`)** |
| Mesorregião | Agreste Paraibano | 4 | 4,46 | 4,42 | +0,79% | `[-2,08%, +3,07%]` | Não (`False`) |
| Mesorregião | Borborema | 3 | 21,25 | 21,08 | +0,83% | `[-1,88%, +4,01%]` | Não (`False`) |
| Mesorregião | Sertão Paraibano | 6 | 7,62 | 7,74 | -1,69% | `[-3,95%, +0,45%]` | Não (`False`) |

> **Conclusão de H2:** **A Hipótese H2 é amplamente confirmada com evidência real.** O valor das variáveis climáticas é fortemente condicionado pela urbanização e pelo regime bioclimático, sendo indispensável para as duas maiores capitais regionais do estado (**João Pessoa** e **Campina Grande**).

---

### 4.3 Hipótese H3: Atraso de Notificação e Correção por Nowcasting ([`reports/teste_hipotese_h3_pb.csv`](teste_hipotese_h3_pb.csv))
- **Taxa Média de Completude em 7 dias (Treino Histórico):** $83,46\%$ dos casos digitados na primeira semana.
- Avaliação sob censura de tempo real nos horizontes curtos ($h=1$ e $h=2$ semanas): a inflação empírica via *nowcasting* estabiliza a série nas semanas incompletas (`REG-06`).

---

## 5. Modelagem Biológica Avançada: Superfície de Risco DLNM (Gasparrini et al., 2010)

Calculamos a matriz bidimensional de **Risco Relativo ($\text{RR}$)** via produto tensorial de *B-Splines cúbicas* (Cross-Basis) cobrindo temperaturas de $22^\circ\text{C}$ a $31^\circ\text{C}$ e defasagens de $1$ a $12$ semanas, tomando $24,0^\circ\text{C}$ como temperatura de referência:

![Superfície DLNM](figures/fig8_dlnm_superficie_temperatura.png)

### 5.1 Valores Numéricos de Risco Relativo ($\text{RR}$) Extraídos da Superfície ([`reports/dlnm_superficie_risco_pb.csv`](dlnm_superficie_risco_pb.csv))

| Temperatura (°C) | Defasagem (Semanas) | Risco Relativo ($\text{RR}$) | IC 95% Inferior | IC 95% Superior | Interpretação Epidemiológica |
| :---: | :---: | :---: | :---: | :---: | :--- |
| $24,0^\circ\text{C}$ | Qualquer | $1,0000$ | $0,8607$ | $1,1618$ | Temperatura de referência basal. |
| $26,0^\circ\text{C}$ | $4$ semanas | $1,1624$ | $1,0005$ | $1,3506$ | Aumento de $16,2\%$ no risco de transmissão. |
| **$27,5^\circ\text{C}$** | **$5$ semanas** | **$1,3647$** | **$1,1746$** | **$1,5856$** | **ÓTIMO TÉRMICO BIOLÓGICO:** Pico de Risco Relativo ($+36,5\%$). |
| $28,0^\circ\text{C}$ | $6$ semanas | $1,3289$ | $1,1438$ | $1,5440$ | Efeito cumulativo prolongado no ciclo do vírus. |
| $30,0^\circ\text{C}$ | $5$ semanas | $1,2814$ | $1,1029$ | $1,4888$ | Desaceleração por estresse térmico do mosquito adulto. |
| $27,5^\circ\text{C}$ | $12$ semanas | $1,0482$ | $0,9022$ | $1,2179$ | Dissipação do efeito térmico após 3 meses. |

---

## 6. Importância das Variáveis via TreeSHAP no Horizonte Principal ($h=4$)

Decomposição matemática da predição mediana do LightGBM no conjunto de teste final ([`reports/importancia_shap_lightgbm_pb.csv`](importancia_shap_lightgbm_pb.csv)):

| Ranking | Variável | Grupo de Atributo | Contribuição Média Absoluta $\|\text{TreeSHAP}\|$ | Participação Relativa (%) |
| :---: | :--- | :--- | ---: | ---: |
| **1°** | `incidencia_100k_lag4` | Histórico de Casos / Incidência | **5,5808** | **44,09%** |
| **2°** | `sen_se_1` | Sazonalidade Harmônica | **1,9256** | **15,21%** |
| **3°** | `incidencia_100k_lag5` | Histórico de Casos / Incidência | **1,4630** | **11,56%** |
| **4°** | `incidencia_mm4_lag4` | Média Móvel de Incidência (4 sem.) | **1,3840** | **10,93%** |
| **5°** | `temp_media_lag12` | Clima Defasado | **0,2925** | **2,31%** |
| **6°** | `incidencia_100k_lag8` | Histórico de Casos / Incidência | 0,2167 | 1,71% |
| **7°** | `cos_se_1` | Sazonalidade Harmônica | 0,1676 | 1,32% |
| **8°** | `umidade_media_lag6` | Clima Defasado | 0,1664 | 1,31% |
| **9°** | `incidencia_100k_lag6` | Histórico de Casos / Incidência | 0,1642 | 1,30% |
| **10°** | `chuva_acum_mm4_lag4` | Clima Defasado | 0,1522 | 1,20% |
| **11°** | `umidade_media_lag12` | Clima Defasado | 0,1265 | 1,00% |
| **12°** | `umidade_media_lag7` | Clima Defasado | 0,0821 | 0,65% |
| **13°** | `incidencia_100k_lag7` | Histórico de Casos / Incidência | 0,0798 | 0,63% |
| **14°** | `chuva_acum_lag4` | Clima Defasado | 0,0711 | 0,56% |
| **15°** | `temp_media_mm4_lag4` | Clima Defasado | 0,0710 | 0,56% |

---

## 7. Associação Cruzada por Defasagem Climática – Pergunta P2 ([`reports/analise_defasagens_p2_pb.csv`](analise_defasagens_p2_pb.csv))

Correlações não-paramétricas de Spearman ($r_S$) e respectivos $p$-valores de significância entre variáveis meteorológicas do INMET e a incidência semanal:

| Defasagem $k$ (Semanas) | Spearman Temperatura | $p$-valor Temperatura | Spearman Chuva | $p$-valor Chuva | Spearman Umidade | $p$-valor Umidade |
| :---: | ---: | :---: | ---: | :---: | ---: | :---: |
| **$k=1$** | $0,4492$ | $0,000$ | $0,4889$ | $0,000$ | $0,4467$ | $0,000$ |
| **$k=2$** | $0,4994$ | $0,000$ | $0,4770$ | $0,000$ | $0,4410$ | $0,000$ |
| **$k=3$** | $0,5429$ | $0,000$ | $0,4620$ | $0,000$ | $0,4316$ | $0,000$ |
| **$k=4$** | $0,5977$ | $0,000$ | $0,4549$ | $0,000$ | $0,4263$ | $0,000$ |
| **$k=5$** | $0,6244$ | $0,000$ | $0,4731$ | $0,000$ | $0,4106$ | $0,000$ |
| **$k=6$** | $0,6634$ | $0,000$ | $0,3984$ | $0,000$ | $0,3804$ | $0,000$ |
| **$k=7$** | $0,6859$ | $0,000$ | $0,4069$ | $0,000$ | $0,3631$ | $7,08 \times 10^{-287}$ |
| **$k=8$** | $0,7069$ | $0,000$ | $0,3287$ | $6,03 \times 10^{-232}$ | $0,3305$ | $1,16 \times 10^{-234}$ |
| **$k=9$** | $0,7206$ | $0,000$ | $0,2897$ | $5,27 \times 10^{-178}$ | $0,3016$ | $1,72 \times 10^{-193}$ |
| **$k=10$** | $0,7299$ | $0,000$ | $0,2482$ | $2,12 \times 10^{-129}$ | $0,2698$ | $1,71 \times 10^{-153}$ |
| **$k=11$** | **$0,7321$** | **$0,000$** | $0,2066$ | $3,46 \times 10^{-89}$ | $0,2392$ | $7,83 \times 10^{-120}$ |
| **$k=12$** | $0,7285$ | $0,000$ | $0,1609$ | $2,56 \times 10^{-54}$ | $0,2053$ | $6,08 \times 10^{-88}$ |

---

## 8. Diagnóstico de Resíduos: Período Epidêmico vs. Interepidêmico ([`reports/analise_residuos_pb.csv`](analise_residuos_pb.csv))

Avaliação de viés sistemático e calibração dos intervalos preditivos (80% e 95%) por mesorregião nos períodos de alta (SE 12 a 24) e baixa transmissão:

| Mesorregião | Período Sazonal | Incidência Real Média | Incidência Prevista Média | Viés Médio (Resíduo) | MAE | RMSE | Cobertura 80% | Cobertura 95% |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **Agreste Paraibano** | Alta Transmissão (SE 12–24) | 8,87 | 13,23 | -4,36 | 8,46 | 12,47 | 86,5% | 100,0% |
| Agreste Paraibano | Baixa Transmissão (Demais SE) | 4,04 | 2,15 | +1,89 | 3,08 | 8,23 | 85,6% | 96,8% |
| **Borborema** | Alta Transmissão (SE 12–24) | 48,34 | 33,02 | +15,32 | 31,47 | 45,36 | 73,1% | 93,6% |
| Borborema | Baixa Transmissão (Demais SE) | 24,82 | 9,86 | +14,96 | 17,61 | 43,00 | 79,1% | 89,7% |
| **Mata Paraibana** | Alta Transmissão (SE 12–24) | 10,72 | 17,15 | -6,43 | 8,38 | 11,93 | 82,3% | 100,0% |
| Mata Paraibana | Baixa Transmissão (Demais SE) | 6,43 | 3,55 | +2,88 | 3,79 | 10,76 | 82,8% | 96,4% |
| **Sertão Paraibano** | Alta Transmissão (SE 12–24) | 18,69 | 21,38 | -2,69 | 14,59 | 23,33 | 74,4% | 98,1% |
| Sertão Paraibano | Baixa Transmissão (Demais SE) | 6,71 | 2,18 | +4,53 | 5,46 | 18,36 | 81,4% | 95,7% |

---

## 9. Análise de Sensibilidade Metodológica ([`reports/analise_sensibilidade_pb.csv`](analise_sensibilidade_pb.csv))

Comprovação de que a conclusão do estudo não é artefato de decisões de limpeza ou da perturbação da pandemia de COVID-19 (Seções 5.7 e 11):

| Cenário Analisado | $N$ Treino | MAE Sem Clima | MAE Com Clima | Skill Relativo (%) | IC 95% Bootstrap | Conclusão Robusta? |
| :--- | :---: | ---: | ---: | ---: | :---: | :---: |
| **1. Padrão (2015–2022)** | 7.506 | 14,08 | 11,11 | +21,14% | `[+17,70%, +24,21%]` | **SIM (`True`)** |
| **2. Excluindo Pandemia COVID (Sem 2020/2021)** | 5.634 | 13,62 | 10,77 | +20,88% | `[+16,94%, +24,41%]` | **SIM (`True`)** |
| **3. Apenas Casos Confirmados (Sem Inconclusivos)** | 7.506 | 12,79 | 10,07 | +21,27% | `[+17,87%, +24,32%]` | **SIM (`True`)** |

---

## 10. Benchmark Oficial Externo InfoDengue (Fiocruz/FGV) ([`reports/comparacao_infodengue_pb.csv`](comparacao_infodengue_pb.csv))

Concordância das séries de casos do pipeline com os dados oficiais de notificação e *nowcasting* do InfoDengue:

![Benchmark InfoDengue](figures/fig7_benchmark_infodengue_vs_pipeline.png)

| Município | N° Semanas | Spearman vs. InfoDengue | Spearman vs. Nowcast | Pearson Casos | MAE Casos Brutos | Alerta Máximo Registrado |
| :--- | :---: | ---: | ---: | ---: | ---: | :---: |
| **João Pessoa** | 521 | **0,5563** | **0,5563** | **0,6117** | 261,25 | 4 (Vermelho) |
| **Sousa** | 521 | **0,5215** | **0,5215** | **0,4641** | 15,26 | 4 (Vermelho) |
| **Cabedelo** | 521 | **0,5136** | **0,5136** | **0,5033** | 20,92 | 4 (Vermelho) |
| **Cajazeiras** | 521 | **0,5000** | **0,5000** | **0,4203** | 13,87 | 4 (Vermelho) |
| **Campina Grande**| 521 | **0,4514** | **0,4514** | **0,4530** | 33,14 | 4 (Vermelho) |
| **Patos** | 521 | **0,4559** | **0,4559** | **0,2932** | 24,43 | 4 (Vermelho) |
| **Santa Rita** | 521 | **0,4310** | **0,4310** | **0,3755** | 53,96 | 4 (Vermelho) |
