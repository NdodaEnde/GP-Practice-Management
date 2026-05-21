"""
GP Practice Scan Sync Agent
============================
Watches a local folder for new scanned documents (PDF, images) and
automatically uploads them to Supabase Storage.

The backend document watcher then auto-detects and processes them
through the LandingAI parsing + extraction pipeline.

Usage:
    python scan_sync.py                     # Uses config from .env
    python scan_sync.py --watch-dir /path   # Override watch directory
    python scan_sync.py --once              # Single scan, no watching

Designed to run on the practice's scanning workstation as:
- A background script
- A Windows service (via NSSM or pywin32)
- A system tray app (future)
"""

import os
import sys
import time
import shutil
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import Set

try:
    from supabase import create_client, Client
except ImportError:
    print("ERROR: supabase package not installed. Run: pip install supabase")
    sys.exit(1)

try:
    from dotenv import load_dotenv
except ImportError:
    print("ERROR: python-dotenv not installed. Run: pip install python-dotenv")
    sys.exit(1)

# =========================================================================
# Configuration
# =========================================================================

ALLOWED_EXTENSIONS = {'.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif'}
DEFAULT_SCAN_DIR = os.path.expanduser('~/GP-Scans')
POLL_INTERVAL = 5  # seconds between folder checks
BUCKET_NAME = 'medical-records'

# =========================================================================
# Setup
# =========================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('scan_sync.log', encoding='utf-8')
    ]
)
logger = logging.getLogger('scan-sync')


def load_config():
    """Load configuration from .env file"""
    # Try multiple .env locations
    env_paths = [
        Path(__file__).parent / '.env',
        Path(__file__).parent.parent / 'backend' / '.env',
        Path.cwd() / '.env',
    ]

    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(env_path)
            logger.info(f"Loaded config from {env_path}")
            break

    # Validate required env vars
    required = ['SUPABASE_URL', 'SUPABASE_SERVICE_KEY']
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        logger.error(f"Missing environment variables: {', '.join(missing)}")
        logger.error("Create a .env file with SUPABASE_URL and SUPABASE_SERVICE_KEY")
        sys.exit(1)


def get_supabase() -> Client:
    """Create Supabase client"""
    return create_client(
        os.environ['SUPABASE_URL'],
        os.environ['SUPABASE_SERVICE_KEY']
    )


# =========================================================================
# Sync Agent
# =========================================================================

