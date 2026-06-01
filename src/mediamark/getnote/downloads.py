from pathlib import Path


class GetnoteWebExportError(RuntimeError):
    pass


def read_markdown_download(path: Path) -> str:
    if path.suffix.lower() != ".md":
        raise GetnoteWebExportError(f"Downloaded file is not Markdown: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise GetnoteWebExportError(f"Downloaded Markdown not found: {path}") from exc
    except IsADirectoryError as exc:
        raise GetnoteWebExportError(f"Downloaded Markdown path is not a file: {path}") from exc
    except UnicodeDecodeError as exc:
        raise GetnoteWebExportError(
            f"Downloaded Markdown is not valid UTF-8: {path}"
        ) from exc
    if not text.strip():
        raise GetnoteWebExportError(f"Downloaded Markdown is empty: {path}")
    return text
