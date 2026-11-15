import os
import shutil
from typing import List, Dict, Any, Optional, cast
import yt_dlp

class PlaylistGrabber:
    """Extracts batches of video/audio links from YouTube Playlists, SoundCloud sets, and user channels."""

    @staticmethod
    def is_playlist_url(url: str) -> bool:
        if not url:
            return False
        u = url.lower()
        return any(term in u for term in ("playlist?list=", "&list=", "/sets/", "/album/", "/channel/", "/c/", "/user/"))

    @staticmethod
    def extract_playlist(url: str, max_items: int = 100) -> List[Dict[str, Any]]:
        """
        Extracts all track/video items from a playlist without downloading media files.
        Returns a list of dicts: {"title": ..., "url": ..., "duration": ..., "uploader": ...}
        """
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'skip_download': True,
            'playlistend': max_items,
            'socket_timeout': 15,
        }
        ffmpeg_bin = shutil.which('ffmpeg')
        if ffmpeg_bin:
            ydl_opts['ffmpeg_location'] = ffmpeg_bin

        results = []
        try:
            with yt_dlp.YoutubeDL(cast(Any, ydl_opts)) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    return results

                entries = info.get('entries', [])
                for entry in entries:
                    if not entry:
                        continue
                    v_url = entry.get('url') or entry.get('webpage_url')
                    if not v_url and entry.get('id'):
                        v_url = f"https://www.youtube.com/watch?v={entry.get('id')}"
                    
                    title = entry.get('title', 'Unknown Title')
                    duration = entry.get('duration', 0)
                    uploader = entry.get('uploader', '')

                    if v_url:
                        results.append({
                            "title": title,
                            "url": v_url,
                            "duration": duration,
                            "uploader": uploader
                        })
        except Exception:
            pass

        return results
