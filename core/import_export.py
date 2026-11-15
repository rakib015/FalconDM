import os
import json
import re
from typing import List, Dict, Any

class DownloadListSerializer:
    """Imports and exports download queues to/from IDM (.ef2), aria2, JSON, and TXT formats."""

    @staticmethod
    def export_idm_ef2(tasks: List[Dict[str, Any]], filepath: str) -> bool:
        """
        Exports downloads in IDM Export File Format (.ef2).
        Format:
        <
        URL
        file_path
        >
        """
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                for t in tasks:
                    url = t.get("url", "").strip()
                    save_path = t.get("save_path", "").strip()
                    if url:
                        f.write("<\n")
                        f.write(f"{url}\n")
                        if save_path:
                            f.write(f"file_path={os.path.dirname(save_path)}\n")
                            f.write(f"file_name={os.path.basename(save_path)}\n")
                        f.write(">\n")
            return True
        except Exception:
            return False

    @staticmethod
    def import_idm_ef2(filepath: str) -> List[Dict[str, str]]:
        """Imports URLs and metadata from an IDM .ef2 export file."""
        results = []
        if not os.path.exists(filepath):
            return results

        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            blocks = re.findall(r'<\s*([\s\S]*?)\s*>', content)
            for block in blocks:
                lines = [line.strip() for line in block.splitlines() if line.strip()]
                if not lines:
                    continue
                url = lines[0]
                save_dir = None
                file_name = None
                for line in lines[1:]:
                    if line.startswith("file_path="):
                        save_dir = line.split("=", 1)[1]
                    elif line.startswith("file_name="):
                        file_name = line.split("=", 1)[1]
                
                results.append({
                    "url": url,
                    "save_dir": save_dir,
                    "filename": file_name
                })
        except Exception:
            pass

        return results

    @staticmethod
    def export_aria2_input(tasks: List[Dict[str, Any]], filepath: str) -> bool:
        """Exports download list formatted for aria2c -i input file."""
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                for t in tasks:
                    url = t.get("url", "").strip()
                    if url:
                        f.write(f"{url}\n")
                        save_path = t.get("save_path")
                        if save_path:
                            f.write(f"  dir={os.path.dirname(save_path)}\n")
                            f.write(f"  out={os.path.basename(save_path)}\n")
            return True
        except Exception:
            return False

    @staticmethod
    def import_plain_urls(filepath: str) -> List[str]:
        """Imports raw list of URLs from TXT."""
        urls = []
        if not os.path.exists(filepath):
            return urls
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    u = line.strip()
                    if u and (u.startswith("http://") or u.startswith("https://") or u.startswith("magnet:")):
                        urls.append(u)
        except Exception:
            pass
        return urls

    @staticmethod
    def import_metalink(filepath_or_content: str) -> List[Dict[str, Any]]:
        """
        Parses Metalink (.metalink, .meta4) XML documents (RFC 5854 & Metalink 3.0).
        Extracts filename, size, hashes (SHA-256/MD5), and all mirror URLs.
        """
        import xml.etree.ElementTree as ET
        results = []
        try:
            if os.path.isfile(filepath_or_content):
                tree = ET.parse(filepath_or_content)
                root = tree.getroot()
            else:
                root = ET.fromstring(filepath_or_content)

            # Strip XML namespaces for uniform querying
            for elem in root.iter():
                if '}' in elem.tag:
                    elem.tag = elem.tag.split('}', 1)[1]

            for file_elem in root.iter('file'):
                name = file_elem.attrib.get('name', '')
                size = 0
                size_elem = file_elem.find('size')
                if size_elem is not None and size_elem.text:
                    try:
                        size = int(size_elem.text.strip())
                    except ValueError:
                        pass

                checksum_expected = ""
                checksum_type = ""
                for hash_elem in file_elem.iter('hash'):
                    h_type = hash_elem.attrib.get('type', '').lower()
                    h_val = (hash_elem.text or '').strip()
                    if h_type in ('sha-256', 'sha256') and h_val:
                        checksum_expected = h_val
                        checksum_type = "sha256"
                        break
                    elif h_type in ('md5', 'sha1') and not checksum_expected:
                        checksum_expected = h_val
                        checksum_type = h_type

                urls = []
                for url_elem in file_elem.iter('url'):
                    u = (url_elem.text or '').strip()
                    if u.startswith('http://') or u.startswith('https://') or u.startswith('ftp://'):
                        urls.append(u)

                if urls:
                    results.append({
                        "filename": name,
                        "url": urls[0],
                        "mirrors": urls[1:],
                        "file_size": size,
                        "checksum_expected": checksum_expected,
                        "checksum_type": checksum_type
                    })
        except Exception:
            pass
        return results

    @staticmethod
    def export_metalink(tasks: List[Dict[str, Any]], filepath: str) -> bool:
        """Exports download tasks in standard RFC 5854 Metalink 4 XML format."""
        try:
            lines = [
                '<?xml version="1.0" encoding="UTF-8"?>',
                '<metalink xmlns="urn:ietf:params:xml:ns:metalink">'
            ]
            for t in tasks:
                fn = t.get("filename") or os.path.basename(t.get("save_path", "download.bin"))
                url = t.get("url", "")
                if not url:
                    continue
                size = t.get("file_size", 0)
                mirrors = t.get("mirrors", [])
                h_expected = t.get("checksum_expected", "")
                h_type = t.get("checksum_type", "sha-256")

                lines.append(f'  <file name="{fn}">')
                if size > 0:
                    lines.append(f'    <size>{size}</size>')
                if h_expected:
                    lines.append(f'    <hash type="{h_type}">{h_expected}</hash>')
                lines.append(f'    <url priority="1">{url}</url>')
                for idx, m in enumerate(mirrors, start=2):
                    lines.append(f'    <url priority="{idx}">{m}</url>')
                lines.append('  </file>')
            lines.append('</metalink>')

            with open(filepath, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            return True
        except Exception:
            return False

    @staticmethod
    def generate_curl_command(task: Any) -> str:
        """Generates production-grade cURL command with resume, output file, and browser headers."""
        if hasattr(task, 'to_dict'):
            t = task.to_dict()
        elif isinstance(task, dict):
            t = task
        else:
            t = {"url": str(task)}

        url = t.get("url", "")
        fn = t.get("filename") or os.path.basename(t.get("save_path", "download.bin"))
        hdrs = t.get("headers") or {}

        parts = ["curl", "-C", "-", "-L", "-o", f'"{fn}"', f'"{url}"']
        if "User-Agent" in hdrs:
            parts.extend(["-H", f'"User-Agent: {hdrs["User-Agent"]}"'])
        if "Referer" in hdrs:
            parts.extend(["-H", f'"Referer: {hdrs["Referer"]}"'])
        if "Cookie" in hdrs:
            parts.extend(["-H", f'"Cookie: {hdrs["Cookie"]}"'])

        return " ".join(parts)
