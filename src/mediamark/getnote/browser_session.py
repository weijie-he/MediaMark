from pathlib import Path

from mediamark.config import GetnoteWebConfig


class GetnoteBrowserSession:
    def __init__(self, config: GetnoteWebConfig) -> None:
        self.config = config

    def export_markdown_for_url(self, url: str) -> Path:
        raise NotImplementedError(
            "Getnote browser export is not available before automation wiring"
        )
