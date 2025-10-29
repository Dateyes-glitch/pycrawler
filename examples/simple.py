"""
Basic usage example for SanctionsWatch.

This script shows the simplest way to get started with the framework.
"""

import asyncio
from sanctions_watch import EUSanctionsCrawler


async def simple_example():
    """Simple example of crawling EU sanctions."""
    print("Starting simple crawl example...")
    
    # Create and use crawler
    async with EUSanctionsCrawler() as crawler:
        result = await crawler.crawl()
        
        print(f"Found {result.total_entities} entities from {result.source}")
        
        # Print first few entities
        for i, entity in enumerate(result.entities[:5]):
            print(f"{i+1}. {entity.name} - {entity.entity_type}")


if __name__ == "__main__":
    asyncio.run(simple_example())
