import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from mediamark.models import PartSelectionMode

GetnoteFallbackMode = Literal["cli", "web", "auto"]


def expand_path(value: Any) -> Path | None:
    if value is None:
        return None
    return Path(os.path.expandvars(str(value))).expanduser()


def _expand_path(value: Any) -> Path | None:
    return expand_path(value)


def _reject_bool(value: Any) -> Any:
    if isinstance(value, bool):
        raise ValueError("Boolean values are not valid numeric config values")
    return value


class BilibiliConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)

    cookie_file: Path | None = Path("~/.config/mediamark/bilibili.cookie")
    prefer_ai_subtitle: bool = True
    request_sleep_seconds: float = Field(default=1.0, ge=0)
    part_selection: PartSelectionMode = "selected"

    @field_validator("cookie_file", mode="before")
    @classmethod
    def expand_cookie_file(cls, value: Any) -> Any:
        return _expand_path(value)

    @field_validator("request_sleep_seconds", mode="before")
    @classmethod
    def reject_bool_sleep_seconds(cls, value: Any) -> Any:
        return _reject_bool(value)


class GetnoteBudgetConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)

    max_fallbacks_per_run: int | None = Field(default=None, ge=1)
    max_minutes_per_run: int | None = Field(default=None, ge=1)

    @field_validator("max_fallbacks_per_run", "max_minutes_per_run", mode="before")
    @classmethod
    def reject_bool_budget_numbers(cls, value: Any) -> Any:
        return _reject_bool(value)


class GetnoteWebConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)

    enabled: bool = False
    user_data_dir: Path = Path("~/.config/mediamark/getnote-web-chrome")
    headless: bool = False
    timeout_seconds: int = Field(default=600, ge=1)
    max_items_per_run: int = Field(default=5, ge=1)
    download_dir: Path = Path("~/.cache/mediamark/getnote-web-downloads")

    @field_validator("user_data_dir", "download_dir", mode="before")
    @classmethod
    def expand_paths(cls, value: Any) -> Any:
        return _expand_path(value)

    @field_validator("timeout_seconds", "max_items_per_run", mode="before")
    @classmethod
    def reject_bool_numbers(cls, value: Any) -> Any:
        return _reject_bool(value)


class GetnoteProfileConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)

    name: str
    enabled: bool = True
    cli_path: str = "getnote"
    env: dict[str, str] = Field(default_factory=dict)
    budget: GetnoteBudgetConfig = Field(default_factory=GetnoteBudgetConfig)

    @field_validator("cli_path", mode="before")
    @classmethod
    def expand_cli_path(cls, value: Any) -> Any:
        expanded = _expand_path(value)
        if expanded is None:
            return None
        return str(expanded)

    @field_validator("env", mode="before")
    @classmethod
    def expand_env_values(cls, value: Any) -> Any:
        if value is None:
            return {}
        return {
            str(key): str(os.path.expandvars(str(raw)).replace("~", str(Path.home()), 1))
            for key, raw in dict(value).items()
        }


class GetnoteConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)

    enabled: bool = True
    fallback_mode: GetnoteFallbackMode = "cli"
    cli_path: str = "getnote"
    budget: GetnoteBudgetConfig = Field(default_factory=GetnoteBudgetConfig)
    profiles: list[GetnoteProfileConfig] = Field(default_factory=list)
    web: GetnoteWebConfig = Field(default_factory=GetnoteWebConfig)

    @field_validator("cli_path", mode="before")
    @classmethod
    def expand_cli_path(cls, value: Any) -> Any:
        expanded = _expand_path(value)
        if expanded is None:
            return None
        return str(expanded)

    @field_validator("profiles")
    @classmethod
    def reject_duplicate_profile_names(
        cls, value: list[GetnoteProfileConfig]
    ) -> list[GetnoteProfileConfig]:
        names = [profile.name for profile in value]
        if len(names) != len(set(names)):
            raise ValueError("Get笔记 profile names must be unique")
        return value


class LimitsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)

    limit: int | None = Field(default=None, ge=1)

    @field_validator("limit", mode="before")
    @classmethod
    def reject_bool_limits(cls, value: Any) -> Any:
        return _reject_bool(value)


class MarkdownConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)

    filename_template: str = "{published_at}-{title}-{bvid}.md"


class OutputConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)

    directory_template: str = ""


class ArchiveConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)

    dedupe: bool = True
    write_collection_index: bool = True
    collection_index_dir: str = "_collections"


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)

    output_dir: Path = Path("./output/transcripts")
    manifest_path: Path = Path("./data/manifest.jsonl")
    bilibili: BilibiliConfig = Field(default_factory=BilibiliConfig)
    getnote: GetnoteConfig = Field(default_factory=GetnoteConfig)
    limits: LimitsConfig = Field(default_factory=LimitsConfig)
    markdown: MarkdownConfig = Field(default_factory=MarkdownConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    archive: ArchiveConfig = Field(default_factory=ArchiveConfig)

    @field_validator("output_dir", "manifest_path", mode="before")
    @classmethod
    def expand_path_fields(cls, value: Any) -> Any:
        return _expand_path(value)


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data or {}


def load_config(path: Path | None) -> AppConfig:
    if path is None:
        return AppConfig()
    return AppConfig.model_validate(_read_yaml(path))
