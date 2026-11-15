import os
import sys
import time
import logging
from logging.handlers import RotatingFileHandler
import traceback
from typing import Optional, Dict, Any, List

_FALCON_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE_PATH = os.path.join(_FALCON_ROOT, "falcondm_downloads.log")


class FalconLogger:
    """
    Centralized, thread-safe diagnostic and error logger for FalconDM.
    Maintains a persistent rotating log file (falcondm_downloads.log) to trace
    download attempts, HTTP responses, connection drops, SSL issues, and disk write errors.
    """

    _instance: Optional['FalconLogger'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FalconLogger, cls).__new__(cls)
            cls._instance._init_logger()
        return cls._instance

    def _init_logger(self):
        self.log_path = LOG_FILE_PATH
        self.logger = logging.getLogger("FalconDM")
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False

        # Clear existing handlers to prevent duplicate messages
        if self.logger.handlers:
            self.logger.handlers.clear()

        # 1. Rotating File Handler (up to 10MB per file, 3 backups)
        try:
            file_handler = RotatingFileHandler(
                self.log_path,
                maxBytes=10 * 1024 * 1024,
                backupCount=3,
                encoding="utf-8",
                delay=True
            )
            file_formatter = logging.Formatter(
                "[%(asctime)s] [%(levelname)s] [%(threadName)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            file_handler.setFormatter(file_formatter)
            file_handler.setLevel(logging.DEBUG)
            self.logger.addHandler(file_handler)
        except Exception as e:
            print(f"[FalconLogger Init Error]: Could not create file handler: {e}")

        # 2. Console Handler (UTF-8 safe)
        try:
            console_handler = logging.StreamHandler(sys.stdout)
            console_formatter = logging.Formatter("[FalconDM] %(levelname)s: %(message)s")
            console_handler.setFormatter(console_formatter)
            console_handler.setLevel(logging.INFO)
            self.logger.addHandler(console_handler)
        except Exception:
            pass

        self.info("=" * 60)
        self.info(f"FalconDM Logger initialized. Log target: {self.log_path}")
        self.info(f"Python: {sys.version.split()[0]} | Platform: {sys.platform}")
        self.info("=" * 60)

    def get_log_file_path(self) -> str:
        return self.log_path

    def info(self, msg: str):
        self.logger.info(msg)

    def warning(self, msg: str):
        self.logger.warning(msg)

    def error(self, msg: str, exc: Optional[Exception] = None):
        if exc:
            tb = traceback.format_exc()
            self.logger.error(f"{msg} | Exception: {exc}\n{tb}")
        else:
            self.logger.error(msg)

    def debug(self, msg: str):
        self.logger.debug(msg)

    def read_recent_logs(self, max_lines: int = 500) -> str:
        """Reads the most recent log entries for display in the UI log viewer."""
        if not os.path.exists(self.log_path):
            return "No log file found yet. Downloads and diagnostics will be logged here."
        try:
            with open(self.log_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
                if len(lines) > max_lines:
                    lines = lines[-max_lines:]
                return "".join(lines)
        except Exception as e:
            return f"Error reading log file: {e}"

    def clear_logs(self) -> bool:
        """Clears the current log file."""
        try:
            with open(self.log_path, "w", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [INFO] Log file cleared by user.\n")
            return True
        except Exception as e:
            self.error(f"Failed to clear log file: {e}")
            return False

    # ================= Specialized Download Tracers =================

    def log_task_created(self, task):
        url = getattr(task, "url", "unknown")
        fn = getattr(task, "filename", "unknown")
        sp = getattr(task, "save_path", "unknown")
        num_conn = getattr(task, "num_connections", 8)
        self.info(f"TASK_CREATED | ID: {getattr(task, 'task_id', '')} | File: '{fn}' | Connections: {num_conn} | SaveTo: {sp} | URL: {url}")

    def log_probe_attempt(self, task, candidate_url: str):
        self.debug(f"PROBE_START | File: '{getattr(task, 'filename', '')}' | Testing candidate URL: {candidate_url}")

    def log_probe_result(
        self,
        task,
        candidate_url: str,
        success: bool,
        status_code: Optional[int] = None,
        headers: Optional[Dict[str, Any]] = None,
        error_msg: Optional[str] = None
    ):
        fn = getattr(task, "filename", "")
        if success:
            content_len = headers.get("Content-Length", "unknown") if headers else "unknown"
            accept_ranges = headers.get("Accept-Ranges", "none") if headers else "none"
            server = headers.get("Server", "unknown") if headers else "unknown"
            content_type = headers.get("Content-Type", "unknown") if headers else "unknown"
            self.info(
                f"PROBE_SUCCESS | File: '{fn}' | HTTP {status_code} | Size: {content_len} bytes | "
                f"Ranges: {accept_ranges} | ContentType: {content_type} | Server: {server} | URL: {candidate_url}"
            )
        else:
            code_str = f"HTTP {status_code}" if status_code else "No HTTP Response"
            reason = error_msg or "Unknown error"
            self.warning(f"PROBE_FAILED | File: '{fn}' | {code_str} | Reason: {reason} | URL: {candidate_url}")

    def log_download_start(self, task):
        fn = getattr(task, "filename", "")
        size = getattr(task, "file_size", 0)
        resumable = getattr(task, "resumable", False)
        segs = len(getattr(task, "segments", []))
        self.info(f"DOWNLOAD_START | File: '{fn}' | Size: {size} bytes | Resumable: {resumable} | Active Threads: {segs}")

    def log_thread_error(
        self,
        task,
        segment_id: int,
        error: Exception,
        url: str,
        status_code: Optional[int] = None
    ):
        fn = getattr(task, "filename", "")
        status_part = f"HTTP {status_code} - " if status_code else ""
        err_str = str(error)
        
        # Diagnostic categorization
        hint = ""
        err_lower = err_str.lower()
        if "403" in err_str:
            hint = " [HINT: HTTP 403 Forbidden - URL token expired, Cloudflare challenge, or missing Referer/Cookies]"
        elif "401" in err_str:
            hint = " [HINT: HTTP 401 Unauthorized - Authentication credentials required]"
        elif "404" in err_str:
            hint = " [HINT: HTTP 404 Not Found - File URL does not exist or expired]"
        elif "416" in err_str:
            hint = " [HINT: HTTP 416 Range Not Satisfiable - Server does not allow multi-part byte ranges]"
        elif "ssl" in err_lower or "certificate" in err_lower:
            hint = " [HINT: SSL/TLS Handshake Error - Invalid certificate, proxy, or system date incorrect]"
        elif "10054" in err_str or "connection reset" in err_lower:
            hint = " [HINT: Connection Reset - Remote host dropped connection or network rate-limit reached]"
        elif "permission denied" in err_lower or "winerror 5" in err_lower or "winerror 32" in err_lower:
            hint = " [HINT: Disk Permission Error - Cannot write to destination path. Run as Admin or pick another folder]"
        elif "timeout" in err_lower:
            hint = " [HINT: Timeout - Server failed to respond within timeout window]"

        msg = f"THREAD_ERROR | File: '{fn}' | Thread #{segment_id} | {status_part}{err_str}{hint} | URL: {url}"
        self.error(msg)

        # Store recent error on task object for direct GUI inspect
        if hasattr(task, "diagnostic_log"):
            task.diagnostic_log.append(f"[{time.strftime('%H:%M:%S')}] Thread #{segment_id}: {status_part}{err_str}{hint}")
            if len(task.diagnostic_log) > 20:
                task.diagnostic_log.pop(0)

    def log_task_failure(self, task, reason: str, exc: Optional[Exception] = None):
        fn = getattr(task, "filename", "")
        url = getattr(task, "url", "")
        sp = getattr(task, "save_path", "")
        dl = getattr(task, "downloaded_bytes", 0)
        tot = getattr(task, "file_size", 0)
        self.error(
            f"TASK_FAILED | File: '{fn}' | Progress: {dl}/{tot} bytes | SavePath: '{sp}' | "
            f"Error: {reason} | URL: {url}",
            exc=exc
        )
        if hasattr(task, "diagnostic_log"):
            task.diagnostic_log.append(f"[{time.strftime('%H:%M:%S')}] CRITICAL: {reason}")

    def log_task_completed(self, task):
        fn = getattr(task, "filename", "")
        tot = getattr(task, "file_size", 0)
        sp = getattr(task, "save_path", "")
        dur = getattr(task, "duration_seconds", None)
        dur_str = f" in {dur:.1f}s" if dur else ""
        self.info(f"TASK_COMPLETED | File: '{fn}' ({tot} bytes){dur_str} -> '{sp}'")


falcon_logger = FalconLogger()
