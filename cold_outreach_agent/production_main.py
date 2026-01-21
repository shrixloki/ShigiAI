"""Production-grade main entry point for the Cold Outreach Agent."""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config.production_settings import settings
from infrastructure.database.service import ProductionDatabaseService
from infrastructure.logging.service import ProductionLoggingService
from infrastructure.email.service import ProductionEmailService
from infrastructure.scraping.google_maps_scraper import ProductionGoogleMapsScraperService
from core.state_machines.lead_state_machine import LeadStateMachine
from core.state_machines.email_state_machine import EmailStateMachine
from core.models.lead import LeadState, ReviewStatus
from core.models.email import EmailState, CampaignType
from core.exceptions import ColdOutreachAgentError

console = Console()


class ProductionApp:
    """Production-grade application manager."""
    
    def __init__(self):
        self.db_service: Optional[ProductionDatabaseService] = None
        self.logging_service: Optional[ProductionLoggingService] = None
        self.email_service: Optional[ProductionEmailService] = None
        self.scraping_service: Optional[ProductionGoogleMapsScraperService] = None
        self.lead_state_machine: Optional[LeadStateMachine] = None
        self.email_state_machine: Optional[EmailStateMachine] = None
        self.analyzer_service: Optional['ProductionWebsiteAnalyzerService'] = None
    
    async def initialize(self):
        """Initialize all services."""
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                
                # Initialize logging
                task = progress.add_task("Initializing logging service...", total=None)
                self.logging_service = ProductionLoggingService(
                    log_dir=settings.logging.log_dir,
                    log_level=settings.logging.level,
                    max_file_size=settings.logging.max_file_size,
                    backup_count=settings.logging.backup_count
                )
                progress.update(task, description="✓ Logging service initialized")
                
                # Initialize database
                task = progress.add_task("Initializing database...", total=None)
                self.db_service = ProductionDatabaseService(settings.database.path)
                await self.db_service.initialize()
                progress.update(task, description="✓ Database initialized")
                
                # Initialize state machines
                task = progress.add_task("Initializing state machines...", total=None)
                self.lead_state_machine = LeadStateMachine(self.db_service, self.logging_service)
                self.email_state_machine = EmailStateMachine(self.db_service, self.logging_service)
                progress.update(task, description="✓ State machines initialized")
                
                # Initialize email service
                task = progress.add_task("Initializing email service...", total=None)
                email_config = {
                    'primary_provider': settings.email.primary_provider,
                    'smtp_host': settings.email.smtp_host,
                    'smtp_port': settings.email.smtp_port,
                    'smtp_username': settings.email.smtp_username,
                    'smtp_password': settings.email.smtp_password,
                    'smtp_use_tls': settings.email.smtp_use_tls,
                    'sender_name': settings.email.sender_name,
                    'sender_email': settings.email.sender_email,
                    'max_emails_per_day': settings.email.max_emails_per_day,
                    'max_emails_per_hour': settings.email.max_emails_per_hour
                }
                self.email_service = ProductionEmailService(
                    db_service=self.db_service,
                    audit_service=self.logging_service,
                    config=email_config
                )
                progress.update(task, description="✓ Email service initialized")
                
                # Initialize scraping service
                task = progress.add_task("Initializing scraping service...", total=None)
                self.scraping_service = ProductionGoogleMapsScraperService()
                progress.update(task, description="✓ Scraping service initialized")
                
                # Initialize website analyzer service
                task = progress.add_task("Initializing website analyzer...", total=None)
                from infrastructure.scraping.website_analyzer import ProductionWebsiteAnalyzerService
                self.analyzer_service = ProductionWebsiteAnalyzerService(self.db_service)
                progress.update(task, description="✓ Website analyzer initialized")
            
            self.logging_service.log_application_event(
                "Application initialized successfully",
                component="main",
                operation="initialize"
            )
            
        except Exception as e:
            if self.logging_service:
                self.logging_service.log_error(e, component="main", operation="initialize")
            raise
    
    async def cleanup(self):
        """Clean up resources."""
        try:
            if self.scraping_service:
                await self.scraping_service._cleanup_browser()
            
            if self.logging_service:
                self.logging_service.log_application_event(
                    "Application cleanup completed",
                    component="main",
                    operation="cleanup"
                )
        except Exception as e:
            if self.logging_service:
                self.logging_service.log_error(e, component="main", operation="cleanup")


