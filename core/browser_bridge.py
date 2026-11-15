import os
import json
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import urllib.parse
from typing import Callable, Optional, Any
from core.platform_utils import safe_print

HTML_DASHBOARD = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FalconDM — Universal Browser Integration Hub</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: linear-gradient(135deg, #090d16 0%, #0f172a 100%);
            color: #f8fafc;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 24px;
        }
        .container {
            width: 100%;
            max-width: 760px;
            background: #111827;
            border: 1px solid #1e293b;
            border-radius: 16px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.6), 0 0 40px rgba(37, 99, 235, 0.15);
            padding: 32px;
        }
        .header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 20px;
            border-bottom: 1px solid #1f2937;
            padding-bottom: 18px;
        }
        .logo-title {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .icon {
            font-size: 26px;
            background: rgba(37, 99, 235, 0.2);
            border: 1px solid #2563eb;
            width: 46px;
            height: 46px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        h1 {
            font-size: 20px;
            font-weight: 800;
            color: #ffffff;
            letter-spacing: -0.5px;
        }
        .badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(34, 197, 94, 0.15);
            border: 1px solid rgba(34, 197, 94, 0.3);
            color: #4ade80;
            font-size: 12px;
            font-weight: 700;
            padding: 6px 12px;
            border-radius: 999px;
        }
        .dot {
            width: 8px;
            height: 8px;
            background: #22c55e;
            border-radius: 50%;
            box-shadow: 0 0 8px #22c55e;
        }
        p.subtitle {
            color: #94a3b8;
            font-size: 13px;
            line-height: 1.5;
            margin-bottom: 20px;
        }
        /* Navigation Tabs */
        .tabs {
            display: flex;
            gap: 6px;
            border-bottom: 1px solid #1e293b;
            margin-bottom: 20px;
            overflow-x: auto;
            padding-bottom: 4px;
        }
        .tab-btn {
            background: transparent;
            border: none;
            color: #94a3b8;
            font-size: 13px;
            font-weight: 700;
            padding: 8px 14px;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s;
            white-space: nowrap;
        }
        .tab-btn:hover {
            color: #f1f5f9;
            background: #182234;
        }
        .tab-btn.active {
            color: #38bdf8;
            background: #182234;
            border: 1px solid #2563eb;
        }
        .tab-content {
            display: none;
            animation: fadeIn 0.2s ease;
        }
        .tab-content.active {
            display: block;
        }
        .card {
            background: #182234;
            border: 1px solid #1e293b;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
        }
        .card h3 {
            font-size: 15px;
            color: #38bdf8;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .card p {
            color: #94a3b8;
            font-size: 13px;
            margin-bottom: 14px;
            line-height: 1.5;
        }
        ol.steps {
            color: #cbd5e1;
            font-size: 13px;
            margin-left: 20px;
            margin-bottom: 16px;
            line-height: 1.7;
        }
        code {
            background: #0f172a;
            color: #38bdf8;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: monospace;
            font-size: 12px;
        }
        .btn-group {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 12px;
        }
        .btn-action {
            background: #2563eb;
            color: #ffffff;
            border: none;
            font-weight: 700;
            font-size: 12px;
            padding: 9px 16px;
            border-radius: 7px;
            cursor: pointer;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            transition: all 0.2s ease;
        }
        .btn-action:hover {
            background: #1d4ed8;
            transform: translateY(-1px);
        }
        .btn-secondary {
            background: #374151;
            color: #e5e7eb;
        }
        .btn-secondary:hover {
            background: #4b5563;
        }
        /* Bookmarklet button style */
        .bookmarklet-btn {
            display: inline-block;
            background: linear-gradient(135deg, #0284c7, #2563eb);
            color: #fff !important;
            font-weight: 800;
            font-size: 14px;
            padding: 12px 24px;
            border-radius: 999px;
            border: 2px dashed #38bdf8;
            text-decoration: none;
            cursor: move;
            box-shadow: 0 4px 15px rgba(2, 132, 199, 0.4);
            margin: 10px 0;
            transition: all 0.2s;
        }
        .bookmarklet-btn:hover {
            transform: scale(1.03);
            box-shadow: 0 6px 20px rgba(2, 132, 199, 0.6);
        }
        /* Send box */
        .send-box {
            background: #0f172a;
            border: 1px solid #1e293b;
            border-radius: 12px;
            padding: 18px;
            margin-bottom: 20px;
        }
        .send-box label {
            display: block;
            font-size: 11px;
            font-weight: 700;
            color: #cbd5e1;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .input-group {
            display: flex;
            gap: 8px;
        }
        input[type="text"] {
            flex: 1;
            background: #181a20;
            border: 1px solid #334155;
            color: #f8fafc;
            padding: 10px 14px;
            border-radius: 8px;
            font-size: 13px;
            outline: none;
            transition: border-color 0.2s;
        }
        input[type="text"]:focus {
            border-color: #38bdf8;
        }
        button.btn-send {
            background: #0284c7;
            color: #ffffff;
            border: none;
            font-weight: 700;
            padding: 10px 18px;
            border-radius: 8px;
            cursor: pointer;
            transition: background 0.2s;
        }
        button.btn-send:hover {
            background: #0369a1;
        }
        .features-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
        }
        .feat-item {
            background: #0f172a;
            border: 1px solid #1e293b;
            padding: 12px;
            border-radius: 8px;
            font-size: 12px;
            color: #94a3b8;
        }
        .feat-item strong {
            color: #f1f5f9;
            display: block;
            margin-bottom: 2px;
            font-size: 13px;
        }
        .toast {
            position: fixed;
            bottom: 24px;
            right: 24px;
            background: #1e293b;
            border: 1px solid #22c55e;
            color: #4ade80;
            font-weight: 700;
            padding: 12px 20px;
            border-radius: 8px;
            display: none;
            box-shadow: 0 4px 15px rgba(0,0,0,0.5);
            animation: fadeIn 0.3s;
            z-index: 9999;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo-title">
                <div class="icon">⚡</div>
                <div>
                    <h1>FalconDM Universal Browser Hub</h1>
                    <div style="font-size: 12px; color: #64748b;">Compatible with ANY Browser on your System</div>
                </div>
            </div>
            <div class="badge">
                <div class="dot"></div>
                ONLINE (:9666)
            </div>
        </div>

        <p class="subtitle">
            FalconDM's turbo download engine integrates with <strong>every major web browser</strong>. Select your browser below for 10-second setup or use the universal 1-click bookmarklet:
        </p>

        <!-- Browser Navigation Tabs -->
        <div class="tabs">
            <button class="tab-btn active" onclick="switchTab('tab-chrome')">🌐 Chrome / Edge / Brave</button>
            <button class="tab-btn" onclick="switchTab('tab-firefox')">🦊 Mozilla Firefox</button>
            <button class="tab-btn" onclick="switchTab('tab-safari')">🍏 Safari & Any Browser</button>
            <button class="tab-btn" onclick="switchTab('tab-userscript')">📜 Userscript</button>
            <button class="tab-btn" onclick="switchTab('tab-clipboard')">📋 Clipboard (No-Install)</button>
        </div>

        <!-- Tab 1: Chrome / Chromium / Edge / Brave / Opera / Arc / Vivaldi -->
        <div id="tab-chrome" class="tab-content active">
            <div class="card">
                <div style="font-size: 11px; font-weight: 800; color: #38bdf8; text-transform: uppercase; margin-bottom: 4px;">Chromium Browsers • Native Extension</div>
                <h3>🌐 Google Chrome, Edge, Brave, Opera, Arc, Vivaldi</h3>

                <!-- 1-Click Instant Installer Box -->
                <div style="background: rgba(37, 99, 235, 0.12); border: 1px solid rgba(59, 130, 246, 0.4); border-radius: 12px; padding: 16px; margin: 14px 0 20px 0; display: flex; align-items: center; justify-content: space-between; gap: 14px; flex-wrap: wrap;">
                    <div style="flex: 1; min-width: 250px;">
                        <div style="font-weight: 800; color: #60a5fa; font-size: 14px; display: flex; align-items: center; gap: 6px;">⚡ 1-Click Auto Install (100% Free - No Store Fee)</div>
                        <div style="font-size: 12px; color: #94a3b8; margin-top: 4px; line-height: 1.4;">Registers native registry host, copies extension folder path to clipboard & launches your browser in one tap!</div>
                    </div>
                    <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                        <button class="btn-action" style="background: linear-gradient(135deg, #2563eb, #1d4ed8); font-weight: 700; padding: 8px 14px; font-size: 12px;" onclick="autoInstallExtension('chrome')">⚡ Install for Chrome</button>
                        <button class="btn-action" style="background: linear-gradient(135deg, #0284c7, #0369a1); font-weight: 700; padding: 8px 14px; font-size: 12px;" onclick="autoInstallExtension('edge')">⚡ Install for Edge</button>
                        <button class="btn-action" style="background: linear-gradient(135deg, #ea580c, #c2410c); font-weight: 700; padding: 8px 14px; font-size: 12px;" onclick="autoInstallExtension('brave')">⚡ Install for Brave</button>
                    </div>
                </div>

                <p>Or install manually into any Chromium browser in 3 simple steps:</p>
                <ol class="steps">
                    <li>Open your browser extensions manager: <code id="browserExtUrl">chrome://extensions</code> (or <code onclick="navigator.clipboard.writeText('edge://extensions')">edge://extensions</code> / <code onclick="navigator.clipboard.writeText('brave://extensions')">brave://extensions</code>)</li>
                    <li>Turn ON <strong>Developer mode</strong> switch (top-right corner).</li>
                    <li>Click <strong>Load unpacked</strong> and select the <code>browser_extension</code> folder.</li>
                </ol>
                <div class="btn-group">
                    <button class="btn-action btn-secondary" onclick="openExtensionFolder()">📂 Open Extension Folder</button>
                    <button class="btn-action" onclick="launchBrowser('chrome')">🚀 Open Chrome Extensions</button>
                    <button class="btn-action" onclick="launchBrowser('edge')">🚀 Open Edge Extensions</button>
                    <button class="btn-action" onclick="launchBrowser('brave')">🚀 Open Brave Extensions</button>
                </div>
            </div>
        </div>

        <!-- Tab 2: Mozilla Firefox & Floorp & LibreWolf -->
        <div id="tab-firefox" class="tab-content">
            <div class="card">
                <div style="font-size: 11px; font-weight: 800; color: #f97316; text-transform: uppercase; margin-bottom: 4px;">Gecko Browsers • WebExtension</div>
                <h3>🦊 Mozilla Firefox, Floorp, LibreWolf, Waterfox</h3>
                <p>Firefox natively supports FalconDM via Manifest V3 temporary add-ons or packaged XPI:</p>
                <ol class="steps">
                    <li>In Firefox address bar, navigate to: <code>about:debugging#/runtime/this-firefox</code></li>
                    <li>Click <strong>Load Temporary Add-on...</strong> button.</li>
                    <li>Select the <code>manifest.json</code> file inside FalconDM's <code>browser_extension</code> folder (or download the <code>.xpi</code> below).</li>
                </ol>
                <div class="btn-group">
                    <button class="btn-action btn-secondary" onclick="openExtensionFolder()">📂 Open Extension Folder</button>
                    <a href="/falcondm.xpi" class="btn-action" style="background: #ea580c;">📥 Download Firefox Add-on (.xpi)</a>
                    <button class="btn-action" onclick="launchBrowser('firefox')">🚀 Open Firefox Debugging</button>
                </div>
            </div>
        </div>

        <!-- Tab 3: Safari & Any Other Browser (Bookmarklet) -->
        <div id="tab-safari" class="tab-content">
            <div class="card" style="text-align: center;">
                <div style="font-size: 11px; font-weight: 800; color: #a855f7; text-transform: uppercase; margin-bottom: 4px;">Universal Compatibility • Zero Installation</div>
                <h3 style="justify-content: center;">🍏 Universal 1-Click FalconDM Bookmarklet</h3>
                <p>Works in <strong>100% of browsers everywhere</strong> (Safari on Mac/iPad, Chrome, Edge, Firefox, Tor, mobile browsers, locked-down work PCs) with no extension needed:</p>
                
                <div style="margin: 16px 0;">
                    <a href="javascript:(function(){const u=window.location.href;const s=window.getSelection().toString();const t=prompt('⚡ Send download to FalconDM:',s||u);if(t){fetch('http://127.0.0.1:9666/download',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:t})}).then(r=>r.json()).then(d=>alert('⚡ Sent to FalconDM Turbo Downloader!')).catch(e=>alert('❌ FalconDM is not running. Launch FalconDM first!'));}})();" class="bookmarklet-btn" title="Drag this button to your Bookmarks Bar">
                        ⚡ Send to FalconDM
                    </a>
                </div>
                
                <p style="font-size: 12px; color: #cbd5e1; max-width: 520px; margin: 0 auto 14px;">
                    👆 <strong>Drag & Drop</strong> the button above directly into your browser's Bookmarks bar.<br>
                    Whenever you are on any video or download page, click the bookmark to send it to FalconDM!
                </p>
                <button class="btn-action btn-secondary" onclick="copyBookmarklet()">📋 Copy Bookmarklet Code</button>
            </div>
        </div>

        <!-- Tab 4: Tampermonkey Userscript -->
        <div id="tab-userscript" class="tab-content">
            <div class="card">
                <div style="font-size: 11px; font-weight: 800; color: #10b981; text-transform: uppercase; margin-bottom: 4px;">Userscript Manager • All Browsers</div>
                <h3>📜 Tampermonkey & Violentmonkey Userscript</h3>
                <p>If you already use Tampermonkey, Violentmonkey, or Greasemonkey in any browser:</p>
                <ol class="steps">
                    <li>Install <a href="https://www.tampermonkey.net/" target="_blank" style="color:#38bdf8; font-weight:bold;">Tampermonkey Extension</a> in your browser.</li>
                    <li>Click the button below — Tampermonkey will open and prompt you to install in 1 click:</li>
                </ol>
                <div class="btn-group">
                    <a href="/falcon_browser_extension.user.js" class="btn-action" style="background: #059669;">📥 1-Click Install Userscript</a>
                    <button class="btn-action btn-secondary" onclick="openExtensionFolder()">📂 View Script File</button>
                </div>
            </div>
        </div>

        <!-- Tab 5: Clipboard Sniffing -->
        <div id="tab-clipboard" class="tab-content">
            <div class="card">
                <div style="font-size: 11px; font-weight: 800; color: #f59e0b; text-transform: uppercase; margin-bottom: 4px;">Zero-Install • System-Wide</div>
                <h3>📋 Clipboard Auto-Sniffing (No Setup Needed)</h3>
                <p>FalconDM includes an automatic system clipboard watcher that monitors all browsers simultaneously:</p>
                <ul style="color: #cbd5e1; font-size: 13px; margin-left: 20px; margin-bottom: 14px; line-height: 1.7;">
                    <li>Keep FalconDM open in the background or minimized to the system tray.</li>
                    <li>Whenever you <strong>Copy (Ctrl+C)</strong> any downloadable file link or video link in <em>any</em> browser, FalconDM instantly detects and offers to turbo-download it!</li>
                    <li>Supports YouTube, TikTok, Facebook, Twitter, Google Drive, direct ZIP, EXE, ISO, MP4, and 30+ formats.</li>
                </ul>
            </div>
        </div>

        <!-- Quick URL Tester -->
        <div class="send-box">
            <label for="urlInput">⚡ Quick Test: Send any URL into FalconDM</label>
            <div class="input-group">
                <input type="text" id="urlInput" placeholder="Paste any file or video URL to test (e.g. https://.../file.zip)">
                <button class="btn-send" onclick="sendDownload()">Send</button>
            </div>
        </div>

        <!-- Feature Highlights -->
        <div class="features-grid">
            <div class="feat-item">
                <strong>⚡ IDM-Grade Download Interception</strong>
                Auto-intercepts .zip, .exe, .iso, .mp4, and binary downloads directly from your browser.
            </div>
            <div class="feat-item">
                <strong>🎬 Floating Video Grabber Badge</strong>
                Overlays a 1-click video grabber with resolution selection on YouTube, TikTok, Facebook, etc.
            </div>
        </div>
    </div>

    <div id="toast" class="toast">✓ Download sent to FalconDM!</div>

    <script>
        function switchTab(tabId) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            const target = document.getElementById(tabId);
            if (target) target.classList.add('active');
            event.target.classList.add('active');
        }

        function autoInstallExtension(name) {
            fetch('/api/install-extension', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ browser: name })
            })
            .then(res => res.json())
            .then(data => {
                showToast('🚀 Native host registered & folder path copied!');
                alert("⚡ FalconDM 1-Click Extension Setup\n\n" +
                      "1. The extension folder path has been COPIED to your clipboard!\n" +
                      "2. Your " + name.toUpperCase() + " extensions page has opened.\n\n" +
                      "Now simply do these 2 quick steps:\n" +
                      "  1. Turn ON 'Developer mode' (toggle switch at top-right)\n" +
                      "  2. Click 'Load unpacked' (top-left)\n" +
                      "  3. Press Ctrl + V in the folder dialog and hit Enter!\n\n" +
                      "That's it! FalconDM is fully active!");
            })
            .catch(() => showToast('Could not auto-launch. Please open browser manually.'));
        }

        function openExtensionFolder() {
            fetch('/open-folder', { method: 'POST' })
            .then(() => showToast('📂 Opened browser_extension folder in Windows Explorer!'))
            .catch(() => showToast('Folder: e:\\CODE\\FalconDM\\browser_extension'));
        }

        function launchBrowser(name) {
            fetch('/launch-browser', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ browser: name })
            })
            .then(() => showToast('🚀 Launching ' + name + ' extensions page...'))
            .catch(() => showToast('Could not launch browser directly. Open manually.'));
        }

        function copyBookmarklet() {
            const code = "javascript:(function(){const u=window.location.href;const s=window.getSelection().toString();const t=prompt('⚡ Send download to FalconDM:',s||u);if(t){fetch('http://127.0.0.1:9666/download',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:t})}).then(r=>r.json()).then(d=>alert('⚡ Sent to FalconDM Turbo Downloader!')).catch(e=>alert('❌ FalconDM is not running. Launch FalconDM first!'));}})();";
            navigator.clipboard.writeText(code).then(() => {
                showToast('📋 Bookmarklet code copied to clipboard!');
            });
        }

        function sendDownload() {
            const input = document.getElementById('urlInput');
            const url = input.value.trim();
            if (!url) return;

            fetch('/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: url })
            })
            .then(res => res.json())
            .then(data => {
                showToast('✓ Successfully sent to FalconDM!');
                input.value = '';
            })
            .catch(err => {
                showToast('❌ Error sending download to FalconDM.');
            });
        }

        function showToast(text) {
            const t = document.getElementById('toast');
            t.textContent = text;
            t.style.display = 'block';
            setTimeout(() => { t.style.display = 'none'; }, 3200);
        }
    </script>
