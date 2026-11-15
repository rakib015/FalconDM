import os
import json
import uuid
import threading
from typing import List, Dict, Optional
from core.engine import DownloadTask

EXT_CATEGORIES = {
    "Compressed": [".zip", ".rar", ".7z", ".tar", ".gz", ".iso", ".bz2", ".xz", ".tgz", ".zst", ".7zip", ".cab"],
    "Video": [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".ts", ".3gp", ".m3u8", ".mpd"],
    "Audio": [".mp3", ".flac", ".wav", ".aac", ".ogg", ".m4a", ".wma", ".opus", ".aiff", ".alac", ".mid", ".midi"],
    "Image": [".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".avif", ".bmp", ".tiff", ".tif", ".heic", ".heif", ".ico", ".raw", ".psd", ".ai", ".eps"],
    "Document": [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".csv", ".epub", ".rtf", ".mobi", ".djvu", ".odt", ".ods", ".odp"],
    "Program": [".exe", ".msi", ".apk", ".dmg", ".bat", ".cmd", ".sh", ".bin", ".torrent", ".deb", ".rpm", ".pkg", ".crx", ".xpi", ".img"]
}

def detect_category(filename: str) -> str:
    if not filename:
        return "General"
    if filename.startswith(("http://", "https://")):
        try:
            from core.media_grabber import MediaGrabber
            if MediaGrabber.is_likely_media_url(filename):
                return "Video"
        except Exception:
            pass
    ext = os.path.splitext(filename.lower())[1]
    for cat, exts in EXT_CATEGORIES.items():
        if ext in exts:
            return cat
    return "General"


class DownloadManager:
    def __init__(self, data_file: str = "downloads.json", max_concurrent: int = 3):
        self.data_file = data_file
        self.max_concurrent = max_concurrent
        self.tasks: Dict[str, DownloadTask] = {}
        self.lock = threading.RLock()
        self.global_speed_limit_bps: int = 0
        self.default_download_dir = os.path.join(os.path.expanduser("~"), "Downloads", "FalconDM")
        self.routing_rules: Dict[str, str] = {}
        self.named_queues: Dict[str, dict] = {
            "Default": {"max_concurrent": 3},
            "Night Owl": {"max_concurrent": 8},
            "Priority": {"max_concurrent": 1}
        }
        os.makedirs(self.default_download_dir, exist_ok=True)
        self.load_state()

    def add_routing_rule(self, pattern: str, target_folder: str) -> None:
        """Adds a smart destination routing rule by domain, regex, or file extension."""
        with self.lock:
            self.routing_rules[pattern.strip().lower()] = os.path.abspath(target_folder)
            self.save_state()

    def remove_routing_rule(self, pattern: str) -> bool:
        with self.lock:
            p = pattern.strip().lower()
            if p in self.routing_rules:
                del self.routing_rules[p]
                self.save_state()
                return True
            return False

    def resolve_destination_folder(self, url: str, filename: str, category: str) -> str:
        """Resolves target folder using smart routing rules before falling back to category dir."""
        with self.lock:
            url_l = (url or "").lower()
            fn_l = (filename or "").lower()
            for pattern, folder in self.routing_rules.items():
                if pattern in url_l or pattern in fn_l or fn_l.endswith(pattern):
                    os.makedirs(folder, exist_ok=True)
                    return folder
            return self.get_category_dir(category)

    def _sync_system_power_and_audio(self):
        """Prevents Windows system sleep while downloading and releases lock when idle."""
        try:
            from core.platform_utils import prevent_system_sleep
            active = any(t.status == DownloadTask.STATUS_DOWNLOADING for t in self.tasks.values())
            prevent_system_sleep(active)
        except Exception:
            pass

    def _on_task_status_update(self, task: DownloadTask):
        self._sync_system_power_and_audio()
        if task.status == DownloadTask.STATUS_COMPLETED:
            try:
                from core.platform_utils import play_audio_alert
                play_audio_alert("complete")
            except Exception:
                pass
        self.rebalance_speed_limits()

    def set_global_speed_limit(self, bps: int):
        """Sets the collective global bandwidth limit across all active downloads."""
        with self.lock:
            self.global_speed_limit_bps = max(0, bps)
            self.rebalance_speed_limits()

    def rebalance_speed_limits(self):
        """Dynamically distributes the global speed limit equally among active downloading tasks."""
        with self.lock:
            active_tasks = [t for t in self.tasks.values() if t.status == DownloadTask.STATUS_DOWNLOADING]
            if not active_tasks:
                return
            if self.global_speed_limit_bps <= 0:
                for t in active_tasks:
                    t.set_speed_limit(0)
            else:
                share_bps = max(10 * 1024, self.global_speed_limit_bps // len(active_tasks))
                for t in active_tasks:
                    t.set_speed_limit(share_bps)

    def get_category_dir(self, category: str) -> str:
        folder = os.path.join(self.default_download_dir, category)
        os.makedirs(folder, exist_ok=True)
        return folder

    def create_task(
        self,
        url: str,
        filename: Optional[str] = None,
        save_dir: Optional[str] = None,
        num_connections: int = 8,
        category: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        queue_name: str = "Default",
        auto_start: bool = True,
        mirrors: Optional[List[str]] = None,
        priority: int = 1,
        sequential_mode: bool = False
    ) -> DownloadTask:
        with self.lock:
            task_id = str(uuid.uuid4())
            
            # Temporary target filename if not yet probed
            clean_name = filename or "pending_download"
            cat = category or detect_category(clean_name)
            target_dir = save_dir or self.resolve_destination_folder(url, clean_name, cat)
            save_path = os.path.join(target_dir, clean_name)

            task = DownloadTask(
                task_id=task_id,
                url=url,
                save_path=save_path,
                num_connections=num_connections,
                category=cat,
                headers=headers or {},
                mirrors=mirrors or [],
                priority=priority,
                sequential_mode=sequential_mode
            )
            task.queue_name = queue_name
            task.on_status_change = self._on_task_status_update
            
            self.tasks[task_id] = task
            self.save_state()

            if auto_start:
                # Probe and start asynchronously
                threading.Thread(target=self._start_task_worker, args=(task,), daemon=True).start()

            return task

    def _start_task_worker(self, task: DownloadTask):
        if task.file_size == 0 and not task.segments:
            if task.probe():
                # Re-check category once real filename is discovered
                real_cat = detect_category(task.filename)
                task.category = real_cat
                # If was placed in general directory, update to smart destination folder
                current_dir = os.path.dirname(task.save_path)
                target_cat_dir = self.resolve_destination_folder(task.url, task.filename, real_cat)
                if current_dir == self.default_download_dir or current_dir == self.get_category_dir("General"):
                    task.save_path = os.path.join(target_cat_dir, task.filename)
        task.on_status_change = self._on_task_status_update
        task.start()
        self._sync_system_power_and_audio()
        self.rebalance_speed_limits()
        self.save_state()

    def pause_task(self, task_id: str):
        with self.lock:
            task = self.tasks.get(task_id)
            if task:
                task.pause()
                self.rebalance_speed_limits()
                self.save_state()

    def resume_task(self, task_id: str):
        with self.lock:
            task = self.tasks.get(task_id)
            if task:
                task.start()
                self.rebalance_speed_limits()
                self.save_state()

    def refresh_task_url(self, task_id: str, new_url: str, new_headers: Optional[dict] = None) -> bool:
        """Updates expired URL/headers on an existing task and resumes it without losing downloaded progress."""
        with self.lock:
            task = self.tasks.get(task_id)
            if not task:
                return False
            task.url = new_url.strip()
            if new_headers:
                task.headers.update(new_headers)
            if task.status in (DownloadTask.STATUS_ERROR, DownloadTask.STATUS_PAUSED, DownloadTask.STATUS_CANCELED):
                task.status = DownloadTask.STATUS_PAUSED
                task.error_message = ""
            self.save_state()
            task.start()
            return True

    def set_task_priority(self, task_id: str, priority: int) -> bool:
        """Sets download priority (0=Low, 1=Normal, 2=High)."""
        with self.lock:
            task = self.tasks.get(task_id)
            if not task:
                return False
            task.priority = max(0, min(2, priority))
            self.save_state()
            return True

    def add_task_mirror(self, task_id: str, mirror_url: str) -> bool:
        """Adds a fallback mirror URL to an existing task."""
        with self.lock:
            task = self.tasks.get(task_id)
            if not task:
                return False
            clean_url = mirror_url.strip()
            if not hasattr(task, 'mirrors'):
                task.mirrors = []
            if clean_url and clean_url not in task.mirrors and clean_url != task.url:
                task.mirrors.append(clean_url)
                self.save_state()
                return True
            return False

    def move_task_up(self, task_id: str) -> bool:
        """Moves task one position earlier in queue list."""
        with self.lock:
            keys = list(self.tasks.keys())
            if task_id not in keys:
                return False
            idx = keys.index(task_id)
            if idx <= 0:
                return False
            keys[idx - 1], keys[idx] = keys[idx], keys[idx - 1]
            reordered = {k: self.tasks[k] for k in keys}
            self.tasks.clear()
            self.tasks.update(reordered)
            self.save_state()
            return True

    def move_task_down(self, task_id: str) -> bool:
        """Moves task one position later in queue list."""
        with self.lock:
            keys = list(self.tasks.keys())
            if task_id not in keys:
                return False
            idx = keys.index(task_id)
            if idx >= len(keys) - 1:
                return False
            keys[idx], keys[idx + 1] = keys[idx + 1], keys[idx]
            reordered = {k: self.tasks[k] for k in keys}
            self.tasks.clear()
            self.tasks.update(reordered)
            self.save_state()
            return True

    def move_task_to_top(self, task_id: str) -> bool:
        """Moves task to top of queue list."""
        with self.lock:
            if task_id not in self.tasks:
                return False
            task = self.tasks.pop(task_id)
            reordered = {task_id: task}
            reordered.update(self.tasks)
            self.tasks.clear()
            self.tasks.update(reordered)
            self.save_state()
            return True

    def move_task_to_bottom(self, task_id: str) -> bool:
        """Moves task to bottom of queue list."""
        with self.lock:
            if task_id not in self.tasks:
                return False
            task = self.tasks.pop(task_id)
            self.tasks[task_id] = task
            self.save_state()
            return True

    def remove_task(self, task_id: str, delete_file: bool = False):
        with self.lock:
            task = self.tasks.get(task_id)
            if task:
                task.cancel()
                if delete_file and os.path.exists(task.save_path):
                    try:
                        os.remove(task.save_path)
                    except Exception:
                        pass
                del self.tasks[task_id]
                self.rebalance_speed_limits()
                self.save_state()

    def pause_all(self):
        with self.lock:
            for task in self.tasks.values():
                if task.status == DownloadTask.STATUS_DOWNLOADING:
                    task.pause()
            self.save_state()

    def resume_all(self):
        with self.lock:
            for task in self.tasks.values():
                if task.status in (DownloadTask.STATUS_PAUSED, DownloadTask.STATUS_QUEUED):
                    task.start()
            self.save_state()

    def get_filtered_tasks(self, category: Optional[str] = None, status: Optional[str] = None) -> List[DownloadTask]:
        with self.lock:
            results = list(self.tasks.values())
            if category and category != "All Downloads":
                results = [t for t in results if t.category.lower() == category.lower()]
            if status:
                if status == "Unfinished":
                    results = [t for t in results if t.status != DownloadTask.STATUS_COMPLETED]
                elif status == "Finished":
                    results = [t for t in results if t.status == DownloadTask.STATUS_COMPLETED]
                else:
                    results = [t for t in results if t.status.lower() == status.lower()]
            return results

    def save_state(self):
        with self.lock:
            data = [task.to_dict() for task in self.tasks.values()]
            try:
                with open(self.data_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
            except Exception as e:
                print(f"[FalconDM] Error saving state: {e}")

    def load_state(self):
        with self.lock:
            if not os.path.exists(self.data_file):
                return
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data:
                    task = DownloadTask.from_dict(item)
                    task.on_status_change = self._on_task_status_update
                    self.tasks[task.task_id] = task
            except Exception as e:
                print(f"[FalconDM] Error loading state: {e}")
