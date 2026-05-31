from dataclasses import dataclass
from typing import Any, Protocol

from mediamark.models import PartSelectionMode, Platform, VideoItem


@dataclass(frozen=True)
class ExpansionContext:
    bilibili_client: Any
    part_selection: PartSelectionMode


class PlatformAdapter(Protocol):
    platform: Platform

    def matches(self, input_value: str) -> bool:
        ...

    async def expand(
        self,
        input_value: str,
        context: ExpansionContext,
    ) -> list[VideoItem]:
        ...
