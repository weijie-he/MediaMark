from datetime import datetime, timezone
from typing import Any

from mediamark.models import NoteContent, Transcript, VideoItem


def _quote(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, datetime):
        value = value.isoformat()
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


def _format_yaml_list(key: str, values: list[str]) -> list[str]:
    if not values:
        return [f"{key}: []"]
    return [f"{key}:"] + [f"  - {_quote(value)}" for value in values]


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values


def _format_timestamp(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _render_transcript(transcript: Transcript) -> str:
    return "\n".join(
        f"[{_format_timestamp(line.start_seconds)}] {line.text.strip()}"
        for line in transcript.lines
        if line.text.strip()
    )


def _frontmatter(
    video: VideoItem,
    source: str,
    content_level: str,
    has_summary: bool,
    sections: list[str],
) -> str:
    generated_at = datetime.now(timezone.utc).isoformat()
    fields = [
        ("title", video.title),
        ("source", video.platform),
        ("platform", video.platform),
        ("url", video.url),
        ("external_id", video.external_id),
        ("bvid", video.bvid),
        ("aid", video.aid),
        ("cid", video.cid),
        ("part", video.part_index),
        ("part_title", video.part_title),
        ("owner", video.owner_name),
        ("owner_mid", video.owner_mid),
        ("published_at", video.published_at),
        ("view_count", video.view_count),
        ("transcript_source", source),
        ("content_level", content_level),
        ("has_summary", has_summary),
    ]
    tags = _unique([video.platform, *video.tags])
    collections = [video.collection] if video.collection else []
    lines = ["---"]
    lines.extend(f"{key}: {_quote(value)}" for key, value in fields)
    lines.extend(_format_yaml_list("tags", tags))
    lines.extend(_format_yaml_list("collections", collections))
    lines.append(f"sections: [{', '.join(_quote(section) for section in sections)}]")
    lines.append(f"generated_at: {_quote(generated_at)}")
    lines.append("---")
    return "\n".join(lines)


def _note_sections(note: NoteContent) -> list[str]:
    if note.raw_markdown:
        return ["raw_markdown"]

    sections: list[str] = []
    if note.summary:
        sections.append("summary")
    if note.key_points:
        sections.append("key_points")
    if note.outline:
        sections.append("outline")
    if note.transcript_text:
        sections.append("transcript")
    return sections


def _render_note_body(video: VideoItem, note: NoteContent) -> str:
    parts = [f"# {video.title}", f"原始链接: {video.url}"]

    if note.raw_markdown:
        parts.append(note.raw_markdown.strip())
        return "\n\n".join(part for part in parts if part)

    if note.summary:
        parts.extend(["## 摘要", note.summary.strip()])

    if note.key_points:
        parts.extend(["## 要点", "\n".join(f"- {point}" for point in note.key_points)])

    if note.outline:
        parts.extend(["## 大纲", "\n".join(f"- {item}" for item in note.outline)])

    if note.transcript_text:
        parts.extend(["## 逐字稿", note.transcript_text.strip()])

    return "\n\n".join(part for part in parts if part)


def render_markdown(
    video: VideoItem,
    transcript: Transcript | None,
    note: NoteContent | None,
) -> str:
    if transcript is not None:
        sections = ["transcript"]
        frontmatter = _frontmatter(
            video=video,
            source=transcript.source,
            content_level="transcript_only",
            has_summary=False,
            sections=sections,
        )
        body = "\n\n".join(
            [
                f"# {video.title}",
                f"原始链接: {video.url}",
                "## 逐字稿",
                _render_transcript(transcript),
            ]
        )
        return f"{frontmatter}\n\n{body}\n"

    if note is not None:
        sections = _note_sections(note)
        frontmatter = _frontmatter(
            video=video,
            source="getnote",
            content_level="note_plus_transcript",
            has_summary=note.has_summary,
            sections=sections,
        )
        return f"{frontmatter}\n\n{_render_note_body(video, note)}\n"

    frontmatter = _frontmatter(
        video=video,
        source="failed",
        content_level="metadata_only",
        has_summary=False,
        sections=[],
    )
    body = "\n\n".join([f"# {video.title}", f"原始链接: {video.url}"])
    return f"{frontmatter}\n\n{body}\n"
