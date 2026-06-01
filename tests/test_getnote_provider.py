import pytest

from mediamark.config import GetnoteConfig, GetnoteWebConfig
from mediamark.getnote.cli_client import GetnoteCliError
from mediamark.getnote.profiles import GetnoteProfilePool, NoGetnoteProfileAvailable
from mediamark.getnote.provider import AutoGetnoteClient, build_getnote_client
from mediamark.models import NoteContent, VideoItem


def make_video() -> VideoItem:
    return VideoItem(
        url="https://www.bilibili.com/video/BV1xx411c7mD",
        bvid="BV1xx411c7mD",
        aid=1,
        cid=2,
        title="title",
        duration_seconds=60,
    )


class FakeClient:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def save_url(self, video):
        self.calls.append(video.url)
        if self.error:
            raise self.error
        return self.result


def test_auto_getnote_client_uses_web_after_not_member_error():
    cli = FakeClient(error=GetnoteCliError("OpenAPI 仅对会员开放 not_member code=10201"))
    web = FakeClient(result=NoteContent(raw_markdown="# web"))
    client = AutoGetnoteClient(cli_client=cli, web_client=web)

    note = client.save_url(make_video())

    assert note.raw_markdown == "# web"
    assert cli.calls == ["https://www.bilibili.com/video/BV1xx411c7mD"]
    assert web.calls == ["https://www.bilibili.com/video/BV1xx411c7mD"]


def test_auto_getnote_client_reraises_non_membership_cli_error():
    cli = FakeClient(error=GetnoteCliError("network down"))
    web = FakeClient(result=NoteContent(raw_markdown="# web"))
    client = AutoGetnoteClient(cli_client=cli, web_client=web)

    with pytest.raises(GetnoteCliError, match="network down"):
        client.save_url(make_video())

    assert web.calls == []


def test_auto_getnote_client_uses_web_after_all_profile_membership_errors():
    cli = FakeClient(
        error=NoGetnoteProfileAvailable(
            "profiles failed",
            errors=[
                GetnoteCliError("not_member"),
                GetnoteCliError("API error code=10201"),
            ],
        )
    )
    web = FakeClient(result=NoteContent(raw_markdown="# web"))
    client = AutoGetnoteClient(cli_client=cli, web_client=web)

    note = client.save_url(make_video())

    assert note.raw_markdown == "# web"
    assert web.calls == ["https://www.bilibili.com/video/BV1xx411c7mD"]


def test_auto_getnote_client_reraises_mixed_profile_errors():
    cli = FakeClient(
        error=NoGetnoteProfileAvailable(
            "profiles failed",
            errors=[
                GetnoteCliError("not_member"),
                GetnoteCliError("network down"),
            ],
        )
    )
    web = FakeClient(result=NoteContent(raw_markdown="# web"))
    client = AutoGetnoteClient(cli_client=cli, web_client=web)

    with pytest.raises(NoGetnoteProfileAvailable, match="profiles failed"):
        client.save_url(make_video())

    assert web.calls == []


def test_build_getnote_client_cli_mode_returns_cli_pool():
    config = GetnoteConfig(fallback_mode="cli")

    client = build_getnote_client(config)

    assert isinstance(client, GetnoteProfilePool)


@pytest.mark.parametrize("fallback_mode", ["web", "auto"])
def test_build_getnote_client_rejects_web_fallback_modes(tmp_path, fallback_mode):
    config = GetnoteConfig(
        fallback_mode=fallback_mode,
        web=GetnoteWebConfig(enabled=True, user_data_dir=tmp_path / "profile"),
    )

    with pytest.raises(ValueError, match="split-links"):
        build_getnote_client(config)
