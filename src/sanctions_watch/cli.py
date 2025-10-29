"""Command-line interface for SanctionsWatch."""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import click
import structlog
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.panel import Panel

from .core.models import CrawlResult, CrawlerConfig
from .crawlers import EUSanctionsCrawler, OFACCrawler, UNSanctionsCrawler, UKTreasuryCrawler


# Configure logging
logger = structlog.get_logger(__name__)
console = Console()


# Crawler registry
CRAWLERS = {
    'eu-sanctions': EUSanctionsCrawler,
    'ofac': OFACCrawler,
    'un-sanctions': UNSanctionsCrawler,
    'uk-treasury': UKTreasuryCrawler,
}


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option('--quiet', '-q', is_flag=True, help='Suppress all output except errors')
def cli(verbose: bool, quiet: bool):
    """SanctionsWatch: Comprehensive sanctions data crawler framework."""
    # Configure logging level
    if quiet:
        level = 'ERROR'
    elif verbose:
        level = 'DEBUG'
    else:
        level = 'INFO'
        
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


@cli.command()
@click.option('--source', '-s', multiple=True, 
              type=click.Choice(list(CRAWLERS.keys()) + ['all']),
              default=['all'], help='Source(s) to crawl')
@click.option('--output', '-o', type=click.Path(), help='Output file path')
@click.option('--format', 'output_format', type=click.Choice(['json', 'csv']), 
              default='json', help='Output format')
@click.option('--rate-limit', type=float, default=2.0, 
              help='Rate limit in seconds between requests')
@click.option('--timeout', type=int, default=60, 
              help='Request timeout in seconds')
def crawl(source: List[str], output: Optional[str], output_format: str, 
          rate_limit: float, timeout: int):
    """Crawl sanctions data from specified sources."""
    
    # Determine which sources to crawl
    if 'all' in source:
        sources_to_crawl = list(CRAWLERS.keys())
    else:
        sources_to_crawl = list(source)
    
    console.print(Panel(
        f"Starting crawl for sources: {', '.join(sources_to_crawl)}",
        title="SanctionsWatch Crawler",
        border_style="blue"
    ))
    
    # Run the crawl
    results = asyncio.run(_run_crawl(sources_to_crawl, rate_limit, timeout))
    
    # Display results
    _display_results(results)
    
    # Save output if specified
    if output:
        _save_results(results, output, output_format)
        console.print(f"✅ Results saved to {output}")


async def _run_crawl(sources: List[str], rate_limit: float, timeout: int) -> Dict[str, CrawlResult]:
    """Run crawl for specified sources."""
    results = {}
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:
        
        main_task = progress.add_task("Overall progress", total=len(sources))
        
        for source_name in sources:
            crawler_class = CRAWLERS[source_name]
            
            # Create custom config with user settings
            config = crawler_class.DEFAULT_CONFIG.copy()
            config.rate_limit_seconds = rate_limit
            config.timeout_seconds = timeout
            
            crawler_task = progress.add_task(f"Crawling {source_name}", total=None)
            
            try:
                async with crawler_class(config) as crawler:
                    result = await crawler.crawl()
                    results[source_name] = result
                    
                progress.update(crawler_task, completed=True, description=f"✅ {source_name}")
                
            except Exception as e:
                logger.error("Crawl failed", source=source_name, error=str(e))
                progress.update(crawler_task, completed=True, description=f"❌ {source_name}")
                
            progress.advance(main_task)
    
    return results


def _display_results(results: Dict[str, CrawlResult]) -> None:
    """Display crawl results in a formatted table."""
    table = Table(title="Crawl Results Summary")
    
    table.add_column("Source", style="cyan", no_wrap=True)
    table.add_column("Status", style="green")
    table.add_column("Entities", justify="right", style="magenta")
    table.add_column("Errors", justify="right", style="red")
    table.add_column("Duration", justify="right", style="yellow")
    
    total_entities = 0
    total_errors = 0
    
    for source_name, result in results.items():
        status = "✅ Success" if result.error_count == 0 else "⚠️  Partial"
        duration = result.metadata.get('crawl_duration_seconds', 0)
        
        table.add_row(
            source_name,
            status,
            str(result.total_entities),
            str(result.error_count),
            f"{duration:.1f}s"
        )
        
        total_entities += result.total_entities
        total_errors += result.error_count
    
    # Add summary row
    table.add_row(
        "TOTAL",
        "📊 Summary",
        str(total_entities),
        str(total_errors),
        "-",
        style="bold"
    )
    
    console.print(table)


