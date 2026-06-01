# MediaMark 后续功能路线图

本文档记录 MediaMark 在第一个 CLI 版本之后的功能规划。排序原则是：先补齐 B 站核心语义和批处理安全性，再扩展到多平台，最后增强 GUI、发布和商业化体验。

## 产品方向

MediaMark 的长期目标不是只做 B 站字幕下载器，而是成为一个个人知识采集工具：

```text
视频 / 图文 / 文章链接
  -> 识别平台和内容结构
  -> 优先使用平台已有文本或字幕
  -> 必要时调用 Get笔记或其他转写能力
  -> 生成结构化 Markdown
  -> 支持批处理、断点续跑、失败重试和额度控制
```

当前 v1 的核心策略仍然保留：**B 站字幕优先，Get笔记 CLI 兜底**。后续新增能力不能破坏这一点。

免费账号不再提供基于浏览器的全自动 Get笔记流程。对于可展开为多个视频的 B 站输入，优先提供 `split-links` 只拆分链接；后续转化和 Markdown 导出由用户自行完成。

## P0：下一版优先实现

### 1. B 站指定分 P 处理

当前能力偏向于“给一个 BVID，展开所有分 P”。后续需要支持 B 站视频选集链接：

```text
https://www.bilibili.com/video/BV...?p=2
```

需要补齐：

- 识别 URL 中的 `p` 参数。
- 支持只处理指定分 P。
- dry-run 中显示 `P1`、`P2` 等分 P 信息。
- 配置默认行为：
  - `selected_part_only`：只处理 URL 指定分 P。
  - `all_parts`：处理同一 BVID 的所有分 P。

推荐默认：如果 URL 明确包含 `p`，则只处理指定分 P；如果没有 `p`，则处理全部分 P。

### 2. Get笔记额度预算保护

Get笔记会员版和 CLI 可用账号都有额度限制，因此在支持账号池之前，应该先支持预算控制，避免一次批处理耗尽额度。

建议配置：

```yaml
getnote:
  enabled: true
  budget:
    max_fallbacks_per_run: 20
    max_minutes_per_run: 120
    stop_when_quota_unknown: true
```

需要支持：

- dry-run 估算哪些视频可能需要 Get笔记。
- 超过本次预算时停止处理或提示用户。
- Get笔记额度未知时是否继续，由配置控制。
- manifest 中记录 Get笔记 fallback 次数和失败原因。

### 3. 失败重试和状态命令

批量处理时，失败是常态。需要把失败处理从“记录错误”升级为“可操作的任务队列”。

建议新增命令：

```bash
mediamark status
mediamark retry-failed
mediamark clean-pending
```

需要支持的错误分类：

- `no_subtitle`
- `getnote_disabled`
- `getnote_quota_exceeded`
- `getnote_auth_failed`
- `network_error`
- `platform_parse_error`
- `subtitle_parse_error`

### 4. 发布方案文档

需要维护独立发布文档，见 [release.md](./release.md)。

下一版至少要说明：

- 本地开发安装方式。
- Git 安装方式。
- PyPI / pipx / uv tool 分发计划。
- standalone binary 的打包计划。
- Get笔记 CLI 仍是外部依赖。

## P1：批处理规模化

### 5. Get笔记账号池 / profile

账号池不应该被设计成“绕过免费额度限制”的能力，而应定义为：允许用户配置多个自己合法拥有的 Get笔记账号/profile，并按照健康状态、预算和失败次数选择可用 profile。

建议配置形态：

```yaml
getnote:
  accounts:
    - name: main
      cli_path: getnote
      env:
        GETNOTE_HOME: "~/.config/getnote-main"
    - name: backup
      cli_path: getnote
      env:
        GETNOTE_HOME: "~/.config/getnote-backup"
```

实现前需要先验证 Get笔记 CLI 是否支持 profile 或可通过环境变量隔离登录态。如果 CLI 不支持，应先只做文档说明和单账号预算控制。

需要支持：

- 每个账号/profile 的启用状态。
- 每个账号/profile 的失败次数和冷却时间。
- 额度不足时切换到下一个可用账号。
- 所有自动切换都写入 manifest 或日志，便于审计。

### 6. 输入源 Adapter 架构

多平台前必须先抽象输入源，避免把 B 站、抖音、小红书、公众号逻辑塞进一个 client。

建议抽象：

```text
InputResolver
  -> BilibiliResolver
  -> DouyinResolver
  -> XiaohongshuResolver
  -> WeChatResolver

Extractor
  -> SubtitleExtractor
  -> GetnoteExtractor
  -> LocalTranscriber

Renderer
  -> MarkdownRenderer
```

统一中间模型：

```text
ExtractedItem
  platform
  url
  canonical_url
  title
  author
  published_at
  view_count
  duration_seconds
  part_index
  part_title
  transcript_candidates
```

### 7. 批量输入增强

当前链接列表文件只支持每行一个链接。后续建议支持 CSV / JSONL：

```csv
url,platform,tags,collection,allow_getnote
https://www.bilibili.com/video/BV...,bilibili,"ai,course",ml,yes
```

用途：

- 给不同链接设置标签。
- 控制是否允许 Get笔记兜底。
- 指定输出目录或 collection。
- 支持更清晰的批处理审计。

## P1：多平台支持

### 8. 抖音视频

优先支持单条公开视频链接，不建议第一版就做主页批量抓取。

第一阶段能力：

- 识别抖音单视频 URL。
- 提取标题、作者、发布时间等基础元数据，能取多少取多少。
- 优先交给 Get笔记处理。
- dry-run 中明确标记平台为 `douyin`。

风险：

- 登录态和风控复杂。
- 链接可能有短链、跳转和时效参数。
- 不建议在 CLI 初期做大规模自动抓取。

