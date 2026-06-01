from pathlib import Path

import pytest

from mediamark.config import GetnoteWebConfig
from mediamark.getnote.web_client import GetnoteWebClient
from mediamark.models import VideoItem


class FakeSession:
    def __init__(self, markdown_path: Path):
        self.markdown_path = markdown_path
        self.calls = []

    def export_markdown_for_url(self, url: str) -> Path:
        self.calls.append(url)
        return self.markdown_path


class FalsySession(FakeSession):
    def __bool__(self):
        return False


def make_video() -> VideoItem:
    return VideoItem(
        url="https://www.bilibili.com/video/BV1xx411c7mD",
        bvid="BV1xx411c7mD",
        aid=1,
        cid=2,
        title="title",
    )


def test_getnote_web_client_returns_raw_markdown(tmp_path):
    exported = tmp_path / "export.md"
    exported.write_text("# Web Markdown", encoding="utf-8")
    session = FakeSession(exported)
    client = GetnoteWebClient(
        GetnoteWebConfig(enabled=True, user_data_dir=tmp_path / "profile"),
        session=session,
    )

    result = client.save_url(make_video())

    assert result.note.raw_markdown == "# Web Markdown"
    assert result.profile_name == "web"
    assert result.provider_name == "web"
    assert session.calls == ["https://www.bilibili.com/video/BV1xx411c7mD"]


def test_getnote_web_client_accepts_falsy_session(tmp_path):
    exported = tmp_path / "export.md"
    exported.write_text("# Web Markdown", encoding="utf-8")
    session = FalsySession(exported)
    client = GetnoteWebClient(
        GetnoteWebConfig(enabled=True, user_data_dir=tmp_path / "profile"),
        session=session,
    )

    result = client.save_url(make_video())

    assert result.note.raw_markdown == "# Web Markdown"
    assert session.calls == ["https://www.bilibili.com/video/BV1xx411c7mD"]


def test_getnote_web_client_respects_max_items_per_run(tmp_path):
    first = tmp_path / "first.md"
    first.write_text("# first", encoding="utf-8")
    session = FakeSession(first)
    client = GetnoteWebClient(
        GetnoteWebConfig(
            enabled=True,
            user_data_dir=tmp_path / "profile",
            max_items_per_run=1,
        ),
        session=session,
    )

    client.save_url(make_video())

    with pytest.raises(RuntimeError, match="max_items_per_run=1"):
        client.save_url(make_video())
