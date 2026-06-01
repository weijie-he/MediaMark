from pathlib import Path

import pytest

from mediamark.getnote.downloads import GetnoteWebExportError, read_markdown_download


def test_read_markdown_download_accepts_md_file(tmp_path):
    path = tmp_path / "note.md"
    path.write_text("# 标题\n\n正文", encoding="utf-8")

    assert read_markdown_download(path) == "# 标题\n\n正文"


def test_read_markdown_download_accepts_uppercase_md_extension(tmp_path):
    path = tmp_path / "note.MD"
    path.write_text("# 标题", encoding="utf-8")

    assert read_markdown_download(path) == "# 标题"


def test_read_markdown_download_rejects_empty_file(tmp_path):
    path = tmp_path / "note.md"
    path.write_text("   ", encoding="utf-8")

    with pytest.raises(GetnoteWebExportError, match="empty"):
        read_markdown_download(path)


def test_read_markdown_download_rejects_non_markdown_extension(tmp_path):
    path = tmp_path / "note.txt"
    path.write_text("# 标题", encoding="utf-8")

    with pytest.raises(GetnoteWebExportError, match="Markdown"):
        read_markdown_download(path)


def test_read_markdown_download_wraps_missing_file(tmp_path):
    path = tmp_path / "missing.md"

    with pytest.raises(GetnoteWebExportError, match="not found"):
        read_markdown_download(path)


def test_read_markdown_download_wraps_directory_path(tmp_path):
    path = tmp_path / "note.md"
    path.mkdir()

    with pytest.raises(GetnoteWebExportError, match="not a file"):
        read_markdown_download(path)


def test_read_markdown_download_wraps_invalid_utf8(tmp_path):
    path = tmp_path / "note.md"
    path.write_bytes(b"\xff\xfe\x00")

    with pytest.raises(GetnoteWebExportError, match="valid UTF-8"):
        read_markdown_download(path)
