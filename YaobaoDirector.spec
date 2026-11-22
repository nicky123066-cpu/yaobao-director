# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_all,collect_data_files

ROOT=Path(SPECPATH)
datas=[(str(ROOT/'runtime/static'),'runtime/static'),(str(ROOT/'runtime/vendor'),'runtime/vendor'),(str(ROOT/'assets'),'assets')]
datas += [(str(p),'runtime') for p in (ROOT/'runtime').glob('*.ps1')]
datas += collect_data_files('webview')
binaries=[]
hiddenimports=['webview.platforms.winforms','webview.platforms.edgechromium','webview.platforms.win32','win32timezone','win32gui','win32process']
for name in ['pythonnet','clr_loader']:
    d,b,h=collect_all(name);datas+=d;binaries+=b;hiddenimports+=h
a=Analysis([str(ROOT/'director_desktop.py')],pathex=[str(ROOT),str(ROOT/'runtime')],binaries=binaries,datas=datas,
           hiddenimports=hiddenimports,hookspath=[],hooksconfig={},runtime_hooks=[],
           excludes=['uiautomation','wxreply','tkinter','pytest','PyInstaller','numpy','matplotlib'],noarchive=False,optimize=0)
# This installation uses the existing Microsoft C++ runtime in System32.
# Do not overwrite or duplicate a protected machine runtime DLL.
for dll in ['vcruntime140.dll','vcruntime140_1.dll']:
    if (Path('C:/Windows/System32')/dll).is_file():
        a.binaries=[row for row in a.binaries if Path(row[0]).name.casefold()!=dll]
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='幺爆导演台',debug=False,bootloader_ignore_signals=False,
        strip=False,upx=False,console=False,disable_windowed_traceback=False,icon=str(ROOT/'assets/app.ico'),version=str(ROOT/'version_info.txt'))
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='YaobaoDirector')
