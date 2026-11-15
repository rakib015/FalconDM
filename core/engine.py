import os
import re
import time
import math
import queue
import socket
import urllib.parse
import threading
import requests
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection
from typing import Dict, List, Optional, Callable
from core.credential_manager import credential_store
try:
    from core.logger import falcon_logger
except ImportError:
    from .logger import falcon_logger

DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 FalconDM/2.0"

class TurboHTTPAdapter(HTTPAdapter):
    """High-throughput HTTP adapter with TCP_NODELAY and tuned 512KB socket buffer."""
    def init_poolmanager(self, *args, **kwargs):
        sock_opts = list(getattr(HTTPConnection, 'default_socket_options', []))
        if hasattr(socket, 'TCP_NODELAY'):
            sock_opts.append((socket.IPPROTO_TCP, socket.TCP_NODELAY, 1))
        if hasattr(socket, 'SO_RCVBUF'):
            sock_opts.append((socket.SOL_SOCKET, socket.SO_RCVBUF, 512 * 1024))
        kwargs['socket_options'] = sock_opts
        super().init_poolmanager(*args, **kwargs)

class TokenBucketRateLimiter:
    """Precision token bucket rate limiter for thread-safe bandwidth shaping."""
    def __init__(self, rate_bps: int = 0):
        self.rate_bps = max(0, rate_bps)
        self.tokens = float(self.rate_bps)
        self.last_update = time.time()
        self._lock = threading.Lock()

    def set_rate(self, rate_bps: int):
        with self._lock:
            self.rate_bps = max(0, rate_bps)
            self.tokens = float(self.rate_bps)
            self.last_update = time.time()

    def consume(self, amount: int):
        if self.rate_bps <= 0:
            return
        while True:
            with self._lock:
                now = time.time()
                elapsed = now - self.last_update
                self.last_update = now
                self.tokens = min(float(self.rate_bps), self.tokens + elapsed * self.rate_bps)
                if self.tokens >= amount:
                    self.tokens -= amount
                    return
                needed = amount - self.tokens
                wait_time = max(0.005, min(0.1, needed / self.rate_bps))
            time.sleep(wait_time)

