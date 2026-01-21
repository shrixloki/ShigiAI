#!/usr/bin/env python3
"""Desktop deployment script for Cold Outreach Agent."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from cold_outreach_agent.desktop_app.packager import DesktopPackager
from cold_outreach_agent.core.exceptions import DesktopPackagingError
from rich.console import Console
from rich.panel import Panel

console = Console()


def main():
    """Main deployment function."""
    
    console.print(Panel.fit(
        "[bold blue]Cold Outreach Agent - Desktop Deployment[/bold blue]\n"
        "[dim]Building production-ready desktop application[/dim]",
        border_style="blue"
    ))
    
    try:
        # Create packager
        packager = DesktopPackager()
        
        # Validate build environment
        console.print("[yellow]Validating build environment...[/yellow]")
        validation = packager.validate_build_environment()
        
        if not validation["valid"]:
            console.print("[red]Build environment validation failed:[/red]")
            for error in validation["errors"]:
                console.print(f"  [red]✗[/red] {error}")
            
            if validation["warnings"]:
                console.print("[yellow]Warnings:[/yellow]")
                for warning in validation["warnings"]:
                    console.print(f"  [yellow]⚠[/yellow] {warning}")
            
            console.print("\n[red]Please fix the errors above before building.[/red]")
            return 1
        
        console.print("[green]✓ Build environment validated[/green]")
        
        # Package application
        console.print("\n[yellow]Building desktop application...[/yellow]")
        
        result = packager.package_application(
            app_name="ColdOutreachAgent",
            version="1.0.0",
            include_frontend=True,
            create_installer=True
        )
        
        # Display results
        console.print("\n[green]✓ Desktop application built successfully![/green]")
        console.print(f"[dim]Package: {result['package_path']}[/dim]")
        
        if result.get('installer_path'):
            console.print(f"[dim]Installer: {result['installer_path']}[/dim]")
        
        # Display next steps
        console.print(Panel(
            "[bold green]Deployment Complete![/bold green]\n\n"
            "[white]Next Steps:[/white]\n"
            f"1. Navigate to: {result['package_path']}\n"
            "2. Configure .env file with your email settings\n"
            "3. Run the application:\n"
            "   • Windows: Double-click ColdOutreachAgent.exe or run start.bat\n"
            "   • Mac/Linux: Run ./ColdOutreachAgent or ./start.sh\n\n"
            "[dim]The application will start a web server and open your browser automatically.[/dim]",
            border_style="green"
        ))
        
        return 0
        
    except DesktopPackagingError as e:
        console.print(f"[red]Packaging failed: {e.message}[/red]")
        if e.context:
            console.print(f"[dim]Context: {e.context}[/dim]")
        return 1
        
    except Exception as e:
        console.print(f"[red]Unexpected error: {str(e)}[/red]")
        if "--debug" in sys.argv:
            import traceback
            console.print(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())