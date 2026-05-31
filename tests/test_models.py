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
