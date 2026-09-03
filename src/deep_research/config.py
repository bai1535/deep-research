"""Application configuration loaded from environment variables.

Uses python-dotenv to load a .env file (if present), then exposes a singleton
`Config` dataclass via `get_config()`.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


@dataclass
class LLMConfig:
    """Single LLM endpoint configuration."""

    model: str
    base_url: str
    api_key: str = "not-needed"


@dataclass
class Config:
    """Application configuration loaded from environment."""

    # DeepSeek (strong reasoning)
    deepseek: LLMConfig = field(default_factory=lambda: LLMConfig(
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        api_key=os.getenv("DEEPSEEK_API_KEY", ""),
    ))

    # Qwen (light tasks) — supports both local Ollama and remote GPUStack endpoints
    qwen: LLMConfig = field(default_factory=lambda: LLMConfig(
        model=os.getenv("QWEN_MODEL", os.getenv("OLLAMA_MODEL", "qwen3.6-a3b")),
        base_url=os.getenv("QWEN_BASE_URL", os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")),
        api_key=os.getenv("QWEN_API_KEY", "not-needed"),
    ))

    # Search APIs
    tavily_api_key: str = field(default_factory=lambda: os.getenv("TAVILY_API_KEY", ""))
    exa_api_key: str = field(default_factory=lambda: os.getenv("EXA_API_KEY", ""))
    firecrawl_api_key: str = field(default_factory=lambda: os.getenv("FIRECRAWL_API_KEY", ""))

    # Database
    database_url: str = field(default_factory=lambda: os.getenv(
        "DATABASE_URL", "postgresql://researcher:deepresearch@localhost:5432/deep_research"
    ))
    db_pool_size: int = field(default_factory=lambda: int(os.getenv("DB_POOL_SIZE", "20")))

    # Paths
    output_dir: str = field(default_factory=lambda: os.getenv("RESEARCH_OUTPUT_DIR", "./runs"))


_config: Config | None = None


def get_config() -> Config:
    """Return the singleton Config instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config
