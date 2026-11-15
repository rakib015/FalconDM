import time
import threading
from datetime import datetime
from typing import Optional, Callable
from core.config_manager import config_store

class BandwidthScheduler:
    """Schedules automatic bandwidth throttling during peak hours and uncapped speed at night."""

    def __init__(self, on_apply_limit: Optional[Callable[[int], None]] = None):
        self.on_apply_limit = on_apply_limit
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def is_enabled(self) -> bool:
        return config_store.get("bandwidth_schedule_enabled", False)

    def set_enabled(self, val: bool):
        config_store.set("bandwidth_schedule_enabled", val)

    def get_schedule(self) -> dict:
        return {
            "enabled": self.is_enabled(),
            "peak_start_hour": config_store.get("peak_start_hour", 9),
            "peak_end_hour": config_store.get("peak_end_hour", 23),
            "peak_limit_bps": config_store.get("peak_limit_bps", 2 * 1024 * 1024),  # 2 MB/s
            "night_limit_bps": config_store.get("night_limit_bps", 0)                # Unlimited
        }

    def set_schedule(self, peak_start: int, peak_end: int, peak_bps: int, night_bps: int = 0):
        config_store.set("peak_start_hour", peak_start)
        config_store.set("peak_end_hour", peak_end)
        config_store.set("peak_limit_bps", peak_bps)
        config_store.set("night_limit_bps", night_bps)

    def get_current_target_speed(self) -> int:
        """Determines target speed limit in Bps for the current time of day."""
        if not self.is_enabled():
            return 0  # Unlimited or managed manually
        
        hour = datetime.now().hour
        p_start = config_store.get("peak_start_hour", 9)
        p_end = config_store.get("peak_end_hour", 23)
        peak_limit = config_store.get("peak_limit_bps", 2 * 1024 * 1024)
        night_limit = config_store.get("night_limit_bps", 0)

        # Check if inside peak interval
        if p_start <= p_end:
            is_peak = (p_start <= hour < p_end)
        else:
            is_peak = (hour >= p_start or hour < p_end)

        return peak_limit if is_peak else night_limit

    def _loop(self):
        while self._running:
            try:
                if self.is_enabled() and self.on_apply_limit:
                    target_bps = self.get_current_target_speed()
                    self.on_apply_limit(target_bps)
            except Exception:
                pass
            time.sleep(30)  # Check every 30 seconds
