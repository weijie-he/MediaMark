from mediamark.config import GetnoteWebConfig


class GetnoteWebClient:
    def __init__(self, config: GetnoteWebConfig) -> None:
        self.config = config

    def save_url(self, video):
        raise NotImplementedError(
            "GetnoteWebClient is implemented in the browser automation task"
        )
