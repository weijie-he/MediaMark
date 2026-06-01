from collections.abc import Callable
from dataclasses import dataclass

from mediamark.config import GetnoteProfileConfig
from mediamark.getnote.budget import GetnoteBudget, GetnoteBudgetExceeded
from mediamark.getnote.cli_client import GetnoteCliClient
from mediamark.models import NoteContent, VideoItem


class NoGetnoteProfileAvailable(RuntimeError):
    pass


@dataclass
class GetnoteProfileResult:
    note: NoteContent
    profile_name: str
    provider_name: str = "cli"


class GetnoteProfilePool:
    def __init__(
        self,
        profiles: list[GetnoteProfileConfig],
        client_factory: Callable[[GetnoteProfileConfig], GetnoteCliClient] | None = None,
    ) -> None:
        self.profiles = [profile for profile in profiles if profile.enabled]
        self.client_factory = client_factory or (
            lambda profile: GetnoteCliClient(cli_path=profile.cli_path, env=profile.env)
        )
        self.budgets = {
            profile.name: GetnoteBudget(profile.budget)
            for profile in self.profiles
        }
        self.clients = {
            profile.name: self.client_factory(profile)
            for profile in self.profiles
        }

    def save_url(self, video: VideoItem) -> GetnoteProfileResult:
        errors: list[str] = []
        for profile in self.profiles:
            try:
                self.budgets[profile.name].consume(video)
                note = self.clients[profile.name].save_url(video.url)
            except GetnoteBudgetExceeded as exc:
                errors.append(f"{profile.name}: {exc}")
                continue
            except Exception as exc:
                errors.append(f"{profile.name}: {exc}")
                continue
            return GetnoteProfileResult(note=note, profile_name=profile.name)

        raise NoGetnoteProfileAvailable("; ".join(errors) or "No enabled Get笔记 profiles")
