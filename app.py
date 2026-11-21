from datetime import datetime
from html import escape
import os
from pathlib import Path
import time

import streamlit as st
import yaml

from src.env_loader import load_dotenv
from src.pipeline import FactCheckingPipeline
from src.web_retriever import WEB_FAILURE_MESSAGES, WEB_RETRYABLE_STATUSES


ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")
SOURCE_MODE = "Kiểm tra nguồn"
LEGACY_MODE = "Kiểm chứng RT-V2 (cũ)"
EXAMPLES = {
    "Tin thật 2025": "Từ ngày 1/7/2025, cả nước vận hành chính quyền địa phương hai cấp và còn 34 tỉnh, thành phố.",
    "Tin bịa": "Bộ Y tế khuyến cáo uống nước chanh ấm mỗi sáng giúp chữa khỏi ung thư gan.",
    "Lệch số liệu": "Giá xăng RON 95 giảm 500 đồng mỗi lít từ chiều nay.",
}

# Lucide icons (stroke, 24×24) – không dùng emoji làm icon.
ICONS = {
    "check": '<path d="M21.8 10A10 10 0 1 1 17 3.34"/><path d="m9 11 3 3L22 4"/>',
    "alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    "x": '<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/>',
    "help": '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>',
}
VERDICT_STYLE = {
    "SOURCE_FOUND": ("found", "check"),
    "SOURCE_CONFLICT": ("conflict", "alert"),
    "NO_SOURCE": ("none", "x"),
    "SUPPORTED": ("found", "check"),
    "REFUTED": ("none", "x"),
    "NOT_ENOUGH_INFO": ("neutral", "help"),
}
STATUS_TEXT = {"supports": "Xác nhận", "conflicts": "Lệch / mâu thuẫn", "related": "Liên quan, chưa đủ",
               "unrelated": "Không liên quan"}
STATUS_TONE = {"supports": "found", "conflicts": "conflict", "related": "neutral", "unrelated": "muted"}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700&family=Newsreader:opsz,wght@6..72,500;6..72,600&display=swap');
:root {
  --ink: #1C1917; --muted: #57534E; --faint: #78716C; --paper: #FAFAF7; --card: #FFFFFF; --line: #E4E2DC;
  --accent: #1E40AF; --accent-soft: #EEF2FF;
  --found: #166534; --found-bg: #F0FDF4; --found-line: #86EFAC;
  --conflict: #92400E; --conflict-bg: #FFFBEB; --conflict-line: #FCD34D;
  --none: #991B1B; --none-bg: #FEF2F2; --none-line: #FCA5A5;
  --neutral: #334155; --neutral-bg: #F1F5F9; --neutral-line: #CBD5E1;
}
.stApp, .stApp p, .stApp li, .stApp label, .stApp textarea, .stApp input, .stApp button p, .stApp a p,
.stApp div[data-testid="stMarkdownContainer"] { font-family: 'Be Vietnam Pro', system-ui, sans-serif; }
.block-container { max-width: 860px; padding-top: 2.2rem; padding-bottom: 4rem; }
.stApp h1, .stApp h2, .stApp h3, .stApp .masthead h1, .serif {
  font-family: 'Newsreader', Georgia, serif !important; letter-spacing: -0.01em; font-weight: 600 !important; }
.masthead { border-bottom: 1px solid var(--line); padding-bottom: 1.1rem; margin-bottom: 1.4rem; }
.kicker { color: var(--accent); font-size: .78rem; font-weight: 600; letter-spacing: .12em; text-transform: uppercase; }
.masthead h1 { font-size: 2.35rem; line-height: 1.15; margin: .35rem 0 .5rem; color: var(--ink); padding: 0; }
.lede { color: var(--muted); font-size: 1.02rem; line-height: 1.6; margin: 0; max-width: 46rem; }
.chips { display: flex; flex-wrap: wrap; gap: .4rem; margin: .2rem 0 .2rem; }
.chip { display: inline-flex; align-items: center; gap: .3rem; font-size: .8rem; line-height: 1.2; padding: .28rem .6rem;
        border-radius: 999px; border: 1px solid var(--line); background: var(--card); color: var(--muted); white-space: nowrap; }
