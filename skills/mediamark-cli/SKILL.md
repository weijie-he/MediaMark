---
name: mediamark-cli
description: Use MediaMark CLI to convert media links into Markdown notes. Trigger when the user wants to run, configure, diagnose, batch process, or explain MediaMark for Bilibili, Douyin, Xiaohongshu, Get笔记 fallback, Obsidian-friendly output, manifest status/retry, or collection index workflows.
---

# MediaMark CLI

Use this skill when helping users run or troubleshoot MediaMark, the CLI that converts media content into Markdown notes.

Work from the MediaMark repository root, the directory that contains `pyproject.toml`. If a project-level `AGENTS.md` requires a command prefix such as `rtk`, follow it; otherwise run the commands as shown without that prefix.

## Capabilities

- Bilibili: single video, BV id, selected P, uploader homepage, collection/list, native subtitles first, Get笔记 fallback.
- Douyin: experimental single video URL only, Get笔记 fallback only.
- Xiaohongshu: experimental single note URL only, Get笔记 fallback only.
- Batch input: text, CSV, JSONL.
- Output: Markdown files, Obsidian-friendly frontmatter, optional `{platform}/{collection}` directory layout, collection index.
- State: JSONL manifest, status, retry failed, clean pending.

Do not claim support for platform homepage/search scraping beyond Bilibili. Do not suggest bypassing platform login, anti-bot rules, or Get笔记 quota limits.

## Preflight

From the repository root:

```bash
uv sync
uv run mediamark doctor
uv run mediamark platforms
```

If `uv run mediamark` is not available, use the local environment:

```bash
.venv/bin/python -m mediamark.cli --help
```

Get笔记 is an external dependency. For fallback flows, make sure the user has installed and authenticated it:

```bash
npm install -g @getnote/cli
getnote auth
getnote save "https://www.bilibili.com/video/BV..." -o json
```

If Codex has a Get笔记-related skill available, use it before debugging Get笔记 CLI behavior.

## Run Safely

For any batch, collection, uploader page, Douyin, or Xiaohongshu request, dry-run first:

```bash
uv run mediamark run ./links.csv --dry-run --estimate-getnote
```

Use `--no-getnote` when the user wants Bilibili subtitles only:

```bash
uv run mediamark run "https://www.bilibili.com/video/BV..." --no-getnote
```

Use `--limit` and sorting for large Bilibili inputs:

```bash
uv run mediamark run "mid:123456" --sort views-desc --limit 50 --dry-run --estimate-getnote
```

Then run without `--dry-run`:

```bash
uv run mediamark run ./links.csv --sort source
```

## Common Commands

Single inputs:

```bash
uv run mediamark run "BV1xx411c7mD"
uv run mediamark run "https://www.bilibili.com/video/BV...?p=2"
uv run mediamark run "https://www.bilibili.com/video/BV...?p=2" --part-selection all
uv run mediamark run "https://www.douyin.com/video/..."
uv run mediamark run "https://www.xiaohongshu.com/explore/..."
```

Bilibili batch sources:

```bash
uv run mediamark run "https://space.bilibili.com/123456" --sort time-desc --limit 20
uv run mediamark run "mid:123456" --sort views-desc --limit 50
uv run mediamark run "https://space.bilibili.com/123456/lists/987654"
```

Manifest operations:

```bash
uv run mediamark status
uv run mediamark status --json
uv run mediamark retry-failed --dry-run
uv run mediamark retry-failed --error-code getnote_quota_exceeded
uv run mediamark clean-pending
```

## Batch Files

Text files contain one input per non-empty line:

```text
BV1xx411c7mD
mid:123456
https://www.douyin.com/video/...
```

CSV supports metadata:

```csv
url,platform,tags,collection,allow_getnote
https://www.bilibili.com/video/BV...,bilibili,"ai,course",ml,yes
https://www.douyin.com/video/...,douyin,"short,idea",shorts,yes
https://www.xiaohongshu.com/explore/...,xiaohongshu,"note,idea",inbox,yes
```

JSONL equivalent:

```jsonl
{"url":"BV1xx411c7mD","tags":["ai"],"allow_getnote":false}
{"url":"https://www.douyin.com/video/...","platform":"douyin","tags":["short"],"allow_getnote":true}
{"url":"https://www.xiaohongshu.com/explore/...","platform":"xiaohongshu","collection":"inbox","allow_getnote":true}
```

For CSV/JSONL, `platform` can be `bilibili`, `douyin`, or `xiaohongshu`.

## Config Patterns

Start from:

```bash
cp config.example.yaml config.yaml
```

Limit Get笔记 usage:

```yaml
getnote:
  budget:
    max_fallbacks_per_run: 20
    max_minutes_per_run: 120
```

Use multiple Get笔记 profiles:

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
```

Organize output and generate collection indexes:

```yaml
output:
  directory_template: "{platform}/{collection}"

archive:
  dedupe: true
  write_collection_index: true
  collection_index_dir: "_collections"
```

Useful filename fields:

```text
platform, owner, collection, published_at, title, bvid, id, external_id, part_index, part_title
```

## Output Semantics

MediaMark frontmatter records content level honestly:

- `transcript_only`: native Bilibili subtitle; no summary.
- `note_plus_transcript`: Get笔记 fallback; may include summary, outline, key points, transcript.
- `metadata_only`: failed internal result; normally recorded in manifest rather than written as a note.

Obsidian-friendly fields include:

```yaml
platform: "bilibili"
tags:
  - "bilibili"
  - "course"
collections:
  - "机器学习"
```

The platform name is automatically included in `tags`; CSV/JSONL tags are appended.

## Verification

After running a conversion:

```bash
uv run mediamark status
find output -name '*.md' | head
```

When modifying MediaMark itself, run:

```bash
.venv/bin/python -m pytest -q
env PYTHONPATH=src .venv/bin/python -c 'from pathlib import Path; from mediamark.config import load_config; print(load_config(Path("config.example.yaml")).model_dump()["archive"]["collection_index_dir"])'
```
