"""Run PhoBERT or Gemini on identical blind gold inputs, without retrieval.

No gold labels are loaded here. Score the saved predictions afterwards using
scripts/evaluate_model_gold.py. API calls occur only with --backend gemini.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DEFAULT_INPUTS = ROOT / "tests/golden/model_comparison_v1/inputs.jsonl"
DEFAULT_PROTOCOL = DEFAULT_INPUTS.parent / "PROTOCOL.md"


def load_env(path):
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                key, value = key.strip(), value.strip().strip('"').strip("'")
                if key and value:
                    os.environ.setdefault(key, value)


def load_inputs(path):
    records, seen = [], set()
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if set(row) != {"id", "as_of", "claim", "evidence"}:
            raise ValueError("Use inputs.jsonl, not gold.jsonl; unexpected or gold fields detected")
        if not isinstance(row["id"], str) or not row["id"] or row["id"] in seen:
            raise ValueError("Inputs have missing/duplicate case IDs")
        if not isinstance(row["claim"], str) or not row["claim"].strip():
            raise ValueError("Input claim is empty")
        if not isinstance(row["evidence"], list):
            raise ValueError("evidence must be a list")
        pids = []
        for evidence in row["evidence"]:
            allowed = {"document_id", "passage_id", "content", "source", "source_type", "url", "published_at"}
            if not isinstance(evidence, dict) or not set(evidence) <= allowed:
                raise ValueError("Unexpected evidence metadata / possible gold leak")
            if not isinstance(evidence.get("content"), str) or not evidence.get("passage_id"):
                raise ValueError("Missing evidence content/passage_id")
            pids.append(evidence["passage_id"])
        if len(set(pids)) != len(pids):
            raise ValueError("Duplicate passage IDs in one case")
        seen.add(row["id"])
        records.append(row)
    if not records:
        raise ValueError("No input cases")
    return records


def protocol_prompt():
    protocol = DEFAULT_PROTOCOL.read_text(encoding="utf-8")
    marker = "```text\n"
    if protocol.count(marker) != 1:
        raise ValueError("Expected one frozen prompt in PROTOCOL.md")
    return protocol.split(marker, 1)[1].split("```", 1)[0].strip()


def text_sha256(path):
    """Line-ending independent hash for the frozen text files (see evaluate_model_gold)."""
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_phobert(config_path, project_rules):
    from src.system_builder import build_verifier, load_config
    from src.minimal_pair import MinimalPairVerifier
    from src.verdict_guard import GuardedVerifier
    config = load_config(ROOT, config_path)
    verifier, fallback = build_verifier(config, ROOT, engine="phobert", require_phobert=True)
    if fallback:
        raise RuntimeError("PhoBERT evaluation cannot use a rule-based fallback")
    metadata = dict(config["verification"])
    metadata["applied_project_rules"] = project_rules
    raw_verifier = verifier
    if project_rules and metadata.get("guard", False):
        verifier = GuardedVerifier(verifier)
    if project_rules and metadata.get("minimal_pair", True):
        verifier = MinimalPairVerifier(verifier)
    model_dir = ROOT / config["verification"]["model_path"]
    metadata["model_safetensors_sha256"] = sha256(model_dir / "model.safetensors")
    metadata["multi_passage_policy"] = "Each passage scored separately, then existing rank-aware aggregation"
    metadata["as_of_metadata_used"] = False
    return verifier, raw_verifier, metadata


def phobert_prediction(record, verifier, raw_verifier):
    from src.schemas import Evidence, RetrievedEvidence
    from src.evidence_focus import ensemble_texts, focus_text
    items = [RetrievedEvidence(Evidence(**evidence), float(len(record["evidence"]) - i))
             for i, evidence in enumerate(record["evidence"])]
    # Report potential truncation even if project rules later decide without calling PhoBERT.
    contents = [item.evidence.content for item in items]
    if raw_verifier.evidence_view == "ensemble":
        views = ensemble_texts(record["claim"], contents) if contents else []
    else:
        views = [focus_text(record["claim"], text, raw_verifier.evidence_view) for text in contents]
    lengths = []
    for text in views:
        encoded = raw_verifier.tokenizer(raw_verifier._segment(record["claim"]), raw_verifier._segment(text),
                                        truncation=False, verbose=False)
        lengths.append(len(encoded["input_ids"]))
    result = verifier.verify(record["claim"], items)
    return {"id": record["id"], **asdict(result),
            "input_diagnostics": {"pair_token_lengths": lengths, "max_length": raw_verifier.max_length,
                                  "pairs_over_limit": sum(n > raw_verifier.max_length for n in lengths)}}


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("phobert", "gemini"), required=True)
    parser.add_argument("--inputs", type=Path, default=DEFAULT_INPUTS)
    parser.add_argument("--output", type=Path, required=True, help="New prediction JSONL (refuses overwrite)")
    parser.add_argument("--config", type=Path, default=ROOT / "configs/config.yaml")
    parser.add_argument("--model", help="Gemini model ID; defaults to GEMINI_MODEL from .env")
    parser.add_argument("--project-rules", action="store_true", help="PhoBERT only: apply current minimal-pair/guard config")
    parser.add_argument("--limit", type=int, help="Smoke run only; not a full 84-case comparison")
    parser.add_argument("--timeout", type=float, default=90)
    parser.add_argument("--max-output-tokens", type=int, default=4096)
    parser.add_argument("--temperature", type=float)
    parser.add_argument("--json-mode", choices=("schema", "mime", "prompt"), default="schema",
                        help="Gemini API JSON mode; 'prompt' for models whose endpoint rejects JSON mode (e.g. some Gemma)")
    parser.add_argument("--pause-seconds", type=float, default=1, help="Pause between Gemini requests; no automatic retries")
    parser.add_argument("--max-retries", type=int, default=0,
                        help="Gemini only: retry transient HTTP 429/500/502/503/504 or network errors (label-blind); counted in metadata")
    parser.add_argument("--resume-from", type=Path,
                        help="Gemini only: copy successful rows from an earlier run of the SAME model/prompt/inputs and "
                             "call the API only for its failed (label null) cases; equivalent to a label-blind retry")
    parser.add_argument("--dry-run", action="store_true", help="Validate blind inputs and export run metadata; no model/API call")
    args = parser.parse_args()
    try:
        load_env(ROOT / ".env")
        records = load_inputs(args.inputs)
        if args.limit is not None:
            if args.limit < 1:
                raise ValueError("--limit must be positive")
            records = records[:args.limit]
        if args.pause_seconds < 0:
            raise ValueError("--pause-seconds cannot be negative")
        reused = {}
        if args.resume_from:
            if args.backend != "gemini":
                raise ValueError("--resume-from is only available for Gemini")
            previous_meta = json.loads(args.resume_from.with_name(args.resume_from.stem + ".run.json").read_text(encoding="utf-8"))
            previous_model = previous_meta.get("model")
            wanted_model = args.model or os.environ.get("GEMINI_MODEL")
            if previous_model != wanted_model:
                raise ValueError(f"--resume-from was made with model {previous_model}, not {wanted_model}")
            if previous_meta.get("prompt_sha256") != hashlib.sha256(protocol_prompt().encode("utf-8")).hexdigest():
                raise ValueError("--resume-from used a different prompt")
            previous_raw = {}
            raw_file = args.resume_from.with_name(args.resume_from.stem + ".raw.jsonl")
            if raw_file.exists():
                for line in raw_file.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        item = json.loads(line)
                        previous_raw[item["id"]] = item.get("response")
            for line in args.resume_from.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    if row.get("label"):
                        row["reused_from_previous_run"] = True
                        reused[row["id"]] = (row, previous_raw.get(row["id"]))
        if args.max_retries < 0:
            raise ValueError("--max-retries cannot be negative")
        if args.backend != "phobert" and args.project_rules:
            raise ValueError("--project-rules is only available for PhoBERT")
        prompt = protocol_prompt()
        input_hash = text_sha256(args.inputs)
        manifest = json.loads((DEFAULT_INPUTS.parent / "manifest.json").read_text(encoding="utf-8"))
        if input_hash != manifest["sha256"]["inputs.jsonl"]:
            raise ValueError("Inputs do not match the frozen 84-case dataset")
        if text_sha256(DEFAULT_PROTOCOL) != manifest["sha256"]["PROTOCOL.md"]:
            raise ValueError("Frozen protocol changed; do not silently change the comparison prompt")
        output = args.output.resolve()
        metadata_path = output.with_name(output.stem + ".run.json")
        raw_path = output.with_name(output.stem + ".raw.jsonl")
        protected_dir = DEFAULT_INPUTS.parent.resolve()
        for path in (output, metadata_path, raw_path):
            if path.exists() or path.is_relative_to(protected_dir):
                raise ValueError(f"Refusing to overwrite an existing/protected file: {path}")
        model = args.model or os.environ.get("GEMINI_MODEL")
        if args.backend == "gemini" and not model and not args.dry_run:
            raise ValueError("Set GEMINI_MODEL in .env or pass --model with an available model ID")
        metadata = {
            "started_at_utc": datetime.now(timezone.utc).isoformat(), "backend": args.backend,
            "case_count": len(records), "full_dataset": len(records) == 84,
            "dataset_version": manifest["dataset_version"], "inputs_sha256": input_hash,
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "runner_sha256": sha256(Path(__file__)), "python": sys.version,
            "gold_labels_loaded": False, "external_search": False,
            "automatic_retries": args.max_retries if args.backend == "gemini" else 0,
            "dry_run": args.dry_run, "model": model if args.backend == "gemini" else "phobert_rt_v2_balanced",
        }
        if args.backend == "gemini":
            metadata["generation"] = {"temperature": args.temperature, "max_output_tokens": args.max_output_tokens,
                                      "timeout": args.timeout, "pause_seconds": args.pause_seconds,
                                      "max_retries": args.max_retries,
                                      "json_mode": args.json_mode}
            metadata["client_sha256"] = sha256(ROOT / "src/gemini_gold.py")
        if args.dry_run:
            output.parent.mkdir(parents=True, exist_ok=True)
            metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"DRY RUN: {len(records)} blind cases; no predictions/model/API call. {metadata_path}")
            return 0
        if args.backend == "gemini":
            from src.gemini_gold import GeminiGoldClient
            client = GeminiGoldClient(model, timeout=args.timeout, max_output_tokens=args.max_output_tokens,
                                      temperature=args.temperature, json_mode=args.json_mode)
        else:
            os.environ.setdefault("HF_HOME", str(ROOT / ".cache/huggingface"))
            verifier, raw_verifier, settings = build_phobert(args.config, args.project_rules)
            metadata["verification"] = settings
            metadata["phobert_runtime_sha256"] = sha256(ROOT / "src/phobert_fact_checker.py")
            metadata["config_sha256"] = sha256(args.config if args.config.is_absolute() else ROOT / args.config)
        output.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        failures, truncated, retries_used = 0, 0, 0
        with output.open("x", encoding="utf-8") as predictions, raw_path.open("x", encoding="utf-8") as raw_log:
            for index, record in enumerate(records, 1):
                if record["id"] in reused:
                    prediction, raw = reused[record["id"]]
                    predictions.write(json.dumps(prediction, ensure_ascii=False) + "\n")
                    raw_log.write(json.dumps({"id": record["id"], "response": raw}, ensure_ascii=False) + "\n")
                    print(f"{index:02d}/{len(records)} {record['id']} {prediction['label']} (reused)", flush=True)
                    continue
                started = time.perf_counter()
                raw = None
                try:
                    if args.backend == "gemini":
                        attempt = 0
                        while True:
                            try:
                                prediction, raw = client.predict(record, prompt)
                                break
                            except RuntimeError as error:
                                text = str(error)
                                transient = any(f"HTTP {code}" in text for code in (429, 500, 502, 503, 504)) \
                                    or "network/timeout" in text
                                if not transient or attempt >= args.max_retries:
                                    raise
                                attempt += 1
                                retries_used += 1
                                time.sleep(min(60.0, 5.0 * 2 ** (attempt - 1)))
                        if attempt:
                            prediction["retries"] = attempt
                    else:
                        prediction = phobert_prediction(record, verifier, raw_verifier)
                        truncated += int(prediction["input_diagnostics"]["pairs_over_limit"] > 0)
                except Exception as error:
                    failures += 1
                    raw = getattr(error, "raw", None)
                    # Never propagate an arbitrary transport exception containing a credential.
                    message = str(error)
                    key = os.environ.get("GEMINI_API_KEY", "")
                    if key:
                        message = message.replace(key, "[REDACTED]")
                    prediction = {"id": record["id"], "label": None, "evidence_ids": [],
                                  "error": f"{type(error).__name__}: {message}"}
                prediction["latency_seconds"] = round(time.perf_counter() - started, 4)
                predictions.write(json.dumps(prediction, ensure_ascii=False) + "\n")
                predictions.flush()
                raw_log.write(json.dumps({"id": record["id"], "response": raw}, ensure_ascii=False) + "\n")
                raw_log.flush()
                print(f"{index:02d}/{len(records)} {record['id']} {prediction['label'] or 'ERROR'}", flush=True)
                if args.backend == "gemini" and index < len(records):
                    time.sleep(args.pause_seconds)
        metadata.update(finished_at_utc=datetime.now(timezone.utc).isoformat(), failed_cases=failures,
                        cases_with_truncated_pairs=truncated if args.backend == "phobert" else None,
                        retries_used=retries_used, reused_cases=len(reused),
                        resumed_from=str(args.resume_from) if args.resume_from else None,
                        predictions_sha256=sha256(output))
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Saved {output}; failures={failures}; truncated_cases={truncated}")
        return 1 if failures else 0
    except (ValueError, RuntimeError, OSError, KeyError, TypeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
