import os
import time
import threading
import urllib.parse
from typing import Optional, Dict, Any, List
import requests

from core.config_manager import config_store
from core.platform_utils import safe_print

def _format_bytes(size_bytes: int) -> str:
    if size_bytes <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    while size >= 1024.0 and i < len(units) - 1:
        size /= 1024.0
        i += 1
    return f"{size:.2f} {units[i]}"

def _format_speed(bps: float) -> str:
    if bps <= 0:
        return "0.0 KB/s"
    if bps >= 1024 * 1024:
        return f"{bps / (1024 * 1024):.2f} MB/s"
    return f"{bps / 1024:.1f} KB/s"


class TelegramRemoteBot:
    """
    FalconDM Telegram Remote Control Bot.
    Allows users to:
      - Send any download link or magnet via Telegram from their phone.
      - Check real-time download speeds, active tasks, and progress.
      - Receive instant alerts on their phone when big files finish downloading.
    """

    def __init__(self, manager=None):
        self.manager = manager
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_update_id = 0

    @property
    def token(self) -> str:
        return config_store.get("telegram_bot_token", "").strip()

    @property
    def allowed_chats(self) -> List[int]:
        raw = config_store.get("telegram_allowed_chat_ids", [])
        if isinstance(raw, str):
            try:
                return [int(x.strip()) for x in raw.split(",") if x.strip().lstrip("-").isdigit()]
            except Exception:
                return []
        elif isinstance(raw, list):
            res = []
            for item in raw:
                try:
                    res.append(int(item))
                except Exception:
                    pass
            return res
        return []

    def is_configured(self) -> bool:
        return bool(self.token)

    def start(self):
        """Starts the Telegram polling daemon thread."""
        if self._thread and self._thread.is_alive():
            return
        if not self.is_configured():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="FalconTelegramBot")
        self._thread.start()
        safe_print("[FalconDM Telegram Bot] Started listening for remote commands.")

    def stop(self):
        self._stop_event.set()

    def send_message(self, chat_id: int, text: str, parse_mode: str = "Markdown") -> bool:
        if not self.token:
            return False
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode
        }
        try:
            resp = requests.post(url, json=payload, timeout=10)
            return resp.status_code == 200
        except Exception:
            return False

    def notify_all_allowed(self, text: str):
        """Sends an alert to all configured chat IDs."""
        for cid in self.allowed_chats:
            self.send_message(cid, text)

    def notify_download_complete(self, task):
        """Sends completion notification with file metadata."""
        size_str = _format_bytes(getattr(task, "file_size", 0))
        fname = getattr(task, "filename", "Unknown File")
        cat = getattr(task, "category", "General")
        save_path = getattr(task, "save_path", "")

        msg = (
            f"⚡ *Download Finished!*\n\n"
            f"📁 *File:* `{fname}`\n"
            f"📦 *Size:* `{size_str}`\n"
            f"🏷️ *Category:* `{cat}`\n"
            f"📍 *Location:* `{save_path}`\n\n"
            f"✅ *FalconDM Turbo Engine*"
        )
        self.notify_all_allowed(msg)

    def _poll_loop(self):
        while not self._stop_event.is_set():
            if not self.token:
                time.sleep(5)
                continue

            try:
                url = f"https://api.telegram.org/bot{self.token}/getUpdates"
                params = {"offset": self._last_update_id + 1, "timeout": 20}
                resp = requests.get(url, params=params, timeout=25)
                if resp.status_code != 200:
                    time.sleep(3)
                    continue

                data = resp.json()
                for update in data.get("result", []):
                    self._last_update_id = update["update_id"]
                    msg = update.get("message")
                    if not msg:
                        continue
                    self._handle_incoming_message(msg)

            except Exception as e:
                time.sleep(3)

    def _handle_incoming_message(self, msg: Dict[str, Any]):
        chat_id = msg.get("chat", {}).get("id")
        text = (msg.get("text") or "").strip()
        if not chat_id or not text:
            return

        # Security check: whitelist chat IDs
        allowed = self.allowed_chats
        if allowed and chat_id not in allowed:
            self.send_message(
                chat_id,
                f"⛔ *Unauthorized Access.*\nYour Telegram Chat ID is `{chat_id}`.\n"
                f"Add this Chat ID in FalconDM Settings to enable remote control.",
                parse_mode="Markdown"
            )
            return

        # Commands
        cmd_lower = text.lower()

        if cmd_lower in ("/start", "/help"):
            help_text = (
                "⚡ *FalconDM Remote Control Bot*\n\n"
                "Send any link directly to this chat and FalconDM on your PC will download it at turbo speed!\n\n"
                "*Available Commands:*\n"
                "• `http(s)://...` or `magnet:...` — Start download\n"
                "• `/status` — View active downloads, speeds, and ETA\n"
                "• `/pauseall` — Pause all active downloads\n"
                "• `/resumeall` — Resume all downloads\n"
                "• `/speed <limit>` — Set speed cap (e.g. `/speed 5mb` or `/speed unlimited`)\n"
                "• `/ping` — Check if your PC is online"
            )
            self.send_message(chat_id, help_text)
            return

        if cmd_lower == "/ping":
            self.send_message(chat_id, "🟢 *FalconDM PC is online and ready!*")
            return

        if cmd_lower == "/status":
            self._send_status(chat_id)
            return

        if cmd_lower == "/pauseall":
            if self.manager:
                self.manager.pause_all()
                self.send_message(chat_id, "⏸ *All downloads paused.*")
            return

        if cmd_lower == "/resumeall":
            if self.manager:
                self.manager.resume_all()
                self.send_message(chat_id, "▶ *All downloads resumed.*")
            return

        if cmd_lower.startswith("/speed"):
            parts = text.split()
            if len(parts) > 1 and self.manager:
                choice = parts[1].lower()
                if "unlimit" in choice or choice == "0":
                    self.manager.set_global_speed_limit(0)
                    self.send_message(chat_id, "🚀 *Speed limit removed (Unlimited).*")
                else:
                    m = re.match(r'(\d+)\s*(k|m|g)?', choice)
                    if m:
                        val = int(m.group(1))
                        unit = (m.group(2) or "m").lower()
                        multiplier = 1024 * 1024 if unit == "m" else (1024 if unit == "k" else 1024 * 1024 * 1024)
                        bps = val * multiplier
                        self.manager.set_global_speed_limit(bps)
                        self.send_message(chat_id, f"⚡ *Global speed cap set to {_format_speed(bps)}*")
            return

        # Direct URL or Magnet link detected
        if text.startswith("http://") or text.startswith("https://") or text.startswith("magnet:"):
            url = text.split()[0]
            if self.manager:
                # Check Debrid unrestrictor if enabled
                try:
                    from core.debrid_resolver import DebridResolver
                    if DebridResolver.is_debrid_enabled() and DebridResolver.is_supported_url(url):
                        self.send_message(chat_id, "🧲 *Unrestricting link via Real-Debrid...*")
                        ok, direct_url, meta = DebridResolver.unrestrict_link(url)
                        if ok:
                            url = direct_url
                except Exception:
                    pass

                task = self.manager.create_task(url)
                self.send_message(
                    chat_id,
                    f"🚀 *Download Started!*\n\n"
                    f"📁 *Name:* `{task.filename}`\n"
                    f"⚡ *Streams:* `{task.num_connections}` connections\n"
                    f"🏷️ *Category:* `{task.category}`"
                )
            else:
                self.send_message(chat_id, "⚠️ *DownloadManager not attached.*")
            return

        self.send_message(chat_id, "❓ Unknown command. Send a URL or type `/help`.")

    def _send_status(self, chat_id: int):
        if not self.manager:
            self.send_message(chat_id, "⚠️ Manager not available.")
            return

        tasks = list(self.manager.tasks.values())
        active = [t for t in tasks if t.status == "Downloading"]
        total_speed = sum(t.speed_bps for t in active)

        if not tasks:
            self.send_message(chat_id, "📭 *Queue is empty. No active downloads.*")
            return

        lines = [f"⚡ *FalconDM Live Status* (Speed: `{_format_speed(total_speed)}`)\n"]
        for t in tasks[-6:]:  # show last 6
            pct = getattr(t, "progress_pct", 0.0)
            status_icon = "▶" if t.status == "Downloading" else ("✓" if t.status == "Completed" else "⏸")
            lines.append(f"{status_icon} *{t.filename[:28]}*")
            lines.append(f"   `{_format_bytes(t.downloaded_bytes)} / {_format_bytes(t.file_size)}` ({pct:.1f}%) — `{_format_speed(t.speed_bps)}`\n")

        self.send_message(chat_id, "\n".join(lines))

telegram_bot = TelegramRemoteBot()

