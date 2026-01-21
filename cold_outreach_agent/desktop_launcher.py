"""
Cold Outreach Agent - Desktop Application Launcher

This is the main entry point for the packaged desktop application.
It starts the backend server and opens the browser to the dashboard.
"""

import os
import sys
import time
import socket
import threading
import webbrowser
import subprocess
from pathlib import Path


def get_base_path():
    """Get the base path for the application (handles PyInstaller freezing)."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return Path(sys._MEIPASS)
    else:
        # Running as script
        return Path(__file__).parent


def find_free_port(start_port: int = 8000, max_attempts: int = 10) -> int:
    """Find a free port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"Could not find a free port in range {start_port}-{start_port + max_attempts}")


def wait_for_server(host: str, port: int, timeout: int = 30) -> bool:
    """Wait for the server to become available."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                s.connect((host, port))
                return True
        except (socket.error, socket.timeout):
            time.sleep(0.5)
    return False


def start_server(port: int):
    """Start the FastAPI server using uvicorn."""
    import uvicorn
    from api.server import app
    
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=port,
        log_level="info",
        access_log=False,
    )


def main():
    """Main entry point for the desktop application."""
    print("=" * 50)
    print("  Cold Outreach Agent - Desktop Application")
    print("=" * 50)
    print()
    
    # Ensure we're in the correct directory
    base_path = get_base_path()
    os.chdir(base_path)
    
    # Add to Python path if needed
    if str(base_path) not in sys.path:
        sys.path.insert(0, str(base_path))
    
    # Find a free port
    port = find_free_port(8000)
    url = f"http://127.0.0.1:{port}"
    
    print(f"Starting server on port {port}...")
    
    # Start server in background thread
    server_thread = threading.Thread(target=start_server, args=(port,), daemon=True)
    server_thread.start()
    
    # Wait for server to be ready
    print("Waiting for server to start...")
    if wait_for_server("127.0.0.1", port):
        print(f"Server started successfully!")
        print(f"Opening browser to {url}")
        print()
        print("Press Ctrl+C to stop the server")
        print()
        
        # Open browser
        time.sleep(1)  # Give a small delay for server to fully initialize
        webbrowser.open(url)
        
        # Keep main thread alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")
    else:
        print("ERROR: Server failed to start within timeout period.")
        print("Please check the logs for errors.")
        sys.exit(1)


if __name__ == "__main__":
    main()
