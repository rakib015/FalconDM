import os
import sys

# Ensure FalconDM root is in sys.path
_FALCON_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _FALCON_ROOT not in sys.path:
    sys.path.insert(0, _FALCON_ROOT)

import urllib
import urllib.parse
import time
import shutil
import zipfile
import tarfile
import subprocess
import threading
import queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import customtkinter as ctk
from typing import Optional, List, Dict, Any, Callable

try:
    from ..core.engine import DownloadTask, Segment
    from ..core.state_manager import DownloadManager, EXT_CATEGORIES, detect_category
    from ..core.clipboard_watcher import ClipboardWatcher
    from ..core.browser_bridge import BrowserBridge
    from ..core.media_grabber import MediaGrabber
    from ..core.scheduler import QueueScheduler
    from ..core.torrent_engine import TorrentEngine
    from ..core.converter import MediaConverter
    from ..core.credential_manager import credential_store
    from ..core.config_manager import config_store, THEME_PALETTES
    from ..core.notifications import notification_manager
    from ..core.tray_icon import FalconTrayIcon
    from ..core.antivirus_scanner import AntivirusScanner
    from ..core.telegram_bot import telegram_bot
    from ..core.cloud_uploader import cloud_uploader
    from ..core.debrid_resolver import DebridResolver
    from ..core.host_resolvers import HostResolver
    from .dialogs import (
        VideoGrabberDialog,
        BatchDownloadDialog,
        ChecksumDialog,
        BrowserIntegrationDialog,
        SchedulerDialog,
        SpeedLimiterDialog,
        SiteLoginsDialog,
        MediaConverterDialog,
        TorrentDownloadDialog,
        SiteGrabberDialog,
        SettingsDialog,
        FilePropertiesDialog,
        RefreshAddressDialog,
        LiveSpeedHUDDialog,
        QuickLookDialog,
        ShutdownWarningDialog,
        AISecurityDialog,
        AISummaryDialog,
        AINaturalLanguageDialog,
        DownloadLogViewerDialog
    )
    from .download_window import FloatingDownloadDialog
    from .drop_target import FloatingDropBasket
    from .notifications_ui import CyberToastNotification
    from ..core.platform_utils import open_file_or_folder, bring_window_to_front, safe_print
    from ..core.ai_engine import ai_engine
except (ImportError, ValueError):
    from core.engine import DownloadTask, Segment
    from core.state_manager import DownloadManager, EXT_CATEGORIES, detect_category
    from core.clipboard_watcher import ClipboardWatcher
    from core.browser_bridge import BrowserBridge
    from core.media_grabber import MediaGrabber
    from core.scheduler import QueueScheduler
    from core.torrent_engine import TorrentEngine
    from core.converter import MediaConverter
    from core.credential_manager import credential_store
    from core.config_manager import config_store, THEME_PALETTES
    from core.notifications import notification_manager
    from core.tray_icon import FalconTrayIcon
    from core.antivirus_scanner import AntivirusScanner
    from core.telegram_bot import telegram_bot
    from core.cloud_uploader import cloud_uploader
    from core.debrid_resolver import DebridResolver
    from core.host_resolvers import HostResolver
    from core.platform_utils import open_file_or_folder, bring_window_to_front, safe_print
    from core.ai_engine import ai_engine
    from gui.dialogs import (
        VideoGrabberDialog,
        BatchDownloadDialog,
        ChecksumDialog,
        BrowserIntegrationDialog,
        SchedulerDialog,
        SpeedLimiterDialog,
        SiteLoginsDialog,
        MediaConverterDialog,
        TorrentDownloadDialog,
        SiteGrabberDialog,
        SettingsDialog,
        FilePropertiesDialog,
        RefreshAddressDialog,
        LiveSpeedHUDDialog,
        QuickLookDialog,
        ShutdownWarningDialog,
        AISecurityDialog,
        AISummaryDialog,
        AINaturalLanguageDialog,
        DownloadLogViewerDialog
    )
    from gui.download_window import FloatingDownloadDialog
    from gui.drop_target import FloatingDropBasket
    from gui.notifications_ui import CyberToastNotification

# Theme styling
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

def format_bytes(size_bytes: int) -> str:
    if size_bytes <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    while size >= 1024.0 and i < len(units) - 1:
        size /= 1024.0
        i += 1
    return f"{size:.2f} {units[i]}"

def format_speed(bps: float) -> str:
    if bps <= 0:
        return "0.0 KB/s"
    if bps >= 1024 * 1024:
        return f"{bps / (1024 * 1024):.2f} MB/s"
    return f"{bps / 1024:.1f} KB/s"

def format_time(seconds: int) -> str:
    try:
        sec = int(float(seconds))
    except (ValueError, TypeError):
        return "--:--:--"
    if sec <= 0 or sec > 86400 * 30:
        return "--:--:--"
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def get_file_icon(filename: str, category: str = "") -> str:
    ext = os.path.splitext(filename)[1].lower()
    cat = (category or "").lower()
    if cat == "video" or ext in (".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv", ".ts", ".m4v"):
        return "🎬 "
    if cat == "audio" or ext in (".mp3", ".flac", ".wav", ".aac", ".ogg", ".m4a", ".opus", ".wma"):
        return "🎵 "
    if cat == "image" or ext in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".bmp", ".ico", ".tiff", ".avif"):
        return "🖼️ "
    if cat == "compressed" or ext in (".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso", ".dmg"):
        return "📦 "
    if cat == "document" or ext in (".pdf", ".epub", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".txt", ".md"):
        return "📄 "
    if cat == "program" or ext in (".exe", ".msi", ".bat", ".cmd", ".apk", ".dmg", ".bin"):
        return "⚙️ "
    return "📁 "

def format_status_badge(status: str) -> str:
    if status == DownloadTask.STATUS_DOWNLOADING:
        return "⚡ Downloading"
    if status == DownloadTask.STATUS_COMPLETED:
        return "✅ Completed"
    if status == DownloadTask.STATUS_PAUSED:
        return "⏸️ Paused"
    if status == DownloadTask.STATUS_ERROR:
        return "⚠️ Error"
    if status == DownloadTask.STATUS_QUEUED:
        return "⏳ Queued"
    if "reconnect" in status.lower():
        return "🔄 Reconnecting"
    return status


def extract_filename_from_url(url: str) -> str:
    if not url:
        return ""
    try:
        import urllib.parse
        parsed = urllib.parse.urlparse(url)
        clean_path = urllib.parse.unquote(parsed.path)
        name = os.path.basename(clean_path).strip()
        if name and "." in name:
            return name
    except Exception:
        pass
    return ""


