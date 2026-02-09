#!/usr/bin/env python3
"""Evaluation runner for PokéProf Notebook.

Runs each Q&A pair through the full pipeline (route → retrieve → synthesize)
and checks whether expected keywords appear in the answer.

Usage:
    python tests/eval/run_eval.py                 # full LLM eval
    python tests/eval/run_eval.py --no-llm        # keyword search only
    python tests/eval/run_eval.py --category rulebook  # filter by category
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from dotenv import load_dotenv

load_dotenv(project_root / ".env")

from pokeprof_notebook.config import get_project_root, load_config
from pokeprof_notebook.indexer import load_tree
from pokeprof_notebook.overlay import annotate_sections, load_overlay
from pokeprof_notebook.retriever import search, search_multi
from pokeprof_notebook.router import route
from pokeprof_notebook.synthesizer import synthesize

EVAL_SET_PATH = Path(__file__).parent / "eval_set.json"
INDEXES_DIR = get_project_root() / "data" / "indexes"
OVERLAY_PATH = INDEXES_DIR / "overlay_manifest.json"


def load_eval_set(category: str | None = None) -> list[dict]:
    """Load eval set, optionally filtering by category."""
    entries = json.loads(EVAL_SET_PATH.read_text(encoding="utf-8"))
    if category:
        entries = [e for e in entries if e["category"] == category]
    return entries


def check_answer(answer: str, expected_contains: list[str]) -> bool:
    """Check if the answer contains at least one expected keyword."""
    answer_lower = answer.lower()
    return any(kw.lower() in answer_lower for kw in expected_contains)


def run_single(
    entry: dict,
    config,
    model: str,
    no_llm: bool,
) -> dict:
    """Run a single eval entry through the pipeline. Returns result dict."""
    question = entry["question"]
    persona = entry.get("persona", "judge")
    t0 = time.time()

    try:
        # Route
        route_decision = route(question, config, persona)

        # Load indexes
        indexes = {}
        for doc_name in route_decision.documents:
            index_path = INDEXES_DIR / f"{doc_name}.json"
            if index_path.exists():
                indexes[doc_name] = load_tree(index_path)

        # Retrieve
        if len(indexes) > 1:
            sections = search_multi(
                question, indexes, max_sections=10, model=model, use_llm=not no_llm,
                card_names=route_decision.card_names,
            )
        elif indexes:
            _, index = next(iter(indexes.items()))
            sections = search(question, index, max_sections=5, model=model, use_llm=not no_llm)
        else:
            sections = []

        # Overlay
        if OVERLAY_PATH.exists() and sections:
            manifest = load_overlay(OVERLAY_PATH)
            sections = annotate_sections(sections, manifest, question)

        # Synthesize
        if no_llm or not sections:
            # Use raw section content as "answer" for keyword matching
            answer = "\n".join(s.node.content[:500] for s in sections)
        else:
            answer = synthesize(question, sections, persona=persona, model=model)

        elapsed = time.time() - t0

        passed = check_answer(answer, entry["expected_answer_contains"])

        return {
            "id": entry["id"],
            "question": question,
            "category": entry["category"],
            "difficulty": entry.get("difficulty", "medium"),
            "passed": passed,
            "elapsed": round(elapsed, 2),
            "routed_to": route_decision.documents,
            "sections_found": len(sections),
            "answer_preview": answer[:200] if answer else "(empty)",
            "error": None,
        }

    except Exception as e:
        elapsed = time.time() - t0
        return {
            "id": entry["id"],
            "question": question,
            "category": entry["category"],
            "difficulty": entry.get("difficulty", "medium"),
            "passed": False,
            "elapsed": round(elapsed, 2),
            "routed_to": [],
            "sections_found": 0,
            "answer_preview": "",
            "error": str(e),
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run PokéProf eval set")
    parser.add_argument("--no-llm", action="store_true", help="Keyword search only")
    parser.add_argument("--model", default="claude-haiku-4-5-20251001")
    parser.add_argument("--category", help="Filter by category")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    if not args.no_llm and not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set. Use --no-llm for keyword-only eval.")
        sys.exit(1)

    entries = load_eval_set(args.category)
    print(f"Running {len(entries)} eval entries...")
    print()

    config = load_config()
    results = []

    for i, entry in enumerate(entries, 1):
        result = run_single(entry, config, args.model, args.no_llm)
        results.append(result)

        status = "PASS" if result["passed"] else "FAIL"
        marker = "\u2713" if result["passed"] else "\u2717"
        print(f"  [{i:2d}/{len(entries)}] {marker} {status}  {result['id']:<16s}  "
              f"{result['elapsed']:5.1f}s  {entry['question'][:60]}")

        if args.verbose and not result["passed"]:
            print(f"         Expected: {entry['expected_answer_contains']}")
            print(f"         Answer:   {result['answer_preview'][:120]}")
            if result["error"]:
                print(f"         Error:    {result['error']}")

    # Summary
    print()
    print("=" * 70)

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed
    accuracy = passed / total * 100 if total else 0
    avg_time = sum(r["elapsed"] for r in results) / total if total else 0

    print(f"Results: {passed}/{total} passed ({accuracy:.0f}% accuracy)")
    print(f"Average time: {avg_time:.1f}s")
    print()

    # Per-category breakdown
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_cat[r["category"]].append(r)

    print("By category:")
    for cat in sorted(by_cat):
        cat_results = by_cat[cat]
        cat_passed = sum(1 for r in cat_results if r["passed"])
        cat_total = len(cat_results)
        cat_pct = cat_passed / cat_total * 100 if cat_total else 0
        print(f"  {cat:<20s}  {cat_passed}/{cat_total}  ({cat_pct:.0f}%)")

    # Per-difficulty breakdown
    by_diff: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_diff[r["difficulty"]].append(r)

    print()
    print("By difficulty:")
    for diff in ["easy", "medium", "hard"]:
        if diff in by_diff:
            diff_results = by_diff[diff]
            diff_passed = sum(1 for r in diff_results if r["passed"])
            diff_total = len(diff_results)
            diff_pct = diff_passed / diff_total * 100 if diff_total else 0
            print(f"  {diff:<20s}  {diff_passed}/{diff_total}  ({diff_pct:.0f}%)")

    # Failures
    failures = [r for r in results if not r["passed"]]
    if failures:
        print()
        print("Failures:")
        for r in failures:
            print(f"  {r['id']}: {r['question'][:60]}")
            if r["error"]:
                print(f"    Error: {r['error']}")

    # Exit code
    if accuracy < 80:
        print(f"\nFAILED: Accuracy {accuracy:.0f}% is below 80% threshold.")
        sys.exit(1)
    else:
        print(f"\nPASSED: Accuracy {accuracy:.0f}% meets 80% threshold.")


if __name__ == "__main__":
    main()
