"""Allowlisted web retrieval for W3-05.

The retriever is intentionally separate from the local BM25 pipeline.  It only
returns passages fetched from approved hosts; fusion and end-to-end evaluation
remain later retrieval tasks.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timezone
import gzip
from hashlib import sha256
from html.parser import HTMLParser
from ipaddress import ip_address
import json
import os
from pathlib import Path
import re
import socket
import time
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.robotparser import RobotFileParser
import zlib

from src.schemas import Evidence, RetrievedEvidence


class WebRetrievalError(RuntimeError):
    """A controlled web-retrieval failure; callers should fall back to local."""


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
        # Tín hiệu ngày đăng: meta tags (name/property/itemprop -> content),
        # thuộc tính datetime của <time>, và các blob JSON-LD (<script ld+json>).
        self.meta: dict[str, str] = {}
        self.time_values: list[str] = []
        self.ldjson_blobs: list[str] = []
        self._in_ldjson = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "meta":
            attr = {k.lower(): (v or "") for k, v in attrs}
            key = attr.get("property") or attr.get("name") or attr.get("itemprop")
            content = attr.get("content")
            if key and content:
                # Giữ tín hiệu đầu tiên cho mỗi khóa (thường là tag chuẩn ở <head>).
                self.meta.setdefault(key.lower().strip(), content.strip())
        if tag == "time":
            attr = {k.lower(): (v or "") for k, v in attrs}
            # Bỏ <time> trong header/nav/footer/aside: đó là đồng hồ 'hôm nay' của trang, không phải ngày bài.
            if attr.get("datetime") and self._skip_depth == 0:
                self.time_values.append(attr["datetime"].strip())
        if tag == "script":
            attr = {k.lower(): (v or "") for k, v in attrs}
            if "ld+json" in attr.get("type", "").lower():
                self._in_ldjson = True
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
        if tag == "script":
            self._in_ldjson = False
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1
        if self._skip_depth == 0 and tag in self._BLOCKS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        if self._in_ldjson:
            self.ldjson_blobs.append(data)
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


def extract_passages(html: str, minimum_chars: int, maximum_chars: int, max_passages: int) -> tuple[str, list[str]]:
    parser = _PageTextParser()
    parser.feed(html)
    parser.close()
    title = re.sub(r"\s+", " ", parser.title).strip()
    passages: list[str] = []
    seen_passages: set[str] = set()

    def append_unique(passage: str) -> None:
        normalized = re.sub(r"\s+", " ", passage).strip()
        fingerprint = normalized.casefold()
        if len(normalized) >= minimum_chars and fingerprint not in seen_passages:
            seen_passages.add(fingerprint)
            passages.append(normalized[:maximum_chars])

    for paragraph in parser.paragraphs():
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
        if len(passages) >= max_passages:
            break
    return title, passages[:max_passages]


# --- Trích xuất ngày đăng (published_at) cho bằng chứng web -------------------
#
# Bằng chứng web trước đây chỉ có ``retrieved_at`` (thời điểm ta tải trang), nên
# không thể neo thời gian: một bài 2023 trông "mới" như bài hôm nay. Ở đây ta rút
# NGÀY ĐĂNG thật từ trang, theo thứ tự tín hiệu đáng tin cậy giảm dần. Chỉ đọc,
# không bịa: không có tín hiệu hợp lệ thì trả None (verifier/neo thời gian tự xử).

# Thứ tự ưu tiên khóa meta: tín hiệu "published" chuẩn trước, "modified" sau cùng.
_PUBLISHED_META_KEYS = (
    "article:published_time",
    "datepublished",
    "og:published_time",
    "pubdate",
    "publishdate",
    "publish-date",
    "publication_date",
    "parsely-pub-date",
    "sailthru.date",
    "dc.date.issued",
    "dc.date",
    "date",
    "article:modified_time",
    "og:updated_time",
    "lastmod",
)

_DMY = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b")
_YMD = re.compile(r"\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b")


def _normalize_date(raw: str | None) -> str | None:
    """Chuẩn hóa một chuỗi ngày về ISO (giữ nguyên độ chính xác sẵn có).

    Chấp nhận ISO 8601 (có/không giờ, có 'Z'), dd/mm/yyyy và yyyy/mm/dd. Trả None
    nếu không parse được hoặc năm vô lý (ngoài 2000..năm sau)."""
    if not raw:
        return None
    text = raw.strip()
    if not text:
        return None
    parsed: datetime | None = None
    # 1) ISO 8601 trực tiếp (ưu tiên vì giữ cả timezone/giờ).
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        parsed = None
    # 2) yyyy-mm-dd / yyyy/mm/dd ở đầu chuỗi (một số trang gắn thêm chữ phía sau).
    if parsed is None:
        match = _YMD.search(text)
        if match:
            year, month, day = (int(g) for g in match.groups())
            try:
                parsed = datetime(year, month, day)
            except ValueError:
                parsed = None
    # 3) dd/mm/yyyy (định dạng VN phổ biến).
    if parsed is None:
        match = _DMY.search(text)
        if match:
            day, month, year = (int(g) for g in match.groups())
            try:
                parsed = datetime(year, month, day)
            except ValueError:
                parsed = None
    if parsed is None:
        return None
    upper = datetime.now(parsed.tzinfo).year + 1 if parsed.tzinfo else datetime.now().year + 1
    if not (2000 <= parsed.year <= upper):
        return None
    return parsed.isoformat()


def _ldjson_dates(blobs: list[str]) -> list[str]:
    """Rút mọi giá trị datePublished/dateCreated từ các blob JSON-LD."""
    dates: list[str] = []
    for blob in blobs:
        text = blob.strip()
        if not text:
            continue
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            # Vài trang chèn nhiều object nối nhau; bắt bằng regex làm phương án dự phòng.
            for match in re.finditer(r'"date(?:Published|Created)"\s*:\s*"([^"]+)"', text):
                dates.append(match.group(1))
            continue

        def walk(node: object) -> None:
            if isinstance(node, dict):
                for field in ("datePublished", "dateCreated"):
                    value = node.get(field)
                    if isinstance(value, str):
                        dates.append(value)
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(data)
    return dates


def extract_published_at(html: str) -> str | None:
    """Trả ngày đăng (ISO) tốt nhất tìm được trên trang, hoặc None.

    Thứ tự: meta tag chuẩn -> JSON-LD datePublished -> thẻ <time datetime=...>.
    Luôn ưu tiên tín hiệu 'published' hơn 'modified'."""
    parser = _PageTextParser()
    parser.feed(html)
    parser.close()

    for key in _PUBLISHED_META_KEYS:
        normalized = _normalize_date(parser.meta.get(key))
        if normalized:
            return normalized
    for candidate in _ldjson_dates(parser.ldjson_blobs):
        normalized = _normalize_date(candidate)
        if normalized:
            return normalized
    for candidate in parser.time_values:
        normalized = _normalize_date(candidate)
        if normalized:
            return normalized
    return None


class UsageLedger:
    """Small local, process-safe counter. It never stores claims, keys or page text."""

    def __init__(self, directory: Path, per_minute: int, monthly_budget: int) -> None:
        self.path = directory / "usage.json"
        self.lock_path = directory / "usage.lock"
        self.per_minute = per_minute
        self.monthly_budget = monthly_budget
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
                state = json.loads(self.path.read_text(encoding="utf-8"))
            except FileNotFoundError:
                state = {}
            if state.get("month") != month:
                state = {"month": month, "requests": 0, "recent": []}
            recent = [stamp for stamp in state.get("recent", []) if now.timestamp() - float(stamp) < 60]
            if state["requests"] >= self.monthly_budget:
                raise WebRetrievalError("Đã dùng hết ngân sách credit web của tháng")
            if len(recent) >= self.per_minute:
                raise WebRetrievalError("Đã chạm giới hạn request web mỗi phút")
            state["requests"] += 1
            state["recent"] = recent + [now.timestamp()]
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(state, separators=(",", ":")), encoding="utf-8")
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
        )
        self.last_status = "not_run"

    def _fetch_robots(self, page_url: str, timeout: float) -> str:
        """Fetch robots.txt from the exact approved host without redirects."""
        parsed = urlsplit(page_url)
        robots_url = urlunsplit(("https", parsed.netloc, "/robots.txt", "", ""))
        if not allowed_url(robots_url, set(self.allowed_sources)):
            raise WebRetrievalError("robots.txt nằm ngoài allowlist")
        assert_public_dns(parsed.hostname or "")
        request = Request(robots_url, headers={"User-Agent": "VietnameseFactChecking/1.0", "Accept-Encoding": "identity"})
        try:
            with build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
                if not response.headers.get_content_type().startswith("text/"):
                    raise WebRetrievalError("robots.txt không phải văn bản")
                raw = response.read(int(self.policy["max_robots_bytes"]) + 1)  # type: ignore[index]
                if len(raw) > int(self.policy["max_robots_bytes"]):  # type: ignore[index]
                    raise WebRetrievalError("robots.txt vượt giới hạn kích thước")
                charset = response.headers.get_content_charset() or "utf-8"
                return raw.decode(charset)
        except HTTPError as error:
            if error.code == 404:
                return ""
            raise WebRetrievalError("Không tải được robots.txt") from error
        except (URLError, TimeoutError, UnicodeDecodeError, LookupError) as error:
            raise WebRetrievalError("Không tải hoặc giải mã được robots.txt") from error

    def _robots_allow(self, page_url: str, timeout: float) -> bool:
        if not bool(self.policy.get("obey_robots_txt", True)):
            return True
        try:
            robots = self.robots_fetcher(page_url, timeout)
            parser = RobotFileParser()
            parser.parse(robots.splitlines())
            return parser.can_fetch("VietnameseFactChecking", page_url)
        except WebRetrievalError:
            if self.policy.get("robots_failure", "deny") == "allow":
                return True
            return False

    def _request_tavily(self, payload: dict[str, object], api_key: str, timeout: float) -> dict[str, object]:
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            self.provider["endpoint"], body, method="POST",  # type: ignore[index]
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
        try:
            with build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
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
                with build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
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
            except (URLError, TimeoutError) as error:
                raise WebRetrievalError("Hết thời gian hoặc không tải được trang nguồn web") from error
        raise WebRetrievalError("Trang web chuyển hướng quá nhiều lần")

    def search(self, claim: str, top_k: int = 3) -> list[RetrievedEvidence]:
        """Search without a publication-date restriction."""
        return self._search(claim, top_k)

    def search_time_window(self, claim: str, top_k: int, start_date: date,
                           end_date: date, *, language: str | None = None) -> list[RetrievedEvidence]:
        """Search fresh news only, using Tavily's server-side date filter.

        The page is still fetched and its own publication metadata is extracted;
        the provider's date is used only to avoid spending candidates on pages
        outside the requested window.
        """
        if start_date > end_date:
            raise ValueError("start_date phải không muộn hơn end_date")
        options: dict[str, object] = {
            "topic": "news",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "include_published_date": True,
            "filter_by_published_date": True,
        }
        if language:
            options["language"] = language
            options["filter_by_language"] = True
        return self._search(claim, top_k, options)

    def _search(self, claim: str, top_k: int,
                provider_overrides: dict[str, object] | None = None) -> list[RetrievedEvidence]:
        if top_k < 1:
            raise ValueError("top_k phải lớn hơn 0")
        if not self.enabled:
            self.last_status = "disabled"
            return []
        if not self.api_key:
            self.last_status = "missing_api_key"
            return []
        payload = {
            "query": claim,
            "search_depth": self.provider["search_depth"],
            "topic": self.provider["topic"],
            "max_results": self.provider["max_results"],
            "include_domains": sorted(self.allowed_sources),
            "include_answer": False,
            "include_raw_content": False,
            "auto_parameters": False,
        }
        if provider_overrides:
            payload.update(provider_overrides)
        try:
            self.ledger.reserve()
            response = self.provider_request(payload, self.api_key, float(self.limits["timeout_seconds"]))
        except WebRetrievalError:
            self.last_status = "local_only"
            return []
        results = response.get("results", [])
        if not isinstance(results, list):
            self.last_status = "invalid_provider_response"
            return []
        collected: list[RetrievedEvidence] = []
        seen_urls: set[str] = set()
        for rank, result in enumerate(results):
            if len(collected) >= top_k:
                break
            if not isinstance(result, dict) or not isinstance(result.get("url"), str):
                continue
            url = canonical_url(result["url"])
            if url in seen_urls or not allowed_url(url, set(self.allowed_sources)):
                continue
            seen_urls.add(url)
            try:
                if not self._robots_allow(url, float(self.limits["timeout_seconds"])):
                    raise WebRetrievalError("robots.txt không cho phép tải trang nguồn")
                final_url, html = self.page_fetcher(url, float(self.limits["timeout_seconds"]))
                final_url = canonical_url(final_url)
                if not allowed_url(final_url, set(self.allowed_sources)):
                    raise WebRetrievalError("Trang cuối cùng ngoài allowlist")
                title, passages = extract_passages(
                    html,
                    int(self.extraction["minimum_passage_chars"]),
                    int(self.extraction["maximum_passage_chars"]),
                    int(self.extraction["max_passages_per_page"]),
                )
                published_at = extract_published_at(html)
            except WebRetrievalError:
                continue
            source = self.allowed_sources[urlsplit(final_url).hostname or ""]
            base_score = float(result.get("score", 1.0))
            fetched_at = datetime.now(timezone.utc).isoformat()
            document_id = f"web-{sha256(final_url.encode('utf-8')).hexdigest()[:16]}"
            for passage_index, passage in enumerate(passages):
                if len(collected) >= top_k:
                    break
                evidence = Evidence(
                    document_id=document_id,
                    passage_id=f"{document_id}-p{passage_index + 1:02d}",
                    content=passage,
                    source=str(source["name"]),
                    url=final_url,
                    domain=urlsplit(final_url).hostname or "",
                    article_id=document_id,
                    title=title or str(result.get("title") or ""),
                    published_at=published_at,
                    retrieved_at=fetched_at,
                    source_type={"government": "government", "international": "international_org", "press": "news"}[source["category"]],
                    authority_score={"government": 0.95, "international": 0.95, "press": 0.7}[source["category"]],
                )
                collected.append(RetrievedEvidence(evidence, base_score - rank * 0.001 - passage_index * 0.0001))
        self.last_status = "ok" if collected else "no_eligible_passages"
        return collected
