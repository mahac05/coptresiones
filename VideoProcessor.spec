# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec для Видео Обработчика.

Сборка:
    pyinstaller VideoProcessor.spec

Результат:
    dist/VideoProcessor.exe
"""

import os

block_cipher = None

# FFmpeg бинарники — включаем рядом с exe
ffmpeg_dir = os.path.join('resources', 'ffmpeg')
ffmpeg_bins = []
for name in ('ffmpeg.exe', 'ffprobe.exe'):
    path = os.path.join(ffmpeg_dir, name)
    if os.path.exists(path):
        ffmpeg_bins.append((path, '.'))  # кладём в корень рядом с exe

a = Analysis(
    ['app_pyqt.py'],
    pathex=[],
    binaries=ffmpeg_bins,
    datas=[('resources/icon.ico', 'resources')],
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'psutil',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'scipy',
        'pandas',
        'PIL',
        'cv2',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='VideoProcessor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # без консоли (GUI)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resources\\icon.ico',  # иконка приложения
)
