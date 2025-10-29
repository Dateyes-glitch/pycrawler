"""Core data models for sanctions entities."""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, HttpUrl


class EntityType(str, Enum):
    """Types of sanctioned entities."""
    PERSON = "person"
    ENTITY = "entity"
    VESSEL = "vessel"
    AIRCRAFT = "aircraft"
    ORGANIZATION = "organization"
    UNKNOWN = "unknown"


class IdentifierType(str, Enum):
    """Types of entity identifiers."""
    PASSPORT = "passport"
    NATIONAL_ID = "national_id"
    TAX_ID = "tax_id"
    REGISTRATION_NUMBER = "registration_number"
    IMO_NUMBER = "imo_number"
    CALL_SIGN = "call_sign"
    SWIFT_BIC = "swift_bic"
    OTHER = "other"


class AddressType(str, Enum):
    """Types of addresses."""
    RESIDENCE = "residence"
    BUSINESS = "business"
    BIRTH_PLACE = "birth_place"
    REGISTRATION = "registration"
    OTHER = "other"


class SanctionStatus(str, Enum):
    """Sanction status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DELISTED = "delisted"
    PENDING = "pending"


class Address(BaseModel):
    """Address information for an entity."""
    address_type: AddressType
    street: Optional[str] = None
    city: Optional[str] = None
    state_province: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    full_address: Optional[str] = None


class Identifier(BaseModel):
    """Identifier information for an entity."""
    identifier_type: IdentifierType
    value: str
    issuing_country: Optional[str] = None
    issuing_authority: Optional[str] = None
    issue_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None


class EntityDates(BaseModel):
    """Important dates for an entity."""
    birth_date: Optional[datetime] = None
    death_date: Optional[datetime] = None
    incorporation_date: Optional[datetime] = None
    dissolution_date: Optional[datetime] = None


class Reference(BaseModel):
    """Reference information and sources."""
    source_url: Optional[HttpUrl] = None
    reference_number: Optional[str] = None
    publication_date: Optional[datetime] = None
    legal_basis: Optional[str] = None
    additional_info: Optional[str] = None


class SanctionProgram(BaseModel):
    """Sanction program information."""
    name: str
    authority: str
    program_type: str
    description: Optional[str] = None
    legal_basis: Optional[str] = None


class SanctionEntity(BaseModel):
    """Core model for a sanctioned entity."""
    
    # Core identification
    id: str = Field(..., description="Unique identifier for the entity")
    name: str = Field(..., description="Primary name of the entity")
    alternative_names: List[str] = Field(default_factory=list, description="Alternative names and aliases")
    entity_type: EntityType = Field(..., description="Type of entity")
    
    # Source information
    source: str = Field(..., description="Data source (e.g., 'eu-sanctions', 'ofac')")
    source_id: Optional[str] = Field(None, description="Original ID from source system")
    
    # Sanction details
    sanction_status: SanctionStatus = Field(default=SanctionStatus.ACTIVE)
    sanctions_programs: List[SanctionProgram] = Field(default_factory=list)
    sanctions_reasons: List[str] = Field(default_factory=list)
    
    # Entity details
    addresses: List[Address] = Field(default_factory=list)
    identifiers: List[Identifier] = Field(default_factory=list)
    dates: Optional[EntityDates] = None
    
    # Additional information
    nationality: Optional[str] = None
    citizenship: List[str] = Field(default_factory=list)
    occupation: Optional[str] = None
    position: Optional[str] = None
    
    # References and sources
    references: List[Reference] = Field(default_factory=list)
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    data_quality_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    
    # Additional fields for flexible data
    additional_data: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }
        
    def add_identifier(self, identifier_type: IdentifierType, value: str, **kwargs) -> None:
        """Add an identifier to the entity."""
        identifier = Identifier(identifier_type=identifier_type, value=value, **kwargs)
        self.identifiers.append(identifier)
        
    def add_address(self, address_type: AddressType, **kwargs) -> None:
        """Add an address to the entity."""
        address = Address(address_type=address_type, **kwargs)
        self.addresses.append(address)
        
    def add_sanction_program(self, name: str, authority: str, program_type: str, **kwargs) -> None:
        """Add a sanction program to the entity."""
        program = SanctionProgram(
            name=name, 
            authority=authority, 
            program_type=program_type,
            **kwargs
        )
        self.sanctions_programs.append(program)


class CrawlResult(BaseModel):
    """Result of a crawling operation."""
    source: str
    entities: List[SanctionEntity]
    crawl_timestamp: datetime = Field(default_factory=datetime.utcnow)
    total_entities: int
    success_count: int
    error_count: int
    errors: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate counts after initialization."""
        self.total_entities = len(self.entities)
        self.success_count = self.total_entities - self.error_count


class CrawlerConfig(BaseModel):
    """Configuration for crawlers."""
    source: str
    base_url: str
    rate_limit_seconds: float = 1.0
    max_retries: int = 3
    timeout_seconds: int = 30
    user_agent: str = "SanctionsWatch/0.1.0"
    headers: Dict[str, str] = Field(default_factory=dict)
    verify_ssl: bool = True
    custom_settings: Dict[str, Any] = Field(default_factory=dict)
