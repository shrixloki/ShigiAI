#!/usr/bin/env python3
import sys
sys.path.append('cold_outreach_agent')

from services.db_service import DatabaseService

db = DatabaseService()
outreach_leads = db.get_approved_leads_for_outreach()

print(f"🎯 LEADS READY FOR OUTREACH: {len(outreach_leads)}")
print("=" * 50)

if outreach_leads:
    for i, lead in enumerate(outreach_leads[:10], 1):
        print(f"{i}. {lead['business_name']}")
        print(f"   📧 Email: {lead['email']}")
        print(f"   📍 Location: {lead.get('location', 'N/A')}")
        print()
else:
    print("❌ No leads ready for outreach!")
    print()
    print("Checking why...")
    
    # Check all approved leads
    approved = db.get_leads_by_review_status('approved')
    print(f"📊 Total approved leads: {len(approved)}")
    
    # Check which ones have emails
    with_email = [l for l in approved if l.get('email') and l.get('email').strip()]
    print(f"📧 Approved leads with email: {len(with_email)}")
    
    # Check outreach status
    not_sent = [l for l in with_email if l.get('outreach_status') == 'not_sent']
    print(f"🚀 Approved + Email + Not Sent: {len(not_sent)}")
    
    if with_email:
        print("\n📧 Leads with emails:")
        for lead in with_email[:5]:
            print(f"- {lead['business_name']}: {lead['email']} (status: {lead.get('outreach_status', 'unknown')})")
    
    if not with_email:
        print("\n💡 Need to run website analysis to extract emails!")
        print("Run: python main.py analyze")