import os
import sys
import shutil
import subprocess
from typing import Any

# Configure standard streams for UTF-8 safety
try:
    _reconfig_out = getattr(sys.stdout, 'reconfigure', None)
    if callable(_reconfig_out):
        _reconfig_out(encoding='utf-8', errors='replace')
    _reconfig_err = getattr(sys.stderr, 'reconfigure', None)
    if callable(_reconfig_err):
        _reconfig_err(encoding='utf-8', errors='replace')
except Exception:
    pass

def safe_print(*args: Any, **kwargs: Any) -> None:
    """UTF-8 safe console printer that never crashes on Windows cp1252 or emojis."""
    try:
        print(*args, **kwargs)
    except (UnicodeEncodeError, OSError):
        try:
            encoding = getattr(sys.stdout, 'encoding', None) or 'utf-8'
            safe_args = [
                str(a).encode(encoding, errors='replace').decode(encoding, errors='replace')
                for a in args
            ]
            print(*safe_args, **kwargs)
        except Exception:
            pass
    except Exception:
        pass

def open_file_or_folder(path: str, select: bool = False) -> None:
    """
    Cross-platform file and folder opener.
    Works natively on Windows, Linux (GNOME/KDE/XFCE/Wayland), and macOS.
    """
    if not path:
        return
    abs_path = os.path.abspath(path)
    
    if sys.platform == "win32":
        try:
            if select and os.path.isfile(abs_path):
                subprocess.run(f'explorer /select,"{abs_path}"', shell=True)
            elif os.path.exists(abs_path):
                target = abs_path if os.path.isdir(abs_path) else os.path.dirname(abs_path)
                subprocess.run(f'explorer "{target}"', shell=True)
            else:
                parent = os.path.dirname(abs_path)
                if os.path.exists(parent):
                    subprocess.run(f'explorer "{parent}"', shell=True)
        except Exception:
            pass
    elif sys.platform == "darwin":
        try:
            if select and os.path.isfile(abs_path):
                subprocess.run(["open", "-R", abs_path])
            else:
                target = abs_path if os.path.isdir(abs_path) else os.path.dirname(abs_path)
                subprocess.run(["open", target])
        except Exception:
            pass
    else:
        # Linux (X11 / Wayland)
        try:
            target = abs_path if os.path.isdir(abs_path) else os.path.dirname(abs_path)
            subprocess.run(["xdg-open", target])
        except Exception:
            try:
                # Fallback to gio or nautilus
                subprocess.run(["gio", "open", target])
            except Exception:
                pass

def bring_window_to_front(target: Any, is_main: bool = False) -> None:
    """
    Reliably activates, restores, and focuses a Tkinter / CustomTkinter window
    across all platforms without throwing errors on Linux or older Windows versions.
    """
    if not target:
        return
    try:
        target.deiconify()
        target.state('normal')
        target.update_idletasks()
        target.lift()
        target.attributes('-topmost', True)
        target.after(300, lambda: target.attributes('-topmost', False))
        target.focus_force()
    except Exception:
        pass

    if sys.platform == "win32":
        try:
            import ctypes
            frame_str = getattr(target, 'wm_frame', lambda: "")()
            hwnd = int(frame_str, 16) if frame_str else (ctypes.windll.user32.GetParent(target.winfo_id()) or target.winfo_id())
            try:
                ctypes.windll.user32.AllowSetForegroundWindow(-1)
            except Exception:
                pass
            ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            target.after(300, lambda: ctypes.windll.user32.SetWindowPos(hwnd, -2, 0, 0, 0, 0, 0x0001 | 0x0002))
        except Exception:
            pass
    elif sys.platform.startswith("linux"):
        try:
            target.attributes('-topmost', True)
            target.lift()
            target.after(300, lambda: target.attributes('-topmost', False))
        except Exception:
            pass

def trigger_system_shutdown(sleep: bool = False) -> None:
    """Safely shuts down or suspends the host computer (Windows / Linux / macOS)."""
    if sys.platform == "win32":
        try:
            if sleep:
                subprocess.run("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)
            else:
                subprocess.run("shutdown /s /t 0", shell=True)
        except Exception:
            pass
    elif sys.platform.startswith("linux"):
        try:
            cmd = ["systemctl", "suspend"] if sleep else ["systemctl", "poweroff"]
            subprocess.run(cmd)
        except Exception:
            pass
    elif sys.platform == "darwin":
        try:
            cmd = ["pmset", "sleepnow"] if sleep else ["osascript", "-e", 'tell app "System Events" to shut down']
            subprocess.run(cmd)
        except Exception:
            pass

def get_browser_extension_dir() -> str:
    """Returns the resolved absolute path to the browser_extension directory."""
    candidates = []
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        candidates.append(os.path.join(exe_dir, "browser_extension"))
        candidates.append(os.path.join(exe_dir, "_internal", "browser_extension"))
    
    file_dir = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.abspath(os.path.join(file_dir, "..", "browser_extension")))
    candidates.append(os.path.abspath(os.path.join(file_dir, "..", "..", "browser_extension")))
    candidates.append(os.path.abspath(os.path.join(file_dir, "browser_extension")))

    for c in candidates:
        if os.path.isdir(c) and os.path.isfile(os.path.join(c, "manifest.json")):
            return os.path.abspath(c)
    return os.path.abspath(candidates[0])

