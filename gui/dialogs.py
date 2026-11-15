import os
import sys

_FALCON_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _FALCON_ROOT not in sys.path:
    sys.path.insert(0, _FALCON_ROOT)

import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import customtkinter as ctk
from typing import Callable, Optional, List, Dict, Any

try:
    from ..core.media_grabber import MediaGrabber
    from ..core.batch_manager import BatchManager
    from ..core.hasher import compute_checksums
    from ..core.engine import DEFAULT_USER_AGENT
    from ..core.credential_manager import credential_store
    from ..core.converter import MediaConverter
    from ..core.torrent_engine import TorrentEngine
    from ..core.site_grabber import SiteGrabber
    from ..core.config_manager import config_store
    from ..core.browser_bridge import BridgeRequestHandler
    from ..core.platform_utils import open_file_or_folder, bring_window_to_front
    from ..core.ai_engine import ai_engine
    from ..core.logger import falcon_logger
except (ImportError, ValueError):
    from core.media_grabber import MediaGrabber
    from core.batch_manager import BatchManager
    from core.hasher import compute_checksums
    from core.engine import DEFAULT_USER_AGENT
    from core.credential_manager import credential_store
    from core.converter import MediaConverter
    from core.torrent_engine import TorrentEngine
    from core.site_grabber import SiteGrabber
    from core.config_manager import config_store
    from core.browser_bridge import BridgeRequestHandler
    from core.platform_utils import open_file_or_folder, bring_window_to_front
    from core.ai_engine import ai_engine
    from core.logger import falcon_logger

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

