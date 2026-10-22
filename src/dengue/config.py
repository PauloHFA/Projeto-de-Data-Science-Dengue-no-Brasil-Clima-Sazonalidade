"""Configurações globais, constantes epidemiológicas e parâmetros da UF piloto (Paraíba - PB)."""

from dataclasses import dataclass
from pathlib import Path

# Diretórios do projeto
ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
REPORTS_DIR = ROOT_DIR / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"

# Semente global para reprodutibilidade estrita (REG-08)
SEED: int = 42

# Escopo geográfico piloto: Paraíba (PB)
UF_PILOTO: str = "PB"
CODIGO_UF_IBGE: str = "25"

# Janela temporal do estudo (REG-07)
ANO_INICIO: int = 2015
ANO_FIM: int = 2024
ANOS_ESTUDO: tuple[int, ...] = tuple(range(ANO_INICIO, ANO_FIM + 1))

# Corte temporal para validação rolling-origin e teste final único (REG-02, REG-07)
DATA_INICIO_VALIDACAO: str = "2019-01-06"  # Início da janela rolling-origin de validação
DATA_INICIO_TESTE_FINAL: str = "2023-01-01"  # Reservado para avaliação final única (2023-2024)

# Horizontes de previsão em semanas epidemiológicas (Seção 1 e 9.2)
HORIZONTES: tuple[int, ...] = (1, 2, 4, 8)
HORIZONTE_PRINCIPAL: int = 4
MAX_LAG_CLIMA: int = 12
MAX_LAG_CASOS: int = 8

# Código SINAN de caso descartado (Seção 5.2 e 9.1)
CODIGO_DESCARTADO_SINAN: str = "5"


@dataclass(frozen=True)
class EstacaoINMET:
    """Metadados de estação meteorológica do INMET na Paraíba (PB)."""

    codigo: str
    nome: str
    municipio_ibge6: str
    lat: float
    lon: float
    altitude: float
    mesorregiao: str


# Estações de referência do INMET na Paraíba (cobrindo as 4 mesorregiões)
ESTACOES_INMET_PB: tuple[EstacaoINMET, ...] = (
    EstacaoINMET("A320", "JOAO PESSOA", "250750", -7.1653, -34.8156, 34.0, "Mata Paraibana"),
    EstacaoINMET("A310", "AREIA", "250110", -6.9753, -35.7181, 575.0, "Agreste Paraibano"),
    EstacaoINMET("A313", "CAMPINA GRANDE", "250400", -7.2256, -35.9047, 546.0, "Agreste Paraibano"),
    EstacaoINMET("A348", "CABACEIRAS", "250310", -7.4919, -36.2869, 390.0, "Borborema"),
    EstacaoINMET("A331", "MONTEIRO", "250970", -7.8936, -37.1211, 604.0, "Borborema"),
    EstacaoINMET("A321", "PATOS", "251080", -7.0794, -37.2728, 264.0, "Sertao Paraibano"),
    EstacaoINMET("A333", "SAO GONCALO (SOUSA)", "251620", -6.8358, -38.3114, 235.0, "Sertao Paraibano"),
    EstacaoINMET("82795", "CAJAZEIRAS", "250370", -6.8897, -38.5453, 298.0, "Sertao Paraibano"),
)