def register_browser_integration() -> bool:
    """Registers native messaging hosts in OS registry for Chrome, Edge, Brave, Opera, and Firefox."""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        import json

        ext_dir = get_browser_extension_dir()
        base_dir = os.path.dirname(ext_dir)

        exe_path = sys.executable
        is_frozen = getattr(sys, 'frozen', False) or exe_path.lower().endswith("falcondm.exe")
        
        target_host_bin = ""
        if is_frozen and os.path.isfile(exe_path):
            target_host_bin = exe_path
        else:
            bat_candidate = os.path.join(base_dir, "core", "native_host.bat")
            if os.path.isfile(bat_candidate):
                target_host_bin = bat_candidate
            else:
                target_host_bin = os.path.abspath(os.path.join(os.path.dirname(__file__), "native_host.bat"))

        # Use AppData to ensure writes succeed under lowest user privileges
        manifest_dir = os.path.join(os.getenv("APPDATA") or base_dir, "FalconDM", "native_messaging")
        os.makedirs(manifest_dir, exist_ok=True)

        chrome_manifest = os.path.join(manifest_dir, "com.falcondm.downloader.json")
        firefox_manifest = os.path.join(manifest_dir, "com.falcondm.downloader_firefox.json")

        cdata = {
            "name": "com.falcondm.downloader",
            "description": "FalconDM Native Messaging Host for Auto-Launching",
            "path": target_host_bin,
            "type": "stdio",
            "allowed_origins": [
                "chrome-extension://kbekmfgcpjeiiiehpffkapbpncbpfjcj/"
            ]
        }
        with open(chrome_manifest, "w", encoding="utf-8") as f:
            json.dump(cdata, f, indent=2)

        fdata = {
            "name": "com.falcondm.downloader",
            "description": "FalconDM Native Messaging Host for Firefox Auto-Launching",
            "path": target_host_bin,
            "type": "stdio",
            "allowed_extensions": [
                "falcondm-turbo@falcondm.local"
            ]
        }
        with open(firefox_manifest, "w", encoding="utf-8") as f:
            json.dump(fdata, f, indent=2)

        # List of registry keys for all Chromium & Mozilla browsers
        reg_keys = [
            (winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\NativeMessagingHosts\com.falcondm.downloader", chrome_manifest),
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Edge\NativeMessagingHosts\com.falcondm.downloader", chrome_manifest),
            (winreg.HKEY_CURRENT_USER, r"Software\BraveSoftware\Brave-Browser\NativeMessagingHosts\com.falcondm.downloader", chrome_manifest),
            (winreg.HKEY_CURRENT_USER, r"Software\Opera Software\Opera Stable\NativeMessagingHosts\com.falcondm.downloader", chrome_manifest),
            (winreg.HKEY_CURRENT_USER, r"Software\Opera Software\Opera GX Stable\NativeMessagingHosts\com.falcondm.downloader", chrome_manifest),
            (winreg.HKEY_CURRENT_USER, r"Software\Vivaldi\NativeMessagingHosts\com.falcondm.downloader", chrome_manifest),
            (winreg.HKEY_CURRENT_USER, r"Software\Mozilla\NativeMessagingHosts\com.falcondm.downloader", firefox_manifest)
        ]

        for hkey, subkey, manifest_file in reg_keys:
            try:
                with winreg.CreateKey(hkey, subkey) as k:
                    winreg.SetValueEx(k, "", 0, winreg.REG_SZ, manifest_file)
            except Exception:
                pass

        # Copy extension path to Windows clipboard for convenience
        try:
            if os.path.isdir(ext_dir):
                subprocess.run(["powershell", "-NoProfile", "-Command", f"Set-Clipboard -Value '{ext_dir}'"],
                               capture_output=True, timeout=3, check=False)
        except Exception:
            pass

        return True
    except Exception as e:
        safe_print(f"[PlatformUtils] Error registering native messaging: {e}")
        return False


def prevent_system_sleep(enable: bool = True) -> bool:
    """
    Prevents the host operating system from going to sleep or hibernating
    while downloads are actively transferring.
    """
    if sys.platform == "win32":
        try:
            import ctypes
            ES_CONTINUOUS = 0x80000000
            ES_SYSTEM_REQUIRED = 0x00000001
            ES_AWAYMODE_REQUIRED = 0x00000040
            if enable:
                ctypes.windll.kernel32.SetThreadExecutionState(
                    ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED
                )
            else:
                ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
            return True
        except Exception:
            return False
    return False


def play_audio_alert(sound_type: str = "complete") -> None:
    """
    Plays a subtle notification chime when downloads complete or fail.
    Uses native Windows APIs with zero external audio library dependencies.
    """
    if sys.platform == "win32":
        try:
            import winsound
            import threading

            def _beep():
                try:
                    if sound_type == "complete":
                        winsound.Beep(587, 120)
                        winsound.Beep(880, 200)
                    elif sound_type == "error":
                        winsound.Beep(440, 150)
                        winsound.Beep(330, 220)
                    else:
                        winsound.MessageBeep(winsound.MB_ICONASTERISK)
                except Exception:
                    pass

            threading.Thread(target=_beep, daemon=True).start()
        except Exception:
            pass


def fast_preallocate_file(filepath: str, size: int) -> bool:
    """
    Instantly pre-allocates file storage on disk without thrashing or fragmentation.
    """
    if size <= 0:
        return False
    try:
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, "a+b") as f:
            f.truncate(size)
        return True
    except Exception:
        try:
            with open(filepath, "wb") as f:
                f.seek(size - 1)
                f.write(b'\0')
            return True
        except Exception:
            return False


