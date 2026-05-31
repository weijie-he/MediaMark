import pytest

from mediamark.config import GetnoteBudgetConfig
from mediamark.getnote.budget import GetnoteBudget, GetnoteBudgetExceeded
from mediamark.models import VideoItem


def make_video(duration_seconds=None):
    return VideoItem(
        url="https://www.bilibili.com/video/BV1xx411c7mD",
        bvid="BV1xx411c7mD",
        aid=1,
        cid=2,
        title="视频",
        duration_seconds=duration_seconds,
    )


def test_budget_allows_unlimited_fallbacks():
    budget = GetnoteBudget(GetnoteBudgetConfig())

    budget.consume(make_video())
    budget.consume(make_video())

    assert budget.fallbacks_used == 2


def test_budget_blocks_after_max_fallbacks():
    budget = GetnoteBudget(GetnoteBudgetConfig(max_fallbacks_per_run=1))

    budget.consume(make_video())

    with pytest.raises(GetnoteBudgetExceeded, match="max_fallbacks_per_run=1"):
        budget.consume(make_video())


def test_budget_blocks_when_minutes_would_exceed_limit():
    budget = GetnoteBudget(GetnoteBudgetConfig(max_minutes_per_run=1))

    with pytest.raises(GetnoteBudgetExceeded, match="max_minutes_per_run=1"):
        budget.consume(make_video(duration_seconds=120))
