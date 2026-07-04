"""Print DeepSeek's raw extraction on a few LIAR statements for a quality audit.

Runs the real reasoning pipeline on a small, fixed sample so a human (or a
reference model) can judge whether the extracted atomic claims and rhetoric are
faithful — i.e. whether deepseek-v4-flash is good enough for this task.

    python scripts/quality_probe.py            # 6 statements
    python scripts/quality_probe.py 8          # N statements
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "packages" / "graph_schema"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "packages" / "epistemic_math"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "packages" / "observability"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "packages" / "evaluation"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "agentic_reasoning"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "graph_layer"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "ingestion_service"))

os.environ.setdefault("REDIS_URL", "")
os.environ.setdefault("EPIS_LLM_CACHE", "false")

from evaluation.env import load_dotenv  # noqa: E402
from evaluation.liar import load_liar  # noqa: E402


async def main() -> None:
    load_dotenv()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

    n = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    rows = load_liar(split="test")
    # A fixed, diverse sample spread across the split.
    step = max(len(rows) // n, 1)
    sample = [rows[i * step] for i in range(n)]

    from agentic_reasoning import build_reasoning_graph
    from graph_schema import RawDocument

    graph = build_reasoning_graph()
    print(f"\nModel: {os.getenv('LLM_MODEL', 'deepseek-v4-flash')}  via  {os.getenv('DEEPSEEK_BASE_URL')}\n")

    for i, row in enumerate(sample):
        doc = RawDocument(id=f"probe_{i}", content=row["statement"], source_name="LIAR")
        try:
            final = await graph.ainvoke({"document": doc, "attempts": 0, "errors": []})
        except Exception as exc:  # noqa: BLE001
            print(f"[{i}] ERROR: {exc}\n")
            continue
        res = final.get("result")
        print("=" * 88)
        print(f"[{i}] LABEL={row['label']:<12} VALID={final.get('valid')}")
        print(f"    STATEMENT: {row['statement']}")
        if res is None:
            print("    (no result)\n")
            continue
        print("    CLAIMS:")
        for c in res.claims:
            print(f"      - ({c.confidence:.2f}) {c.statement}")
        print("    RHETORIC:")
        if not res.rhetoric:
            print("      (none detected)")
        for r in res.rhetoric:
            print(f"      - {r.category.value} (sev {r.severity_weight:.2f})")
        print()


if __name__ == "__main__":
    asyncio.run(main())
