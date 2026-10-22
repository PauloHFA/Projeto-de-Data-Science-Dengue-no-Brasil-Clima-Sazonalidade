# Plano de Análise Pré-Registrado (`REG-07`)

**Data de registro:** 2026-10-22  
**Status:** Congelado antes da abertura do conjunto de teste final (2023–2024)  
**Conformidade:** `REG-01` a `REG-14`

---

## 1. Escopo e Unidade de Análise

- **Unidade geográfica piloto:** Estado da Paraíba (UF `PB`, código IBGE `25`, 223 municípios), agregando notificações por município de residência (código IBGE de 6 dígitos no SINAN iniciado por `25`, ex: João Pessoa `250750`, Campina Grande `250400`, Patos `251080`, Sousa `251620`, Cajazeiras `250370`) e por Semana Epidemiológica (SE, domingo a sábado, padrão `epiweeks` / CDC / Ministério da Saúde).
- **Variável resposta ($Y_{m, t}$):** Incidência semanal de casos prováveis de dengue por 100.000 habitantes no município $m$ e semana de início dos primeiros sintomas $t$:
  $$\text{Incidência}_{m,t} = \frac{\text{Casos Prováveis}_{m,t}}{\text{População}_{m, \text{ano}(t)}} \times 100.000$$
- **Definição de caso provável:** Todas as notificações do SINAN com data de primeiros sintomas (`DT_SIN_PRI`) válida, **exceto** casos descartados (`CLASSI_FIN == 5` na codificação pós-2014).
- **Horizontes de previsão avaliados:** $h \in \{1, 2, 4, 8\}$ semanas epidemiológicas à frente, sendo **$h = 4$ semanas** o horizonte primário de decisão.

---

## 2. Particionamento Temporal e Protocolo de Validação (`REG-01`, `REG-02`, `REG-07`)

1. **Período Total:** 2015-SE01 a 2024-SE52 (10 anos completos).
2. **Conjunto de Desenvolvimento e Validação (*Rolling-Origin*):** 2015-SE01 a 2022-SE52.
   - Treino inicial mínimo: 2015-SE01 a 2018-SE52 (4 ciclos sazonais completos).
   - Janela expansiva (*expanding window*) com avaliação passo a passo de 2019-SE01 a 2022-SE52.
   - Em cada instante de corte $t_{\text{corte}}$, o modelo que prevê $t_{\text{alvo}} = t_{\text{corte}}$ com antecedência $h$ só tem acesso a rótulos e atributos observados até $t_{\text{corte}} - h$.
3. **Conjunto de Teste Final (*Holdout* Único):** 2023-SE01 a 2024-SE52.
   - **Regra de bloqueio (`REG-07`):** Nenhuma decisão de arquitetura, seleção de hiperparâmetros, escolha de lags ou filtro de limpeza pode ser ajustada após a avaliação no teste final.
4. **Sinalização de atraso de notificação (`REG-06`):** As últimas 4 semanas anteriores ao instante de emissão da previsão sofrem truncamento por atraso de digitação/notificação; para avaliação de H3, comparamos o modelo alimentado com a contagem consolidada *versus* a contagem truncada corrigida por fator empírico de atraso (*nowcasting* simplificado).

---

## 3. Perguntas de Pesquisa e Hipóteses Falsificáveis

### Perguntas
- **P1 (Preditiva - Principal):** Variáveis climáticas defasadas reduzem o erro de previsão frente a baselines sazonais e autorregressivos?
- **P2 (Exploratória):** Quais defasagens (em semanas, de $k = 1$ a $12$) de temperatura média e precipitação acumulada apresentam maior associação cruzada com a incidência?
- **P3 (Descritiva / Clustering):** Existem grupos de municípios com perfis sazonais semelhantes (curva média normalizada por SE)?
- **P4 (Espacial):** Há autocorrelação espacial estatisticamente significativa (Índice $I$ de Moran global e LISA local) da incidência anual/epidêmica entre municípios vizinhos?
- **P5 (Associativa - Opcional):** Quais características demográficas (faixa etária, sexo) se associam à proporção de casos com sinais de alarme ou dengue grave (`CLASSI_FIN` $\in \{11, 12\}$)?

### Hipóteses Falsificáveis e Critérios de Decisão Pré-Registrados

