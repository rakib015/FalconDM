import json
import threading
import time
from typing import Optional, Dict, Any
import requests
from core.config_manager import config_store

class WebhookNotifier:
    """Sends notification alerts to Discord Webhook and Telegram Bot."""

    @staticmethod
    def get_discord_webhook() -> str:
        return config_store.get("discord_webhook", "").strip()

    @staticmethod
    def set_discord_webhook(url: str):
        config_store.set("discord_webhook", url.strip())

    @staticmethod
    def get_telegram_config() -> tuple[str, str]:
        token = config_store.get("telegram_token", "").strip()
        chat_id = config_store.get("telegram_chat_id", "").strip()
        return token, chat_id

    @staticmethod
    def set_telegram_config(token: str, chat_id: str):
        config_store.set("telegram_token", token.strip())
        config_store.set("telegram_chat_id", chat_id.strip())

    @classmethod
    def notify_completed(cls, filename: str, file_size_str: str, speed_str: str, elapsed_seconds: float):
        """Asynchronously dispatches download complete webhook."""
        def worker():
            cls._send_discord(
                title="⚡ Download Completed!",
                description=f"**{filename}** has finished downloading successfully.",
                color=0x10b981,
                fields=[
                    {"name": "File Size", "value": file_size_str or "Unknown", "inline": True},
                    {"name": "Avg Speed", "value": speed_str or "N/A", "inline": True},
                    {"name": "Duration", "value": f"{elapsed_seconds:.1f}s", "inline": True}
                ]
            )
            cls._send_telegram(
                f"⚡ <b>FalconDM Download Complete</b>\n\n"
                f"<b>File:</b> <code>{filename}</code>\n"
                f"<b>Size:</b> {file_size_str}\n"
                f"<b>Speed:</b> {speed_str}\n"
                f"<b>Duration:</b> {elapsed_seconds:.1f}s"
            )
        threading.Thread(target=worker, daemon=True).start()

    @classmethod
    def notify_error(cls, filename: str, error_msg: str):
        """Asynchronously dispatches download failed webhook."""
        def worker():
            cls._send_discord(
                title="❌ Download Error",
                description=f"Error occurred while downloading **{filename}**.",
                color=0xef4444,
                fields=[{"name": "Error Details", "value": f"`{error_msg[:200]}`", "inline": False}]
            )
            cls._send_telegram(
                f"❌ <b>FalconDM Download Error</b>\n\n"
                f"<b>File:</b> <code>{filename}</code>\n"
                f"<b>Error:</b> <i>{error_msg}</i>"
            )
        threading.Thread(target=worker, daemon=True).start()

    @classmethod
    def _send_discord(cls, title: str, description: str, color: int = 0x2563eb, fields: Optional[list] = None):
        webhook_url = cls.get_discord_webhook()
        if not webhook_url or not webhook_url.startswith("http"):
            return
        payload = {
            "username": "FalconDM Accelerator",
            "avatar_url": "https://raw.githubusercontent.com/favicon.ico",
            "embeds": [{
                "title": title,
                "description": description,
                "color": color,
                "fields": fields or [],
                "footer": {"text": "FalconDM Turbo Download Engine"}
            }]
        }
        try:
            requests.post(webhook_url, json=payload, timeout=5)
        except Exception:
            pass

    @classmethod
    def _send_telegram(cls, html_text: str):
        token, chat_id = cls.get_telegram_config()
        if not token or not chat_id:
            return
        api_url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": html_text,
            "parse_mode": "HTML"
        }
        try:
            requests.post(api_url, json=payload, timeout=5)
        except Exception:
            pass
