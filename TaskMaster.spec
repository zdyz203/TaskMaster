# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for macOS .app bundle.
# Build: pyinstaller TaskMaster.spec --noconfirm

import sys

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('hooks.example.macos.json', '.'),
        ('README.md', '.'),
    ],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'PyQt5.QtWebEngineCore',
        'PyQt5.QtWebEngineWidgets',
        'PyQt5.QtMultimedia',
        'PyQt5.QtMultimediaWidgets',
        'PyQt5.QtQml',
        'PyQt5.QtQuick',
        'PyQt5.QtSql',
        'PyQt5.QtTest',
        'PyQt5.QtBluetooth',
        'PyQt5.QtPositioning',
        'PyQt5.QtSerialPort',
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
    name='TaskMaster',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    target_arch='arm64',
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='TaskMaster',
)

app = BUNDLE(
    coll,
    name='TaskMaster.app',
    icon=None,
    bundle_identifier='com.local.taskmaster',
    info_plist={
        'CFBundleName': 'TaskMaster',
        'CFBundleDisplayName': 'TaskMaster',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleVersion': '1.0.0',
        # LSUIElement=true 让 app 不出现在 Dock，仅以菜单栏托盘形式存在 —
        # 这个项目本来就靠系统托盘控制，符合常驻浮窗的形态
        'LSUIElement': True,
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': False,
    },
)
