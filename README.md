# MediaMark

MediaMark 是一个多平台媒体内容转 Markdown 的个人知识采集工具。当前第一个 CLI 版本先从 B 站开始：把视频字幕导出为本地 Markdown 文件；只有在视频没有可用 B 站字幕时，才会调用 Get笔记作为兜底。

v0.4 开始加入平台 Adapter 架构，并实验性支持抖音单链接。抖音不做站内字幕抓取，单链接会直接交给 Get笔记兜底；主页、合集、搜索页批量抓取暂不支持。

v0.5 继续增强多平台输出：实验性支持小红书单链接，增加输出目录模板、运行内去重、collection index，以及更适合 Obsidian 的 frontmatter。

v1 的行为是保守的：

- 优先尝试 B 站原字幕或 AI 字幕。
- 有 B 站字幕的视频会生成 `transcript_only` Markdown，`has_summary: false`，正文包含 `## 逐字稿`。
- 没有字幕的视频才会调用 Get笔记；Get笔记成功时生成 `note_plus_transcript` Markdown。
- Get笔记可能返回摘要、要点、大纲和逐字稿。B 站字幕只有逐字稿，所以 Markdown frontmatter 会用 `transcript_source`、`content_level`、`has_summary` 和 `sections` 如实标明文件内容。

## 文档

- [后续功能路线图](docs/roadmap.md)
- [发布和分发方案](docs/release.md)

## 安装

要求：

- Python 3.12+
- `uv`

安装项目依赖：

```bash
uv sync
```

在项目目录中运行 CLI：

```bash
uv run mediamark run "https://www.bilibili.com/video/BV..." --output ./output/transcripts
```

发布或批处理前可以先做本地诊断：

```bash
uv run mediamark doctor
```

## Get笔记兜底

Get笔记 CLI 是外部依赖，不会被打包进 MediaMark。

请单独安装并登录 Get笔记 CLI：

```bash
npm install -g @getnote/cli
getnote auth
```

需要兜底时，MediaMark 会调用：

```bash
getnote save <url> -o json
```

如果在 agent 工作流中使用本项目，也可以安装或启用对应的 Get笔记 skills。skills 可以帮助 agent 理解 Get笔记 CLI 和 JSON 输出；额度控制仍然依赖 `--dry-run`、`--no-getnote`、小批量验证和账号额度检查。

大批量运行前，建议先确认账号和额度可用：

```bash
getnote save "https://www.bilibili.com/video/BV..." -o json
```

如果只想使用 B 站字幕，不希望调用 Get笔记，请使用 `--no-getnote`：

```bash
uv run mediamark run "https://www.bilibili.com/video/BV..." --no-getnote
```

可以用配置限制本次运行最多调用多少次 Get笔记、最多兜底多少分钟视频：

```yaml
getnote:
  budget:
    max_fallbacks_per_run: 20
    max_minutes_per_run: 120
```

`null` 表示不限制。预算只影响 Get笔记兜底调用；有 B 站字幕的视频不会消耗 Get笔记预算。

需要隔离多个 Get笔记登录态或账号时，可以配置 profiles。MediaMark 会按顺序选择 enabled profile，并在 profile 预算耗尽时尝试下一个：

```yaml
getnote:
  profiles:
    - name: main
      enabled: true
      cli_path: "getnote"
      env:
        GETNOTE_HOME: "~/.config/getnote-main"
      budget:
        max_fallbacks_per_run: 20
        max_minutes_per_run: 120
    - name: backup
      enabled: true
      cli_path: "getnote"
      env:
        GETNOTE_HOME: "~/.config/getnote-backup"
      budget:
        max_fallbacks_per_run: 10
        max_minutes_per_run: 60
```

## 配置

默认配置足够完成第一次运行。需要自定义路径或行为时，可以复制并编辑示例配置：

```bash
cp config.example.yaml config.yaml
uv run mediamark run "BV1xx411c7mD" --config config.yaml
```

重要字段：