.chip.found { color: var(--found); background: var(--found-bg); border-color: var(--found-line); }
.chip.conflict { color: var(--conflict); background: var(--conflict-bg); border-color: var(--conflict-line); }
.chip.none { color: var(--none); background: var(--none-bg); border-color: var(--none-line); }
.chip.neutral { color: var(--neutral); background: var(--neutral-bg); border-color: var(--neutral-line); }
.chip.muted { color: var(--faint); }
.chip.accent { color: var(--accent); background: var(--accent-soft); border-color: #C7D2FE; }
.dot { width: .45rem; height: .45rem; border-radius: 50%; background: currentColor; display: inline-block; }
.verdict { border: 1px solid var(--line); border-left-width: 6px; border-radius: .75rem; padding: 1.25rem 1.4rem;
           background: var(--card); margin: 1.2rem 0 1rem; }
.verdict.found { border-color: var(--found-line); border-left-color: var(--found); background: var(--found-bg); }
.verdict.conflict { border-color: var(--conflict-line); border-left-color: var(--conflict); background: var(--conflict-bg); }
.verdict.none { border-color: var(--none-line); border-left-color: var(--none); background: var(--none-bg); }
.verdict.neutral { border-color: var(--neutral-line); border-left-color: var(--neutral); background: var(--neutral-bg); }
.verdict-head { display: flex; align-items: center; gap: .75rem; }
.verdict-head svg { width: 2rem; height: 2rem; flex: none; }
.verdict.found .verdict-head { color: var(--found); } .verdict.conflict .verdict-head { color: var(--conflict); }
.verdict.none .verdict-head { color: var(--none); } .verdict.neutral .verdict-head { color: var(--neutral); }
.verdict-title { font-family: 'Newsreader', Georgia, serif; font-size: 1.6rem; font-weight: 600; line-height: 1.2; }
.verdict-code { font-family: ui-monospace, Consolas, monospace; font-size: .75rem; color: var(--faint); margin-left: auto; }
.verdict-claim { font-family: 'Newsreader', Georgia, serif; font-size: 1.08rem; color: var(--ink); font-style: italic;
                 margin: .8rem 0 .4rem; line-height: 1.5; }
.verdict-text { color: var(--ink); margin: .2rem 0 0; line-height: 1.6; }
.stats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .75rem; margin-top: 1rem; }
.stat { background: rgba(255,255,255,.7); border: 1px solid var(--line); border-radius: .6rem; padding: .7rem .85rem; }
.stat-label { font-size: .75rem; color: var(--muted); text-transform: uppercase; letter-spacing: .06em; }
.stat-value { font-size: 1.45rem; font-weight: 600; color: var(--ink); font-variant-numeric: tabular-nums; }
.meter { height: .35rem; background: var(--line); border-radius: 999px; overflow: hidden; margin-top: .35rem; }
.meter > span { display: block; height: 100%; background: var(--ink); border-radius: 999px; }
.section-eyebrow { font-size: .74rem; font-weight: 600; letter-spacing: .1em; text-transform: uppercase; color: var(--faint);
                   margin: 1.8rem 0 .1rem; }
.section-title { font-family: 'Newsreader', Georgia, serif; font-size: 1.4rem; font-weight: 600; margin: 0 0 .7rem; color: var(--ink); }
.src-head { display: flex; align-items: center; gap: .7rem; }
.src-badge { width: 2.2rem; height: 2.2rem; border-radius: .5rem; background: var(--ink); color: #fff; display: grid;
             place-items: center; font-weight: 700; font-size: .95rem; flex: none; text-transform: uppercase; }
.src-name { font-weight: 600; color: var(--ink); line-height: 1.25; }
.src-domain { font-size: .82rem; color: var(--muted); }
.src-rel { margin-left: auto; }
.quote { font-family: 'Newsreader', Georgia, serif; font-size: 1.04rem; line-height: 1.6; color: var(--ink);
         border-left: 3px solid var(--line); padding: .1rem 0 .1rem .9rem; margin: .8rem 0 .7rem; }
