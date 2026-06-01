import importlib
import tomllib
from pathlib import Path


def test_project_exposes_mediamark_package_and_cli_entrypoint():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text())

    assert pyproject["project"]["name"] == "mediamark"
    assert pyproject["project"]["scripts"] == {"mediamark": "mediamark.cli:app"}

    package = importlib.import_module("mediamark")
    assert package.__version__ == pyproject["project"]["version"]
    assert package.__version__ == "0.6.0"


def test_package_declares_playwright_dependency():
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert any(dep.startswith("playwright") for dep in data["project"]["dependencies"])
