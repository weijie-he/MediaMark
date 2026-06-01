from mediamark.config import GetnoteConfig, GetnoteProfileConfig
from mediamark.getnote.cli_client import is_membership_required_error
from mediamark.getnote.profiles import GetnoteProfilePool, NoGetnoteProfileAvailable
from mediamark.getnote.web_client import GetnoteWebClient
from mediamark.models import VideoItem


def _is_membership_only_failure(exc: Exception) -> bool:
    if isinstance(exc, NoGetnoteProfileAvailable):
        return bool(exc.errors) and all(
            is_membership_required_error(error)
            for error in exc.errors
        )
    return is_membership_required_error(exc)


class AutoGetnoteClient:
    def __init__(self, cli_client: object, web_client: object) -> None:
        self.cli_client = cli_client
        self.web_client = web_client

    def save_url(self, video: VideoItem) -> object:
        try:
            return self.cli_client.save_url(video)
        except Exception as exc:
            if not _is_membership_only_failure(exc):
                raise
            return self.web_client.save_url(video)


def _profiles_from_config(config: GetnoteConfig) -> list[GetnoteProfileConfig]:
    if config.profiles:
        return config.profiles
    return [
        GetnoteProfileConfig(
            name="default",
            enabled=config.enabled,
            cli_path=config.cli_path,
            budget=config.budget,
        )
    ]


def _build_cli_pool(config: GetnoteConfig) -> GetnoteProfilePool:
    return GetnoteProfilePool(_profiles_from_config(config))


def _build_web_client(config: GetnoteConfig) -> GetnoteWebClient:
    if not config.web.enabled:
        raise ValueError("getnote.web.enabled must be true when fallback_mode uses web")
    return GetnoteWebClient(config.web)


def build_getnote_client(config: GetnoteConfig) -> object:
    if config.fallback_mode == "cli":
        return _build_cli_pool(config)
    if config.fallback_mode == "web":
        return _build_web_client(config)
    if config.fallback_mode == "auto":
        return AutoGetnoteClient(
            cli_client=_build_cli_pool(config),
            web_client=_build_web_client(config),
        )
    raise ValueError(f"Unsupported Get笔记 fallback mode: {config.fallback_mode}")
