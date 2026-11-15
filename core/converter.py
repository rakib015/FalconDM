import os
import re
import sys
import shutil
import subprocess
import threading
from typing import Optional, Callable, Dict, Any

class MediaConverter:
    """Built-in Audio & Video Converter & Stream Extractor powered by FFmpeg."""

    _cached_ffmpeg: Optional[str] = None

    @classmethod
    def get_ffmpeg_path(cls) -> Optional[str]:
        if cls._cached_ffmpeg and os.path.isfile(cls._cached_ffmpeg):
            return cls._cached_ffmpeg

        # 1. System PATH
        p = shutil.which("ffmpeg")
        if p:
            cls._cached_ffmpeg = p
            return p

        # 2. Gyan WinGet Packages directory
        local_app = os.environ.get("LOCALAPPDATA", "")
        if local_app:
            base_dir = os.path.join(local_app, "Microsoft", "WinGet", "Packages")
            if os.path.isdir(base_dir):
                for root, _, files in os.walk(base_dir):
                    if "ffmpeg.exe" in files:
                        full_p = os.path.join(root, "ffmpeg.exe")
                        cls._cached_ffmpeg = full_p
                        return full_p

        return None

    @classmethod
    def get_media_duration(cls, filepath: str) -> float:
        """Extracts total duration of media file in seconds using ffmpeg."""
        ffmpeg_bin = cls.get_ffmpeg_path()
        if not ffmpeg_bin or not os.path.isfile(filepath):
            return 0.0

        cmd = [ffmpeg_bin, "-i", filepath]
        try:
            proc = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True, errors='ignore')
            m = re.search(r'Duration:\s*(\d+):(\d+):(\d+\.\d+)', proc.stderr)
            if m:
                hours, mins, secs = m.groups()
                return int(hours) * 3600 + int(mins) * 60 + float(secs)
        except Exception:
            pass
        return 0.0

    @classmethod
    def convert(
        cls,
        input_path: str,
        target_format: str,
        output_dir: Optional[str] = None,
        resolution: Optional[str] = None,
        progress_hook: Optional[Callable[[float], None]] = None,
        stop_event: Optional[threading.Event] = None
    ) -> Optional[str]:
        """
        Converts media or extracts audio to target format (MP3, MP4, MKV, WAV, FLAC, M4A).
        Returns the output file path on success, None on error.
        """
        ffmpeg_bin = cls.get_ffmpeg_path()
        if not ffmpeg_bin or not os.path.isfile(input_path):
            return None

        base_name = os.path.splitext(os.path.basename(input_path))[0]
        out_ext = target_format.lower().replace(".", "")
        dest_dir = output_dir or os.path.dirname(input_path)
        os.makedirs(dest_dir, exist_ok=True)
        out_path = os.path.join(dest_dir, f"{base_name}_converted.{out_ext}")

        total_duration = cls.get_media_duration(input_path)

        cmd = [ffmpeg_bin, "-y", "-i", input_path]

        # Resolution filter
        if resolution and resolution in ("1080p", "720p", "480p", "360p"):
            height = resolution.replace("p", "")
            cmd.extend(["-vf", f"scale=-2:{height}"])

        # Format-specific encoding flags
        if out_ext == "mp3":
            cmd.extend(["-vn", "-c:a", "libmp3lame", "-b:a", "320k"])
        elif out_ext == "wav":
            cmd.extend(["-vn", "-c:a", "pcm_s16le"])
        elif out_ext == "flac":
            cmd.extend(["-vn", "-c:a", "flac"])
        elif out_ext == "m4a":
            cmd.extend(["-vn", "-c:a", "aac", "-b:a", "256k"])
        elif out_ext == "mkv":
            cmd.extend(["-c", "copy"])
        elif out_ext == "mp4":
            cmd.extend(["-c:v", "libx264", "-preset", "fast", "-crf", "22", "-c:a", "aac", "-b:a", "192k"])
        else:
            cmd.extend(["-c:a", "copy", "-c:v", "copy"])

        cmd.append(out_path)

        try:
            proc = subprocess.Popen(
                cmd,
                stderr=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                errors='ignore',
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )

            time_regex = re.compile(r'time=(\d+):(\d+):(\d+\.\d+)')

            if proc.stderr:
                for line in proc.stderr:
                    if stop_event and stop_event.is_set():
                        proc.terminate()
                        if os.path.exists(out_path):
                            try: os.remove(out_path)
                            except Exception: pass
                        return None

                    match = time_regex.search(line)
                    if match and total_duration > 0 and progress_hook:
                        h, m, s = match.groups()
                        curr_sec = int(h) * 3600 + int(m) * 60 + float(s)
                        pct = min(100.0, (curr_sec / total_duration) * 100.0)
                        progress_hook(pct)

            proc.wait()

            if proc.returncode == 0 and os.path.isfile(out_path):
                if progress_hook:
                    progress_hook(100.0)
                return out_path
            return None

        except Exception as e:
            print(f"[FalconDM MediaConverter] Conversion error: {e}")
            return None

    @classmethod
    def compress_for_discord(
        cls,
        input_path: str,
        target_size_mb: float = 24.0,
        output_dir: Optional[str] = None,
        progress_hook: Optional[Callable[[float], None]] = None,
        stop_event: Optional[threading.Event] = None
    ) -> Optional[str]:
        """
        Compresses any video down to exact target megabytes (e.g. 24MB for Discord 25MB limit)
        using calculated 2-pass bitrate allocation and AAC audio.
        """
        ffmpeg_bin = cls.get_ffmpeg_path()
        if not ffmpeg_bin or not os.path.isfile(input_path):
            return None

        duration = cls.get_media_duration(input_path)
        if duration <= 0:
            return None

        # Calculate exact target video bitrate in kbits/s
        target_total_kbits = (target_size_mb * 8192)  # 24MB * 8192 kb
        total_bitrate_kbps = target_total_kbits / duration
        audio_bitrate_kbps = 96
        video_bitrate_kbps = max(100, int(total_bitrate_kbps - audio_bitrate_kbps))

        base_name = os.path.splitext(os.path.basename(input_path))[0]
        dest_dir = output_dir or os.path.dirname(input_path)
        os.makedirs(dest_dir, exist_ok=True)
        out_path = os.path.join(dest_dir, f"{base_name}_discord_{int(target_size_mb)}mb.mp4")

        cmd = [
            ffmpeg_bin, "-y", "-i", input_path,
            "-c:v", "libx264",
            "-b:v", f"{video_bitrate_kbps}k",
            "-maxrate", f"{int(video_bitrate_kbps * 1.25)}k",
            "-bufsize", f"{int(video_bitrate_kbps * 2)}k",
            "-preset", "faster",
            "-c:a", "aac",
            "-b:a", f"{audio_bitrate_kbps}k",
            "-movflags", "+faststart",
            out_path
        ]

        try:
            proc = subprocess.Popen(
                cmd,
                stderr=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                errors='ignore',
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )

            time_regex = re.compile(r'time=(\d+):(\d+):(\d+\.\d+)')
            if proc.stderr:
                for line in proc.stderr:
                    if stop_event and stop_event.is_set():
                        proc.terminate()
                        if os.path.exists(out_path):
                            try: os.remove(out_path)
                            except Exception: pass
                        return None

                    m = time_regex.search(line)
                    if m and duration > 0 and progress_hook:
                        h, mn, s = m.groups()
                        curr_sec = int(h) * 3600 + int(mn) * 60 + float(s)
                        progress_hook(min(100.0, (curr_sec / duration) * 100.0))

            proc.wait()
            if proc.returncode == 0 and os.path.isfile(out_path):
                if progress_hook:
                    progress_hook(100.0)
                return out_path
            return None
        except Exception as e:
            print(f"[FalconDM MediaConverter] Discord compression error: {e}")
            return None

    @classmethod
    def extract_subtitles(cls, input_path: str, output_path: Optional[str] = None) -> Optional[str]:
        """Extracts embedded subtitle stream (.srt) from video file."""
        ffmpeg_bin = cls.get_ffmpeg_path()
        if not ffmpeg_bin or not os.path.isfile(input_path):
            return None

        out = output_path or os.path.splitext(input_path)[0] + ".srt"
        cmd = [ffmpeg_bin, "-y", "-i", input_path, "-map", "0:s:0?", "-c:s", "srt", out]
        try:
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
            if res.returncode == 0 and os.path.isfile(out) and os.path.getsize(out) > 0:
                return out
        except Exception:
            pass
        return None
