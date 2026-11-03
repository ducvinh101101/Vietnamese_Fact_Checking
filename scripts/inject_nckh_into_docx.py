import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

def insert_paragraph_before(p, text, style=None, bold=False, italic=False, size=Pt(11)):
    new_p = p.insert_paragraph_before(text, style=style)
    if style is None or style == 'Normal':
        for r in new_p.runs:
            r.font.size = size
            r.font.bold = bold
            r.font.italic = italic
    return new_p

def insert_table_before(p, headers, data, col_widths=None):
    # In docx, insert table before paragraph using xml
    table = p._element.xpath('ancestor::w:body')[0]
    tbl = p._parent.add_table(rows=len(data) + 1, cols=len(headers))
    tbl.style = 'Table Grid'
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    
    # Header
    for c_idx, h in enumerate(headers):
        cell = tbl.cell(0, c_idx)
        cell.text = str(h)
        for cp in cell.paragraphs:
            cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for r in cp.runs:
                r.font.bold = True
                r.font.size = Pt(10)
                
    # Data
    for r_idx, row in enumerate(data):
        for c_idx, val in enumerate(row):
            cell = tbl.cell(r_idx + 1, c_idx)
            cell.text = str(val)
            for cp in cell.paragraphs:
                cp.alignment = WD_ALIGN_PARAGRAPH.LEFT if c_idx == 0 else WD_ALIGN_PARAGRAPH.CENTER
                for r in cp.runs:
                    r.font.size = Pt(9.5)
                    
    if col_widths:
        for r in tbl.rows:
            for c_idx, w in enumerate(col_widths):
                r.cells[c_idx].width = Inches(w)
                
    # Move the tbl before p
    p._element.addprevious(tbl._element)
    return tbl

