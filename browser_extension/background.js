// FalconDM Background Service Worker - Cross-Browser Interception & Context Menus
// Compatible with: Google Chrome, Microsoft Edge, Mozilla Firefox, Brave, Opera, Vivaldi, Arc
const browserAPI = (typeof browser !== "undefined" && browser.runtime) ? browser : chrome;
const FALCON_API = "http://127.0.0.1:9666/download";

// Downloadable file extensions to intercept from any browser and any website
const INTERCEPT_EXTENSIONS = [
  ".zip", ".rar", ".7z", ".tar", ".gz", ".iso", ".bz2", ".xz", ".tgz", ".zst", ".7zip", ".cab",
  ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".3gp", ".ts", ".m3u8", ".mpd",
  ".mp3", ".flac", ".wav", ".aac", ".ogg", ".m4a", ".opus", ".wma", ".aiff", ".alac",
  ".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".avif", ".bmp", ".tiff", ".tif", ".heic", ".ico", ".raw", ".psd",
  ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".csv", ".txt", ".epub", ".mobi", ".rtf",
  ".exe", ".msi", ".apk", ".dmg", ".bin", ".torrent", ".deb", ".rpm", ".pkg", ".crx", ".xpi", ".img"
];

let autoInterceptEnabled = true;

// Load user auto-intercept setting
if (browserAPI.storage && browserAPI.storage.local) {
  browserAPI.storage.local.get({ autoIntercept: true }, (items) => {
    autoInterceptEnabled = items.autoIntercept !== false;
  });
}

// Register Context Menus safely
function setupContextMenu() {
  try {
    if (browserAPI.contextMenus) {
      browserAPI.contextMenus.removeAll(() => {
        if (browserAPI.runtime.lastError) {}
        browserAPI.contextMenus.create({
          id: "falcondm-download",
          title: "⚡ Download with FalconDM",
          contexts: ["all"]
        }, () => {
          if (browserAPI.runtime.lastError) {}
        });
      });
    }
  } catch (e) {}
}

if (browserAPI.runtime && browserAPI.runtime.onInstalled) {
  browserAPI.runtime.onInstalled.addListener(setupContextMenu);
}
if (browserAPI.runtime && browserAPI.runtime.onStartup) {
  browserAPI.runtime.onStartup.addListener(setupContextMenu);
}

// Handle Context Menu clicks on any website
if (browserAPI.contextMenus && browserAPI.contextMenus.onClicked) {
  browserAPI.contextMenus.onClicked.addListener((info, tab) => {
    let targetUrl = info.linkUrl || info.srcUrl;
    if (!targetUrl && info.selectionText) {
      const sel = info.selectionText.trim();
      if (sel.startsWith("http://") || sel.startsWith("https://") || sel.startsWith("magnet:?")) {
        targetUrl = sel;
      }
    }
    if (!targetUrl) {
      targetUrl = info.pageUrl || (tab ? tab.url : "");
    }
    if (targetUrl) {
      sendToFalcon(targetUrl, tab ? tab.id : null);
    }
  });
}

// IDM-Grade Automatic Download Interception for any browser (onCreated + onDeterminingFilename)
const interceptedDownloadIds = new Set();

