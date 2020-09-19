# -*- mode: python -*-

block_cipher = None


a = Analysis(['/Users/marcos/PycharmProjects/myClientGui/src/main/python/main.py'],
             pathex=['/Users/marcos/PycharmProjects/myClientGui/target/PyInstaller'],
             binaries=[],
             datas=[],
             hiddenimports=[],
             hookspath=['/Users/marcos/PycharmProjects/myClientGui/venv/lib/python3.6/site-packages/fbs/freeze/hooks'],
             runtime_hooks=['/Users/marcos/PycharmProjects/myClientGui/target/PyInstaller/fbs_pyinstaller_hook.py'],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='myClientGUI',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=False,
          console=False , icon='/Users/marcos/PycharmProjects/myClientGui/target/Icon.icns')
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=False,
               name='myClientGUI')
app = BUNDLE(coll,
             name='myClientGUI.app',
             icon='/Users/marcos/PycharmProjects/myClientGui/target/Icon.icns',
             bundle_identifier=None)
