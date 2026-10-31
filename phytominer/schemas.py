"""Versioned dataset kinds and scientific table grains."""

from .evidence import EVENT_COLUMNS
from .models import TABLES

TABLES_V2 = {
    name: columns
    for name, columns in TABLES.items()
    if name not in ("retrieval_events", "relationship_evidence")
}
TABLES.update(
    {
        "unmatched_genes": TABLES["genes"],
        "unresolved_relationships": TABLES["relationships"],
    }
)
REQUIRED = {
    "collection": set(),
    "homologs": {
        "seeds",
        "genes",
        "organisms",
        "relationships",
        "provenance",
        "features",
        "unmatched_genes",
        "unresolved_relationships",
        "retrieval_events",
        "relationship_evidence",
    },
    "features": {
        "genes",
        "features",
        "organisms",
        "unmatched_genes",
        "retrieval_events",
    },
    "annotated": {"genes", "annotations", "annotated_genes"},
}
NULLABLE = {
    "label",
    "target_organism_id",
    "pac_gene_id",
    "transcript_name",
    "pac_transcript_id",
}
assert EVENT_COLUMNS
KEYS = {name: columns for name, columns in TABLES.items()}
KEYS["genes"] = ("organism_id", "gene_name")
KEYS["organisms"] = ("organism_id",)
KEYS["annotations"] = KEYS["genes"]
KEYS["annotated_genes"] = KEYS["genes"]
