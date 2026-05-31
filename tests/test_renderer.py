from datetime import datetime, timezone

from mediamark.markdown.renderer import render_markdown
from mediamark.models import NoteContent, Transcript, TranscriptLine, VideoItem


def make_video(title: str = "示例视频") -> VideoItem:
    return VideoItem(
        url="https://www.bilibili.com/video/BV1xx411c7mD",
        bvid="BV1xx411c7mD",
        aid=123,
        cid=456,
        title=title,
        owner_name="UP",
        owner_mid="789",
        published_at=datetime(2026, 5, 30, tzinfo=timezone.utc),
        view_count=1000,
        part_index=1,
        part_title="P1",
    )


def test_render_transcript_only_document():
    transcript = Transcript(
        source="bilibili_subtitle",
        lines=[TranscriptLine(start_seconds=1, end_seconds=2, text="你好")],
    )

    markdown = render_markdown(video=make_video(), transcript=transcript, note=None)

    assert 'transcript_source: "bilibili_subtitle"' in markdown
    assert 'content_level: "transcript_only"' in markdown
    assert "has_summary: false" in markdown
    assert "## 逐字稿" in markdown
    assert "[00:00:01] 你好" in markdown


def test_render_getnote_document_with_summary():
    note = NoteContent(summary="摘要", transcript_text="正文")

    markdown = render_markdown(video=make_video(), transcript=None, note=note)

    assert 'transcript_source: "getnote"' in markdown
    assert 'content_level: "note_plus_transcript"' in markdown
    assert "has_summary: true" in markdown
    assert "## 摘要" in markdown
    assert "摘要" in markdown
    assert "## 逐字稿" in markdown


def test_render_markdown_frontmatter_uses_video_platform():
    video = VideoItem(
        url="https://www.douyin.com/video/123",
        bvid=None,
        aid=None,
        cid=None,
        title="抖音视频 123",
        platform="douyin",
        external_id="123",
    )

    markdown = render_markdown(
        video=video,
        transcript=None,
        note=NoteContent(summary="摘要", transcript_text="正文"),
    )

    assert 'source: "douyin"' in markdown
    assert 'external_id: "123"' in markdown


def test_render_markdown_frontmatter_is_obsidian_friendly():
    video = make_video()
    video.tags = ["course", "ai"]
    video.collection = "机器学习"

    markdown = render_markdown(
        video=video,
        transcript=None,
        note=NoteContent(summary="摘要", transcript_text="正文"),
    )

    assert 'platform: "bilibili"' in markdown
    assert "tags:" in markdown
    assert '- "bilibili"' in markdown
    assert '- "course"' in markdown
    assert "collections:" in markdown
    assert '- "机器学习"' in markdown


def test_render_prefers_transcript_when_note_is_also_present():
    transcript = Transcript(
        source="bilibili_subtitle",
        lines=[TranscriptLine(start_seconds=1, end_seconds=2, text="字幕优先")],
    )
    note = NoteContent(summary="不要渲染我", raw_markdown="## 摘要\n\n不要渲染我")

    markdown = render_markdown(video=make_video(), transcript=transcript, note=note)

    assert 'transcript_source: "bilibili_subtitle"' in markdown
    assert 'content_level: "transcript_only"' in markdown
    assert "[00:00:01] 字幕优先" in markdown
    assert "不要渲染我" not in markdown


def test_render_getnote_raw_markdown_does_not_duplicate_structured_sections():
    note = NoteContent(
        summary="摘要",
        raw_markdown="## 摘要\n\nraw摘要\n\n## 逐字稿\n\n正文",
    )

    markdown = render_markdown(video=make_video(), transcript=None, note=note)

    assert markdown.count("## 摘要") == 1
    assert "raw摘要" in markdown
    assert "\n\n摘要\n\n" not in markdown


def test_render_getnote_structured_sections_without_raw_markdown():
    note = NoteContent(
        summary="摘要",
        key_points=["要点一"],
        outline=["开场"],
        transcript_text="正文",
    )

    markdown = render_markdown(video=make_video(), transcript=None, note=note)

    assert "## 摘要" in markdown
    assert "摘要" in markdown
    assert "## 要点" in markdown
    assert "- 要点一" in markdown
    assert "## 大纲" in markdown
    assert "- 开场" in markdown
    assert "## 逐字稿" in markdown
    assert "正文" in markdown


def test_render_getnote_document_with_key_points_and_outline():
    note = NoteContent(
        key_points=["要点一", "要点二"],
        outline=["开场", "结尾"],
        transcript_text="正文",
    )

    markdown = render_markdown(video=make_video(), transcript=None, note=note)

    assert 'sections: ["key_points", "outline", "transcript"]' in markdown
    assert "## 要点" in markdown
    assert "- 要点一" in markdown
    assert "- 要点二" in markdown
    assert "## 大纲" in markdown
    assert "- 开场" in markdown
    assert "- 结尾" in markdown
    assert "## 逐字稿" in markdown
    assert "正文" in markdown


def test_render_transcript_timestamps_as_hours_minutes_seconds():
    transcript = Transcript(
        source="bilibili_subtitle",
        lines=[
            TranscriptLine(start_seconds=65, end_seconds=66, text="一分钟后"),
            TranscriptLine(start_seconds=3661, end_seconds=3662, text="一小时后"),
        ],
    )

    markdown = render_markdown(video=make_video(), transcript=transcript, note=None)

    assert "[00:01:05] 一分钟后" in markdown
    assert "[01:01:01] 一小时后" in markdown


def test_frontmatter_quotes_and_escapes_yaml_sensitive_strings():
    markdown = render_markdown(
        video=make_video(title='标题 "带引号": 需要转义'),
        transcript=None,
        note=None,
    )

    assert 'title: "标题 \\"带引号\\": 需要转义"' in markdown


def test_render_metadata_only_document_without_transcript_or_note():
    markdown = render_markdown(video=make_video(), transcript=None, note=None)

    assert 'transcript_source: "failed"' in markdown
    assert 'content_level: "metadata_only"' in markdown
    assert "has_summary: false" in markdown
    assert "sections: []" in markdown
    assert "## 摘要" not in markdown
    assert "## 逐字稿" not in markdown
