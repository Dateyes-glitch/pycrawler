"""EU Sanctions crawler implementation."""

import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, List, Optional
import re

from ..core.base import BaseCrawler
from ..core.models import (
    SanctionEntity, EntityType, CrawlerConfig, 
    Address, AddressType, Identifier, IdentifierType,
    EntityDates, Reference, SanctionProgram, SanctionStatus
)
from ..core.exceptions import CrawlerError, DataValidationError


class EUSanctionsCrawler(BaseCrawler):
    """Crawler for EU sanctions data from the European External Action Service."""
    
    DEFAULT_CONFIG = CrawlerConfig(
        source="eu-sanctions",
        base_url="https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content",
        rate_limit_seconds=2.0,
        timeout_seconds=60,
    )
    
    def __init__(self, config: Optional[CrawlerConfig] = None):
        """Initialize EU sanctions crawler."""
        super().__init__(config or self.DEFAULT_CONFIG)
        
    async def _fetch_data(self) -> ET.Element:
        """Fetch EU sanctions XML data."""
        try:
            response = await self._make_request(self.config.base_url)
            content = await response.text()
            
            # Parse XML
            root = ET.fromstring(content)
            self.logger.info("Fetched EU sanctions XML", size_kb=len(content) // 1024)
            
            return root
            
        except ET.ParseError as e:
            raise CrawlerError(f"Failed to parse EU sanctions XML: {e}")
        except Exception as e:
            raise CrawlerError(f"Failed to fetch EU sanctions data: {e}")
            
    def _parse_entity(self, xml_element: ET.Element) -> SanctionEntity:
        """Parse an individual entity from EU sanctions XML."""
        try:
            # Extract basic information
            entity_id = self._get_xml_text(xml_element, './/unitId')
            if not entity_id:
                entity_id = self._get_xml_text(xml_element, './/logicalId')
                
            names = self._extract_names(xml_element)
            primary_name = names[0] if names else "Unknown"
            alternative_names = names[1:] if len(names) > 1 else []
            
            # Determine entity type
            entity_type = self._determine_entity_type(xml_element)
            
            # Create base entity
            entity = SanctionEntity(
                id=f"eu-{entity_id}",
                name=primary_name,
                alternative_names=alternative_names,
                entity_type=entity_type,
                source=self.config.source,
                source_id=entity_id,
                sanction_status=SanctionStatus.ACTIVE
            )
            
            # Extract additional details
            self._extract_addresses(xml_element, entity)
            self._extract_identifiers(xml_element, entity)
            self._extract_dates(xml_element, entity)
            self._extract_sanctions_info(xml_element, entity)
            self._extract_personal_info(xml_element, entity)
            
            return entity
            
        except Exception as e:
            self.logger.error("Failed to parse EU entity", error=str(e))
            raise DataValidationError(f"Failed to parse EU entity: {e}")
            
    def _extract_names(self, xml_element: ET.Element) -> List[str]:
        """Extract all names and aliases from XML element."""
        names = []
        
        # Primary names
        for name_elem in xml_element.findall('.//nameAlias'):
            # Check for different name types
            whole_name = self._get_xml_text(name_elem, 'wholeName')
            if whole_name:
                names.append(whole_name.strip())
                
            # Check for structured names (first, middle, last)
            first_name = self._get_xml_text(name_elem, 'firstName')
            middle_name = self._get_xml_text(name_elem, 'middleName')
            last_name = self._get_xml_text(name_elem, 'lastName')
            
            if any([first_name, middle_name, last_name]):
                full_name = ' '.join(filter(None, [first_name, middle_name, last_name]))
                if full_name and full_name not in names:
                    names.append(full_name.strip())
                    
        return names
        
    def _determine_entity_type(self, xml_element: ET.Element) -> EntityType:
        """Determine entity type from XML element."""
        # Check for explicit entity type indicators
        subject_type = self._get_xml_text(xml_element, './/subjectType')
        
        if subject_type:
            subject_type_lower = subject_type.lower()
            if 'person' in subject_type_lower or 'individual' in subject_type_lower:
                return EntityType.PERSON
            elif 'entity' in subject_type_lower or 'enterprise' in subject_type_lower:
                return EntityType.ENTITY
            elif 'vessel' in subject_type_lower or 'ship' in subject_type_lower:
                return EntityType.VESSEL
                
        # Fallback: check for birth date (indicates person)
        birth_date = xml_element.find('.//birthdate')
        if birth_date is not None:
            return EntityType.PERSON
            
        # Check for registration info (indicates entity)
        registration = xml_element.find('.//identification')
        if registration is not None:
            return EntityType.ENTITY
            
        return EntityType.UNKNOWN
        
    def _extract_addresses(self, xml_element: ET.Element, entity: SanctionEntity) -> None:
        """Extract address information."""
        for address_elem in xml_element.findall('.//address'):
            try:
                # Get address components
                street = self._get_xml_text(address_elem, 'street')
                city = self._get_xml_text(address_elem, 'city')
                state = self._get_xml_text(address_elem, 'stateProvince')
                postal_code = self._get_xml_text(address_elem, 'zipCode')
                country = self._get_xml_text(address_elem, 'country')
                
                # Create full address string
                address_parts = [street, city, state, postal_code, country]
                full_address = ', '.join(filter(None, address_parts))
                
                address = Address(
                    address_type=AddressType.OTHER,  # EU doesn't specify address type
                    street=street,
                    city=city,
                    state_province=state,
                    postal_code=postal_code,
                    country=country,
                    full_address=full_address if full_address else None
                )
                
                entity.addresses.append(address)
                
            except Exception as e:
                self.logger.warning("Failed to parse address", error=str(e))
                
    def _extract_identifiers(self, xml_element: ET.Element, entity: SanctionEntity) -> None:
        """Extract identification documents and numbers."""
        for id_elem in xml_element.findall('.//identification'):
            try:
                id_type = self._get_xml_text(id_elem, 'identificationTypeCode')
                id_value = self._get_xml_text(id_elem, 'number')
                country = self._get_xml_text(id_elem, 'countryIso2Code')
                
                if id_value:
                    # Map EU ID types to our enum
                    identifier_type = self._map_identifier_type(id_type)
                    
                    identifier = Identifier(
                        identifier_type=identifier_type,
                        value=id_value,
                        issuing_country=country
                    )
                    
                    entity.identifiers.append(identifier)
                    
            except Exception as e:
                self.logger.warning("Failed to parse identifier", error=str(e))
                
    def _extract_dates(self, xml_element: ET.Element, entity: SanctionEntity) -> None:
        """Extract important dates."""
        try:
            dates = EntityDates()
            
            # Birth date
            birth_date_elem = xml_element.find('.//birthdate')
            if birth_date_elem is not None:
                birth_date_str = birth_date_elem.text
                if birth_date_str:
                    dates.birth_date = self._parse_date(birth_date_str)
                    
            entity.dates = dates
            
        except Exception as e:
            self.logger.warning("Failed to parse dates", error=str(e))
            
    def _extract_sanctions_info(self, xml_element: ET.Element, entity: SanctionEntity) -> None:
        """Extract sanctions program and legal basis information."""
        try:
            # Extract regulation references
            for regulation_elem in xml_element.findall('.//regulation'):
                regulation_number = self._get_xml_text(regulation_elem, 'number')
                publication_date = self._get_xml_text(regulation_elem, 'publicationDate')
                
                if regulation_number:
                    program = SanctionProgram(
                        name=f"EU Regulation {regulation_number}",
                        authority="European Union",
                        program_type="EU Sanctions",
                        legal_basis=regulation_number
                    )
                    entity.sanctions_programs.append(program)
                    
                    # Add reference
                    ref = Reference(
                        reference_number=regulation_number,
                        publication_date=self._parse_date(publication_date) if publication_date else None,
                        legal_basis=regulation_number
                    )
                    entity.references.append(ref)
                    
        except Exception as e:
            self.logger.warning("Failed to parse sanctions info", error=str(e))
            
    def _extract_personal_info(self, xml_element: ET.Element, entity: SanctionEntity) -> None:
        """Extract personal information like nationality, occupation."""
        try:
            # Nationality
            nationality = self._get_xml_text(xml_element, './/countryIso2Code')
            if nationality:
                entity.nationality = nationality
                entity.citizenship = [nationality]
                
            # Function/Position
            function = self._get_xml_text(xml_element, './/function')
            if function:
                entity.position = function
                
        except Exception as e:
            self.logger.warning("Failed to parse personal info", error=str(e))
            
    def _get_xml_text(self, element: ET.Element, xpath: str) -> Optional[str]:
        """Safely get text from XML element."""
        try:
            found = element.find(xpath)
            return found.text.strip() if found is not None and found.text else None
        except AttributeError:
            return None
            
    def _map_identifier_type(self, eu_type: Optional[str]) -> IdentifierType:
        """Map EU identifier types to our standard types."""
        if not eu_type:
            return IdentifierType.OTHER
            
        eu_type_lower = eu_type.lower()
        
        mapping = {
            'passport': IdentifierType.PASSPORT,
            'national': IdentifierType.NATIONAL_ID,
            'tax': IdentifierType.TAX_ID,
            'registration': IdentifierType.REGISTRATION_NUMBER,
            'id': IdentifierType.NATIONAL_ID,
        }
        
        for key, identifier_type in mapping.items():
            if key in eu_type_lower:
                return identifier_type
                
        return IdentifierType.OTHER
        
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string to datetime object."""
        if not date_str:
            return None
            
        # Try different date formats used by EU
        date_formats = [
            '%Y-%m-%d',
            '%d/%m/%Y',
            '%d.%m.%Y',
            '%Y',  # Year only
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
                
        self.logger.warning("Failed to parse date", date_str=date_str)
        return None
