// FalconDM Browser Integration - Content Script (IDM-Style Media Grabber v2.8.2)
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

// 2. IDM-Style Shadow DOM Encapsulated Media Grabber Button
let currentActiveMedia = null;
const dismissedMediaSet = new WeakSet();
let positionRafId = null;
let overlayHost = null;
let shadowRoot = null;

// Draggable offsets
let dragOffsetX = 0;
let dragOffsetY = 0;
let isDragging = false;
let didDrag = false;
let dragStartX = 0;
let dragStartY = 0;
let initialHostLeft = 0;
let initialHostTop = 0;
const DRAG_THRESHOLD = 5;

function createPlayerOverlay() {
  if (overlayHost && shadowRoot) return { host: overlayHost, root: shadowRoot };

  let existing = document.querySelector("falcondm-media-overlay");
  if (existing && existing.shadowRoot) {
    overlayHost = existing;
    shadowRoot = existing.shadowRoot;
    return { host: overlayHost, root: shadowRoot };
  }

  overlayHost = document.createElement("falcondm-media-overlay");
  Object.assign(overlayHost.style, {
    position: "fixed",
    display: "none",
    zIndex: "2147483647",
    pointerEvents: "auto",
    userSelect: "none"
  });

  shadowRoot = overlayHost.attachShadow({ mode: "open" });
  shadowRoot.innerHTML = `
    <style>
      :host {
        all: initial;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        font-size: 12px;
        line-height: 1.2;
        box-sizing: border-box;
      }
      *, *::before, *::after {
        box-sizing: border-box;
      }
      .falcondm-container {
        position: relative;
        display: inline-flex;
        align-items: center;
        background: linear-gradient(135deg, #1d4ed8 0%, #2563eb 100%);
        color: #ffffff;
        border-radius: 8px;
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.45), 0 0 0 1px rgba(255, 255, 255, 0.25);
        height: 32px;
        cursor: grab;
      }
      .falcondm-container:active {
        cursor: grabbing;
      }
      .falcondm-main-btn {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 0 10px;
        height: 100%;
        cursor: pointer;
        border-top-left-radius: 8px;
        border-bottom-left-radius: 8px;
        transition: background 0.15s ease;
      }
      .falcondm-main-btn:hover {
        background: rgba(255, 255, 255, 0.15);
      }
      .falcondm-main-btn svg {
        flex-shrink: 0;
        width: 15px;
        height: 15px;
        stroke: #ffffff;
      }
      .falcondm-label {
        font-weight: 700;
        font-size: 12px;
        white-space: nowrap;
        color: #ffffff;
      }
      .falcondm-badge {
        font-size: 9px;
        background: rgba(255, 255, 255, 0.25);
        color: #ffffff;
        padding: 1px 5px;
        border-radius: 4px;
        font-weight: 800;
        letter-spacing: 0.5px;
      }
      .falcondm-toggle-btn {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0 7px;
        height: 100%;
        border-left: 1px solid rgba(255, 255, 255, 0.25);
        cursor: pointer;
        transition: background 0.15s ease;
      }
      .falcondm-toggle-btn:hover {
        background: rgba(255, 255, 255, 0.15);
      }
      .falcondm-toggle-btn svg {
        width: 10px;
        height: 10px;
        stroke: #ffffff;
      }
      .falcondm-close-btn {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0 8px;
        height: 100%;
        border-left: 1px solid rgba(255, 255, 255, 0.25);
        border-top-right-radius: 8px;
        border-bottom-right-radius: 8px;
        cursor: pointer;
        opacity: 0.85;
        transition: background 0.15s ease, opacity 0.15s ease;
      }
      .falcondm-close-btn:hover {
        background: rgba(239, 68, 68, 0.6);
        opacity: 1;
      }
      .falcondm-close-btn svg {
        width: 11px;
        height: 11px;
        stroke: #ffffff;
      }
      .falcondm-menu {
        display: none;
        position: absolute;
        top: calc(100% + 6px);
        right: 0;
        background: rgba(15, 23, 42, 0.98);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(56, 189, 248, 0.4);
        border-radius: 10px;
        box-shadow: 0 14px 32px rgba(0, 0, 0, 0.85);
        width: 250px;
        overflow: hidden;
        z-index: 2147483647;
        font-size: 12px;
        font-weight: 600;
        padding: 4px 0;
      }
      .falcondm-menu-header {
        padding: 6px 12px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        font-size: 10px;
        font-weight: 800;
        color: #94a3b8;
        letter-spacing: 0.5px;
        text-transform: uppercase;
      }
      .falcondm-q-item {
        padding: 8px 12px;
        color: #f8fafc;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: space-between;
        transition: background 0.12s ease;
      }
      .falcondm-q-item:hover {
        background: rgba(30, 41, 59, 0.95);
      }
      .falcondm-q-badge {
        font-size: 10px;
        padding: 2px 6px;
        border-radius: 4px;
        font-weight: 700;
      }
      .falcondm-q-badge.blue {
        background: #2563eb;
        color: #fff;
      }
      .falcondm-q-badge.dark {
        background: #1e293b;
        color: #38bdf8;
        border: 1px solid #334155;
      }
      .falcondm-q-badge.gray {
        background: #1e293b;
        color: #94a3b8;
      }
      .falcondm-q-badge.sky {
        background: #0284c7;
        color: #fff;
      }
      .falcondm-q-divider {
        border-top: 1px solid rgba(255, 255, 255, 0.08);
      }
    </style>
    <div class="falcondm-container" id="falcondm-container">
      <div class="falcondm-main-btn" id="falcondm-main-dl" title="Download video with FalconDM (MP4)">
        <svg viewBox="0 0 24 24" fill="none" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
          <polyline points="7 10 12 15 17 10"></polyline>
          <line x1="12" y1="15" x2="12" y2="3"></line>
        </svg>
        <span class="falcondm-label" id="falcondm-label">Download Video</span>
        <span class="falcondm-badge" id="falcondm-badge">MP4</span>
      </div>
      <div class="falcondm-toggle-btn" id="falcondm-toggle" title="Select Video Quality / Format">
        <svg viewBox="0 0 24 24" fill="none" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="6 9 12 15 18 9"></polyline>
        </svg>
      </div>
      <div class="falcondm-close-btn" id="falcondm-close" title="Close download button for this video">
        <svg viewBox="0 0 24 24" fill="none" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <line x1="18" y1="6" x2="6" y2="18"></line>
          <line x1="6" y1="6" x2="18" y2="18"></line>
        </svg>
      </div>
      <div class="falcondm-menu" id="falcondm-menu"></div>
    </div>
  `;

  // Attach drag listeners to host
  overlayHost.addEventListener("mousedown", onDragStart);

  // Attach action handlers inside shadowRoot
  const mainBtn = shadowRoot.getElementById("falcondm-main-dl");
  const toggleBtn = shadowRoot.getElementById("falcondm-toggle");
  const closeBtn = shadowRoot.getElementById("falcondm-close");
  const menu = shadowRoot.getElementById("falcondm-menu");

  mainBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    e.preventDefault();
    if (didDrag) { didDrag = false; return; }
    triggerDownload("bestvideo+bestaudio/best");
  });

  toggleBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    e.preventDefault();
    if (didDrag) { didDrag = false; return; }
    menu.style.display = menu.style.display === "block" ? "none" : "block";
  });

  closeBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    e.preventDefault();
    if (currentActiveMedia) {
      dismissedMediaSet.add(currentActiveMedia);
    }
    overlayHost.style.display = "none";
    menu.style.display = "none";
  });

  const container = document.fullscreenElement || document.body || document.documentElement;
  container.appendChild(overlayHost);
  return { host: overlayHost, root: shadowRoot };
}

