import re
from enum import StrEnum
from urllib.parse import parse_qs, urlparse

from pydantic import BaseModel


class InputKind(StrEnum):
    VIDEO = "video"
    COLLECTION = "collection"
    UPLOADER = "uploader"
    FILE = "file"


class ClassifiedInput(BaseModel):
    kind: InputKind
    value: str
    raw: str
    part_index: int | None = None


_BVID_RE = re.compile(r"(BV[a-zA-Z0-9]{10})(?![a-zA-Z0-9])")
_BARE_BVID_RE = re.compile(r"BV[a-zA-Z0-9]{10}")


def _is_bilibili_host(host: str) -> bool:
    return host == "bilibili.com" or host.endswith(".bilibili.com")


def _query_has_numeric_value(query: dict[str, list[str]], keys: tuple[str, ...]) -> bool:
    return any(value.isdigit() for key in keys for value in query.get(key, []))


def _first_positive_int(query: dict[str, list[str]], key: str) -> int | None:
    values = query.get(key) or []
    if not values or not values[0].isdigit():
        return None
    parsed = int(values[0])
    return parsed if parsed >= 1 else None


def _is_medialist_id(value: str) -> bool:
    return value.isdigit() or (
        value.startswith("ml") and value.removeprefix("ml").isdigit()
    )


def extract_bvid(value: str) -> str | None:
    match = _BVID_RE.search(value)
    return match.group(1) if match else None


def classify_input(value: str) -> ClassifiedInput:
    raw = value.strip()
    if raw.startswith("mid:"):
        mid = raw.removeprefix("mid:")
        if mid.isdigit():
            return ClassifiedInput(kind=InputKind.UPLOADER, value=mid, raw=raw)
        return ClassifiedInput(kind=InputKind.FILE, value=raw, raw=raw)

    parsed = urlparse(raw)
    host = parsed.netloc.lower()
    path = parsed.path
    path_parts = [part for part in path.split("/") if part]
    query = parse_qs(parsed.query)
    is_bilibili_url = _is_bilibili_host(host)

    bvid = extract_bvid(raw)
    if bvid and is_bilibili_url:
        return ClassifiedInput(
            kind=InputKind.VIDEO,
            value=bvid,
            raw=raw,
            part_index=_first_positive_int(query, "p"),
        )
    if bvid and ((not parsed.scheme and not host) and _BARE_BVID_RE.fullmatch(raw)):
        return ClassifiedInput(kind=InputKind.VIDEO, value=bvid, raw=raw)

    if host == "space.bilibili.com":
        if not path_parts or not path_parts[0].isdigit():
            return ClassifiedInput(kind=InputKind.FILE, value=raw, raw=raw)
        if len(path_parts) >= 2 and path_parts[1] in {"lists", "series"}:
            if len(path_parts) >= 3 and path_parts[2].isdigit():
                return ClassifiedInput(kind=InputKind.COLLECTION, value=raw, raw=raw)
            return ClassifiedInput(kind=InputKind.FILE, value=raw, raw=raw)
        return ClassifiedInput(kind=InputKind.UPLOADER, value=path_parts[0], raw=raw)

    has_supported_collection_path = any(
        (
            part == "medialist"
            and (
                (
                    index + 1 < len(path_parts)
                    and _is_medialist_id(path_parts[index + 1])
                )
                or (
                    index + 2 < len(path_parts)
                    and path_parts[index + 1] == "play"
                    and _is_medialist_id(path_parts[index + 2])
                )
            )
        )
        or (
            part in {"collection", "list"}
            and index + 1 < len(path_parts)
            and path_parts[index + 1].isdigit()
        )
        for index, part in enumerate(path_parts)
    )

    if is_bilibili_url and (
        has_supported_collection_path
        or _query_has_numeric_value(query, ("list", "media_id", "fid"))
        or (
            _query_has_numeric_value(query, ("mid", "spmid"))
            and _query_has_numeric_value(query, ("series_id", "sid"))
        )
    ):
        return ClassifiedInput(kind=InputKind.COLLECTION, value=raw, raw=raw)

    return ClassifiedInput(kind=InputKind.FILE, value=raw, raw=raw)
