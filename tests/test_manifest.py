import json
from datetime import datetime, timezone
from pathlib import Path

from mediamark.storage.manifest import ManifestStore


def test_manifest_records_and_reads_completed_items(tmp_path):
    path = tmp_path / "manifest.jsonl"
    store = ManifestStore(path)

    store.record_done(key="BV1:1", url="https://example.com", output_path=Path("out.md"), source="bilibili_subtitle")

    assert store.completed_keys() == {"BV1:1"}


def test_manifest_latest_record_wins(tmp_path):
    path = tmp_path / "manifest.jsonl"
    store = ManifestStore(path)

    store.record_failed(key="BV1:1", url="https://example.com", error="first")
    store.record_done(key="BV1:1", url="https://example.com", output_path=Path("out.md"), source="getnote")

    records = store.latest_records()

    assert records["BV1:1"]["status"] == "done"
    assert records["BV1:1"]["source"] == "getnote"


def test_manifest_done_record_uses_path_field(tmp_path):
    path = tmp_path / "manifest.jsonl"
    store = ManifestStore(path)

    store.record_done(key="BV1:1", url="https://example.com", output_path=Path("out.md"), source="getnote")

    record = store.latest_records()["BV1:1"]

    assert record["path"] == "out.md"
    assert "output_path" not in record


def test_manifest_records_pending_items(tmp_path):
    path = tmp_path / "manifest.jsonl"
    store = ManifestStore(path)

    store.record_pending(key="BV1:1", url="https://example.com")

    records = store.latest_records()

    assert records["BV1:1"]["status"] == "pending"
    assert records["BV1:1"]["url"] == "https://example.com"


def test_manifest_records_skipped_items_with_reason(tmp_path):
    path = tmp_path / "manifest.jsonl"
    store = ManifestStore(path)

    store.record_skipped(key="BV1:1", url="https://example.com", reason="already done")

    records = store.latest_records()

    assert records["BV1:1"]["status"] == "skipped"
    assert records["BV1:1"]["reason"] == "already done"


def test_manifest_latest_records_returns_empty_dict_when_missing(tmp_path):
    store = ManifestStore(tmp_path / "missing.jsonl")

    assert store.latest_records() == {}


def test_manifest_jsonl_contains_recorded_at(tmp_path):
    path = tmp_path / "manifest.jsonl"
    store = ManifestStore(path)

    store.record_failed(key="BV1:1", url="https://example.com", error="boom")

    record = json.loads(path.read_text(encoding="utf-8").strip())

    assert record["recorded_at"]


def test_manifest_record_methods_create_parent_directories(tmp_path):
    path = tmp_path / "nested" / "manifests" / "manifest.jsonl"
    store = ManifestStore(path)

    store.record_pending(key="BV1:1", url="https://example.com")

    assert path.exists()
    assert store.latest_records()["BV1:1"]["status"] == "pending"


def test_manifest_latest_records_skips_blank_lines(tmp_path):
    path = tmp_path / "manifest.jsonl"
    path.write_text(
        "\n"
        + json.dumps({"key": "BV1:1", "url": "https://example.com", "status": "done"})
        + "\n\n",
        encoding="utf-8",
    )
    store = ManifestStore(path)

    records = store.latest_records()

    assert records["BV1:1"]["status"] == "done"


def test_manifest_jsonl_preserves_non_ascii_text(tmp_path):
    path = tmp_path / "manifest.jsonl"
    store = ManifestStore(path)

    store.record_failed(key="BV1:1", url="https://例子.com/视频", error="字幕下载失败")

    text = path.read_text(encoding="utf-8")

    assert "https://例子.com/视频" in text
    assert "字幕下载失败" in text
    assert "\\u" not in text


def test_manifest_recorded_at_is_parseable_timezone_aware_utc(tmp_path):
    path = tmp_path / "manifest.jsonl"
    store = ManifestStore(path)

    store.record_skipped(key="BV1:1", url="https://example.com", reason="已完成")

    record = json.loads(path.read_text(encoding="utf-8").strip())
    recorded_at = datetime.fromisoformat(record["recorded_at"])

    assert recorded_at.tzinfo is not None
    assert recorded_at.utcoffset() == timezone.utc.utcoffset(recorded_at)


def test_manifest_completed_keys_excludes_latest_non_done_status(tmp_path):
    path = tmp_path / "manifest.jsonl"
    store = ManifestStore(path)

    store.record_done(key="BV1:1", url="https://example.com", output_path=Path("out.md"), source="getnote")
    store.record_failed(key="BV1:1", url="https://example.com", error="later failure")

    assert store.completed_keys() == set()


