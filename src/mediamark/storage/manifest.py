import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ManifestStore:
    def __init__(self, path: Path):
        self.path = path

    def _append(self, record: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {**record, "recorded_at": datetime.now(timezone.utc).isoformat()}
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False))
            file.write("\n")

    def latest_records(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}

        records: dict[str, dict[str, Any]] = {}
        with self.path.open(encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue
                record = json.loads(line)
                records[record["key"]] = record
        return records

    def completed_keys(self) -> set[str]:
        if not self.path.exists():
            return set()

        completed: set[str] = set()
        with self.path.open(encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue
                record = json.loads(line)
                key = record["key"]
                status = record["status"]
                if status == "done":
                    completed.add(key)
                elif status == "skipped" and record.get("reason") == "already completed":
                    continue
                else:
                    completed.discard(key)
        return completed

    def status_counts(self) -> dict[str, int]:
        counts = {"done": 0, "failed": 0, "pending": 0, "skipped": 0}
        for record in self.latest_records().values():
            status = record.get("status")
            if status in counts:
                counts[status] += 1
        return counts

    def failed_records(self) -> list[dict[str, Any]]:
        return [
            record
            for record in self.latest_records().values()
            if record.get("status") == "failed"
        ]

    def pending_records(self) -> list[dict[str, Any]]:
        return [
            record
            for record in self.latest_records().values()
            if record.get("status") == "pending"
        ]

    def clean_pending(self) -> int:
        pending = self.pending_records()
        for record in pending:
            self.record_skipped(
                key=record["key"],
                url=record["url"],
                reason="cleaned pending",
            )
        return len(pending)

    def next_attempt(self, key: str) -> int:
        record = self.latest_records().get(key)
        if record is None:
            return 1
        return int(record.get("attempt") or 1) + 1

    def record_pending(self, key: str, url: str) -> None:
        self._append({"key": key, "url": url, "status": "pending"})

    def record_done(
        self,
        key: str,
        url: str,
        output_path: Path,
        source: str,
        getnote_profile: str | None = None,
        input_url: str | None = None,
    ) -> None:
        record = {
            "key": key,
            "url": url,
            "status": "done",
            "path": str(output_path),
            "source": source,
        }
        if getnote_profile is not None:
            record["getnote_profile"] = getnote_profile
        if input_url is not None:
            record["input_url"] = input_url
        self._append(record)

    def record_failed(
        self,
        key: str,
        url: str,
        error: str,
        error_code: str | None = None,
        attempt: int | None = None,
        getnote_profile: str | None = None,
        input_url: str | None = None,
    ) -> None:
        record = {"key": key, "url": url, "status": "failed", "error": error}
        if error_code is not None:
            record["error_code"] = error_code
        if attempt is not None:
            record["attempt"] = attempt
        if getnote_profile is not None:
            record["getnote_profile"] = getnote_profile
        if input_url is not None:
            record["input_url"] = input_url
        self._append(record)

    def record_skipped(self, key: str, url: str, reason: str) -> None:
        self._append({"key": key, "url": url, "status": "skipped", "reason": reason})
