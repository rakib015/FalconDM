import threading
import winsound
from typing import Optional
from core.config_manager import config_store

class NotificationManager:
    """Dispatches sound cues and notification alerts."""

    @staticmethod
    def play_complete_sound():
        if not config_store.get("play_sounds", True):
            return
        def worker():
            try:
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except Exception:
                pass
        threading.Thread(target=worker, daemon=True).start()

    @staticmethod
    def play_error_sound():
        if not config_store.get("play_sounds", True):
            return
        def worker():
            try:
                winsound.MessageBeep(winsound.MB_ICONHAND)
            except Exception:
                pass
        threading.Thread(target=worker, daemon=True).start()

    @staticmethod
    def play_start_sound():
        if not config_store.get("play_sounds", True):
            return
        def worker():
            try:
                winsound.MessageBeep(winsound.MB_OK)
            except Exception:
                pass
        threading.Thread(target=worker, daemon=True).start()

notification_manager = NotificationManager()
play_finish_sound = NotificationManager.play_complete_sound
setattr(NotificationManager, "play_finish_sound", staticmethod(NotificationManager.play_complete_sound))
