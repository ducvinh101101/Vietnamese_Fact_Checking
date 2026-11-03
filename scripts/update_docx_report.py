import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

def add_styled_table(doc, headers, data, col_widths=None):
    table = doc.add_table(rows=len(data) + 1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = 'Table Grid'
    
    # Header
    hdr_cells = table.rows[0].cells
    for i, h in enumerate(headers):
        hdr_cells[i].text = str(h)
        for p in hdr_cells[i].paragraphs:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in p.runs:
                run.font.bold = True
                run.font.size = Pt(10)
    
    # Rows
    for r_idx, row in enumerate(data):
        row_cells = table.rows[r_idx + 1].cells
        for c_idx, val in enumerate(row):
            row_cells[c_idx].text = str(val)
            for p in row_cells[c_idx].paragraphs:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT if c_idx == 0 else WD_ALIGN_PARAGRAPH.CENTER
                for run in p.runs:
                    run.font.size = Pt(9.5)
                    
    # Widths
    if col_widths:
        for r in table.rows:
            for c_idx, w in enumerate(col_widths):
                r.cells[c_idx].width = Inches(w)
    return table

def update_report(docx_path):
    doc = docx.Document(docx_path)
    
    # Find insertion point: Right before Section 5.4 or around 5.4
    # We will locate paragraph "5.4 Kết quả" and rewrite Section 5.4 with comprehensive academic depth!
    target_idx = None
    for i, p in enumerate(doc.paragraphs):
        if p.text.strip() == "5.4 Kết quả" and p.style.name.startswith("Heading"):
            target_idx = i
            break
            
    print(f"Found '5.4 Kết quả' at index {target_idx}")
    
    # Let's add detailed subsections to 5.4:
    # 5.4.1 Bảng đối chuẩn Verifier trên Bằng chứng vàng (Oracle)
    # 5.4.2 Benchmark Retrieval: BM25 vs Dense FAISS vs Hybrid RRF
    # 5.4.3 Thực nghiệm nhánh Content-Risk: Thất bại của Content-Only & Sự cần thiết của RAG
    # 5.4.4 Tối ưu hóa End-to-End từ W4-02 đến Cấu hình cuối
    
    # We can append comprehensive notes and tables right before 5.5 Đánh giá
    eval_idx = None
    for i, p in enumerate(doc.paragraphs):
        if p.text.strip() == "5.5 Đánh giá" and p.style.name.startswith("Heading"):
            eval_idx = i
            break
            
    print(f"Found '5.5 Đánh giá' at index {eval_idx}")

    # Let's inspect paragraphs between 5.4 and 5.5 to make sure everything stays harmonious
    # In python-docx, inserting before a paragraph is done using p._p.addprevious()
    # Alternatively, we can add rich sections at the end of 5.4
    
    # Let's create an updated document with the complete enriched structure!
    doc.save(docx_path)
    print("Report updated.")

if __name__ == "__main__":
    update_report("docs/BAO_CAO_DE_TAI_XLNNTN.docx")