.meta { font-size: .8rem; color: var(--faint); margin-top: .45rem; }
.probs { display: flex; gap: .9rem; flex-wrap: wrap; font-size: .8rem; color: var(--muted); margin: .25rem 0 .4rem; }
.probs b { color: var(--ink); font-variant-numeric: tabular-nums; }
.passage { font-size: .92rem; line-height: 1.55; color: var(--ink); margin: .2rem 0 .3rem; }
.empty { border: 1px dashed var(--line); border-radius: .75rem; padding: 1.1rem 1.2rem; color: var(--muted); background: var(--card); }
.footnote { color: var(--faint); font-size: .8rem; line-height: 1.5; border-top: 1px solid var(--line); margin-top: 2.2rem; padding-top: .9rem; }
div[data-testid="stTextArea"] textarea { font-size: 1.02rem; line-height: 1.55; }
div[data-testid="stButton"] button, div[data-testid="stLinkButton"] a { transition: background-color .18s ease, border-color .18s ease; }
@media (max-width: 640px) {
  .block-container { padding-top: 3.4rem; }
  .masthead h1 { font-size: 1.8rem; } .verdict-code { display: none; } .verdict { padding: 1rem 1rem; }
  .stats { gap: .4rem; } .stat { padding: .55rem .6rem; }
  .stat-label { font-size: .64rem; letter-spacing: .03em; } .stat-value { font-size: 1.15rem; }
}
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
</style>
"""


def load_yaml(name: str) -> dict:
    with (ROOT / "configs" / name).open(encoding="utf-8") as file:
        return yaml.safe_load(file)


@st.cache_resource(show_spinner=False)
def get_checker():
    """Một instance PhoBERT RT-V2 cho chế độ cũ (VnCoreNLP dùng chung qua shared_vncorenlp)."""
    from src.phobert_fact_checker import PhoBERTFactChecker

    verification = load_yaml("config.yaml")["verification"]
    return PhoBERTFactChecker(
        ROOT / verification["model_path"], ROOT / verification["vncorenlp_dir"], verification["max_length"],
        verification.get("temperature", 1.0), verification.get("decisive_min_confidence", 0.0),
        verification.get("retrieval_rank_bias", 0.0),
        aggregation_model_path=str(ROOT / verification["aggregation_model_path"]) if verification.get("aggregation_model_path") else None,
    )


@st.cache_resource(show_spinner=False)
def get_pipeline() -> FactCheckingPipeline:
    config = load_yaml("config.yaml")
    verification = config["verification"]
    checker = get_checker() if verification["engine"] == "phobert" else None
    return FactCheckingPipeline(
        evidence_path=str(ROOT / config["paths"]["evidence_path"]),
        top_k=config["retrieval"]["top_k"],
        support_threshold=verification["support_threshold"],
        refute_markers=verification["refute_markers"],
        engine=verification["engine"],
        checker=checker,
    )


@st.cache_resource(show_spinner=False)
def get_source_pipeline():
    from src.source_attribution_factory import build_pipeline, build_verifier, load_config

    config = load_config()
    verifier = None
    if config["verifier"].get("enabled"):
        legacy_model = load_yaml("config.yaml")["verification"]["model_path"]
        # Cùng model với pipeline cũ thì dùng chung instance; khác (vd. RT-V3) thì nạp riêng.
        same = Path(config["verifier"]["model_path"]) == Path(legacy_model)
        verifier = get_checker() if same else build_verifier(config)
    return build_pipeline(config, verifier=verifier, use_verifier=verifier is not None)


@st.cache_data(show_spinner=False)
def run_cached(claim: str) -> dict[str, object]:
    """Cache a JSON-safe response; the model resource remains cached separately."""
    return get_pipeline().run_json(claim)


class WebUnavailable(Exception):
    """Ném ra BÊN TRONG hàm cache khi web lỗi: st.cache_data không lưu ngoại lệ, nên kết quả
    "chỉ kho cục bộ" do lỗi mạng tạm thời không bị ghi nhớ và lần sau sẽ tra web lại."""

    def __init__(self, response: dict[str, object]) -> None:
        super().__init__(str(response["retrieval"]["web_status"]))  # type: ignore[index]
        self.response = response


def web_status(response: dict[str, object]) -> str | None:
    return response.get("retrieval", {}).get("web_status")  # type: ignore[union-attr]


@st.cache_data(show_spinner=False)
def run_source_cached(claim: str) -> dict[str, object]:
    response = get_source_pipeline().run_json(claim)
    if web_status(response) in WEB_FAILURE_MESSAGES:
        raise WebUnavailable(response)
    return response


def run_source(claim: str) -> dict[str, object]:
    """Chạy kiểm tra nguồn; web lỗi tạm thời thì tự thử lại một lần, vẫn lỗi thì trả kết quả kèm trạng thái lỗi."""
    try:
        return run_source_cached(claim)
    except WebUnavailable as failure:
        response = failure.response
    if web_status(response) in WEB_RETRYABLE_STATUSES:
        try:
            return run_source_cached(claim)
        except WebUnavailable as failure:
            response = failure.response
    return response


def web_enabled() -> bool:
    try:
        return bool(load_yaml("source_attribution.yaml")["web"].get("enabled")) and bool(os.environ.get("TAVILY_API_KEY"))
    except (OSError, KeyError):
        return False


# ---------- Thành phần hiển thị ----------
def html(markup: str) -> None:
    # Gộp về một dòng: dòng trống/thụt lề trong khối HTML sẽ bị Markdown hiểu thành đoạn văn hoặc code.
    st.markdown(" ".join(line.strip() for line in markup.splitlines() if line.strip()), unsafe_allow_html=True)


def icon(name: str) -> str:
    return (f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-hidden="true">{ICONS[name]}</svg>')


def chip(text: str, tone: str = "", dot: bool = False) -> str:
    return f'<span class="chip {tone}">{"<span class=dot></span>" if dot else ""}{escape(str(text))}</span>'


def format_date(value) -> str:
    if not value:
        return "không rõ"
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime("%d/%m/%Y")
    except ValueError:
        return escape(str(value))


def section(eyebrow: str, title: str) -> None:
    html(f'<div class="section-eyebrow">{escape(eyebrow)}</div><div class="section-title">{escape(title)}</div>')


def verdict_card(label: str, title: str, explanation: str, claim: str, stats: list[tuple[str, str, float | None]],
                 footer: str = "") -> None:
    tone, icon_name = VERDICT_STYLE.get(label, ("neutral", "help"))
    stat_html = "".join(
        f'<div class="stat"><div class="stat-label">{escape(name)}</div><div class="stat-value">{escape(value)}</div>'
        + (f'<div class="meter"><span style="width:{max(0.0, min(1.0, fill)) * 100:.0f}%"></span></div>' if fill is not None else "")
        + "</div>"
        for name, value, fill in stats
    )
    html(f"""
