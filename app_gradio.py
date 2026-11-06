"""Giao diện Gradio kiểm chứng thông tin tiếng Việt.

    py -3.13 app_gradio.py                    # mở http://127.0.0.1:7860
    py -3.13 app_gradio.py --share            # tạo link công khai tạm thời để demo

Dùng CHUNG src/system_builder.py với app.py (Streamlit) và CLI, nên verdict giống hệt.
Hai chế độ: "Kho local" (cấu hình đã đo trên test) và "Local + web" (Tavily + neo thời gian).
"""

from __future__ import annotations

import argparse
import html
import os
from datetime import date
from functools import lru_cache
from pathlib import Path

import gradio as gr

from src.demo_cases import DEMO_CASES
from src.runtime_config import ConfigValidationError, load_runtime_config
from src.system_builder import FactCheckSystem, SystemOptions, build_system, load_dotenv

ROOT = Path(__file__).parent
os.environ.setdefault("HF_HOME", str(ROOT / ".cache/huggingface"))
load_dotenv(ROOT / ".env")

MODES = {"Kho local (đã đánh giá)": "local", "Local + web (Tavily)": "hybrid"}
MODELS = {
    "PhoBERT Đề tài (Cục bộ CPU, < 0.3s)": "phobert",
    "LLM Gemma 4 (Google Cloud, Suy luận sâu)": "gemma",
}
VERDICTS = {
    "SUPPORTED": ("supported", "✓", "ĐƯỢC ỦNG HỘ", "Bằng chứng truy xuất xác nhận phát biểu."),
    "REFUTED": ("refuted", "✕", "BỊ BÁC BỎ", "Bằng chứng truy xuất mâu thuẫn với phát biểu."),
    "NOT_ENOUGH_INFO": ("nei", "?", "CHƯA ĐỦ THÔNG TIN", "Chưa tìm được bằng chứng đủ để kết luận."),
}

CSS = """
.gradio-container {max-width: 1180px !important; margin: auto;}
#hero {padding: 22px 26px; border-radius: 16px; margin-bottom: 6px;
       background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 55%, #0ea5e9 100%); color: #fff;}
#hero h1 {margin: 0 0 4px; font-size: 1.7rem; color: #fff;}
#hero p {margin: 0; opacity: .92;}
#hero, #hero * {color: #fff !important;}
#hero .chips {margin-top: 12px; display: flex; gap: 8px; flex-wrap: wrap;}
#hero .chip {background: rgba(255,255,255,.16); border: 1px solid rgba(255,255,255,.28);
             padding: 3px 10px; border-radius: 999px; font-size: .82rem;}
.disclaimer {font-size: .85rem; padding: 8px 12px; border-radius: 10px;
             background: rgba(234,179,8,.12); border: 1px solid rgba(234,179,8,.35);}
.verdict {display: flex; gap: 16px; align-items: center; padding: 18px 20px; border-radius: 14px;
          border: 1px solid; margin-bottom: 10px;}
.verdict .icon {width: 54px; height: 54px; border-radius: 50%; display: grid; place-items: center;
                font-size: 1.7rem; font-weight: 700; color: #fff; flex-shrink: 0;}
.verdict .label {font-size: 1.35rem; font-weight: 700; letter-spacing: .02em;}
.verdict .meta {opacity: .8; font-size: .9rem; margin-top: 2px;}
.verdict .score {margin-left: auto; text-align: right; min-width: 140px;}
.verdict .bar {height: 8px; border-radius: 99px; background: rgba(127,127,127,.25); overflow: hidden; margin-top: 6px;}
.verdict .bar > span {display: block; height: 100%;}
.supported {background: rgba(22,163,74,.10); border-color: rgba(22,163,74,.45);}
.supported .icon, .supported .bar > span {background: #16a34a;}
.refuted {background: rgba(220,38,38,.10); border-color: rgba(220,38,38,.45);}
.refuted .icon, .refuted .bar > span {background: #dc2626;}
.nei {background: rgba(100,116,139,.12); border-color: rgba(100,116,139,.45);}
.nei .icon, .nei .bar > span {background: #64748b;}
.note {padding: 9px 12px; border-radius: 10px; margin: 6px 0; font-size: .9rem;
       background: rgba(37,99,235,.08); border-left: 4px solid #2563eb;}
.note.warn {background: rgba(234,179,8,.12); border-left-color: #ca8a04;}
.ev {border: 1px solid rgba(127,127,127,.28); border-radius: 12px; padding: 12px 14px; margin: 8px 0;}
.ev.cited {border-color: #2563eb; box-shadow: 0 0 0 1px rgba(37,99,235,.25);}
.ev .head {display: flex; gap: 8px; flex-wrap: wrap; align-items: center; font-size: .82rem; margin-bottom: 6px;}
.badge {padding: 2px 8px; border-radius: 999px; font-weight: 600; font-size: .75rem;
        background: rgba(127,127,127,.16);}
.badge.web {background: rgba(14,165,233,.18); color: #0369a1;}
.badge.local {background: rgba(99,102,241,.16); color: #4338ca;}
.badge.cite {background: #2563eb; color: #fff;}
.ev .body {line-height: 1.55;}
.ev .foot {font-size: .8rem; opacity: .75; margin-top: 6px;}
.ev a {font-weight: 600;}
.empty {opacity: .7; font-style: italic; padding: 8px 2px;}
"""

