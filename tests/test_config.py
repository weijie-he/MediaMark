from pathlib import Path

import pytest
from pydantic import ValidationError

from mediamark.config import load_config


def test_load_config_defaults(tmp_path):
    config = load_config(None)

    assert config.output_dir == Path("./output/transcripts")
    assert config.bilibili.cookie_file == Path.home() / ".config/mediamark/bilibili.cookie"
    assert config.bilibili.part_selection == "selected"
    assert config.getnote.enabled is True
    assert config.getnote.budget.max_fallbacks_per_run is None
    assert config.getnote.budget.max_minutes_per_run is None
    assert config.markdown.filename_template == "{published_at}-{title}-{bvid}.md"


def test_load_config_overrides_paths(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
output_dir: "./notes"
manifest_path: "./state/manifest.jsonl"
getnote:
  enabled: false
""",
        encoding="utf-8",
    )

    config = load_config(config_file)

    assert config.output_dir == Path("./notes")
    assert config.manifest_path == Path("./state/manifest.jsonl")
    assert config.getnote.enabled is False


def test_load_config_allows_all_parts_mode(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
bilibili:
  part_selection: all
""",
        encoding="utf-8",
    )

    config = load_config(config_file)

    assert config.bilibili.part_selection == "all"


def test_load_config_accepts_getnote_budget(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
getnote:
  budget:
    max_fallbacks_per_run: 2
    max_minutes_per_run: 30
""",
        encoding="utf-8",
    )

    config = load_config(config_file)

    assert config.getnote.budget.max_fallbacks_per_run == 2
    assert config.getnote.budget.max_minutes_per_run == 30


def test_load_config_accepts_getnote_profiles(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
getnote:
  profiles:
    - name: main
      enabled: true
      cli_path: getnote
      env:
        GETNOTE_HOME: "$MEDIAMARK_TEST_HOME/main"
      budget:
        max_fallbacks_per_run: 2
""",
        encoding="utf-8",
    )

    config = load_config(config_file)

    assert config.getnote.profiles[0].name == "main"
    assert config.getnote.profiles[0].enabled is True
    assert config.getnote.profiles[0].env["GETNOTE_HOME"].endswith("/main")
    assert config.getnote.profiles[0].budget.max_fallbacks_per_run == 2


def test_load_config_rejects_getnote_auto_web_config(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
getnote:
  enabled: true
  fallback_mode: auto
  web:
    enabled: true
    user_data_dir: "~/Library/Application Support/MediaMark/getnote-web"
    headless: false
    browser_channel: msedge
    timeout_seconds: 300
    max_items_per_run: 3
    download_dir: "~/.cache/mediamark/getnote-web-downloads"
""",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="split-links"):
        load_config(config_file)


def test_load_config_rejects_invalid_getnote_fallback_mode(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
getnote:
  fallback_mode: private-api
""",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        load_config(config_file)


@pytest.mark.parametrize("fallback_mode", ["web", "auto"])
def test_load_config_rejects_getnote_web_fallback_modes(tmp_path, fallback_mode):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        f"""
getnote:
  fallback_mode: {fallback_mode}
""",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="cli"):
        load_config(config_file)


@pytest.mark.parametrize("field_name", ["timeout_seconds", "max_items_per_run"])
def test_load_config_rejects_bool_getnote_web_numbers(tmp_path, field_name):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        f"""
getnote:
  web:
    {field_name}: true
""",
        encoding="utf-8",
    )

    with pytest.raises(
        ValidationError, match="Boolean values are not valid numeric"
    ):
        load_config(config_file)


def test_load_config_accepts_output_directory_template(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
output:
  directory_template: "{platform}/{collection}"
""",
        encoding="utf-8",
    )

    config = load_config(config_file)

    assert config.output.directory_template == "{platform}/{collection}"


def test_load_config_accepts_archive_options(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
archive:
  dedupe: false
  write_collection_index: false
  collection_index_dir: "_indexes"
""",
        encoding="utf-8",
    )

    config = load_config(config_file)

    assert config.archive.dedupe is False
    assert config.archive.write_collection_index is False
    assert config.archive.collection_index_dir == "_indexes"


def test_load_config_rejects_duplicate_getnote_profile_names(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
getnote:
  profiles:
    - name: main
    - name: main
""",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        load_config(config_file)


def test_load_config_expands_environment_variables_in_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIAMARK_TEST_DIR", str(tmp_path))
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
output_dir: "$MEDIAMARK_TEST_DIR/notes"
""",
        encoding="utf-8",
    )

    config = load_config(config_file)

    assert config.output_dir == tmp_path / "notes"


def test_load_config_expands_environment_variables_in_getnote_cli_path(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("MEDIAMARK_TEST_BIN", str(tmp_path / "bin"))
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
getnote:
  cli_path: "$MEDIAMARK_TEST_BIN/getnote"
""",
        encoding="utf-8",
    )

    config = load_config(config_file)

    assert config.getnote.cli_path == str(tmp_path / "bin/getnote")


def test_load_config_rejects_extra_top_level_keys(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
unknown_key: true
""",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        load_config(config_file)


@pytest.mark.parametrize(
    "yaml_text",
    [
        """
bilibili:
  request_sleep_seconds: -1
""",
        """
limits:
  limit: 0
""",
    ],
)
def test_load_config_rejects_invalid_numeric_values(tmp_path, yaml_text):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml_text, encoding="utf-8")

    with pytest.raises(ValidationError):
        load_config(config_file)


@pytest.mark.parametrize(
    "yaml_text",
    [
        """
bilibili:
  request_sleep_seconds: true
""",
        """
limits:
  limit: true
""",
        """
getnote:
  budget:
    max_fallbacks_per_run: true
""",
        """
getnote:
  budget:
    max_minutes_per_run: true
""",
    ],
)
def test_load_config_rejects_boolean_numeric_values(tmp_path, yaml_text):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml_text, encoding="utf-8")

    with pytest.raises(ValidationError):
        load_config(config_file)
