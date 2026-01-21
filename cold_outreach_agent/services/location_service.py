"""
Location Service - Validates and normalizes geographic locations for Google Maps search.

Provides:
1. Location validation and normalization
2. Fallback hierarchy (city → metro → region → country)
3. Common location aliases and corrections
4. Error logging with specific failure reasons
"""

import re
from typing import Optional, Tuple, List, Dict
from dataclasses import dataclass
from enum import Enum


class LocationConfidence(str, Enum):
    """Confidence level of location resolution."""
    EXACT = "exact"           # Validated city match
    METRO = "metro"           # Metro area approximation
    REGION = "region"         # State/province level
    COUNTRY = "country"       # Country level
    UNKNOWN = "unknown"       # Could not validate


@dataclass
class LocationResult:
    """Result of location validation/normalization."""
    original: str
    normalized: str
    search_query: str
    confidence: LocationConfidence
    fallback_used: bool
    city: Optional[str]
    region: Optional[str]
    country: Optional[str]
    error: Optional[str] = None


class LocationService:
    """
    Validates and normalizes locations for Google Maps search.
    
    Features:
    - Normalizes common abbreviations (TX → Texas)
    - Provides fallback hierarchy for failed searches
    - Returns structured location data for storage
    """
    
    # US State abbreviations to full names
    US_STATES = {
        "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
        "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
        "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
        "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
        "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
        "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
        "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
        "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
        "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
        "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
        "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
        "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
        "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia"
    }
    
    # Common city aliases and corrections
    CITY_ALIASES = {
        "nyc": "New York City, NY",
        "la": "Los Angeles, CA",
        "sf": "San Francisco, CA",
        "dc": "Washington, DC",
        "philly": "Philadelphia, PA",
        "chi": "Chicago, IL",
        "atl": "Atlanta, GA",
        "bay area": "San Francisco Bay Area, CA",
        "silicon valley": "San Jose, CA",
    }
    
    # Metro area mappings (city → metro area)
    METRO_AREAS = {
        "san francisco": "San Francisco Bay Area",
        "oakland": "San Francisco Bay Area",
        "berkeley": "San Francisco Bay Area",
        "san jose": "San Francisco Bay Area",
        "palo alto": "San Francisco Bay Area",
        "dallas": "Dallas-Fort Worth",
        "fort worth": "Dallas-Fort Worth",
        "arlington": "Dallas-Fort Worth",  # TX context
        "new york": "New York Metro",
        "brooklyn": "New York Metro",
        "queens": "New York Metro",
        "manhattan": "New York Metro",
        "los angeles": "Greater Los Angeles",
        "long beach": "Greater Los Angeles",
        "pasadena": "Greater Los Angeles",
        "seattle": "Seattle Metro",
        "tacoma": "Seattle Metro",
        "bellevue": "Seattle Metro",
    }
    
    # Country codes
    COUNTRY_CODES = {
        "us": "United States",
        "usa": "United States",
        "uk": "United Kingdom",
        "gb": "United Kingdom",
        "ca": "Canada",
        "au": "Australia",
        "nz": "New Zealand",
        "de": "Germany",
        "fr": "France",
        "it": "Italy",
        "es": "Spain",
        "mx": "Mexico",
        "br": "Brazil",
        "in": "India",
        "cn": "China",
        "jp": "Japan",
    }
    
    def __init__(self):
        # Reverse lookup for state names
        self._state_name_to_abbr = {v.lower(): k for k, v in self.US_STATES.items()}
    
    def validate_and_normalize(self, location: str) -> LocationResult:
        """
        Validate and normalize a location string.
        
        Args:
            location: Raw location input (e.g., "Austin, TX", "NYC", "sf bay area")
            
        Returns:
            LocationResult with normalized location and confidence level
        """
        if not location or not location.strip():
            return LocationResult(
                original=location,
                normalized="",
                search_query="",
                confidence=LocationConfidence.UNKNOWN,
                fallback_used=False,
                city=None,
                region=None,
                country=None,
                error="Empty location provided"
            )
        
        original = location.strip()
        normalized = original.lower()
        
        # Check for common aliases first
        if normalized in self.CITY_ALIASES:
            expanded = self.CITY_ALIASES[normalized]
            return self._parse_location(expanded, original, fallback_used=False)
        
        # Check for country codes
        if normalized in self.COUNTRY_CODES:
            return LocationResult(
                original=original,
                normalized=self.COUNTRY_CODES[normalized],
                search_query=self.COUNTRY_CODES[normalized],
                confidence=LocationConfidence.COUNTRY,
                fallback_used=False,
                city=None,
                region=None,
                country=self.COUNTRY_CODES[normalized]
            )
        
        # Parse as "City, State" or "City, State, Country"
        return self._parse_location(original, original, fallback_used=False)
    
    def _parse_location(
        self, 
        location: str, 
        original: str,
        fallback_used: bool = False
    ) -> LocationResult:
        """Parse a location string into components."""
        
        # Split by comma
        parts = [p.strip() for p in location.split(",")]
        
        city = None
        region = None
        country = None
        confidence = LocationConfidence.EXACT
        
        if len(parts) >= 3:
            # City, State, Country
            city = parts[0]
            region = self._normalize_region(parts[1])
            country = parts[2]
        elif len(parts) == 2:
            # City, State (assume US) or City, Country
            city = parts[0]
            second = parts[1].strip().upper()
            
            if second in self.US_STATES:
                region = self.US_STATES[second]
                country = "USA"
            elif second.lower() in self._state_name_to_abbr:
                region = second
                country = "USA"
            elif second.lower() in self.COUNTRY_CODES:
                country = self.COUNTRY_CODES[second.lower()]
            else:
                # Assume it's a region/state name
                region = second
        else:
            # Single location - could be city or region
            single = location.strip()
            upper = single.upper()
            
            if upper in self.US_STATES:
                region = self.US_STATES[upper]
                country = "USA"
                confidence = LocationConfidence.REGION
            elif single.lower() in self._state_name_to_abbr:
                region = single
                country = "USA"
                confidence = LocationConfidence.REGION
            else:
                city = single
                # Could be anything, mark as exact but may fail
        
        # Build normalized string
        normalized_parts = []
        if city:
            normalized_parts.append(city.title())
        if region:
            normalized_parts.append(region)
        if country:
            normalized_parts.append(country)
        
        normalized = ", ".join(normalized_parts) if normalized_parts else location
        
        # Build search query optimized for Google Maps
        search_query = normalized
        
        return LocationResult(
            original=original,
            normalized=normalized,
            search_query=search_query,
            confidence=confidence,
            fallback_used=fallback_used,
            city=city.title() if city else None,
            region=region,
            country=country
        )
    
    def _normalize_region(self, region: str) -> str:
        """Normalize region/state string."""
        upper = region.strip().upper()
        if upper in self.US_STATES:
            return self.US_STATES[upper]
        return region.strip().title()
    
    def get_fallback_locations(self, location_result: LocationResult) -> List[str]:
        """
        Get fallback locations in order of specificity.
        
        Returns list of locations to try if primary search fails:
        1. Original city
        2. Metro area (if applicable)
        3. Region/State
        4. Country
        """
        fallbacks = []
        
        # 1. Original stays first (already tried)
        # 2. Try metro area if city has one
        if location_result.city:
            city_lower = location_result.city.lower()
            if city_lower in self.METRO_AREAS:
                metro = self.METRO_AREAS[city_lower]
                if location_result.region:
                    fallbacks.append(f"{metro}, {location_result.region}")
                else:
                    fallbacks.append(metro)
        
        # 3. Region only
        if location_result.region:
            if location_result.country:
                fallbacks.append(f"{location_result.region}, {location_result.country}")
            else:
                fallbacks.append(location_result.region)
        
        # 4. Country only
        if location_result.country:
            fallbacks.append(location_result.country)
        
        return fallbacks
    
    def format_for_google_maps(self, query: str, location_result: LocationResult) -> str:
        """
        Format search query for Google Maps URL.
        
        Args:
            query: Business type (e.g., "restaurants", "plumbers")
            location_result: Validated location
            
        Returns:
            Formatted search string for Google Maps URL
        """
        # Use the search_query from location result
        return f"{query} near {location_result.search_query}"
    
    def get_geo_bias_params(self, location_result: LocationResult) -> Dict[str, str]:
        """
        Get parameters for geo-biasing the search.
        
        This can be used to add additional URL parameters for better results.
        """
        params = {}
        
        # Add language hint for non-English speaking countries
        country = (location_result.country or "").lower()
        if country in ["germany", "de"]:
            params["hl"] = "de"
        elif country in ["france", "fr"]:
            params["hl"] = "fr"
        elif country in ["spain", "es", "mexico", "mx"]:
            params["hl"] = "es"
        elif country in ["italy", "it"]:
            params["hl"] = "it"
        elif country in ["brazil", "br"]:
            params["hl"] = "pt-BR"
        elif country in ["japan", "jp"]:
            params["hl"] = "ja"
        elif country in ["china", "cn"]:
            params["hl"] = "zh-CN"
        # Default to English
        
        return params


# Singleton instance
_location_service: Optional[LocationService] = None

def get_location_service() -> LocationService:
    """Get or create the location service singleton."""
    global _location_service
    if _location_service is None:
        _location_service = LocationService()
    return _location_service
