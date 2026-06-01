from pathlib import Path
from typing import Protocol

from mediamark.config import GetnoteWebConfig
from mediamark.getnote.browser_session import GetnoteBrowserSession
from mediamark.getnote.downloads import read_markdown_download
from mediamark.getnote.profiles import GetnoteProfileResult
from mediamark.models import NoteContent, VideoItem


class GetnoteWebSession(Protocol):
    def export_markdown_for_url(self, url: str) -> Path:
        ...


class GetnoteWebClient:
    def __init__(
        self,
        config: GetnoteWebConfig,
        session: GetnoteWebSession | None = None,
    ) -> None:
        self.config = config
        self.session = session if session is not None else GetnoteBrowserSession(config)

    def save_url(self, video: VideoItem) -> GetnoteProfileResult:
        markdown_path = self.session.export_markdown_for_url(video.url)
        markdown = read_markdown_download(markdown_path)
        return GetnoteProfileResult(
            note=NoteContent(raw_markdown=markdown),
            profile_name="web",
            provider_name="web",
        )
