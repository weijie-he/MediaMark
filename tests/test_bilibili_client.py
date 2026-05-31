from datetime import datetime, timezone

import httpx
import pytest
import respx

from mediamark.bilibili.client import BilibiliApiError, BilibiliClient


@pytest.mark.asyncio
@respx.mock
async def test_get_video_by_bvid_maps_metadata():
    respx.get("https://api.bilibili.com/x/web-interface/view").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "bvid": "BV1xx411c7mD",
                    "aid": 123,
                    "title": "Example",
                    "owner": {"name": "UP", "mid": 456},
                    "pubdate": 1780000000,
                    "stat": {"view": 789},
                    "pages": [{"cid": 111, "page": 1, "part": "P1", "duration": 180}],
                },
            },
        )
    )

    async with BilibiliClient() as client:
        videos = await client.get_video_by_bvid("BV1xx411c7mD")

    assert len(videos) == 1
    assert videos[0].bvid == "BV1xx411c7mD"
    assert videos[0].aid == 123
    assert videos[0].cid == 111
    assert videos[0].title == "Example"
    assert videos[0].owner_name == "UP"
    assert videos[0].owner_mid == "456"
    assert videos[0].published_at == datetime.fromtimestamp(1780000000, tz=timezone.utc)
    assert videos[0].view_count == 789
    assert videos[0].duration_seconds == 180


@pytest.mark.asyncio
@respx.mock
async def test_bilibili_client_uses_cookie_file_when_present(tmp_path):
    cookie_file = tmp_path / "bilibili.cookie"
    cookie_file.write_text("SESSDATA=abc; bili_jct=def", encoding="utf-8")
    route = respx.get("https://api.bilibili.com/x/web-interface/view").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "bvid": "BV_COOKIE",
                    "aid": 123,
                    "title": "Cookie",
                    "pages": [{"cid": 111, "page": 1, "part": "P1"}],
                },
            },
        )
    )

    async with BilibiliClient(cookie_file=cookie_file) as client:
        await client.get_video_by_bvid("BV_COOKIE")

    assert route.calls[0].request.headers["cookie"] == "SESSDATA=abc; bili_jct=def"


@pytest.mark.asyncio
@respx.mock
async def test_get_uploader_videos_expands_video_items():
    respx.get("https://api.bilibili.com/x/space/wbi/arc/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "list": {
                        "vlist": [
                            {"bvid": "BV1"},
                            {"bvid": "BV2"},
                        ]
                    }
                },
            },
        )
    )
    respx.get("https://api.bilibili.com/x/web-interface/view").mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "bvid": "BV1",
                        "aid": 1,
                        "title": "One",
                        "owner": {"name": "UP", "mid": 456},
                        "pubdate": 1780000000,
                        "stat": {"view": 100},
                        "pages": [{"cid": 11, "page": 1, "part": "P1"}],
                    },
                },
            ),
            httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "bvid": "BV2",
                        "aid": 2,
                        "title": "Two",
                        "owner": {"name": "UP", "mid": 456},
                        "pubdate": 1780000100,
                        "stat": {"view": 200},
                        "pages": [{"cid": 22, "page": 1, "part": "P1"}],
                    },
                },
            ),
        ]
    )

    async with BilibiliClient() as client:
        videos = await client.get_uploader_videos("456", max_pages=1)

    assert [video.bvid for video in videos] == ["BV1", "BV2"]


@pytest.mark.asyncio
@respx.mock
async def test_get_collection_videos_expands_media_list_items():
    respx.get("https://api.bilibili.com/x/v3/fav/resource/list").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 0,
                "data": {"medias": [{"bvid": "BV3"}], "has_more": False},
            },
        )
    )
    respx.get("https://api.bilibili.com/x/web-interface/view").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "bvid": "BV3",
                    "aid": 3,
                    "title": "Three",
                    "owner": {"name": "UP", "mid": 456},
                    "pubdate": 1780000200,
                    "stat": {"view": 300},
                    "pages": [{"cid": 33, "page": 1, "part": "P1"}],
                },
            },
        )
    )

    async with BilibiliClient() as client:
        videos = await client.get_collection_videos(
            "https://www.bilibili.com/medialist/play/ml123"
        )

    assert [video.bvid for video in videos] == ["BV3"]


