from pathlib import Path

import pytest

from mediamark.config import GetnoteWebConfig
import mediamark.getnote.browser_session as browser_session
from mediamark.getnote.browser_session import (
    GetnoteBrowserSession,
    GetnoteWebExportFailed,
    GetnoteWebExportNotFound,
    GetnoteWebGenerationTimeout,
    GetnoteWebLoginRequired,
)


class FakeDownload:
    def __init__(self, path: Path, *, fail=False):
        self.path = path
        self.fail = fail

    def save_as(self, target: Path):
        if self.fail:
            raise RuntimeError("download failed")
        target.write_text(self.path.read_text(encoding="utf-8"), encoding="utf-8")


class FakeDownloadContext:
    def __init__(self, download):
        self.value = download

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return None


class FakeLocator:
    def __init__(self, page, name):
        self.page = page
        self.name = name

    def count(self):
        return 1 if self.name in self.page.available else 0

    def is_visible(self):
        return self.name not in self.page.hidden

    def is_enabled(self):
        return self.name not in self.page.disabled

    @property
    def first(self):
        return self

    def click(self, timeout=None):
        self.page.action_timeouts.append(timeout)
        self.page.clicked.append(self.name)

    def fill(self, value, timeout=None):
        self.page.action_timeouts.append(timeout)
        self.page.filled.append((self.name, value))

    def press(self, key, timeout=None):
        self.page.action_timeouts.append(timeout)
        self.page.pressed.append((self.name, key))


class FakePage:
    def __init__(self, download):
        self.download = download
        self.available = {
            "textarea[placeholder*='链接']",
            "button:has-text('保存')",
            "text=Markdown",
        }
        self.hidden = set()
        self.disabled = set()
        self.clicked = []
        self.filled = []
        self.pressed = []
        self.urls = []
        self.load_states = []
        self.timeouts = []
        self.default_timeout = None
        self.action_timeouts = []

    def set_default_timeout(self, timeout):
        self.default_timeout = timeout

    def goto(self, url, wait_until=None, timeout=None):
        self.urls.append(url)

    def wait_for_load_state(self, state=None, timeout=None):
        self.load_states.append(state)
        return None

    def wait_for_timeout(self, ms):
        self.timeouts.append(ms)
        return None

    def locator(self, selector):
        return FakeLocator(self, selector)

    def expect_download(self, timeout=None):
        return FakeDownloadContext(self.download)


class FakeContext:
    def __init__(self, page, *, fail_close=False):
        self.page = page
        self.fail_close = fail_close
        self.closed = False

    def new_page(self):
        return self.page

    def close(self):
        self.closed = True
        if self.fail_close:
            raise RuntimeError("close failed")


class FakeChromium:
    def __init__(self, context):
        self.context = context
        self.launch_kwargs = None

    def launch_persistent_context(self, *args, **kwargs):
        self.launch_args = args
        self.launch_kwargs = kwargs
        return self.context


class FakePlaywright:
    def __init__(self, chromium):
        self.chromium = chromium

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return None


