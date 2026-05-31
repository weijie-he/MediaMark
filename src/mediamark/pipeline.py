from pathlib import Path
from typing import Protocol

from slugify import slugify

from mediamark.config import AppConfig
from mediamark.collections import write_collection_indexes
from mediamark.getnote.budget import GetnoteBudget, _duration_minutes
from mediamark.markdown.renderer import render_markdown
from mediamark.models import (
    ErrorCode,
    GetnoteEstimate,
    GetnoteEstimateItem,
    NoteContent,
    ProcessResult,
    SortMode,
    Transcript,
    VideoItem,
    sort_video_items,
)

DEFAULT_FILENAME_TEMPLATE = "{published_at}-{title}-{bvid}.md"


class BilibiliTranscriptClient(Protocol):
    async def get_subtitle_transcript(
        self, aid: int, cid: int, prefer_ai: bool = True
    ) -> Transcript | None:
        ...


class GetnoteClient(Protocol):
    def save_url(self, video: VideoItem) -> object:
        ...


class PipelineManifest(Protocol):
    def completed_keys(self) -> set[str]:
        ...

    def record_pending(self, key: str, url: str) -> None:
        ...

    def record_done(self, key: str, url: str, output_path: Path, source: str) -> None:
        ...

    def record_failed(self, key: str, url: str, error: str) -> None:
        ...

    def record_skipped(self, key: str, url: str, reason: str) -> None:
        ...


def video_key(video: VideoItem) -> str:
    return f"{video.bvid or video.url}:{video.part_index}"


def _slug(value: object, fallback: str) -> str:
    if value is None:
        return fallback
    return slugify(str(value), allow_unicode=True) or fallback


def _path_template_context(video: VideoItem) -> dict[str, object]:
    published_at = video.published_at.date().isoformat() if video.published_at else "unknown-date"
    content_id = video.bvid or video.external_id or "unknown-id"
    return {
        "platform": _slug(video.platform, "unknown-platform"),
        "owner": _slug(video.owner_name, "unknown-owner"),
        "collection": _slug(video.collection, "uncategorized"),
        "published_at": published_at,
        "title": _slug(video.title, "untitled"),
        "bvid": video.bvid or "unknown-bvid",
        "id": content_id,
        "external_id": video.external_id or "unknown-external-id",
        "part_index": video.part_index,
        "part_title": _slug(video.part_title, f"p{video.part_index}"),
    }


def _safe_relative_template_path(rendered: str) -> Path:
    parts = [
        part
        for part in Path(rendered).parts
        if part not in {"", ".", "..", Path(rendered).anchor}
    ]
    return Path(*parts) if parts else Path()


def output_path_for(config: AppConfig, video: VideoItem) -> Path:
    context = _path_template_context(video)
    filename = config.markdown.filename_template.format(
        **context,
    )
    if config.markdown.filename_template == DEFAULT_FILENAME_TEMPLATE and video.part_index > 1:
        stem, suffix = Path(filename).stem, Path(filename).suffix
        filename = f"{stem}-p{video.part_index}{suffix}"
    directory_template = config.output.directory_template.strip()
    if not directory_template:
        return config.output_dir / filename
    directory = _safe_relative_template_path(directory_template.format(**context))
    return config.output_dir / directory / filename


def _classify_error(exc: Exception) -> ErrorCode:
    text = str(exc).lower()
    if "disabled" in text:
        return "getnote_disabled"
    if "budget" in text:
        return "getnote_budget_exceeded"
    if "quota" in text:
        return "getnote_quota_exceeded"
    if "auth" in text or "login" in text:
        return "getnote_auth_failed"
    if "getnote" in text:
        return "getnote_cli_error"
    if "network" in text or "timeout" in text:
        return "network_error"
    if "subtitle" in text:
        return "subtitle_parse_error"
    return "unknown_error"


def _note_and_profile(result: object) -> tuple[NoteContent, str | None]:
    if isinstance(result, NoteContent):
        return result, None
    note = getattr(result, "note", None)
    profile_name = getattr(result, "profile_name", None)
    if isinstance(note, NoteContent):
        return note, profile_name if isinstance(profile_name, str) else None
    raise TypeError("Get笔记 client must return NoteContent or GetnoteProfileResult")


