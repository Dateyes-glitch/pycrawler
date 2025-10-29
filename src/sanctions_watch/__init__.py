"""SanctionsWatch: A comprehensive sanctions data crawler framework."""

__version__ = "0.1.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

from .core.base import BaseCrawler
from .core.models import SanctionEntity, EntityType
from .crawlers.eu_sanctions import EUSanctionsCrawler
from .crawlers.ofac import OFACCrawler
from .crawlers.un_sanctions import UNSanctionsCrawler
from .crawlers.uk_treasury import UKTreasuryCrawler

__all__ = [
    "BaseCrawler",
    "SanctionEntity", 
    "EntityType",
    "EUSanctionsCrawler",
    "OFACCrawler", 
    "UNSanctionsCrawler",
    "UKTreasuryCrawler",
]