def _save_results(results: Dict[str, CrawlResult], output_path: str, format: str) -> None:
    """Save crawl results to file."""
    output_file = Path(output_path)
    
    if format == 'json':
        # Combine all entities
        all_entities = []
        for result in results.values():
            for entity in result.entities:
                all_entities.append(entity.dict())
        
        with open(output_file, 'w') as f:
            json.dump({
                'timestamp': datetime.utcnow().isoformat(),
                'total_entities': len(all_entities),
                'sources': list(results.keys()),
                'entities': all_entities
            }, f, indent=2, default=str)
            
    elif format == 'csv':
        import pandas as pd
        
        # Convert entities to flat records
        records = []
        for source_name, result in results.items():
            for entity in result.entities:
                record = {
                    'source': source_name,
                    'id': entity.id,
                    'name': entity.name,
                    'entity_type': entity.entity_type,
                    'sanction_status': entity.sanction_status,
                    'nationality': entity.nationality,
                    'last_updated': entity.last_updated.isoformat() if entity.last_updated else None,
                }
                records.append(record)
        
        df = pd.DataFrame(records)
        df.to_csv(output_file, index=False)


@cli.command()
@click.option('--source', '-s', type=click.Choice(list(CRAWLERS.keys()) + ['all']),
              default='all', help='Source to validate')
def validate(source: str):
    """Validate data quality for specified source."""
    console.print(f"🔍 Validating data quality for: {source}")
    
    # TODO: Implement data validation logic
    console.print("⚠️  Data validation not implemented yet")


@cli.command()
@click.option('--source', '-s', type=click.Choice(list(CRAWLERS.keys()) + ['all']),
              default='all', help='Source to check health')
def health(source: str):
    """Check health status of crawlers."""
    
    if source == 'all':
        sources_to_check = list(CRAWLERS.keys())
    else:
        sources_to_check = [source]
    
    table = Table(title="Crawler Health Status")
    table.add_column("Source", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Base URL", style="blue")
    table.add_column("Rate Limit", justify="right", style="yellow")
    
    for source_name in sources_to_check:
        crawler_class = CRAWLERS[source_name]
        crawler = crawler_class()
        health_status = crawler.get_health_status()
        
        status = "🟢 Ready" if health_status['status'] == 'ready' else "🔴 Not Ready"
        
        table.add_row(
            source_name,
            status,
            health_status['config']['base_url'],
            f"{health_status['config']['rate_limit']}s"
        )
    
    console.print(table)


@cli.command()
def version():
    """Show version information."""
    from . import __version__
    console.print(f"SanctionsWatch version {__version__}")


@cli.command()
@click.argument('source', type=click.Choice(list(CRAWLERS.keys())))
def info(source: str):
    """Show detailed information about a specific crawler."""
    crawler_class = CRAWLERS[source]
    config = crawler_class.DEFAULT_CONFIG
    
    info_panel = f"""
Source: {config.source}
Base URL: {config.base_url}
Rate Limit: {config.rate_limit_seconds} seconds
Timeout: {config.timeout_seconds} seconds
User Agent: {config.user_agent}
SSL Verification: {'Yes' if config.verify_ssl else 'No'}
"""
    
    console.print(Panel(
        info_panel.strip(),
        title=f"Crawler Information: {source}",
        border_style="green"
    ))


def main():
    """Main entry point for the CLI."""
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n⏹️  Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        console.print(f"❌ Error: {e}", style="red")
        sys.exit(1)


if __name__ == '__main__':
    main()
