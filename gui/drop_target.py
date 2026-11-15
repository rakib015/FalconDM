import os
import tkinter as tk
import customtkinter as ctk
from typing import Callable, Optional

class FloatingDropBasket(tk.Toplevel):
    """The iconic IDM floating desktop Drop Target / Basket widget.
    Draggable anywhere, always-on-top, accepts drag-and-drop URLs and clicks.
    """

    def __init__(self, parent, on_url_dropped: Callable[[str], None], on_open_main: Callable[[], None]):
        super().__init__(parent)
        self.on_url_dropped = on_url_dropped
        self.on_open_main = on_open_main

        self.title("FalconDM Basket")
        self.geometry("90x90+100+100")
        self.overrideredirect(True)  # Frameless floating widget
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.92)  # Semi-transparent glassmorphism

        self._drag_start_x = 0
        self._drag_start_y = 0

        self._build_ui()
        self._bind_events()

    def _build_ui(self):
        self.configure(bg="#0f172a")

        # Outer rounded container
        self.frame = ctk.CTkFrame(
            self,
            width=86,
            height=86,
            corner_radius=20,
            fg_color="#181a20",
            border_width=2,
            border_color="#2563eb"
        )
        self.frame.pack(padx=2, pady=2, fill="both", expand=True)

        # Top header with Close '✕'
        self.top_bar = tk.Frame(self.frame, bg="#181a20")
        self.top_bar.pack(fill="x", padx=4, pady=(2, 0))

        self.btn_close = tk.Label(
            self.top_bar,
            text="✕",
            font=("Arial", 8, "bold"),
            bg="#181a20",
            fg="#94a3b8",
            cursor="hand2"
        )
        self.btn_close.pack(side="right")
        self.btn_close.bind("<Button-1>", lambda e: self.withdraw())
        self.btn_close.bind("<Enter>", lambda e: self.btn_close.config(fg="#ef4444"))
        self.btn_close.bind("<Leave>", lambda e: self.btn_close.config(fg="#94a3b8"))

        # Falcon Icon
        self.lbl_icon = ctk.CTkLabel(
            self.frame,
            text="🦅",
            font=ctk.CTkFont(size=24),
            cursor="hand2"
        )
        self.lbl_icon.pack(pady=(2, 0))

        self.lbl_text = ctk.CTkLabel(
            self.frame,
            text="FalconDM",
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color="#38bdf8",
            cursor="hand2"
        )
        self.lbl_text.pack(pady=(0, 6))

    def _bind_events(self):
        # Dragging handlers
        for w in (self, self.frame, self.lbl_icon, self.lbl_text):
            w.bind("<Button-1>", self._on_mouse_down)
            w.bind("<B1-Motion>", self._on_mouse_drag)
            w.bind("<Double-Button-1>", lambda e: self.on_open_main())
            w.bind("<Button-3>", self._show_context_menu)

    def _on_mouse_down(self, event):
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def _on_mouse_drag(self, event):
        dx = event.x - self._drag_start_x
        dy = event.y - self._drag_start_y
        new_x = self.winfo_x() + dx
        new_y = self.winfo_y() + dy
        self.geometry(f"+{new_x}+{new_y}")

    def _show_context_menu(self, event):
        menu = tk.Menu(self, tearoff=0, bg="#181a20", fg="#f3f4f6", activebackground="#2563eb")
        menu.add_command(label="📂 Show FalconDM", command=self.on_open_main)
        menu.add_command(label="📋 Paste URL from Clipboard", command=self._paste_clipboard)
        menu.add_separator()
        menu.add_command(label="❌ Hide Floating Basket", command=self.withdraw)
        menu.tk_popup(event.x_root, event.y_root)

    def _paste_clipboard(self):
        try:
            cb = self.clipboard_get().strip()
            if cb.startswith("http://") or cb.startswith("https://") or cb.startswith("magnet:?"):
                self.on_url_dropped(cb)
        except Exception:
            pass

    def toggle(self):
        if self.state() == "normal":
            self.withdraw()
        else:
            self.deiconify()
            self.lift()
