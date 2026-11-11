"""DeepSeek Chat Completions client for fixed-evidence verification."""

import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen


DEFAULT_DEEPSEEK_MODEL = "deepseek-flash"


class DeepSeekOutputError(ValueError):
    pass


class DeepSeekClient:
    def __init__(self, model: str, api_key: str, timeout: float):
        self.model = model
        self.api_key = api_key.strip()
        self.timeout = timeout
        if not self.api_key:
            raise ValueError("Thiếu DEEPSEEK_API_KEY. Hãy điền key vào .env hoặc biến môi trường")

    def predict(self, record: dict, prompt: str) -> tuple[dict, dict]:
        if set(record) != {"id", "as_of", "claim", "evidence"}:
            raise ValueError("DeepSeek chỉ nhận ID, ngày đối chiếu, phát biểu và bằng chứng")
        example = {"id": record["id"], "label": "NOT_ENOUGH_INFO",
                   "evidence_ids": [], "explanation": "Bằng chứng chưa đủ để kết luận."}
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": f"{prompt}\nVí dụ JSON: {json.dumps(example, ensure_ascii=False)}"},
                {"role": "user", "content": json.dumps(record, ensure_ascii=False)},
            ],
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
            "max_tokens": 1024,
        }
        request = Request(
            "https://api.deepseek.com/chat/completions",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        request.add_unredirected_header("Authorization", f"Bearer {self.api_key}")
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = json.load(response)
        except HTTPError as error:
            detail = {
                401: "kiểm tra API key",
                402: "kiểm tra số dư tài khoản",
                429: "đã chạm giới hạn tần suất, hãy thử lại sau",
            }.get(error.code, "kiểm tra quyền truy cập model hoặc thử lại sau")
            raise RuntimeError(f"DeepSeek HTTP {error.code} ({detail})") from None
        except OSError:
            raise RuntimeError("DeepSeek gặp lỗi kết nối hoặc hết thời gian chờ") from None
        except ValueError:
            raise DeepSeekOutputError("DeepSeek trả phản hồi HTTP không phải JSON") from None

        try:
            choice = raw["choices"][0]
            if choice["finish_reason"] != "stop":
                raise ValueError
            prediction = json.loads(choice["message"]["content"])
            citations = prediction["evidence_ids"]
            if (prediction["id"] != record["id"] or not isinstance(citations, list)
                    or not all(isinstance(pid, str) for pid in citations)
                    or not isinstance(prediction["explanation"], str)):
                raise ValueError
        except (KeyError, IndexError, TypeError, ValueError):
            raise DeepSeekOutputError("DeepSeek trả kết quả kiểm chứng thiếu trường hoặc sai định dạng") from None
        return prediction, raw