<div class="verdict {tone}" role="status">
  <div class="verdict-head">{icon(icon_name)}<span class="verdict-title">{escape(title)}</span>
    <span class="verdict-code">{escape(label)}</span></div>
  <div class="verdict-claim">“{escape(claim)}”</div>
  <p class="verdict-text">{escape(explanation)}</p>
  <div class="stats">{stat_html}</div>
  {footer}
</div>""")


def source_header(name: str, domain: str, right: str = "") -> str:
    initial = escape((domain or name or "?").removeprefix("www.")[:1])
    return (f'<div class="src-head"><div class="src-badge" aria-hidden="true">{initial}</div>'
            f'<div><div class="src-name">{escape(name or domain or "Không rõ nguồn")}</div>'
            f'<div class="src-domain">{escape(domain or "kho cục bộ")}</div></div>'
            f'<div class="src-rel">{right}</div></div>')


def probabilities_line(probabilities: dict | None) -> str:
    if not probabilities:
        return ""
    names = {"SUPPORTED": "Xác nhận", "REFUTED": "Mâu thuẫn", "NOT_ENOUGH_INFO": "Chưa đủ"}
    parts = "".join(f"<span>{names.get(k, k)} <b>{v:.2f}</b></span>" for k, v in probabilities.items())
    return f'<div class="probs" aria-label="Xác suất RT-V3">{parts}</div>'


def show_source_result(claim: str, response: dict, seconds: float) -> None:
    verdict = response["verdict"]
    status = web_status(response)
    if status in WEB_FAILURE_MESSAGES:
        retry = " Bấm “Kiểm tra nguồn” để thử lại." if status in WEB_RETRYABLE_STATUSES else ""
        st.warning(f"**Lần này chưa tra được web – kết quả chỉ dựa trên kho dữ liệu cục bộ**, nên có thể báo "
                   f"“Không tìm thấy nguồn” dù tin có thật. {WEB_FAILURE_MESSAGES[status]}{retry}",
                   icon=":material/wifi_off:")
    sources = verdict["independent_sources"]
    assessed = response["retrieval"]["assessed"]
    domains = "".join(chip(domain, "accent") for domain in sources)
    verdict_card(
        str(verdict["label"]), str(verdict["label_text"]), str(verdict["explanation"]), claim,
        [("Điểm khớp", f"{float(verdict['confidence']):.2f}", float(verdict["confidence"])),
         ("Nguồn độc lập", str(len(sources)), None),
         ("Đoạn đã đánh giá", str(len(assessed)), None)],
        footer=f'<div class="chips" style="margin-top:.8rem">{domains}</div>' if domains else "",
    )
    st.caption(f"Xử lý trong {seconds:.1f} giây. Điểm khớp đo mức độ đoạn trích khớp phát biểu, "
               "không phải xác suất phát biểu đúng; hãy mở nguồn để đọc đối chiếu.")

    section("Nhánh verifier", "Nguồn được dùng để kết luận")
    if not response["citations"]:
        html('<div class="empty">Không có đoạn nào đủ liên quan và được verifier xác nhận để làm nguồn cho phát biểu này. '
             'Có thể thông tin chưa được báo chí chính thống đăng, hoặc phát biểu đã bị diễn đạt sai lệch.</div>')
    for index, item in enumerate(response["citations"]):
        with st.container(border=True):
            relevance = chip(f"Liên quan {item['relevance']:.2f}", "accent")
            html(source_header(str(item["source"]), str(item.get("domain") or ""), relevance))
            html(f'<div class="quote">{escape(str(item["content"]))}</div>')
            facets = ([chip(f"Khớp: {d}", "found", True) for d in item["matched_details"]]
                      + [chip(f"Lệch: {d}", "conflict", True) for d in item["conflicting_details"]]
                      + [chip(f"Không nhắc tới: {d}", "muted", True) for d in item["missing_details"]])
            if facets:
                html(f'<div class="chips">{"".join(facets)}</div>')
            html(probabilities_line(item.get("verifier_probabilities")))
            html(f'<div class="meta">Xuất bản: {format_date(item.get("published_at"))} · '
                 f'Truy xuất: {format_date(item.get("retrieved_at")) if item.get("retrieved_at") else "kho cục bộ"}</div>')
            if item["url"]:
                st.link_button("Mở bài gốc", str(item["url"]), icon=":material/open_in_new:",
                               key=f"cite-{index}-{item['passage_id']}")

    section("Nhánh retrieval", "Quá trình tìm kiếm")
    with st.expander(f"Nhánh retrieval: {response['retrieval']['retrieved_count']} ứng viên, "
                     f"{len(assessed)} đoạn đã đánh giá", icon=":material/manage_search:"):
        for index, item in enumerate(assessed):
            tone = STATUS_TONE.get(item["status"], "muted")
            head = chip(STATUS_TEXT.get(item["status"], item["status"]), tone, True)
            html(source_header(str(item["source"]), str(item.get("domain") or ""),
                               head + " " + chip(f"Liên quan {item['relevance']:.2f}")))
            html(probabilities_line(item.get("verifier_probabilities")))
            html(f'<div class="passage">{escape(str(item["content"]))}</div>')
            if item["url"]:
                st.link_button("Mở URL nguồn", str(item["url"]), icon=":material/open_in_new:", type="tertiary",
                               key=f"url-{index}-{item['passage_id']}")
            if index < len(assessed) - 1:
                st.divider()
    with st.expander("Truy vấn đã dùng", icon=":material/search:"):
        for query in response["queries"]:
            st.code(query, language=None, wrap_lines=True)


def show_legacy_result(claim: str, response: dict, seconds: float) -> None:
    verdict = response["verdict"]
    retrieval = response["retrieval"]
    citations = response["citations"]
    titles = {"SUPPORTED": "Được bằng chứng ủng hộ", "REFUTED": "Bị bằng chứng bác bỏ",
              "NOT_ENOUGH_INFO": "Chưa đủ bằng chứng"}
    label = str(verdict["label"])
    verdict_card(label, titles.get(label, label), str(verdict["explanation"]), claim,
                 [("Điểm mô hình", f"{float(verdict['confidence']):.2f}", float(verdict["confidence"])),
                  ("Citation", str(len(citations)), None),
                  ("Passage tìm thấy", str(retrieval["retrieved_count"]), None)])
    st.caption(f"Xử lý trong {seconds:.1f} giây. Điểm mô hình không phải xác suất thông tin đúng trong thực tế.")

    section("Nhánh verifier", "Citation dùng cho kết luận")
    if not citations:
        html('<div class="empty">Chưa có đoạn được dùng để xác nhận hoặc bác bỏ phát biểu.</div>')
    cited_ids = {str(item["passage_id"]) for item in citations}
    for index, item in enumerate(citations):
        with st.container(border=True):
            html(source_header(str(item["source"]), str(item.get("domain") or ""),
                               chip(f"Retrieval {float(item['score']):.2f}", "accent")))
            html(f'<div class="quote">{escape(str(item["content"]))}</div>')
            html(f'<div class="meta">Truy xuất: {format_date(item.get("retrieved_at"))}</div>')
            if item["url"]:
                st.link_button("Mở nguồn", str(item["url"]), icon=":material/open_in_new:", key=f"lcite-{index}")

    section("Nhánh retrieval", "Các passage đã tìm thấy")
    with st.expander(f"Nhánh retrieval: {retrieval['retrieved_count']} passage đã tìm thấy", icon=":material/manage_search:"):
        for index, item in enumerate(retrieval["evidence"]):
            cited = item["passage_id"] in cited_ids
            marker = chip("Được verifier trích dẫn" if cited else "Ứng viên, chưa trích dẫn", "found" if cited else "muted", True)
            html(source_header(str(item["source"]), str(item.get("domain") or ""),
                               marker + " " + chip(f"Score {float(item['score']):.2f}")))
            html(f'<div class="passage">{escape(str(item["content"]))}</div>')
            html(f'<div class="meta">{escape(str(item.get("source_type") or ""))} · xuất bản: {format_date(item.get("published_at"))}</div>')
            if item["url"]:
                st.link_button("Mở URL nguồn", str(item["url"]), icon=":material/open_in_new:", type="tertiary",
                               key=f"lurl-{index}")
            if index < len(retrieval["evidence"]) - 1:
                st.divider()


def use_example() -> None:
    choice = st.session_state.get("example")
    if choice:
        st.session_state["claim"] = EXAMPLES[choice]
        st.session_state["example"] = None


# ---------- Trang ----------
st.set_page_config(page_title="Kiểm tra nguồn tin tiếng Việt", page_icon=":material/fact_check:", layout="centered")
html(CSS)

with st.sidebar:
    st.markdown("### Cách đọc kết quả")
    html(f"""
