const browserAPI = (typeof browser !== "undefined" && browser.runtime) ? browser : chrome;
const FALCON_API = "http://127.0.0.1:9666/download";
const PING_API = "http://127.0.0.1:9666/ping";

let currentTabUrl = "";
let currentTabId = null;
let detectedMediaList = [];

// 1. Check server status
fetch(PING_API)
  .then(res => res.json())
  .then(data => {
    const badge = document.getElementById("statusBadge");
    badge.textContent = "ONLINE";
    badge.style.color = "#4ade80";
  })
  .catch(err => {
    const badge = document.getElementById("statusBadge");
    badge.textContent = "OFFLINE";
    badge.style.color = "#f87171";
  });

// 2. Tab Navigation
const tabBtnQuick = document.getElementById("tabBtnQuick");
const tabBtnSniff = document.getElementById("tabBtnSniff");
const tabContentQuick = document.getElementById("tabContentQuick");
const tabContentSniff = document.getElementById("tabContentSniff");

tabBtnQuick.addEventListener("click", () => {
  tabBtnQuick.classList.add("active");
  tabBtnSniff.classList.remove("active");
  tabContentQuick.classList.add("active");
  tabContentSniff.classList.remove("active");
});

tabBtnSniff.addEventListener("click", () => {
  tabBtnSniff.classList.add("active");
  tabBtnQuick.classList.remove("active");
  tabContentSniff.classList.add("active");
  tabContentQuick.classList.remove("active");
  fetchTabMedia();
});

// 3. Get current active tab & inspect media
if (browserAPI.tabs && browserAPI.tabs.query) {
  browserAPI.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs && tabs[0]) {
      const tab = tabs[0];
      currentTabId = tab.id;
      currentTabUrl = tab.url || "";
      document.getElementById("tabTitle").textContent = tab.title || currentTabUrl;
      fetchTabMedia();
    }
  });
}

function formatBytes(bytes) {
  if (!bytes || bytes <= 0) return "";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

let currentFilter = "all";

// Setup filter button handlers
document.querySelectorAll(".sniff-filter").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".sniff-filter").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    currentFilter = btn.getAttribute("data-filter") || "all";
    renderSnifferList();
  });
});

function renderSnifferList() {
  const container = document.getElementById("snifferContainer");
  const countEl = document.getElementById("sniffCount");
  countEl.textContent = detectedMediaList.length;

  const filtered = detectedMediaList.filter(item => {
    if (currentFilter === "all") return true;
    if (currentFilter === "video") return item.type === "video";
    if (currentFilter === "audio") return item.type === "audio";
    if (currentFilter === "image") return item.type === "image";
    if (currentFilter === "file") return item.type === "archive" || item.type === "document" || item.type === "program" || item.type === "file";
    return true;
  });

  if (filtered.length === 0) {
    container.innerHTML = `<div class="empty-sniffer">${detectedMediaList.length === 0 ? "No media or streams found on page yet." : "No items match current filter (" + currentFilter + ")."}</div>`;
    return;
  }

  container.innerHTML = "";
  filtered.forEach((item, idx) => {
    const row = document.createElement("div");
    row.className = "sniffer-item";

    const icon = item.type === "video" ? "🎬" : item.type === "audio" ? "🎵" : item.type === "image" ? "🖼️" : item.type === "archive" ? "📦" : item.type === "document" ? "📄" : "⚙️";
    const sizeStr = item.size ? ` • ${formatBytes(item.size)}` : "";
    const mimeStr = item.mime ? ` (${item.mime.split('/')[1] || item.mime})` : "";

    row.innerHTML = `
      <div class="sniffer-info">
        <div class="sniffer-name" title="${item.name}">${icon} ${item.name}</div>
        <div class="sniffer-meta">
          <span style="text-transform: uppercase; font-weight: 700; color: #38bdf8;">${item.type}</span>
          <span style="color: #4ade80;">${sizeStr}${mimeStr}</span>
          <span style="color: #64748b; font-size: 9px;" title="${item.url}">${item.url.substring(0, 24)}...</span>
        </div>
      </div>
      <button class="btn-sniff-dl" data-idx="${idx}">Download</button>
    `;

    row.querySelector(".btn-sniff-dl").addEventListener("click", () => {
      sendDownload(item.url, item.name);
    });

    container.appendChild(row);
  });
}

