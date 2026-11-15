import os
import sys
import time
import unittest

# Ensure FalconDM root is in sys.path
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.engine import DownloadTask, Segment, TokenBucketRateLimiter
from core.state_manager import DownloadManager, detect_category
from core.clipboard_watcher import ClipboardWatcher
from core.media_grabber import MediaGrabber
from core.debrid_resolver import DebridResolver
from core.telegram_bot import TelegramRemoteBot
from core.cloud_uploader import CloudUploader
from core.converter import MediaConverter
from core.config_manager import config_store
from gui.download_window import format_bytes, format_speed, format_time


class TestFalconDMEnhancements(unittest.TestCase):

    def test_format_helpers(self):
        self.assertEqual(format_bytes(0), "0 B")
        self.assertEqual(format_bytes(1024), "1.00 KB")
        self.assertEqual(format_bytes(1024 * 1024 * 50), "50.00 MB")
        self.assertEqual(format_bytes(1024 * 1024 * 1024 * 2), "2.00 GB")

        self.assertEqual(format_speed(0), "0.0 KB/s")
        self.assertEqual(format_speed(512 * 1024), "512.0 KB/s")
        self.assertEqual(format_speed(2.5 * 1024 * 1024), "2.50 MB/s")

        self.assertEqual(format_time(0), "--:--:--")
        self.assertEqual(format_time(65), "01:05")
        self.assertEqual(format_time(3665), "01:01:05")

    def test_token_bucket_rate_limiter(self):
        limiter = TokenBucketRateLimiter(rate_bps=1000)
        self.assertEqual(limiter.rate_bps, 1000)
        limiter.set_rate(5000)
        self.assertEqual(limiter.rate_bps, 5000)
        limiter.set_rate(0)
        t0 = time.time()
        limiter.consume(100000)
        self.assertLess(time.time() - t0, 0.1)

    def test_auto_retry_and_resilience_attributes(self):
        task = DownloadTask("test_id", "https://example.com/file.zip", "test.zip")
        self.assertTrue(hasattr(task, "auto_retry_count"))
        self.assertTrue(hasattr(task, "max_auto_retries"))
        self.assertTrue(hasattr(task, "auto_retry_enabled"))
        self.assertTrue(task.auto_retry_enabled)
        self.assertEqual(task.auto_retry_count, 0)
        self.assertEqual(task.max_auto_retries, 10)

    def test_global_speed_limiter(self):
        manager = DownloadManager(data_file="test_downloads_temp.json")
        try:
            self.assertEqual(manager.global_speed_limit_bps, 0)
            manager.set_global_speed_limit(2 * 1024 * 1024)
            self.assertEqual(manager.global_speed_limit_bps, 2 * 1024 * 1024)

            t1 = DownloadTask("t1", "https://example.com/1.zip", "1.zip")
            t2 = DownloadTask("t2", "https://example.com/2.zip", "2.zip")
            t1.status = DownloadTask.STATUS_DOWNLOADING
            t2.status = DownloadTask.STATUS_DOWNLOADING
            manager.tasks["t1"] = t1
            manager.tasks["t2"] = t2

            manager.rebalance_speed_limits()
            self.assertEqual(t1.speed_limit_bps, 1024 * 1024)
            self.assertEqual(t2.speed_limit_bps, 1024 * 1024)

            t1.status = DownloadTask.STATUS_COMPLETED
            manager.rebalance_speed_limits()
            self.assertEqual(t2.speed_limit_bps, 2 * 1024 * 1024)

            manager.set_global_speed_limit(0)
            self.assertEqual(t2.speed_limit_bps, 0)
        finally:
            if os.path.exists("test_downloads_temp.json"):
                os.remove("test_downloads_temp.json")

    def test_advanced_clipboard_watcher(self):
        detected = []
        watcher = ClipboardWatcher(lambda: "", lambda url: detected.append(url))

        self.assertTrue(watcher.is_downloadable("https://www.youtube.com/watch?v=dQw4w9WgXcQ"))
        self.assertTrue(watcher.is_downloadable("https://tiktok.com/@user/video/12345"))
        self.assertTrue(watcher.is_downloadable("https://x.com/user/status/123456"))

        self.assertTrue(watcher.is_downloadable("https://drive.google.com/file/d/1a2b3c/view"))
        self.assertTrue(watcher.is_downloadable("https://www.mediafire.com/file/abcdef/archive"))
        self.assertTrue(watcher.is_downloadable("https://pixeldrain.com/u/abc1234"))
        self.assertTrue(watcher.is_downloadable("https://mega.nz/file/xyz#123"))

        self.assertTrue(watcher.is_downloadable("https://example.com/downloads/setup.exe"))
        self.assertTrue(watcher.is_downloadable("https://cdn.example.org/download.php?file=game.zip&token=abc"))
        self.assertTrue(watcher.is_downloadable("https://live.site.com/hls/stream.m3u8"))

        self.assertTrue(watcher.is_downloadable("magnet:?xt=urn:btih:0123456789abcdef"))

        self.assertFalse(watcher.is_downloadable("https://google.com/search?q=weather"))
        self.assertFalse(watcher.is_downloadable("Just some text"))
        self.assertFalse(watcher.is_downloadable(""))

    def test_media_grabber_heuristics(self):
        self.assertTrue(MediaGrabber.is_likely_media_url("https://www.youtube.com/watch?v=abc"))
        self.assertTrue(MediaGrabber.is_likely_media_url("https://cdn.site.com/video.mp4"))
        self.assertTrue(MediaGrabber.is_likely_media_url("https://stream.server.net/live/manifest.m3u8"))
        self.assertFalse(MediaGrabber.is_likely_media_url("https://example.com/document.pdf"))

    def test_category_detection(self):
        self.assertEqual(detect_category("movie.mp4"), "Video")
        self.assertEqual(detect_category("song.flac"), "Audio")
        self.assertEqual(detect_category("backup.7z"), "Compressed")
        self.assertEqual(detect_category("installer.msi"), "Program")
        self.assertEqual(detect_category("invoice.pdf"), "Document")
        self.assertEqual(detect_category("photo.png"), "Image")

    def test_debrid_resolver(self):
        self.assertTrue(DebridResolver.is_supported_url("https://rapidgator.net/file/123456/test.rar"))
        self.assertTrue(DebridResolver.is_supported_url("https://1fichier.com/?abcdef"))
        self.assertTrue(DebridResolver.is_supported_url("magnet:?xt=urn:btih:fedcba9876543210"))
        self.assertFalse(DebridResolver.is_supported_url("https://example.com/file.zip"))

    def test_telegram_remote_bot(self):
        bot = TelegramRemoteBot()
        self.assertFalse(bot.is_configured())  # Token is empty initially
        self.assertEqual(bot.allowed_chats, [])

    def test_cloud_uploader(self):
        self.assertFalse(CloudUploader.is_auto_upload_enabled())
        self.assertFalse(CloudUploader.should_delete_after_upload())

    def test_media_converter_extensions(self):
        self.assertTrue(hasattr(MediaConverter, "compress_for_discord"))
        self.assertTrue(hasattr(MediaConverter, "extract_subtitles"))

    def test_turbo_http_adapter_and_stall_kick(self):
        task = DownloadTask("test_stall", "https://example.com/test.iso", "test.iso")
        self.assertEqual(task.stalled_timeout, 8.0)
        self.assertEqual(task.priority, 1)
        self.assertEqual(task.mirrors, [])

        seg = Segment(0, 0, 1000)
        self.assertTrue(hasattr(seg, "stall_count"))
        self.assertTrue(hasattr(seg, "last_progress_time"))
        self.assertTrue(hasattr(seg, "kick_requested"))
        self.assertEqual(seg.stall_count, 0)
        self.assertFalse(seg.kick_requested)

    def test_queue_reordering_and_priorities(self):
        temp_file = "test_queue_temp.json"
        manager = DownloadManager(data_file=temp_file)
        try:
            t1 = manager.create_task("https://example.com/1.zip", "1.zip", auto_start=False)
            t2 = manager.create_task("https://example.com/2.zip", "2.zip", auto_start=False)
            t3 = manager.create_task("https://example.com/3.zip", "3.zip", auto_start=False)

            self.assertEqual(list(manager.tasks.keys()), [t1.task_id, t2.task_id, t3.task_id])

            # Move Up
            self.assertTrue(manager.move_task_up(t2.task_id))
            self.assertEqual(list(manager.tasks.keys()), [t2.task_id, t1.task_id, t3.task_id])

            # Move Down
            self.assertTrue(manager.move_task_down(t2.task_id))
            self.assertEqual(list(manager.tasks.keys()), [t1.task_id, t2.task_id, t3.task_id])

            # Move to Bottom / Top
            self.assertTrue(manager.move_task_to_bottom(t1.task_id))
            self.assertEqual(list(manager.tasks.keys()), [t2.task_id, t3.task_id, t1.task_id])
            self.assertTrue(manager.move_task_to_top(t1.task_id))
            self.assertEqual(list(manager.tasks.keys()), [t1.task_id, t2.task_id, t3.task_id])

            # Set Priority
            manager.set_task_priority(t3.task_id, DownloadTask.PRIORITY_HIGH)
            self.assertEqual(t3.priority, 2)

            # Fallback Mirror
            self.assertTrue(manager.add_task_mirror(t1.task_id, "https://mirror.example.com/1.zip"))
            self.assertIn("https://mirror.example.com/1.zip", t1.mirrors)

            # Serialization check
            d = t1.to_dict()
            self.assertEqual(d["priority"], 1)
            self.assertIn("https://mirror.example.com/1.zip", d["mirrors"])

            restored = DownloadTask.from_dict(d)
            self.assertEqual(restored.priority, 1)
            self.assertEqual(restored.mirrors, ["https://mirror.example.com/1.zip"])
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)

    def test_media_grabber_pro_capabilities(self):
        import inspect
        sig = inspect.signature(MediaGrabber.download_media)
        self.assertIn("download_subtitles", sig.parameters)

    def test_browser_extension_registration(self):
        import json
        from core.platform_utils import register_browser_integration
        ok = register_browser_integration()
        self.assertTrue(ok)
        
        # Verify JSON manifests
        base_dir = os.path.dirname(os.path.abspath(__file__))
        c_manifest = os.path.join(base_dir, "core", "com.falcondm.downloader.json")
        f_manifest = os.path.join(base_dir, "core", "com.falcondm.downloader_firefox.json")
        self.assertTrue(os.path.exists(c_manifest))
        with open(c_manifest, "r", encoding="utf-8") as f:
            cdata = json.load(f)
        self.assertIn("path", cdata)
        self.assertTrue(cdata["path"].endswith("native_host.bat"))
        self.assertIn("chrome-extension://kbekmfgcpjeiiiehpffkapbpncbpfjcj/", cdata["allowed_origins"])

        # Reset back to portable relative path to prevent local path leaks
        cdata["path"] = "native_host.bat"
        with open(c_manifest, "w", encoding="utf-8") as f:
            json.dump(cdata, f, indent=2)
        if os.path.exists(f_manifest):
            with open(f_manifest, "r", encoding="utf-8") as f:
                fdata = json.load(f)
            fdata["path"] = "native_host.bat"
            with open(f_manifest, "w", encoding="utf-8") as f:
                json.dump(fdata, f, indent=2)

    def test_lightweight_memory_and_low_spec_utils(self):
        from core.platform_utils import trim_memory_footprint, is_low_spec_system
        # Test memory trim runs without exception
        trim_memory_footprint()
        # Test low-spec check returns a boolean
        res = is_low_spec_system()
        self.assertIsInstance(res, bool)

    def test_prevent_system_sleep_and_audio(self):
        from core.platform_utils import prevent_system_sleep, play_audio_alert
        # Test sleep prevention toggles cleanly
        ok1 = prevent_system_sleep(True)
        ok2 = prevent_system_sleep(False)
        self.assertIsInstance(ok1, bool)
        self.assertIsInstance(ok2, bool)

        # Test audio alert dispatch
        play_audio_alert("complete")
        play_audio_alert("error")

    def test_fast_preallocate_file(self):
        from core.platform_utils import fast_preallocate_file
        test_path = os.path.join(_ROOT, "test_prealloc_temp.bin")
        try:
            ok = fast_preallocate_file(test_path, 1024 * 1024)
            self.assertTrue(ok)
            self.assertTrue(os.path.exists(test_path))
            self.assertEqual(os.path.getsize(test_path), 1024 * 1024)
        finally:
            if os.path.exists(test_path):
                os.remove(test_path)

    def test_sequential_stream_mode_and_preview(self):
        task = DownloadTask(
            task_id="seq_test",
            url="https://example.com/movie.mp4",
            save_path="test_movie.mp4",
            num_connections=6,
            sequential_mode=True
        )
        task.file_size = 100 * 1024 * 1024  # 100 MB
        task.resumable = True
        task.init_segments()

        self.assertTrue(task.sequential_mode)
        # Check that head (seg 0) starts at 0 and tail (seg 1) starts near the end
        self.assertEqual(task.segments[0].start, 0)
        self.assertGreater(task.segments[1].start, 90 * 1024 * 1024)

        # Test serialization
        d = task.to_dict()
        self.assertTrue(d.get("sequential_mode"))
        restored = DownloadTask.from_dict(d)
        self.assertTrue(restored.sequential_mode)

    def test_smart_routing_rules(self):
        temp_data = os.path.join(_ROOT, "test_routing_temp.json")
        manager = DownloadManager(data_file=temp_data)
        try:
            manager.add_routing_rule("github.com", os.path.join(_ROOT, "test_dev_folder"))
            dest = manager.resolve_destination_folder("https://github.com/release/tool.zip", "tool.zip", "Compressed")
            self.assertEqual(os.path.abspath(dest), os.path.abspath(os.path.join(_ROOT, "test_dev_folder")))

            manager.remove_routing_rule("github.com")
            dest2 = manager.resolve_destination_folder("https://github.com/release/tool.zip", "tool.zip", "Compressed")
            self.assertIn("Compressed", dest2)
        finally:
            if os.path.exists(temp_data):
                os.remove(temp_data)
            dev_f = os.path.join(_ROOT, "test_dev_folder")
            if os.path.exists(dev_f):
                os.rmdir(dev_f)

    def test_remember_download_folder_and_preferences(self):
        # Verify default configuration keys exist
        self.assertTrue(config_store.get("remember_last_download_dir", True))
        self.assertIn("category_custom_dirs", config_store.settings)
        self.assertIn("last_download_dir", config_store.settings)

        # Test updating and persisting category-specific remembered directories
        test_dir = os.path.join(_ROOT, "test_custom_cat_dir")
        cat_dirs = dict(config_store.get("category_custom_dirs", {}) or {})
        cat_dirs["Video"] = test_dir
        config_store.set("category_custom_dirs", cat_dirs)
        config_store.set("last_download_dir", test_dir)

        self.assertEqual(config_store.get("category_custom_dirs").get("Video"), test_dir)
        self.assertEqual(config_store.get("last_download_dir"), test_dir)

        # Restore
        cat_dirs.pop("Video", None)
        config_store.set("category_custom_dirs", cat_dirs)
        config_store.set("last_download_dir", "")

    def test_falcon_logger_and_diagnostics(self):
        from core.logger import falcon_logger
        self.assertIsNotNone(falcon_logger)
        log_path = falcon_logger.get_log_file_path()
        self.assertTrue(os.path.exists(log_path) or os.path.exists(os.path.dirname(log_path)))

        # Test diagnostic logging
        task = DownloadTask("diag_test", "https://example.com/test_err.zip", "test_err.zip")
        self.assertTrue(hasattr(task, "diagnostic_log"))
        
        falcon_logger.log_thread_error(task, 1, Exception("403 Forbidden"), task.url, status_code=403)
        self.assertTrue(len(task.diagnostic_log) > 0)
        self.assertIn("403", task.diagnostic_log[-1])
        self.assertIn("HINT", task.diagnostic_log[-1])

        # Test reading logs
        recent = falcon_logger.read_recent_logs(50)
        self.assertIsInstance(recent, str)
        self.assertIn("THREAD_ERROR", recent)

    def test_host_resolvers(self):
        from core.host_resolvers import HostResolver
        self.assertTrue(HostResolver.is_resolvable("https://drive.google.com/file/d/1A2B3C4D/view?usp=sharing"))
        self.assertTrue(HostResolver.is_resolvable("https://dropbox.com/s/12345/myfile.zip?dl=0"))
        self.assertTrue(HostResolver.is_resolvable("https://github.com/torvalds/linux/blob/master/Makefile"))
        self.assertTrue(HostResolver.is_resolvable("https://pixeldrain.com/u/abc12345"))
        self.assertTrue(HostResolver.is_resolvable("https://www.mediafire.com/file/xyz123/file.rar/file"))
        self.assertFalse(HostResolver.is_resolvable("https://example.com/regular_file.zip"))

        # Test Dropbox resolution
        db_res = HostResolver.resolve_url("https://www.dropbox.com/s/12345/myfile.zip?dl=0")
        self.assertEqual(db_res["resolved_url"], "https://www.dropbox.com/s/12345/myfile.zip?dl=1")
        self.assertEqual(db_res["host"], "Dropbox")

        # Test GitHub resolution
        gh_res = HostResolver.resolve_url("https://github.com/torvalds/linux/blob/master/Makefile")
        self.assertEqual(gh_res["resolved_url"], "https://github.com/torvalds/linux/raw/master/Makefile")
        self.assertEqual(gh_res["host"], "GitHub Raw")

        # Test PixelDrain resolution
        px_res = HostResolver.resolve_url("https://pixeldrain.com/u/abc12345")
        self.assertEqual(px_res["resolved_url"], "https://pixeldrain.com/api/file/abc12345?download")
        self.assertEqual(px_res["host"], "PixelDrain")

    def test_range_integrity_and_single_stream_fallback(self):
        task = DownloadTask("test_range_integ", "https://example.com/test.bin", os.path.join(_ROOT, "temp_range_test.bin"))
        task.file_size = 1000
        task.resumable = True
        task.num_connections = 2
        task.init_segments()
        self.assertEqual(len(task.segments), 2)
        s0 = task.segments[0]
        s1 = task.segments[1]

        # Verify segments configuration
        self.assertEqual(s0.start, 0)
        self.assertEqual(s1.start, 500)

        # Clean up
        if os.path.exists(task.save_path):
            os.remove(task.save_path)

    def test_version_v2(self):
        import core
        self.assertEqual(core.__version__, "2.8.0")

    def test_batch_manager_multidimensional_and_alpha(self):
        from core.batch_manager import BatchManager
        # Numeric expansion
        urls_num = BatchManager.expand_pattern("https://example.com/file[01-03].zip")
        self.assertEqual(urls_num, [
            "https://example.com/file01.zip",
            "https://example.com/file02.zip",
            "https://example.com/file03.zip"
        ])
        # Alpha expansion
        urls_alpha = BatchManager.expand_pattern("https://example.com/part_[a-c].rar")
        self.assertEqual(urls_alpha, [
            "https://example.com/part_a.rar",
            "https://example.com/part_b.rar",
            "https://example.com/part_c.rar"
        ])
        # Multi-dimensional combo
        urls_combo = BatchManager.expand_pattern("https://example.com/doc[1-2]_[a-b].pdf")
        self.assertEqual(urls_combo, [
            "https://example.com/doc1_a.pdf",
            "https://example.com/doc1_b.pdf",
            "https://example.com/doc2_a.pdf",
            "https://example.com/doc2_b.pdf"
        ])

    def test_metalink_parser_and_exporter(self):
        from core.import_export import DownloadListSerializer
        metalink_xml = """<?xml version="1.0" encoding="UTF-8"?>
<metalink xmlns="urn:ietf:params:xml:ns:metalink">
  <file name="ubuntu-24.04.iso">
    <size>4000000000</size>
    <hash type="sha-256">01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b</hash>
    <url priority="1">https://mirror1.example.com/ubuntu-24.04.iso</url>
    <url priority="2">https://mirror2.example.com/ubuntu-24.04.iso</url>
  </file>
</metalink>"""
        parsed = DownloadListSerializer.import_metalink(metalink_xml)
        self.assertEqual(len(parsed), 1)
        item = parsed[0]
        self.assertEqual(item["filename"], "ubuntu-24.04.iso")
        self.assertEqual(item["url"], "https://mirror1.example.com/ubuntu-24.04.iso")
        self.assertEqual(item["mirrors"], ["https://mirror2.example.com/ubuntu-24.04.iso"])
        self.assertEqual(item["checksum_type"], "sha256")
        self.assertEqual(item["checksum_expected"], "01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b")

    def test_curl_command_generator(self):
        from core.import_export import DownloadListSerializer
        task_data = {
            "url": "https://example.com/release.tar.gz",
            "filename": "release.tar.gz",
            "headers": {
                "User-Agent": "Mozilla/5.0 Test",
                "Referer": "https://example.com/portal"
            }
        }
        curl_cmd = DownloadListSerializer.generate_curl_command(task_data)
        self.assertIn("curl -C - -L -o \"release.tar.gz\"", curl_cmd)
        self.assertIn("https://example.com/release.tar.gz", curl_cmd)
        self.assertIn("-H \"User-Agent: Mozilla/5.0 Test\"", curl_cmd)
        self.assertIn("-H \"Referer: https://example.com/portal\"", curl_cmd)

    def test_url_checksum_sniffing_and_verification(self):
        url_with_hash = "https://example.com/archive.zip#sha256=abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"
        task = DownloadTask("test_hash_sniff", url_with_hash, os.path.join(_ROOT, "temp_hash_test.bin"))
        self.assertEqual(task.checksum_type, "sha256")
        self.assertEqual(task.checksum_expected, "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789")

        # Test actual hash verification against temporary file
        test_path = os.path.join(_ROOT, "temp_hash_test.bin")
        with open(test_path, "wb") as f:
            f.write(b"Hello FalconDM v2.8.0")
        
        import hashlib
        real_hash = hashlib.sha256(b"Hello FalconDM v2.8.0").hexdigest()
        task.checksum_expected = real_hash
        verified = task.verify_integrity()
        self.assertTrue(verified)
        self.assertTrue(task.checksum_verified)

        # Clean up
        if os.path.exists(test_path):
            os.remove(test_path)

    def test_torrent_engine_trackers_and_dht(self):
        from core.torrent_engine import TorrentEngine, PUBLIC_TRACKERS, DHT_BOOTSTRAP_NODES
        self.assertGreaterEqual(len(PUBLIC_TRACKERS), 6)
        self.assertGreaterEqual(len(DHT_BOOTSTRAP_NODES), 2)
        
        magnet = "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567&dn=TestPayload"
        enhanced = TorrentEngine.enhance_magnet_link(magnet)
        self.assertIn("tr=udp", enhanced)
        self.assertIn("dn=TestPayload", enhanced)

        # Test command building with metadata-only mode
        cmd = TorrentEngine.build_aria2_command(magnet, "C:\\TestDir", metadata_only=True)
        self.assertIn("--bt-metadata-only=true", cmd)
        self.assertIn("--enable-dht=true", cmd)

    def test_auto_speed_optimizer(self):
        from core.engine import DownloadTask
        # High-speed connection probe with low latency & large file -> scales to 32 connections
        task_fast = DownloadTask("opt_fast", "http://example.com/big.iso", "big.iso", num_connections=8)
        task_fast.file_size = 80 * 1024 * 1024
        task_fast.resumable = True
        task_fast._apply_auto_speed_optimization(latency_ms=35.0)
        self.assertEqual(task_fast.num_connections, 32)

        # Medium latency & medium file -> scales to 16 connections
        task_med = DownloadTask("opt_med", "http://example.com/med.zip", "med.zip", num_connections=8)
        task_med.file_size = 12 * 1024 * 1024
        task_med.resumable = True
        task_med._apply_auto_speed_optimization(latency_ms=130.0)
        self.assertEqual(task_med.num_connections, 16)

        # Non-resumable host -> locks to 1 connection
        task_single = DownloadTask("opt_single", "http://example.com/live.stream", "live.stream", num_connections=8)
        task_single.file_size = 0
        task_single.resumable = False
        task_single._apply_auto_speed_optimization(latency_ms=20.0)
        self.assertEqual(task_single.num_connections, 1)

    def test_theme_palettes_and_custom_accents(self):
        from core.config_manager import THEME_PALETTES, config_store
        expected_themes = ["Cyberpunk Cyan", "Emerald Matrix", "Sunset Orange", "Vaporwave Violet", "Crimson Turbo"]
        for theme in expected_themes:
            self.assertIn(theme, THEME_PALETTES)
            palette = THEME_PALETTES[theme]
            self.assertIn("primary", palette)
            self.assertIn("accent", palette)
            self.assertIn("graph_fill", palette)
            self.assertIn("graph_line", palette)

        # Test settings persistence
        config_store.set("ui_theme_accent", "Emerald Matrix")
        self.assertEqual(config_store.get("ui_theme_accent"), "Emerald Matrix")
        config_store.set("ui_theme_accent", "Cyberpunk Cyan")

    def test_browser_extension_packaging(self):
        from build_extension_packages import build_extension_packages
        build_extension_packages()
        out_dir = os.path.join(_ROOT, "dist_extension")
        chrome_zip = os.path.join(out_dir, "FalconDM-Chrome-WebStore-v2.8.0.zip")
        firefox_zip = os.path.join(out_dir, "FalconDM-Firefox-AMO-v2.8.0.zip")
        guide_file = os.path.join(out_dir, "SUBMISSION_GUIDE.md")

        self.assertTrue(os.path.isfile(chrome_zip))
        self.assertTrue(os.path.isfile(firefox_zip))
        self.assertTrue(os.path.isfile(guide_file))
        self.assertGreater(os.path.getsize(chrome_zip), 1000)
        self.assertGreater(os.path.getsize(firefox_zip), 1000)

        # Verify manifest inside Chrome zip has no gecko settings
        import zipfile
        with zipfile.ZipFile(chrome_zip, "r") as z:
            manifest_str = z.read("manifest.json").decode("utf-8")
            self.assertNotIn("browser_specific_settings", manifest_str)
            self.assertNotIn('"key"', manifest_str)

    def test_task_latency_ms_and_speed_indicator(self):
        task = DownloadTask("lat_test", "https://example.com/test.iso", "test.iso", num_connections=8)
        self.assertEqual(task.latency_ms, 0.0)
        task.latency_ms = 45.2
        self.assertEqual(task.latency_ms, 45.2)

    def test_floating_download_theme_and_security_suite(self):
        from gui.download_window import FloatingDownloadDialog
        from core.hasher import compute_checksums
        import tempfile

        # Verify theme palette helper returns valid palettes
        for theme_name in ["Emerald Matrix", "Sunset Orange", "Vaporwave Violet", "Crimson Turbo", "Cyberpunk Cyan"]:
            config_store.set("ui_theme_accent", theme_name)
            # Create a mock dialog instance without running Tk loop
            dummy_task = DownloadTask("dummy_task", "https://example.com/test.bin", "test.bin")
            # Directly verify theme lookup
            from core.config_manager import THEME_PALETTES
            palette = THEME_PALETTES.get(theme_name)
            self.assertIsNotNone(palette)
            self.assertIn("accent", palette)
            self.assertIn("primary", palette)

        # Reset back to default
        config_store.set("ui_theme_accent", "Cyberpunk Cyan")

        # Test checksum verification with temp file
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tf.write(b"FalconDM Turbo Checksum Test Data 12345")
            temp_path = tf.name

        try:
            hashes = compute_checksums(temp_path, ['sha256', 'md5'])
            self.assertIn('sha256', hashes)
            self.assertIn('md5', hashes)
            self.assertEqual(len(hashes['sha256']), 64)
            self.assertEqual(len(hashes['md5']), 32)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