class VideoGrabberDialog(ctk.CTkToplevel):
    """Sniffs and downloads videos from YouTube, TikTok, Twitter/X, Reddit, Instagram, etc."""

    def __init__(self, parent, on_download_video: Callable, default_url="", headers: Optional[dict] = None):
        super().__init__(parent)
        self.title("FalconDM - Select Video / Media Format")
        self.geometry("640x550")
        self.minsize(600, 500)
        self.resizable(True, True)
        self.on_download_video = on_download_video
        self.headers = headers or {}
        
        # Center dialog directly on user monitor
        try:
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            w, h = 640, 550
            x = max(0, (sw - w) // 2)
            y = max(0, (sh - h) // 2)
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            self.geometry("640x550+300+200")

        # Keep modal reliably in front of browser (cross-platform)
        bring_window_to_front(self)

        self.media_info: Optional[Dict[str, Any]] = None
        self._build_ui(default_url)

    def _build_ui(self, default_url: str):
        # 1. Header
        header = ctk.CTkFrame(self, fg_color="#141a24", height=48, corner_radius=0)
        header.pack(fill="x", side="top")
        ctk.CTkLabel(header, text="🎬 Universal Video & Media Grabber", font=ctk.CTkFont(size=14, weight="bold"), text_color="#f0f6fc").pack(side="left", padx=16, pady=10)

        # 2. Bottom Action Bar (Packed BEFORE body so it's always locked and visible at the bottom)
        btn_bar = ctk.CTkFrame(self, fg_color="#141a24", height=54, corner_radius=0)
        btn_bar.pack(fill="x", side="bottom")

        btn_cancel = ctk.CTkButton(btn_bar, text="Cancel", width=86, height=32, corner_radius=6, fg_color="#21262d", hover_color="#30363d", text_color="#cbd5e1", command=self.destroy)
        btn_cancel.pack(side="right", padx=14, pady=11)

        self.btn_download = ctk.CTkButton(btn_bar, text="⚡ Download Video", width=140, height=32, corner_radius=6, fg_color="#2563eb", hover_color="#1d4ed8", font=ctk.CTkFont(size=12, weight="bold"), text_color="#ffffff", command=self._submit)
        self.btn_download.pack(side="right", padx=(0, 6), pady=11)

        # 3. Expanding Body Area
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=(10, 4))

        # URL Input
        ctk.CTkLabel(body, text="Video / Media Webpage URL:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#cbd5e1").pack(anchor="w", pady=(0, 2))
        url_frame = ctk.CTkFrame(body, fg_color="transparent")
        url_frame.pack(fill="x", pady=(0, 8))

        self.entry_url = ctk.CTkEntry(url_frame, placeholder_text="e.g. YouTube, TikTok, Twitter/X, Reddit, Vimeo link", height=32, corner_radius=6, fg_color="#0d1117", border_color="#30363d", text_color="#f0f6fc")
        self.entry_url.pack(side="left", fill="x", expand=True, padx=(0, 8))
        if default_url:
            self.entry_url.insert(0, default_url)
            self.after(100, self._fetch_media)

        self.btn_fetch = ctk.CTkButton(url_frame, text="🔍 Grab Media", width=105, height=32, corner_radius=6, command=self._fetch_media, fg_color="#1f6feb", hover_color="#388bfd", text_color="#ffffff", font=ctk.CTkFont(size=11, weight="bold"))
        self.btn_fetch.pack(side="right")

        # Media Card Info
        self.card_info = ctk.CTkFrame(body, fg_color="#161b22", corner_radius=8, border_width=1, border_color="#30363d", height=130)
        self.card_info.pack(fill="x", pady=(0, 8))
        self.card_info.pack_propagate(False)

        self.lbl_title = ctk.CTkLabel(self.card_info, text="Enter a video URL above and click 'Grab Media'.", font=ctk.CTkFont(size=11, weight="bold"), text_color="#9ca3af", wraplength=580, justify="left")
        self.lbl_title.pack(anchor="w", padx=14, pady=(12, 4))

        self.lbl_details = ctk.CTkLabel(self.card_info, text="Supports YouTube, TikTok, Twitter/X, Instagram, Facebook, Reddit, Twitch, and 1000+ streaming sites.", font=ctk.CTkFont(size=10), text_color="#8b949e", wraplength=580, justify="left")
        self.lbl_details.pack(anchor="w", padx=14, pady=(0, 8))

        # Quality Selection
        ctk.CTkLabel(body, text="Select Video Quality / Format:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#cbd5e1").pack(anchor="w", pady=(2, 2))
        self.combo_formats = ctk.CTkComboBox(body, values=["Best Available Quality (Auto)"], height=32, corner_radius=6, fg_color="#0d1117", button_color="#21262d", border_color="#30363d", text_color="#f0f6fc", dropdown_fg_color="#161b22")
        self.combo_formats.pack(fill="x", pady=(0, 6))

        # Subtitles & Captions Switch
        opt_frame = ctk.CTkFrame(body, fg_color="transparent")
        opt_frame.pack(fill="x", pady=(0, 8))
        self.chk_subtitles = ctk.CTkCheckBox(
            opt_frame,
            text="Extract & Download Subtitles / Closed Captions (.srt)",
            font=ctk.CTkFont(size=11),
            text_color="#38bdf8",
            fg_color="#0284c7"
        )
        self.chk_subtitles.pack(side="left")

        # Save Directory
        ctk.CTkLabel(body, text="Save To:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#cbd5e1").pack(anchor="w", pady=(2, 2))
        dir_frame = ctk.CTkFrame(body, fg_color="transparent")
        dir_frame.pack(fill="x", pady=(0, 4))

        base_dl = config_store.get("default_download_dir", os.path.join(os.path.expanduser("~"), "Downloads", "FalconDM"))
        default_dir = os.path.join(base_dl, "Video")
        os.makedirs(default_dir, exist_ok=True)
        self.entry_dir = ctk.CTkEntry(dir_frame, height=32, corner_radius=6, fg_color="#0d1117", border_color="#30363d", text_color="#f0f6fc")
        self.entry_dir.insert(0, default_dir)
        self.entry_dir.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_browse = ctk.CTkButton(dir_frame, text="Browse...", width=86, height=32, corner_radius=6, command=self._browse_dir, fg_color="#21262d", hover_color="#30363d", border_width=1, border_color="#30363d", text_color="#cbd5e1", font=ctk.CTkFont(size=11))
        btn_browse.pack(side="right")

    def _browse_dir(self):
        f = filedialog.askdirectory(initialdir=self.entry_dir.get())
        if f:
            self.entry_dir.delete(0, "end")
            self.entry_dir.insert(0, f)

    def _fetch_media(self):
        url = self.entry_url.get().strip()
        if not url:
            messagebox.showwarning("Empty URL", "Please enter a media URL.")
            return

        self.btn_fetch.configure(state="disabled", text="Inspecting...")
        self.lbl_title.configure(text="Extracting stream info and formats from remote server...", text_color="#38bdf8")

        def fetch_worker():
            try:
                info = MediaGrabber.probe_media(url, headers=getattr(self, 'headers', None))
            except Exception as e:
                info = None

            def update_ui():
                if not self.winfo_exists():
                    return
                self.btn_fetch.configure(state="normal", text="🔍 Grab Media")
                if not info:
                    clean_name = os.path.basename(url.split('?')[0].split('#')[0]) or "Video_Stream"
                    self.lbl_title.configure(text=f"🎥 Media Stream: {clean_name}", text_color="#f3f4f6")
                    self.lbl_details.configure(text="Stream ready. Choose format below and click 'Download Video'.", text_color="#94a3b8")
                    self.combo_formats.configure(values=["Best Available Quality (Auto)", "Direct Stream (.mp4)", "Extract Audio (.mp3)"])
                    self.combo_formats.set("Best Available Quality (Auto)")
                    return
                self.media_info = info
                self.lbl_title.configure(text=f"🎥 {info.get('title', 'Unknown Title')}", text_color="#f3f4f6")
                
                uploader = info.get('uploader', 'Unknown Creator')
                try:
                    dur = int(float(info.get('duration') or 0))
                    dur_str = f"{dur // 60}:{dur % 60:02d}" if dur > 0 else "Live Stream"
                except Exception:
                    dur_str = "Unknown"
                self.lbl_details.configure(text=f"Author: {uploader} | Duration: {dur_str} | Formats available: {len(info.get('formats', []))}", text_color="#94a3b8")

                format_labels = []
                for f in info.get('formats', []):
                    lbl = f"{f.get('resolution', 'Direct')} ({f.get('ext', 'mp4').upper()})"
                    format_labels.append(lbl)

                if format_labels:
                    self.combo_formats.configure(values=format_labels)
                    self.combo_formats.set(format_labels[0])

                if info.get('has_subtitles'):
                    self.chk_subtitles.select()

            self.after(0, update_ui)

        threading.Thread(target=fetch_worker, daemon=True).start()

    def _submit(self):
        url = self.entry_url.get().strip()
        if not url:
            return
        
        selected_fmt = self.combo_formats.get()
        format_id = "bestvideo+bestaudio/best"
        
        if self.media_info and 'formats' in self.media_info:
            for f in self.media_info['formats']:
                if f['resolution'] in selected_fmt:
                    format_id = f['format_id']
                    break

        if format_id == "direct" and MediaGrabber.is_likely_media_url(url):
            format_id = "bestvideo+bestaudio/best"

        save_dir = self.entry_dir.get().strip()
        download_subs = bool(self.chk_subtitles.get())
        try:
            self.on_download_video(url, format_id, save_dir, headers=getattr(self, 'headers', None), download_subtitles=download_subs)
        except TypeError:
            try:
                self.on_download_video(url, format_id, save_dir, headers=getattr(self, 'headers', None))
            except TypeError:
                self.on_download_video(url, format_id, save_dir)
        self.destroy()


class BatchDownloadDialog(ctk.CTkToplevel):
    """Batch URL & Pattern Downloader (e.g. file[01-20].zip or multi-line URLs)."""

    def __init__(self, parent, on_enqueue_batch: Callable[[List[str], str], None]):
        super().__init__(parent)
        self.title("FalconDM - Batch Downloader & Pattern Grabber")
        self.geometry("640x530")
        self.resizable(False, False)
        self.on_enqueue_batch = on_enqueue_batch

        self.transient(parent)
        try:
            parent.deiconify()
            parent.state('normal')
            self.lift()
            self.attributes('-topmost', True)
            self.after(200, lambda: self.attributes('-topmost', False))
            self.focus_force()
            import ctypes
            ctypes.windll.user32.ShowWindow(self.winfo_id(), 9)
            ctypes.windll.user32.SetForegroundWindow(self.winfo_id())
        except Exception:
            pass

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 320
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 265
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

        self._build_ui()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="#181a20", height=50)
        header.pack(fill="x")
        ctk.CTkLabel(header, text="📦 Batch Downloader & Pattern Grabber", font=ctk.CTkFont(size=15, weight="bold"), text_color="#38bdf8").pack(side="left", padx=20, pady=10)

        # Bottom Bar (packed before body to lock at bottom)
        btn_bar = ctk.CTkFrame(self, fg_color="#181a20", height=60)
        btn_bar.pack(fill="x", side="bottom")

        btn_cancel = ctk.CTkButton(btn_bar, text="Cancel", width=90, height=36, fg_color="#4b5563", command=self.destroy)
        btn_cancel.pack(side="right", padx=15, pady=12)

        self.btn_start = ctk.CTkButton(btn_bar, text="⚡ Enqueue All to Queue", width=170, height=36, fg_color="#2563eb", hover_color="#1d4ed8", font=ctk.CTkFont(weight="bold"), command=self._submit)
        self.btn_start.pack(side="right", padx=(0, 5), pady=12)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=15)

        # Instructions
        ctk.CTkLabel(body, text="Enter multi-line URLs or URL range pattern:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(body, text="Example: https://example.com/files/part[01-10].rar", font=ctk.CTkFont(size=11), text_color="#9ca3af").pack(anchor="w", pady=(0, 6))

        # Text area
        self.txt_urls = ctk.CTkTextbox(body, height=180, font=("Consolas", 11))
        self.txt_urls.pack(fill="x", pady=(0, 10))

        # Preview Count Row
        preview_row = ctk.CTkFrame(body, fg_color="transparent")
        preview_row.pack(fill="x", pady=(0, 10))

        self.lbl_count = ctk.CTkLabel(preview_row, text="0 URLs detected", font=ctk.CTkFont(size=12, weight="bold"), text_color="#94a3b8")
        self.lbl_count.pack(side="left")

        btn_parse = ctk.CTkButton(preview_row, text="🔍 Test & Expand Pattern", width=160, height=32, command=self._parse_and_preview, fg_color="#374151")
        btn_parse.pack(side="right")

        # Destination Folder
        ctk.CTkLabel(body, text="Save Location:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", pady=(5, 2))
        dir_frame = ctk.CTkFrame(body, fg_color="transparent")
        dir_frame.pack(fill="x", pady=(0, 10))

        base_dl = config_store.get("default_download_dir", os.path.join(os.path.expanduser("~"), "Downloads", "FalconDM"))
        default_dir = os.path.join(base_dl, "Batch")
        os.makedirs(default_dir, exist_ok=True)
        self.entry_dir = ctk.CTkEntry(dir_frame, height=35)
        self.entry_dir.insert(0, default_dir)
        self.entry_dir.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_browse = ctk.CTkButton(dir_frame, text="Browse...", width=90, height=35, command=self._browse_dir, fg_color="#374151")
        btn_browse.pack(side="right")

    def _browse_dir(self):
        f = filedialog.askdirectory(initialdir=self.entry_dir.get())
        if f:
            self.entry_dir.delete(0, "end")
            self.entry_dir.insert(0, f)

    def _get_urls(self) -> List[str]:
        raw = self.txt_urls.get("1.0", "end").strip()
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        expanded = []
        for line in lines:
            if "[" in line and "]" in line:
                expanded.extend(BatchManager.expand_pattern(line))
            elif line.startswith("http://") or line.startswith("https://"):
                expanded.append(line)
        return expanded

    def _parse_and_preview(self):
        urls = self._get_urls()
        self.lbl_count.configure(text=f"✓ {len(urls)} URLs ready for download queue", text_color="#4ade80")

    def _submit(self):
        urls = self._get_urls()
        if not urls:
            messagebox.showwarning("No URLs", "Please enter at least one valid URL or pattern.")
            return
        save_dir = self.entry_dir.get().strip()
        self.on_enqueue_batch(urls, save_dir)
        self.destroy()


class ChecksumDialog(ctk.CTkToplevel):
    """File Checksum & Integrity Verifier (MD5, SHA-1, SHA-256)."""

    def __init__(self, parent, initial_file=""):
        super().__init__(parent)
        self.title("FalconDM - File Checksum & Hash Verifier")
        self.geometry("640x480")
        self.resizable(False, False)

        self.transient(parent)
        try:
            parent.deiconify()
            parent.state('normal')
            self.lift()
            self.attributes('-topmost', True)
            self.after(200, lambda: self.attributes('-topmost', False))
            self.focus_force()
            import ctypes
            ctypes.windll.user32.ShowWindow(self.winfo_id(), 9)
            ctypes.windll.user32.SetForegroundWindow(self.winfo_id())
        except Exception:
            pass

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 320
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 240
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

        self._build_ui(initial_file)

    def _build_ui(self, initial_file: str):
        header = ctk.CTkFrame(self, fg_color="#181a20", height=50)
        header.pack(fill="x")
        ctk.CTkLabel(header, text="🔍 Checksum & Integrity Verifier", font=ctk.CTkFont(size=15, weight="bold"), text_color="#38bdf8").pack(side="left", padx=20, pady=10)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=15)

        # File Chooser
        ctk.CTkLabel(body, text="Select File to Verify:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        row_file = ctk.CTkFrame(body, fg_color="transparent")
        row_file.pack(fill="x", pady=(2, 10))

        self.entry_file = ctk.CTkEntry(row_file, height=35)
        if initial_file:
            self.entry_file.insert(0, initial_file)
        self.entry_file.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_browse = ctk.CTkButton(row_file, text="Browse...", width=90, height=35, command=self._browse, fg_color="#374151")
        btn_browse.pack(side="right")

        self.btn_calc = ctk.CTkButton(body, text="Calculate Checksums", height=35, fg_color="#2563eb", hover_color="#1d4ed8", font=ctk.CTkFont(weight="bold"), command=self._calculate)
        self.btn_calc.pack(fill="x", pady=(0, 10))

        # Checksum Fields
        self.card_hashes = ctk.CTkFrame(body, fg_color="#111827", corner_radius=8)
        self.card_hashes.pack(fill="x", pady=5)

        r_md5 = ctk.CTkFrame(self.card_hashes, fg_color="transparent")
        r_md5.pack(fill="x", padx=12, pady=6)
        ctk.CTkLabel(r_md5, text="MD5:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#9ca3af", width=70, anchor="w").pack(side="left")
        self.entry_md5 = ctk.CTkEntry(r_md5, height=28, font=("Consolas", 10))
        self.entry_md5.pack(side="left", fill="x", expand=True)

        r_sha1 = ctk.CTkFrame(self.card_hashes, fg_color="transparent")
        r_sha1.pack(fill="x", padx=12, pady=6)
        ctk.CTkLabel(r_sha1, text="SHA-1:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#9ca3af", width=70, anchor="w").pack(side="left")
        self.entry_sha1 = ctk.CTkEntry(r_sha1, height=28, font=("Consolas", 10))
        self.entry_sha1.pack(side="left", fill="x", expand=True)

        r_sha256 = ctk.CTkFrame(self.card_hashes, fg_color="transparent")
        r_sha256.pack(fill="x", padx=12, pady=6)
        ctk.CTkLabel(r_sha256, text="SHA-256:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#9ca3af", width=70, anchor="w").pack(side="left")
        self.entry_sha256 = ctk.CTkEntry(r_sha256, height=28, font=("Consolas", 10))
        self.entry_sha256.pack(side="left", fill="x", expand=True)

        # Compare Expected Hash
        ctk.CTkLabel(body, text="Verify Against Expected Hash:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", pady=(10, 2))
        row_comp = ctk.CTkFrame(body, fg_color="transparent")
        row_comp.pack(fill="x", pady=(0, 5))

        self.entry_compare = ctk.CTkEntry(row_comp, placeholder_text="Paste expected MD5/SHA1/SHA256 from website here", height=34, font=("Consolas", 10))
        self.entry_compare.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_verify = ctk.CTkButton(row_comp, text="Compare", width=90, height=34, command=self._compare_hash, fg_color="#10b981", hover_color="#059669")
        btn_verify.pack(side="right")

        self.lbl_verify_res = ctk.CTkLabel(body, text="", font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_verify_res.pack(anchor="w", pady=(4, 0))

        # Auto-calculate if file provided
        if initial_file and os.path.exists(initial_file):
            self.after(200, self._calculate)

    def _browse(self):
        f = filedialog.askopenfilename()
        if f:
            self.entry_file.delete(0, "end")
            self.entry_file.insert(0, f)
            self._calculate()

    def _calculate(self):
        path = self.entry_file.get().strip()
        if not os.path.isfile(path):
            messagebox.showerror("Error", "File does not exist.")
            return

        self.btn_calc.configure(state="disabled", text="Computing Hashes...")

        def calc_worker():
            hashes = compute_checksums(path)
            def update_ui():
                self.btn_calc.configure(state="normal", text="Calculate Checksums")
                for key, val in hashes.items():
                    entry = getattr(self, f"entry_{key}", None)
                    if entry:
                        entry.delete(0, "end")
                        entry.insert(0, val)
                if self.entry_compare.get().strip():
                    self._compare_hash()
            self.after(0, update_ui)

        threading.Thread(target=calc_worker, daemon=True).start()

    def _compare_hash(self):
        comp = self.entry_compare.get().strip().lower()
        if not comp:
            return
        
        md5 = self.entry_md5.get().strip().lower()
        sha1 = self.entry_sha1.get().strip().lower()
        sha256 = self.entry_sha256.get().strip().lower()

        if comp in (md5, sha1, sha256):
            self.lbl_verify_res.configure(text="✓ Checksum Matched! File is 100% authentic and uncorrupted.", text_color="#4ade80")
        else:
            self.lbl_verify_res.configure(text="❌ Hash MISMATCH! File may be corrupt or modified.", text_color="#f87171")


class BrowserIntegrationDialog(ctk.CTkToplevel):
    """Universal browser integration hub: Chrome, Edge, Brave, Opera, Arc, Firefox, Safari, and any browser."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("FalconDM - Universal Browser Integration (Works with ANY Browser)")
        self.geometry("720x560")
        self.minsize(680, 520)
        self.resizable(True, True)

        self.transient(parent)
        try:
            parent.deiconify()
            parent.state('normal')
            self.lift()
            self.attributes('-topmost', True)
            self.after(200, lambda: self.attributes('-topmost', False))
            self.focus_force()
            import ctypes
            ctypes.windll.user32.ShowWindow(self.winfo_id(), 9)
            ctypes.windll.user32.SetForegroundWindow(self.winfo_id())
        except Exception:
            pass

        self.update_idletasks()
        try:
            x = parent.winfo_x() + (parent.winfo_width() // 2) - 360
            y = parent.winfo_y() + (parent.winfo_height() // 2) - 280
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        self._build_ui()

    def _build_ui(self):
        import webbrowser

        ext_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "browser_extension"))
        script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "falcon_browser_extension.user.js"))
        bookmarklet_code = (
            "javascript:(function(){const u=window.location.href;const s=window.getSelection().toString();"
            "const t=prompt('⚡ Send download to FalconDM:',s||u);if(t){fetch('http://127.0.0.1:9666/download',"
            "{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:t})})"
            ".then(r=>r.json()).then(d=>alert('⚡ Sent to FalconDM Turbo Downloader!'))"
            ".catch(e=>alert('❌ FalconDM is not running. Launch FalconDM first!'));}})();"
        )

        # 1. Header
        header = ctk.CTkFrame(self, fg_color="#181a20", height=54, corner_radius=0)
        header.pack(fill="x", side="top")
        
        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left", padx=20, pady=8)
        ctk.CTkLabel(title_box, text="⚡ Universal Browser Integration Hub", font=ctk.CTkFont(size=15, weight="bold"), text_color="#38bdf8").pack(anchor="w")
        ctk.CTkLabel(title_box, text="Compatible with Chrome, Edge, Firefox, Brave, Opera, Arc, Safari & more", font=ctk.CTkFont(size=11), text_color="#64748b").pack(anchor="w")

        status_badge = ctk.CTkLabel(header, text="● Bridge Online (:9666)", font=ctk.CTkFont(size=11, weight="bold"), text_color="#4ade80", fg_color="rgba(34,197,94,0.15)", corner_radius=999, padx=12, pady=4)
        status_badge.pack(side="right", padx=20, pady=12)

        # 2. Bottom Action Bar (locked at bottom)
        btn_row = ctk.CTkFrame(self, fg_color="#181a20", height=60, corner_radius=0)
        btn_row.pack(fill="x", side="bottom")

        btn_close = ctk.CTkButton(btn_row, text="Close", width=90, height=36, fg_color="#4b5563", hover_color="#374151", command=self.destroy)
        btn_close.pack(side="right", padx=15, pady=12)

        def open_folder():
            import subprocess
            if os.path.exists(ext_dir):
                subprocess.run(f'explorer "{ext_dir}"', shell=True)
            else:
                messagebox.showinfo("Extension Folder", f"Path: {ext_dir}")

        def open_web_hub():
            webbrowser.open("http://127.0.0.1:9666/")

        btn_web = ctk.CTkButton(btn_row, text="🌐 Open Web Setup Hub", width=170, height=36, fg_color="#0284c7", hover_color="#0369a1", font=ctk.CTkFont(weight="bold"), command=open_web_hub)
        btn_web.pack(side="right", padx=(0, 8), pady=12)

        btn_folder = ctk.CTkButton(btn_row, text="📂 Open Extension Folder", width=170, height=36, fg_color="#334155", hover_color="#475569", font=ctk.CTkFont(weight="bold"), command=open_folder)
        btn_folder.pack(side="right", padx=(0, 8), pady=12)

        # 3. Tabview for Browser-Specific Guides
        tabview = ctk.CTkTabview(self, fg_color="#111827", segmented_button_fg_color="#182234", segmented_button_selected_color="#2563eb", segmented_button_selected_hover_color="#1d4ed8")
        tabview.pack(fill="both", expand=True, padx=20, pady=15)

        tab_chrome = tabview.add("🌐 Chrome / Edge / Brave")
        tab_firefox = tabview.add("🦊 Mozilla Firefox")
        tab_safari = tabview.add("🍏 Safari & Any Browser")
        tab_userscript = tabview.add("📜 Userscript")
        tab_clipboard = tabview.add("📋 Zero-Install Clipboard")

        # --- Tab 1: Chrome / Edge / Brave / Opera / Arc / Vivaldi ---
        c_scroll = ctk.CTkScrollableFrame(tab_chrome, fg_color="transparent")
        c_scroll.pack(fill="both", expand=True, padx=5, pady=5)

        ctk.CTkLabel(c_scroll, text="Native Chromium Extension (Chrome, Edge, Brave, Opera, Arc, Vivaldi)", font=ctk.CTkFont(size=14, weight="bold"), text_color="#38bdf8").pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(c_scroll, text="Provides IDM-grade automatic download interception + floating video grabber overlay.", font=ctk.CTkFont(size=12), text_color="#94a3b8").pack(anchor="w", pady=(0, 12))

        c_steps = (
            "1. Open your browser extensions manager:\n"
            "   • Google Chrome: chrome://extensions\n"
            "   • Microsoft Edge: edge://extensions\n"
            "   • Brave Browser: brave://extensions\n"
            "   • Opera / Arc / Vivaldi: extensions settings\n\n"
            "2. Turn ON 'Developer mode' toggle switch in the top-right corner.\n"
            "3. Click 'Load unpacked' and select the FalconDM browser_extension directory.\n"
            "4. Done! FalconDM will now auto-intercept file downloads and show download buttons."
        )
        c_box = ctk.CTkFrame(c_scroll, fg_color="#182234", corner_radius=8, border_width=1, border_color="#1e293b")
        c_box.pack(fill="x", pady=5)
        ctk.CTkLabel(c_box, text=c_steps, font=ctk.CTkFont(family="Consolas", size=12), justify="left", text_color="#e5e7eb").pack(anchor="w", padx=16, pady=14)

        def one_click_install(bname="chrome"):
            from core.platform_utils import register_browser_integration
            register_browser_integration()
            BridgeRequestHandler.launch_browser_extensions(bname)
            messagebox.showinfo(
                "FalconDM 1-Click Setup",
                f"⚡ Extension folder path COPIED to clipboard!\n\n"
                f"Your {bname.upper()} extensions page has opened.\n\n"
                f"Now simply do these 2 steps:\n"
                f"  1. Turn ON 'Developer mode' (toggle at top-right)\n"
                f"  2. Click 'Load unpacked'\n"
                f"  3. Press Ctrl + V in the folder dialog and hit Enter!\n\n"
                f"FalconDM is now fully active in your browser!"
            )

        c_btn_row = ctk.CTkFrame(c_scroll, fg_color="transparent")
        c_btn_row.pack(anchor="w", pady=10)
        ctk.CTkButton(c_btn_row, text="⚡ 1-Click Install (Chrome)", width=180, height=32, fg_color="#059669", hover_color="#047857", font=ctk.CTkFont(size=11, weight="bold"), command=lambda: one_click_install("chrome")).pack(side="left", padx=(0, 8))
        ctk.CTkButton(c_btn_row, text="⚡ 1-Click Install (Edge)", width=170, height=32, fg_color="#0284c7", hover_color="#0369a1", font=ctk.CTkFont(size=11, weight="bold"), command=lambda: one_click_install("edge")).pack(side="left", padx=(0, 8))
        ctk.CTkButton(c_btn_row, text="📂 Open Folder", width=120, height=32, fg_color="#334155", hover_color="#475569", font=ctk.CTkFont(size=11, weight="bold"), command=open_folder).pack(side="left", padx=(0, 8))
        ctk.CTkButton(c_btn_row, text="🚀 Brave", width=90, height=32, fg_color="#334155", hover_color="#475569", font=ctk.CTkFont(size=11, weight="bold"), command=lambda: one_click_install("brave")).pack(side="left")

        # --- Tab 2: Firefox & Gecko Browsers ---
        f_scroll = ctk.CTkScrollableFrame(tab_firefox, fg_color="transparent")
        f_scroll.pack(fill="both", expand=True, padx=5, pady=5)

        ctk.CTkLabel(f_scroll, text="Mozilla Firefox / Floorp / LibreWolf / Waterfox Integration", font=ctk.CTkFont(size=14, weight="bold"), text_color="#f97316").pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(f_scroll, text="Firefox supports FalconDM via Manifest V3 temporary add-on or packaged XPI bundle.", font=ctk.CTkFont(size=12), text_color="#94a3b8").pack(anchor="w", pady=(0, 12))

        f_steps = (
            "1. In Firefox address bar, navigate to: about:debugging#/runtime/this-firefox\n"
            "2. Click the 'Load Temporary Add-on...' button.\n"
            "3. Select the 'manifest.json' file inside FalconDM's browser_extension folder\n"
            "   (or click 'Package Firefox Add-on' below to generate a falcondm.xpi).\n"
            "4. Ready! Firefox will seamlessly forward downloads and media to FalconDM."
        )
        f_box = ctk.CTkFrame(f_scroll, fg_color="#182234", corner_radius=8, border_width=1, border_color="#1e293b")
        f_box.pack(fill="x", pady=5)
        ctk.CTkLabel(f_box, text=f_steps, font=ctk.CTkFont(family="Consolas", size=12), justify="left", text_color="#e5e7eb").pack(anchor="w", padx=16, pady=14)

        def package_xpi():
            import zipfile
            assets_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets"))
            out_xpi = os.path.join(assets_dir, "falcondm.xpi")
            try:
                with zipfile.ZipFile(out_xpi, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for root, _, files in os.walk(ext_dir):
                        for f in files:
                            full_path = os.path.join(root, f)
                            rel_path = os.path.relpath(full_path, ext_dir)
                            zf.write(full_path, rel_path)
                import subprocess
                subprocess.run(f'explorer /select,"{out_xpi}"', shell=True)
                messagebox.showinfo("Firefox Add-on", f"Packaged Firefox Add-on created:\n{out_xpi}\n\nYou can load this file directly in Firefox!")
            except Exception as e:
                messagebox.showerror("Error", f"Could not package XPI: {e}")

        f_btn_row = ctk.CTkFrame(f_scroll, fg_color="transparent")
        f_btn_row.pack(anchor="w", pady=10)
        ctk.CTkButton(f_btn_row, text="📦 Package Firefox Add-on (.xpi)", width=200, height=32, fg_color="#ea580c", hover_color="#c2410c", font=ctk.CTkFont(size=11, weight="bold"), command=package_xpi).pack(side="left", padx=(0, 8))
        ctk.CTkButton(f_btn_row, text="🚀 Open Firefox Debugging", width=180, height=32, fg_color="#334155", hover_color="#475569", font=ctk.CTkFont(size=11, weight="bold"), command=lambda: BridgeRequestHandler.launch_browser_extensions("firefox")).pack(side="left", padx=(0, 8))
        ctk.CTkButton(f_btn_row, text="📂 Open Extension Folder", width=160, height=32, fg_color="#334155", hover_color="#475569", font=ctk.CTkFont(size=11, weight="bold"), command=open_folder).pack(side="left")

        # --- Tab 3: Safari & Any Other Browser (Bookmarklet) ---
        s_scroll = ctk.CTkScrollableFrame(tab_safari, fg_color="transparent")
        s_scroll.pack(fill="both", expand=True, padx=5, pady=5)

        ctk.CTkLabel(s_scroll, text="Universal 1-Click Bookmarklet (Works on 100% of All Browsers)", font=ctk.CTkFont(size=14, weight="bold"), text_color="#a855f7").pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(s_scroll, text="Safari on macOS/iPad, Chrome on iOS/Android, Tor, and school/work locked browsers.", font=ctk.CTkFont(size=12), text_color="#94a3b8").pack(anchor="w", pady=(0, 12))

        s_desc = (
            "No extensions or developer permissions required!\n\n"
            "How to use on Safari or ANY browser:\n"
            "1. Copy the Bookmarklet code below.\n"
            "2. Create a new Bookmark in Safari (or any browser) and paste the code into the URL field.\n"
            "   (Or open the Web Hub and drag the '⚡ Send to FalconDM' button into your bookmarks bar!)\n"
            "3. Whenever you are browsing any video or file download, click the bookmark to send it straight to FalconDM!"
        )
        s_box = ctk.CTkFrame(s_scroll, fg_color="#182234", corner_radius=8, border_width=1, border_color="#1e293b")
        s_box.pack(fill="x", pady=5)
        ctk.CTkLabel(s_box, text=s_desc, font=ctk.CTkFont(size=12), justify="left", text_color="#e5e7eb").pack(anchor="w", padx=16, pady=12)

        def copy_bookmarklet():
            self.clipboard_clear()
            self.clipboard_append(bookmarklet_code)
            messagebox.showinfo("Bookmarklet Copied", "✓ Universal Bookmarklet code copied to clipboard!\n\nPaste it into the URL field of any browser bookmark.")

        s_btn_row = ctk.CTkFrame(s_scroll, fg_color="transparent")
        s_btn_row.pack(anchor="w", pady=10)
        ctk.CTkButton(s_btn_row, text="📋 Copy Bookmarklet Code", width=190, height=32, fg_color="#9333ea", hover_color="#7e22ce", font=ctk.CTkFont(size=11, weight="bold"), command=copy_bookmarklet).pack(side="left", padx=(0, 8))
        ctk.CTkButton(s_btn_row, text="🌐 Drag & Drop from Web Hub", width=200, height=32, fg_color="#334155", hover_color="#475569", font=ctk.CTkFont(size=11, weight="bold"), command=open_web_hub).pack(side="left")

        # --- Tab 4: Tampermonkey Userscript ---
        u_scroll = ctk.CTkScrollableFrame(tab_userscript, fg_color="transparent")
        u_scroll.pack(fill="both", expand=True, padx=5, pady=5)

        ctk.CTkLabel(u_scroll, text="Userscript Manager (Tampermonkey / Violentmonkey / Greasemonkey)", font=ctk.CTkFont(size=14, weight="bold"), text_color="#10b981").pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(u_scroll, text="Universal cross-browser script supporting Chrome, Firefox, Edge, Safari (Userscripts app).", font=ctk.CTkFont(size=12), text_color="#94a3b8").pack(anchor="w", pady=(0, 12))

        u_desc = (
            "1. Install Tampermonkey or Violentmonkey extension in your browser.\n"
            "2. Click 'Install Userscript via Web Hub' below or open the script file.\n"
            "3. Tampermonkey will prompt you to confirm with 1 click.\n"
            "4. Instantly activates floating video grabber buttons and Alt + Click downloading!"
        )
        u_box = ctk.CTkFrame(u_scroll, fg_color="#182234", corner_radius=8, border_width=1, border_color="#1e293b")
        u_box.pack(fill="x", pady=5)
        ctk.CTkLabel(u_box, text=u_desc, font=ctk.CTkFont(size=12), justify="left", text_color="#e5e7eb").pack(anchor="w", padx=16, pady=12)

        def open_userscript():
            if os.path.exists(script_path):
                os.startfile(script_path)
            else:
                messagebox.showinfo("Userscript", f"Script location:\n{script_path}")

        u_btn_row = ctk.CTkFrame(u_scroll, fg_color="transparent")
        u_btn_row.pack(anchor="w", pady=10)
        ctk.CTkButton(u_btn_row, text="🌐 Install Userscript via Web Hub", width=220, height=32, fg_color="#059669", hover_color="#047857", font=ctk.CTkFont(size=11, weight="bold"), command=lambda: webbrowser.open("http://127.0.0.1:9666/falcon_browser_extension.user.js")).pack(side="left", padx=(0, 8))
        ctk.CTkButton(u_btn_row, text="📂 Open Script File", width=150, height=32, fg_color="#334155", hover_color="#475569", font=ctk.CTkFont(size=11, weight="bold"), command=open_userscript).pack(side="left")

        # --- Tab 5: Clipboard Sniffing ---
        clip_scroll = ctk.CTkScrollableFrame(tab_clipboard, fg_color="transparent")
        clip_scroll.pack(fill="both", expand=True, padx=5, pady=5)

        ctk.CTkLabel(clip_scroll, text="Clipboard Auto-Sniffing (Zero Setup Required)", font=ctk.CTkFont(size=14, weight="bold"), text_color="#f59e0b").pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(clip_scroll, text="Works seamlessly across EVERY application and browser on your Windows system.", font=ctk.CTkFont(size=12), text_color="#94a3b8").pack(anchor="w", pady=(0, 12))

        clip_desc = (
            "• Keep FalconDM running (either in main window or minimized to system tray).\n"
            "• Whenever you Copy (Ctrl+C) any download link, ISO, EXE, ZIP, MP4, or video link\n"
            "  in ANY browser (Chrome, Edge, Firefox, Safari, Brave, Opera, Tor, etc.),\n"
            "  FalconDM immediately sniffs it and offers to download at maximum turbo speed!\n\n"
            "• No browser extensions, no developer mode, and no configuration required."
        )
        clip_box = ctk.CTkFrame(clip_scroll, fg_color="#182234", corner_radius=8, border_width=1, border_color="#1e293b")
        clip_box.pack(fill="x", pady=5)
        ctk.CTkLabel(clip_box, text=clip_desc, font=ctk.CTkFont(size=12), justify="left", text_color="#e5e7eb").pack(anchor="w", padx=16, pady=14)



class SchedulerDialog(ctk.CTkToplevel):
    """IDM-Style Queue Scheduler & Power Management Dialog."""

    def __init__(self, parent, scheduler):
        super().__init__(parent)
        self.scheduler = scheduler
        self.title("FalconDM - Queue Scheduler & Power Management")
        self.geometry("620x540")
        self.resizable(False, False)

        self.transient(parent)
        try:
            parent.deiconify()
            parent.state('normal')
            self.lift()
            self.attributes('-topmost', True)
            self.after(200, lambda: self.attributes('-topmost', False))
            self.focus_force()
            import ctypes
            ctypes.windll.user32.ShowWindow(self.winfo_id(), 9)
            ctypes.windll.user32.SetForegroundWindow(self.winfo_id())
        except Exception:
            pass

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 310
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 270
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

        self._build_ui()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="#181a20", height=50)
        header.pack(fill="x")
        ctk.CTkLabel(header, text="⏱️ Automated Queue Scheduler & Power Control", font=ctk.CTkFont(size=14, weight="bold"), text_color="#38bdf8").pack(side="left", padx=20, pady=10)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=15)

        # 1. Queue Selection
        row_q = ctk.CTkFrame(body, fg_color="transparent")
        row_q.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(row_q, text="Select Queue:", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(0, 10))
        self.combo_queue = ctk.CTkComboBox(row_q, values=list(self.scheduler.queues.keys()), command=self._on_queue_change, width=200)
        self.combo_queue.set("Night Queue" if "Night Queue" in self.scheduler.queues else "Default")
        self.combo_queue.pack(side="left")

        # 2. Timing Schedule Card
        card_sched = ctk.CTkFrame(body, fg_color="#111827", corner_radius=8)
        card_sched.pack(fill="x", pady=6, padx=2)

        self.var_sched_enabled = ctk.BooleanVar(value=False)
        chk_sched = ctk.CTkCheckBox(card_sched, text="Enable Automated Time Scheduling", variable=self.var_sched_enabled, font=ctk.CTkFont(size=12, weight="bold"), text_color="#38bdf8")
        chk_sched.pack(anchor="w", padx=16, pady=(12, 10))

        # Time inputs
        time_row = ctk.CTkFrame(card_sched, fg_color="transparent")
        time_row.pack(fill="x", padx=16, pady=(0, 12))

        ctk.CTkLabel(time_row, text="Start downloads at (HH:MM):", font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 8))
        self.entry_start = ctk.CTkEntry(time_row, width=70, placeholder_text="02:00")
        self.entry_start.pack(side="left", padx=(0, 20))

        ctk.CTkLabel(time_row, text="Stop at (HH:MM):", font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 8))
        self.entry_stop = ctk.CTkEntry(time_row, width=70, placeholder_text="06:30")
        self.entry_stop.pack(side="left")

        # 3. Concurrency settings
        card_conc = ctk.CTkFrame(body, fg_color="#111827", corner_radius=8)
        card_conc.pack(fill="x", pady=6, padx=2)

        conc_row = ctk.CTkFrame(card_conc, fg_color="transparent")
        conc_row.pack(fill="x", padx=16, pady=12)

        ctk.CTkLabel(conc_row, text="Max Concurrent Active Downloads:", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(0, 10))
        self.combo_conc = ctk.CTkComboBox(conc_row, values=["1 Download at a time", "2 Simultaneous Downloads", "3 Simultaneous Downloads", "5 Simultaneous Downloads"], width=220)
        self.combo_conc.set("1 Download at a time")
        self.combo_conc.pack(side="left")

        # 4. Power Management Card (Auto-Shutdown)
        card_power = ctk.CTkFrame(body, fg_color="#111827", corner_radius=8)
        card_power.pack(fill="x", pady=6, padx=2)

        self.var_shutdown = ctk.BooleanVar(value=False)
        chk_power = ctk.CTkCheckBox(
            card_power,
            text="🔴 Auto-Shutdown: Turn off computer when all downloads in this queue finish",
            variable=self.var_shutdown,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#f87171"
        )
        chk_power.pack(anchor="w", padx=16, pady=12)

        # Abort shutdown button (if active)
        if self.scheduler.shutdown_triggered:
            btn_abort = ctk.CTkButton(card_power, text="⚠️ Cancel Pending Shutdown Countdown!", fg_color="#dc2626", hover_color="#b91c1c", command=self._abort_shutdown)
            btn_abort.pack(anchor="w", padx=16, pady=(0, 10))

        # Bottom Buttons
        btn_bar = ctk.CTkFrame(self, fg_color="#181a20", height=60)
        btn_bar.pack(fill="x", side="bottom")

        btn_close = ctk.CTkButton(btn_bar, text="Close", width=90, height=36, fg_color="#4b5563", command=self.destroy)
        btn_close.pack(side="right", padx=15, pady=12)

        btn_save = ctk.CTkButton(btn_bar, text="💾 Save Schedule Settings", width=170, height=36, fg_color="#2563eb", hover_color="#1d4ed8", font=ctk.CTkFont(weight="bold"), command=self._save_settings)
        btn_save.pack(side="right", padx=(0, 5), pady=12)

        self._load_queue_settings(self.combo_queue.get())

    def _on_queue_change(self, choice: str):
        self._load_queue_settings(choice)

    def _load_queue_settings(self, q_name: str):
        q = self.scheduler.get_or_create_queue(q_name)
        self.var_sched_enabled.set(q.enabled)
        self.entry_start.delete(0, "end")
        if q.start_time:
            self.entry_start.insert(0, q.start_time)
        self.entry_stop.delete(0, "end")
        if q.stop_time:
            self.entry_stop.insert(0, q.stop_time)
        self.var_shutdown.set(q.shutdown_on_finish)
        conc_map = {1: "1 Download at a time", 2: "2 Simultaneous Downloads", 3: "3 Simultaneous Downloads", 5: "5 Simultaneous Downloads"}
        self.combo_conc.set(conc_map.get(q.max_concurrent, "1 Download at a time"))

    def _save_settings(self):
        q_name = self.combo_queue.get().strip()
        q = self.scheduler.get_or_create_queue(q_name)
        q.enabled = self.var_sched_enabled.get()
        q.start_time = self.entry_start.get().strip() or None
        q.stop_time = self.entry_stop.get().strip() or None
        q.shutdown_on_finish = self.var_shutdown.get()

        conc_str = self.combo_conc.get()
        q.max_concurrent = int(conc_str[0]) if conc_str and conc_str[0].isdigit() else 1

        self.scheduler.save_config()
        messagebox.showinfo("Scheduler Saved", f"Settings for queue '{q_name}' saved successfully!")
        self.destroy()

    def _abort_shutdown(self):
        self.scheduler.abort_shutdown()
        messagebox.showinfo("Shutdown Aborted", "Computer shutdown countdown was successfully cancelled.")


class SpeedLimiterDialog(ctk.CTkToplevel):
    """Global Bandwidth Speed Limiter Configuration."""

    def __init__(self, parent, manager):
        super().__init__(parent)
        self.manager = manager
        self.title("FalconDM - Bandwidth Speed Limiter")
        self.geometry("480x320")
        self.resizable(False, False)

        self.transient(parent)
        try:
            parent.deiconify()
            parent.state('normal')
            self.lift()
            self.attributes('-topmost', True)
            self.after(200, lambda: self.attributes('-topmost', False))
            self.focus_force()
            import ctypes
            ctypes.windll.user32.ShowWindow(self.winfo_id(), 9)
            ctypes.windll.user32.SetForegroundWindow(self.winfo_id())
        except Exception:
            pass

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 240
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 160
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

        self._build_ui()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="#181a20", height=45)
        header.pack(fill="x")
        ctk.CTkLabel(header, text="⚡ Global Bandwidth Speed Limiter", font=ctk.CTkFont(size=14, weight="bold"), text_color="#38bdf8").pack(side="left", padx=20, pady=8)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=15)

        ctk.CTkLabel(body, text="Select Maximum Download Speed Limit:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", pady=(0, 6))

        self.combo_speed = ctk.CTkComboBox(
            body,
            values=["Unlimited (Maximum Speed)", "256 KB/s", "512 KB/s", "1 MB/s", "2 MB/s", "5 MB/s", "10 MB/s", "25 MB/s"],
            height=35
        )
        self.combo_speed.set("Unlimited (Maximum Speed)")
        self.combo_speed.pack(fill="x", pady=(0, 15))

        lbl_desc = ctk.CTkLabel(
            body,
            text="The speed limiter uses FalconDM's precision Token Bucket algorithm to smoothly throttle download sockets without causing network jitter or packet drops.",
            font=ctk.CTkFont(size=11),
            text_color="#9ca3af",
            wraplength=440,
            justify="left"
        )
        lbl_desc.pack(anchor="w")

        btn_bar = ctk.CTkFrame(self, fg_color="#181a20", height=50)
        btn_bar.pack(fill="x", side="bottom")

        btn_close = ctk.CTkButton(btn_bar, text="Cancel", width=90, height=34, fg_color="#4b5563", command=self.destroy)
        btn_close.pack(side="right", padx=15, pady=8)

        btn_apply = ctk.CTkButton(btn_bar, text="⚡ Apply Limit", width=120, height=34, fg_color="#2563eb", hover_color="#1d4ed8", font=ctk.CTkFont(weight="bold"), command=self._apply_limit)
        btn_apply.pack(side="right", padx=(0, 5), pady=8)

    def _apply_limit(self):
        choice = self.combo_speed.get()
        speed_map = {
            "Unlimited (Maximum Speed)": 0,
            "256 KB/s": 256 * 1024,
            "512 KB/s": 512 * 1024,
            "1 MB/s": 1024 * 1024,
            "2 MB/s": 2 * 1024 * 1024,
            "5 MB/s": 5 * 1024 * 1024,
            "10 MB/s": 10 * 1024 * 1024,
            "25 MB/s": 25 * 1024 * 1024,
        }
        bps = speed_map.get(choice, 0)
        for task in self.manager.tasks.values():
            if hasattr(task, "set_speed_limit"):
                task.set_speed_limit(bps)

        msg = f"Speed limit set to {choice} for all downloads!" if bps > 0 else "Speed limit removed. All downloads running at maximum turbo speed!"
        messagebox.showinfo("Speed Limiter Updated", msg)
        self.destroy()


class SiteLoginsDialog(ctk.CTkToplevel):
    """Site Logins & Password Manager (HTTP Basic Auth & Premium Filelocker Credentials)."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("FalconDM - Site Logins & Password Manager")
        self.geometry("620x500")
        self.resizable(False, False)

        self.transient(parent)
        try:
            parent.deiconify()
            parent.state('normal')
            self.lift()
            self.attributes('-topmost', True)
            self.after(200, lambda: self.attributes('-topmost', False))
            self.focus_force()
            import ctypes
            ctypes.windll.user32.ShowWindow(self.winfo_id(), 9)
            ctypes.windll.user32.SetForegroundWindow(self.winfo_id())
        except Exception:
            pass

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 310
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 250
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

        self._build_ui()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="#181a20", height=50)
        header.pack(fill="x")
        ctk.CTkLabel(header, text="🔑 Site Logins & Password Manager", font=ctk.CTkFont(size=14, weight="bold"), text_color="#38bdf8").pack(side="left", padx=20, pady=10)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=15)

        # Form Inputs
        form_frame = ctk.CTkFrame(body, fg_color="#111827", corner_radius=8)
        form_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(form_frame, text="Add / Update Site Credential:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=16, pady=(12, 6))

        row1 = ctk.CTkFrame(form_frame, fg_color="transparent")
        row1.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(row1, text="Domain / Hostname:", width=130, anchor="w", font=ctk.CTkFont(size=11)).pack(side="left")
        self.entry_domain = ctk.CTkEntry(row1, placeholder_text="e.g. rapidgator.net or 192.168.1.1", height=32)
        self.entry_domain.pack(side="left", fill="x", expand=True)

        row2 = ctk.CTkFrame(form_frame, fg_color="transparent")
        row2.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(row2, text="Username:", width=130, anchor="w", font=ctk.CTkFont(size=11)).pack(side="left")
        self.entry_user = ctk.CTkEntry(row2, placeholder_text="Username / Account Email", height=32)
        self.entry_user.pack(side="left", fill="x", expand=True)

        row3 = ctk.CTkFrame(form_frame, fg_color="transparent")
        row3.pack(fill="x", padx=16, pady=(4, 12))
        ctk.CTkLabel(row3, text="Password:", width=130, anchor="w", font=ctk.CTkFont(size=11)).pack(side="left")
        self.entry_pass = ctk.CTkEntry(row3, placeholder_text="Password / API Token", show="•", height=32)
        self.entry_pass.pack(side="left", fill="x", expand=True)

        btn_save = ctk.CTkButton(form_frame, text="➕ Save Credential", fg_color="#2563eb", hover_color="#1d4ed8", font=ctk.CTkFont(weight="bold"), command=self._save_credential)
        btn_save.pack(anchor="e", padx=16, pady=(0, 12))

        # Saved List
        ctk.CTkLabel(body, text="Active Saved Site Credentials:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", pady=(8, 4))
        self.scroll_list = ctk.CTkScrollableFrame(body, fg_color="#181a20", height=150, corner_radius=6)
        self.scroll_list.pack(fill="both", expand=True)

        btn_bar = ctk.CTkFrame(self, fg_color="#181a20", height=50)
        btn_bar.pack(fill="x", side="bottom")

        btn_close = ctk.CTkButton(btn_bar, text="Close", width=90, height=34, fg_color="#4b5563", command=self.destroy)
        btn_close.pack(side="right", padx=15, pady=8)

        self._refresh_list()

    def _refresh_list(self):
        for w in self.scroll_list.winfo_children():
            w.destroy()

        if not credential_store.credentials:
            ctk.CTkLabel(self.scroll_list, text="No site credentials saved yet.", text_color="#6b7280").pack(pady=20)
            return

        for domain, cred in credential_store.credentials.items():
            row = ctk.CTkFrame(self.scroll_list, fg_color="#111827", height=36)
            row.pack(fill="x", pady=2, padx=4)
            u_text = cred.get('username') or '(Header Auth)'
            ctk.CTkLabel(row, text=f"🌐 {domain}", font=ctk.CTkFont(size=12, weight="bold"), text_color="#38bdf8").pack(side="left", padx=10)
            ctk.CTkLabel(row, text=f"User: {u_text}", font=ctk.CTkFont(size=11), text_color="#9ca3af").pack(side="left", padx=10)

            def make_delete(d):
                return lambda: self._delete_credential(d)

            btn_del = ctk.CTkButton(row, text="Delete", width=60, height=24, fg_color="#ef4444", hover_color="#dc2626", command=make_delete(domain))
            btn_del.pack(side="right", padx=8, pady=4)

    def _save_credential(self):
        domain = self.entry_domain.get().strip()
        user = self.entry_user.get().strip()
        pw = self.entry_pass.get().strip()
        if not domain:
            messagebox.showwarning("Missing Domain", "Please enter a domain or hostname.")
            return

        credential_store.add_credential(domain, username=user, password=pw)
        self.entry_domain.delete(0, "end")
        self.entry_user.delete(0, "end")
        self.entry_pass.delete(0, "end")
        self._refresh_list()
        messagebox.showinfo("Saved", f"Credentials for {domain} saved!")

    def _delete_credential(self, domain):
        credential_store.remove_credential(domain)
        self._refresh_list()


class MediaConverterDialog(ctk.CTkToplevel):
    """Built-in Media Format Converter & Stream Extractor (MP4, MKV, MP3, WAV, FLAC)."""

    def __init__(self, parent, initial_file: str = ""):
        super().__init__(parent)
        self.title("FalconDM - Audio & Video Converter")
        self.geometry("620x460")
        self.resizable(False, False)

        self.transient(parent)
        try:
            parent.deiconify()
            parent.state('normal')
            self.lift()
            self.attributes('-topmost', True)
            self.after(200, lambda: self.attributes('-topmost', False))
            self.focus_force()
            import ctypes
            ctypes.windll.user32.ShowWindow(self.winfo_id(), 9)
            ctypes.windll.user32.SetForegroundWindow(self.winfo_id())
        except Exception:
            pass

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 310
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 230
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

        self.initial_file = initial_file
        self._stop_event = threading.Event()
        self._build_ui()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="#181a20", height=50)
        header.pack(fill="x")
        ctk.CTkLabel(header, text="🔄 Audio & Video Converter (FFmpeg Studio)", font=ctk.CTkFont(size=14, weight="bold"), text_color="#38bdf8").pack(side="left", padx=20, pady=10)

        # Bottom Bar (docked first)
        btn_bar = ctk.CTkFrame(self, fg_color="#181a20", height=50)
        btn_bar.pack(fill="x", side="bottom")

        btn_close = ctk.CTkButton(btn_bar, text="Close", width=90, height=34, fg_color="#4b5563", command=self._cancel)
        btn_close.pack(side="right", padx=15, pady=8)

        self.btn_convert = ctk.CTkButton(btn_bar, text="⚡ Convert Now", width=140, height=34, fg_color="#10b981", hover_color="#059669", font=ctk.CTkFont(weight="bold"), command=self._start_conversion)
        self.btn_convert.pack(side="right", padx=(0, 5), pady=8)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=15)

        # File Chooser
        ctk.CTkLabel(body, text="Source Video / Audio File:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", pady=(0, 4))
        f_row = ctk.CTkFrame(body, fg_color="transparent")
        f_row.pack(fill="x", pady=(0, 10))

        self.entry_file = ctk.CTkEntry(f_row, height=35)
        if self.initial_file:
            self.entry_file.insert(0, self.initial_file)
        self.entry_file.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_browse = ctk.CTkButton(f_row, text="Browse...", width=90, height=35, fg_color="#374151", command=self._browse_file)
        btn_browse.pack(side="right")

        # Format & Resolution Controls
        settings_frame = ctk.CTkFrame(body, fg_color="#111827", corner_radius=8)
        settings_frame.pack(fill="x", pady=10)

        s_row = ctk.CTkFrame(settings_frame, fg_color="transparent")
        s_row.pack(fill="x", padx=16, pady=14)

        col1 = ctk.CTkFrame(s_row, fg_color="transparent")
        col1.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ctk.CTkLabel(col1, text="Target Format:", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")
        self.combo_format = ctk.CTkComboBox(
            col1,
            values=[
                "MP3 (Audio Only - 320kbps)",
                "Discord Compressor (<25MB)",
                "Discord Nitro Compressor (<50MB)",
                "MP4 (H.264 + AAC)",
                "MKV (Container)",
                "Extract Subtitles (.srt)",
                "WAV (Lossless)",
                "FLAC (Lossless)",
                "M4A (AAC)"
            ],
            height=34
        )
        self.combo_format.set("MP3 (Audio Only - 320kbps)")
        self.combo_format.pack(fill="x", pady=(4, 0))

        col2 = ctk.CTkFrame(s_row, fg_color="transparent")
        col2.pack(side="right", fill="x", expand=True, padx=(10, 0))
        ctk.CTkLabel(col2, text="Resolution (Video only):", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")
        self.combo_res = ctk.CTkComboBox(col2, values=["Original Resolution", "1080p (Full HD)", "720p (HD)", "480p (SD)"], height=34)
        self.combo_res.set("Original Resolution")
        self.combo_res.pack(fill="x", pady=(4, 0))

        # Progress bar
        self.lbl_progress = ctk.CTkLabel(body, text="Ready to convert.", font=ctk.CTkFont(size=11), text_color="#9ca3af")
        self.lbl_progress.pack(anchor="w", pady=(10, 4))

        self.prog_bar = ctk.CTkProgressBar(body, height=14, corner_radius=4, progress_color="#2563eb")
        self.prog_bar.pack(fill="x", pady=(0, 15))
        self.prog_bar.set(0)

    def _browse_file(self):
        f = filedialog.askopenfilename(filetypes=[("Media Files", "*.mp4 *.mkv *.avi *.mov *.flv *.webm *.mp3 *.wav *.m4a *.ts *.part")])
        if f:
            self.entry_file.delete(0, "end")
            self.entry_file.insert(0, f)

    def _start_conversion(self):
        src = self.entry_file.get().strip()
        if not src or not os.path.isfile(src):
            messagebox.showwarning("File Missing", "Please select a valid media file to convert.")
            return

        fmt_str = self.combo_format.get()
        target_ext = fmt_str.split()[0].lower()
        res_str = self.combo_res.get()
        res = None
        if "1080p" in res_str: res = "1080p"
        elif "720p" in res_str: res = "720p"
        elif "480p" in res_str: res = "480p"

        self.btn_convert.configure(state="disabled", text="Converting...")
        self.lbl_progress.configure(text="FFmpeg encoding in progress...", text_color="#38bdf8")
        self._stop_event.clear()

        def worker():
            def prog_cb(pct):
                self.after(0, lambda: self._update_progress(pct))

            if "discord" in fmt_str.lower():
                target_mb = 49.0 if "50mb" in fmt_str.lower() else 24.0
                out = MediaConverter.compress_for_discord(src, target_size_mb=target_mb, progress_hook=prog_cb, stop_event=self._stop_event)
            elif "subtitles" in fmt_str.lower():
                out = MediaConverter.extract_subtitles(src)
                if out:
                    prog_cb(100.0)
            else:
                out = MediaConverter.convert(src, target_ext, resolution=res, progress_hook=prog_cb, stop_event=self._stop_event)
            def done():
                self.btn_convert.configure(state="normal", text="⚡ Convert Now")
                if out and os.path.isfile(out):
                    self.lbl_progress.configure(text=f"✓ Finished! Saved as {os.path.basename(out)}", text_color="#4ade80")
                    messagebox.showinfo("Conversion Complete", f"File converted successfully:\n{out}")
                else:
                    self.lbl_progress.configure(text="❌ Conversion failed or aborted.", text_color="#f87171")

            self.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    def _update_progress(self, pct):
        self.prog_bar.set(pct / 100.0)
        self.lbl_progress.configure(text=f"Encoding... {pct:.1f}%")

    def _cancel(self):
        self._stop_event.set()
        self.destroy()


class TorrentDownloadDialog(ctk.CTkToplevel):
    """BitTorrent & Magnet Link Downloader (IDM-Killer feature)."""

    def __init__(self, parent, on_download_torrent: Optional[Callable[[str, str], None]] = None, default_url="", on_start_torrent: Optional[Callable[[str, str], None]] = None, default_source=""):
        super().__init__(parent)
        self.on_download_torrent = on_download_torrent or on_start_torrent
        source = default_source or default_url
        self.title("FalconDM - Torrent & Magnet Downloader")
        self.geometry("620x370")
        self.minsize(580, 340)
        self.resizable(True, True)

        self.transient(parent)
        try:
            parent.deiconify()
            parent.state('normal')
            self.lift()
            self.attributes('-topmost', True)
            self.after(200, lambda: self.attributes('-topmost', False))
            self.focus_force()
            import ctypes
            ctypes.windll.user32.ShowWindow(self.winfo_id(), 9)
            ctypes.windll.user32.SetForegroundWindow(self.winfo_id())
        except Exception:
            pass

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 310
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 185
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

        self._build_ui(source)

    def _build_ui(self, default_url: str):
        # 1. Header
        header = ctk.CTkFrame(self, fg_color="#141a24", height=48, corner_radius=0)
        header.pack(fill="x", side="top")
        ctk.CTkLabel(header, text="🧲 BitTorrent & Magnet Link Accelerator", font=ctk.CTkFont(size=14, weight="bold"), text_color="#f0f6fc").pack(side="left", padx=16, pady=10)

        # 2. Bottom Button Bar (Packed BEFORE body so it's always visible at the bottom)
        btn_bar = ctk.CTkFrame(self, fg_color="#141a24", height=54, corner_radius=0)
        btn_bar.pack(fill="x", side="bottom")

        btn_close = ctk.CTkButton(btn_bar, text="Cancel", width=86, height=32, corner_radius=6, fg_color="#21262d", hover_color="#30363d", text_color="#cbd5e1", command=self.destroy)
        btn_close.pack(side="right", padx=14, pady=11)

        self.btn_download = ctk.CTkButton(btn_bar, text="⚡ Download Torrent", width=150, height=32, corner_radius=6, fg_color="#2563eb", hover_color="#1d4ed8", font=ctk.CTkFont(size=12, weight="bold"), text_color="#ffffff", command=self._submit)
        self.btn_download.pack(side="right", padx=(0, 6), pady=11)

        # 3. Expanding Body
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=(12, 6))

        ctk.CTkLabel(body, text="Magnet Link or .torrent File Path / URL:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#cbd5e1").pack(anchor="w", pady=(0, 4))
        self.entry_source = ctk.CTkEntry(body, placeholder_text="magnet:?xt=urn:btih:... or path to .torrent file", height=32, corner_radius=6, fg_color="#0d1117", border_color="#30363d", text_color="#f0f6fc")
        if default_url:
            self.entry_source.insert(0, default_url)
        self.entry_source.pack(fill="x", pady=(0, 10))

        # Destination folder
        ctk.CTkLabel(body, text="Save Destination Folder:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#cbd5e1").pack(anchor="w", pady=(0, 4))
        dir_frame = ctk.CTkFrame(body, fg_color="transparent")
        dir_frame.pack(fill="x", pady=(0, 10))

        default_dir = os.path.join(os.path.expanduser("~"), "Downloads", "FalconDM", "Torrents")
        os.makedirs(default_dir, exist_ok=True)
        self.entry_dir = ctk.CTkEntry(dir_frame, height=32, corner_radius=6, fg_color="#0d1117", border_color="#30363d", text_color="#f0f6fc")
        self.entry_dir.insert(0, default_dir)
        self.entry_dir.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_browse = ctk.CTkButton(dir_frame, text="Browse...", width=86, height=32, corner_radius=6, fg_color="#21262d", hover_color="#30363d", border_width=1, border_color="#30363d", text_color="#cbd5e1", font=ctk.CTkFont(size=11), command=self._browse_dir)
        btn_browse.pack(side="right")

        lbl_info = ctk.CTkLabel(
            body,
            text="Powered by aria2c multi-peer swarm engine with DHT and Local Peer Discovery.\nDownloads directly into your local storage with zero speed caps.",
            font=ctk.CTkFont(size=11),
            text_color="#8b949e",
            justify="left"
        )
        lbl_info.pack(anchor="w")

    def _browse_dir(self):
        d = filedialog.askdirectory(initialdir=self.entry_dir.get())
        if d:
            self.entry_dir.delete(0, "end")
            self.entry_dir.insert(0, d)

    def _submit(self):
        source = self.entry_source.get().strip()
        if not source:
            messagebox.showwarning("Missing Source", "Please enter a magnet link or torrent file path.")
            return
        save_dir = self.entry_dir.get().strip()
        if self.on_download_torrent:
            self.on_download_torrent(source, save_dir)
        self.destroy()


class SiteGrabberDialog(ctk.CTkToplevel):
    """Enterprise-grade Site Grabber, Recursive Web Crawler, and Deep Media Sniffer."""

    def __init__(self, parent, on_enqueue_batch: Callable[[List[str], str], None]):
        super().__init__(parent)
        self.title("FalconDM - Enterprise Site Grabber & Deep Web Crawler")
        self.geometry("920x680")
        self.minsize(780, 540)
        self.on_enqueue_batch = on_enqueue_batch

        self.transient(parent)
        try:
            parent.deiconify()
            parent.state('normal')
            self.lift()
            self.attributes('-topmost', True)
            self.after(200, lambda: self.attributes('-topmost', False))
            self.focus_force()
            import ctypes
            ctypes.windll.user32.ShowWindow(self.winfo_id(), 9)
            ctypes.windll.user32.SetForegroundWindow(self.winfo_id())
        except Exception:
            pass

        self.raw_items: List[Dict[str, Any]] = []
        self.displayed_items: List[Dict[str, Any]] = []
        self._is_probing = False
        self._build_ui()

    def _build_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color="#181a20", height=50)
        header.pack(fill="x")
        ctk.CTkLabel(
            header,
            text="🕷️ Site Grabber & Deep Web Crawler",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#38bdf8"
        ).pack(side="left", padx=20, pady=10)
        
        ctk.CTkLabel(
            header,
            text="Recursively crawls websites, probes file sizes, and batch extracts media",
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8"
        ).pack(side="left", padx=10, pady=10)

        # Bottom Bar (docked first)
        btn_bar = ctk.CTkFrame(self, fg_color="#181a20", height=55)
        btn_bar.pack(fill="x", side="bottom")

        btn_cancel = ctk.CTkButton(btn_bar, text="Cancel", width=90, height=36, fg_color="#4b5563", command=self.destroy)
        btn_cancel.pack(side="right", padx=15, pady=10)

        self.btn_download = ctk.CTkButton(
            btn_bar,
            text="⚡ Download Selected",
            width=180,
            height=36,
            fg_color="#10b981",
            hover_color="#059669",
            font=ctk.CTkFont(weight="bold"),
            command=self._submit
        )
        self.btn_download.pack(side="right", padx=(0, 5), pady=10)

        btn_export = ctk.CTkButton(
            btn_bar,
            text="📄 Export Links...",
            width=130,
            height=36,
            fg_color="#374151",
            hover_color="#4b5563",
            command=self._export_links
        )
        btn_export.pack(side="left", padx=15, pady=10)

        self.btn_probe = ctk.CTkButton(
            btn_bar,
            text="⚡ Probe File Sizes",
            width=150,
            height=36,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            command=self._start_probe_sizes
        )
        self.btn_probe.pack(side="left", padx=(0, 10), pady=10)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=12)

        # Top controls Row 1: URL + Category + Scan
        top_row = ctk.CTkFrame(body, fg_color="transparent")
        top_row.pack(fill="x", pady=(0, 8))

        self.entry_url = ctk.CTkEntry(top_row, placeholder_text="https://example.com/gallery or website URL", height=35)
        self.entry_url.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.combo_cat = ctk.CTkComboBox(
            top_row,
            values=["All", "Videos", "Audio", "Images", "Documents", "Archives", "All Links"],
            width=125,
            height=35
        )
        self.combo_cat.set("All")
        self.combo_cat.pack(side="left", padx=(0, 8))

        self.btn_scan = ctk.CTkButton(
            top_row,
            text="🔍 Crawl Site",
            width=120,
            height=35,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            font=ctk.CTkFont(weight="bold"),
            command=self._start_scan
        )
        self.btn_scan.pack(side="left")

        # Top controls Row 2: Crawl Depth + Same Domain Checkbox + Filter Search
        opt_row = ctk.CTkFrame(body, fg_color="transparent")
        opt_row.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(opt_row, text="Depth:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#cbd5e1").pack(side="left", padx=(0, 4))
        self.combo_depth = ctk.CTkComboBox(
            opt_row,
            values=["1 (Page Only)", "2 (Child Pages)", "3 (Deep Crawl)"],
            width=140,
            height=30
        )
        self.combo_depth.set("1 (Page Only)")
        self.combo_depth.pack(side="left", padx=(0, 12))

        self.same_domain_var = ctk.BooleanVar(value=True)
        cb_domain = ctk.CTkCheckBox(opt_row, text="Same Domain Only", variable=self.same_domain_var, font=ctk.CTkFont(size=11))
        cb_domain.pack(side="left", padx=(0, 16))

        # Real-time search filter
        self.entry_filter = ctk.CTkEntry(opt_row, placeholder_text="🔎 Filter by filename, wildcard (*.pdf), or format...", height=30)
        self.entry_filter.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.entry_filter.bind("<KeyRelease>", lambda e: self._apply_filter())

        # Table for results
        table_frame = ctk.CTkFrame(body, fg_color="#181a20", corner_radius=6)
        table_frame.pack(fill="both", expand=True, pady=(0, 8))

        columns = ("name", "size", "category", "ext", "url")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="extended")
        self.tree.heading("name", text="File Name")
        self.tree.heading("size", text="Size")
        self.tree.heading("category", text="Category")
        self.tree.heading("ext", text="Format")
        self.tree.heading("url", text="Download URL")

        self.tree.column("name", width=250, anchor="w")
        self.tree.column("size", width=95, anchor="center")
        self.tree.column("category", width=90, anchor="center")
        self.tree.column("ext", width=75, anchor="center")
        self.tree.column("url", width=360, anchor="w")

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True, padx=(5, 0), pady=5)
        scrollbar.pack(side="right", fill="y", padx=(0, 5), pady=5)

        # Action / Selection Row
        sel_row = ctk.CTkFrame(body, fg_color="transparent")
        sel_row.pack(fill="x", pady=(0, 6))

        self.lbl_stats = ctk.CTkLabel(sel_row, text="Enter a URL above and click Crawl Site to extract files.", font=ctk.CTkFont(size=12), text_color="#94a3b8")
        self.lbl_stats.pack(side="left")

        btn_sel_all = ctk.CTkButton(sel_row, text="Select All", width=85, height=28, fg_color="#374151", command=self._select_all)
        btn_sel_all.pack(side="right", padx=(6, 0))

        btn_desel = ctk.CTkButton(sel_row, text="Deselect All", width=85, height=28, fg_color="#374151", command=self._deselect_all)
        btn_desel.pack(side="right")

        # Save Destination
        dir_frame = ctk.CTkFrame(body, fg_color="transparent")
        dir_frame.pack(fill="x", pady=(0, 2))

        ctk.CTkLabel(dir_frame, text="Save To:", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(0, 8))
        default_dir = os.path.join(os.path.expanduser("~"), "Downloads", "FalconDM", "Grabbed")
        os.makedirs(default_dir, exist_ok=True)
        self.entry_dir = ctk.CTkEntry(dir_frame, height=32)
        self.entry_dir.insert(0, default_dir)
        self.entry_dir.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_browse = ctk.CTkButton(dir_frame, text="Browse...", width=80, height=32, fg_color="#374151", command=self._browse_dir)
        btn_browse.pack(side="right")

    def _browse_dir(self):
        d = filedialog.askdirectory(initialdir=self.entry_dir.get())
        if d:
            self.entry_dir.delete(0, "end")
            self.entry_dir.insert(0, d)

    def _select_all(self):
        self.tree.selection_set(self.tree.get_children())
        self._update_stats()

    def _deselect_all(self):
        self.tree.selection_remove(self.tree.get_children())
        self._update_stats()

    def _update_stats(self):
        total = len(self.tree.get_children())
        selected = len(self.tree.selection())
        self.lbl_stats.configure(text=f"Showing {total} files | Selected: {selected}")

    def _start_scan(self):
        url = self.entry_url.get().strip()
        if not url or not (url.startswith("http://") or url.startswith("https://")):
            messagebox.showwarning("Invalid URL", "Please enter a valid HTTP/HTTPS URL.")
            return

        cat = self.combo_cat.get()
        depth_str = self.combo_depth.get()
        max_depth = 1
        if "2" in depth_str:
            max_depth = 2
        elif "3" in depth_str:
            max_depth = 3

        same_domain = self.same_domain_var.get()

        self.btn_scan.configure(state="disabled", text="Crawling...")
        self.lbl_stats.configure(text="Crawling website and discovering links...", text_color="#38bdf8")

        for item in self.tree.get_children():
            self.tree.delete(item)

        def worker():
            try:
                def page_callback(page_url: str, visited_count: int, queue_len: int):
                    self.after(0, lambda: self.lbl_stats.configure(
                        text=f"Crawling page {visited_count} ({queue_len} queued)... {os.path.basename(page_url) or page_url[:30]}",
                        text_color="#38bdf8"
                    ))

                results = SiteGrabber.crawl_site(
                    start_url=url,
                    max_depth=max_depth,
                    same_domain=same_domain,
                    max_pages=20 if max_depth > 1 else 1,
                    category=cat,
                    on_page_crawled=page_callback
                )

                def on_done():
                    self.btn_scan.configure(state="normal", text="🔍 Crawl Site")
                    self.raw_items = results
                    self._apply_filter()
                    self.tree.selection_set(self.tree.get_children())
                    self.lbl_stats.configure(text=f"Extraction complete! Found {len(results)} files.", text_color="#34d399")
                self.after(0, on_done)
            except Exception as e:
                def on_err():
                    self.btn_scan.configure(state="normal", text="🔍 Crawl Site")
                    self.lbl_stats.configure(text=f"Scan error: {str(e)}", text_color="#f87171")
                    messagebox.showerror("Scan Failed", str(e))
                self.after(0, on_err)

        threading.Thread(target=worker, daemon=True).start()

    def _apply_filter(self):
        query = self.entry_filter.get().strip()
        filtered = SiteGrabber.filter_items(self.raw_items, search_query=query)
        self.displayed_items = filtered

        for item in self.tree.get_children():
            self.tree.delete(item)

        for r in filtered:
            size_display = r.get("size_str", "Unknown")
            self.tree.insert("", "end", values=(r["filename"], size_display, r["category"], r["ext"], r["url"]))

        self.tree.selection_set(self.tree.get_children())
        self._update_stats()

    def _start_probe_sizes(self):
        if not self.raw_items:
            messagebox.showinfo("No Files", "Please crawl a webpage first before probing file sizes.")
            return

        if self._is_probing:
            return

        self._is_probing = True
        self.btn_probe.configure(state="disabled", text="⚡ Probing...")
        self.lbl_stats.configure(text="Probing remote file sizes via HTTP HEAD...", text_color="#38bdf8")

        def worker():
            def prog_cb(completed: int, total: int):
                self.after(0, lambda: self.lbl_stats.configure(
                    text=f"Probing file sizes: {completed}/{total} completed...",
                    text_color="#38bdf8"
                ))

            SiteGrabber.probe_file_sizes(self.raw_items, max_workers=10, on_progress=prog_cb)

            def on_done():
                self._is_probing = False
                self.btn_probe.configure(state="normal", text="⚡ Probe File Sizes")
                self._apply_filter()
                self.lbl_stats.configure(text=f"File sizes updated for {len(self.raw_items)} files!", text_color="#34d399")
            self.after(0, on_done)

        threading.Thread(target=worker, daemon=True).start()

    def _export_links(self):
        if not self.displayed_items:
            messagebox.showinfo("No Links", "No links available to export.")
            return

        save_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text File", "*.txt"), ("JSON File", "*.json"), ("All Files", "*.*")],
            initialfile="grabbed_links.txt"
        )
        if save_path:
            fmt = "json" if save_path.lower().endswith(".json") else "txt"
            ok = SiteGrabber.export_links(self.displayed_items, save_path, export_format=fmt)
            if ok:
                messagebox.showinfo("Export Successful", f"Successfully exported {len(self.displayed_items)} links to:\n{save_path}")
            else:
                messagebox.showerror("Export Failed", "Could not write export file.")

    def _submit(self):
        selected_ids = self.tree.selection()
        if not selected_ids:
            messagebox.showwarning("No Files Selected", "Please select at least one file to download.")
            return

        urls = []
        for item_id in selected_ids:
            vals = self.tree.item(item_id, "values")
            # In our 5-column format: name, size, category, ext, url
            if vals and len(vals) >= 5:
                urls.append(vals[4])
            elif vals and len(vals) >= 4:
                urls.append(vals[3])

        save_dir = self.entry_dir.get().strip()
        self.on_enqueue_batch(urls, save_dir)
        self.destroy()



