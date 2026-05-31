import re
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

from mediamark.bilibili.subtitles import parse_subtitle_json
from mediamark.models import Transcript
from mediamark.models import VideoItem


VIEW_URL = "https://api.bilibili.com/x/web-interface/view"
PLAYER_WBI_URL = "https://api.bilibili.com/x/player/wbi/v2"
UPLOADER_URL = "https://api.bilibili.com/x/space/wbi/arc/search"
FAVORITE_URL = "https://api.bilibili.com/x/v3/fav/resource/list"
SERIES_URL = "https://api.bilibili.com/x/series/archives"


class BilibiliApiError(RuntimeError):
    pass


def _is_bilibili_host(host: str) -> bool:
    return host == "bilibili.com" or host.endswith(".bilibili.com")


def _first_query_value(query: dict[str, list[str]], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        values = query.get(key)
        if values and values[0]:
            return values[0]
    return None


def _first_numeric_query_value(query: dict[str, list[str]], keys: tuple[str, ...]) -> str | None:
    value = _first_query_value(query, keys)
    if value is None:
        return None
    return value if value.isdigit() else None


def _extract_collection_media_id(url: str) -> str | None:
    parsed = urlparse(url)
    if not _is_bilibili_host(parsed.netloc.lower()):
        return None
    query = parse_qs(parsed.query, keep_blank_values=True)
    query_value = _first_numeric_query_value(query, ("media_id", "fid", "list"))
    if query_value:
        return query_value

    path_parts = [part for part in parsed.path.split("/") if part]
    for index, part in enumerate(path_parts):
        if part == "medialist" and index + 1 < len(path_parts) and path_parts[index + 1].isdigit():
            return path_parts[index + 1]
        if (
            part == "medialist"
            and index + 2 < len(path_parts)
            and path_parts[index + 1] == "play"
        ):
            media_id = path_parts[index + 2]
            if match := re.fullmatch(r"(?:ml)?(\d+)", media_id):
                return match.group(1)
        if part in {"collection", "list"} and index + 1 < len(path_parts):
            media_id = path_parts[index + 1]
            if media_id.isdigit():
                return media_id

    return None


def _extract_series_ids(url: str) -> tuple[str, str] | None:
    parsed = urlparse(url)
    if not _is_bilibili_host(parsed.netloc.lower()):
        return None
    query = parse_qs(parsed.query)
    mid = _first_query_value(query, ("mid", "spmid"))
    series_id = _first_query_value(query, ("series_id", "sid"))
    if mid and series_id and mid.isdigit() and series_id.isdigit():
        return mid, series_id

    path_parts = [part for part in parsed.path.split("/") if part]
    if parsed.netloc.lower() == "space.bilibili.com" and len(path_parts) >= 3:
        if path_parts[1] in {"lists", "series"} and path_parts[0].isdigit() and path_parts[2].isdigit():
            return path_parts[0], path_parts[2]

    return None


def _has_series_query_keys(url: str) -> bool:
    query = parse_qs(urlparse(url).query)
    return bool(
        (query.get("mid") or query.get("spmid"))
        and (query.get("series_id") or query.get("sid"))
    )


class BilibiliClient:
    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        cookie_file: Path | None = None,
        request_sleep_seconds: float = 0.0,
    ) -> None:
        self._request_sleep_seconds = request_sleep_seconds
        self._owns_client = client is None
        if client is None:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                "Referer": "https://www.bilibili.com/",
            }
            if cookie_file is not None and cookie_file.exists():
                cookie = cookie_file.read_text(encoding="utf-8").strip()
                if cookie:
                    headers["Cookie"] = cookie
            client = httpx.AsyncClient(
                headers=headers,
                trust_env=False,
                timeout=20.0,
            )
        self._client = client

    async def __aenter__(self) -> "BilibiliClient":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _get_json(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = await self._client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 0:
            message = payload.get("message") or payload.get("msg") or "Bilibili API request failed"
            raise BilibiliApiError(f"{message} (code={payload.get('code')})")
        if self._request_sleep_seconds:
            await asyncio.sleep(self._request_sleep_seconds)
        return payload

    async def get_video_by_bvid(self, bvid: str) -> list[VideoItem]:
        payload = await self._get_json(VIEW_URL, params={"bvid": bvid})
        return self._map_view_data(payload["data"])

    async def get_subtitle_transcript(
        self, aid: int, cid: int, prefer_ai: bool = True
    ) -> Transcript | None:
        payload = await self._get_json(PLAYER_WBI_URL, params={"aid": aid, "cid": cid})
        subtitles = ((payload.get("data") or {}).get("subtitle") or {}).get("subtitles") or []
        if not subtitles:
            return None

        usable_subtitles = [subtitle for subtitle in subtitles if subtitle.get("subtitle_url")]
        if not usable_subtitles:
            return None

        for subtitle in self._ordered_subtitles(usable_subtitles, prefer_ai):
            subtitle_url = subtitle.get("subtitle_url")
            if subtitle_url.startswith("//"):
                subtitle_url = f"https:{subtitle_url}"

            response = await self._client.get(subtitle_url)
            response.raise_for_status()
            transcript = parse_subtitle_json(response.json())
            if transcript.lines:
                return transcript
        return None

    @staticmethod
    def _ordered_subtitles(subtitles: list[dict[str, Any]], prefer_ai: bool) -> list[dict[str, Any]]:
        ai = [subtitle for subtitle in subtitles if subtitle.get("ai_type")]
        human = [subtitle for subtitle in subtitles if not subtitle.get("ai_type")]
        if prefer_ai:
            return [*ai, *human]
        return [*human, *ai]

    @staticmethod
    def _map_view_data(data: dict[str, Any]) -> list[VideoItem]:
        bvid = data.get("bvid")
        pages = data.get("pages") or [{}]
        owner = data.get("owner") or {}
        stat = data.get("stat") or {}
        pubdate = data.get("pubdate")
        published_at = (
            datetime.fromtimestamp(pubdate, tz=timezone.utc) if pubdate is not None else None
        )

        videos: list[VideoItem] = []
        for fallback_index, page in enumerate(pages, start=1):
            part_index = int(page.get("page") or fallback_index)
            videos.append(
                VideoItem(
                    url=_video_url(bvid, part_index),
                    bvid=bvid,
                    aid=data.get("aid"),
                    cid=page.get("cid"),
                    title=data.get("title") or page.get("part") or bvid or "",
                    owner_name=owner.get("name"),
                    owner_mid=str(owner["mid"]) if owner.get("mid") is not None else None,
                    published_at=published_at,
                    view_count=stat.get("view"),
                    part_index=part_index,
                    part_title=page.get("part"),
                    duration_seconds=page.get("duration"),
                )
            )
        return videos

    async def get_uploader_videos(
        self, mid: str, page_size: int = 30, max_pages: int | None = None
    ) -> list[VideoItem]:
        videos: list[VideoItem] = []
        page = 1
        while max_pages is None or page <= max_pages:
            payload = await self._get_json(
                UPLOADER_URL,
                params={"mid": mid, "pn": page, "ps": page_size, "order": "pubdate"},
            )
            vlist = ((payload.get("data") or {}).get("list") or {}).get("vlist") or []
            if not vlist:
                break
            for item in vlist:
                bvid = item.get("bvid")
                if bvid:
                    videos.extend(await self.get_video_by_bvid(bvid))
            page += 1
        return videos

    # Bilibili uses different endpoint families for favorite media lists and series.
    # Keep both branches explicit so URL parsing failures are visible to the caller.
    async def get_collection_videos(
        self, url: str, page_size: int = 20, max_pages: int | None = None
    ) -> list[VideoItem]:
        series_ids = _extract_series_ids(url)
        if series_ids:
            mid, series_id = series_ids
            return await self.get_series_videos(mid, series_id, page_size, max_pages)
        if _has_series_query_keys(url):
            raise BilibiliApiError(f"Could not parse collection URL: {url}")
        media_id = _extract_collection_media_id(url)
        if media_id is None:
            raise BilibiliApiError(f"Could not parse collection URL: {url}")
        return await self.get_favorite_videos(media_id, page_size, max_pages)

    async def get_favorite_videos(
        self, media_id: str, page_size: int = 20, max_pages: int | None = None
    ) -> list[VideoItem]:
        videos: list[VideoItem] = []
        page = 1
        while max_pages is None or page <= max_pages:
            payload = await self._get_json(
                FAVORITE_URL,
                params={"media_id": media_id, "pn": page, "ps": page_size},
            )
            data = payload.get("data") or {}
            media_items = data.get("medias") or data.get("media_list") or []
            if not media_items:
                break
            for item in media_items:
                bvid = item.get("bvid")
                if bvid:
                    videos.extend(await self.get_video_by_bvid(bvid))
            if data.get("has_more") is False:
                break
            page += 1
        return videos

    async def get_series_videos(
        self, mid: str, series_id: str, page_size: int = 30, max_pages: int | None = None
    ) -> list[VideoItem]:
        videos: list[VideoItem] = []
        page = 1
        total: int | None = None
        archive_count = 0
        while max_pages is None or page <= max_pages:
            payload = await self._get_json(
                SERIES_URL,
                params={"mid": mid, "series_id": series_id, "pn": page, "ps": page_size},
            )
            data = payload.get("data") or {}
            archives = data.get("archives") or []
            if not archives:
                break
            archive_count += len(archives)
            for item in archives:
                bvid = item.get("bvid")
                if bvid:
                    videos.extend(await self.get_video_by_bvid(bvid))
            page_info = data.get("page") or {}
            total = page_info.get("total") or data.get("total") or total
            if total is not None and archive_count >= int(total):
                break
            page += 1
        return videos


def _video_url(bvid: str | None, part_index: int) -> str:
    if not bvid:
        return "https://www.bilibili.com/video/"
    url = f"https://www.bilibili.com/video/{bvid}"
    if part_index > 1:
        return f"{url}?p={part_index}"
    return url
