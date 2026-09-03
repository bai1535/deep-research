"""Database read tool — reads research data for scoring / editing."""

from __future__ import annotations

from deep_research.core.tool import BuildTool
from deep_research.db import Repository


class SQLiteReadTool(BuildTool):
    name = "sqlite_read"  # kept for backward compatibility with LLM prompts
    description = "Read all research data (cards, verified cards) for a given run ID."
    parameters = {
        "type": "object",
        "properties": {
            "run_id": {"type": "string", "description": "Research run ID"},
        },
        "required": ["run_id"],
    }

    async def execute(self, args: dict) -> str:
        repo = Repository()
        run = await repo.get_run(args["run_id"])
        if run is None:
            return f"No run found with id: {args['run_id']}"

        cards = await repo.get_research_cards(args["run_id"])
        verified = await repo.get_verified_cards(args["run_id"])

        parts = [f"## Run: {run['question']} (status: {run['status']})", ""]

        if cards:
            from deep_research.tools.web_fetch import classify_url
            parts.append("### Research Cards:")
            for card in cards:
                parts.append(f"\n**Perspective: {card.perspective}**")
                parts.append(f"Question: {card.research_question}")
                for j, claim in enumerate(card.key_findings):
                    parts.append(f"  Claim {j}: [{claim.confidence.value}] {claim.text}")
                    if claim.sources:
                        labeled = [f"{s} {classify_url(s)}" for s in claim.sources[:3]]
                        parts.append(f"    Sources: {', '.join(labeled)}")

        if verified:
            parts.append("\n### Verified Cards:")
            for vc in verified:
                parts.append(f"\n**{vc.perspective}** (Round {vc.verification_round}, resolved={vc.resolved})")
                for entry in vc.entries:
                    parts.append(f"  Claim {entry.claim_index}: {entry.status.value} — {entry.reasoning[:200]}")

        return "\n".join(parts)
