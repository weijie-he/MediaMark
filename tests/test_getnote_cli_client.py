import subprocess

import pytest

from mediamark.getnote.cli_client import GetnoteCliClient, GetnoteCliError, parse_getnote_payload


def test_parse_getnote_payload_with_summary_and_markdown():
    payload = {
        "title": "Example",
        "summary": "这是摘要",
        "markdown": "## 要点\n\n- A\n\n## 逐字稿\n\n正文",
    }

    note = parse_getnote_payload(payload)

    assert note.summary == "这是摘要"
    assert note.raw_markdown == "## 要点\n\n- A\n\n## 逐字稿\n\n正文"
    assert note.has_summary is True


def test_parse_getnote_payload_with_nested_data():
    payload = {
        "data": {
            "note": {
                "summary": "嵌套摘要",
                "content": "正文",
            }
        }
    }

    note = parse_getnote_payload(payload)

    assert note.summary == "嵌套摘要"
    assert note.transcript_text == "正文"


def test_parse_getnote_payload_uses_direct_nested_data_payload():
    payload = {
        "data": {
            "summary": "直接 data 摘要",
            "content": "直接 data 正文",
        }
    }

    note = parse_getnote_payload(payload)

    assert note.summary == "直接 data 摘要"
    assert note.transcript_text == "直接 data 正文"


def test_parse_getnote_payload_maps_md_alias_to_raw_markdown():
    payload = {
        "summary": "摘要",
        "md": "# 标题\n\n正文",
    }

    note = parse_getnote_payload(payload)

    assert note.raw_markdown == "# 标题\n\n正文"


def test_parse_getnote_payload_maps_transcript_to_transcript_text():
    payload = {
        "summary": "摘要",
        "transcript": "逐字稿正文",
    }

    note = parse_getnote_payload(payload)

    assert note.transcript_text == "逐字稿正文"


def test_parse_getnote_payload_extracts_key_points_and_outline_lists():
    payload = {
        "abstract": "摘要",
        "points": ["要点一", "要点二"],
        "outline": ["开场", "结尾"],
    }

    note = parse_getnote_payload(payload)

    assert note.summary == "摘要"
    assert note.key_points == ["要点一", "要点二"]
    assert note.outline == ["开场", "结尾"]


def test_parse_getnote_payload_ignores_non_list_key_points_and_outline():
    payload = {
        "key_points": "不是列表",
        "outline": {"title": "也不是列表"},
    }

    note = parse_getnote_payload(payload)

    assert note.key_points == []
    assert note.outline == []


def test_save_url_invokes_getnote_cli_and_parses_stdout(monkeypatch):
    calls = []

    def fake_run(args, check, capture_output, text, env=None):
        calls.append(
            {
                "args": args,
                "check": check,
                "capture_output": capture_output,
                "text": text,
            }
        )
        return subprocess.CompletedProcess(
            args,
            0,
            stdout='{"summary": "CLI 摘要", "text": "正文"}',
            stderr="",
        )

    monkeypatch.setattr("mediamark.getnote.cli_client.subprocess.run", fake_run)

    note = GetnoteCliClient(cli_path="/bin/getnote").save_url("https://example.com/video")

    assert calls == [
        {
            "args": ["/bin/getnote", "save", "https://example.com/video", "-o", "json"],
            "check": False,
            "capture_output": True,
            "text": True,
        }
    ]
    assert note.summary == "CLI 摘要"
    assert note.transcript_text == "正文"


def test_save_url_passes_profile_environment(monkeypatch):
    captured = {}

    def fake_run(args, check, capture_output, text, env):
        captured["env"] = env
        return subprocess.CompletedProcess(
            args,
            0,
            stdout='{"summary":"摘要","text":"正文"}',
            stderr="",
        )

    monkeypatch.setenv("EXISTING_ENV", "keep")
    monkeypatch.setattr("mediamark.getnote.cli_client.subprocess.run", fake_run)

    GetnoteCliClient(cli_path="getnote", env={"GETNOTE_HOME": "/tmp/getnote-main"}).save_url(
        "https://example.com/video"
    )

    assert captured["env"]["EXISTING_ENV"] == "keep"
    assert captured["env"]["GETNOTE_HOME"] == "/tmp/getnote-main"


def test_save_url_raises_getnote_cli_error_on_nonzero_return_code(monkeypatch):
    def fake_run(args, check, capture_output, text, env=None):
        return subprocess.CompletedProcess(
            args,
            2,
            stdout="partial stdout",
            stderr="failed stderr",
        )

    monkeypatch.setattr("mediamark.getnote.cli_client.subprocess.run", fake_run)

    with pytest.raises(GetnoteCliError) as exc_info:
        GetnoteCliClient().save_url("https://example.com/video")

    message = str(exc_info.value)
    assert "failed stderr" in message
    assert "partial stdout" in message


def test_save_url_wraps_subprocess_launch_failures(monkeypatch):
    def fake_run(args, check, capture_output, text, env=None):
        raise FileNotFoundError("missing")

    monkeypatch.setattr("mediamark.getnote.cli_client.subprocess.run", fake_run)

    with pytest.raises(GetnoteCliError) as exc_info:
        GetnoteCliClient(cli_path="/missing/getnote").save_url("https://example.com/video")

    message = str(exc_info.value)
    assert "/missing/getnote" in message
    assert "missing" in message


def test_save_url_raises_getnote_cli_error_on_invalid_json_stdout(monkeypatch):
    def fake_run(args, check, capture_output, text, env=None):
        return subprocess.CompletedProcess(args, 0, stdout="not json", stderr="")

    monkeypatch.setattr("mediamark.getnote.cli_client.subprocess.run", fake_run)

    with pytest.raises(GetnoteCliError) as exc_info:
        GetnoteCliClient().save_url("https://example.com/video")

    assert "Invalid JSON" in str(exc_info.value)


def test_save_url_raises_getnote_cli_error_on_non_object_json_stdout(monkeypatch):
    def fake_run(args, check, capture_output, text, env=None):
        return subprocess.CompletedProcess(args, 0, stdout="[]", stderr="")

    monkeypatch.setattr("mediamark.getnote.cli_client.subprocess.run", fake_run)

    with pytest.raises(GetnoteCliError):
        GetnoteCliClient().save_url("https://example.com/video")


def test_save_url_raises_getnote_cli_error_on_bad_scalar_field_type(monkeypatch):
    def fake_run(args, check, capture_output, text, env=None):
        return subprocess.CompletedProcess(args, 0, stdout='{"summary": ["bad"]}', stderr="")

    monkeypatch.setattr("mediamark.getnote.cli_client.subprocess.run", fake_run)

    with pytest.raises(GetnoteCliError):
        GetnoteCliClient().save_url("https://example.com/video")
