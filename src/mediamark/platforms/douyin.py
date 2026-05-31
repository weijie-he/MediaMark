from urllib.parse import urlparse

from mediamark.models import Platform, VideoItem
from mediamark.platforms.base import ExpansionContext


def _is_douyin_host(host: str) -> bool:
    return (
        host == "douyin.com"
        or host.endswith(".douyin.com")
        or host == "iesdouyin.com"
        or host.endswith(".iesdouyin.com")
    )


def _external_id_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    path_parts = [part for part in parsed.path.split("/") if part]
    if not path_parts:
        return None
    if "video" in path_parts:
        index = path_parts.index("video")
        if index + 1 < len(path_parts):
            return path_parts[index + 1]
    return path_parts[-1]


class DouyinAdapter:
    platform: Platform = "douyin"

    def matches(self, input_value: str) -> bool:
        parsed = urlparse(input_value.strip())
        return parsed.scheme in {"http", "https"} and _is_douyin_host(parsed.netloc.lower())

    async def expand(
        self,
        input_value: str,
        context: ExpansionContext,
    ) -> list[VideoItem]:
        url = input_value.strip()
        external_id = _external_id_from_url(url)
        title_suffix = f" {external_id}" if external_id else ""
        return [
            VideoItem(
                url=url,
                bvid=None,
                aid=None,
                cid=None,
                title=f"抖音视频{title_suffix}",
                platform="douyin",
                external_id=external_id,
            )
        ]
