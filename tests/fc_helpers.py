"""Helper functions and adapters for extended fact-checking test suite."""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = Path(os.environ.get("FC_CORPUS", ROOT / "data/evidence/vifactcheck_passages.jsonl"))
REQUIRED_FIELDS = ("document_id", "passage_id", "content", "source", "url")


def load_verify() -> Callable[[str], Any] | None:
    """Import verify function from FC_VERIFY_FN ('module:function').

    Defaults to 'tests.fc_adapter:verify_claim' or 'src.pipeline:verify_claim'.
    Returns None if import or initialization fails.
    """
    fn_spec = os.environ.get("FC_VERIFY_FN", "tests.fc_adapter:verify_claim")
    try:
        if ":" in fn_spec:
            module_name, func_name = fn_spec.split(":", 1)
        else:
            module_name, func_name = fn_spec.rsplit(".", 1)
        mod = importlib.import_module(module_name)
        func = getattr(mod, func_name)
        return func
    except Exception as exc:
        print(f"[fc_helpers] Could not load verify function from '{fn_spec}': {exc}")
        return None


def normalize_result(r: Any) -> tuple[str, list[str]]:
    """Normalize result object or dict into (label, [passage_id]).

    Normalizes 'NOT_ENOUGH_INFO' -> 'NEI'.
    Extracts citation passage IDs whether dict or object.
    """
    label: str = ""
    citations: list[str] = []

    if isinstance(r, dict):
        if "label" in r:
            label = str(r["label"])
        elif "verdict" in r:
            verdict = r["verdict"]
            if isinstance(verdict, dict):
                label = str(verdict.get("label", ""))
            else:
                label = str(getattr(verdict, "label", ""))

        raw_citations = r.get("citations") or r.get("evidence_ids") or []
        for c in raw_citations:
            if isinstance(c, dict):
                pid = c.get("passage_id")
                if pid:
                    citations.append(str(pid))
            elif isinstance(c, str):
                citations.append(c)
            elif hasattr(c, "passage_id"):
                citations.append(str(c.passage_id))
    elif hasattr(r, "label"):
        label = str(r.label)
        raw_evidence = getattr(r, "evidence_ids", []) or getattr(r, "citations", [])
        for c in raw_evidence:
            if isinstance(c, str):
                citations.append(c)
            elif isinstance(c, dict):
                pid = c.get("passage_id")
                if pid:
                    citations.append(str(pid))
            elif hasattr(c, "passage_id"):
                citations.append(str(c.passage_id))

    if label == "NOT_ENOUGH_INFO":
        label = "NEI"

    return label, citations


def read_jsonl(path: str | Path) -> list[tuple[int, str]]:
    """Read a JSONL file and return a list of (1-indexed line_number, raw_line)."""
    p = Path(path)
    if not p.exists():
        return []
    results: list[tuple[int, str]] = []
    with p.open(encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            results.append((idx, line))
    return results
