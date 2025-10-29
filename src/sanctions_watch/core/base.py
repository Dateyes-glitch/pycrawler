"""Base crawler class and common functionality."""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional, Dict, Any, AsyncGenerator
import time

import aiohttp
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .models import SanctionEntity, CrawlResult, CrawlerConfig
from .exceptions import CrawlerError, RateLimitError, DataValidationError


logger = structlog.get_logger(__name__)


class BaseCrawler(ABC):
    """Abstract base class for all sanctions data crawlers."""
    
    def __init__(self, config: CrawlerConfig):
        """Initialize the crawler with configuration."""
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        self.last_request_time = 0.0
        self.logger = logger.bind(source=config.source)
        
    async def __aenter__(self):
        """Async context manager entry."""
        await self._create_session()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self._close_session()
        
    async def _create_session(self) -> None:
        """Create HTTP session with proper configuration."""
        timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
        connector = aiohttp.TCPConnector(verify_ssl=self.config.verify_ssl)
        
        headers = {
            'User-Agent': self.config.user_agent,
            **self.config.headers
        }
        
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers=headers
        )
        
    async def _close_session(self) -> None:
        """Close HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None
            
    async def _rate_limit(self) -> None:
        """Implement rate limiting between requests."""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        if time_since_last_request < self.config.rate_limit_seconds:
            sleep_time = self.config.rate_limit_seconds - time_since_last_request
            self.logger.debug("Rate limiting", sleep_time=sleep_time)
            await asyncio.sleep(sleep_time)
            
        self.last_request_time = time.time()
        
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((aiohttp.ClientError, RateLimitError))
    )
    async def _make_request(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """Make HTTP request with retry logic and rate limiting."""
        if not self.session:
            raise CrawlerError("Session not initialized. Use async context manager.")
            
        await self._rate_limit()
        
        self.logger.info("Making request", url=url)
        
        try:
            response = await self.session.get(url, **kwargs)
            
            if response.status == 429:
                raise RateLimitError(f"Rate limit exceeded for {url}")
            elif response.status >= 400:
                response.raise_for_status()
                
            return response
            
        except aiohttp.ClientError as e:
            self.logger.error("Request failed", url=url, error=str(e))
            raise
            
    @abstractmethod
    async def _fetch_data(self) -> Any:
        """Fetch raw data from the source. Must be implemented by subclasses."""
        pass
        
    @abstractmethod
    def _parse_entity(self, raw_data: Any) -> SanctionEntity:
        """Parse raw data into SanctionEntity. Must be implemented by subclasses."""
        pass
        
    def _validate_entity(self, entity: SanctionEntity) -> bool:
        """Validate a parsed entity."""
        try:
            # Basic validation - entity must have name and valid type
            if not entity.name or not entity.name.strip():
                raise DataValidationError("Entity name is required")
                
            if not entity.id or not entity.id.strip():
                raise DataValidationError("Entity ID is required")
                
            if not entity.source:
                raise DataValidationError("Entity source is required")
                
            return True
            
        except Exception as e:
            self.logger.warning("Entity validation failed", entity_id=entity.id, error=str(e))
            return False
            
    async def crawl(self) -> CrawlResult:
        """Main crawl method that orchestrates the data collection process."""
        start_time = datetime.utcnow()
        entities: List[SanctionEntity] = []
        errors: List[str] = []
        
        self.logger.info("Starting crawl", source=self.config.source)
        
        try:
            # Ensure session is created
            if not self.session:
                await self._create_session()
                
            # Fetch raw data
            raw_data = await self._fetch_data()
            
            # Process data
            async for entity in self._process_data(raw_data):
                if self._validate_entity(entity):
                    entities.append(entity)
                else:
                    errors.append(f"Validation failed for entity: {entity.id}")
                    
        except Exception as e:
            error_msg = f"Crawl failed for {self.config.source}: {str(e)}"
            self.logger.error("Crawl failed", error=error_msg)
            errors.append(error_msg)
            
        finally:
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            result = CrawlResult(
                source=self.config.source,
                entities=entities,
                crawl_timestamp=start_time,
                total_entities=len(entities),
                success_count=len(entities),
                error_count=len(errors),
                errors=errors,
                metadata={
                    'crawl_duration_seconds': duration,
                    'start_time': start_time.isoformat(),
                    'end_time': end_time.isoformat(),
                }
            )
            
            self.logger.info(
                "Crawl completed",
                total_entities=result.total_entities,
                errors=result.error_count,
                duration=duration
            )
            
            return result
            
    async def _process_data(self, raw_data: Any) -> AsyncGenerator[SanctionEntity, None]:
        """Process raw data and yield entities. Can be overridden for custom processing."""
        if isinstance(raw_data, list):
            for item in raw_data:
                try:
                    entity = self._parse_entity(item)
                    yield entity
                except Exception as e:
                    self.logger.warning("Failed to parse entity", error=str(e), item=str(item)[:100])
        else:
            try:
                entity = self._parse_entity(raw_data)
                yield entity
            except Exception as e:
                self.logger.warning("Failed to parse data", error=str(e))
                
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the crawler."""
        return {
            'source': self.config.source,
            'status': 'ready' if self.session else 'not_initialized',
            'last_request_time': self.last_request_time,
            'config': {
                'base_url': self.config.base_url,
                'rate_limit': self.config.rate_limit_seconds,
                'timeout': self.config.timeout_seconds,
            }
        }
