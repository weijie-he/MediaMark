import pytest

from mediamark.config import GetnoteConfig, GetnoteWebConfig
from mediamark.getnote.cli_client import GetnoteCliError
from mediamark.getnote.profiles import GetnoteProfilePool, NoGetnoteProfileAvailable
from mediamark.getnote.provider import AutoGetnoteClient, build_getnote_client
from mediamark.getnote.web_client import GetnoteWebClient
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


def test_build_getnote_client_web_mode_requires_enabled_web_config(tmp_path):
    config = GetnoteConfig(
        fallback_mode="web",
        web=GetnoteWebConfig(enabled=False, user_data_dir=tmp_path / "profile"),
    )

    with pytest.raises(ValueError, match="getnote.web.enabled"):
        build_getnote_client(config)


def test_build_getnote_client_web_mode_returns_web_client(tmp_path):
    config = GetnoteConfig(
        fallback_mode="web",
        web=GetnoteWebConfig(enabled=True, user_data_dir=tmp_path / "profile"),
    )

    client = build_getnote_client(config)

    assert isinstance(client, GetnoteWebClient)
    assert client.config.user_data_dir == tmp_path / "profile"


def test_build_getnote_client_auto_mode_returns_auto_client(tmp_path):
    config = GetnoteConfig(
        fallback_mode="auto",
        web=GetnoteWebConfig(enabled=True, user_data_dir=tmp_path / "profile"),
    )

    client = build_getnote_client(config)

    assert isinstance(client, AutoGetnoteClient)
    assert isinstance(client.cli_client, GetnoteProfilePool)
    assert isinstance(client.web_client, GetnoteWebClient)