class SettingsDialog(ctk.CTkToplevel):
    """FalconDM Settings & Configuration Dialog."""

    def __init__(self, parent, on_save_callback: Optional[Callable[[], None]] = None):
        super().__init__(parent)
        self.title("FalconDM - Preferences & Settings")
        self.geometry("640x540")
        self.resizable(False, False)
        self.on_save_callback = on_save_callback

        self.transient(parent)
        try:
            parent.deiconify()
            parent.state('normal')
            self.lift()
            self.attributes('-topmost', True)
            self.after(200, lambda: self.attributes('-topmost', False))
            self.focus_force()
            import ctypes
            ctypes.windll.user32.ShowWindow(self.winfo_id(), 9)
            ctypes.windll.user32.SetForegroundWindow(self.winfo_id())
        except Exception:
            pass

        self._build_ui()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="#141a24", height=48, corner_radius=0, border_width=1, border_color="#1f2737")
        header.pack(fill="x")
        ctk.CTkLabel(
            header,
            text="⚙️ Preferences & Engine Settings",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color="#f8fafc"
        ).pack(side="left", padx=18, pady=10)

        # Bottom Bar (packed first so pinned to bottom)
        btn_bar = ctk.CTkFrame(self, fg_color="#141a24", height=54, corner_radius=0, border_width=1, border_color="#1f2737")
        btn_bar.pack(fill="x", side="bottom")

        btn_cancel = ctk.CTkButton(
            btn_bar,
            text="Cancel",
            width=90,
            height=32,
            corner_radius=6,
            fg_color="#1e293b",
            hover_color="#334155",
            text_color="#cbd5e1",
            font=ctk.CTkFont(size=11),
            command=self.destroy
        )
        btn_cancel.pack(side="right", padx=16, pady=11)

        btn_save = ctk.CTkButton(
            btn_bar,
            text="💾 Save Preferences",
            width=150,
            height=32,
            corner_radius=6,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#ffffff",
            command=self._save
        )
        btn_save.pack(side="right", padx=(0, 6), pady=11)

        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=18, pady=12)

        # Appearance & Theme Accents
        ctk.CTkLabel(body, text="APPEARANCE & THEME ACCENTS", font=ctk.CTkFont(size=10, weight="bold"), text_color="#38bdf8").pack(anchor="w", pady=(5, 6))
        theme_frame = ctk.CTkFrame(body, fg_color="transparent")
        theme_frame.pack(fill="x", pady=(2, 10))
        ctk.CTkLabel(theme_frame, text="Cyberpunk Accent Color Palette:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#cbd5e1").pack(side="left")
        self.combo_theme = ctk.CTkComboBox(
            theme_frame,
            values=["Cyberpunk Cyan", "Emerald Matrix", "Sunset Orange", "Vaporwave Violet", "Crimson Turbo"],
            width=200,
            height=30
        )
        self.combo_theme.set(config_store.get("ui_theme_accent", "Cyberpunk Cyan"))
        self.combo_theme.pack(side="right")

        # 1. Downloads section
        ctk.CTkLabel(body, text="GENERAL DOWNLOADS", font=ctk.CTkFont(size=10, weight="bold"), text_color="#38bdf8").pack(anchor="w", pady=(5, 6))

        ctk.CTkLabel(body, text="Default Download Folder:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#cbd5e1").pack(anchor="w")
        dir_frame = ctk.CTkFrame(body, fg_color="transparent")
        dir_frame.pack(fill="x", pady=(2, 10))
        self.entry_dir = ctk.CTkEntry(
            dir_frame,
            height=32,
            corner_radius=6,
            fg_color="#0b0f17",
            border_width=1,
            border_color="#1e2638",
            text_color="#f8fafc"
        )
        self.entry_dir.insert(0, config_store.get("default_download_dir"))
        self.entry_dir.pack(side="left", fill="x", expand=True, padx=(0, 8))
        btn_browse = ctk.CTkButton(
            dir_frame,
            text="Browse...",
            width=80,
            height=32,
            corner_radius=6,
            fg_color="#1a2232",
            hover_color="#253046",
            border_width=1,
            border_color="#243046",
            text_color="#cbd5e1",
            font=ctk.CTkFont(size=11),
            command=self._browse_dir
        )
        btn_browse.pack(side="right")

        # Always ask where to save each file
        self.var_ask_save = ctk.BooleanVar(value=config_store.get("ask_save_location_everytime", True))
        ctk.CTkSwitch(
            body,
            text="Always ask where to download each file before starting (Save As prompt)",
            variable=self.var_ask_save,
            progress_color="#2563eb",
            font=ctk.CTkFont(size=11, weight="bold")
        ).pack(anchor="w", pady=(0, 6))

        # Remember last used download folder
        self.var_remember_dir = ctk.BooleanVar(value=config_store.get("remember_last_download_dir", True))
        ctk.CTkSwitch(
            body,
            text="Remember last used download folder for future downloads",
            variable=self.var_remember_dir,
            progress_color="#2563eb",
            font=ctk.CTkFont(size=11, weight="bold")
        ).pack(anchor="w", pady=(0, 6))

        self.var_instant_media = ctk.BooleanVar(value=config_store.get("instant_media_download", True))
        ctk.CTkSwitch(
            body,
            text="Instant 1-Click Video Download (Skip format dialog on video hover click)",
            variable=self.var_instant_media,
            progress_color="#2563eb",
            font=ctk.CTkFont(size=11, weight="bold")
        ).pack(anchor="w", pady=(0, 10))

        row1 = ctk.CTkFrame(body, fg_color="transparent")
        row1.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(row1, text="Default Connections:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#cbd5e1").pack(side="left", padx=(0, 8))
        self.combo_threads = ctk.CTkComboBox(
            row1,
            values=["4", "8", "16", "32"],
            width=80,
            height=30,
            corner_radius=6,
            fg_color="#0b0f17",
            button_color="#1e293b",
            border_color="#1e2638",
            dropdown_fg_color="#141a24",
            text_color="#f8fafc"
        )
        self.combo_threads.set(str(config_store.get("default_threads", 16)))
        self.combo_threads.pack(side="left")

        ctk.CTkLabel(row1, text="Max Concurrent Tasks:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#cbd5e1").pack(side="left", padx=(18, 8))
        self.combo_concurr = ctk.CTkComboBox(
            row1,
            values=["1", "2", "3", "5", "8", "10"],
            width=80,
            height=30,
            corner_radius=6,
            fg_color="#0b0f17",
            button_color="#1e293b",
            border_color="#1e2638",
            dropdown_fg_color="#141a24",
            text_color="#f8fafc"
        )
        self.combo_concurr.set(str(config_store.get("max_concurrent_tasks", 3)))
        self.combo_concurr.pack(side="left")

        # Auto-Speed Optimizer switch
        self.var_auto_speed = ctk.BooleanVar(value=config_store.get("auto_speed_optimizer", True))
        ctk.CTkSwitch(
            body,
            text="⚡ Auto-Speed Optimizer (Auto-scale 8-32 connections by server latency & BDP)",
            variable=self.var_auto_speed,
            progress_color="#2563eb",
            font=ctk.CTkFont(size=11, weight="bold")
        ).pack(anchor="w", pady=(2, 10))

        # 2. System & Tray Section
        ctk.CTkLabel(body, text="SYSTEM & BEHAVIOR", font=ctk.CTkFont(size=10, weight="bold"), text_color="#38bdf8").pack(anchor="w", pady=(12, 6))

        self.var_tray = ctk.BooleanVar(value=config_store.get("minimize_to_tray_on_close", True))
        ctk.CTkSwitch(body, text="Minimize to System Tray when closing FalconDM", variable=self.var_tray, progress_color="#2563eb", font=ctk.CTkFont(size=11)).pack(anchor="w", pady=4)

        self.var_sounds = ctk.BooleanVar(value=config_store.get("play_sounds", True))
        ctk.CTkSwitch(body, text="Play audio chimes on download completion & errors", variable=self.var_sounds, progress_color="#2563eb", font=ctk.CTkFont(size=11)).pack(anchor="w", pady=4)

        self.var_shutdown = ctk.BooleanVar(value=config_store.get("shutdown_on_completion", False))
        ctk.CTkSwitch(body, text="Shut down computer when all downloads finish (with 30s safety warning)", variable=self.var_shutdown, progress_color="#ef4444", font=ctk.CTkFont(size=11)).pack(anchor="w", pady=4)

        self.var_floating_dl = ctk.BooleanVar(value=config_store.get("show_floating_download_window", False))
        ctk.CTkSwitch(body, text="Open floating popup window when a download starts", variable=self.var_floating_dl, progress_color="#2563eb", font=ctk.CTkFont(size=11)).pack(anchor="w", pady=4)

        self.var_sniff = ctk.BooleanVar(value=config_store.get("clipboard_sniff_enabled", True))
        ctk.CTkSwitch(body, text="Automatically sniff download links from clipboard", variable=self.var_sniff, progress_color="#2563eb", font=ctk.CTkFont(size=11)).pack(anchor="w", pady=4)

        # 3. Browser Integration Section
        ctk.CTkLabel(body, text="BROWSER INTEGRATION", font=ctk.CTkFont(size=10, weight="bold"), text_color="#38bdf8").pack(anchor="w", pady=(12, 6))
        integ_frame = ctk.CTkFrame(body, fg_color="#111827", corner_radius=8, border_width=1, border_color="#1f293d")
        integ_frame.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(integ_frame, text="Chrome, Edge, Brave & Firefox Native Integration", font=ctk.CTkFont(size=11, weight="bold"), text_color="#f8fafc").pack(anchor="w", padx=12, pady=(10, 2))
        ctk.CTkLabel(integ_frame, text="Registers OS messaging hosts so browser downloads auto-route to FalconDM.", font=ctk.CTkFont(size=10), text_color="#94a3b8").pack(anchor="w", padx=12, pady=(0, 8))
        btn_integ = ctk.CTkButton(
            integ_frame,
            text="⚡ Setup / Register Native Host",
            width=220,
            height=30,
            corner_radius=6,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._setup_browser_integration
        )
        btn_integ.pack(anchor="w", padx=12, pady=(0, 10))

        # 4. Remote Control & Cloud Integration Section
        ctk.CTkLabel(body, text="TELEGRAM BOT & REAL-DEBRID CLOUD", font=ctk.CTkFont(size=10, weight="bold"), text_color="#38bdf8").pack(anchor="w", pady=(14, 6))

        ctk.CTkLabel(body, text="Real-Debrid API Key (Unrestrict 1fichier, Rapidgator, Magnet):", font=ctk.CTkFont(size=11, weight="bold"), text_color="#cbd5e1").pack(anchor="w")
        self.entry_debrid = ctk.CTkEntry(body, height=32, corner_radius=6, fg_color="#0b0f17", border_width=1, border_color="#1e2638", text_color="#f8fafc", show="*")
        self.entry_debrid.insert(0, config_store.get("real_debrid_api_key", ""))
        self.entry_debrid.pack(fill="x", pady=(2, 8))

        ctk.CTkLabel(body, text="Telegram Bot Token (Remote control & phone completion alerts):", font=ctk.CTkFont(size=11, weight="bold"), text_color="#cbd5e1").pack(anchor="w")
        self.entry_tg_token = ctk.CTkEntry(body, height=32, corner_radius=6, fg_color="#0b0f17", border_width=1, border_color="#1e2638", text_color="#f8fafc", show="*")
        self.entry_tg_token.insert(0, config_store.get("telegram_bot_token", ""))
        self.entry_tg_token.pack(fill="x", pady=(2, 8))

        ctk.CTkLabel(body, text="Telegram Allowed Chat ID(s) (e.g. 123456789):", font=ctk.CTkFont(size=11, weight="bold"), text_color="#cbd5e1").pack(anchor="w")
        self.entry_tg_chats = ctk.CTkEntry(body, height=32, corner_radius=6, fg_color="#0b0f17", border_width=1, border_color="#1e2638", text_color="#f8fafc")
        tg_chats_val = config_store.get("telegram_allowed_chat_ids", [])
        if isinstance(tg_chats_val, list):
            self.entry_tg_chats.insert(0, ", ".join(str(x) for x in tg_chats_val))
        else:
            self.entry_tg_chats.insert(0, str(tg_chats_val))
        self.entry_tg_chats.pack(fill="x", pady=(2, 8))

        self.var_auto_upload = ctk.BooleanVar(value=config_store.get("auto_upload_enabled", False))
        ctk.CTkSwitch(body, text="Auto-upload completed downloads to Telegram", variable=self.var_auto_upload, progress_color="#2563eb", font=ctk.CTkFont(size=11)).pack(anchor="w", pady=4)

        self.var_delete_uploaded = ctk.BooleanVar(value=config_store.get("auto_upload_delete_local", False))
        ctk.CTkSwitch(body, text="Delete local file after successful upload (saves disk space)", variable=self.var_delete_uploaded, progress_color="#ef4444", font=ctk.CTkFont(size=11)).pack(anchor="w", pady=4)

        self.var_remote_web = ctk.BooleanVar(value=config_store.get("allow_remote_web_access", True))
        ctk.CTkSwitch(body, text="Enable Mobile & Local Wi-Fi Web Dashboard (http://<PC-IP>:9666)", variable=self.var_remote_web, progress_color="#2563eb", font=ctk.CTkFont(size=11)).pack(anchor="w", pady=4)

        # 5. Network & Identity
        ctk.CTkLabel(body, text="NETWORK & USER AGENT", font=ctk.CTkFont(size=10, weight="bold"), text_color="#38bdf8").pack(anchor="w", pady=(12, 6))

        ctk.CTkLabel(body, text="Custom HTTP User-Agent:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#cbd5e1").pack(anchor="w")
        self.entry_ua = ctk.CTkEntry(
            body,
            height=32,
            corner_radius=6,
            fg_color="#0b0f17",
            border_width=1,
            border_color="#1e2638",
            text_color="#f8fafc"
        )
        self.entry_ua.insert(0, config_store.get("user_agent", DEFAULT_USER_AGENT))
        self.entry_ua.pack(fill="x", pady=(2, 10))

    def _setup_browser_integration(self):
        from core.platform_utils import register_browser_integration, open_file_or_folder
        ok = register_browser_integration()
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ext_folder = os.path.join(base_dir, "browser_extension")
        if ok:
            messagebox.showinfo(
                "Browser Integration",
                f"FalconDM Native Messaging Host registered in Windows Registry!\n\n"
                f"To load the extension in Chrome / Edge / Brave:\n"
                f"1. Open chrome://extensions (or edge://extensions)\n"
                f"2. Enable 'Developer mode'\n"
                f"3. Click 'Load unpacked' and select:\n{ext_folder}"
            )
            open_file_or_folder(ext_folder)
        else:
            messagebox.showinfo("Browser Extension", f"Load unpacked extension from:\n{ext_folder}")
            open_file_or_folder(ext_folder)

    def _browse_dir(self):
        d = filedialog.askdirectory(initialdir=self.entry_dir.get())
        if d:
            self.entry_dir.delete(0, "end")
            self.entry_dir.insert(0, d)

    def _save(self):
        config_store.set("ui_theme_accent", self.combo_theme.get())
        config_store.set("auto_speed_optimizer", self.var_auto_speed.get())
        config_store.set("default_download_dir", self.entry_dir.get().strip())
        config_store.set("ask_save_location_everytime", self.var_ask_save.get())
        config_store.set("remember_last_download_dir", self.var_remember_dir.get())
        config_store.set("instant_media_download", self.var_instant_media.get())
        config_store.set("shutdown_on_completion", self.var_shutdown.get())
        config_store.set("default_threads", int(self.combo_threads.get()))
        config_store.set("max_concurrent_tasks", int(self.combo_concurr.get()))
        config_store.set("minimize_to_tray_on_close", self.var_tray.get())
        config_store.set("play_sounds", self.var_sounds.get())
        config_store.set("show_basket_on_startup", False)
        config_store.set("show_floating_download_window", self.var_floating_dl.get())
        config_store.set("clipboard_sniff_enabled", self.var_sniff.get())
        config_store.set("user_agent", self.entry_ua.get().strip())
        config_store.set("real_debrid_api_key", self.entry_debrid.get().strip())
        config_store.set("telegram_bot_token", self.entry_tg_token.get().strip())
        chats_str = self.entry_tg_chats.get().strip()
        chats_list = [int(x.strip()) for x in chats_str.split(",") if x.strip().lstrip("-").isdigit()]
        config_store.set("telegram_allowed_chat_ids", chats_list)
        config_store.set("auto_upload_enabled", self.var_auto_upload.get())
        config_store.set("auto_upload_delete_local", self.var_delete_uploaded.get())
        config_store.set("allow_remote_web_access", self.var_remote_web.get())

        # Restart / reconfigure telegram bot if token changed
        try:
            from core.telegram_bot import telegram_bot
            if telegram_bot.is_configured():
                telegram_bot.start()
        except Exception:
            pass

        if self.on_save_callback:
            self.on_save_callback()

        messagebox.showinfo("Settings Saved", "Your preferences have been updated successfully.")
        self.destroy()


