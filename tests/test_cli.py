import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from mediamark.models import ProcessResult, VideoItem
from mediamark.storage.manifest import ManifestStore


runner = CliRunner()


def make_video(
    bvid: str,
    *,
    title: str | None = None,
    published_at: datetime | None = None,
    view_count: int | None = None,
    part_index: int = 1,
    duration_seconds: int | None = None,
) -> VideoItem:
    return VideoItem(
        url=f"https://www.bilibili.com/video/{bvid}",
        bvid=bvid,
        aid=1,
        cid=2,
        title=title or bvid,
        owner_name="UP",
        owner_mid="123",
        published_at=published_at,
        view_count=view_count,
        part_index=part_index,
        part_title=title or bvid,
        duration_seconds=duration_seconds,
    )


def test_run_help_lists_cli_options_and_sort_modes():
    from mediamark.cli import app

    result = runner.invoke(app, ["run", "--help"])

    assert result.exit_code == 0
    for expected in [
        "source",
        "time-desc",
        "time-asc",
        "views-desc",
        "views-asc",
        "--config",
        "-c",
        "--output",
        "-o",
        "--sort",
        "--limit",
        "--no-getnote",
        "--dry-run",
        "--estimate-getnote",
        "--skip-existing",
        "--no-skip-existing",
        "--part-selection",
    ]:
        assert expected in result.output


def test_filter_selected_part_keeps_matching_part():
    from mediamark.cli import _filter_selected_part

    videos = [
        make_video("BV1xx411c7mD", part_index=1),
        make_video("BV1xx411c7mD", part_index=2),
    ]

    selected = _filter_selected_part(videos, part_index=2, input_value="input")

    assert [video.part_index for video in selected] == [2]


def test_filter_selected_part_raises_when_part_missing():
    from mediamark.cli import _filter_selected_part

    with pytest.raises(typer.BadParameter) as exc_info:
        _filter_selected_part(
            [make_video("BV1xx411c7mD", part_index=1)],
            part_index=9,
            input_value="input",
        )

    assert "p=9" in str(exc_info.value)


def test_dry_run_sorts_limits_and_does_not_create_pipeline_or_getnote(monkeypatch):
    from mediamark import cli

    videos = [
        make_video("BV_LOW00001", view_count=10, title="low"),
        make_video("BV_HIGH0001", view_count=300, title="high"),
        make_video("BV_MID00001", view_count=100, title="mid"),
    ]

    class FakeBilibiliClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return None

        async def get_uploader_videos(self, mid: str):
            assert mid == "123"
            return videos

    def fail_getnote(*args, **kwargs):
        raise AssertionError("dry-run must not create GetnoteCliClient")

    def fail_pipeline(*args, **kwargs):
        raise AssertionError("dry-run must not create Pipeline")

    monkeypatch.setattr(cli, "BilibiliClient", FakeBilibiliClient)
    monkeypatch.setattr(cli, "GetnoteCliClient", fail_getnote)
    monkeypatch.setattr(cli, "Pipeline", fail_pipeline)

    result = runner.invoke(
        cli.app,
        ["run", "mid:123", "--sort", "views-desc", "--limit", "2", "--dry-run"],
    )

    assert result.exit_code == 0
    assert result.output.index("BV_HIGH0001") < result.output.index("BV_MID00001")
    assert "BV_LOW00001" not in result.output
    assert "high" in result.output
    assert "mid" in result.output


def test_dry_run_prints_part_index_and_part_title(monkeypatch):
    from mediamark import cli

    video = make_video("BV1xx411c7mD", title="课程", part_index=2)
    video.part_title = "第二讲"

    class FakeBilibiliClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return None

        async def get_video_by_bvid(self, bvid: str):
            return [video]

    monkeypatch.setattr(cli, "BilibiliClient", FakeBilibiliClient)

    result = runner.invoke(cli.app, ["run", "BV1xx411c7mD", "--dry-run"])

    assert result.exit_code == 0
    assert "P2" in result.output
    assert "第二讲" in result.output


