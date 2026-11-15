import os
import re
import json
import fnmatch
import urllib.parse
from typing import List, Dict, Set, Optional, Callable, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from bs4 import BeautifulSoup

CATEGORY_EXTENSIONS: Dict[str, Set[str]] = {
    "Videos": {".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv", ".ts", ".m4v", ".3gp", ".wmv", ".m3u8"},
    "Audio": {".mp3", ".flac", ".wav", ".aac", ".ogg", ".m4a", ".opus", ".wma"},
    "Images": {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".bmp", ".ico", ".tiff", ".avif"},
    "Documents": {".pdf", ".epub", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".txt", ".md", ".csv"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso", ".dmg", ".tgz", ".7zip"}
}

DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 FalconDM/2.0"

def _attr_to_str(val: Any) -> str:
    """Safely converts BeautifulSoup Tag attribute values (which can be str, list, or None) to clean str."""
    if val is None:
        return ""
    if isinstance(val, (list, tuple)):
        return " ".join(str(x) for x in val).strip()
    return str(val).strip()


class SiteGrabber:
    """Enterprise-grade Site Grabber, Web Crawler, and Deep Media Sniffer."""

    @staticmethod
    def crawl_page(
        page_url: str,
        category: str = "All",
        user_agent: Optional[str] = None,
        timeout: int = 15
    ) -> List[Dict[str, Any]]:
        """Scrapes and extracts media, links, and documents from a single webpage (Backward compatible)."""
        return SiteGrabber.crawl_site(
            start_url=page_url,
            max_depth=1,
            same_domain=True,
            max_pages=1,
            category=category,
            user_agent=user_agent,
            timeout=timeout
        )

    @staticmethod
    def crawl_site(
        start_url: str,
        max_depth: int = 1,
        same_domain: bool = True,
        max_pages: int = 15,
        category: str = "All",
        user_agent: Optional[str] = None,
        timeout: int = 15,
        on_page_crawled: Optional[Callable[[str, int, int], None]] = None
    ) -> List[Dict[str, Any]]:
        """
        Recursively crawls a website up to max_depth levels to extract all target downloadable files.
        """
        headers = {"User-Agent": user_agent or DEFAULT_USER_AGENT}
        parsed_start = urllib.parse.urlparse(start_url)
        base_domain = parsed_start.netloc.lower()

        visited_pages: Set[str] = set()
        queue: List[tuple[str, int]] = [(start_url, 1)]
        all_results: Dict[str, Dict[str, Any]] = {}

        while queue and len(visited_pages) < max_pages:
            current_url, depth = queue.pop(0)
            
            # Normalize URL to avoid loops
            norm_url = current_url.split("#")[0].rstrip("/")
            if norm_url in visited_pages:
                continue
            visited_pages.add(norm_url)

            if on_page_crawled:
                try:
                    on_page_crawled(current_url, len(visited_pages), len(queue))
                except Exception:
                    pass

            try:
                resp = requests.get(current_url, headers=headers, timeout=timeout)
                if resp.status_code != 200 or not resp.text:
                    continue

                content_type = resp.headers.get("Content-Type", "").lower()
                if "html" not in content_type:
                    continue

                html_text = resp.text
                page_items, child_links = SiteGrabber._parse_html_and_links(
                    html_text,
                    base_url=current_url,
                    category=category
                )

                for item in page_items:
                    u = item["url"]
                    if u not in all_results:
                        all_results[u] = item

                # Queue child pages if within depth
                if depth < max_depth:
                    for clink in child_links:
                        c_parsed = urllib.parse.urlparse(clink)
                        if same_domain and c_parsed.netloc.lower() != base_domain:
                            continue
                        
                        # Exclude media extensions from being crawled as HTML pages
                        c_path = c_parsed.path.lower()
                        c_ext = os.path.splitext(c_path)[1]
                        if c_ext in (".zip", ".rar", ".exe", ".iso", ".mp4", ".mkv", ".pdf", ".mp3", ".jpg", ".png"):
                            continue

                        norm_child = clink.split("#")[0].rstrip("/")
                        if norm_child not in visited_pages and all(q[0].split("#")[0].rstrip("/") != norm_child for q in queue):
                            queue.append((clink, depth + 1))

            except Exception:
                continue

        return list(all_results.values())

    @staticmethod
    def _parse_html_and_links(
        html_content: str,
        base_url: str = "https://example.com/",
        category: str = "All"
    ) -> tuple[List[Dict[str, Any]], Set[str]]:
        soup = BeautifulSoup(html_content, "html.parser")
        found_urls: Set[str] = set()
        navigable_links: Set[str] = set()

        # 1. <a> hrefs
        for a in soup.find_all("a", href=True):
            href = _attr_to_str(a.get("href"))
            if href and not href.startswith("javascript:") and not href.startswith("mailto:") and not href.startswith("tel:"):
                full_url = urllib.parse.urljoin(base_url, href)
                found_urls.add(full_url)
                navigable_links.add(full_url)

        # 2. <img> src, data-src, srcset
        for img in soup.find_all("img"):
            src = _attr_to_str(img.get("src") or img.get("data-src") or img.get("data-original") or img.get("data-lazy"))
            if src:
                found_urls.add(urllib.parse.urljoin(base_url, src))
            srcset = _attr_to_str(img.get("srcset"))
            if srcset:
                for item in srcset.split(","):
                    parts = item.strip().split()
                    if parts:
                        found_urls.add(urllib.parse.urljoin(base_url, parts[0]))

        # 3. <video>, <audio>, <source>, <track>
        for tag in soup.find_all(["video", "audio", "source", "track"]):
            src = _attr_to_str(tag.get("src") or tag.get("data-src"))
            if src:
                found_urls.add(urllib.parse.urljoin(base_url, src))

        # 4. <link> (preload, prefetch, stylesheet, icon)
        for link in soup.find_all("link", href=True):
            href = _attr_to_str(link.get("href"))
            if href:
                found_urls.add(urllib.parse.urljoin(base_url, href))

        # 5. Inline styles background-image: url(...)
        css_url_pattern = re.compile(r'url\(\s*[\'"]?([^\'")]+)[\'"]?\s*\)', re.IGNORECASE)
        for elem in soup.find_all(style=True):
            style_text = _attr_to_str(elem.get("style"))
            for match in css_url_pattern.findall(style_text):
                if match and not match.startswith("data:"):
                    found_urls.add(urllib.parse.urljoin(base_url, match.strip()))

        # 6. Deep script regex extraction for direct media/archive URLs
        media_regex = re.compile(
            r'https?://[^\s"\'<>]+\.(?:mp4|mkv|webm|avi|mov|mp3|flac|wav|zip|rar|7z|tar|gz|iso|pdf|epub|docx|xlsx)(?=[?"\'\s<>]|$)',
            re.IGNORECASE
        )
        for script in soup.find_all("script"):
            script_text = script.string or ""
            for m in media_regex.findall(script_text):
                found_urls.add(m)

        # Determine target extensions filter
        target_exts = set()
        if category in CATEGORY_EXTENSIONS:
            target_exts = CATEGORY_EXTENSIONS[category]
        elif category == "All":
            for s in CATEGORY_EXTENSIONS.values():
                target_exts.update(s)

        results: List[Dict[str, Any]] = []
        for u in found_urls:
            parsed = urllib.parse.urlparse(u)
            path = parsed.path
            ext = os.path.splitext(path)[1].lower()
            if not ext:
                continue

            if category != "All Links" and target_exts and ext not in target_exts:
                continue

            fname = os.path.basename(path)
            if not fname:
                fname = "file_" + str(len(results) + 1) + ext

            # Classify category
            cat = "General"
            for c_name, exts in CATEGORY_EXTENSIONS.items():
                if ext in exts:
                    cat = c_name
                    break

            results.append({
                "url": u,
                "filename": fname,
                "ext": ext,
                "category": cat,
                "size_bytes": 0,
                "size_str": "Unknown",
                "resumable": None
            })

        return results, navigable_links

    @staticmethod
    def parse_html(
        html_content: str,
        base_url: str = "https://example.com/",
        category: str = "All"
    ) -> List[Dict[str, Any]]:
        """Parses raw HTML content and extracts categorized downloadable links (Backward compatible)."""
        items, _ = SiteGrabber._parse_html_and_links(html_content, base_url, category)
        return items

    @staticmethod
    def probe_file_sizes(
        items: List[Dict[str, Any]],
        max_workers: int = 10,
        timeout: int = 8,
        on_progress: Optional[Callable[[int, int], None]] = None
    ) -> List[Dict[str, Any]]:
        """
        Concurrently probes remote file sizes (Content-Length) and resume capabilities using fast HTTP HEAD requests.
        """
        headers = {"User-Agent": DEFAULT_USER_AGENT}
        total = len(items)
        completed = 0

        def _probe_single(item: Dict[str, Any]) -> None:
            url = item.get("url", "")
            try:
                # 1. Try HEAD request
                r = requests.head(url, headers=headers, allow_redirects=True, timeout=timeout)
                size = 0
                if "Content-Length" in r.headers:
                    size = int(r.headers.get("Content-Length", 0))
                
                # If server refused HEAD, try Range bytes=0-0 GET
                if size == 0 or r.status_code >= 400:
                    r_get = requests.get(url, headers={"Range": "bytes=0-0", **headers}, stream=True, timeout=timeout)
                    cr = r_get.headers.get("Content-Range", "")
                    if "/" in cr:
                        try:
                            size = int(cr.split("/")[-1])
                        except Exception:
                            pass
                    elif "Content-Length" in r_get.headers:
                        size = int(r_get.headers.get("Content-Length", 0))
                    r_get.close()

                item["size_bytes"] = size
                item["size_str"] = SiteGrabber.format_bytes(size) if size > 0 else "Unknown"
                item["resumable"] = ("bytes" in r.headers.get("Accept-Ranges", "").lower()) or (r.status_code == 206)
            except Exception:
                item["size_bytes"] = 0
                item["size_str"] = "Unknown"

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_probe_single, item) for item in items]
            for fut in as_completed(futures):
                completed += 1
                if on_progress:
                    try:
                        on_progress(completed, total)
                    except Exception:
                        pass

        return items

    @staticmethod
    def filter_items(
        items: List[Dict[str, Any]],
        search_query: str = "",
        category: str = "All",
        min_size_bytes: int = 0,
        max_size_bytes: int = 0
    ) -> List[Dict[str, Any]]:
        """Filters extracted items using search terms, wildcards, regex, and size constraints."""
        filtered = []
        pattern = None
        if search_query:
            # Check if user entered a regex or wildcard
            if any(ch in search_query for ch in ("*", "?", "[", "]")):
                regex_str = fnmatch.translate(search_query)
                pattern = re.compile(regex_str, re.IGNORECASE)
            else:
                pattern = re.compile(re.escape(search_query), re.IGNORECASE)

        for item in items:
            if category != "All" and item.get("category") != category:
                continue

            fname = item.get("filename", "")
            url = item.get("url", "")
            if pattern and not (pattern.search(fname) or pattern.search(url)):
                continue

            size = item.get("size_bytes", 0)
            if min_size_bytes > 0 and size > 0 and size < min_size_bytes:
                continue
            if max_size_bytes > 0 and size > 0 and size > max_size_bytes:
                continue

            filtered.append(item)

        return filtered

    @staticmethod
    def export_links(items: List[Dict[str, Any]], filepath: str, export_format: str = "txt") -> bool:
        """Exports the discovered link collection to TXT, JSON, or CSV."""
        try:
            if export_format.lower() == "json":
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(items, f, indent=2)
            else:
                with open(filepath, "w", encoding="utf-8") as f:
                    for it in items:
                        f.write(f"{it.get('url', '')}\n")
            return True
        except Exception:
            return False

    @staticmethod
    def format_bytes(size_bytes: int) -> str:
        """Helper to format byte count into clean human-readable unit string."""
        if size_bytes <= 0:
            return "0 B"
        units = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        size = float(size_bytes)
        while size >= 1024.0 and i < len(units) - 1:
            size /= 1024.0
            i += 1
        return f"{size:.2f} {units[i]}"
