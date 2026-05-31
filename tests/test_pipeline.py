from datetime import datetime, timezone
from pathlib import Path

import pytest

from mediamark.config import AppConfig, GetnoteConfig, MarkdownConfig
from mediamark.models import NoteContent, Transcript, TranscriptLine, VideoItem
from mediamark.pipeline import Pipeline, output_path_for, video_key
from mediamark.storage.manifest import ManifestStore


class FakeBilibiliClient:
    def __init__(self, responses: dict[tuple[int, int], Transcript | None | Exception]):
        self.responses = responses
        self.calls: list[tuple[int, int, bool]] = []

    async def get_subtitle_transcript(
        self, aid: int, cid: int, prefer_ai: bool = True
    ) -> Transcript | None:
        self.calls.append((aid, cid, prefer_ai))
        response = self.responses.get((aid, cid))
        if isinstance(response, Exception):
            raise response
        return response


class FakeGetnoteClient:
    def __init__(self, note: NoteContent | None = None):
        self.note = note or NoteContent(summary="笔记摘要", transcript_text="笔记正文")
        self.calls: list[str] = []

    def save_url(self, video: VideoItem) -> NoteContent:
        self.calls.append(video.url)
        return self.note


class FakeGetnoteProfilePool:
    def __init__(self):
        self.calls = []

    def save_url(self, video):
        self.calls.append(video.url)
        return type(
            "ProfileResult",
            (),
            {
                "note": NoteContent(summary="profile 摘要", transcript_text="正文"),
                "profile_name": "main",
            },
        )()


def make_config(tmp_path: Path, getnote_enabled: bool = True) -> AppConfig:
    return AppConfig(
        output_dir=tmp_path / "out",
        manifest_path=tmp_path / "manifest.jsonl",
        getnote=GetnoteConfig(enabled=getnote_enabled),
        markdown=MarkdownConfig(filename_template="{published_at}-{title}-{bvid}.md"),
    )


def make_video(
    bvid: str | None = "BV1xx411c7mD",
    *,
    aid: int | None = 123,
    cid: int | None = 456,
    title: str = "示例视频",
    published_at: datetime | None = datetime(2026, 5, 30, tzinfo=timezone.utc),
    view_count: int | None = 100,
    part_index: int = 1,
    duration_seconds: int | None = None,
) -> VideoItem:
    return VideoItem(
        url=f"https://www.bilibili.com/video/{bvid or 'av123'}?p={part_index}",
        bvid=bvid,
        aid=aid,
        cid=cid,
        title=title,
        owner_name="UP",
        owner_mid="789",
        published_at=published_at,
        view_count=view_count,
        part_index=part_index,
        part_title=f"P{part_index}",
        duration_seconds=duration_seconds,
    )


def make_transcript(text: str = "字幕正文") -> Transcript:
    return Transcript(
        source="bilibili_subtitle",
        lines=[TranscriptLine(start_seconds=1, end_seconds=2, text=text)],
    )


@pytest.mark.asyncio
async def test_process_uses_bilibili_subtitle_without_getnote(tmp_path):
    config = make_config(tmp_path)
    video = make_video()
    bilibili = FakeBilibiliClient({(123, 456): make_transcript("来自字幕")})
    getnote = FakeGetnoteClient()
    manifest = ManifestStore(config.manifest_path)
    pipeline = Pipeline(config, bilibili=bilibili, getnote=getnote, manifest=manifest)

    results = await pipeline.process([video], sort="source", limit=None, skip_existing=False)

    assert len(results) == 1
    assert results[0].status == "done"
    assert results[0].transcript_source == "bilibili_subtitle"
    assert results[0].content_level == "transcript_only"
    assert results[0].path is not None
    assert results[0].path.exists()
    assert "[00:00:01] 来自字幕" in results[0].path.read_text(encoding="utf-8")
    assert getnote.calls == []
    assert bilibili.calls == [(123, 456, True)]
    assert manifest.latest_records()[video_key(video)]["source"] == "bilibili_subtitle"


@pytest.mark.asyncio
async def test_process_applies_sort_and_limit(tmp_path):
    config = make_config(tmp_path)
    videos = [
        make_video("BV_LOW", aid=1, cid=10, view_count=10),
        make_video("BV_HIGH", aid=2, cid=20, view_count=300),
        make_video("BV_MID", aid=3, cid=30, view_count=100),
    ]
    bilibili = FakeBilibiliClient({(2, 20): make_transcript("最高播放")})
    pipeline = Pipeline(
        config,
        bilibili=bilibili,
        getnote=FakeGetnoteClient(),
        manifest=ManifestStore(config.manifest_path),
    )

    results = await pipeline.process(videos, sort="views-desc", limit=1, skip_existing=False)

    assert [result.video.bvid for result in results] == ["BV_HIGH"]
    assert bilibili.calls == [(2, 20, True)]


