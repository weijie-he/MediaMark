from datetime import datetime, timezone

from mediamark.models import VideoItem, sort_video_items


def make_video(
    title: str,
    published_at: str | None,
    view_count: int | None,
) -> VideoItem:
    return VideoItem(
        url=f"https://www.bilibili.com/video/{title}",
        bvid=title,
        aid=None,
        cid=None,
        title=title,
        owner_name="owner",
        owner_mid="1",
        published_at=(
            datetime.fromisoformat(published_at).replace(tzinfo=timezone.utc)
            if published_at is not None
            else None
        ),
        view_count=view_count,
        part_index=1,
        part_title=title,
    )


def test_sort_source_keeps_input_order():
    videos = [
        make_video("BV3", "2026-05-03T00:00:00", 300),
        make_video("BV1", "2026-05-01T00:00:00", 100),
        make_video("BV2", "2026-05-02T00:00:00", 200),
    ]

    result = sort_video_items(videos, "source")

    assert [item.bvid for item in result] == ["BV3", "BV1", "BV2"]


def test_sort_by_time_desc():
    videos = [
        make_video("BV1", "2026-05-01T00:00:00", 100),
        make_video("BV3", "2026-05-03T00:00:00", 300),
        make_video("BV2", "2026-05-02T00:00:00", 200),
    ]

    result = sort_video_items(videos, "time-desc")

    assert [item.bvid for item in result] == ["BV3", "BV2", "BV1"]


def test_sort_by_time_desc_handles_missing_dates_after_aware_dates():
    videos = [
        make_video("BV_MISSING", None, 100),
        make_video("BV_DATED", "2026-05-03T00:00:00", 300),
    ]

    result = sort_video_items(videos, "time-desc")

    assert [item.bvid for item in result] == ["BV_DATED", "BV_MISSING"]


def test_sort_by_time_asc():
    videos = [
        make_video("BV3", "2026-05-03T00:00:00", 300),
        make_video("BV1", "2026-05-01T00:00:00", 100),
        make_video("BV2", "2026-05-02T00:00:00", 200),
    ]

    result = sort_video_items(videos, "time-asc")

    assert [item.bvid for item in result] == ["BV1", "BV2", "BV3"]


def test_sort_by_views_desc():
    videos = [
        make_video("BV1", "2026-05-01T00:00:00", 100),
        make_video("BV3", "2026-05-03T00:00:00", 300),
        make_video("BV2", "2026-05-02T00:00:00", 200),
    ]

    result = sort_video_items(videos, "views-desc")

    assert [item.bvid for item in result] == ["BV3", "BV2", "BV1"]


def test_sort_by_views_asc_treats_missing_view_count_as_zero():
    videos = [
        make_video("BV2", "2026-05-02T00:00:00", 200),
        make_video("BV_MISSING", "2026-05-03T00:00:00", None),
        make_video("BV1", "2026-05-01T00:00:00", 100),
    ]

    result = sort_video_items(videos, "views-asc")

    assert [item.bvid for item in result] == ["BV_MISSING", "BV1", "BV2"]
