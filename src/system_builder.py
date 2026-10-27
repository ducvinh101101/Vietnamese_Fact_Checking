"""Dựng hệ thống kiểm chứng hoàn chỉnh từ config — dùng CHUNG cho giao diện (app.py) và CLI.

Trước đây giao diện chỉ chạy nhánh local còn nhánh web chỉ có trong CLI
(scripts/run_web_fact_check.py), và hai nơi dựng verifier khác nhau (CLI không dùng
evidence_view/minimal_pair đã chọn trên dev). Module này là nơi DUY NHẤT dựng hệ thống
để hai đầu vào cho kết quả giống nhau.

Hai chế độ:

* ``local``  — đúng pipeline đã đánh giá trên test (BM25 corpus ``paths.evidence_path``,
  top_k từ config, PhoBERT RT-V2 + evidence_view/minimal_pair/guard theo config).
  Số liệu báo cáo (Macro-F1 72,3% test) áp dụng cho chế độ này.
* ``hybrid`` — claim thời sự / ngoài kho: local W3-08 (corpus v2 + lọc metadata + rerank)
  + web Tavily qua allowlist, trộn RRF -> neo thời gian -> gộp URL/xếp chủ đề -> verifier.
  Guard hậu kiểm BẬT mặc định ở nhánh này (thiết kế cho claim thời sự). Chế độ này CHƯA
  có phép đo định lượng trên tập có nhãn; chỉ có golden test xác định (tests/golden).

Không có API key web hoặc web lỗi -> nhánh web rỗng, hệ thống vẫn chạy với local
(chính sách ``fail_to: local_only``) và báo rõ trạng thái trong ``web_status``.
"""

from __future__ import annotations

import os
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from src.contracts import Verifier
from src.fact_checker import RuleBasedFactChecker
from src.fusion_retriever import FusionRetriever
from src.io_utils import load_evidence_jsonl
from src.minimal_pair import MinimalPairVerifier
from src.pipeline import FactCheckingPipeline
from src.query_enrichment import TimeAwareRetriever
from src.reranked_retriever import MetadataRerankedRetriever
from src.retriever import BM25Retriever
from src.temporal_gate import TemporalGateRetriever
from src.topical_rerank import TopicalRerankRetriever
from src.verdict_guard import GuardedVerifier

ROOT = Path(__file__).resolve().parents[1]
MODES = ("local", "hybrid")
_BLOCKED_TORCH = "Application Control policy has blocked"


