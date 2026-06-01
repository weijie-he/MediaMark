import asyncio
import json
import os
import shutil
from pathlib import Path
from typing import Annotated

import pydantic
import typer
import typer.rich_utils
import yaml
from rich.console import Console

from mediamark.bilibili.client import BilibiliClient
from mediamark.config import AppConfig, expand_path, load_config
from mediamark.getnote.provider import build_getnote_client
from mediamark.input_batch import parse_input_file
from mediamark.models import (
    BatchInputRow,
    PartSelectionMode,
    Platform,
    ProcessResult,
    SortMode,
    VideoItem,
    sort_video_items,
)
from mediamark.pipeline import Pipeline
from mediamark.platforms import adapter_for_input, adapter_for_platform
from mediamark.platforms.base import ExpansionContext
from mediamark.platforms.bilibili import filter_selected_part
from mediamark.platforms.capabilities import platform_capabilities
from mediamark.storage.manifest import ManifestStore


typer.rich_utils.MAX_WIDTH = 120

app = typer.Typer(
    help="Convert media content to Markdown, starting with Bilibili subtitles and Get笔记 notes."
)
console = Console()

SORT_HELP = "Sort mode: source, time-desc, time-asc, views-desc, views-asc."


@app.callback()
def main() -> None:
    pass


def _load_config_for_cli(config_path: Path | None) -> AppConfig:
    try:
        return load_config(config_path)
    except (FileNotFoundError, OSError, pydantic.ValidationError, yaml.YAMLError) as exc:
        path_text = (
            f" for path {config_path.name} ({config_path})"
            if config_path is not None
            else ""
        )
        raise typer.BadParameter(f"Config error{path_text}: {exc}") from exc


async def _expand_input(
    client: BilibiliClient,
    input_value: str,
    part_selection: PartSelectionMode = "selected",
    platform: Platform | None = None,
    _file_stack: set[Path] | None = None,
) -> list[VideoItem]:
    context = ExpansionContext(
        bilibili_client=client,
        part_selection=part_selection,
    )
    adapter = adapter_for_platform(platform) if platform else adapter_for_input(input_value)
    if adapter is not None:
        try:
            return await adapter.expand(input_value, context)
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc

    path = Path(input_value).expanduser()
    if not path.exists():
        raise typer.BadParameter(f"File not found: {path}")
    try:
        resolved_path = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise typer.BadParameter(f"Could not resolve input file {path}: {exc}") from exc
    if not resolved_path.is_file():
        raise typer.BadParameter(f"Input path is not a file: {path}")

    file_stack = set() if _file_stack is None else _file_stack
    if resolved_path in file_stack:
        raise typer.BadParameter(
            f"Recursive/cyclic input file detected: {resolved_path}"
        )

    videos: list[VideoItem] = []
    nested_file_stack = {*file_stack, resolved_path}
    structured_input = resolved_path.suffix.lower() in {".csv", ".jsonl"}
    try:
        rows = parse_input_file(resolved_path)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    for row in rows:
        nested_videos = await _expand_input(
            client,
            row.url,
            part_selection=part_selection,
            platform=row.platform if structured_input else None,
            _file_stack=nested_file_stack,
        )
        videos.extend(_apply_batch_metadata(nested_videos, row, str(resolved_path)))
    return videos


def _filter_selected_part(
    videos: list[VideoItem],
    part_index: int | None,
    input_value: str,
) -> list[VideoItem]:
    try:
        return filter_selected_part(videos, part_index, input_value)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _apply_batch_metadata(
    videos: list[VideoItem],
    row: BatchInputRow,
    input_url: str,
) -> list[VideoItem]:
    updated: list[VideoItem] = []
    for video in videos:
        values: dict[str, object] = {}
        if row.tags:
            values["tags"] = list(row.tags)
        if row.collection is not None:
            values["collection"] = row.collection
        if row.allow_getnote is not None:
            values["allow_getnote"] = row.allow_getnote
        if video.input_url is None:
            values["input_url"] = input_url
        updated.append(video.model_copy(update=values) if values else video)
    return updated


def _print_dry_run(videos: list[VideoItem]) -> None:
    for video in videos:
        published = video.published_at.isoformat() if video.published_at else "-"
        views = video.view_count if video.view_count is not None else "-"
        part = f"P{video.part_index}"
        part_title = f" {video.part_title}" if video.part_title else ""
        console.print(
            f"{video.bvid or '-'} {part}{part_title} "
            f"views={views} published={published} {video.title}"
        )


def _print_split_links(videos: list[VideoItem]) -> None:
    for video in videos:
        console.print(video.url)


def _print_result_summary(results: list[ProcessResult]) -> None:
    done = sum(result.status == "done" for result in results)
    failed = sum(result.status == "failed" for result in results)
    skipped = sum(result.status == "skipped" for result in results)
    console.print(f"done={done} failed={failed} skipped={skipped}")