def update_docx(docx_path):
    doc = docx.Document('docs/BAO_CAO_DE_TAI_XLNNTN.docx.bak')
    
    # Find paragraph "5.4 Kết quả"
    p_kết_quả = None
    for p in doc.paragraphs:
        if p.text.strip() == "5.4 Kết quả" and p.style.name.startswith("Heading"):
            p_kết_quả = p
            break
            
    # Find paragraph "5.5 Đánh giá"
    p_đánh_giá = None
    for p in doc.paragraphs:
        if p.text.strip() == "5.5 Đánh giá" and p.style.name.startswith("Heading"):
            p_đánh_giá = p
            break

    # We will insert new subsections right before 5.5 Đánh giá
    insert_paragraph_before(p_đánh_giá, "5.4.1 Bảng đối chuẩn Verifier trên Bằng chứng vàng (Oracle)", style='Heading 3')
    insert_paragraph_before(p_đánh_giá, 
        "Để xác định trần năng lực lý thuyết của các mô hình phân loại quan hệ thực tế (claim–evidence), "
        "thực nghiệm so sánh được tiến hành trên tập bằng chứng vàng (Gold Evidence) của ViFactCheck. "
        "Bảng dưới đây tổng hợp kết quả của các mô hình baseline và mô hình đề xuất so với bài báo gốc [5]:")
    
    h_oracle = ["Mô hình / Cấu hình", "Tập dữ liệu", "Dev Macro-F1", "Test Macro-F1", "F1 REFUTED", "Quyết định & Ghi chú"]
    d_oracle = [
        ["E1 (TF-IDF + Linear SVM)", "ViFactCheck Gold", "—", "40,15%", "34,10%", "Baseline phân loại từ khóa bề mặt."],
        ["ViFactCheck PhoBERT-base [5]", "ViFactCheck Gold", "—", "77,76%", "—", "Số báo AAAI 2025 (phân chia ngẫu nhiên)."],
        ["E2 (PhoBERT-base Đề tài)", "ViFactCheck Gold", "85,01%", "81,07%", "77,90%", "Mô hình tốt nhất đề tài (+3,31 điểm vs [5])."],
        ["E7 (PhoBERT batch 16 var)", "ViFactCheck Gold", "84,18%", "80,25%", "76,80%", "Loại: Dev thấp hơn E2, giữ E2."]
    ]
    insert_table_before(p_đánh_giá, h_oracle, d_oracle, [2.2, 1.2, 1.0, 1.0, 1.0, 2.0])
    
    insert_paragraph_before(p_đánh_giá, "")
    insert_paragraph_before(p_đánh_giá, "5.4.2 Benchmark Retrieval: So sánh BM25, Dense Retrieval và Hybrid RRF", style='Heading 3')
    insert_paragraph_before(p_đánh_giá, 
        "Khả năng tìm đúng ngữ cảnh là điều kiện tiên quyết của hệ thống RAG. "
        "Ba kiến trúc truy xuất được đánh giá trên 1.076 truy vấn test từ kho 5.845 đoạn văn:")
    
    h_retrieval = ["Retriever", "Cấu hình / Không gian vector", "Recall@3", "Recall@5", "MRR@5", "Độ trễ p95", "Quyết định"]
    d_retrieval = [
        ["BM25 Passage (E3)", "Rank-BM25 (k1=1,5, b=0,75)", "98,14%", "98,98%", "0,9671", "81,20 ms", "Chọn làm Retriever chính."],
        ["Dense Retrieval (E4)", "Multilingual E5-small + FAISS", "92,10%*", "95,65%*", "0,9125*", "33,72 ms", "Loại: Kém BM25 2,87 điểm Recall."],
        ["Hybrid RRF (E5)", "BM25 + Dense RRF (k=60)", "96,20%*", "98,43%*", "0,9547*", "115,40 ms", "Loại: Không vượt được BM25 thuần."]
    ]
    insert_table_before(p_đánh_giá, h_retrieval, d_retrieval, [1.8, 2.2, 0.9, 0.9, 0.9, 1.0, 1.8])
    insert_paragraph_before(p_đánh_giá, "(* Số đo trên tập dev 1.080 claim. BM25 chứng minh ưu thế vượt trội về độ chính xác từ khóa và tên riêng trên báo chí tiếng Việt.)", italic=True)

    insert_paragraph_before(p_đánh_giá, "")
    insert_paragraph_before(p_đánh_giá, "5.4.3 Thực nghiệm nhánh Content-Risk: Bằng chứng về sự thất bại của Content-Only", style='Heading 3')
    insert_paragraph_before(p_đánh_giá, 
        "Một câu hỏi nghiên cứu quan trọng: Liệu có thể phát hiện tin giả chỉ dựa vào văn phong và nội dung bài viết (Content-only)? "
        "Thực nghiệm E9 và E10 được tiến hành trên tập VFND (221 bài báo) với giao thức Nested Stratified GroupKFold theo tên miền:")
    
    h_content = ["Mô hình", "Đầu vào", "Macro-F1 OOF", "ROC-AUC", "Recall FAKE", "F1 FAKE", "Kết luận"]
    d_content = [
        ["E9 (TF-IDF + LinearSVC)", "[TITLE] + [BODY]", "77,27%", "88,21%", "60,82%", "71,52%", "Thắng nhờ đặc trưng từ khóa bề mặt của domain."],
        ["E10 (PhoBERT-base)", "[TITLE] + [BODY]", "48,59%", "70,20%", "19,58%", "28,36%", "Sụp đổ (-28,68 điểm): Bỏ lọt >80% tin giả."]
    ]
    insert_table_before(p_đánh_giá, h_content, d_content, [1.8, 1.4, 1.1, 1.0, 1.0, 1.0, 2.2])
    insert_paragraph_before(p_đánh_giá, 
        "Kết quả khẳng định tính tất yếu của kiến trúc RAG: Mô hình học sâu hiểu ngữ nghĩa không thể phân biệt tin thật và tin giả "
        "nếu chỉ đọc độc lập bài viết; bắt buộc phải có cơ chế đối chiếu với bằng chứng sự thật bên ngoài.", bold=True)
    insert_paragraph_before(p_đánh_giá, "")

    doc.save(docx_path)
    print("Successfully injected all NCKH sections into docx!")

if __name__ == '__main__':
    update_docx('docs/BAO_CAO_DE_TAI_XLNNTN.docx')
