# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

ctk_datas = collect_data_files('customtkinter')

added_datas = [
    ('browser_extension', 'browser_extension'),
    ('assets', 'assets'),
    ('core/com.falcondm.downloader.json', 'core'),
    ('core/com.falcondm.downloader_firefox.json', 'core'),
    ('core/native_host.bat', 'core'),
    ('core/native_host.py', 'core'),
    ('register_native_host.bat', '.'),
    ('install_extension.bat', '.'),
    ('install_extension.ps1', '.'),
] + ctk_datas

hidden_imports = [
    'customtkinter',
    'pystray',
    'pystray._win32',
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'PIL.ImageTk',
    'PIL._imagingtk',
    'requests',
    'urllib3',
    'bs4',
    'queue',
    'threading',
    'subprocess',
    'ctypes',
    'http.server',
    'socketserver',
    'json',
    'core',
    'core.engine',
    'core.state_manager',
    'core.browser_bridge',
    'core.clipboard_watcher',
    'core.scheduler',
    'core.media_grabber',
    'core.torrent_engine',
    'core.converter',
    'core.credential_manager',
    'core.config_manager',
    'core.notifications',
    'core.tray_icon',
    'core.antivirus_scanner',
    'core.platform_utils',
    'core.site_grabber',
    'core.ai_engine',
    'core.logger',
    'core.host_resolvers',
    'core.hls_stream_grabber',
    'core.hasher',
    'core.debrid_resolver',
    'core.telegram_bot',
    'core.cloud_uploader',
    'core.playlist_grabber',
    'core.archive_unpacker',
    'core.bandwidth_scheduler',
    'core.duplicate_detector',
    'core.import_export',
    'core.webhook_notifier',
    'core.native_host',
    'gui',
    'gui.app',
    'gui.dialogs',
    'gui.download_window',
    'gui.drop_target',
    'gui.notifications_ui',
]

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=added_datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'numpy', 'scipy', 'pandas', 'torch',
        'lxml', 'bcrypt',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FalconDM',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico' if os.path.exists('assets/icon.ico') else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FalconDM',
)
