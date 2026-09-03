"""Tests for the config module."""

import os

from deep_research.config import Config, LLMConfig, get_config


def test_llm_config_defaults():
    """LLMConfig has sensible defaults."""
    cfg = LLMConfig(model="test-model", base_url="http://localhost:8080/v1")
    assert cfg.model == "test-model"
    assert cfg.base_url == "http://localhost:8080/v1"
    assert cfg.api_key == "not-needed"


def test_llm_config_with_key():
    """LLMConfig accepts explicit api_key."""
    cfg = LLMConfig(model="m", base_url="http://x", api_key="secret")
    assert cfg.api_key == "secret"


def test_config_uses_env_vars():
    """Config picks up values from the environment (set by clean_env fixture)."""
    cfg = Config()
    assert cfg.deepseek.api_key == "test-ds-key"
    assert cfg.deepseek.model == "deepseek-chat"
    assert cfg.deepseek.base_url == "https://api.deepseek.com/v1"
    assert cfg.qwen.model == "qwen3.6-a3b"
    assert cfg.qwen.base_url == "https://test-qwen.local/v1"
    assert cfg.qwen.api_key == "test-qwen-key"
    assert cfg.tavily_api_key == "test-tvly-key"
    assert cfg.exa_api_key == "test-exa-key"


def test_config_defaults_without_env():
    """Config falls back to defaults when env vars are unset."""
    # Temporarily remove env vars that clean_env or the container may have set.
    for key in (
        "DEEPSEEK_API_KEY",
        "TAVILY_API_KEY",
        "EXA_API_KEY",
        "FIRECRAWL_API_KEY",
        "DATABASE_URL",
        "RESEARCH_OUTPUT_DIR",
        "DB_POOL_SIZE",
    ):
        os.environ.pop(key, None)

    cfg = Config()
    assert cfg.deepseek.api_key == ""
    assert cfg.tavily_api_key == ""
    assert cfg.exa_api_key == ""
    assert cfg.firecrawl_api_key == ""
    assert cfg.database_url == (
        "postgresql://researcher:deepresearch@localhost:5432/deep_research"
    )
    assert cfg.db_pool_size == 20
    assert cfg.output_dir == "./runs"


def test_get_config_is_singleton():
    """get_config() returns the same instance every time."""
    a = get_config()
    b = get_config()
    assert a is b


def test_temp_db_fixture(temp_db):
    """temp_db fixture creates a real temp file that exists during the test."""
    from pathlib import Path

    p = Path(temp_db)
    assert p.exists()
    assert p.suffix == ".db"


def test_temp_output_dir_fixture(temp_output_dir):
    """temp_output_dir fixture creates a real temp directory."""
    from pathlib import Path

    p = Path(temp_output_dir)
    assert p.exists()
    assert p.is_dir()
