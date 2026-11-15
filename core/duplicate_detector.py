import os
from typing import Optional, Dict, Any, List
from core.state_manager import DownloadManager
from core.hasher import compute_checksums

class DuplicateDetector:
    """Detects duplicate downloads by URL, target filename, or cryptographic checksum."""

    def __init__(self, manager: DownloadManager):
        self.manager = manager

    def check_duplicate_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Returns existing task info if URL is already in queue or library."""
        norm_url = url.strip()
        for task in self.manager.tasks.values():
            if task.url.strip() == norm_url:
                return {
                    "task_id": task.task_id,
                    "filename": task.filename,
                    "status": task.status,
                    "save_path": task.save_path,
                    "file_size": task.file_size
                }
        return None

    def check_existing_file(self, save_path: str) -> bool:
        """Checks if target file already exists on disk and is non-empty."""
        return os.path.exists(save_path) and os.path.getsize(save_path) > 0

    def find_duplicate_by_hash(self, target_hash: str, hash_type: str = "sha256") -> Optional[str]:
        """Finds any completed task on disk with an identical hash."""
        target_hash = target_hash.strip().lower()
        for task in self.manager.tasks.values():
            if task.status == "completed" and os.path.exists(task.save_path):
                try:
                    hashes = compute_checksums(task.save_path)
                    if hashes.get(hash_type, "").lower() == target_hash:
                        return task.save_path
                except Exception:
                    pass
        return None
