"""Simple normalization utilities for SanctionsWatch mock data."""
from typing import Iterable, List
from ..core.models import SanctionEntity


def normalize_entities(entities: Iterable[SanctionEntity]) -> List[SanctionEntity]:
    """Normalize basic fields (trim names, unify casing for entity_type)."""
    normalized: List[SanctionEntity] = []
    for e in entities:
        e.name = e.name.strip()
        e.alternative_names = [n.strip() for n in e.alternative_names]
        # Ensure entity_type is lowercase string in additional_data mirror
        e.additional_data.setdefault("normalized", {})["entity_type"] = str(e.entity_type).lower()
        normalized.append(e)
    return normalized
