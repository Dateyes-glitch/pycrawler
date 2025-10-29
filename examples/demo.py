#!/usr/bin/env python3
"""
Example usage of the SanctionsWatch framework.

This script demonstrates how to use the library to crawl sanctions data
and perform basic operations.
"""

import asyncio
import json
import sys
from pathlib import Path

from sanctions_watch import EUSanctionsCrawler, OFACCrawler, UKTreasuryCrawler
from sanctions_watch.core.models import EntityType


async def demo_single_crawler():
    """Demonstrate crawling from a single source."""
    print("🔍 Demo: Single Source Crawl (EU Sanctions)")
    print("=" * 50)
    
    try:
        # Initialize EU sanctions crawler
        async with EUSanctionsCrawler() as crawler:
            print(f"Crawling from: {crawler.config.base_url}")
            
            # Perform crawl
            result = await crawler.crawl()
            
            print(f"✅ Crawl completed!")
            print(f"   Source: {result.source}")
            print(f"   Total entities: {result.total_entities}")
            print(f"   Errors: {result.error_count}")
            print(f"   Duration: {result.metadata.get('crawl_duration_seconds', 0):.2f}s")
            
            # Show some sample entities
            if result.entities:
                print("\n📋 Sample entities:")
                for i, entity in enumerate(result.entities[:3]):
                    print(f"   {i+1}. {entity.name} ({entity.entity_type})")
            
            return result
            
    except Exception as e:
        print(f"❌ Error during crawl: {e}")
        return None


async def demo_multiple_crawlers():
    """Demonstrate crawling from multiple sources."""
    print("\n🔍 Demo: Multiple Source Crawl")
    print("=" * 50)
    
    crawlers = [
        ("EU Sanctions", EUSanctionsCrawler()),
        ("UK Treasury", UKTreasuryCrawler()),
        # Note: OFAC might be slower, so commenting out for demo
        # ("OFAC", OFACCrawler()),
    ]
    
    results = {}
    
    for name, crawler_instance in crawlers:
        try:
            print(f"\n📡 Crawling {name}...")
            async with crawler_instance as crawler:
                result = await crawler.crawl()
                results[name] = result
                print(f"   ✅ {name}: {result.total_entities} entities")
                
        except Exception as e:
            print(f"   ❌ {name} failed: {e}")
            
    return results


def analyze_results(results):
    """Analyze and display results statistics."""
    print("\n📊 Analysis Summary")
    print("=" * 50)
    
    total_entities = 0
    entity_types = {}
    sources = []
    
    for source_name, result in results.items():
        sources.append(source_name)
        total_entities += result.total_entities
        
        # Count entity types
        for entity in result.entities:
            entity_type = entity.entity_type
            entity_types[entity_type] = entity_types.get(entity_type, 0) + 1
    
    print(f"📈 Total entities across all sources: {total_entities}")
    print(f"🌐 Sources crawled: {', '.join(sources)}")
    
    print("\n📋 Entity types breakdown:")
    for entity_type, count in sorted(entity_types.items()):
        print(f"   {entity_type.value}: {count}")


def save_sample_data(results, output_file="sample_data.json"):
    """Save a sample of the crawled data."""
    print(f"\n💾 Saving sample data to {output_file}")
    
    sample_data = {
        "timestamp": "2025-10-28T19:37:00Z",
        "total_sources": len(results),
        "sample_entities": []
    }
    
    # Take a few entities from each source
    for source_name, result in results.items():
        for entity in result.entities[:2]:  # Take first 2 from each source
            sample_data["sample_entities"].append({
                "source": source_name,
                "id": entity.id,
                "name": entity.name,
                "type": entity.entity_type,
                "nationality": entity.nationality,
                "sanctions_programs": [p.name for p in entity.sanctions_programs]
            })
    
    with open(output_file, 'w') as f:
        json.dump(sample_data, f, indent=2, default=str)
    
    print(f"   ✅ Saved {len(sample_data['sample_entities'])} sample entities")


async def main():
    """Main demo function."""
    print("🚀 SanctionsWatch Demo")
    print("=" * 50)
    print("This demo shows how to use the SanctionsWatch framework")
    print("to crawl sanctions data from multiple international sources.")
    print()
    
    # Single crawler demo
    single_result = await demo_single_crawler()
    
    if single_result and single_result.total_entities > 0:
        # Multiple crawlers demo
        all_results = await demo_multiple_crawlers()
        
        if all_results:
            # Add single result to all results
            all_results["EU Sanctions (detailed)"] = single_result
            
            # Analyze results
            analyze_results(all_results)
            
            # Save sample data
            save_sample_data(all_results)
    
    print("\n🎯 Demo completed!")
    print("\nNext steps:")
    print("1. Check the generated sample_data.json file")
    print("2. Try running: sanctions-watch crawl --help")
    print("3. Explore the source code in src/sanctions_watch/")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  Demo cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        sys.exit(1)
