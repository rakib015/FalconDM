import os
import sys
import time
import argparse
from core.engine import DownloadTask
from core.state_manager import DownloadManager
from core.site_grabber import SiteGrabber
from core.hasher import compute_checksums
from core.config_manager import config_store

def handle_cli(args: list) -> bool:
    """
    Parses CLI arguments. Returns True if CLI command handled, False to launch GUI.
    """
    if len(args) <= 1:
        return False

    parser = argparse.ArgumentParser(
        prog="falcondm",
        description="⚡ FalconDM — Turbo Multi-Threaded Download Manager (CLI Mode)"
    )
    subparsers = parser.add_subparsers(dest="command", help="FalconDM Commands")

    # 1. Download command
    dl_parser = subparsers.add_parser("download", help="Download a URL with turbo multi-threading")
    dl_parser.add_argument("url", help="HTTP, HTTPS, or media URL to download")
    dl_parser.add_argument("-c", "--connections", type=int, default=16, help="Number of concurrent connections (1-32)")
    dl_parser.add_argument("-o", "--output", default=".", help="Save destination folder")
    dl_parser.add_argument("-f", "--filename", default=None, help="Custom filename override")

    # 2. List command
    subparsers.add_parser("list", help="List all downloads and current statuses")

    # 3. Crawl / Site-grab command
    grab_parser = subparsers.add_parser("site-grab", help="Crawl website and extract downloadable media")
    grab_parser.add_argument("url", help="Website URL to crawl")
    grab_parser.add_argument("-d", "--depth", type=int, default=1, help="Crawl depth (1-3)")
    grab_parser.add_argument("-c", "--category", default="All", help="Media category filter")

    # 4. Hash command
    hash_parser = subparsers.add_parser("hash", help="Calculate cryptographic checksum of a file")
    hash_parser.add_argument("filepath", help="Path to file")

    parsed = parser.parse_args(args[1:])

    if parsed.command == "download":
        print(f"🚀 FalconDM Turbo Engine: Initializing download for {parsed.url}")
        save_dir = os.path.abspath(parsed.output)
        os.makedirs(save_dir, exist_ok=True)
        
        task = DownloadTask(
            task_id="cli_task",
            url=parsed.url,
            save_path=os.path.join(save_dir, parsed.filename or "downloaded_file"),
            num_connections=parsed.connections
        )
        if not task.probe():
            print("❌ Failed to connect or probe remote URL.")
            return True

        if not parsed.filename:
            task.save_path = os.path.join(save_dir, task.filename)

        print(f"📦 File: {task.filename} ({task.file_size / 1048576:.2f} MB)")
        print(f"⚡ Resumable: {task.resumable} | Connections: {task.num_connections}")
        
        task.start()
        last_print = 0
        while task.status == DownloadTask.STATUS_DOWNLOADING:
            now = time.time()
            if now - last_print >= 0.5:
                pct = (task.downloaded_bytes / max(1, task.file_size)) * 100
                spd = task.speed_bps / 1048576
                sys.stdout.write(f"\r⏳ Progress: {pct:.1f}% | Speed: {spd:.2f} MB/s | ETA: {task.eta_seconds}s  ")
                sys.stdout.flush()
                last_print = now
            time.sleep(0.1)

        sys.stdout.write("\n")
        if task.status == DownloadTask.STATUS_COMPLETED:
            print(f"✅ Download 100% Complete! Saved to: {task.save_path}")
        else:
            print(f"❌ Download failed: {task.error_message}")
        return True

    elif parsed.command == "list":
        dm = DownloadManager()
        tasks = dm.tasks.values()
        print(f"📋 FalconDM Library: {len(tasks)} items")
        print("-" * 65)
        for t in tasks:
            print(f"[{t.status.upper():11}] {t.filename[:30]:30} | {t.file_size / 1048576:6.1f} MB | {t.url}")
        return True

    elif parsed.command == "site-grab":
        print(f"🕷️ Crawling {parsed.url} (Depth: {parsed.depth}, Category: {parsed.category})...")
        items = SiteGrabber.crawl_site(parsed.url, max_depth=parsed.depth, category=parsed.category)
        print(f"✓ Discovered {len(items)} downloadable files:")
        for it in items[:20]:
            print(f"  • [{it.get('category')}] {it.get('filename')} -> {it.get('url')}")
        if len(items) > 20:
            print(f"  ... and {len(items) - 20} more.")
        return True

    elif parsed.command == "hash":
        if not os.path.exists(parsed.filepath):
            print(f"❌ File not found: {parsed.filepath}")
            return True
        hashes = compute_checksums(parsed.filepath)
        print(f"File: {parsed.filepath}")
        print(f"MD5:    {hashes['md5']}")
        print(f"SHA-1:  {hashes['sha1']}")
        print(f"SHA256: {hashes['sha256']}")
        return True

    return False
