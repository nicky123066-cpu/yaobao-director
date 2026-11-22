# Third-party components

- React / React DOM — MIT: https://github.com/facebook/react
- Lucide — ISC: https://github.com/lucide-icons/lucide
- Vite — MIT: https://github.com/vitejs/vite
- TypeScript — Apache-2.0: https://github.com/microsoft/TypeScript
- pywebview — BSD-3-Clause: https://github.com/r0x0r/pywebview
- pythonnet — MIT: https://github.com/pythonnet/pythonnet
- pywin32 — PSF: https://github.com/mhammond/pywin32
- imageio-ffmpeg — BSD-2-Clause: https://github.com/imageio/imageio-ffmpeg
- PyInstaller (build tool) — GPL-2.0 with exception: https://pyinstaller.org/en/stable/license.html

`npm ci` and `pip install` install the corresponding dependencies and their license files. This source repository does not include a prebuilt FFmpeg executable, Python runtime, Node.js runtime, personal project database, or API keys.

FFmpeg runs as a separate command-line process. When packaging a desktop distribution, check the actual FFmpeg binary's build/license (`ffmpeg -L` and `ffmpeg -buildconf`), preserve its notices, and provide corresponding source/build information required by that binary's license. The Windows packaging script copies the installed dependency's license material and records the FFmpeg build and version output. See https://ffmpeg.org/legal.html and https://github.com/imageio/imageio-ffmpeg for source/build information; the historical Gyan build notice is retained in `runtime/vendor/FFMPEG-LICENSE.txt` for reference only, not as a description of every installed FFmpeg build.

Concept SVG illustrations in `runtime/artwork.py` are project-generated artwork. No external fonts or downloaded artwork are bundled there.
