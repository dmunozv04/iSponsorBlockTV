# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import exec_statement
cert_datas = exec_statement("""
    import ssl
    print(ssl.get_default_verify_paths().cafile)""").strip().split()
cert_datas = [(f, 'lib') for f in cert_datas]

block_cipher = None

options = [ ('u', None, 'OPTION') ]

a = Analysis(['main-macos.py'],
             pathex=[],
             binaries=[],
             datas=cert_datas,
             hiddenimports=['certifi'],
             hookspath=[],
             hooksconfig={},
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,  
          [],
          options,
          name='iSponsorBlockTV-macos',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=True,
          disable_windowed_traceback=False,
          target_arch=None,
          codesign_identity=None,
          entitlements_file=None)