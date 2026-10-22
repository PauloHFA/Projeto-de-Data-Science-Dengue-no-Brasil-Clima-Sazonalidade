# Dicionário de Dados Oficial e Mapeamento de Variáveis

Conforme exigido na **Seção 3** e na regra **`REG-09`**, este documento registra os códigos, tipos e domínios das variáveis utilizadas nas três fontes primárias do projeto.

---

## 1. SINAN – Dengue (DATASUS / PySUS)

Fonte: Sistema de Informação de Agravos de Notificação (`SINAN-DENGUE`).  
Referência oficial: *Dicionário de Dados SINAN Online – Dengue (versão pós-2014)*.

| Coluna Original | Coluna Padronizada | Tipo | Domínio / Regras de Validação (`REG-09`) | Uso no Pipeline |
| :--- | :--- | :--- | :--- | :--- |
| `DT_NOTIFIC` | `dt_notificacao` | `datetime64[ns]` | Data válida entre `2015-01-01` e `2025-12-31`; deve ser $\ge$ `dt_sintomas` | Cálculo do atraso de notificação (`REG-06`) |
| `DT_SIN_PRI` | `dt_sintomas` | `datetime64[ns]` | Data válida entre `2015-01-01` e `2024-12-31` (não nula após limpeza) | **Data de referência epidemiológica** para agregação semanal (Seção 5.2) |
| `ID_MUNICIP` | `municipio` | `str` (6 dígitos) | Código IBGE de 6 dígitos numéricos (`^[0-9]{6}$`); na Paraíba (PB) inicia com `25` | Chave espacial de agregação municipal |
| `SG_UF_NOT` / `SG_UF` | `uf` | `str` | Código IBGE da UF (`25` para PB) ou sigla (`PB`) | Filtro de unidade federativa |
| `CLASSI_FIN` | `classificacao_final` | `str` | `5` = Descartado; `10` = Dengue; `11` = Dengue com sinais de alarme; `12` = Dengue grave; `8` = Inconclusivo; `1` = Dengue clássico (legado pré-2014); vazio/nulo = Em investigação | **Filtro de caso provável:** exclui `CLASSI_FIN == "5"` |
| `CRITERIO` | `criterio_confirmacao` | `str` | `1` = Laboratório; `2` = Clínico-epidemiológico; `3` = Em investigação | Análise exploratória de qualidade / testagem |
| `NU_IDADE_N` | `idade_anos` | `float64` | Codificação SINAN: 1º dígito = unidade (`1`=hora, `2`=dia, `3`=mês, `4`=ano), dígitos 2–4 = valor. Convertido para anos em $[0, 120]$ | Limpeza de idades implausíveis e análise opcional P5 |
| `CS_SEXO` | `sexo` | `str` | `M` = Masculino, `F` = Feminino, `I` = Ignorado | Análise descritiva e P5 |

---

## 2. INMET – Séries Meteorológicas Históricas

Fonte: Instituto Nacional de Meteorologia (Estações Automáticas e Convencionais).  
Granularidade original: Horária ou diária, agregada para **Semana Epidemiológica (SE)** por estação e mapeada para o município mais próximo (distância geodésica Haversine até o centroide municipal).

| Variável Agregada (SE) | Nome da Coluna | Unidade | Agregação Semanal | Domínio Plausível (`REG-09`) |
| :--- | :--- | :--- | :--- | :--- |
| Temperatura Média Semanal | `temp_media` | °C | Média aritmética diária/semanal | $[-5.0, 45.0]$ °C |
| Temperatura Mínima Semanal | `temp_min` | °C | Mínimo semanal das mínimas diárias | $[-10.0, 40.0]$ °C |
| Temperatura Máxima Semanal | `temp_max` | °C | Máximo semanal das máximas diárias | $[0.0, 50.0]$ °C |
| Precipitação Acumulada | `chuva_acum` | mm | Soma acumulada na SE | $[0.0, 1000.0]$ mm |
| Umidade Relativa Média | `umidade_media` | % | Média aritmética na SE | $[5.0, 100.0]$ % |

---

## 3. IBGE – População e Malha Municipal

Fonte: Estimativas Populacionais Municipais (SIDRA/IBGE) e Malha Municipal Digital.

| Coluna | Tipo | Domínio / Observação |
| :--- | :--- | :--- |
| `municipio` | `str` (6 dígitos) | Código IBGE de 6 dígitos (sem dígito verificador, compatível com `ID_MUNICIP` do SINAN) |
| `municipio_ibge7` | `str` (7 dígitos) | Código IBGE completo de 7 dígitos (usado para cruzamento com malha `geopandas`) |
| `nome_municipio` | `str` | Nome oficial do município |
| `ano` | `int64` | Ano de referência ($2015 \le \text{ano} \le 2024$) |
| `populacao` | `int64` | População residente estimada ($> 0$); denominador para cálculo de incidência por 100 mil hab. (`REG-05`) |
| `lat`, `lon` | `float64` | Coordenadas do centroide municipal em graus decimais (SIRGAS 2000 / WGS84) |
