import os
import shutil
import zipfile
import tarfile
import subprocess
from typing import List, Optional, Dict, Any
from core.config_manager import config_store

class ArchiveUnpacker:
    """Auto-extracts archives (.zip, .tar, .7z, .rar) with optional password dictionary matching."""

    @staticmethod
    def is_archive(filepath: str) -> bool:
        ext = os.path.splitext(filepath)[1].lower()
        return ext in (".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar")

    @staticmethod
    def get_saved_passwords() -> List[str]:
        return config_store.get("archive_passwords", ["", "1234", "password", "falcondm"])

    @staticmethod
    def add_saved_password(pwd: str):
        pwds = config_store.get("archive_passwords", [])
        if pwd and pwd not in pwds:
            pwds.append(pwd)
            config_store.set("archive_passwords", pwds)

    @classmethod
    def extract_archive(cls, filepath: str, dest_folder: Optional[str] = None) -> Dict[str, Any]:
        """
        Attempts to extract an archive. If password protected, tries saved password list.
        """
        if not os.path.exists(filepath):
            return {"success": False, "message": "File does not exist"}

        if not dest_folder:
            dest_folder = os.path.splitext(filepath)[0]
        os.makedirs(dest_folder, exist_ok=True)

        lower = filepath.lower()

        # 1. ZIP file
        if lower.endswith(".zip"):
            passwords = [""] + cls.get_saved_passwords()
            for pwd in passwords:
                try:
                    pwd_bytes = pwd.encode('utf-8') if pwd else None
                    with zipfile.ZipFile(filepath, 'r') as zf:
                        zf.extractall(dest_folder, pwd=pwd_bytes)
                    return {"success": True, "dest": dest_folder, "password_used": pwd}
                except RuntimeError as e:
                    if "password" in str(e).lower() or "bad password" in str(e).lower():
                        continue
                    else:
                        break
                except Exception:
                    continue

        # 2. Tar archives
        elif any(lower.endswith(ext) for ext in (".tar", ".tar.gz", ".tgz", ".tar.bz2")):
            try:
                with tarfile.open(filepath, 'r:*') as tf:
                    tf.extractall(dest_folder)
                return {"success": True, "dest": dest_folder, "password_used": None}
            except Exception as e:
                return {"success": False, "message": str(e)}

        # 3. 7z / RAR via 7z binary if installed
        seven_zip = shutil.which("7z") or shutil.which("7za")
        if seven_zip:
            passwords = [""] + cls.get_saved_passwords()
            for pwd in passwords:
                pwd_arg = f"-p{pwd}" if pwd else "-p"
                cmd = f'"{seven_zip}" x "{filepath}" -o"{dest_folder}" -y {pwd_arg}'
                res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if res.returncode == 0:
                    return {"success": True, "dest": dest_folder, "password_used": pwd}

        return {"success": False, "message": "Failed to unpack or password not matched"}
