#!/usr/bin/env python3
"""
Production-grade startup script for Cold Outreach Agent.
Handles service initialization, health checks, and graceful shutdown.
"""

import asyncio
import os
import signal
import sys
import time
from pathlib import Path
from typing import Optional

import uvicorn
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "cold_outreach_agent"))

from cold_outreach_agent.config.production_settings import settings
from cold_outreach_agent.infrastructure.database.service import ProductionDatabaseService
from cold_outreach_agent.infrastructure.logging.service import ProductionLoggingService

console = Console()


class ProductionLauncher:
    """Production launcher with health checks and monitoring."""
    
    def __init__(self):
        self.db_service: Optional[ProductionDatabaseService] = None
        self.logging_service: Optional[ProductionLoggingService] = None
        self.server_process = None
        self.is_running = False
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        console.print(f"\\n[yellow]Received signal {signum}, initiating graceful shutdown...[/yellow]")
        self.is_running = False
    
    async def validate_environment(self) -> bool:
        """Validate environment and configuration."""
        
        console.print("[blue]Validating environment...[/blue]")
        
        # Check Python version
        if sys.version_info < (3, 8):
            console.print("[red]✗ Python 3.8+ required[/red]")
            return False
        
        console.print(f"[green]✓ Python {sys.version.split()[0]}[/green]")
        
        # Validate configuration
        validation_summary = settings.get_validation_summary()
        
        if not validation_summary["is_valid"]:
            console.print("[red]✗ Configuration validation failed:[/red]")
            for section, errors in validation_summary["errors_by_section"].items():
                for error in errors:
                    console.print(f"  [red]•[/red] {section}: {error}")
            return False
        
        console.print("[green]✓ Configuration valid[/green]")
        
        # Check required directories
        required_dirs = [
            settings.database.path.parent,
            settings.logging.log_dir,
        ]
        
        for directory in required_dirs:
            if not directory.exists():
                try:
                    directory.mkdir(parents=True, exist_ok=True)
                    console.print(f"[green]✓ Created directory: {directory}[/green]")
                except Exception as e:
                    console.print(f"[red]✗ Failed to create directory {directory}: {e}[/red]")
                    return False
            else:
                console.print(f"[green]✓ Directory exists: {directory}[/green]")
        
        return True
    
    async def initialize_services(self) -> bool:
        """Initialize core services."""
        
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
                progress.update(task, description="[green]✓ Logging service initialized[/green]")
                
                # Initialize database
                task = progress.add_task("Initializing database...", total=None)
                self.db_service = ProductionDatabaseService(settings.database.path)
                await self.db_service.initialize()
                progress.update(task, description="[green]✓ Database initialized[/green]")
                
                # Run health checks
                task = progress.add_task("Running health checks...", total=None)
                health_ok = await self.run_health_checks()
                if health_ok:
                    progress.update(task, description="[green]✓ Health checks passed[/green]")
                else:
                    progress.update(task, description="[red]✗ Health checks failed[/red]")
                    return False
            
            return True
            
        except Exception as e:
            console.print(f"[red]Service initialization failed: {e}[/red]")
            if self.logging_service:
                self.logging_service.log_error(e, component="launcher", operation="initialize_services")
            return False
    
    async def run_health_checks(self) -> bool:
        """Run comprehensive health checks."""
        
        checks_passed = 0
        total_checks = 3
        
        # Database health check
        try:
            from cold_outreach_agent.core.models.common import PaginationParams
            await self.db_service.get_leads(pagination=PaginationParams(page=1, page_size=1))
            checks_passed += 1
        except Exception as e:
            console.print(f"[red]✗ Database health check failed: {e}[/red]")
        
        # Configuration health check
        validation_summary = settings.get_validation_summary()
        if validation_summary["is_valid"]:
            checks_passed += 1
        else:
            console.print("[red]✗ Configuration health check failed[/red]")
        
        # File system health check
        try:
            # Test write permissions
            test_file = settings.logging.log_dir / "health_check.tmp"
            test_file.write_text("health check", encoding='utf-8')
            test_file.unlink()
            checks_passed += 1
        except Exception as e:
            console.print(f"[red]✗ File system health check failed: {e}[/red]")
        
        return checks_passed == total_checks
    
    def start_api_server(self):
        """Start the FastAPI server."""
        
        try:
            console.print(f"[blue]Starting API server on {settings.system.environment} environment...[/blue]")
            
            # Import the production server
            from cold_outreach_agent.api.production_server import app
            
            # Configure server settings
            server_config = {
                "app": app,
                "host": "0.0.0.0",
                "port": 8000,
                "log_level": settings.logging.level.lower(),
                "access_log": settings.logging.log_api_requests,
                "reload": settings.system.debug and settings.system.environment == "development",
                "workers": 1,  # Single worker for SQLite compatibility
            }
            
            # Add SSL configuration for production
            if settings.system.environment == "production":
                # SSL configuration would go here
                pass
            
            self.is_running = True
            
            # Log startup
            if self.logging_service:
                self.logging_service.log_application_event(
                    "Production server starting",
                    component="launcher",
                    operation="start_server",
                    environment=settings.system.environment,
                    debug_mode=settings.system.debug
                )
            
            # Start server
            uvicorn.run(**server_config)
            
        except Exception as e:
            console.print(f"[red]Failed to start API server: {e}[/red]")
            if self.logging_service:
                self.logging_service.log_error(e, component="launcher", operation="start_server")
            raise
    
    async def cleanup(self):
        """Clean up resources."""
        
        try:
            console.print("[blue]Cleaning up resources...[/blue]")
            
            if self.logging_service:
                self.logging_service.log_application_event(
                    "Production server shutting down",
                    component="launcher",
                    operation="cleanup"
                )
            
            # Cleanup would go here
            console.print("[green]✓ Cleanup completed[/green]")
            
        except Exception as e:
            console.print(f"[red]Cleanup error: {e}[/red]")
    
    async def run(self):
        """Main run method."""
        
        try:
            # Display startup banner
            banner = Panel(
                f"Cold Outreach Agent v1.0.0\\n"
                f"Environment: {settings.system.environment}\\n"
                f"Debug Mode: {settings.system.debug}",
                title="Production Startup",
                border_style="blue"
            )
            console.print(banner)
            
            # Validate environment
            if not await self.validate_environment():
                console.print("[red]Environment validation failed. Exiting.[/red]")
                return 1
            
            # Initialize services
            if not await self.initialize_services():
                console.print("[red]Service initialization failed. Exiting.[/red]")
                return 1
            
            # Start API server
            console.print("[green]✓ All systems ready. Starting API server...[/green]")
            console.print("[dim]Press Ctrl+C to stop the server[/dim]")
            
            self.start_api_server()
            
            return 0
            
        except KeyboardInterrupt:
            console.print("\\n[yellow]Shutdown requested by user[/yellow]")
            return 0
        
        except Exception as e:
            console.print(f"[red]Startup failed: {e}[/red]")
            if settings.system.debug:
                import traceback
                console.print(traceback.format_exc())
            return 1
        
        finally:
            await self.cleanup()


async def main():
    """Main entry point."""
    launcher = ProductionLauncher()
    return await launcher.run()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))