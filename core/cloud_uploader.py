import os
import threading
from typing import Optional, Dict, Any, Callable
import requests
from core.config_manager import config_store
from core.platform_utils import safe_print

class CloudUploader:
    """
    Automated Cloud & Telegram Uploader.
    Automatically uploads finished downloads to a Telegram Channel, Group, or Cloud storage,
    and optionally purges the local file to save storage space.
    """

    @classmethod
    def is_auto_upload_enabled(cls) -> bool:
        return config_store.get("auto_upload_enabled", False)

    @classmethod
    def get_telegram_target_chat(cls) -> str:
        return str(config_store.get("auto_upload_telegram_chat_id", "")).strip()

    @classmethod
    def should_delete_after_upload(cls) -> bool:
        return config_store.get("auto_upload_delete_local", False)

    @classmethod
    def upload_to_telegram(
        cls,
        file_path: str,
        caption: str = "",
        chat_id: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> bool:
        """
        Uploads a local file to a Telegram chat/channel using the Telegram Bot API.
        """
        bot_token = config_store.get("telegram_bot_token", "").strip()
        target_chat = chat_id or cls.get_telegram_target_chat()

        if not bot_token or not target_chat:
            return False

        if not os.path.isfile(file_path):
            safe_print(f"[FalconDM CloudUploader] File not found: {file_path}")
            return False

        file_size = os.path.getsize(file_path)
        # Telegram standard bot upload limit is 50MB (2000MB on local bot api)
        if file_size > 50 * 1024 * 1024:
            safe_print(f"[FalconDM CloudUploader] File {os.path.basename(file_path)} ({file_size} bytes) exceeds standard Telegram Bot 50MB upload limit.")
            return False

        url = f"https://api.telegram.org/bot{bot_token}/sendDocument"

        try:
            with open(file_path, "rb") as f:
                files = {"document": (os.path.basename(file_path), f)}
                data = {
                    "chat_id": target_chat,
                    "caption": caption or f"⚡ Uploaded via FalconDM: {os.path.basename(file_path)}"
                }
                safe_print(f"[FalconDM CloudUploader] Uploading {os.path.basename(file_path)} to Telegram {target_chat}...")
                resp = requests.post(url, files=files, data=data, timeout=120)

                if resp.status_code == 200:
                    safe_print(f"[FalconDM CloudUploader] Successfully uploaded {os.path.basename(file_path)}")
                    if cls.should_delete_after_upload():
                        try:
                            os.remove(file_path)
                            safe_print(f"[FalconDM CloudUploader] Deleted local file after upload: {file_path}")
                        except Exception as del_err:
                            safe_print(f"[FalconDM CloudUploader] Could not delete local file: {del_err}")
                    return True
                else:
                    safe_print(f"[FalconDM CloudUploader] Upload failed: HTTP {resp.status_code} - {resp.text}")
                    return False
        except Exception as e:
            safe_print(f"[FalconDM CloudUploader] Error during upload: {e}")
            return False

    @classmethod
    def handle_task_completion(cls, task):
        """Asynchronously dispatches auto-upload when download completes."""
        if not cls.is_auto_upload_enabled():
            return

        file_path = getattr(task, "save_path", "")
        if not file_path or not os.path.isfile(file_path):
            return

        threading.Thread(
            target=cls.upload_to_telegram,
            args=(file_path, f"⚡ *{task.filename}* ({getattr(task, 'file_size', 0)} bytes)"),
            daemon=True
        ).start()

cloud_uploader = CloudUploader()