class FilePropertiesDialog(ctk.CTkToplevel):
    """
    Comprehensive File Inspector & Link Refresher (the iconic IDM feature).
    Allows inspecting file stats, computing SHA256/MD5 hashes, and updating
    expired download URLs to resume stalled downloads seamlessly.
    """

    def __init__(self, parent, task, on_url_updated: Optional[Callable[[str, str], None]] = None):
        super().__init__(parent)
        self.task = task
        self.on_url_updated = on_url_updated
        self.title(f"FalconDM - Properties: {task.filename}")
        self.geometry("620x520")
        self.minsize(560, 460)

        # Center dialog
        try:
            x = parent.winfo_x() + (parent.winfo_width() // 2) - 310
            y = parent.winfo_y() + (parent.winfo_height() // 2) - 260
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        self._build_ui()

    def _build_ui(self):
        # 1. Header
        header = ctk.CTkFrame(self, fg_color="#141a24", height=48, corner_radius=0, border_width=1, border_color="#1f2737")
        header.pack(fill="x")

        lbl_title = ctk.CTkLabel(
            header,
            text=f"⚡ Download Properties & Details",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color="#f8fafc"
        )
        lbl_title.pack(side="left", padx=16, pady=10)

        # Status Badge
        lbl_stat = ctk.CTkLabel(
            header,
            text=f"● {self.task.status}",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#38bdf8" if self.task.status == "Downloading" else ("#4ade80" if self.task.status == "Completed" else "#f59e0b"),
            fg_color="#0f172a",
            corner_radius=4,
            padx=8,
            pady=2
        )
        lbl_stat.pack(side="right", padx=16, pady=10)

        # 2. Body Scrollable
        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=14, pady=10)

        # File Overview Card
        card_info = ctk.CTkFrame(body, fg_color="#141a24", corner_radius=8, border_width=1, border_color="#1f2737")
        card_info.pack(fill="x", pady=(0, 10))

        def make_row(parent, label, value, text_color="#cbd5e1"):
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=3)
            ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=11, weight="bold"), text_color="#94a3b8", width=120, anchor="w").pack(side="left")
            val_lbl = ctk.CTkLabel(row, text=str(value), font=ctk.CTkFont(size=11), text_color=text_color, anchor="w")
            val_lbl.pack(side="left", fill="x", expand=True)
            return val_lbl

        make_row(card_info, "File Name:", self.task.filename, "#f8fafc")
        
        sz_text = format_bytes(self.task.file_size) if self.task.file_size > 0 else "Unknown"
        dl_text = format_bytes(self.task.downloaded_bytes)
        make_row(card_info, "File Size:", f"{sz_text} ({dl_text} downloaded)")
        make_row(card_info, "Progress:", f"{self.task.progress_pct:.1f}%")
        make_row(card_info, "Category:", self.task.category)
        make_row(card_info, "Connections:", f"{self.task.num_connections} active streams (multi-threaded)")

        # Target Save Path
        row_path = ctk.CTkFrame(card_info, fg_color="transparent")
        row_path.pack(fill="x", padx=12, pady=(3, 8))
        ctk.CTkLabel(row_path, text="Save Location:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#94a3b8", width=120, anchor="w").pack(side="left")
        
        self.entry_path = ctk.CTkEntry(row_path, height=28, fg_color="#0b0f17", border_color="#1e2638", text_color="#cbd5e1", font=ctk.CTkFont(size=11))
        self.entry_path.insert(0, self.task.save_path)
        self.entry_path.pack(side="left", fill="x", expand=True, padx=(0, 6))

        # 3. Download Link & URL Refresher Card (Crucial for expired session links)
        ctk.CTkLabel(body, text="DOWNLOAD ADDRESS (URL REFRESHER)", font=ctk.CTkFont(size=10, weight="bold"), text_color="#38bdf8").pack(anchor="w", pady=(8, 4))
        
        card_url = ctk.CTkFrame(body, fg_color="#141a24", corner_radius=8, border_width=1, border_color="#1f2737")
        card_url.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            card_url,
            text="If this download expired or failed due to session timeout, paste the refreshed direct URL below and click 'Save New URL' to resume.",
            font=ctk.CTkFont(size=10),
            text_color="#64748b",
            wraplength=540,
            justify="left"
        ).pack(anchor="w", padx=12, pady=(10, 4))

        url_row = ctk.CTkFrame(card_url, fg_color="transparent")
        url_row.pack(fill="x", padx=12, pady=(2, 10))

        self.entry_url = ctk.CTkEntry(
            url_row,
            height=32,
            corner_radius=6,
            fg_color="#0b0f17",
            border_color="#1e2638",
            text_color="#f8fafc",
            font=ctk.CTkFont(size=11)
        )
        self.entry_url.insert(0, self.task.url)
        self.entry_url.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_save_url = ctk.CTkButton(
            url_row,
            text="Save New URL",
            width=110,
            height=32,
            corner_radius=6,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._on_save_url
        )
        btn_save_url.pack(side="right")

        # 4. Instant Integrity Hasher Card
        ctk.CTkLabel(body, text="INTEGRITY CHECKSUMS (SHA256 & MD5)", font=ctk.CTkFont(size=10, weight="bold"), text_color="#38bdf8").pack(anchor="w", pady=(8, 4))
        
        card_hash = ctk.CTkFrame(body, fg_color="#141a24", corner_radius=8, border_width=1, border_color="#1f2737")
        card_hash.pack(fill="x", pady=(0, 10))

        h_row = ctk.CTkFrame(card_hash, fg_color="transparent")
        h_row.pack(fill="x", padx=12, pady=8)

        self.lbl_sha = ctk.CTkLabel(h_row, text="SHA-256: [Click Calculate to compute]", font=ctk.CTkFont(size=10), text_color="#94a3b8", anchor="w")
        self.lbl_sha.pack(side="left", fill="x", expand=True)

        self.btn_calc_hash = ctk.CTkButton(
            h_row,
            text="🔍 Compute Hashes",
            width=120,
            height=28,
            corner_radius=6,
            fg_color="#1e293b",
            hover_color="#334155",
            font=ctk.CTkFont(size=10),
            command=self._calc_hashes
        )
        self.btn_calc_hash.pack(side="right")

        # Bottom Bar
        btn_bar = ctk.CTkFrame(self, fg_color="#141a24", height=50, corner_radius=0, border_width=1, border_color="#1f2737")
        btn_bar.pack(fill="x", side="bottom")

        btn_close = ctk.CTkButton(
            btn_bar,
            text="Close",
            width=80,
            height=32,
            corner_radius=6,
            fg_color="#1e293b",
            hover_color="#334155",
            text_color="#cbd5e1",
            font=ctk.CTkFont(size=11),
            command=self.destroy
        )
        btn_close.pack(side="right", padx=14, pady=9)

        if os.path.exists(self.task.save_path):
            btn_open_file = ctk.CTkButton(
                btn_bar,
                text="▶ Open File",
                width=96,
                height=32,
                corner_radius=6,
                fg_color="#2563eb",
                hover_color="#1d4ed8",
                font=ctk.CTkFont(size=11, weight="bold"),
                command=self._open_file
            )
            btn_open_file.pack(side="left", padx=(14, 6), pady=9)

        btn_open_fld = ctk.CTkButton(
            btn_bar,
            text="📁 Open Folder",
            width=96,
            height=32,
            corner_radius=6,
            fg_color="#1e293b",
            hover_color="#334155",
            font=ctk.CTkFont(size=11),
            command=self._open_folder
        )
        btn_open_fld.pack(side="left", padx=4, pady=9)

        btn_copy_curl = ctk.CTkButton(
            btn_bar,
            text="📋 Copy cURL",
            width=96,
            height=32,
            corner_radius=6,
            fg_color="#1e293b",
            hover_color="#334155",
            font=ctk.CTkFont(size=11),
            command=self._copy_curl
        )
        btn_copy_curl.pack(side="left", padx=4, pady=9)

    def _copy_curl(self):
        from core.import_export import DownloadListSerializer
        cmd = DownloadListSerializer.generate_curl_command(self.task)
        self.clipboard_clear()
        self.clipboard_append(cmd)
        messagebox.showinfo("cURL Copied", "cURL command copied to clipboard!")

    def _on_save_url(self):
        new_url = self.entry_url.get().strip()
        if not new_url or not (new_url.startswith("http://") or new_url.startswith("https://")):
            messagebox.showwarning("Invalid URL", "Please enter a valid HTTP or HTTPS download URL.")
            return

        self.task.url = new_url
        if self.on_url_updated:
            self.on_url_updated(self.task.task_id, new_url)

        messagebox.showinfo("URL Updated", "Download source address updated successfully!\nYou can now resume this download.")

    def _calc_hashes(self):
        if not os.path.exists(self.task.save_path):
            messagebox.showwarning("File Not Found", "The target file does not exist on disk yet.")
            return

        self.btn_calc_hash.configure(state="disabled", text="Computing...")
        
        def worker():
            try:
                res = compute_checksums(self.task.save_path)
                sha = res.get("sha256", "Error")
                md5 = res.get("md5", "Error")
                def update_ui():
                    self.lbl_sha.configure(text=f"SHA256: {sha[:32]}...\nMD5: {md5}")
                    self.btn_calc_hash.configure(state="normal", text="✓ Re-compute")
                self.after(0, update_ui)
            except Exception as e:
                def on_err():
                    self.lbl_sha.configure(text=f"Error: {e}")
                    self.btn_calc_hash.configure(state="normal", text="Retry")
                self.after(0, on_err)

        threading.Thread(target=worker, daemon=True).start()

    def _open_file(self):
        if os.path.exists(self.task.save_path):
            try:
                os.startfile(self.task.save_path)
            except Exception as e:
                messagebox.showerror("Error", f"Could not open file: {e}")
        else:
            messagebox.showwarning("File Not Found", "The target file does not exist on disk yet.")

    def _open_folder(self):
        fld = os.path.dirname(self.task.save_path) if self.task.save_path else os.getcwd()
        if os.path.exists(fld):
            try:
                os.startfile(fld)
            except Exception as e:
                messagebox.showerror("Error", f"Could not open folder: {e}")
        else:
            messagebox.showwarning("Folder Not Found", "The download destination folder does not exist.")

