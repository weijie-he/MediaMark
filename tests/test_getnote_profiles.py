import pytest

from mediamark.config import GetnoteBudgetConfig, GetnoteProfileConfig
from mediamark.getnote.profiles import (
    GetnoteProfilePool,
    GetnoteProfileResult,
    NoGetnoteProfileAvailable,
)
from mediamark.models import NoteContent, VideoItem


class FakeClient:
    def __init__(self, name, *, fail=False):
        self.name = name
        self.fail = fail
        self.calls = []

    def save_url(self, url):
        self.calls.append(url)
        if self.fail:
            raise RuntimeError(f"{self.name} failed")
        return NoteContent(summary=f"{self.name} 摘要", transcript_text="正文")


def make_video():
    return VideoItem(
        url="https://www.bilibili.com/video/BV1xx411c7mD",
        bvid="BV1xx411c7mD",
        aid=1,
        cid=2,
        title="视频",
    )


def test_profile_pool_uses_first_enabled_profile():
    clients = {"main": FakeClient("main"), "backup": FakeClient("backup")}
    pool = GetnoteProfilePool(
        [
            GetnoteProfileConfig(name="main"),
            GetnoteProfileConfig(name="backup"),
        ],
        client_factory=lambda profile: clients[profile.name],
    )

    result = pool.save_url(make_video())

    assert isinstance(result, GetnoteProfileResult)
    assert result.profile_name == "main"
    assert result.provider_name == "cli"
    assert result.note.summary == "main 摘要"
    assert clients["backup"].calls == []


def test_profile_pool_skips_profile_when_budget_exhausted():
    clients = {"main": FakeClient("main"), "backup": FakeClient("backup")}
    pool = GetnoteProfilePool(
        [
            GetnoteProfileConfig(
                name="main",
                budget=GetnoteBudgetConfig(max_fallbacks_per_run=1),
            ),
            GetnoteProfileConfig(name="backup"),
        ],
        client_factory=lambda profile: clients[profile.name],
    )

    pool.save_url(make_video())
    second = pool.save_url(make_video())

    assert second.profile_name == "backup"


def test_profile_pool_raises_when_no_profiles_are_available():
    pool = GetnoteProfilePool(
        [GetnoteProfileConfig(name="main", enabled=False)],
        client_factory=lambda profile: FakeClient(profile.name),
    )

    with pytest.raises(NoGetnoteProfileAvailable):
        pool.save_url(make_video())
