import os
from pathlib import Path

# --- Project Root ---
PROJECT_ROOT = Path(__file__).parent.parent

# --- External Services ---
PHYTOZOME_SERVICE_URL = os.getenv(
    "PHYTOZOME_SERVICE_URL",
    "https://phytozome-next.jgi.doe.gov/phytomine/service"
)

# --- Runtime Parameters ---
DEFAULT_SLEEP = float(os.getenv("PHYTO_SLEEP_SECONDS", "1.5"))
DEFAULT_CHUNK = int(os.getenv("PHYTO_CHUNK_SIZE", "16"))
DEFAULT_WORKERS = int(os.getenv("PHYTO_MAX_WORKERS", "4"))

# --- File and Directory Paths ---
DATA_DIR = PROJECT_ROOT / "data"
CHECKPOINTS_DIR = PROJECT_ROOT / "checkpoints"
TSV_DIR = Path(os.getenv("PHYTO_TSV_DIR", str(DATA_DIR / "tsv")))
HEATMAP_DIR = Path(os.getenv("PHYTO_HEATMAP_DIR", str(DATA_DIR / "heatmaps")))
HOMOLOGS_OUTPUT_FILE = Path(os.getenv("PHYTO_HOMOLOGS", str(DATA_DIR / "step1output.csv")))
HOMOLOGS_CHECKPOINT_DIR = CHECKPOINTS_DIR / "homologs"
STEP2_OUTPUT_FILE = Path(os.getenv("PHYTO_STEP2", str(DATA_DIR / "step2output.csv")))
GENE_CHECKPOINT_DIR = CHECKPOINTS_DIR / "genes"
GENE_OUTPUT_FILE = Path(os.getenv("PHYTO_GENES", str(DATA_DIR / "step3output.csv")))

# --- Column Name Constants ---
JOIN_COL = ['primaryIdentifier', 'organism.shortName']
HOMOLOG_GENE_ID = 'primaryIdentifier'
TSV_GENE_ID = 'Gene_ID_from_TSV'

# --- api.py views and column order ---
HOMOLOGS_COLUMN_ORDER = [
    "source.organism", "source.gene", "relationship", "subunit1",
    "primaryIdentifier", "secondaryIdentifier", "organism.commonName",
    "organism.shortName", "organism.proteomeId", "gene.genomicOrder",
    "gene.length", "sequence.length", "sequence.residues"]
HOMOLOGS_QUERY_VIEW = [
    "gene.primaryIdentifier", "relationship", "ortholog_organism.commonName",
    "ortholog_organism.shortName", "ortholog_organism.proteomeId",
    "ortholog_gene.primaryIdentifier", "ortholog_gene.length",
    "ortholog_gene.secondaryIdentifier", "ortholog_gene.genomicOrder",
    "ortholog_gene.sequence.length", "ortholog_gene.sequence.residues"]
GENES_QUERY_VIEW = [
    "length", "primaryIdentifier", "secondaryIdentifier", "organism.commonName",
    "organism.proteomeId", "organism.shortName", "organism.species",
    "coexpressions.highRange", "coexpressions.lowRange", "coexpressions.JSON",
    "proteins.length", "proteins.primaryIdentifier", "rnaSeqExpressions.abundance",
    "rnaSeqExpressions.confhi", "rnaSeqExpressions.conflo", "rnaSeqExpressions.count",
    "rnaSeqExpressions.countdispersionvar", "rnaSeqExpressions.countuncertaintyvar",
    "rnaSeqExpressions.countvariance", "rnaSeqExpressions.libraryExpressionLevel",
    "rnaSeqExpressions.experiment.name", "rnaSeqExpressions.experiment.experimentGroup",
    "sequence.length", "sequence.residues", "CDSs.gene.CDSs.name",
    "CDSs.primaryIdentifier", "CDSs.organism.name"]