| Hipótese | Enunciado | Métrica Primária | Critério de Decisão (Refutação / Suporte) |
| :--- | :--- | :--- | :--- |
| **H1** | Adicionar temperatura e precipitação defasadas ($k \ge h$) a um modelo autorregressivo/sazonal reduz o erro de previsão em comparação ao modelo sem clima e ao melhor baseline. | $\text{MAE}$ (em incidência por 100 mil hab.) e $\text{Skill Relativo} = 1 - \frac{\text{MAE}_{\text{clima}}}{\text{MAE}_{\text{sem clima}}}$ | **Suportada** se, em pelo menos um horizonte $h \in \{1, 2, 4, 8\}$ (priorizando $h=4$), o $\text{Skill Relativo} > 0$ e o limite inferior do Intervalo de Confiança de 95% (via *block bootstrap* com blocos de 4 semanas, $B=1000$) for estritamente maior que $0$. Caso contrário, **refutada** (reportar ausência de ganho conforme `REG-13`). |
| **H2** | O ganho preditivo do modelo com clima varia segundo o porte populacional do município (pequeno $< 50\text{k}$, médio $50\text{k}\text{–}200\text{k}$, grande $> 200\text{k}$ hab.) e macrorregião de saúde. | Diferença de $\text{Skill Relativo}$ entre estratos populacionais / regionais | **Suportada** se a diferença de *Skill* entre municípios de grande porte e pequeno porte tiver IC 95% (bootstrap) que não contenha zero. |
| **H3** | Tratar explicitamente o atraso de notificação nas semanas recentes ($t - h$) reduz o erro de previsão em curto prazo ($h \in \{1, 2\}$) quando os dados são avaliados sob censura de digitação em tempo real. | $\text{MAE}$ sob simulação de censura em tempo real (*vintage data*) | **Suportada** se o modelo com correção de truncamento apresentar $\text{MAE}$ significativamente menor (IC 95% bootstrap $> 0$) que o modelo ingênuo sob dados censurados para $h \in \{1, 2\}$. |

---

## 4. Hierarquia de Modelos (`REG-03`, `REG-04`)

1. **Baseline 1 – Seasonal Naive:** Previsão para $(m, t)$ igual à incidência observada na mesma semana epidemiológica do ano anterior $(m, t - 52)$ (ou última disponível compatível com $h$). Intervalos empíricos baseados nos quantis históricos dos resíduos sazonais.
2. **Baseline 2 – Persistência Defasada:** Previsão para $(m, t)$ igual ao último valor conhecido no momento da emissão: $\hat{y}_{m, t} = y_{m, t - h}$.
3. **Modelo Estatístico 1 – GLM Contagem (Poisson / Binomial Negativa via `statsmodels`):** Com *offset* de $\log(\text{população})$, harmônicos sazonais ($\sin, \cos$ da SE) e lags de incidência ($k \ge h$), comparado na versão **Sem Clima** vs. **Com Clima**.
4. **Modelo Estatístico 2 – Referência de Séries Temporais (SARIMAX / ETS):** Ajustado na série agregada estadual/municipal com e sem covariáveis climáticas exógenas defasadas ($k \ge h$).
5. **Modelo de Machine Learning – LightGBM com Perda Quantílica (`alpha` $\in \{0.025, 0.10, 0.50, 0.90, 0.975\}$):**
   - Fornece previsão pontual (mediana $\alpha = 0.50$) e intervalos preditivos de **80%** ($[\hat{q}_{0.10}, \hat{q}_{0.90}]$) e **95%** ($[\hat{q}_{0.025}, \hat{q}_{0.975}]$).
   - Versão **Apenas Histórico + Sazonalidade** vs. Versão **Histórico + Sazonalidade + Clima Defasado**.

---

## 5. Métricas de Avaliação (Seção 10)

- **Erro Pontual:** $\text{MAE}$ e $\text{RMSE}$ em unidades de incidência por 100 mil habitantes (`REG-05`).
- **Ganho Relativo:** $\text{Skill} = 1 - \text{MAE}_{\text{modelo}} / \text{MAE}_{\text{baseline}}$.
- **Qualidade Probabilística / Intervalar (`REG-04`):**
  - *Weighted Interval Score* ($\text{WIS}$) combinando os intervalos de 80% e 95% mais a mediana, e *Pinball Loss* por quantil.
  - Cobertura empírica nominal de 80% e 95%.
- **Utilidade em Saúde Pública:** Erro na magnitude do pico anual ($\text{incidência}_{\max}$) e erro em semanas na localização da semana de pico ($\Delta \text{SE}_{\text{pico}}$).
- **Proibição explícita:** $\text{MAPE}$ não será utilizado devido à inflação por denominadores próximos de zero em semanas interepidêmicas.
