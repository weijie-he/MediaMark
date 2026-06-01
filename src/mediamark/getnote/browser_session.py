from pathlib import Path
from typing import Protocol
from uuid import uuid4

from mediamark.config import GetnoteWebConfig


GETNOTE_WEB_URL = "https://www.biji.com"

LINK_INPUT_LOCATORS = [
    "textarea[placeholder*='链接']",
    "textarea[placeholder*='粘贴']",
    "input[placeholder*='链接']",
    "textarea",
]
SUBMIT_LOCATORS = [
    "button:has-text('保存')",
    "button:has-text('生成')",
    "button:has-text('开始')",
    "button:has-text('确定')",
]
MARKDOWN_EXPORT_LOCATORS = [
    "text=Markdown",
    "text=导出 Markdown",
    "text=下载 Markdown",
]


class GetnoteWebBrowserError(RuntimeError):
    pass


class GetnoteWebLoginRequired(GetnoteWebBrowserError):
    pass


class GetnoteWebGenerationTimeout(GetnoteWebBrowserError):
    pass


class GetnoteWebExportNotFound(GetnoteWebBrowserError):
    pass


class GetnoteWebExportFailed(GetnoteWebBrowserError):
    pass


class PlaywrightFactory(Protocol):
    def __call__(self) -> object:
        ...


def _default_playwright_factory() -> object:
    from playwright.sync_api import sync_playwright

    return sync_playwright()


class GetnoteBrowserSession:
    def __init__(
        self,
        config: GetnoteWebConfig,
        playwright_factory: PlaywrightFactory | None = None,
    ) -> None:
        self.config = config
        self.playwright_factory = playwright_factory or _default_playwright_factory

    def export_markdown_for_url(self, url: str) -> Path:
        user_data_dir = self.config.user_data_dir
        download_dir = self.config.download_dir
        user_data_dir.mkdir(parents=True, exist_ok=True)
        download_dir.mkdir(parents=True, exist_ok=True)
        timeout_ms = self.config.timeout_seconds * 1000
        target = download_dir / f"getnote-export-{uuid4().hex}.md"
        context = None

        try:
            with self.playwright_factory() as playwright:
                context = playwright.chromium.launch_persistent_context(
                    str(user_data_dir),
                    headless=self.config.headless,
                    channel="chrome",
                    accept_downloads=True,
                    downloads_path=str(download_dir),
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-popup-blocking",
                    ],
                )
                page = context.new_page()
                page.set_default_timeout(timeout_ms)
                page.goto(
                    GETNOTE_WEB_URL,
                    wait_until="domcontentloaded",
                    timeout=timeout_ms,
                )

                link_input = self._wait_for_login_or_input(page, timeout_ms)
                link_input.fill(url, timeout=timeout_ms)

                self._submit_url(page, timeout_ms)
                self._wait_for_generation(page, timeout_ms)
                return self._export_markdown(page, timeout_ms, target)
        except GetnoteWebBrowserError:
            raise
        except Exception as exc:
            raise GetnoteWebBrowserError(
                f"Get笔记 Web browser automation failed: {exc}"
            ) from exc
        finally:
            if context is not None:
                try:
                    context.close()
                except Exception:
                    pass

    def _wait_for_login_or_input(self, page: object, timeout_ms: int) -> object:
        link_input = self._first_available_locator(page, LINK_INPUT_LOCATORS)
        if link_input is not None:
            return link_input

        print("Get笔记 Web 需要登录：请在打开的 Chrome 窗口完成登录。")
        return self._wait_for_locator(
            page,
            LINK_INPUT_LOCATORS,
            timeout_ms,
            GetnoteWebLoginRequired(
                "Get笔记 Web login or link input was not available"
            ),
            poll_ms=5000,
        )

    def _submit_url(self, page: object, timeout_ms: int) -> None:
        submit = self._first_available_locator(page, SUBMIT_LOCATORS)
        if submit is None:
            raise GetnoteWebBrowserError(
                "Get笔记 Web browser automation failed: submit button not found"
            )
        submit.click(timeout=timeout_ms)

    def _wait_for_generation(self, page: object, timeout_ms: int) -> None:
        self._wait_for_locator(
            page,
            MARKDOWN_EXPORT_LOCATORS,
            timeout_ms,
            GetnoteWebGenerationTimeout(
                "Get笔记 Web note generation timed out before Markdown export was available"
            ),
            poll_ms=3000,
        )

    def _export_markdown(self, page: object, timeout_ms: int, target: Path) -> Path:
        markdown_export = self._first_available_locator(page, MARKDOWN_EXPORT_LOCATORS)
        if markdown_export is None:
            raise GetnoteWebExportNotFound(
                "Get笔记 Web Markdown export action was not found"
            )
        try:
            with page.expect_download(timeout=timeout_ms) as download_info:
                markdown_export.click(timeout=timeout_ms)
            download_info.value.save_as(target)
        except GetnoteWebBrowserError:
            raise
        except Exception as exc:
            raise GetnoteWebExportFailed(
                f"Get笔记 Markdown export failed: {exc}"
            ) from exc
        return target

    def _wait_for_locator(
        self,
        page: object,
        selectors: list[str],
        timeout_ms: int,
        error: GetnoteWebBrowserError,
        poll_ms: int = 1000,
    ) -> object:
        deadline = timeout_ms
        elapsed = 0
        while elapsed <= deadline:
            locator = self._first_available_locator(page, selectors)
            if locator is not None:
                return locator
            wait_ms = min(poll_ms, deadline - elapsed)
            if wait_ms <= 0:
                break
            page.wait_for_timeout(wait_ms)
            elapsed += wait_ms
        raise error

    @staticmethod
    def _first_available_locator(page: object, selectors: list[str]) -> object | None:
        for selector in selectors:
            locator = page.locator(selector)
            if locator.count() > 0:
                first = locator.first()
                if first.is_visible() and first.is_enabled():
                    return first
        return None