def load_dotenv(path: Path) -> None:
    """Nạp KEY=VALUE từ .env vào os.environ (không ghi đè biến đã có, không in giá trị)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


def load_config(root: Path = ROOT, config_path: Path | None = None) -> dict[str, Any]:
    path = config_path or root / "configs" / "config.yaml"
    path = path if path.is_absolute() else root / path
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@dataclass
class SystemOptions:
    mode: str = "local"
    use_web: bool = True              # chỉ có nghĩa ở hybrid; False = như --local-only của CLI
    as_of: date | None = None
    top_k: int | None = None          # None: local dùng retrieval.top_k, hybrid dùng 5
    candidate_k: int = 20
    window_today: int = 10
    window_current: int = 365
    time_enrich: bool = True
    temporal_gate: bool = True
    keep_undated: bool = False
    topical_rerank: bool = True
    guard: bool | None = None         # None: local theo config (false), hybrid bật
    local_plain: bool = False
    engine: str | None = None         # None: theo config; "rule_based" để demo/test không cần GPU
    require_phobert: bool = False

    def __post_init__(self) -> None:
        if self.mode not in MODES:
            raise ValueError(f"mode không hợp lệ: {self.mode!r}; chọn một trong {MODES}")
        if self.top_k is not None and self.top_k < 1:
            raise ValueError("top_k phải lớn hơn 0")


@dataclass
class FactCheckSystem:
    pipeline: FactCheckingPipeline
    mode: str
    fallback_reason: str | None = None
    web_status: str | None = None
    web_layer: TimeAwareRetriever | None = None
    fusion: FusionRetriever | None = None
    gate: TemporalGateRetriever | None = None
    guard: GuardedVerifier | None = None
    minimal_pair: MinimalPairVerifier | None = None
    settings: dict[str, Any] = field(default_factory=dict)

    def check(self, claim: str) -> dict[str, Any]:
        """Chạy pipeline, trả JSON contract W3-03 + ``origin`` từng bằng chứng + ``diagnostics``."""
        response = self.pipeline.run_json(claim)
        for record in [*response["retrieval"]["evidence"], *response["citations"]]:
            record["origin"] = "web" if str(record["passage_id"]).startswith("web-") else "local"
        response["diagnostics"] = self.diagnostics()
        return response

    def diagnostics(self) -> dict[str, Any]:
        info: dict[str, Any] = {"mode": self.mode, "settings": dict(self.settings),
                                "fallback_reason": self.fallback_reason, "web_status": self.web_status}
        if self.web_layer is not None:
            info["web_enriched_query"] = self.web_layer.last_enriched_query
        if self.fusion is not None:
            info["web_error"] = self.fusion.last_web_error
        if self.gate is not None and self.gate.last_applied:
            info["temporal_gate"] = {
                "recency_class": self.gate.last_class,
                "cutoff": self.gate.last_cutoff.isoformat() if self.gate.last_cutoff else None,
                "window_days": self.gate.last_window,
                "kept": self.gate.last_kept,
                "dropped_stale": self.gate.last_dropped_stale,
                "dropped_undated": self.gate.last_dropped_undated,
                "dropped_future": getattr(self.gate, "last_dropped_future", 0),
                "dropped": [
                    {"reason": reason,
                     "origin": "web" if str(item.evidence.passage_id).startswith("web-") else "local",
                     "source": item.evidence.source,
                     "published_at": item.evidence.published_at,
                     "url": item.evidence.url}
                    for reason, item in self.gate.last_dropped_items
                ],
            }
        if self.guard is not None and self.guard.last_downgraded:
            info["guard_reason"] = self.guard.last_reason
        if self.minimal_pair is not None and self.minimal_pair.last_reason:
            info["minimal_pair_reason"] = self.minimal_pair.last_reason
        return info


def build_verifier(config: dict[str, Any], root: Path = ROOT, engine: str | None = None,
                   require_phobert: bool = False) -> tuple[Verifier, str | None]:
    """Verifier theo config. Trả (verifier, lý do fallback) — fallback rule-based CHỈ khi
    Windows Application Control chặn torch, và luôn báo ra ngoài để giao diện hiển thị."""
    v = config["verification"]
    engine = engine or v["engine"]
    rule_based = RuleBasedFactChecker(float(v.get("support_threshold", 0.45)), v.get("refute_markers"))
    if engine == "rule_based":
        return rule_based, None
    if engine != "phobert":
        raise ValueError(f"Verifier không hỗ trợ: {engine}")
    from src.phobert_fact_checker import PhoBERTFactChecker  # import muộn: torch nặng

    try:
        return PhoBERTFactChecker(
            str(root / v["model_path"]), str(root / v["vncorenlp_dir"]),
            int(v["max_length"]), float(v.get("temperature", 1.0)),
            float(v.get("decisive_min_confidence", 0.0)), float(v.get("retrieval_rank_bias", 0.0)),
            aggregation_model_path=str(root / v["aggregation_model_path"]) if v.get("aggregation_model_path") else None,
            evidence_view=v.get("evidence_view", "passage"),
        ), None
    except RuntimeError as error:
        if require_phobert or _BLOCKED_TORCH not in str(error):
            raise
        return rule_based, str(error)


def load_web_retriever(root: Path = ROOT) -> tuple[Any | None, str]:
    """WebRetriever từ configs/web_retrieval.yaml (bật lúc chạy). Không có key -> (None, lý do)."""
    from src.web_retriever import WebRetriever

    config = deepcopy(yaml.safe_load((root / "configs" / "web_retrieval.yaml").read_text(encoding="utf-8")))
    config["enabled"] = True
    config["cache"] = dict(config["cache"])
    config["cache"]["directory"] = str(root / ".cache" / "web_retrieval")
    key_env = config["provider"]["api_key_env"]
    if not os.environ.get(key_env):
        return None, f"Thiếu biến môi trường {key_env} (đặt trong .env hoặc PowerShell); đang chạy chỉ với kho local."
    hosts = len(config["source_policy"]["allowlist"])
    return WebRetriever(config), f"Web bật: Tavily, chỉ nhận {hosts} nguồn trong allowlist."


def _find(wrapper: Any, kind: type) -> Any | None:
    node = wrapper
    while node is not None:
        if isinstance(node, kind):
            return node
        node = getattr(node, "inner", None)
    return None


def build_system(options: SystemOptions | None = None, config: dict[str, Any] | None = None,
                 root: Path = ROOT, web_retriever: Any | None = None,
                 verifier: Verifier | None = None) -> FactCheckSystem:
    """Dựng hệ thống. ``web_retriever``/``verifier`` cho phép test tiêm bản giả (không mạng/GPU)."""
    options = options or SystemOptions()
    config = config or load_config(root)
    v = config["verification"]
    fallback_reason = None
    if verifier is None:
        verifier, fallback_reason = build_verifier(config, root, options.engine, options.require_phobert)
    minimal_pair = bool(v.get("minimal_pair", True))

    if options.mode == "local":
        guard = bool(v.get("guard", False)) if options.guard is None else options.guard
        top_k = options.top_k or int(config["retrieval"]["top_k"])
        pipeline = FactCheckingPipeline(
            evidence_path=str(root / config["paths"]["evidence_path"]), top_k=top_k,
            checker=verifier, guard=guard, minimal_pair=minimal_pair,
        )
        return FactCheckSystem(
            pipeline, "local", fallback_reason,
            guard=_find(pipeline.checker, GuardedVerifier),
            minimal_pair=_find(pipeline.checker, MinimalPairVerifier),
            settings={"top_k": top_k, "guard": guard, "minimal_pair": minimal_pair,
                      "evidence_view": v.get("evidence_view", "passage"),
                      "corpus": config["paths"]["evidence_path"]},
        )

    # --- hybrid: local W3-08 + web, RRF, neo thời gian, gộp URL/xếp chủ đề.
    if options.local_plain:
        local = BM25Retriever(load_evidence_jsonl(root / config["paths"]["evidence_path"]))
        corpus = config["paths"]["evidence_path"]
    else:
        rr = yaml.safe_load((root / "configs" / "reranked_retrieval.yaml").read_text(encoding="utf-8"))
        local = MetadataRerankedRetriever(BM25Retriever(load_evidence_jsonl(root / rr["corpus"])), rr)
        corpus = rr["corpus"]

    web, web_status = None, "Đã tắt web (chỉ dùng kho local)."
    if options.use_web:
        if web_retriever is not None:
            web, web_status = web_retriever, "Web bật (retriever tiêm vào)."
        else:
            web, web_status = load_web_retriever(root)
    web_layer = None
    if web is not None:
        web_layer = TimeAwareRetriever(web, as_of=options.as_of, enabled=options.time_enrich,
                                       window_today=options.window_today, window_current=options.window_current)
    fusion = FusionRetriever(local, web_layer or web, candidate_k=options.candidate_k)
    gate = TemporalGateRetriever(
        fusion, as_of=options.as_of, window_today=options.window_today, window_current=options.window_current,
        candidate_k=options.candidate_k, drop_unknown_dates=not options.keep_undated,
        enabled=options.temporal_gate,
    )
    retriever = TopicalRerankRetriever(gate, candidate_k=options.candidate_k, enabled=options.topical_rerank)
    guard = True if options.guard is None else options.guard
    top_k = options.top_k or 5
    pipeline = FactCheckingPipeline(retriever=retriever, checker=verifier, top_k=top_k,
                                    guard=guard, minimal_pair=minimal_pair)
    return FactCheckSystem(
        pipeline, "hybrid", fallback_reason, web_status=web_status, web_layer=web_layer,
        fusion=fusion, gate=gate,
        guard=_find(pipeline.checker, GuardedVerifier),
        minimal_pair=_find(pipeline.checker, MinimalPairVerifier),
        settings={"top_k": top_k, "guard": guard, "minimal_pair": minimal_pair,
                  "evidence_view": v.get("evidence_view", "passage"), "corpus": corpus,
                  "web": web is not None, "temporal_gate": options.temporal_gate,
                  "window_today": options.window_today, "window_current": options.window_current,
                  "topical_rerank": options.topical_rerank},
    )