// Drag & Drop Repositioning
function onDragStart(e) {
  const path = e.composedPath();
  const isClose = path.some(el => el.id === "falcondm-close");
  const isToggle = path.some(el => el.id === "falcondm-toggle");
  const isMenu = path.some(el => el.id === "falcondm-menu" || (el.classList && el.classList.contains("falcondm-q-item")));
  if (isClose || isMenu) return;

  dragStartX = e.clientX;
  dragStartY = e.clientY;
  initialHostLeft = parseFloat(overlayHost.style.left) || 0;
  initialHostTop = parseFloat(overlayHost.style.top) || 0;
  isDragging = false;
  didDrag = false;

  window.addEventListener("mousemove", onDragMove, { passive: false });
  window.addEventListener("mouseup", onDragEnd, { passive: false });
}

function onDragMove(e) {
  const dx = e.clientX - dragStartX;
  const dy = e.clientY - dragStartY;
  if (!isDragging) {
    if (Math.hypot(dx, dy) >= DRAG_THRESHOLD) {
      isDragging = true;
    } else {
      return;
    }
  }

  e.preventDefault();
  overlayHost.style.left = `${Math.max(10, Math.min(window.innerWidth - 150, initialHostLeft + dx))}px`;
  overlayHost.style.top = `${Math.max(10, Math.min(window.innerHeight - 50, initialHostTop + dy))}px`;
}

