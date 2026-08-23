from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "validation" / "validate_public_data.py"
MANIFEST = ROOT / "validation" / "public-data-manifest.json"


def _validation_module() -> ModuleType:
    specification = importlib.util.spec_from_file_location("public_data_validation", SCRIPT)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        specification.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def test_public_manifest_pins_sources_without_vendoring_raw_archives() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["accessed_on"] == "2026-08-23"
    assert set(manifest["sources"]) == {"OM-PUB-001", "OM-PUB-002"}
    for source in manifest["sources"].values():
        assert source["record_url"].startswith("https://")
        assert source["dataset_doi"].startswith("10.")
        assert source["dataset_license"] == "CC-BY-4.0"
        for file_specification in source["files"].values():
            if "sha256" in file_specification:
                assert len(file_specification["sha256"]) == 64
                assert file_specification["size_bytes"] > 0
    assert not list((ROOT / "validation").glob("*.zip"))
    assert not list((ROOT / "validation").glob("*.qmp"))


def test_gc_preprocessor_accepts_only_the_two_explicit_published_formats() -> None:
    module = _validation_module()
    parse = module._parse_gc_timestamp
    assert parse("31/01/2024 16:32") == datetime(2024, 1, 31, 16, 32)
    assert parse("31/Jan/2024 16:32") == datetime(2024, 1, 31, 16, 32)
    assert parse("31/jAn/2024 16:32") == datetime(2024, 1, 31, 16, 32)
    with pytest.raises(ValueError, match="explicit published format"):
        parse("2024-01-31 16:32:00")
    with pytest.raises(ValueError, match="explicit published format"):
        parse("31/Jax/2024 16:32")


def test_public_validation_refuses_repository_output() -> None:
    module = _validation_module()
    with pytest.raises(ValueError, match="outside"):
        module._external_empty_directory(ROOT / "validation-output")