@pytest.mark.asyncio
async def test_process_skips_existing_completed_manifest_keys(tmp_path):
    config = make_config(tmp_path)
    video = make_video()
    manifest = ManifestStore(config.manifest_path)
    manifest.record_done(
        key=video_key(video),
        url=video.url,
        output_path=tmp_path / "already.md",
        source="bilibili_subtitle",
    )
    bilibili = FakeBilibiliClient({(123, 456): make_transcript()})
    pipeline = Pipeline(
        config, bilibili=bilibili, getnote=FakeGetnoteClient(), manifest=manifest
    )

    results = await pipeline.process([video], sort="source", limit=None, skip_existing=True)

    assert results[0].status == "skipped"
    assert results[0].video == video
    assert bilibili.calls == []
    assert manifest.latest_records()[video_key(video)]["status"] == "skipped"


@pytest.mark.asyncio
async def test_process_skips_existing_completed_key_across_repeated_runs(tmp_path):
    config = make_config(tmp_path)
    video = make_video()
    manifest = ManifestStore(config.manifest_path)
    manifest.record_done(
        key=video_key(video),
        url=video.url,
        output_path=tmp_path / "already.md",
        source="bilibili_subtitle",
    )
    bilibili = FakeBilibiliClient({(123, 456): make_transcript()})
    pipeline = Pipeline(
        config, bilibili=bilibili, getnote=FakeGetnoteClient(), manifest=manifest
    )

    first_results = await pipeline.process([video], sort="source", limit=None, skip_existing=True)
    second_results = await pipeline.process([video], sort="source", limit=None, skip_existing=True)

    assert [result.status for result in first_results] == ["skipped"]
    assert [result.status for result in second_results] == ["skipped"]
    assert bilibili.calls == []


@pytest.mark.asyncio
async def test_process_skips_duplicate_completed_key_in_same_run(tmp_path):
    config = make_config(tmp_path)
    video = make_video()
    duplicate = video.model_copy()
    bilibili = FakeBilibiliClient({(123, 456): None})
    getnote = FakeGetnoteClient(NoteContent(summary="备用摘要", transcript_text="备用正文"))
    pipeline = Pipeline(
        config,
        bilibili=bilibili,
        getnote=getnote,
        manifest=ManifestStore(config.manifest_path),
    )

    results = await pipeline.process(
        [video, duplicate], sort="source", limit=None, skip_existing=True
    )

    assert [result.status for result in results] == ["done", "skipped"]
    assert bilibili.calls == [(123, 456, True)]
    assert getnote.calls == [video.url]


@pytest.mark.asyncio
async def test_process_uses_getnote_fallback_when_subtitle_missing(tmp_path):
    config = make_config(tmp_path)
    video = make_video()
    bilibili = FakeBilibiliClient({(123, 456): None})
    getnote = FakeGetnoteClient(NoteContent(summary="备用摘要", transcript_text="备用正文"))
    pipeline = Pipeline(
        config,
        bilibili=bilibili,
        getnote=getnote,
        manifest=ManifestStore(config.manifest_path),
    )

    results = await pipeline.process([video], sort="source", limit=None, skip_existing=False)

    assert results[0].status == "done"
    assert results[0].transcript_source == "getnote"
    assert results[0].content_level == "note_plus_transcript"
    assert getnote.calls == [video.url]
    assert results[0].path is not None
    assert "备用摘要" in results[0].path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_process_douyin_uses_getnote_without_bilibili_subtitle_lookup(tmp_path):
    config = make_config(tmp_path)
    video = make_video(bvid=None, aid=None, cid=None, title="抖音视频")
    video.url = "https://www.douyin.com/video/123"
    video.platform = "douyin"
    video.external_id = "123"
    bilibili = FakeBilibiliClient({})
    getnote = FakeGetnoteClient(NoteContent(summary="摘要", transcript_text="正文"))
    pipeline = Pipeline(
        config,
        bilibili=bilibili,
        getnote=getnote,
        manifest=ManifestStore(config.manifest_path),
    )

    results = await pipeline.process([video], sort="source", limit=None, skip_existing=False)

    assert results[0].status == "done"
    assert bilibili.calls == []
    assert getnote.calls == [video.url]


