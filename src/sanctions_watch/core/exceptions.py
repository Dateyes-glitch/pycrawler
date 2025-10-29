"""Custom exceptions for the sanctions watch framework."""


class SanctionsWatchError(Exception):
    """Base exception for all sanctions watch errors."""
    pass


class CrawlerError(SanctionsWatchError):
    """Exception raised when crawler operations fail."""
    pass


class DataValidationError(SanctionsWatchError):
    """Exception raised when data validation fails."""
    pass


class RateLimitError(CrawlerError):
    """Exception raised when rate limits are exceeded."""
    pass


class ConfigurationError(SanctionsWatchError):
    """Exception raised when configuration is invalid."""
    pass


class DatabaseError(SanctionsWatchError):
    """Exception raised when database operations fail."""
    pass


class ExportError(SanctionsWatchError):
    """Exception raised when export operations fail."""
    pass
