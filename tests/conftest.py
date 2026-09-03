"""Shared pytest fixtures for the deep-research test suite."""

import os
import tempfile
from pathlib import Path
import pytest


@pytest.fixture(autouse=True)
def clean_env():
    """Ensure tests don't leak real API keys.

    Sets known test values for all API-key env vars before each test,
    then restores the original environment afterwards.
    """
    old = os.environ.copy()
    os.environ.update({
        "DEEPSEEK_API_KEY": "test-ds-key",
        "TAVILY_API_KEY": "test-tvly-key",
        "EXA_API_KEY": "test-exa-key",
        "QWEN_API_KEY": "test-qwen-key",
        "QWEN_BASE_URL": "https://test-qwen.local/v1",
        "QWEN_MODEL": "qwen3.6-a3b",
    })
    yield
    os.environ.clear()
    os.environ.update(old)


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database file for testing.

    Yields the path to the file; cleans up after the test.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def temp_output_dir():
    """Create a temporary output directory for testing.

    Yields the directory path; cleaned up automatically on teardown.
    """
    with tempfile.TemporaryDirectory() as d:
        yield d