class ScanSyncAgent:
    """Watches a folder for new scans and uploads to Supabase Storage"""

    def __init__(self, watch_dir: str, workspace_id: str, poll_interval: int = POLL_INTERVAL):
        self.watch_dir = Path(watch_dir)
        self.workspace_id = workspace_id
        self.poll_interval = poll_interval
        self.supabase = get_supabase()

        # Subdirectories for file lifecycle
        self.uploaded_dir = self.watch_dir / '_uploaded'
        self.failed_dir = self.watch_dir / '_failed'

        # Track files we're currently processing to avoid double-uploads
        self._processing: Set[str] = set()

        # Ensure directories exist
        self.watch_dir.mkdir(parents=True, exist_ok=True)
        self.uploaded_dir.mkdir(exist_ok=True)
        self.failed_dir.mkdir(exist_ok=True)

        logger.info(f"Scan sync agent initialized")
        logger.info(f"  Watch directory: {self.watch_dir}")
        logger.info(f"  Uploaded archive: {self.uploaded_dir}")
        logger.info(f"  Failed archive:   {self.failed_dir}")
        logger.info(f"  Workspace:        {self.workspace_id}")
        logger.info(f"  Bucket:           {BUCKET_NAME}")

    def scan_once(self) -> int:
        """Scan the watch directory and upload any new files. Returns count uploaded."""
        uploaded_count = 0

        for file_path in self.watch_dir.iterdir():
            # Skip directories and hidden files
            if not file_path.is_file():
                continue
            if file_path.name.startswith('.') or file_path.name.startswith('_'):
                continue

            # Check extension
            if file_path.suffix.lower() not in ALLOWED_EXTENSIONS:
                continue

            # Skip if already processing
            if str(file_path) in self._processing:
                continue

            # Skip if file is still being written (size changing)
            if not self._is_file_stable(file_path):
                logger.debug(f"Skipping {file_path.name} — still being written")
                continue

            # Upload
            self._processing.add(str(file_path))
            try:
                success = self._upload_file(file_path)
                if success:
                    self._move_to_uploaded(file_path)
                    uploaded_count += 1
                else:
                    self._move_to_failed(file_path)
            except Exception as e:
                logger.error(f"Error processing {file_path.name}: {e}")
                self._move_to_failed(file_path)
            finally:
                self._processing.discard(str(file_path))

        return uploaded_count

    def watch(self):
        """Continuously watch the folder and upload new files"""
        logger.info(f"Watching {self.watch_dir} for new scans (poll every {self.poll_interval}s)...")
        logger.info("Press Ctrl+C to stop")

        try:
            while True:
                count = self.scan_once()
                if count > 0:
                    logger.info(f"Uploaded {count} file(s)")
                time.sleep(self.poll_interval)
        except KeyboardInterrupt:
            logger.info("Stopped by user")

    def _is_file_stable(self, file_path: Path, wait_seconds: float = 2.0) -> bool:
        """Check if a file has stopped being written to (stable size)"""
        try:
            size1 = file_path.stat().st_size
            time.sleep(wait_seconds)
            size2 = file_path.stat().st_size
            return size1 == size2 and size1 > 0
        except OSError:
            return False

    def _upload_file(self, file_path: Path) -> bool:
        """Upload a single file to Supabase Storage"""
        filename = file_path.name
        file_size = file_path.stat().st_size

        # Generate a unique document path
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        # Storage path: workspace_id/scan_YYYYMMDD_HHMMSS/filename
        storage_folder = f"scan_{timestamp}"
        storage_path = f"{self.workspace_id}/{storage_folder}/{filename}"

        logger.info(f"Uploading {filename} ({file_size / 1024:.1f} KB) → {storage_path}")

        try:
            file_bytes = file_path.read_bytes()

            # Determine content type
            content_type = self._get_content_type(filename)

            self.supabase.storage.from_(BUCKET_NAME).upload(
                path=storage_path,
                file=file_bytes,
                file_options={
                    'content-type': content_type,
                    'cache-control': '3600',
                    'upsert': 'false'
                }
            )

            logger.info(f"Uploaded successfully: {filename}")
            return True

        except Exception as e:
            logger.error(f"Upload failed for {filename}: {e}")
            return False

    def _move_to_uploaded(self, file_path: Path):
        """Move file to the _uploaded archive"""
        dest = self.uploaded_dir / file_path.name

        # Avoid overwriting: add timestamp if name conflicts
        if dest.exists():
            stem = file_path.stem
            suffix = file_path.suffix
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            dest = self.uploaded_dir / f"{stem}_{timestamp}{suffix}"

        shutil.move(str(file_path), str(dest))
        logger.debug(f"Archived to {dest}")

    def _move_to_failed(self, file_path: Path):
        """Move file to the _failed folder for manual inspection"""
        dest = self.failed_dir / file_path.name

        if dest.exists():
            stem = file_path.stem
            suffix = file_path.suffix
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            dest = self.failed_dir / f"{stem}_{timestamp}{suffix}"

        shutil.move(str(file_path), str(dest))
        logger.warning(f"Moved to failed: {dest}")

    @staticmethod
    def _get_content_type(filename: str) -> str:
        ext = Path(filename).suffix.lower()
        types = {
            '.pdf': 'application/pdf',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.tiff': 'image/tiff',
            '.tif': 'image/tiff',
        }
        return types.get(ext, 'application/octet-stream')


# =========================================================================
# CLI
# =========================================================================

def main():
    parser = argparse.ArgumentParser(
        description='GP Practice Scan Sync Agent — uploads scanned documents to Supabase'
    )
    parser.add_argument(
        '--watch-dir',
        default=os.environ.get('SCAN_WATCH_DIR', DEFAULT_SCAN_DIR),
        help=f'Folder to watch for scanned documents (default: {DEFAULT_SCAN_DIR})'
    )
    parser.add_argument(
        '--workspace-id',
        default=os.environ.get('DEMO_WORKSPACE_ID', 'demo-gp-workspace-001'),
        help='Workspace ID for multi-tenant isolation'
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='Scan once and exit (no continuous watching)'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=POLL_INTERVAL,
        help=f'Seconds between folder scans (default: {POLL_INTERVAL})'
    )

    args = parser.parse_args()

    # Load configuration
    load_config()

    # Create and run agent
    agent = ScanSyncAgent(
        watch_dir=args.watch_dir,
        workspace_id=args.workspace_id,
        poll_interval=args.interval
    )

    if args.once:
        count = agent.scan_once()
        logger.info(f"Single scan complete: {count} file(s) uploaded")
    else:
        agent.watch()


if __name__ == '__main__':
    main()