@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize(
    "url",
    [
        "https://www.bilibili.com/index.html?foo=ml123",
        "https://www.bilibili.com/index.html?ml123=anything",
    ],
)
async def test_get_collection_videos_rejects_unsupported_query_ml_patterns(url):
    favorite_route = respx.get("https://api.bilibili.com/x/v3/fav/resource/list").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 0,
                "data": {"medias": [], "has_more": False},
            },
        )
    )

    async with BilibiliClient() as client:
        with pytest.raises(BilibiliApiError):
            await client.get_collection_videos(url)

    assert not favorite_route.called


@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize(
    "url",
    [
        "https://www.bilibili.com/collection/123",
        "https://www.bilibili.com/list/123",
        "https://www.bilibili.com/medialist/123",
        "https://www.bilibili.com/index.html?list=123",
    ],
)
async def test_get_collection_videos_extracts_favorite_media_id_from_collection_forms(
    url,
):
    favorite_route = respx.get("https://api.bilibili.com/x/v3/fav/resource/list").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 0,
                "data": {"medias": [{"bvid": "BV4"}], "has_more": False},
            },
        )
    )
    respx.get("https://api.bilibili.com/x/web-interface/view").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "bvid": "BV4",
                    "aid": 4,
                    "title": "Four",
                    "owner": {"name": "UP", "mid": 456},
                    "pubdate": 1780000300,
                    "stat": {"view": 400},
                    "pages": [{"cid": 44, "page": 1, "part": "P1"}],
                },
            },
        )
    )

    async with BilibiliClient() as client:
        videos = await client.get_collection_videos(url)

    assert favorite_route.calls[0].request.url.params["media_id"] == "123"
    assert [video.bvid for video in videos] == ["BV4"]


@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize(
    ("url", "page_size"),
    [
        ("https://www.bilibili.com/index.html?media_id=123", 7),
        ("https://www.bilibili.com/index.html?fid=123", 8),
    ],
)
async def test_get_collection_videos_extracts_query_media_id_and_forwards_page_size(
    url,
    page_size,
):
    favorite_route = respx.get("https://api.bilibili.com/x/v3/fav/resource/list").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 0,
                "data": {"medias": [{"bvid": "BV_QUERY"}], "has_more": False},
            },
        )
    )
    respx.get("https://api.bilibili.com/x/web-interface/view").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "bvid": "BV_QUERY",
                    "aid": 7,
                    "title": "Query",
                    "owner": {"name": "UP", "mid": 456},
                    "pubdate": 1780000600,
                    "stat": {"view": 700},
                    "pages": [{"cid": 71, "page": 1, "part": "P1"}],
                },
            },
        )
    )

    async with BilibiliClient() as client:
        videos = await client.get_collection_videos(
            url, page_size=page_size, max_pages=1
        )

    assert favorite_route.calls[0].request.url.params["media_id"] == "123"
    assert favorite_route.calls[0].request.url.params["ps"] == str(page_size)
    assert [video.bvid for video in videos] == ["BV_QUERY"]


@pytest.mark.asyncio
@respx.mock
async def test_get_uploader_videos_forwards_page_size():
    uploader_route = respx.get("https://api.bilibili.com/x/space/wbi/arc/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 0,
                "data": {"list": {"vlist": [{"bvid": "BV_UP"}]}},
            },
        )
    )
    respx.get("https://api.bilibili.com/x/web-interface/view").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "bvid": "BV_UP",
                    "aid": 8,
                    "title": "Uploader",
                    "owner": {"name": "UP", "mid": 456},
                    "pubdate": 1780000700,
                    "stat": {"view": 800},
                    "pages": [{"cid": 81, "page": 1, "part": "P1"}],
                },
            },
        )
    )

    async with BilibiliClient() as client:
        videos = await client.get_uploader_videos("456", page_size=9, max_pages=1)

    assert uploader_route.calls[0].request.url.params["ps"] == "9"
    assert [video.bvid for video in videos] == ["BV_UP"]