def _print_getnote_estimate(
    fallback_count: int,
    fallback_minutes: int,
    within_budget: bool,
) -> None:
    console.print(
        f"getnote_fallbacks={fallback_count} "
        f"getnote_minutes={fallback_minutes} "
        f"within_budget={str(within_budget).lower()}"
    )


async def _run_inputs(
    input_values: list[str],
    config: AppConfig,
    sort: SortMode,
    skip_existing: bool,
    dry_run: bool,
    estimate_getnote: bool = False,
) -> list[ProcessResult]:
    async with BilibiliClient(
        cookie_file=config.bilibili.cookie_file,
        request_sleep_seconds=config.bilibili.request_sleep_seconds,
    ) as client:
        videos: list[VideoItem] = []
        for input_value in input_values:
            videos.extend(
                await _expand_input(
                    client,
                    input_value,
                    part_selection=config.bilibili.part_selection,
                )
            )

        if dry_run:
            selected_videos = sort_video_items(videos, sort)
            if config.limits.limit is not None:
                selected_videos = selected_videos[: config.limits.limit]
            _print_dry_run(selected_videos)
            if estimate_getnote:
                pipeline = Pipeline(
                    config=config,
                    bilibili=client,
                    getnote=None,
                    manifest=ManifestStore(config.manifest_path),
                )
                estimate = await pipeline.estimate_getnote_need(
                    videos,
                    sort=sort,
                    limit=config.limits.limit,
                )
                _print_getnote_estimate(
                    estimate.fallback_count,
                    estimate.fallback_minutes,
                    estimate.within_budget,
                )
            return []

        getnote = build_getnote_client(config.getnote) if config.getnote.enabled else None
        pipeline = Pipeline(
            config=config,
            bilibili=client,
            getnote=getnote,
            manifest=ManifestStore(config.manifest_path),
        )
        return await pipeline.process(
            videos,
            sort=sort,
            limit=config.limits.limit,
            skip_existing=skip_existing,
        )


async def _split_links(
    input_value: str,
    config_path: Path | None,
    sort: SortMode,
    limit: int | None,
    part_selection: PartSelectionMode | None,
) -> None:
    config = _load_config_for_cli(config_path)
    if limit is not None:
        config.limits.limit = limit
    if part_selection is not None:
        config.bilibili.part_selection = part_selection

    async with BilibiliClient(
        cookie_file=config.bilibili.cookie_file,
        request_sleep_seconds=config.bilibili.request_sleep_seconds,
    ) as client:
        videos = await _expand_input(
            client,
            input_value,
            part_selection=config.bilibili.part_selection,
        )
    selected_videos = sort_video_items(videos, sort)
    if config.limits.limit is not None:
        selected_videos = selected_videos[: config.limits.limit]
    _print_split_links(selected_videos)


async def _main(
    input_value: str,
    config_path: Path | None,
    output: Path | None,
    sort: SortMode,
    limit: int | None,
    skip_existing: bool,
    no_getnote: bool,
    dry_run: bool,
    estimate_getnote: bool,
    part_selection: PartSelectionMode | None,
) -> None:
    config = _load_config_for_cli(config_path)
    if output is not None:
        expanded_output = expand_path(output)
        if expanded_output is not None:
            config.output_dir = expanded_output
    if limit is not None:
        config.limits.limit = limit
    if no_getnote:
        config.getnote.enabled = False
    if part_selection is not None:
        config.bilibili.part_selection = part_selection

    results = await _run_inputs(
        input_values=[input_value],
        config=config,
        sort=sort,
        skip_existing=skip_existing,
        dry_run=dry_run,
        estimate_getnote=estimate_getnote,
    )
    if not dry_run:
        _print_result_summary(results)


@app.command()
def run(
    input_value: Annotated[
        str,
        typer.Argument(
            help="Bilibili video URL, uploader URL/mid, collection URL, or file path."
        ),
    ],
    config_path: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Config YAML path."),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output directory override."),
    ] = None,
    sort: Annotated[
        SortMode,
        typer.Option("--sort", help=SORT_HELP),
    ] = "source",
    limit: Annotated[
        int | None,
        typer.Option("--limit", min=1, help="After sorting max count."),
    ] = None,
    skip_existing: Annotated[
        bool,
        typer.Option(
            "--skip-existing/--no-skip-existing",
            help=(
                "Skip videos already marked done in the manifest; "
                "use --no-skip-existing to process them again."
            ),
        ),
    ] = True,
    no_getnote: Annotated[
        bool,
        typer.Option("--no-getnote", help="Disable Get笔记 fallback."),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Expand, sort, and display videos without writing files.",
        ),
    ] = False,
    estimate_getnote: Annotated[
        bool,
        typer.Option(
            "--estimate-getnote",
            help="During --dry-run, estimate Get笔记 fallback usage.",
        ),
    ] = False,
    part_selection: Annotated[
        PartSelectionMode | None,
        typer.Option(
            "--part-selection",
            help="When a Bilibili video URL contains ?p=N, process selected part or all parts.",
        ),
    ] = None,
) -> None:
    asyncio.run(
        _main(
            input_value=input_value,
            config_path=config_path,
            output=output,
            sort=sort,
            limit=limit,
            skip_existing=skip_existing,
            no_getnote=no_getnote,
            dry_run=dry_run,
            estimate_getnote=estimate_getnote,
            part_selection=part_selection,
        )
    )


