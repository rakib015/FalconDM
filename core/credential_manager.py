import os
import json
import urllib.parse
from typing import Dict, Optional, Tuple, Any

class CredentialManager:
    """Manages saved site logins, Basic/Digest HTTP credentials, and custom session tokens."""

    def __init__(self, config_file: str = "site_credentials.json"):
        self.config_file = config_file
        self.credentials: Dict[str, Dict[str, Any]] = {}
        self.load()

    def _normalize_host(self, host_or_url: str) -> str:
        h = host_or_url.strip().lower()
        if "://" in h:
            try:
                parsed = urllib.parse.urlparse(h)
                h = parsed.netloc or parsed.path
            except Exception:
                pass
        # Strip port or www prefix if present
        if ":" in h:
            h = h.split(":")[0]
        if h.startswith("www."):
            h = h[4:]
        return h

    def add_credential(
        self,
        domain: str,
        username: str = "",
        password: str = "",
        custom_headers: Optional[Dict[str, str]] = None
    ):
        host = self._normalize_host(domain)
        self.credentials[host] = {
            "domain": host,
            "username": username,
            "password": password,
            "custom_headers": custom_headers or {}
        }
        self.save()

    def remove_credential(self, domain: str):
        host = self._normalize_host(domain)
        if host in self.credentials:
            del self.credentials[host]
            self.save()

    def get_credential(self, url: str) -> Optional[Dict[str, Any]]:
        host = self._normalize_host(url)
        # Exact match
        if host in self.credentials:
            return self.credentials[host]
        # Suffix / domain match (e.g. sub.rapidgator.net matches rapidgator.net)
        for d, cred in self.credentials.items():
            if host.endswith("." + d) or host == d:
                return cred
        return None

    def get_auth_tuple(self, url: str) -> Optional[Tuple[str, str]]:
        cred = self.get_credential(url)
        if cred and cred.get("username") and cred.get("password"):
            return (cred["username"], cred["password"])
        return None

    def get_auth_headers(self, url: str) -> Dict[str, str]:
        cred = self.get_credential(url)
        if cred and cred.get("custom_headers"):
            return cred["custom_headers"].copy()
        return {}

    def save(self):
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.credentials, f, indent=2)
        except Exception as e:
            print(f"[FalconDM CredentialManager] save error: {e}")

    def load(self):
        if not os.path.exists(self.config_file):
            return
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                self.credentials = json.load(f)
        except Exception as e:
            print(f"[FalconDM CredentialManager] load error: {e}")

# Global singleton
credential_store = CredentialManager()
