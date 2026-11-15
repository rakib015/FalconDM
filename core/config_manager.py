import os
import json
from typing import Any, Dict, Optional

DEFAULT_SETTINGS = {
    "default_download_dir": os.path.join(os.path.expanduser("~"), "Downloads", "FalconDM"),
    "last_download_dir": "",
    "remember_last_download_dir": True,
    "category_custom_dirs": {},
    "default_threads": 16,
    "minimize_to_tray_on_close": True,
    "play_sounds": True,
    "show_basket_on_startup": False,
    "show_floating_download_window": True,
    "clipboard_sniff_enabled": True,
    "ask_save_location_everytime": True,
    "max_concurrent_tasks": 3,
    "shutdown_on_completion": False,
    "instant_media_download": True,
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 FalconDM/2.0",
    "allow_remote_web_access": True,
    "real_debrid_api_key": "",
    "telegram_bot_token": "",
    "telegram_allowed_chat_ids": [],
    "auto_upload_enabled": False,
    "auto_upload_telegram_chat_id": "",
    "auto_upload_delete_local": False
}

class ConfigManager:
    """Manages application settings and user preferences."""
    _instance: Optional['ConfigManager'] = None
    config_path: str = "falcon_settings.json"
    settings: Dict[str, Any] = {}

    def __new__(cls, config_path: Optional[str] = None):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if not config_path:
                resolved_path = os.path.join(base_dir, "falcon_settings.json")
            elif not os.path.isabs(config_path):
                resolved_path = os.path.join(base_dir, config_path)
            else:
                resolved_path = config_path
            cls._instance.config_path = resolved_path
            cls._instance.settings = DEFAULT_SETTINGS.copy()
            cls._instance.load()
        return cls._instance

    def load(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.settings.update(data)
            except Exception as e:
                print(f"[ConfigManager] Could not load settings: {e}")

    def save(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"[ConfigManager] Could not save settings: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        return self.settings.get(key, default if default is not None else DEFAULT_SETTINGS.get(key))

    def set(self, key: str, value: Any):
        self.settings[key] = value
        self.save()

config_store = ConfigManager()
