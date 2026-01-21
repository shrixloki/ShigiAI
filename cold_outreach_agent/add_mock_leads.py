#!/usr/bin/env python3
"""Add mock discovered leads for testing."""

from services.db_service import DatabaseService
from datetime import datetime

def add_mock_leads():
    db = DatabaseService()
    
    # Add some mock discovered leads
    mock_leads = [
        {
            'business_name': 'Austin Pizza Co',
            'category': 'Restaurant',
            'location': 'Austin, TX',
            'maps_url': 'https://maps.google.com/place1',
            'website_url': 'https://austinpizza.com',
            'email': 'info@austinpizza.com',
            'discovery_source': 'maps',
            'discovery_confidence': 'high',
            'tag': 'unknown',
            'review_status': 'pending',
            'outreach_status': 'not_sent',
            'discovered_at': datetime.now().isoformat()
        },
        {
            'business_name': 'Taco Bell Downtown',
            'category': 'Restaurant',
            'location': 'Austin, TX',
            'maps_url': 'https://maps.google.com/place2',
            'website_url': '',
            'email': '',
            'discovery_source': 'maps',
            'discovery_confidence': 'medium',
            'tag': 'no_website',
            'review_status': 'pending',
            'outreach_status': 'not_sent',
            'discovered_at': datetime.now().isoformat()
        },
        {
            'business_name': 'Coffee House Central',
            'category': 'Coffee Shop',
            'location': 'Austin, TX',
            'maps_url': 'https://maps.google.com/place3',
            'website_url': 'https://coffeehouse.wix.com',
            'email': 'hello@coffeehouse.com',
            'discovery_source': 'maps',
            'discovery_confidence': 'high',
            'tag': 'outdated_site',
            'review_status': 'pending',
            'outreach_status': 'not_sent',
            'discovered_at': datetime.now().isoformat()
        },
        {
            'business_name': 'Local Plumber Pro',
            'category': 'Plumbing',
            'location': 'Austin, TX',
            'maps_url': 'https://maps.google.com/place4',
            'website_url': 'https://plumberpro.com',
            'email': 'contact@plumberpro.com',
            'discovery_source': 'maps',
            'discovery_confidence': 'high',
            'tag': 'unknown',
            'review_status': 'pending',
            'outreach_status': 'not_sent',
            'discovered_at': datetime.now().isoformat()
        }
    ]
    
    for lead in mock_leads:
        try:
            lead_id = db.add_lead(lead)
            print(f"Added lead: {lead_id} - {lead['business_name']}")
        except Exception as e:
            print(f"Error adding {lead['business_name']}: {e}")
    
    print("Mock discovery leads added successfully!")

if __name__ == "__main__":
    add_mock_leads()