function onDragEnd(e) {
  window.removeEventListener("mousemove", onDragMove);
  window.removeEventListener("mouseup", onDragEnd);
  if (isDragging) {
    didDrag = true;
    isDragging = false;
    dragOffsetX += (e.clientX - dragStartX);
    dragOffsetY += (e.clientY - dragStartY);
  }
}

function triggerDownload(formatId) {
  if (!currentActiveMedia) return;
  const targetUrl = resolveMediaUrl(currentActiveMedia);
  const isAudioOnly = (formatId === "bestaudio" || formatId === "bestaudio/best" || currentActiveMedia.tagName === "AUDIO") && !formatId.includes("video");
  const smartTitle = extractSmartMediaTitle(currentActiveMedia);
  const ext = isAudioOnly ? ".mp3" : ".mp4";
  const filename = smartTitle ? `${smartTitle}${ext}` : "";

  if (targetUrl) {
    browserAPI.runtime.sendMessage({
      action: "download",
      url: targetUrl,
      filename: filename,
      format_id: formatId
    });
    showToast(formatId === "prompt" ? "⚡ Opening FalconDM Media Downloader..." : `⚡ Downloading: ${smartTitle || "Media"} (${isAudioOnly ? "MP3" : "MP4"})...`);
  } else {
    showToast("❌ Could not resolve media URL.");
  }
}

function renderQualityMenuForMedia(media) {
  const { root } = createPlayerOverlay();
  const menu = root.getElementById("falcondm-menu");
  if (!menu) return;

  const isAudio = media && media.tagName === "AUDIO";

  if (isAudio) {
    menu.innerHTML = `
      <div class="falcondm-menu-header">Audio Download Options</div>
      <div class="falcondm-q-item" data-format="bestaudio/best">
        <span>🎵 Extract / Download MP3</span>
        <span class="falcondm-q-badge sky">MP3</span>
      </div>
      <div class="falcondm-q-item" data-format="direct">
        <span>🌟 Direct Audio Stream</span>
        <span class="falcondm-q-badge dark">DIRECT</span>
      </div>
    `;
  } else {
    menu.innerHTML = `
      <div class="falcondm-menu-header">Select Download Format</div>
      <div class="falcondm-q-item" data-format="bestvideo+bestaudio/best">
        <span>🌟 Best Available Quality (Auto)</span>
        <span class="falcondm-q-badge blue">MP4</span>
      </div>
      <div class="falcondm-q-item" data-format="bestvideo[height<=1080]+bestaudio/best[height<=1080]">
        <span>🎬 1080p Full HD</span>
        <span class="falcondm-q-badge dark">1080p</span>
      </div>
      <div class="falcondm-q-item" data-format="bestvideo[height<=720]+bestaudio/best[height<=720]">
        <span>🎥 720p HD</span>
        <span class="falcondm-q-badge gray">720p</span>
      </div>
      <div class="falcondm-q-item" data-format="bestvideo[height<=480]+bestaudio/best[height<=480]">
        <span>📱 480p SD</span>
        <span class="falcondm-q-badge gray">480p</span>
      </div>
      <div class="falcondm-q-item falcondm-q-divider" data-format="bestaudio/best">
        <span>🎵 Extract Audio (MP3)</span>
        <span class="falcondm-q-badge sky">MP3</span>
      </div>
      <div class="falcondm-q-item falcondm-q-divider" data-format="prompt">
        <span>⚙️ More Options / Choose Folder...</span>
        <span class="falcondm-q-badge gray">PROMPT</span>
      </div>
    `;
  }

  menu.querySelectorAll(".falcondm-q-item").forEach(item => {
    item.onclick = (e) => {
      e.stopPropagation();
      e.preventDefault();
      menu.style.display = "none";
      const formatId = item.getAttribute("data-format");
      triggerDownload(formatId);
    };
  });
}