@pytest.mark.asyncio
@respx.mock
async def test_get_uploader_videos_default_fetches_until_empty_page():
    uploader_route = respx.get("https://api.bilibili.com/x/space/wbi/arc/search").mock(
        side_effect=[
            httpx.Response(
                200,
                json={"code": 0, "data": {"list": {"vlist": [{"bvid": "BV_PAGE1"}]}}},
            ),
            httpx.Response(
                200,
                json={"code": 0, "data": {"list": {"vlist": [{"bvid": "BV_PAGE2"}]}}},
            ),
            httpx.Response(200, json={"code": 0, "data": {"list": {"vlist": []}}}),
        ]
    )
    respx.get("https://api.bilibili.com/x/web-interface/view").mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "bvid": "BV_PAGE1",
                        "aid": 10,
                        "title": "Page 1",
                        "pages": [{"cid": 101, "page": 1, "part": "P1"}],
                    },
                },
            ),
            httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "bvid": "BV_PAGE2",
                        "aid": 20,
                        "title": "Page 2",
                        "pages": [{"cid": 201, "page": 1, "part": "P1"}],
                    },
                },
            ),
        ]
    )

    async with BilibiliClient() as client:
        videos = await client.get_uploader_videos("456")

    assert uploader_route.calls.call_count == 3
    assert [video.bvid for video in videos] == ["BV_PAGE1", "BV_PAGE2"]


@pytest.mark.asyncio
@respx.mock
async def test_get_collection_videos_forwards_pagination_to_series():
    series_route = respx.get("https://api.bilibili.com/x/series/archives").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "archives": [{"bvid": "BV_SERIES"}],
                    "page": {"total": 1},
                },
            },
        )
    )
    respx.get("https://api.bilibili.com/x/web-interface/view").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "bvid": "BV_SERIES",
                    "aid": 9,
                    "title": "Series",
                    "owner": {"name": "UP", "mid": 456},
                    "pubdate": 1780000800,
                    "stat": {"view": 900},
                    "pages": [{"cid": 91, "page": 1, "part": "P1"}],
                },
            },
        )
    )

    async with BilibiliClient() as client:
        videos = await client.get_collection_videos(
            "https://space.bilibili.com/456/lists/789",
            page_size=11,
            max_pages=1,
        )

    assert series_route.calls[0].request.url.params["ps"] == "11"
    assert [video.bvid for video in videos] == ["BV_SERIES"]


@pytest.mark.asyncio
@respx.mock(assert_all_called=False)
async def test_get_collection_videos_raises_when_collection_url_cannot_be_parsed():
    favorite_route = respx.get("https://api.bilibili.com/x/v3/fav/resource/list").mock(
        return_value=httpx.Response(
            200,
            json={"code": 0, "data": {"medias": [], "has_more": False}},
        )
    )

    async with BilibiliClient() as client:
        with pytest.raises(BilibiliApiError):
            await client.get_collection_videos("https://www.bilibili.com/unknown/path")

    assert favorite_route.calls.call_count == 0


@pytest.mark.asyncio
@respx.mock(assert_all_called=False)
async def test_get_collection_videos_raises_for_untrusted_bilibili_suffix_host():
    favorite_route = respx.get("https://api.bilibili.com/x/v3/fav/resource/list").mock(
        return_value=httpx.Response(
            200,
            json={"code": 0, "data": {"medias": [], "has_more": False}},
        )
    )

    async with BilibiliClient() as client:
        with pytest.raises(BilibiliApiError):
            await client.get_collection_videos("https://evilbilibili.com/index.html?list=123")

    assert favorite_route.calls.call_count == 0