<div class="chips" style="flex-direction:column;align-items:flex-start;gap:.55rem">
  {chip("Có nguồn xác nhận", "found", True)}
  <span class="meta" style="margin:0">Có đoạn từ nguồn chính thống nói cùng nội dung, khớp số liệu và ngày tháng.</span>
  {chip("Có nguồn nhưng lệch chi tiết", "conflict", True)}
  <span class="meta" style="margin:0">Nguồn nói về cùng sự việc nhưng khác con số, ngày tháng, hoặc nói ngược lại.</span>
  {chip("Không tìm thấy nguồn", "none", True)}
  <span class="meta" style="margin:0">Không có đoạn nào đủ liên quan và được xác nhận. Không có nghĩa là chắc chắn sai.</span>
</div>""")
    st.markdown("### Nguồn tra cứu")
    st.caption("Kho ViFactCheck (1.041 bài báo) và, khi có `TAVILY_API_KEY`, web giới hạn trong 25 tên miền: "
               "cơ quan nhà nước, TTXVN, báo chí chính thống, tingia.gov.vn.")
    st.markdown("### Mô hình")
    st.caption("PhoBERT RT-V3 (xác nhận / mâu thuẫn / chưa đủ) và VnCoreNLP tách từ. "
               "Chế độ cũ dùng RT-V2 với nhãn SUPPORTED / REFUTED / NEI.")

html("""
<header class="masthead">
  <div class="kicker">Kiểm chứng nguồn tin tiếng Việt</div>
  <h1>Phát biểu này có nguồn thật không?</h1>
  <p class="lede">Nhập một phát biểu. Hệ thống tìm trong báo chí chính thống và cơ quan nhà nước, đối chiếu từng đoạn
  bằng mô hình PhoBERT, rồi cho biết có nguồn nói cùng nội dung hay không, kèm đoạn trích và đường dẫn để bạn tự kiểm tra.</p>
