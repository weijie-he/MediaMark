import csv
import json
from pathlib import Path
from typing import Any

from mediamark.models import BatchInputRow


def parse_input_file(path: Path) -> list[BatchInputRow]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _parse_csv(path)
    if suffix == ".jsonl":
        return _parse_jsonl(path)
    return _parse_text(path)


def _parse_text(path: Path) -> list[BatchInputRow]:
    return [
        BatchInputRow(url=line.strip())
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _parse_csv(path: Path) -> list[BatchInputRow]:
    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames or "url" not in reader.fieldnames:
            raise ValueError("CSV input must include a url column")
        return [_row_from_mapping(row) for row in reader if (row.get("url") or "").strip()]


def _parse_jsonl(path: Path) -> list[BatchInputRow]:
    rows: list[BatchInputRow] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"JSONL input row {line_number} must be an object")
        rows.append(_row_from_mapping(payload))
    return rows


def _row_from_mapping(mapping: dict[str, Any]) -> BatchInputRow:
    data = dict(mapping)
    if not data.get("platform"):
        data.pop("platform", None)
    if data.get("collection") == "":
        data["collection"] = None
    data["tags"] = _parse_tags(data.get("tags"))
    if "allow_getnote" in data:
        data["allow_getnote"] = _parse_optional_bool(data.get("allow_getnote"))
    return BatchInputRow.model_validate(data)


def _parse_tags(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _parse_optional_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"Invalid allow_getnote value: {value}")
