"""Async data-access layer backed by PostgreSQL."""

from __future__ import annotations

from datetime import datetime

from deep_research.models.schemas import (
    ResearchRun, ResearchCard, VerifiedCard, ScoreResult, InsightResult, RunStatus,
)
from deep_research.db.schema import get_pool


class Repository:
    """Async repository.  All methods acquire a connection from the pool."""

    # ── Runs ─────────────────────────────────────────────────────────

    async def create_run(self, run: ResearchRun) -> str:
        pool = await get_pool()
        await pool.execute(
            "INSERT INTO research_runs (id, question, status, created_at) VALUES ($1,$2,$3,$4)",
            run.id, run.question, run.status.value, run.created_at,
        )
        return run.id

    async def update_run_status(self, run_id: str, status: RunStatus) -> None:
        pool = await get_pool()
        if status == RunStatus.COMPLETED:
            completed_at = datetime.now().isoformat()
            await pool.execute(
                "UPDATE research_runs SET status=$1, completed_at=$2 WHERE id=$3",
                status.value, completed_at, run_id,
            )
        else:
            await pool.execute(
                "UPDATE research_runs SET status=$1 WHERE id=$2",
                status.value, run_id,
            )

    async def get_run(self, run_id: str) -> dict | None:
        pool = await get_pool()
        row = await pool.fetchrow(
            "SELECT id, question, status, created_at, completed_at FROM research_runs WHERE id=$1",
            run_id,
        )
        if row is None:
            return None
        return {
            "id": row["id"], "question": row["question"],
            "status": row["status"], "created_at": row["created_at"],
            "completed_at": row["completed_at"],
        }

    # ── Research cards ───────────────────────────────────────────────

    async def save_research_card(
        self, run_id: str, card: ResearchCard, *, replace: bool = False,
    ) -> int:
        """Persist a ResearchCard.

        With *replace=True* (used by graph-level augmentation), any prior
        card for the same (run_id, perspective) is deleted first — this
        keeps the table free of duplicates when augment loops or resumes
        re-run the same perspective.
        """
        pool = await get_pool()
        if replace:
            await pool.execute(
                "DELETE FROM research_cards WHERE run_id=$1 AND perspective=$2",
                run_id, card.perspective,
            )
            await pool.execute(
                "DELETE FROM claims WHERE run_id=$1 AND perspective=$2",
                run_id, card.perspective,
            )
        row = await pool.fetchrow(
            "INSERT INTO research_cards (run_id, perspective, research_question, card_json) "
            "VALUES ($1,$2,$3,$4) RETURNING id",
            run_id, card.perspective, card.research_question, card.model_dump_json(),
        )
        card_id = row["id"]
        for i, claim in enumerate(card.key_findings):
            await pool.execute(
                "INSERT INTO claims (run_id, perspective, card_id, claim_index, claim_text, confidence) "
                "VALUES ($1,$2,$3,$4,$5,$6)",
                run_id, card.perspective, card_id, i, claim.text, claim.confidence.value,
            )
        return card_id

    async def get_research_cards(self, run_id: str) -> list[ResearchCard]:
        pool = await get_pool()
        rows = await pool.fetch(
            "SELECT card_json FROM research_cards WHERE run_id=$1 ORDER BY id",
            run_id,
        )
        return [ResearchCard.model_validate_json(r["card_json"]) for r in rows]

    # ── Verified cards ───────────────────────────────────────────────

    async def save_verified_card(self, run_id: str, card: VerifiedCard) -> None:
        pool = await get_pool()
        await pool.execute(
            "INSERT INTO verified_cards (run_id, perspective, verification_round, card_json) "
            "VALUES ($1,$2,$3,$4)",
            run_id, card.perspective, card.verification_round, card.model_dump_json(),
        )
        for entry in card.entries:
            await pool.execute(
                "UPDATE claims SET verification_status=$1 "
                "WHERE run_id=$2 AND perspective=$3 AND claim_index=$4",
                entry.status.value, run_id, card.perspective, entry.claim_index,
            )

    async def get_verified_cards(self, run_id: str) -> list[VerifiedCard]:
        pool = await get_pool()
        rows = await pool.fetch(
            "SELECT card_json FROM verified_cards WHERE run_id=$1 ORDER BY id",
            run_id,
        )
        return [VerifiedCard.model_validate_json(r["card_json"]) for r in rows]

    # ── Scores / Insights ────────────────────────────────────────────

    async def save_score(self, run_id: str, score: ScoreResult) -> None:
        pool = await get_pool()
        await pool.execute(
            "INSERT INTO scores (run_id, score_json) VALUES ($1,$2) "
            "ON CONFLICT (run_id) DO UPDATE SET score_json=$2",
            run_id, score.model_dump_json(),
        )

    # ── Checkpoints ─────────────────────────────────────────────────

    async def save_checkpoint(self, run_id: str, node_name: str, state_json: str) -> None:
        """Persist a full state snapshot after a node completes."""
        pool = await get_pool()
        await pool.execute(
            "INSERT INTO run_checkpoints (run_id, node_name, state_json) VALUES ($1,$2,$3)",
            run_id, node_name, state_json,
        )

    async def get_last_checkpoint(self, run_id: str) -> dict | None:
        """Return the most recent checkpoint for a run, or None."""
        pool = await get_pool()
        row = await pool.fetchrow(
            "SELECT node_name, state_json FROM run_checkpoints "
            "WHERE run_id=$1 ORDER BY id DESC LIMIT 1",
            run_id,
        )
        if row is None:
            return None
        return {"node_name": row["node_name"], "state": row["state_json"]}

    async def clear_checkpoints(self, run_id: str) -> None:
        """Delete all checkpoints for a run (after successful completion)."""
        pool = await get_pool()
        await pool.execute("DELETE FROM run_checkpoints WHERE run_id=$1", run_id)

    async def save_insights(self, run_id: str, insights: InsightResult) -> None:
        pool = await get_pool()
        await pool.execute(
            "INSERT INTO insights (run_id, insights_json) VALUES ($1,$2) "
            "ON CONFLICT (run_id) DO UPDATE SET insights_json=$2",
            run_id, insights.model_dump_json(),
        )
