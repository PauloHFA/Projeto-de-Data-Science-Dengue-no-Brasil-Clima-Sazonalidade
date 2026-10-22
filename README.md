# Projeto de Data Science: Dengue no Brasil – Clima, Sazonalidade e Previsão de Casos

Repositório de análise científica e reprodutível de dados abertos de saúde (SINAN/DATASUS), clima (INMET) e demografia (IBGE), construído sob estritas regras de rigor científico (`REG-01` a `REG-14`).

> **Aviso Ético e Legal (Seção 12):** Este projeto tem finalidade exclusivamente **educacional e analítica**. Os dados utilizados são públicos e anonimizados. Os modelos e resultados aqui gerados **não substituem a vigilância epidemiológica oficial** e não devem orientar decisões clínicas.

---

## 1. Pergunta Central e Escopo Piloto

**Pergunta principal (P1):** Variáveis climáticas defasadas (temperatura, precipitação, umidade) melhoram a previsão de curto prazo ($h \in \{1, 2, 4, 8\}$ semanas epidemiológicas, com foco principal em $h = 4$) da incidência de dengue em comparação com modelos que usam apenas o histórico de casos e sazonalidade?

- **Unidade de análise piloto:** Estado da Paraíba (UF `PB`, código IBGE `25`, 223 municípios), permitindo análises preditivas municipais/estaduais (P1, P2), agrupamento sazonal entre mesorregiões do Litoral ao Sertão (P3) e autocorrelação espacial via Índice de Moran (P4).
- **Janela temporal:** 2015 a 2024 (10 anos).
  - **Desenvolvimento e Validação (*Rolling-Origin*):** 2015 a 2022.
  - **Conjunto de Teste Final (travado – `REG-07`):** 2023 a 2024 (aberto uma única vez após o congelamento dos modelos).

---

## 2. Estrutura do Repositório

```text
dengue-clima/
├── README.md
├── pyproject.toml              # Dependências e configuração de testes/lint
├── Makefile                    # make data | features | train | report | test | all
├── docs/
│   ├── plano_de_analise.md     # Pré-registro de hipóteses, métricas e janelas (REG-07)
│   ├── dicionario_de_dados.md  # Mapeamento oficial SINAN, INMET e IBGE
│   └── decisoes/               # Registros de decisão arquitetural (ADRs)
├── data/
│   ├── raw/                    # Dados brutos imutáveis em Parquet + manifesto SHA-256 (REG-08)
│   ├── interim/                # Dados limpos + funil de exclusão auditável (REG-12)
│   └── processed/              # Painéis semanais município x SE e matrizes de atributos
├── src/dengue/
│   ├── config.py               # Seeds fixas, constantes e configuração do estudo
│   ├── cli.py                  # Orquestrador de linha de comando (reprodução em 1 comando)
│   ├── ingestao/               # Coleta automatizada SINAN, INMET, IBGE e hash SHA-256
│   ├── qualidade/              # Contratos Pandera (REG-09) e funil de limpeza (REG-12)
│   ├── features/               # Engenharia de lags (k >= h), sazonalidade e escalonamento (REG-01, REG-14)
│   ├── modelos/                # Baselines (Seasonal Naive, Persistência), GLM (Poisson/NegBin) e LightGBM Quantílico
│   ├── validacao/              # Split rolling-origin (REG-02), MAE, RMSE, Skill, WIS, cobertura e bootstrap em blocos
│   └── visualizacao/           # Curvas epidêmicas, defasagem-resposta e diagnóstico de resíduos
├── notebooks/                  # Exploração e narrativa (toda lógica reside em src/dengue - REG-10)
├── tests/                      # Testes unitários, contratos de dados e anti-vazamento (pytest)
└── reports/                    # Relatório em Quarto (.qmd), figuras e tabelas consolidadas
```

---

## 3. Como Reproduzir (`REG-08`)

### Instalação
```bash
pip install -e ".[dev]"
```

### Executar a Suíte de Testes (Fase 0)
```bash
pytest
# ou: make test
```

### Executar o Pipeline Completo em 1 Comando
```bash
python -m dengue.cli all
# ou: make all
```
