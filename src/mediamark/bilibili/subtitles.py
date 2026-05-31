from typing import Any

from mediamark.models import Transcript, TranscriptLine


def _parse_seconds(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_subtitle_json(payload: dict[str, Any]) -> Transcript:
    lines: list[TranscriptLine] = []
    body = payload.get("body")
    if not isinstance(body, list):
        return Transcript(source="bilibili_subtitle", lines=lines)

    for item in body:
        if not isinstance(item, dict):
            continue
        text = str(item.get("content") or "").strip()
        if not text:
            continue
        start_seconds = _parse_seconds(item.get("from"))
        if start_seconds is None:
            continue
        end_seconds = _parse_seconds(item.get("to")) if item.get("to") is not None else None
        lines.append(
            TranscriptLine(
                start_seconds=start_seconds,
                end_seconds=end_seconds,
                text=text,
            )
        )
    return Transcript(source="bilibili_subtitle", lines=lines)
