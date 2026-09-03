"""PostgreSQL schema and async connection pool."""

from __future__ import annotations

import logging

import asyncpg

from deep_research.config import get_config

logger = logging.getLogger("deep_research.db")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS research_runs (
    id TEXT PRIMARY KEY,
    question TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS research_cards (
    id SERIAL PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES research_runs(id),
    perspective TEXT NOT NULL,
    research_question TEXT NOT NULL,
    card_json JSONB NOT NULL,
    created_at TEXT NOT NULL DEFAULT to_char(now(), 'YYYY-MM-DD\"T\"HH24:MI:SS')
);

CREATE TABLE IF NOT EXISTS verified_cards (
    id SERIAL PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES research_runs(id),
    perspective TEXT NOT NULL,
    verification_round INTEGER NOT NULL DEFAULT 1,
    card_json JSONB NOT NULL,
    created_at TEXT NOT NULL DEFAULT to_char(now(), 'YYYY-MM-DD\"T\"HH24:MI:SS')
);

CREATE TABLE IF NOT EXISTS claims (
    id SERIAL PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES research_runs(id),
    perspective TEXT NOT NULL,
    card_id INTEGER NOT NULL,
    claim_index INTEGER NOT NULL,
    claim_text TEXT NOT NULL,
    confidence TEXT,
    verification_status TEXT,
    created_at TEXT NOT NULL DEFAULT to_char(now(), 'YYYY-MM-DD\"T\"HH24:MI:SS')
);

CREATE TABLE IF NOT EXISTS scores (
    id SERIAL PRIMARY KEY,
    run_id TEXT NOT NULL UNIQUE REFERENCES research_runs(id),
    score_json JSONB NOT NULL,
    created_at TEXT NOT NULL DEFAULT to_char(now(), 'YYYY-MM-DD\"T\"HH24:MI:SS')
);

CREATE TABLE IF NOT EXISTS insights (
    id SERIAL PRIMARY KEY,
    run_id TEXT NOT NULL UNIQUE REFERENCES research_runs(id),
    insights_json JSONB NOT NULL,
    created_at TEXT NOT NULL DEFAULT to_char(now(), 'YYYY-MM-DD\"T\"HH24:MI:SS')
);

CREATE TABLE IF NOT EXISTS run_checkpoints (
    id SERIAL PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES research_runs(id),
    node_name TEXT NOT NULL,
    state_json JSONB NOT NULL,
    created_at TEXT NOT NULL DEFAULT to_char(now(), 'YYYY-MM-DD\"T\"HH24:MI:SS')
);
"""

_pool: asyncpg.Pool | None = None


async def init_db() -> asyncpg.Pool:
    """Initialise the connection pool and create tables.  Idempotent."""
    global _pool
    if _pool is not None:
        return _pool

    config = get_config()
    _pool = await asyncpg.create_pool(
        config.database_url,
        min_size=2,
        max_size=config.db_pool_size,
    )
    async with _pool.acquire() as conn:
        await conn.execute(SCHEMA_SQL)
    logger.info("PostgreSQL pool ready (max=%d connections)", config.db_pool_size)
    return _pool


async def get_pool() -> asyncpg.Pool:
    """Return the shared connection pool (initialises on first call)."""
    if _pool is None:
        return await init_db()
    return _pool


async def close_db() -> None:
    """Gracefully close the pool."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