</header>""")

mode = st.segmented_control("Chế độ", [SOURCE_MODE, LEGACY_MODE], default=SOURCE_MODE, required=True,
                            label_visibility="collapsed", key="mode")
status_chips = (chip("Web: 25 nguồn chính thống", "found", True) if web_enabled()
                else chip("Chỉ kho cục bộ (chưa có TAVILY_API_KEY)", "muted", True))
if mode == SOURCE_MODE:
    html(f'<div class="chips">{status_chips}{chip("Verifier: PhoBERT RT-V3")}</div>')
else:
    html(f'<div class="chips">{chip("Kho cục bộ · BM25 top-3")}{chip("Verifier: PhoBERT RT-V2")}</div>')

# Liên kết chia sẻ được: ?q=<phát biểu> tự điền và tự kiểm tra một lần mỗi phiên.
auto_run = False
if st.query_params.get("q") and not st.session_state.get("_deeplink_done"):
    st.session_state["claim"] = st.query_params["q"][:2000]
    st.session_state["_deeplink_done"] = True
    auto_run = True

st.pills("Thử nhanh", list(EXAMPLES), key="example", on_change=use_example)
claim = st.text_area("Phát biểu cần kiểm tra", key="claim", height=110, max_chars=2000,
                     placeholder="Ví dụ: Từ ngày 1/7/2025, cả nước còn 34 tỉnh, thành phố.")
submitted = st.button("Kiểm tra nguồn" if mode == SOURCE_MODE else "Kiểm chứng", type="primary",
                      icon=":material/search:", width="stretch") or auto_run

if submitted:
    text = (claim or "").strip()
    if len(text) < 10:
        st.warning("Hãy nhập một phát biểu đầy đủ (ít nhất 10 ký tự) trước khi kiểm tra.", icon=":material/edit_note:")
    else:
        try:
            started = time.perf_counter()
            with st.spinner("Đang tìm và đối chiếu nguồn… lần đầu cần nạp mô hình, có thể mất 20–40 giây."):
                response = run_source(text) if mode == SOURCE_MODE else run_cached(text)
            st.session_state["result"] = {"mode": mode, "claim": text, "response": response,
                                          "seconds": time.perf_counter() - started}
            st.query_params["q"] = text
            # URL ?q= do app tự ghi (để chia sẻ link) – đánh dấu đã xử lý, nếu không lần bấm sau
            # khối deep-link sẽ ghi đè phát biểu mới bằng phát biểu cũ trong URL.
            st.session_state["_deeplink_done"] = True
        except (RuntimeError, ValueError) as error:
            st.session_state.pop("result", None)
            st.error(f"Không kiểm tra được: {error}", icon=":material/error:")

result = st.session_state.get("result")
if result and result["mode"] == mode:
    if mode == SOURCE_MODE:
        show_source_result(result["claim"], result["response"], result["seconds"])
    else:
        show_legacy_result(result["claim"], result["response"], result["seconds"])

html('<div class="footnote">Kết quả chỉ để tham khảo, không thay thế việc đọc nguồn gốc. "Không tìm thấy nguồn" nghĩa là '
     'hệ thống không tìm được nguồn trong phạm vi tra cứu, không chứng minh phát biểu là sai. '
     'Pipeline và kết quả được cache; sửa config hoặc model cần chọn Clear cache rồi chạy lại.</div>')