HERO = """
<div id="hero">
  <h1>🔎 Kiểm chứng thông tin tiếng Việt</h1>
  <p>Nhập một phát biểu — hệ thống tìm bằng chứng, đối chiếu bằng PhoBERT hoặc LLM Gemma 4 và trả kết luận kèm nguồn trích dẫn.</p>
  <div class="chips">
    <span class="chip">BM25 + web allowlist</span><span class="chip">PhoBERT RT-V2 (ensemble)</span>
    <span class="chip">Tùy chọn LLM Gemma 4</span><span class="chip">Test ViFactCheck: Macro-F1 72,3%</span>
  </div>
</div>
<div class="disclaimer">⚠️ Bản thử nghiệm nghiên cứu, chưa xác nhận 80% ngoài thực tế. Điểm mô hình không phải
xác suất thông tin đúng — luôn mở nguồn gốc để kiểm tra.</div>
"""


@lru_cache(maxsize=8)
def get_system(mode: str, engine: str, as_of: date | None) -> FactCheckSystem:
    config = load_runtime_config(ROOT / "configs" / "config.yaml")
    return build_system(SystemOptions(mode=mode, engine=engine, as_of=as_of), config=config, root=ROOT)


def _e(value: object) -> str:
    return html.escape("" if value is None else str(value))


def render_verdict(verdict: dict, mode: str, engine: str) -> str:
    css, icon, title, meaning = VERDICTS.get(str(verdict["label"]), VERDICTS["NOT_ENOUGH_INFO"])
    score = max(0.0, min(1.0, float(verdict["confidence"])))
    mode_name = next(name for name, value in MODES.items() if value == mode)
    engine_name = next(name for name, value in MODELS.items() if value == engine)
    return f"""
<div class="verdict {css}">
  <div class="icon">{icon}</div>
  <div><div class="label">{title}</div><div class="meta">{_e(verdict['label'])} · {_e(meaning)}</div>
       <div class="meta">Nguồn: {_e(mode_name)} · <b>Mô hình: {_e(engine_name)}</b></div></div>
  <div class="score"><div class="meta">Độ tự tin</div><div class="label">{score:.2f}</div>
       <div class="bar"><span style="width:{100 * score:.0f}%"></span></div></div>
</div>
<div class="note">{_e(verdict['explanation'])}</div>"""