# Global app instance
app = ProductionApp()


@click.group()
@click.option('--debug', is_flag=True, help='Enable debug mode')
async def cli(debug):
    """Cold Outreach Agent - Production CLI."""
    if debug:
        settings.system.debug = True
        settings.logging.level = "DEBUG"
    
    # Validate configuration
    validation_summary = settings.get_validation_summary()
    if not validation_summary["is_valid"]:
        console.print("[red]Configuration errors found:[/red]")
        for section, errors in validation_summary["errors_by_section"].items():
            for error in errors:
                console.print(f"  [red]•[/red] {section}: {error}")
        console.print("\\n[yellow]Please fix configuration errors before proceeding.[/yellow]")
        sys.exit(1)
    
    # Initialize application
    await app.initialize()


@cli.command()
@click.option('--query', '-q', required=True, help='Business category to search for')
@click.option('--location', '-l', required=True, help='Location to search in')
@click.option('--max-results', '-m', default=50, help='Maximum number of results')
async def discover(query: str, location: str, max_results: int):
    """Discover businesses from Google Maps."""
    
    try:
        console.print(f"[blue]Discovering {query} in {location}...[/blue]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Searching Google Maps...", total=None)
            
            result = await app.scraping_service.discover_businesses(
                query=query,
                location=location,
                max_results=max_results
            )
            
            if not result.success:
                console.print(f"[red]Discovery failed: {result.error}[/red]")
                return
            
            progress.update(task, description="Saving discovered leads...")
            
            # Save leads to database
            saved_leads = []
            for lead_data in result.data.discovered_leads:
                try:
                    lead = await app.db_service.create_lead(lead_data)
                    saved_leads.append(lead)
                except Exception as e:
                    # Log duplicate errors or others but continue
                    if "already exists" not in str(e):
                        app.logging_service.log_error(e, component="cli", operation="save_lead")
            
            saved_count = len(saved_leads)
        
        # Display results
        table = Table(title="Discovery Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Count", style="green")
        
        table.add_row("Discovered", str(len(result.data.discovered_leads)))
        table.add_row("Saved", str(saved_count))
        table.add_row("Skipped", str(result.data.skipped_count))
        table.add_row("Errors", str(result.data.error_count))
        
        console.print(table)
        
        if result.data.errors:
            console.print("\\n[yellow]Errors encountered:[/yellow]")
            for error in result.data.errors[:5]:
                console.print(f"  [red]•[/red] {error}")
        
        if saved_leads:
            console.print(f"\\n[blue]Analyzing {len(saved_leads)} websites for contact info...[/blue]")
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Analyzing websites...", total=len(saved_leads))
                
                # Run analysis
                lead_ids = [str(l.id) for l in saved_leads if l.website_url]
                if lead_ids:
                    analysis_results = await app.analyzer_service.analyze_leads(lead_ids)
                    
                    found_emails = sum(1 for success in analysis_results.values() if success)
                    console.print(f"[green]Found {found_emails} emails from websites[/green]")
                else:
                    console.print("[yellow]No websites to analyze[/yellow]")
                
                progress.update(task, completed=len(saved_leads))

        console.print("\\n[green]✓ Discovery completed![/green]")
        console.print("[dim]All leads are pending review. Use 'status' command to see details.[/dim]")
    
    except Exception as e:
        app.logging_service.log_error(e, component="cli", operation="discover")
        console.print(f"[red]Discovery failed: {str(e)}[/red]")


