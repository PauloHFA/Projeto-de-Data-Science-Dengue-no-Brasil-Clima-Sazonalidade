.PHONY: help setup data infodengue features train report test lint all

PYTHON ?= python

help:
	@echo "Comandos disponiveis:"
	@echo "  make setup      - Instala o pacote em modo editavel e dependencias de desenvolvimento"
	@echo "  make data       - Executa a ingestao, validacao de contratos e limpeza (Fase 1)"
	@echo "  make infodengue - Baixa e compara com o benchmark oficial do InfoDengue (Fiocruz/FGV)"
	@echo "  make features   - Gera atributos defasados e sazonais sem vazamento temporal (Fase 3/4)"
	@echo "  make train      - Executa validacao rolling-origin, baselines e modelos (Fase 3/4)"
	@echo "  make report     - Compila tabelas de resultados, graficos e relatorio final (Fase 5/6)"
	@echo "  make test       - Executa suite de testes automatizados (contratos, anti-vazamento, metricas)"
	@echo "  make lint       - Verifica formatacao e qualidade de codigo com ruff"
	@echo "  make all        - Roda o pipeline completo de ponta a ponta (REG-08)"

setup:
	$(PYTHON) -m pip install -e ".[dev]"

data:
	$(PYTHON) -m dengue.cli data

infodengue:
	$(PYTHON) -m dengue.cli infodengue

features:
	$(PYTHON) -m dengue.cli features

train:
	$(PYTHON) -m dengue.cli train

report:
	$(PYTHON) -m dengue.cli report

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check src tests

all: test data features train report
