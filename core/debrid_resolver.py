import os
import re
import urllib.parse
from typing import Optional, Dict, Any, Tuple
import requests
from core.config_manager import config_store
from core.platform_utils import safe_print

DEBRID_SUPPORTED_HOSTS = (
    "rapidgator.net", "1fichier.com", "turbobit.net", "nitroflare.com",
    "ddownload.com", "katfile.com", "mega.nz", "filefactory.com",
    "uploadgig.com", "alfafile.net", "k2s.cc", "keep2share.cc",
    "mexashare.com", "dropapk.to", "filerio.in", "clicknupload.click",
    "wdupload.com", "uptobox.com"
)

class DebridResolver:
    """
    Real-Debrid & Multi-Host Cloud Link Unrestrictor.
    Instantly converts slow, paywalled filehost links (Rapidgator, 1fichier, Turbobit, etc.)
    and torrent magnets into ultra-fast unrestricted direct HTTP links (up to 100+ MB/s).
    """

    API_BASE = "https://api.real-debrid.com/rest/1.0"

    @classmethod
    def get_api_key(cls) -> str:
        return config_store.get("real_debrid_api_key", "").strip()

    @classmethod
    def is_debrid_enabled(cls) -> bool:
        return bool(cls.get_api_key())

    @classmethod
    def is_supported_url(cls, url: str) -> bool:
        if not url:
            return False
        clean = url.strip().lower()
        if clean.startswith("magnet:?xt=urn:btih:"):
            return True
        try:
            domain = urllib.parse.urlparse(clean).netloc.lower()
            return any(host in domain for host in DEBRID_SUPPORTED_HOSTS)
        except Exception:
            return False

    @classmethod
    def unrestrict_link(cls, url: str, password: Optional[str] = None) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Unrestricts a filehost link via Real-Debrid API.
        Returns: (success: bool, direct_url_or_error_message: str, metadata: dict)
        """
        api_key = cls.get_api_key()
        if not api_key:
            return False, "Real-Debrid API key is not configured.", None

        headers = {
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "FalconDM/2.0 Turbo"
        }

        # 1. Magnet / Torrent Handling
        if url.strip().lower().startswith("magnet:?xt=urn:btih:"):
            return cls._unrestrict_magnet(url, headers)

        # 2. Direct Filehost Unrestriction
        endpoint = f"{cls.API_BASE}/unrestrict/link"
        data = {"link": url.strip()}
        if password:
            data["password"] = password

        try:
            resp = requests.post(endpoint, headers=headers, data=data, timeout=15)
            if resp.status_code == 200:
                res_data = resp.json()
                download_link = res_data.get("download")
                if download_link:
                    safe_print(f"[FalconDM Debrid] Successfully unrestricted: {res_data.get('filename')}")
                    return True, download_link, res_data
            
            error_data = resp.json() if resp.content else {}
            err_msg = error_data.get("error_details") or error_data.get("error") or f"HTTP {resp.status_code}"
            return False, f"Debrid error: {err_msg}", None
        except Exception as e:
            return False, f"Debrid connection error: {str(e)}", None

    @classmethod
    def _unrestrict_magnet(cls, magnet_url: str, headers: Dict[str, str]) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Adds magnet to Real-Debrid cloud cache and retrieves direct HTTP download link."""
        try:
            add_resp = requests.post(
                f"{cls.API_BASE}/torrents/addMagnet",
                headers=headers,
                data={"magnet": magnet_url.strip()},
                timeout=15
            )
            if add_resp.status_code not in (200, 201):
                return False, f"Failed to add magnet: HTTP {add_resp.status_code}", None
            
            torrent_id = add_resp.json().get("id")
            if not torrent_id:
                return False, "Failed to retrieve torrent ID from Real-Debrid", None

            # Select all files
            requests.post(
                f"{cls.API_BASE}/torrents/selectFiles/{torrent_id}",
                headers=headers,
                data={"files": "all"},
                timeout=15
            )

            # Check torrent info
            info_resp = requests.get(f"{cls.API_BASE}/torrents/info/{torrent_id}", headers=headers, timeout=15)
            if info_resp.status_code == 200:
                t_info = info_resp.json()
                links = t_info.get("links", [])
                if links:
                    # Unrestrict the first high-speed link
                    return cls.unrestrict_link(links[0])
                return False, f"Torrent added to cloud cache. Status: {t_info.get('status')}", t_info

            return False, "Failed to inspect torrent status on Real-Debrid", None
        except Exception as e:
            return False, f"Magnet debrid error: {str(e)}", None