function handleDownloadIntercept(downloadItem) {
  if (!autoInterceptEnabled) return false;
  if (!downloadItem || !downloadItem.id) return false;
  if (interceptedDownloadIds.has(downloadItem.id)) return true;

  const url = downloadItem.finalUrl || downloadItem.url;
  if (!url || typeof url !== "string") return false;

  const lowerUrl = url.toLowerCase();
  if (lowerUrl.startsWith("data:") || lowerUrl.startsWith("blob:") ||
      lowerUrl.startsWith("chrome:") || lowerUrl.startsWith("edge:") ||
      lowerUrl.startsWith("about:") || lowerUrl.startsWith("moz-extension:") ||
      lowerUrl.startsWith("chrome-extension:")) {
    return false;
  }

  // Ignore downloads initiated by our own extension
  if (downloadItem.byExtensionId === browserAPI.runtime.id) return false;

  const filename = (downloadItem.filename || "").toLowerCase();
  const cleanUrl = lowerUrl.split("?")[0].split("#")[0];

  const hasMatch = INTERCEPT_EXTENSIONS.some(ext => cleanUrl.endsWith(ext) || filename.endsWith(ext));
  const mime = (downloadItem.mime || "").toLowerCase();
  const isBinaryMime = mime.includes("application/zip") ||
                       mime.includes("application/x-zip") ||
                       mime.includes("application/octet-stream") ||
                       mime.includes("application/x-msdownload") ||
                       mime.includes("application/vnd.android.package-archive") ||
                       mime.includes("video/") || mime.includes("audio/");

  if (hasMatch || isBinaryMime || (downloadItem.fileSize && downloadItem.fileSize > 512 * 1024)) {
    interceptedDownloadIds.add(downloadItem.id);
    if (interceptedDownloadIds.size > 200) {
      const first = interceptedDownloadIds.values().next().value;
      interceptedDownloadIds.delete(first);
    }

    try {
      browserAPI.downloads.cancel(downloadItem.id, () => {
        if (browserAPI.runtime.lastError) {}
        if (browserAPI.downloads.erase) {
          browserAPI.downloads.erase({ id: downloadItem.id }, () => {});
        }
      });
    } catch (e) {}

    sendToFalcon(url, null, downloadItem.filename || "", "", downloadItem.fileSize || 0);
    return true;
  }
  return false;
}

if (browserAPI.downloads && browserAPI.downloads.onCreated) {
  browserAPI.downloads.onCreated.addListener((downloadItem) => {
    handleDownloadIntercept(downloadItem);
  });
}

if (browserAPI.downloads && browserAPI.downloads.onDeterminingFilename) {
  browserAPI.downloads.onDeterminingFilename.addListener((downloadItem, suggest) => {
    if (handleDownloadIntercept(downloadItem)) {
      try { suggest(); } catch (e) {}
    }
  });
}

// Global Tab Media Store for Intercepted Network Streams
const tabMediaStore = new Map(); // tabId -> Array of media items

