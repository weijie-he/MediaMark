from pathlib import Path

import pytest

from mediamark.config import GetnoteWebConfig
from mediamark.getnote.downloads import GetnoteWebExportError
from mediamark.getnote.web_client import GetnoteWebClient, GetnoteWebQuotaExceeded
from mediamark.models import VideoItem


class FakeSession:
    def __init__(self, markdown_path: Path, *, error: Exception | None = None):
        self.markdown_path = markdown_path
        self.error = error
        self.calls = []

    def export_markdown_for_url(self, url: str) -> Path:
        self.calls.append(url)
        if self.error is not None:
            raise self.error
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

    with pytest.raises(GetnoteWebQuotaExceeded, match="max_items_per_run=1"):
        client.save_url(make_video())

    assert session.calls == ["https://www.bilibili.com/video/BV1xx411c7mD"]


def test_getnote_web_client_does_not_consume_quota_on_export_failure(tmp_path):
    exported = tmp_path / "export.md"
    exported.write_text("# recovered", encoding="utf-8")
    session = FakeSession(exported, error=RuntimeError("browser failed"))
    client = GetnoteWebClient(
        GetnoteWebConfig(
            enabled=True,
            user_data_dir=tmp_path / "profile",
            max_items_per_run=1,
        ),
        session=session,
    )

    with pytest.raises(RuntimeError, match="browser failed"):
        client.save_url(make_video())

    session.error = None
    result = client.save_url(make_video())

    assert result.note.raw_markdown == "# recovered"
    assert len(session.calls) == 2


def test_getnote_web_client_does_not_consume_quota_on_read_failure(tmp_path):
    bad = tmp_path / "bad.txt"
    bad.write_text("not markdown", encoding="utf-8")
    good = tmp_path / "good.md"
    good.write_text("# recovered", encoding="utf-8")
    session = FakeSession(bad)
    client = GetnoteWebClient(
        GetnoteWebConfig(
            enabled=True,
            user_data_dir=tmp_path / "profile",
            max_items_per_run=1,
        ),
        session=session,
    )

    with pytest.raises(GetnoteWebExportError, match="Markdown"):
        client.save_url(make_video())

    session.markdown_path = good
    result = client.save_url(make_video())

    assert result.note.raw_markdown == "# recovered"
    assert len(session.calls) == 2