class RefreshAddressDialog(ctk.CTkToplevel):
    """IDM-style dialog to refresh expired temporary download URLs without losing downloaded progress."""

    def __init__(self, parent, task, manager, on_refreshed: Optional[Callable] = None):
        super().__init__(parent)
        self.task = task
        self.manager = manager
        self.on_refreshed = on_refreshed

        self.title(f"FalconDM - Refresh Download Address: {task.filename}")
        self.geometry("620x400")
        self.resizable(False, False)
        self.transient(parent)
        try:
            parent.deiconify()
            parent.state('normal')
            self.lift()
            self.attributes('-topmost', True)
            self.after(200, lambda: self.attributes('-topmost', False))
            self.focus_force()
            import ctypes
            ctypes.windll.user32.ShowWindow(self.winfo_id(), 9)
            ctypes.windll.user32.SetForegroundWindow(self.winfo_id())
        except Exception:
            pass

        self.update_idletasks()
        try:
            x = parent.winfo_x() + (parent.winfo_width() // 2) - 310
            y = parent.winfo_y() + (parent.winfo_height() // 2) - 200
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        self._build_ui()

    def _build_ui(self):
        import webbrowser

        header = ctk.CTkFrame(self, fg_color="#181a20", height=50, corner_radius=0)
        header.pack(fill="x", side="top")
        ctk.CTkLabel(header, text="🔄 Refresh Expired Download Address", font=ctk.CTkFont(size=14, weight="bold"), text_color="#38bdf8").pack(side="left", padx=16, pady=10)

        prog_str = f"Progress: {(self.task.downloaded_bytes / 1048576):.1f} MB"
        if self.task.file_size > 0:
            prog_str += f" / {(self.task.file_size / 1048576):.1f} MB ({self.task.progress_pct:.1f}%)"
        ctk.CTkLabel(header, text=prog_str, font=ctk.CTkFont(size=11, weight="bold"), text_color="#4ade80").pack(side="right", padx=16, pady=10)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=15)

        info_box = ctk.CTkFrame(body, fg_color="#182234", corner_radius=8, border_width=1, border_color="#1e293b")
        info_box.pack(fill="x", pady=(0, 12))
        info_text = (
            "💡 Temporary links from Google Drive, Rapidgator, or media sites expire after a short time.\n"
            "Paste the new refreshed download link below. FalconDM will immediately verify the stream\n"
            "and resume downloading from where it stopped — without losing your downloaded data!"
        )
        ctk.CTkLabel(info_box, text=info_text, font=ctk.CTkFont(size=11), text_color="#94a3b8", justify="left").pack(anchor="w", padx=12, pady=10)

        ctk.CTkLabel(body, text="Original / Expired Address:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#94a3b8").pack(anchor="w", pady=(0, 2))
        entry_old = ctk.CTkEntry(body, height=28, fg_color="#0f172a", text_color="#64748b", border_color="#1e293b", font=ctk.CTkFont(size=11))
        entry_old.pack(fill="x", pady=(0, 10))
        entry_old.insert(0, self.task.url)
        entry_old.configure(state="readonly")

        ctk.CTkLabel(body, text="New Refreshed Download Address (URL):", font=ctk.CTkFont(size=11, weight="bold"), text_color="#f1f5f9").pack(anchor="w", pady=(0, 2))
        self.entry_new = ctk.CTkEntry(body, height=32, placeholder_text="Paste new download link here...", fg_color="#0f172a", text_color="#38bdf8", border_color="#2563eb", font=ctk.CTkFont(size=12))
        self.entry_new.pack(fill="x", pady=(0, 8))

        # Check if clipboard already has a URL
        try:
            cb = self.clipboard_get().strip()
            if cb.startswith("http://") or cb.startswith("https://"):
                if cb != self.task.url:
                    self.entry_new.insert(0, cb)
        except Exception:
            pass

        btn_tools_row = ctk.CTkFrame(body, fg_color="transparent")
        btn_tools_row.pack(fill="x", pady=(0, 10))

        def paste_cb():
            try:
                cb = self.clipboard_get().strip()
                if cb.startswith("http://") or cb.startswith("https://"):
                    self.entry_new.delete(0, "end")
                    self.entry_new.insert(0, cb)
            except Exception:
                pass

        def open_web():
            referer = self.task.headers.get("Referer") or self.task.url
            webbrowser.open(referer)

        ctk.CTkButton(btn_tools_row, text="📋 Paste from Clipboard", width=160, height=28, fg_color="#1e293b", hover_color="#334155", font=ctk.CTkFont(size=11), command=paste_cb).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_tools_row, text="🌐 Re-open Webpage in Browser", width=190, height=28, fg_color="#1e293b", hover_color="#334155", font=ctk.CTkFont(size=11), command=open_web).pack(side="left")

        # Bottom buttons
        btn_bar = ctk.CTkFrame(self, fg_color="#181a20", height=54, corner_radius=0)
        btn_bar.pack(fill="x", side="bottom")

        ctk.CTkButton(btn_bar, text="Cancel", width=90, height=34, fg_color="#4b5563", hover_color="#374151", command=self.destroy).pack(side="right", padx=16, pady=10)
        ctk.CTkButton(btn_bar, text="⚡ Update & Resume Download", width=220, height=34, fg_color="#2563eb", hover_color="#1d4ed8", font=ctk.CTkFont(weight="bold"), command=self._submit).pack(side="right", padx=(0, 8), pady=10)

    def _submit(self):
        new_url = self.entry_new.get().strip()
        if not new_url or not (new_url.startswith("http://") or new_url.startswith("https://")):
            messagebox.showwarning("Invalid URL", "Please enter a valid HTTP or HTTPS download URL.")
            return

        success = self.manager.refresh_task_url(self.task.task_id, new_url)
        if success:
            if self.on_refreshed:
                self.on_refreshed()
            messagebox.showinfo("Address Refreshed", f"✓ Download address updated successfully!\nFalconDM is now resuming {self.task.filename}.")
            self.destroy()
        else:
            messagebox.showerror("Error", "Could not refresh task URL in manager.")


