import pytest

from mediamark.models import VideoItem
from mediamark.platforms import adapter_for_input, adapter_for_platform
from mediamark.platforms.base import ExpansionContext
from mediamark.platforms.douyin import DouyinAdapter
from mediamark.platforms.xiaohongshu import XiaohongshuAdapter


class FakeBilibiliClient:
    async def get_video_by_bvid(self, bvid: str):
        return [
            VideoItem(
                url=f"https://www.bilibili.com/video/{bvid}",
                bvid=bvid,
                aid=1,
                cid=2,
                title="B 站视频",
            )
        ]

    async def get_uploader_videos(self, mid: str):
        return []

    async def get_collection_videos(self, url: str):
        return []


def test_adapter_registry_detects_douyin_url():
    adapter = adapter_for_input("https://www.douyin.com/video/123")

    assert adapter is not None
    assert adapter.platform == "douyin"


def test_adapter_registry_detects_xiaohongshu_url():
    adapter = adapter_for_input("https://www.xiaohongshu.com/explore/abc123")

    assert adapter is not None
    assert adapter.platform == "xiaohongshu"


def test_adapter_registry_can_select_by_platform():
    adapter = adapter_for_platform("douyin")

    assert adapter.platform == "douyin"


def test_adapter_registry_can_select_xiaohongshu_by_platform():
    adapter = adapter_for_platform("xiaohongshu")

    assert adapter.platform == "xiaohongshu"


@pytest.mark.asyncio
async def test_douyin_adapter_expands_single_video_url():
    adapter = DouyinAdapter()
    videos = await adapter.expand(
        "https://www.douyin.com/video/123",
        ExpansionContext(
            bilibili_client=FakeBilibiliClient(),
            part_selection="selected",
        ),
    )

    assert videos[0].platform == "douyin"
    assert videos[0].external_id == "123"
    assert videos[0].aid is None
    assert videos[0].cid is None


@pytest.mark.asyncio
async def test_xiaohongshu_adapter_expands_single_note_url():
    adapter = XiaohongshuAdapter()
    videos = await adapter.expand(
        "https://www.xiaohongshu.com/explore/abc123",
        ExpansionContext(
            bilibili_client=FakeBilibiliClient(),
            part_selection="selected",
        ),
    )

    assert videos[0].platform == "xiaohongshu"
    assert videos[0].external_id == "abc123"
    assert videos[0].aid is None
    assert videos[0].cid is None
