"""CLI entry point for the deep-research system.

Usage:
    deep-research "What is the future of quantum computing?"
    deep-research --output ./my-runs "Will fusion energy be viable by 2035?"
"""

import deep_research.qwen_patch  # noqa: F401 — must load before any LLM calls

import asyncio
import argparse
import logging
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from deep_research.pipeline import run_research


def setup_logging(log_dir: str = "./logs") -> None:
    """Configure logging to both file and console."""
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    log_file = Path(log_dir) / f"deep-research-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-7s] %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers.clear()
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    # Silence noisy third-party loggers
    for noisy in ("LiteLLM", "httpx", "urllib3", "openai", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    print(f"📝 Log: {log_file}")
    return str(log_file)


def main():
    parser = argparse.ArgumentParser(
        prog="deep-research",
        description="Multi-agent deep research system — "
                    "fan-out web searches, adversarial verification, and cited report synthesis.",
    )
    parser.add_argument("question", nargs="+", help="Research question")
    parser.add_argument("--output", "-o", help="Override output directory")
    parser.add_argument("--log-dir", default="./logs", help="Log directory")

    args = parser.parse_args()
    question = " ".join(args.question)

    if args.output:
        os.environ["RESEARCH_OUTPUT_DIR"] = args.output

    log_file = setup_logging(args.log_dir)
    logger = logging.getLogger("deep_research")

    print(f"\n🔬 Deep Research Starting...")
    print(f"   Question: {question}")
    print(f"   Log: {log_file}\n")

    try:
        result = asyncio.run(run_research(question))
        print(f"\n✅ Research complete!")
        print(f"   Run ID: {result.id}")
        print(f"   Report: runs/{result.id}/report.md")
        print(f"   Evidence: runs/{result.id}/evidence.json")
    except Exception as e:
        logger.error("Fatal error in main: %s", e)
        logger.error(traceback.format_exc())
        print(f"\n❌ Research failed: {e}")
        print(f"   Full traceback in: {log_file}")
        sys.exit(1)


if __name__ == "__main__":
    main()