</body>
</html>
"""

HTML_WEB_REMOTE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FalconDM — Web Remote Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', -apple-system, sans-serif; }
        body { background: #0b0f19; color: #f1f5f9; padding: 20px; min-height: 100vh; }
        .header { display: flex; justify-content: space-between; align-items: center; max-width: 860px; margin: 0 auto 24px; padding-bottom: 16px; border-bottom: 1px solid #1e293b; }
        .logo { font-size: 20px; font-weight: 800; color: #38bdf8; display: flex; align-items: center; gap: 8px; }
        .status-pill { background: rgba(34,197,94,0.15); border: 1px solid rgba(34,197,94,0.4); color: #4ade80; font-size: 11px; font-weight: bold; padding: 4px 12px; border-radius: 999px; }
        .container { max-width: 860px; margin: 0 auto; }
        .card { background: #131c2e; border: 1px solid #1e293b; border-radius: 12px; padding: 18px; margin-bottom: 14px; box-shadow: 0 4px 20px rgba(0,0,0,0.3); }
        .add-box { display: flex; gap: 8px; margin-bottom: 22px; }
        .add-input { flex: 1; background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 12px 14px; color: #fff; font-size: 14px; outline: none; }
        .add-input:focus { border-color: #2563eb; }
        .add-btn { background: #2563eb; color: #fff; border: none; border-radius: 8px; padding: 0 20px; font-weight: bold; cursor: pointer; font-size: 13px; }
        .add-btn:hover { background: #1d4ed8; }
        .task-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
        .task-title { font-weight: 600; font-size: 14px; color: #f8fafc; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 72%; }
        .badge { font-size: 11px; padding: 3px 8px; border-radius: 6px; font-weight: bold; }
        .badge-downloading { background: rgba(56,189,248,0.2); color: #38bdf8; }
        .badge-completed { background: rgba(34,197,94,0.2); color: #4ade80; }
        .badge-paused { background: rgba(234,179,8,0.2); color: #facc15; }
        .badge-error { background: rgba(239,68,68,0.2); color: #f87171; }
        .progress-bg { background: #1e293b; height: 8px; border-radius: 4px; overflow: hidden; margin: 10px 0; }
        .progress-bar { height: 100%; background: linear-gradient(90deg, #2563eb, #38bdf8); width: 0%; transition: width 0.3s; }
        .task-meta { display: flex; justify-content: space-between; font-size: 12px; color: #94a3b8; }
        .actions { display: flex; gap: 8px; margin-top: 12px; }
        .btn-sm { background: #1e293b; border: 1px solid #334155; color: #cbd5e1; border-radius: 6px; padding: 6px 14px; font-size: 11px; cursor: pointer; font-weight: 600; }
        .btn-sm:hover { background: #334155; color: #fff; }
        .btn-del { color: #f87171; border-color: rgba(239,68,68,0.3); }
        .btn-del:hover { background: rgba(239,68,68,0.2); color: #fca5a5; }
    </style>
</head>
<body>
<div class="header">
  <div class="logo">⚡ FalconDM Web Remote</div>
  <div class="status-pill">● Online & Syncing</div>
</div>
<div class="container">
  <div class="add-box">
    <input type="text" id="newUrl" class="add-input" placeholder="Paste download URL (HTTP/HTTPS/Magnet)...">
    <button class="add-btn" onclick="addUrl()">+ Add Download</button>
  </div>
  <div id="taskList"></div>
</div>
<script>
async function refreshTasks() {
  try {
    const res = await fetch('/api/tasks');
    const tasks = await res.json();
    const list = document.getElementById('taskList');
    if (!tasks || tasks.length === 0) {
      list.innerHTML = '<div class="card" style="text-align:center; color:#64748b; padding:40px;">No active downloads. Add a URL above to start!</div>';
      return;
    }
    list.innerHTML = tasks.map(t => `
      <div class="card">
        <div class="task-header">
          <div class="task-title" title="${t.filename}">${t.filename}</div>
          <span class="badge badge-${t.status}">${t.status.toUpperCase()}</span>
        </div>
        <div class="progress-bg"><div class="progress-bar" style="width: ${t.progress.toFixed(1)}%"></div></div>
        <div class="task-meta">
          <span>${(t.downloaded / 1048576).toFixed(1)} MB / ${(t.size / 1048576).toFixed(1)} MB (${t.progress.toFixed(1)}%)</span>
          <span>⚡ ${(t.speed / 1048576).toFixed(2)} MB/s</span>
        </div>
        <div class="actions">
          ${t.status === 'downloading' ? `<button class="btn-sm" onclick="pauseTask('${t.id}')">⏸ Pause</button>` : `<button class="btn-sm" onclick="resumeTask('${t.id}')">▶ Resume</button>`}
          <button class="btn-sm btn-del" onclick="deleteTask('${t.id}')">🗑 Delete</button>
        </div>
      </div>
    `).join('');
  } catch(e) {}
}
async function addUrl() {
  const input = document.getElementById('newUrl');
  const u = input.value.trim();
  if(!u) return;
  await fetch('/api/add', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({url: u})});
  input.value = '';
  refreshTasks();
}
async function pauseTask(id) { await fetch('/api/pause', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id})}); refreshTasks(); }
async function resumeTask(id) { await fetch('/api/resume', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id})}); refreshTasks(); }
async function deleteTask(id) { if(confirm('Delete download?')) { await fetch('/api/delete', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id})}); refreshTasks(); } }
setInterval(refreshTasks, 1000);
refreshTasks();
</script>
</body>
</html>
"""

