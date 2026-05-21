"""
Setup script for the GP Scan Sync Agent.
Installs dependencies and configures the watch folder.

Usage:
    python setup.py
"""

import subprocess
import sys
import os
from pathlib import Path


def main():
    print("=" * 50)
    print("GP Practice Scan Sync Agent — Setup")
    print("=" * 50)
    print()

    # 1. Install dependencies
    print("[1/3] Installing Python dependencies...")
    deps = ['supabase', 'python-dotenv']
    for dep in deps:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', dep, '-q'])
    print("  Dependencies installed.")

    # 2. Create .env if it doesn't exist
    env_path = Path(__file__).parent / '.env'
    if not env_path.exists():
        example = Path(__file__).parent / '.env.example'
        if example.exists():
            import shutil
            shutil.copy(str(example), str(env_path))
            print(f"\n[2/3] Created .env file at: {env_path}")
            print("  ** IMPORTANT: Edit .env and fill in your Supabase credentials **")
        else:
            print(f"\n[2/3] No .env.example found — create .env manually")
    else:
        print(f"\n[2/3] .env already exists at: {env_path}")

    # 3. Create default scan folder
    scan_dir = Path.home() / 'GP-Scans'
    scan_dir.mkdir(exist_ok=True)
    (scan_dir / '_uploaded').mkdir(exist_ok=True)
    (scan_dir / '_failed').mkdir(exist_ok=True)

    print(f"\n[3/3] Scan folder ready: {scan_dir}")
    print(f"  Place scanned documents here and they'll be uploaded automatically.")

    print()
    print("=" * 50)
    print("Setup complete!")
    print()
    print("To start the sync agent:")
    print(f"  python scan_sync.py")
    print()
    print("To configure your scanner:")
    print(f"  Set scan destination to: {scan_dir}")
    print()
    print("The agent will:")
    print("  1. Watch the folder for new PDF/image files")
    print("  2. Upload them to Supabase Storage")
    print("  3. Move processed files to _uploaded/")
    print("  4. The backend auto-processes them with LandingAI")
    print("=" * 50)


if __name__ == '__main__':
    main()
