"""Versioned dataset kinds and scientific table grains."""

from .models import TABLES, TABLES_V2 as TABLES_V2

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
        "seed_outcomes",
    },
    "features": {
        "genes",
        "features",
        "organisms",
        "unmatched_genes",
        "retrieval_events",
        "seed_outcomes",
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
KEYS = {name: columns for name, columns in TABLES.items()}
KEYS["genes"] = ("organism_id", "gene_name")
KEYS["organisms"] = ("organism_id",)
KEYS["annotations"] = KEYS["genes"]
KEYS["annotated_genes"] = KEYS["genes"]

KEYS["seed_outcomes"] = ("organism_id", "gene_name")
KEYS["retrieval_events"] = ("event_id",)