class BridgeRequestHandler(BaseHTTPRequestHandler):
    on_browser_download: Any = None
    download_manager: Any = None
    on_focus_window: Any = None

    def do_OPTIONS(self):
        # Allow cross-origin requests from any browser tab / extension with Private Network Access
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS, PUT, DELETE')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Access-Control-Allow-Private-Network', 'true')
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ('/', '/index.html'):
            ua = self.headers.get('User-Agent', '').lower()
            if 'mobile' in ua or 'android' in ua or 'iphone' in ua:
                body = HTML_WEB_REMOTE.encode('utf-8')
            else:
                body = HTML_DASHBOARD.encode('utf-8')
            self._send_html(body)

        elif path in ('/remote', '/dashboard'):
            # Serve modern responsive mobile web remote
            body = HTML_WEB_REMOTE.encode('utf-8')
            self._send_html(body)

        elif path == '/api/tasks':
            # Return live task status in JSON
            tasks_data = []
            if BridgeRequestHandler.download_manager:
                for t in BridgeRequestHandler.download_manager.tasks.values():
                    size = t.file_size or 1
                    prog = (t.downloaded_bytes / max(1, size)) * 100
                    tasks_data.append({
                        "id": t.task_id,
                        "filename": t.filename,
                        "status": t.status,
                        "size": t.file_size,
                        "downloaded": t.downloaded_bytes,
                        "speed": t.speed_bps,
                        "progress": min(100.0, max(0.0, prog)),
                        "eta": t.eta_seconds,
                        "url": t.url
                    })
            self._send_json(200, tasks_data)

        elif path in ('/falcon_browser_extension.user.js', '/extension.user.js'):
            # Serve the userscript file so Tampermonkey / Violentmonkey automatically opens install dialog
            script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "falcon_browser_extension.user.js"))
            if os.path.isfile(script_path):
                with open(script_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/javascript; charset=utf-8')
                self.send_header('Content-Length', str(len(content)))
                self.send_header('Connection', 'close')
                self.send_header('Content-Disposition', 'inline; filename="falcon_browser_extension.user.js"')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(content)
            else:
                self._send_json(404, {"error": "Userscript file not found on disk"})

        elif path in ('/falcondm.xpi', '/extension.xpi', '/falcondm.zip', '/extension.zip'):
            import io
            import zipfile
            ext_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "browser_extension"))
            if os.path.isdir(ext_dir):
                buffer = io.BytesIO()
                with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for root, _, files in os.walk(ext_dir):
                        for f in files:
                            full_path = os.path.join(root, f)
                            rel_path = os.path.relpath(full_path, ext_dir)
                            zf.write(full_path, rel_path)
                content = buffer.getvalue()
                is_xpi = path.endswith('.xpi')
                filename = "falcondm.xpi" if is_xpi else "falcondm_extension.zip"
                mime = "application/x-xpinstall" if is_xpi else "application/zip"
                self.send_response(200)
                self.send_header('Content-Type', mime)
                self.send_header('Content-Length', str(len(content)))
                self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(content)
            else:
                self._send_json(404, {"error": "Extension directory not found"})

        elif path in ('/ping', '/status', '/api/status', '/health', '/api/health', '/check', '/api/ping'):
            self._send_json(200, {
                "status": "ok",
                "app": "FalconDM",
                "name": "FalconDM",
                "version": "2.0.0",
                "connected": True,
                "is_running": True
            })

        elif path in ('/queues', '/api/queues'):
            self._send_json(200, [
                {"id": 1, "name": "Default", "status": "idle"}
            ])

        elif path in ('/settings', '/api/settings'):
            self._send_json(200, {
                "integrationPort": 15151,
                "enabled": True
            })

        elif path in ('/focus', '/api/focus'):
            if BridgeRequestHandler.on_focus_window:
                BridgeRequestHandler.on_focus_window()
            self._send_json(200, {"success": True, "message": "FalconDM window focused"})

        elif path == '/download':
            qs = urllib.parse.parse_qs(parsed.query)
            url = qs.get('url', [''])[0]
            if url and BridgeRequestHandler.on_browser_download:
                BridgeRequestHandler.on_browser_download({"url": url})
                self._send_json(200, {"success": True, "message": "Enqueued in FalconDM"})
            else:
                self._send_json(400, {"error": "Missing url parameter"})

        elif path in ('/flashgot', '/flashgot/', '/flash', '/flash/'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(b"JDownloader\r\n")

        elif path in ('/jdcheck.js', '/flash/jdcheck.js'):
            self.send_response(200)
            self.send_header('Content-Type', 'application/javascript; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(b"jdownloader=true; var version='9.581';\r\n")

        elif path == '/crossdomain.xml':
            self.send_response(200)
            self.send_header('Content-Type', 'text/xml; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(b'<?xml version="1.0"?><cross-domain-policy><allow-access-from domain="*" /></cross-domain-policy>')

        elif path in ('/jsonrpc', '/rpc'):
            qs = urllib.parse.parse_qs(parsed.query)
            params_b64 = qs.get('params', [''])[0]
            if params_b64:
                try:
                    import base64
                    decoded = base64.b64decode(params_b64).decode('utf-8')
                    rpc_req = json.loads(decoded)
                    self._handle_aria2_jsonrpc(rpc_req)
                    return
                except Exception:
                    pass
            self._send_json(200, {"jsonrpc": "2.0", "result": "FalconDM aria2 RPC Active"})

        else:
            self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length) if length > 0 else b'{}'
        try:
            raw_str = body.decode('utf-8', errors='ignore') if body else '{}'
            data = json.loads(raw_str)
        except Exception:
            data = {}

        clean_path = self.path.split('?')[0].rstrip('/')

        # 0a. JDownloader & pyLoad Click'n'Load v2 Handlers
        if clean_path in ('/flash/addcrypted2', '/flash/add', '/flashgot', '/flashgot/'):
            self._handle_clicknload(body)
            return

        # 0b. aria2 & Motrix universal JSON-RPC Bridge
        elif clean_path in ('/jsonrpc', '/rpc'):
            self._handle_aria2_jsonrpc(data)
            return

        # 1. Connectivity & health checks (AB DM extension calls POST /ping with body null)
        if clean_path in ('/ping', '/api/ping', '/status', '/api/status', '/health', '/api/health', '/check'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', '*')
            self.send_header('Access-Control-Allow-Private-Network', 'true')
            self.end_headers()
            self.wfile.write(b"pong")
            return

        elif clean_path in ('/queues', '/api/queues'):
            self._send_json(200, [
                {"id": 1, "name": "Default", "status": "idle"}
            ])
            return

        elif clean_path in ('/settings', '/api/settings'):
            self._send_json(200, {
                "integrationPort": 15151,
                "enabled": True
            })
            return

        elif clean_path in ('/download', '/api/add', '/add', '/add-download-task', '/start-headless-download'):
            def _extract_download_items(payload_data: Any) -> list:
                extracted = []
                if isinstance(payload_data, list):
                    for elem in payload_data:
                        extracted.extend(_extract_download_items(elem))
                elif isinstance(payload_data, dict):
                    # AB Download Manager Extension schema: {"items": [{link, headers, suggestedName, ...}], "options": {...}}
                    if "items" in payload_data and isinstance(payload_data["items"], list):
                        for sub in payload_data["items"]:
                            extracted.extend(_extract_download_items(sub))
                    # AB Download Manager Headless schema: {"downloadSource": {"link": ...}, "name": ...}
                    elif "downloadSource" in payload_data and isinstance(payload_data["downloadSource"], dict):
                        src = payload_data["downloadSource"]
                        url = src.get("link") or src.get("url") or ""
                        fn = payload_data.get("name") or src.get("name") or src.get("suggestedName") or ""
                        hdrs = src.get("headers") or payload_data.get("headers") or {}
                        extracted.append({
                            "url": url,
                            "filename": fn,
                            "headers": hdrs,
                            "file_size": payload_data.get("file_size") or payload_data.get("size", 0),
                            "format_id": payload_data.get("format_id", "")
                        })
                    # Standard or Direct schema: {"url": "...", "filename": "..."}
                    else:
                        url = payload_data.get("url") or payload_data.get("link") or payload_data.get("href") or ""
                        fn = (payload_data.get("filename") or payload_data.get("name") or 
                              payload_data.get("title") or payload_data.get("suggestedName") or "")
                        hdrs = payload_data.get("headers") or {}
                        extracted.append({
                            "url": url,
                            "filename": fn,
                            "headers": hdrs,
                            "file_size": payload_data.get("file_size") or payload_data.get("size", 0),
                            "format_id": payload_data.get("format_id", "")
                        })
                elif isinstance(payload_data, str) and payload_data.strip().startswith(("http://", "https://", "magnet:", "ftp://")):
                    extracted.append({
                        "url": payload_data.strip(),
                        "filename": "",
                        "headers": {},
                        "file_size": 0,
                        "format_id": ""
                    })
                return extracted

            items = _extract_download_items(data)
            processed_any = False
            for item in items:
                url = item.get("url", "")
                filename = item.get("filename", "")
                headers = item.get("headers", {})
                if url and BridgeRequestHandler.on_browser_download:
                    processed_any = True
                    safe_print(f"[FalconDM Bridge] Intercepted download: {filename or url}")
                    payload = {
                        "url": url,
                        "filename": filename,
                        "headers": headers,
                        "file_size": item.get("file_size", 0),
                        "format_id": item.get("format_id", "")
                    }
                    try:
                        BridgeRequestHandler.on_browser_download(payload)
                    except Exception as e:
                        safe_print(f"[FalconDM Bridge] Error in on_browser_download: {e}")

            if processed_any:
                if clean_path in ('/add', '/start-headless-download', '/add-download-task'):
                    # AB Download Manager plain text compatibility
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/plain; charset=utf-8')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
                    self.send_header('Access-Control-Allow-Headers', '*')
                    self.send_header('Access-Control-Allow-Private-Network', 'true')
                    self.end_headers()
                    self.wfile.write(b"OK")
                else:
                    # FalconDM extension, userscript, and web remote JSON compatibility
                    self._send_json(200, {"status": "ok", "success": True, "message": "Download received by FalconDM"})
            else:
                self._send_json(400, {"error": "Invalid payload, 'url' or 'downloadSource.link' required"})

        elif self.path in ('/focus', '/api/focus'):
            if BridgeRequestHandler.on_focus_window:
                BridgeRequestHandler.on_focus_window()
            self._send_json(200, {"success": True, "message": "FalconDM window focused"})

        elif self.path == '/api/pause':
            tid = data.get('id')
            if tid and BridgeRequestHandler.download_manager:
                BridgeRequestHandler.download_manager.pause_task(tid)
                self._send_json(200, {"success": True})
            else:
                self._send_json(400, {"error": "Missing id"})

        elif self.path == '/api/resume':
            tid = data.get('id')
            if tid and BridgeRequestHandler.download_manager:
                BridgeRequestHandler.download_manager.resume_task(tid)
                self._send_json(200, {"success": True})
            else:
                self._send_json(400, {"error": "Missing id"})

        elif self.path == '/api/delete':
            tid = data.get('id')
            if tid and BridgeRequestHandler.download_manager:
                BridgeRequestHandler.download_manager.delete_task(tid, delete_file=False)
                self._send_json(200, {"success": True})
            else:
                self._send_json(400, {"error": "Missing id"})

        elif self.path == '/open-folder':
            from core.platform_utils import open_file_or_folder
            ext_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "browser_extension"))
            open_file_or_folder(ext_dir)
            self._send_json(200, {"success": True})

        elif self.path in ('/api/install-extension', '/install-extension'):
            from core.platform_utils import register_browser_integration
            bname = data.get('browser', 'chrome')
            ok = register_browser_integration()
            BridgeRequestHandler.launch_browser_extensions(bname)
            ext_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "browser_extension"))
            self._send_json(200, {
                "success": ok,
                "browser": bname,
                "extension_path": ext_dir,
                "message": "Native host registered, path copied to clipboard, browser opened!"
            })

        elif self.path == '/launch-browser':
            bname = data.get('browser', 'chrome')
            BridgeRequestHandler.launch_browser_extensions(bname)
            self._send_json(200, {"success": True, "browser": bname})

        else:
            self._send_json(404, {"error": "Endpoint not found"})

    def _handle_clicknload(self, body: bytes):
        """Processes JDownloader / pyLoad Click'n'Load v2 encrypted payload with AES-128-CBC."""
        import base64
        import re
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend

        raw_text = body.decode('utf-8', errors='ignore')
        form_data = urllib.parse.parse_qs(raw_text)

        crypted = form_data.get('crypted', [''])[0]
        jk = form_data.get('jk', [''])[0]
        passwords = form_data.get('passwords', [''])[0]
        package_name = form_data.get('package', [''])[0]

        urls = []
        if crypted and jk:
            try:
                m = re.search(r"['\"]([a-fA-F0-9]{32})['\"]", jk)
                key_hex = m.group(1) if m else jk.strip()
                if len(key_hex) == 32:
                    key = bytes.fromhex(key_hex)
                    raw_cipher = base64.b64decode(crypted)
                    decryptor = Cipher(algorithms.AES(key), modes.CBC(key), backend=default_backend()).decryptor()
                    decrypted = decryptor.update(raw_cipher) + decryptor.finalize()
                    pad = decrypted[-1]
                    if 0 < pad <= 16:
                        plaintext = decrypted[:-pad].decode('utf-8', errors='ignore')
                    else:
                        plaintext = decrypted.rstrip(b'\x00').decode('utf-8', errors='ignore')
                    for line in plaintext.splitlines():
                        u = line.strip()
                        if u.startswith('http://') or u.startswith('https://') or u.startswith('magnet:'):
                            urls.append(u)
            except Exception as e:
                safe_print(f"[FalconDM Click'n'Load] Decryption error: {e}")

        if not urls:
            for val in form_data.get('urls', []) + form_data.get('url', []):
                for line in val.splitlines():
                    u = line.strip()
                    if u.startswith('http://') or u.startswith('https://') or u.startswith('magnet:'):
                        urls.append(u)

        added_count = 0
        if urls and BridgeRequestHandler.on_browser_download:
            for u in urls:
                BridgeRequestHandler.on_browser_download({
                    "url": u,
                    "filename": "",
                    "package": package_name,
                    "password": passwords
                })
                added_count += 1
            safe_print(f"[FalconDM Click'n'Load] Successfully captured {added_count} links (Package: {package_name or 'Default'})")

        self.send_response(200)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(b"success\r\n")

    def _handle_aria2_jsonrpc(self, req: dict):
        """Processes aria2 / Motrix universal JSON-RPC protocol requests."""
        import time
        req_id = req.get("id", "1")
        method = req.get("method", "")
        raw_params = req.get("params", [])

        params = []
        for p in raw_params:
            if isinstance(p, str) and p.startswith("token:"):
                continue
            params.append(p)

        mgr = BridgeRequestHandler.download_manager

        if method == "aria2.addUri":
            uris = params[0] if len(params) > 0 and isinstance(params[0], list) else []
            options = params[1] if len(params) > 1 and isinstance(params[1], dict) else {}
            if not uris:
                self._send_json(200, {"jsonrpc": "2.0", "id": req_id, "error": {"code": 1, "message": "No URI provided"}})
                return

            primary_url = uris[0]
            mirrors = uris[1:] if len(uris) > 1 else []
            filename = options.get("out", "")
            save_dir = options.get("dir", "")
            headers_list = options.get("header", [])
            headers_dict = {}
            if isinstance(headers_list, list):
                for h in headers_list:
                    if ":" in h:
                        k, v = h.split(":", 1)
                        headers_dict[k.strip()] = v.strip()

            if BridgeRequestHandler.on_browser_download:
                BridgeRequestHandler.on_browser_download({
                    "url": primary_url,
                    "filename": filename,
                    "save_dir": save_dir,
                    "headers": headers_dict,
                    "mirrors": mirrors
                })
                task_gid = f"aria2_{int(time.time()*1000)}"
                self._send_json(200, {"jsonrpc": "2.0", "id": req_id, "result": task_gid})
            elif mgr:
                task = mgr.create_task(primary_url, filename=filename, custom_dir=save_dir, headers=headers_dict)
                for m in mirrors:
                    mgr.add_task_mirror(task.task_id, m)
                self._send_json(200, {"jsonrpc": "2.0", "id": req_id, "result": task.task_id})
            else:
                self._send_json(200, {"jsonrpc": "2.0", "id": req_id, "error": {"code": 1, "message": "Engine not ready"}})
            return

        elif method == "aria2.tellStatus":
            gid = params[0] if params else ""
            task = mgr.tasks.get(gid) if mgr else None
            if not task:
                self._send_json(200, {"jsonrpc": "2.0", "id": req_id, "error": {"code": 1, "message": f"Task {gid} not found"}})
                return
            status_str = "active" if task.status == "downloading" else ("complete" if task.status == "completed" else ("paused" if task.status == "paused" else "error"))
            res = {
                "gid": task.task_id,
                "status": status_str,
                "totalLength": str(task.file_size or 0),
                "completedLength": str(task.downloaded_bytes or 0),
                "downloadSpeed": str(int(task.speed_bps or 0)),
                "uploadSpeed": "0",
                "dir": os.path.dirname(task.save_path),
                "files": [{
                    "index": "1",
                    "path": task.save_path,
                    "length": str(task.file_size or 0),
                    "completedLength": str(task.downloaded_bytes or 0),
                    "selected": "true",
                    "uris": [{"uri": task.url, "status": "used"}]
                }]
            }
            self._send_json(200, {"jsonrpc": "2.0", "id": req_id, "result": res})
            return

        elif method in ("aria2.tellActive", "aria2.tellWaiting", "aria2.tellStopped"):
            tasks = list(mgr.tasks.values()) if mgr else []
            if method == "aria2.tellActive":
                matched = [t for t in tasks if t.status == "downloading"]
            elif method == "aria2.tellWaiting":
                matched = [t for t in tasks if t.status == "queued"]
            else:
                matched = [t for t in tasks if t.status in ("completed", "paused", "error")]
            results = []
            for task in matched:
                status_str = "active" if task.status == "downloading" else ("complete" if task.status == "completed" else ("paused" if task.status == "paused" else "error"))
                results.append({
                    "gid": task.task_id,
                    "status": status_str,
                    "totalLength": str(task.file_size or 0),
                    "completedLength": str(task.downloaded_bytes or 0),
                    "downloadSpeed": str(int(task.speed_bps or 0)),
                    "files": [{"path": task.save_path, "length": str(task.file_size or 0)}]
                })
            self._send_json(200, {"jsonrpc": "2.0", "id": req_id, "result": results})
            return

        elif method == "aria2.pause":
            gid = params[0] if params else ""
            if mgr:
                mgr.pause_task(gid)
            self._send_json(200, {"jsonrpc": "2.0", "id": req_id, "result": gid})
            return

        elif method == "aria2.unpause":
            gid = params[0] if params else ""
            if mgr:
                mgr.resume_task(gid)
            self._send_json(200, {"jsonrpc": "2.0", "id": req_id, "result": gid})
            return

        elif method == "aria2.remove":
            gid = params[0] if params else ""
            if mgr:
                mgr.remove_task(gid)
            self._send_json(200, {"jsonrpc": "2.0", "id": req_id, "result": gid})
            return

        elif method == "aria2.getVersion":
            self._send_json(200, {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "version": "1.37.0-FalconDM",
                    "enabledFeatures": ["Async DNS", "BitTorrent", "Firefox3-Cookie", "GZip", "HTTPS", "MessageDigest", "Metalink", "XML-RPC"]
                }
            })
            return

        elif method == "system.listMethods":
            self._send_json(200, {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": [
                    "aria2.addUri", "aria2.tellStatus", "aria2.tellActive", "aria2.tellWaiting",
                    "aria2.tellStopped", "aria2.pause", "aria2.unpause", "aria2.remove", "aria2.getVersion"
                ]
            })
            return

        else:
            self._send_json(200, {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": "OK"
            })

    @staticmethod
    def launch_browser_extensions(browser_name: str):
        """Launches target browser directly to its extension management page."""
        import subprocess
        urls = {
            "chrome": "chrome://extensions",
            "edge": "edge://extensions",
            "brave": "brave://extensions",
            "opera": "opera://extensions",
            "firefox": "about:debugging#/runtime/this-firefox",
            "vivaldi": "vivaldi://extensions"
        }
        b_key = browser_name.lower().strip()
        target_url = urls.get(b_key, "http://127.0.0.1:9666/")
        
        commands = {
            "chrome": ["cmd", "/c", "start", "chrome", target_url],
            "edge": ["cmd", "/c", "start", "msedge", target_url],
            "brave": ["cmd", "/c", "start", "brave", target_url],
            "opera": ["cmd", "/c", "start", "opera", target_url],
            "firefox": ["cmd", "/c", "start", "firefox", target_url]
        }
        cmd = commands.get(b_key)
        try:
            if cmd:
                subprocess.Popen(cmd, shell=True)
            else:
                import webbrowser
                webbrowser.open("http://127.0.0.1:9666/")
        except Exception:
            import webbrowser
            webbrowser.open("http://127.0.0.1:9666/")

    def _send_html(self, body: bytes):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Connection', 'close')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, data: Any):
        body = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Connection', 'close')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Private-Network', 'true')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Silence standard HTTP logs
        pass


