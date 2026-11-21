import os
import sys
import threading
from typing import Dict, List, Optional, Any, Callable, cast
import yt_dlp
from core.platform_utils import safe_print

class MediaGrabber:
    """Extracts video/audio streams from 1000+ websites (YouTube, Twitter/X, TikTok, Reddit, Instagram, etc.)."""

    @staticmethod
    def is_likely_media_url(url: str) -> bool:
        """Heuristic to detect media streaming platforms and direct media files from any website."""
        if not url:
            return False
        import urllib.parse
        url_lower = url.lower()

        # 1. Known media platforms
        domains = [
            "youtube.com", "youtu.be", "twitter.com", "x.com", "tiktok.com",
            "reddit.com", "instagram.com", "facebook.com", "fb.watch",
            "vimeo.com", "twitch.tv", "soundcloud.com", "dailymotion.com",
            "bilibili.com", "rumble.com", "odysee.com", "streamable.com",
            "threads.net", "vk.com", "pinterest.com", "loom.com",
            ".m3u8", ".mpd"
        ]
        if any(d in url_lower for d in domains):
            return True

        # 2. Direct media file extensions from any website
        try:
            parsed = urllib.parse.urlparse(url_lower)
            path = parsed.path
            media_exts = (
                ".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv", ".wmv",
                ".m4v", ".ts", ".3gp", ".f4v", ".vob", ".mpg", ".mpeg",
                ".mp3", ".m4a", ".aac", ".flac", ".wav", ".ogg", ".opus"
            )
            if any(path.endswith(ext) for ext in media_exts):
                return True
            if any(ext in url_lower for ext in (".mp4", ".mkv", ".webm", ".m3u8", ".mpd", ".flv", ".mov")):
                return True
        except Exception:
            pass

        return False

    @classmethod
    def _sanitize_media_headers(cls, headers: Optional[Dict[str, str]]) -> Dict[str, str]:
        """Filters out browser internal and CORS headers that cause streaming APIs (Facebook, YouTube, etc.) to reject requests."""
        if not headers:
            return {}
        clean = {}
        for k, v in headers.items():
            k_lower = k.lower()
            if k_lower in ('cookie', 'sec-fetch-dest', 'sec-fetch-mode', 'sec-fetch-site', 
                           'sec-fetch-user', 'sec-ch-ua', 'sec-ch-ua-mobile', 'sec-ch-ua-platform',
                           'origin', 'referer', 'accept', 'accept-language'):
                continue
            clean[k] = v
        return clean

    @classmethod
    def probe_media(cls, url: str, headers: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
        """Extracts title, thumbnail, duration, and format options without downloading."""
        import shutil
        ffmpeg_bin = shutil.which('ffmpeg')
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'windowsfilenames': True,
            'socket_timeout': 15,
            'nocheckcertificate': True,
        }
        if ffmpeg_bin:
            ydl_opts['ffmpeg_location'] = ffmpeg_bin

        clean_hdrs = cls._sanitize_media_headers(headers)
        if clean_hdrs:
            ydl_opts['http_headers'] = clean_hdrs

        info = None
        try:
            with yt_dlp.YoutubeDL(cast(Any, ydl_opts)) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception:
            # If request failed with headers, immediately retry without headers
            if 'http_headers' in ydl_opts:
                ydl_opts.pop('http_headers', None)
                try:
                    with yt_dlp.YoutubeDL(cast(Any, ydl_opts)) as ydl:
                        info = ydl.extract_info(url, download=False)
                except Exception as e:
                    info = None
            else:
                info = None

        if info:
            title = info.get('title', 'media_download')
            thumbnail = info.get('thumbnail', '')
            duration = info.get('duration', 0)
            uploader = info.get('uploader', '')

            # Filter formats to high quality user-friendly list
            raw_formats: List[Any] = info.get('formats') or []
            clean_formats = []
            seen_res = set()

            subtitles_dict = info.get('subtitles') or {}
            auto_caps = info.get('automatic_captions') or {}
            has_subtitles = bool(subtitles_dict or auto_caps)
            available_subs = list(subtitles_dict.keys()) or list(auto_caps.keys())

            for f in raw_formats:
                format_id = f.get('format_id')
                height = f.get('height')
                fps = f.get('fps')
                ext = f.get('ext', 'mp4')
                filesize = f.get('filesize') or f.get('filesize_approx') or 0
                vcodec = f.get('vcodec', 'none')
                acodec = f.get('acodec', 'none')

                if height and height > 0 and vcodec != 'none':
                    fps_str = f" {int(fps)}fps" if fps and fps >= 50 else ""
                    if height >= 2160:
                        res_label = f"4K UHD (2160p{fps_str})"
                    elif height >= 1440:
                        res_label = f"2K QHD (1440p{fps_str})"
                    elif height >= 1080:
                        res_label = f"1080p FHD{fps_str}"
                    elif height >= 720:
                        res_label = f"720p HD{fps_str}"
                    else:
                        res_label = f"{height}p{fps_str}"

                    if res_label not in seen_res:
                        seen_res.add(res_label)
                        clean_formats.append({
                            'format_id': format_id,
                            'resolution': res_label,
                            'height': height,
                            'fps': fps or 30,
                            'ext': ext,
                            'filesize': filesize,
                            'vcodec': vcodec,
                            'acodec': acodec,
                            'is_audio_only': False,
                            'url': f.get('url', '')
                        })

            # Sort by resolution and framerate descending
            clean_formats.sort(key=lambda x: (x.get('height', 0), x.get('fps', 0)), reverse=True)

            # Audio-only extraction presets
            clean_formats.append({
                'format_id': 'bestaudio_mp3_320',
                'resolution': '🎵 MP3 Audio (320kbps High Quality)',
                'ext': 'mp3',
                'filesize': 0,
                'vcodec': 'none',
                'acodec': 'mp3',
                'is_audio_only': True,
                'url': ''
            })
            clean_formats.append({
                'format_id': 'bestaudio_m4a',
                'resolution': '🎵 M4A Audio (High Quality AAC)',
                'ext': 'm4a',
                'filesize': 0,
                'vcodec': 'none',
                'acodec': 'aac',
                'is_audio_only': True,
                'url': ''
            })
            clean_formats.append({
                'format_id': 'bestaudio_flac',
                'resolution': '🎵 FLAC Audio (Lossless Studio Quality)',
                'ext': 'flac',
                'filesize': 0,
                'vcodec': 'none',
                'acodec': 'flac',
                'is_audio_only': True,
                'url': ''
            })

            # Best overall default option
            clean_formats.insert(0, {
                'format_id': 'bestvideo+bestaudio/best',
                'resolution': 'Best Available Quality (Auto)',
                'ext': 'mp4',
                'filesize': 0,
                'vcodec': 'auto',
                'acodec': 'auto',
                'is_audio_only': False,
                'url': ''
            })

            return {
                'title': title,
                'thumbnail': thumbnail,
                'duration': duration,
                'uploader': uploader,
                'formats': clean_formats,
                'has_subtitles': has_subtitles,
                'available_subs': available_subs,
                'raw_info': info
            }

        # Fallback if yt-dlp could not extract stream details directly
        import urllib.parse
        try:
            parsed = urllib.parse.urlparse(url)
            base_name = os.path.basename(parsed.path) or "media_stream"
            ext = os.path.splitext(base_name)[1].lstrip('.').lower() or "mp4"
            is_media_domain = cls.is_likely_media_url(url)
            
            fallback_formats = [
                {
                    'format_id': 'bestvideo+bestaudio/best',
                    'resolution': 'Best Available Quality (Auto)',
                    'ext': 'mp4',
                    'filesize': 0,
                    'vcodec': 'auto',
                    'acodec': 'auto',
                    'is_audio_only': False,
                    'url': ''
                },
                {
                    'format_id': 'bestaudio',
                    'resolution': 'Extract Audio Only (MP3)',
                    'ext': 'mp3',
                    'filesize': 0,
                    'vcodec': 'none',
                    'acodec': 'mp3',
                    'is_audio_only': True,
                    'url': ''
                }
            ]
            if not is_media_domain:
                fallback_formats.append({
                    'format_id': 'direct',
                    'resolution': 'Original Video Quality (Source Stream)',
                    'ext': ext,
                    'filesize': 0,
                    'vcodec': 'auto',
                    'acodec': 'auto',
                    'is_audio_only': False,
                    'url': url
                })
            return {
                'title': base_name,
                'thumbnail': '',
                'duration': 0,
                'uploader': 'Web Media Server',
                'formats': fallback_formats,
                'raw_info': {}
            }
        except Exception:
            return None

    @classmethod
    def download_media(
        cls,
        url: str,
        format_id: str,
        output_template: str,
        progress_hook: Optional[Callable] = None,
        headers: Optional[Dict[str, str]] = None,
        download_subtitles: bool = False
    ) -> bool:
        """Downloads media using yt-dlp multi-fragment engine with progress callbacks, subtitle ripping, and multi-format audio."""
        def internal_hook(d):
            if progress_hook:
                status = d.get('status')
                if status == 'downloading':
                    total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                    downloaded = d.get('downloaded_bytes', 0)
                    speed = d.get('speed') or 0.0
                    eta = d.get('eta') or 0
                    progress_hook({
                        'status': 'downloading',
                        'total_bytes': total,
                        'downloaded_bytes': downloaded,
                        'speed': speed,
                        'eta': eta,
                        'filename': d.get('filename', '')
                    })
                elif status == 'finished':
                    progress_hook({
                        'status': 'finished',
                        'filename': d.get('filename', '')
                    })

        import shutil
        ffmpeg_bin = shutil.which('ffmpeg')

        format_lower = (format_id or "").lower()
        is_audio = (
            format_id in ('bestaudio', 'bestaudio/best', 'bestaudio_mp3_320', 'bestaudio_m4a', 'bestaudio_flac')
            or 'audio' in format_lower
        )
        if is_audio:
            chosen_format = 'bestaudio/best'
        elif format_id in ('bestvideo+bestaudio/best', 'best', ''):
            chosen_format = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best'
        elif '+' in format_id or '/' in format_id:
            # Complex format string already specified (e.g. bestvideo[height<=1080]+bestaudio...)
            chosen_format = f"{format_id}/bestvideo+bestaudio/best"
        else:
            chosen_format = f"{format_id}+bestaudio/bestvideo+bestaudio/best"

        ydl_opts = {
            'format': chosen_format,
            'outtmpl': output_template,
            'progress_hooks': [internal_hook],
            'concurrent_fragment_downloads': 8,
            'windowsfilenames': True,
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'skip_unavailable_fragments': True,
            'compat_opts': ['no-live-chat'],
        }

        if ffmpeg_bin:
            ydl_opts['ffmpeg_location'] = ffmpeg_bin
            if not is_audio:
                ydl_opts['merge_output_format'] = 'mp4'

        clean_hdrs = cls._sanitize_media_headers(headers)
        if clean_hdrs:
            ydl_opts['http_headers'] = clean_hdrs

        # Audio conversion routing
        if is_audio:
            codec = 'mp3'
            qual = '320'
            if format_id == 'bestaudio_m4a':
                codec = 'm4a'
                qual = '256'
            elif format_id == 'bestaudio_flac':
                codec = 'flac'
                qual = '0'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': codec,
                'preferredquality': qual,
            }]

        # Subtitle extraction support (English/main subtitles, never request 'all' to avoid HTTP 429)
        if download_subtitles:
            ydl_opts['writesubtitles'] = True
            ydl_opts['writeautomaticsub'] = True
            ydl_opts['subtitleslangs'] = ['en', 'en-US', 'en-orig']
            ydl_opts['subtitlesformat'] = 'srt/best'
            if 'postprocessors' not in ydl_opts:
                ydl_opts['postprocessors'] = []
            ydl_opts['postprocessors'].append({
                'key': 'FFmpegSubtitlesConvertor',
                'format': 'srt',
            })

        try:
            with yt_dlp.YoutubeDL(cast(Any, ydl_opts)) as ydl:
                ydl.download([url])
            return True
        except Exception as e:
            # Retry 1: If subtitle extraction caused failure (e.g. rate limit), strip subtitles and retry
            if ydl_opts.get('writesubtitles'):
                ydl_opts.pop('writesubtitles', None)
                ydl_opts.pop('writeautomaticsub', None)
                ydl_opts.pop('subtitleslangs', None)
                ydl_opts.pop('subtitlesformat', None)
                if 'postprocessors' in ydl_opts:
                    ydl_opts['postprocessors'] = [p for p in ydl_opts['postprocessors'] if p.get('key') != 'FFmpegSubtitlesConvertor']
                try:
                    with yt_dlp.YoutubeDL(cast(Any, ydl_opts)) as ydl:
                        ydl.download([url])
                    return True
                except Exception as sub_err:
                    e = sub_err

            # Retry 2: If download failed with headers, retry once cleanly without headers
            if 'http_headers' in ydl_opts:
                ydl_opts.pop('http_headers', None)
                try:
                    with yt_dlp.YoutubeDL(cast(Any, ydl_opts)) as ydl:
                        ydl.download([url])
                    return True
                except Exception as retry_err:
                    e = retry_err
            
            # Retry 3: Fall back to default best video/audio combination
            fallback_fmt = 'bestaudio/best' if is_audio else 'bestvideo+bestaudio/best'
            if ydl_opts.get('format') != fallback_fmt:
                ydl_opts['format'] = fallback_fmt
                try:
                    with yt_dlp.YoutubeDL(cast(Any, ydl_opts)) as ydl:
                        ydl.download([url])
                    return True
                except Exception as format_err:
                    e = format_err

            # Retry 4: Ultimate fallback to single stream 'best'
            if ydl_opts.get('format') != 'best':
                ydl_opts['format'] = 'best'
                try:
                    with yt_dlp.YoutubeDL(cast(Any, ydl_opts)) as ydl:
                        ydl.download([url])
                    return True
                except Exception as ultimate_err:
                    e = ultimate_err

            try:
                err_msg = str(e).encode('ascii', errors='replace').decode('ascii')
                safe_print(f"[FalconDM MediaGrabber] download error: {err_msg}")
            except Exception:
                err_msg = "Download error"
            if progress_hook:
                progress_hook({'status': 'error', 'error': err_msg})
            return False
