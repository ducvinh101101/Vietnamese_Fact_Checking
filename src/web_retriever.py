"""Allowlisted web retrieval for W3-05.

The retriever is intentionally separate from the local BM25 pipeline.  It only
returns passages fetched from approved hosts; fusion and end-to-end evaluation
remain later retrieval tasks.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import gzip
from hashlib import sha256
from html.parser import HTMLParser
from http.client import HTTPException
from ipaddress import ip_address
import json
import os
from pathlib import Path
import re
import socket
import ssl
import time
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener
from urllib.robotparser import RobotFileParser
import zlib

from src.schemas import Evidence, RetrievedEvidence


SOURCE_TYPES = {"government": "government", "international": "international_org", "press": "news", "fact_check": "fact_check"}
AUTHORITY = {"government": 0.95, "international": 0.95, "fact_check": 0.9, "press": 0.7}


class WebRetrievalError(RuntimeError):
    """A controlled web-retrieval failure; callers should fall back to local."""


class WebLimitError(WebRetrievalError):
    """Hết hạn mức request (tháng hoặc phút) – thử lại ngay không giúp được."""

    def __init__(self, message: str, status: str) -> None:
        super().__init__(message)
        self.status = status


# last_status → câu giải thích cho người dùng khi web KHÔNG tra được (kết quả chỉ dựa trên kho cục bộ).
WEB_FAILURE_MESSAGES = {
    "local_only": "Không kết nối được dịch vụ tìm kiếm web.",
    "invalid_provider_response": "Dịch vụ tìm kiếm web trả kết quả không hợp lệ.",
    "pages_unreachable": "Tìm được bài trên web nhưng không tải được trang nào (mạng chậm hoặc trang chặn).",
    "rate_limited": "Đã chạm giới hạn số lần tìm web mỗi phút; đợi khoảng 1 phút rồi thử lại.",
    "budget_exhausted": "Đã dùng hết hạn mức tìm web của tháng.",
    "error": "Tìm kiếm web gặp lỗi không mong đợi.",
}
# Lỗi tạm thời: thử lại ngay có thể thành công (hạn mức thì không).
WEB_RETRYABLE_STATUSES = frozenset({"local_only", "invalid_provider_response", "pages_unreachable", "error"})


_TLS_CONTEXT: ssl.SSLContext | None = None


def tls_context() -> ssl.SSLContext:
    """Ngữ cảnh TLS cho mọi request web: vẫn kiểm tra chứng chỉ và tên miền như mặc định, thêm:

    * root CA của ``certifi`` – trên Windows Python chỉ thấy các root đã có sẵn trong kho máy (Windows tải
      root khi trình duyệt cần), vd. thiếu GlobalSign Root R6 nên www.sggp.org.vn bị từ chối;
    * không đề nghị cipher DHE – moh.gov.vn chọn DHE với khóa quá yếu (``DH_KEY_TOO_SMALL``); bỏ DHE thì máy
      chủ dùng ECDHE/RSA như với trình duyệt (Chrome, Firefox cũng đã bỏ DHE)."""
    global _TLS_CONTEXT
    if _TLS_CONTEXT is None:
        context = ssl.create_default_context()
        try:
            import certifi

            context.load_verify_locations(cafile=certifi.where())
        except ImportError:
            pass
        context.set_ciphers("DEFAULT:!DHE:!kDHE:!kDHEPSK")
        _TLS_CONTEXT = context
    return _TLS_CONTEXT


def _opener():
    return build_opener(HTTPSHandler(context=tls_context()), _NoRedirect())


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):  # type: ignore[override]
        return None


class _PageTextParser(HTMLParser):
    _BLOCKS = {"p", "li", "h1", "h2", "h3", "h4", "article", "main", "section", "div", "br"}
    _SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "header", "aside"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self._in_title = False
        self._skip_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in self._SKIP:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True
        if self._skip_depth == 0 and tag in self._BLOCKS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1
        if self._skip_depth == 0 and tag in self._BLOCKS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        if self._skip_depth == 0:
            self._parts.append(data)

    def paragraphs(self) -> list[str]:
        return [
            normalized for part in "".join(self._parts).splitlines()
            if (normalized := re.sub(r"\s+", " ", part).strip())
        ]


def allowed_url(url: str, allowed_hosts: set[str]) -> bool:
    """Accept only exact allowlisted HTTPS hosts with no credentials or odd port."""
    try:
        parsed = urlsplit(url)
        return (
            parsed.scheme == "https"
            and parsed.hostname is not None
            and parsed.hostname.lower() in allowed_hosts
            and parsed.username is None
            and parsed.password is None
            and parsed.port in (None, 443)
            and not any(char.isspace() or ord(char) < 32 for char in url)
            and "\\" not in url
        )
    except ValueError:
        return False


def assert_public_dns(hostname: str, resolver: Callable[..., object] = socket.getaddrinfo) -> None:
    """Reject loopback/private/link-local DNS answers before every page request."""
    try:
        addresses = resolver(hostname, 443, type=socket.SOCK_STREAM)
    except OSError as error:
        raise WebRetrievalError("Không phân giải được hostname nguồn web") from error
    resolved = {entry[4][0] for entry in addresses}  # type: ignore[index]
    if not resolved:
        raise WebRetrievalError("Hostname nguồn web không có địa chỉ IP")
    for raw_ip in resolved:
        address = ip_address(raw_ip)
        if not address.is_global:
            raise WebRetrievalError("Nguồn web trỏ tới IP private hoặc không định tuyến được")


def canonical_url(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path or "/", parsed.query, ""))


GZIP_MAGIC = bytes([0x1F, 0x8B])


def decode_robots_response(raw: bytes, content_encoding: str | None) -> str:
    """Giải mã robots.txt chịu lỗi máy chủ: gzip không khai báo (tienphong.vn), charset sai kiểu
    ``utf-8,gbk`` (laodong.vn). robots.txt gần như luôn ASCII nên decode UTF-8 có thay thế là an toàn;
    trước đây các lỗi này làm cả trang bị coi là "cấm tải" và bị loại khỏi nguồn."""
    encoding = (content_encoding or "identity").lower().strip()
    try:
        if encoding in {"gzip", "x-gzip"} or raw[:2] == GZIP_MAGIC:
            raw = gzip.decompress(raw)
        elif encoding == "deflate":
            raw = zlib.decompress(raw)
    except (OSError, zlib.error) as error:
        raise WebRetrievalError("Không giải nén được robots.txt") from error
    return raw.decode("utf-8", errors="replace")


def decode_html_response(raw: bytes, content_encoding: str | None, header_charset: str | None) -> str:
    """Decode a bounded HTML response without silently turning compressed bytes into text."""
    encoding = (content_encoding or "identity").lower().strip()
    try:
        if encoding in {"", "identity"}:
            decoded_bytes = raw
        elif encoding in {"gzip", "x-gzip"}:
            decoded_bytes = gzip.decompress(raw)
        elif encoding == "deflate":
            decoded_bytes = zlib.decompress(raw)
        else:
            raise WebRetrievalError(f"Content-Encoding không được hỗ trợ: {encoding}")
    except (OSError, zlib.error) as error:
        raise WebRetrievalError("Không giải nén được nội dung HTML nguồn web") from error

    match = re.search(br"<meta[^>]+charset=[\"']?\s*([a-zA-Z0-9._-]+)", decoded_bytes[:8192], re.I)
    candidates = [
        match.group(1).decode("ascii") if match else None,
        "utf-8",
        header_charset,
    ]
    for charset in dict.fromkeys(candidate for candidate in candidates if candidate):
        try:
            return decoded_bytes.decode(charset)
        except (LookupError, UnicodeDecodeError):
            continue
    raise WebRetrievalError("Không xác định được charset HTML nguồn web")


def _main_content_paragraphs(html: str) -> list[str] | None:
    """Thân bài chính bằng trafilatura (bỏ menu, quảng cáo, bài liên quan) nếu đã cài."""
    try:
        import trafilatura
    except ImportError:
        return None
    text = trafilatura.extract(html, include_comments=False, include_tables=False, favor_precision=True)
    if not text:
        return None
    return [line.strip() for line in text.splitlines() if line.strip()]


def extract_passages(html: str, minimum_chars: int, maximum_chars: int, max_passages: int,
                     query: str | None = None, main_content: bool = False) -> tuple[str, list[str]]:
    """Cắt trang thành passage và trả tối đa ``max_passages`` passage.

    Khi có ``query`` (claim), passage được chọn theo **độ liên quan** với claim
    thay vì lấy các passage đầu trang (thường là sapo/menu/chú thích ảnh).
    ``main_content=True`` dùng trafilatura để chỉ lấy thân bài.
    """
    parser = _PageTextParser()
    parser.feed(html)
    parser.close()
    title = re.sub(r"\s+", " ", parser.title).strip()
    paragraphs = (_main_content_paragraphs(html) if main_content else None) or parser.paragraphs()
    passages: list[str] = []
    seen_passages: set[str] = set()

    def append_unique(passage: str) -> None:
        normalized = re.sub(r"\s+", " ", passage).strip()
        fingerprint = normalized.casefold()
        if len(normalized) >= minimum_chars and fingerprint not in seen_passages:
            seen_passages.add(fingerprint)
            passages.append(normalized[:maximum_chars])

    for paragraph in paragraphs:
        sentences = re.split(r"(?<=[.!?…])\s+", paragraph)
        chunk = ""
        for sentence in sentences:
            candidate = f"{chunk} {sentence}".strip()
            if chunk and len(candidate) > maximum_chars:
                append_unique(chunk)
                chunk = sentence
            else:
                chunk = candidate
        append_unique(chunk)
        if query is None and len(passages) >= max_passages:
            break
    if query is not None and len(passages) > max_passages:
        from src.source_reranker import LexicalSourceScorer

        scores = LexicalSourceScorer().score(query, passages)
        order = sorted(range(len(passages)), key=lambda index: (-scores[index], index))[:max_passages]
        return title, [passages[index] for index in order]
    return title, passages[:max_passages]


def key_fingerprint(api_key: str | None) -> str:
    """Định danh ngắn của API key cho sổ đếm (không đảo ngược được, không lộ key)."""
    return sha256((api_key or "").encode("utf-8")).hexdigest()[:12]


class UsageLedger:
    """Small local, process-safe counter. It never stores claims, keys or page text.

    Hạn mức tháng và giới hạn/phút được đếm **riêng cho từng API key** (theo ``key_fingerprint``) vì hạn
    mức của Tavily gắn với key: đổi key thì đếm lại từ 0. Sổ định dạng cũ (một bộ đếm chung) được giữ
    dưới tên ``legacy``."""

    def __init__(self, directory: Path, per_minute: int, monthly_budget: int, account: str = "default") -> None:
        self.path = directory / "usage.json"
        self.lock_path = directory / "usage.lock"
        self.per_minute = per_minute
        self.monthly_budget = monthly_budget
        self.account = account
        directory.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _lock(self):
        deadline = time.monotonic() + 2.0
        descriptor: int | None = None
        while descriptor is None:
            try:
                descriptor = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise WebRetrievalError("Không khóa được bộ đếm quota web")
                time.sleep(0.05)
        try:
            yield
        finally:
            os.close(descriptor)
            self.lock_path.unlink(missing_ok=True)

    def reserve(self) -> None:
        now = datetime.now(timezone.utc)
        month = now.strftime("%Y-%m")
        with self._lock():
            try:
                book = json.loads(self.path.read_text(encoding="utf-8"))
            except FileNotFoundError:
                book = {}
            if "accounts" not in book:  # sổ cũ: một bộ đếm chung cho mọi key
                book = {"accounts": {"legacy": book} if book else {}}
            state = book["accounts"].get(self.account, {})
            if state.get("month") != month:
                state = {"month": month, "requests": 0, "recent": []}
            recent = [stamp for stamp in state.get("recent", []) if now.timestamp() - float(stamp) < 60]
            if state["requests"] >= self.monthly_budget:
                raise WebLimitError("Đã dùng hết ngân sách credit web của tháng", "budget_exhausted")
            if len(recent) >= self.per_minute:
                raise WebLimitError("Đã chạm giới hạn request web mỗi phút", "rate_limited")
            state["requests"] += 1
            state["recent"] = recent + [now.timestamp()]
            book["accounts"][self.account] = state
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(book, separators=(",", ":")), encoding="utf-8")
            temporary.replace(self.path)


class WebRetriever:
    """Tavily search + guarded page fetch + passage extraction for approved hosts."""

    def __init__(self, config: dict[str, object], api_key: str | None = None,
                 provider_request: Callable[[dict[str, object], str, float], dict[str, object]] | None = None,
                 page_fetcher: Callable[[str, float], tuple[str, str]] | None = None,
                 robots_fetcher: Callable[[str, float], str] | None = None) -> None:
        self.config = config
        self.provider = config["provider"]  # type: ignore[assignment]
        self.limits = config["limits"]  # type: ignore[assignment]
        self.policy = config["source_policy"]  # type: ignore[assignment]
        self.cache = config["cache"]  # type: ignore[assignment]
        self.extraction = config["extraction"]  # type: ignore[assignment]
        self.enabled = bool(config["enabled"])
        self.allowed_sources = {entry["host"]: entry for entry in self.policy["allowlist"]}  # type: ignore[index]
        self.api_key = api_key if api_key is not None else os.environ.get(self.provider["api_key_env"])  # type: ignore[index]
        self.provider_request = provider_request or self._request_tavily
        self.page_fetcher = page_fetcher or self._fetch_page
        self.robots_fetcher = robots_fetcher or self._fetch_robots
        self.ledger = UsageLedger(
            Path(self.cache["directory"]),  # type: ignore[index]
            int(self.limits["requests_per_minute"]),  # type: ignore[index]
            int(self.limits["monthly_credit_budget"]),  # type: ignore[index]
            account=key_fingerprint(self.api_key),
        )
        self.last_status = "not_run"
        # Vết lần search gần nhất (truy vấn, URL provider trả, kết quả tải từng trang) – để phân tích lỗi sau,
        # không chứa key; xem _new_trace().
        self.last_trace: dict[str, object] = self._new_trace()
        # robots.txt theo host, chỉ lưu khi tải THÀNH CÔNG (lỗi tạm thời được thử lại lần sau).
        self._robots_cache: dict[str, str] = {}
        self.last_documents: dict[str, list[str]] = {}

    def article_passages(self, document_id: str) -> list[str]:
        """Mọi đoạn của bài (lần search gần nhất), theo thứ tự trong trang."""
        return list(self.last_documents.get(document_id, []))

    def _fetch_robots(self, page_url: str, timeout: float) -> str:
        """Tải robots.txt của host được duyệt. Đi theo tối đa 5 lần chuyển hướng như RFC 9309 (vd. qdnd.vn →
        www.qdnd.vn, nld.com.vn → tuoitre.vn/nld) nhưng mỗi bước vẫn phải nằm trong allowlist và là IP công khai."""
        parsed = urlsplit(page_url)
        current = urlunsplit(("https", parsed.netloc, "/robots.txt", "", ""))
        for _ in range(6):
            if not allowed_url(current, set(self.allowed_sources)):
                raise WebRetrievalError("robots.txt nằm ngoài allowlist")
            assert_public_dns(urlsplit(current).hostname or "")
            request = Request(current, headers={"User-Agent": "VietnameseFactChecking/1.0", "Accept-Encoding": "identity"})
            try:
                with _opener().open(request, timeout=timeout) as response:
                    if not response.headers.get_content_type().startswith("text/"):
                        raise WebRetrievalError("robots.txt không phải văn bản")
                    raw = response.read(int(self.policy["max_robots_bytes"]) + 1)  # type: ignore[index]
                    if len(raw) > int(self.policy["max_robots_bytes"]):  # type: ignore[index]
                        raise WebRetrievalError("robots.txt vượt giới hạn kích thước")
                    return decode_robots_response(raw, response.headers.get("Content-Encoding"))
            except HTTPError as error:
                if error.code == 404:
                    return ""
                if error.code in {301, 302, 303, 307, 308} and error.headers.get("Location"):
                    current = canonical_url(urljoin(current, error.headers["Location"]))
                    continue
                raise WebRetrievalError("Không tải được robots.txt") from error
            except (URLError, TimeoutError, OSError, HTTPException, UnicodeDecodeError, LookupError) as error:
                raise WebRetrievalError("Không tải hoặc giải mã được robots.txt") from error
        raise WebRetrievalError("robots.txt chuyển hướng quá nhiều lần")

    def _robots_allow(self, page_url: str, timeout: float) -> bool:
        if not bool(self.policy.get("obey_robots_txt", True)):
            return True
        try:
            host = (urlsplit(page_url).hostname or "").lower()
            if host not in self._robots_cache:
                self._robots_cache[host] = self.robots_fetcher(page_url, timeout)
            robots = self._robots_cache[host]
            parser = RobotFileParser()
            parser.parse(robots.splitlines())
            return parser.can_fetch("VietnameseFactChecking", page_url)
        except WebRetrievalError:
            if self.policy.get("robots_failure", "deny") == "allow":
                return True
            raise  # không tải được robots.txt = lỗi mạng (tạm thời), khác với robots.txt chặn trang

    def _request_tavily(self, payload: dict[str, object], api_key: str, timeout: float) -> dict[str, object]:
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            self.provider["endpoint"], body, method="POST",  # type: ignore[index]
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
        try:
            with _opener().open(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            raise WebRetrievalError("Search provider không trả kết quả hợp lệ") from error

    def _fetch_page(self, url: str, timeout: float) -> tuple[str, str]:
        current = canonical_url(url)
        for _ in range(int(self.extraction["max_redirects"]) + 1):  # type: ignore[index]
            if not allowed_url(current, set(self.allowed_sources)):
                raise WebRetrievalError("Redirect đi tới nguồn ngoài allowlist")
            assert_public_dns(urlsplit(current).hostname or "")
            request = Request(current, headers={"User-Agent": "VietnameseFactChecking/1.0", "Accept-Encoding": "gzip, deflate"})
            try:
                with _opener().open(request, timeout=timeout) as response:
                    if not response.headers.get_content_type().startswith("text/html"):
                        raise WebRetrievalError("Nguồn web không trả HTML")
                    raw = response.read(int(self.extraction["max_page_bytes"]) + 1)  # type: ignore[index]
                    if len(raw) > int(self.extraction["max_page_bytes"]):  # type: ignore[index]
                        raise WebRetrievalError("Trang web vượt giới hạn kích thước")
                    return current, decode_html_response(
                        raw,
                        response.headers.get("Content-Encoding"),
                        response.headers.get_content_charset(),
                    )
            except HTTPError as error:
                if error.code not in {301, 302, 303, 307, 308} or not error.headers.get("Location"):
                    raise WebRetrievalError("Không tải được trang nguồn web") from error
                current = canonical_url(urljoin(current, error.headers["Location"]))
            except (URLError, TimeoutError, OSError, HTTPException) as error:  # vd. IncompleteRead, ConnectionReset
                raise WebRetrievalError("Hết thời gian hoặc không tải được trang nguồn web") from error
        raise WebRetrievalError("Trang web chuyển hướng quá nhiều lần")

    @staticmethod
    def _new_trace() -> dict[str, object]:
        # pages[].outcome: used | no_passages | robots_blocked | fetch_failed | not_allowed | duplicate | not_read
        return {"queries": [], "provider_error": None, "search_results": [], "pages": []}

    @staticmethod
    def _error_text(error: BaseException) -> str:
        cause = error.__cause__
        return f"{error} ({type(cause).__name__}: {cause})" if cause is not None else str(error)

    def search(self, claim: str, top_k: int = 3) -> list[RetrievedEvidence]:
        if top_k < 1:
            raise ValueError("top_k phải lớn hơn 0")
        self.last_trace = trace = self._new_trace()
        if not self.enabled:
            self.last_status = "disabled"
            return []
        if not self.api_key:
            self.last_status = "missing_api_key"
            return []
        # Nhiều truy vấn (claim gốc + từ khóa/thực thể) khi config cho phép
        # nhiều request/claim; mỗi request vẫn đi qua ledger ngân sách.
        from src.query_generation import generate_queries

        query_count = max(1, int(self.limits.get("requests_per_claim", 1)))  # type: ignore[union-attr]
        queries = [query.text for query in generate_queries(claim)][:query_count]
        batches: list[list[object]] = []
        provider_failed = False
        limit_status: str | None = None
        for query in queries:
            payload = {
                "query": query[:400],
                "search_depth": self.provider["search_depth"],
                "topic": self.provider["topic"],
                "max_results": self.provider["max_results"],
                "include_domains": sorted(self.allowed_sources),
                "include_answer": False,
                "include_raw_content": False,
                "auto_parameters": False,
            }
            try:
                self.ledger.reserve()
                response = self.provider_request(payload, self.api_key, float(self.limits["timeout_seconds"]))
            except WebLimitError as error:
                provider_failed, limit_status = True, error.status
                trace["provider_error"] = self._error_text(error)
                break
            except WebRetrievalError as error:
                provider_failed = True
                trace["provider_error"] = self._error_text(error)
                break
            trace["queries"].append(payload["query"])  # type: ignore[union-attr]
            batch = response.get("results", [])
            if not isinstance(batch, list):
                self.last_status = "invalid_provider_response"
                return []
            for rank, item in enumerate(batch):
                if isinstance(item, dict):
                    trace["search_results"].append({  # type: ignore[union-attr]
                        "query_index": len(batches), "rank": rank, "url": item.get("url"),
                        "title": item.get("title"), "score": item.get("score"),
                    })
            batches.append(batch)
        # Xen kẽ kết quả các truy vấn để trang của truy vấn từ khóa cũng được đọc.
        results = [batch[i] for i in range(max((len(b) for b in batches), default=0)) for batch in batches if i < len(batch)]
        if provider_failed and not results:
            self.last_status = limit_status or "local_only"
            return []
        return self.read_pages(claim, results, top_k)

    def read_pages(self, claim: str, results: list[object], top_k: int) -> list[RetrievedEvidence]:
        """Tải và cắt các trang provider trả (không gọi provider – không tốn credit).

        Ghi ``last_documents``: document_id → mọi đoạn của bài theo thứ tự trong trang (cho bản tóm tắt cả bài);
        kết quả trả về chỉ gồm ``top_k`` đoạn liên quan nhất.
        """
        trace = self.last_trace
        self.last_documents = {}
        # Lấy passage từ NHIỀU trang (trước đây dừng ngay sau trang đầu vì
        # top_k = số passage/trang), rồi xếp hạng toàn cục theo độ liên quan.
        max_pages = int(self.extraction.get("max_pages", len(results) or 1))  # type: ignore[union-attr]
        main_content = str(self.extraction.get("main_content_extractor", "")) == "trafilatura"  # type: ignore[union-attr]
        pages_used = 0
        pages_failed = 0  # trang tải lỗi (timeout, robots, redirect) – khác với trang tải được nhưng không có đoạn
        collected: list[RetrievedEvidence] = []
        seen_urls: set[str] = set()
        pages = trace["pages"]
        for rank, result in enumerate(results):
            if not isinstance(result, dict) or not isinstance(result.get("url"), str):
                continue
            url = canonical_url(result["url"])
            page: dict[str, object] = {"url": url}
            pages.append(page)  # type: ignore[union-attr]
            if url in seen_urls:
                page["outcome"] = "duplicate"
                continue
            if not allowed_url(url, set(self.allowed_sources)):
                page["outcome"] = "not_allowed"
                continue
            if pages_used >= max_pages:
                page["outcome"] = "not_read"
                continue
            seen_urls.add(url)
            try:
                if not self._robots_allow(url, float(self.limits["timeout_seconds"])):
                    page["outcome"] = "robots_blocked"
                    continue  # robots.txt chặn: chính sách của trang, không tính là lỗi tải
                final_url, html = self.page_fetcher(url, float(self.limits["timeout_seconds"]))
                final_url = canonical_url(final_url)
                if not allowed_url(final_url, set(self.allowed_sources)):
                    raise WebRetrievalError("Trang cuối cùng ngoài allowlist")
                title, passages = extract_passages(
                    html,
                    int(self.extraction["minimum_passage_chars"]),
                    int(self.extraction["maximum_passage_chars"]),
                    int(self.extraction["max_passages_per_page"]),
                    query=claim,
                    main_content=main_content,
                )
                _, article = extract_passages(
                    html, int(self.extraction["minimum_passage_chars"]), int(self.extraction["maximum_passage_chars"]),
                    int(self.extraction.get("max_article_passages", 60)), main_content=main_content,
                )
            except WebRetrievalError as error:
                pages_failed += 1
                page.update(outcome="fetch_failed", error=self._error_text(error))
                continue
            page["final_url"] = final_url
            if not passages:
                page["outcome"] = "no_passages"
                continue
            pages_used += 1
            source = self.allowed_sources[urlsplit(final_url).hostname or ""]
            fetched_at = datetime.now(timezone.utc).isoformat()
            document_id = f"web-{sha256(final_url.encode('utf-8')).hexdigest()[:16]}"
            from src.source_reranker import LexicalSourceScorer

            relevance = LexicalSourceScorer().score(claim, passages)
            self.last_documents[document_id] = article or passages
            page.update(outcome="used", title=title or result.get("title"), passages=len(passages),
                        max_relevance=round(max(relevance), 4))
            for passage_index, passage in enumerate(passages):
                evidence = Evidence(
                    document_id=document_id,
                    passage_id=f"{document_id}-p{passage_index + 1:02d}",
                    content=passage,
                    source=str(source["name"]),
                    url=final_url,
                    domain=urlsplit(final_url).hostname or "",
                    article_id=document_id,
                    title=title or str(result.get("title") or ""),
                    retrieved_at=fetched_at,
                    source_type=SOURCE_TYPES[str(source["category"])],
                    authority_score=AUTHORITY[str(source["category"])],
                )
                # Điểm dương, ưu tiên độ liên quan; hạng của provider chỉ phá hòa.
                score = 0.001 + relevance[passage_index] - rank * 1e-5 - passage_index * 1e-7
                collected.append(RetrievedEvidence(evidence, score))
        collected.sort(key=lambda item: (-item.score, item.evidence.passage_id))
        collected = collected[:top_k]
        if collected:
            self.last_status = "ok"
        elif pages_failed and not pages_used:
            self.last_status = "pages_unreachable"
        else:
            self.last_status = "no_eligible_passages"
        return collected
