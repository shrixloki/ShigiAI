#!/usr/bin/env python3
"""Simple launcher script to run the Cold Outreach Agent production system."""

import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set environment variable to help with imports
os.environ['PYTHONPATH'] = str(project_root)

# Now import and run the production system
try:
    from cold_outreach_agent.production_main import main
    import asyncio
    
    if __name__ == "__main__":
        print("🚀 Starting Cold Outreach Agent Production System...")
        print(f"📁 Project Root: {project_root}")
        print(f"🐍 Python Path: {sys.path[0]}")
        
        # Run the main application
        sys.exit(asyncio.run(main()))
        
except ImportError as e:
    print(f"❌ Import Error: {e}")
    print("🔧 Trying to fix import paths...")
    
    # Alternative approach - run the start-production.py script
    try:
        exec(open(project_root / "start-production.py").read())
    except Exception as e2:
        print(f"❌ Failed to run start-production.py: {e2}")
        print("📋 Available files:")
        for file in project_root.glob("start*.py"):
            print(f"  - {file.name}")
        sys.exit(1)

except Exception as e:
    print(f"❌ Unexpected error: {e}")
    sys.exit(1)