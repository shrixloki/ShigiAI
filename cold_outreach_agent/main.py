"""CLI entry point for the cold outreach automation agent."""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import settings
from modules import (
    action_logger,
    ScoutModule,
    AnalystModule,
    MessengerModule,
    FollowUpModule,
    ReplyDetectorModule,
    HunterModule,
    WebsiteAnalyzerModule,
)
from services.db_service import DatabaseService


def validate_config() -> bool:
    """Validate configuration before running."""
    errors = settings.validate()
    if errors:
        print(f"Configuration error: Missing required settings: {', '.join(errors)}")
        print("Please check your .env file.")
        return False
    return True


def cmd_discover(args):
    """Run hunter module to discover businesses from maps."""
    if not args.query or not args.location:
        print("Error: --query and --location are required")
        return 1
    
    print(f"Discovering: {args.query} in {args.location}")
    print("This may take a few minutes...\n")
    
    hunter = HunterModule()
    result = hunter.discover_sync(
        query=args.query,
        location=args.location,
        max_results=args.max or 50
    )
    
    print(f"\nDiscovery Results:")
    print(f"  Discovered: {result['discovered']}")
    print(f"  Skipped (duplicates): {result['skipped']}")
    print(f"  Errors: {len(result['errors'])}")
    
    if result['errors']:
        print("\nErrors:")
        for err in result['errors'][:5]:
            print(f"  - {err}")
    
    print("\nNote: All discovered leads are PENDING review.")
    print("Use the dashboard to approve leads before outreach.")
    
    return 0


def cmd_analyze(args):
    """Run website analyzer to extract emails and classify sites."""
    print("Analyzing websites for pending leads...")
    
    analyzer = WebsiteAnalyzerModule()
    result = analyzer.analyze_all_pending()
    
    print(f"\nAnalysis Results:")
    print(f"  Analyzed: {result['analyzed']}")
    print(f"  Emails found: {result['emails_found']}")
    print(f"  Errors: {result['errors']}")
    
    return 0


def cmd_scout(args):
    """Run scout module to import leads from CSV."""
    if not args.source:
        print("Error: --source CSV file path required")
        return 1
    
    scout = ScoutModule()
    result = scout.import_from_csv(args.source)
    
    print(f"\nScout Results:")
    print(f"  Imported: {result['imported']}")
    print(f"  Skipped (duplicates): {result['skipped']}")
    print(f"  Errors: {len(result['errors'])}")
    
    if result['errors']:
        print("\nErrors:")
        for err in result['errors'][:10]:
            print(f"  - {err}")
    
    print("\nNote: All imported leads are PENDING review.")
    
    return 0


def cmd_approve(args):
    """Approve leads for outreach."""
    db = DatabaseService()
    
    if args.all:
        pending = db.get_leads_by_review_status('pending')
        count = db.bulk_approve_leads([l['lead_id'] for l in pending])
        print(f"Approved {count} leads")
    elif args.lead_id:
        if db.approve_lead(args.lead_id):
            print(f"Lead {args.lead_id} approved")
        else:
            print(f"Failed to approve lead {args.lead_id}")
    else:
        print("Error: Specify --lead-id or --all")
        return 1
    
    return 0


def cmd_reject(args):
    """Reject leads."""
    db = DatabaseService()
    
    if args.lead_id:
        if db.reject_lead(args.lead_id):
            print(f"Lead {args.lead_id} rejected")
        else:
            print(f"Failed to reject lead {args.lead_id}")
    else:
        print("Error: Specify --lead-id")
        return 1
    
    return 0


def cmd_status(args):
    """Show lead status summary."""
    db = DatabaseService()
    counts = db.get_lead_counts()
    
    print("\nLead Status Summary:")
    print(f"  Total leads: {counts['total']}")
    print(f"  Pending review: {counts['pending_review']}")
    print(f"  Approved: {counts['approved']}")
    print(f"  Rejected: {counts['rejected']}")
    print(f"  Sent initial: {counts['sent_initial']}")
    print(f"  Sent follow-up: {counts['sent_followup']}")
    print(f"  Replied: {counts['replied']}")
    print(f"\n  Emails sent today: {db.get_emails_sent_today()}")
    
    return 0


