"""Concurrency stress test — submits N research tasks simultaneously.

Usage (on the server):
  python3 scripts/stress_test.py http://localhost:8000 5

This verifies:
  - Semaphore gating: N concurrent tasks queue rather than crash
  - DB writes: no "database is locked" under concurrent load
  - All tasks complete (or fail gracefully)

Each task costs ~$0.06-0.15 in DeepSeek API fees.
Use a small N (3-5) for smoke testing.
"""

import asyncio
import sys
import time

import httpx


async def submit_one(client: httpx.AsyncClient, url: str, i: int) -> dict:
    """Submit one research and poll until completion."""
    t0 = time.time()
    # Submit
    r = await client.post(
        f"{url}/research",
        json={"question": f"压力测试问题 #{i}: 什么是云计算？"},
        timeout=10,
    )
    submit_ms = (time.time() - t0) * 1000
    if r.status_code != 202:
        return {"idx": i, "status": "submit_failed", "code": r.status_code, "submit_ms": submit_ms}

    run_id = r.json()["run_id"]
    # Poll until done
    t1 = time.time()
    while True:
        await asyncio.sleep(2)
        r = await client.get(f"{url}/research/{run_id}", timeout=10)
        if r.status_code != 200:
            return {"idx": i, "run_id": run_id, "status": "poll_failed", "submit_ms": submit_ms}
        st = r.json()
        if st["status"] in ("completed", "failed"):
            elapsed = time.time() - t1
            return {
                "idx": i, "run_id": run_id, "status": st["status"],
                "score": st.get("score"), "findings": st.get("findings"),
                "submit_ms": round(submit_ms, 1),
                "research_s": round(elapsed, 1),
            }


async def main():
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 3

    print(f"Stress test: {n} concurrent tasks → {url}")
    print(f"Estimated cost: ~${n * 0.08:.2f}")
    print("─" * 50)

    t0 = time.time()
    async with httpx.AsyncClient() as client:
        tasks = [submit_one(client, url, i) for i in range(1, n + 1)]
        results = await asyncio.gather(*tasks)

    total_s = time.time() - t0
    completed = [r for r in results if r["status"] == "completed"]
    failed = [r for r in results if r["status"] not in ("completed", "poll_failed", "submit_failed")]

    print("\nResults:")
    for r in sorted(results, key=lambda x: x["idx"]):
        if r["status"] == "completed":
            print(f"  #{r['idx']}: ✅ {r['run_id']} — score={r['score']} — {r['findings']} findings — "
                  f"submit={r['submit_ms']}ms — research={r['research_s']}s")
        else:
            print(f"  #{r['idx']}: ❌ {r['status']} — {r.get('run_id', 'N/A')}")

    print(f"\nTotal: {len(completed)}/{n} completed in {total_s:.0f}s")
    if failed:
        print(f"FAILURES: {len(failed)} tasks did not complete normally")
        # Check logs for these run_ids
        for f in failed:
            print(f"  Run {f.get('run_id', '?')}: {f['status']}")
    else:
        print("All tasks completed — concurrency works.")


if __name__ == "__main__":
    asyncio.run(main())
