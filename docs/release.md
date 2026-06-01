# MediaMark 发布和分发方案

本文档说明 MediaMark 使用 Python 作为 CLI 实现语言时，后续如何分发给不同类型的用户。

## 分发目标

MediaMark 的分发分三类用户：

1. 开发者和早期用户：能接受 GitHub、`uv`、命令行环境。
2. 普通 CLI 用户：希望一条命令安装，不关心项目源码。
3. 非技术用户：希望下载可执行文件或使用图形化界面。

不同阶段使用不同分发方式，不需要一开始就做所有渠道。

## 当前开发期

开发期推荐：

```bash
uv sync
uv run mediamark doctor
uv run mediamark run "https://www.bilibili.com/video/BV..." --dry-run
uv run mediamark run ./links.csv --dry-run --estimate-getnote
uv run mediamark platforms
uv run mediamark run "https://www.xiaohongshu.com/explore/..." --dry-run
uv run mediamark status --json
```

这种方式适合项目开发和本地验证。

## v0.x：Git 安装

早期未发布 PyPI 时，可以让用户直接从 Git 仓库安装。

推荐：

```bash
uv tool install git+https://github.com/<owner>/mediamark
```

备选：

```bash
pipx install git+https://github.com/<owner>/mediamark
```

适用场景：

- 内测。
- 小范围用户试用。
- 不想频繁发布 PyPI。

注意：

- 用户仍需有 Python 环境。
- 仍需单独安装 Get笔记 CLI。
- 如果仓库私有，用户需要配置 GitHub 权限。

## v0.4+：PyPI 发布

当 CLI 命令、配置、manifest 和文档稳定后，发布到 PyPI。

用户安装：

```bash
uv tool install mediamark
```

或：

```bash
pipx install mediamark
```

为什么推荐 `uv tool` / `pipx`：

- 它们会为 CLI 创建隔离环境。
- 不污染用户项目依赖。
- 安装后会暴露 `mediamark` 命令。

发布前检查：

```bash
uv build
uv publish
```

发布要求：

- `pyproject.toml` 中保留 console script：

```toml
[project.scripts]
mediamark = "mediamark.cli:app"
```

- README 有中文安装说明。
- `config.example.yaml` 与当前配置模型一致。
- 测试全量通过。

## v1.0：standalone binary

面向不想安装 Python 的用户，可以提供独立可执行文件。

候选方案：

- PyInstaller。
- Nuitka。
- Briefcase。

优先建议 PyInstaller，因为它上手快，适合 CLI。

目标产物：

```text
mediamark-macos-arm64
mediamark-macos-x64
mediamark-linux-x64
mediamark-windows-x64.exe
```

注意：

- 需要在对应系统上分别构建。
- 二进制体积会明显大于源码包。
- Get笔记 CLI 仍是外部依赖，不打包进 MediaMark。
- 用户首次运行时应做 preflight 检查。

建议命令：

```bash
mediamark doctor
```

`doctor` 应检查：

- Python/运行时信息。
- B 站 cookie 文件是否存在。
- `getnote` 是否在 PATH 中。
- Get笔记是否已登录。
- 输出目录是否可写。
- manifest 路径是否可写。

## Homebrew

macOS/Linux 稳定后可以提供 Homebrew tap：

```bash
brew tap <owner>/mediamark
brew install mediamark
```

Homebrew formula 可以选择：

- 从 PyPI 安装 Python 包。
- 下载 GitHub Release 中的 standalone binary。

推荐后者，用户体验更接近普通 CLI 工具。

## Windows 渠道

Windows 后续可以考虑：

- GitHub Release `.exe`。
- Scoop bucket。
- winget。

早期不建议投入太多，先保证 PyPI / uv tool 可用。

## GUI 产品分发

如果后续做图形化界面，建议分阶段：

1. 本地 Web UI：仍然通过 CLI 启动。
2. Tauri/Electron 桌面壳：调用本地 CLI 或本地服务。
3. 独立安装包：`.dmg`、`.exe`、`.AppImage`。

不建议在 CLI 还不稳定时直接做完整 GUI 分发。

## Get笔记 CLI 依赖策略

Get笔记 CLI 始终作为外部依赖：

```bash
npm install -g @getnote/cli
getnote auth
```

MediaMark 不打包 Get笔记 CLI，原因：

- Get笔记有自己的登录态和账号体系。
- 打包第三方 CLI 会增加升级和授权风险。
- 用户应显式知道何时会消耗 Get笔记额度。

MediaMark 应提供清晰错误：

```text
未找到 getnote CLI。
请先安装并登录：
  npm install -g @getnote/cli
  getnote auth
```

## 推荐版本节奏

### v0.1-v0.3

- GitHub 源码分发。
- `uv run` 本地开发。
- `uv tool install git+...` 内测。
- v0.3 开始支持 CSV / JSONL 批量输入、Get笔记 profiles、quota dry-run 和 manifest JSON 状态。

### v0.4-v0.6

- 发布 PyPI。
- 主推 `uv tool install mediamark`。
- 支持 `pipx install mediamark`。
- 增加 `mediamark doctor`。
- v0.4 增加平台 Adapter、抖音单链接实验支持和 `mediamark platforms` 能力矩阵。
- v0.5 增加小红书单链接实验支持、输出目录布局、collection index 和 Obsidian frontmatter。

### v1.0

- GitHub Release 附带 standalone binary。
- 发布 Homebrew tap。
- 完整中文 README。
- 独立配置文档和平台能力矩阵。

### v1.x

- Windows Scoop / winget。
- 本地 Web UI。
- 桌面 GUI 安装包。

## 发布前检查清单

每次发布前运行：

```bash
uv run pytest -q
uv run mediamark doctor
uv run mediamark run --help
uv run mediamark split-links --help
uv run mediamark run "BV1xx411c7mD" --dry-run
uv run mediamark split-links "BV1xx411c7mD"
uv run mediamark run ./links.csv --dry-run --estimate-getnote
uv run mediamark platforms
uv run mediamark run "https://www.xiaohongshu.com/explore/..." --dry-run
uv run mediamark status
uv run mediamark status --json
```

如果发布 standalone binary，还需要在目标平台验证：

```bash
./mediamark --help
./mediamark run "BV1xx411c7mD" --dry-run
./mediamark doctor
```

文档检查：

- README 中安装命令与当前发布渠道一致。
- `config.example.yaml` 可被当前版本加载。
- release notes 写明破坏性变更。
- Get笔记 CLI 仍标注为外部依赖。
- 免费账号流程说明为 `split-links` 拆分链接后手动转化并导出 Markdown，不再宣传 Web 浏览器全自动方案。

## 不建议的发布方式

短期不建议：

- 要求普通用户 `pip install` 到全局 Python。
- 把 Get笔记 CLI 打包进二进制。
- 在 CLI 未稳定时发布 GUI 安装包。
- 同时维护过多安装渠道。

优先把 PyPI、uv tool、standalone binary 三条路径做好。
