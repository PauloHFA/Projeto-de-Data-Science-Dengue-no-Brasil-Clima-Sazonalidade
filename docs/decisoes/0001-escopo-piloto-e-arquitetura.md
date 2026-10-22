# ADR 0001: Definição do Escopo Piloto, Horizontes e Arquitetura Anti-Vazamento

- **Data:** 2026-10-22
- **Status:** Aceito
- **Contexto:** Início da Fase 0 (Fundação) conforme a Seção 17 do documento base do projeto.

## Decisões

1. **Unidade de Análise Piloto (UF = PB – Paraíba):**
   - Adotamos o estado da Paraíba (sigla `PB`, código IBGE `25`, 223 municípios) como unidade federativa piloto.
   - *Justificativa:* A Paraíba possui dados abertos completos no SINAN/DATASUS, estações meteorológicas do INMET distribuídas em diferentes regimes climáticos (Mata Paraibana, Agreste, Borborema e Sertão — ex: João Pessoa, Campina Grande, Areia, Monteiro, Patos, São Gonçalo/Sousa) e 223 municípios, sendo ideal para investigar contrastes climáticos e sazonais (P1, P2, P3) e autocorrelação espacial via Índice de Moran (P4).

2. **Horizontes de Previsão ($h \in \{1, 2, 4, 8\}$ semanas):**
   - O pipeline suporta parametrização explícita de $h$, com foco principal de relatório em **$h = 4$ semanas** (antecedência operacional ideal para vigilância em saúde pública) e avaliação complementar em $h = 1, 2, 8$.

3. **Janela Histórica (2015–2024):**
   - Desenvolvimento e validação *rolling-origin* em 2015–2022; conjunto de teste final reservado em 2023–2024 (`REG-07`).

4. **Garantia Arquitetural Contra Vazamento Temporal (`REG-01` e `REG-14`):**
   - Toda função geradora de atributos defasados recebe obrigatoriamente o parâmetro `horizonte: int` e rejeita qualquer lag $k < \text{horizonte}$ via `ValueError` e testes automatizados em `tests/test_anti_vazamento.py`.
   - Transformadores que aprendem parâmetros (imputação, escalonamento) operam dentro de objetos ajustados exclusivamente na partição de treino de cada corte do `rolling_origin`.
