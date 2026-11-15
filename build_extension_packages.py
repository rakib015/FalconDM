import os
import json
import zipfile
import shutil

def build_extension_packages():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    ext_dir = os.path.join(base_dir, "browser_extension")
    out_dir = os.path.join(base_dir, "dist_extension")
    os.makedirs(out_dir, exist_ok=True)

    with open(os.path.join(ext_dir, "manifest.json"), "r", encoding="utf-8") as f:
        manifest_data = json.load(f)

    version = manifest_data.get("version", "2.8.0")
    print(f"📦 Packaging FalconDM Browser Extension v{version}...")

    # Assets to package
    common_files = [
        "background.js",
        "content.js",
        "popup.html",
        "popup.js",
        "icon16.png",
        "icon48.png",
        "icon128.png"
    ]

    # Verify all files exist
    for fn in common_files:
        p = os.path.join(ext_dir, fn)
        if not os.path.isfile(p):
            raise FileNotFoundError(f"Missing extension asset: {fn}")

    # =========================================================================
    # 1. Chrome Web Store & Edge Add-ons Package (Strict Manifest V3)
    # =========================================================================
    chrome_manifest = manifest_data.copy()
    # Strip Firefox/Gecko specific keys and development public key
    chrome_manifest.pop("browser_specific_settings", None)
    chrome_manifest.pop("key", None)

    chrome_zip_path = os.path.join(out_dir, f"FalconDM-Chrome-WebStore-v{version}.zip")
    with zipfile.ZipFile(chrome_zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(chrome_manifest, indent=2))
        for fn in common_files:
            z.write(os.path.join(ext_dir, fn), arcname=fn)
    print(f"  ✓ Created: dist_extension/FalconDM-Chrome-WebStore-v{version}.zip ({os.path.getsize(chrome_zip_path)} bytes)")

    # =========================================================================
    # 2. Firefox Add-ons (AMO) Package (Gecko Manifest V3)
    # =========================================================================
    firefox_manifest = manifest_data.copy()
    firefox_manifest.pop("key", None)
    if "browser_specific_settings" not in firefox_manifest:
        firefox_manifest["browser_specific_settings"] = {
            "gecko": {
                "id": "falcondm-turbo@falcondm.local",
                "strict_min_version": "109.0"
            }
        }
    # Firefox MV3 supports background.scripts or background.service_worker
    if "background" in firefox_manifest and "service_worker" in firefox_manifest["background"]:
        sw = firefox_manifest["background"]["service_worker"]
        firefox_manifest["background"] = {
            "scripts": [sw]
        }

    firefox_zip_path = os.path.join(out_dir, f"FalconDM-Firefox-AMO-v{version}.zip")
    with zipfile.ZipFile(firefox_zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(firefox_manifest, indent=2))
        for fn in common_files:
            z.write(os.path.join(ext_dir, fn), arcname=fn)
    print(f"  ✓ Created: dist_extension/FalconDM-Firefox-AMO-v{version}.zip ({os.path.getsize(firefox_zip_path)} bytes)")

    # =========================================================================
    # 3. Store Submission Guide
    # =========================================================================
    guide_path = os.path.join(out_dir, "SUBMISSION_GUIDE.md")
    guide_content = f"""# 🌐 FalconDM Browser Extension - Store Submission Guide (v{version})

This folder contains pre-packaged, validated extension zip bundles ready for submission to browser web stores.

---

### 1. Google Chrome Web Store
- **Package:** `FalconDM-Chrome-WebStore-v{version}.zip`
- **Dashboard:** [https://chrome.google.com/webstore/devconsole/](https://chrome.google.com/webstore/devconsole/)
- **Instructions:**
  1. Click **New Item** and upload `FalconDM-Chrome-WebStore-v{version}.zip`.
  2. Categories: **Productivity** / **Workflow & Planning**.
  3. Single Purpose: *"High-speed download accelerator integration and web media grabber for FalconDM desktop app."*
  4. Privacy Policy: State that no personal data is collected or transmitted outside `http://127.0.0.1:9666` (local desktop bridge).

---

### 2. Mozilla Firefox Add-ons (AMO)
- **Package:** `FalconDM-Firefox-AMO-v{version}.zip`
- **Dashboard:** [https://addons.mozilla.org/developers/addon/submit/distribution](https://addons.mozilla.org/developers/addon/submit/distribution)
- **Instructions:**
  1. Choose *"On this site"* (Listed).
  2. Upload `FalconDM-Firefox-AMO-v{version}.zip`.
  3. Firefox automatically validates the manifest and gecko ID.

---

### 3. Microsoft Edge Add-ons
- **Package:** `FalconDM-Chrome-WebStore-v{version}.zip` (Edge supports Chrome MV3 format directly)
- **Dashboard:** [https://partner.microsoft.com/dashboard/microsoftedge](https://partner.microsoft.com/dashboard/microsoftedge)
- **Instructions:**
  1. Click **Create new extension** and upload the zip.

---

### 4. Local Developer Mode (Load Unpacked - 100% Free)
Users can always load the `browser_extension` folder directly in Developer Mode with zero store submission fees!
"""
    with open(guide_path, "w", encoding="utf-8") as f:
        f.write(guide_content)
    print(f"  ✓ Created: dist_extension/SUBMISSION_GUIDE.md")
    print(f"🎉 All extension packages generated successfully in dist_extension/!")

if __name__ == "__main__":
    build_extension_packages()
