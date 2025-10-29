"""UN Security Council sanctions crawler implementation."""

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


class UNSanctionsCrawler(BaseCrawler):
    """Crawler for UN Security Council Consolidated Sanctions List."""
    
    DEFAULT_CONFIG = CrawlerConfig(
        source="un-sanctions",
        base_url="https://placeholder.invalid/un/consolidated.xml",
        rate_limit_seconds=3.0,
        timeout_seconds=90,
    )
    
    def __init__(self, config: Optional[CrawlerConfig] = None):
        """Initialize UN sanctions crawler."""
        super().__init__(config or self.DEFAULT_CONFIG)
        
    async def _fetch_data(self) -> ET.Element:
        """Fetch UN sanctions XML data."""
        try:
            mock_file = self.config.custom_settings.get('mock_file') if hasattr(self.config, 'custom_settings') else None
            if mock_file:
                with open(mock_file, 'r', encoding='utf-8') as f:
                    content = f.read()
            else:
                response = await self._make_request(self.config.base_url)
                content = await response.text()
            
            # Parse XML
            root = ET.fromstring(content)
            self.logger.info("Fetched UN sanctions XML", size_kb=len(content) // 1024)
            
            return root
            
        except ET.ParseError as e:
            raise CrawlerError(f"Failed to parse UN sanctions XML: {e}")
        except Exception as e:
            raise CrawlerError(f"Failed to fetch UN sanctions data: {e}")
            
    def _parse_entity(self, xml_element: ET.Element) -> SanctionEntity:
        """Parse an individual entity from UN sanctions XML."""
        try:
            # Extract basic information
            entity_id = (
                xml_element.get('dataid')
                or self._get_xml_text(xml_element, '@dataid')
                or self._get_xml_text(xml_element, 'REFERENCE_NUMBER')
                or 'unknown'
            )
            
            # Extract names
            names = self._extract_names(xml_element)
            if not names:
                # Fallback for simple mock inputs
                names = [
                    ' '.join(filter(None, [
                        self._get_xml_text(xml_element, 'FIRST_NAME'),
                        self._get_xml_text(xml_element, 'SECOND_NAME'),
                        self._get_xml_text(xml_element, 'THIRD_NAME'),
                        self._get_xml_text(xml_element, 'FOURTH_NAME'),
                    ])).strip()
                ]
                names = [n for n in names if n]
            primary_name = names[0] if names else "Unknown"
            alternative_names = names[1:] if len(names) > 1 else []
            
            # Determine entity type
            entity_type = self._determine_entity_type(xml_element)
            
            # Create base entity
            entity = SanctionEntity(
                id=f"un-{entity_id}",
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
            self.logger.error("Failed to parse UN entity", error=str(e))
            raise DataValidationError(f"Failed to parse UN entity: {e}")
            
    def _extract_names(self, xml_element: ET.Element) -> List[str]:
        """Extract all names and aliases from UN XML element."""
        names = []
        
        # Primary name (varies by entity type)
        name_fields = [
            'FIRST_NAME', 'SECOND_NAME', 'THIRD_NAME', 'FOURTH_NAME',
            'NAME_ORIGINAL_SCRIPT', 'ENTITY_NAME'
        ]
        
        name_parts = []
        for field in name_fields:
            value = self._get_xml_text(xml_element, field)
            if value:
                name_parts.append(value)
                
        if name_parts:
            full_name = ' '.join(name_parts).strip()
            if full_name:
                names.append(full_name)
        
        # Alternative names
        for alias_elem in xml_element.findall('.//INDIVIDUAL_ALIAS') + xml_element.findall('.//ENTITY_ALIAS'):
            alias_parts = []
            for field in ['ALIAS_NAME', 'QUALITY']:
                value = self._get_xml_text(alias_elem, field)
                if value:
                    alias_parts.append(value)
                    
            if alias_parts:
                alias_name = ' '.join(alias_parts).strip()
                if alias_name and alias_name not in names:
                    names.append(alias_name)
                    
        return names
        
    def _determine_entity_type(self, xml_element: ET.Element) -> EntityType:
        """Determine entity type from UN XML element."""
        # UN uses different top-level elements for different types
        tag = xml_element.tag.lower()
        
        if 'individual' in tag:
            return EntityType.PERSON
        elif 'entity' in tag:
            return EntityType.ENTITY
            
        # Check for specific fields
        if xml_element.find('FIRST_NAME') is not None:
            return EntityType.PERSON
        elif xml_element.find('ENTITY_NAME') is not None:
            return EntityType.ENTITY
            
        return EntityType.UNKNOWN
        
    def _extract_addresses(self, xml_element: ET.Element, entity: SanctionEntity) -> None:
        """Extract address information from UN XML."""
        for address_elem in xml_element.findall('.//INDIVIDUAL_ADDRESS') + xml_element.findall('.//ENTITY_ADDRESS'):
            try:
                street = self._get_xml_text(address_elem, 'STREET')
                city = self._get_xml_text(address_elem, 'CITY')
                state = self._get_xml_text(address_elem, 'STATE_PROVINCE')
                country = self._get_xml_text(address_elem, 'COUNTRY')
                
                # Create full address
                address_parts = [street, city, state, country]
                full_address = ', '.join(filter(None, address_parts))
                
                address = Address(
                    address_type=AddressType.OTHER,
                    street=street,
                    city=city,
                    state_province=state,
                    country=country,
                    full_address=full_address if full_address else None
                )
                
                entity.addresses.append(address)
                
            except Exception as e:
                self.logger.warning("Failed to parse UN address", error=str(e))
                
    def _extract_identifiers(self, xml_element: ET.Element, entity: SanctionEntity) -> None:
        """Extract identification documents from UN XML."""
        for id_elem in xml_element.findall('.//INDIVIDUAL_DOCUMENT') + xml_element.findall('.//ENTITY_DOCUMENT'):
            try:
                doc_type = self._get_xml_text(id_elem, 'TYPE_OF_DOCUMENT')
                doc_number = self._get_xml_text(id_elem, 'NUMBER')
                country = self._get_xml_text(id_elem, 'ISSUING_COUNTRY')
                
                if doc_number:
                    identifier_type = self._map_identifier_type(doc_type)
                    
                    identifier = Identifier(
                        identifier_type=identifier_type,
                        value=doc_number,
                        issuing_country=country
                    )
                    
                    entity.identifiers.append(identifier)
                    
            except Exception as e:
                self.logger.warning("Failed to parse UN identifier", error=str(e))
                
    def _extract_dates(self, xml_element: ET.Element, entity: SanctionEntity) -> None:
        """Extract important dates from UN XML."""
        try:
            dates = EntityDates()
            
            # Date of birth
            birth_date = self._get_xml_text(xml_element, 'INDIVIDUAL_DATE_OF_BIRTH')
            if birth_date:
                dates.birth_date = self._parse_date(birth_date)
                
            if dates.birth_date:
                entity.dates = dates
                
        except Exception as e:
            self.logger.warning("Failed to parse UN dates", error=str(e))
            
    def _extract_sanctions_info(self, xml_element: ET.Element, entity: SanctionEntity) -> None:
        """Extract sanctions program information from UN XML."""
        try:
            # Extract committee information
            committee = self._get_xml_text(xml_element, 'UN_LIST_TYPE')
            if committee:
                program = SanctionProgram(
                    name=f"UN {committee}",
                    authority="United Nations Security Council",
                    program_type="UN Sanctions",
                    description=committee
                )
                entity.sanctions_programs.append(program)
                
            # Extract listing date
            listed_on = self._get_xml_text(xml_element, 'LISTED_ON')
            if listed_on:
                ref = Reference(
                    publication_date=self._parse_date(listed_on),
                    additional_info=f"Listed on UN sanctions list: {listed_on}"
                )
                entity.references.append(ref)
                
        except Exception as e:
            self.logger.warning("Failed to parse UN sanctions info", error=str(e))
            
    def _extract_personal_info(self, xml_element: ET.Element, entity: SanctionEntity) -> None:
        """Extract personal information from UN XML."""
        try:
            # Nationality
            nationality = self._get_xml_text(xml_element, 'NATIONALITY')
            if nationality:
                entity.nationality = nationality
                entity.citizenship = [nationality]
                
            # Place of birth (can indicate nationality)
            place_of_birth = self._get_xml_text(xml_element, 'PLACE_OF_BIRTH')
            if place_of_birth and not entity.nationality:
                entity.nationality = place_of_birth
                
        except Exception as e:
            self.logger.warning("Failed to parse UN personal info", error=str(e))
            
    def _get_xml_text(self, element: ET.Element, xpath: str) -> Optional[str]:
        """Safely get text from XML element, supports attribute lookups like '@attr'."""
        try:
            if xpath.startswith('@'):
                attr = xpath[1:]
                val = element.get(attr)
                return val.strip() if isinstance(val, str) else val
            found = element.find(xpath)
            return found.text.strip() if found is not None and found.text else None
        except Exception:
            return None
            
    def _map_identifier_type(self, un_type: Optional[str]) -> IdentifierType:
        """Map UN identifier types to our standard types."""
        if not un_type:
            return IdentifierType.OTHER
            
        un_type_lower = un_type.lower()
        
        mapping = {
            'passport': IdentifierType.PASSPORT,
            'national': IdentifierType.NATIONAL_ID,
            'identity': IdentifierType.NATIONAL_ID,
            'tax': IdentifierType.TAX_ID,
            'registration': IdentifierType.REGISTRATION_NUMBER,
        }
        
        for key, identifier_type in mapping.items():
            if key in un_type_lower:
                return identifier_type
                
        return IdentifierType.OTHER
        
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse UN date string to datetime object."""
        if not date_str:
            return None
            
        # UN uses various date formats
        date_formats = [
            '%Y-%m-%d',    # 1970-01-01
            '%d %b %Y',    # 01 Jan 1970
            '%Y',          # 1970
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
                
        self.logger.warning("Failed to parse UN date", date_str=date_str)
        return None
