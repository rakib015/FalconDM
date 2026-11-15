import os
import shutil
import tempfile
import subprocess
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Callable, Dict, Any, List
import requests

DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 FalconDM/2.0"

class HLSStreamGrabber:
    """Native HLS (.m3u8) parallel stream grabber and FFmpeg segment muxer."""

    @staticmethod
    def is_m3u8(url: str) -> bool:
        return bool(url and ".m3u8" in url.lower())

    @classmethod
    def download_hls(
        cls,
        m3u8_url: str,
        output_mp4_path: str,
        max_workers: int = 8,
        on_progress: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, Any]:
        """
        Parses m3u8 playlist, downloads .ts segments concurrently, and stitches them into MP4.
        """
        headers = {"User-Agent": DEFAULT_UA}
        try:
            resp = requests.get(m3u8_url, headers=headers, timeout=10)
            if resp.status_code != 200:
                return {"success": False, "message": f"HTTP {resp.status_code} fetching m3u8"}

            lines = resp.text.splitlines()
            ts_urls = []
            
            # Check if master playlist redirecting to highest quality
            sub_m3u8 = None
            for line in lines:
                line = line.strip()
                if line.endswith(".m3u8") or ".m3u8?" in line:
                    sub_m3u8 = urllib.parse.urljoin(m3u8_url, line)
            
            if sub_m3u8:
                resp = requests.get(sub_m3u8, headers=headers, timeout=10)
                lines = resp.text.splitlines()
                m3u8_url = sub_m3u8

            for line in lines:
                line = line.strip()
                if line and not line.startswith("#"):
                    full_ts = urllib.parse.urljoin(m3u8_url, line)
                    ts_urls.append(full_ts)

            if not ts_urls:
                return {"success": False, "message": "No TS video segments found in playlist"}

            # Download segments to temp dir
            temp_dir = tempfile.mkdtemp(prefix="falcondm_hls_")
            total = len(ts_urls)
            downloaded = 0

            def _download_ts(idx: int, url: str) -> tuple[int, str]:
                path = os.path.join(temp_dir, f"seg_{idx:05d}.ts")
                r = requests.get(url, headers=headers, timeout=15)
                with open(path, "wb") as f:
                    f.write(r.content)
                return idx, path

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(_download_ts, i, u) for i, u in enumerate(ts_urls)]
                for fut in as_completed(futures):
                    fut.result()
                    downloaded += 1
                    if on_progress:
                        try:
                            on_progress(downloaded, total)
                        except Exception:
                            pass

            # Create concat list for FFmpeg
            concat_txt = os.path.join(temp_dir, "concat.txt")
            with open(concat_txt, "w", encoding="utf-8") as f:
                for i in range(total):
                    seg_name = f"seg_{i:05d}.ts"
                    f.write(f"file '{seg_name}'\n")

            ffmpeg_bin = shutil.which("ffmpeg")
            if not ffmpeg_bin:
                shutil.rmtree(temp_dir, ignore_errors=True)
                return {"success": False, "message": "FFmpeg not found to mux HLS stream"}

            cmd = f'"{ffmpeg_bin}" -y -f concat -safe 0 -i "{concat_txt}" -c copy "{output_mp4_path}"'
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            shutil.rmtree(temp_dir, ignore_errors=True)

            if proc.returncode == 0 and os.path.exists(output_mp4_path):
                return {"success": True, "path": output_mp4_path, "segments": total}
            else:
                return {"success": False, "message": f"FFmpeg concat failed: {proc.stderr[:200]}"}

        except Exception as e:
            return {"success": False, "message": str(e)}