function positionOverlay(media) {
  if (!media || dismissedMediaSet.has(media)) return;
  const { host, root } = createPlayerOverlay();
  const rect = media.getBoundingClientRect();

  // Hidden, detached, or scrolled completely out of view
  if (rect.width < 80 || rect.height < 50 || rect.bottom <= 0 || rect.top >= window.innerHeight) {
    host.style.display = "none";
    return;
  }

  const isAudio = media.tagName === "AUDIO";
  const labelSpan = root.getElementById("falcondm-label");
  const badgeSpan = root.getElementById("falcondm-badge");
  if (labelSpan) {
    labelSpan.textContent = isAudio ? "Download Audio" : "Download Video";
  }
  if (badgeSpan) {
    badgeSpan.textContent = isAudio ? "MP3" : "MP4";
    badgeSpan.style.background = isAudio ? "#0284c7" : "rgba(255,255,255,0.25)";
  }

  renderQualityMenuForMedia(media);

  // Position at top-right inside video viewport with offset
  const pad = 12;
  const naturalLeft = Math.max(pad, Math.min(window.innerWidth - 180, rect.right - 180));
  const naturalTop = Math.max(pad, Math.min(window.innerHeight - 45, rect.top + pad));

  const finalLeft = naturalLeft + dragOffsetX;
  const finalTop = naturalTop + dragOffsetY;

  host.style.left = `${Math.max(pad, Math.min(window.innerWidth - 180, finalLeft))}px`;
  host.style.top = `${Math.max(pad, Math.min(window.innerHeight - 45, finalTop))}px`;
  host.style.display = "block";
}

function updateActiveOverlayPosition() {
  if (!currentActiveMedia || dismissedMediaSet.has(currentActiveMedia)) {
    if (overlayHost) overlayHost.style.display = "none";
    return;
  }
  positionOverlay(currentActiveMedia);
}

// Keep button smoothly pinned to video on scroll and resize
window.addEventListener("scroll", () => {
  if (positionRafId) cancelAnimationFrame(positionRafId);
  positionRafId = requestAnimationFrame(updateActiveOverlayPosition);
}, { passive: true });

window.addEventListener("resize", () => {
  if (positionRafId) cancelAnimationFrame(positionRafId);
  positionRafId = requestAnimationFrame(updateActiveOverlayPosition);
}, { passive: true });

document.addEventListener("fullscreenchange", () => {
  if (overlayHost) {
    const targetParent = document.fullscreenElement || document.body || document.documentElement;
    if (overlayHost.parentElement !== targetParent) {
      targetParent.appendChild(overlayHost);
    }
  }
  updateActiveOverlayPosition();
});

