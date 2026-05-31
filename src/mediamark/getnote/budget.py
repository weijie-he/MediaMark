from math import ceil

from mediamark.config import GetnoteBudgetConfig
from mediamark.models import VideoItem


class GetnoteBudgetExceeded(RuntimeError):
    pass


class GetnoteBudget:
    def __init__(self, config: GetnoteBudgetConfig) -> None:
        self.config = config
        self.fallbacks_used = 0
        self.minutes_used = 0

    def consume(self, video: VideoItem) -> None:
        next_fallbacks = self.fallbacks_used + 1
        if (
            self.config.max_fallbacks_per_run is not None
            and next_fallbacks > self.config.max_fallbacks_per_run
        ):
            raise GetnoteBudgetExceeded(
                "Get笔记 budget exhausted: "
                f"max_fallbacks_per_run={self.config.max_fallbacks_per_run}"
            )

        video_minutes = _duration_minutes(video)
        next_minutes = self.minutes_used + video_minutes
        if (
            self.config.max_minutes_per_run is not None
            and next_minutes > self.config.max_minutes_per_run
        ):
            raise GetnoteBudgetExceeded(
                "Get笔记 budget exhausted: "
                f"max_minutes_per_run={self.config.max_minutes_per_run}"
            )

        self.fallbacks_used = next_fallbacks
        self.minutes_used = next_minutes


def _duration_minutes(video: VideoItem) -> int:
    if video.duration_seconds is None:
        return 0
    return max(1, ceil(video.duration_seconds / 60))
