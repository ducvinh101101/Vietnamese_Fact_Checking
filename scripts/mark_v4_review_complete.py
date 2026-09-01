"""Mark Vinh's verifier-only E2 error review as complete in the backlog."""
from pathlib import Path


path = Path("docs/BACKLOG.md")
text = path.read_text(encoding="utf-8")
old = "| V4 | Đọc thủ công 10 lỗi E2 và phân loại nguyên nhân | Vinh | Đang thực hiện | Hoàn tất bảng nhận xét trong `PHAN_TICH_LOI_E2.md` |"
new = "| V4 | Đọc thủ công 10 lỗi E2 và phân loại nguyên nhân | Vinh | Hoàn thành | Review tại `REVIEW_10_LOI_E2.md`; không bao gồm retrieval |"
if old not in text:
    raise RuntimeError("Expected V4 backlog row was not found.")
path.write_text(text.replace(old, new), encoding="utf-8")
print("Marked V4 complete.")
