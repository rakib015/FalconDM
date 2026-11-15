import os
import subprocess
import shutil
from typing import Optional, Dict, Any
from core.config_manager import config_store

class AntivirusScanner:
    """Invokes Windows Defender or custom Antivirus engine to scan completed downloads."""

    @staticmethod
    def get_defender_path() -> Optional[str]:
        # Typical Windows Defender MpCmdRun paths
        candidates = [
            os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "Windows Defender", "MpCmdRun.exe"),
            os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), "Windows Defender", "MpCmdRun.exe"),
            os.path.join(os.environ.get("ProgramData", "C:\\ProgramData"), "Microsoft", "Windows Defender", "Platform")
        ]
        for c in candidates[:2]:
            if os.path.isfile(c):
                return c
        
        # Check Defender Platform directory for newest version
        plat_dir = candidates[2]
        if os.path.isdir(plat_dir):
            try:
                subdirs = sorted(os.listdir(plat_dir), reverse=True)
                for s in subdirs:
                    exe = os.path.join(plat_dir, s, "MpCmdRun.exe")
                    if os.path.isfile(exe):
                        return exe
            except Exception:
                pass

        return shutil.which("MpCmdRun.exe")

    @classmethod
    def scan_file(cls, filepath: str) -> Dict[str, Any]:
        """
        Scans a file with Windows Defender.
        Return code:
          0 = Clean (No malware detected)
          2 = Threat detected
          other = Warning / Error
        """
        if not os.path.exists(filepath):
            return {"success": False, "clean": False, "message": "File does not exist"}

        custom_av = config_store.get("custom_antivirus_cmd", "").strip()
        if custom_av:
            cmd = custom_av.replace("%file%", f'"{filepath}"')
            try:
                res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
                clean = (res.returncode == 0)
                return {
                    "success": True,
                    "clean": clean,
                    "engine": "Custom AV",
                    "returncode": res.returncode,
                    "output": res.stdout or res.stderr
                }
            except Exception as e:
                return {"success": False, "clean": False, "engine": "Custom AV", "message": str(e)}

        import sys
        if sys.platform.startswith("linux"):
            clam = shutil.which("clamscan")
            if clam:
                cmd = [clam, "--no-summary", filepath]
                try:
                    res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                    clean = (res.returncode == 0)
                    return {
                        "success": True,
                        "clean": clean,
                        "engine": "ClamAV",
                        "returncode": res.returncode,
                        "message": "Clean: No threats detected" if clean else "Threat detected",
                        "output": res.stdout or res.stderr
                    }
                except Exception as e:
                    return {"success": False, "clean": True, "engine": "ClamAV", "message": str(e)}
            return {"success": False, "clean": True, "engine": "None", "message": "No Linux antivirus scanner found (install clamav)"}

        defender_exe = cls.get_defender_path()
        if not defender_exe:
            return {"success": False, "clean": True, "engine": "None", "message": "Windows Defender CLI not found"}

        cmd = f'"{defender_exe}" -Scan -ScanType 3 -File "{filepath}"'
        try:
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
            clean = (res.returncode == 0)
            msg = "Clean: No threats detected" if clean else "Warning: Threat detected or scan failed"
            return {
                "success": True,
                "clean": clean,
                "engine": "Windows Defender",
                "returncode": res.returncode,
                "message": msg,
                "output": res.stdout
            }
        except Exception as e:
            return {"success": False, "clean": False, "engine": "Windows Defender", "message": str(e)}
