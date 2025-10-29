"""Simple deduplication for SanctionsWatch mock data."""
from typing import Iterable, List, Dict
from ..core.models import SanctionEntity


def deduplicate_entities(entities: Iterable[SanctionEntity]) -> List[SanctionEntity]:
    """Deduplicate by (normalized name lower, source)."""
    seen: Dict[str, SanctionEntity] = {}
    result: List[SanctionEntity] = []
    for e in entities:
        key = f"{e.source}:{e.name.lower()}"
        if key not in seen:
            seen[key] = e
            result.append(e)
    return result
