import os
import sys
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

def create_deck(output_pptx_path):
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    # Color Palette - High Contrast for Projectors
    C_DARK_BG = RGBColor(15, 23, 42)       # #0f172a deep navy
    C_LIGHT_BG = RGBColor(248, 250, 252)   # #f8fafc clean off-white
    C_WHITE = RGBColor(255, 255, 255)
    C_TEXT_MAIN = RGBColor(15, 23, 42)     # #0f172a deep slate
    C_TEXT_MUTED = RGBColor(71, 85, 105)   # #475569 slate muted
    C_CARD_BG = RGBColor(255, 255, 255)    # pure white card
    C_CARD_ALT = RGBColor(241, 245, 249)   # #f1f5f9 light gray panel
    C_BORDER = RGBColor(203, 213, 225)     # #cbd5e1 visible border
    C_ACCENT_BLUE = RGBColor(2, 132, 199)  # #0284c7 cyan/blue
    C_ACCENT_AMBER = RGBColor(217, 119, 6) # #d97706 amber
    C_ACCENT_GREEN = RGBColor(13, 148, 136)# #0d9488 teal/green
    C_ACCENT_ROSE = RGBColor(225, 29, 72)  # #e11d48 crimson rose
    C_TH_BG = RGBColor(30, 41, 59)         # #1e293b dark header

    TOTAL_SLIDES = 11

    def add_bg(slide, color):
        shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
        shape.fill.solid()
        shape.fill.fore_color.rgb = color
        shape.line.fill.background()
        return shape

    def add_header(slide, title, category="MÔN XỬ LÝ NGÔN NGỮ TỰ NHIÊN · BÁO CÁO ĐỀ TÀI NCKH", slide_num=None):
        add_bg(slide, C_LIGHT_BG)
        # Category tag
        cat_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.35), Inches(11.0), Inches(0.35))
        tf_cat = cat_box.text_frame
        tf_cat.word_wrap = True
        tf_cat.margin_left = tf_cat.margin_right = tf_cat.margin_top = tf_cat.margin_bottom = 0
        p_cat = tf_cat.paragraphs[0]
        p_cat.text = category.upper()
        p_cat.font.size = Pt(13)
        p_cat.font.bold = True
        p_cat.font.color.rgb = C_ACCENT_AMBER

        # Main Title (26pt Bold, single line)
        title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.68), Inches(11.0), Inches(0.65))
        tf_title = title_box.text_frame
        tf_title.word_wrap = True
        tf_title.margin_left = tf_title.margin_right = tf_title.margin_top = tf_title.margin_bottom = 0
        p_title = tf_title.paragraphs[0]
        p_title.text = title
        p_title.font.size = Pt(26)
        p_title.font.bold = True
        p_title.font.color.rgb = C_TEXT_MAIN

        # Slide Number
        if slide_num:
            num_box = slide.shapes.add_textbox(Inches(11.2), Inches(0.4), Inches(1.5), Inches(0.4))
            tf_num = num_box.text_frame
            tf_num.word_wrap = True
            p_num = tf_num.paragraphs[0]
            p_num.text = f"{slide_num:02d} / {TOTAL_SLIDES:02d}"
            p_num.alignment = PP_ALIGN.RIGHT
            p_num.font.size = Pt(14)
            p_num.font.bold = True
            p_num.font.color.rgb = C_TEXT_MUTED

    def add_card(slide, left, top, width, height, bg_color=C_CARD_BG, border_color=C_BORDER):
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height))
        card.fill.solid()
        card.fill.fore_color.rgb = bg_color
        if border_color:
            card.line.color.rgb = border_color
            card.line.width = Pt(1.5)
        else:
            card.line.fill.background()
        return card

    def format_table(table, col_widths, headers, data, font_size=15):
        for i, w in enumerate(col_widths):
            table.columns[i].width = Inches(w)
        # Headers
        for j, h in enumerate(headers):
            cell = table.cell(0, j)
            cell.margin_top = cell.margin_bottom = Inches(0.06)
            cell.margin_left = cell.margin_right = Inches(0.08)
            cell.fill.solid()
            cell.fill.fore_color.rgb = C_TH_BG
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            p = cell.text_frame.paragraphs[0]
            p.text = str(h)
            p.font.size = Pt(font_size + 0.5)
            p.font.bold = True
            p.font.color.rgb = C_WHITE
            p.alignment = PP_ALIGN.CENTER
        # Rows
        for r_idx, row in enumerate(data):
            row_bg = C_WHITE if r_idx % 2 == 0 else C_CARD_ALT
            for c_idx, val in enumerate(row):
                cell = table.cell(r_idx + 1, c_idx)
                cell.margin_top = cell.margin_bottom = Inches(0.05)
                cell.margin_left = cell.margin_right = Inches(0.08)
                cell.fill.solid()
                cell.fill.fore_color.rgb = row_bg
                cell.vertical_anchor = MSO_ANCHOR.MIDDLE
                p = cell.text_frame.paragraphs[0]
                p.text = str(val)
                p.font.size = Pt(font_size)
                p.font.color.rgb = C_TEXT_MAIN
                if c_idx == 0:
                    p.alignment = PP_ALIGN.LEFT
                    p.font.bold = True
                else:
                    p.alignment = PP_ALIGN.CENTER

    # =========================================================================
    # SLIDE 1: Trang Tiêu đề (Dark Navy Sang trọng)
    # =========================================================================
    s1 = prs.slides.add_slide(blank_layout)
    add_bg(s1, C_DARK_BG)
    
    tb1 = s1.shapes.add_textbox(Inches(1.0), Inches(1.5), Inches(11.3), Inches(4.8))
    tf1 = tb1.text_frame; tf1.word_wrap = True
    
    p = tf1.paragraphs[0]
    p.text = "MÔN XỬ LÝ NGÔN NGỮ TỰ NHIÊN · BÁO CÁO ĐỀ TÀI NCKH"
    p.font.size = Pt(16); p.font.bold = True; p.font.color.rgb = RGBColor(245, 158, 11)
    p.space_after = Pt(24)

    p = tf1.add_paragraph()
    p.text = "Hệ thống kiểm chứng thông tin tiếng Việt\ndựa trên truy xuất bằng chứng (RAG)"
    p.font.size = Pt(38); p.font.bold = True; p.font.color.rgb = C_WHITE
    p.space_after = Pt(24)

    p = tf1.add_paragraph()
    p.text = "So sánh toàn diện: Truy xuất BM25, Mô hình PhoBERT tinh chỉnh (Ensemble 3 góc nhìn),\nCơ chế Neo thời gian cho tin mới, và Stress-test đối đầu LLM Gemma 4"
    p.font.size = Pt(19); p.font.color.rgb = RGBColor(203, 213, 225)
    p.space_after = Pt(36)

    p = tf1.add_paragraph()
    p.text = "Sinh viên thực hiện: Vinh & Quang   |   Thời gian: Tháng 10/2026"
    p.font.size = Pt(16); p.font.bold = True; p.font.color.rgb = RGBColor(148, 163, 184)

    # =========================================================================
    # SLIDE 2: Đặt vấn đề & Thí nghiệm Tiền trạm (Tại sao Content-Only thất bại?)
    # =========================================================================
    s2 = prs.slides.add_slide(blank_layout)
    add_header(s2, "Đặt vấn đề & Thí nghiệm Tiền trạm: Thất bại của Content-Only", slide_num=2)

    # Left: The problem & Solution
    add_card(s2, 0.8, 1.6, 5.7, 5.3)
    tb_l = s2.shapes.add_textbox(Inches(1.1), Inches(1.8), Inches(5.1), Inches(4.8))
    tf_l = tb_l.text_frame; tf_l.word_wrap = True
    p = tf_l.paragraphs[0]
    p.text = "1. Bất cập & Hướng tiếp cận RAG"
    p.font.size = Pt(21); p.font.bold = True; p.font.color.rgb = C_ACCENT_ROSE; p.space_after = Pt(16)
    
    bullets_s2 = [
        ("Mô hình cũ chỉ đọc bài viết:", "Gán nhãn Thật/Giả như 'hộp đen', hoàn toàn không có bằng chứng đối chiếu."),
        ("Thiếu trích dẫn nguồn:", "Người dùng và chuyên gia không thể thẩm định tính xác thực."),
        ("Giải pháp RAG của Đề tài:", "Truy xuất trước - Kết luận sau: Tự động tìm kiếm bằng chứng từ kho báo chí và Web trước khi đưa ra phán quyết 3 nhãn chặt chẽ (Ủng hộ / Bác bỏ / Chưa đủ căn cứ).")
    ]
    for b_title, b_desc in bullets_s2:
        p = tf_l.add_paragraph()
        p.text = "• " + b_title + " "
        p.font.size = Pt(16); p.font.bold = True; p.font.color.rgb = C_TEXT_MAIN
        r = p.add_run(); r.text = b_desc; r.font.bold = False
        p.space_after = Pt(14)

    # Right: The Pilot Experiment Table
    add_card(s2, 6.8, 1.6, 5.7, 5.3, bg_color=C_CARD_ALT)
    tb_r = s2.shapes.add_textbox(Inches(7.0), Inches(1.8), Inches(5.3), Inches(0.5))
    tf_r = tb_r.text_frame; tf_r.word_wrap = True
    p = tf_r.paragraphs[0]
    p.text = "2. Thí nghiệm trên tập VFND (221 bài)"
    p.font.size = Pt(19); p.font.bold = True; p.font.color.rgb = C_ACCENT_BLUE

    tbl_shape = s2.shapes.add_table(3, 4, Inches(7.0), Inches(2.35), Inches(5.3), Inches(1.8))
    t = tbl_shape.table
    w = [2.3, 1.0, 1.0, 1.0]
    h = ["Phương pháp", "Macro-F1", "ROC-AUC", "Bắt tin giả"]
    d = [
        ["Baseline Từ khóa (SVM)", "77.27%", "88.21%", "60.82%"],
        ["PhoBERT Ngữ nghĩa", "48.59%", "70.20%", "19.58%"]
    ]
    format_table(t, w, h, d, font_size=14.5)

    tb_sub = s2.shapes.add_textbox(Inches(7.0), Inches(4.4), Inches(5.3), Inches(2.3))
    tf_sub = tb_sub.text_frame; tf_sub.word_wrap = True
    p = tf_sub.paragraphs[0]
    p.text = "💡 Phát hiện Khoa học Cốt lõi:"
    p.font.size = Pt(17); p.font.bold = True; p.font.color.rgb = C_ACCENT_ROSE; p.space_after = Pt(6)
    insights_s2 = [
        "PhoBERT sụp đổ (-29 điểm F1): Khi chia tách nguồn bài báo chặt chẽ, mô hình ngữ nghĩa bỏ lọt hơn 80% tin giả.",
        "Baseline từ khóa chỉ thắng ảo nhờ ăn theo đặc trưng tên miền báo có sẵn trong tập dữ liệu.",
        "KẾT LUẬN: BẮT BUỘC phải đối chiếu bằng chứng sự thật (RAG)!"
    ]
    for it in insights_s2:
        p = tf_sub.add_paragraph()
        p.text = "• " + it
        p.font.size = Pt(15); p.font.color.rgb = C_TEXT_MAIN; p.space_after = Pt(4)

    # =========================================================================
    # SLIDE 3: Kiến trúc Tổng thể & Kỷ luật Chống rò rỉ Dữ liệu
    # =========================================================================
    s3 = prs.slides.add_slide(blank_layout)
    add_header(s3, "Kiến trúc Tổng thể Hệ thống & Kỷ luật Dữ liệu Thực nghiệm", slide_num=3)

    # Top: 4 Arch Blocks
    arch_blocks = [
        ("1. TRUY XUẤT", "Tìm kiếm đa nguồn", "• Kho Báo: 5.845 đoạn\n• BM25 lấy 20 đoạn\n• Web: 33 báo uy tín", C_ACCENT_BLUE),
        ("2. TỔNG HỢP", "Lọc & Xếp hạng", "• Gộp danh sách RRF\n• Neo thời gian 10/365d\n• Rerank theo uy tín", C_ACCENT_AMBER),
        ("3. ĐỌC HIỂU", "PhoBERT Tinh chỉnh", "• Ensemble 3 góc nhìn:\n  + Cả đoạn văn\n  + Câu khớp đầu\n  + Duy nhất câu khớp", C_ACCENT_GREEN),
        ("4. RA QUYẾT ĐỊNH", "Quyết định & Hậu kiểm", "• Trọng số theo rank\n• Ngưỡng tự tin 0.5\n• Luật đổi số min-pair\n• Dẫn link bài gốc", C_ACCENT_ROSE)
    ]
    for idx, (b_step, b_title, b_desc, b_col) in enumerate(arch_blocks):
        x = 0.8 + idx * 2.95
        add_card(s3, x, 1.6, 2.8, 2.7)
        bar = s3.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(1.6), Inches(2.8), Inches(0.12))
        bar.fill.solid(); bar.fill.fore_color.rgb = b_col; bar.line.fill.background()

        tb = s3.shapes.add_textbox(Inches(x + 0.12), Inches(1.8), Inches(2.55), Inches(2.4))
        tf = tb.text_frame; tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = b_step; p.font.size = Pt(12); p.font.bold = True; p.font.color.rgb = b_col
        p1 = tf.add_paragraph()
        p1.text = b_title; p1.font.size = Pt(16); p1.font.bold = True; p1.font.color.rgb = C_TEXT_MAIN; p1.space_after = Pt(6)
        p2 = tf.add_paragraph()
        p2.text = b_desc; p2.font.size = Pt(13.5); p2.font.color.rgb = C_TEXT_MAIN

    # Bottom Left: Dataset Table
    add_card(s3, 0.8, 4.5, 6.4, 2.4)
    tbl_shape = s3.shapes.add_table(5, 4, Inches(1.0), Inches(4.6), Inches(6.0), Inches(2.1))
    t = tbl_shape.table
    w = [1.8, 1.4, 1.4, 1.4]
    h = ["Tập dữ liệu", "Tỷ lệ", "Số lượng", "Phân bố nhãn"]
    d = [
        ["Tập Huấn luyện (Train)", "70%", "5.076", "Cân bằng"],
        ["Tập Tinh chỉnh (Dev)", "15%", "1.080", "Cân bằng"],
        ["Tập Đánh giá (Test)", "15%", "1.076", "Cân bằng"],
        ["Tổng cộng (ViFactCheck)", "100%", "7.232", "12 chủ đề"]
    ]
    format_table(t, w, h, d, font_size=13.5)

    # Bottom Right: Rules & Specs
    add_card(s3, 7.5, 4.5, 5.0, 2.4, bg_color=C_CARD_ALT)
    tb_b = s3.shapes.add_textbox(Inches(7.7), Inches(4.6), Inches(4.6), Inches(2.1))
    tf_b = tb_b.text_frame; tf_b.word_wrap = True
    p = tf_b.paragraphs[0]
    p.text = "Kỷ luật NCKH & Môi trường thực nghiệm"
    p.font.size = Pt(16.5); p.font.bold = True; p.font.color.rgb = C_ACCENT_BLUE; p.space_after = Pt(6)
    specs_s3 = [
        "Nguyên tắc rò rỉ = 0: Group-split URL, toàn bộ câu của 1 bài báo chỉ nằm ở 1 tập.",
        "Kỷ luật Test: Mọi siêu tham số khóa cứng trên Dev; Test chỉ chạy đúng 1 lần.",
        "Huấn luyện: PhoBERT-base, AdamW, lr=1e-5, batch 16 trên GPU Kaggle T4."
    ]
    for sp in specs_s3:
        p = tf_b.add_paragraph()
        p.text = "• " + sp
        p.font.size = Pt(14); p.font.color.rgb = C_TEXT_MAIN; p.space_after = Pt(4)

    # =========================================================================
    # SLIDE 4: Benchmark Truy xuất (Retrieval) & Đọc hiểu Chuẩn (Oracle Verifier)
    # =========================================================================
    s4 = prs.slides.add_slide(blank_layout)
    add_header(s4, "Đánh giá Thành phần Độc lập: Tìm kiếm & Đọc hiểu Chuẩn", slide_num=4)

    # Left: Retrieval Benchmark
    add_card(s4, 0.8, 1.6, 5.7, 5.3)
    tb_l = s4.shapes.add_textbox(Inches(1.0), Inches(1.8), Inches(5.3), Inches(0.5))
    tf_l = tb_l.text_frame; tf_l.word_wrap = True
    p = tf_l.paragraphs[0]
    p.text = "1. Hiệu năng Khâu Tìm kiếm (5.845 đoạn)"
    p.font.size = Pt(19); p.font.bold = True; p.font.color.rgb = C_ACCENT_BLUE

    tbl_shape = s4.shapes.add_table(4, 4, Inches(1.0), Inches(2.35), Inches(5.3), Inches(2.0))
    t = tbl_shape.table
    w = [2.0, 1.1, 1.1, 1.1]
    h = ["Phương pháp", "Top-3", "Top-5", "MRR"]
    d = [
        ["BM25 Từ khóa (Chọn)", "98.14%", "98.98%", "0.9671"],
        ["Dense Embedding (E5)", "92.10%*", "95.65%*", "0.9125*"],
        ["Hybrid (BM25 + Dense)", "96.20%*", "98.43%*", "0.9547*"]
    ]
    format_table(t, w, h, d, font_size=14.5)

    tb_sub_l = s4.shapes.add_textbox(Inches(1.0), Inches(4.5), Inches(5.3), Inches(2.2))
    tf_sub_l = tb_sub_l.text_frame; tf_sub_l.word_wrap = True
    p = tf_sub_l.paragraphs[0]
    p.text = "🔍 Căn cứ khoa học chọn BM25:"
    p.font.size = Pt(16); p.font.bold = True; p.font.color.rgb = C_ACCENT_BLUE; p.space_after = Pt(4)
    pts_s4_l = [
        "Dense Embedding tụt gần 3 điểm: Tiếng Việt cần bắt chính xác tên riêng, ngày tháng và con số.",
        "Hybrid không hơn BM25 thuần mà tốn gấp đôi tài nguyên RAM và độ trễ.",
        "BM25 thuần đạt Top-5 99.0%, chạy cực nhẹ 81ms trên CPU."
    ]
    for pt in pts_s4_l:
        p = tf_sub_l.add_paragraph()
        p.text = "• " + pt
        p.font.size = Pt(14.5); p.font.color.rgb = C_TEXT_MAIN; p.space_after = Pt(3)

    # Right: Oracle Verifier Benchmark
    add_card(s4, 6.8, 1.6, 5.7, 5.3, bg_color=C_CARD_ALT)
    tb_r = s4.shapes.add_textbox(Inches(7.0), Inches(1.8), Inches(5.3), Inches(0.5))
    tf_r = tb_r.text_frame; tf_r.word_wrap = True
    p = tf_r.paragraphs[0]
    p.text = "2. Năng lực Đọc hiểu khi có Bằng chứng"
    p.font.size = Pt(19); p.font.bold = True; p.font.color.rgb = C_ACCENT_GREEN

    tbl_shape2 = s4.shapes.add_table(4, 4, Inches(7.0), Inches(2.35), Inches(5.3), Inches(2.0))
    t2 = tbl_shape2.table
    w2 = [2.3, 1.0, 1.0, 1.0]
    h2 = ["Mô hình Đọc hiểu", "Dev", "Test", "F1 Bác bỏ"]
    d2 = [
        ["Baseline Từ khóa (SVM)", "—", "40.15%", "34.10%"],
        ["PhoBERT AAAI 2025*", "—", "77.76%", "—"],
        ["PhoBERT Đề tài (Chọn)", "85.01%", "81.07%", "77.90%"]
    ]
    format_table(t2, w2, h2, d2, font_size=14.5)

    tb_sub_r = s4.shapes.add_textbox(Inches(7.0), Inches(4.5), Inches(5.3), Inches(2.2))
    tf_sub_r = tb_sub_r.text_frame; tf_sub_r.word_wrap = True
    p = tf_sub_r.paragraphs[0]
    p.text = "📊 Phân tích Khoa học:"
    p.font.size = Pt(16); p.font.bold = True; p.font.color.rgb = C_ACCENT_GREEN; p.space_after = Pt(4)
    pts_s4_r = [
        "Hiểu ngữ nghĩa vượt trội: PhoBERT vượt Baseline từ vựng tới +40.92 điểm Macro-F1.",
        "Vượt bài báo AAAI 2025: Đạt 81.07% vs 77.76% (+3.31 điểm) nhờ chuẩn hóa tiền xử lý tiếng Việt.",
        "Khóa Checkpoint: Mô hình PhoBERT này được giữ làm hạt nhân đọc hiểu cho toàn hệ thống."
    ]
    for pt in pts_s4_r:
        p = tf_sub_r.add_paragraph()
        p.text = "• " + pt
        p.font.size = Pt(14.5); p.font.color.rgb = C_TEXT_MAIN; p.space_after = Pt(3)

    # =========================================================================
    # SLIDE 5: Tiến trình Tối ưu End-to-End & Sửa lệch pha Train/Serve
    # =========================================================================
    s5 = prs.slides.add_slide(blank_layout)
    add_header(s5, "Tiến trình Tối ưu End-to-End & Sửa lệch pha Huấn luyện", slide_num=5)

    # Left: End-to-End Progress
    add_card(s5, 0.8, 1.6, 6.0, 5.3)
    tb_l = s5.shapes.add_textbox(Inches(1.0), Inches(1.8), Inches(5.6), Inches(0.45))
    tf_l = tb_l.text_frame; tf_l.word_wrap = True
    p = tf_l.paragraphs[0]
    p.text = "1. Tiến trình Tự tìm kiếm (1.076 mẫu Test)"
    p.font.size = Pt(19); p.font.bold = True; p.font.color.rgb = C_ACCENT_BLUE

    tbl_shape = s5.shapes.add_table(5, 4, Inches(1.0), Inches(2.15), Inches(5.6), Inches(2.3))
    t = tbl_shape.table
    w = [2.4, 1.0, 1.1, 1.1]
    h = ["Phiên bản Hệ thống", "Macro-F1", "F1 Bác bỏ", "Cải thiện"]
    d = [
        ["1. Baseline Tự tìm ban đầu", "59.49%", "45.20%", "Mốc đầu"],
        ["2. Thêm Chính sách thứ hạng", "62.94%", "49.81%", "+3.45"],
        ["3. Thêm Lọc & Xếp hạng nguồn", "69.92%", "62.21%", "+10.43"],
        ["4. HOÀN CHỈNH (Ensemble)", "72.31%", "66.20%", "+12.82*"]
    ]
    format_table(t, w, h, d, font_size=14)

    tb_sub_l = s5.shapes.add_textbox(Inches(1.0), Inches(4.75), Inches(5.6), Inches(1.9))
    tf_sub_l = tb_sub_l.text_frame; tf_sub_l.word_wrap = True
    p = tf_sub_l.paragraphs[0]
    p.text = "🌟 Cải thiện vượt bậc: +12.82 điểm Macro-F1"
    p.font.size = Pt(16); p.font.bold = True; p.font.color.rgb = C_ACCENT_GREEN; p.space_after = Pt(4)
    p2 = tf_sub_l.add_paragraph()
    p2.text = "• Sửa đúng ròng +122 phát biểu. Nhãn khó BÁC BỎ tăng vọt từ 45.2% lên 66.2% (+21.0 điểm). Độ trung thực trích dẫn đạt 95.4%."
    p2.font.size = Pt(14.5); p2.font.color.rgb = C_TEXT_MAIN

    # Right: Train/Serve Mismatch
    add_card(s5, 7.1, 1.6, 5.4, 5.3, bg_color=C_CARD_ALT)
    tb_r = s5.shapes.add_textbox(Inches(7.3), Inches(1.8), Inches(5.0), Inches(0.45))
    tf_r = tb_r.text_frame; tf_r.word_wrap = True
    p = tf_r.paragraphs[0]
    p.text = "2. Khắc phục Lệch pha (Train/Serve)"
    p.font.size = Pt(19); p.font.bold = True; p.font.color.rgb = C_ACCENT_ROSE

    tbl_shape2 = s5.shapes.add_table(4, 4, Inches(7.3), Inches(2.15), Inches(5.0), Inches(2.0))
    t2 = tbl_shape2.table
    w2 = [2.0, 1.0, 1.0, 1.0]
    h2 = ["Phiên bản Mô hình", "F1", "F1 Bác bỏ", "Tỷ lệ NEI"]
    d2 = [
        ["PhoBERT Gốc", "62.66%", "52.50%", "30.28%"],
        ["Tinh chỉnh lần 1", "71.35%", "61.40%", "40.93%"],
        ["Cân bằng nhãn (Khóa)", "70.75%", "64.23%", "28.52%"]
    ]
    format_table(t2, w2, h2, d2, font_size=14)

    tb_sub_r = s5.shapes.add_textbox(Inches(7.3), Inches(4.45), Inches(5.0), Inches(2.2))
    tf_sub_r = tb_sub_r.text_frame; tf_sub_r.word_wrap = True
    p = tf_sub_r.paragraphs[0]
    p.text = "🎯 Quyết định chọn bản Cân bằng nhãn:"
    p.font.size = Pt(16); p.font.bold = True; p.font.color.rgb = C_ACCENT_ROSE; p.space_after = Pt(4)
    pts_s5_r = [
        "Bản 1 bị tật lười phán đoán: Trả Không Đủ Tin tới 41%!",
        "Bản Cân bằng nhãn ép mô hình bắt mâu thuẫn: Tỷ lệ NEI giảm về 28.5%, F1 Bác bỏ tăng lên 64.23%.",
        "Chính thức khóa cấu hình này làm mô hình cốt lõi."
    ]
    for pt in pts_s5_r:
        p = tf_sub_r.add_paragraph()
        p.text = "• " + pt
        p.font.size = Pt(14); p.font.color.rgb = C_TEXT_MAIN; p.space_after = Pt(3)

    # =========================================================================
    # SLIDE 6: Phân tích Đóng góp (Ablation) & Ma trận nhầm lẫn
    # =========================================================================
    s6 = prs.slides.add_slide(blank_layout)
    add_header(s6, "Phân tích Đóng góp Thành phần & Ma trận Nhầm lẫn (Dev/Test)", slide_num=6)

    # Left: Ablation Study
    add_card(s6, 0.8, 1.6, 6.0, 5.3)
    tb_l = s6.shapes.add_textbox(Inches(1.0), Inches(1.8), Inches(5.6), Inches(0.45))
    tf_l = tb_l.text_frame; tf_l.word_wrap = True
    p = tf_l.paragraphs[0]
    p.text = "1. Bóc tách Đóng góp Thành phần (Ablation)"
    p.font.size = Pt(19); p.font.bold = True; p.font.color.rgb = C_ACCENT_BLUE

    tbl_shape = s6.shapes.add_table(6, 3, Inches(1.0), Inches(2.15), Inches(5.6), Inches(2.5))
    t = tbl_shape.table
    w = [2.7, 1.3, 1.6]
    h = ["Thành phần can thiệp", "Độ tăng F1", "Quyết định"]
    d = [
        ["Ensemble 3 góc nhìn bằng chứng", "+2.6 điểm", "BẬT CHÍNH THỨC"],
        ["Đối chiếu số liệu (bắt đổi số)", "+0.1 điểm", "BẬT CHÍNH THỨC"],
        ["Đưa câu khớp nhất lên đầu", "+1.4 điểm", "KHÔNG CHỌN"],
        ["Chỉ lấy duy nhất câu khớp nhất", "-6.2 điểm", "LOẠI BỎ"],
        ["Bộ lọc ngưỡng an toàn ở kho báo", "-10.0 điểm", "TẮT Ở KHO BÁO"]
    ]
    format_table(t, w, h, d, font_size=13.5)

    tb_sub_l = s6.shapes.add_textbox(Inches(1.0), Inches(4.9), Inches(5.6), Inches(1.8))
    tf_sub_l = tb_sub_l.text_frame; tf_sub_l.word_wrap = True
    p = tf_sub_l.paragraphs[0]
    p.text = "💡 Bài học Phương pháp NCKH:"
    p.font.size = Pt(15.5); p.font.bold = True; p.font.color.rgb = C_ACCENT_BLUE; p.space_after = Pt(2)
    p2 = tf_sub_l.add_paragraph()
    p2.text = "• Cắt ngắn còn 1 câu làm mất ngữ cảnh (-6.2 điểm). Mọi quyết định chọn tính năng đều dựa trên tập Dev có người gán nhãn."
    p2.font.size = Pt(14); p2.font.color.rgb = C_TEXT_MAIN

    # Right: Confusion Matrix & Bottleneck
    add_card(s6, 7.1, 1.6, 5.4, 5.3, bg_color=C_CARD_ALT)
    tb_r = s6.shapes.add_textbox(Inches(7.3), Inches(1.8), Inches(5.0), Inches(0.45))
    tf_r = tb_r.text_frame; tf_r.word_wrap = True
    p = tf_r.paragraphs[0]
    p.text = "2. Ma trận Nhầm lẫn & Chẩn đoán Lỗi"
    p.font.size = Pt(19); p.font.bold = True; p.font.color.rgb = C_ACCENT_ROSE

    tbl_shape2 = s6.shapes.add_table(4, 4, Inches(7.3), Inches(2.15), Inches(5.0), Inches(2.0))
    t2 = tbl_shape2.table
    w2 = [1.7, 1.1, 1.1, 1.1]
    h2 = ["Thực \\ Đoán", "Ủng hộ", "Bác bỏ", "Chưa đủ"]
    d2 = [
        ["Ủng hộ (368)", "312 (85%)", "21 (6%)", "35 (9%)"],
        ["Bác bỏ (356)", "88 (25%)", "206 (58%)", "62 (17%)"],
        ["Chưa đủ (352)", "48 (14%)", "39 (11%)", "265 (75%)"]
    ]
    format_table(t2, w2, h2, d2, font_size=13.5)

    tb_sub_r = s6.shapes.add_textbox(Inches(7.3), Inches(4.45), Inches(5.0), Inches(2.2))
    tf_sub_r = tb_sub_r.text_frame; tf_sub_r.word_wrap = True
    p = tf_sub_r.paragraphs[0]
    p.text = "🎯 ĐỊNH LƯỢNG ĐIỂM NGHẼN HỆ THỐNG:"
    p.font.size = Pt(16); p.font.bold = True; p.font.color.rgb = C_ACCENT_ROSE; p.space_after = Pt(4)
    pts_s6_r = [
        "Chỉ 2.3% lỗi do Tìm kiếm bỏ sót bài nguồn!",
        "97.7% lỗi nằm ở Đọc hiểu (88 câu Bác bỏ bị đoán nhầm thành Ủng hộ do chỉ khớp từ bề mặt).",
        "Mấu chốt nâng cấp hệ thống là năng lực suy luận logic."
    ]
    for pt in pts_s6_r:
        p = tf_sub_r.add_paragraph()
        p.text = "• " + pt
        p.font.size = Pt(14); p.font.color.rgb = C_TEXT_MAIN; p.space_after = Pt(3)

    # =========================================================================
    # SLIDE 7: Mở rộng: Benchmark Đối đầu LLM Gemma 4 trên 84 ca Độc lập
    # =========================================================================
    s7 = prs.slides.add_slide(blank_layout)
    add_header(s7, "Mở rộng: Đánh giá Đối đầu PhoBERT vs LLM Gemma 4 (84 ca Độc lập)", slide_num=7)

    # Left: Blind Protocol & Architecture
    add_card(s7, 0.8, 1.6, 5.6, 5.3)
    tb_l = s7.shapes.add_textbox(Inches(1.0), Inches(1.8), Inches(5.2), Inches(4.8))
    tf_l = tb_l.text_frame; tf_l.word_wrap = True
    p = tf_l.paragraphs[0]
    p.text = "1. Giao thức Thí nghiệm Độc lập Chặt chẽ"
    p.font.size = Pt(20); p.font.bold = True; p.font.color.rgb = C_ACCENT_BLUE; p.space_after = Pt(14)
    specs_s7 = [
        ("Bộ Độc lập 84 ca cân bằng:", "28 Ủng hộ / 28 Bác bỏ / 28 Chưa đủ tin; thiết kế theo 7 nhóm suy luận phức tạp trong thế giới giả lập để triệt rò rỉ mạng."),
        ("Khóa mã băm SHA-256:", "File đề bài gửi mô hình hoàn toàn không chứa đáp án."),
        ("Kỷ luật chấm độc lập:", "Code test độc lập; lỗi mất mạng API Google tính là đoán sai."),
        ("So sánh kiến trúc:", "PhoBERT (Encoder 135M chạy CPU) vs Gemma 4 (Decoder LLM 31B/26B MoE qua API).")
    ]
    for sh, sb in specs_s7:
        p = tf_l.add_paragraph()
        p.text = "• " + sh + " "
        p.font.size = Pt(15.5); p.font.bold = True; p.font.color.rgb = C_TEXT_MAIN
        r = p.add_run(); r.text = sb; r.font.bold = False
        p.space_after = Pt(12)

    # Right: Results Table & Significance
    add_card(s7, 6.7, 1.6, 5.8, 5.3, bg_color=C_CARD_ALT)
    tb_r = s7.shapes.add_textbox(Inches(6.9), Inches(1.8), Inches(5.4), Inches(0.45))
    tf_r = tb_r.text_frame; tf_r.word_wrap = True
    p = tf_r.paragraphs[0]
    p.text = "2. Kết quả Đối đầu trên 84 ca Chuẩn gán tay"
    p.font.size = Pt(19); p.font.bold = True; p.font.color.rgb = C_ACCENT_GREEN

    tbl_shape = s7.shapes.add_table(5, 5, Inches(6.9), Inches(2.15), Inches(5.4), Inches(2.2))
    t = tbl_shape.table
    w = [2.2, 0.8, 0.8, 0.8, 0.8]
    h = ["Mô hình", "Chính xác", "Macro-F1", "F1 Bác bỏ", "Trích dẫn"]
    d = [
        ["PhoBERT Đề tài", "33.3%", "22.5%", "49.5%", "24/84"],
        ["PhoBERT + Luật", "34.5%", "23.1%", "51.0%", "25/84"],
        ["Gemma 4 31B", "85.7%", "90.0%", "89.3%", "70/84"],
        ["Gemma 4 26B (MoE)", "85.7%", "90.5%", "88.9%", "47/84"]
    ]
    format_table(t, w, h, d, font_size=13.5)

    tb_sub_r = s7.shapes.add_textbox(Inches(6.9), Inches(4.6), Inches(5.4), Inches(2.1))
    tf_sub_r = tb_sub_r.text_frame; tf_sub_r.word_wrap = True
    p = tf_sub_r.paragraphs[0]
    p.text = "📊 KIỂM ĐỊNH Ý NGHĨA THỐNG KÊ:"
    p.font.size = Pt(16); p.font.bold = True; p.font.color.rgb = C_ACCENT_BLUE; p.space_after = Pt(4)
    res_s7 = [
        "LLM vượt trội về suy luận logic: Gemma 4 hơn PhoBERT +67.5 điểm Macro-F1 (kiểm định McNemar p < 10⁻¹⁰).",
        "Hai cỡ Gemma 4 ngang ngửa: Bản 31B và 26B đều đạt 85.7% độ chính xác (không khác biệt thống kê).",
        "Nếu loại trừ các ca rớt mạng: Gemma 4 31B đạt tới 94.7% (72/76 ca)."
    ]
    for r in res_s7:
        p = tf_sub_r.add_paragraph()
        p.text = "• " + r
        p.font.size = Pt(14); p.font.color.rgb = C_TEXT_MAIN; p.space_after = Pt(2)

    # =========================================================================
    # SLIDE 8: Phân tích Điểm mù theo 7 Nhóm Suy luận & Bản chất Lỗi
    # =========================================================================
    s8 = prs.slides.add_slide(blank_layout)
    add_header(s8, "PhoBERT tụt ở đâu? Phân tích theo 7 Nhóm Suy luận", slide_num=8)

    # Left: 7 Reasoning Groups Table
    add_card(s8, 0.8, 1.6, 6.4, 5.3)
    tbl_shape = s8.shapes.add_table(8, 3, Inches(1.0), Inches(1.75), Inches(6.0), Inches(4.8))
    t = tbl_shape.table
    w = [3.2, 1.4, 1.4]
    h = ["Nhóm Suy luận (12 câu/nhóm)", "PhoBERT Đề tài", "LLM Gemma 4"]
    d = [
        ["Tính toán số học & Đơn vị", "25.0%", "66.7%"],
        ["Xâu chuỗi nhiều bài báo (Multi-hop)", "25.0%", "91.7%"],
        ["Mốc thời gian & Lịch sử", "33.3%", "91.7%"],
        ["Phủ định logic & 'chưa'", "33.3%", "75.0%"],
        ["Lượng từ 'tất cả' vs 'một số'", "33.3%", "83.3%"],
        ["Phạm vi đối tượng & Trùng tên", "33.3%", "91.7%"],
        ["Bằng chứng xung đột & Đính chính", "50.0%", "100.0%"]
    ]
    format_table(t, w, h, d, font_size=14.5)

    # Right: Case Studies
    add_card(s8, 7.5, 1.6, 5.0, 5.3, bg_color=C_CARD_ALT)
    tb_r = s8.shapes.add_textbox(Inches(7.7), Inches(1.8), Inches(4.6), Inches(4.8))
    tf_r = tb_r.text_frame; tf_r.word_wrap = True
    p = tf_r.paragraphs[0]
    p.text = "🔍 Phân tích Bản chất Lỗi"
    p.font.size = Pt(20); p.font.bold = True; p.font.color.rgb = C_ACCENT_ROSE; p.space_after = Pt(14)
    cases_s8 = [
        ("Điểm mù Tính toán:", "Phát biểu 'Tổng 75 cuốn', bài viết 'đợt 1: 35, đợt 2: 40'. PhoBERT phán Bác bỏ vì thấy số 75 khác 35 và 40. Gemma tính nhẩm 35+40=75 -> Đúng Ủng hộ."),
        ("Điểm mù Xâu chuỗi (Multi-hop):", "Cần kết hợp 2 bài báo độc lập. PhoBERT đọc từng đoạn riêng rẽ nên hoàn toàn bất lực."),
        ("Gemma suy diễn quá mức:", "Coi 'chưa nhắc tới' là 'sai' (3 câu Chưa Đủ Tin bị phán thành Bác bỏ).")
    ]
    for ch, cb in cases_s8:
        p = tf_r.add_paragraph()
        p.text = "• " + ch + " "
        p.font.size = Pt(15); p.font.bold = True; p.font.color.rgb = C_TEXT_MAIN
        r = p.add_run(); r.text = cb; r.font.bold = False
        p.space_after = Pt(12)

    # =========================================================================
    # SLIDE 9: Đánh đổi Vận hành Thực tế & Kiến trúc Hybrid 2 Tầng
    # =========================================================================
    s9 = prs.slides.add_slide(blank_layout)
    add_header(s9, "Đánh đổi Thực tế & Đề xuất Kiến trúc Hybrid 2 Tầng", slide_num=9)

    # Left: Operational Trade-offs
    add_card(s9, 0.8, 1.6, 5.6, 5.3)
    tb_l = s9.shapes.add_textbox(Inches(1.0), Inches(1.8), Inches(5.2), Inches(0.5))
    tf_l = tb_l.text_frame; tf_l.word_wrap = True
    p = tf_l.paragraphs[0]
    p.text = "1. Đánh đổi Vận hành Thực tế"
    p.font.size = Pt(19); p.font.bold = True; p.font.color.rgb = C_TEXT_MAIN

    tbl_shape = s9.shapes.add_table(5, 3, Inches(1.0), Inches(2.35), Inches(5.2), Inches(2.5))
    t = tbl_shape.table
    w = [2.2, 1.5, 1.5]
    h = ["Tiêu chí vận hành", "PhoBERT Đề tài", "LLM Gemma 4"]
    d = [
        ["Thời gian trung vị (p50)", "0.25 giây", "51.0 giây"],
        ["Thời gian phân vị p95", "0.50 giây", "313.0 giây (5 phút)"],
        ["Khả năng chạy Offline", "100% không mạng", "Phụ thuộc API"],
        ["Lỗi mạng / quá tải", "0 ca lỗi", "8 ca (HTTP 500/503)"]
    ]
    format_table(t, w, h, d, font_size=14.5)

    tb_sub_l = s9.shapes.add_textbox(Inches(1.0), Inches(5.35), Inches(5.2), Inches(1.4))
    tf_sub_l = tb_sub_l.text_frame; tf_sub_l.word_wrap = True
    p = tf_sub_l.paragraphs[0]
    p.text = "⚡ PhoBERT nhanh hơn 30 - 200 lần, hoàn toàn miễn phí và chạy mượt mà 100% offline trên laptop."
    p.font.size = Pt(15); p.font.bold = True; p.font.color.rgb = C_ACCENT_GREEN

    # Right: Hybrid 2-Tier Architecture
    add_card(s9, 6.7, 1.6, 5.8, 5.3, bg_color=C_CARD_ALT)
    tb_r = s9.shapes.add_textbox(Inches(7.0), Inches(1.8), Inches(5.2), Inches(4.8))
    tf_r = tb_r.text_frame; tf_r.word_wrap = True
    p = tf_r.paragraphs[0]
    p.text = "2. Giải pháp: Kiến trúc Hybrid 2 Tầng"
    p.font.size = Pt(20); p.font.bold = True; p.font.color.rgb = C_ACCENT_BLUE; p.space_after = Pt(14)
    props_s9 = [
        ("TẦNG 1 (PhoBERT Đề tài - Local):", "Sàng lọc ~80% phát biểu cơ bản hàng ngày. Tốc độ tức thì (< 0.5s), chi phí 0 đồng, bảo mật tuyệt đối."),
        ("TẦNG 2 (LLM Gemma 4 - Cloud API):", "Chỉ kích hoạt khi: Phát hiện có con số cần tính nhẩm, xâu chuỗi nhiều bài báo, hoặc Tầng 1 thiếu tự tin (decisive score < 0.5)."),
        ("HIỆU QUẢ KỲ VỌNG:", "Đạt độ chính xác > 85% của LLM với chi phí và độ trễ gần bằng mô hình nhỏ!")
    ]
    for ph, pb in props_s9:
        p = tf_r.add_paragraph()
        p.text = "• " + ph + " "
        p.font.size = Pt(15.5); p.font.bold = True; p.font.color.rgb = C_TEXT_MAIN
        r = p.add_run(); r.text = pb; r.font.bold = False
        p.space_after = Pt(10)

    # =========================================================================
    # SLIDE 10: Sản phẩm Hoàn chỉnh: Giao diện Web & Bộ Kiểm thử 333 Tests
    # =========================================================================
    s10 = prs.slides.add_slide(blank_layout)
    add_header(s10, "Sản phẩm Thực tế & Bộ Kiểm thử Phần mềm Tự động", slide_num=10)

    # Left: Web UI
    add_card(s10, 0.8, 1.6, 5.6, 5.3)
    tb_l = s10.shapes.add_textbox(Inches(1.0), Inches(1.8), Inches(5.2), Inches(4.8))
    tf_l = tb_l.text_frame; tf_l.word_wrap = True
    p = tf_l.paragraphs[0]
    p.text = "1. Giao diện Người dùng Web"
    p.font.size = Pt(20); p.font.bold = True; p.font.color.rgb = C_ACCENT_BLUE; p.space_after = Pt(16)
    ui_s10 = [
        ("Hai chế độ kiểm chứng:", "Kho Báo chí đã đánh giá (5.845 đoạn) & Tìm kiếm Web trực tiếp (33 báo uy tín có lọc ngày neo thời gian)."),
        ("Minh bạch bằng chứng:", "Thẻ kết quả theo mã màu trực quan, trích dẫn rõ đoạn văn cụ thể và link mở bài báo gốc."),
        ("Demo trực tiếp:", "Sẵn sàng các ca thực tế (Tổng thống Brazil, giá xăng, tin thời sự mới). Chạy: py -3.13 app_gradio.py.")
    ]
    for uh, ub in ui_s10:
        p = tf_l.add_paragraph()
        p.text = "• " + uh + " "
        p.font.size = Pt(16); p.font.bold = True; p.font.color.rgb = C_TEXT_MAIN
        r = p.add_run(); r.text = ub; r.font.bold = False
        p.space_after = Pt(14)

    # Right: Testing & Robustness
    add_card(s10, 6.7, 1.6, 5.8, 5.3, bg_color=C_CARD_ALT)
    tb_r = s10.shapes.add_textbox(Inches(7.0), Inches(1.8), Inches(5.2), Inches(4.8))
    tf_r = tb_r.text_frame; tf_r.word_wrap = True
    p = tf_r.paragraphs[0]
    p.text = "2. Kiểm thử Phần mềm & Độ vững"
    p.font.size = Pt(20); p.font.bold = True; p.font.color.rgb = C_ACCENT_GREEN; p.space_after = Pt(16)
    tests_s10 = [
        ("333 Bài kiểm thử tự động:", "Chạy vượt qua 100% trên CPU thông qua hệ thống Pytest."),
        ("Sửa dứt điểm 20 lỗi đối kháng:", "Chặn câu lệnh phá hoại (prompt-injection), sửa lỗi lấy nhầm đồng hồ web, chặn tin 'tương lai'."),
        ("Chuẩn hóa đầu ra JSON:", "Mọi kết luận đúng/sai đều có trích dẫn hợp lệ; khi Chưa Đủ Tin tuyệt đối không dẫn nguồn bừa.")
    ]
    for th, tb_t in tests_s10:
        p = tf_r.add_paragraph()
        p.text = "• " + th + " "
        p.font.size = Pt(16); p.font.bold = True; p.font.color.rgb = C_TEXT_MAIN
        r = p.add_run(); r.text = tb_t; r.font.bold = False
        p.space_after = Pt(14)

    # =========================================================================
    # SLIDE 11: Đóng góp Khoa học Chính, Giới hạn & Kết luận
    # =========================================================================
    s11 = prs.slides.add_slide(blank_layout)
    add_header(s11, "Đóng góp Khoa học Chính, Giới hạn & Kết luận", slide_num=11)

    # Left: Contributions
    add_card(s11, 0.8, 1.6, 5.6, 5.3)
    tb_l = s11.shapes.add_textbox(Inches(1.0), Inches(1.8), Inches(5.2), Inches(4.8))
    tf_l = tb_l.text_frame; tf_l.word_wrap = True
    p = tf_l.paragraphs[0]
    p.text = "1. Đóng góp Khoa học Chính"
    p.font.size = Pt(20); p.font.bold = True; p.font.color.rgb = C_ACCENT_GREEN; p.space_after = Pt(16)
    contribs_s11 = [
        ("Hệ thống RAG tiếng Việt hoàn chỉnh:", "Tự tìm bằng chứng kho báo chí và Web có kiểm soát neo thời gian cho tin mới."),
        ("Hiệu năng End-to-End thực tế:", "Đạt 72.31% Macro-F1 (vượt baseline ban đầu +12.8 điểm), F1 Bác bỏ đạt 66.2%."),
        ("Định lượng khoảng cách:", "Chứng minh điểm nghẽn nằm ở Đọc hiểu (97.7%) chứ không nằm ở Tìm kiếm (chỉ 2.3%)."),
        ("Bộ đánh giá độc lập 84 ca:", "Phân tích khách quan điểm mạnh/yếu của mô hình nhỏ so với LLM lớn.")
    ]
    for ch, cb in contribs_s11:
        p = tf_l.add_paragraph()
        p.text = "• " + ch + " "
        p.font.size = Pt(16); p.font.bold = True; p.font.color.rgb = C_TEXT_MAIN
        r = p.add_run(); r.text = cb; r.font.bold = False
        p.space_after = Pt(10)

    # Right: Limitations & Next Steps
    add_card(s11, 6.7, 1.6, 5.8, 5.3, bg_color=C_CARD_ALT)
    tb_r = s11.shapes.add_textbox(Inches(7.0), Inches(1.8), Inches(5.2), Inches(4.8))
    tf_r = tb_r.text_frame; tf_r.word_wrap = True
    p = tf_r.paragraphs[0]
    p.text = "2. Giới hạn & Hướng phát triển"
    p.font.size = Pt(20); p.font.bold = True; p.font.color.rgb = C_ACCENT_ROSE; p.space_after = Pt(16)
    limits_s11 = [
        ("Dữ liệu thế giới đóng:", "Kho báo chí hiện tại gần như luôn có bài nguồn; ngoài đời thực tỷ lệ Chưa Đủ Tin sẽ cao hơn."),
        ("Trích dẫn mức bài viết:", "Cần mở rộng kiểm toán thủ công 100% ở từng câu trích dẫn cụ thể."),
        ("HƯỚNG PHÁT TRIỂN TIẾP:", "Triển khai hệ thống Hybrid 2 tầng (PhoBERT + Gemma 4); huấn luyện mô hình với 900 câu đối kháng đổi số liệu đã chuẩn bị."),
        ("Tài liệu tham khảo chính:", "FEVER (NAACL 2018), RAG (NeurIPS 2020), ViFactCheck (AAAI 2025), PhoBERT (EMNLP 2020), Gemma 4 (Google 2026).")
    ]
    for lh, lb in limits_s11:
        p = tf_r.add_paragraph()
        p.text = "• " + lh + " "
        p.font.size = Pt(15.5); p.font.bold = True; p.font.color.rgb = C_TEXT_MAIN
        r = p.add_run(); r.text = lb; r.font.bold = False
        p.space_after = Pt(8)

    # Save presentation
    os.makedirs(os.path.dirname(output_pptx_path), exist_ok=True)
    prs.save(output_pptx_path)
    print(f"Presentation saved successfully to {output_pptx_path}")

if __name__ == "__main__":
    out_path = "docs/SLIDE_BAO_CAO_DE_TAI.pptx"
    create_deck(out_path)