@pytest.mark.asyncio
@respx.mock(assert_all_called=False)
@pytest.mark.parametrize(
    "url",
    [
        "https://www.bilibili.com/index.html?list=https://www.bilibili.com/list",
        "https://www.bilibili.com/index.html?media_id=abc",
        "https://www.bilibili.com/index.html?fid=abc",
    ],
)
async def test_get_collection_videos_raises_for_malformed_query_media_ids(url):
    favorite_route = respx.get("https://api.bilibili.com/x/v3/fav/resource/list").mock(
        return_value=httpx.Response(
            200,
            json={"code": 0, "data": {"medias": [], "has_more": False}},
        )
    )

    async with BilibiliClient() as client:
        with pytest.raises(BilibiliApiError):
            await client.get_collection_videos(url)

    assert favorite_route.calls.call_count == 0


@pytest.mark.asyncio
@respx.mock(assert_all_called=False)
@pytest.mark.parametrize(
    "url",
    [
        "https://www.bilibili.com/index.html?mid=abc&series_id=def",
        "https://www.bilibili.com/index.html?mid=123&series_id=abc",
    ],
)
async def test_get_collection_videos_raises_for_malformed_series_query_ids(url):
    series_route = respx.get("https://api.bilibili.com/x/series/archives").mock(
        return_value=httpx.Response(
            200,
            json={"code": 0, "data": {"archives": [], "page": {"total": 0}}},
        )
    )

    async with BilibiliClient() as client:
        with pytest.raises(BilibiliApiError):
            await client.get_collection_videos(url)

    assert series_route.calls.call_count == 0


@pytest.mark.asyncio
@respx.mock
async def test_get_series_videos_tracks_archives_not_expanded_video_parts():
    series_route = respx.get("https://api.bilibili.com/x/series/archives").mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "archives": [{"bvid": "BV_MULTI"}],
                        "page": {"total": 2},
                    },
                },
            ),
            httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "archives": [{"bvid": "BV_SINGLE"}],
                        "page": {"total": 2},
                    },
                },
            ),
        ]
    )
    respx.get("https://api.bilibili.com/x/web-interface/view").mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "bvid": "BV_MULTI",
                        "aid": 5,
                        "title": "Multi",
                        "owner": {"name": "UP", "mid": 456},
                        "pubdate": 1780000400,
                        "stat": {"view": 500},
                        "pages": [
                            {"cid": 51, "page": 1, "part": "P1"},
                            {"cid": 52, "page": 2, "part": "P2"},
                        ],
                    },
                },
            ),
            httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "bvid": "BV_SINGLE",
                        "aid": 6,
                        "title": "Single",
                        "owner": {"name": "UP", "mid": 456},
                        "pubdate": 1780000500,
                        "stat": {"view": 600},
                        "pages": [{"cid": 61, "page": 1, "part": "P1"}],
                    },
                },
            ),
        ]
    )

    async with BilibiliClient() as client:
        videos = await client.get_series_videos("456", "789")

    assert series_route.calls.call_count == 2
    assert [video.bvid for video in videos] == ["BV_MULTI", "BV_MULTI", "BV_SINGLE"]


@pytest.mark.asyncio
@respx.mock
async def test_get_subtitle_transcript_returns_none_when_no_subtitles():
    subtitle_list_route = respx.get("https://api.bilibili.com/x/player/wbi/v2").mock(
        return_value=httpx.Response(
            200,
            json={"code": 0, "data": {"subtitle": {"subtitles": []}}},
        )
    )

    async with BilibiliClient() as client:
        transcript = await client.get_subtitle_transcript(aid=123, cid=456)

    assert transcript is None
    assert subtitle_list_route.calls[0].request.url.params["aid"] == "123"
    assert subtitle_list_route.calls[0].request.url.params["cid"] == "456"


