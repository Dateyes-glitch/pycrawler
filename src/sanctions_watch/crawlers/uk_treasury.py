"""UK Treasury sanctions crawler implementation."""

import csv
import io
from datetime import datetime
from typing import Any, List, Optional, Dict

from ..core.base import BaseCrawler
from ..core.models import (
    SanctionEntity, EntityType, CrawlerConfig, 
    Address, AddressType, Identifier, IdentifierType,
    EntityDates, Reference, SanctionProgram, SanctionStatus
)
from ..core.exceptions import CrawlerError, DataValidationError


class UKTreasuryCrawler(BaseCrawler):
    """Crawler for UK HM Treasury sanctions (OFSI Consolidated List)."""
    
    DEFAULT_CONFIG = CrawlerConfig(
        source="uk-treasury",
        base_url="https://ofsistorage.blob.core.windows.net/publishlive/2022format/ConList.csv",
        rate_limit_seconds=2.0,
        timeout_seconds=60,
    )
    
    def __init__(self, config: Optional[CrawlerConfig] = None):
        """Initialize UK Treasury crawler."""
        super().__init__(config or self.DEFAULT_CONFIG)
        
    async def _fetch_data(self) -> List[Dict[str, str]]:
        """Fetch UK Treasury sanctions CSV data."""
        try:
            response = await self._make_request(self.config.base_url)
            content = await response.text()
            
            # Parse CSV
            csv_reader = csv.DictReader(io.StringIO(content))
            data = list(csv_reader)
            
            self.logger.info("Fetched UK Treasury CSV", rows=len(data))
            return data
            
        except Exception as e:
            raise CrawlerError(f"Failed to fetch UK Treasury data: {e}")
            
    def _parse_entity(self, row_data: Dict[str, str]) -> SanctionEntity:
        """Parse an individual entity from UK Treasury CSV row."""
        try:
            # Extract basic information
            entity_id = row_data.get('GroupID', '').strip()
            name1 = row_data.get('Name1', '').strip()
            name2 = row_data.get('Name2', '').strip()
            name3 = row_data.get('Name3', '').strip()
            name4 = row_data.get('Name4', '').strip()
            name5 = row_data.get('Name5', '').strip()
            name6 = row_data.get('Name6', '').strip()
            
            # Construct primary name and alternatives
            names = [name for name in [name1, name2, name3, name4, name5, name6] if name]
            primary_name = names[0] if names else "Unknown"
            alternative_names = names[1:] if len(names) > 1 else []
            
            # Determine entity type
            entity_type = self._determine_entity_type(row_data)
            
            # Create base entity
            entity = SanctionEntity(
                id=f"uk-{entity_id}",
                name=primary_name,
                alternative_names=alternative_names,
                entity_type=entity_type,
                source=self.config.source,
                source_id=entity_id,
                sanction_status=SanctionStatus.ACTIVE
            )
            
            # Extract additional details
            self._extract_addresses(row_data, entity)
            self._extract_identifiers(row_data, entity)
            self._extract_dates(row_data, entity)
            self._extract_sanctions_info(row_data, entity)
            self._extract_personal_info(row_data, entity)
            
            return entity
            
        except Exception as e:
            self.logger.error("Failed to parse UK entity", error=str(e))
            raise DataValidationError(f"Failed to parse UK entity: {e}")
            
    def _determine_entity_type(self, row_data: Dict[str, str]) -> EntityType:
        """Determine entity type from UK Treasury CSV row."""
        group_type = row_data.get('GroupType', '').lower()
        
        if 'individual' in group_type:
            return EntityType.PERSON
        elif 'entity' in group_type or 'organisation' in group_type:
            return EntityType.ENTITY
        elif 'ship' in group_type or 'vessel' in group_type:
            return EntityType.VESSEL
            
        # Check for birth date (indicates person)
        if row_data.get('DOB'):
            return EntityType.PERSON
            
        return EntityType.UNKNOWN
        
    def _extract_addresses(self, row_data: Dict[str, str], entity: SanctionEntity) -> None:
        """Extract address information from UK Treasury CSV."""
        try:
            # UK Treasury provides up to 6 address fields
            address_fields = [
                row_data.get('Address1', '').strip(),
                row_data.get('Address2', '').strip(), 
                row_data.get('Address3', '').strip(),
                row_data.get('Address4', '').strip(),
                row_data.get('Address5', '').strip(),
                row_data.get('Address6', '').strip(),
            ]
            
            # Filter out empty fields
            address_parts = [part for part in address_fields if part]
            
            if address_parts:
                full_address = ', '.join(address_parts)
                
                # Try to parse structured address
                country = None
                postal_code = None
                city = None
                
                # Last part is often country
                if address_parts:
                    potential_country = address_parts[-1]
                    if len(potential_country) <= 50:  # Reasonable country name length
                        country = potential_country
                        
                # Look for postal codes in address parts
                for part in address_parts:
                    if self._looks_like_postal_code(part):
                        postal_code = part
                        break
                        
                address = Address(
                    address_type=AddressType.OTHER,
                    city=city,
                    postal_code=postal_code,
                    country=country,
                    full_address=full_address
                )
                
                entity.addresses.append(address)
                
        except Exception as e:
            self.logger.warning("Failed to parse UK address", error=str(e))
            
    def _extract_identifiers(self, row_data: Dict[str, str], entity: SanctionEntity) -> None:
        """Extract identification documents from UK Treasury CSV."""
        try:
            # Passport numbers
            passport_details = row_data.get('PassportDetails', '').strip()
            if passport_details:
                # Parse passport details (format varies)
                passport_parts = passport_details.split()
                for part in passport_parts:
                    if len(part) >= 6:  # Reasonable passport number length
                        identifier = Identifier(
                            identifier_type=IdentifierType.PASSPORT,
                            value=part
                        )
                        entity.identifiers.append(identifier)
                        break
                        
            # National ID numbers
            national_id = row_data.get('NationalIdentificationNumber', '').strip()
            if national_id:
                identifier = Identifier(
                    identifier_type=IdentifierType.NATIONAL_ID,
                    value=national_id
                )
                entity.identifiers.append(identifier)
                
        except Exception as e:
            self.logger.warning("Failed to parse UK identifiers", error=str(e))
            
    def _extract_dates(self, row_data: Dict[str, str], entity: SanctionEntity) -> None:
        """Extract important dates from UK Treasury CSV."""
        try:
            dates = EntityDates()
            
            # Date of birth
            dob = row_data.get('DOB', '').strip()
            if dob:
                dates.birth_date = self._parse_date(dob)
                
            if dates.birth_date:
                entity.dates = dates
                
        except Exception as e:
            self.logger.warning("Failed to parse UK dates", error=str(e))
            
    def _extract_sanctions_info(self, row_data: Dict[str, str], entity: SanctionEntity) -> None:
        """Extract sanctions program information from UK Treasury CSV."""
        try:
            # Extract regime
            regime = row_data.get('Regime', '').strip()
            if regime:
                program = SanctionProgram(
                    name=regime,
                    authority="UK HM Treasury OFSI",
                    program_type="UK Sanctions",
                    description=regime
                )
                entity.sanctions_programs.append(program)
                
            # Extract listed date as reference
            listed_on = row_data.get('ListedOn', '').strip()
            if listed_on:
                ref = Reference(
                    publication_date=self._parse_date(listed_on),
                    additional_info=f"Listed on UK sanctions list: {listed_on}"
                )
                entity.references.append(ref)
                
        except Exception as e:
            self.logger.warning("Failed to parse UK sanctions info", error=str(e))
            
    def _extract_personal_info(self, row_data: Dict[str, str], entity: SanctionEntity) -> None:
        """Extract personal information from UK Treasury CSV."""
        try:
            # Town of birth (often used as nationality indicator)
            town_of_birth = row_data.get('TownOfBirth', '').strip()
            country_of_birth = row_data.get('CountryOfBirth', '').strip()
            
            if country_of_birth:
                entity.nationality = country_of_birth
                entity.citizenship = [country_of_birth]
                
            # Position
            position = row_data.get('Position', '').strip()
            if position:
                entity.position = position
                
        except Exception as e:
            self.logger.warning("Failed to parse UK personal info", error=str(e))
            
    def _looks_like_postal_code(self, text: str) -> bool:
        """Check if text looks like a postal code."""
        # Simple heuristics for postal codes
        text = text.strip()
        return (
            len(text) >= 3 and len(text) <= 10 and
            any(c.isdigit() for c in text)
        )
        
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse UK date string to datetime object."""
        if not date_str:
            return None
            
        # UK uses various date formats
        date_formats = [
            '%d/%m/%Y',    # 01/01/1970
            '%d-%m-%Y',    # 01-01-1970
            '%Y-%m-%d',    # 1970-01-01
            '%d %b %Y',    # 01 Jan 1970
            '%b %Y',       # Jan 1970
            '%Y',          # 1970
        ]
        
        # Clean up date string
        date_str = date_str.strip().replace('00/00/', '01/01/')
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
                
        self.logger.warning("Failed to parse UK date", date_str=date_str)
        return None
