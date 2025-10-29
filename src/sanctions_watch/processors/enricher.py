"""Simple enrichment for SanctionsWatch mock data."""
from typing import Iterable, List
from ..core.models import SanctionEntity, SanctionProgram


def enrich_entities(entities: Iterable[SanctionEntity]) -> List[SanctionEntity]:
    """Add a mock program entry if missing and compute a naive quality score."""
    enriched: List[SanctionEntity] = []
    for e in entities:
        if not e.sanctions_programs:
            e.add_sanction_program(name="Unknown Program", authority=e.source.upper(), program_type="general")
        # Naive data quality score: presence of address and identifiers
        score = 0.0
        score += 0.4 if e.addresses else 0.0
        score += 0.4 if e.identifiers else 0.0
        score += 0.2 if e.alternative_names else 0.0
        e.data_quality_score = round(min(score, 1.0), 2)
        enriched.append(e)
    return enriched
