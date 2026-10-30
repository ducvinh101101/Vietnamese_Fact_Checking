"""One-click check + benchmark: trained PhoBERT vs an LLM on the frozen 84-case set.

Runs every step with this interpreter, logs each to <out>/NN_<step>.log and writes
<out>/summary.json. Meant for a PyCharm run configuration (no typing in a terminal):

    python scripts/run_llm_benchmark.py --model gemma-4-31b-it

Steps: pytest, dataset validate, release smoke, demo cases, PhoBERT (verifier only),
PhoBERT + project rules, LLM 3-case smoke (picks the first JSON mode the endpoint
accepts: schema -> mime -> prompt), LLM full 84 cases, scoring of all three.
The API key is read from .env by run_model_gold.py and never printed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="gemma-4-31b-it")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--pause-seconds", type=float, default=4.0, help="Free-tier friendly pacing")
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--max-output-tokens", type=int, default=8192)
    parser.add_argument("--max-retries", type=int, default=4,
                        help="Retries for transient API errors (HTTP 429/5xx); decided before seeing scores")
    parser.add_argument("--resume-from", type=Path, help="Earlier llm_*.jsonl: re-call only its failed cases")
    parser.add_argument("--phobert-dir", type=Path, help="Reuse phobert.jsonl/phobert_project.jsonl from this folder")
    parser.add_argument("--skip-phobert", action="store_true", help="Skip the two PhoBERT runs (LLM only)")
    args = parser.parse_args()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    tag = args.model.replace("/", "_")
    out = args.out or ROOT / "outputs" / f"benchmark_{tag}_{datetime.now():%Y%m%d_%H%M}"
    out.mkdir(parents=True, exist_ok=True)
    py = sys.executable
    env = dict(__import__("os").environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    summary = {"model": args.model, "python": sys.version, "started": datetime.now().isoformat(),
               "out": str(out), "steps": []}

    def step(name, cmd, timeout=3600):
        index = len(summary["steps"]) + 1
        log = out / f"{index:02d}_{name}.log"
        print(f"\n=== [{index:02d}] {name}: {' '.join(map(str, cmd[1:]))}", flush=True)
        started = time.perf_counter()
        try:
            proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=timeout)
            rc, text = proc.returncode, proc.stdout + ("\n--- stderr ---\n" + proc.stderr if proc.stderr else "")
        except subprocess.TimeoutExpired as error:
            rc, text = -9, f"TIMEOUT after {timeout}s\n{error.stdout or ''}\n{error.stderr or ''}"
        seconds = round(time.perf_counter() - started, 1)
        log.write_text(text, encoding="utf-8")
        tail = "\n".join(text.strip().splitlines()[-6:])
        print(tail, flush=True)
        print(f"--> rc={rc} ({seconds}s) log={log.name}", flush=True)
        summary["steps"].append({"name": name, "rc": rc, "seconds": seconds, "log": log.name})
        (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return rc, text

    if not args.skip_tests:
        step("pytest", [py, "-m", "pytest", "-q", "-p", "no:faulthandler", "-p", "no:cacheprovider",
                        f"--basetemp={ROOT / '.cache' / ('pytest_' + out.name)}"], timeout=3600)
    step("validate_gold", [py, "scripts/evaluate_model_gold.py", "validate"])
    step("check_release_smoke", [py, "scripts/check_release.py", "--smoke"], timeout=1800)
    step("demo_cases", [py, "scripts/run_demo_cases.py"], timeout=1800)

    phobert_home = args.phobert_dir or out
    phobert = phobert_home / "phobert.jsonl"
    phobert_rules = phobert_home / "phobert_project.jsonl"
    if not args.skip_phobert and not args.phobert_dir:
        step("phobert_verifier", [py, "scripts/run_model_gold.py", "--backend", "phobert", "--output", str(phobert)])
        step("phobert_project_rules", [py, "scripts/run_model_gold.py", "--backend", "phobert", "--project-rules",
                                       "--output", str(phobert_rules)])

    common = ["--model", args.model, "--timeout", str(args.timeout), "--max-output-tokens",
              str(args.max_output_tokens), "--pause-seconds", str(args.pause_seconds),
              "--max-retries", str(args.max_retries)]
    chosen = None
    if args.resume_from:
        previous = json.loads(args.resume_from.with_name(args.resume_from.stem + ".run.json").read_text(encoding="utf-8"))
        chosen = previous.get("generation", {}).get("json_mode", "schema")
    for mode in (() if chosen else ("schema", "mime", "prompt")):
        smoke = out / f"llm_smoke_{mode}.jsonl"
        rc, _ = step(f"llm_smoke_{mode}", [py, "scripts/run_model_gold.py", "--backend", "gemini", "--limit", "3",
                                          "--json-mode", mode, "--output", str(smoke), *common], timeout=900)
        rows = [json.loads(line) for line in smoke.read_text(encoding="utf-8").splitlines()] if smoke.exists() else []
        if rows and any(row.get("label") for row in rows):
            chosen = mode
            break
    summary["llm_json_mode"] = chosen
    llm = out / f"llm_{tag}.jsonl"
    scored = [phobert, phobert_rules]
    if chosen:
        resume = ["--resume-from", str(args.resume_from)] if args.resume_from else []
        step("llm_full_84", [py, "scripts/run_model_gold.py", "--backend", "gemini", "--json-mode", chosen,
                             "--output", str(llm), *resume, *common], timeout=6 * 3600)
        if llm.exists():
            scored.append(llm)
    else:
        print("LLM smoke failed in every JSON mode; see llm_smoke_*.log / *.jsonl 'error' fields.", flush=True)
    llm_present = llm.exists()
    for base in (phobert, phobert_rules):
        if base.exists() and llm_present:
            step(f"score_{base.stem}_vs_llm", [py, "scripts/evaluate_model_gold.py", "score", str(base), str(llm),
                                              "--output", str(out / f"report_{base.stem}_vs_llm.json")])
        elif base.exists():
            step(f"score_{base.stem}", [py, "scripts/evaluate_model_gold.py", "score", str(base),
                                        "--output", str(out / f"report_{base.stem}.json")])
    summary["finished"] = datetime.now().isoformat()
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDONE. Summary: {out / 'summary.json'}", flush=True)
    return 0 if all(s["rc"] == 0 for s in summary["steps"] if not s["name"].startswith("llm_smoke")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
