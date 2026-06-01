import json
import os
import subprocess
from typing import Any

from mediamark.models import NoteContent


class GetnoteCliError(RuntimeError):
    pass


def is_membership_required_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return (
        "not_member" in text
        or "10201" in text
        or "openapi 仅对会员开放" in text
        or "仅对会员开放" in text
    )


def _dig_note_payload(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    if isinstance(data, dict):
        note = data.get("note")
        if isinstance(note, dict):
            return note
        return data
    return payload


def _list_or_empty(value: Any) -> list[str]:
    if isinstance(value, list):
        return value
    return []


def _str_or_none(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _first_str(*values: Any) -> str | None:
    for value in values:
        text = _str_or_none(value)
        if text is not None:
            return text
    return None


def _bad_scalar_field(payload: dict[str, Any]) -> str | None:
    note_payload = _dig_note_payload(payload)
    for key in ("summary", "abstract", "markdown", "md", "transcript", "content", "text"):
        value = note_payload.get(key)
        if value is not None and not isinstance(value, str):
            return key
    return None


def parse_getnote_payload(payload: dict[str, Any]) -> NoteContent:
    note_payload = _dig_note_payload(payload)

    return NoteContent(
        summary=_first_str(note_payload.get("summary"), note_payload.get("abstract")),
        key_points=_list_or_empty(note_payload.get("key_points") or note_payload.get("points")),
        outline=_list_or_empty(note_payload.get("outline")),
        transcript_text=_first_str(
            note_payload.get("transcript"),
            note_payload.get("content"),
            note_payload.get("text"),
        ),
        raw_markdown=_first_str(note_payload.get("markdown"), note_payload.get("md")),
    )


class GetnoteCliClient:
    def __init__(self, cli_path: str = "getnote", env: dict[str, str] | None = None) -> None:
        self.cli_path = cli_path
        self.env = env or {}

    def save_url(self, url: str) -> NoteContent:
        try:
            result = subprocess.run(
                [self.cli_path, "save", url, "-o", "json"],
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, **self.env},
            )
        except OSError as exc:
            raise GetnoteCliError(f"Failed to launch getnote CLI {self.cli_path}: {exc}") from exc

        if result.returncode != 0:
            raise GetnoteCliError(
                f"getnote CLI failed with exit code {result.returncode}. "
                f"stderr: {result.stderr} stdout: {result.stdout}"
            )

        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise GetnoteCliError(f"Invalid JSON from getnote CLI: {result.stdout}") from exc

        if not isinstance(payload, dict):
            raise GetnoteCliError("Invalid getnote CLI JSON: expected object payload")

        bad_scalar_field = _bad_scalar_field(payload)
        if bad_scalar_field is not None:
            raise GetnoteCliError(
                f"Invalid getnote CLI JSON: field {bad_scalar_field!r} must be a string"
            )

        try:
            return parse_getnote_payload(payload)
        except Exception as exc:
            raise GetnoteCliError(f"Invalid getnote CLI JSON payload: {exc}") from exc