@pytest.mark.asyncio
async def test_process_uses_getnote_profile_pool_when_subtitle_missing(tmp_path):
    config = make_config(tmp_path)
    video = make_video()
    bilibili = FakeBilibiliClient({(123, 456): None})
    pool = FakeGetnoteProfilePool()
    pipeline = Pipeline(
        config,
        bilibili=bilibili,
        getnote=pool,
        manifest=ManifestStore(config.manifest_path),
    )

    results = await pipeline.process([video], sort="source", limit=None, skip_existing=False)

    assert results[0].getnote_profile == "main"
    assert pool.calls == [video.url]


@pytest.mark.asyncio
async def test_process_respects_video_allow_getnote_false(tmp_path):
    config = make_config(tmp_path)
    video = make_video()
    video.allow_getnote = False
    bilibili = FakeBilibiliClient({(123, 456): None})
    pool = FakeGetnoteProfilePool()
    pipeline = Pipeline(
        config,
        bilibili=bilibili,
        getnote=pool,
        manifest=ManifestStore(config.manifest_path),
    )

    results = await pipeline.process([video], sort="source", limit=None, skip_existing=False)

    assert results[0].status == "failed"
    assert results[0].error_code == "getnote_disabled"
    assert pool.calls == []


@pytest.mark.asyncio
async def test_process_stops_getnote_after_fallback_budget_is_exhausted(tmp_path):
    config = make_config(tmp_path)
    config.getnote.budget.max_fallbacks_per_run = 1
    first = make_video("BV_FIRST", aid=1, cid=10)
    second = make_video("BV_SECOND", aid=2, cid=20)
    bilibili = FakeBilibiliClient({(1, 10): None, (2, 20): None})
    getnote = FakeGetnoteClient(NoteContent(summary="摘要", transcript_text="正文"))
    pipeline = Pipeline(
        config,
        bilibili=bilibili,
        getnote=getnote,
        manifest=ManifestStore(config.manifest_path),
    )

    results = await pipeline.process(
        [first, second], sort="source", limit=None, skip_existing=False
    )

    assert [result.status for result in results] == ["done", "failed"]
    assert getnote.calls == [first.url]
    assert "max_fallbacks_per_run=1" in (results[1].error or "")


@pytest.mark.asyncio
async def test_process_checks_minutes_budget_before_getnote_call(tmp_path):
    config = make_config(tmp_path)
    config.getnote.budget.max_minutes_per_run = 1
    video = make_video(duration_seconds=120)
    bilibili = FakeBilibiliClient({(123, 456): None})
    getnote = FakeGetnoteClient()
    pipeline = Pipeline(
        config,
        bilibili=bilibili,
        getnote=getnote,
        manifest=ManifestStore(config.manifest_path),
    )

    results = await pipeline.process([video], sort="source", limit=None, skip_existing=False)

    assert results[0].status == "failed"
    assert getnote.calls == []
    assert "max_minutes_per_run=1" in (results[0].error or "")
    assert results[0].error_code == "getnote_budget_exceeded"


@pytest.mark.asyncio
async def test_process_records_failed_disabled_getnote_and_continues(tmp_path):
    config = make_config(tmp_path, getnote_enabled=False)
    first = make_video("BV_NO_SUB", aid=1, cid=10, view_count=1)
    second = make_video("BV_OK", aid=2, cid=20, view_count=2)
    bilibili = FakeBilibiliClient({(1, 10): None, (2, 20): make_transcript("继续处理")})
    manifest = ManifestStore(config.manifest_path)
    pipeline = Pipeline(config, bilibili=bilibili, getnote=None, manifest=manifest)

    results = await pipeline.process([first, second], sort="source", limit=None, skip_existing=False)

    assert [result.status for result in results] == ["failed", "done"]
    assert "No Bilibili subtitle and Get笔记 fallback is disabled" in (results[0].error or "")
    assert results[1].transcript_source == "bilibili_subtitle"
    records = manifest.latest_records()
    assert records[video_key(first)]["status"] == "failed"
    assert records[video_key(second)]["status"] == "done"


def test_output_path_for_slugifies_unicode_and_fills_missing_values(tmp_path):
    config = AppConfig(
        output_dir=tmp_path / "out",
        markdown=MarkdownConfig(filename_template="{published_at}-{title}-{bvid}.md"),
    )
    video = make_video(
        bvid=None,
        title="标题 Mixed 你好",
        published_at=None,
    )

    path = output_path_for(config, video)

    assert path == tmp_path / "out" / "unknown-date-标题-mixed-你好-unknown-bvid.md"


