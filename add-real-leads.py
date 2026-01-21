#!/usr/bin/env python3
"""
Add REAL leads to your Cold Outreach Agent
No mock data - only real business leads you want to contact
"""

import sys
import os
sys.path.append('cold_outreach_agent')

from services.db_service import DatabaseService
from modules.scout import ScoutModule
from datetime import datetime

def add_real_leads():
    """Add real business leads for outreach."""
    
    print("🎯 Cold Outreach Agent - Real Lead Entry")
    print("=" * 50)
    print("Enter REAL business leads you want to contact.")
    print("All leads will be marked as PENDING for your review.")
    print()
    
    scout = ScoutModule()
    db = DatabaseService()
    
    leads_added = 0
    
    while True:
        print(f"\n📝 Lead #{leads_added + 1}")
        print("-" * 20)
        
        # Get business info
        business_name = input("Business Name: ").strip()
        if not business_name:
            print("❌ Business name is required!")
            continue
            
        email = input("Email Address: ").strip()
        if not email or "@" not in email:
            print("❌ Valid email is required!")
            continue
            
        category = input("Category (optional): ").strip()
        location = input("Location (optional): ").strip()
        website = input("Website URL (optional): ").strip()
        
        # Add the lead
        success, message = scout.add_single_lead(
            business_name=business_name,
            email=email,
            category=category,
            location=location,
            website_url=website
        )
        
        if success:
            leads_added += 1
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")
        
        # Ask to continue
        print()
        continue_adding = input("Add another lead? (y/n): ").strip().lower()
        if continue_adding not in ['y', 'yes']:
            break
    
    print(f"\n🎉 Added {leads_added} real leads!")
    print("📊 Go to http://localhost:5173 to review and approve them")
    print("💡 Only approved leads will receive outreach emails")

def import_from_csv():
    """Import real leads from a CSV file."""
    
    print("📁 CSV Import for Real Leads")
    print("=" * 30)
    print("CSV should have columns: business_name, email")
    print("Optional columns: category, location, website_url")
    print()
    
    csv_path = input("Enter CSV file path: ").strip()
    
    if not csv_path:
        print("❌ No file specified")
        return
    
    scout = ScoutModule()
    result = scout.import_from_csv(csv_path)
    
    print(f"\n📊 Import Results:")
    print(f"✅ Imported: {result['imported']}")
    print(f"⏭️  Skipped: {result['skipped']}")
    print(f"❌ Errors: {len(result['errors'])}")
    
    if result['errors']:
        print("\nErrors:")
        for error in result['errors'][:5]:  # Show first 5 errors
            print(f"  • {error}")
    
    if result['imported'] > 0:
        print(f"\n🎉 {result['imported']} real leads imported!")
        print("📊 Go to http://localhost:5173 to review and approve them")

def show_current_leads():
    """Show current leads in the database."""
    
    db = DatabaseService()
    leads = db.get_all_leads()
    
    if not leads:
        print("📭 No leads in database")
        print("💡 Add some real leads first!")
        return
    
    print(f"\n📊 Current Leads ({len(leads)} total)")
    print("=" * 50)
    
    for lead in leads[:10]:  # Show first 10
        status = lead.get('review_status', 'unknown')
        outreach = lead.get('outreach_status', 'unknown')
        print(f"• {lead['business_name']} ({lead['email']})")
        print(f"  Status: {status} | Outreach: {outreach}")
    
    if len(leads) > 10:
        print(f"... and {len(leads) - 10} more")
    
    counts = db.get_lead_counts()
    print(f"\n📈 Summary:")
    print(f"  Pending Review: {counts['pending_review']}")
    print(f"  Approved: {counts['approved']}")
    print(f"  Rejected: {counts['rejected']}")

def main():
    print("🚀 Real Lead Management")
    print("=" * 30)
    print("1. Add leads manually")
    print("2. Import from CSV")
    print("3. Show current leads")
    print("4. Exit")
    
    choice = input("\nChoose option (1-4): ").strip()
    
    if choice == "1":
        add_real_leads()
    elif choice == "2":
        import_from_csv()
    elif choice == "3":
        show_current_leads()
    elif choice == "4":
        print("👋 Goodbye!")
    else:
        print("❌ Invalid choice")

if __name__ == "__main__":
    main()