class BrowserBridge:
    """Local server allowing browser extensions and Web Remote to control FalconDM."""

    def __init__(self, port: int = 9666, on_download: Optional[Callable[[dict], None]] = None, manager: Any = None, on_focus: Optional[Callable[[], None]] = None):
        self.port = port
        self.compat_port = 15151
        self.aria2_port = 6800
        self.on_download = on_download
        self.manager = manager
        self.on_focus = on_focus
        self.server: Optional[ThreadingHTTPServer] = None
        self.compat_server: Optional[ThreadingHTTPServer] = None
        self.aria2_server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._compat_thread: Optional[threading.Thread] = None
        self._aria2_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self):
        from core.config_manager import config_store
        bind_host = '0.0.0.0' if config_store.get('allow_remote_web_access', True) else '127.0.0.1'
        BridgeRequestHandler.on_browser_download = self.on_download
        BridgeRequestHandler.download_manager = self.manager
        BridgeRequestHandler.on_focus_window = self.on_focus
        try:
            ThreadingHTTPServer.allow_reuse_address = True
            self.server = ThreadingHTTPServer((bind_host, self.port), BridgeRequestHandler)
            self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self._thread.start()
            safe_print(f"[FalconDM Bridge] Browser Integration active on {bind_host}:{self.port}")
        except Exception as e:
            safe_print(f"[FalconDM Bridge] Warning: Could not bind port {self.port}: {e}")

        self._try_bind_compat_port()
        self._try_bind_aria2_port()

    def _try_bind_aria2_port(self) -> bool:
        if self.aria2_server is not None or self._stop_event.is_set():
            return True
        try:
            ThreadingHTTPServer.allow_reuse_address = True
            self.aria2_server = ThreadingHTTPServer(('127.0.0.1', self.aria2_port), BridgeRequestHandler)
            self._aria2_thread = threading.Thread(target=self.aria2_server.serve_forever, daemon=True)
            self._aria2_thread.start()
            safe_print(f"[FalconDM Bridge] aria2 / Motrix JSON-RPC compatibility active on 127.0.0.1:{self.aria2_port}")
            return True
        except Exception as e:
            safe_print(f"[FalconDM Bridge] Notice: Port {self.aria2_port} busy or reserved ({e}). aria2 JSON-RPC accessible via :9666/jsonrpc.")
            return False

    def _try_bind_compat_port(self) -> bool:
        if self.compat_server is not None or self._stop_event.is_set():
            return True
        try:
            ThreadingHTTPServer.allow_reuse_address = True
            self.compat_server = ThreadingHTTPServer(('127.0.0.1', self.compat_port), BridgeRequestHandler)
            self._compat_thread = threading.Thread(target=self.compat_server.serve_forever, daemon=True)
            self._compat_thread.start()
            safe_print(f"[FalconDM Bridge] AB Download Manager Extension Compatibility active on 127.0.0.1:{self.compat_port}")
            return True
        except Exception as e:
            safe_print(f"[FalconDM Bridge] Notice: Port {self.compat_port} not bound ({e}). FalconDM will automatically listen on {self.compat_port} when available.")
            self._start_compat_retry_worker()
            return False

    def _start_compat_retry_worker(self):
        def retry_loop():
            import time
            while not self._stop_event.is_set() and self.compat_server is None:
                time.sleep(5)
                try:
                    ThreadingHTTPServer.allow_reuse_address = True
                    server = ThreadingHTTPServer(('127.0.0.1', self.compat_port), BridgeRequestHandler)
                    self.compat_server = server
                    self._compat_thread = threading.Thread(target=server.serve_forever, daemon=True)
                    self._compat_thread.start()
                    safe_print(f"[FalconDM Bridge] Port {self.compat_port} became available! AB Download Manager Extension Compatibility is now active.")
                    break
                except Exception:
                    continue
        t = threading.Thread(target=retry_loop, daemon=True)
        t.start()

    def stop(self):
        self._stop_event.set()
        if self.server:
            try:
                self.server.shutdown()
            except Exception:
                pass
        if self.compat_server:
            try:
                self.compat_server.shutdown()
            except Exception:
                pass
        if self.aria2_server:
            try:
                self.aria2_server.shutdown()
            except Exception:
                pass

