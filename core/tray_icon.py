import threading
from typing import Callable, Optional, Any
from PIL import Image, ImageDraw
import pystray

def create_falcon_icon_image() -> Image.Image:
    """Creates a high-DPI FalconDM shield icon."""
    img = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Background rounded container
    d.rounded_rectangle([4, 4, 60, 60], radius=14, fill='#1e293b', outline='#2563eb', width=3)
    # Downward turbo lightning / arrow
    d.polygon([(32, 14), (48, 36), (37, 36), (37, 48), (27, 48), (27, 36), (16, 36)], fill='#38bdf8')
    return img

class FalconTrayIcon:
    """Manages the Windows System Tray notification area icon."""

    def __init__(
        self,
        on_open: Callable[[], None],
        on_toggle_basket: Callable[[], None],
        on_resume_all: Callable[[], None],
        on_pause_all: Callable[[], None],
        on_open_settings: Callable[[], None],
        on_exit: Callable[[], None]
    ):
        self.on_open = on_open
        self.on_toggle_basket = on_toggle_basket
        self.on_resume_all = on_resume_all
        self.on_pause_all = on_pause_all
        self.on_open_settings = on_open_settings
        self.on_exit = on_exit

        self.icon: Any = None
        self._thread: Optional[threading.Thread] = None

    def start(self):
        img = create_falcon_icon_image()
        menu = pystray.Menu(
            pystray.MenuItem("📂 Open FalconDM", lambda icon, item: self.on_open(), default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("▶ Resume All Downloads", lambda icon, item: self.on_resume_all()),
            pystray.MenuItem("⏸ Pause All Downloads", lambda icon, item: self.on_pause_all()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("⚙️ Settings...", lambda icon, item: self.on_open_settings()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("❌ Exit FalconDM", lambda icon, item: self.on_exit())
        )
        self.icon = pystray.Icon("FalconDM", img, "FalconDM - Turbo Download Accelerator", menu=menu)
        
        self._thread = threading.Thread(target=self.icon.run, daemon=True)
        self._thread.start()

    def notify(self, title: str, message: str):
        if self.icon:
            try:
                self.icon.notify(message, title)
            except Exception:
                pass

    def stop(self):
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
