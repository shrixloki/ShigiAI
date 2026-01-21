"""Desktop application main entry point."""

import asyncio
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Optional

import uvicorn
from rich.console import Console
from rich.panel import Panel

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from cold_outreach_agent.config.production_settings import ProductionSettings
from cold_outreach_agent.api.production_server import app as fastapi_app
from cold_outreach_agent.core.exceptions import ConfigurationError


console = Console()


class DesktopApplication:
    """Desktop application manager."""
    
    def __init__(self):
        self.settings: Optional[ProductionSettings] = None
        self.server_thread: Optional[threading.Thread] = None
        self.server_process = None
        self.port = 8000
        self.host = "127.0.0.1"
        self.running = False
        
    def start(self):
        """Start the desktop application."""
        try:
            console.print(Panel.fit(
                "[bold blue]Cold Outreach Agent[/bold blue]\n"
                "[dim]Production-Grade Lead Discovery & Email Outreach[/dim]",
                border_style="blue"
            ))
            
            # Load and validate configuration
            self._load_configuration()
            
            # Start the web server
            self._start_web_server()
            
            # Open browser
            self._open_browser()
            
            # Keep application running
            self._run_main_loop()
            
        except KeyboardInterrupt:
            console.print("\n[yellow]Shutting down...[/yellow]")
            self.shutdown()
        except Exception as e:
            console.print(f"[red]Application error: {str(e)}[/red]")
            self.shutdown()
            sys.exit(1)
    
    def _load_configuration(self):
        """Load and validate configuration."""
        try:
            # Set working directory to the executable directory
            if getattr(sys, 'frozen', False):
                # Running as compiled executable
                app_dir = Path(sys.executable).parent
            else:
                # Running as script
                app_dir = Path(__file__).parent.parent.parent
            
            os.chdir(app_dir)
            
            # Load settings
            env_file = app_dir / ".env"
            if not env_file.exists():
                console.print("[yellow]Warning: .env file not found. Using default settings.[/yellow]")
                console.print("[dim]Copy .env.example to .env and configure your settings.[/dim]")
            
            self.settings = ProductionSettings(env_file if env_file.exists() else None)
            
            # Validate configuration
            validation_summary = self.settings.get_validation_summary()
            
            if not validation_summary["is_valid"]:
                console.print("[red]Configuration errors found:[/red]")
                for section, errors in validation_summary["errors_by_section"].items():
                    for error in errors:
                        console.print(f"  [red]•[/red] {section}: {error}")
                
                console.print("\n[yellow]Please fix configuration errors in .env file[/yellow]")
                
                # Don't exit immediately - let user see the web interface for configuration
                console.print("[dim]Starting with default settings. Configure via web interface.[/dim]")
            
            console.print("[green]✓ Configuration loaded[/green]")
            
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration: {str(e)}")
    
    def _start_web_server(self):
        """Start the FastAPI web server in a separate thread."""
        
        def run_server():
            """Run the uvicorn server."""
            try:
                # Configure uvicorn to run without the default signal handlers
                # since we're running in a thread
                config = uvicorn.Config(
                    app=fastapi_app,
                    host=self.host,
                    port=self.port,
                    log_level="info" if self.settings.system.debug else "warning",
                    access_log=False,  # Disable access logs for cleaner output
                    reload=False,
                    loop="asyncio"
                )
                
                server = uvicorn.Server(config)
                
                # Store server reference for shutdown
                self.server_process = server
                
                # Run the server
                asyncio.run(server.serve())
                
            except Exception as e:
                console.print(f"[red]Server error: {str(e)}[/red]")
                self.running = False
        
        # Start server in background thread
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        
        # Wait for server to start
        max_wait = 10  # seconds
        wait_time = 0
        
        while wait_time < max_wait:
            try:
                import requests
                response = requests.get(f"http://{self.host}:{self.port}/health", timeout=1)
                if response.status_code == 200:
                    break
            except:
                pass
            
            time.sleep(0.5)
            wait_time += 0.5
        
        if wait_time >= max_wait:
            raise RuntimeError("Failed to start web server")
        
        console.print(f"[green]✓ Web server started on http://{self.host}:{self.port}[/green]")
        self.running = True
    
    def _open_browser(self):
        """Open the web interface in the default browser."""
        
        url = f"http://{self.host}:{self.port}"
        
        try:
            # Wait a moment for server to be fully ready
            time.sleep(1)
            
            # Open browser
            webbrowser.open(url)
            console.print(f"[green]✓ Opened browser to {url}[/green]")
            
        except Exception as e:
            console.print(f"[yellow]Could not open browser automatically: {str(e)}[/yellow]")
            console.print(f"[dim]Please manually navigate to: {url}[/dim]")
    
    def _run_main_loop(self):
        """Run the main application loop."""
        
        console.print("\n[green]Application is running![/green]")
        console.print(f"[dim]Web interface: http://{self.host}:{self.port}[/dim]")
        console.print("[dim]Press Ctrl+C to stop[/dim]\n")
        
        try:
            # Keep the main thread alive
            while self.running:
                time.sleep(1)
                
                # Check if server thread is still alive
                if self.server_thread and not self.server_thread.is_alive():
                    console.print("[red]Server thread died unexpectedly[/red]")
                    break
                    
        except KeyboardInterrupt:
            pass
    
    def shutdown(self):
        """Shutdown the application gracefully."""
        
        console.print("[yellow]Shutting down application...[/yellow]")
        
        self.running = False
        
        # Stop the server
        if self.server_process:
            try:
                self.server_process.should_exit = True
                console.print("[green]✓ Server stopped[/green]")
            except Exception as e:
                console.print(f"[yellow]Warning: Error stopping server: {str(e)}[/yellow]")
        
        # Wait for server thread to finish
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=5)
        
        console.print("[green]✓ Application shutdown complete[/green]")


def main():
    """Main entry point for desktop application."""
    
    # Handle command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] in ["--help", "-h"]:
            print("Cold Outreach Agent - Desktop Application")
            print("Usage: ColdOutreachAgent [options]")
            print("")
            print("Options:")
            print("  --help, -h     Show this help message")
            print("  --version, -v  Show version information")
            print("  --config       Show configuration path")
            print("")
            print("Configuration:")
            print("  Edit the .env file in the application directory")
            print("  Copy .env.example to .env to get started")
            return
        
        elif sys.argv[1] in ["--version", "-v"]:
            print("Cold Outreach Agent v1.0.0")
            print("Production-Grade Lead Discovery & Email Outreach Platform")
            return
        
        elif sys.argv[1] == "--config":
            if getattr(sys, 'frozen', False):
                config_path = Path(sys.executable).parent / ".env"
            else:
                config_path = Path(__file__).parent.parent.parent / ".env"
            
            print(f"Configuration file: {config_path}")
            print(f"Exists: {config_path.exists()}")
            return
    
    # Create and start the desktop application
    app = DesktopApplication()
    app.start()


if __name__ == "__main__":
    main()