class Pipeline:
    def __init__(
        self,
        config: AppConfig,
        bilibili: BilibiliTranscriptClient,
        getnote: GetnoteClient | None,
        manifest: PipelineManifest,
    ) -> None:
        self.config = config
        self.bilibili = bilibili
        self.getnote = getnote
        self.manifest = manifest
        self.getnote_budget = GetnoteBudget(config.getnote.budget)

    async def process(
        self,
        videos: list[VideoItem],
        sort: SortMode,
        limit: int | None,
        skip_existing: bool,
    ) -> list[ProcessResult]:
        selected_videos = sort_video_items(videos, sort)
        if limit is not None:
            selected_videos = selected_videos[:limit]

        completed_keys = self.manifest.completed_keys() if skip_existing else set()
        seen_keys: set[str] = set()
        results: list[ProcessResult] = []
        for video in selected_videos:
            key = video_key(video)
            if self.config.archive.dedupe and key in seen_keys:
                self.manifest.record_skipped(key=key, url=video.url, reason="duplicate input")
                results.append(ProcessResult(video=video, status="skipped"))
                continue
            if skip_existing and key in completed_keys:
                self.manifest.record_skipped(key=key, url=video.url, reason="already completed")
                results.append(ProcessResult(video=video, status="skipped"))
                seen_keys.add(key)
                continue

            attempt = self.manifest.next_attempt(key) if hasattr(self.manifest, "next_attempt") else 1
            self.manifest.record_pending(key=key, url=video.url)
            seen_keys.add(key)
            try:
                result = await self._process_one(video)
                if skip_existing and result.status == "done":
                    completed_keys.add(key)
                results.append(result)
            except Exception as exc:
                error = str(exc)
                error_code = _classify_error(exc)
                self.manifest.record_failed(
                    key=key,
                    url=video.url,
                    error=error,
                    error_code=error_code,
                    attempt=attempt,
                    input_url=video.input_url,
                )
                results.append(
                    ProcessResult(
                        video=video,
                        status="failed",
                        transcript_source="failed",
                        content_level="metadata_only",
                        error=error,
                        error_code=error_code,
                    )
                )
        if self.config.archive.write_collection_index:
            write_collection_indexes(self.config, results)
        return results

    async def estimate_getnote_need(
        self,
        videos: list[VideoItem],
        sort: SortMode,
        limit: int | None,
    ) -> GetnoteEstimate:
        selected_videos = sort_video_items(videos, sort)
        if limit is not None:
            selected_videos = selected_videos[:limit]

        items: list[GetnoteEstimateItem] = []
        fallback_count = 0
        fallback_minutes = 0
        for video in selected_videos:
            transcript = None
            if video.aid is not None and video.cid is not None:
                transcript = await self.bilibili.get_subtitle_transcript(
                    video.aid,
                    video.cid,
                    prefer_ai=self.config.bilibili.prefer_ai_subtitle,
                )

            needs_getnote = transcript is None and video.allow_getnote is not False
            reason = None
            if transcript is not None:
                reason = "bilibili_subtitle"
            elif video.allow_getnote is False:
                reason = "getnote_disabled"
            else:
                fallback_count += 1
                fallback_minutes += _duration_minutes(video)
                reason = "missing_subtitle"
            items.append(
                GetnoteEstimateItem(
                    video=video,
                    needs_getnote=needs_getnote,
                    reason=reason,
                )
            )

        budget = self.config.getnote.budget
        within_budget = (
            (
                budget.max_fallbacks_per_run is None
                or fallback_count <= budget.max_fallbacks_per_run
            )
            and (
                budget.max_minutes_per_run is None
                or fallback_minutes <= budget.max_minutes_per_run
            )
        )
        return GetnoteEstimate(
            items=items,
            fallback_count=fallback_count,
            fallback_minutes=fallback_minutes,
            within_budget=within_budget,
        )

    async def _process_one(self, video: VideoItem) -> ProcessResult:
        transcript: Transcript | None = None
        note: NoteContent | None = None

        if video.aid is not None and video.cid is not None:
            transcript = await self.bilibili.get_subtitle_transcript(
                video.aid,
                video.cid,
                prefer_ai=self.config.bilibili.prefer_ai_subtitle,
            )

        if transcript is not None:
            source = "bilibili_subtitle"
            content_level = "transcript_only"
            profile_name = None
        else:
            if video.allow_getnote is False:
                raise RuntimeError("Get笔记 fallback is disabled for this input row")
            if not self.config.getnote.enabled or self.getnote is None:
                raise RuntimeError("No Bilibili subtitle and Get笔记 fallback is disabled")
            self.getnote_budget.consume(video)
            note, profile_name = _note_and_profile(self.getnote.save_url(video))
            source = "getnote"
            content_level = "note_plus_transcript"

        markdown = render_markdown(video=video, transcript=transcript, note=note)
        path = output_path_for(self.config, video)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown, encoding="utf-8")

        self.manifest.record_done(
            key=video_key(video),
            url=video.url,
            output_path=path,
            source=source,
            getnote_profile=profile_name,
            input_url=video.input_url,
        )
        return ProcessResult(
            video=video,
            status="done",
            transcript_source=source,
            content_level=content_level,
            path=path,
            getnote_profile=profile_name,
        )