// Real-Time Network Stream & Media Sniffer (IDM-Grade Interception)
if (browserAPI.webRequest && browserAPI.webRequest.onHeadersReceived) {
  try {
    browserAPI.webRequest.onHeadersReceived.addListener(
      (details) => {
        if (!details || details.tabId < 0) return;
        const url = details.url;
        if (!url || typeof url !== "string") return;
        const lower = url.toLowerCase();

        // Skip extension internals or local backend
        if (lower.startsWith("chrome:") || lower.startsWith("edge:") || lower.startsWith("moz-extension:") || lower.includes("127.0.0.1:9666")) return;

        let mime = "";
        let contentLength = 0;
        let contentDisposition = "";

        if (details.responseHeaders) {
          for (const h of details.responseHeaders) {
            const name = h.name.toLowerCase();
            if (name === "content-type") mime = (h.value || "").toLowerCase();
            else if (name === "content-length") contentLength = parseInt(h.value || "0", 10) || 0;
            else if (name === "content-disposition") contentDisposition = h.value || "";
          }
        }

        const cleanPath = lower.split("?")[0].split("#")[0];

        // Only detect genuine video/audio streams and standalone downloadable binaries
        // NEVER intercept normal web page images (avoids flooding tabs with 100+ IPC calls per second)
        const isVideo = mime.startsWith("video/") ||
                        mime.includes("application/vnd.apple.mpegurl") ||
                        mime.includes("application/x-mpegurl") ||
                        mime.includes("application/dash+xml") ||
                        cleanPath.endsWith(".m3u8") || cleanPath.endsWith(".mpd") ||
                        cleanPath.endsWith(".mp4") || cleanPath.endsWith(".webm") ||
                        cleanPath.endsWith(".flv") || cleanPath.endsWith(".mkv");

        const isAudio = (mime.startsWith("audio/") ||
                        cleanPath.endsWith(".mp3") || cleanPath.endsWith(".m4a") ||
                        cleanPath.endsWith(".flac") || cleanPath.endsWith(".wav") ||
                        cleanPath.endsWith(".opus") || cleanPath.endsWith(".ogg")) &&
                        !cleanPath.endsWith(".js") && !cleanPath.endsWith(".css");

        const isArchiveOrBinary = INTERCEPT_EXTENSIONS.some(ext => cleanPath.endsWith(ext) && !ext.match(/\.(jpg|jpeg|png|webp|gif|svg|avif|ico)$/i));
        const isLargeStream = contentLength > 5 * 1024 * 1024 && (mime.includes("octet-stream") || mime.includes("binary"));

        if (isVideo || isAudio || isArchiveOrBinary || isLargeStream) {
          const type = isVideo ? "video" : (isAudio ? "audio" : (isArchiveOrBinary ? "archive" : "file"));
          let list = tabMediaStore.get(details.tabId) || [];

          // Deduplicate
          if (!list.some(item => item.url === url)) {
            let filename = "";
            if (contentDisposition) {
              const m = contentDisposition.match(/filename\*?=['"]?(?:UTF-\d['"]*)?([^;\r\n"']*)['"]?/i);
              if (m && m[1]) filename = decodeURIComponent(m[1]);
            }
            if (!filename) {
              try {
                const u = new URL(url);
                filename = u.pathname.split("/").pop() || "";
              } catch (e) {}
            }
            if (!filename || filename.length < 3) {
              filename = `${type}_stream_${list.length + 1}`;
            }

            const mediaRecord = {
              url: url,
              type: type,
              mime: mime,
              size: contentLength,
              filename: filename,
              timestamp: Date.now()
            };

            list.unshift(mediaRecord);
            if (list.length > 50) list.pop();
            tabMediaStore.set(details.tabId, list);

            // Update extension badge on browser toolbar with stream count
            if (browserAPI.action && browserAPI.action.setBadgeText) {
              browserAPI.action.setBadgeText({ tabId: details.tabId, text: `${list.length}` });
              browserAPI.action.setBadgeBackgroundColor({ tabId: details.tabId, color: "#2563eb" });
            }

            // Throttled notification to content script
            if (browserAPI.tabs && browserAPI.tabs.sendMessage) {
              browserAPI.tabs.sendMessage(details.tabId, { action: "mediaStreamDetected", media: mediaRecord }, () => {
                if (browserAPI.runtime.lastError) {}
              });
            }
          }
        }
      },
      { urls: ["<all_urls>"] },
      ["responseHeaders"]
    );
  } catch (err) {
    console.warn("[FalconDM] webRequest listener setup skipped:", err);
  }
}

// Clean up closed tabs
if (browserAPI.tabs && browserAPI.tabs.onRemoved) {
  browserAPI.tabs.onRemoved.addListener((tabId) => {
    tabMediaStore.delete(tabId);
  });
}

// Listen for messages from content scripts and popup
if (browserAPI.runtime && browserAPI.runtime.onMessage) {
  browserAPI.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "download" && request.url) {
      sendToFalcon(request.url, sender.tab ? sender.tab.id : null, request.filename || "", request.format_id || "");
      sendResponse({ status: "sent" });
    } else if (request.action === "getTabMediaList") {
      const tabId = request.tabId || (sender.tab ? sender.tab.id : null);
      const list = tabId ? (tabMediaStore.get(tabId) || []) : [];
      sendResponse({ media: list });
      return true;
    } else if (request.action === "setAutoIntercept") {
      autoInterceptEnabled = !!request.enabled;
      if (browserAPI.storage && browserAPI.storage.local) {
        browserAPI.storage.local.set({ autoIntercept: autoInterceptEnabled });
      }
      sendResponse({ status: "ok", autoIntercept: autoInterceptEnabled });
    } else if (request.action === "getAutoIntercept") {
      sendResponse({ autoIntercept: autoInterceptEnabled });
    }
    return true;
  });
}

