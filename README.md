# 幺爆导演台 · 单机开源版

<img src="assets/fox-desktop-white.png" alt="幺爆导演台狐狸 LOGO" width="112">

面向短剧、漫剧与带货视频的 Windows 桌面制作工具。黑色主题，项目和素材保存在本机；由操作者逐步确认、点击生成，不会打开软件就自动调用付费模型。

**问题咨询：微信 `tk98555`。** 也欢迎在 GitHub Issues 提交问题；请勿附带 API 密钥或私人项目数据。

**[下载 Windows 单机版](https://github.com/nicky123066-cpu/yaobao-director/releases/latest)** · 解压整个目录后双击“幺爆导演台.exe”。源码运行方法见下文。

## 可以做什么

- 故事台：新建项目、编辑剧本、手动改写。
- 资产台：提取角色/场景、管理参考图、生成与选择资产图版本。
- 分镜台：编译镜头、调整动作/时长/提示词、生成首帧和动态镜头。
- 配音台：生成、试听与调整台词配音。
- 合成导出：预览并导出 MP4、SRT 与项目素材。
- 带货视频：导入真人实拍或商品图片，编排字幕、配音与成片。
- 任务中心：查看进度、暂停/恢复、失败重试、用量台账与预算。
- 模型与设置：按文本、图片、视频用途分别配置供应商和模型。

单机版不包含 Yabo 的微信接管、客户管理、公司账号会员后台或自动发布。人物照片数字人口播与精确口型生成尚未接入。

## 制作流程

**剧本 → 角色/场景 → 分镜 → 首帧 → 配音 → 动态镜头（可选）→ 合成与导出**

每次点击只执行当前阶段。重新打开软件时，上次未完成任务保持暂停，需要手动核对后继续。未配置云模型时可以使用本地示意画面做预演；本地示意画面不代表真实 AI 生图。

## 从源码运行

需要 Windows 10/11、Python 3.12、Node.js 22 LTS、Edge WebView2，以及 Microsoft Visual C++ 2015–2022 运行库。

在仓库根目录使用 PowerShell：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd ui
npm ci
npm run build
cd ..
.\.venv\Scripts\python.exe director_desktop.py
```

前端构建产物会同步到 `runtime/static`。启动后创建空项目库，项目与配置默认保存到仓库根目录 `data/`，不含个人配置、演示项目或历史数据库。

可以指定独立数据目录：

```powershell
.\.venv\Scripts\python.exe director_desktop.py --data "D:\YaobaoProjects"
```

不要将 Yabo 正在管理的数据目录直接用于单机版。

## 模型配置

1. 打开“模型与设置”，分别选择文本、图片、视频用途的供应商。
2. 填写供应商官方 API 地址、实际可用的模型 ID，保存对应 API Key。
3. 检查连接与预算，再开启真实生成。
4. 回到当前制作步骤，手动点击生成并核对结果。

界面包含 DeepSeek、火山方舟等预设；动态镜头沿用即梦 Seedance 2.5 预设。**模型名称、可用性、权限和费用以供应商账号实际支持为准**，可以在界面修改。本软件不附赠 API 额度。

Windows 下的 API Key 使用当前用户 DPAPI 加密保存，换电脑或 Windows 用户后需要重新填写。不要提交 `data/`、`.env`、`*.dpapi` 或自己的媒体素材。

## Windows 打包

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\scripts\build_windows.ps1
```

程序输出到 `dist/YaobaoDirector/幺爆导演台.exe`。运行时保留整个输出目录，不能只复制 EXE。FFmpeg 作为独立命令行进程运行，打包脚本会从安装的 `imageio-ffmpeg` 依赖复制对应可执行文件和许可证。

## 测试

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest tests -q
cd ui
npm run build
```

本地完整制作检查（Windows，生成示意 MP4，不调用云模型）：

```powershell
.\.venv\Scripts\python.exe scripts/check_manual_flow.py
```

## 文档

- [操作流程](docs/幺爆导演台操作流程.md)
- [模型配置培训](docs/模型配置培训流程.md)
- [业务制作、操作流程与模型清单](docs/业务制作、操作流程与模型清单.md)
- [第三方组件说明](THIRD_PARTY_NOTICES.md)

## 开源协议与咨询

应用源码使用 [MIT License](LICENSE)，第三方组件保留各自许可证。FFmpeg 是独立可执行程序，其具体构建可能适用 GPL/LGPL 等许可，分发时需保留对应许可及源码获取信息。

**问题咨询：微信 `tk98555`。**