@cli.command()
@click.option('--lead-id', help='Specific lead ID to approve')
@click.option('--all', 'approve_all', is_flag=True, help='Approve all pending leads')
async def approve(lead_id: Optional[str], approve_all: bool):
    """Approve leads for outreach."""
    
    try:
        if not lead_id and not approve_all:
            console.print("[red]Please specify --lead-id or --all[/red]")
            return
        
        if approve_all:
            # Get all pending leads
            pending_leads = await app.lead_state_machine.get_leads_by_state(LeadState.PENDING_REVIEW)
            
            if not pending_leads:
                console.print("[yellow]No pending leads found[/yellow]")
                return
            
            console.print(f"[blue]Approving {len(pending_leads)} pending leads...[/blue]")
            
            approved_count = 0
            failed_count = 0
            
            with Progress(console=console) as progress:
                task = progress.add_task("Approving leads...", total=len(pending_leads))
                
                for lead in pending_leads:
                    try:
                        result = await app.lead_state_machine.approve_lead(
                            lead_id=lead.id,
                            actor="cli_user",
                            reason="Bulk approval via CLI"
                        )
                        
                        if result.success:
                            approved_count += 1
                        else:
                            failed_count += 1
                    
                    except Exception as e:
                        app.logging_service.log_error(e, component="cli", operation="approve_lead")
                        failed_count += 1
                    
                    progress.advance(task)
            
            console.print(f"[green]✓ Approved {approved_count} leads[/green]")
            if failed_count > 0:
                console.print(f"[red]✗ Failed to approve {failed_count} leads[/red]")
        
        else:
            # Approve specific lead
            from uuid import UUID
            try:
                lead_uuid = UUID(lead_id)
                result = await app.lead_state_machine.approve_lead(
                    lead_id=lead_uuid,
                    actor="cli_user",
                    reason="Manual approval via CLI"
                )
                
                if result.success:
                    console.print(f"[green]✓ Lead {lead_id} approved[/green]")
                else:
                    console.print(f"[red]✗ Failed to approve lead: {result.error}[/red]")
            
            except ValueError:
                console.print("[red]Invalid lead ID format[/red]")
    
    except Exception as e:
        app.logging_service.log_error(e, component="cli", operation="approve")
        console.print(f"[red]Approval failed: {str(e)}[/red]")


@cli.command()
async def outreach():
    """Send emails to approved leads."""
    
    try:
        # Get approved leads ready for outreach
        ready_leads = await app.lead_state_machine.get_leads_ready_for_outreach()
        
        if not ready_leads:
            console.print("[yellow]No leads ready for outreach[/yellow]")
            console.print("[dim]Use 'approve' command to approve leads first[/dim]")
            return
        
        console.print(f"[blue]Starting outreach for {len(ready_leads)} leads...[/blue]")
        
        sent_count = 0
        failed_count = 0
        
        with Progress(console=console) as progress:
            task = progress.add_task("Sending emails...", total=len(ready_leads))
            
            for lead in ready_leads:
                try:
                    result = await app.email_service.create_and_send_campaign(
                        lead=lead,
                        campaign_type=CampaignType.INITIAL
                    )
                    
                    if result.success:
                        sent_count += 1
                    else:
                        failed_count += 1
                        app.logging_service.log_application_event(
                            f"Email send failed for lead {lead.id}: {result.error}",
                            component="cli",
                            operation="outreach",
                            lead_id=str(lead.id)
                        )
                
                except Exception as e:
                    app.logging_service.log_error(e, component="cli", operation="send_email")
                    failed_count += 1
                
                progress.advance(task)
        
        # Display results
        table = Table(title="Outreach Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Count", style="green")
        
        table.add_row("Emails Sent", str(sent_count))
        table.add_row("Failed", str(failed_count))
        table.add_row("Total Processed", str(len(ready_leads)))
        
        console.print(table)
        
        if sent_count > 0:
            console.print("[green]✓ Outreach completed![/green]")
        
        if failed_count > 0:
            console.print(f"[yellow]⚠ {failed_count} emails failed to send[/yellow]")
    
    except Exception as e:
        app.logging_service.log_error(e, component="cli", operation="outreach")
        console.print(f"[red]Outreach failed: {str(e)}[/red]")


@cli.command()
async def status():
    """Show system status and lead statistics."""
    
    try:
        # Get lead counts by state
        lead_counts = {}
        for state in LeadState:
            leads = await app.lead_state_machine.get_leads_by_state(state)
            lead_counts[state] = len(leads)
        
        # Get email statistics
        email_stats = await app.email_service.get_campaign_statistics()
        
        # Display lead status
        lead_table = Table(title="Lead Status")
        lead_table.add_column("State", style="cyan")
        lead_table.add_column("Count", style="green")
        
        for state, count in lead_counts.items():
            lead_table.add_row(state.replace("_", " ").title(), str(count))
        
        console.print(lead_table)
        
        # Display email status
        email_table = Table(title="Email Status")
        email_table.add_column("Metric", style="cyan")
        email_table.add_column("Count", style="green")
        
        email_table.add_row("Sent Today", str(email_stats.get("sent_today", 0)))
        email_table.add_row("Sent This Hour", str(email_stats.get("sent_this_hour", 0)))
        email_table.add_row("Daily Remaining", str(email_stats.get("daily_remaining", 0)))
        email_table.add_row("Hourly Remaining", str(email_stats.get("hourly_remaining", 0)))
        
        console.print(email_table)
        
        # Display configuration status
        validation_summary = settings.get_validation_summary()
        
        config_panel = Panel(
            f"Environment: {settings.system.environment}\\n"
            f"Debug Mode: {settings.system.debug}\\n"
            f"Configuration: {'✓ Valid' if validation_summary['is_valid'] else '✗ Invalid'}",
            title="System Configuration",
            border_style="green" if validation_summary['is_valid'] else "red"
        )
        
        console.print(config_panel)
    
    except Exception as e:
        app.logging_service.log_error(e, component="cli", operation="status")
        console.print(f"[red]Status check failed: {str(e)}[/red]")