- `output_dir`：Markdown 文件输出目录。
- `manifest_path`：JSONL manifest 路径，用于断点续跑和跳过已完成项目。
- `bilibili.cookie_file`：可选的 B 站 cookie 文件路径。
- `bilibili.prefer_ai_subtitle`：有多个字幕时优先选择 AI 字幕。
- `bilibili.request_sleep_seconds`：B 站 API 请求后的等待时间。
- `bilibili.part_selection`：视频 URL 包含 `?p=N` 时的处理方式，`selected` 只处理指定分 P，`all` 处理全部分 P。
- `getnote.enabled`：是否启用 Get笔记兜底。
- `getnote.cli_path`：外部 `getnote` CLI 的可执行文件路径。
- `getnote.budget.max_fallbacks_per_run`：本次运行最多调用多少次 Get笔记。
- `getnote.budget.max_minutes_per_run`：本次运行最多使用 Get笔记兜底多少分钟视频。
- `getnote.profiles`：可选的 Get笔记 profile 列表，每个 profile 支持 `name`、`enabled`、`cli_path`、`env` 和独立 `budget`。
- `output.directory_template`：可选的输出子目录模板，例如 `{platform}/{collection}`。
- `archive.dedupe`：是否在同一运行中跳过重复内容。
- `archive.write_collection_index`：是否为 `collection` 生成索引 Markdown。
- `archive.collection_index_dir`：collection index 输出目录名。
- `limits.limit`：展开并排序后最多处理多少个视频。
- `markdown.filename_template`：输出文件名模板。

命令行参数会覆盖本次运行加载到的配置，例如 `--output`、`--limit` 和 `--no-getnote`。

## 输入类型

`mediamark run` 支持：

- 单个 B 站视频 URL。
- 单个抖音视频 URL。该能力是实验性的，需要启用 Get笔记兜底。
- 单个小红书笔记 URL。该能力是实验性的，需要启用 Get笔记兜底。
- 裸 BV 号，例如 `BV1xx411c7mD`。
- B 站 UP 主主页 URL。
- `mid:<number>` 形式的 UP 主 id，例如 `mid:123456`。
- B 站合集、列表或系列 URL。
- 文本文件路径。文件中每个非空行都可以是上述任意一种输入。
- CSV 文件路径，至少包含 `url` 列，可选 `platform`、`tags`、`collection`、`allow_getnote`。
- JSONL 文件路径，每行一个对象，可选字段同 CSV。

示例：

```bash
uv run mediamark run "https://www.bilibili.com/video/BV..."
uv run mediamark run "https://www.bilibili.com/video/BV...?p=2"
uv run mediamark run "https://www.bilibili.com/video/BV...?p=2" --part-selection all
uv run mediamark run "BV1xx411c7mD"
uv run mediamark run "https://space.bilibili.com/123456"
uv run mediamark run "mid:123456"
uv run mediamark run "https://space.bilibili.com/123456/lists/987654"
uv run mediamark run "https://www.douyin.com/video/..."
uv run mediamark run "https://www.xiaohongshu.com/explore/..."
uv run mediamark run ./links.txt
uv run mediamark run ./links.csv
uv run mediamark run ./links.jsonl
```

对于合集、UP 主主页和链接列表文件，MediaMark 会先展开为视频或分 P 记录，再应用排序和数量限制。

对于 B 站视频选集 URL，默认行为是：如果 URL 明确包含 `?p=N`，只处理该分 P；如果没有 `p` 参数，则处理该 BVID 的全部分 P。使用 `--part-selection all` 可以忽略 `?p=N` 并处理全部分 P。

CSV 示例：

```csv
url,platform,tags,collection,allow_getnote
https://www.bilibili.com/video/BV...,bilibili,"ai,course",ml,yes
https://www.douyin.com/video/...,douyin,"short,idea",shorts,yes
https://www.xiaohongshu.com/explore/...,xiaohongshu,"note,idea",inbox,yes
```

JSONL 示例：

```json
{"url":"BV1xx411c7mD","tags":["ai"],"allow_getnote":false}
{"url":"https://www.douyin.com/video/...","platform":"douyin","tags":["short"],"allow_getnote":true}
{"url":"https://www.xiaohongshu.com/explore/...","platform":"xiaohongshu","collection":"inbox","allow_getnote":true}
```

查看当前平台能力矩阵：

```bash
uv run mediamark platforms
uv run mediamark platforms --json
```

## 排序和数量限制

支持的排序模式：

- `source`：保持输入或上游展开顺序。
- `time-desc`：发布时间从新到旧。
- `time-asc`：发布时间从旧到新。
- `views-desc`：播放量从高到低。
- `views-asc`：播放量从低到高。

