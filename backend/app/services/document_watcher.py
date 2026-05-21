"""
Document Watcher Service — Automated Document Processing Pipeline

IMPORTANT: This service does NOT auto-process on startup. It only processes
documents that are newly uploaded AFTER the watcher starts. Already-existing
documents in storage are registered but NOT sent to LandingAI unless
explicitly triggered via the API.

Two responsibilities:
1. Storage Scanner: Detects new files in Supabase Storage 'medical-records' bucket
   that don't yet have a digitised_documents record, and registers them (status='uploaded').
   Already-processed files are SKIPPED entirely.
2. Auto-Processor: Picks up documents with status='queued_for_processing' ONLY
   (not 'uploaded') and runs the LandingAI pipeline. Documents must be explicitly
   queued — either by the scan agent setting the status, or via the UI "Process" button.

This prevents accidental credit consumption on every server restart.
"""

import asyncio
import os
import tempfile
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Set

logger = logging.getLogger(__name__)

# Allowed file extensions for auto-processing
ALLOWED_EXTENSIONS = {'.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif'}

# Status that means "already handled, don't touch"
TERMINAL_STATUSES = {'parsed', 'extracted', 'validated', 'approved', 'error', 'parsing', 'extracting'}


class DocumentWatcher:
    """
    Background service that watches Supabase Storage for new documents
    and processes them through the LandingAI pipeline ONLY when explicitly queued.
    """

    def __init__(self, supabase_client, workspace_id: str):
        self.supabase = supabase_client
        self.workspace_id = workspace_id
        self._running = False
        self._scan_interval = int(os.environ.get('WATCHER_SCAN_INTERVAL', '60'))  # 60s default (was 30)
        self._process_interval = int(os.environ.get('WATCHER_PROCESS_INTERVAL', '15'))  # 15s default (was 10)
        self._max_concurrent = int(os.environ.get('WATCHER_MAX_CONCURRENT', '2'))
        self._processing_semaphore = asyncio.Semaphore(self._max_concurrent)
        self._bucket = 'medical-records'
        # Track known file paths to avoid repeated DB lookups
        self._known_paths: Set[str] = set()
        self._initial_scan_done = False
        # Track documents currently being processed to prevent double-processing
        self._processing_ids: Set[str] = set()

    async def start(self):
        """Start the watcher background tasks"""
        self._running = True

        # Load all known file paths from DB on startup (one-time)
        await self._load_known_paths()

        logger.info(
            f"DocumentWatcher started (scan: {self._scan_interval}s, "
            f"process: {self._process_interval}s, "
            f"known files: {len(self._known_paths)})"
        )

        # Run both loops concurrently
        await asyncio.gather(
            self._storage_scan_loop(),
            self._auto_process_loop(),
            return_exceptions=True
        )

    async def stop(self):
        """Stop the watcher gracefully"""
        self._running = False
        logger.info("DocumentWatcher stopping...")

    async def _load_known_paths(self):
        """Load all known file_path values from digitised_documents on startup.
        This prevents re-scanning the entire DB on every poll cycle."""
        try:
            result = self.supabase.table('digitised_documents') \
                .select('file_path') \
                .eq('workspace_id', self.workspace_id) \
                .execute()

            for row in (result.data or []):
                fp = row.get('file_path')
                if fp:
                    self._known_paths.add(fp)

            self._initial_scan_done = True
            logger.info(f"Loaded {len(self._known_paths)} known file paths from DB")
        except Exception as e:
            logger.error(f"Failed to load known paths: {e}")
            self._initial_scan_done = True  # Continue anyway

    # =========================================================================
    # STORAGE SCANNER — Detect new files in Supabase Storage
    # =========================================================================

    async def _storage_scan_loop(self):
        """Periodically scan Supabase Storage for unregistered files"""
        while self._running:
            try:
                await self._scan_storage()
            except Exception as e:
                logger.error(f"Storage scan error: {e}", exc_info=True)

            await asyncio.sleep(self._scan_interval)

    async def _scan_storage(self):
        """
        List files in the medical-records bucket under our workspace
        and register any that don't have a digitised_documents record.
        New files get status='uploaded' (NOT auto-processed).
        """
        try:
            # List top-level items in workspace folder
            files = self.supabase.storage.from_(self._bucket).list(
                path=self.workspace_id,
                options={'limit': 100, 'sortBy': {'column': 'created_at', 'order': 'desc'}}
            )

            if not files:
                return

            new_count = 0
            for item in files:
                if item.get('id') is None:
                    # This is a folder — list its contents
                    folder_name = item.get('name', '')
                    if not folder_name:
                        continue

                    folder_path = f"{self.workspace_id}/{folder_name}"

                    # Quick check: if any known path starts with this folder, skip listing
                    # This avoids listing folders we've already fully processed
                    if self._folder_fully_known(folder_path):
                        continue

                    folder_files = self.supabase.storage.from_(self._bucket).list(
                        path=folder_path,
                        options={'limit': 10}
                    )

                    for file_item in (folder_files or []):
                        if file_item.get('id') is not None:
                            storage_path = f"{folder_path}/{file_item['name']}"
                            if storage_path not in self._known_paths:
                                registered = await self._register_if_new(
                                    storage_path=storage_path,
                                    filename=file_item['name'],
                                    file_size=file_item.get('metadata', {}).get('size'),
                                    folder_hint=folder_name
                                )
                                if registered:
                                    new_count += 1
                            # Either way, add to known set
                            self._known_paths.add(storage_path)
                else:
                    # Direct file in workspace root
                    filename = item.get('name', '')
                    storage_path = f"{self.workspace_id}/{filename}"

                    if storage_path not in self._known_paths:
                        if self._is_allowed_file(filename):
                            registered = await self._register_if_new(
                                storage_path=storage_path,
                                filename=filename,
                                file_size=item.get('metadata', {}).get('size')
                            )
                            if registered:
                                new_count += 1
                        self._known_paths.add(storage_path)

            if new_count > 0:
                logger.info(f"Storage scan found {new_count} new file(s)")

        except Exception as e:
            logger.error(f"Error scanning storage bucket: {e}")

    def _folder_fully_known(self, folder_path: str) -> bool:
        """Check if we already have records for files in this folder"""
        prefix = folder_path + "/"
        return any(p.startswith(prefix) for p in self._known_paths)

    async def _register_if_new(
        self,
        storage_path: str,
        filename: str,
        file_size: Optional[int] = None,
        folder_hint: Optional[str] = None
    ) -> bool:
        """Register a storage file as a digitised_document if not already tracked.
        Returns True if a new record was created."""

        if not self._is_allowed_file(filename):
            return False

        # Double-check DB (in case known_paths missed it)
        existing = self.supabase.table('digitised_documents') \
            .select('id') \
            .eq('file_path', storage_path) \
            .execute()

        if existing.data:
            return False  # Already registered

        # Create new digitised_documents record with status='uploaded'
        # NOTE: 'uploaded' means registered but NOT queued for processing.
        # User must explicitly trigger processing or use status='queued_for_processing'.
        document_id = folder_hint if folder_hint else str(uuid.uuid4())

        # Check if this document_id is already used
        id_check = self.supabase.table('digitised_documents') \
            .select('id') \
            .eq('id', document_id) \
            .execute()

        if id_check.data:
            document_id = str(uuid.uuid4())

        doc_data = {
            'id': document_id,
            'workspace_id': self.workspace_id,
            'filename': filename,
            'file_path': storage_path,
            'file_size': file_size,
            'status': 'uploaded',
            'source': 'storage_watcher',
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat()
        }

        try:
            self.supabase.table('digitised_documents').insert(doc_data).execute()
            logger.info(f"Registered new document: {filename} (id: {document_id}, status: uploaded)")
            return True
        except Exception as e:
            logger.error(f"Failed to register document {filename}: {e}")
            return False

    def _is_allowed_file(self, filename: str) -> bool:
        """Check if file extension is supported for processing"""
        if not filename:
            return False
        ext = Path(filename).suffix.lower()
        return ext in ALLOWED_EXTENSIONS

    # =========================================================================
    # AUTO-PROCESSOR — Only processes documents explicitly queued
    # =========================================================================

    async def _auto_process_loop(self):
        """Periodically pick up documents marked 'queued_for_processing' and run the pipeline.
        Does NOT touch documents with status 'uploaded' — those need explicit action."""
        while self._running:
            try:
                await self._process_queued_documents()
            except Exception as e:
                logger.error(f"Auto-process error: {e}", exc_info=True)

            await asyncio.sleep(self._process_interval)

    async def _process_queued_documents(self):
        """Find documents with status 'queued_for_processing' and process them"""

        # Multi-tenant: process queued docs across ALL workspaces, not just the
        # demo workspace the watcher was originally booted with. Per-doc
        # workspace_id is read from the row and passed into the processor.
        result = self.supabase.table('digitised_documents') \
            .select('id, filename, file_path, file_size, workspace_id') \
            .eq('status', 'queued_for_processing') \
            .order('created_at', desc=False) \
            .limit(self._max_concurrent) \
            .execute()

        if not result.data:
            return

        tasks = []
        for doc in result.data:
            doc_id = doc['id']
            # Skip if already being processed (prevent double-processing)
            if doc_id in self._processing_ids:
                continue
            self._processing_ids.add(doc_id)
            tasks.append(self._process_single_document(doc))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _process_single_document(self, doc: dict):
        """Process a single document through the LandingAI pipeline"""

        async with self._processing_semaphore:
            document_id   = doc['id']
            filename      = doc['filename']
            file_path     = doc['file_path']
            doc_workspace = doc.get('workspace_id') or self.workspace_id  # per-doc, not the watcher's bootstrap workspace

            logger.info(f"Processing document: {filename} (id: {document_id}, workspace: {doc_workspace})")

            try:
                # Update status to 'parsing'
                self.supabase.table('digitised_documents') \
                    .update({
                        'status': 'parsing',
                        'updated_at': datetime.now(timezone.utc).isoformat()
                    }) \
                    .eq('id', document_id) \
                    .execute()

                # Download file from Supabase Storage to temp
                temp_file_path = await self._download_to_temp(file_path, filename, document_id)

                if not temp_file_path:
                    raise Exception(f"Failed to download file from storage: {file_path}")

                # Run GPDocumentProcessor
                from app.services.gp_processor import GPDocumentProcessor
                processor = GPDocumentProcessor(supabase_client=self.supabase)

                result = await processor.process_and_save_patient_file(
                    file_path=str(temp_file_path),
                    filename=filename,
                    organization_id=doc_workspace,
                    document_id=document_id,
                    workspace_id=doc_workspace
                )

                if result.get('success'):
                    update_data = {
                        'status': 'extracted',
                        'parsed_doc_id': result.get('parsed_doc_id'),
                        'pages_count': result.get('pages_processed'),
                        'updated_at': datetime.now(timezone.utc).isoformat()
                    }
                    self.supabase.table('digitised_documents') \
                        .update(update_data) \
                        .eq('id', document_id) \
                        .execute()

                    logger.info(
                        f"Processed {filename}: "
                        f"{result.get('pages_processed')} pages, "
                        f"{len(result.get('chunks', []))} chunks, "
                        f"{result.get('processing_time', 0):.1f}s"
                    )
                else:
                    raise Exception(result.get('error', 'Processing returned failure'))

            except Exception as e:
                logger.error(f"Processing failed for {filename}: {e}")
                self.supabase.table('digitised_documents') \
                    .update({
                        'status': 'error',
                        'error_message': str(e)[:500],
                        'updated_at': datetime.now(timezone.utc).isoformat()
                    }) \
                    .eq('id', document_id) \
                    .execute()

            finally:
                # Remove from processing set
                self._processing_ids.discard(document_id)
                # Clean up temp file
                if 'temp_file_path' in locals() and temp_file_path:
                    try:
                        Path(temp_file_path).unlink(missing_ok=True)
                    except Exception:
                        pass

    async def _download_to_temp(
        self, storage_path: str, filename: str, document_id: str
    ) -> Optional[Path]:
        """Download a file from Supabase Storage to a temp location"""

        try:
            file_bytes = self.supabase.storage.from_(self._bucket).download(storage_path)

            if not file_bytes:
                logger.error(f"Empty file downloaded: {storage_path}")
                return None

            temp_dir = Path(tempfile.gettempdir())
            temp_path = temp_dir / f"watcher_{document_id}_{filename}"
            temp_path.write_bytes(file_bytes)

            logger.info(f"Downloaded {len(file_bytes)} bytes to {temp_path}")
            return temp_path

        except Exception as e:
            logger.error(f"Failed to download from storage: {e}")
            return None


# =========================================================================
# Module-level singleton and helpers
# =========================================================================

_watcher_instance: Optional[DocumentWatcher] = None
_watcher_task: Optional[asyncio.Task] = None


def get_document_watcher(supabase_client, workspace_id: str) -> DocumentWatcher:
    """Get or create the DocumentWatcher singleton"""
    global _watcher_instance
    if _watcher_instance is None:
        _watcher_instance = DocumentWatcher(supabase_client, workspace_id)
    return _watcher_instance


async def start_document_watcher(supabase_client, workspace_id: str) -> DocumentWatcher:
    """Start the document watcher as a background task"""
    global _watcher_task, _watcher_instance

    watcher = get_document_watcher(supabase_client, workspace_id)
    _watcher_task = asyncio.create_task(watcher.start())
    logger.info("Document watcher background task created")
    return watcher


async def stop_document_watcher():
    """Stop the document watcher"""
    global _watcher_instance, _watcher_task

    if _watcher_instance:
        await _watcher_instance.stop()

    if _watcher_task:
        _watcher_task.cancel()
        try:
            await _watcher_task
        except asyncio.CancelledError:
            pass

    _watcher_instance = None
    _watcher_task = None
    logger.info("Document watcher stopped")
