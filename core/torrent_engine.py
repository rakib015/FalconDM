import os
import re
import sys
import shutil
import subprocess
import threading
import urllib.parse
from typing import Optional, Callable, Dict, Any, List

# Curated Tier-1 Public High-Speed BitTorrent Trackers
PUBLIC_TRACKERS: List[str] = [
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://open.stealth.si:80/announce",
    "udp://tracker.torrent.eu.org:451/announce",
    "udp://tracker.bittor.pw:1337/announce",
    "udp://public.tracker.vraphim.com:6969/announce",
    "udp://opentracker.i2p.rocks:6969/announce",
    "udp://tracker.moeking.me:6969/announce",
    "http://tracker.openbittorrent.com:80/announce",
    "udp://explodie.org:6969/announce"
]

# Standard DHT Bootstrap Entry Points
DHT_BOOTSTRAP_NODES: List[str] = [
    "router.bittorrent.com:6881",
    "dht.transmissionbt.com:6881",
    "router.utorrent.com:6881",
    "dht.libtorrent.org:25401"
]

class TorrentEngine:
    """High-speed BitTorrent & Magnet Link Engine (IDM lacks this — FalconDM exclusive)."""

    _cached_bin: Optional[str] = None

    @classmethod
    def get_aria2_path(cls) -> Optional[str]:
        if cls._cached_bin and os.path.isfile(cls._cached_bin):
            return cls._cached_bin

        # 1. Check system PATH
        p = shutil.which("aria2c")
        if p:
            cls._cached_bin = p
            return p

        # 2. Check WinGet Packages directory
        local_app = os.environ.get("LOCALAPPDATA", "")
        if local_app:
            base_dir = os.path.join(local_app, "Microsoft", "WinGet", "Packages")
            if os.path.isdir(base_dir):
                for root, _, files in os.walk(base_dir):
                    if "aria2c.exe" in files:
                        full_p = os.path.join(root, "aria2c.exe")
                        cls._cached_bin = full_p
                        return full_p

        return None

    @staticmethod
    def is_torrent_url(url: str) -> bool:
        """Determines if a URL is a Magnet link or points to a .torrent file."""
        u = url.strip()
        if u.startswith("magnet:?"):
            return True
        path = urllib.parse.urlparse(u).path.lower()
        if path.endswith(".torrent"):
            return True
        return False

    @staticmethod
    def parse_magnet_title(magnet_url: str) -> str:
        """Extracts display name (dn) from magnet link query parameters."""
        try:
            parsed = urllib.parse.urlparse(magnet_url)
            qs = urllib.parse.parse_qs(parsed.query)
            if 'dn' in qs and qs['dn']:
                return qs['dn'][0]
            if 'xt' in qs and qs['xt']:
                xt = qs['xt'][0]
                return f"Torrent_{xt.split(':')[-1][:12]}"
        except Exception:
            pass
        return "Torrent_Download"

    @classmethod
    def enhance_magnet_link(cls, magnet_url: str) -> str:
        """
        Injects Tier-1 public high-speed trackers into magnet query parameters to drastically
        accelerate initial peer discovery and DHT swarm resolution.
        """
        if not magnet_url.startswith("magnet:?"):
            return magnet_url

        try:
            parsed = urllib.parse.urlparse(magnet_url)
            qs = urllib.parse.parse_qs(parsed.query)
            existing_trackers = set(qs.get("tr", []))
            
            # Merge existing and public trackers
            for t in PUBLIC_TRACKERS:
                existing_trackers.add(t)

            qs["tr"] = list(existing_trackers)
            new_query = urllib.parse.urlencode(qs, doseq=True)
            return f"magnet:?{new_query}"
        except Exception:
            return magnet_url

    @classmethod
    def build_aria2_command(
        cls,
        source: str,
        save_dir: str,
        max_peers: int = 80,
        metadata_only: bool = False
    ) -> List[str]:
        """Constructs optimized aria2c CLI command with DHT, PEX, and public tracker injection."""
        aria2_bin = cls.get_aria2_path() or "aria2c"
        
        # If magnet link, auto-enhance with trackers
        if source.startswith("magnet:?"):
            source = cls.enhance_magnet_link(source)

        cmd = [
            aria2_bin,
            source,
            f"--dir={save_dir}",
            "--enable-dht=true",
            "--enable-dht6=true",
            "--enable-peer-exchange=true",
            "--bt-enable-lpd=true",
            f"--bt-max-peers={max_peers}",
            f"--bt-tracker={','.join(PUBLIC_TRACKERS[:6])}",
            f"--dht-entry-point={DHT_BOOTSTRAP_NODES[0]}",
            f"--dht-entry-point6={DHT_BOOTSTRAP_NODES[0]}",
            "--bt-request-peer-speed-limit=250K",
            "--seed-time=0",
            "--summary-interval=1",
            "--console-log-level=warn",
            "--show-console-readout=true"
        ]
        
        if metadata_only:
            cmd.append("--bt-metadata-only=true")
            cmd.append("--bt-save-metadata=true")

        return cmd

    @classmethod
    def download_torrent(
        cls,
        source: str,
        save_dir: str,
        progress_hook: Optional[Callable[[Dict[str, Any]], None]] = None,
        stop_event: Optional[threading.Event] = None
    ) -> bool:
        """
        Executes multi-peer torrent or magnet download via aria2c subprocess with real-time stats parsing.
        """
        aria2_bin = cls.get_aria2_path()
        if not aria2_bin:
            if progress_hook:
                progress_hook({"status": "error", "error": "aria2c engine not found on system."})
            return False

        os.makedirs(save_dir, exist_ok=True)
        cmd = cls.build_aria2_command(source, save_dir)

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )

            # Regex for parsing aria2c console progress readout:
            # e.g.: [#a1b2c3 50MiB/100MiB(50%) CN:8 DL:2.5MiB/s ETA:20s]
            progress_regex = re.compile(
                r'\[#\w+\s+([0-9.]+[A-Za-z]+)/([0-9.]+[A-Za-z]+)\(([0-9.]+)%\)\s+CN:(\d+)\s+DL:([0-9.]+[A-Za-z]+/s)(?:\s+ETA:([0-9A-Za-z]+))?\]'
            )

            def parse_human_bytes(val_str: str) -> int:
                units = {"b": 1, "kib": 1024, "mib": 1024**2, "gib": 1024**3, "tib": 1024**4, "kb": 1000, "mb": 1000**2, "gb": 1000**3}
                m = re.match(r'([0-9.]+)\s*([A-Za-z]+)', val_str.lower().strip())
                if m:
                    num, u = m.groups()
                    return int(float(num) * units.get(u, 1))
                return 0

            if proc.stdout:
                for line in proc.stdout:
                    if stop_event and stop_event.is_set():
                        proc.terminate()
                        break

                    match = progress_regex.search(line)
                    if match and progress_hook:
                        done_str, total_str, pct_str, cn_str, speed_str, eta_str = match.groups()
                        done_b = parse_human_bytes(done_str)
                        total_b = parse_human_bytes(total_str)
                        speed_bps = float(parse_human_bytes(speed_str.replace('/s', '')))

                        progress_hook({
                            "status": "downloading",
                            "downloaded_bytes": done_b,
                            "total_bytes": total_b,
                            "speed": speed_bps,
                            "connections": int(cn_str),
                            "eta": eta_str or "0s"
                        })

            proc.wait()

            if proc.returncode == 0:
                if progress_hook:
                    progress_hook({"status": "finished"})
                return True
            else:
                if progress_hook:
                    progress_hook({"status": "error", "error": f"aria2c exited with code {proc.returncode}"})
                return False

        except Exception as e:
            if progress_hook:
                progress_hook({"status": "error", "error": str(e)})
            return False

    @classmethod
    def fetch_torrent_metadata(cls, magnet_url: str, save_dir: str, timeout_sec: int = 45) -> Optional[str]:
        """
        Connects to DHT / trackers and downloads only the .torrent metadata file without downloading payload.
        Returns the path to the downloaded .torrent file on success.
        """
        aria2_bin = cls.get_aria2_path()
        if not aria2_bin or not magnet_url.startswith("magnet:?"):
            return None

        os.makedirs(save_dir, exist_ok=True)
        cmd = cls.build_aria2_command(magnet_url, save_dir, metadata_only=True)
        cmd.append(f"--bt-stop-timeout={timeout_sec}")

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            proc.wait(timeout=timeout_sec + 5)
            # Find generated .torrent file in save_dir
            for f in os.listdir(save_dir):
                if f.endswith(".torrent"):
                    return os.path.join(save_dir, f)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        return None