@pytest.mark.asyncio
@respx.mock
async def test_get_subtitle_transcript_prefixes_protocol_relative_url_and_parses_lines():
    respx.get(
        "https://api.bilibili.com/x/player/wbi/v2",
        params={"aid": "123", "cid": "456"},
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "subtitle": {
                        "subtitles": [
                            {"subtitle_url": "//sub.example.com/subtitle.json"},
                        ]
                    }
                },
            },
        )
    )
    subtitle_route = respx.get("https://sub.example.com/subtitle.json").mock(
        return_value=httpx.Response(
            200,
            json={"body": [{"from": 1.0, "to": 2.5, "content": "字幕"}]},
        )
    )

    async with BilibiliClient() as client:
        transcript = await client.get_subtitle_transcript(aid=123, cid=456)

    assert subtitle_route.called
    assert transcript is not None
    assert transcript.source == "bilibili_subtitle"
    assert transcript.lines[0].start_seconds == 1.0
    assert transcript.lines[0].end_seconds == 2.5
    assert transcript.lines[0].text == "字幕"


@pytest.mark.asyncio
@respx.mock
async def test_get_subtitle_transcript_skips_subtitle_entries_without_url():
    respx.get(
        "https://api.bilibili.com/x/player/wbi/v2",
        params={"aid": "123", "cid": "456"},
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "subtitle": {
                        "subtitles": [
                            {"lan": "zh-CN"},
                            {"subtitle_url": "//sub.example.com/subtitle.json"},
                        ]
                    }
                },
            },
        )
    )
    subtitle_route = respx.get("https://sub.example.com/subtitle.json").mock(
        return_value=httpx.Response(
            200,
            json={"body": [{"from": 1.0, "to": 2.0, "content": "可用字幕"}]},
        )
    )

    async with BilibiliClient() as client:
        transcript = await client.get_subtitle_transcript(aid=123, cid=456)

    assert subtitle_route.called
    assert transcript is not None
    assert transcript.lines[0].text == "可用字幕"


@pytest.mark.asyncio
@respx.mock
async def test_get_subtitle_transcript_prefers_non_ai_subtitle_when_requested():
    respx.get(
        "https://api.bilibili.com/x/player/wbi/v2",
        params={"aid": "123", "cid": "456"},
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "subtitle": {
                        "subtitles": [
                            {
                                "ai_type": 1,
                                "subtitle_url": "//sub.example.com/ai.json",
                            },
                            {"subtitle_url": "//sub.example.com/manual.json"},
                        ]
                    }
                },
            },
        )
    )
    manual_route = respx.get("https://sub.example.com/manual.json").mock(
        return_value=httpx.Response(
            200,
            json={"body": [{"from": 1.0, "to": 2.0, "content": "人工"}]},
        )
    )

    async with BilibiliClient() as client:
        transcript = await client.get_subtitle_transcript(
            aid=123, cid=456, prefer_ai=False
        )

    assert manual_route.called
    assert transcript is not None
    assert transcript.lines[0].text == "人工"


@pytest.mark.asyncio
@respx.mock
async def test_get_subtitle_transcript_prefers_ai_subtitle_when_requested():
    respx.get(
        "https://api.bilibili.com/x/player/wbi/v2",
        params={"aid": "123", "cid": "456"},
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "subtitle": {
                        "subtitles": [
                            {"subtitle_url": "//sub.example.com/manual.json"},
                            {
                                "ai_type": 1,
                                "subtitle_url": "//sub.example.com/ai.json",
                            },
                        ]
                    }
                },
            },
        )
    )
    ai_route = respx.get("https://sub.example.com/ai.json").mock(
        return_value=httpx.Response(
            200,
            json={"body": [{"from": 1.0, "to": 2.0, "content": "AI优先"}]},
        )
    )

    async with BilibiliClient() as client:
        transcript = await client.get_subtitle_transcript(
            aid=123, cid=456, prefer_ai=True
        )

    assert ai_route.called
    assert transcript is not None
    assert transcript.lines[0].text == "AI优先"


