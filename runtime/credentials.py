"""Current-user Windows DPAPI storage. Only encrypted bytes are written to disk."""
import ctypes
import json
import os
from pathlib import Path
from threading import RLock

_LOCK=RLock()


def supported():
    return os.name=="nt"


def _crypt(raw, decrypt=False):
    if not supported():
        raise ValueError("此系统未提供 Windows 加密存储，请使用服务端环境变量配置密钥")
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_=[("size",wintypes.DWORD),("data",ctypes.POINTER(ctypes.c_ubyte))]
    crypt32=ctypes.WinDLL("crypt32",use_last_error=True)
    kernel32=ctypes.WinDLL("kernel32",use_last_error=True)
    method=crypt32.CryptUnprotectData if decrypt else crypt32.CryptProtectData
    method.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
    method.restype=wintypes.BOOL
    kernel32.LocalFree.argtypes=[ctypes.c_void_p];kernel32.LocalFree.restype=ctypes.c_void_p
    buffer=ctypes.create_string_buffer(raw)
    source=Blob(len(raw),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte)))
    output=Blob()
    if not method(ctypes.byref(source),None,None,None,None,1,ctypes.byref(output)):
        raise ValueError("无法读取本机加密密钥，请确认仍由原 Windows 用户运行工作台")
    try:return ctypes.string_at(output.data,output.size)
    finally:kernel32.LocalFree(output.data)


class CredentialStore:
    def __init__(self, root):
        self.path=Path(root)/"model-credentials.dpapi"

    def _load(self):
        if not self.path.is_file():return {}
        raw=self.path.read_bytes()
        if len(raw)>256*1024:raise ValueError("本机密钥文件大小异常，未读取")
        try:
            value=json.loads(_crypt(raw,decrypt=True))
            if not isinstance(value,dict):raise ValueError()
            return value
        except (OSError,ValueError,TypeError):
            raise ValueError("本机密钥存储无法解密，请使用原 Windows 账号，或暂用环境变量连接") from None

    def get(self, name):
        with _LOCK:return self._load().get(name)

    def set(self, name, secret):
        if not isinstance(secret,str) or not 8<=len(secret)<=16384 or any(ord(c)<33 or ord(c)>126 for c in secret):
            raise ValueError("API Key 需为 8–16384 个可打印字符，不能包含空格或换行")
        with _LOCK:
            values=self._load();values[name]=secret
            encrypted=_crypt(json.dumps(values,ensure_ascii=False).encode())
            self.path.parent.mkdir(parents=True,exist_ok=True)
            temporary=self.path.with_suffix(".tmp")
            temporary.write_bytes(encrypted)
            os.replace(temporary,self.path)


def read_key(root, name):
    if root is None:return None
    try:return CredentialStore(root).get(name)
    except (ValueError,OSError):return None