class Segment:
    def __init__(self, segment_id: int, start: int, end: int, current: Optional[int] = None, status: str = "pending"):
        self.segment_id = segment_id
        self.start = start
        self.end = end
        self.current = current if current is not None else start
        self.status = status  # pending, downloading, completed, error
        self.error_msg = ""
        self.speed = 0.0
        self.last_bytes = 0
        self.last_time = time.time()
        self.last_progress_time = time.time()
        self.stall_count = 0
        self.active_response = None
        self.kick_requested = False

    @property
    def total_bytes(self) -> int:
        return max(0, self.end - self.start + 1)

    @property
    def downloaded_bytes(self) -> int:
        return max(0, self.current - self.start)

    @property
    def remaining_bytes(self) -> int:
        return max(0, self.end - self.current + 1)

    @property
    def progress_pct(self) -> float:
        if self.total_bytes <= 0:
            return 100.0
        return min(100.0, (self.downloaded_bytes / self.total_bytes) * 100.0)

    def to_dict(self) -> dict:
        return {
            "id": self.segment_id,
            "start": self.start,
            "end": self.end,
            "current": self.current,
            "status": self.status,
            "stall_count": getattr(self, "stall_count", 0)
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Segment':
        seg = cls(
            segment_id=data["id"],
            start=data["start"],
            end=data["end"],
            current=data.get("current", data["start"]),
            status=data.get("status", "pending")
        )
        seg.stall_count = data.get("stall_count", 0)
        return seg


class DownloadTask:
    STATUS_QUEUED = "Queued"
    STATUS_CONNECTING = "Connecting"
    STATUS_DOWNLOADING = "Downloading"
    STATUS_PAUSED = "Paused"
    STATUS_COMPLETED = "Completed"
    STATUS_ERROR = "Error"
    STATUS_CANCELED = "Canceled"

    PRIORITY_LOW = 0
    PRIORITY_NORMAL = 1
    PRIORITY_HIGH = 2

    queue_name: str = "Default"

    def __init__(
        self,
        task_id: str,
        url: str,
        save_path: str,
        num_connections: int = 8,
        category: str = "General",
        headers: Optional[Dict[str, str]] = None,
        mirrors: Optional[List[str]] = None,
        priority: int = 1,
        sequential_mode: bool = False
    ):
        self.task_id = task_id
        self.url = url
        self.save_path = save_path
        self.filename = os.path.basename(save_path)
        self.num_connections = max(1, min(32, num_connections))
        self.category = category
        self.headers = headers or {}
        self.mirrors: List[str] = mirrors or []
        self.active_mirror_index = -1
        self.priority = priority
        self.sequential_mode = sequential_mode
        
        self.status = self.STATUS_QUEUED
        self.file_size = 0
        self.resumable = False
        self.error_message = ""
        self.etag = ""
        self.queue_name = "Default"
        
        self.segments: List[Segment] = []
        self._threads: List[threading.Thread] = []
        self._stop_event = threading.Event()
        self._file_lock = threading.Lock()
        
        # Performance tracking
        self.downloaded_bytes = 0
        self.speed_bps = 0.0
        self.eta_seconds = 0
        self._speed_samples = []
        self._last_calc_time = time.time()
        self._last_downloaded = 0
        
        # Speed limiter (0 = unlimited, otherwise bytes/sec)
        self.speed_limit_bps = 0
        self._throttle_lock = threading.Lock()
        self._segment_lock = threading.RLock()
        self.rate_limiter = TokenBucketRateLimiter(self.speed_limit_bps)

        # Smart Auto-Retry & Resilience
        self.auto_retry_count = 0
        self.max_auto_retries = 10
        self.auto_retry_enabled = True
        self.stalled_timeout = 8.0  # Ultra-responsive 8s stall detection & kick

        # High-performance HTTP connection pool for TCP/TLS handshake reuse with TCP_NODELAY & 512KB buffer
        self._session = requests.Session()
        adapter = TurboHTTPAdapter(pool_connections=24, pool_maxsize=32, max_retries=3)
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)

        # Callbacks
        self.on_progress: Optional[Callable[['DownloadTask'], None]] = None
        self.on_status_change: Optional[Callable[['DownloadTask'], None]] = None
        self.diagnostic_log: List[str] = []

        # Checksum / Cryptographic Integrity Verification (aria2 / Motrix / IDM standard)
        self.checksum_expected: Optional[str] = None
        self.checksum_type: Optional[str] = None
        self.checksum_verified: Optional[bool] = None
        self._sniff_checksum_from_url()

        try:
            falcon_logger.log_task_created(self)
        except Exception:
            pass

    def _sniff_checksum_from_url(self) -> None:
        """Auto-sniffs cryptographic hashes from URL fragments or query parameters (e.g. #sha256=...)."""
        if not self.url or self.checksum_expected:
            return
        m = re.search(r'[#&?](sha256|sha512|sha1|md5)=([a-fA-F0-9]{32,128})', self.url, re.IGNORECASE)
        if m:
            self.checksum_type = m.group(1).lower()
            self.checksum_expected = m.group(2).lower()

    def verify_integrity(self) -> Optional[bool]:
        """Verifies downloaded file against expected checksum if configured."""
        if not self.checksum_expected or not os.path.isfile(self.save_path):
            return None
        try:
            from core.hasher import compute_checksums
            algo = self.checksum_type or 'sha256'
            sums = compute_checksums(self.save_path, [algo])
            calculated = sums.get(algo, '').lower()
            if calculated == self.checksum_expected.lower():
                self.checksum_verified = True
                falcon_logger.logger.info(f"Integrity check passed: {algo.upper()} verified for {self.filename}")
                return True
            else:
                self.checksum_verified = False
                falcon_logger.logger.warning(
                    f"Integrity check FAILED: {algo.upper()} mismatch for {self.filename} "
                    f"(Expected {self.checksum_expected}, got {calculated})"
                )
                return False
        except Exception as e:
            falcon_logger.logger.error(f"Integrity verification error for {self.filename}: {e}")
            return None

    def _build_request_headers(self) -> Dict[str, str]:
        """Constructs browser-grade anti-bot headers with Cloudflare, Akamai and CDN bypass."""
        cred_headers = credential_store.get_auth_headers(self.url)
        import sys
        platform_name = '"Linux"' if sys.platform.startswith('linux') else ('"macOS"' if sys.platform == 'darwin' else '"Windows"')
        headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "*/*",
            "Accept-Encoding": "identity",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": platform_name,
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site",
        }
        headers.update(cred_headers)
        headers.update(self.headers)

        # Synthesize Origin from Referer if missing
        if "Referer" in headers and "Origin" not in headers:
            try:
                ref_parsed = urllib.parse.urlparse(headers["Referer"])
                if ref_parsed.scheme and ref_parsed.netloc:
                    headers["Origin"] = f"{ref_parsed.scheme}://{ref_parsed.netloc}"
            except Exception:
                pass
        return headers

    def set_speed_limit(self, bps: int):
        """Dynamically sets speed limit in bytes per second (0 = unlimited)."""
        self.speed_limit_bps = max(0, bps)
        self.rate_limiter.set_rate(self.speed_limit_bps)

    def probe(self) -> bool:
        """Probes the remote URL to determine file size, resume capability, and optimal filename, with mirror failover."""
        self.status = self.STATUS_CONNECTING
        self._notify_status()
        
        candidate_urls = [self.url] + [m for m in self.mirrors if m and m != self.url]
        last_error = ""

        for candidate in candidate_urls:
            try:
                falcon_logger.log_probe_attempt(self, candidate)
                auth_tuple = credential_store.get_auth_tuple(candidate)
                req_headers = self._build_request_headers()
                
                # 1. Try HEAD request
                resp = self._session.head(candidate, headers=req_headers, auth=auth_tuple, allow_redirects=True, timeout=12)
                
                # If server blocks HEAD or returns 405/403, fall back to range GET
                if resp.status_code >= 400 or "Content-Length" not in resp.headers:
                    probe_headers = req_headers.copy()
                    probe_headers["Range"] = "bytes=0-0"
                    resp = self._session.get(candidate, headers=probe_headers, auth=auth_tuple, stream=True, allow_redirects=True, timeout=12)
                    resp.close()

                if resp.status_code >= 400:
                    last_error = f"HTTP {resp.status_code} - {getattr(resp, 'reason', 'Error')}"
                    falcon_logger.log_probe_result(self, candidate, False, status_code=resp.status_code, error_msg=last_error)
                    continue

                # Candidate responded successfully! Set as active url
                self.url = candidate

                # Determine Filename
                cd = resp.headers.get("Content-Disposition", "")
                detected_filename = None
                if cd:
                    fname_match = re.findall(r'filename\*?=(?:UTF-8\'\')?["\']?([^"\';\r\n]+)', cd, re.IGNORECASE)
                    if fname_match:
                        detected_filename = urllib.parse.unquote(fname_match[0].strip())
                
                if not detected_filename:
                    parsed_url = urllib.parse.urlparse(resp.url or self.url)
                    path_part = parsed_url.path.strip("/")
                    if path_part:
                        detected_filename = urllib.parse.unquote(os.path.basename(path_part))
                
                if not detected_filename:
                    detected_filename = "download_" + self.task_id[:8]
                
                # Sanitize filename
                detected_filename = re.sub(r'[\\/*?:"<>|]', "_", detected_filename)
                save_dir = os.path.dirname(self.save_path) or os.getcwd()
                self.save_path = os.path.join(save_dir, detected_filename)
                self.filename = detected_filename

                # Determine File Size
                if "Content-Range" in resp.headers:
                    cr_match = re.search(r'/(\d+)', resp.headers["Content-Range"])
                    if cr_match:
                        self.file_size = int(cr_match.group(1))
                elif "Content-Length" in resp.headers:
                    self.file_size = int(resp.headers["Content-Length"])
                else:
                    self.file_size = 0

                # Determine Resumability
                accept_ranges = resp.headers.get("Accept-Ranges", "").lower()
                self.resumable = (accept_ranges == "bytes" or "Content-Range" in resp.headers) and (self.file_size > 0)
                self.etag = resp.headers.get("ETag", "").strip('"')

                falcon_logger.log_probe_result(
                    self, candidate, True,
                    status_code=getattr(resp, "status_code", 200),
                    headers=dict(resp.headers)
                )
                return True
            except Exception as e:
                last_error = str(e)
                falcon_logger.log_probe_result(self, candidate, False, error_msg=last_error)
                continue

        self.status = self.STATUS_ERROR
        self.error_message = f"Connection probe failed: {last_error}"
        falcon_logger.log_task_failure(self, self.error_message)
        self._notify_status()
        return False

    def can_preview_media(self) -> bool:
        """Determines if enough initial media container metadata has downloaded to play in VLC/media player."""
        if not os.path.exists(self.save_path):
            return False
        media_exts = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".mp3", ".wav", ".aac", ".m4a"}
        ext = os.path.splitext(self.filename.lower())[1]
        if ext not in media_exts and getattr(self, "category", "") not in ("Video", "Audio"):
            return False
        return self.downloaded_bytes >= 1024 * 1024 or self.progress_pct >= 2.0

    def launch_preview(self) -> bool:
        """Launches partial media stream in VLC or OS default video player."""
        try:
            from core.platform_utils import launch_in_media_player
            return launch_in_media_player(self.save_path)
        except Exception:
            return False

    def init_segments(self):
        """Initializes byte segments based on file size, target connection threads, and sequential mode."""
        if not self.resumable or self.file_size <= 0:
            # Single stream segment
            seg = Segment(0, 0, self.file_size - 1 if self.file_size > 0 else 0)
            if self.downloaded_bytes > 0:
                seg.current = self.downloaded_bytes
            self.segments = [seg]
            return

        if getattr(self, "sequential_mode", False) and self.file_size > 4 * 1024 * 1024 and self.num_connections > 1:
            # Sequential streaming mode for instant media playback:
            # Segment 0: Head of file (first 4MB or 4%)
            # Segment 1: Tail of file (last 4MB or 4% - contains MP4 moov / MKV cues)
            # Remaining segments: sequential chunks across the middle
            head_size = min(4 * 1024 * 1024, int(self.file_size * 0.04))
            tail_size = min(4 * 1024 * 1024, int(self.file_size * 0.04))
            mid_start = head_size
            mid_end = max(mid_start, self.file_size - tail_size - 1)

            self.segments = [
                Segment(0, 0, head_size - 1),
                Segment(1, self.file_size - tail_size, self.file_size - 1)
            ]
            rem_connections = max(1, self.num_connections - 2)
            mid_len = max(0, mid_end - mid_start + 1)
            part_size = mid_len // rem_connections
            for i in range(rem_connections):
                s = mid_start + (i * part_size)
                e = mid_end if i == rem_connections - 1 else (s + part_size - 1)
                self.segments.append(Segment(len(self.segments), s, e))
            return

        # Multi-thread segmented calculation
        part_size = self.file_size // self.num_connections
        self.segments = []
        for i in range(self.num_connections):
            start = i * part_size
            end = self.file_size - 1 if i == self.num_connections - 1 else (start + part_size - 1)
            self.segments.append(Segment(i, start, end))

    def start(self):
        """Starts or resumes the download across active segment workers."""
        if self.status == self.STATUS_DOWNLOADING:
            return
        
        self._stop_event.clear()
        
        # Probe first if file_size is unverified
        if self.file_size == 0 and not self.segments:
            if not self.probe():
                return

        # Prepare segment definitions
        if not self.segments:
            self.init_segments()

        # Fast pre-allocate file if new
        try:
            from core.platform_utils import fast_preallocate_file
            if not os.path.exists(self.save_path) and self.file_size > 0:
                fast_preallocate_file(self.save_path, self.file_size)
            else:
                os.makedirs(os.path.dirname(os.path.abspath(self.save_path)), exist_ok=True)
                if not os.path.exists(self.save_path):
                    with open(self.save_path, "wb") as f:
                        pass
        except Exception as e:
            self.status = self.STATUS_ERROR
            self.error_message = f"Could not allocate file: {str(e)}"
            falcon_logger.log_task_failure(self, self.error_message, exc=e)
            self._notify_status()
            return

        self.status = self.STATUS_DOWNLOADING
        falcon_logger.log_download_start(self)
        self._notify_status()

        # Recalculate downloaded bytes from segments
        self.downloaded_bytes = sum(s.downloaded_bytes for s in self.segments)
        self._last_downloaded = self.downloaded_bytes
        self._last_calc_time = time.time()

        # Launch worker threads
        self._threads = []
        if not self.resumable or len(self.segments) == 1:
            t = threading.Thread(target=self._single_stream_worker, daemon=True)
            self._threads.append(t)
            t.start()
        else:
            for segment in self.segments:
                if segment.current <= segment.end:
                    t = threading.Thread(target=self._segment_worker, args=(segment,), daemon=True)
                    self._threads.append(t)
                    t.start()

        # Launch dynamic watchdog/monitor thread
        monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        monitor_thread.start()

    def pause(self):
        """Gracefully pauses all segment threads."""
        if self.status != self.STATUS_DOWNLOADING:
            return
        self.status = self.STATUS_PAUSED
        self._stop_event.set()
        self.speed_bps = 0.0
        self.eta_seconds = 0
        self._notify_status()

    def cancel(self):
        """Cancels download and stops threads."""
        self.status = self.STATUS_CANCELED
        self._stop_event.set()
        self.speed_bps = 0.0
        self.eta_seconds = 0
        self._notify_status()

    def _segment_worker(self, initial_segment: Segment):
        """Worker thread with advanced End-Game dynamic work-stealing and chunk splitting."""
        curr = initial_segment
        idle_spins = 0
        max_spins = 6  # Retain thread alive for up to 3 seconds to assist lagging chunks
        while not self._stop_event.is_set():
            if curr:
                self._download_segment_range(curr)
                idle_spins = 0
            if self._stop_event.is_set():
                break

            # Adaptive End-Game threshold:
            # As download nears completion, reduce split threshold so all connections finish in parallel
            pct = self.progress_pct
            if pct >= 95.0:
                threshold = 256 * 1024       # 256 KB in final stretch
            elif pct >= 80.0:
                threshold = 512 * 1024       # 512 KB in end-game
            else:
                threshold = 1024 * 1024      # 1 MB standard

            curr = self._steal_and_split_segment(min_size=threshold)
            if not curr:
                idle_spins += 1
                if idle_spins >= max_spins or all(s.status == "completed" or s.current > s.end for s in self.segments):
                    break
                time.sleep(0.5)

    def _download_segment_range(self, segment: Segment):
        """Downloads the byte range of a single segment with ultra-low CPU overhead, stall auto-kick, and optimized disk streaming."""
        segment.status = "downloading"
        chunk_size = 256 * 1024  # 256KB optimized buffer for maximum throughput
        
        auth_tuple = credential_store.get_auth_tuple(self.url)
        req_headers = self._build_request_headers()
        
        retry_count = 0
        max_retries = 5

        while segment.current <= segment.end and not self._stop_event.is_set():
            try:
                headers = req_headers.copy()
                headers["Range"] = f"bytes={segment.current}-{segment.end}"
                
                resp = self._session.get(self.url, headers=headers, auth=auth_tuple, stream=True, timeout=15)
                segment.active_response = resp
                now_start = time.time()
                segment.last_progress_time = now_start
                segment.kick_requested = False
                
                if resp.status_code not in (200, 206):
                    err_txt = f"HTTP {resp.status_code} - {getattr(resp, 'reason', 'Error')}"
                    falcon_logger.log_thread_error(self, segment.segment_id, Exception(err_txt), self.url, status_code=resp.status_code)
                    raise Exception(err_txt)

                # Range integrity check: If server returned 200 OK instead of 206 Partial Content,
                # the server ignored the Range header and sent the entire file starting at byte 0.
                if resp.status_code == 200:
                    if len(self.segments) > 1 or segment.current > 0:
                        if segment.segment_id == 0 and segment.current == 0:
                            # Segment 0 has the valid full stream from byte 0. Convert this task to single-stream.
                            falcon_logger.logger.warning(
                                f"[Task {self.task_id}] Server returned HTTP 200 OK instead of 206 Partial Content. "
                                f"Range requests unsupported; smoothly converting in-flight to single-connection stream."
                            )
                            self.resumable = False
                            with self._segment_lock:
                                for s in self.segments[1:]:
                                    s.status = "canceled"
                                    s.current = s.end + 1
                                self.segments = [segment]
                            segment.end = self.file_size - 1 if self.file_size > 0 else 0
                        else:
                            # Non-zero segment received 200 OK: MUST NOT write byte 0 at segment.current!
                            try:
                                resp.close()
                            except Exception:
                                pass
                            segment.active_response = None
                            err_txt = f"HTTP 200 returned for range {segment.current}-{segment.end}. Server does not support byte ranges."
                            falcon_logger.log_thread_error(self, segment.segment_id, Exception(err_txt), self.url, status_code=200)
                            raise Exception(err_txt)

                with open(self.save_path, "r+b") as f:
                    for chunk in resp.iter_content(chunk_size=chunk_size):
                        if self._stop_event.is_set() or segment.kick_requested:
                            break
                        if chunk:
                            chunk_len = len(chunk)
                            # Respect dynamic split: don't write past segment.end if end was lowered
                            if segment.current + chunk_len - 1 > segment.end:
                                chunk = chunk[:max(0, segment.end - segment.current + 1)]
                                chunk_len = len(chunk)
                                if chunk_len == 0:
                                    break

                            # Apply token bucket rate limiting only when rate limit is active
                            if self.speed_limit_bps > 0:
                                self.rate_limiter.consume(chunk_len)

                            # Zero-lock direct write to thread's independent segment offset
                            f.seek(segment.current)
                            f.write(chunk)

                            now_c = time.time()
                            segment.current += chunk_len
                            segment.last_time = now_c
                            segment.last_progress_time = now_c
                            self.downloaded_bytes += chunk_len

                    try:
                        f.flush()
                    except Exception:
                        pass

                try:
                    resp.close()
                except Exception:
                    pass
                segment.active_response = None

                if segment.kick_requested:
                    segment.kick_requested = False
                    time.sleep(0.05)
                    continue

                if segment.current > segment.end:
                    segment.status = "completed"
                    break

            except Exception as e:
                segment.active_response = None
                if segment.kick_requested:
                    segment.kick_requested = False
                    time.sleep(0.05)
                    continue

                retry_count += 1
                segment.status = "error"
                segment.error_msg = str(e)
                falcon_logger.log_thread_error(self, segment.segment_id, e, self.url)
                if retry_count > max_retries or self._stop_event.is_set():
                    break
                # Failover to mirror if available
                if self.mirrors and retry_count >= 2:
                    self.active_mirror_index = (self.active_mirror_index + 1) % len(self.mirrors)
                    self.url = self.mirrors[self.active_mirror_index]
                backoff_time = min(6.0, 1.0 * (1.4 ** retry_count))
                time.sleep(backoff_time)  # Exponential backoff before retry

        if segment.current > segment.end:
            segment.status = "completed"
        elif self._stop_event.is_set():
            segment.status = "paused"

    def _single_stream_worker(self):
        """Worker thread for non-resumable or single-thread downloads with asynchronous disk buffering and auto-retry."""
        segment = self.segments[0]
        segment.status = "downloading"
        chunk_size = 256 * 1024  # 256KB buffer
        
        auth_tuple = credential_store.get_auth_tuple(self.url)
        req_headers = self._build_request_headers()
        
        retry_count = 0
        max_retries = 5

        while not self._stop_event.is_set() and (self.file_size == 0 or segment.current <= segment.end):
            # If resuming single stream with range
            if segment.current > 0 and self.resumable:
                req_headers["Range"] = f"bytes={segment.current}-"
                mode = "r+b"
            else:
                mode = "r+b" if os.path.exists(self.save_path) and segment.current > 0 else "wb"
                if mode == "wb":
                    segment.current = 0
                    self.downloaded_bytes = 0

            try:
                resp = self._session.get(self.url, headers=req_headers, auth=auth_tuple, stream=True, timeout=20)
                if resp.status_code not in (200, 206):
                    err_txt = f"HTTP {resp.status_code} - {getattr(resp, 'reason', 'Error')}"
                    falcon_logger.log_thread_error(self, 0, Exception(err_txt), self.url, status_code=resp.status_code)
                    raise Exception(err_txt)

                # If we requested resume with Range but server returned 200 OK (server ignored Range)
                if segment.current > 0 and resp.status_code == 200:
                    falcon_logger.logger.warning(
                        f"[Task {self.task_id}] Requested resume at byte {segment.current}, but server returned 200 OK. "
                        f"Server does not support resume. Restarting cleanly from byte 0."
                    )
                    segment.current = 0
                    self.downloaded_bytes = 0
                    self.resumable = False
                    mode = "wb"

                with open(self.save_path, mode) as f:
                    if mode == "r+b":
                        f.seek(segment.current)
                    elif mode == "wb":
                        f.seek(0)
                        f.truncate(0)
                    for chunk in resp.iter_content(chunk_size=chunk_size):
                        if self._stop_event.is_set():
                            break
                        if chunk:
                            chunk_len = len(chunk)
                            if self.speed_limit_bps > 0:
                                self.rate_limiter.consume(chunk_len)
                            f.write(chunk)
                            segment.current += chunk_len
                            segment.last_time = time.time()
                            self.downloaded_bytes += chunk_len
                    try:
                        f.flush()
                    except Exception:
                        pass
                
                resp.close()
                if not self._stop_event.is_set():
                    segment.status = "completed"
                    if self.file_size == 0:
                        self.file_size = segment.current
                        segment.end = segment.current - 1
                    break
                else:
                    segment.status = "paused"
                    break
            except Exception as e:
                retry_count += 1
                segment.status = "error"
                self.error_message = str(e)
                falcon_logger.log_thread_error(self, 0, e, self.url)
                if retry_count > max_retries or self._stop_event.is_set():
                    falcon_logger.log_task_failure(self, f"Single stream worker failed: {e}", exc=e)
                    break
                time.sleep(min(8.0, 1.5 * retry_count))

    def _apply_throttle(self, bytes_transferred: int):
        """Applies voluntary speed limit if configured."""
        self.rate_limiter.consume(bytes_transferred)

    def _reconnect_and_resume(self):
        """Seamlessly revives stalled or errored connections without byte loss."""
        if self._stop_event.is_set():
            return
        
        # Fresh connection pool
        try:
            self._session.close()
            self._session = requests.Session()
            adapter = HTTPAdapter(pool_connections=24, pool_maxsize=32, max_retries=3)
            self._session.mount("http://", adapter)
            self._session.mount("https://", adapter)
        except Exception:
            pass

        self.error_message = ""
        self.status = self.STATUS_DOWNLOADING
        self._notify_status()

        if not self.resumable or len(self.segments) <= 1:
            if self.segments and self.segments[0].status != "completed":
                self.segments[0].status = "pending"
                t = threading.Thread(target=self._single_stream_worker, daemon=True)
                self._threads.append(t)
                t.start()
        else:
            for s in self.segments:
                if s.status in ("error", "pending") and s.current <= s.end:
                    s.status = "pending"
                    t = threading.Thread(target=self._segment_worker, args=(s,), daemon=True)
                    self._threads.append(t)
                    t.start()

    def _monitor_loop(self):
        """Monitors download throughput, segment status, detects stalls, and auto-recovers from network drops."""
        while not self._stop_event.is_set() and self.status in (self.STATUS_DOWNLOADING, "Auto-reconnecting"):
            time.sleep(0.5)
            now = time.time()
            dt = now - self._last_calc_time
            
            if dt >= 0.5:
                current_dl = sum(s.downloaded_bytes for s in self.segments) if self.segments else self.downloaded_bytes
                delta_bytes = current_dl - self._last_downloaded
                inst_speed = max(0.0, delta_bytes / dt)
                
                # Smoothed speed moving average
                self._speed_samples.append(inst_speed)
                if len(self._speed_samples) > 6:
                    self._speed_samples.pop(0)
                self.speed_bps = sum(self._speed_samples) / len(self._speed_samples)
                
                self.downloaded_bytes = current_dl
                self._last_downloaded = current_dl
                self._last_calc_time = now
                
                # Calculate ETA
                if self.file_size > 0 and self.speed_bps > 0:
                    rem_bytes = max(0, self.file_size - self.downloaded_bytes)
                    self.eta_seconds = int(rem_bytes / self.speed_bps)
                else:
                    self.eta_seconds = 0
                
                # Check for dynamic segment splitting if some threads finished early
                self._try_dynamic_split()
                
                self._notify_progress()

            # Check completion condition
            all_done = False
            if self.segments:
                all_done = all(s.status == "completed" or s.current > s.end for s in self.segments)
            
            if all_done:
                self.status = self.STATUS_COMPLETED
                self.speed_bps = 0.0
                self.eta_seconds = 0
                self.auto_retry_count = 0
                self.error_message = ""
                self.verify_integrity()
                falcon_logger.log_task_completed(self)
                self._notify_status()
                self._notify_progress()
                break

            # Proactive Stalled Segment Auto-Kick (prevents lingering hung connections)
            if self.status == self.STATUS_DOWNLOADING and not self._stop_event.is_set():
                now_mono = time.time()
                active_workers = sum(1 for s in self.segments if s.status == "downloading")
                if active_workers > 0:
                    for seg in self.segments:
                        if seg.status == "downloading" and seg.current <= seg.end:
                            idle_sec = now_mono - getattr(seg, 'last_progress_time', now_mono)
                            if idle_sec > self.stalled_timeout:
                                seg.stall_count = getattr(seg, 'stall_count', 0) + 1
                                seg.last_progress_time = now_mono
                                seg.kick_requested = True
                                resp_handle = getattr(seg, 'active_response', None)
                                if resp_handle is not None:
                                    try:
                                        resp_handle.raw.close()
                                    except Exception:
                                        pass

            # Smart Resilience: Check if all threads died before completion
            active_workers = sum(1 for s in self.segments if s.status == "downloading")
            has_errored = any(s.status == "error" for s in self.segments)

            if not all_done and active_workers == 0 and has_errored and not self._stop_event.is_set():
                # If segmented download failed due to lack of range support on server, immediately fall back to single stream
                if self.resumable and len(self.segments) > 1:
                    range_unsupported = any(
                        "does not support byte ranges" in getattr(s, "error_msg", "") or
                        "does not support byte ranges" in self.error_message
                        for s in self.segments
                    )
                    if range_unsupported:
                        falcon_logger.logger.warning(
                            f"[Task {self.task_id}] Byte ranges unsupported by server. Falling back automatically to clean single-stream."
                        )
                        self.resumable = False
                        with self._segment_lock:
                            self.segments = [Segment(0, 0, self.file_size - 1 if self.file_size > 0 else 0)]
                            self.downloaded_bytes = 0
                            self._last_downloaded = 0
                        if os.path.exists(self.save_path):
                            try:
                                with open(self.save_path, "wb") as f:
                                    f.truncate(0)
                            except Exception:
                                pass
                        self._reconnect_and_resume()
                        continue

                if self.auto_retry_enabled and self.auto_retry_count < self.max_auto_retries:
                    self.auto_retry_count += 1
                    backoff_sec = min(30, 2 * self.auto_retry_count)
                    self.status = "Auto-reconnecting"
                    for remaining in range(backoff_sec, 0, -1):
                        if self._stop_event.is_set():
                            break
                        self.error_message = f"Network connection lost. Auto-resuming in {remaining}s (Attempt {self.auto_retry_count}/{self.max_auto_retries})..."
                        self._notify_status()
                        time.sleep(1.0)

                    if not self._stop_event.is_set():
                        self._reconnect_and_resume()
                        continue
                else:
                    self.status = self.STATUS_ERROR
                    self.error_message = "Download stopped: Network connection lost (max retries reached)."
                    falcon_logger.log_task_failure(self, self.error_message)
                    self.speed_bps = 0.0
                    self.eta_seconds = 0
                    self._notify_status()
                    break

    def _steal_and_split_segment(self, min_size: int = 1024 * 1024) -> Optional[Segment]:
        """Finds the slowest or largest remaining active segment, dynamically bisects it, and returns a new sub-segment."""
        if not self.resumable or self._stop_event.is_set():
            return None
            
        with self._segment_lock:
            if len(self.segments) >= 32:
                return None
            
            candidates = [
                s for s in self.segments 
                if s.status == "downloading" and s.remaining_bytes >= min_size
            ]
            if not candidates:
                return None

            # Pick segment with the largest remaining bytes
            slowest = max(candidates, key=lambda s: s.remaining_bytes)
            remaining = slowest.remaining_bytes
            if remaining < min_size:
                return None

            # Split in half
            mid = slowest.current + (remaining // 2)
            old_end = slowest.end
            slowest.end = mid - 1

            new_seg = Segment(len(self.segments), mid, old_end)
            new_seg.status = "downloading"
            self.segments.append(new_seg)
            return new_seg

    def _try_dynamic_split(self):
        """Monitors download progress and triggers dynamic end-game splitting when threads idle."""
        if not self.resumable or len(self.segments) >= 32 or self._stop_event.is_set():
            return
        
        pct = self.progress_pct
        if pct >= 95.0:
            threshold = 256 * 1024
        elif pct >= 80.0:
            threshold = 512 * 1024
        else:
            threshold = 1024 * 1024

        active_count = sum(1 for s in self.segments if s.status == "downloading")
        completed_count = sum(1 for s in self.segments if s.status == "completed")
        
        if completed_count > 0 and active_count < min(self.num_connections, 32):
            new_seg = self._steal_and_split_segment(min_size=threshold)
            if new_seg:
                t = threading.Thread(target=self._segment_worker, args=(new_seg,), daemon=True)
                self._threads.append(t)
                t.start()

    def _notify_progress(self):
        if self.on_progress:
            try:
                self.on_progress(self)
            except Exception:
                pass

    def _notify_status(self):
        if self.on_status_change:
            try:
                self.on_status_change(self)
            except Exception:
                pass

    @property
    def progress_pct(self) -> float:
        if self.file_size <= 0:
            return 100.0 if self.status == self.STATUS_COMPLETED else 0.0
        return min(100.0, (self.downloaded_bytes / self.file_size) * 100.0)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "url": self.url,
            "save_path": self.save_path,
            "filename": self.filename,
            "num_connections": self.num_connections,
            "category": self.category,
            "status": self.status,
            "file_size": self.file_size,
            "downloaded_bytes": self.downloaded_bytes,
            "resumable": self.resumable,
            "etag": self.etag,
            "headers": self.headers,
            "queue_name": getattr(self, "queue_name", "Default"),
            "priority": getattr(self, "priority", 1),
            "sequential_mode": getattr(self, "sequential_mode", False),
            "mirrors": getattr(self, "mirrors", []),
            "speed_limit_bps": self.speed_limit_bps,
            "error_message": getattr(self, "error_message", ""),
            "diagnostic_log": getattr(self, "diagnostic_log", [])[-20:],
            "checksum_expected": getattr(self, "checksum_expected", None),
            "checksum_type": getattr(self, "checksum_type", None),
            "checksum_verified": getattr(self, "checksum_verified", None),
            "segments": [s.to_dict() for s in self.segments]
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'DownloadTask':
        task = cls(
            task_id=data["task_id"],
            url=data["url"],
            save_path=data["save_path"],
            num_connections=data.get("num_connections", 8),
            category=data.get("category", "General"),
            headers=data.get("headers", {}),
            mirrors=data.get("mirrors", []),
            priority=data.get("priority", 1),
            sequential_mode=data.get("sequential_mode", False)
        )
        task.filename = data.get("filename", os.path.basename(task.save_path))
        task.status = data.get("status", cls.STATUS_QUEUED)
        if task.status == cls.STATUS_DOWNLOADING:
            task.status = cls.STATUS_PAUSED
        task.file_size = data.get("file_size", 0)
        task.downloaded_bytes = data.get("downloaded_bytes", 0)
        task.resumable = data.get("resumable", False)
        task.etag = data.get("etag", "")
        task.queue_name = data.get("queue_name", "Default")
        task.priority = data.get("priority", 1)
        task.mirrors = data.get("mirrors", [])
        task.error_message = data.get("error_message", "")
        task.diagnostic_log = data.get("diagnostic_log", [])
        task.checksum_expected = data.get("checksum_expected", None)
        task.checksum_type = data.get("checksum_type", None)
        task.checksum_verified = data.get("checksum_verified", None)
        task.set_speed_limit(data.get("speed_limit_bps", 0))
        task.segments = [Segment.from_dict(s) for s in data.get("segments", [])]
        return task
