from __future__ import annotations

import re
from importlib.metadata import version
from pathlib import Path

import operandomerge

REPOSITORY_ROOT = Path(__file__).parents[2]


def _match(path: str, pattern: str) -> str:
    content = (REPOSITORY_ROOT / path).read_text(encoding="utf-8")
    matched = re.search(pattern, content, flags=re.MULTILINE)
    if matched is None:
        raise AssertionError(f"Version pattern was not found in {path}")
    return matched.group(1)


def test_package_runtime_citation_changelog_and_readme_versions_match() -> None:
    project_version = _match("pyproject.toml", r'^version = "([^"]+)"$')
    citation_version = _match("CITATION.cff", r"^version: ([^\s]+)$")
    changelog_version = _match("CHANGELOG.md", r"^## \[([^]]+)\]")
    readme_version = _match("README.md", r"^Supported in ([^:]+):$")
    assert project_version == "0.1.3"
    assert operandomerge.__version__ == project_version
    assert version("operandomerge") == project_version
    assert citation_version == project_version
    assert changelog_version == project_version
    assert readme_version == project_version
