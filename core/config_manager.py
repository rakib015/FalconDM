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
    "auto_upload_delete_local": False,
    "ui_theme_accent": "Cyberpunk Cyan",
    "auto_speed_optimizer": True,
    "github_acceleration_enabled": True,
    "huggingface_acceleration_enabled": True,
    "wrapped_links_enabled": True,
    "arxiv_resolver_enabled": True
}

THEME_PALETTES: Dict[str, Dict[str, str]] = {
    "Cyberpunk Cyan": {
        "primary": "#0284c7",
        "primary_hover": "#0369a1",
        "accent": "#38bdf8",
        "badge_bg": "#082f49",
        "badge_text": "#38bdf8",
        "graph_fill": "#082f49",
        "graph_line": "#38bdf8"
    },
    "Emerald Matrix": {
        "primary": "#059669",
        "primary_hover": "#047857",
        "accent": "#10b981",
        "badge_bg": "#064e3b",
        "badge_text": "#34d399",
        "graph_fill": "#064e3b",
        "graph_line": "#10b981"
    },
    "Sunset Orange": {
        "primary": "#ea580c",
        "primary_hover": "#c2410c",
        "accent": "#f97316",
        "badge_bg": "#431407",
        "badge_text": "#fb923c",
        "graph_fill": "#451a03",
        "graph_line": "#f97316"
    },
    "Vaporwave Violet": {
        "primary": "#7c3aed",
        "primary_hover": "#6d28d9",
        "accent": "#a855f7",
        "badge_bg": "#3b0764",
        "badge_text": "#c084fc",
        "graph_fill": "#3b0764",
        "graph_line": "#a855f7"
    },
    "Crimson Turbo": {
        "primary": "#dc2626",
        "primary_hover": "#b91c1c",
        "accent": "#f43f5e",
        "badge_bg": "#450a0a",
        "badge_text": "#fb7185",
        "graph_fill": "#4c0519",
        "graph_line": "#f43f5e"
    },
    "AB Violet": {
        "primary": "#6366f1",
        "primary_hover": "#4f46e5",
        "accent": "#818cf8",
        "badge_bg": "#1e1b4b",
        "badge_text": "#a5b4fc",
        "graph_fill": "#1e1b4b",
        "graph_line": "#818cf8"
    },
    "Midnight Slate": {
        "primary": "#0ea5e9",
        "primary_hover": "#0284c7",
        "accent": "#38bdf8",
        "badge_bg": "#0f172a",
        "badge_text": "#7dd3fc",
        "graph_fill": "#0c4a6e",
        "graph_line": "#38bdf8"
    }
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
