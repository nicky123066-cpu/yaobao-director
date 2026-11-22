"""Prepare an installed FFmpeg dependency for a portable Windows build."""
from importlib import metadata
from pathlib import Path
import shutil
import subprocess
import imageio_ffmpeg

ROOT=Path(__file__).resolve().parents[1]

def main():
    source=Path(imageio_ffmpeg.get_ffmpeg_exe()).resolve()
    target=ROOT/'runtime/vendor'
    target.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,target/source.name)
    dist=metadata.distribution('imageio-ffmpeg')
    for file in dist.files or []:
        if 'license' in file.name.lower() and file.suffix.lower() in {'','.txt','.md'}:
            path=Path(dist.locate_file(file))
            if path.is_file():shutil.copy2(path,target/('imageio-'+path.name))
    notices=[]
    for flag in ['-version','-L','-buildconf']:
        result=subprocess.run([str(source),flag],capture_output=True,text=True,errors='replace',check=True,timeout=30,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        notices.append(result.stdout+'\n'+result.stderr)
    (target/'INSTALLED-FFMPEG-NOTICE.txt').write_text('\n\n'.join(notices),'utf-8')
    print('Prepared FFmpeg and installed dependency notices for packaging.')

if __name__=='__main__':main()
