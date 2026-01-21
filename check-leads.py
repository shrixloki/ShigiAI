#!/usr/bin/env python3
import sys
sys.path.append('cold_outreach_agent')

from services.db_service import DatabaseService

db = DatabaseService()
leads = db.get_all_leads()

print(f"🎯 TOTAL LEADS FOUND: {len(leads)}")
print("=" * 50)

if leads:
    for i, lead in enumerate(leads[:10], 1):
        status = lead.get('review_status', 'unknown')
        source = lead.get('discovery_source', 'unknown')
        print(f"{i}. {lead['business_name']}")
        print(f"   📧 Email: {lead.get('email', 'Not found yet')}")
        print(f"   📍 Location: {lead.get('location', 'N/A')}")
        print(f"   🏷️  Status: {status}")
        print(f"   🔍 Source: {source}")
        print()
    
    if len(leads) > 10:
        print(f"... and {len(leads) - 10} more leads!")
    
    counts = db.get_lead_counts()
    print("📊 SUMMARY:")
    print(f"   Pending Review: {counts['pending_review']}")
    print(f"   Approved: {counts['approved']}")
    print(f"   Rejected: {counts['rejected']}")
else:
    print("No leads found yet. Discovery might still be running...")
    print("Check http://localhost:5173 for real-time updates!")