### 9. 小红书视频 / 笔记

小红书比抖音更复杂，图文混排、登录态和反爬限制都更明显。

第一阶段能力：

- 支持单条笔记 URL。
- 能提取公开标题、正文、作者时优先保存为 Markdown。
- 视频内容优先走 Get笔记或后续转写能力。
- 批量主页/搜索采集暂不做。

风险：

- 自动化访问可能触发风控。
- 内容不一定是纯视频，可能是图文笔记。
- 需要明确合规和个人使用边界。

### 10. 公众号文章 / 视频

公众号更适合先做“文章转 Markdown”，视频只是文章中的嵌入资源。

第一阶段能力：

- 支持公众号文章 URL。
- 提取标题、公众号名称、发布时间、正文。
- 保留图片和视频占位链接。
- 如果文章内视频可交给 Get笔记处理，则作为附加 transcript。

优先级高于小红书批量抓取，因为文章转 Markdown 与 MediaMark 的输出模型更接近。

### 11. 平台能力矩阵

多平台支持必须有能力矩阵，避免用户误以为所有平台都有同等能力。

示例：

| 平台 | 单链接 | 批量 | 原字幕/正文优先 | Get笔记兜底 | 状态 |
|---|---:|---:|---:|---:|---|
| B 站 | 是 | 是 | 是 | 是 | 稳定 |
| 抖音 | 是 | 否 | 部分 | 是 | 实验 |
| 小红书 | 是 | 否 | 部分 | 是 | 实验 |
| 公众号 | 是 | 文件批量 | 是 | 部分 | 实验 |

## P2：产品体验增强

### 12. 额度 dry-run

dry-run 应从“预览视频列表”升级为“预估执行成本”。

需要显示：

- 本次会处理多少条。
- 已有字幕多少条。
- 预计需要 Get笔记多少条。
- 预计总时长。
- 是否超过预算。
- 将使用哪个 Get笔记账号/profile。

### 13. 输出目录布局

支持按平台、作者、合集、日期组织文件：

```yaml
output:
  layout: "{platform}/{owner}/{published_at}-{title}-{id}.md"
```

注意这会影响当前 `markdown.filename_template`，需要决定是保留单一模板，还是拆为 `directory_template` 和 `filename_template`。

### 14. 去重和归档

同一个视频可能来自多个合集、UP 主主页或链接文件。

需要支持：

- 基于 canonical URL / BVID / 平台 ID 去重。
- 同一内容只处理一次。
- manifest 记录它出现在哪些输入源中。
- 可选生成 collection index 文件。

### 15. Obsidian 友好输出

增强 frontmatter：

```yaml
tags:
  - bilibili
  - course
collections:
  - "某课程合集"
platform: "bilibili"
```

后续可以支持：

- Obsidian vault 输出目录。
- wikilink。
- Bases 字段约定。
- collection index 页面。

### 16. 本地转写兜底

Get笔记额度不足时，可以考虑本地 Whisper 或其他转写服务。

不建议过早实现，因为它会显著增加依赖、模型下载、GPU/CPU 性能和分发复杂度。

## P3：GUI 和商业化前准备

### 17. 本地 Web UI

在桌面 GUI 前，优先做本地 Web UI：

- 任务列表。
- dry-run 预览。
- 失败重试。
- 账号/profile 状态。
- 额度预算状态。
- 输出目录配置。

本地 Web UI 可以先复用 Python 后端，后续再考虑 Tauri 或 Electron 包装。

### 18. 图形化桌面产品

当 CLI 任务队列、账号/profile、额度 dry-run、多平台 adapter 稳定后，再做桌面端。

候选技术：

- Tauri + Web 前端 + Python 后端/CLI。
- Electron + TypeScript + Python CLI。
- 全 TypeScript 重写，仅在分发痛点很明确时考虑。

### 19. 合规和风险说明

多平台后必须有单独合规说明：

- 仅处理用户有权访问的内容。
- 尊重平台规则和内容版权。
- 登录态自动化存在账号风险。
- 不鼓励绕过平台限制或批量抓取非授权内容。

## 版本节奏建议

### v0.2：B 站批处理补强

- B 站指定分 P。
- Get笔记预算保护。
- 失败重试和状态命令。
- 发布方案文档和 `doctor` 本地诊断命令。

具体执行计划见 [MediaMark v0.2 B 站批处理补强执行计划](./superpowers/plans/2026-05-31-v0.2-bilibili-batch-hardening.md)。

### v0.3：Get笔记规模化

- Get笔记 profile/env 设计和验证。
- quota dry-run。
- manifest JSON 状态和错误码。
- CSV / JSONL 批量输入。

具体执行计划见 [MediaMark v0.3 Get笔记规模化执行计划](./superpowers/plans/2026-05-31-v0.3-getnote-scaling.md)。

### v0.4：多平台 Adapter

- 输入源 Adapter 架构。
- 抖音单链接实验支持。
- 平台能力矩阵。
- 当前实现不抓取抖音接口，抖音单链接通过 Get笔记兜底。

### v0.5：多平台增强

- 小红书单链接实验支持。
- 输出目录布局。
- 去重和 collection index。
- Obsidian 友好 frontmatter。
- 当前实现不抓取小红书接口，小红书单链接通过 Get笔记兜底。

### v1.0：稳定发布

- PyPI 发布。
- standalone binary。
- 完整用户文档。
- 稳定平台能力矩阵。

## 暂不做

这些功能有价值，但不应进入近期版本：

- 自动批量抓取抖音/小红书主页。
- 绕过平台登录或风控限制。
- 自动规避 Get笔记免费额度。
- 复杂 GUI。
- 本地大模型摘要和转写。

这些方向会显著增加维护成本、合规风险或分发复杂度，应该等核心 CLI 稳定后再评估。