class AddDownloadDialog(ctk.CTkToplevel):
    """
    Sleek, modern IDM-style 'Add Download' dialog matching user specification:
    - Row 1: URL input + Copy URL button
    - Row 2: [✔] Use Category checkbox + Category dropdown + '+' button + Live size badge (e.g. 170.02 MB ✔)
    - Row 3: Save folder entry + Browse folder button (📁) + Reset button (🔄)
    - Row 4: Save as Filename entry
    - Row 5: Action buttons: [ Add ] (Queue) | [ Download ] (Start Turbo) | [ Cancel ]
    """
    def __init__(self, parent, on_submit, default_url="", default_filename="", default_category="", initial_size=0, headers=None):
        super().__init__(parent)
        self.title("Add Download")
        self.geometry("580x340")
        self.minsize(540, 310)
        self.resizable(False, False)
        self.on_submit = on_submit
        self.headers = headers or {}
        self.initial_size = initial_size or 0
        self._user_custom_dir = False
        self.var_ask_save = ctk.BooleanVar(value=config_store.get("ask_save_location_everytime", True))
        
        self.base_download_dir = config_store.get("default_download_dir", os.path.join(os.path.expanduser("~"), "Downloads", "FalconDM"))

        # Center dialog directly on the user's primary monitor screen
        try:
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            w, h = 580, 340
            x = max(0, (sw - w) // 2)
            y = max(0, (sh - h) // 2)
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            self.geometry("580x340+300+250")

        # Keep modal reliably in front of browser until user acts (cross-platform)
        bring_window_to_front(self)

        self._build_ui(default_url, default_filename, default_category)
        if default_url:
            self.after(100, self._auto_probe)

    def _resolve_initial_folder(self, sel_cat: str) -> str:
        cat_custom_dirs = config_store.get("category_custom_dirs", {}) or {}
        if getattr(self, "var_use_cat", None) and self.var_use_cat.get():
            if sel_cat in cat_custom_dirs and os.path.isdir(cat_custom_dirs[sel_cat]):
                return cat_custom_dirs[sel_cat]
            return os.path.join(self.base_download_dir, sel_cat)
        else:
            last_dir = config_store.get("last_download_dir", "")
            if config_store.get("remember_last_download_dir", True) and last_dir and os.path.isdir(last_dir):
                return last_dir
            return self.base_download_dir

    def _build_ui(self, default_url: str, default_filename: str, default_category: str = ""):
        self.configure(fg_color="#0e131f")
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=16, pady=16)

        # 1. URL Row
        url_row = ctk.CTkFrame(container, fg_color="transparent")
        url_row.pack(fill="x", pady=(0, 10))

        self.entry_url = ctk.CTkEntry(
            url_row,
            placeholder_text="Download URL (https://...)",
            height=32,
            corner_radius=6,
            fg_color="#0a0d14",
            border_width=1,
            border_color="#1e293b",
            text_color="#f8fafc",
            placeholder_text_color="#64748b"
        )
        self.entry_url.pack(side="left", fill="x", expand=True, padx=(0, 6))
        if default_url:
            self.entry_url.insert(0, default_url)

        btn_copy = ctk.CTkButton(
            url_row,
            text="⧉",
            width=36,
            height=32,
            corner_radius=6,
            fg_color="#1e293b",
            hover_color="#334155",
            border_width=1,
            border_color="#334155",
            text_color="#cbd5e1",
            font=ctk.CTkFont(size=14),
            command=self._copy_url
        )
        btn_copy.pack(side="right")

        # 2. Category & Size Row
        cat_row = ctk.CTkFrame(container, fg_color="transparent")
        cat_row.pack(fill="x", pady=(0, 10))

        self.var_use_cat = ctk.BooleanVar(value=True)
        chk_cat = ctk.CTkCheckBox(
            cat_row,
            text="Use Category",
            variable=self.var_use_cat,
            command=self._on_category_changed,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#6366f1",
            hover_color="#4f46e5",
            text_color="#cbd5e1"
        )
        chk_cat.pack(side="left", padx=(0, 10))

        cat_options = ["Programs", "Compressed", "Video", "Audio", "Documents", "General"]
        self.combo_category = ctk.CTkComboBox(
            cat_row,
            values=cat_options,
            width=130,
            height=30,
            corner_radius=6,
            fg_color="#0a0d14",
            button_color="#1e293b",
            border_color="#1e293b",
            dropdown_fg_color="#111827",
            text_color="#f8fafc",
            command=lambda v: self._on_category_changed()
        )
        # Determine initial category
        clean_init = (default_category or "").strip()
        if clean_init.lower() in ("program", "programs"):
            sel_cat = "Programs"
        elif clean_init.lower() in ("compressed", "archive", "archives"):
            sel_cat = "Compressed"
        elif clean_init.lower() in ("video", "videos"):
            sel_cat = "Video"
        elif clean_init.lower() in ("audio", "music"):
            sel_cat = "Audio"
        elif clean_init.lower() in ("document", "documents"):
            sel_cat = "Documents"
        else:
            detected = detect_category(default_filename or default_url)
            sel_cat = "Programs" if detected == "Program" else (detected if detected in cat_options else "General")

        self.combo_category.set(sel_cat)
        self.combo_category.pack(side="left", padx=(0, 6))

        btn_add_cat = ctk.CTkButton(
            cat_row,
            text="+",
            width=28,
            height=30,
            corner_radius=6,
            fg_color="#1e293b",
            hover_color="#334155",
            border_width=1,
            border_color="#334155",
            text_color="#cbd5e1",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._on_add_category
        )
        btn_add_cat.pack(side="left", padx=(0, 10))

        # Size badge on the right
        self.badge_frame = ctk.CTkFrame(
            cat_row,
            fg_color="#064e3b" if self.initial_size > 0 else "#172554",
            corner_radius=6,
            border_width=1,
            border_color="#059669" if self.initial_size > 0 else "#2563eb",
            height=30
        )
        self.badge_frame.pack(side="right")
        self.badge_frame.pack_propagate(False)

        init_size_text = f"{format_bytes(self.initial_size)} ✔" if self.initial_size > 0 else "⏳ Probing..."
        self.lbl_size_badge = ctk.CTkLabel(
            self.badge_frame,
            text=init_size_text,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#34d399" if self.initial_size > 0 else "#60a5fa",
            padx=10
        )
        self.lbl_size_badge.pack(fill="both", expand=True)

        # 3. Save Folder Row
        dir_row = ctk.CTkFrame(container, fg_color="transparent")
        dir_row.pack(fill="x", pady=(0, 10))

        initial_folder = self._resolve_initial_folder(sel_cat)
        self.entry_dir = ctk.CTkEntry(
            dir_row,
            height=32,
            corner_radius=6,
            fg_color="#0a0d14",
            border_width=1,
            border_color="#1e293b",
            text_color="#f8fafc"
        )
        self.entry_dir.insert(0, initial_folder)
        self.entry_dir.pack(side="left", fill="x", expand=True, padx=(0, 6))

        btn_browse = ctk.CTkButton(
            dir_row,
            text="📁",
            width=36,
            height=32,
            corner_radius=6,
            fg_color="#1e293b",
            hover_color="#334155",
            border_width=1,
            border_color="#334155",
            text_color="#cbd5e1",
            font=ctk.CTkFont(size=13),
            command=self._browse_dir
        )
        btn_browse.pack(side="left", padx=(0, 4))

        btn_reset = ctk.CTkButton(
            dir_row,
            text="🔄",
            width=36,
            height=32,
            corner_radius=6,
            fg_color="#1e293b",
            hover_color="#334155",
            border_width=1,
            border_color="#334155",
            text_color="#cbd5e1",
            font=ctk.CTkFont(size=13),
            command=self._reset_dir
        )
        btn_reset.pack(side="right")

        # 4. Filename Row
        fn_row = ctk.CTkFrame(container, fg_color="transparent")
        fn_row.pack(fill="x", pady=(0, 10))

        self.entry_filename = ctk.CTkEntry(
            fn_row,
            height=32,
            corner_radius=6,
            fg_color="#0a0d14",
            border_width=1,
            border_color="#1e293b",
            text_color="#f8fafc",
            font=ctk.CTkFont(size=11)
        )
        init_name = default_filename or extract_filename_from_url(default_url) or "downloaded_file"
        self.entry_filename.insert(0, init_name)
        self.entry_filename.pack(fill="x", expand=True)

        # 5. Options Row: Remember Folder & Don't Ask Again
        opt_row = ctk.CTkFrame(container, fg_color="transparent")
        opt_row.pack(fill="x", pady=(0, 12))

        self.var_remember_folder = ctk.BooleanVar(value=config_store.get("remember_last_download_dir", True))
        self.chk_remember = ctk.CTkCheckBox(
            opt_row,
            text="Remember this download folder",
            variable=self.var_remember_folder,
            font=ctk.CTkFont(size=11),
            fg_color="#6366f1",
            hover_color="#4f46e5",
            text_color="#cbd5e1",
            checkbox_width=18,
            checkbox_height=18
        )
        self.chk_remember.pack(side="left", padx=(0, 16))

        self.var_dont_ask = ctk.BooleanVar(value=not config_store.get("ask_save_location_everytime", True))
        self.chk_dont_ask = ctk.CTkCheckBox(
            opt_row,
            text="Don't ask again (Auto-download)",
            variable=self.var_dont_ask,
            font=ctk.CTkFont(size=11),
            fg_color="#6366f1",
            hover_color="#4f46e5",
            text_color="#cbd5e1",
            checkbox_width=18,
            checkbox_height=18
        )
        self.chk_dont_ask.pack(side="left")

        # 6. Bottom Action Buttons Row
        btn_row = ctk.CTkFrame(container, fg_color="transparent")
        btn_row.pack(fill="x", side="bottom")

        btn_cancel = ctk.CTkButton(
            btn_row,
            text="Cancel",
            width=85,
            height=32,
            corner_radius=6,
            fg_color="#1e293b",
            hover_color="#334155",
            border_width=1,
            border_color="#334155",
            text_color="#94a3b8",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self.destroy
        )
        btn_cancel.pack(side="right")

        btn_download = ctk.CTkButton(
            btn_row,
            text="Download",
            width=115,
            height=32,
            corner_radius=6,
            fg_color="#6366f1",
            hover_color="#4f46e5",
            border_width=1,
            border_color="#818cf8",
            text_color="#ffffff",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=lambda: self._submit(auto_start=True)
        )
        btn_download.pack(side="right", padx=(0, 8))

        btn_add = ctk.CTkButton(
            btn_row,
            text="Add",
            width=85,
            height=32,
            corner_radius=6,
            fg_color="#1e293b",
            hover_color="#334155",
            border_width=1,
            border_color="#334155",
            text_color="#cbd5e1",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=lambda: self._submit(auto_start=False)
        )
        btn_add.pack(side="right", padx=(0, 8))

    def _copy_url(self):
        try:
            self.clipboard_clear()
            self.clipboard_append(self.entry_url.get().strip())
        except Exception:
            pass

    def _on_category_changed(self):
        if not getattr(self, "_user_custom_dir", False):
            cat = self.combo_category.get()
            new_dir = self._resolve_initial_folder(cat)
            self.entry_dir.delete(0, "end")
            self.entry_dir.insert(0, new_dir)

    def _browse_dir(self):
        initial = self.entry_dir.get().strip() or config_store.get("last_download_dir") or self.base_download_dir
        folder = filedialog.askdirectory(initialdir=initial)
        if folder:
            norm = os.path.normpath(folder)
            self.entry_dir.delete(0, "end")
            self.entry_dir.insert(0, norm)
            self._user_custom_dir = True

    def _reset_dir(self):
        self._user_custom_dir = False
        cat = self.combo_category.get() if self.var_use_cat.get() else ""
        reset_folder = os.path.join(self.base_download_dir, cat) if cat else self.base_download_dir
        self.entry_dir.delete(0, "end")
        self.entry_dir.insert(0, reset_folder)

    def _on_add_category(self):
        from tkinter import simpledialog
        new_cat = simpledialog.askstring("Add Category", "Enter new category name:", parent=self)
        if new_cat and new_cat.strip():
            clean = new_cat.strip().capitalize()
            vals = list(self.combo_category.cget("values"))
            if clean not in vals:
                vals.insert(0, clean)
                self.combo_category.configure(values=vals)
            self.combo_category.set(clean)
            self._on_category_changed()

    def _auto_probe(self):
        url = self.entry_url.get().strip()
        if not url:
            return
        save_folder = self.entry_dir.get().strip() or self.base_download_dir
        headers = dict(self.headers)

        def probe_worker():
            probe_url = url
            probe_filename = None
            if HostResolver.is_resolvable(url):
                try:
                    resolved = HostResolver.resolve_url(url)
                    probe_url = resolved.get("resolved_url") or url
                    probe_filename = resolved.get("filename")
                    if resolved.get("headers"):
                        headers.update(resolved["headers"])
                except Exception:
                    pass

            task = DownloadTask("probe", probe_url, os.path.join(save_folder, probe_filename or "file"), headers=headers)
            success = task.probe()
            if probe_filename and (not task.filename or task.filename in ("file", "download_probe")):
                task.filename = probe_filename

            def update_ui():
                if not self.winfo_exists():
                    return
                if success and task.file_size > 0:
                    self.badge_frame.configure(fg_color="#064e3b", border_color="#059669")
                    self.lbl_size_badge.configure(
                        text=f"{format_bytes(task.file_size)} ✔",
                        text_color="#34d399"
                    )
                    curr = self.entry_filename.get().strip()
                    if (not curr or curr == "downloaded_file") and task.filename:
                        self.entry_filename.delete(0, "end")
                        self.entry_filename.insert(0, task.filename)
                        cat = detect_category(task.filename)
                        if cat != "General":
                            norm_cat = "Programs" if cat == "Program" else (cat if cat in ["Compressed", "Video", "Audio", "Documents"] else cat)
                            self.combo_category.set(norm_cat)
                            if not getattr(self, "_user_custom_dir", False):
                                self._on_category_changed()
                elif success:
                    self.badge_frame.configure(fg_color="#14532d", border_color="#16a34a")
                    self.lbl_size_badge.configure(text="Stream ✔", text_color="#4ade80")
                else:
                    self.badge_frame.configure(fg_color="#172554", border_color="#2563eb")
                    self.lbl_size_badge.configure(text="Direct ✔", text_color="#60a5fa")

            self.after(0, update_ui)

        threading.Thread(target=probe_worker, daemon=True).start()

    def _submit(self, auto_start: bool = True):
        url = self.entry_url.get().strip()
        if not url or not (url.startswith("http://") or url.startswith("https://") or url.startswith("magnet:")):
            messagebox.showerror("Invalid URL", "Please enter a valid HTTP, HTTPS or Magnet download URL.")
            return

        cat = self.combo_category.get()
        save_dir = self.entry_dir.get().strip() or self.base_download_dir
        os.makedirs(save_dir, exist_ok=True)
        filename = self.entry_filename.get().strip() or None

        # Persist folder remembering preference and path
        remember = self.var_remember_folder.get()
        config_store.set("remember_last_download_dir", remember)
        if remember:
            config_store.set("last_download_dir", save_dir)
            if self.var_use_cat.get():
                cat_dirs = dict(config_store.get("category_custom_dirs", {}) or {})
                cat_dirs[cat] = save_dir
                config_store.set("category_custom_dirs", cat_dirs)

        # Update ask_save_location_everytime setting
        dont_ask = self.var_dont_ask.get()
        config_store.set("ask_save_location_everytime", not dont_ask)

        try:
            self.on_submit(url, save_dir, 32, cat, filename, auto_start=auto_start, headers=self.headers)
        except TypeError:
            try:
                self.on_submit(url, save_dir, 32, cat, filename, auto_start)
            except TypeError:
                self.on_submit(url, save_dir, 32, cat, filename)
        self.destroy()


class FalconDMApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("FalconDM v2.8.1 - High Speed Turbo Download Accelerator (Free IDM)")
        self.geometry("1220x780")
        self.minsize(1040, 660)

        # State manager
        self.manager = DownloadManager()
        self.selected_task_id: Optional[str] = None
        self.active_category = "All Downloads"
        self.active_dialogs = {}
        self._active_modal = None
        self.search_var = ctk.StringVar(value="")
        self.segment_panel_collapsed = True
        self.cat_count_labels = {}
        self.clipboard_sniff_enabled = ctk.BooleanVar(value=config_store.get("clipboard_sniff_enabled", True))
        self._completed_tasks_seen = {tid for tid, t in self.manager.tasks.items() if t.status == DownloadTask.STATUS_COMPLETED}
        self._shutdown_dialog_active: bool = False

        self.sort_column = "name"
        self.sort_reverse = False

        # Lightweight Performance & Differential Render Caches
        self._tree_row_cache: Dict[str, tuple] = {}
        self._cat_count_cache: Dict[str, tuple] = {}
        self._last_clipboard_check: float = 0.0
        self._speed_graph_idle_cleared: bool = False
        self._last_spd_text: str = ""
        self._last_total_threads: int = -1
        self._last_counts_tuple: Optional[tuple] = None
        self._idle_trimmed: bool = False

        # Build UI
        self._build_layout()

        # Center main window on screen
        try:
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            w, h = 1220, 780
            x = max(0, (sw - w) // 2)
            y = max(0, (sh - h) // 2)
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            self.geometry("1220x780")

        # Thread-safe UI event queue
        self._ui_queue: queue.Queue = queue.Queue()
        self._check_ui_queue()

        self._setup_auto_refresh()

        # 1. Start Browser Bridge Server (Port 9666 & 15151)
        self.bridge = BrowserBridge(
            port=9666,
            on_download=self._on_browser_incoming_download,
            manager=self.manager,
            on_focus=lambda: self.dispatch_to_main(self.bring_to_front)
        )
        self.bridge.start()

        # 2. Start Automated Queue Scheduler
        self.scheduler = QueueScheduler(self.manager)
        self.scheduler.start()

        # 2b. Start Telegram Remote Bot Daemon
        telegram_bot.manager = self.manager
        if telegram_bot.is_configured():
            telegram_bot.start()

        # 3. Setup Safe Clipboard Watcher
        self.watcher = ClipboardWatcher(
            get_clipboard_fn=self._safe_get_clipboard,
            on_url_detected=self._on_clipboard_url_detected
        )
        self.watcher.enabled = self.clipboard_sniff_enabled.get()

        self.basket = None

        # 4. System Tray Icon (pystray) - callbacks dispatched safely to main thread
        try:
            self.tray = FalconTrayIcon(
                on_open=lambda: self.dispatch_to_main(self._restore_from_tray),
                on_toggle_basket=lambda: None,
                on_resume_all=lambda: self.dispatch_to_main(self._on_resume_all),
                on_pause_all=lambda: self.dispatch_to_main(self._on_pause_all),
                on_open_settings=lambda: self.dispatch_to_main(self._on_click_settings),
                on_exit=lambda: self.dispatch_to_main(self._on_exit_app)
            )
            self.tray.start()
        except Exception as e:
            print(f"[FalconDM Tray] Notice: System tray initialization skipped ({e})")

        # Window Close Protocol (Minimize to tray)
        self.protocol("WM_DELETE_WINDOW", self._on_window_close)

        # Global Keybindings for Power Users
        self.bind("<Control-n>", lambda e: self._on_click_add_url())
        self.bind("<Control-N>", lambda e: self._on_click_add_url())
        self.bind("<Control-f>", lambda e: self._focus_search())
        self.bind("<Control-F>", lambda e: self._focus_search())
        self.bind("<Alt-Up>", lambda e: self._on_move_task_up())
        self.bind("<Alt-Down>", lambda e: self._on_move_task_down())
        self.bind("<F5>", lambda e: self._refresh_table())
        self.bind("<Control-q>", lambda e: self._on_quick_look())
        self.bind("<Control-Q>", lambda e: self._on_quick_look())
        if hasattr(self, 'tree'):
            self.tree.bind("<Delete>", lambda e: self._on_click_delete())
            def _handle_space(e):
                if self.selected_task_id:
                    t = self.manager.tasks.get(self.selected_task_id)
                    if t and t.status == DownloadTask.STATUS_COMPLETED:
                        self._on_quick_look()
                        return "break"
                self._toggle_selected_pause_resume()
                return "break"
            self.tree.bind("<space>", _handle_space)

        # Automatic memory footprint reclaim when minimized to taskbar or tray
        def _on_window_unmap(event):
            if event and event.widget == self:
                try:
                    if getattr(self, "state", lambda: "normal")() in ("iconic", "withdrawn"):
                        from core.platform_utils import trim_memory_footprint
                        self.after(250, trim_memory_footprint)
                except Exception:
                    pass
        self.bind("<Unmap>", _on_window_unmap)

        # Check if requested to start silently in lightweight tray mode
        start_minimized = ("--tray" in sys.argv or "-t" in sys.argv or "--light" in sys.argv or "--eco" in sys.argv)
        if start_minimized:
            self.withdraw()
            from core.platform_utils import trim_memory_footprint
            self.after(500, trim_memory_footprint)
        else:
            self.bring_to_front()

        # Automatic Browser Integration: register native messaging hosts on startup
        try:
            from core.platform_utils import register_browser_integration
            threading.Thread(target=register_browser_integration, daemon=True).start()
        except Exception:
            pass

        # First run check: automatically prompt user with 1-click browser extension setup
        if not config_store.get("extension_setup_prompted", False):
            def _prompt_extension_setup():
                config_store.set("extension_setup_prompted", True)
                if not start_minimized:
                    try:
                        BrowserIntegrationDialog(self)
                    except Exception:
                        pass
            self.after(1200, _prompt_extension_setup)

    def dispatch_to_main(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        """Safely dispatches a callback to execute on the Tkinter mainloop thread."""
        self._ui_queue.put((fn, args, kwargs))

    def _check_ui_queue(self) -> None:
        """Drains and executes all pending cross-thread UI actions safely on the main thread."""
        try:
            while True:
                item = self._ui_queue.get_nowait()
                fn, args, kwargs = item
                try:
                    fn(*args, **kwargs)
                except Exception as e:
                    safe_print(f"[FalconDM UI Queue Error] {e}")
        except queue.Empty:
            pass
        try:
            is_withdrawn = getattr(self, "state", lambda: "normal")() == "withdrawn"
            interval = 180 if is_withdrawn else 60
            self.after(interval, self._check_ui_queue)
        except Exception:
            pass

    def bring_to_front(self, window=None):
        """Cross-platform window activator working on Windows (all versions), Linux (X11/Wayland), and macOS."""
        target = window or self
        bring_window_to_front(target, is_main=(target == self))

    def _safe_get_clipboard(self) -> str:
        try:
            return self.clipboard_get()
        except Exception:
            return ""

    def _build_layout(self):
        self._build_header_bar()
        self._build_toolbar()

        self.center_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.center_frame.pack(fill="both", expand=True, padx=12, pady=(2, 6))

        self._build_sidebar()
        self._build_main_table()

        self._build_segment_panel()
        self._build_statusbar()

    def get_theme_palette(self) -> Dict[str, str]:
        theme_name = config_store.get("ui_theme_accent", "Cyberpunk Cyan")
        return THEME_PALETTES.get(theme_name, THEME_PALETTES["Cyberpunk Cyan"])

    def apply_theme_accent(self, theme_name: Optional[str] = None):
        """Dynamically applies active accent color palette across toolbar buttons, graphs, and UI accents."""
        if theme_name:
            config_store.set("ui_theme_accent", theme_name)
        palette = self.get_theme_palette()
        if hasattr(self, "btn_add"):
            self.btn_add.configure(
                fg_color=palette["primary"],
                hover_color=palette["primary_hover"],
                border_color=palette["accent"]
            )
        if hasattr(self, "header_speed_lbl"):
            self.header_speed_lbl.configure(text_color=palette["accent"])
        self._refresh_table()
        self._draw_speed_graph()

    def _build_header_bar(self):
        header = ctk.CTkFrame(self, fg_color="#0b0f19", height=54, corner_radius=12, border_width=1, border_color="#1e293b")
        header.pack(fill="x", padx=12, pady=(10, 6))
        header.pack_propagate(False)

        # Left brand cluster
        brand_frame = ctk.CTkFrame(header, fg_color="transparent")
        brand_frame.pack(side="left", padx=14, pady=6)

        badge_box = ctk.CTkFrame(brand_frame, width=34, height=34, corner_radius=9, fg_color="#1e1b4b", border_width=1, border_color="#4f46e5")
        badge_box.pack(side="left", padx=(0, 10))
        badge_box.pack_propagate(False)
        ctk.CTkLabel(badge_box, text="⚡", font=ctk.CTkFont(size=17), text_color="#38bdf8").place(relx=0.5, rely=0.5, anchor="center")

        brand_text_box = ctk.CTkFrame(brand_frame, fg_color="transparent")
        brand_text_box.pack(side="left", padx=(0, 12))
        lbl_logo = ctk.CTkLabel(brand_text_box, text="FalconDM v2.8.1", font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"), text_color="#f8fafc")
        lbl_logo.pack(anchor="w")
        lbl_tagline = ctk.CTkLabel(brand_text_box, text="TURBO ENGINE • 32X ACCELERATOR", font=ctk.CTkFont(family="Segoe UI", size=8, weight="bold"), text_color="#818cf8")
        lbl_tagline.pack(anchor="w", pady=(0, 0))

        lbl_status = ctk.CTkLabel(
            brand_frame,
            text="● READY (:9666)",
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color="#34d399",
            fg_color="#062e1c",
            corner_radius=10,
            padx=9,
            pady=3
        )
        lbl_status.pack(side="left")

        # Center search bar
        search_frame = ctk.CTkFrame(header, fg_color="transparent")
        search_frame.pack(side="left", fill="x", expand=True, padx=20, pady=8)

        self.search_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="🔍 Search downloads (Name, Extension, Category, URL)...",
            textvariable=self.search_var,
            height=34,
            corner_radius=8,
            fg_color="#070a12",
            border_width=1,
            border_color="#1e293b",
            text_color="#f8fafc",
            placeholder_text_color="#64748b",
            font=ctk.CTkFont(size=11)
        )
        self.search_entry.pack(fill="x", expand=True)
        self.search_var.trace_add("write", lambda *args: self._refresh_table())

        # Right status & utilities
        right_header = ctk.CTkFrame(header, fg_color="transparent")
        right_header.pack(side="right", padx=12, pady=8)

        self.header_speed_lbl = ctk.CTkLabel(
            right_header,
            text="⚡ 0.0 KB/s",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#38bdf8",
            fg_color="#0c1b30",
            corner_radius=8,
            padx=12,
            pady=5,
            cursor="hand2"
        )
        self.header_speed_lbl.pack(side="left", padx=(0, 8))
        self.header_speed_lbl.bind("<Button-1>", lambda e: self._on_click_speed_hud())

        btn_remote = ctk.CTkButton(
            right_header,
            text="🌐 Web Remote",
            width=105,
            height=32,
            corner_radius=8,
            fg_color="#111827",
            hover_color="#1f2937",
            border_width=1,
            border_color="#374151",
            text_color="#e5e7eb",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._on_click_web_remote
        )
        btn_remote.pack(side="left", padx=(0, 6))

        btn_settings = ctk.CTkButton(
            right_header,
            text="⚙️",
            width=34,
            height=32,
            corner_radius=8,
            fg_color="#111827",
            hover_color="#1f2937",
            border_width=1,
            border_color="#374151",
            text_color="#e5e7eb",
            font=ctk.CTkFont(size=13),
            command=self._on_click_settings
        )
        btn_settings.pack(side="left")

    def _build_toolbar(self):
        toolbar = ctk.CTkFrame(self, fg_color="#0b0f19", height=50, corner_radius=12, border_width=1, border_color="#1e293b")
        toolbar.pack(fill="x", padx=12, pady=(0, 6))
        toolbar.pack_propagate(False)

        palette = self.get_theme_palette()

        # 1. Primary Action: Add URL
        self.btn_add = ctk.CTkButton(
            toolbar,
            text="➕ New Download",
            width=145,
            height=34,
            corner_radius=8,
            fg_color=palette["primary"],
            hover_color=palette["primary_hover"],
            border_width=1,
            border_color=palette["accent"],
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#ffffff",
            command=self._on_click_add_url
        )
        self.btn_add.pack(side="left", padx=(8, 6), pady=8)

        # 2. Core Task Controls with modern semantic hues
        self.btn_resume = ctk.CTkButton(
            toolbar,
            text="▶ Resume",
            width=82,
            height=32,
            corner_radius=8,
            fg_color="#064e3b",
            hover_color="#047857",
            border_width=1,
            border_color="#059669",
            text_color="#6ee7b7",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._on_click_resume
        )
        self.btn_resume.pack(side="left", padx=2, pady=8)

        self.btn_pause = ctk.CTkButton(
            toolbar,
            text="⏸ Pause",
            width=76,
            height=32,
            corner_radius=8,
            fg_color="#451a03",
            hover_color="#78350f",
            border_width=1,
            border_color="#b45309",
            text_color="#fcd34d",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._on_click_pause
        )
        self.btn_pause.pack(side="left", padx=2, pady=8)

        self.btn_delete = ctk.CTkButton(
            toolbar,
            text="🗑 Delete",
            width=76,
            height=32,
            corner_radius=8,
            fg_color="#450a0a",
            hover_color="#7f1d1d",
            border_width=1,
            border_color="#b91c1c",
            text_color="#fca5a5",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._on_click_delete
        )
        self.btn_delete.pack(side="left", padx=2, pady=8)

        btn_open = ctk.CTkButton(
            toolbar,
            text="📁 Folder",
            width=76,
            height=32,
            corner_radius=8,
            fg_color="#111827",
            hover_color="#1f2937",
            border_width=1,
            border_color="#374151",
            text_color="#e5e7eb",
            font=ctk.CTkFont(size=11),
            command=self._on_click_open_folder
        )
        btn_open.pack(side="left", padx=2, pady=8)

        # Divider
        div = ctk.CTkFrame(toolbar, width=1, height=22, fg_color="#1e293b")
        div.pack(side="left", padx=8, pady=13)

        # 3. Supercharged Tools Dropdown Menu
        self.btn_tools = ctk.CTkButton(
            toolbar,
            text="🛠️ Tools  ▾",
            width=92,
            height=32,
            corner_radius=8,
            fg_color="#111827",
            hover_color="#1f2937",
            border_width=1,
            border_color="#374151",
            text_color="#e5e7eb",
            font=ctk.CTkFont(size=11),
            command=self._open_tools_menu
        )
        self.btn_tools.pack(side="left", padx=2, pady=8)

        # 4. Quick Look Preview Button
        self.btn_quick_look = ctk.CTkButton(
            toolbar,
            text="👁️ Quick Look",
            width=100,
            command=self._on_quick_look,
            height=32,
            corner_radius=8,
            fg_color="#172554",
            hover_color="#1e3a8a",
            border_width=1,
            border_color="#2563eb",
            text_color="#93c5fd",
            font=ctk.CTkFont(size=11, weight="bold")
        )
        self.btn_quick_look.pack(side="left", padx=2, pady=8)

        # 5. Live Speed HUD Button
        self.btn_hud = ctk.CTkButton(
            toolbar,
            text="📈 Speed HUD",
            width=100,
            command=self._on_click_speed_hud,
            height=32,
            corner_radius=8,
            fg_color="#082f49",
            hover_color="#075985",
            border_width=1,
            border_color="#0284c7",
            text_color="#38bdf8",
            font=ctk.CTkFont(size=11, weight="bold")
        )
        self.btn_hud.pack(side="left", padx=2, pady=8)

        # 6. AI Agent / Natural Language Downloader Button
        self.btn_ai = ctk.CTkButton(
            toolbar,
            text="✨ AI Agent",
            width=92,
            command=self._open_ai_agent,
            height=32,
            corner_radius=8,
            fg_color="#2e1065",
            hover_color="#3b0764",
            border_width=1,
            border_color="#7c3aed",
            text_color="#c084fc",
            font=ctk.CTkFont(size=11, weight="bold")
        )
        self.btn_ai.pack(side="left", padx=2, pady=8)

        # Right-side controls: Clipboard Sniff Switch & Speed Limiter
        right_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        right_frame.pack(side="right", padx=10, pady=7)

        switch_clip = ctk.CTkSwitch(
            right_frame,
            text="Sniffer",
            variable=self.clipboard_sniff_enabled,
            command=self._on_toggle_clipboard_sniff,
            progress_color="#2563eb",
            font=ctk.CTkFont(size=11)
        )
        switch_clip.pack(side="left", padx=(0, 12))

        ctk.CTkLabel(right_frame, text="Speed:", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(side="left", padx=(0, 4))
        self.speed_limiter_var = ctk.StringVar(value="Unlimited")
        combo_speed = ctk.CTkComboBox(
            right_frame,
            values=["Unlimited", "1 MB/s", "5 MB/s", "10 MB/s", "25 MB/s"],
            width=100,
            height=30,
            corner_radius=8,
            fg_color="#161f2e",
            button_color="#243248",
            border_color="#202c40",
            text_color="#cbd5e1",
            dropdown_fg_color="#0d131f",
            variable=self.speed_limiter_var,
            command=self._on_change_speed_limit
        )
        combo_speed.pack(side="left")

    def _open_tools_menu(self):
        menu = tk.Menu(self, tearoff=0, bg="#141a24", fg="#cbd5e1", activebackground="#1e293b", activeforeground="#ffffff", bd=1)
        menu.add_command(label="🕷️ Site Grabber & Web Crawler", command=self._on_click_site_grabber)
        menu.add_command(label="🎬 Video & Media Grabber", command=self._on_click_grab_video)
        menu.add_command(label="🧲 BitTorrent & Magnet Downloader", command=self._on_click_torrent)
        menu.add_command(label="📦 Batch Pattern Downloader", command=self._on_click_batch)
        menu.add_separator()
        menu.add_command(label="🔄 Media & Audio Converter", command=self._on_click_converter)
        menu.add_command(label="⏱️ Automated Queue Scheduler", command=self._on_click_scheduler)
        menu.add_command(label="🔑 Site Logins & Vault", command=self._on_click_logins)
        menu.add_separator()
        menu.add_command(label="📈 Live Speed & Performance HUD", command=self._on_click_speed_hud)
        menu.add_command(label="🌐 Web Remote Dashboard (:9666)", command=self._on_click_web_remote)
        menu.add_command(label="🧩 Browser Extension Setup", command=self._on_click_browser_ext)
        menu.add_command(label="🔍 File Hash Verifier (SHA256)", command=self._on_click_checksum)
        menu.add_separator()
        menu.add_command(label="✨ AI Natural Language Downloader", command=self._open_ai_agent)
        menu.add_command(label="🛡️ AI Threat & Deception Shield", command=self._on_ai_threat_scan)
        menu.add_separator()
        menu.add_command(label="📥 Import Metalink File (.meta4/.metalink)...", command=self._on_import_metalink)
        menu.add_command(label="📦 Build Extension Store Packages (.zip)...", command=self._on_build_extension_packages)
        menu.add_separator()
        menu.add_command(label="📜 View Download Diagnostics & Error Logs", command=self._open_log_viewer)
        menu.add_command(label="ℹ️ About FalconDM v2.8.1", command=self._show_about_dialog)

        try:
            x = self.btn_tools.winfo_rootx()
            y = self.btn_tools.winfo_rooty() + self.btn_tools.winfo_height() + 2
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _show_about_dialog(self):
        messagebox.showinfo(
            "About FalconDM v2.8.1",
            "FalconDM v2.8.1 (Release 2.8.1)\n\n"
            "High-Speed Turbo Segmented Download Accelerator\n\n"
            "• Up to 32 Parallel Segmented Connection Streams\n"
            "• Universal aria2 & Motrix JSON-RPC Bridge (:6800 / :9666)\n"
            "• JDownloader & pyLoad Click'n'Load v2 Decryption\n"
            "• RFC 5854 Metalink Multi-Mirror Acceleration (.meta4)\n"
            "• Cryptographic Integrity Auto-Verification (SHA-256/MD5)\n"
            "• One-Click cURL Command Export & Multi-dimensional Batch Expansion\n"
            "• Cloud Storage Direct Resolvers (Google Drive, MediaFire, Dropbox, PixelDrain, GitHub)\n"
            "• Anti-Corruption Non-Range Fallback & In-Flight Demotion\n"
            "• Multi-Thread Video & Audio Stream Grabber\n"
            "• Automated Queue Scheduler & Dynamic Bandwidth Limiter\n\n"
            "Status: v2.8.1 Active & Ready"
        )

    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self.center_frame, width=220, fg_color="#0b0f19", corner_radius=12, border_width=1, border_color="#1e293b")
        sidebar.pack(side="left", fill="y", padx=(0, 10), pady=0)
        sidebar.pack_propagate(False)

        lbl_cat = ctk.CTkLabel(sidebar, text="D A S H B O A R D", font=ctk.CTkFont(size=9, weight="bold"), text_color="#64748b")
        lbl_cat.pack(anchor="w", padx=16, pady=(12, 4))

        self.cat_buttons = {}
        self.cat_count_labels = {}
        
        main_categories = [
            ("All Downloads", "📥 All Downloads"),
            ("Unfinished", "⚡ In Progress"),
            ("Finished", "✓ Completed"),
            ("Paused", "⏸ Paused / Stopped"),
        ]

        for cat_key, label in main_categories:
            item_row = ctk.CTkFrame(sidebar, fg_color="transparent", height=32)
            item_row.pack(fill="x", padx=6, pady=1)
            item_row.pack_propagate(False)

            is_active = (cat_key == "All Downloads")
            btn = ctk.CTkButton(
                item_row,
                text=label,
                anchor="w",
                height=32,
                corner_radius=8,
                fg_color="#1e3a6a" if is_active else "transparent",
                border_width=1 if is_active else 0,
                border_color="#2563eb" if is_active else "#0d131f",
                text_color="#ffffff" if is_active else "#94a3b8",
                hover_color="#161f2e",
                font=ctk.CTkFont(size=11, weight="bold" if is_active else "normal"),
                command=lambda k=cat_key: self._on_select_category(k)
            )
            btn.pack(side="left", fill="both", expand=True)
            self.cat_buttons[cat_key] = btn

            badge = ctk.CTkLabel(
                item_row,
                text="0",
                width=24,
                height=18,
                corner_radius=9,
                fg_color="#2563eb" if is_active else "#161f2e",
                text_color="#ffffff" if is_active else "#64748b",
                font=ctk.CTkFont(size=9, weight="bold")
            )
            badge.place(relx=1.0, rely=0.5, anchor="e", x=-6)
            self.cat_count_labels[cat_key] = badge

        # Media section
        lbl_media = ctk.CTkLabel(sidebar, text="F I L E  T Y P E S", font=ctk.CTkFont(size=9, weight="bold"), text_color="#64748b")
        lbl_media.pack(anchor="w", padx=16, pady=(12, 4))

        media_categories = [
            ("Video", "🎬 Videos"),
            ("Audio", "🎵 Audio"),
            ("Image", "🖼️ Images"),
            ("Compressed", "📦 Compressed"),
            ("Document", "📄 Documents"),
            ("Program", "⚙️ Programs")
        ]

        for cat_key, label in media_categories:
            item_row = ctk.CTkFrame(sidebar, fg_color="transparent", height=32)
            item_row.pack(fill="x", padx=6, pady=1)
            item_row.pack_propagate(False)

            btn = ctk.CTkButton(
                item_row,
                text=label,
                anchor="w",
                height=32,
                corner_radius=8,
                fg_color="transparent",
                border_width=0,
                border_color="#0d131f",
                text_color="#94a3b8",
                hover_color="#161f2e",
                font=ctk.CTkFont(size=11),
                command=lambda k=cat_key: self._on_select_category(k)
            )
            btn.pack(side="left", fill="both", expand=True)
            self.cat_buttons[cat_key] = btn

            badge = ctk.CTkLabel(
                item_row,
                text="0",
                width=24,
                height=18,
                corner_radius=9,
                fg_color="#161f2e",
                text_color="#64748b",
                font=ctk.CTkFont(size=9, weight="bold")
            )
            badge.place(relx=1.0, rely=0.5, anchor="e", x=-6)
            self.cat_count_labels[cat_key] = badge

        # Bottom Hardware Speedometer & Waveform
        speedo_frame = ctk.CTkFrame(sidebar, fg_color="#070a12", corner_radius=10, border_width=1, border_color="#1e293b", cursor="hand2")
        speedo_frame.pack(side="bottom", fill="x", padx=8, pady=10)
        speedo_frame.bind("<Button-1>", lambda e: self._on_click_speed_hud())

        top_spd = ctk.CTkFrame(speedo_frame, fg_color="transparent")
        top_spd.pack(fill="x", padx=8, pady=(8, 0))
        lbl_tp = ctk.CTkLabel(top_spd, text="● THROUGHPUT", font=ctk.CTkFont(size=9, weight="bold"), text_color="#10b981")
        lbl_tp.pack(side="left")
        lbl_tp.bind("<Button-1>", lambda e: self._on_click_speed_hud())
        self.lbl_peak_speed = ctk.CTkLabel(top_spd, text="Peak: 0.0 KB/s", font=ctk.CTkFont(size=8, weight="bold"), text_color="#38bdf8")
        self.lbl_peak_speed.pack(side="right")
        self.lbl_peak_speed.bind("<Button-1>", lambda e: self._on_click_speed_hud())

        self.lbl_global_speed = ctk.CTkLabel(speedo_frame, text="0.0 KB/s", font=ctk.CTkFont(size=19, weight="bold"), text_color="#38bdf8", cursor="hand2")
        self.lbl_global_speed.pack(pady=(1, 2))
        self.lbl_global_speed.bind("<Button-1>", lambda e: self._on_click_speed_hud())
        
        # Live Waveform Graph Canvas (Cyber Obsidian glow)
        self.speed_canvas = tk.Canvas(speedo_frame, width=188, height=48, bg="#05080e", highlightthickness=1, highlightbackground="#162030", cursor="hand2")
        self.speed_canvas.pack(padx=6, pady=(1, 4))
        self.speed_canvas.bind("<Button-1>", lambda e: self._on_click_speed_hud())
        self.speed_history = [0.0] * 48
        self.peak_speed_seen = 0.0

        self.lbl_active_streams = ctk.CTkLabel(speedo_frame, text="⚡ 0 Streams Connected", font=ctk.CTkFont(size=10), text_color="#64748b", cursor="hand2")
        self.lbl_active_streams.pack(pady=(0, 2))
        self.lbl_active_streams.bind("<Button-1>", lambda e: self._on_click_speed_hud())

        lbl_hud_link = ctk.CTkLabel(speedo_frame, text="📊 Open Live Speed HUD ↗", font=ctk.CTkFont(size=9, weight="bold"), text_color="#38bdf8", cursor="hand2")
        lbl_hud_link.pack(pady=(0, 6))
        lbl_hud_link.bind("<Button-1>", lambda e: self._on_click_speed_hud())

    def _build_main_table(self):
        self.table_container = ctk.CTkFrame(self.center_frame, fg_color="#0b0f19", corner_radius=12, border_width=1, border_color="#1e293b")
        self.table_container.pack(side="right", fill="both", expand=True)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background="#070a12",
            foreground="#e2e8f0",
            rowheight=38,
            fieldbackground="#070a12",
            bordercolor="#1e293b",
            borderwidth=0,
            font=("Segoe UI", 10)
        )
        style.configure(
            "Treeview.Heading",
            background="#0f172a",
            foreground="#94a3b8",
            relief="flat",
            font=("Segoe UI", 10, "bold"),
            padding=(6, 8)
        )
        style.map("Treeview", background=[("selected", "#1e3a6a")], foreground=[("selected", "#ffffff")])
        style.map("Treeview.Heading", background=[("active", "#1e293b")], foreground=[("active", "#38bdf8")])

        columns = ("name", "size", "status", "progress", "speed", "eta", "category")
        self.tree = ttk.Treeview(self.table_container, columns=columns, show="headings", selectmode="browse")
        
        self.tree.tag_configure("odd_row", background="#070a12")
        self.tree.tag_configure("even_row", background="#0b101d")

        self.tree.heading("name", text="File Name", command=lambda: self._on_click_column_header("name"))
        self.tree.heading("size", text="Size", command=lambda: self._on_click_column_header("size"))
        self.tree.heading("status", text="Status", command=lambda: self._on_click_column_header("status"))
        self.tree.heading("progress", text="Progress", command=lambda: self._on_click_column_header("progress"))
        self.tree.heading("speed", text="Speed", command=lambda: self._on_click_column_header("speed"))
        self.tree.heading("eta", text="Time Left", command=lambda: self._on_click_column_header("eta"))
        self.tree.heading("category", text="Category", command=lambda: self._on_click_column_header("category"))

        self.tree.column("name", width=320, anchor="w")
        self.tree.column("size", width=85, anchor="center")
        self.tree.column("status", width=110, anchor="center")
        self.tree.column("progress", width=130, anchor="center")
        self.tree.column("speed", width=95, anchor="center")
        self.tree.column("eta", width=85, anchor="center")
        self.tree.column("category", width=90, anchor="center")

        scrollbar = ttk.Scrollbar(self.table_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)
        scrollbar.pack(side="right", fill="y", padx=(0, 6), pady=6)

        # Empty state view
        self.empty_state = ctk.CTkFrame(self.table_container, fg_color="#0e1524", corner_radius=12, border_width=1, border_color="#1e293b", width=420, height=210)
        self.empty_state.pack_propagate(False)
        
        badge = ctk.CTkFrame(self.empty_state, width=44, height=44, corner_radius=22, fg_color="#172554", border_width=1, border_color="#1e40af")
        badge.pack(pady=(22, 8))
        badge.pack_propagate(False)
        ctk.CTkLabel(badge, text="⚡", font=ctk.CTkFont(size=20), text_color="#38bdf8").place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(self.empty_state, text="Ready for Turbo Acceleration", font=ctk.CTkFont(size=14, weight="bold"), text_color="#f8fafc").pack(pady=(0, 4))
        ctk.CTkLabel(self.empty_state, text="Paste any download link, video URL, or torrent to begin.", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(pady=(0, 14))
        
        btn_box = ctk.CTkFrame(self.empty_state, fg_color="transparent")
        btn_box.pack()
        ctk.CTkButton(btn_box, text="➕ Add Download Now", fg_color="#2563eb", hover_color="#1d4ed8", font=ctk.CTkFont(size=11, weight="bold"), height=32, width=156, corner_radius=8, command=self._on_click_add_url).pack(side="left", padx=4)
        ctk.CTkButton(btn_box, text="🌐 Web Remote", fg_color="#161f2e", hover_color="#243248", border_width=1, border_color="#202c40", text_color="#cbd5e1", font=ctk.CTkFont(size=11), height=32, width=110, corner_radius=8, command=self._on_click_web_remote).pack(side="left", padx=4)

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", self._on_tree_double_click)
        self.tree.bind("<Button-3>", self._on_tree_right_click)
        self.tree.bind("<Return>", lambda e: self._on_tree_double_click(None))
        self.tree.bind("<Alt-Return>", lambda e: self._open_file_properties())

        # Comprehensive Power User Context Menu
        self.context_menu = tk.Menu(self, tearoff=0, bg="#141a24", fg="#cbd5e1", activebackground="#1e293b", activeforeground="#ffffff", bd=1)
        self.context_menu.add_command(label="👁️ Quick Look Preview (Space)", command=self._on_quick_look)
        self.context_menu.add_command(label="▶ Open File", command=self._on_context_open_file)
        self.context_menu.add_command(label="📁 Open Containing Folder", command=self._on_click_open_folder)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="⚡ Show Floating Progress Monitor", command=self._open_floating_window)
        self.context_menu.add_command(label="📈 Live Speed & Performance HUD", command=self._on_click_speed_hud)
        self.context_menu.add_command(label="🔄 Refresh Download Address (URL)...", command=self._on_click_refresh_address)
        self.context_menu.add_command(label="🔗 Add Fallback Mirror URL...", command=self._on_add_mirror_url)
        self.context_menu.add_command(label="ℹ️ Properties & Info...", command=self._open_file_properties)
        self.context_menu.add_command(label="📜 View Diagnostics & Error Log...", command=self._on_context_view_log)
        self.context_menu.add_separator()
        
        # Priority & Queue Control Submenu
        self.priority_menu = tk.Menu(self.context_menu, tearoff=0, bg="#141a24", fg="#cbd5e1", activebackground="#1e293b", activeforeground="#ffffff")
        self.priority_menu.add_command(label="⚡ High Priority (Download First)", command=lambda: self._set_selected_priority(2))
        self.priority_menu.add_command(label="• Normal Priority", command=lambda: self._set_selected_priority(1))
        self.priority_menu.add_command(label="↓ Low Priority (Background)", command=lambda: self._set_selected_priority(0))
        self.context_menu.add_cascade(label="⭐ Set Download Priority", menu=self.priority_menu)

        self.context_menu.add_command(label="⬆️ Move Up in Queue (Alt+Up)", command=self._on_move_task_up)
        self.context_menu.add_command(label="⬇️ Move Down in Queue (Alt+Down)", command=self._on_move_task_down)
        self.context_menu.add_command(label="⏫ Move to Top of Queue", command=self._on_move_task_top)
        self.context_menu.add_command(label="⏬ Move to Bottom of Queue", command=self._on_move_task_bottom)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="▶ Resume Download", command=self._on_click_resume)
        self.context_menu.add_command(label="⏸ Pause Download", command=self._on_click_pause)
        self.context_menu.add_command(label="🔄 Redownload (From 0%)", command=self._on_redownload)
        self.context_menu.add_command(label="▶ Resume All Downloads", command=self._on_resume_all)
        self.context_menu.add_command(label="⏸ Pause All Downloads", command=self._on_pause_all)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="🎬 Preview / Play Media", command=self._on_context_preview)
        self.context_menu.add_command(label="⚡ Toggle Sequential Stream Mode", command=self._on_toggle_sequential)
        self.context_menu.add_command(label="🔄 Convert / Extract MP3...", command=self._on_context_convert)
        self.context_menu.add_command(label="📦 Extract Archive (.zip/.tar)...", command=self._on_context_extract)
        self.context_menu.add_command(label="🛡️ Scan with Windows Defender", command=self._on_context_scan_av)
        self.context_menu.add_command(label="🔍 Checksum (MD5/SHA256)", command=self._on_context_checksum)
        self.context_menu.add_command(label="📋 Copy Download Link", command=self._on_copy_link)
        self.context_menu.add_command(label="📋 Copy as cURL Command", command=self._on_copy_curl_command)
        self.context_menu.add_command(label="📋 Copy File Path", command=self._on_copy_file_path)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="✨ AI Summary & Key Takeaways", command=self._on_ai_summary)
        self.context_menu.add_command(label="🎙️ AI Generate Subtitles (.srt)", command=self._on_ai_subtitles)
        self.context_menu.add_command(label="🛡️ AI Threat & Deception Scan", command=self._on_ai_threat_scan)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="📄 Export Links to File...", command=self._on_export_links)
        self.context_menu.add_command(label="🗑 Clear Completed Downloads", command=self._on_clear_completed)
        self.context_menu.add_command(label="🗑 Remove from List", command=self._on_click_delete)

    def _build_segment_panel(self):
        self.segment_box = ctk.CTkFrame(self, fg_color="#0d131f", height=36, corner_radius=10, border_width=1, border_color="#1e293b")
        self.segment_box.pack(fill="x", padx=12, pady=(0, 6))
        self.segment_box.pack_propagate(False)

        top_row = ctk.CTkFrame(self.segment_box, fg_color="transparent")
        top_row.pack(fill="x", padx=14, pady=(6, 4))

        # Bottom panel mode: "graph" (default) or "segments"
        self.bottom_panel_mode = "graph"

        mode_box = ctk.CTkFrame(top_row, fg_color="#141c2c", corner_radius=6, border_width=1, border_color="#1f2c42")
        mode_box.pack(side="left", padx=(0, 10))

        self.btn_mode_graph = ctk.CTkButton(
            mode_box,
            text="📈 Live Speed Curve",
            width=135,
            height=22,
            corner_radius=4,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            text_color="#ffffff",
            font=ctk.CTkFont(size=10, weight="bold"),
            command=lambda: self._set_bottom_mode("graph")
        )
        self.btn_mode_graph.pack(side="left", padx=2, pady=2)

        self.btn_mode_segments = ctk.CTkButton(
            mode_box,
            text="🧩 Connection Chunks",
            width=135,
            height=22,
            corner_radius=4,
            fg_color="transparent",
            hover_color="#1f2c42",
            text_color="#94a3b8",
            font=ctk.CTkFont(size=10, weight="bold"),
            command=lambda: self._set_bottom_mode("segments")
        )
        self.btn_mode_segments.pack(side="left", padx=2, pady=2)

        self.lbl_segment_title = ctk.CTkLabel(
            top_row,
            text="Real-Time Bandwidth: 0.0 KB/s  •  Peak: 0.0 KB/s  •  Rolling 60s Window",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#94a3b8"
        )
        self.lbl_segment_title.pack(side="left", fill="x", expand=True)

        self.btn_toggle_segments = ctk.CTkButton(
            top_row,
            text="▼ Expand",
            width=76,
            height=22,
            corner_radius=6,
            fg_color="#161f2e",
            hover_color="#243248",
            border_width=1,
            border_color="#202c40",
            text_color="#38bdf8",
            font=ctk.CTkFont(size=10, weight="bold"),
            command=self._toggle_segment_panel
        )
        self.btn_toggle_segments.pack(side="right")

        self.bottom_content_frame = ctk.CTkFrame(self.segment_box, fg_color="transparent")

        # Full-width Live Speed Graph Canvas
        self.main_speed_canvas = tk.Canvas(
            self.bottom_content_frame,
            height=100,
            bg="#060910",
            highlightthickness=1,
            highlightbackground="#182338",
            cursor="crosshair"
        )

        # IDM-Style Full-Width Segment Map Canvas
        self.main_segment_map_canvas = tk.Canvas(
            self.bottom_content_frame,
            height=20,
            bg="#060910",
            highlightthickness=1,
            highlightbackground="#182338"
        )

        self.seg_scroll = None
        self.seg_widgets = []

    def _set_bottom_mode(self, mode: str):
        self.bottom_panel_mode = mode
        if mode == "graph":
            self.btn_mode_graph.configure(fg_color="#2563eb", text_color="#ffffff")
            self.btn_mode_segments.configure(fg_color="transparent", text_color="#94a3b8")
            if not self.segment_panel_collapsed:
                if self.seg_scroll:
                    self.seg_scroll.pack_forget()
                if hasattr(self, 'main_segment_map_canvas'):
                    self.main_segment_map_canvas.pack_forget()
                self.main_speed_canvas.pack(fill="both", expand=True, padx=8, pady=(0, 6))
                self._draw_speed_graph()
        else:
            self.btn_mode_segments.configure(fg_color="#2563eb", text_color="#ffffff")
            self.btn_mode_graph.configure(fg_color="transparent", text_color="#94a3b8")
            if not self.segment_panel_collapsed:
                self.main_speed_canvas.pack_forget()
                if hasattr(self, 'main_segment_map_canvas'):
                    self.main_segment_map_canvas.pack(fill="x", padx=8, pady=(0, 4))
                if self.seg_scroll is None:
                    self.seg_scroll = ctk.CTkScrollableFrame(self.bottom_content_frame, orientation="horizontal", fg_color="transparent", height=66)
                self.seg_scroll.pack(fill="both", expand=True, padx=8, pady=(0, 6))
                self._update_segment_monitor()

    def _toggle_segment_panel(self):
        if not self.segment_panel_collapsed:
            self.segment_box.configure(height=36)
            self.bottom_content_frame.pack_forget()
            self.btn_toggle_segments.configure(text="▼ Expand")
            self.segment_panel_collapsed = True
        else:
            self.segment_box.configure(height=148)
            self.bottom_content_frame.pack(fill="both", expand=True, padx=8, pady=(0, 6))
            self.btn_toggle_segments.configure(text="▲ Collapse")
            self.segment_panel_collapsed = False
            self._set_bottom_mode(self.bottom_panel_mode)

    def _build_statusbar(self):
        self.statusbar = ctk.CTkFrame(self, fg_color="#080c14", height=28, corner_radius=0, border_width=1, border_color="#182234")
        self.statusbar.pack(fill="x", side="bottom")

        self.lbl_status_left = ctk.CTkLabel(
            self.statusbar,
            text="🟢 Bridge: 127.0.0.1:9666  •  Sniffer: Active",
            font=ctk.CTkFont(size=10),
            text_color="#94a3b8"
        )
        self.lbl_status_left.pack(side="left", padx=16)

        self.lbl_status_center = ctk.CTkLabel(
            self.statusbar,
            text="⚡ Tasks: 0 Active, 0 Completed",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#cbd5e1"
        )
        self.lbl_status_center.pack(side="left", expand=True)

        # Global Speed Throttle Selector
        throttle_box = ctk.CTkFrame(self.statusbar, fg_color="transparent")
        throttle_box.pack(side="right", padx=(0, 12))

        ctk.CTkLabel(throttle_box, text="Global Speed:", font=ctk.CTkFont(size=10, weight="bold"), text_color="#94a3b8").pack(side="left", padx=(0, 6))
        self.combo_global_speed = ctk.CTkComboBox(
            throttle_box,
            values=["Unlimited", "512 KB/s", "1 MB/s", "2 MB/s", "5 MB/s", "10 MB/s", "20 MB/s"],
            width=105,
            height=22,
            corner_radius=4,
            fg_color="#0d131f",
            button_color="#1e293b",
            border_color="#1e293b",
            text_color="#38bdf8",
            dropdown_fg_color="#0d131f",
            font=ctk.CTkFont(size=9, weight="bold"),
            command=self._on_change_global_speed
        )
        saved_limit = config_store.get("global_speed_limit_bps", 0)
        speed_label = "Unlimited"
        if saved_limit > 0:
            if saved_limit >= 1024 * 1024:
                speed_label = f"{saved_limit // (1024 * 1024)} MB/s"
            else:
                speed_label = f"{saved_limit // 1024} KB/s"
            self.manager.set_global_speed_limit(saved_limit)
        self.combo_global_speed.set(speed_label)
        self.combo_global_speed.pack(side="left")

        self.lbl_status_right = ctk.CTkLabel(
            self.statusbar,
            text="FalconDM Turbo Engine 2.0 • Multi-Stream Acceleration",
            font=ctk.CTkFont(size=10),
            text_color="#64748b"
        )
        self.lbl_status_right.pack(side="right", padx=16)

    def _on_change_global_speed(self, choice: str):
        speed_map = {
            "Unlimited": 0,
            "512 KB/s": 512 * 1024,
            "1 MB/s": 1024 * 1024,
            "2 MB/s": 2 * 1024 * 1024,
            "5 MB/s": 5 * 1024 * 1024,
            "10 MB/s": 10 * 1024 * 1024,
            "20 MB/s": 20 * 1024 * 1024,
        }
        bps = speed_map.get(choice, 0)
        self.manager.set_global_speed_limit(bps)
        config_store.set("global_speed_limit_bps", bps)
        if hasattr(self, 'lbl_status_right'):
            if bps > 0:
                self.lbl_status_right.configure(text=f"FalconDM Turbo • Global Cap: {choice}", text_color="#f59e0b")
            else:
                self.lbl_status_right.configure(text="FalconDM Turbo Engine 2.0 • Multi-Stream Acceleration", text_color="#64748b")

    # ================== Dialog Openers ==================

    def _on_click_add_url(self):
        clip_url = ""
        try:
            cb = self.clipboard_get().strip()
            if cb.startswith("http://") or cb.startswith("https://"):
                clip_url = cb
        except Exception:
            pass
        AddDownloadDialog(self, on_submit=self._create_download, default_url=clip_url)

    def _on_click_grab_video(self):
        clip_url = ""
        try:
            cb = self.clipboard_get().strip()
            if cb.startswith("http://") or cb.startswith("https://"):
                clip_url = cb
        except Exception:
            pass
        VideoGrabberDialog(self, on_download_video=self._download_video_stream, default_url=clip_url)

    def _on_click_batch(self):
        BatchDownloadDialog(self, on_enqueue_batch=self._enqueue_batch_urls)

    def _on_click_checksum(self):
        selected_file = ""
        if self.selected_task_id:
            task = self.manager.tasks.get(self.selected_task_id)
            if task and os.path.exists(task.save_path):
                selected_file = task.save_path
        ChecksumDialog(self, initial_file=selected_file)

    def _on_click_browser_ext(self):
        BrowserIntegrationDialog(self)

    def _on_click_scheduler(self):
        SchedulerDialog(self, self.scheduler)

    def _on_click_speed_limiter(self):
        SpeedLimiterDialog(self, self.manager)

    def _on_click_torrent(self):
        clip_url = ""
        try:
            cb = self.clipboard_get().strip()
            if cb.startswith("magnet:?") or cb.endswith(".torrent"):
                clip_url = cb
        except Exception:
            pass
        TorrentDownloadDialog(self, on_start_torrent=self._download_torrent_stream, default_source=clip_url)

    def _on_click_converter(self):
        selected_file = ""
        if self.selected_task_id:
            task = self.manager.tasks.get(self.selected_task_id)
            if task and os.path.exists(task.save_path):
                selected_file = task.save_path
        MediaConverterDialog(self, initial_file=selected_file)

    def _on_click_logins(self):
        SiteLoginsDialog(self)

    def _on_toggle_basket(self):
        # Permanently disabled as per user configuration
        pass

    def _on_click_site_grabber(self):
        SiteGrabberDialog(self, on_enqueue_batch=self._enqueue_batch_urls)

    def _on_click_settings(self):
        SettingsDialog(self, on_save_callback=self._on_settings_applied)

    def _on_click_speed_hud(self):
        LiveSpeedHUDDialog(self, self.manager)

    def _on_click_refresh_address(self):
        if not self.selected_task_id:
            messagebox.showinfo("No Selection", "Please select a download from the list to refresh its address.")
            return
        task = self.manager.tasks.get(self.selected_task_id)
        if not task:
            return
        RefreshAddressDialog(self, task, self.manager, on_refreshed=self._refresh_table)

    def _set_selected_priority(self, priority: int):
        if not self.selected_task_id:
            messagebox.showinfo("No Selection", "Please select a download to set its priority.")
            return
        if self.manager.set_task_priority(self.selected_task_id, priority):
            self._refresh_table()

    def _on_move_task_up(self):
        if not self.selected_task_id:
            return
        if self.manager.move_task_up(self.selected_task_id):
            self._refresh_table()

    def _on_move_task_down(self):
        if not self.selected_task_id:
            return
        if self.manager.move_task_down(self.selected_task_id):
            self._refresh_table()

    def _on_move_task_top(self):
        if not self.selected_task_id:
            return
        if self.manager.move_task_to_top(self.selected_task_id):
            self._refresh_table()

    def _on_move_task_bottom(self):
        if not self.selected_task_id:
            return
        if self.manager.move_task_to_bottom(self.selected_task_id):
            self._refresh_table()

    def _on_add_mirror_url(self):
        if not self.selected_task_id:
            messagebox.showinfo("Select Download", "Please select a download to add a mirror URL.")
            return
        task = self.manager.tasks.get(self.selected_task_id)
        if not task:
            return
        prompt_dlg = ctk.CTkInputDialog(text=f"Enter fallback mirror URL for '{task.filename}':", title="Add Mirror URL")
        mirror_url = prompt_dlg.get_input()
        if mirror_url and mirror_url.strip():
            added = self.manager.add_task_mirror(self.selected_task_id, mirror_url.strip())
            if added:
                messagebox.showinfo("Mirror Added", f"✅ Fallback mirror added successfully to '{task.filename}'.")
                self._refresh_table()
            else:
                messagebox.showwarning("Mirror Exists", "Mirror URL is already configured or identical to source.")

    def _open_ai_agent(self):
        AINaturalLanguageDialog(self, on_enqueue_batch=self._enqueue_batch_urls)

    def _on_ai_summary(self):
        if not self.selected_task_id:
            messagebox.showinfo("Select a Download", "Please select a download to generate an AI summary.")
            return
        task = self.manager.tasks.get(self.selected_task_id)
        if not task:
            return
        AISummaryDialog(self, file_path=task.save_path, url=task.url, title=task.filename)

    def _on_ai_subtitles(self):
        if not self.selected_task_id:
            messagebox.showinfo("Select a Video", "Please select a video download to extract subtitles.")
            return
        task = self.manager.tasks.get(self.selected_task_id)
        if not task:
            return
        
        def worker():
            srt_path = ai_engine.extract_subtitles(task.save_path, url=task.url)
            def done():
                if srt_path and os.path.exists(srt_path):
                    messagebox.showinfo("Subtitles Generated", f"✅ Subtitles generated successfully:\n\n{srt_path}")
                    open_file_or_folder(srt_path, select=True)
                else:
                    messagebox.showinfo("Subtitles", "Could not extract automatic subtitles for this stream.")
            self.after(0, done)

        threading.Thread(target=worker, daemon=True).start()
        messagebox.showinfo("Generating Subtitles", "FalconDM AI is extracting and aligning subtitles in the background...")

    def _on_ai_threat_scan(self):
        target_path = ""
        if self.selected_task_id:
            task = self.manager.tasks.get(self.selected_task_id)
            if task and os.path.exists(task.save_path):
                target_path = task.save_path
        if not target_path:
            f = filedialog.askopenfilename(title="Select File for AI Threat & Deception Scan")
            if f:
                target_path = f
        if target_path:
            AISecurityDialog(self, target_path)

    def _on_settings_applied(self):
        self.apply_theme_accent()
        self.clipboard_sniff_enabled.set(config_store.get("clipboard_sniff_enabled", True))
        if hasattr(self, 'watcher'):
            self.watcher.enabled = self.clipboard_sniff_enabled.get()
        if self.basket and hasattr(self.basket, 'withdraw'):
            self.basket.withdraw()

    def _on_window_close(self):
        if config_store.get("minimize_to_tray_on_close", True):
            self.withdraw()
            from core.platform_utils import trim_memory_footprint
            self.after(200, trim_memory_footprint)
            if hasattr(self, 'tray'):
                self.tray.notify("FalconDM Minimized", "FalconDM is running in the background in your system tray.")
        else:
            self._on_exit_app()

    def _restore_from_tray(self):
        try:
            self.deiconify()
            self.state('normal')
            self.lift()
            self.focus_force()
        except Exception:
            pass

    def _on_exit_app(self):
        try:
            if hasattr(self, 'tray'):
                self.tray.stop()
        except Exception:
            pass
        self.destroy()
        os._exit(0)

    def _on_resume_all(self):
        for task_id in list(self.manager.tasks.keys()):
            self.manager.resume_task(task_id)
        self._refresh_table()

    def _on_pause_all(self):
        for task_id in list(self.manager.tasks.keys()):
            self.manager.pause_task(task_id)
        self._refresh_table()

    def _on_clear_completed(self):
        to_del = [tid for tid, t in self.manager.tasks.items() if t.status == DownloadTask.STATUS_COMPLETED]
        for tid in to_del:
            self.manager.remove_task(tid, delete_file=False)
            self._tree_row_cache.pop(tid, None)
        self.selected_task_id = None
        self._refresh_table()
        self._clear_segment_monitor()
        from core.platform_utils import trim_memory_footprint
        self.after(200, trim_memory_footprint)

    # ================== Background Events ==================

    def _on_clipboard_url_detected(self, url: str):
        if not self.clipboard_sniff_enabled.get():
            return
        
        # Don't pop up if a dialog is already showing
        if hasattr(self, '_active_modal') and self._active_modal and self._active_modal.winfo_exists():
            return

        def prompt_user():
            # Double check if url already active
            for t in self.manager.tasks.values():
                if t.url == url and t.status in ("Downloading", "Queued"):
                    return
            
            if hasattr(self, '_active_modal') and self._active_modal and self._active_modal.winfo_exists():
                return

            # If it's a media site, open Video Grabber, else Add Download Dialog
            if MediaGrabber.is_likely_media_url(url):
                self._active_modal = VideoGrabberDialog(self, on_download_video=self._download_video_stream, default_url=url)
            else:
                self._active_modal = AddDownloadDialog(self, on_submit=self._create_download, default_url=url)

        self.dispatch_to_main(prompt_user)

    def _on_browser_incoming_download(self, data: dict):
        url = data.get("url", "")
        filename = data.get("filename", "")
        headers = data.get("headers", {})
        queue_name = data.get("queue_name", "Default")
        format_id = data.get("format_id", "")
        def handle():
            nonlocal url, filename, headers
            try:
                self.bring_to_front()

                # Resolve cloud storage links if applicable
                if HostResolver.is_resolvable(url):
                    try:
                        resolved = HostResolver.resolve_url(url)
                        url = resolved.get("resolved_url") or url
                        if not filename and resolved.get("filename"):
                            filename = resolved["filename"]
                        if resolved.get("headers"):
                            merged = dict(headers)
                            merged.update(resolved["headers"])
                            headers = merged
                    except Exception:
                        pass

                guessed_cat = detect_category(filename or url)
                has_media_intent = (format_id and any(x in format_id for x in ("video", "audio", "prompt"))) or MediaGrabber.is_likely_media_url(url)
                is_media = has_media_intent and (guessed_cat in ("Video", "Audio") or (guessed_cat == "General" and MediaGrabber.is_likely_media_url(url)))

                if format_id in ("direct_turbo", "image_direct"):
                    target_cat = "Image" if guessed_cat == "General" else guessed_cat
                    save_dir = self.manager.get_category_dir(target_cat)
                    default_threads = config_store.get("default_threads", 32)
                    task = self.manager.create_task(
                        url=url,
                        filename=filename or None,
                        save_dir=save_dir,
                        num_connections=default_threads,
                        category=target_cat,
                        headers=headers,
                        queue_name=queue_name,
                        auto_start=True
                    )
                    notification_manager.play_start_sound()
                    self._refresh_table()
                    self.selected_task_id = task.task_id
                    if config_store.get("show_floating_download_window", True):
                        dlg = FloatingDownloadDialog(self, task)
                        self.bring_to_front(dlg)
                elif is_media:
                    if format_id and format_id != "prompt":
                        # Direct instant media download with user-selected quality format!
                        save_dir = os.path.join(config_store.get("default_download_dir"), "Video" if "audio" not in format_id else "Audio")
                        os.makedirs(save_dir, exist_ok=True)
                        self._download_video_stream(url, format_id, save_dir, headers=headers, title_hint=filename)
                    else:
                        # Ask user which video format they want to download (only for media files)
                        dlg = VideoGrabberDialog(self, on_download_video=self._download_video_stream, default_url=url, headers=headers)
                        self.bring_to_front(dlg)
                elif config_store.get("ask_save_location_everytime", True):
                    # Always ask where to download the file (IDM style destination confirmation)
                    initial_size = data.get("file_size", 0) or data.get("size", 0)
                    dlg = AddDownloadDialog(
                        self,
                        on_submit=self._create_download,
                        default_url=url,
                        default_filename=filename,
                        default_category=guessed_cat,
                        initial_size=initial_size,
                        headers=headers
                    )
                    self.bring_to_front(dlg)
                else:
                    default_threads = config_store.get("default_threads", 32)
                    cat_custom_dirs = config_store.get("category_custom_dirs", {}) or {}
                    last_dir = config_store.get("last_download_dir", "")
                    if guessed_cat in cat_custom_dirs and os.path.isdir(cat_custom_dirs[guessed_cat]):
                        target_save_dir = cat_custom_dirs[guessed_cat]
                    elif config_store.get("remember_last_download_dir", True) and last_dir and os.path.isdir(last_dir):
                        target_save_dir = last_dir
                    else:
                        target_save_dir = self.manager.get_category_dir(guessed_cat)

                    task = self.manager.create_task(
                        url=url,
                        filename=filename or None,
                        save_dir=target_save_dir,
                        num_connections=default_threads,
                        category=guessed_cat,
                        headers=headers,
                        queue_name=queue_name,
                        auto_start=True
                    )
                    notification_manager.play_start_sound()
                    self._refresh_table()
                    self.selected_task_id = task.task_id
                    if config_store.get("show_floating_download_window", True):
                        dlg = FloatingDownloadDialog(self, task)
                        self.bring_to_front(dlg)
            except Exception as e:
                safe_print(f"[FalconDM Browser Handler Error]: {e}")

        self.dispatch_to_main(handle)

    def _on_toggle_clipboard_sniff(self):
        self.watcher.enabled = self.clipboard_sniff_enabled.get()

    def _on_basket_url_dropped(self, url: str):
        if not url:
            return
        if url.startswith("magnet:?") or url.endswith(".torrent"):
            TorrentDownloadDialog(self, on_start_torrent=self._download_torrent_stream, default_source=url)
        elif MediaGrabber.is_likely_media_url(url):
            VideoGrabberDialog(self, on_download_video=self._download_video_stream, default_url=url)
        else:
            AddDownloadDialog(self, on_submit=self._create_download, default_url=url)

    def _on_open_from_basket(self):
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
        except Exception:
            pass

    # ================== Creation & Downloads ==================

    def _create_download(self, url: str, save_dir: str, num_threads: int, category: str, custom_filename: Optional[str] = None, auto_start: bool = True, headers: Optional[dict] = None):
        # Check Debrid Unrestrictor (Real-Debrid / Multi-Host cloud unrestrict)
        try:
            if DebridResolver.is_debrid_enabled() and DebridResolver.is_supported_url(url):
                ok, unres_url, meta = DebridResolver.unrestrict_link(url)
                if ok:
                    url = unres_url
        except Exception:
            pass

        # Cloud Storage Direct Link Resolution (Google Drive, Dropbox, MediaFire, PixelDrain, GitHub)
        try:
            if HostResolver.is_resolvable(url):
                resolved = HostResolver.resolve_url(url)
                url = resolved.get("resolved_url") or url
                if not custom_filename and resolved.get("filename"):
                    custom_filename = resolved["filename"]
                if resolved.get("headers"):
                    merged_headers = dict(headers or {})
                    merged_headers.update(resolved["headers"])
                    headers = merged_headers
        except Exception:
            pass

        if MediaGrabber.is_likely_media_url(url):
            dlg = VideoGrabberDialog(self, on_download_video=self._download_video_stream, default_url=url, headers=headers)
            self.bring_to_front(dlg)
            return

        # Smart Duplicate Download Detection (IDM Style)
        existing = [t for t in self.manager.tasks.values() if t.url.strip().lower() == url.strip().lower()]
        if existing:
            t = existing[0]
            if t.status in (DownloadTask.STATUS_DOWNLOADING, DownloadTask.STATUS_QUEUED):
                messagebox.showinfo("Already Downloading", f"'{t.filename}' is already currently downloading.")
                self.selected_task_id = t.task_id
                self._refresh_table()
                return
            elif t.status == DownloadTask.STATUS_PAUSED:
                res = messagebox.askyesno("Paused Download Found", f"'{t.filename}' is currently paused.\n\nDo you want to resume the existing download?")
                if res:
                    self.manager.resume_task(t.task_id)
                    self.selected_task_id = t.task_id
                    self._refresh_table()
                    return
            elif t.status == DownloadTask.STATUS_COMPLETED:
                res = messagebox.askyesno("Already Downloaded", f"'{t.filename}' was already completed.\n\nDo you want to download a new copy?")
                if not res:
                    self.selected_task_id = t.task_id
                    self._refresh_table()
                    return

        task = self.manager.create_task(
            url=url,
            filename=custom_filename or None,
            save_dir=save_dir or config_store.get("default_download_dir"),
            num_connections=num_threads or config_store.get("default_threads", 32),
            category=category,
            headers=headers or {},
            auto_start=auto_start
        )
        if auto_start:
            notification_manager.play_start_sound()
            self._refresh_table()
            self.selected_task_id = task.task_id
            if config_store.get("show_floating_download_window", True):
                dlg = FloatingDownloadDialog(self, task)
                self.bring_to_front(dlg)
        else:
            task.status = DownloadTask.STATUS_QUEUED
            self.manager.save_state()
            self._refresh_table()
            self.selected_task_id = task.task_id

    def _download_video_stream(self, url: str, format_id: str, save_dir: str, headers: Optional[dict] = None, title_hint: Optional[str] = None, download_subtitles: bool = False):
        """Dispatches video download worker using MediaGrabber."""
        is_media_domain = MediaGrabber.is_likely_media_url(url)
        if format_id == "direct" and not is_media_domain:
            task = self.manager.create_task(
                url=url,
                filename=title_hint or None,
                save_dir=save_dir or config_store.get("default_download_dir"),
                num_connections=config_store.get("default_threads", 16),
                category="Video",
                headers=headers or {},
                auto_start=True
            )
            notification_manager.play_start_sound()
            self._refresh_table()
            self.selected_task_id = task.task_id
            return

        if format_id in ("direct", ""):
            format_id = "bestvideo+bestaudio/best"

        import uuid
        task_id = str(uuid.uuid4())
        outtmpl = os.path.join(save_dir, "%(title).80s.%(ext)s")
        
        display_name = title_hint or "Fetching video stream..."
        task = DownloadTask(
            task_id=task_id,
            url=url,
            save_path=os.path.join(save_dir, title_hint or "video_download"),
            category="Video" if not format_id.startswith("bestaudio") else "Audio",
            headers=headers or {}
        )
        task.filename = display_name
        task.status = DownloadTask.STATUS_DOWNLOADING
        self.manager.tasks[task_id] = task
        notification_manager.play_start_sound()
        self._refresh_table()
        self.selected_task_id = task_id

        def video_worker():
            captured_filename: Optional[str] = None

            def progress_cb(data):
                nonlocal captured_filename
                st = data.get('status')
                if st == 'downloading':
                    task.downloaded_bytes = data.get('downloaded_bytes', 0)
                    task.file_size = data.get('total_bytes', 0)
                    task.speed_bps = data.get('speed', 0.0)
                    task.eta_seconds = data.get('eta', 0)
                    raw_fn = data.get('filename', '')
                    if raw_fn:
                        ext_lower = os.path.splitext(raw_fn)[1].lower()
                        # Avoid intermediate subtitle or temp file extensions overwriting media title
                        if ext_lower not in ('.srt', '.vtt', '.sub', '.lrc', '.part', '.ytdl'):
                            captured_filename = str(raw_fn)
                            task.filename = os.path.basename(raw_fn)
                            task.save_path = raw_fn
                elif st == 'finished':
                    raw_fn = data.get('filename', '')
                    if raw_fn:
                        ext_lower = os.path.splitext(raw_fn)[1].lower()
                        if ext_lower not in ('.srt', '.vtt', '.sub', '.lrc', '.part', '.ytdl'):
                            captured_filename = str(raw_fn)
                            task.filename = os.path.basename(raw_fn)
                            task.save_path = raw_fn
                elif st == 'error':
                    task.status = DownloadTask.STATUS_ERROR
                    task.error_message = data.get('error', 'Download failed')

            success = MediaGrabber.download_media(
                url,
                format_id,
                outtmpl,
                progress_hook=progress_cb,
                headers=headers,
                download_subtitles=download_subtitles
            )
            if success:
                task.status = DownloadTask.STATUS_COMPLETED
                final_path = captured_filename or task.save_path
                if final_path is not None and os.path.exists(final_path):
                    task.filename = os.path.basename(final_path)
                    task.save_path = final_path
                    task.file_size = os.path.getsize(final_path)
                    task.downloaded_bytes = task.file_size
                notification_manager.play_complete_sound()
            else:
                task.status = DownloadTask.STATUS_ERROR
            self.manager.save_state()
            self.dispatch_to_main(self._refresh_table)

        threading.Thread(target=video_worker, daemon=True).start()
        if config_store.get("show_floating_download_window", True):
            dlg = FloatingDownloadDialog(self, task)
            self.bring_to_front(dlg)

    def _download_torrent_stream(self, source: str, save_dir: str):
        """Dispatches BitTorrent / Magnet download worker using TorrentEngine (aria2c)."""
        import uuid
        task_id = str(uuid.uuid4())
        name = "Torrent Download"
        if source.startswith("magnet:"):
            try:
                parsed = urllib.parse.parse_qs(urllib.parse.urlparse(source).query)
                dn = parsed.get("dn", ["Magnet Download"])
                name = dn[0]
            except Exception:
                name = "Magnet Download"
        else:
            name = os.path.basename(source)
            
        task = DownloadTask(
            task_id=task_id,
            url=source,
            save_path=os.path.join(save_dir, name),
            category="Document"
        )
        task.filename = name
        task.status = DownloadTask.STATUS_DOWNLOADING
        self.manager.tasks[task_id] = task
        self._refresh_table()
        self.selected_task_id = task_id

        def torrent_worker():
            def progress_cb(data):
                st = data.get('status')
                if st == 'downloading':
                    task.downloaded_bytes = data.get('downloaded_bytes', 0)
                    task.file_size = data.get('total_bytes', 0)
                    task.speed_bps = data.get('speed', 0.0)
                    task.eta_seconds = data.get('eta', 0)
                    fn = data.get('filename')
                    if fn:
                        task.filename = fn
                        task.save_path = os.path.join(save_dir, fn)
                        task.category = detect_category(fn)
                elif st == 'completed':
                    task.status = DownloadTask.STATUS_COMPLETED
                    task.speed_bps = 0.0
                    task.eta_seconds = 0
                    self.manager.save_state()
                elif st == 'error':
                    task.status = DownloadTask.STATUS_ERROR
                    task.error_message = data.get('error', 'Torrent download failed')

            success = TorrentEngine.download_torrent(source, save_dir, progress_hook=progress_cb)
            if success:
                task.status = DownloadTask.STATUS_COMPLETED
            else:
                task.status = DownloadTask.STATUS_ERROR
            self.manager.save_state()

        threading.Thread(target=torrent_worker, daemon=True).start()
        if config_store.get("show_floating_download_window", True):
            dlg = FloatingDownloadDialog(self, task)
            self.bring_to_front(dlg)


    # ================== Table & Actions ==================

    def _open_floating_window(self):
        if not self.selected_task_id:
            return
        task = self.manager.tasks.get(self.selected_task_id)
        if task:
            FloatingDownloadDialog(self, task)

    def _on_context_preview(self):
        if not self.selected_task_id:
            return
        task = self.manager.tasks.get(self.selected_task_id)
        if not task:
            return
        if not os.path.exists(task.save_path) or os.path.getsize(task.save_path) < 1024:
            messagebox.showinfo("Preview Not Available", "Download has not saved enough bytes yet to preview.")
            return

        ffplay_candidates = [
            "ffplay",
            shutil.which("ffplay") or "",
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin\ffplay.exe")
        ]
        ffplay_bin = None
        for cand in ffplay_candidates:
            if os.path.isfile(cand) or shutil.which(cand):
                ffplay_bin = cand
                break
        
        try:
            if ffplay_bin:
                subprocess.Popen([ffplay_bin, "-autoexit", "-window_title", f"FalconDM Preview - {task.filename}", task.save_path])
            else:
                os.startfile(task.save_path)
        except Exception as e:
            messagebox.showerror("Preview Failed", f"Could not launch media player: {e}")

    def _on_toggle_sequential(self):
        if not self.selected_task_id:
            return
        task = self.manager.tasks.get(self.selected_task_id)
        if not task:
            return
        curr = getattr(task, "sequential_mode", False)
        task.sequential_mode = not curr
        self.manager.save_state()
        state_str = "ENABLED (Stream while downloading)" if task.sequential_mode else "DISABLED (Standard turbo multi-connection)"
        messagebox.showinfo("Sequential Mode", f"Sequential streaming mode is now {state_str} for '{task.filename}'.")

    def _on_context_extract(self):
        if not self.selected_task_id:
            return
        task = self.manager.tasks.get(self.selected_task_id)
        if not task or not os.path.exists(task.save_path):
            messagebox.showinfo("File Missing", "File does not exist yet.")
            return
        
        path = task.save_path
        lower = path.lower()
        if not (lower.endswith(".zip") or lower.endswith(".tar") or lower.endswith(".tar.gz") or lower.endswith(".tgz")):
            messagebox.showinfo("Not an Archive", "FalconDM auto-extract currently supports .zip and .tar.gz archives.")
            return

        dest_folder = os.path.splitext(path)[0]
        os.makedirs(dest_folder, exist_ok=True)
        try:
            if lower.endswith(".zip"):
                with zipfile.ZipFile(path, 'r') as z:
                    z.extractall(dest_folder)
            elif lower.endswith(".tar") or lower.endswith(".tar.gz") or lower.endswith(".tgz"):
                with tarfile.open(path, 'r:*') as t:
                    t.extractall(dest_folder)
            
            open_file_or_folder(dest_folder)
            messagebox.showinfo("Extracted", f"Successfully extracted archive to:\n{dest_folder}")
        except Exception as e:
            messagebox.showerror("Extraction Error", f"Failed to extract archive: {e}")

    def _on_export_links(self):
        tasks = [t for t in self.manager.tasks.values() if t.url]
        if not tasks:
            messagebox.showinfo("No Downloads", "No download links to export.")
            return
        save_file = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[
                ("Plain Text URL List", "*.txt"),
                ("Metalink 4 XML Document", "*.meta4"),
                ("aria2 Input Format", "*.aria2"),
                ("Internet Download Manager Export", "*.ef2"),
                ("All Files", "*.*")
            ],
            initialfile="falcondm_downloads.txt"
        )
        if save_file:
            try:
                from core.import_export import DownloadListSerializer
                ext = os.path.splitext(save_file)[1].lower()
                task_dicts = [t.to_dict() for t in tasks]
                if ext in ('.meta4', '.metalink'):
                    ok = DownloadListSerializer.export_metalink(task_dicts, save_file)
                elif ext == '.ef2':
                    ok = DownloadListSerializer.export_idm_ef2(task_dicts, save_file)
                elif ext == '.aria2':
                    ok = DownloadListSerializer.export_aria2_input(task_dicts, save_file)
                else:
                    with open(save_file, "w", encoding="utf-8") as f:
                        for t in tasks:
                            f.write(f"{t.url}\n")
                    ok = True

                if ok:
                    messagebox.showinfo("Export Successful", f"Successfully exported {len(tasks)} tasks to:\n{save_file}")
                else:
                    messagebox.showerror("Export Failed", "Could not write export file.")
            except Exception as e:
                messagebox.showerror("Export Failed", str(e))

    def _on_import_metalink(self):
        filepath = filedialog.askopenfilename(
            title="Import Metalink File",
            filetypes=[
                ("Metalink Documents", "*.metalink;*.meta4;*.xml"),
                ("All Files", "*.*")
            ]
        )
        if not filepath:
            return
        try:
            from core.import_export import DownloadListSerializer
            items = DownloadListSerializer.import_metalink(filepath)
            if not items:
                messagebox.showwarning("Metalink Import", "No downloadable files found in this Metalink file.")
                return
            count = 0
            for item in items:
                url = item.get("url")
                fn = item.get("filename")
                mirrors = item.get("mirrors", [])
                h_val = item.get("checksum_expected", "")
                h_type = item.get("checksum_type", "")
                task = self.manager.create_task(url, filename=fn)
                for m in mirrors:
                    self.manager.add_task_mirror(task.task_id, m)
                if h_val:
                    task.checksum_expected = h_val
                    task.checksum_type = h_type
                count += 1
            self._refresh_table()
            messagebox.showinfo("Metalink Imported", f"Successfully imported {count} download task(s) with multi-mirror acceleration!")
        except Exception as e:
            messagebox.showerror("Metalink Error", f"Failed to parse Metalink file:\n{e}")

    def _on_build_extension_packages(self):
        """Generates validated .zip packages for Chrome Web Store, Edge Add-ons, and Firefox AMO."""
        try:
            from build_extension_packages import build_extension_packages
            build_extension_packages()
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            out_dir = os.path.join(base_dir, "dist_extension")
            messagebox.showinfo(
                "Store Packages Ready",
                f"Browser Extension store packages created successfully in:\n{out_dir}\n\n"
                f"• FalconDM-Chrome-WebStore.zip (Chrome, Edge, Brave, Opera)\n"
                f"• FalconDM-Firefox-AMO.zip (Firefox AMO)\n"
                f"• SUBMISSION_GUIDE.md (Step-by-step submission checklist)"
            )
            open_file_or_folder(out_dir)
        except Exception as err:
            messagebox.showerror("Packaging Error", f"Failed to generate extension packages:\n{err}")

    def _on_copy_curl_command(self):
        if not self.selected_task_id:
            return
        task = self.manager.tasks.get(self.selected_task_id)
        if not task:
            return
        from core.import_export import DownloadListSerializer
        cmd = DownloadListSerializer.generate_curl_command(task)
        self.clipboard_clear()
        self.clipboard_append(cmd)
        if hasattr(self, 'lbl_status_center'):
            self.lbl_status_center.configure(text=f"📋 cURL command copied: {task.filename}")
        if hasattr(self, 'tray'):
            self.tray.notify("cURL Copied", f"cURL command for {task.filename} copied to clipboard!")

    def _on_context_scan_av(self):
        if not self.selected_task_id:
            return
        task = self.manager.tasks.get(self.selected_task_id)
        if not task or not os.path.exists(task.save_path):
            messagebox.showinfo("File Missing", "File does not exist on disk yet.")
            return
        res = AntivirusScanner.scan_file(task.save_path)
        if res.get("clean"):
            messagebox.showinfo("Security Scan Clean", f"✅ File is 100% Clean!\n\nEngine: {res.get('engine')}\nResult: {res.get('message')}")
        else:
            messagebox.showwarning("Security Alert", f"⚠️ Threat Detected or Scan Issue!\n\nEngine: {res.get('engine')}\nResult: {res.get('message')}")

    def _on_click_web_remote(self):
        import webbrowser
        webbrowser.open("http://127.0.0.1:9666/remote")

    def _enqueue_batch_urls(self, urls: List[str], save_dir: str):
        if not urls:
            return
        threads = config_store.get("default_threads", 16)
        dest = save_dir or config_store.get("default_download_dir")
        for u in urls:
            try:
                self.manager.create_task(
                    url=u,
                    save_dir=dest,
                    num_connections=threads,
                    auto_start=True
                )
            except Exception:
                pass
        notification_manager.play_start_sound()
        self._refresh_table()
        messagebox.showinfo("Enqueued", f"Successfully enqueued {len(urls)} downloads to FalconDM!")

    def _on_context_convert(self):
        if not self.selected_task_id:
            return
        task = self.manager.tasks.get(self.selected_task_id)
        if task and os.path.exists(task.save_path):
            MediaConverterDialog(self, initial_file=task.save_path)
        else:
            messagebox.showinfo("File Not Ready", "Please wait until the download finishes or choose a completed file to convert.")

    def _on_context_checksum(self):
        if not self.selected_task_id:
            return
        task = self.manager.tasks.get(self.selected_task_id)
        if task and os.path.exists(task.save_path):
            ChecksumDialog(self, initial_file=task.save_path)
        else:
            messagebox.showinfo("File Incomplete", "Please wait until the download finishes to verify checksums.")

    def _on_copy_link(self):
        if not self.selected_task_id:
            return
        task = self.manager.tasks.get(self.selected_task_id)
        if task:
            self.clipboard_clear()
            self.clipboard_append(task.url)
            messagebox.showinfo("Copied", "Download URL copied to clipboard.")

    def _on_select_category(self, cat_key: str):
        self.active_category = cat_key
        for k, btn in self.cat_buttons.items():
            if k == cat_key:
                btn.configure(fg_color="#172554", border_width=1, border_color="#3b82f6", text_color="#ffffff", font=ctk.CTkFont(size=11, weight="bold"))
            else:
                btn.configure(fg_color="transparent", border_width=0, border_color="#0b0f19", text_color="#94a3b8", font=ctk.CTkFont(size=11, weight="normal"))
        self._refresh_table()

    def _on_tree_select(self, event):
        selected = self.tree.selection()
        if selected:
            self.selected_task_id = selected[0]
            self._update_segment_monitor()

    def _on_context_open_file(self):
        if not self.selected_task_id:
            return
        task = self.manager.tasks.get(self.selected_task_id)
        if task and os.path.exists(task.save_path):
            try:
                os.startfile(task.save_path)
            except Exception as e:
                messagebox.showerror("Error", f"Could not launch file: {e}")
        else:
            messagebox.showinfo("File Not Ready", "This download has not completed yet or the file was moved.")

    def _open_file_properties(self):
        if not self.selected_task_id:
            return
        task = self.manager.tasks.get(self.selected_task_id)
        if not task:
            return
        def on_url_updated(task_id, new_url):
            self._refresh_table()
        FilePropertiesDialog(self, task, on_url_updated=on_url_updated)

    def _open_log_viewer(self, task=None):
        DownloadLogViewerDialog(self, task=task)

    def _on_context_view_log(self):
        task = self.manager.tasks.get(self.selected_task_id) if self.selected_task_id else None
        self._open_log_viewer(task=task)

    def _on_copy_file_path(self):
        if not self.selected_task_id:
            return
        task = self.manager.tasks.get(self.selected_task_id)
        if task:
            self.clipboard_clear()
            self.clipboard_append(os.path.abspath(task.save_path))
            messagebox.showinfo("Copied", "File path copied to clipboard.")

    def _on_redownload(self):
        if not self.selected_task_id:
            return
        task = self.manager.tasks.get(self.selected_task_id)
        if not task:
            return
        if messagebox.askyesno("Redownload", f"Do you want to re-download '{task.filename}' from 0%?"):
            task.pause()
            if os.path.exists(task.save_path):
                try:
                    os.remove(task.save_path)
                except Exception:
                    pass
            task.init_segments()
            task.downloaded_bytes = 0
            task.status = DownloadTask.STATUS_DOWNLOADING
            task.start()
            self._refresh_table()

    def _on_tree_double_click(self, event):
        # Double clicking completed file opens Built-in Quick Look Preview
        # If unfinished, opens floating download progress monitor
        if not self.selected_task_id:
            return
        task = self.manager.tasks.get(self.selected_task_id)
        if task and task.status == DownloadTask.STATUS_COMPLETED and os.path.exists(task.save_path):
            self._on_quick_look()
            return
        self._open_floating_window()

    def _on_quick_look(self):
        if not self.selected_task_id:
            messagebox.showinfo("Quick Look", "Please select a download from the list to preview.")
            return
        task = self.manager.tasks.get(self.selected_task_id)
        if task:
            QuickLookDialog(self, task=task)

    def _on_tree_right_click(self, event):
        row_id = self.tree.identify_row(event.y)
        if row_id:
            self.tree.selection_set(row_id)
            self.selected_task_id = row_id
            self.context_menu.post(event.x_root, event.y_root)

    def _on_click_column_header(self, col: str):
        if self.sort_column == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = col
            self.sort_reverse = False
        self._refresh_table()

    def _focus_search(self):
        if hasattr(self, 'search_entry'):
            self.search_entry.focus_set()
            self.search_entry.select_range(0, tk.END)

    def _toggle_selected_pause_resume(self):
        if not self.selected_task_id:
            return
        t = self.manager.tasks.get(self.selected_task_id)
        if not t:
            return
        if t.status == DownloadTask.STATUS_DOWNLOADING:
            self.manager.pause_task(self.selected_task_id)
        else:
            self.manager.resume_task(self.selected_task_id)
        self._refresh_table()

    def _on_click_resume(self):
        if self.selected_task_id:
            self.manager.resume_task(self.selected_task_id)
            self._refresh_table()

    def _on_click_pause(self):
        if self.selected_task_id:
            self.manager.pause_task(self.selected_task_id)
            self._refresh_table()

    def _on_click_delete(self):
        if not self.selected_task_id:
            return
        task = self.manager.tasks.get(self.selected_task_id)
        if not task:
            return
        
        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to remove '{task.filename}' from the download list?\n(Target file will remain intact)"
        )
        if confirm:
            tid = self.selected_task_id
            self.manager.remove_task(tid, delete_file=False)
            self._tree_row_cache.pop(tid, None)
            self.selected_task_id = None
            self._refresh_table()
            self._clear_segment_monitor()
            from core.platform_utils import trim_memory_footprint
            self.after(200, trim_memory_footprint)

    def _on_click_open_folder(self):
        if not self.selected_task_id:
            return
        task = self.manager.tasks.get(self.selected_task_id)
        if not task:
            return
        
        path = task.save_path
        folder = os.path.dirname(path)
        if os.path.exists(path):
            open_file_or_folder(path, select=True)
        elif os.path.exists(folder):
            open_file_or_folder(folder)
        else:
            messagebox.showinfo("Folder Not Found", f"Directory does not exist yet:\n{folder}")

    def _on_change_speed_limit(self, choice: str):
        limit_map = {
            "Unlimited": 0,
            "1 MB/s": 1024 * 1024,
            "5 MB/s": 5 * 1024 * 1024,
            "10 MB/s": 10 * 1024 * 1024,
            "25 MB/s": 25 * 1024 * 1024,
        }
        limit = limit_map.get(choice, 0)
        for task in self.manager.tasks.values():
            task.speed_limit_bps = limit

    # ================== Visual Updates ==================

    def _refresh_table(self):
        tasks = list(self.manager.tasks.values())
        
        # 1. Update Category Counts on Sidebar Badges
        total_count = len(tasks)
        unfin_count = len([t for t in tasks if t.status != DownloadTask.STATUS_COMPLETED])
        fin_count = len([t for t in tasks if t.status == DownloadTask.STATUS_COMPLETED])
        paused_count = len([t for t in tasks if t.status in (DownloadTask.STATUS_PAUSED, DownloadTask.STATUS_ERROR)])

        counts_map = {
            "All Downloads": total_count,
            "Unfinished": unfin_count,
            "Finished": fin_count,
            "Paused": paused_count,
            "Video": len([t for t in tasks if t.category.lower() == "video"]),
            "Audio": len([t for t in tasks if t.category.lower() == "audio"]),
            "Image": len([t for t in tasks if t.category.lower() == "image"]),
            "Compressed": len([t for t in tasks if t.category.lower() == "compressed"]),
            "Document": len([t for t in tasks if t.category.lower() == "document"]),
            "Program": len([t for t in tasks if t.category.lower() == "program"]),
        }

        category_colors = {
            "All Downloads": ("#1e3a8a", "#93c5fd"),
            "Unfinished": ("#065f46", "#6ee7b7"),
            "Finished": ("#14532d", "#86efac"),
            "Paused": ("#78350f", "#fcd34d"),
            "Video": ("#312e81", "#a5b4fc"),
            "Audio": ("#4c1d95", "#d8b4fe"),
            "Image": ("#064e3b", "#6ee7b7"),
            "Compressed": ("#164e63", "#67e8f9"),
            "Document": ("#713f12", "#fde047"),
            "Program": ("#1e3a8a", "#93c5fd"),
        }

        for k, lbl in self.cat_count_labels.items():
            cnt = counts_map.get(k, 0)
            is_active = (k == self.active_category)
            cache_key = (cnt, is_active)
            if self._cat_count_cache.get(k) == cache_key:
                continue
            self._cat_count_cache[k] = cache_key

            lbl.configure(text=str(cnt))
            if is_active:
                lbl.configure(fg_color="#3b82f6", text_color="#ffffff")
            elif cnt > 0:
                bg_col, txt_col = category_colors.get(k, ("#1e293b", "#cbd5e1"))
                lbl.configure(fg_color=bg_col, text_color=txt_col)
            else:
                lbl.configure(fg_color="#111827", text_color="#475569")

        # 2. Filter by Category
        if self.active_category == "Unfinished":
            filtered = [t for t in tasks if t.status != DownloadTask.STATUS_COMPLETED]
        elif self.active_category == "Finished":
            filtered = [t for t in tasks if t.status == DownloadTask.STATUS_COMPLETED]
        elif self.active_category == "Paused":
            filtered = [t for t in tasks if t.status in (DownloadTask.STATUS_PAUSED, DownloadTask.STATUS_ERROR)]
        elif self.active_category != "All Downloads":
            filtered = [t for t in tasks if t.category.lower() == self.active_category.lower()]
        else:
            filtered = tasks

        # 3. Filter by Search Query
        q = self.search_var.get().strip().lower() if hasattr(self, 'search_var') else ""
        if q:
            filtered = [t for t in filtered if q in t.filename.lower() or q in t.url.lower() or q in t.category.lower()]

        # 4. Sort Filtered Tasks by User's Selected Column
        col_titles = {
            "name": "File Name",
            "size": "Size",
            "status": "Status",
            "progress": "Progress",
            "speed": "Speed",
            "eta": "Time Left",
            "category": "Category"
        }
        for c_id, base_title in col_titles.items():
            if self.sort_column == c_id:
                indicator = " ▲" if not self.sort_reverse else " ▼"
                self.tree.heading(c_id, text=base_title + indicator)
            else:
                self.tree.heading(c_id, text=base_title)

        if self.sort_column == "name":
            filtered.sort(key=lambda t: t.filename.lower(), reverse=self.sort_reverse)
        elif self.sort_column == "size":
            filtered.sort(key=lambda t: t.file_size, reverse=self.sort_reverse)
        elif self.sort_column == "status":
            filtered.sort(key=lambda t: t.status, reverse=self.sort_reverse)
        elif self.sort_column == "progress":
            filtered.sort(key=lambda t: t.progress_pct, reverse=self.sort_reverse)
        elif self.sort_column == "speed":
            filtered.sort(key=lambda t: t.speed_bps, reverse=self.sort_reverse)
        elif self.sort_column == "eta":
            filtered.sort(key=lambda t: (t.eta_seconds if t.eta_seconds > 0 else 99999999), reverse=self.sort_reverse)
        elif self.sort_column == "category":
            filtered.sort(key=lambda t: t.category, reverse=self.sort_reverse)

        # 5. Handle Empty State
        if not filtered:
            if hasattr(self, 'empty_state') and not self.empty_state.winfo_ismapped():
                self.empty_state.place(relx=0.5, rely=0.45, anchor="center")
        else:
            if hasattr(self, 'empty_state') and self.empty_state.winfo_ismapped():
                self.empty_state.place_forget()

        # 6. Populate Treeview with Alternating Zebra Rows (Differential Caching)
        existing_items = set(self.tree.get_children())
        visible_ids = set()

        for idx, task in enumerate(filtered):
            visible_ids.add(task.task_id)
            row_tag = "even_row" if idx % 2 == 0 else "odd_row"
            icon = get_file_icon(task.filename, task.category)
            prio = getattr(task, "priority", 1)
            prio_badge = "⚡ " if prio == 2 else ("↓ " if prio == 0 else "")
            mirror_badge = " [🔗]" if getattr(task, "mirrors", []) else ""
            display_name = f" {prio_badge}{icon}  {task.filename}{mirror_badge}"
            size_str = format_bytes(task.file_size) if task.file_size > 0 else "Unknown"
            
            # High-tech unicode progress representation
            if task.status == DownloadTask.STATUS_DOWNLOADING:
                pct = int(task.progress_pct)
                blocks = max(0, min(10, pct // 10))
                bar_viz = "▰" * blocks + "▱" * (10 - blocks)
                prog_str = f"{bar_viz} {task.progress_pct:.0f}%"
            elif task.status == DownloadTask.STATUS_COMPLETED:
                prog_str = "▰▰▰▰▰▰▰▰▰▰ 100%"
            else:
                prog_str = f"{task.progress_pct:.1f}%"

            speed_str = format_speed(task.speed_bps) if task.status == DownloadTask.STATUS_DOWNLOADING else "--"
            eta_str = format_time(task.eta_seconds) if task.status == DownloadTask.STATUS_DOWNLOADING else "--"
            status_badge = format_status_badge(task.status)

            values = (
                display_name,
                size_str,
                status_badge,
                prog_str,
                speed_str,
                eta_str,
                task.category
            )

            row_signature = (values, row_tag)
            if task.task_id in existing_items:
                if self._tree_row_cache.get(task.task_id) != row_signature:
                    self.tree.item(task.task_id, values=values, tags=(row_tag,))
                    self._tree_row_cache[task.task_id] = row_signature
            else:
                self.tree.insert("", "end", iid=task.task_id, values=values, tags=(row_tag,))
                self._tree_row_cache[task.task_id] = row_signature

        for item_id in existing_items - visible_ids:
            self.tree.delete(item_id)
            self._tree_row_cache.pop(item_id, None)

    def _update_segment_monitor(self):
        if not self.selected_task_id:
            self._clear_segment_monitor()
            return

        task = self.manager.tasks.get(self.selected_task_id)
        if not task:
            self._clear_segment_monitor()
            return

        self.lbl_segment_title.configure(
            text=f"⚡ Thread Chunk Monitor: {task.filename} ({len(task.segments)} Threads Active | {format_speed(task.speed_bps)})"
        )

        if self.segment_panel_collapsed or not self.seg_scroll:
            return

        needed = len(task.segments)
        while len(self.seg_widgets) < needed:
            idx = len(self.seg_widgets)
            card = ctk.CTkFrame(self.seg_scroll, fg_color="#101726", width=140, height=68, corner_radius=8, border_width=1, border_color="#1e293b")
            card.pack(side="left", padx=5, pady=2)
            card.pack_propagate(False)

            lbl = ctk.CTkLabel(card, text=f"⚡ Stream #{idx + 1}", font=ctk.CTkFont(size=10, weight="bold"), text_color="#cbd5e1")
            lbl.pack(anchor="w", padx=8, pady=(4, 0))

            bar = ctk.CTkProgressBar(card, height=8, corner_radius=4, progress_color="#2563eb", fg_color="#1e293b")
            bar.pack(fill="x", padx=8, pady=(4, 2))

            pct_lbl = ctk.CTkLabel(card, text="0.0%", font=ctk.CTkFont(size=9, weight="bold"), text_color="#38bdf8")
            pct_lbl.pack(anchor="e", padx=8, pady=(0, 4))

            self.seg_widgets.append((card, bar, pct_lbl))

        for i, segment in enumerate(task.segments):
            card, bar, pct_lbl = self.seg_widgets[i]
            progress = segment.progress_pct / 100.0
            bar.set(progress)
            
            if segment.status == "completed":
                bar.configure(progress_color="#10b981")
                pct_lbl.configure(text="100% (Done)", text_color="#34d399")
            elif segment.status == "downloading":
                bar.configure(progress_color="#38bdf8")
                pct_lbl.configure(text=f"{segment.progress_pct:.1f}%", text_color="#38bdf8")
            elif segment.status == "error":
                bar.configure(progress_color="#ef4444")
                pct_lbl.configure(text="Error", text_color="#f87171")
            else:
                bar.configure(progress_color="#64748b")
                pct_lbl.configure(text=f"{segment.progress_pct:.1f}%", text_color="#94a3b8")

        self._draw_main_segment_map(task)

    def _draw_main_segment_map(self, task):
        c = getattr(self, "main_segment_map_canvas", None)
        if not c or not c.winfo_exists() or self.bottom_panel_mode != "segments" or self.segment_panel_collapsed:
            return
        c.delete("all")
        w = c.winfo_width() if c.winfo_width() > 50 else 760
        h = c.winfo_height() if c.winfo_height() > 8 else 20

        segments = getattr(task, "segments", [])
        total_size = getattr(task, "file_size", 0)

        c.create_rectangle(1, 1, w - 1, h - 1, fill="#070b12", outline="#1e293b", width=1)
        if not segments or total_size <= 0:
            prog = getattr(task, "progress_pct", 0.0) / 100.0
            fill_w = max(2, int((w - 4) * prog))
            c.create_rectangle(2, 2, 2 + fill_w, h - 2, fill="#0284c7", outline="")
            return

        pad_x = 2
        pad_y = 2
        draw_w = max(10, w - (pad_x * 2))
        draw_h = max(4, h - (pad_y * 2))

        for seg in segments:
            x0 = pad_x + (seg.start / total_size) * draw_w
            x1 = pad_x + ((seg.end + 1) / total_size) * draw_w
            xc = pad_x + (seg.current / total_size) * draw_w

            c.create_rectangle(x0, pad_y, x1, pad_y + draw_h, fill="#0d1522", outline="")
            if xc > x0:
                is_done = seg.status == "completed" or seg.current > seg.end
                fill_color = "#10b981" if is_done else "#0284c7"
                c.create_rectangle(x0, pad_y, min(x1, xc), pad_y + draw_h, fill=fill_color, outline="")

            if seg.status == "downloading" and xc < x1:
                head_x = min(x1 - 1, xc)
                c.create_line(head_x, pad_y, head_x, pad_y + draw_h, fill="#38bdf8", width=2)
                c.create_line(head_x - 1, pad_y, head_x - 1, pad_y + draw_h, fill="#ffffff", width=1)

            c.create_line(x1, pad_y, x1, pad_y + draw_h, fill="#1e293b", width=1)

    def _clear_segment_monitor(self):
        self.lbl_segment_title.configure(text="⚡ Connection Chunk Visualizer (Select a download above to view active threads)")
        if hasattr(self, 'main_segment_map_canvas') and self.main_segment_map_canvas.winfo_exists():
            self.main_segment_map_canvas.delete("all")
        for card, _, _ in self.seg_widgets:
            card.destroy()
        self.seg_widgets.clear()

    def _draw_speed_graph(self):
        c_mini = getattr(self, 'speed_canvas', None)
        c_main = getattr(self, 'main_speed_canvas', None)
        history = getattr(self, 'speed_history', [])
        if not history:
            return

        max_spd = max(history)
        # Eco-mode: Skip canvas redraw if speed is 0 and history is flat
        if max_spd <= 1.0 and all(v <= 0 for v in history[-5:]):
            if getattr(self, '_speed_graph_idle_cleared', False):
                return
            self._speed_graph_idle_cleared = True
        else:
            self._speed_graph_idle_cleared = False

        n = len(history)

        # 1. Mini Sidebar Speed Waveform
        if c_mini and c_mini.winfo_exists():
            c_mini.delete("all")
            w = c_mini.winfo_width() if c_mini.winfo_width() > 10 else 188
            h = c_mini.winfo_height() if c_mini.winfo_height() > 10 else 48
            points = []
            for i, val in enumerate(history):
                x = (i / max(1, n - 1)) * (w - 8) + 4
                ratio = min(1.0, val / max_spd) if max_spd > 0 else 0
                y = (h - 4) - (ratio * (h - 12))
                points.append((x, y))

            # Precision cyber grid lines
            c_mini.create_line(2, h // 2, w - 2, h // 2, fill="#121b28", dash=(2, 3))
            c_mini.create_line(2, h // 4, w - 2, h // 4, fill="#0d141e", dash=(1, 4))
            c_mini.create_line(2, 3 * h // 4, w - 2, 3 * h // 4, fill="#0d141e", dash=(1, 4))

            # Filled multi-layer area & stroke
            if len(points) >= 2:
                poly_points = [4, h - 2]
                for pt in points:
                    poly_points.extend(pt)
                poly_points.extend([w - 4, h - 2])
                c_mini.create_polygon(poly_points, fill="#0b1b33", outline="")

                flat_pts = [coord for pt in points for coord in pt]
                c_mini.create_line(flat_pts, fill="#1e40af", width=3, smooth=True)
                c_mini.create_line(flat_pts, fill="#38bdf8", width=1.5, smooth=True)

                lx, ly = points[-1]
                c_mini.create_oval(lx - 5, ly - 5, lx + 5, ly + 5, fill="#0e3a6a", outline="#38bdf8", width=1)
                c_mini.create_oval(lx - 2.5, ly - 2.5, lx + 2.5, ly + 2.5, fill="#ffffff", outline="#38bdf8", width=1.5)

        # 2. Main Full-Width Live Speed Curve (in Bottom Performance Panel)
        if c_main and c_main.winfo_exists() and not getattr(self, 'segment_panel_collapsed', True) and getattr(self, 'bottom_panel_mode', 'graph') == 'graph':
            c_main.delete("all")
            w = c_main.winfo_width() if c_main.winfo_width() > 50 else 760
            h = c_main.winfo_height() if c_main.winfo_height() > 30 else 100

            pad_left = 65
            pad_right = 20
            pad_top = 14
            pad_bot = 20
            plot_w = max(20, w - pad_left - pad_right)
            plot_h = max(20, h - pad_top - pad_bot)

            # Draw speed grid scale lines
            steps = 3
            for s in range(steps + 1):
                gy = pad_top + plot_h - (s / steps) * plot_h
                c_main.create_line(pad_left, gy, w - pad_right, gy, fill="#141d2c", dash=(2, 4))
                spd_at_line = (s / steps) * max_spd
                c_main.create_text(pad_left - 8, gy, text=format_speed(spd_at_line), fill="#64748b", font=("Segoe UI", 8), anchor="e")

            # Draw time grid lines (-60s, -45s, -30s, -15s, Now)
            time_labels = [("-60s", 0.0), ("-45s", 0.25), ("-30s", 0.50), ("-15s", 0.75), ("Now", 1.0)]
            for lbl, pct in time_labels:
                gx = pad_left + pct * plot_w
                c_main.create_line(gx, pad_top, gx, pad_top + plot_h, fill="#101824", dash=(1, 5))
                c_main.create_text(gx, pad_top + plot_h + 10, text=lbl, fill="#64748b", font=("Segoe UI", 8), anchor="center")

            # Plot curve points
            points = []
            for i, val in enumerate(history):
                x = pad_left + (i / max(1, n - 1)) * plot_w
                ratio = min(1.0, val / max_spd) if max_spd > 0 else 0
                y = (pad_top + plot_h) - (ratio * plot_h)
                points.append((x, y))

            if len(points) >= 2:
                palette = self.get_theme_palette()
                # Gradient fill under curve
                poly = [pad_left, pad_top + plot_h]
                for pt in points:
                    poly.extend(pt)
                poly.extend([pad_left + plot_w, pad_top + plot_h])
                c_main.create_polygon(poly, fill=palette.get("graph_fill", "#0c1d38"), outline="")

                # Neon cyber strokes
                flat_pts = [coord for pt in points for coord in pt]
                c_main.create_line(flat_pts, fill=palette.get("primary", "#1d4ed8"), width=4, smooth=True)
                c_main.create_line(flat_pts, fill=palette.get("graph_line", "#38bdf8"), width=2, smooth=True)

                # Peak speed dashed line
                peak_y = (pad_top + plot_h) - (plot_h)
                c_main.create_line(pad_left, peak_y, w - pad_right, peak_y, fill="#22c55e", dash=(3, 3), width=1)
                c_main.create_text(w - pad_right - 6, peak_y - 6, text=f"Peak: {format_speed(max_spd)}", fill="#4ade80", font=("Segoe UI", 8, "bold"), anchor="e")

                # Glowing leading pulse point
                last_x, last_y = points[-1]
                c_main.create_oval(last_x - 6, last_y - 6, last_x + 6, last_y + 6, fill="#0e3a6a", outline="#38bdf8", width=1.5)
                c_main.create_oval(last_x - 3, last_y - 3, last_x + 3, last_y + 3, fill="#ffffff", outline="#38bdf8", width=1.5)

            # Live Stats Badge on Top Right
            curr_spd = history[-1] if history else 0.0
            recent_avg = sum(history[-15:]) / max(1, len(history[-15:]))
            badge_text = f"THROUGHPUT: {format_speed(curr_spd)}  |  PEAK: {format_speed(self.peak_speed_seen)}  |  AVG: {format_speed(recent_avg)}"
            c_main.create_text(w - pad_right - 10, pad_top + 2, text=badge_text, fill="#38bdf8", font=("Segoe UI", 9, "bold"), anchor="e")

    def _setup_auto_refresh(self):
        def ticker():
            now_tick = time.time()
            # Throttle clipboard sniffing to once every 1.5 seconds instead of every 250ms
            if hasattr(self, 'watcher') and (now_tick - getattr(self, '_last_clipboard_check', 0.0) >= 1.5):
                self._last_clipboard_check = now_tick
                self.watcher.check_once()

            self._refresh_table()
            if self.selected_task_id:
                self._update_segment_monitor()

            active_tasks = [t for t in self.manager.tasks.values() if t.status == DownloadTask.STATUS_DOWNLOADING]
            total_speed = sum(t.speed_bps for t in active_tasks)
            total_threads = sum(len(t.segments) for t in active_tasks)

            spd_text = format_speed(total_speed)
            if spd_text != getattr(self, '_last_spd_text', ''):
                self._last_spd_text = spd_text
                self.lbl_global_speed.configure(text=spd_text)
                if hasattr(self, 'header_speed_lbl'):
                    if total_speed > 0:
                        self.header_speed_lbl.configure(text=f"⚡ {spd_text}", fg_color="#064e3b", text_color="#34d399")
                    else:
                        self.header_speed_lbl.configure(text="⚡ 0.0 KB/s", fg_color="#0c1b30", text_color="#38bdf8")

            if total_threads != getattr(self, '_last_total_threads', -1):
                self._last_total_threads = total_threads
                self.lbl_active_streams.configure(text=f"⚡ {total_threads} Streams Connected")

            completed_count = sum(1 for t in self.manager.tasks.values() if t.status == DownloadTask.STATUS_COMPLETED)
            active_count = len(active_tasks)
            total_count = len(self.manager.tasks)

            counts_tuple = (active_count, completed_count, total_count)
            if counts_tuple != getattr(self, '_last_counts_tuple', None):
                self._last_counts_tuple = counts_tuple
                if hasattr(self, 'lbl_status_center'):
                    self.lbl_status_center.configure(text=f"Tasks: {active_count} Active, {completed_count} Completed | Total: {total_count}")

            # Automatic memory trim when all tasks transition to idle
            if active_count == 0 and completed_count > 0:
                if not getattr(self, '_idle_trimmed', False):
                    self._idle_trimmed = True
                    from core.platform_utils import trim_memory_footprint
                    self.after(2000, trim_memory_footprint)
            elif active_count > 0:
                self._idle_trimmed = False

            # Notification & Audio cue for newly completed tasks
            completed_now = {tid for tid, t in self.manager.tasks.items() if t.status == DownloadTask.STATUS_COMPLETED}
            if hasattr(self, '_completed_tasks_seen'):
                newly_completed = completed_now - self._completed_tasks_seen
                if newly_completed:
                    self._completed_tasks_seen.update(newly_completed)
                    notification_manager.play_complete_sound()
                    for tid in newly_completed:
                        t = self.manager.tasks.get(tid)
                        if t:
                            if hasattr(self, 'tray'):
                                self.tray.notify("Download Finished!", f"{t.filename} ({format_bytes(t.file_size)}) is ready.")
                            try:
                                CyberToastNotification(
                                    self,
                                    title="Download Complete",
                                    filename=t.filename,
                                    file_path=t.save_path,
                                    file_size_str=format_bytes(t.file_size),
                                    is_error=False
                                )
                            except Exception:
                                pass

                            # Telegram Remote Alert & Cloud Auto-Upload
                            try:
                                telegram_bot.notify_download_complete(t)
                                cloud_uploader.handle_task_completion(t)
                            except Exception:
                                pass

                    if active_count == 0 and config_store.get("shutdown_on_completion", False):
                        if not getattr(self, '_shutdown_dialog_active', False):
                            self._shutdown_dialog_active = True
                            dlg = ShutdownWarningDialog(self, countdown_sec=30)
                            self.bring_to_front(dlg)

            # When minimized to system tray, skip canvas redraws & relax ticker to save CPU/battery
            if getattr(self, "state", lambda: "normal")() == "withdrawn":
                now_t = time.time()
                if now_t - getattr(self, "_last_tray_mem_trim", 0.0) > 40.0:
                    self._last_tray_mem_trim = now_t
                    from core.platform_utils import trim_memory_footprint
                    trim_memory_footprint()
                has_active_traffic = bool(active_tasks) or (total_speed > 0)
                self.after(1200 if has_active_traffic else 2500, ticker)
                return

            if hasattr(self, 'speed_history'):
                self.speed_history.append(total_speed)
                if len(self.speed_history) > 60:
                    self.speed_history.pop(0)

                peak = max(getattr(self, 'peak_speed_seen', 0.0), total_speed)
                self.peak_speed_seen = peak
                if hasattr(self, 'lbl_peak_speed'):
                    self.lbl_peak_speed.configure(text=f"Peak: {format_speed(peak)}")

                if hasattr(self, 'lbl_segment_title') and getattr(self, 'bottom_panel_mode', 'graph') == 'graph':
                    recent_avg = sum(self.speed_history[-15:]) / max(1, len(self.speed_history[-15:]))
                    self.lbl_segment_title.configure(
                        text=f"Throughput: {format_speed(total_speed)}  •  Peak: {format_speed(peak)}  •  Avg: {format_speed(recent_avg)}  •  {total_threads} Streams Active"
                    )

                self._draw_speed_graph()

            # Dynamic eco-refresh: 250ms when downloading, 750ms when idle to conserve battery & CPU
            has_active_traffic = bool(active_tasks) or (total_speed > 0)
            self.after(250 if has_active_traffic else 750, ticker)

        self.after(250, ticker)


def run_app():
    app = FalconDMApp()
    app.mainloop()

if __name__ == "__main__":
    run_app()
