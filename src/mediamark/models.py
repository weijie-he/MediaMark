from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


SortMode = Literal["source", "time-desc", "time-asc", "views-desc", "views-asc"]
PartSelectionMode = Literal["selected", "all"]
Platform = Literal["bilibili", "douyin", "xiaohongshu"]
TranscriptSource = Literal["bilibili_subtitle", "getnote", "failed"]
ContentLevel = Literal["transcript_only", "note_plus_transcript", "metadata_only"]
GetnoteProvider = Literal["cli", "web"]
ErrorCode = Literal[
    "no_subtitle",
    "getnote_disabled",
    "getnote_budget_exceeded",
    "getnote_quota_exceeded",
    "getnote_auth_failed",
    "getnote_cli_error",
    "getnote_web_login_required",
    "getnote_web_generation_timeout",
    "getnote_web_export_not_found",
    "getnote_web_export_failed",
    "getnote_web_browser_error",
    "network_error",
    "platform_parse_error",
    "subtitle_parse_error",
    "unknown_error",
]
MIN_AWARE_DATETIME = datetime.min.replace(tzinfo=timezone.utc)


class TranscriptLine(BaseModel):
    start_seconds: float
    end_seconds: float | None = None
    text: str


class Transcript(BaseModel):
    source: TranscriptSource
    lines: list[TranscriptLine] = Field(default_factory=list)


class NoteContent(BaseModel):
    summary: str | None = None
    key_points: list[str] = Field(default_factory=list)
    outline: list[str] = Field(default_factory=list)
    transcript_text: str | None = None
    raw_markdown: str | None = None

    @property
    def has_summary(self) -> bool:
        return bool(self.summary or self.key_points or self.outline)


class BatchInputRow(BaseModel):
    url: str
    platform: Platform = "bilibili"
    tags: list[str] = Field(default_factory=list)
    collection: str | None = None
    allow_getnote: bool | None = None


class VideoItem(BaseModel):
    url: str
    bvid: str | None
    aid: int | None
    cid: int | None
    title: str
    platform: Platform = "bilibili"
    external_id: str | None = None
    owner_name: str | None = None
    owner_mid: str | None = None
    published_at: datetime | None = None
    view_count: int | None = None
    part_index: int = 1
    part_title: str | None = None
    duration_seconds: int | None = None
    tags: list[str] = Field(default_factory=list)
    collection: str | None = None
    allow_getnote: bool | None = None
    input_url: str | None = None


class RenderedDocument(BaseModel):
    video: VideoItem
    transcript_source: TranscriptSource
    content_level: ContentLevel
    has_summary: bool
    sections: list[str]
    path: Path | None = None


class ProcessResult(BaseModel):
    video: VideoItem
    status: Literal["done", "failed", "skipped"]
    transcript_source: TranscriptSource | None = None
    content_level: ContentLevel | None = None
    path: Path | None = None
    error: str | None = None
    error_code: ErrorCode | None = None
    getnote_profile: str | None = None
    getnote_provider: GetnoteProvider | None = None


class GetnoteEstimateItem(BaseModel):
    video: VideoItem
    needs_getnote: bool
    reason: str | None = None


class GetnoteEstimate(BaseModel):
    items: list[GetnoteEstimateItem]
    fallback_count: int
    fallback_minutes: int
    within_budget: bool


def sort_video_items(items: list[VideoItem], mode: SortMode) -> list[VideoItem]:
    if mode == "source":
        return list(items)
    if mode == "time-desc":
        return sorted(items, key=lambda item: item.published_at or MIN_AWARE_DATETIME, reverse=True)
    if mode == "time-asc":
        return sorted(items, key=lambda item: item.published_at or MIN_AWARE_DATETIME)
    if mode == "views-desc":
        return sorted(items, key=lambda item: item.view_count or 0, reverse=True)
    if mode == "views-asc":
        return sorted(items, key=lambda item: item.view_count or 0)
    raise ValueError(f"Unsupported sort mode: {mode}")
