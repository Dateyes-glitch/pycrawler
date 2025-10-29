"""Test configuration and fixtures."""

import pytest
import asyncio
from unittest.mock import MagicMock

from sanctions_watch.core.models import CrawlerConfig


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_session():
    """Mock aiohttp session for testing."""
    session = MagicMock()
    return session


@pytest.fixture
def test_config():
    """Test configuration for crawlers."""
    return CrawlerConfig(
        source="test-source",
        base_url="https://example.com/test",
        rate_limit_seconds=0.1,  # Fast for testing
        timeout_seconds=5,
    )
