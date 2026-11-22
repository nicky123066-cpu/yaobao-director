"""An unpacked source checkout finds FFmpeg without the private vendor binary."""
from unittest.mock import patch
import sys
import types
import engine

def test_source_checkout_uses_installed_ffmpeg_dependency(tmp_path,monkeypatch):
    binary=tmp_path/'dependency-ffmpeg.exe'
    binary.write_bytes(b'fixture')
    monkeypatch.setattr(engine,'APP_ROOT',tmp_path)
    monkeypatch.delenv('MANJU_FFMPEG',raising=False)
    monkeypatch.setitem(sys.modules,'imageio_ffmpeg',types.SimpleNamespace(get_ffmpeg_exe=lambda:str(binary)))
    with patch.object(engine.shutil,'which',return_value=None):
        assert engine.ffmpeg_path()==str(binary)

def test_explicit_ffmpeg_selection_takes_precedence(tmp_path,monkeypatch):
    binary=tmp_path/'chosen-ffmpeg.exe'
    binary.write_bytes(b'fixture')
    monkeypatch.setenv('MANJU_FFMPEG',str(binary))
    monkeypatch.setitem(sys.modules,'imageio_ffmpeg',types.SimpleNamespace(get_ffmpeg_exe=lambda:(_ for _ in ()).throw(AssertionError('must not override user choice'))))
    assert engine.ffmpeg_path()==str(binary)
