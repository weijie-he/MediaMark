from mediamark.models import BatchInputRow, VideoItem


def test_batch_input_row_defaults_to_bilibili_platform():
    row = BatchInputRow(url="https://www.bilibili.com/video/BV1xx411c7mD")

    assert row.platform == "bilibili"
    assert row.tags == []
    assert row.collection is None
    assert row.allow_getnote is None


def test_video_item_can_carry_batch_metadata():
    video = VideoItem(
        url="https://www.bilibili.com/video/BV1xx411c7mD",
        bvid="BV1xx411c7mD",
        aid=1,
        cid=2,
        title="视频",
        tags=["ai", "course"],
        collection="ml",
        allow_getnote=False,
        input_url="links.csv",
    )

    assert video.tags == ["ai", "course"]
    assert video.collection == "ml"
    assert video.allow_getnote is False
    assert video.input_url == "links.csv"


def test_video_item_can_carry_platform_metadata():
    video = VideoItem(
        url="https://www.douyin.com/video/123",
        bvid=None,
        aid=None,
        cid=None,
        title="抖音视频 123",
        platform="douyin",
        external_id="123",
    )

    assert video.platform == "douyin"
    assert video.external_id == "123"


def test_video_item_can_carry_xiaohongshu_platform_metadata():
    video = VideoItem(
        url="https://www.xiaohongshu.com/explore/abc123",
        bvid=None,
        aid=None,
        cid=None,
        title="小红书笔记 abc123",
        platform="xiaohongshu",
        external_id="abc123",
    )

    assert video.platform == "xiaohongshu"
    assert video.external_id == "abc123"