async function getCookiesForUrl(url, tabUrl = "") {
  const cookieMap = new Map();
  const urlsToQuery = [];
  if (url && typeof url === "string") urlsToQuery.push(url);
  if (tabUrl && typeof tabUrl === "string" && tabUrl !== url) urlsToQuery.push(tabUrl);

  for (const u of urlsToQuery) {
    try {
      if (!browserAPI.cookies || !browserAPI.cookies.getAll) continue;
      
      // 1. Query exact URL cookies
      const cookies = await new Promise((resolve) => {
        browserAPI.cookies.getAll({ url: u }, (c) => {
          if (browserAPI.runtime.lastError || !c) resolve([]);
          else resolve(c);
        });
      });
      for (const c of cookies) {
        if (!cookieMap.has(c.name)) {
          cookieMap.set(c.name, c.value);
        }
      }

      // 2. Query root and parent domain cookies (captures Cloudflare cf_clearance, __cf_bm, session tokens)
      try {
        const parsed = new URL(u);
        const hostParts = parsed.hostname.split(".");
        if (hostParts.length >= 2) {
          const rootDomain = hostParts.slice(-2).join(".");
          const domainCookies = await new Promise((resolve) => {
            browserAPI.cookies.getAll({ domain: rootDomain }, (c) => {
              if (browserAPI.runtime.lastError || !c) resolve([]);
              else resolve(c);
            });
          });
          for (const c of domainCookies) {
            if (!cookieMap.has(c.name)) {
              cookieMap.set(c.name, c.value);
            }
          }
        }
      } catch (e) {}
    } catch (e) {}
  }

  const parts = [];
  for (const [name, val] of cookieMap.entries()) {
    parts.push(`${name}=${val}`);
  }
  return parts.join("; ");
}

async function sendToFalcon(url, tabId, filename = "", format_id = "", fileSize = 0) {
  let cookieHeader = "";
  let refererHeader = "";

  try {
    if (tabId && browserAPI.tabs && browserAPI.tabs.get) {
      const tab = await new Promise((r) => {
        browserAPI.tabs.get(tabId, (t) => {
          if (browserAPI.runtime.lastError || !t) r(null);
          else r(t);
        });
      });
      if (tab && tab.url) refererHeader = tab.url;
    }
    cookieHeader = await getCookiesForUrl(url, refererHeader);
  } catch (e) {}

  let originHeader = "";
  if (refererHeader) {
    try {
      originHeader = new URL(refererHeader).origin;
    } catch (e) {}
  }

  const payload = {
    url: url,
    filename: filename,
    file_size: fileSize,
    headers: {
      "Cookie": cookieHeader,
      "Referer": refererHeader || url,
      "Origin": originHeader,
      "User-Agent": navigator.userAgent,
      "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
      "Sec-Ch-Ua-Mobile": "?0",
      "Sec-Ch-Ua-Platform": '"Windows"',
      "Sec-Fetch-Dest": "empty",
      "Sec-Fetch-Mode": "cors",
      "Sec-Fetch-Site": "cross-site",
      "Accept": "*/*",
      "Accept-Language": "en-US,en;q=0.9"
    }
  };
  if (format_id) {
    payload.format_id = format_id;
  }

  fetch(FALCON_API, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  })
  .then(res => {
    if (!res.ok) throw new Error("HTTP " + res.status);
    return res.text();
  })
  .then(text => {
    let data;
    try { data = JSON.parse(text); } catch (e) { data = { message: text }; }
    if (tabId && browserAPI.tabs && browserAPI.tabs.sendMessage) {
      browserAPI.tabs.sendMessage(tabId, { action: "showToast", message: "⚡ Sent to FalconDM Turbo Downloader!" }, () => {
        if (browserAPI.runtime.lastError) {}
      });
    }
  })
  .catch(err => {
    // Try Native Messaging Host auto-launch
    try {
      if (browserAPI.runtime && browserAPI.runtime.sendNativeMessage) {
        browserAPI.runtime.sendNativeMessage("com.falcondm.downloader", { action: "launch" }, (response) => {
          if (browserAPI.runtime.lastError) {
            notifyOffline(tabId);
            return;
          }
          // Retry sending after FalconDM has booted up
          setTimeout(() => {
            fetch(FALCON_API, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(payload)
            }).then(() => {
              if (tabId && browserAPI.tabs && browserAPI.tabs.sendMessage) {
                browserAPI.tabs.sendMessage(tabId, { action: "showToast", message: "⚡ FalconDM started & download queued!" }, () => {});
              }
            }).catch(() => notifyOffline(tabId));
          }, 1800);
        });
        return;
      }
    } catch (e) {}

    notifyOffline(tabId);
  });
}

function notifyOffline(tabId) {
  if (tabId && browserAPI.tabs && browserAPI.tabs.sendMessage) {
    browserAPI.tabs.sendMessage(tabId, { action: "showToast", message: "❌ FalconDM is not running. Launch FalconDM first!" }, () => {
      if (browserAPI.runtime.lastError) {}
    });
  }
}
