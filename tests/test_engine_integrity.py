"""Chống 'xanh giả': bảo đảm bộ test hành vi chạy đúng engine được yêu cầu.

Vì fc_adapter mặc định FALLBACK sang rule_based khi PhoBERT không nạp được
(FC_FALLBACK_RULE_BASED=1), các test metamorphic/behavioral có thể vô tình kiểm
rule_based mà vẫn báo pass — che lỗi của pipeline PhoBERT thật. Test này làm lộ điều đó:

- Mặc định: nếu bị fallback, SKIP kèm thông báo rõ (không giả vờ là đã kiểm PhoBERT).
- Khi đặt FC_REQUIRE_PHOBERT=1 (nên bật trong CI/đánh giá chính thức): fallback -> FAIL.
"""

from __future__ import annotations

import os

import pytest

from tests import fc_adapter


def test_requested_engine_is_actually_active():
    requested = os.environ.get("FC_ENGINE", "phobert")
    try:
        fc_adapter.get_pipeline()
    except Exception as exc:  # không dựng nổi cả rule_based -> môi trường hỏng
        pytest.skip(f"Không dựng được pipeline: {exc}")

    active = fc_adapter.active_engine()
    assert active in ("phobert", "rule_based")

    if requested == "phobert" and active != "phobert":
        message = (
            "PhoBERT được yêu cầu nhưng pipeline đang chạy "
            f"'{active}' (fallback). Các test hành vi KHÔNG kiểm đúng engine sản phẩm."
        )
        if os.environ.get("FC_REQUIRE_PHOBERT") == "1":
            pytest.fail(message)
        pytest.skip(message + " Đặt FC_REQUIRE_PHOBERT=1 để biến thành lỗi.")