def render_notes(diagnostics: dict, system: FactCheckSystem) -> str:
    notes = []
    if system.fallback_reason:
        notes.append(("warn", "PhoBERT bị Windows Application Control chặn — đang chạy chế độ demo rule-based. "
                               "Kết quả chỉ để kiểm tra luồng, không đánh giá chất lượng mô hình."))
    if system.mode == "hybrid" and system.web_status:
        notes.append(("" if system.settings.get("web") else "warn", system.web_status))
    if diagnostics.get("web_error"):
        notes.append(("warn", f"Nhánh web lỗi, đã lùi về kho local: {diagnostics['web_error']}"))
    if diagnostics.get("web_search_error"):
        notes.append(("warn", f"Tìm kiếm web: {diagnostics['web_search_error']}"))
    if diagnostics.get("web_search_status") == "no_eligible_passages":
        notes.append(("warn", "Chưa lấy được đoạn web phù hợp. Xem truy vấn và lý do từng bài bị loại ở Chi tiết kỹ thuật."))
    if diagnostics.get("minimal_pair_reason"):
        notes.append(("", f"Luật cặp-tối-thiểu đã điều chỉnh verdict ({diagnostics['minimal_pair_reason']}): phát biểu "
                          "gần trùng một câu trong nguồn nhưng khác số/chiều/phủ định, hoặc trùng nguyên văn."))
    if diagnostics.get("guard_reason"):
        notes.append(("", f"Guard đã hạ verdict xuống NEI: {diagnostics['guard_reason']}."))
    elif diagnostics.get('outcome_stage') == 'verifier_abstained':
        notes.append(('', 'Đã có đoạn bằng chứng đưa vào mô hình, nhưng mô hình chưa xác định được quan hệ '
                          'ủng hộ hoặc bác bỏ. Xem các đoạn truy xuất và kết quả mô hình trong Chi tiết kỹ thuật.'))
    gate = diagnostics.get("temporal_gate")
    if gate:
        notes.append(("", f"Lọc theo thời gian ({gate['recency_class']}): ngày neo {gate.get('anchor_date')}; "
                          f"nhận bài từ {gate['cutoff']} đến {gate.get('end_date')}. "
                          f"Giữ {gate['kept']}; loại {gate['dropped_stale']} quá cũ, {gate['dropped_undated']} "
                          f"không rõ ngày, {gate['dropped_future']} sau ngày tham chiếu."))
    return "".join(f'<div class="note {kind}">{_e(text)}</div>' for kind, text in notes)


def render_evidence(items: list[dict], cited_ids: set[str], empty: str) -> str:
    if not items:
        return f'<div class="empty">{_e(empty)}</div>'
    cards = []
    for item in items:
        origin = item.get("origin", "local")
        cited = item["passage_id"] in cited_ids
        link = f'<a href="{_e(item["url"])}" target="_blank" rel="noopener">Mở nguồn ↗</a>' if item.get("url") else ""
        cards.append(f"""
<div class="ev {'cited' if cited else ''}">
  <div class="head">
    <span class="badge {origin}">{'🌐 web' if origin == 'web' else '🗂 local'}</span>
    {'<span class="badge cite">Được trích dẫn</span>' if cited else ''}
    <b>{_e(item.get('source'))}</b>{f"<span>· {_e(item['domain'])}</span>" if item.get('domain') else ''}
    <span>· điểm {float(item['score']):.2f}</span>
  </div>
  <div class="body">{_e(item['content'])}</div>
  <div class="foot">Xuất bản: {_e((item.get('published_at') or 'không rõ')[:10])} · <code>{_e(item['passage_id'])}</code> · {link}</div>
</div>""")
    return "".join(cards)


def check(claim: str, mode_label: str, model_label: str, use_date: bool, as_of_text: str):
    claim = (claim or "").strip()
    if not claim:
        gr.Warning("Vui lòng nhập phát biểu cần kiểm chứng.")
        return "", "", "", "", {}
    mode = MODES[mode_label]
    engine = MODELS[model_label]
    as_of = None
    if mode == "hybrid" and use_date and as_of_text:
        try:
            as_of = date.fromisoformat(as_of_text.strip())
        except ValueError:
            gr.Warning("Ngày tham chiếu phải có dạng YYYY-MM-DD.")
            return "", "", "", "", {}
    try:
        system = get_system(mode, engine, as_of)
        response = system.check(claim)
    except (RuntimeError, ValueError, ConfigValidationError) as error:
        return f'<div class="note warn">{_e(error)}</div>', "", "", "", {}
    diagnostics = response.get("diagnostics", {})
    cited_ids = {str(item["passage_id"]) for item in response["citations"]}
    gate = diagnostics.get("temporal_gate") or {}
    dropped = "".join(
        f'<div class="ev"><div class="head"><span class="badge">{_e(row["reason"])}</span>'
        f'<span class="badge {row["origin"]}">{_e(row["origin"])}</span><b>{_e(row["source"])}</b>'
        f'<span>· {_e((row["published_at"] or "không rõ")[:10])}</span></div>'
        f'<div class="foot"><a href="{_e(row["url"])}" target="_blank" rel="noopener">{_e(row["url"])}</a></div></div>'
        for row in {(r["reason"], r["url"]): r for r in gate.get("dropped", [])}.values()   # gộp đoạn cùng bài
    )
    retrieved = render_evidence(response["retrieval"]["evidence"], cited_ids, "Không truy xuất được đoạn nào.")
    if dropped:
        retrieved += ("<details><summary><b>Bài bị neo thời gian loại</b> (quá cũ / không rõ ngày / sau ngày tham chiếu)"
                      f"</summary>{dropped}</details>")
    return (
        render_verdict(response["verdict"], mode, engine) + render_notes(diagnostics, system),
        render_evidence(response["citations"], cited_ids, "Không có đoạn nào được dùng để xác nhận hoặc bác bỏ."),
        retrieved,
        f"### Tìm thấy {response['retrieval']['retrieved_count']} đoạn · trích dẫn {len(response['citations'])}",
        {**diagnostics, "schema_version": response.get("schema_version"), "model_engine": engine},
    )


