"""Quick smoke test: run the Orchestrator with real API keys."""
import asyncio
import sys
sys.path.insert(0, "src")

from deep_research.agents import create_orchestrator
from crewai import Task, Crew, Process


async def main():
    print("=" * 60)
    print("Smoke Test: Orchestrator Agent (DeepSeek API)")
    print("=" * 60)

    agent = create_orchestrator()
    print(f"Agent created: {agent.role}")
    print(f"LLM: {agent.llm}")

    task = Task(
        description="""Decompose the following research question into 4 distinct Research Briefs.

Research Question: What are the key differences between CrewAI and LangGraph for building multi-agent systems?

For each perspective, provide:
1. A focused sub-question tailored to that perspective's lens
2. Recommended search keywords (3-5)
3. What types of sources to prioritize

Output the result as a JSON object with keys: "technical", "industry", "critical", "future".
Each value is an object with keys: "sub_question", "keywords" (list of strings), "source_types" (list of strings).

IMPORTANT: Return ONLY the JSON object, no other text.""",
        expected_output="A JSON object with keys: technical, industry, critical, future",
        agent=agent,
    )

    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=True)
    result = await crew.kickoff_async()

    print("\n" + "=" * 60)
    print("Orchestrator Result:")
    print("=" * 60)
    print(result.raw[:1000])
    print("=" * 60)
    print("SMOKE TEST PASSED — Orchestrator responded successfully")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
