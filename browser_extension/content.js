// FalconDM Browser Integration - Content Script (IDM-Style Media Grabber)
// Compatible with: Google Chrome, Microsoft Edge, Mozilla Firefox, Brave, Opera, Vivaldi, Arc
const browserAPI = (typeof browser !== "undefined" && browser.runtime) ? browser : chrome;

// Smart Video Title & Metadata Extractor
function getPageTitle() {
  return extractSmartMediaTitle(null);
}

function extractSmartMediaTitle(media) {
  const host = window.location.hostname.toLowerCase();
  let candidate = "";

  // 1. Facebook Reels & Videos
  if (host.includes("facebook.com") || host.includes("fb.watch")) {
    const postContainer = media ? media.closest('div[role="feed"] > div, div[data-pagelet*="Reel"], div[data-pagelet*="Feed"], div[role="main"], div[role="article"]') : null;
    const captionEl = (postContainer || document).querySelector('div[data-ad-preview="message"], div[dir="auto"][style*="text-align"], span[dir="auto"], h2, strong');
    if (captionEl && captionEl.innerText && captionEl.innerText.trim().length > 3) {
      candidate = captionEl.innerText.trim().split("\n")[0];
    }
  }

  // 2. YouTube
  if (host.includes("youtube.com") || host.includes("youtu.be")) {
    const ytTitle = document.querySelector("h1.ytd-watch-metadata, #title h1, h1.title, #video-title")?.innerText?.trim();
    if (ytTitle) candidate = ytTitle;
  }

  // 3. TikTok
  if (host.includes("tiktok.com")) {
    const ttTitle = document.querySelector('[data-e2e="browse-video-desc"], h1, [data-e2e="user-post-item-desc"]')?.innerText?.trim();
    if (ttTitle) candidate = ttTitle;
  }

  // 4. Twitter / X
  if (host.includes("twitter.com") || host.includes("x.com")) {
    const tweetEl = media ? media.closest('article')?.querySelector('div[data-testid="tweetText"]') : null;
    if (tweetEl && tweetEl.innerText) candidate = tweetEl.innerText.trim().split("\n")[0];
  }

  // 5. Reddit
  if (host.includes("reddit.com")) {
    const rTitle = document.querySelector('h1[slot="title"], h1, [data-testid="post-title"]')?.innerText?.trim();
    if (rTitle) candidate = rTitle;
  }

  // Fallback to OpenGraph / Twitter cards / Heading / Page Title
  if (!candidate || candidate.toLowerCase() === "facebook" || candidate.length < 3) {
    const ogTitle = document.querySelector('meta[property="og:title"]')?.content;
    const twitterTitle = document.querySelector('meta[name="twitter:title"]')?.content;
    const h1 = document.querySelector('h1')?.innerText?.trim();
    let docTitle = document.title?.trim() || "";
    docTitle = docTitle.replace(/ - YouTube$/i, "").replace(/ \| Facebook$/i, "").replace(/ \/ X$/i, "").replace(/^Watch\s*\|\s*/i, "");
    candidate = ogTitle || twitterTitle || h1 || docTitle || "";
  }

  const clean = candidate.replace(/[\\/:*?"<>|\r\n\t]/g, "_").replace(/\s+/g, " ").trim();
  if (clean.toLowerCase() === "facebook" || clean.toLowerCase() === "instagram" || clean.toLowerCase() === "video" || clean.toLowerCase() === "reel") {
    return "";
  }
  return clean.substring(0, 100);
}

let lastDetectedNetworkStream = "";

// Cross-frame media communication (for iframe video players on anime & streaming sites like Anikoto, Zoro, RapidCloud)
window.addEventListener("message", (e) => {
  if (e && e.data && e.data.type === "FALCONDM_IFRAME_MEDIA" && e.data.url) {
    lastDetectedNetworkStream = e.data.url;
  }
});

function broadcastToParent(mediaUrl) {
  if (window.self !== window.top && mediaUrl) {
    try {
      window.parent.postMessage({
        type: "FALCONDM_IFRAME_MEDIA",
        url: mediaUrl,
        title: getPageTitle()
      }, "*");
    } catch (e) {}
  }
}

const DOWNLOAD_EXTS = [
  ".exe", ".msi", ".zip", ".rar", ".7z", ".tar", ".gz", ".iso", ".bz2", ".xz", ".tgz",
  ".apk", ".dmg", ".bin", ".torrent", ".deb", ".rpm", ".pkg", ".crx", ".xpi",
  ".mp4", ".mkv", ".avi", ".mov", ".flv", ".mp3", ".flac", ".wav", ".pdf", ".epub", ".csv"
];

function isDownloadable(url, name) {
  if (!url || typeof url !== "string") return false;
  const clean = url.split("?")[0].split("#")[0].toLowerCase();
  if (DOWNLOAD_EXTS.some(ext => clean.endsWith(ext))) return true;
  if (name && DOWNLOAD_EXTS.some(ext => name.toLowerCase().endsWith(ext))) return true;
  if (clean.includes("/releases/download/")) return true;
  return false;
}

// 1. Automatic 1-Click File Download Interception (IDM Style)
// Clicking any downloadable file link or button routes directly to FalconDM.
// Holding 'Alt' while clicking bypasses FalconDM (lets browser download natively).
document.addEventListener("click", function (e) {
  const link = e.target.closest("a, [data-href], [data-url], [data-download]");
  if (!link) return;

  // Holding Alt bypasses FalconDM
  if (e.altKey) return;

  const href = link.href || link.dataset.href || link.dataset.url || link.dataset.download;
  if (!href || href.startsWith("javascript:") || href.startsWith("#")) return;

  const rawText = link.innerText?.trim() || "";
  const nameAttr = link.getAttribute("download") || "";
  const candidateName = nameAttr || rawText;

  if (link.hasAttribute("download") || isDownloadable(href, candidateName)) {
    e.preventDefault();
    e.stopPropagation();
    browserAPI.runtime.sendMessage({
      action: "download",
      url: href,
      filename: candidateName,
      format_id: ""
    });
    showToast("⚡ Downloading with FalconDM...");
  }
}, true);

// 2. IDM-Style Video & Audio Player Hover Overlay
let currentHoveredMedia = null;
let overlayHideTimeout = null;

function renderQualityMenuForMedia(media) {
  const overlay = createPlayerOverlay();
  const menu = overlay.querySelector("#falcondm-quality-menu");
  if (!menu) return;

  const isAudio = media && media.tagName === "AUDIO";

  if (isAudio) {
    menu.innerHTML = `
      <div style="padding:6px 12px;border-bottom:1px solid rgba(255,255,255,0.08);font-size:10px;font-weight:800;color:#94a3b8;letter-spacing:0.5px;text-transform:uppercase;">Audio Download Options</div>
      <div class="falcondm-q-item" data-format="bestaudio/best" style="padding:8px 12px;color:#f8fafc;cursor:pointer;display:flex;align-items:center;justify-content:space-between;">
        <span>🎵 Extract / Download MP3</span>
        <span style="font-size:10px;background:#0284c7;color:#fff;padding:2px 6px;border-radius:4px;font-weight:700;">MP3</span>
      </div>
      <div class="falcondm-q-item" data-format="direct" style="padding:8px 12px;color:#38bdf8;cursor:pointer;display:flex;align-items:center;justify-content:space-between;">
        <span>🌟 Direct Audio Stream</span>
        <span style="font-size:10px;background:#1e293b;color:#38bdf8;padding:2px 6px;border-radius:4px;">DIRECT</span>
      </div>
    `;
  } else {
    menu.innerHTML = `
      <div style="padding:6px 12px;border-bottom:1px solid rgba(255,255,255,0.08);font-size:10px;font-weight:800;color:#94a3b8;letter-spacing:0.5px;text-transform:uppercase;">Select Download Format</div>
      <div class="falcondm-q-item" data-format="bestvideo+bestaudio/best" style="padding:8px 12px;color:#f8fafc;cursor:pointer;display:flex;align-items:center;justify-content:space-between;">
        <span>🌟 Best Available Quality</span>
        <span style="font-size:10px;background:#2563eb;color:#fff;padding:2px 6px;border-radius:4px;font-weight:700;">AUTO</span>
      </div>
      <div class="falcondm-q-item" data-format="bestvideo[height<=1080]+bestaudio/best[height<=1080]" style="padding:8px 12px;color:#f8fafc;cursor:pointer;display:flex;align-items:center;justify-content:space-between;">
        <span>🎬 1080p Full HD</span>
        <span style="font-size:10px;background:#1e293b;color:#38bdf8;padding:2px 6px;border-radius:4px;border:1px solid #334155;">FHD</span>
      </div>
      <div class="falcondm-q-item" data-format="bestvideo[height<=720]+bestaudio/best[height<=720]" style="padding:8px 12px;color:#f8fafc;cursor:pointer;display:flex;align-items:center;justify-content:space-between;">
        <span>🎥 720p HD</span>
        <span style="font-size:10px;background:#1e293b;color:#94a3b8;padding:2px 6px;border-radius:4px;">HD</span>
      </div>
      <div class="falcondm-q-item" data-format="bestvideo[height<=480]+bestaudio/best[height<=480]" style="padding:8px 12px;color:#f8fafc;cursor:pointer;display:flex;align-items:center;justify-content:space-between;">
        <span>📱 480p SD</span>
        <span style="font-size:10px;background:#1e293b;color:#94a3b8;padding:2px 6px;border-radius:4px;">SD</span>
      </div>
      <div class="falcondm-q-item" data-format="bestaudio/best" style="padding:8px 12px;color:#38bdf8;cursor:pointer;display:flex;align-items:center;justify-content:space-between;border-top:1px solid rgba(255,255,255,0.08);">
        <span>🎵 Extract Audio (MP3)</span>
        <span style="font-size:10px;background:#0284c7;color:#fff;padding:2px 6px;border-radius:4px;">MP3</span>
      </div>
      <div class="falcondm-q-item" data-format="prompt" style="padding:8px 12px;color:#94a3b8;cursor:pointer;display:flex;align-items:center;justify-content:space-between;border-top:1px solid rgba(255,255,255,0.08);font-size:11px;">
        <span>⚙️ More Formats / Options...</span>
        <span style="font-size:9px;background:#1e293b;color:#94a3b8;padding:2px 5px;border-radius:4px;">PROMPT</span>
      </div>
    `;
  }

  menu.querySelectorAll(".falcondm-q-item").forEach(item => {
    item.onmouseover = () => { item.style.backgroundColor = "rgba(30,41,59,0.85)"; };
    item.onmouseout = () => { item.style.backgroundColor = "transparent"; };
    item.onclick = (e) => {
      e.stopPropagation();
      e.preventDefault();
      menu.style.display = "none";
      if (!currentHoveredMedia) return;
      const targetUrl = resolveMediaUrl(currentHoveredMedia);
      const formatId = item.getAttribute("data-format");
      const smartTitle = extractSmartMediaTitle(currentHoveredMedia);
      const isAudioOnly = formatId === "bestaudio" || formatId === "bestaudio/best" || isAudio;
      const ext = isAudioOnly ? ".mp3" : ".mp4";
      const filename = smartTitle ? `${smartTitle}${ext}` : "";

      if (targetUrl) {
        browserAPI.runtime.sendMessage({
          action: "download",
          url: targetUrl,
          filename: filename,
          format_id: formatId
        });
        const label = item.querySelector("span")?.textContent || "Media";
        showToast(formatId === "prompt" ? "⚡ Opening FalconDM Media Downloader..." : `⚡ Downloading (${label}): ${smartTitle || "Media"}...`);
      } else {
        showToast("❌ Could not resolve media URL.");
      }
    };
  });
}

function createPlayerOverlay() {
  let overlay = document.getElementById("falcondm-video-overlay-btn");
  if (overlay) return overlay;

  overlay = document.createElement("div");
  overlay.id = "falcondm-video-overlay-btn";
  overlay.innerHTML = `
    <div style="display:flex;align-items:center;">
      <div id="falcondm-main-dl-action" style="display:flex;align-items:center;gap:6px;padding:6px 11px;cursor:pointer;" title="Click to download media instantly">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="fill:none !important;stroke:#ffffff !important;">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
          <polyline points="7 10 12 15 17 10"></polyline>
          <line x1="12" y1="15" x2="12" y2="3"></line>
        </svg>
        <span id="falcondm-overlay-label" style="color:#ffffff !important;font-weight:700 !important;">Download Video</span>
      </div>
      <div id="falcondm-dropdown-toggle" style="display:flex;align-items:center;justify-content:center;padding:6px 9px;border-left:1px solid rgba(255,255,255,0.25);cursor:pointer;" title="Choose Quality / Format">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" style="fill:none !important;stroke:#ffffff !important;">
          <polyline points="6 9 12 15 18 9"></polyline>
        </svg>
      </div>
    </div>
    <div id="falcondm-quality-menu" style="display:none;position:absolute;top:calc(100% + 6px);right:0;background:rgba(15,23,42,0.96);backdrop-filter:blur(16px);border:1px solid rgba(56,189,248,0.3);border-radius:10px;box-shadow:0 14px 32px rgba(0,0,0,0.85);width:235px;overflow:hidden;z-index:2147483647 !important;font-size:12px;font-weight:600;padding:4px 0;font-family:system-ui,-apple-system,sans-serif;"></div>
  `;
  overlay.style.position = "fixed";
  overlay.style.display = "none";
  overlay.style.backgroundColor = "#2563eb";
  overlay.style.color = "#ffffff";
  overlay.style.borderRadius = "8px";
  overlay.style.fontSize = "12px";
  overlay.style.fontWeight = "bold";
  overlay.style.fontFamily = "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
  overlay.style.boxShadow = "0 4px 20px rgba(0,0,0,0.65), 0 0 0 1px rgba(255,255,255,0.2)";
  overlay.style.zIndex = "2147483647";
  overlay.style.transition = "background-color 0.15s ease";
  overlay.style.userSelect = "none";

  const menu = overlay.querySelector("#falcondm-quality-menu");
  const mainDl = overlay.querySelector("#falcondm-main-dl-action");
  const toggle = overlay.querySelector("#falcondm-dropdown-toggle");

  overlay.onmouseover = () => {
    if (overlayHideTimeout) clearTimeout(overlayHideTimeout);
  };

  overlay.onmouseout = (e) => {
    if (!overlay.contains(e.relatedTarget)) {
      scheduleOverlayHide();
    }
  };

  const toggleMenu = (e) => {
    if (e) {
      e.stopPropagation();
      e.preventDefault();
    }
    menu.style.display = menu.style.display === "block" ? "none" : "block";
  };

  mainDl.onclick = (e) => {
    e.stopPropagation();
    e.preventDefault();
    if (!currentHoveredMedia) return;
    const targetUrl = resolveMediaUrl(currentHoveredMedia);
    const isAudioOnly = currentHoveredMedia.tagName === "AUDIO";
    const smartTitle = extractSmartMediaTitle(currentHoveredMedia);
    const ext = isAudioOnly ? ".mp3" : ".mp4";
    const filename = smartTitle ? `${smartTitle}${ext}` : "";
    const formatId = isAudioOnly ? "bestaudio/best" : "bestvideo+bestaudio/best";

    if (targetUrl) {
      browserAPI.runtime.sendMessage({
        action: "download",
        url: targetUrl,
        filename: filename,
        format_id: formatId
      });
      showToast(`⚡ Downloading with FalconDM: ${smartTitle || "Media Video"}...`);
    } else {
      showToast("❌ Could not resolve video URL.");
    }
  };

  toggle.onclick = toggleMenu;
  document.body.appendChild(overlay);
  return overlay;
}

function positionOverlay(media) {
  if (!media) return;
  const overlay = createPlayerOverlay();
  const rect = media.getBoundingClientRect();
  if (rect.width < 100 || rect.height < 60) return;

  const labelSpan = overlay.querySelector("#falcondm-overlay-label");
  if (labelSpan) {
    labelSpan.textContent = media.tagName === "AUDIO" ? "Download Audio" : "Download Video";
  }

  renderQualityMenuForMedia(media);

  const top = Math.max(10, rect.top + 10);
  const right = Math.max(10, window.innerWidth - rect.right + 10);

  overlay.style.top = `${top}px`;
  overlay.style.right = `${right}px`;
  overlay.style.display = "block";
}

function scheduleOverlayHide() {
  if (overlayHideTimeout) clearTimeout(overlayHideTimeout);
  overlayHideTimeout = setTimeout(() => {
    const overlay = document.getElementById("falcondm-video-overlay-btn");
    if (overlay) {
      const menu = overlay.querySelector("#falcondm-quality-menu");
      if (menu && menu.style.display === "block") return;
      overlay.style.display = "none";
    }
  }, 1200);
}

function resolveMediaUrl(media) {
  if (!media) return window.location.href;
  const href = window.location.href;

  if (href.includes("youtube.com/watch") || href.includes("youtu.be/")) {
    return href;
  }
  if (href.includes("facebook.com") || href.includes("fb.watch")) {
    return href;
  }

  let src = media.currentSrc || media.src;
  if (!src) {
    const source = media.querySelector("source");
    if (source) src = source.src;
  }
  if (src && !src.startsWith("blob:") && !src.startsWith("data:")) {
    return src;
  }

  if (lastDetectedNetworkStream) {
    return lastDetectedNetworkStream;
  }

  return href;
}

// Find video or audio element under cursor
function findMediaUnderCursor(e) {
  if (e.target.closest("#falcondm-video-overlay-btn")) return null;

  const direct = e.target.closest("video, audio");
  if (direct) return direct;

  const iframeTarget = e.target.closest("iframe");
  if (iframeTarget) {
    const src = (iframeTarget.src || "").toLowerCase();
    if (src.includes("youtube") || src.includes("vimeo") || src.includes("player") || src.includes("embed")) {
      const rect = iframeTarget.getBoundingClientRect();
      if (rect.width >= 200 && rect.height >= 120) return iframeTarget;
    }
  }

  const container = e.target.closest('.bpx-player-container, .bpx-player-video-wrap, .video-js, .jwplayer, .plyr, .dplayer, .artplayer');
  if (container) {
    const inside = container.querySelector("video, audio, iframe");
    if (inside) return inside;
  }

  return null;
}

// 1. Mouse hover over any video player attaches the IDM download button
document.addEventListener("mouseover", (e) => {
  const media = findMediaUnderCursor(e);
  if (media) {
    if (overlayHideTimeout) clearTimeout(overlayHideTimeout);
    currentHoveredMedia = media;
    positionOverlay(media);
  }
}, true);

document.addEventListener("mouseout", (e) => {
  const media = findMediaUnderCursor(e);
  if (media) {
    scheduleOverlayHide();
  }
}, true);

// 2. When a video starts playing, immediately attach the download button to it
window.addEventListener("play", (e) => {
  if (e.target && (e.target.tagName === "VIDEO" || e.target.tagName === "AUDIO")) {
    currentHoveredMedia = e.target;
    positionOverlay(e.target);
  }
}, true);

// Clean toast notification
function showToast(msg) {
  const existing = document.getElementById("falcondm-toast");
  if (existing) existing.remove();

  const toast = document.createElement("div");
  toast.id = "falcondm-toast";
  toast.textContent = msg;
  toast.style.position = "fixed";
  toast.style.bottom = "24px";
  toast.style.right = "24px";
  toast.style.backgroundColor = "#0f172a";
  toast.style.color = "#38bdf8";
  toast.style.border = "1px solid #2563eb";
  toast.style.padding = "10px 18px";
  toast.style.borderRadius = "8px";
  toast.style.fontWeight = "bold";
  toast.style.fontFamily = "sans-serif";
  toast.style.fontSize = "13px";
  toast.style.boxShadow = "0 8px 24px rgba(0,0,0,0.6)";
  toast.style.zIndex = "2147483647";
  toast.style.pointerEvents = "none";
  toast.style.transition = "opacity 0.3s ease";
  document.body.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 300);
  }, 2800);
}

// Respond to extension popup queries with active media elements only (zero page crawling)
browserAPI.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "showToast") {
    showToast(request.message);
  } else if (request.action === "getMediaList") {
    const list = [];
    document.querySelectorAll("video, audio").forEach((el, idx) => {
      const src = resolveMediaUrl(el);
      if (src && !src.startsWith("blob:")) {
        list.push({
          url: src,
          type: el.tagName.toLowerCase(),
          name: getPageTitle() || `Media Stream ${idx + 1}`
        });
      }
    });
    sendResponse({ media: list, pageTitle: getPageTitle(), pageUrl: window.location.href });
    return true;
  } else if (request.action === "mediaStreamDetected") {
    if (request.media && request.media.url) {
      lastDetectedNetworkStream = request.media.url;
    }
  }
});
