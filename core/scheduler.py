import os
import time
import subprocess
import threading
from datetime import datetime
from typing import Dict, List, Optional, Callable

class DownloadQueue:
    def __init__(self, name: str, max_concurrent: int = 1):
        self.name = name
        self.max_concurrent = max_concurrent
        self.enabled = False
        self.start_time: Optional[str] = None  # e.g. "02:00"
        self.stop_time: Optional[str] = None   # e.g. "06:30"
        self.shutdown_on_finish = False
        self.is_active = False

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "max_concurrent": self.max_concurrent,
            "enabled": self.enabled,
            "start_time": self.start_time,
            "stop_time": self.stop_time,
            "shutdown_on_finish": self.shutdown_on_finish
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'DownloadQueue':
        q = cls(data.get("name", "Default"), data.get("max_concurrent", 1))
        q.enabled = data.get("enabled", False)
        q.start_time = data.get("start_time")
        q.stop_time = data.get("stop_time")
        q.shutdown_on_finish = data.get("shutdown_on_finish", False)
        return q


class QueueScheduler:
    """Automated Queue Scheduler & Power Management (IDM-grade night downloads & auto-shutdown)."""

    def __init__(self, manager, config_file: str = "scheduler_config.json"):
        self.manager = manager
        self.config_file = config_file
        self.queues: Dict[str, DownloadQueue] = {
            "Default": DownloadQueue("Default", max_concurrent=2),
            "Night Queue": DownloadQueue("Night Queue", max_concurrent=1)
        }
        self.shutdown_triggered = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.on_queue_update: Optional[Callable[[], None]] = None
        self.load_config()

    def start(self):
        if not self._thread or not self._thread.is_alive():
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._scheduler_loop, daemon=True)
            self._thread.start()

    def stop(self):
        self._stop_event.set()

    def get_or_create_queue(self, name: str) -> DownloadQueue:
        if name not in self.queues:
            self.queues[name] = DownloadQueue(name)
        return self.queues[name]

    def _scheduler_loop(self):
        """Monitors scheduled time slots, limits concurrency, and triggers auto-shutdown."""
        while not self._stop_event.is_set():
            time.sleep(1.0)
            now_str = datetime.now().strftime("%H:%M")

            for q_name, q in list(self.queues.items()):
                # 1. Check time-based activations
                if q.enabled and q.start_time:
                    if now_str == q.start_time and not q.is_active:
                        q.is_active = True
                        print(f"[FalconDM Scheduler] Activated queue '{q_name}' at {now_str}")

                if q.enabled and q.stop_time:
                    if now_str == q.stop_time and q.is_active:
                        q.is_active = False
                        self._pause_queue_downloads(q_name)
                        print(f"[FalconDM Scheduler] Stopped queue '{q_name}' at {now_str}")

                # 2. Concurrency management for active queue
                if q.is_active or (q.name == "Default" and not q.enabled):
                    self._balance_queue_concurrency(q)

                # 3. Check for completion and auto-shutdown
                if q.is_active and q.shutdown_on_finish and not self.shutdown_triggered:
                    tasks_in_q = [
                        t for t in self.manager.tasks.values() 
                        if getattr(t, 'queue_name', 'Default') == q_name
                    ]
                    if tasks_in_q:
                        active_or_pending = [
                            t for t in tasks_in_q 
                            if t.status in ("Downloading", "Queued", "Connecting")
                        ]
                        if not active_or_pending:
                            print(f"[FalconDM Scheduler] Queue '{q_name}' completed! Triggering auto-shutdown in 60s...")
                            self.trigger_shutdown()

    def _balance_queue_concurrency(self, q: DownloadQueue):
        """Ensures at most q.max_concurrent tasks are actively downloading."""
        tasks_in_q = [
            t for t in self.manager.tasks.values() 
            if getattr(t, 'queue_name', 'Default') == q.name
        ]
        active_count = sum(1 for t in tasks_in_q if t.status == "Downloading")
        
        if active_count < q.max_concurrent:
            queued = [t for t in tasks_in_q if t.status == "Queued"]
            # Prioritize High (2) over Normal (1) and Low (0)
            queued.sort(key=lambda t: getattr(t, 'priority', 1), reverse=True)
            for task in queued[:q.max_concurrent - active_count]:
                task.start()

    def _pause_queue_downloads(self, q_name: str):
        for t in self.manager.tasks.values():
            if getattr(t, 'queue_name', 'Default') == q_name and t.status == "Downloading":
                t.pause()

    def trigger_shutdown(self):
        """Safely initiates system shutdown after download completion."""
        self.shutdown_triggered = True
        try:
            # 60 second grace period with abort notice
            cmd = 'shutdown /s /t 60 /c "FalconDM Turbo: All scheduled downloads completed! Shutting down in 60 seconds. Run \'shutdown /a\' in cmd to abort."'
            subprocess.Popen(cmd, shell=True)
        except Exception as e:
            print(f"[FalconDM Scheduler] Shutdown execution error: {e}")

    def abort_shutdown(self):
        """Cancels an active pending shutdown."""
        self.shutdown_triggered = False
        try:
            subprocess.Popen("shutdown /a", shell=True)
        except Exception:
            pass

    def save_config(self):
        try:
            data = {name: q.to_dict() for name, q in self.queues.items()}
            import json
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[FalconDM Scheduler] save_config error: {e}")

    def load_config(self):
        if not os.path.exists(self.config_file):
            return
        try:
            import json
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            for name, q_data in data.items():
                self.queues[name] = DownloadQueue.from_dict(q_data)
        except Exception as e:
            print(f"[FalconDM Scheduler] load_config error: {e}")
