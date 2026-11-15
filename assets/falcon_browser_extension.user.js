// ==UserScript==
// @name         FalconDM Universal Browser Integration (Free IDM)
// @namespace    https://falcondm.local
// @version      2.0
// @description  Universal IDM-grade download interceptors and 1-Click "Download with FalconDM" on ANY website!
// @match        *://*/*
// @grant        GM_xmlhttpRequest
// @connect      127.0.0.1
// ==/UserScript==

(function() {
    'use strict';

    const FALCON_API = 'http://127.0.0.1:9666/download';

    function getPageTitle() {
        const ogTitle = document.querySelector('meta[property="og:title"]')?.content;
        const twitterTitle = document.querySelector('meta[name="twitter:title"]')?.content;
        const h1 = document.querySelector('h1')?.innerText?.trim();
        const docTitle = document.title?.trim();
        const raw = ogTitle || twitterTitle || h1 || docTitle || "";
        return raw.replace(/[\\/:*?"<>|]/g, "_").replace(/\s+/g, " ").trim().substring(0, 150);
    }

    function sendToFalcon(url, filename = '', format_id = '') {
        const title = filename || getPageTitle();
        let finalName = title;
        if (format_id && title && !title.includes('.')) {
            const ext = format_id === 'image_direct' ? '.jpg' : (format_id && format_id.includes('audio') ? '.mp3' : '.mp4');
            finalName = `${title}${ext}`;
        }
        GM_xmlhttpRequest({
            method: 'POST',
            url: FALCON_API,
            headers: {
                'Content-Type': 'application/json',
                'Referer': window.location.href
            },
            data: JSON.stringify({
                url: url,
                filename: finalName,
                format_id: format_id,
                headers: {
                    'Referer': window.location.href,
                    'Origin': window.location.origin,
                    'Cookie': document.cookie || '',
                    'User-Agent': navigator.userAgent,
                    'Sec-Ch-Ua': '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
                    'Sec-Ch-Ua-Mobile': '?0',
                    'Sec-Ch-Ua-Platform': '"Windows"',
                    'Sec-Fetch-Dest': 'empty',
                    'Sec-Fetch-Mode': 'cors',
                    'Sec-Fetch-Site': 'cross-site'
                }
            }),
            onload: function(response) {
                showToast('⚡ Sent to FalconDM Turbo Downloader!');
            },
            onerror: function(err) {
                showToast('❌ FalconDM is not running. Launch FalconDM first!');
            }
        });
    }

    function showToast(msg) {
        const existing = document.getElementById('falcondm-toast');
        if (existing) existing.remove();

        const toast = document.createElement('div');
        toast.id = 'falcondm-toast';
        toast.textContent = msg;
        toast.style.position = 'fixed';
        toast.style.bottom = '24px';
        toast.style.right = '24px';
        toast.style.backgroundColor = '#181a20';
        toast.style.color = '#38bdf8';
        toast.style.border = '1px solid #2563eb';
        toast.style.padding = '10px 18px';
        toast.style.borderRadius = '8px';
        toast.style.fontWeight = 'bold';
        toast.style.fontFamily = 'sans-serif';
        toast.style.fontSize = '13px';
        toast.style.boxShadow = '0 8px 24px rgba(0,0,0,0.6)';
        toast.style.zIndex = '2147483647';
        toast.style.pointerEvents = 'none';
        toast.style.transition = 'opacity 0.3s ease';
        document.body.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, 2800);
    }

    const DOWNLOAD_EXTS = [
        '.exe', '.msi', '.zip', '.rar', '.7z', '.tar', '.gz', '.iso', '.bz2', '.xz', '.tgz',
        '.apk', '.dmg', '.bin', '.torrent', '.deb', '.rpm', '.pkg', '.crx', '.xpi',
        '.mp4', '.mkv', '.avi', '.mov', '.flv', '.mp3', '.flac', '.wav', '.pdf', '.epub', '.csv'
    ];

    function isDownloadable(url, name) {
        if (!url || typeof url !== 'string') return false;
        const clean = url.split('?')[0].split('#')[0].toLowerCase();
        if (DOWNLOAD_EXTS.some(ext => clean.endsWith(ext))) return true;
        if (name && DOWNLOAD_EXTS.some(ext => name.toLowerCase().endsWith(ext))) return true;
        if (clean.includes('/releases/download/')) return true;
        return false;
    }

    // 1. Automatic 1-Click File Download Interception (IDM Style)
    // Clicking any downloadable file link or button routes directly to FalconDM.
    // Holding 'Alt' while clicking bypasses FalconDM (lets browser download natively).
    document.addEventListener('click', function(e) {
        const link = e.target.closest('a, [data-href], [data-url], [data-download]');
        if (!link) return;

        // Holding Alt bypasses FalconDM
        if (e.altKey) return;

        const href = link.href || link.dataset.href || link.dataset.url || link.dataset.download;
        if (!href || href.startsWith('javascript:') || href.startsWith('#')) return;

        const rawText = link.innerText?.trim() || '';
        const nameAttr = link.getAttribute('download') || '';
        const candidateName = nameAttr || rawText;

        if (link.hasAttribute('download') || isDownloadable(href, candidateName)) {
            e.preventDefault();
            e.stopPropagation();
            sendToFalcon(href, candidateName, '');
        }
    }, true);

    // 2. IDM-Style Video & Audio Player Hover Overlay (Works on ANY website)
    let currentHoveredMedia = null;
    let overlayHideTimeout = null;

    function createPlayerOverlay() {
        let overlay = document.getElementById('falcondm-video-overlay-btn');
        if (overlay) return overlay;

        overlay = document.createElement('div');
        overlay.id = 'falcondm-video-overlay-btn';
        overlay.innerHTML = `
          <div style="display:flex;align-items:center;">
            <div id="falcondm-main-dl-action" style="display:flex;align-items:center;gap:6px;padding:6px 10px;cursor:pointer;">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="7 10 12 15 17 10"></polyline>
                <line x1="12" y1="15" x2="12" y2="3"></line>
              </svg>
              <span id="falcondm-overlay-label">Download Media</span>
            </div>
            <div id="falcondm-dropdown-toggle" style="display:flex;align-items:center;justify-content:center;padding:6px 8px;border-left:1px solid rgba(255,255,255,0.25);cursor:pointer;" title="Choose Quality / Format">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="6 9 12 15 18 9"></polyline>
              </svg>
            </div>
          </div>
          <div id="falcondm-quality-menu" style="display:none;position:absolute;top:100%;right:0;margin-top:5px;background:#0f172a;border:1px solid #334155;border-radius:8px;box-shadow:0 12px 28px rgba(0,0,0,0.8);width:215px;overflow:hidden;z-index:2147483647;font-size:12px;font-weight:600;padding:4px 0;">
            <div class="falcondm-q-item" data-format="bestvideo+bestaudio/best" style="padding:8px 12px;color:#f8fafc;cursor:pointer;display:flex;align-items:center;justify-content:space-between;">
              <span>🌟 Best Available</span>
              <span style="font-size:10px;background:#2563eb;padding:2px 6px;border-radius:4px;">AUTO</span>
            </div>
            <div class="falcondm-q-item" data-format="bestvideo[height<=1080]+bestaudio/best[height<=1080]" style="padding:8px 12px;color:#f8fafc;cursor:pointer;display:flex;align-items:center;justify-content:space-between;">
              <span>🎬 1080p Full HD</span>
              <span style="font-size:10px;background:#1e293b;padding:2px 6px;border-radius:4px;color:#94a3b8;">FHD</span>
            </div>
            <div class="falcondm-q-item" data-format="bestvideo[height<=720]+bestaudio/best[height<=720]" style="padding:8px 12px;color:#f8fafc;cursor:pointer;display:flex;align-items:center;justify-content:space-between;">
              <span>🎥 720p HD</span>
              <span style="font-size:10px;background:#1e293b;padding:2px 6px;border-radius:4px;color:#94a3b8;">HD</span>
            </div>
            <div class="falcondm-q-item" data-format="bestvideo[height<=480]+bestaudio/best[height<=480]" style="padding:8px 12px;color:#f8fafc;cursor:pointer;display:flex;align-items:center;justify-content:space-between;">
              <span>📱 480p SD</span>
              <span style="font-size:10px;background:#1e293b;padding:2px 6px;border-radius:4px;color:#94a3b8;">SD</span>
            </div>
            <div class="falcondm-q-item" data-format="bestaudio/best" style="padding:8px 12px;color:#38bdf8;cursor:pointer;display:flex;align-items:center;justify-content:space-between;border-top:1px solid #1e293b;">
              <span>🎵 Extract Audio</span>
              <span style="font-size:10px;background:#0284c7;color:#fff;padding:2px 6px;border-radius:4px;">MP3</span>
            </div>
          </div>
        `;
        overlay.style.position = 'absolute';
        overlay.style.display = 'none';
        overlay.style.backgroundColor = '#2563eb';
        overlay.style.color = '#ffffff';
        overlay.style.borderRadius = '6px';
        overlay.style.fontSize = '12px';
        overlay.style.fontWeight = 'bold';
        overlay.style.fontFamily = 'system-ui, -apple-system, sans-serif';
        overlay.style.boxShadow = '0 4px 16px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.2)';
        overlay.style.zIndex = '2147483647';
        overlay.style.transition = 'background-color 0.15s ease';
        overlay.style.userSelect = 'none';

        const menu = overlay.querySelector('#falcondm-quality-menu');
        const mainDl = overlay.querySelector('#falcondm-main-dl-action');
        const toggle = overlay.querySelector('#falcondm-dropdown-toggle');

        overlay.onmouseover = () => { if (overlayHideTimeout) clearTimeout(overlayHideTimeout); };
        overlay.onmouseout = (e) => {
            if (!overlay.contains(e.relatedTarget)) scheduleOverlayHide();
        };

        mainDl.onclick = (e) => {
            e.stopPropagation();
            e.preventDefault();
            if (!currentHoveredMedia) return;
            const targetUrl = resolveMediaUrl(currentHoveredMedia);
            if (targetUrl) {
                sendToFalcon(targetUrl, '', 'prompt');
                showToast("⚡ Opening FalconDM Media Downloader...");
                menu.style.display = 'none';
            }
        };

        toggle.onclick = (e) => {
            e.stopPropagation();
            e.preventDefault();
            menu.style.display = menu.style.display === 'block' ? 'none' : 'block';
        };

        overlay.querySelectorAll('.falcondm-q-item').forEach(item => {
            item.onmouseover = () => { item.style.backgroundColor = '#1e293b'; };
            item.onmouseout = () => { item.style.backgroundColor = 'transparent'; };
            item.onclick = (e) => {
                e.stopPropagation();
                e.preventDefault();
                menu.style.display = 'none';
                if (!currentHoveredMedia) return;
                const targetUrl = resolveMediaUrl(currentHoveredMedia);
                const formatId = item.getAttribute('data-format');
                if (targetUrl) {
                    sendToFalcon(targetUrl, '', formatId);
                }
            };
        });

        document.body.appendChild(overlay);
        return overlay;
    }

    function scheduleOverlayHide() {
        if (overlayHideTimeout) clearTimeout(overlayHideTimeout);
        overlayHideTimeout = setTimeout(() => {
            const overlay = document.getElementById('falcondm-video-overlay-btn');
            if (overlay) {
                overlay.style.display = 'none';
                const menu = overlay.querySelector('#falcondm-quality-menu');
                if (menu) menu.style.display = 'none';
            }
        }, 1200);
    }

    function positionOverlay(media) {
        const overlay = createPlayerOverlay();
        const rect = media.getBoundingClientRect();
        if (media.tagName === 'VIDEO' && rect.width < 100 && rect.height < 70) return;

        const top = window.scrollY + rect.top + 10;
        const left = window.scrollX + rect.right - 185;

        const labelSpan = overlay.querySelector('#falcondm-overlay-label');
        if (labelSpan) {
            labelSpan.textContent = media.tagName === 'IMG' ? 'Download Image' : (media.tagName === 'AUDIO' ? 'Download Audio' : 'Download Video');
        }

        overlay.style.top = `${Math.max(window.scrollY + 10, top)}px`;
        overlay.style.left = `${Math.max(10, left)}px`;
        overlay.style.display = 'block';
    }

    function extractHighResImageUrl(imgEl) {
        if (!imgEl) return '';
        const candidates = [
            imgEl.getAttribute('data-zoom-image'),
            imgEl.getAttribute('data-original'),
            imgEl.getAttribute('data-full-image'),
            imgEl.getAttribute('data-src'),
            imgEl.dataset?.zoomImage,
            imgEl.dataset?.original,
            imgEl.dataset?.fullImage
        ];
        for (const c of candidates) {
            if (c && typeof c === 'string' && !c.startsWith('data:') && !c.startsWith('blob:')) {
                try { return new URL(c, window.location.href).href; } catch (e) { return c; }
            }
        }
        const src = imgEl.currentSrc || imgEl.src;
        return (src && !src.startsWith('data:') && !src.startsWith('blob:')) ? src : '';
    }

    function resolveMediaUrl(media) {
        if (!media) return window.location.href;
        if (media.tagName === 'IMG') {
            const imgUrl = extractHighResImageUrl(media);
            if (imgUrl) return imgUrl;
        }
        if (media.tagName === 'IFRAME') {
            const iframeSrc = media.src || media.dataset.src || media.getAttribute('data-src') || '';
            if (iframeSrc && !iframeSrc.startsWith('about:') && !iframeSrc.startsWith('javascript:')) {
                return iframeSrc;
            }
            return window.location.href;
        }

        const host = window.location.hostname.toLowerCase();
        const href = window.location.href;

        if (media.currentSrc && !media.currentSrc.startsWith('blob:')) return media.currentSrc;
        if (media.src && !media.src.startsWith('blob:')) return media.src;

        const sources = media.querySelectorAll('source');
        for (const s of sources) {
            const src = s.src || s.getAttribute('src') || s.dataset.src;
            if (src && !src.startsWith('blob:')) return src;
        }

        const dataSrc = media.dataset.src || media.dataset.url || media.dataset.videoUrl;
        if (dataSrc && !dataSrc.startsWith('blob:')) return dataSrc;

        const parentLink = media.closest('a[href]');
        if (parentLink && parentLink.href && !parentLink.href.startsWith('javascript:')) {
            return parentLink.href;
        }

        return href;
    }

    function findMediaUnderCursor(e) {
        if (e.target.closest('#falcondm-video-overlay-btn') || e.target.closest('#falcondm-video-btn')) return null;
        const direct = e.target.closest('video, audio');
        if (direct) return direct;

        const iframeTarget = e.target.closest('iframe');
        if (iframeTarget) {
            const src = (iframeTarget.src || '').toLowerCase();
            if (src.includes('youtube') || src.includes('vimeo') || src.includes('player') || src.includes('embed')) {
                const rect = iframeTarget.getBoundingClientRect();
                if (rect.width >= 200 && rect.height >= 120) return iframeTarget;
            }
        }

        const container = e.target.closest('.video-js, .jwplayer, .plyr, .bpx-player-container');
        if (container) {
            const inside = container.querySelector('video, audio, iframe');
            if (inside) return inside;
        }
        return null;
    }

    document.addEventListener('mouseover', (e) => {
        const media = findMediaUnderCursor(e);
        if (media) {
            if (overlayHideTimeout) clearTimeout(overlayHideTimeout);
            currentHoveredMedia = media;
            positionOverlay(media);
        }
    }, true);

    document.addEventListener('mouseout', (e) => {
        const media = findMediaUnderCursor(e);
        if (media) scheduleOverlayHide();
    }, true);

    // When a video or audio starts playing, attach overlay to that player
    window.addEventListener('play', (e) => {
        if (e.target && (e.target.tagName === 'VIDEO' || e.target.tagName === 'AUDIO')) {
            currentHoveredMedia = e.target;
            positionOverlay(e.target);
        }
    }, true);
})();