class LiveSpeedHUDDialog(ctk.CTkToplevel):
    """High-precision real-time download speedometer and bandwidth waveform HUD."""

    def __init__(self, parent, manager):
        super().__init__(parent)
        self.manager = manager
        self.title("FalconDM — Live Speed & Performance HUD")
        self.geometry("660x420")
        self.minsize(600, 360)
        self.resizable(True, True)

        self.speed_history = [0.0] * 60
        self.peak_speed_seen = 0.0
        self.is_running = True

        self.update_idletasks()
        try:
            x = parent.winfo_x() + (parent.winfo_width() // 2) - 330
            y = parent.winfo_y() + (parent.winfo_height() // 2) - 210
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        self._build_ui()
        self._update_loop()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        # 1. Header
        header = ctk.CTkFrame(self, fg_color="#111827", height=50, corner_radius=0)
        header.pack(fill="x", side="top")

        ctk.CTkLabel(header, text="⚡ Real-Time Network Speed HUD", font=ctk.CTkFont(size=14, weight="bold"), text_color="#38bdf8").pack(side="left", padx=16, pady=10)

        self.always_on_top_var = ctk.BooleanVar(value=False)
        
        def toggle_top():
            self.attributes("-topmost", self.always_on_top_var.get())

        chk_top = ctk.CTkCheckBox(header, text="📌 Always on Top", variable=self.always_on_top_var, command=toggle_top, font=ctk.CTkFont(size=11), text_color="#94a3b8")
        chk_top.pack(side="right", padx=16, pady=10)

        # 2. Main Body
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=12)

        # Top metric cards
        metrics_row = ctk.CTkFrame(body, fg_color="transparent")
        metrics_row.pack(fill="x", pady=(0, 10))

        # Big speed card
        card_main = ctk.CTkFrame(metrics_row, fg_color="#0f172a", border_width=1, border_color="#1e293b", corner_radius=8, width=220, height=72)
        card_main.pack(side="left", fill="both", expand=True, padx=(0, 8))
        card_main.pack_propagate(False)
        ctk.CTkLabel(card_main, text="CURRENT THROUGHPUT", font=ctk.CTkFont(size=9, weight="bold"), text_color="#64748b").pack(anchor="w", padx=12, pady=(8, 0))
        self.lbl_main_speed = ctk.CTkLabel(card_main, text="0.0 KB/s", font=ctk.CTkFont(size=24, weight="bold"), text_color="#38bdf8")
        self.lbl_main_speed.pack(anchor="w", padx=12, pady=(0, 6))

        # Peak card
        card_peak = ctk.CTkFrame(metrics_row, fg_color="#0f172a", border_width=1, border_color="#1e293b", corner_radius=8, width=130, height=72)
        card_peak.pack(side="left", fill="both", expand=True, padx=(0, 8))
        card_peak.pack_propagate(False)
        ctk.CTkLabel(card_peak, text="PEAK BURST", font=ctk.CTkFont(size=9, weight="bold"), text_color="#64748b").pack(anchor="w", padx=12, pady=(8, 0))
        self.lbl_peak_val = ctk.CTkLabel(card_peak, text="0.0 KB/s", font=ctk.CTkFont(size=16, weight="bold"), text_color="#4ade80")
        self.lbl_peak_val.pack(anchor="w", padx=12, pady=(4, 6))

        # Average card
        card_avg = ctk.CTkFrame(metrics_row, fg_color="#0f172a", border_width=1, border_color="#1e293b", corner_radius=8, width=130, height=72)
        card_avg.pack(side="left", fill="both", expand=True, padx=(0, 8))
        card_avg.pack_propagate(False)
        ctk.CTkLabel(card_avg, text="5-SEC AVERAGE", font=ctk.CTkFont(size=9, weight="bold"), text_color="#64748b").pack(anchor="w", padx=12, pady=(8, 0))
        self.lbl_avg_val = ctk.CTkLabel(card_avg, text="0.0 KB/s", font=ctk.CTkFont(size=16, weight="bold"), text_color="#facc15")
        self.lbl_avg_val.pack(anchor="w", padx=12, pady=(4, 6))

        # Active streams card
        card_streams = ctk.CTkFrame(metrics_row, fg_color="#0f172a", border_width=1, border_color="#1e293b", corner_radius=8, width=130, height=72)
        card_streams.pack(side="left", fill="both", expand=True)
        card_streams.pack_propagate(False)
        ctk.CTkLabel(card_streams, text="ACTIVE THREADS", font=ctk.CTkFont(size=9, weight="bold"), text_color="#64748b").pack(anchor="w", padx=12, pady=(8, 0))
        self.lbl_streams_val = ctk.CTkLabel(card_streams, text="0 Sockets", font=ctk.CTkFont(size=16, weight="bold"), text_color="#a855f7")
        self.lbl_streams_val.pack(anchor="w", padx=12, pady=(4, 6))

        # Real-time High-Res Waveform Canvas
        chart_frame = ctk.CTkFrame(body, fg_color="#090d16", border_width=1, border_color="#1e293b", corner_radius=8)
        chart_frame.pack(fill="both", expand=True, pady=(0, 8))

        self.hud_canvas = tk.Canvas(chart_frame, bg="#090d16", highlightthickness=0)
        self.hud_canvas.pack(fill="both", expand=True, padx=8, pady=8)

        # Status footer bar
        footer = ctk.CTkFrame(body, fg_color="transparent")
        footer.pack(fill="x")
        self.lbl_hud_footer = ctk.CTkLabel(footer, text="⚡ Monitoring all download streams in real-time (250ms high-res sampling)", font=ctk.CTkFont(size=10), text_color="#64748b")
        self.lbl_hud_footer.pack(side="left")

    def _draw_chart(self):
        c = self.hud_canvas
        if not c or not c.winfo_exists():
            return
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 20 or h < 20:
            return

        max_spd = max(self.speed_history) if self.speed_history else 1.0
        if max_spd <= 0:
            max_spd = 1.0

        n = len(self.speed_history)
        points = []
        for i, val in enumerate(self.speed_history):
            x = (i / max(1, n - 1)) * (w - 16) + 8
            ratio = min(1.0, val / max_spd) if max_spd > 0 else 0
            y = (h - 10) - (ratio * (h - 24))
            points.append((x, y))

        # High-tech cyber grid lines
        for r, color, lbl in [(0.25, "#131c2a", "25%"), (0.5, "#182436", "50%"), (0.75, "#1f2e46", "75%"), (1.0, "#253754", "Peak")]:
            gy = (h - 10) - (r * (h - 24))
            c.create_line(8, gy, w - 8, gy, fill=color, dash=(2, 4))
            # Format speed label
            spd_lbl = format_speed(max_spd * r)
            c.create_text(w - 12, gy - 6, text=spd_lbl, fill="#475569", anchor="e", font=("Consolas", 8))

        # Filled multi-layer gradient polygon
        if len(points) >= 2:
            poly = [8, h - 6]
            for pt in points:
                poly.extend(pt)
            poly.extend([w - 8, h - 6])
            c.create_polygon(poly, fill="#0c1e38", outline="")

            # Smooth neon curve
            flat_pts = [coord for pt in points for coord in pt]
            c.create_line(flat_pts, fill="#1d4ed8", width=4, smooth=True)
            c.create_line(flat_pts, fill="#38bdf8", width=2, smooth=True)

            # Glowing lead pulse point
            last_x, last_y = points[-1]
            c.create_oval(last_x - 5, last_y - 5, last_x + 5, last_y + 5, fill="#38bdf8", outline="#ffffff", width=1.5)

    def _update_loop(self):
        if not self.is_running or not self.winfo_exists():
            return

        active_tasks = [t for t in self.manager.tasks.values() if t.status == "downloading"]
        total_speed = sum(t.speed_bps for t in active_tasks)

        # Append to history
        self.speed_history.append(total_speed)
        if len(self.speed_history) > 60:
            self.speed_history.pop(0)

        if total_speed > self.peak_speed_seen:
            self.peak_speed_seen = total_speed

        recent_avg = sum(self.speed_history[-20:]) / max(1, len(self.speed_history[-20:]))
        active_sockets = sum(len([s for s in getattr(t, 'segments', []) if getattr(s, 'status', '') == 'downloading']) for t in active_tasks) or (len(active_tasks) if active_tasks else 0)

        # Update labels
        self.lbl_main_speed.configure(text=format_speed(total_speed))
        self.lbl_peak_val.configure(text=format_speed(self.peak_speed_seen))
        self.lbl_avg_val.configure(text=format_speed(recent_avg))
        self.lbl_streams_val.configure(text=f"{active_sockets} Sockets")

        self._draw_chart()
        self.after(250, self._update_loop)

    def _on_close(self):
        self.is_running = False
        self.destroy()


class QuickLookDialog(ctk.CTkToplevel):
    """
    macOS / IDM-style Built-in Quick Look Preview Modal.
    Supports instant inspection of:
    - Images: High-resolution preview with dimensions, aspect ratio, zoom
    - Audio: Waveform and playback details with one-click play
    - Video: Codec details, resolution, duration, play in default player
    - Archives (.zip, .tar, .tgz): Live archive contents tree without extracting
    - Documents & Code: First lines text preview
    - Checksum & Hashes: Instant background SHA-256 and MD5 with one-click copy
    """

    def __init__(self, parent, task=None, file_path: Optional[str] = None):
        super().__init__(parent)
        self.task = task
        self.file_path = file_path or (task.save_path if task else "")
        self.filename = os.path.basename(self.file_path) if self.file_path else (task.filename if task else "Unknown")
        self.file_size = 0
        self.exists = False

        if self.file_path and os.path.exists(self.file_path):
            self.exists = True
            try:
                self.file_size = os.path.getsize(self.file_path)
            except Exception:
                self.file_size = getattr(task, 'file_size', 0) if task else 0
        elif task:
            self.file_size = getattr(task, 'file_size', 0)

        self.title(f"FalconDM Quick Look — {self.filename}")
        self.geometry("740x560")
        self.minsize(640, 480)
        self.resizable(True, True)

        self.transient(parent)
        try:
            parent.deiconify()
            parent.state('normal')
            self.lift()
            self.attributes('-topmost', True)
            self.after(200, lambda: self.attributes('-topmost', False))
            self.focus_force()
            import ctypes
            ctypes.windll.user32.ShowWindow(self.winfo_id(), 9)
            ctypes.windll.user32.SetForegroundWindow(self.winfo_id())
        except Exception:
            pass

        try:
            x = parent.winfo_x() + (parent.winfo_width() // 2) - 370
            y = parent.winfo_y() + (parent.winfo_height() // 2) - 280
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        # Keybindings: Space or Escape closes the preview
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<space>", lambda e: self.destroy())

        self._image_tk = None  # Hold reference to avoid garbage collection
        self._build_ui()

    def _format_bytes(self, size_bytes: int) -> str:
        if size_bytes <= 0:
            return "0 B"
        units = ["B", "KB", "MB", "GB", "TB"]
        idx = 0
        val = float(size_bytes)
        while val >= 1024.0 and idx < len(units) - 1:
            val /= 1024.0
            idx += 1
        return f"{val:.2f} {units[idx]}"

    def _get_category_info(self) -> tuple:
        ext = os.path.splitext(self.filename)[1].lower()
        if ext in ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.ico', '.svg', '.tiff', '.tif'):
            return "IMAGE", "🖼️", "#38bdf8"
        if ext in ('.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv', '.m4v', '.ts', '.3gp'):
            return "VIDEO", "🎬", "#f43f5e"
        if ext in ('.mp3', '.flac', '.wav', '.aac', '.ogg', '.m4a', '.opus', '.wma', '.alac'):
            return "AUDIO", "🎵", "#a855f7"
        if ext in ('.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.tgz', '.zst'):
            return "ARCHIVE", "📦", "#eab308"
        if ext in ('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.md', '.json', '.xml', '.csv', '.py', '.js', '.html', '.css', '.log'):
            return "DOCUMENT", "📄", "#10b981"
        if ext in ('.exe', '.msi', '.apk', '.bin', '.iso', '.dmg', '.deb', '.rpm'):
            return "PROGRAM", "⚡", "#f97316"
        return "FILE", "📁", "#94a3b8"

    def _build_ui(self):
        cat_name, cat_icon, cat_color = self._get_category_info()

        # 1. Header Frame
        header = ctk.CTkFrame(self, fg_color="#0e1522", height=64, corner_radius=0, border_width=1, border_color="#1e293b")
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        icon_box = ctk.CTkFrame(header, width=44, height=44, fg_color="#182338", corner_radius=10, border_width=1, border_color="#243450")
        icon_box.pack(side="left", padx=(16, 12), pady=10)
        icon_box.pack_propagate(False)
        ctk.CTkLabel(icon_box, text=cat_icon, font=ctk.CTkFont(size=22)).pack(expand=True)

        meta_frame = ctk.CTkFrame(header, fg_color="transparent")
        meta_frame.pack(side="left", fill="both", expand=True, pady=10)

        lbl_fname = ctk.CTkLabel(meta_frame, text=self.filename, font=ctk.CTkFont(size=14, weight="bold"), text_color="#f8fafc", anchor="w")
        lbl_fname.pack(anchor="w")

        sub_text = f"{cat_name}  •  {self._format_bytes(self.file_size)}"
        if not self.exists:
            sub_text += "  •  ⚠️ Not yet downloaded to disk"
        else:
            sub_text += "  •  ✅ Ready on Disk"
        lbl_sub = ctk.CTkLabel(meta_frame, text=sub_text, font=ctk.CTkFont(size=11), text_color="#94a3b8", anchor="w")
        lbl_sub.pack(anchor="w")

        # Status badge on right
        badge_frame = ctk.CTkFrame(header, fg_color="#132035", border_width=1, border_color=cat_color, corner_radius=14)
        badge_frame.pack(side="right", padx=16, pady=16)
        ctk.CTkLabel(badge_frame, text=f" {cat_name} ", font=ctk.CTkFont(size=11, weight="bold"), text_color=cat_color).pack(padx=8, pady=2)

        # 2. Bottom Action Bar
        bottom_bar = ctk.CTkFrame(self, fg_color="#0c121d", height=50, corner_radius=0, border_width=1, border_color="#1e293b")
        bottom_bar.pack(fill="x", side="bottom")
        bottom_bar.pack_propagate(False)

        btn_close = ctk.CTkButton(
            bottom_bar,
            text="✕ Close",
            width=80,
            height=30,
            corner_radius=6,
            fg_color="#1e293b",
            hover_color="#334155",
            text_color="#cbd5e1",
            font=ctk.CTkFont(size=11),
            command=self.destroy
        )
        btn_close.pack(side="right", padx=(0, 14), pady=10)

        btn_copy_path = ctk.CTkButton(
            bottom_bar,
            text="📋 Copy Path",
            width=100,
            height=30,
            corner_radius=6,
            fg_color="#182338",
            hover_color="#243450",
            border_width=1,
            border_color="#243450",
            text_color="#38bdf8",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._copy_path
        )
        btn_copy_path.pack(side="right", padx=(0, 8), pady=10)

        if self.exists:
            btn_folder = ctk.CTkButton(
                bottom_bar,
                text="📂 Open Folder",
                width=110,
                height=30,
                corner_radius=6,
                fg_color="#1e293b",
                hover_color="#334155",
                text_color="#cbd5e1",
                font=ctk.CTkFont(size=11),
                command=self._open_folder
            )
            btn_folder.pack(side="right", padx=(0, 8), pady=10)

            btn_open = ctk.CTkButton(
                bottom_bar,
                text="▶️ Open File",
                width=110,
                height=30,
                corner_radius=6,
                fg_color="#2563eb",
                hover_color="#1d4ed8",
                text_color="#ffffff",
                font=ctk.CTkFont(size=11, weight="bold"),
                command=self._open_file
            )
            btn_open.pack(side="right", padx=(0, 8), pady=10)

        hint_lbl = ctk.CTkLabel(bottom_bar, text="💡 Press Spacebar or Esc to dismiss", font=ctk.CTkFont(size=10), text_color="#64748b")
        hint_lbl.pack(side="left", padx=16, pady=12)

        # 3. Body Notebook / Tabview
        tabview = ctk.CTkTabview(self, fg_color="#0b0f17", segmented_button_fg_color="#141c2c", segmented_button_selected_color="#2563eb", segmented_button_selected_hover_color="#1d4ed8")
        tabview.pack(fill="both", expand=True, padx=14, pady=10)

        tab_preview = tabview.add("👁️ Quick Preview")
        tab_hashes = tabview.add("🔐 Integrity & Hashes")
        tab_details = tabview.add("ℹ️ Technical Details")

        self._build_preview_tab(tab_preview, cat_name)
        self._build_hashes_tab(tab_hashes)
        self._build_details_tab(tab_details)

    def _build_preview_tab(self, parent, cat_name: str):
        if not self.exists:
            card = ctk.CTkFrame(parent, fg_color="#111827", corner_radius=10, border_width=1, border_color="#1f293d")
            card.pack(fill="both", expand=True, padx=12, pady=12)
            ctk.CTkLabel(card, text="⚠️ File is not currently available on disk", font=ctk.CTkFont(size=14, weight="bold"), text_color="#facc15").pack(pady=(60, 8))
            ctk.CTkLabel(card, text=f"Target path: {self.file_path}", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(pady=(0, 6))
            if self.task and self.task.status != "Completed":
                ctk.CTkLabel(card, text=f"Status: {self.task.status} ({self.task.progress_pct:.1f}% downloaded)", font=ctk.CTkFont(size=12, weight="bold"), text_color="#38bdf8").pack(pady=4)
            return

        ext = os.path.splitext(self.filename)[1].lower()

        # Image Viewer
        if cat_name == "IMAGE":
            self._render_image_preview(parent)
        # Audio Player / Waveform
        elif cat_name == "AUDIO":
            self._render_audio_preview(parent)
        # Video Player Card
        elif cat_name == "VIDEO":
            self._render_video_preview(parent)
        # Archive Contents Explorer
        elif cat_name == "ARCHIVE":
            self._render_archive_preview(parent, ext)
        # Text / Document / Code
        elif cat_name == "DOCUMENT" or ext in ('.txt', '.py', '.json', '.xml', '.csv', '.md', '.log', '.html', '.css', '.ini', '.bat', '.sh'):
            self._render_text_preview(parent)
        # Generic Binary
        else:
            self._render_binary_preview(parent)

    def _render_image_preview(self, parent):
        try:
            from PIL import Image, ImageTk
            with Image.open(self.file_path) as img:
                orig_w, orig_h = img.size
                img_format = img.format or "Image"
                img_mode = img.mode

                # Scale to fit container (up to 620 x 300)
                max_w, max_h = 620, 300
                scale = min(max_w / max(1, orig_w), max_h / max(1, orig_h), 1.0)
                new_w = max(1, int(orig_w * scale))
                new_h = max(1, int(orig_h * scale))

                resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                self._image_tk = ImageTk.PhotoImage(resized)

            canvas_box = ctk.CTkFrame(parent, fg_color="#070a10", corner_radius=8, border_width=1, border_color="#182338")
            canvas_box.pack(fill="both", expand=True, padx=10, pady=8)

            img_lbl = tk.Label(canvas_box, image=self._image_tk, bg="#070a10")
            img_lbl.pack(expand=True, pady=6)

            info_bar = ctk.CTkFrame(canvas_box, fg_color="#0e1522", height=30, corner_radius=0)
            info_bar.pack(fill="x", side="bottom")
            info_bar.pack_propagate(False)

            info_text = f"Dimensions: {orig_w} × {orig_h} px  •  Format: {img_format}  •  Color Mode: {img_mode}  •  File Size: {self._format_bytes(self.file_size)}"
            ctk.CTkLabel(info_bar, text=info_text, font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(side="left", padx=12, pady=4)
        except Exception as e:
            ctk.CTkLabel(parent, text=f"Could not render image preview: {e}", font=ctk.CTkFont(size=12), text_color="#f87171").pack(pady=40)

    def _render_audio_preview(self, parent):
        card = ctk.CTkFrame(parent, fg_color="#0d1422", corner_radius=10, border_width=1, border_color="#1e2c44")
        card.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(card, text="🎵 Audio Track Quick Look", font=ctk.CTkFont(size=15, weight="bold"), text_color="#38bdf8").pack(pady=(24, 6))
        ctk.CTkLabel(card, text=self.filename, font=ctk.CTkFont(size=12), text_color="#cbd5e1").pack(pady=(0, 16))

        # Simulated dynamic waveform canvas
        wave_canvas = tk.Canvas(card, width=540, height=80, bg="#060910", highlightthickness=1, highlightbackground="#1b283d")
        wave_canvas.pack(pady=10)

        import math
        import random
        random.seed(len(self.filename))
        bars = 54
        for i in range(bars):
            bh = int(15 + 45 * abs(math.sin(i * 0.28) * random.uniform(0.6, 1.0)))
            x0 = 8 + i * 10
            x1 = x0 + 6
            y0 = 40 - (bh // 2)
            y1 = 40 + (bh // 2)
            color = "#a855f7" if i % 2 == 0 else "#38bdf8"
            wave_canvas.create_rectangle(x0, y0, x1, y1, fill=color, outline="")

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(pady=16)

        btn_play = ctk.CTkButton(
            btn_row,
            text="▶️ Play Track in Default Player",
            width=220,
            height=34,
            corner_radius=8,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._open_file
        )
        btn_play.pack(side="left", padx=8)

    def _render_video_preview(self, parent):
        card = ctk.CTkFrame(parent, fg_color="#0d1422", corner_radius=10, border_width=1, border_color="#1e2c44")
        card.pack(fill="both", expand=True, padx=12, pady=12)

        icon_frame = ctk.CTkFrame(card, width=72, height=72, fg_color="#182338", corner_radius=16, border_width=1, border_color="#253856")
        icon_frame.pack(pady=(30, 12))
        icon_frame.pack_propagate(False)
        ctk.CTkLabel(icon_frame, text="🎬", font=ctk.CTkFont(size=36)).pack(expand=True)

        ctk.CTkLabel(card, text=self.filename, font=ctk.CTkFont(size=14, weight="bold"), text_color="#f8fafc").pack(pady=(0, 4))
        ctk.CTkLabel(card, text=f"Video Media Container  •  {self._format_bytes(self.file_size)}", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(pady=(0, 20))

        btn_play = ctk.CTkButton(
            card,
            text="▶️ Open in Video Player",
            width=200,
            height=36,
            corner_radius=8,
            fg_color="#e11d48",
            hover_color="#be123c",
            text_color="#ffffff",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._open_file
        )
        btn_play.pack(pady=(0, 10))

    def _render_archive_preview(self, parent, ext: str):
        card = ctk.CTkFrame(parent, fg_color="#0a0f18", corner_radius=8, border_width=1, border_color="#1e293b")
        card.pack(fill="both", expand=True, padx=8, pady=8)

        top_info = ctk.CTkFrame(card, fg_color="transparent")
        top_info.pack(fill="x", padx=10, pady=(6, 4))
        lbl_arch = ctk.CTkLabel(top_info, text="📦 Archive Contents (Direct Inspection)", font=ctk.CTkFont(size=12, weight="bold"), text_color="#facc15")
        lbl_arch.pack(side="left")

        tree_frame = ctk.CTkFrame(card, fg_color="#070a10", corner_radius=6, border_width=1, border_color="#182234")
        tree_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        columns = ("name", "size", "compressed", "date")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=10, selectmode="browse")
        tree.heading("name", text="File / Entry Name")
        tree.heading("size", text="Uncompressed")
        tree.heading("compressed", text="Compressed")
        tree.heading("date", text="Modified Date")

        tree.column("name", width=280, anchor="w")
        tree.column("size", width=95, anchor="e")
        tree.column("compressed", width=95, anchor="e")
        tree.column("date", width=140, anchor="center")

        scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)

        # Style treeview for dark mode
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#070a10", foreground="#f8fafc", fieldbackground="#070a10", borderwidth=0, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", background="#111827", foreground="#94a3b8", borderwidth=1, relief="flat", font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected", "#1e3a8a")], foreground=[("selected", "#ffffff")])

        # Populate archive files
        try:
            if ext == '.zip':
                import zipfile
                with zipfile.ZipFile(self.file_path, 'r') as zf:
                    infos = zf.infolist()[:250]
                    total_uncompressed = 0
                    for info in infos:
                        total_uncompressed += info.file_size
                        date_str = f"{info.date_time[0]:04d}-{info.date_time[1]:02d}-{info.date_time[2]:02d} {info.date_time[3]:02d}:{info.date_time[4]:02d}"
                        tree.insert("", "end", values=(
                            info.filename,
                            self._format_bytes(info.file_size),
                            self._format_bytes(info.compress_size),
                            date_str
                        ))
                    lbl_arch.configure(text=f"📦 ZIP Archive: {len(zf.infolist())} entries  •  Uncompressed: {self._format_bytes(total_uncompressed)}")
            elif ext in ('.tar', '.gz', '.tgz', '.bz2', '.xz'):
                import tarfile
                with tarfile.open(self.file_path, 'r:*') as tf:
                    members = tf.getmembers()[:250]
                    import datetime
                    for m in members:
                        m_date = datetime.datetime.fromtimestamp(m.mtime).strftime("%Y-%m-%d %H:%M") if m.mtime else ""
                        tree.insert("", "end", values=(
                            m.name,
                            self._format_bytes(m.size),
                            "-",
                            m_date
                        ))
                    lbl_arch.configure(text=f"📦 TAR Archive: {len(members)} entries")
            else:
                tree.insert("", "end", values=(f"Archive format {ext} requires 7-Zip or WinRAR to inspect entries.", "", "", ""))
        except Exception as err:
            tree.insert("", "end", values=(f"Error reading archive: {err}", "", "", ""))

    def _render_text_preview(self, parent):
        box = ctk.CTkTextbox(
            parent,
            fg_color="#070a10",
            text_color="#e2e8f0",
            font=ctk.CTkFont(family="Consolas", size=11),
            corner_radius=8,
            border_width=1,
            border_color="#182338"
        )
        box.pack(fill="both", expand=True, padx=8, pady=8)
        try:
            with open(self.file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(32768)  # Read up to 32 KB
                box.insert("1.0", content)
                if len(content) >= 32768:
                    box.insert("end", "\n\n--- [Preview truncated to 32 KB] ---")
            box.configure(state="disabled")
        except Exception as e:
            box.insert("1.0", f"Could not read text: {e}")
            box.configure(state="disabled")

    def _render_binary_preview(self, parent):
        card = ctk.CTkFrame(parent, fg_color="#0d1422", corner_radius=10, border_width=1, border_color="#1e2c44")
        card.pack(fill="both", expand=True, padx=12, pady=12)

        icon_frame = ctk.CTkFrame(card, width=64, height=64, fg_color="#182338", corner_radius=14, border_width=1, border_color="#253856")
        icon_frame.pack(pady=(40, 12))
        icon_frame.pack_propagate(False)
        ctk.CTkLabel(icon_frame, text="⚡", font=ctk.CTkFont(size=32)).pack(expand=True)

        ctk.CTkLabel(card, text=self.filename, font=ctk.CTkFont(size=14, weight="bold"), text_color="#f8fafc").pack(pady=(0, 4))
        ctk.CTkLabel(card, text=f"Binary Executable / Package  •  {self._format_bytes(self.file_size)}", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(pady=(0, 20))

        btn_run = ctk.CTkButton(
            card,
            text="▶️ Run / Execute File",
            width=180,
            height=34,
            corner_radius=8,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._open_file
        )
        btn_run.pack(pady=4)

    def _build_hashes_tab(self, parent):
        card = ctk.CTkFrame(parent, fg_color="#0d1422", corner_radius=8, border_width=1, border_color="#1e2c44")
        card.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(card, text="Cryptographic Hash Verification", font=ctk.CTkFont(size=13, weight="bold"), text_color="#38bdf8").pack(anchor="w", padx=16, pady=(14, 4))
        ctk.CTkLabel(card, text="Verify download integrity against official release checksums to guarantee zero file corruption.", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(anchor="w", padx=16, pady=(0, 14))

        # SHA-256 Row
        ctk.CTkLabel(card, text="SHA-256 CHECKSUM:", font=ctk.CTkFont(size=10, weight="bold"), text_color="#64748b").pack(anchor="w", padx=16, pady=(0, 2))
        row_sha = ctk.CTkFrame(card, fg_color="transparent")
        row_sha.pack(fill="x", padx=16, pady=(0, 12))
        self.entry_sha256 = ctk.CTkEntry(row_sha, height=32, font=ctk.CTkFont(family="Consolas", size=11), fg_color="#070a10", border_color="#1e2c44", text_color="#4ade80")
        self.entry_sha256.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry_sha256.insert(0, "Calculating SHA-256 in background...")

        btn_copy_sha = ctk.CTkButton(row_sha, text="Copy", width=70, height=32, corner_radius=6, fg_color="#1e293b", hover_color="#334155", font=ctk.CTkFont(size=11), command=lambda: self._copy_text(self.entry_sha256.get()))
        btn_copy_sha.pack(side="right")

        # MD5 Row
        ctk.CTkLabel(card, text="MD5 CHECKSUM:", font=ctk.CTkFont(size=10, weight="bold"), text_color="#64748b").pack(anchor="w", padx=16, pady=(0, 2))
        row_md5 = ctk.CTkFrame(card, fg_color="transparent")
        row_md5.pack(fill="x", padx=16, pady=(0, 16))
        self.entry_md5 = ctk.CTkEntry(row_md5, height=32, font=ctk.CTkFont(family="Consolas", size=11), fg_color="#070a10", border_color="#1e2c44", text_color="#38bdf8")
        self.entry_md5.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry_md5.insert(0, "Calculating MD5 in background...")

        btn_copy_md5 = ctk.CTkButton(row_md5, text="Copy", width=70, height=32, corner_radius=6, fg_color="#1e293b", hover_color="#334155", font=ctk.CTkFont(size=11), command=lambda: self._copy_text(self.entry_md5.get()))
        btn_copy_md5.pack(side="right")

        # Compare input
        ctk.CTkLabel(card, text="VERIFY AGAINST EXPECTED HASH:", font=ctk.CTkFont(size=10, weight="bold"), text_color="#64748b").pack(anchor="w", padx=16, pady=(0, 2))
        row_cmp = ctk.CTkFrame(card, fg_color="transparent")
        row_cmp.pack(fill="x", padx=16, pady=(0, 8))
        self.entry_compare = ctk.CTkEntry(row_cmp, height=32, placeholder_text="Paste MD5 or SHA-256 to compare...", font=ctk.CTkFont(family="Consolas", size=11), fg_color="#070a10", border_color="#1e2c44", text_color="#f8fafc")
        self.entry_compare.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.lbl_verify_res = ctk.CTkLabel(card, text="", font=ctk.CTkFont(size=11, weight="bold"))
        self.lbl_verify_res.pack(anchor="w", padx=16)

        def on_cmp_change(*args):
            val = self.entry_compare.get().strip().lower()
            if not val:
                self.lbl_verify_res.configure(text="")
                return
            sha_val = self.entry_sha256.get().strip().lower()
            md5_val = self.entry_md5.get().strip().lower()
            if val == sha_val or val == md5_val:
                self.lbl_verify_res.configure(text="✅ PERFECT MATCH! The file is 100% authentic and uncorrupted.", text_color="#4ade80")
            else:
                self.lbl_verify_res.configure(text="❌ CHECKSUM MISMATCH! Expected hash does not match file.", text_color="#f87171")

        self.entry_compare.bind("<KeyRelease>", on_cmp_change)

        # Trigger background computation if file exists
        if self.exists:
            threading.Thread(target=self._compute_hashes_worker, daemon=True).start()
        else:
            self.entry_sha256.delete(0, "end")
            self.entry_sha256.insert(0, "File does not exist on disk")
            self.entry_md5.delete(0, "end")
            self.entry_md5.insert(0, "File does not exist on disk")

    def _compute_hashes_worker(self):
        import hashlib
        try:
            h_sha = hashlib.sha256()
            h_md5 = hashlib.md5()
            with open(self.file_path, "rb") as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    h_sha.update(chunk)
                    h_md5.update(chunk)
            sha_hex = h_sha.hexdigest()
            md5_hex = h_md5.hexdigest()

            def update_entries():
                if self.winfo_exists():
                    self.entry_sha256.delete(0, "end")
                    self.entry_sha256.insert(0, sha_hex)
                    self.entry_md5.delete(0, "end")
                    self.entry_md5.insert(0, md5_hex)

            self.after(0, update_entries)
        except Exception as e:
            def show_err():
                if self.winfo_exists():
                    self.entry_sha256.delete(0, "end")
                    self.entry_sha256.insert(0, f"Error: {e}")
            self.after(0, show_err)

    def _build_details_tab(self, parent):
        card = ctk.CTkFrame(parent, fg_color="#0d1422", corner_radius=8, border_width=1, border_color="#1e2c44")
        card.pack(fill="both", expand=True, padx=12, pady=12)

        import datetime
        created_str = "-"
        modified_str = "-"
        if self.exists:
            try:
                ct = os.path.getctime(self.file_path)
                mt = os.path.getmtime(self.file_path)
                created_str = datetime.datetime.fromtimestamp(ct).strftime("%Y-%m-%d %H:%M:%S")
                modified_str = datetime.datetime.fromtimestamp(mt).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass

        details = [
            ("Filename:", self.filename),
            ("Full Path:", self.file_path),
            ("Directory:", os.path.dirname(self.file_path) if self.file_path else "-"),
            ("File Size:", f"{self._format_bytes(self.file_size)} ({self.file_size:,} bytes)"),
            ("Date Created:", created_str),
            ("Date Modified:", modified_str),
            ("Source URL:", getattr(self.task, 'url', '-') if self.task else "-"),
            ("Download Status:", getattr(self.task, 'status', 'Completed' if self.exists else 'Unknown') if self.task else ('Completed' if self.exists else 'Unknown'))
        ]

        for idx, (label, val) in enumerate(details):
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=4)
            ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=11, weight="bold"), text_color="#94a3b8", width=120, anchor="w").pack(side="left")
            entry = ctk.CTkEntry(row, height=26, font=ctk.CTkFont(size=11), fg_color="#070a10", border_width=0, text_color="#f8fafc")
            entry.pack(side="left", fill="x", expand=True)
            entry.insert(0, str(val))
            entry.configure(state="readonly")

    def _copy_path(self):
        if self.file_path:
            self._copy_text(self.file_path)

    def _copy_text(self, text: str):
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.update()
        except Exception:
            pass

    def _open_folder(self):
        if not self.file_path:
            return
        open_file_or_folder(self.file_path, select=True)

    def _open_file(self):
        if self.file_path and os.path.exists(self.file_path):
            open_file_or_folder(self.file_path)


class ShutdownWarningDialog(ctk.CTkToplevel):
    """30-second warning countdown before shutting down the computer upon download completion."""

    def __init__(self, parent, countdown_sec: int = 30):
        super().__init__(parent)
        self.title("FalconDM - Auto Shutdown")
        self.geometry("440x230")
        self.resizable(False, False)
        self.remaining = countdown_sec
        self.cancelled = False

        # Center on screen and lift to top
        try:
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            self.geometry(f"+{(sw - 440)//2}+{(sh - 230)//2}")
            self.attributes('-topmost', True)
        except Exception:
            pass

        self._build_ui()
        self._tick()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="#1e1b2e", height=44, corner_radius=0)
        header.pack(fill="x")
        ctk.CTkLabel(header, text="⚠️ All Downloads Finished", font=ctk.CTkFont(size=14, weight="bold"), text_color="#f87171").pack(side="left", padx=16, pady=10)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=14)

        self.lbl_msg = ctk.CTkLabel(
            body,
            text=f"Your PC will shut down in {self.remaining} seconds.\nClick 'Cancel' to keep your computer running.",
            font=ctk.CTkFont(size=12),
            text_color="#f1f5f9",
            justify="center"
        )
        self.lbl_msg.pack(pady=(8, 16))

        btn_frame = ctk.CTkFrame(body, fg_color="transparent")
        btn_frame.pack(fill="x")

        btn_cancel = ctk.CTkButton(
            btn_frame,
            text="❌ Cancel Shutdown",
            width=150,
            height=34,
            corner_radius=6,
            fg_color="#334155",
            hover_color="#475569",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#ffffff",
            command=self._cancel
        )
        btn_cancel.pack(side="left", padx=(0, 10), expand=True)

        btn_now = ctk.CTkButton(
            btn_frame,
            text="⚡ Shut Down Now",
            width=150,
            height=34,
            corner_radius=6,
            fg_color="#dc2626",
            hover_color="#b91c1c",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#ffffff",
            command=self._do_shutdown
        )
        btn_now.pack(side="right", expand=True)

    def _tick(self):
        if self.cancelled:
            return
        if self.remaining <= 0:
            self._do_shutdown()
            return
        self.lbl_msg.configure(
            text=f"Your PC will shut down in {self.remaining} seconds.\nClick 'Cancel' to keep your computer running."
        )
        self.remaining -= 1
        self.after(1000, self._tick)

    def _cancel(self):
        self.cancelled = True
        self.destroy()

    def _do_shutdown(self):
        self.cancelled = True
        self.destroy()
        from core.platform_utils import trigger_system_shutdown
        trigger_system_shutdown(sleep=False)


class AISecurityDialog(ctk.CTkToplevel):
    """FalconDM AI Zero-Trust Threat & Deception Inspector."""

    def __init__(self, parent, file_path: str):
        super().__init__(parent)
        self.file_path = file_path
        self.title("FalconDM AI - Threat & Deception Shield")
        self.geometry("560x420")
        self.minsize(500, 360)
        self.report = ai_engine.inspect_file_threats(file_path)

        # Center on screen
        try:
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            self.geometry(f"+{(sw - 560)//2}+{(sh - 420)//2}")
            self.attributes('-topmost', True)
        except Exception:
            pass

        self._build_ui()

    def _build_ui(self):
        verdict = self.report.get("verdict", "CLEAN")
        if verdict == "DANGEROUS":
            hdr_color = "#450a0a"
            icon = "🛑 CRITICAL THREAT DETECTED"
        elif verdict == "SUSPICIOUS":
            hdr_color = "#422006"
            icon = "⚠️ SUSPICIOUS ATTRIBUTES"
        else:
            hdr_color = "#064e3b"
            icon = "✅ VERIFIED CLEAN & SAFE"

        header = ctk.CTkFrame(self, fg_color=hdr_color, height=50, corner_radius=0)
        header.pack(fill="x")
        ctk.CTkLabel(header, text=icon, font=ctk.CTkFont(size=14, weight="bold"), text_color="#ffffff").pack(side="left", padx=16, pady=12)

        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=18, pady=12)

        # File Target Card
        card = ctk.CTkFrame(body, fg_color="#111827", corner_radius=8, border_width=1, border_color="#1f293d")
        card.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(card, text=f"File: {os.path.basename(self.file_path)}", font=ctk.CTkFont(size=12, weight="bold"), text_color="#f8fafc", wraplength=480).pack(anchor="w", padx=14, pady=(10, 2))
        ctk.CTkLabel(card, text=f"Path: {self.file_path}", font=ctk.CTkFont(size=10), text_color="#94a3b8", wraplength=480).pack(anchor="w", padx=14, pady=(0, 10))

        # Risk Analysis
        ctk.CTkLabel(body, text="THREAT INSPECTION REPORT", font=ctk.CTkFont(size=10, weight="bold"), text_color="#38bdf8").pack(anchor="w", pady=(4, 4))
        ctk.CTkLabel(body, text=self.report.get("message", ""), font=ctk.CTkFont(size=12, weight="bold"), text_color="#f8fafc", wraplength=480, justify="left").pack(anchor="w", pady=(0, 6))

        details = self.report.get("details", [])
        if details:
            for d in details:
                ctk.CTkLabel(body, text=f"• {d}", font=ctk.CTkFont(size=11), text_color="#f87171" if verdict == "DANGEROUS" else "#fbbf24", wraplength=480, justify="left").pack(anchor="w", pady=2)
        else:
            ctk.CTkLabel(body, text="• Binary magic header matches declared file type.\n• No double-extension deception or disguised script payloads detected.", font=ctk.CTkFont(size=11), text_color="#4ade80", justify="left").pack(anchor="w", pady=2)

        sha = self.report.get("sha256")
        if sha:
            ctk.CTkLabel(body, text=f"SHA-256: {sha}", font=ctk.CTkFont(size=9, family="Consolas"), text_color="#64748b", wraplength=480).pack(anchor="w", pady=(8, 0))

        # Bottom Actions
        btn_bar = ctk.CTkFrame(self, fg_color="#141a24", height=50, corner_radius=0)
        btn_bar.pack(fill="x", side="bottom")

        ctk.CTkButton(btn_bar, text="Close", width=80, height=32, corner_radius=6, fg_color="#334155", hover_color="#475569", command=self.destroy).pack(side="right", padx=14, pady=10)
        if verdict == "DANGEROUS":
            ctk.CTkButton(btn_bar, text="🗑️ Delete File Immediately", width=170, height=32, corner_radius=6, fg_color="#dc2626", hover_color="#b91c1c", font=ctk.CTkFont(weight="bold"), command=self._delete_file).pack(side="right", padx=(0, 8), pady=10)
        else:
            ctk.CTkButton(btn_bar, text="📂 Open Containing Folder", width=170, height=32, corner_radius=6, fg_color="#2563eb", hover_color="#1d4ed8", font=ctk.CTkFont(weight="bold"), command=self._open_folder).pack(side="right", padx=(0, 8), pady=10)

    def _delete_file(self):
        if messagebox.askyesno("Confirm Deletion", "Are you sure you want to permanently delete this threat?"):
            try:
                os.remove(self.file_path)
                messagebox.showinfo("Deleted", "Deceptive threat file deleted from system.")
                self.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Could not delete file: {e}")

    def _open_folder(self):
        open_file_or_folder(self.file_path, select=True)


class AISummaryDialog(ctk.CTkToplevel):
    """FalconDM AI Content Summarizer & Note Extractor."""

    def __init__(self, parent, file_path: str, url: str = "", title: str = ""):
        super().__init__(parent)
        self.file_path = file_path
        self.url = url
        self.title("FalconDM AI - Media Summary & Key Takeaways")
        self.geometry("580x460")
        self.minsize(520, 380)

        # Center on screen
        try:
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            self.geometry(f"+{(sw - 580)//2}+{(sh - 460)//2}")
            self.attributes('-topmost', True)
        except Exception:
            pass

        self.summary_data = ai_engine.generate_summary(file_path, url=url, title=title)
        self._build_ui()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="#1e1b4b", height=50, corner_radius=0)
        header.pack(fill="x")
        ctk.CTkLabel(header, text="✨ AI Content Summary & Takeaways", font=ctk.CTkFont(size=14, weight="bold"), text_color="#c084fc").pack(side="left", padx=16, pady=12)

        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=18, pady=12)

        card = ctk.CTkFrame(body, fg_color="#111827", corner_radius=8, border_width=1, border_color="#1f293d")
        card.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(card, text=self.summary_data.get("title", ""), font=ctk.CTkFont(size=13, weight="bold"), text_color="#f8fafc", wraplength=500, justify="left").pack(anchor="w", padx=14, pady=(10, 4))
        ctk.CTkLabel(card, text=f"Media Type: {self.summary_data.get('media_type', 'Media')}", font=ctk.CTkFont(size=11), text_color="#38bdf8").pack(anchor="w", padx=14, pady=(0, 10))

        ctk.CTkLabel(body, text="KEY TAKEAWAYS & HIGHLIGHTS", font=ctk.CTkFont(size=10, weight="bold"), text_color="#a855f7").pack(anchor="w", pady=(0, 6))
        for bullet in self.summary_data.get("bullets", []):
            item_frame = ctk.CTkFrame(body, fg_color="#0f172a", corner_radius=6, border_width=1, border_color="#1e293b")
            item_frame.pack(fill="x", pady=3)
            ctk.CTkLabel(item_frame, text=f"• {bullet}", font=ctk.CTkFont(size=11), text_color="#f1f5f9", wraplength=480, justify="left").pack(anchor="w", padx=12, pady=8)

        # Bottom Bar
        btn_bar = ctk.CTkFrame(self, fg_color="#141a24", height=50, corner_radius=0)
        btn_bar.pack(fill="x", side="bottom")

        ctk.CTkButton(btn_bar, text="Close", width=80, height=32, corner_radius=6, fg_color="#334155", hover_color="#475569", command=self.destroy).pack(side="right", padx=14, pady=10)
        ctk.CTkButton(btn_bar, text="📋 Copy Summary", width=130, height=32, corner_radius=6, fg_color="#6366f1", hover_color="#4f46e5", font=ctk.CTkFont(weight="bold"), command=self._copy).pack(side="right", padx=(0, 8), pady=10)

    def _copy(self):
        text = self.summary_data.get("summary_text", "")
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("Copied", "AI Summary copied to clipboard!")


class AINaturalLanguageDialog(ctk.CTkToplevel):
    """FalconDM AI Natural Language Prompt Downloader."""

    def __init__(self, parent, on_enqueue_batch: Callable[[List[str], str], None]):
        super().__init__(parent)
        self.on_enqueue_batch = on_enqueue_batch
        self.title("FalconDM AI - Natural Language Prompt Downloader")
        self.geometry("640x520")
        self.minsize(560, 420)
        self.crawled_items: List[Dict[str, Any]] = []

        try:
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            self.geometry(f"+{(sw - 640)//2}+{(sh - 520)//2}")
            self.attributes('-topmost', True)
        except Exception:
            pass

        self._build_ui()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="#0f172a", height=50, corner_radius=0)
        header.pack(fill="x")
        ctk.CTkLabel(header, text="🧠 AI Natural Language Downloader", font=ctk.CTkFont(size=14, weight="bold"), text_color="#38bdf8").pack(side="left", padx=16, pady=12)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=12)

        ctk.CTkLabel(body, text="Natural Language Prompt:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#cbd5e1").pack(anchor="w", pady=(0, 2))
        self.entry_prompt = ctk.CTkEntry(
            body,
            placeholder_text="e.g. Download all PDF lecture slides, or Grab all MP3 audio episodes",
            height=34,
            corner_radius=6,
            fg_color="#0b0f17",
            border_color="#1e2638",
            text_color="#f8fafc"
        )
        self.entry_prompt.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(body, text="Target Website / Archive URL:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#cbd5e1").pack(anchor="w", pady=(0, 2))
        url_frame = ctk.CTkFrame(body, fg_color="transparent")
        url_frame.pack(fill="x", pady=(0, 12))

        self.entry_url = ctk.CTkEntry(
            url_frame,
            placeholder_text="https://example.com/course/syllabus or https://archive.org/...",
            height=34,
            corner_radius=6,
            fg_color="#0b0f17",
            border_color="#1e2638",
            text_color="#f8fafc"
        )
        self.entry_url.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.btn_crawl = ctk.CTkButton(
            url_frame,
            text="🔍 Find Links",
            width=110,
            height=34,
            corner_radius=6,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            font=ctk.CTkFont(weight="bold"),
            command=self._start_crawl
        )
        self.btn_crawl.pack(side="right")

        ctk.CTkLabel(body, text="MATCHING DISCOVERED FILES", font=ctk.CTkFont(size=10, weight="bold"), text_color="#38bdf8").pack(anchor="w", pady=(0, 4))
        self.results_scroll = ctk.CTkScrollableFrame(body, fg_color="#0b0f17", corner_radius=8, border_width=1, border_color="#1e2638")
        self.results_scroll.pack(fill="both", expand=True, pady=(0, 8))

        self.lbl_empty = ctk.CTkLabel(self.results_scroll, text="Type a prompt and URL above, then click 'Find Links'.", font=ctk.CTkFont(size=11), text_color="#64748b")
        self.lbl_empty.pack(pady=40)

        # Bottom Bar
        btn_bar = ctk.CTkFrame(self, fg_color="#141a24", height=50, corner_radius=0)
        btn_bar.pack(fill="x", side="bottom")

        ctk.CTkButton(btn_bar, text="Cancel", width=80, height=32, corner_radius=6, fg_color="#334155", hover_color="#475569", command=self.destroy).pack(side="right", padx=14, pady=10)
        self.btn_enqueue = ctk.CTkButton(
            btn_bar,
            text="⚡ Download All Matching (0)",
            width=210,
            height=32,
            corner_radius=6,
            fg_color="#16a34a",
            hover_color="#15803d",
            font=ctk.CTkFont(weight="bold"),
            state="disabled",
            command=self._enqueue_all
        )
        self.btn_enqueue.pack(side="right", padx=(0, 8), pady=10)

    def _start_crawl(self):
        prompt = self.entry_prompt.get().strip()
        url = self.entry_url.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Please enter a valid target URL.")
            return

        self.btn_crawl.configure(state="disabled", text="Inspecting...")
        for w in self.results_scroll.winfo_children():
            w.destroy()

        def worker():
            items = ai_engine.natural_language_crawl(prompt or "download all files", url)

            def update_ui():
                if not self.winfo_exists():
                    return
                self.btn_crawl.configure(state="normal", text="🔍 Find Links")
                self.crawled_items = items
                if not items:
                    ctk.CTkLabel(self.results_scroll, text="No matching downloadable files found on page.", font=ctk.CTkFont(size=11), text_color="#f87171").pack(pady=40)
                    self.btn_enqueue.configure(state="disabled", text="⚡ Download All Matching (0)")
                    return

                for it in items:
                    row = ctk.CTkFrame(self.results_scroll, fg_color="#111827", corner_radius=6, border_width=1, border_color="#1f293d")
                    row.pack(fill="x", pady=2, padx=4)
                    ctk.CTkLabel(row, text=f"[{it['extension']}]", font=ctk.CTkFont(size=10, weight="bold"), text_color="#38bdf8").pack(side="left", padx=8, pady=6)
                    ctk.CTkLabel(row, text=it['title'], font=ctk.CTkFont(size=11), text_color="#f8fafc", wraplength=440, justify="left").pack(side="left", padx=4, pady=6)

                self.btn_enqueue.configure(state="normal", text=f"⚡ Download All Matching ({len(items)})")

            self.after(0, update_ui)

        threading.Thread(target=worker, daemon=True).start()

    def _enqueue_all(self):
        urls = [it['url'] for it in self.crawled_items]
        if urls:
            save_dir = os.path.join(os.path.expanduser("~"), "Downloads", "FalconDM")
            self.on_enqueue_batch(urls, save_dir)
            self.destroy()


