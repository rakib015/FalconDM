import os
import subprocess
import tkinter as tk
import customtkinter as ctk
from typing import Optional, Callable

class CyberToastNotification(ctk.CTkToplevel):
    """
    Sleek Cyber Obsidian toast notification that slides into the bottom-right
    of the user's desktop when a download completes or encounters an error.
    Includes instant 'Open File' and 'Open Folder' action buttons.
    """

    def __init__(
        self,
        parent,
        title: str,
        filename: str,
        file_path: str,
        file_size_str: str = "",
        is_error: bool = False,
        error_msg: str = "",
        on_open_file: Optional[Callable[[str], None]] = None,
        on_open_folder: Optional[Callable[[str], None]] = None
    ):
        super().__init__(parent)
        self.file_path = file_path
        self.on_open_file = on_open_file
        self.on_open_folder = on_open_folder
        self._hovered = False
        self._remaining_ms = 6000

        # Borderless, always-on-top notification card
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        
        # Dimensions
        toast_w = 360
        toast_h = 130
        
        try:
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            x = max(10, sw - toast_w - 24)
            y = max(10, sh - toast_h - 58)  # Docked just above Windows taskbar
            self.geometry(f"{toast_w}x{toast_h}+{x}+{y}")
        except Exception:
            self.geometry(f"{toast_w}x{toast_h}+100+100")

        # Container Frame
        border_col = "#ef4444" if is_error else "#2563eb"
        card = ctk.CTkFrame(
            self,
            fg_color="#0e141f",
            corner_radius=10,
            border_width=1,
            border_color=border_col
        )
        card.pack(fill="both", expand=True)

        # Header Bar
        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.pack(fill="x", padx=12, pady=(10, 4))

        status_text = "✗ Download Failed" if is_error else "✓ Download Complete"
        status_color = "#f87171" if is_error else "#34d399"
        
        lbl_status = ctk.CTkLabel(
            hdr,
            text=f"⚡ {status_text}",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=status_color
        )
        lbl_status.pack(side="left")

        if file_size_str and not is_error:
            lbl_size = ctk.CTkLabel(
                hdr,
                text=file_size_str,
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color="#38bdf8",
                fg_color="#182338",
                corner_radius=4,
                padx=6,
                pady=1
            )
            lbl_size.pack(side="left", padx=(8, 0))

        btn_close = ctk.CTkButton(
            hdr,
            text="✕",
            width=20,
            height=20,
            corner_radius=4,
            fg_color="transparent",
            hover_color="#1f293d",
            text_color="#94a3b8",
            font=ctk.CTkFont(size=11),
            command=self.destroy
        )
        btn_close.pack(side="right")

        # Middle details
        mid_frame = ctk.CTkFrame(card, fg_color="transparent")
        mid_frame.pack(fill="x", padx=12, pady=2)

        # Truncate filename if long
        display_name = filename
        if len(display_name) > 38:
            display_name = display_name[:35] + "..."

        desc_text = error_msg if is_error else display_name
        desc_color = "#fca5a5" if is_error else "#f8fafc"

        lbl_desc = ctk.CTkLabel(
            mid_frame,
            text=desc_text,
            font=ctk.CTkFont(size=11, weight="bold" if not is_error else "normal"),
            text_color=desc_color,
            anchor="w"
        )
        lbl_desc.pack(fill="x")

        # Action Buttons Dock
        if not is_error:
            act_row = ctk.CTkFrame(card, fg_color="transparent")
            act_row.pack(fill="x", padx=12, pady=(6, 8))

            btn_open = ctk.CTkButton(
                act_row,
                text="▶ Open File",
                width=90,
                height=26,
                corner_radius=6,
                fg_color="#2563eb",
                hover_color="#1d4ed8",
                font=ctk.CTkFont(size=11, weight="bold"),
                command=self._do_open_file
            )
            btn_open.pack(side="left", padx=(0, 6))

            btn_folder = ctk.CTkButton(
                act_row,
                text="📁 Folder",
                width=80,
                height=26,
                corner_radius=6,
                fg_color="#1e293b",
                hover_color="#334155",
                font=ctk.CTkFont(size=11),
                command=self._do_open_folder
            )
            btn_folder.pack(side="left")

        # Mouse hover pause logic
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        card.bind("<Enter>", lambda e: self._set_hover(True))
        card.bind("<Leave>", lambda e: self._set_hover(False))

        # Start auto-fade countdown
        self._tick_close()

    def _set_hover(self, val: bool):
        self._hovered = val

    def _tick_close(self):
        if not self.winfo_exists():
            return
        if not self._hovered:
            self._remaining_ms -= 500
            if self._remaining_ms <= 0:
                self.destroy()
                return
        self.after(500, self._tick_close)

    def _do_open_file(self):
        if self.on_open_file and self.file_path:
            self.on_open_file(self.file_path)
        elif self.file_path and os.path.exists(self.file_path):
            try:
                os.startfile(self.file_path)
            except Exception:
                pass
        self.destroy()

    def _do_open_folder(self):
        if self.on_open_folder and self.file_path:
            self.on_open_folder(self.file_path)
        elif self.file_path:
            folder = os.path.dirname(os.path.abspath(self.file_path))
            if os.path.exists(folder):
                try:
                    os.startfile(folder)
                except Exception:
                    pass
        self.destroy()
