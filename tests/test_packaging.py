import importlib
import tomllib
from pathlib import Path


def test_project_exposes_mediamark_package_and_cli_entrypoint():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text())

    assert pyproject["project"]["name"] == "mediamark"
    assert pyproject["project"]["scripts"] == {"mediamark": "mediamark.cli:app"}

    package = importlib.import_module("mediamark")
    assert package.__version__ == pyproject["project"]["version"]
    assert package.__version__ == "0.5.0"