def build_ui() -> gr.Blocks:
    theme = gr.themes.Soft(primary_hue="blue", secondary_hue="sky", neutral_hue="slate",
                           font=[gr.themes.GoogleFont("Be Vietnam Pro"), "system-ui", "sans-serif"])
    with gr.Blocks(theme=theme, css=CSS, title="Kiểm chứng thông tin tiếng Việt") as demo:
        gr.HTML(HERO)
        with gr.Row(equal_height=False):
            with gr.Column(scale=5):
                claim = gr.Textbox(label="Phát biểu cần kiểm chứng", lines=4, max_length=2000,
                                   placeholder="Ví dụ: Tổng thống Brazil Lula hoãn chuyến thăm 6 ngày tới Trung Quốc…")
                with gr.Row():
                    submit = gr.Button("Kiểm chứng", variant="primary", scale=3)
                    clear = gr.ClearButton(value="Xóa", scale=1)
            with gr.Column(scale=3):
                model_choice = gr.Radio(
                    list(MODELS),
                    value=next(iter(MODELS)),
                    label="Mô hình Phán quyết (Verifier)",
                    info="PhoBERT chạy offline nhanh tức thì (<0.3s); Gemma 4 là LLM suy luận logic sâu.",
                )
                mode = gr.Radio(
                    list(MODES),
                    value=next(name for name, value in MODES.items() if value == 'hybrid'),
                    label="Nguồn bằng chứng",
                    info="Kho local là cấu hình đã đo; web dùng cho claim thời sự (cần TAVILY_API_KEY).",
                )
                use_date = gr.Checkbox(label="Đặt ngày tham chiếu (chế độ web)", value=False)
                as_of = gr.Textbox(label="Ngày tham chiếu (YYYY-MM-DD)", value=date.today().isoformat(), visible=False)
        gr.Examples(examples=[[case["claim"], next(k for k, v in MODES.items() if v == case["mode"])]
                              for case in DEMO_CASES],
                    inputs=[claim, mode], label="Ví dụ (D1–D3: cùng một câu nguồn — nguyên văn, đổi số, thêm phủ định)")
        verdict = gr.HTML()
        with gr.Tabs():
            with gr.Tab("Trích dẫn dùng để kết luận"):
                citations = gr.HTML()
            with gr.Tab("Tất cả bằng chứng truy xuất"):
                summary = gr.Markdown()
                retrieved = gr.HTML()
            with gr.Tab("Chi tiết kỹ thuật"):
                details = gr.JSON(label="Cấu hình đang chạy")
        gr.Markdown("Đồ án XLNNTN · dữ liệu ViFactCheck · kết quả là hỗ trợ tham khảo, không thay thế kiểm chứng của con người.")

        use_date.change(lambda on: gr.update(visible=on), use_date, as_of)
        outputs = [verdict, citations, retrieved, summary, details]
        inputs = [claim, mode, model_choice, use_date, as_of]
        submit.click(check, inputs, outputs)
        claim.submit(check, inputs, outputs)
        clear.add([claim, *outputs])
    return demo


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--share", action="store_true", help="Tạo link công khai tạm thời (gradio.live)")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--no-browser", action="store_true", help="Không tự mở tab trình duyệt")
    args = parser.parse_args()
    build_ui().queue(default_concurrency_limit=1).launch(server_port=args.port, share=args.share,
                                                       inbrowser=not args.no_browser)
