# W4-01 — Streamlit: verdict, evidence, nguồn và cache

Chạy: `py -3.13 -m streamlit run app.py`.

> **Giao diện Gradio (2026-10-11, khuyên dùng để demo):** `py -3.13 app_gradio.py` (thêm `--share` để có link công khai tạm thời). Cùng `src/system_builder.py` nên verdict giống hệt Streamlit; trình bày dạng thẻ: verdict màu theo nhãn + thanh điểm, trích dẫn có nhãn local/web, tab "Tất cả bằng chứng" (bài bị neo thời gian loại nằm trong mục thu gọn), tab chi tiết kỹ thuật, 6 ví dụ bấm là chạy. Nội dung lấy từ nguồn được escape HTML.

Giao diện dựng hệ thống qua `src/system_builder.py`, cùng cách dựng với CLI `scripts/run_web_fact_check.py`, nên hai đầu vào cho kết quả giống nhau. Thanh bên có hai chế độ:

- **Kho local (đã đánh giá).** Đúng pipeline đã đo trên test (Macro-F1 72,31%): BM25 → PhoBERT RT-V2 ensemble → luật cặp-tối-thiểu. Guard tắt.
- **Local + web.** Thêm Tavily qua allowlist, RRF, neo thời gian (có thể đặt ngày tham chiếu) và gộp URL. Guard bật. Chế độ này chưa có số đo định lượng. Thiếu `TAVILY_API_KEY` (trong `.env`) thì chạy chỉ với kho local và hiện cảnh báo.

Mỗi lượt hiển thị:

- verdict (màu theo nhãn) và điểm mô hình, kèm lưu ý điểm không phải xác suất đúng;
- giải thích;
- lý do khi luật cặp-tối-thiểu, guard hoặc neo thời gian can thiệp;
- nhánh verifier: các citation được dùng, mỗi cái có nhãn 🗂️ local / 🌐 web, nguồn, ngày đăng và nút mở URL;
- nhánh retrieval: toàn bộ candidate top-k;
- danh sách bằng chứng bị neo thời gian loại;
- chi tiết kỹ thuật (cấu hình đang chạy).

Hộp "Ví dụ nhanh" lấy 6 ca trong `src/demo_cases.py`. Ba ca đầu cùng một câu nguồn: nguyên văn cho SUPPORTED, đổi số hoặc thêm phủ định cho REFUTED.

Cache: `@st.cache_resource` giữ model và pipeline theo (chế độ, ngày tham chiếu); `@st.cache_data` giữ JSON response theo (chế độ, claim), hết hạn sau 15 phút để kết quả web không quá cũ. Không cache API key. Sau khi đổi config hoặc model, dùng menu ⋮ → Clear cache.

Nếu Windows Application Control chặn torch, giao diện chạy chế độ demo rule-based và cảnh báo rõ rằng kết quả không dùng để đánh giá mô hình.
