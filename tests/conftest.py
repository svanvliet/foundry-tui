"""Shared fixtures for all tests."""

import json
from pathlib import Path

import pytest

from foundry_tui.models import ModelCatalog


@pytest.fixture
def project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def catalog_path(project_root: Path) -> Path:
    """Get the path to models-catalog.json."""
    return project_root / "models-catalog.json"


@pytest.fixture
def catalog_data(catalog_path: Path) -> dict:
    """Load raw catalog JSON data."""
    with open(catalog_path) as f:
        return json.load(f)


@pytest.fixture
def catalog(catalog_data: dict) -> ModelCatalog:
    """Load and parse the model catalog."""
    return ModelCatalog.model_validate(catalog_data)
