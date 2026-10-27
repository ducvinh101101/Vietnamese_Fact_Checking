"""Bộ claim minh họa dùng chung cho giao diện (ví dụ nhanh) và scripts/run_demo_cases.py (W4-04).

Mỗi ca ghi rõ nhãn kỳ vọng và LÝ DO, để buổi demo/báo cáo giải thích được hệ thống đúng
hay sai ở đâu. Ca 1–3 lấy từ cùng một câu trong kho (vifactcheck_01030_p001) để minh họa
luật cặp-tối-thiểu: nguyên văn -> SUPPORTED; đổi số / thêm phủ định -> REFUTED.
"""

from __future__ import annotations

DEMO_CASES: list[dict[str, str]] = [
    {
        "id": "D1", "mode": "local", "expected": "SUPPORTED",
        "title": "Có trong kho, đúng nguyên văn",
        "claim": "Tổng thống Brazil Lula hoãn chuyến thăm 6 ngày tới Trung Quốc do bệnh viêm phổi chưa khỏi hẳn.",
        "why": "Trùng nguyên văn một câu trong bài VnExpress (vifactcheck_01030_p001).",
    },
    {
        "id": "D2", "mode": "local", "expected": "REFUTED",
        "title": "Đổi một con số",
        "claim": "Tổng thống Brazil Lula hoãn chuyến thăm 10 ngày tới Trung Quốc do bệnh viêm phổi chưa khỏi hẳn.",
        "why": "Nguồn nói 6 ngày; claim nói 10 ngày — mâu thuẫn số liệu (luật cặp-tối-thiểu).",
    },
    {
        "id": "D3", "mode": "local", "expected": "REFUTED",
        "title": "Thêm phủ định",
        "claim": "Tổng thống Brazil Lula không hoãn chuyến thăm 6 ngày tới Trung Quốc do bệnh viêm phổi chưa khỏi hẳn.",
        "why": "Nguồn khẳng định có hoãn; claim phủ định.",
    },
    {
        "id": "D4", "mode": "local", "expected": "REFUTED",
        "title": "Claim sai trong test ViFactCheck",
        "claim": "Kể từ năm 2015 đến nay, theo Kyodo Nhật Bản đã bị Trung Quốc bắt vì tình nghi tham gia hoạt động gián điệp ít nhất 20 công dân Nhật.",
        "why": "Nhãn người REFUTED (test row 177); verifier phải đọc hiểu, không chỉ khớp từ.",
    },
    {
        "id": "D5", "mode": "local", "expected": "NOT_ENOUGH_INFO",
        "title": "Kho không đủ thông tin",
        "claim": "Đông Nam Á được xem là vùng trũng của bóng đá thế giới, đặc biệt là sau sự thành công của đội tuyển U23 Việt Nam.",
        "why": "Nhãn người NEI (test row 806): bài liên quan có trong kho nhưng không xác nhận nhận định này.",
    },
    {
        "id": "D6", "mode": "hybrid", "expected": "phụ thuộc tin ngày chạy",
        "title": "Thời sự — cần web",
        "claim": "Giá xăng tăng từ chiều nay",
        "why": "Chỉ nhận bằng chứng ≤ 10 ngày. Có bài mới cùng chiều -> SUPPORTED; không có/ngược chiều -> NEI.",
    },
]