def launch_in_media_player(filepath: str) -> bool:
    """
    Launches an audio/video file in VLC Media Player (if available) or the default OS player.
    Supports previewing partially downloaded media files.
    """
    if not filepath or not os.path.exists(filepath):
        return False

    vlc_candidates = [
        r"C:\Program Files\VideoLAN\VLC\vlc.exe",
        r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
    ]
    vlc_path = shutil.which("vlc")
    if not vlc_path:
        for c in vlc_candidates:
            if os.path.isfile(c):
                vlc_path = c
                break

    try:
        if vlc_path:
            subprocess.Popen([vlc_path, filepath], shell=False)
            return True
        else:
            if sys.platform == "win32":
                os.startfile(filepath)
                return True
            else:
                subprocess.Popen(["xdg-open" if sys.platform.startswith("linux") else "open", filepath])
                return True
    except Exception:
        return False



def trim_memory_footprint() -> None:
    """
    Forces garbage collection and releases unmapped memory pages back to the OS.
    On Windows, this reclaims unused working set memory, dropping RAM usage down to ~15-20 MB.
    """
    try:
        import gc
        gc.collect()
        if sys.platform == "win32":
            import ctypes
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            ctypes.windll.psapi.EmptyWorkingSet(handle)
    except Exception:
        pass


def is_low_spec_system() -> bool:
    """
    Detects if the system has limited resources (e.g. <= 2 CPU cores or <= 4GB RAM),
    enabling automatic Eco performance optimizations.
    """
    try:
        cores = os.cpu_count() or 4
        if cores <= 2:
            return True
        try:
            import psutil
            total_ram_gb = psutil.virtual_memory().total / (1024 ** 3)
            if total_ram_gb <= 4.2:
                return True
        except ImportError:
            pass
    except Exception:
        pass
    return False


def prevent_system_sleep(enable: bool = True) -> bool:
    """
    Prevents the host operating system from going to sleep or hibernating
    while downloads are actively transferring.
    """
    if sys.platform == "win32":
        try:
            import ctypes
            ES_CONTINUOUS = 0x80000000
            ES_SYSTEM_REQUIRED = 0x00000001
            ES_AWAYMODE_REQUIRED = 0x00000040
            if enable:
                ctypes.windll.kernel32.SetThreadExecutionState(
                    ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED
                )
            else:
                ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
            return True
        except Exception:
            return False
    return False


def play_audio_alert(sound_type: str = "complete") -> None:
    """
    Plays a subtle notification chime when downloads complete or fail.
    Uses native Windows APIs with zero external audio library dependencies.
    """
    if sys.platform == "win32":
        try:
            import winsound
            import threading

            def _beep():
                try:
                    if sound_type == "complete":
                        winsound.Beep(587, 120)
                        winsound.Beep(880, 200)
                    elif sound_type == "error":
                        winsound.Beep(440, 150)
                        winsound.Beep(330, 220)
                    else:
                        winsound.MessageBeep(winsound.MB_ICONASTERISK)
                except Exception:
                    pass

            threading.Thread(target=_beep, daemon=True).start()
        except Exception:
            pass


def fast_preallocate_file(filepath: str, size: int) -> bool:
    """
    Instantly pre-allocates file storage on disk without thrashing or fragmentation.
    """
    if size <= 0:
        return False
    try:
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, "a+b") as f:
            f.truncate(size)
        return True
    except Exception:
        try:
            with open(filepath, "wb") as f:
                f.seek(size - 1)
                f.write(b'\0')
            return True
        except Exception:
            return False


def launch_in_media_player(filepath: str) -> bool:
    """
    Launches an audio/video file in VLC Media Player (if available) or the default OS player.
    Supports previewing partially downloaded media files.
    """
    if not filepath or not os.path.exists(filepath):
        return False

    vlc_candidates = [
        r"C:\Program Files\VideoLAN\VLC\vlc.exe",
        r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
    ]
    vlc_path = shutil.which("vlc")
    if not vlc_path:
        for c in vlc_candidates:
            if os.path.isfile(c):
                vlc_path = c
                break

    try:
        if vlc_path:
            subprocess.Popen([vlc_path, filepath], shell=False)
            return True
        else:
            if sys.platform == "win32":
                os.startfile(filepath)
                return True
            else:
                subprocess.Popen(["xdg-open" if sys.platform.startswith("linux") else "open", filepath])
                return True
    except Exception:
        return False





