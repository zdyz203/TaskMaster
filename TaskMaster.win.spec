# -*- mode: python ; coding: utf-8 -*-
# Windows PyInstaller spec —— 生成 dist/TaskMaster/TaskMaster.exe 单目录。
# Build: pyinstaller TaskMaster.win.spec --noconfirm --clean

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('notify.py', '.'),
        ('hooks.example.json', '.'),
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
    # console=False —— GUI 程序不弹黑色控制台窗口
    console=False,
    disable_windowed_traceback=False,
    icon=None,
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