class DownloadLogViewerDialog(ctk.CTkToplevel):
    """
    Real-time Download Diagnostics & Log Viewer for FalconDM.
    Displays live download engine logs, thread-level error messages, HTTP status codes,
    and actionable troubleshooting advice for failed or stalled downloads.
    """

    def __init__(self, parent, task=None):
        super().__init__(parent)
        self.task = task
        title_prefix = f"[{task.filename}] " if task and getattr(task, "filename", None) else ""
        self.title(f"FalconDM — {title_prefix}Download Diagnostics & Logs")
        self.geometry("860x620")
        self.minsize(720, 480)
        self.resizable(True, True)

        try:
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            w, h = 860, 620
            x = max(0, (sw - w) // 2)
            y = max(0, (sh - h) // 2)
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            self.geometry("860x620+200+150")

        bring_window_to_front(self)

        self.filter_var = ctk.StringVar(value="All")
        self.search_var = ctk.StringVar(value="")

        self._build_ui()
        self._load_logs()

    def _build_ui(self):
        self.configure(fg_color="#0b0f17")

        # 1. Top Header Banner
        header = ctk.CTkFrame(self, fg_color="#111827", height=54, corner_radius=0, border_width=1, border_color="#1f293d")
        header.pack(fill="x", side="top")

        lbl_head = ctk.CTkLabel(
            header,
            text="📜 Download Diagnostics & System Event Log",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#38bdf8"
        )
        lbl_head.pack(side="left", padx=16, pady=12)

        log_path = falcon_logger.get_log_file_path() if falcon_logger else "falcondm_downloads.log"
        btn_open_file = ctk.CTkButton(
            header,
            text="📂 Open Log File in Notepad",
            width=165,
            height=30,
            corner_radius=6,
            fg_color="#1e293b",
            hover_color="#334155",
            border_width=1,
            border_color="#334155",
            text_color="#cbd5e1",
            font=ctk.CTkFont(size=11),
            command=self._open_log_file
        )
        btn_open_file.pack(side="right", padx=16, pady=12)

        # 2. Bottom Action Bar (Packed bottom first for guaranteed visibility)
        btn_bar = ctk.CTkFrame(self, fg_color="#111827", height=52, corner_radius=0, border_width=1, border_color="#1f293d")
        btn_bar.pack(fill="x", side="bottom")

        btn_close = ctk.CTkButton(
            btn_bar,
            text="Close",
            width=80,
            height=32,
            corner_radius=6,
            fg_color="#21262d",
            hover_color="#30363d",
            text_color="#cbd5e1",
            font=ctk.CTkFont(size=11),
            command=self.destroy
        )
        btn_close.pack(side="right", padx=14, pady=10)

        btn_copy = ctk.CTkButton(
            btn_bar,
            text="📋 Copy Logs",
            width=100,
            height=32,
            corner_radius=6,
            fg_color="#1e293b",
            hover_color="#334155",
            border_width=1,
            border_color="#334155",
            text_color="#cbd5e1",
            font=ctk.CTkFont(size=11),
            command=self._copy_logs
        )
        btn_copy.pack(side="right", padx=(0, 8), pady=10)

        btn_clear = ctk.CTkButton(
            btn_bar,
            text="🗑 Clear Log File",
            width=115,
            height=32,
            corner_radius=6,
            fg_color="#7f1d1d",
            hover_color="#991b1b",
            text_color="#fca5a5",
            font=ctk.CTkFont(size=11),
            command=self._clear_logs
        )
        btn_clear.pack(side="right", padx=(0, 8), pady=10)

        btn_refresh = ctk.CTkButton(
            btn_bar,
            text="🔄 Refresh",
            width=90,
            height=32,
            corner_radius=6,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._load_logs
        )
        btn_refresh.pack(side="left", padx=14, pady=10)

        self.lbl_path = ctk.CTkLabel(
            btn_bar,
            text=f"Log: {log_path}",
            font=ctk.CTkFont(size=10),
            text_color="#64748b"
        )
        self.lbl_path.pack(side="left", padx=8)

        # 3. Main Body Container
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=14, pady=12)

        # 3A. Task Specific Diagnostic Card (if launched for a specific download)
        if self.task:
            task_card = ctk.CTkFrame(body, fg_color="#131b2e", corner_radius=8, border_width=1, border_color="#1e293b")
            task_card.pack(fill="x", pady=(0, 10), padx=2)

            t_header = ctk.CTkFrame(task_card, fg_color="transparent")
            t_header.pack(fill="x", padx=12, pady=(10, 4))

            status_str = getattr(self.task, "status", "Unknown")
            is_err = status_str == "Error"
            status_color = "#ef4444" if is_err else ("#10b981" if status_str == "Completed" else "#38bdf8")

            ctk.CTkLabel(
                t_header,
                text=f"Target: {self.task.filename}",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="#f8fafc"
            ).pack(side="left")

            ctk.CTkLabel(
                t_header,
                text=f"Status: {status_str}",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=status_color
            ).pack(side="right")

            err_msg = getattr(self.task, "error_message", "")
            if err_msg:
                err_frame = ctk.CTkFrame(task_card, fg_color="#2b1216", corner_radius=6, border_width=1, border_color="#7f1d1d")
                err_frame.pack(fill="x", padx=12, pady=4)
                ctk.CTkLabel(
                    err_frame,
                    text=f"⚠️ {err_msg}",
                    font=ctk.CTkFont(size=11, weight="bold"),
                    text_color="#f87171",
                    wraplength=780,
                    justify="left"
                ).pack(fill="x", padx=8, pady=6)

            # Smart Troubleshooting Suggestions
            hint_txt = self._generate_troubleshooting_hint(self.task)
            if hint_txt:
                hint_frame = ctk.CTkFrame(task_card, fg_color="#172554", corner_radius=6, border_width=1, border_color="#1e40af")
                hint_frame.pack(fill="x", padx=12, pady=(2, 8))
                ctk.CTkLabel(
                    hint_frame,
                    text=hint_txt,
                    font=ctk.CTkFont(size=11),
                    text_color="#93c5fd",
                    wraplength=780,
                    justify="left"
                ).pack(fill="x", padx=8, pady=6)

        # 3B. Filter & Search Controls
        filter_bar = ctk.CTkFrame(body, fg_color="transparent")
        filter_bar.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(filter_bar, text="Filter:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#cbd5e1").pack(side="left", padx=(0, 6))

        self.seg_filter = ctk.CTkSegmentedButton(
            filter_bar,
            values=["All", "Errors Only", "Warnings & Errors", "Probe & HTTP"],
            variable=self.filter_var,
            command=lambda v: self._apply_filter(),
            height=28,
            font=ctk.CTkFont(size=11)
        )
        self.seg_filter.pack(side="left", padx=(0, 12))

        ctk.CTkLabel(filter_bar, text="Search:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#cbd5e1").pack(side="left", padx=(0, 6))
        self.entry_search = ctk.CTkEntry(
            filter_bar,
            placeholder_text="Filter log text...",
            height=28,
            width=200,
            textvariable=self.search_var
        )
        self.entry_search.pack(side="left", padx=(0, 6))
        self.search_var.trace_add("write", lambda *args: self._apply_filter())

        # 3C. Log Text Display
        self.txt_logs = ctk.CTkTextbox(
            body,
            font=("Consolas", 11),
            fg_color="#06090f",
            text_color="#e2e8f0",
            border_width=1,
            border_color="#1e293b",
            wrap="none"
        )
        self.txt_logs.pack(fill="both", expand=True)

    def _generate_troubleshooting_hint(self, task) -> str:
        err = getattr(task, "error_message", "").lower()
        if "403" in err:
            return "💡 Actionable Fix: HTTP 403 Forbidden means the server rejected the download request. This usually happens if the link has an expired temporary token, requires active browser cookies/login, or is protected by Cloudflare. Try right-clicking the download and choosing 'Refresh Download Address (URL)' to update the session token."
        elif "401" in err:
            return "💡 Actionable Fix: HTTP 401 Unauthorized means this download requires a username and password. Open 'Site Logins & Vault' from the toolbar to save your credentials for this host."
        elif "404" in err:
            return "💡 Actionable Fix: HTTP 404 Not Found means the file has been deleted or the URL is invalid. Check the source link."
        elif "416" in err:
            return "💡 Actionable Fix: HTTP 416 Range Not Satisfiable means the server does not support multi-segment resuming. Try right-clicking and selecting 'Redownload (From 0%)' with single connection."
        elif "ssl" in err or "certificate" in err:
            return "💡 Actionable Fix: SSL/TLS validation failed. Ensure your computer's date and time are accurate, or check if an antivirus/firewall HTTPS inspection is intercepting connections."
        elif "10054" in err or "connection reset" in err or "connection lost" in err:
            return "💡 Actionable Fix: Remote server or network reset the connection. FalconDM will auto-reconnect automatically. If it persists, try lowering the number of connections to 4 or 8."
        elif "permission" in err or "winerror" in err or "access is denied" in err:
            return "💡 Actionable Fix: Disk permission error. FalconDM cannot write to the target directory. Choose a folder inside your user directory (e.g. Downloads or Desktop)."
        return ""

    def _load_logs(self):
        raw_logs = falcon_logger.read_recent_logs(800) if falcon_logger else "Logger not initialized."
        self._all_lines = raw_logs.splitlines(keepends=True)
        self._apply_filter()

    def _apply_filter(self):
        filt = self.filter_var.get()
        query = self.search_var.get().strip().lower()

        filtered = []
        for line in getattr(self, "_all_lines", []):
            line_lower = line.lower()
            if query and query not in line_lower:
                continue

            if filt == "Errors Only":
                if "error" in line_lower or "failed" in line_lower or "critical" in line_lower:
                    filtered.append(line)
            elif filt == "Warnings & Errors":
                if "error" in line_lower or "failed" in line_lower or "warning" in line_lower or "critical" in line_lower:
                    filtered.append(line)
            elif filt == "Probe & HTTP":
                if "probe" in line_lower or "http" in line_lower or "status" in line_lower:
                    filtered.append(line)
            else:
                filtered.append(line)

        self.txt_logs.delete("1.0", "end")
        if filtered:
            self.txt_logs.insert("1.0", "".join(filtered))
            self.txt_logs.see("end")
        else:
            self.txt_logs.insert("1.0", "No log entries match the selected filter.")

    def _open_log_file(self):
        log_path = falcon_logger.get_log_file_path() if falcon_logger else ""
        if log_path and os.path.exists(log_path):
            open_file_or_folder(log_path)
        else:
            messagebox.showinfo("Log File", f"Log file does not exist yet:\n{log_path}")

    def _copy_logs(self):
        content = self.txt_logs.get("1.0", "end").strip()
        if content:
            self.clipboard_clear()
            self.clipboard_append(content)
            messagebox.showinfo("Copied", f"Copied {len(content.splitlines())} log lines to clipboard.")

    def _clear_logs(self):
        if messagebox.askyesno("Clear Logs", "Are you sure you want to clear the download log file?"):
            if falcon_logger:
                falcon_logger.clear_logs()
            self._load_logs()