def cmd_messenger(args):
    """Run messenger module to send initial emails to APPROVED leads."""
    db = DatabaseService()
    approved = db.get_approved_leads_for_outreach()
    
    if not approved:
        print("No approved leads ready for outreach.")
        print("Use 'approve --all' or the dashboard to approve leads first.")
        return 0
    
    print(f"Sending emails to {len(approved)} approved leads...")
    
    messenger = MessengerModule()
    result = messenger.send_all_pending()
    
    print(f"\nMessenger Results:")
    print(f"  Sent: {result['sent']}")
    print(f"  Skipped: {result['skipped']}")
    print(f"  Errors: {result['errors']}")
    
    if result.get('rate_limited'):
        print("  Note: Daily rate limit reached")
    
    return 0


def cmd_followup(args):
    """Run follow-up module."""
    followup = FollowUpModule()
    result = followup.send_all_followups()
    
    print(f"\nFollow-up Results:")
    print(f"  Sent: {result['sent']}")
    print(f"  Skipped: {result['skipped']}")
    print(f"  Errors: {result['errors']}")
    
    if result.get('rate_limited'):
        print("  Note: Daily rate limit reached")
    
    return 0


def cmd_replies(args):
    """Run reply detector module."""
    detector = ReplyDetectorModule()
    result = detector.check_all_replies()
    
    print(f"\nReply Detection Results:")
    print(f"  Replies found: {result['replies_found']}")
    print(f"  Leads checked: {result['checked']}")
    
    return 0


def cmd_outreach(args):
    """Run outreach pipeline: replies -> messenger -> followup."""
    db = DatabaseService()
    approved = db.get_approved_leads_for_outreach()
    
    if not approved:
        print("No approved leads ready for outreach.")
        return 0
    
    print(f"Running outreach for {len(approved)} approved leads...\n")
    
    # 1. Check for replies first
    print("Step 1: Checking for replies...")
    detector = ReplyDetectorModule()
    replies_result = detector.check_all_replies()
    print(f"  Found {replies_result['replies_found']} replies\n")
    
    # 2. Send initial emails to APPROVED leads
    print("Step 2: Sending initial emails...")
    messenger = MessengerModule()
    messenger_result = messenger.send_all_pending()
    print(f"  Sent {messenger_result['sent']} emails\n")
    
    # 3. Send follow-ups
    print("Step 3: Sending follow-ups...")
    followup = FollowUpModule()
    followup_result = followup.send_all_followups()
    print(f"  Sent {followup_result['sent']} follow-ups\n")
    
    print("Outreach complete.")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Cold Outreach Automation Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py discover --query "restaurants" --location "Austin, TX"
  python main.py analyze
  python main.py scout --source leads.csv
  python main.py approve --all
  python main.py status
  python main.py outreach
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Discover command
    discover_parser = subparsers.add_parser("discover", help="Discover businesses from maps")
    discover_parser.add_argument("--query", "-q", required=True, help="Business category")
    discover_parser.add_argument("--location", "-l", required=True, help="Location to search")
    discover_parser.add_argument("--max", "-m", type=int, default=50, help="Max results")
    
    # Analyze command
    subparsers.add_parser("analyze", help="Analyze websites and extract emails")
    
    # Scout command
    scout_parser = subparsers.add_parser("scout", help="Import leads from CSV")
    scout_parser.add_argument("--source", "-s", help="Path to CSV file")
    
    # Approve command
    approve_parser = subparsers.add_parser("approve", help="Approve leads for outreach")
    approve_parser.add_argument("--lead-id", help="Specific lead ID to approve")
    approve_parser.add_argument("--all", action="store_true", help="Approve all pending leads")
    
    # Reject command
    reject_parser = subparsers.add_parser("reject", help="Reject a lead")
    reject_parser.add_argument("--lead-id", required=True, help="Lead ID to reject")
    
    # Status command
    subparsers.add_parser("status", help="Show lead status summary")
    
    # Messenger command
    subparsers.add_parser("messenger", help="Send initial emails to approved leads")
    
    # Follow-up command
    subparsers.add_parser("followup", help="Send follow-up emails")
    
    # Reply detector command
    subparsers.add_parser("replies", help="Check for replies")
    
    # Outreach command
    subparsers.add_parser("outreach", help="Run full outreach pipeline")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Validate config for email-related commands
    email_commands = ['messenger', 'followup', 'replies', 'outreach']
    if args.command in email_commands and not validate_config():
        return 1
    
    # Route to command handler
    commands = {
        "discover": cmd_discover,
        "analyze": cmd_analyze,
        "scout": cmd_scout,
        "approve": cmd_approve,
        "reject": cmd_reject,
        "status": cmd_status,
        "messenger": cmd_messenger,
        "followup": cmd_followup,
        "replies": cmd_replies,
        "outreach": cmd_outreach,
    }
    
    handler = commands.get(args.command)
    if handler:
        return handler(args)
    
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
