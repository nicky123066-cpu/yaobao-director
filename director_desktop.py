"""幺爆导演台 native desktop entry: one process, no Yabo/WeChat/UIA dependency."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ASSETS=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))
RUNTIME=ASSETS/'runtime'
os.environ['MANJU_RUNTIME_ROOT']=str(RUNTIME)
sys.path.insert(0,str(RUNTIME))
from store import Store
from desktop_core import serve,shutdown


def atomic(path,value):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),'utf-8');temp.replace(path)


class Instance:
    """A kernel mutex is released by Windows even after a crash; no stale file lock."""
    def __init__(self,workspace):
        self.handle=None;self.existing=False;self.workspace=workspace
        if sys.platform=='win32':
            from ctypes import wintypes
            kernel=ctypes.WinDLL('kernel32',use_last_error=True)
            kernel.CreateMutexW.argtypes=[ctypes.c_void_p,wintypes.BOOL,wintypes.LPCWSTR]
            kernel.CreateMutexW.restype=wintypes.HANDLE
            name='Local\\YaobaoDirector.Manual.'+hashlib.sha256(str(workspace).casefold().encode()).hexdigest()[:24]
            self.handle=kernel.CreateMutexW(None,False,name)
            if not self.handle:raise ctypes.WinError(ctypes.get_last_error())
            self.existing=ctypes.get_last_error()==183
    def close(self):
        if self.handle:
            from ctypes import wintypes
            kernel=ctypes.WinDLL('kernel32');kernel.CloseHandle.argtypes=[wintypes.HANDLE];kernel.CloseHandle(self.handle);self.handle=None
    def focus(self):
        import win32gui,win32process
        record=self.workspace/'desktop-instance.json'
        for _ in range(100):
            try:
                info=json.loads(record.read_text('utf-8'));hwnd=int(info['hwnd'])
                if win32gui.IsWindow(hwnd) and win32process.GetWindowThreadProcessId(hwnd)[1]==info['pid']:
                    win32gui.ShowWindow(hwnd,9)
                    try:win32gui.SetForegroundWindow(hwnd)
                    except Exception:win32gui.FlashWindow(hwnd,True)
                    return True
            except (OSError,ValueError,KeyError):pass
            time.sleep(.1)
        return False


def main():
    parser=argparse.ArgumentParser(description='幺爆导演台 · 手动制作桌面版')
    parser.add_argument('--data',type=Path)
    parser.add_argument('--headless',action='store_true')
    parser.add_argument('--status-file',type=Path)
    args=parser.parse_args()
    base=Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).parent
    workspace=(args.data or base/'data').resolve();workspace.mkdir(parents=True,exist_ok=True)
    if (workspace/'.yabo-gateway.json').exists():raise ValueError('请使用独立项目库，不能直接打开正在受Yabo管理的数据库。')
    instance=Instance(workspace)
    if instance.existing:
        try:
            if not instance.focus():raise RuntimeError('幺爆导演台已运行，但窗口尚未就绪，请稍候。')
            return 0
        finally:instance.close()
    server=None;engine=None
    try:
        store=Store(workspace,seed=False)
        server,engine,url,paused=serve(store)
        status={'product':'yaobao-director-desktop','version':'1.0.0','pid':os.getpid(),'port':server.server_port,'workspace':str(workspace),'manual_only':True,'startup_paused_jobs':paused}
        if args.status_file:atomic(args.status_file,status)
        if args.headless:
            try:
                while True:time.sleep(.5)
            except KeyboardInterrupt:pass
            return 0
        # WebView2 lives directly on this process' STA thread. No UIA initialization.
        import webview
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('Yaobao.Director.Manual.Desktop')
        webview.settings['ALLOW_DOWNLOADS']=True
        webview.settings['OPEN_EXTERNAL_LINKS_IN_BROWSER']=True
        webview.settings['ALLOW_FILE_URLS']=False
        window=webview.create_window('幺爆导演台',url,width=1360,height=920,min_size=(1040,720),background_color='#08090b',text_select=True)
        def shown():
            hwnd=int(window.native.Handle.ToInt64())
            try:
                from ctypes import wintypes
                dwm=ctypes.WinDLL('dwmapi');dark=wintypes.BOOL(True)
                dwm.DwmSetWindowAttribute.argtypes=[wintypes.HWND,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD]
                dwm.DwmSetWindowAttribute(hwnd,20,ctypes.byref(dark),ctypes.sizeof(dark))
            except OSError:pass
            atomic(workspace/'desktop-instance.json',{**status,'hwnd':hwnd})
        def closing():
            with store.connection() as db:active=db.execute("SELECT COUNT(*) FROM jobs WHERE state IN ('PENDING','RUNNING')").fetchone()[0]
            if active and ctypes.windll.user32.MessageBoxW(None,'当前制作任务会暂停。已提交的云端视频可能继续计费，下次请到任务中心手动核对。确定退出？','幺爆导演台',0x24)!=6:return False
            return True
        window.events.shown+=shown;window.events.closing+=closing
        webview.start(gui='edgechromium',icon=str(ASSETS/'assets/app.ico'),private_mode=False,storage_path=str(workspace/'webview-profile'),debug=False)
        return 0
    finally:
        if server:shutdown(server,engine)
        record=workspace/'desktop-instance.json'
        try:
            if record.exists() and json.loads(record.read_text('utf-8'))['pid']==os.getpid():record.unlink()
        except (OSError,ValueError,KeyError):pass
        instance.close()


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as exc:
        error=Path(sys.executable).parent/'startup-error.txt' if getattr(sys,'frozen',False) else Path(__file__).parent/'validation/startup-error.txt'
        import traceback
        error.write_text(traceback.format_exc(),'utf-8')
        if sys.platform=='win32':ctypes.windll.user32.MessageBoxW(None,'导演台启动失败：'+str(exc)+'\n详情：'+str(error),'幺爆导演台',0x10)
        raise
