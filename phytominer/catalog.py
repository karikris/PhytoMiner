"""Organism IDs and canonical names from metadata, without genome scans."""

import xml.etree.ElementTree as ET
from .models import ValidationError, ServiceError


class OrganismCatalog:
    def __init__(self, records):
        self.records = records

    @classmethod
    def from_xml(cls, text):
        try:
            root = ET.fromstring(text)
        except ET.ParseError as exc:
            raise ServiceError("Invalid organism configuration XML") from exc
        groups = {}
        for node in root.iter("FilterDescription"):
            if node.get("internalName") in ("organism_id", "ortholog_organism_name"):
                groups[node.get("internalName")] = list(node.iter("Option"))
        names = {}
        for node in groups.get("ortholog_organism_name", []):
            names.setdefault(node.get("displayName"), set()).add(node.get("value"))
        records = []
        for node in groups.get("organism_id", []):
            candidates = names.get(node.get("displayName"), set())
            if len(candidates) != 1 or not node.get("value") or None in candidates:
                raise ServiceError("Missing or ambiguous organism catalog mapping")
            records.append(
                {
                    "organism_id": node.get("value"),
                    "organism_name": next(iter(candidates)),
                    "display_name": node.get("displayName"),
                }
            )
        if not records:
            raise ServiceError("Organism catalog is empty")
        return cls(records)

    def resolve(self, value):
        ids = {r["organism_id"] for r in self.records if value in r.values()}
        if len(ids) != 1:
            raise ValidationError(f"Unknown or ambiguous organism: {value}")
        return ids.pop()

    def names(self, ids):
        return tuple(
            sorted(r["organism_name"] for r in self.records if r["organism_id"] in ids)
        )