function resolveMediaUrl(media) {
  if (!media) return window.location.href;
  const href = window.location.href;
  const host = window.location.hostname.toLowerCase();

  // 1. Facebook Reels & Watch & Posts
  if (host.includes("facebook.com") || host.includes("fb.watch")) {
    if (href.includes("/reel/") || href.includes("/watch") || href.includes("/videos/")) {
      return href;
    }
    const post = media.closest('div[role="feed"] > div, div[role="article"], div[data-pagelet*="Feed"], div[data-pagelet*="Reel"], div[role="main"]');
    if (post) {
      const link = post.querySelector('a[href*="/reel/"], a[href*="/videos/"], a[href*="watch?v="]');
      if (link && link.href) return link.href;
    }
    return href;
  }

  // 2. YouTube
  if (host.includes("youtube.com") || host.includes("youtu.be")) {
    return href;
  }

  // 3. TikTok
  if (host.includes("tiktok.com")) {
    return href;
  }

  // 4. Instagram
  if (host.includes("instagram.com")) {
    return href;
  }

  // 5. Twitter / X
  if (host.includes("twitter.com") || host.includes("x.com")) {
    return href;
  }

  // Direct video element source
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

// 3. Weighted Active Media Discovery Scoring Algorithm
// Digit slots: playing (1e9) beats readyState (1e6) beats viewport area, so active video wins over paused background thumbnails
function computeMediaScore(media) {
  const rect = media.getBoundingClientRect();
  if (rect.width < 100 || rect.height < 60 || rect.bottom <= 0 || rect.right <= 0 || rect.top >= window.innerHeight || rect.left >= window.innerWidth) {
    return -1;
  }
  const isPlaying = (!media.paused && !media.ended) ? 1_000_000_000 : 0;
  const ready = (media.readyState || 0) * 1_000_000;
  const area = rect.width * rect.height;
  return isPlaying + ready + area;
}

function findBestActiveMedia() {
  const candidates = Array.from(document.querySelectorAll("video, audio")).filter(m => !dismissedMediaSet.has(m));
  let best = null;
  let maxScore = -1;

  for (const el of candidates) {
    const score = computeMediaScore(el);
    if (score > maxScore) {
      maxScore = score;
      best = el;
    }
  }
  return best;
}

// Find video or audio element under cursor (including through transparent Facebook overlays)
function findMediaUnderCursor(e) {
  const direct = e.target.closest("video, audio");
  if (direct && !dismissedMediaSet.has(direct)) return direct;

  const iframeTarget = e.target.closest("iframe");
  if (iframeTarget) {
    const src = (iframeTarget.src || "").toLowerCase();
    if (src.includes("youtube") || src.includes("vimeo") || src.includes("player") || src.includes("embed")) {
      const rect = iframeTarget.getBoundingClientRect();
      if (rect.width >= 160 && rect.height >= 90) return iframeTarget;
    }
  }

  // Common modern video player wrapper containers (Facebook, YouTube, Bilibili, JWPlayer, etc.)
  const container = e.target.closest(
    'div[data-pagelet*="Reel"], div[data-pagelet*="Feed"], div[role="feed"] > div, div[role="article"], ' +
    '.html5-video-player, ytd-player, .bpx-player-container, .video-js, .jwplayer, .plyr, .dplayer, .artplayer'
  );
  if (container) {
    const inside = container.querySelector("video, audio, iframe");
    if (inside && !dismissedMediaSet.has(inside)) return inside;
  }

  return null;
}

// Mouse hover over any video player attaches the IDM download button
document.addEventListener("mouseover", (e) => {
  if (overlayHost && e.composedPath().includes(overlayHost)) return;
  const media = findMediaUnderCursor(e);
  if (media && !dismissedMediaSet.has(media)) {
    currentActiveMedia = media;
    positionOverlay(media);
  }
}, true);

// When a video starts playing, immediately attach the persistent download button to it
window.addEventListener("play", (e) => {
  if (e.target && (e.target.tagName === "VIDEO" || e.target.tagName === "AUDIO")) {
    if (!dismissedMediaSet.has(e.target)) {
      currentActiveMedia = e.target;
      positionOverlay(e.target);
    }
  }
}, true);

// Periodic Background Scanner for Facebook Reels and Active Videos (IDM Persistence)
// Ensures the download button is constant and does NOT flicker or disappear on Facebook reels
setInterval(() => {
  // If current media is valid and actively playing, keep it pinned
  if (currentActiveMedia && !dismissedMediaSet.has(currentActiveMedia)) {
    const rect = currentActiveMedia.getBoundingClientRect();
    if (rect.width >= 80 && rect.height >= 50 && rect.bottom > 0 && rect.top < window.innerHeight) {
      positionOverlay(currentActiveMedia);
      return;
    }
  }

  // Find the highest scoring active media
  const best = findBestActiveMedia();
  if (best) {
    currentActiveMedia = best;
    positionOverlay(best);
  }
}, 1200);

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
  toast.style.boxShadow = "0 8px 24px rgba(0,0,0,0.7)";
  toast.style.zIndex = "2147483647";
  toast.style.pointerEvents = "none";
  toast.style.transition = "opacity 0.3s ease";
  document.body.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 300);
  }, 2800);
}

// Respond to extension popup queries with active media elements and page images
browserAPI.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "showToast") {
    showToast(request.message);
  } else if (request.action === "getMediaList") {
    const list = [];
    // 1. Audio and Video elements
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

    // 2. High-Resolution Page Images (Sniffer Image tab support)
    const seenImages = new Set();
    document.querySelectorAll("img[src]").forEach((img) => {
      const src = img.src;
      if (!src || src.startsWith("data:") || seenImages.has(src)) return;
      const w = img.naturalWidth || img.width || 0;
      const h = img.naturalHeight || img.height || 0;
      if (w >= 120 && h >= 120) {
        seenImages.add(src);
        list.push({
          url: src,
          type: "image",
          name: img.alt || img.title || src.split("/").pop().split("?")[0] || "Page Image"
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
