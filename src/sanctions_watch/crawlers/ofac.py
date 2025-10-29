"""OFAC (US Treasury) sanctions crawler implementation."""

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


class OFACCrawler(BaseCrawler):
    """Crawler for OFAC SDN (Specially Designated Nationals) list."""
    
    DEFAULT_CONFIG = CrawlerConfig(
        source="ofac",
        base_url="https://placeholder.invalid/ofac/sdn.xml",
        rate_limit_seconds=3.0,
        timeout_seconds=120,
    )
    
    def __init__(self, config: Optional[CrawlerConfig] = None):
        """Initialize OFAC crawler."""
        super().__init__(config or self.DEFAULT_CONFIG)
        
    async def _fetch_data(self) -> ET.Element:
        """Fetch OFAC SDN XML data."""
        try:
            # If mock file is configured, read from disk
            mock_file = self.config.custom_settings.get('mock_file') if hasattr(self.config, 'custom_settings') else None
            if mock_file:
                with open(mock_file, 'r', encoding='utf-8') as f:
                    content = f.read()
            else:
                response = await self._make_request(self.config.base_url)
                content = await response.text()
            
            # Parse XML
            root = ET.fromstring(content)
            self.logger.info("Fetched OFAC SDN XML", size_kb=len(content) // 1024)
            
            return root
            
        except ET.ParseError as e:
            raise CrawlerError(f"Failed to parse OFAC XML: {e}")
        except Exception as e:
            raise CrawlerError(f"Failed to fetch OFAC data: {e}")
            
    def _parse_entity(self, xml_element: ET.Element) -> SanctionEntity:
        """Parse an individual entity from OFAC SDN XML."""
        try:
            # Extract basic information
            entity_id = (
                xml_element.get('uid')
                or self._get_xml_text(xml_element, './/uid')
                or self._get_xml_text(xml_element, './/uidNumber')
                or 'unknown'
            )
            first_name = self._get_xml_text(xml_element, './/firstName')
            last_name = self._get_xml_text(xml_element, './/lastName')
            
            # Construct name
            if first_name or last_name:
                primary_name = ' '.join(filter(None, [first_name, last_name])).strip() or 'Unknown'
            else:
                primary_name = self._get_xml_text(xml_element, './/title') or 'Unknown'
                
            # Extract aliases
            alternative_names = self._extract_aliases(xml_element)
            
            # Determine entity type
            entity_type = self._determine_entity_type(xml_element)
            
            # Create base entity
            entity = SanctionEntity(
                id=f"ofac-{entity_id}",
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
            self.logger.error("Failed to parse OFAC entity", error=str(e))
            raise DataValidationError(f"Failed to parse OFAC entity: {e}")
            
    def _extract_aliases(self, xml_element: ET.Element) -> List[str]:
        """Extract aliases from OFAC XML."""
        aliases = []
        
        for aka_elem in xml_element.findall('.//aka'):
            aka_type = aka_elem.get('type', '').lower()
            first_name = self._get_xml_text(aka_elem, 'firstName')
            last_name = self._get_xml_text(aka_elem, 'lastName')
            
            if first_name and last_name:
                alias = f"{first_name} {last_name}".strip()
                if alias not in aliases:
                    aliases.append(alias)
                    
        return aliases
        
    def _determine_entity_type(self, xml_element: ET.Element) -> EntityType:
        """Determine entity type from OFAC XML element."""
        sdn_type = xml_element.get('sdnType', '').lower()
        
        if 'individual' in sdn_type:
            return EntityType.PERSON
        elif 'entity' in sdn_type:
            return EntityType.ENTITY
        elif 'vessel' in sdn_type:
            return EntityType.VESSEL
        elif 'aircraft' in sdn_type:
            return EntityType.AIRCRAFT
            
        # Fallback: check for personal info
        if xml_element.find('.//dateOfBirth') is not None:
            return EntityType.PERSON
            
        return EntityType.UNKNOWN
        
    def _extract_addresses(self, xml_element: ET.Element, entity: SanctionEntity) -> None:
        """Extract address information from OFAC XML."""
        for address_elem in xml_element.findall('.//address'):
            try:
                address1 = self._get_xml_text(address_elem, 'address1')
                address2 = self._get_xml_text(address_elem, 'address2')
                city = self._get_xml_text(address_elem, 'city')
                state = self._get_xml_text(address_elem, 'stateOrProvince')
                postal_code = self._get_xml_text(address_elem, 'postalCode')
                country = self._get_xml_text(address_elem, 'country')
                
                # Combine address lines
                street_parts = [address1, address2]
                street = ', '.join(filter(None, street_parts))
                
                # Create full address
                address_parts = [street, city, state, postal_code, country]
                full_address = ', '.join(filter(None, address_parts))
                
                address = Address(
                    address_type=AddressType.OTHER,
                    street=street if street else None,
                    city=city,
                    state_province=state,
                    postal_code=postal_code,
                    country=country,
                    full_address=full_address if full_address else None
                )
                
                entity.addresses.append(address)
                
            except Exception as e:
                self.logger.warning("Failed to parse OFAC address", error=str(e))
                
    def _extract_identifiers(self, xml_element: ET.Element, entity: SanctionEntity) -> None:
        """Extract identification documents from OFAC XML."""
        for id_elem in xml_element.findall('.//id'):
            try:
                id_type = self._get_xml_text(id_elem, 'idType')
                id_number = self._get_xml_text(id_elem, 'idNumber')
                country = self._get_xml_text(id_elem, 'idCountry')
                
                if id_number:
                    identifier_type = self._map_identifier_type(id_type)
                    
                    identifier = Identifier(
                        identifier_type=identifier_type,
                        value=id_number,
                        issuing_country=country
                    )
                    
                    entity.identifiers.append(identifier)
                    
            except Exception as e:
                self.logger.warning("Failed to parse OFAC identifier", error=str(e))
                
    def _extract_dates(self, xml_element: ET.Element, entity: SanctionEntity) -> None:
        """Extract important dates from OFAC XML."""
        try:
            dates = EntityDates()
            
            # Date of birth
            birth_date_elem = xml_element.find('.//dateOfBirth')
            if birth_date_elem is not None:
                birth_date_str = birth_date_elem.text
                if birth_date_str:
                    dates.birth_date = self._parse_date(birth_date_str)
                    
            entity.dates = dates
            
        except Exception as e:
            self.logger.warning("Failed to parse OFAC dates", error=str(e))
            
    def _extract_sanctions_info(self, xml_element: ET.Element, entity: SanctionEntity) -> None:
        """Extract sanctions program information from OFAC XML."""
        try:
            # Extract programs
            for program_elem in xml_element.findall('.//program'):
                program_name = program_elem.text
                if program_name:
                    program = SanctionProgram(
                        name=program_name,
                        authority="US Treasury OFAC",
                        program_type="OFAC Sanctions",
                        description=program_name
                    )
                    entity.sanctions_programs.append(program)
                    
        except Exception as e:
            self.logger.warning("Failed to parse OFAC sanctions info", error=str(e))
            
    def _extract_personal_info(self, xml_element: ET.Element, entity: SanctionEntity) -> None:
        """Extract personal information from OFAC XML."""
        try:
            # Nationality/Citizenship
            nationality = self._get_xml_text(xml_element, './/nationality')
            if nationality:
                entity.nationality = nationality
                entity.citizenship = [nationality]
                
            # Title/Position
            title = self._get_xml_text(xml_element, './/title')
            if title:
                entity.position = title
                
        except Exception as e:
            self.logger.warning("Failed to parse OFAC personal info", error=str(e))
            
    def _get_xml_text(self, element: ET.Element, xpath: str) -> Optional[str]:
        """Safely get text from XML element."""
        try:
            found = element.find(xpath)
            return found.text.strip() if found is not None and found.text else None
        except AttributeError:
            return None
            
    def _map_identifier_type(self, ofac_type: Optional[str]) -> IdentifierType:
        """Map OFAC identifier types to our standard types."""
        if not ofac_type:
            return IdentifierType.OTHER
            
        ofac_type_lower = ofac_type.lower()
        
        mapping = {
            'passport': IdentifierType.PASSPORT,
            'national': IdentifierType.NATIONAL_ID,
            'tax': IdentifierType.TAX_ID,
            'registration': IdentifierType.REGISTRATION_NUMBER,
            'swift': IdentifierType.SWIFT_BIC,
            'imo': IdentifierType.IMO_NUMBER,
            'call sign': IdentifierType.CALL_SIGN,
        }
        
        for key, identifier_type in mapping.items():
            if key in ofac_type_lower:
                return identifier_type
                
        return IdentifierType.OTHER
        
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse OFAC date string to datetime object."""
        if not date_str:
            return None
            
        # OFAC uses various date formats
        date_formats = [
            '%d %b %Y',    # 01 Jan 1970
            '%Y-%m-%d',    # 1970-01-01
            '%d/%m/%Y',    # 01/01/1970
            '%m/%d/%Y',    # 01/01/1970
            '%Y',          # 1970
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
                
        self.logger.warning("Failed to parse OFAC date", date_str=date_str)
        return None