def test_browser_session_exports_markdown_with_fake_playwright(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("# exported", encoding="utf-8")
    page = FakePage(FakeDownload(source))
    context = FakeContext(page)
    chromium = FakeChromium(context)
    config = GetnoteWebConfig(
        enabled=True,
        user_data_dir=tmp_path / "profile",
        download_dir=tmp_path / "downloads",
        timeout_seconds=10,
        browser_channel="msedge",
    )
    session = GetnoteBrowserSession(
        config,
        playwright_factory=lambda: FakePlaywright(chromium),
    )

    exported = session.export_markdown_for_url("https://www.bilibili.com/video/BV1")

    assert exported.exists()
    assert exported.name.startswith("getnote-export-")
    assert exported.name.endswith(".md")
    assert exported.read_text(encoding="utf-8") == "# exported"
    assert (
        "textarea[placeholder*='链接']",
        "https://www.bilibili.com/video/BV1",
    ) in page.filled
    assert "button:has-text('保存')" in page.clicked
    assert "text=Markdown" in page.clicked
    assert chromium.launch_kwargs["headless"] is False
    assert chromium.launch_kwargs["channel"] == "msedge"
    assert chromium.launch_kwargs["accept_downloads"] is True
    assert page.default_timeout == 10000
    assert page.action_timeouts == [10000, 10000, 10000]
    assert "networkidle" not in page.load_states
    assert context.closed is True


def test_browser_session_auto_uses_detected_existing_browser_channel(
    tmp_path, monkeypatch
):
    source = tmp_path / "source.md"
    source.write_text("# exported", encoding="utf-8")
    page = FakePage(FakeDownload(source))
    context = FakeContext(page)
    chromium = FakeChromium(context)
    monkeypatch.setattr(
        browser_session,
        "detect_browser_channel",
        lambda: "msedge",
    )
    config = GetnoteWebConfig(
        enabled=True,
        user_data_dir=tmp_path / "profile",
        download_dir=tmp_path / "downloads",
    )
    session = GetnoteBrowserSession(
        config,
        playwright_factory=lambda: FakePlaywright(chromium),
    )

    session.export_markdown_for_url("https://www.bilibili.com/video/BV1")

    assert chromium.launch_kwargs["channel"] == "msedge"


def test_browser_session_omits_channel_when_auto_detects_no_existing_browser(
    tmp_path, monkeypatch
):
    source = tmp_path / "source.md"
    source.write_text("# exported", encoding="utf-8")
    page = FakePage(FakeDownload(source))
    context = FakeContext(page)
    chromium = FakeChromium(context)
    monkeypatch.setattr(browser_session, "detect_browser_channel", lambda: None)
    config = GetnoteWebConfig(
        enabled=True,
        user_data_dir=tmp_path / "profile",
        download_dir=tmp_path / "downloads",
    )
    session = GetnoteBrowserSession(
        config,
        playwright_factory=lambda: FakePlaywright(chromium),
    )

    session.export_markdown_for_url("https://www.bilibili.com/video/BV1")

    assert "channel" not in chromium.launch_kwargs


def test_browser_session_presses_enter_when_submit_button_missing(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("# exported", encoding="utf-8")
    page = FakePage(FakeDownload(source))
    page.available.remove("button:has-text('保存')")
    context = FakeContext(page)
    chromium = FakeChromium(context)
    config = GetnoteWebConfig(
        enabled=True,
        user_data_dir=tmp_path / "profile",
        download_dir=tmp_path / "downloads",
        timeout_seconds=10,
    )
    session = GetnoteBrowserSession(
        config,
        playwright_factory=lambda: FakePlaywright(chromium),
    )

    session.export_markdown_for_url("https://www.bilibili.com/video/BV1")

    assert (
        "textarea[placeholder*='链接']",
        "Enter",
    ) in page.pressed


def test_browser_session_fails_when_export_locator_missing(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("# exported", encoding="utf-8")
    page = FakePage(FakeDownload(source))
    page.available.remove("text=Markdown")
    context = FakeContext(page)
    chromium = FakeChromium(context)
    config = GetnoteWebConfig(enabled=True, user_data_dir=tmp_path / "profile")
    session = GetnoteBrowserSession(
        config,
        playwright_factory=lambda: FakePlaywright(chromium),
    )

    with pytest.raises(GetnoteWebGenerationTimeout):
        session.export_markdown_for_url("https://www.bilibili.com/video/BV1")


def test_browser_session_waits_when_export_locator_is_hidden(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("# exported", encoding="utf-8")
    page = FakePage(FakeDownload(source))
    page.hidden.add("text=Markdown")
    context = FakeContext(page)
    chromium = FakeChromium(context)
    config = GetnoteWebConfig(
        enabled=True,
        user_data_dir=tmp_path / "profile",
        timeout_seconds=1,
    )
    session = GetnoteBrowserSession(
        config,
        playwright_factory=lambda: FakePlaywright(chromium),
    )

    with pytest.raises(GetnoteWebGenerationTimeout):
        session.export_markdown_for_url("https://www.bilibili.com/video/BV1")

    assert "text=Markdown" not in page.clicked


def test_browser_session_fails_when_export_locator_disappears_before_download(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("# exported", encoding="utf-8")
    page = FakePage(FakeDownload(source))
    page.available.remove("text=Markdown")
    context = FakeContext(page)
    chromium = FakeChromium(context)
    config = GetnoteWebConfig(enabled=True, user_data_dir=tmp_path / "profile")
    session = GetnoteBrowserSession(
        config,
        playwright_factory=lambda: FakePlaywright(chromium),
    )

    with pytest.raises(GetnoteWebExportNotFound):
        session._export_markdown(page, timeout_ms=1000, target=tmp_path / "out.md")


def test_browser_session_fails_when_download_save_fails(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("# exported", encoding="utf-8")
    page = FakePage(FakeDownload(source, fail=True))
    context = FakeContext(page)
    chromium = FakeChromium(context)
    config = GetnoteWebConfig(
        enabled=True,
        user_data_dir=tmp_path / "profile",
        download_dir=tmp_path / "downloads",
    )
    session = GetnoteBrowserSession(
        config,
        playwright_factory=lambda: FakePlaywright(chromium),
    )

    with pytest.raises(GetnoteWebExportFailed):
        session.export_markdown_for_url("https://www.bilibili.com/video/BV1")

    assert context.closed is True


def test_browser_session_fails_when_login_input_missing(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("# exported", encoding="utf-8")
    page = FakePage(FakeDownload(source))
    page.available.remove("textarea[placeholder*='链接']")
    context = FakeContext(page)
    chromium = FakeChromium(context)
    config = GetnoteWebConfig(
        enabled=True,
        user_data_dir=tmp_path / "profile",
        timeout_seconds=1,
    )
    session = GetnoteBrowserSession(
        config,
        playwright_factory=lambda: FakePlaywright(chromium),
    )

    with pytest.raises(GetnoteWebLoginRequired):
        session.export_markdown_for_url("https://www.bilibili.com/video/BV1")

    assert page.timeouts
    assert context.closed is True


def test_browser_session_preserves_original_error_when_context_close_fails(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("# exported", encoding="utf-8")
    page = FakePage(FakeDownload(source, fail=True))
    context = FakeContext(page, fail_close=True)
    chromium = FakeChromium(context)
    config = GetnoteWebConfig(
        enabled=True,
        user_data_dir=tmp_path / "profile",
        download_dir=tmp_path / "downloads",
    )
    session = GetnoteBrowserSession(
        config,
        playwright_factory=lambda: FakePlaywright(chromium),
    )

    with pytest.raises(GetnoteWebExportFailed, match="download failed"):
        session.export_markdown_for_url("https://www.bilibili.com/video/BV1")

    assert context.closed is True
