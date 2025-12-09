#!/usr/bin/env python3
"""
Main entry point for Sifra Advanced
"""

import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sifra.crew import SifraAdvCrew


def main():
    """
    Main function to run Sifra Advanced
    """
    print("🚀 Starting Sifra Advanced...")
    print("=" * 50)
    
    try:
        # Initialize the crew
        crew = SifraAdvCrew()
        
        # Run the crew
        result = crew.run()
        
        print("✅ Sifra Advanced completed successfully!")
        print(f"Result: {result}")
        
    except Exception as e:
        print(f"❌ Error running Sifra Advanced: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
