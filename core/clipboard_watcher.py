import time
import re
from typing import Callable, Optional

import time
import re
import urllib.parse
from typing import Callable, Optional, Set, Dict

DOWNLOAD_EXTENSIONS = (
    # Archives & Compressed
    ".zip", ".rar", ".7z", ".7zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".zst", ".cab", ".iso", ".img",
    # Video & Streams
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".ts", ".3gp", ".m3u8", ".mpd",
    # Audio
    ".mp3", ".flac", ".wav", ".aac", ".ogg", ".m4a", ".opus", ".wma", ".aiff", ".alac",
    # Documents & Books
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".csv", ".txt", ".epub", ".mobi", ".cbz", ".cbr",
    # Executables & Packages
    ".exe", ".msi", ".apk", ".dmg", ".pkg", ".deb", ".rpm", ".appx", ".msix", ".bin", ".run", ".torrent"
)

MEDIA_DOMAINS = (
    "youtube.com", "youtu.be", "twitter.com", "x.com", "tiktok.com",
    "reddit.com", "instagram.com", "facebook.com", "fb.watch", "vimeo.com",
    "twitch.tv", "soundcloud.com", "dailymotion.com", "bilibili.com",
    "rumble.com", "odysee.com", "streamable.com", "threads.net", "loom.com",
    "pinterest.com", "vk.com"
)

CLOUD_STORAGE_DOMAINS = (
    "drive.google.com", "dropbox.com", "mediafire.com", "pixeldrain.com",
    "mega.nz", "gofile.io", "1fichier.com", "sendspace.com", "catbox.moe",
    "fastupload.io", "wetransfer.com", "krakenfiles.com", "rapidgator.net",
    "ddownload.com", "nitroflare.com", "turbobit.net"
)

class ClipboardWatcher:
    """Intelligent high-precision system clipboard sniffer for media, direct links, and cloud storage."""

    def __init__(self, get_clipboard_fn: Callable[[], str], on_url_detected: Callable[[str], None]):
        self.get_clipboard_fn = get_clipboard_fn
        self.on_url_detected = on_url_detected
        self.enabled = True
        self._recent_urls: Dict[str, float] = {}  # URL -> timestamp (debounce cache)
        self._last_content = ""
        try:
            self._last_content = self.get_clipboard_fn().strip()
        except Exception:
            self._last_content = ""

    def is_downloadable(self, text: str) -> bool:
        """Determines if the copied text is a valid download, media stream, cloud host, or mirror link."""
        if not text:
            return False

        clean_text = text.strip()
        clean_lower = clean_text.lower()

        # 1. Magnet links & Legacy Wrapped Download Protocols (Thunder, FlashGet, QQ Xuanfeng)
        if clean_lower.startswith(("magnet:?xt=urn:btih:", "thunder://", "flashget://", "qqdl://")):
            return True

        # 1b. arXiv paper notation (e.g. arxiv:1706.03762)
        if clean_lower.startswith("arxiv:"):
            return True

        # 2. Must be HTTP/HTTPS
        if not (clean_text.startswith("http://") or clean_text.startswith("https://")):
            return False

        try:
            parsed = urllib.parse.urlparse(clean_text)
            netloc = parsed.netloc.lower()
            path = parsed.path.lower()
            query = parsed.query.lower()
        except Exception:
            return False

        # 2b. Research repositories, AI model hubs & Git platforms
        if any(h in netloc for h in ("arxiv.org", "alphaxiv.org", "huggingface.co", "hf.co", "github.com", "githubusercontent.com")):
            return True

        # 3. Known Media Streaming Sites
        if any(domain in netloc for domain in MEDIA_DOMAINS):
            return True

        # 4. Known Cloud Storage File Hosts
        if any(domain in netloc for domain in CLOUD_STORAGE_DOMAINS):
            return True

        # 5. Direct file extensions in URL path (e.g. /files/archive.zip)
        if any(path.endswith(ext) for ext in DOWNLOAD_EXTENSIONS):
            return True

        # 6. File extensions embedded in path segments or query parameters (e.g. ?file=setup.exe or dl.php?name=app.apk)
        for ext in DOWNLOAD_EXTENSIONS:
            if ext in path or ext in query:
                return True

        return False

    def check_once(self):
        """Called periodically from main UI thread to safely inspect clipboard without thread contention."""
        if not self.enabled:
            return

        try:
            content = self.get_clipboard_fn().strip()
            if not content or content == self._last_content:
                return
            
            self._last_content = content
            now = time.time()

            # Clean expired URLs from cache (older than 60 seconds)
            self._recent_urls = {u: t for u, t in self._recent_urls.items() if now - t < 60.0}

            # Check if recently prompted
            if content in self._recent_urls:
                return

            if self.is_downloadable(content):
                self._recent_urls[content] = now
                self.on_url_detected(content)
        except Exception:
            pass