@cli.command()
@click.option('--port', default=8000, help='Port to run server on')
@click.option('--host', default='127.0.0.1', help='Host to bind server to')
async def server(port: int, host: str):
    """Start the web API server."""
    
    try:
        console.print(f"[blue]Starting API server on {host}:{port}...[/blue]")
        
        # Import and run the production server
        import uvicorn
        from api.production_server import app as fastapi_app
        
        uvicorn.run(
            fastapi_app,
            host=host,
            port=port,
            log_level=settings.logging.level.lower(),
            reload=settings.system.debug
        )
    
    except Exception as e:
        app.logging_service.log_error(e, component="cli", operation="server")
        console.print(f"[red]Server failed to start: {str(e)}[/red]")


@cli.command()
async def validate():
    """Validate system configuration."""
    
    validation_summary = settings.get_validation_summary()
    
    if validation_summary["is_valid"]:
        console.print("[green]✓ Configuration is valid[/green]")
    else:
        console.print("[red]✗ Configuration has errors:[/red]")
        
        for section, errors in validation_summary["errors_by_section"].items():
            console.print(f"\\n[yellow]{section.title()}:[/yellow]")
            for error in errors:
                console.print(f"  [red]•[/red] {error}")
    
    # Display configuration summary
    config_table = Table(title="Configuration Summary")
    config_table.add_column("Section", style="cyan")
    config_table.add_column("Status", style="green")
    
    sections = ["database", "email", "scraping", "logging", "security", "system"]
    for section in sections:
        has_errors = section in validation_summary["errors_by_section"]
        status = "✗ Errors" if has_errors else "✓ Valid"
        style = "red" if has_errors else "green"
        config_table.add_row(section.title(), f"[{style}]{status}[/{style}]")
    
    console.print(config_table)


@cli.command()
@click.option('--port', default=8000, help='Port to run server on')
@click.option('--host', default='127.0.0.1', help='Host to bind server to')
async def launch(port: int, host: str):
    """Launch the desktop application (Server + Browser)."""
    import webbrowser
    import uvicorn
    from api.production_server import app as fastapi_app
    
    url = f"http://{host}:{port}"
    console.print(f"[green]Launching Cold Outreach Agent at {url}...[/green]")
    
    # Open browser after a short delay to allow server to start
    async def open_browser():
        await asyncio.sleep(1.5)
        webbrowser.open(url)
        console.print("[dim]Browser opened[/dim]")

    # We need to run the browser opener concurrently with the server
    # Uvicorn blocks, so we schedule the browser opener on the loop before starting uvicorn?
    # Actually uvicorn.run takes control. 
    # Better approach: Threading or specialized uvicorn config.
    # For simplicity, we'll use a thread for opening browser.
    
    import threading
    def browser_thread():
        import time
        time.sleep(1.5)
        webbrowser.open(url)
    
    threading.Thread(target=browser_thread, daemon=True).start()
    
    try:
        # Import and run the production server
        uvicorn.run(
            fastapi_app,
            host=host,
            port=port,
            log_level=settings.logging.level.lower(),
            reload=False # No reload in desktop mode
        )
    except Exception as e:
         console.print(f"[red]Failed to launch: {e}[/red]")



async def main():
    """Main entry point."""
    try:
        await cli()
    except KeyboardInterrupt:
        console.print("\\n[yellow]Operation cancelled by user[/yellow]")
    except Exception as e:
        console.print(f"[red]Application error: {str(e)}[/red]")
        if settings.system.debug:
            import traceback
            console.print(traceback.format_exc())
        sys.exit(1)
    finally:
        await app.cleanup()


if __name__ == "__main__":
    asyncio.run(main())