def test_output_path_for_exposes_part_fields_to_template(tmp_path):
    config = AppConfig(
        output_dir=tmp_path / "out",
        markdown=MarkdownConfig(
            filename_template="{published_at}-{title}-p{part_index}-{part_title}-{bvid}.md"
        ),
    )
    video = make_video(
        bvid="BV_MULTI",
        title="合集标题",
        part_index=3,
    )

    path = output_path_for(config, video)

    assert path == tmp_path / "out" / "2026-05-30-合集标题-p3-p3-BV_MULTI.md"


@pytest.mark.asyncio
async def test_process_writes_default_template_multi_part_videos_to_distinct_paths(tmp_path):
    config = make_config(tmp_path)
    first = make_video("BV_MULTI", aid=1, cid=10, title="合集标题", part_index=1)
    second = make_video("BV_MULTI", aid=2, cid=20, title="合集标题", part_index=2)
    bilibili = FakeBilibiliClient(
        {(1, 10): make_transcript("第一集"), (2, 20): make_transcript("第二集")}
    )
    pipeline = Pipeline(
        config,
        bilibili=bilibili,
        getnote=FakeGetnoteClient(),
        manifest=ManifestStore(config.manifest_path),
    )

    results = await pipeline.process([first, second], sort="source", limit=None, skip_existing=False)

    paths = [result.path for result in results]
    assert paths[0] is not None
    assert paths[1] is not None
    assert paths[0] != paths[1]
    assert paths[0].name == "2026-05-30-合集标题-BV_MULTI.md"
    assert paths[1].name == "2026-05-30-合集标题-BV_MULTI-p2.md"
    assert "第一集" in paths[0].read_text(encoding="utf-8")
    assert "第二集" in paths[1].read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_process_records_single_video_failure_and_continues(tmp_path):
    config = make_config(tmp_path)
    first = make_video("BV_FAIL", aid=1, cid=10, view_count=1)
    second = make_video("BV_OK", aid=2, cid=20, view_count=2)
    bilibili = FakeBilibiliClient(
        {(1, 10): RuntimeError("subtitle exploded"), (2, 20): make_transcript("成功")}
    )
    manifest = ManifestStore(config.manifest_path)
    pipeline = Pipeline(
        config,
        bilibili=bilibili,
        getnote=FakeGetnoteClient(),
        manifest=manifest,
    )

    results = await pipeline.process([first, second], sort="source", limit=None, skip_existing=False)

    assert [result.status for result in results] == ["failed", "done"]
    assert results[0].error == "subtitle exploded"
    assert results[1].path is not None
    records = manifest.latest_records()
    assert records[video_key(first)]["status"] == "failed"
    assert records[video_key(first)]["error"] == "subtitle exploded"
    assert records[video_key(second)]["status"] == "done"


@pytest.mark.asyncio
async def test_process_records_error_code_attempt_and_input_url(tmp_path):
    config = make_config(tmp_path, getnote_enabled=False)
    video = make_video()
    video.input_url = "links.csv"
    bilibili = FakeBilibiliClient({(123, 456): None})
    manifest = ManifestStore(config.manifest_path)
    manifest.record_failed(video_key(video), video.url, "previous", attempt=1)
    pipeline = Pipeline(config, bilibili=bilibili, getnote=None, manifest=manifest)

    results = await pipeline.process([video], sort="source", limit=None, skip_existing=False)

    record = manifest.latest_records()[video_key(video)]
    assert results[0].error_code == "getnote_disabled"
    assert record["error_code"] == "getnote_disabled"
    assert record["attempt"] == 2
    assert record["input_url"] == "links.csv"


@pytest.mark.asyncio
async def test_estimate_getnote_need_marks_items_without_subtitles(tmp_path):
    config = make_config(tmp_path)
    with_subtitle = make_video("BV_OK", aid=1, cid=10, duration_seconds=60)
    without_subtitle = make_video("BV_NEED", aid=2, cid=20, duration_seconds=120)
    bilibili = FakeBilibiliClient({(1, 10): make_transcript("字幕"), (2, 20): None})
    pipeline = Pipeline(
        config,
        bilibili=bilibili,
        getnote=None,
        manifest=ManifestStore(config.manifest_path),
    )

    estimate = await pipeline.estimate_getnote_need(
        [with_subtitle, without_subtitle],
        sort="source",
        limit=None,
    )

    assert estimate.fallback_count == 1
    assert estimate.fallback_minutes == 2
    assert estimate.items[1].needs_getnote is True


def test_video_key_uses_bvid_or_url_and_part_index():
    with_bvid = make_video("BV_MULTI", part_index=2)
    without_bvid = make_video(None, part_index=3)

    assert video_key(with_bvid) == "BV_MULTI:2"
    assert video_key(without_bvid) == f"{without_bvid.url}:3"