示例：

```bash
uv run mediamark run "https://space.bilibili.com/123456" --sort views-desc --limit 50
uv run mediamark run "mid:123456" --sort time-desc --limit 20
uv run mediamark run ./links.txt --sort source
```

`--limit` 会在输入展开和排序之后生效。

## 试运行

使用 `--dry-run` 可以只展开、排序、限制数量并打印选中的视频，不写 Markdown、不更新 manifest，也不调用 Get笔记：

```bash
uv run mediamark run "mid:123456" --sort views-desc --limit 10 --dry-run
```

如果想在试运行时估算需要调用多少次 Get笔记和多少分钟额度，可以加 `--estimate-getnote`：

```bash
uv run mediamark run ./links.csv --dry-run --estimate-getnote
```

## 跳过已完成

MediaMark 会把处理进度写入 `manifest.jsonl`。默认情况下，后续运行会跳过 manifest 中已经完成的项目：

```bash
uv run mediamark run ./links.txt --skip-existing
```

如果希望重新处理已经完成的项目，请使用 `--no-skip-existing`：

```bash
uv run mediamark run ./links.txt --no-skip-existing
```

## 状态、重试和诊断

查看 manifest 当前状态：

```bash
uv run mediamark status
```

输出机器可读 JSON：

```bash
uv run mediamark status --json
```

重跑失败项：

```bash
uv run mediamark retry-failed
```

只重跑指定错误码的失败项：

```bash
uv run mediamark retry-failed --error-code getnote_quota_exceeded
```

只打印将要重跑的失败 URL：

```bash
uv run mediamark retry-failed --dry-run
```

把异常中断留下的 `pending` 记录标记为 skipped：

```bash
uv run mediamark clean-pending
```

检查配置、输出目录、manifest 路径、B 站 cookie 和 Get笔记 CLI：

```bash
uv run mediamark doctor
```

`doctor` 只做本地检查，不请求 B 站接口，也不会消耗 Get笔记额度。

## 内容层级

Markdown frontmatter 会包含类似字段：

```yaml
transcript_source: "bilibili_subtitle"
content_level: "transcript_only"
has_summary: false
sections: ["transcript"]
```

内容层级：

- `transcript_only`：来自 B 站字幕。文档包含 `## 逐字稿`，`has_summary` 固定为 `false`。
- `note_plus_transcript`：来自 Get笔记兜底。文档可能包含 `## 摘要`、`## 要点`、`## 大纲` 和/或 `## 逐字稿`；当 Get笔记返回摘要、要点或大纲时，`has_summary` 为 `true`。

失败处理：

- `metadata_only` 是内部失败结果使用的内容层级。当前 v1 流水线中，失败项目会在 `manifest.jsonl` 中记录 `status: "failed"` 和错误信息，不会写出 metadata-only Markdown 文件。

逐字稿来源：

- `bilibili_subtitle`：B 站原字幕或 AI 字幕。
- `getnote`：Get笔记兜底结果。
- `failed`：内部失败处理结果。

## 输出文件名

默认文件名模板：

```yaml
markdown:
  filename_template: "{published_at}-{title}-{bvid}.md"
```

对于多 P 视频，P1 保持默认文件名。使用默认模板时，P2 及之后会在扩展名前自动追加 `-p{part_index}`。

如果希望按平台、作者或 collection 组织目录，可以设置：

```yaml
output:
  directory_template: "{platform}/{collection}"
```

开启 collection index 后，带 `collection` 的成功结果会写入：

```text
output/transcripts/_collections/<collection>.md
```

自定义模板可使用以下字段：

- `published_at`
- `title`
- `bvid`
- `id`
- `external_id`
- `platform`
- `owner`
- `collection`
- `part_index`
- `part_title`

示例：

```yaml
markdown:
  filename_template: "{published_at}-{title}-p{part_index}-{part_title}-{bvid}.md"
```

使用自定义模板时，如果希望多 P 视频文件名互不覆盖，请自行包含 `part_index` 或 `part_title`。

## Obsidian 友好字段

Markdown frontmatter 会包含平台、标签和合集字段，便于 Obsidian 检索：

```yaml
platform: "bilibili"
tags:
  - "bilibili"
  - "course"
collections:
  - "机器学习"
```

`tags` 会自动包含平台名，并追加 CSV / JSONL 中提供的标签。