function fetchTabMedia() {
  if (!currentTabId) return;

  // Query background webRequest network sniffer
  browserAPI.runtime.sendMessage({ action: "getTabMediaList", tabId: currentTabId }, (bgRes) => {
    const netMedia = (bgRes && bgRes.media) ? bgRes.media : [];

    // Query content script DOM elements
    browserAPI.tabs.sendMessage(currentTabId, { action: "getMediaList" }, (domRes) => {
      const domMedia = (domRes && domRes.media) ? domRes.media : [];

      const combined = [];
      const seen = new Set();

      for (const item of [...netMedia, ...domMedia]) {
        if (!item || !item.url || seen.has(item.url)) continue;
        seen.add(item.url);
        combined.push(item);
      }

      detectedMediaList = combined;
      renderSnifferList();
    });
  });
}

document.getElementById("btnRescanTab").addEventListener("click", fetchTabMedia);

document.getElementById("btnDownloadAllSniff").addEventListener("click", () => {
  const filtered = detectedMediaList.filter(item => {
    if (currentFilter === "all") return true;
    if (currentFilter === "video") return item.type === "video";
    if (currentFilter === "audio") return item.type === "audio";
    if (currentFilter === "image") return item.type === "image";
    if (currentFilter === "file") return item.type === "archive" || item.type === "document" || item.type === "program" || item.type === "file";
    return true;
  });

  if (filtered.length === 0) {
    setStatus("No media items in current view to download.", "#facc15");
    return;
  }
  filtered.forEach(item => {
    sendDownload(item.url, item.name);
  });
  setStatus(`Sent ${filtered.length} media file(s) to FalconDM!`, "#4ade80");
});

// 4. Auto-Intercept Toggle
const chkAuto = document.getElementById("chkAutoIntercept");
const sliderSpan = document.getElementById("sliderSpan");

function updateSliderStyle(checked) {
  if (sliderSpan) {
    sliderSpan.style.backgroundColor = checked ? "#2563eb" : "#475569";
  }
}

if (browserAPI.runtime && browserAPI.runtime.sendMessage) {
  browserAPI.runtime.sendMessage({ action: "getAutoIntercept" }, (res) => {
    if (res && typeof res.autoIntercept === "boolean") {
      chkAuto.checked = res.autoIntercept;
      updateSliderStyle(res.autoIntercept);
    }
  });
}

chkAuto.addEventListener("change", () => {
  const isEnabled = chkAuto.checked;
  updateSliderStyle(isEnabled);
  if (browserAPI.runtime && browserAPI.runtime.sendMessage) {
    browserAPI.runtime.sendMessage({ action: "setAutoIntercept", enabled: isEnabled });
  }
});

// 5. Quick action buttons
document.getElementById("btnWebRemote").addEventListener("click", () => {
  if (browserAPI.tabs && browserAPI.tabs.create) {
    browserAPI.tabs.create({ url: "http://127.0.0.1:9666/remote" });
  } else {
    window.open("http://127.0.0.1:9666/remote", "_blank");
  }
});

document.getElementById("btnSetupGuide").addEventListener("click", () => {
  if (browserAPI.tabs && browserAPI.tabs.create) {
    browserAPI.tabs.create({ url: "http://127.0.0.1:9666/" });
  } else {
    window.open("http://127.0.0.1:9666/", "_blank");
  }
});

document.getElementById("btnDownloadTab").addEventListener("click", () => {
  if (currentTabUrl) {
    const title = document.getElementById("tabTitle").textContent;
    sendDownload(currentTabUrl, title);
  }
});

document.getElementById("btnSendCustom").addEventListener("click", () => {
  const url = document.getElementById("customUrl").value.trim();
  if (url) {
    sendDownload(url);
    document.getElementById("customUrl").value = "";
  }
});

function setStatus(text, color) {
  const msgEl = document.getElementById("statusMsg");
  msgEl.textContent = text;
  msgEl.style.color = color || "#4ade80";
  setTimeout(() => {
    msgEl.textContent = "";
  }, 3500);
}

function sendDownload(url, filename = "") {
  setStatus("Sending to FalconDM...", "#38bdf8");

  fetch(FALCON_API, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url: url, filename: filename })
  })
  .then(res => {
    if (!res.ok) throw new Error("HTTP " + res.status);
    return res.text();
  })
  .then(text => {
    setStatus("⚡ Sent to FalconDM successfully!", "#4ade80");
  })
  .catch(err => {
    setStatus("❌ FalconDM is offline. Launch app first!", "#f87171");
  });
}
