import os
import subprocess
import time
import threading
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from typing import Optional

try:
    from ..core.platform_utils import open_file_or_folder, bring_window_to_front
    from ..core.config_manager import config_store, THEME_PALETTES
    from ..core.hasher import compute_checksums
    from ..core.antivirus_scanner import AntivirusScanner
except (ImportError, ValueError):
    from core.platform_utils import open_file_or_folder, bring_window_to_front
    from core.config_manager import config_store, THEME_PALETTES
    from core.hasher import compute_checksums
    from core.antivirus_scanner import AntivirusScanner

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


class FloatingDownloadDialog(ctk.CTkToplevel):
    """The iconic IDM floating per-download status monitor window with live connection thread matrix."""

    def __init__(self, parent, task):
        super().__init__(parent)
        self.task = task
        self.title(f"{task.filename} - FalconDM Turbo Download")
        self.geometry("660x540")
        self.minsize(580, 480)
        self.resizable(True, True)

        # Center on primary monitor (cross-platform)
        try:
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            w, h = 660, 540
            x = max(0, (sw - w) // 2)
            y = max(0, (sh - h) // 2)
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            self.geometry("660x540+300+200")

        bring_window_to_front(self)

        self.auto_close = ctk.BooleanVar(value=False)
        self.shutdown_on_complete = ctk.BooleanVar(value=False)
        self.open_when_done = ctk.BooleanVar(value=False)
        self.play_chime = ctk.BooleanVar(value=True)
        self._chime_played = False
        self.speed_history = [0.0] * 35
        self.peak_speed_seen = 0.0
        self._computed_sha256 = ""
        self._computed_md5 = ""
        self._hash_thread_started = False
        self._completion_card_shown = False

        self._build_ui()
        self._start_tick()

    def get_theme_palette(self) -> dict:
        try:
            theme_name = config_store.get("ui_theme_accent", "Cyberpunk Cyan")
            return THEME_PALETTES.get(theme_name, THEME_PALETTES["Cyberpunk Cyan"])
        except Exception:
            return {
                "primary": "#0284c7",
                "primary_hover": "#0369a1",
                "accent": "#38bdf8",
                "badge_bg": "#082f49",
                "badge_text": "#38bdf8",
                "graph_fill": "#082f49",
                "graph_line": "#38bdf8"
            }

    def _build_ui(self):
        palette = self.get_theme_palette()
        # 1. Header Banner (Packed Top)
        header = ctk.CTkFrame(self, fg_color="#0b0f19", height=48, corner_radius=0, border_width=1, border_color="#1e293b")
        header.pack(fill="x", side="top")
        
        self.lbl_head = ctk.CTkLabel(
            header,
            text=f"⚡ FalconDM Turbo Download ({getattr(self.task, 'num_connections', 8)} Connections)",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=palette.get("accent", "#38bdf8")
        )
        self.lbl_head.pack(side="left", padx=16, pady=10)

        # 2. Bottom Action Bar (PACKED FIRST AT BOTTOM TO GUARANTEE VISIBILITY)
        btn_bar = ctk.CTkFrame(self, fg_color="#0b0f19", height=54, corner_radius=0, border_width=1, border_color="#1e293b")
        btn_bar.pack(fill="x", side="bottom")

        # Start / Resume / Pause Button
        self.btn_pause = ctk.CTkButton(
            btn_bar,
            text="⏸ Pause",
            width=110,
            height=32,
            corner_radius=6,
            fg_color="#451a03",
            hover_color="#78350f",
            border_width=1,
            border_color="#d97706",
            text_color="#fcd34d",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._toggle_pause
        )
        self.btn_pause.pack(side="left", padx=(14, 6), pady=11)

        # Cancel Button
        self.btn_cancel = ctk.CTkButton(
            btn_bar,
            text="✕ Cancel",
            width=90,
            height=32,
            corner_radius=6,
            fg_color="#450a0a",
            hover_color="#7f1d1d",
            border_width=1,
            border_color="#dc2626",
            text_color="#fca5a5",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._cancel
        )
        self.btn_cancel.pack(side="left", padx=4, pady=11)

        # Diagnostics & Error Log Button
        self.btn_view_log = ctk.CTkButton(
            btn_bar,
            text="📜 Log",
            width=80,
            height=32,
            corner_radius=6,
            fg_color="#111827",
            hover_color="#1f2937",
            border_width=1,
            border_color="#374151",
            text_color="#e5e7eb",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._open_log
        )
        self.btn_view_log.pack(side="left", padx=4, pady=11)

        # Checksum / Security Button
        self.btn_security = ctk.CTkButton(
            btn_bar,
            text="🛡️ Checksum",
            width=100,
            height=32,
            corner_radius=6,
            fg_color="#064e3b",
            hover_color="#047857",
            border_width=1,
            border_color="#10b981",
            text_color="#34d399",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._toggle_security_card
        )
        self.btn_security.pack(side="left", padx=4, pady=11)

        # Preview in VLC / Media Player Button (appears when streamable)
        self.btn_preview = ctk.CTkButton(
            btn_bar,
            text="🎬 Play in VLC",
            width=115,
            height=32,
            corner_radius=6,
            fg_color="#8b5cf6",
            hover_color="#7c3aed",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._launch_preview
        )

        # Open File Button (appears when finished)
        self.btn_open_file = ctk.CTkButton(
            btn_bar,
            text="🚀 Open File",
            width=100,
            height=32,
            corner_radius=6,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._open_file
        )
        # Open Folder Button (appears when finished)
        self.btn_open_folder = ctk.CTkButton(
            btn_bar,
            text="📂 Open Folder",
            width=110,
            height=32,
            corner_radius=6,
            fg_color="#334155",
            hover_color="#475569",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._open_folder
        )

        # Hide to background button
        btn_hide = ctk.CTkButton(
            btn_bar,
            text="Hide to Background",
            width=135,
            height=32,
            corner_radius=6,
            fg_color="#1e293b",
            hover_color="#334155",
            text_color="#cbd5e1",
            font=ctk.CTkFont(size=11),
            command=self.destroy
        )
        btn_hide.pack(side="right", padx=14, pady=11)

        # 3. Automation Checkboxes (Packed bottom above action bar)
        opts_frame = ctk.CTkFrame(self, fg_color="transparent")
        opts_frame.pack(fill="x", side="bottom", padx=16, pady=(2, 6))

        ctk.CTkCheckBox(opts_frame, text="Close when done", variable=self.auto_close, font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 12))
        ctk.CTkCheckBox(opts_frame, text="Open file when finished", variable=self.open_when_done, font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 12))
        ctk.CTkCheckBox(opts_frame, text="Audio chime", variable=self.play_chime, font=ctk.CTkFont(size=11), text_color="#38bdf8").pack(side="left", padx=(0, 12))
        ctk.CTkCheckBox(opts_frame, text="Shutdown PC when done", variable=self.shutdown_on_complete, font=ctk.CTkFont(size=11), text_color="#f87171").pack(side="left")

        # 4. Speed Limiter & Direct Actions Row (Packed bottom above options)
        speed_frame = ctk.CTkFrame(self, fg_color="transparent")
        speed_frame.pack(fill="x", side="bottom", padx=16, pady=(4, 6))

        ctk.CTkLabel(speed_frame, text="Speed Limit:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#94a3b8").pack(side="left", padx=(0, 8))
        self.combo_speed = ctk.CTkComboBox(
            speed_frame,
            values=["Unlimited", "256 KB/s", "512 KB/s", "1 MB/s", "2 MB/s", "5 MB/s", "10 MB/s"],
            width=120,
            height=28,
            corner_radius=6,
            fg_color="#141a24",
            button_color="#1e293b",
            border_color="#1f2737",
            text_color="#f8fafc",
            dropdown_fg_color="#141a24",
            command=self._on_change_speed_limit
        )
        current_limit = getattr(self.task, "speed_limit_bps", 0)
        limit_text = "Unlimited"
        if current_limit > 0:
            if current_limit >= 1024 * 1024:
                limit_text = f"{current_limit // (1024 * 1024)} MB/s"
            else:
                limit_text = f"{current_limit // 1024} KB/s"
        self.combo_speed.set(limit_text)
        self.combo_speed.pack(side="left")

        # Inline Quick Actions right beside Speed Limit
        self.btn_speed_cancel = ctk.CTkButton(
            speed_frame,
            text="✕ Cancel",
            width=76,
            height=28,
            corner_radius=6,
            fg_color="#450a0a",
            hover_color="#7f1d1d",
            border_width=1,
            border_color="#dc2626",
            text_color="#fca5a5",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._cancel
        )
        self.btn_speed_cancel.pack(side="right", padx=(4, 0))

        self.btn_speed_resume = ctk.CTkButton(
            speed_frame,
            text="⏸ Pause",
            width=100,
            height=28,
            corner_radius=6,
            fg_color="#451a03",
            hover_color="#78350f",
            border_width=1,
            border_color="#d97706",
            text_color="#fcd34d",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._toggle_pause
        )
        self.btn_speed_resume.pack(side="right", padx=(0, 4))

        # 5. Main Details Card (Packed Top)
        card = ctk.CTkFrame(self, fg_color="#0b0f19", corner_radius=10, border_width=1, border_color="#1e293b")
        card.pack(fill="x", side="top", padx=14, pady=(10, 8))

        # File name row
        row1 = ctk.CTkFrame(card, fg_color="transparent")
        row1.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(row1, text="File Name:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#94a3b8", width=80, anchor="w").pack(side="left")
        self.lbl_fname = ctk.CTkLabel(row1, text=self.task.filename, font=ctk.CTkFont(size=12, weight="bold"), text_color="#f8fafc", anchor="w")
        self.lbl_fname.pack(side="left", fill="x", expand=True)

        # Status row
        row2 = ctk.CTkFrame(card, fg_color="transparent")
        row2.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(row2, text="Status:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#94a3b8", width=80, anchor="w").pack(side="left")
        self.lbl_status = ctk.CTkLabel(row2, text=self.task.status, font=ctk.CTkFont(size=11, weight="bold"), text_color="#38bdf8", anchor="w")
        self.lbl_status.pack(side="left")

        # Big Progress Bar
        self.prog_bar = ctk.CTkProgressBar(card, height=16, corner_radius=6, progress_color="#4f46e5", fg_color="#070a12")
        self.prog_bar.pack(fill="x", padx=12, pady=(8, 4))
        self.prog_bar.set(0)

        # Progress Stats Grid
        stats_frame = ctk.CTkFrame(card, fg_color="transparent")
        stats_frame.pack(fill="x", padx=12, pady=(4, 10))

        # Left stats: Downloaded / Size
        self.lbl_downloaded = ctk.CTkLabel(stats_frame, text="0 B / 0 B (0%)", font=ctk.CTkFont(size=11), text_color="#cbd5e1")
        self.lbl_downloaded.pack(side="left")

        # Right stats: Speed & ETA
        self.lbl_speed_eta = ctk.CTkLabel(stats_frame, text="Speed: 0.0 KB/s | Time Left: --:--:--", font=ctk.CTkFont(size=11, weight="bold"), text_color="#34d399")
        self.lbl_speed_eta.pack(side="right")

        # 5b. Real-Time Cyber Speed Waveform HUD
        graph_box = ctk.CTkFrame(self, fg_color="#060910", corner_radius=10, border_width=1, border_color="#1e293b", height=82)
        graph_box.pack(fill="x", side="top", padx=14, pady=(0, 8))
        graph_box.pack_propagate(False)

        top_graph_bar = ctk.CTkFrame(graph_box, fg_color="transparent", height=18)
        top_graph_bar.pack(fill="x", padx=10, pady=(4, 0))
        ctk.CTkLabel(top_graph_bar, text="BANDWIDTH THROUGHPUT", font=ctk.CTkFont(size=9, weight="bold"), text_color="#64748b").pack(side="left")
        self.lbl_peak_speed_graph = ctk.CTkLabel(top_graph_bar, text="Peak: 0.0 KB/s", font=ctk.CTkFont(size=9, weight="bold"), text_color="#34d399")
        self.lbl_peak_speed_graph.pack(side="right")

        self.speed_canvas = tk.Canvas(graph_box, bg="#060910", highlightthickness=0, height=54)
        self.speed_canvas.pack(fill="both", expand=True, padx=6, pady=(0, 4))

        # 5c. IDM-Style Segment Thread Matrix Visualizer
        seg_box = ctk.CTkFrame(self, fg_color="#060910", corner_radius=10, border_width=1, border_color="#1e293b", height=42)
        seg_box.pack(fill="x", side="top", padx=14, pady=(0, 6))
        seg_box.pack_propagate(False)

        top_seg_bar = ctk.CTkFrame(seg_box, fg_color="transparent", height=14)
        top_seg_bar.pack(fill="x", padx=10, pady=(2, 0))
        ctk.CTkLabel(top_seg_bar, text="SEGMENTED FILE MAP (IDM MULTI-THREAD MATRIX)", font=ctk.CTkFont(size=9, weight="bold"), text_color="#64748b").pack(side="left")
        self.lbl_stream_count_hud = ctk.CTkLabel(top_seg_bar, text=f"{len(getattr(self.task, 'segments', []))} Streams", font=ctk.CTkFont(size=9, weight="bold"), text_color="#38bdf8")
        self.lbl_stream_count_hud.pack(side="right")

        self.segment_canvas = tk.Canvas(seg_box, bg="#060910", highlightthickness=0, height=18)
        self.segment_canvas.pack(fill="both", expand=True, padx=6, pady=(0, 4))

        # 6. Connection Threads Chunk Monitor Table (Expands in remaining middle space)
        lbl_chunk = ctk.CTkLabel(self, text="ACTIVE CONNECTION THREADS", font=ctk.CTkFont(size=9, weight="bold"), text_color="#64748b")
        lbl_chunk.pack(anchor="w", side="top", padx=16, pady=(2, 2))

        self.table_scroll = ctk.CTkScrollableFrame(self, fg_color="#0d121c", height=120, corner_radius=8, border_width=1, border_color="#1f2737")
        self.table_scroll.pack(fill="both", expand=True, side="top", padx=14, pady=(0, 6))

        # 7. File Integrity & Security Suite Card (Shown when completed or toggled)
        self.card_security = ctk.CTkFrame(self, fg_color="#0b0f19", corner_radius=10, border_width=1, border_color="#10b981")

        sec_head = ctk.CTkFrame(self.card_security, fg_color="transparent")
        sec_head.pack(fill="x", padx=14, pady=(8, 4))
        ctk.CTkLabel(
            sec_head,
            text="🛡️ CRYPTOGRAPHIC INTEGRITY & SECURITY SUITE",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#10b981"
        ).pack(side="left")

        btn_show_threads = ctk.CTkButton(
            sec_head,
            text="📊 View Thread Map",
            width=120,
            height=24,
            corner_radius=4,
            fg_color="#1e293b",
            hover_color="#334155",
            font=ctk.CTkFont(size=10),
            command=self._toggle_security_card
        )
        btn_show_threads.pack(side="right")

        h_frame = ctk.CTkFrame(self.card_security, fg_color="#070b12", corner_radius=8, border_width=1, border_color="#1e293b")
        h_frame.pack(fill="x", padx=14, pady=(0, 6))

        # SHA-256 Row
        sha_row = ctk.CTkFrame(h_frame, fg_color="transparent")
        sha_row.pack(fill="x", padx=10, pady=(6, 3))
        ctk.CTkLabel(sha_row, text="SHA-256:", font=ctk.CTkFont(size=10, weight="bold"), text_color="#94a3b8", width=65, anchor="w").pack(side="left")
        self.lbl_sha256 = ctk.CTkLabel(sha_row, text="Calculating cryptographic hash...", font=ctk.CTkFont(family="Consolas", size=9), text_color="#cbd5e1", anchor="w")
        self.lbl_sha256.pack(side="left", fill="x", expand=True)
        self.btn_copy_sha = ctk.CTkButton(sha_row, text="📋 Copy", width=60, height=22, font=ctk.CTkFont(size=10), command=self._copy_sha256)
        self.btn_copy_sha.pack(side="right")

        # MD5 Row
        md5_row = ctk.CTkFrame(h_frame, fg_color="transparent")
        md5_row.pack(fill="x", padx=10, pady=(0, 6))
        ctk.CTkLabel(md5_row, text="MD5:", font=ctk.CTkFont(size=10, weight="bold"), text_color="#94a3b8", width=65, anchor="w").pack(side="left")
        self.lbl_md5 = ctk.CTkLabel(md5_row, text="Calculating...", font=ctk.CTkFont(family="Consolas", size=9), text_color="#cbd5e1", anchor="w")
        self.lbl_md5.pack(side="left", fill="x", expand=True)
        self.btn_copy_md5 = ctk.CTkButton(md5_row, text="📋 Copy", width=60, height=22, font=ctk.CTkFont(size=10), command=self._copy_md5)
        self.btn_copy_md5.pack(side="right")

        # Verify & AV Row
        verify_card = ctk.CTkFrame(self.card_security, fg_color="#070b12", corner_radius=8, border_width=1, border_color="#1e293b")
        verify_card.pack(fill="x", padx=14, pady=(0, 6))

        val_row = ctk.CTkFrame(verify_card, fg_color="transparent")
        val_row.pack(fill="x", padx=10, pady=(6, 6))

        self.entry_compare_hash = ctk.CTkEntry(
            val_row,
            placeholder_text="Paste expected SHA256 or MD5 hash to verify match...",
            height=28,
            font=ctk.CTkFont(family="Consolas", size=10),
            fg_color="#0b0f19",
            border_color="#1e293b"
        )
        self.entry_compare_hash.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry_compare_hash.bind("<KeyRelease>", self._check_hash_match)

        self.lbl_hash_match_badge = ctk.CTkLabel(
            val_row,
            text="",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#94a3b8",
            width=115
        )
        self.lbl_hash_match_badge.pack(side="left", padx=(0, 8))

        self.btn_scan_av = ctk.CTkButton(
            val_row,
            text="🛡️ Scan Antivirus",
            width=120,
            height=28,
            corner_radius=6,
            fg_color="#1e293b",
            hover_color="#334155",
            font=ctk.CTkFont(size=10, weight="bold"),
            command=self._run_av_scan
        )
        self.btn_scan_av.pack(side="right")

        self.thread_rows = []
        self._sync_buttons()

    def _on_change_speed_limit(self, choice: str):
        speed_map = {
            "Unlimited": 0,
            "256 KB/s": 256 * 1024,
            "512 KB/s": 512 * 1024,
            "1 MB/s": 1024 * 1024,
            "2 MB/s": 2 * 1024 * 1024,
            "5 MB/s": 5 * 1024 * 1024,
            "10 MB/s": 10 * 1024 * 1024,
        }
        bps = speed_map.get(choice, 0)
        if hasattr(self.task, "set_speed_limit"):
            self.task.set_speed_limit(bps)

    def _launch_preview(self):
        if hasattr(self.task, "launch_preview"):
            self.task.launch_preview()
        else:
            try:
                from core.platform_utils import launch_in_media_player
                launch_in_media_player(self.task.save_path)
            except Exception:
                pass

    def _sync_buttons(self):
        st = getattr(self.task, "status", "")
        if st == "Downloading":
            # Running state -> Show Pause
            if hasattr(self, 'btn_pause') and self.btn_pause.winfo_exists():
                self.btn_pause.configure(text="⏸ Pause", fg_color="#f59e0b", hover_color="#d97706")
            if hasattr(self, 'btn_speed_resume') and self.btn_speed_resume.winfo_exists():
                self.btn_speed_resume.configure(text="⏸ Pause", fg_color="#f59e0b", hover_color="#d97706")
            if hasattr(self, 'btn_cancel') and self.btn_cancel.winfo_exists():
                self.btn_cancel.configure(text="✕ Cancel", fg_color="#ef4444", hover_color="#dc2626")
            if hasattr(self, 'btn_speed_cancel') and self.btn_speed_cancel.winfo_exists():
                self.btn_speed_cancel.configure(text="✕ Cancel", fg_color="#ef4444", hover_color="#dc2626")
            if hasattr(self, 'btn_open_file') and self.btn_open_file.winfo_exists():
                self.btn_open_file.pack_forget()
            if hasattr(self, 'btn_open_folder') and self.btn_open_folder.winfo_exists():
                self.btn_open_folder.pack_forget()

        # Update Live Preview in VLC button
        if hasattr(self, 'btn_preview') and self.btn_preview.winfo_exists():
            can_preview = hasattr(self.task, "can_preview_media") and self.task.can_preview_media()
            if can_preview and st != "Completed":
                self.btn_preview.pack(side="left", padx=4, pady=11)
            else:
                self.btn_preview.pack_forget()

        elif st == "Completed":
            # Completed state -> Show Open File and Open Folder
            palette = self.get_theme_palette()
            if hasattr(self, 'btn_pause') and self.btn_pause.winfo_exists():
                self.btn_pause.configure(text="🚀 Open File", fg_color=palette.get("primary", "#2563eb"), hover_color=palette.get("primary_hover", "#1d4ed8"))
            if hasattr(self, 'btn_speed_resume') and self.btn_speed_resume.winfo_exists():
                self.btn_speed_resume.configure(text="🚀 Open File", fg_color=palette.get("primary", "#2563eb"), hover_color=palette.get("primary_hover", "#1d4ed8"))
            if hasattr(self, 'btn_cancel') and self.btn_cancel.winfo_exists():
                self.btn_cancel.configure(text="📂 Open Folder", fg_color="#334155", hover_color="#475569")
            if hasattr(self, 'btn_speed_cancel') and self.btn_speed_cancel.winfo_exists():
                self.btn_speed_cancel.configure(text="📂 Open Folder", fg_color="#334155", hover_color="#475569")

            # Auto-reveal Integrity & Security Card upon download completion
            if not getattr(self, "_completion_card_shown", False):
                self._completion_card_shown = True
                if hasattr(self, 'table_scroll') and self.table_scroll.winfo_ismapped():
                    self.table_scroll.pack_forget()
                if hasattr(self, 'card_security') and not self.card_security.winfo_ismapped():
                    self.card_security.pack(fill="both", expand=True, side="top", padx=14, pady=(0, 6))
                self._start_hash_calculation()

        else:
            # Paused / Queued / Error / Canceled -> Show Start/Resume
            if hasattr(self, 'btn_pause') and self.btn_pause.winfo_exists():
                self.btn_pause.configure(text="▶ Start / Resume", fg_color="#10b981", hover_color="#059669")
            if hasattr(self, 'btn_speed_resume') and self.btn_speed_resume.winfo_exists():
                self.btn_speed_resume.configure(text="▶ Start / Resume", fg_color="#10b981", hover_color="#059669")
            if hasattr(self, 'btn_cancel') and self.btn_cancel.winfo_exists():
                self.btn_cancel.configure(text="✕ Cancel", fg_color="#ef4444", hover_color="#dc2626")
            if hasattr(self, 'btn_speed_cancel') and self.btn_speed_cancel.winfo_exists():
                self.btn_speed_cancel.configure(text="✕ Cancel", fg_color="#ef4444", hover_color="#dc2626")
            if hasattr(self, 'btn_open_file') and self.btn_open_file.winfo_exists():
                self.btn_open_file.pack_forget()
            if hasattr(self, 'btn_open_folder') and self.btn_open_folder.winfo_exists():
                self.btn_open_folder.pack_forget()

        # Update Live Preview in VLC button
        if hasattr(self, 'btn_preview') and self.btn_preview.winfo_exists():
            can_preview = hasattr(self.task, "can_preview_media") and self.task.can_preview_media()
            if can_preview and st != "Completed":
                self.btn_preview.pack(side="left", padx=4, pady=11)
            else:
                self.btn_preview.pack_forget()

        # Update Log button styling on error
        if hasattr(self, 'btn_view_log') and self.btn_view_log.winfo_exists():
            if st in ("Error", "Auto-reconnecting"):
                self.btn_view_log.configure(text="⚠️ Error Log", fg_color="#ef4444", hover_color="#dc2626")
            else:
                self.btn_view_log.configure(text="📜 Log", fg_color="#334155", hover_color="#475569")

    def _open_log(self):
        try:
            from gui.dialogs import DownloadLogViewerDialog
            DownloadLogViewerDialog(self, task=self.task)
        except Exception:
            try:
                from .dialogs import DownloadLogViewerDialog
                DownloadLogViewerDialog(self, task=self.task)
            except Exception:
                pass

    def _toggle_pause(self):
        mgr = getattr(self.master, "manager", None)
        if self.task.status == "Downloading":
            # Pause task
            if mgr and hasattr(mgr, "pause_task"):
                mgr.pause_task(self.task.task_id)
            else:
                self.task.pause()
        elif self.task.status == "Completed":
            # Already completed, open the file
            self._open_file()
            return
        else:
            # Start or resume task
            if mgr and hasattr(mgr, "resume_task"):
                mgr.resume_task(self.task.task_id)
            else:
                self.task.start()

        refresh_fn = getattr(self.master, "_refresh_table", None)
        if callable(refresh_fn):
            try:
                refresh_fn()
            except Exception:
                pass
        self._sync_buttons()

    def _cancel(self):
        if self.task.status == "Completed":
            self._open_folder()
            return

        mgr = getattr(self.master, "manager", None)
        if mgr and hasattr(mgr, "remove_task"):
            mgr.remove_task(self.task.task_id, delete_file=False)
        else:
            self.task.cancel()

        refresh_fn = getattr(self.master, "_refresh_table", None)
        if callable(refresh_fn):
            try:
                refresh_fn()
            except Exception:
                pass
        self.destroy()

    def _open_file(self):
        if os.path.exists(self.task.save_path):
            try:
                os.startfile(self.task.save_path)
            except Exception:
                pass

    def _open_folder(self):
        target_path = os.path.abspath(self.task.save_path)
        folder = os.path.dirname(target_path)
        if os.path.exists(target_path):
            open_file_or_folder(target_path, select=True)
        elif os.path.exists(folder):
            open_file_or_folder(folder)

    def _toggle_security_card(self):
        if getattr(self, "card_security", None) and self.card_security.winfo_ismapped():
            self.card_security.pack_forget()
            if hasattr(self, 'table_scroll'):
                self.table_scroll.pack(fill="both", expand=True, side="top", padx=14, pady=(0, 6))
        else:
            if hasattr(self, 'table_scroll') and self.table_scroll.winfo_ismapped():
                self.table_scroll.pack_forget()
            if hasattr(self, 'card_security'):
                self.card_security.pack(fill="both", expand=True, side="top", padx=14, pady=(0, 6))
            self._start_hash_calculation()

    def _copy_sha256(self):
        val = getattr(self, "_computed_sha256", "")
        if val:
            self.clipboard_clear()
            self.clipboard_append(val)
            self.btn_copy_sha.configure(text="✓ Copied!")
            self.after(1500, lambda: self.btn_copy_sha.configure(text="📋 Copy"))

    def _copy_md5(self):
        val = getattr(self, "_computed_md5", "")
        if val:
            self.clipboard_clear()
            self.clipboard_append(val)
            self.btn_copy_md5.configure(text="✓ Copied!")
            self.after(1500, lambda: self.btn_copy_md5.configure(text="📋 Copy"))

    def _check_hash_match(self, event=None):
        expected = self.entry_compare_hash.get().strip().lower()
        if not expected:
            self.lbl_hash_match_badge.configure(text="", text_color="#94a3b8")
            self.entry_compare_hash.configure(border_color="#1e293b")
            return
        cur_sha = getattr(self, "_computed_sha256", "").lower()
        cur_md5 = getattr(self, "_computed_md5", "").lower()
        if (expected in (cur_sha, cur_md5)) and (cur_sha or cur_md5):
            self.lbl_hash_match_badge.configure(text="✓ Validated!", text_color="#10b981")
            self.entry_compare_hash.configure(border_color="#10b981")
        else:
            self.lbl_hash_match_badge.configure(text="✕ Mismatch", text_color="#ef4444")
            self.entry_compare_hash.configure(border_color="#ef4444")

    def _run_av_scan(self):
        if not os.path.exists(self.task.save_path):
            return
        self.btn_scan_av.configure(text="Scanning...", state="disabled")
        def worker():
            res = AntivirusScanner.scan_file(self.task.save_path)
            def update():
                self.btn_scan_av.configure(state="normal")
                if res.get("clean"):
                    self.btn_scan_av.configure(text="✅ Clean File", fg_color="#064e3b", text_color="#34d399")
                else:
                    self.btn_scan_av.configure(text="⚠️ Threat Found", fg_color="#7f1d1d", text_color="#fca5a5")
            self.after(0, update)
        threading.Thread(target=worker, daemon=True).start()

    def _start_hash_calculation(self):
        if getattr(self, "_hash_thread_started", False):
            return
        if not os.path.exists(self.task.save_path):
            return
        self._hash_thread_started = True

        def calc():
            try:
                res = compute_checksums(self.task.save_path, ['sha256', 'md5'])
                sha = res.get('sha256', '')
                md5 = res.get('md5', '')
                self._computed_sha256 = sha
                self._computed_md5 = md5

                def apply():
                    if hasattr(self, 'lbl_sha256') and self.lbl_sha256.winfo_exists():
                        self.lbl_sha256.configure(text=sha or "N/A")
                    if hasattr(self, 'lbl_md5') and self.lbl_md5.winfo_exists():
                        self.lbl_md5.configure(text=md5 or "N/A")
                    self._check_hash_match()

                self.after(0, apply)
            except Exception:
                pass

        threading.Thread(target=calc, daemon=True).start()

    def _draw_speed_graph(self):
        c = getattr(self, "speed_canvas", None)
        if not c or not c.winfo_exists():
            return
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 20 or h < 15:
            return

        max_spd = max(self.speed_history) if self.speed_history else 1.0
        if max_spd <= 0:
            max_spd = 1.0

        n = len(self.speed_history)
        points = []
        for i, val in enumerate(self.speed_history):
            x = (i / max(1, n - 1)) * (w - 12) + 6
            ratio = min(1.0, val / max_spd) if max_spd > 0 else 0
            y = (h - 6) - (ratio * (h - 16))
            points.append((x, y))

        palette = self.get_theme_palette()

        # Cyber Grid Lines
        for r, color in [(0.33, "#131c2a"), (0.66, "#182436")]:
            gy = (h - 6) - (r * (h - 16))
            c.create_line(6, gy, w - 6, gy, fill=color, dash=(2, 4))

        # Filled gradient polygon
        if len(points) >= 2:
            poly = [6, h - 4]
            for pt in points:
                poly.extend(pt)
            poly.extend([w - 6, h - 4])
            c.create_polygon(poly, fill=palette.get("graph_fill", "#0c1e38"), outline="")

            # Glowing neon curve
            flat_pts = [coord for pt in points for coord in pt]
            c.create_line(flat_pts, fill=palette.get("primary", "#1d4ed8"), width=3, smooth=True)
            c.create_line(flat_pts, fill=palette.get("graph_line", "#38bdf8"), width=1.5, smooth=True)

            # Glowing lead pulse point
            last_x, last_y = points[-1]
            c.create_oval(last_x - 3.5, last_y - 3.5, last_x + 3.5, last_y + 3.5, fill=palette.get("accent", "#38bdf8"), outline="#ffffff", width=1)

    def _draw_segment_matrix(self):
        c = getattr(self, "segment_canvas", None)
        if not c or not c.winfo_exists():
            return
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 20 or h < 8:
            return

        segments = getattr(self.task, "segments", [])
        total_size = getattr(self.task, "file_size", 0)

        # Background base track
        c.create_rectangle(1, 1, w - 1, h - 1, fill="#070b12", outline="#1e293b", width=1)

        palette = self.get_theme_palette()

        if not segments or total_size <= 0:
            prog = getattr(self.task, "progress_pct", 0.0) / 100.0
            fill_w = max(2, int((w - 4) * prog))
            c.create_rectangle(2, 2, 2 + fill_w, h - 2, fill=palette.get("primary", "#0284c7"), outline="")
            return

        pad_x = 2
        pad_y = 2
        draw_w = max(10, w - (pad_x * 2))
        draw_h = max(4, h - (pad_y * 2))

        for seg in segments:
            x0 = pad_x + (seg.start / total_size) * draw_w
            x1 = pad_x + ((seg.end + 1) / total_size) * draw_w
            xc = pad_x + (seg.current / total_size) * draw_w

            # Unfinished track segment
            c.create_rectangle(x0, pad_y, x1, pad_y + draw_h, fill="#0d1522", outline="")

            # Downloaded portion
            if xc > x0:
                is_done = seg.status == "completed" or seg.current > seg.end
                fill_color = "#10b981" if is_done else palette.get("primary", "#0284c7")
                c.create_rectangle(x0, pad_y, min(x1, xc), pad_y + draw_h, fill=fill_color, outline="")

            # Active download head glow sliver
            if seg.status == "downloading" and xc < x1:
                head_x = min(x1 - 1, xc)
                c.create_line(head_x, pad_y, head_x, pad_y + draw_h, fill=palette.get("accent", "#38bdf8"), width=2)
                c.create_line(head_x - 1, pad_y, head_x - 1, pad_y + draw_h, fill="#ffffff", width=1)

            # Segment boundary divider
            c.create_line(x1, pad_y, x1, pad_y + draw_h, fill="#1e293b", width=1)

    def _start_tick(self):
        def update_loop():
            if not self.winfo_exists():
                return

            # When minimized, sleep longer and skip drawing graphics
            if getattr(self, "state", lambda: "normal")() == "iconic":
                self.after(1000, update_loop)
                return

            palette = self.get_theme_palette()
            latency = getattr(self.task, "latency_ms", 0.0)
            conn_count = getattr(self.task, 'num_connections', 8)
            head_str = f"⚡ FalconDM Turbo Download ({conn_count} Connections"
            if latency > 0:
                head_str += f" • {latency:.0f}ms Ping"
            head_str += ")"
            if hasattr(self, 'lbl_head') and self.lbl_head.winfo_exists():
                self.lbl_head.configure(text=head_str, text_color=palette.get("accent", "#38bdf8"))

            self.lbl_fname.configure(text=self.task.filename)

            if getattr(self.task, "status", "") == "Auto-reconnecting":
                msg = getattr(self.task, "error_message", "Auto-reconnecting...")
                self.lbl_status.configure(text=msg, text_color="#f59e0b")
            elif getattr(self.task, "status", "") == "Error":
                self.lbl_status.configure(text=f"Error: {self.task.error_message}", text_color="#ef4444")
            elif getattr(self.task, "status", "") == "Completed":
                self.lbl_status.configure(text="Completed", text_color="#10b981")
            else:
                self.lbl_status.configure(text=self.task.status, text_color=palette.get("accent", "#38bdf8"))
            
            prog = getattr(self.task, "progress_pct", 0.0) / 100.0
            self.prog_bar.configure(progress_color=palette.get("primary", "#0284c7"))
            self.prog_bar.set(prog)

            size_str = format_bytes(self.task.file_size) if self.task.file_size > 0 else "Unknown"
            dl_str = format_bytes(self.task.downloaded_bytes)
            self.lbl_downloaded.configure(text=f"{dl_str} of {size_str} ({getattr(self.task, 'progress_pct', 0.0):.1f}%)")

            speed_str = format_speed(self.task.speed_bps)
            eta_str = format_time(self.task.eta_seconds)
            self.lbl_speed_eta.configure(text=f"Speed: {speed_str} | Time Left: {eta_str}")

            # Update live speed waveform
            self.speed_history.append(self.task.speed_bps)
            if len(self.speed_history) > 35:
                self.speed_history.pop(0)
            if self.task.speed_bps > self.peak_speed_seen:
                self.peak_speed_seen = self.task.speed_bps
            if hasattr(self, "lbl_peak_speed_graph"):
                self.lbl_peak_speed_graph.configure(text=f"Peak: {format_speed(self.peak_speed_seen)}")
            self._draw_speed_graph()
            self._draw_segment_matrix()

            # Keep button states in sync with live status
            self._sync_buttons()

            # Update segment rows
            segments = getattr(self.task, "segments", [])
            while len(self.thread_rows) < len(segments):
                idx = len(self.thread_rows)
                row = ctk.CTkFrame(self.table_scroll, fg_color="#0f172a", height=28, corner_radius=4)
                row.pack(fill="x", pady=2)
                row.pack_propagate(False)

                t_lbl = ctk.CTkLabel(row, text=f"Thread #{idx+1}", font=ctk.CTkFont(size=10, weight="bold"), width=70, anchor="w")
                t_lbl.pack(side="left", padx=8)

                bar = ctk.CTkProgressBar(row, height=8, corner_radius=2, progress_color="#38bdf8", fg_color="#1e293b")
                bar.pack(side="left", fill="x", expand=True, padx=6)

                pct = ctk.CTkLabel(row, text="0%", font=ctk.CTkFont(size=9), width=50, anchor="e")
                pct.pack(side="right", padx=8)

                range_lbl = ctk.CTkLabel(row, text="", font=ctk.CTkFont(size=9), text_color="#94a3b8", width=120, anchor="center")
                range_lbl.pack(side="right")

                self.thread_rows.append((row, bar, pct, range_lbl))

            for i, seg in enumerate(segments):
                row, bar, pct, range_lbl = self.thread_rows[i]
                bar.set(seg.progress_pct / 100.0)
                pct.configure(text=f"{seg.progress_pct:.1f}%")
                range_lbl.configure(text=f"{format_bytes(seg.downloaded_bytes)} / {format_bytes(seg.total_bytes)}")
                
                if seg.status == "completed":
                    bar.configure(progress_color="#10b981")
                elif seg.status == "downloading":
                    bar.configure(progress_color=palette.get("accent", "#38bdf8"))
                else:
                    bar.configure(progress_color="#64748b")

            # Check completion actions
            if self.task.status == "Completed":
                if self.play_chime.get() and not getattr(self, "_chime_played", False):
                    self._chime_played = True
                    try:
                        from core.platform_utils import play_audio_alert
                        play_audio_alert("complete")
                    except Exception:
                        pass
                if self.open_when_done.get() and os.path.exists(self.task.save_path):
                    try:
                        os.startfile(self.task.save_path)
                    except Exception:
                        pass

                if self.shutdown_on_complete.get():
                    subprocess.run("shutdown /s /t 60", shell=True)

                if self.auto_close.get():
                    self.destroy()
                    return

            self.after(350, update_loop)

        self.after(350, update_loop)