@pytest.mark.asyncio
@respx.mock
async def test_get_subtitle_transcript_tries_next_subtitle_when_preferred_is_empty():
    respx.get(
        "https://api.bilibili.com/x/player/wbi/v2",
        params={"aid": "123", "cid": "456"},
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "subtitle": {
                        "subtitles": [
                            {
                                "ai_type": 1,
                                "subtitle_url": "//sub.example.com/empty-ai.json",
                            },
                            {"subtitle_url": "//sub.example.com/manual.json"},
                        ]
                    }
                },
            },
        )
    )
    empty_ai_route = respx.get("https://sub.example.com/empty-ai.json").mock(
        return_value=httpx.Response(200, json={"body": []})
    )
    manual_route = respx.get("https://sub.example.com/manual.json").mock(
        return_value=httpx.Response(
            200,
            json={"body": [{"from": 1.0, "to": 2.0, "content": "人工兜底"}]},
        )
    )

    async with BilibiliClient() as client:
        transcript = await client.get_subtitle_transcript(
            aid=123, cid=456, prefer_ai=True
        )

    assert empty_ai_route.called
    assert manual_route.called
    assert transcript is not None
    assert transcript.lines[0].text == "人工兜底"


@pytest.mark.asyncio
@respx.mock
async def test_get_subtitle_transcript_falls_back_to_usable_ai_subtitle_when_human_has_no_url():
    respx.get(
        "https://api.bilibili.com/x/player/wbi/v2",
        params={"aid": "123", "cid": "456"},
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "subtitle": {
                        "subtitles": [
                            {"lan": "zh-CN"},
                            {
                                "ai_type": 1,
                                "subtitle_url": "//sub.example.com/ai.json",
                            },
                        ]
                    }
                },
            },
        )
    )
    ai_route = respx.get("https://sub.example.com/ai.json").mock(
        return_value=httpx.Response(
            200,
            json={"body": [{"from": 1.0, "to": 2.0, "content": "AI字幕"}]},
        )
    )

    async with BilibiliClient() as client:
        transcript = await client.get_subtitle_transcript(
            aid=123, cid=456, prefer_ai=False
        )

    assert ai_route.called
    assert transcript is not None
    assert transcript.lines[0].text == "AI字幕"


@pytest.mark.asyncio
@respx.mock
async def test_get_subtitle_transcript_treats_zero_ai_type_as_non_ai():
    respx.get(
        "https://api.bilibili.com/x/player/wbi/v2",
        params={"aid": "123", "cid": "456"},
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "subtitle": {
                        "subtitles": [
                            {
                                "ai_type": 1,
                                "subtitle_url": "//sub.example.com/ai.json",
                            },
                            {
                                "ai_type": 0,
                                "subtitle_url": "//sub.example.com/manual.json",
                            },
                        ]
                    }
                },
            },
        )
    )
    manual_route = respx.get("https://sub.example.com/manual.json").mock(
        return_value=httpx.Response(
            200,
            json={"body": [{"from": 1.0, "to": 2.0, "content": "人工"}]},
        )
    )

    async with BilibiliClient() as client:
        transcript = await client.get_subtitle_transcript(
            aid=123, cid=456, prefer_ai=False
        )

    assert manual_route.called
    assert transcript is not None
    assert transcript.lines[0].text == "人工"


@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize(
    "subtitle_payload",
    [
        {"body": [{"from": 1, "to": 2, "content": "   "}]},
        {"body": []},
    ],
)
async def test_get_subtitle_transcript_returns_none_when_subtitle_has_no_usable_lines(
    subtitle_payload,
):
    respx.get(
        "https://api.bilibili.com/x/player/wbi/v2",
        params={"aid": "123", "cid": "456"},
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "subtitle": {
                        "subtitles": [
                            {"subtitle_url": "//sub.example.com/subtitle.json"},
                        ]
                    }
                },
            },
        )
    )
    respx.get("https://sub.example.com/subtitle.json").mock(
        return_value=httpx.Response(200, json=subtitle_payload)
    )

    async with BilibiliClient() as client:
        transcript = await client.get_subtitle_transcript(aid=123, cid=456)

    assert transcript is None


@pytest.mark.asyncio
async def test_bilibili_client_does_not_close_injected_httpx_client():
    external_client = httpx.AsyncClient(trust_env=False)

    async with BilibiliClient(client=external_client):
        pass

    assert not external_client.is_closed

    await BilibiliClient(client=external_client).aclose()

    assert not external_client.is_closed

    await external_client.aclose()
