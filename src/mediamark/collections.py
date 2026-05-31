import os
from pathlib import Path

from slugify import slugify

from mediamark.config import AppConfig
from mediamark.models import ProcessResult


def write_collection_indexes(config: AppConfig, results: list[ProcessResult]) -> list[Path]:
    grouped: dict[str, list[ProcessResult]] = {}
    for result in results:
        if result.status != "done" or result.path is None or not result.video.collection:
            continue
        grouped.setdefault(result.video.collection, []).append(result)

    written: list[Path] = []
    for collection, collection_results in grouped.items():
        filename = f"{slugify(collection, allow_unicode=True) or 'collection'}.md"
        index_path = config.output_dir / config.archive.collection_index_dir / filename
        index_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"# {collection}", ""]
        for result in collection_results:
            assert result.path is not None
            link = _relative_link(result.path, index_path.parent)
            lines.append(f"- [{result.video.title}]({link})")
        index_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        written.append(index_path)
    return written


def _relative_link(path: Path, start: Path) -> str:
    try:
        return os.path.relpath(path, start=start)
    except ValueError:
        return str(path)
