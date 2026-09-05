# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all

# Recolecta automáticamente TODOS los binarios, datos y módulos de pythonnet y webview
datas_pn, binaries_pn, hiddenimports_pn = collect_all('pythonnet')
datas_wv, binaries_wv, hiddenimports_wv = collect_all('webview')

a = Analysis(
    ['app_desktop.py'],
    pathex=[],
    binaries=binaries_pn + binaries_wv,
    datas=[('static', 'static')] + datas_pn + datas_wv,
    hiddenimports=hiddenimports_pn + hiddenimports_wv,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MenutronDAD',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='static/icono.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MenutronDAD',
)