def test_manifest_completed_keys_preserves_done_after_already_completed_skip(tmp_path):
    path = tmp_path / "manifest.jsonl"
    store = ManifestStore(path)

    store.record_done(
        key="BV1:1",
        url="https://example.com",
        output_path=Path("out.md"),
        source="getnote",
    )
    store.record_skipped(key="BV1:1", url="https://example.com", reason="already completed")

    assert store.completed_keys() == {"BV1:1"}


def test_manifest_status_counts_latest_records(tmp_path):
    store = ManifestStore(tmp_path / "manifest.jsonl")
    store.record_pending("a", "url-a")
    store.record_done("a", "url-a", Path("a.md"), "bilibili_subtitle")
    store.record_failed("b", "url-b", "network")
    store.record_pending("c", "url-c")

    assert store.status_counts() == {
        "done": 1,
        "failed": 1,
        "pending": 1,
        "skipped": 0,
    }


def test_manifest_failed_records_returns_latest_failed_records(tmp_path):
    store = ManifestStore(tmp_path / "manifest.jsonl")
    store.record_failed("a", "url-a", "network")
    store.record_done("a", "url-a", Path("a.md"), "bilibili_subtitle")
    store.record_failed("b", "url-b", "quota")

    failed = store.failed_records()

    assert [record["key"] for record in failed] == ["b"]
    assert failed[0]["url"] == "url-b"


def test_manifest_failed_record_stores_error_code_attempt_and_profile(tmp_path):
    store = ManifestStore(tmp_path / "manifest.jsonl")

    store.record_failed(
        key="BV1:1",
        url="https://example.com",
        error="quota",
        error_code="getnote_quota_exceeded",
        attempt=2,
        getnote_profile="main",
        input_url="links.csv",
    )

    record = store.latest_records()["BV1:1"]
    assert record["error_code"] == "getnote_quota_exceeded"
    assert record["attempt"] == 2
    assert record["getnote_profile"] == "main"
    assert record["input_url"] == "links.csv"


def test_manifest_records_getnote_provider_on_done(tmp_path):
    store = ManifestStore(tmp_path / "manifest.jsonl")

    store.record_done(
        key="BV1:1",
        url="https://example.com",
        output_path=Path("out.md"),
        source="getnote",
        getnote_profile="default",
        getnote_provider="web",
    )

    record = store.latest_records()["BV1:1"]
    assert record["getnote_provider"] == "web"


def test_manifest_record_done_preserves_positional_input_url(tmp_path):
    store = ManifestStore(tmp_path / "manifest.jsonl")

    store.record_done(
        "BV1:1",
        "https://example.com",
        Path("out.md"),
        "getnote",
        "default",
        "links.csv",
    )

    record = store.latest_records()["BV1:1"]
    assert record["getnote_profile"] == "default"
    assert record["input_url"] == "links.csv"
    assert "getnote_provider" not in record


def test_manifest_records_getnote_provider_on_failed(tmp_path):
    store = ManifestStore(tmp_path / "manifest.jsonl")

    store.record_failed(
        key="BV1:1",
        url="https://example.com",
        error="boom",
        error_code="getnote_web_export_failed",
        getnote_profile="default",
        getnote_provider="web",
    )

    record = store.latest_records()["BV1:1"]
    assert record["getnote_provider"] == "web"


def test_manifest_record_failed_preserves_positional_input_url(tmp_path):
    store = ManifestStore(tmp_path / "manifest.jsonl")

    store.record_failed(
        "BV1:1",
        "https://example.com",
        "boom",
        "getnote_cli_error",
        2,
        "default",
        "links.csv",
    )

    record = store.latest_records()["BV1:1"]
    assert record["getnote_profile"] == "default"
    assert record["input_url"] == "links.csv"
    assert "getnote_provider" not in record


def test_manifest_next_attempt_uses_latest_record(tmp_path):
    store = ManifestStore(tmp_path / "manifest.jsonl")
    store.record_failed("BV1:1", "url", "first", attempt=1)
    store.record_failed("BV1:1", "url", "second", attempt=2)

    assert store.next_attempt("BV1:1") == 3


def test_manifest_clean_pending_marks_pending_as_skipped(tmp_path):
    store = ManifestStore(tmp_path / "manifest.jsonl")
    store.record_pending("a", "url-a")
    store.record_failed("b", "url-b", "network")

    cleaned = store.clean_pending()

    assert cleaned == 1
    latest = store.latest_records()
    assert latest["a"]["status"] == "skipped"
    assert latest["a"]["reason"] == "cleaned pending"
    assert latest["b"]["status"] == "failed"
