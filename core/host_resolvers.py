import re
import urllib.parse
from typing import Optional, Dict, Any
import requests
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

from core.logger import falcon_logger

DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 FalconDM/2.0"

def _attr_to_str(val: Any) -> str:
    """Safely converts BeautifulSoup Tag attribute values to clean str for type safety."""
    if val is None:
        return ""
    if isinstance(val, (list, tuple)):
        return "".join(str(x) for x in val)
    return str(val)

class HostResolver:
    """Detects and resolves direct download links for cloud storage and file hosts."""

    @staticmethod
    def is_resolvable(url: str) -> bool:
        if not url:
            return False
        u = url.lower()
        return any(domain in u for domain in (
            "drive.google.com",
            "drive.usercontent.google.com",
            "dropbox.com",
            "1drv.ms",
            "onedrive.live.com",
            "mediafire.com",
            "github.com",
            "pixeldrain.com"
        ))

    @staticmethod
    def resolve_url(url: str, timeout: int = 12) -> Dict[str, Any]:
        """
        Attempts to resolve a direct high-speed downloadable link from a file host page.
        Returns dict with:
          resolved_url: str (the direct download link)
          filename: Optional[str]
          headers: Dict[str, str]
          host: str
        """
        parsed = urllib.parse.urlparse(url)
        netloc = parsed.netloc.lower()

        try:
            # 1. Google Drive
            if "drive.google.com" in netloc or "drive.usercontent.google.com" in netloc:
                res = HostResolver._resolve_google_drive(url, timeout)
                if res.get("resolved_url") != url:
                    falcon_logger.logger.info(f"HostResolver: Resolved Google Drive link -> {res.get('resolved_url')[:80]}... (File: {res.get('filename')})")
                return res

            # 2. Dropbox
            if "dropbox.com" in netloc:
                res = HostResolver._resolve_dropbox(url)
                if res.get("resolved_url") != url:
                    falcon_logger.logger.info(f"HostResolver: Converted Dropbox link to direct stream -> {res.get('resolved_url')[:80]}...")
                return res

            # 3. GitHub
            if "github.com" in netloc:
                res = HostResolver._resolve_github(url)
                return res

            # 4. PixelDrain
            if "pixeldrain.com" in netloc:
                res = HostResolver._resolve_pixeldrain(url)
                return res

            # 5. MediaFire
            if "mediafire.com" in netloc:
                res = HostResolver._resolve_mediafire(url, timeout)
                if res.get("resolved_url") != url:
                    falcon_logger.logger.info(f"HostResolver: Resolved MediaFire link -> {res.get('resolved_url')[:80]}... (File: {res.get('filename')})")
                return res

            # 6. OneDrive / 1drv.ms
            if "1drv.ms" in netloc or "onedrive.live.com" in netloc:
                res = HostResolver._resolve_onedrive(url, timeout)
                return res
        except Exception as e:
            falcon_logger.logger.warning(f"HostResolver error for {url}: {e}")

        # Default fallback: return original
        return {
            "resolved_url": url,
            "filename": None,
            "headers": {},
            "host": "Direct"
        }

    @staticmethod
    def _resolve_google_drive(url: str, timeout: int = 12) -> Dict[str, Any]:
        # Extract File ID
        file_id = None
        match = re.search(r'/file/d/([a-zA-Z0-9_-]+)', url)
        if match:
            file_id = match.group(1)
        else:
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            if 'id' in qs:
                file_id = qs['id'][0]

        if not file_id:
            return {"resolved_url": url, "filename": None, "headers": {}, "host": "Google Drive"}

        # Initial download endpoint
        direct_url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&authuser=0"
        
        session = requests.Session()
        session.headers.update({"User-Agent": DEFAULT_UA})
        
        try:
            resp = session.get(direct_url, timeout=timeout, stream=True, allow_redirects=True)
            content_type = resp.headers.get("Content-Type", "").lower()
            cd = resp.headers.get("Content-Disposition", "")
            fname = None

            if cd and "filename=" in cd:
                match_fn = re.findall(r'filename\*?=(?:UTF-8\'\')?["\']?([^"\';\r\n]+)', cd, re.IGNORECASE)
                if match_fn:
                    fname = urllib.parse.unquote(match_fn[0].strip())

            # If response is already the file binary stream (not HTML virus warning)
            if "text/html" not in content_type and (cd or resp.status_code == 200):
                final_url = resp.url or direct_url
                resp.close()
                return {
                    "resolved_url": final_url,
                    "filename": fname,
                    "headers": {"User-Agent": DEFAULT_UA},
                    "host": "Google Drive"
                }

            # Response is HTML: large file virus warning page
            # Read first 128KB of HTML to find the confirmation token or download form
            html_chunks = []
            for chunk in resp.iter_content(chunk_size=16384):
                html_chunks.append(chunk)
                if sum(len(c) for c in html_chunks) > 131072:
                    break
            resp.close()
            html_text = b"".join(html_chunks).decode("utf-8", errors="ignore")

            # Check BeautifulSoup if available
            if BeautifulSoup:
                soup = BeautifulSoup(html_text, "html.parser")
                
                # Check for modern Google Drive download form
                form = soup.find("form", id="download-form") or soup.find("form", action=re.compile(r'/download'))
                if form:
                    raw_action = _attr_to_str(form.get("action", ""))
                    if raw_action.startswith("/"):
                        action = "https://drive.usercontent.google.com" + raw_action
                    elif not raw_action.startswith("http"):
                        action = "https://drive.usercontent.google.com/download"
                    else:
                        action = raw_action
                    params: Dict[str, str] = {}
                    for inp in form.find_all("input"):
                        inp_name = _attr_to_str(inp.get("name", ""))
                        if inp_name:
                            params[inp_name] = _attr_to_str(inp.get("value", ""))
                    if "confirm" in params or "uuid" in params:
                        sep = "&" if "?" in action else "?"
                        direct_url = action + sep + urllib.parse.urlencode(params)
                
                # Check for download link tag
                if not form:
                    a_tag = soup.find("a", id="uc-download-link") or soup.find("a", href=re.compile(r'confirm='))
                    if a_tag and a_tag.get("href"):
                        href_str = _attr_to_str(a_tag.get("href", ""))
                        if href_str.startswith("/"):
                            direct_url = "https://drive.google.com" + href_str
                        elif href_str:
                            direct_url = href_str

                # Extract filename if visible in warning dialog
                if not fname:
                    name_span = soup.find("span", class_="uc-name-size") or soup.find("a", class_="uc-name-size")
                    if name_span:
                        raw_name = name_span.get_text().strip()
                        # Often "filename.zip (1.5G)"
                        m_split = re.split(r'\s*\([0-9.]+\s*[KMGT]?B?\)', raw_name)
                        if m_split and m_split[0]:
                            fname = m_split[0].strip()
            else:
                # Regex fallback for confirmation uuid and token
                m_confirm = re.search(r'name=["\']confirm["\']\s+value=["\']([^"\']+)["\']', html_text)
                m_uuid = re.search(r'name=["\']uuid["\']\s+value=["\']([^"\']+)["\']', html_text)
                if m_confirm:
                    conf_val = m_confirm.group(1)
                    uuid_part = f"&uuid={m_uuid.group(1)}" if m_uuid else ""
                    direct_url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm={conf_val}{uuid_part}"

            return {
                "resolved_url": direct_url,
                "filename": fname,
                "headers": {"User-Agent": DEFAULT_UA},
                "host": "Google Drive"
            }
        except Exception as e:
            falcon_logger.logger.warning(f"Google Drive resolution failed: {e}")
            return {
                "resolved_url": direct_url,
                "filename": None,
                "headers": {"User-Agent": DEFAULT_UA},
                "host": "Google Drive"
            }

    @staticmethod
    def _resolve_dropbox(url: str) -> Dict[str, Any]:
        # Switch dl=0 to dl=1
        clean = re.sub(r'([?&])dl=0', r'\1dl=1', url)
        if "dl=1" not in clean:
            clean += ("&" if "?" in clean else "?") + "dl=1"
        return {
            "resolved_url": clean,
            "filename": None,
            "headers": {"User-Agent": DEFAULT_UA},
            "host": "Dropbox"
        }

    @staticmethod
    def _resolve_github(url: str) -> Dict[str, Any]:
        # Handle github blob -> raw
        if "/blob/" in url:
            raw = url.replace("/blob/", "/raw/")
            return {
                "resolved_url": raw,
                "filename": None,
                "headers": {"User-Agent": DEFAULT_UA},
                "host": "GitHub Raw"
            }
        return {
            "resolved_url": url,
            "filename": None,
            "headers": {"User-Agent": DEFAULT_UA},
            "host": "GitHub"
        }

    @staticmethod
    def _resolve_pixeldrain(url: str) -> Dict[str, Any]:
        # Convert /u/<id> to /api/file/<id>?download
        m = re.search(r'pixeldrain\.com/u/([a-zA-Z0-9_-]+)', url)
        if m:
            fid = m.group(1)
            return {
                "resolved_url": f"https://pixeldrain.com/api/file/{fid}?download",
                "filename": None,
                "headers": {"User-Agent": DEFAULT_UA},
                "host": "PixelDrain"
            }
        return {"resolved_url": url, "filename": None, "headers": {}, "host": "PixelDrain"}

    @staticmethod
    def _resolve_mediafire(url: str, timeout: int = 12) -> Dict[str, Any]:
        try:
            resp = requests.get(url, headers={"User-Agent": DEFAULT_UA}, timeout=timeout)
            if resp.status_code == 200:
                html = resp.text
                resolved_url = None
                filename = None

                # Search via BeautifulSoup
                if BeautifulSoup:
                    soup = BeautifulSoup(html, "html.parser")
                    btn = (
                        soup.find("a", id="downloadButton") or
                        soup.find("a", attrs={"aria-label": "Download file"}) or
                        soup.find("a", class_=re.compile(r'popsok|download_link'))
                    )
                    if btn and btn.get("href"):
                        resolved_url = _attr_to_str(btn.get("href", ""))

                    # Extract Filename
                    fn_div = (
                        soup.find("div", class_="filename") or
                        soup.find("div", class_="dl-btn-label") or
                        soup.find("meta", property="og:title")
                    )
                    if fn_div:
                        filename = _attr_to_str(fn_div.get("content", "")) if fn_div.name == "meta" else fn_div.get_text().strip()

                # Regex fallback for download URL
                if not resolved_url:
                    m = re.search(r'href=[\'"](https?://download\d+\.mediafire\.com/[^\'"]+)[\'"]', html)
                    if not m:
                        m = re.search(r'kNO\s*=\s*[\'"](https?://[^\'"]+)[\'"]', html)
                    if m:
                        resolved_url = m.group(1)

                if resolved_url:
                    return {
                        "resolved_url": resolved_url,
                        "filename": filename,
                        "headers": {"User-Agent": DEFAULT_UA, "Referer": url},
                        "host": "MediaFire"
                    }
        except Exception as e:
            falcon_logger.logger.warning(f"MediaFire resolution failed: {e}")

        return {"resolved_url": url, "filename": None, "headers": {}, "host": "MediaFire"}

    @staticmethod
    def _resolve_onedrive(url: str, timeout: int = 12) -> Dict[str, Any]:
        """Resolves 1drv.ms shortlink or onedrive.live.com sharing link to direct download link."""
        try:
            # 1drv.ms redirects to onedrive.live.com
            resp = requests.head(url, headers={"User-Agent": DEFAULT_UA}, allow_redirects=True, timeout=timeout)
            final_url = resp.url or url
            if "1drv.ms" in url or "onedrive.live.com" in final_url:
                # OneDrive direct download can be formed by replacing /view.aspx or adding download=1
                if "download=1" not in final_url:
                    sep = "&" if "?" in final_url else "?"
                    direct = final_url + sep + "download=1"
                    return {
                        "resolved_url": direct,
                        "filename": None,
                        "headers": {"User-Agent": DEFAULT_UA},
                        "host": "OneDrive"
                    }
        except Exception:
            pass
        return {"resolved_url": url, "filename": None, "headers": {}, "host": "OneDrive"}