@app.command("split-links")
def split_links(
    input_value: Annotated[
        str,
        typer.Argument(
            help="Bilibili video, uploader, collection, or file input to expand into video URLs."
        ),
    ],
    config_path: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Config YAML path."),
    ] = None,
    sort: Annotated[
        SortMode,
        typer.Option("--sort", help=SORT_HELP),
    ] = "source",
    limit: Annotated[
        int | None,
        typer.Option("--limit", min=1, help="After sorting max count."),
    ] = None,
    part_selection: Annotated[
        PartSelectionMode | None,
        typer.Option(
            "--part-selection",
            help="When a Bilibili video URL contains ?p=N, print selected part or all parts.",
        ),
    ] = None,
) -> None:
    asyncio.run(
        _split_links(
            input_value=input_value,
            config_path=config_path,
            sort=sort,
            limit=limit,
            part_selection=part_selection,
        )
    )


def _manifest_from_config(config_path: Path | None) -> ManifestStore:
    config = _load_config_for_cli(config_path)
    return ManifestStore(config.manifest_path)


@app.command()
def status(
    config_path: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Config YAML path."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print machine-readable manifest status."),
    ] = False,
) -> None:
    manifest = _manifest_from_config(config_path)
    counts = manifest.status_counts()
    failed = manifest.failed_records()
    if json_output:
        console.print(
            json.dumps(
                {"counts": counts, "failed": failed},
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    console.print(" ".join(f"{name}={count}" for name, count in counts.items()))
    if failed:
        console.print("failed:")
        for record in failed:
            error_code = f" {record.get('error_code')}" if record.get("error_code") else ""
            console.print(
                f"- {record['key']} {record['url']}{error_code} {record.get('error', '')}"
            )


@app.command("platforms")
def platforms(
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print JSON platform capabilities."),
    ] = False,
) -> None:
    capabilities = platform_capabilities()
    if json_output:
        console.print(json.dumps(capabilities, ensure_ascii=False, indent=2))
        return
    for capability in capabilities:
        enabled = [
            name
            for name in (
                "single_video",
                "uploader",
                "collection",
                "native_subtitle",
                "getnote_fallback",
            )
            if capability.get(name) is True
        ]
        console.print(
            f"{capability['platform']} status={capability['status']} "
            f"capabilities={','.join(enabled)}"
        )


@app.command("clean-pending")
def clean_pending(
    config_path: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Config YAML path."),
    ] = None,
) -> None:
    manifest = _manifest_from_config(config_path)
    cleaned = manifest.clean_pending()
    console.print(f"cleaned={cleaned}")


@app.command("retry-failed")
def retry_failed(
    config_path: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Config YAML path."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Print failed URLs without processing."),
    ] = False,
    error_code: Annotated[
        str | None,
        typer.Option("--error-code", help="Retry only failures with this error_code."),
    ] = None,
) -> None:
    config = _load_config_for_cli(config_path)
    failed = ManifestStore(config.manifest_path).failed_records()
    if error_code is not None:
        failed = [record for record in failed if record.get("error_code") == error_code]
    input_values = [record["url"] for record in failed]
    if dry_run:
        for input_value in input_values:
            console.print(input_value)
        return
    results = asyncio.run(
        _run_inputs(
            input_values=input_values,
            config=config,
            sort="source",
            skip_existing=False,
            dry_run=False,
            estimate_getnote=False,
        )
    )
    _print_result_summary(results)


def _path_parent_writable(path: Path) -> bool:
    probe = path if path.exists() else path.parent
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    return probe.exists() and probe.is_dir() and os.access(probe, os.W_OK)


@app.command()
def doctor(
    config_path: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Config YAML path."),
    ] = None,
) -> None:
    config = _load_config_for_cli(config_path)
    console.print("config=ok")
    console.print(f"output_dir={'ok' if _path_parent_writable(config.output_dir) else 'failed'}")
    console.print(f"manifest_path={'ok' if _path_parent_writable(config.manifest_path) else 'failed'}")
    if config.bilibili.cookie_file is None:
        console.print("bilibili_cookie=skipped")
    elif config.bilibili.cookie_file.exists():
        console.print("bilibili_cookie=ok")
    else:
        console.print("bilibili_cookie=missing")
    console.print(f"getnote={'ok' if shutil.which(config.getnote.cli_path) else 'missing'}")