def test_run_passes_option_overrides_into_pipeline(monkeypatch, tmp_path):
    from mediamark import cli

    video = make_video("BV1xx411c7mD")
    captured: dict[str, object] = {}

    class FakeBilibiliClient:
        def __init__(self, *args, **kwargs):
            captured["bilibili_kwargs"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return None

        async def get_video_by_bvid(self, bvid: str):
            assert bvid == "BV1xx411c7mD"
            return [video]

    class FakeManifestStore:
        def __init__(self, path: Path):
            captured["manifest_path"] = path

    class FakePipeline:
        def __init__(self, config, bilibili, getnote, manifest):
            captured["output_dir"] = config.output_dir
            captured["config_limit"] = config.limits.limit
            captured["getnote_enabled"] = config.getnote.enabled
            captured["getnote"] = getnote
            captured["manifest"] = manifest

        async def process(self, videos, sort, limit, skip_existing):
            captured["videos"] = videos
            captured["sort"] = sort
            captured["limit"] = limit
            captured["skip_existing"] = skip_existing
            return [
                ProcessResult(video=video, status="done"),
                ProcessResult(video=video, status="failed"),
                ProcessResult(video=video, status="skipped"),
            ]

    monkeypatch.setattr(cli, "BilibiliClient", FakeBilibiliClient)
    monkeypatch.setattr(cli, "ManifestStore", FakeManifestStore)
    monkeypatch.setattr(cli, "Pipeline", FakePipeline)

    result = runner.invoke(
        cli.app,
        [
            "run",
            "BV1xx411c7mD",
            "--output",
            str(tmp_path / "notes"),
            "--limit",
            "2",
            "--no-getnote",
            "--no-skip-existing",
        ],
    )

    assert result.exit_code == 0
    assert captured["output_dir"] == tmp_path / "notes"
    assert captured["config_limit"] == 2
    assert captured["getnote_enabled"] is False
    assert captured["getnote"] is None
    assert captured["videos"] == [video]
    assert captured["sort"] == "source"
    assert captured["limit"] == 2
    assert captured["skip_existing"] is False
    assert "cookie_file" in captured["bilibili_kwargs"]
    assert captured["bilibili_kwargs"]["request_sleep_seconds"] == 1.0
    assert "done=1 failed=1 skipped=1" in result.output


def test_run_part_selection_all_overrides_config(monkeypatch):
    from mediamark import cli

    captured: dict[str, object] = {}

    class FakeBilibiliClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return None

        async def get_video_by_bvid(self, bvid: str):
            return [
                make_video(bvid, part_index=1),
                make_video(bvid, part_index=2),
            ]

    class FakeManifestStore:
        def __init__(self, path: Path):
            pass

    class FakePipeline:
        def __init__(self, config, bilibili, getnote, manifest):
            pass

        async def process(self, videos, sort, limit, skip_existing):
            captured["videos"] = videos
            return []

    monkeypatch.setattr(cli, "BilibiliClient", FakeBilibiliClient)
    monkeypatch.setattr(cli, "ManifestStore", FakeManifestStore)
    monkeypatch.setattr(cli, "Pipeline", FakePipeline)

    result = runner.invoke(
        cli.app,
        [
            "run",
            "https://www.bilibili.com/video/BV1xx411c7mD?p=2",
            "--part-selection",
            "all",
            "--no-getnote",
        ],
    )

    assert result.exit_code == 0
    assert [video.part_index for video in captured["videos"]] == [1, 2]


def test_run_expands_output_override_before_pipeline(monkeypatch):
    from mediamark import cli

    video = make_video("BV1xx411c7mD")
    captured: dict[str, object] = {}

    class FakeBilibiliClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return None

        async def get_video_by_bvid(self, bvid: str):
            return [video]

    class FakeManifestStore:
        def __init__(self, path: Path):
            pass

    class FakePipeline:
        def __init__(self, config, bilibili, getnote, manifest):
            captured["output_dir"] = config.output_dir

        async def process(self, videos, sort, limit, skip_existing):
            return []

    monkeypatch.setattr(cli, "BilibiliClient", FakeBilibiliClient)
    monkeypatch.setattr(cli, "ManifestStore", FakeManifestStore)
    monkeypatch.setattr(cli, "Pipeline", FakePipeline)

    result = runner.invoke(
        cli.app,
        ["run", "BV1xx411c7mD", "--output", "~/mediamark-cli-test", "--no-getnote"],
    )

    assert result.exit_code == 0
    assert captured["output_dir"] == Path.home() / "mediamark-cli-test"


def test_missing_config_path_reports_cli_friendly_error(tmp_path):
    from mediamark.cli import app

    missing_config = tmp_path / "missing.yaml"

    result = runner.invoke(
        app,
        ["run", "BV1xx411c7mD", "--config", str(missing_config), "--dry-run"],
    )

    assert result.exit_code != 0
    assert "config" in result.output.lower()
    assert "error" in result.output.lower()
    assert missing_config.name in result.output
    assert "Traceback" not in result.output


def test_expand_input_recursively_reads_non_empty_file_lines(tmp_path):
    from mediamark.cli import _expand_input

    nested = tmp_path / "nested.txt"
    nested.write_text("BVnested0001\n\n", encoding="utf-8")
    inputs = tmp_path / "inputs.txt"
    inputs.write_text(
        f"BVdirect0001\n\nmid:42\n{nested}\n",
        encoding="utf-8",
    )

    class FakeClient:
        async def get_video_by_bvid(self, bvid: str):
            return [make_video(bvid)]

        async def get_uploader_videos(self, mid: str):
            assert mid == "42"
            return [make_video("BV_UPLOADER1"), make_video("BV_UPLOADER2")]

        async def get_collection_videos(self, url: str):
            raise AssertionError(f"unexpected collection URL: {url}")

    result = asyncio.run(_expand_input(FakeClient(), str(inputs)))

    assert [video.bvid for video in result] == [
        "BVdirect0001",
        "BV_UPLOADER1",
        "BV_UPLOADER2",
        "BVnested0001",
    ]


def test_expand_input_filters_selected_part_from_video_url():
    from mediamark.cli import _expand_input

    class FakeClient:
        async def get_video_by_bvid(self, bvid: str):
            return [
                make_video(bvid, part_index=1),
                make_video(bvid, part_index=2),
            ]

    result = asyncio.run(
        _expand_input(
            FakeClient(),
            "https://www.bilibili.com/video/BV1xx411c7mD?p=2",
        )
    )

    assert [video.part_index for video in result] == [2]


def test_expand_input_can_ignore_selected_part_when_requested():
    from mediamark.cli import _expand_input

    class FakeClient:
        async def get_video_by_bvid(self, bvid: str):
            return [
                make_video(bvid, part_index=1),
                make_video(bvid, part_index=2),
            ]

    result = asyncio.run(
        _expand_input(
            FakeClient(),
            "https://www.bilibili.com/video/BV1xx411c7mD?p=2",
            part_selection="all",
        )
    )

    assert [video.part_index for video in result] == [1, 2]


def test_expand_input_supports_douyin_single_url():
    from mediamark.cli import _expand_input

    class FakeClient:
        pass

    result = asyncio.run(
        _expand_input(FakeClient(), "https://www.douyin.com/video/123")
    )

    assert result[0].platform == "douyin"
    assert result[0].external_id == "123"


def test_expand_csv_input_respects_douyin_platform(tmp_path):
    from mediamark.cli import _expand_input

    path = tmp_path / "links.csv"
    path.write_text(
        "url,platform,tags\nhttps://example.com/share/123,douyin,short\n",
        encoding="utf-8",
    )

    class FakeClient:
        pass

    result = asyncio.run(_expand_input(FakeClient(), str(path)))

    assert result[0].platform == "douyin"
    assert result[0].tags == ["short"]


def test_expand_input_supports_xiaohongshu_single_url():
    from mediamark.cli import _expand_input

    class FakeClient:
        pass

    result = asyncio.run(
        _expand_input(FakeClient(), "https://www.xiaohongshu.com/explore/abc123")
    )

    assert result[0].platform == "xiaohongshu"
    assert result[0].external_id == "abc123"


def test_expand_input_rejects_directory_input(tmp_path):
    from mediamark.cli import _expand_input

    class FakeClient:
        pass

    with pytest.raises(typer.BadParameter):
        asyncio.run(_expand_input(FakeClient(), str(tmp_path)))


def test_expand_input_rejects_cyclic_file_input(tmp_path):
    from mediamark.cli import _expand_input

    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text(f"{second}\n", encoding="utf-8")
    second.write_text(f"{first}\n", encoding="utf-8")

    class FakeClient:
        pass

    with pytest.raises(typer.BadParameter, match="recursive|cyclic"):
        asyncio.run(_expand_input(FakeClient(), str(first)))


def test_status_command_prints_manifest_counts(tmp_path):
    from mediamark.cli import app

    manifest = tmp_path / "manifest.jsonl"
    store = ManifestStore(manifest)
    store.record_done("a", "url-a", tmp_path / "a.md", "bilibili_subtitle")
    store.record_failed("b", "url-b", "network")
    config = tmp_path / "config.yaml"
    config.write_text(f'manifest_path: "{manifest}"\n', encoding="utf-8")

    result = runner.invoke(app, ["status", "--config", str(config)])

    assert result.exit_code == 0
    assert "done=1" in result.output
    assert "failed=1" in result.output
    assert "url-b" in result.output


def test_status_command_supports_json_output(tmp_path):
    from mediamark.cli import app

    manifest = tmp_path / "manifest.jsonl"
    store = ManifestStore(manifest)
    store.record_failed("a", "url-a", "quota", error_code="getnote_quota_exceeded")
    config = tmp_path / "config.yaml"
    config.write_text(f'manifest_path: "{manifest}"\n', encoding="utf-8")

    result = runner.invoke(app, ["status", "--config", str(config), "--json"])

    assert result.exit_code == 0
    assert '"failed": 1' in result.output
    assert '"error_code": "getnote_quota_exceeded"' in result.output


def test_clean_pending_command_marks_pending_records(tmp_path):
    from mediamark.cli import app

    manifest = tmp_path / "manifest.jsonl"
    store = ManifestStore(manifest)
    store.record_pending("a", "url-a")
    config = tmp_path / "config.yaml"
    config.write_text(f'manifest_path: "{manifest}"\n', encoding="utf-8")

    result = runner.invoke(app, ["clean-pending", "--config", str(config)])

    assert result.exit_code == 0
    assert "cleaned=1" in result.output
    assert ManifestStore(manifest).latest_records()["a"]["status"] == "skipped"


def test_retry_failed_reprocesses_failed_manifest_urls(monkeypatch, tmp_path):
    from mediamark import cli

    manifest_path = tmp_path / "manifest.jsonl"
    store = ManifestStore(manifest_path)
    store.record_failed(
        "BV1xx411c7mD:1",
        "https://www.bilibili.com/video/BV1xx411c7mD",
        "network",
    )
    config_path = tmp_path / "config.yaml"
    config_path.write_text(f'manifest_path: "{manifest_path}"\n', encoding="utf-8")
    captured = {}

    async def fake_run_inputs(
        input_values, config, sort, skip_existing, dry_run, estimate_getnote=False
    ):
        captured["input_values"] = input_values
        captured["skip_existing"] = skip_existing
        captured["dry_run"] = dry_run
        captured["estimate_getnote"] = estimate_getnote
        return [ProcessResult(video=make_video("BV1xx411c7mD"), status="done")]

    monkeypatch.setattr(cli, "_run_inputs", fake_run_inputs)

    result = runner.invoke(cli.app, ["retry-failed", "--config", str(config_path)])

    assert result.exit_code == 0
    assert captured["input_values"] == ["https://www.bilibili.com/video/BV1xx411c7mD"]
    assert captured["skip_existing"] is False
    assert captured["dry_run"] is False
    assert captured["estimate_getnote"] is False
    assert "done=1 failed=0 skipped=0" in result.output


def test_retry_failed_filters_by_error_code(monkeypatch, tmp_path):
    from mediamark import cli

    manifest = tmp_path / "manifest.jsonl"
    store = ManifestStore(manifest)
    store.record_failed("a", "url-a", "quota", error_code="getnote_quota_exceeded")
    store.record_failed("b", "url-b", "network", error_code="network_error")
    config = tmp_path / "config.yaml"
    config.write_text(f'manifest_path: "{manifest}"\n', encoding="utf-8")
    captured = {}

    async def fake_run_inputs(
        input_values, config, sort, skip_existing, dry_run, estimate_getnote=False
    ):
        captured["input_values"] = input_values
        return []

    monkeypatch.setattr(cli, "_run_inputs", fake_run_inputs)

    result = runner.invoke(
        cli.app,
        ["retry-failed", "--config", str(config), "--error-code", "network_error"],
    )

    assert result.exit_code == 0
    assert captured["input_values"] == ["url-b"]


def test_run_dry_run_estimate_getnote_prints_summary(monkeypatch):
    from mediamark import cli

    class FakeBilibiliClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return None

        async def get_video_by_bvid(self, bvid: str):
            return [make_video(bvid, duration_seconds=120)]

        async def get_subtitle_transcript(self, aid, cid, prefer_ai=True):
            return None

    monkeypatch.setattr(cli, "BilibiliClient", FakeBilibiliClient)

    result = runner.invoke(
        cli.app,
        ["run", "BV1xx411c7mD", "--dry-run", "--estimate-getnote"],
    )

    assert result.exit_code == 0
    assert "getnote_fallbacks=1" in result.output
    assert "getnote_minutes=2" in result.output


def test_platforms_command_lists_capabilities():
    from mediamark.cli import app

    result = runner.invoke(app, ["platforms"])

    assert result.exit_code == 0
    assert "bilibili" in result.output
    assert "douyin" in result.output
    assert "xiaohongshu" in result.output
    assert "single_video" in result.output


def test_platforms_command_supports_json_output():
    from mediamark.cli import app

    result = runner.invoke(app, ["platforms", "--json"])

    assert result.exit_code == 0
    assert '"platform": "douyin"' in result.output
    assert '"platform": "xiaohongshu"' in result.output


def test_doctor_reports_getnote_and_paths(monkeypatch, tmp_path):
    from mediamark.cli import app

    config_path = tmp_path / "config.yaml"
    manifest_path = tmp_path / "data" / "manifest.jsonl"
    output_dir = tmp_path / "out"
    config_path.write_text(
        f"""
output_dir: "{output_dir}"
manifest_path: "{manifest_path}"
getnote:
  cli_path: "getnote"
""",
        encoding="utf-8",
    )
    monkeypatch.setattr("mediamark.cli.shutil.which", lambda value: "/usr/bin/getnote")

    result = runner.invoke(app, ["doctor", "--config", str(config_path)])

    assert result.exit_code == 0
    assert "config=ok" in result.output
    assert "output_dir=ok" in result.output
    assert "manifest_path=ok" in result.output
    assert "getnote=ok" in result.output


def test_doctor_does_not_create_missing_output_or_manifest_directories(
    monkeypatch, tmp_path
):
    from mediamark.cli import app

    config_path = tmp_path / "config.yaml"
    output_dir = tmp_path / "missing-output"
    manifest_path = tmp_path / "missing-data" / "manifest.jsonl"
    config_path.write_text(
        f"""
output_dir: "{output_dir}"
manifest_path: "{manifest_path}"
getnote:
  cli_path: "getnote"
""",
        encoding="utf-8",
    )
    def fake_access(path, mode):
        return Path(path) == config_path

    monkeypatch.setattr("mediamark.cli.shutil.which", lambda value: "/usr/bin/getnote")
    monkeypatch.setattr("mediamark.cli.os.access", fake_access)

    result = runner.invoke(app, ["doctor", "--config", str(config_path)])

    assert result.exit_code == 0
    assert "output_dir=failed" in result.output
    assert "manifest_path=failed" in result.output
    assert not output_dir.exists()
    assert not manifest_path.parent.exists()
