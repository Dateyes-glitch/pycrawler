"""Test the base crawler functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from sanctions_watch.core.base import BaseCrawler
from sanctions_watch.core.models import SanctionEntity, EntityType, CrawlerConfig


class TestCrawler(BaseCrawler):
    """Test implementation of BaseCrawler."""
    
    async def _fetch_data(self):
        return {"test": "data"}
    
    def _parse_entity(self, raw_data):
        return SanctionEntity(
            id="test-1",
            name="Test Entity",
            entity_type=EntityType.PERSON,
            source=self.config.source
        )


class TestBaseCrawler:
    """Test cases for BaseCrawler."""
    
    def test_crawler_initialization(self, test_config):
        """Test crawler initializes correctly."""
        crawler = TestCrawler(test_config)
        assert crawler.config.source == "test-source"
        assert crawler.session is None
    
    @pytest.mark.asyncio
    async def test_crawler_context_manager(self, test_config):
        """Test async context manager functionality."""
        async with TestCrawler(test_config) as crawler:
            assert crawler.session is not None
    
    @pytest.mark.asyncio
    async def test_crawl_success(self, test_config):
        """Test successful crawl operation."""
        async with TestCrawler(test_config) as crawler:
            # Mock the HTTP session
            crawler.session = AsyncMock()
            
            result = await crawler.crawl()
            
            assert result.source == "test-source"
            assert result.total_entities == 1
            assert result.error_count == 0
    
    def test_entity_validation(self, test_config):
        """Test entity validation logic."""
        crawler = TestCrawler(test_config)
        
        # Valid entity
        valid_entity = SanctionEntity(
            id="test-1",
            name="Test Entity",
            entity_type=EntityType.PERSON,
            source="test-source"
        )
        assert crawler._validate_entity(valid_entity) is True
        
        # Invalid entity (no name)
        invalid_entity = SanctionEntity(
            id="test-2",
            name="",
            entity_type=EntityType.PERSON,
            source="test-source"
        )
        assert crawler._validate_entity(invalid_entity) is False
