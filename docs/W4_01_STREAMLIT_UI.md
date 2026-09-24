# W4-01 — Streamlit: verdict, evidence, nguồn và cache

Giao diện dùng `FactCheckingPipeline.run_json()` nên chỉ hiển thị citation thuộc
evidence của chính lượt retrieval. UI tách rõ nhánh verifier (verdict, giải thích,
citation được dùng) và nhánh retrieval (toàn bộ candidate top-k). Mỗi source có
passage ID, score, source/domain/type, thời điểm retrieval/publication nếu biết và
nút mở URL.

`@st.cache_resource` cache model/pipeline; `@st.cache_data` cache JSON response
theo claim. Không cache API key hay thay đổi logic verifier. Khi đổi config/model,
dùng **Clear cache** của Streamlit trước lượt chạy mới.

Chạy `streamlit run app.py`. UI không khẳng định score là xác suất sự thật và
không gọi web retrieval mặc định; web/hybrid integration cần đánh giá riêng.
