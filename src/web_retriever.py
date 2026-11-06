"""Allowlisted web retrieval for W3-05.

The retriever is intentionally separate from the local BM25 pipeline.  It only
returns passages fetched from approved hosts; fusion and end-to-end evaluation
remain later retrieval tasks.
"""

from __future__ import annotations

from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import gzip
from hashlib import sha256
from html.parser import HTMLParser
from http.client import HTTPException
from ipaddress import ip_address
import json
from math import isfinite
import os
from pathlib import Path
import re
import socket
import time
from threading import Lock
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.robotparser import RobotFileParser
import zlib

from src.schemas import Evidence, RetrievedEvidence
from src.query_enrichment import publication_date
from src.news_discovery import NewsDiscovery
from src.topical_rerank import eligible, relevance
from src.verbatim import verbatim_span
from src.evidence_focus import split_sentences
from src.evidence_focus import sentence_score


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
        self._stack: list[tuple[str, bool, bool]] = []
        self._content_parts: list[str] = []
        # Tín hiệu ngày đăng: meta tags (name/property/itemprop -> content),
        # thuộc tính datetime của <time>, và các blob JSON-LD (<script ld+json>).
        self.meta: dict[str, str] = {}
        self.time_values: list[str] = []
        self.ldjson_blobs: list[str] = []
        self._in_ldjson = False
        self.headlines: list[str] = []
        self._headline_parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attr = {k.lower(): (v or "") for k, v in attrs}
        marker = attr.get("class", "") + " " + attr.get("id", "")
        skipped = tag in self._SKIP or bool(re.search(r"sidebar|related|recommend|tin-lien-quan|box-tin", marker, re.I))
        main = tag in {"article", "main"} or bool(re.search(r"article-body|article-content|detail-content|detail__content|contentdetail", marker, re.I))
        if tag not in {"meta", "link", "img", "br", "hr", "input", "source", "wbr", "area", "base", "embed", "param", "track"}:
            self._stack.append((tag, skipped, main))
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
        if skipped:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True
        if tag == 'h1' and self._skip_depth == 0:
            self._headline_parts = []
        if self._skip_depth == 0 and tag in self._BLOCKS:
            self._parts.append("\n")
            self._content_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        if tag == "script":
            self._in_ldjson = False
        if tag == 'h1' and self._headline_parts is not None:
            self.headlines.append(''.join(self._headline_parts).strip())
            self._headline_parts = None
        for index in range(len(self._stack) - 1, -1, -1):
            if self._stack[index][0] == tag:
                del self._stack[index:]
                break
        self._skip_depth = sum(entry[1] for entry in self._stack)
        if self._skip_depth == 0 and tag in self._BLOCKS:
            self._parts.append("\n")
            self._content_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._headline_parts is not None and self._skip_depth == 0:
            self._headline_parts.append(data)
        if self._in_title:
            self.title += data
        if self._in_ldjson:
            self.ldjson_blobs.append(data)
        if self._skip_depth == 0:
            self._parts.append(data)
            if any(entry[2] for entry in self._stack):
                self._content_parts.append(data)

    def paragraphs(self, prefer_content: bool = False) -> list[str]:
        parts = self._content_parts if prefer_content and "".join(self._content_parts).strip() else self._parts
        return [
            normalized for part in "".join(parts).splitlines()
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


def extract_passages(html: str, minimum_chars: int, maximum_chars: int, max_passages: int,
                     query: str | None = None) -> tuple[str, list[str]]:
    parser = _PageTextParser()
    parser.feed(html)
    parser.close()
    title = re.sub(r"\s+", " ", parser.title).strip()
    passages: list[str] = []
    seen_passages: set[str] = set()

    def append_unique(passage: str) -> None:
        normalized = re.sub(r"\s+", " ", passage).strip()
        fingerprint = normalized.casefold()
        exact = query is not None and verbatim_span(query, normalized) is not None
        if (len(normalized) >= minimum_chars or exact) and fingerprint not in seen_passages:
            seen_passages.add(fingerprint)
            passages.append(normalized[:maximum_chars])

    paragraphs = parser.paragraphs(prefer_content=True)
    # The standfirst is sometimes outside <article>, but is still publisher text.
    description = parser.meta.get("og:description") or parser.meta.get("description")
    if query and description and not any(description.strip() in p for p in paragraphs):
        paragraphs.insert(0, description)
    headline = parser.headlines[0] if parser.headlines else parser.meta.get('og:title')
    if query and headline and not any(headline in p for p in paragraphs):
        paragraphs.insert(0, headline)
    for paragraph in paragraphs:
        sentences = split_sentences(paragraph)
        if query:
            # Do not bury a copied sentence inside a longer chunk, or discard it
            # solely because it is shorter than the generic 120-character floor.
            for sentence in sentences:
                if verbatim_span(query, sentence) is not None:
                    append_unique(sentence)
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
    if query:
        # A title/standfirst claim can contain several facts spread over adjacent
        # paragraphs. Keep their original order in bounded context windows.
        for index, paragraph in enumerate(paragraphs):
            context = paragraph
            for following in paragraphs[index + 1:index + 5]:
                if len(context) + len(following) + 1 > maximum_chars:
                    break
                context += " " + following
                append_unique(context)
        passages.sort(key=lambda passage: (verbatim_span(query, passage) is None, -relevance(query, passage)))
    return title, passages[:max_passages]


def search_queries(claim: str) -> list[str]:
    """Bounded alternatives: full claim, short lead, distinctive content terms.

    No LLM rewrite: negations, numbers and names remain in the original claim
    used to rank passages and verify. These variants only discover candidate URLs.
    """
    plain = re.sub(r"\s+ngày\s+\d{2}/\d{2}/\d{4}$", "", claim).strip()
    # normalize_text has already collapsed title/standfirst newlines in the UI.
    lead = re.split(r"(?<=[.!?…])\s+|(?=\bMỗi\b)", plain, maxsplit=1)[0].strip()
    lead = " ".join(lead.split()[:24])
    from src.topical_rerank import _STOPWORDS
    terms = list(dict.fromkeys(word for word in re.findall(r"\d+(?:[.,]\d+)*%?|[^\W\d_]+", plain)
                              if word.casefold() not in _STOPWORDS))
    keywords = " ".join(terms[:22])
    return list(dict.fromkeys(q for q in (claim.strip(), lead, keywords) if q))


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
    if not isinstance(raw, str) or not raw:
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
    if parsed is None:
        try:
            parsed = parsedate_to_datetime(text)
        except (ValueError, TypeError, OverflowError):
            pass
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
    # Some Vietnamese publishers display a publication stamp in page text
    # without machine-readable metadata (e.g. Petrolimex's "12:00 SA @ ...").
    # Anchor to the timestamp so dates in the article body are not mistaken
    # for the publication date.
    stamp = re.compile(
        r"\b\d{1,2}:\d{2}\s*(?:SA|CH)\s*@[^\n]{0,60}?-\s*"
        r"(\d{1,2})\s+tháng\s+(\d{1,2}),?\s+(\d{4})\b",
        re.IGNORECASE,
    )
    for paragraph in parser.paragraphs():
        match = stamp.search(paragraph)
        if match:
            day, month, year = map(int, match.groups())
            normalized = _normalize_date(f"{year:04d}-{month:02d}-{day:02d}")
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
                 robots_fetcher: Callable[[str, float], str] | None = None,
                 feed_fetcher: Callable[[str, float], tuple[str, str]] | None = None) -> None:
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
        self.last_attempts: list[dict[str, object]] = []
        self.last_candidates: list[dict[str, object]] = []
        self.last_error: str | None = None
        self._page_cache: dict[str, tuple[str, str] | WebRetrievalError] = {}
        self._robots_cache: dict[str, tuple[float, str | None]] = {}
        self._robots_locks: dict[str, Lock] = {}
        self._provider_count = 0
        self.discovery = NewsDiscovery(config.get('discovery', {}), feed_fetcher or self._fetch_feed,
                                       lambda url: allowed_url(url, set(self.allowed_sources)), _normalize_date)

    def _prefetch_pages(self, results: list, claim: str) -> None:
        fetching = self.config.get('fetching', {})
        # Reserve budget for later queries. Lightweight snippet scoring only
        # chooses which pages to fetch; snippets never become evidence.
        ranked_results = sorted((r for r in results if isinstance(r, dict)),
                                key=lambda r: -sentence_score(claim, str(r.get('title') or '') + ' ' + str(r.get('content') or '')))
        pending = list(dict.fromkeys(canonical_url(r['url']) for r in ranked_results
                       if isinstance(r, dict) and isinstance(r.get('url'), str)
                       and allowed_url(r['url'], set(self.allowed_sources))
                       and canonical_url(r['url']) not in self._page_cache))
        remaining = min(int(fetching.get('max_pages_per_request', 20)),
                        max(0, int(fetching.get('max_pages_per_claim', 60)) - len(self._page_cache)))
        timeout = min(float(self.limits['timeout_seconds']), float(fetching.get('timeout_seconds', 8)))
        def fetch(url):
            try:
                if not self._robots_allow(url, timeout):
                    raise WebRetrievalError('robots.txt không cho phép tải hoặc không đọc được robots.txt')
                return url, self.page_fetcher(url, timeout)
            except (WebRetrievalError, OSError, HTTPException) as error:
                return url, WebRetrievalError(str(error))
        workers = max(1, min(6, int(fetching.get('workers', 1))))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for url, outcome in pool.map(fetch, pending[:remaining]):
                self._page_cache[url] = outcome

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
                # Broken headers such as charset=utf-8,gbk are not a codec name.
                for candidate in dict.fromkeys([charset.split(",")[0].strip(), "utf-8", "gbk"]):
                    try:
                        return raw.decode(candidate)
                    except (LookupError, UnicodeDecodeError):
                        continue
                raise WebRetrievalError("Không giải mã được robots.txt")
        except HTTPError as error:
            if error.code == 404:
                return ""
            raise WebRetrievalError("Không tải được robots.txt") from error
        except (URLError, TimeoutError, UnicodeDecodeError, LookupError, HTTPException) as error:
            raise WebRetrievalError("Không tải hoặc giải mã được robots.txt") from error

    def _robots_allow(self, page_url: str, timeout: float) -> bool:
        if not bool(self.policy.get("obey_robots_txt", True)):
            return True
        try:
            host = urlsplit(page_url).hostname or ''
            with self._robots_locks.setdefault(host, Lock()):
                cached = self._robots_cache.get(host)
                if cached and time.monotonic() - cached[0] < (300 if cached[1] is not None else 30):
                    robots = cached[1]
                else:
                    try:
                        robots = self.robots_fetcher(page_url, timeout)
                    except WebRetrievalError:
                        self._robots_cache[host] = (time.monotonic(), None)
                        raise
                    self._robots_cache[host] = (time.monotonic(), robots)
                if robots is None:
                    raise WebRetrievalError('Không tải được robots.txt')
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
        except HTTPError as error:
            raise WebRetrievalError(f"Tavily trả HTTP {error.code}; kiểm tra key, quota hoặc tham số") from error
        except (URLError, TimeoutError, json.JSONDecodeError, HTTPException) as error:
            raise WebRetrievalError("Search provider không trả kết quả hợp lệ") from error

    def _fetch_page(self, url: str, timeout: float) -> tuple[str, str]:
        return self._fetch_resource(url, timeout, ('text/html',))

    def _fetch_feed(self, url: str, timeout: float) -> tuple[str, str]:
        if not self._robots_allow(url, timeout):
            raise WebRetrievalError('robots.txt không cho phép tải RSS')
        return self._fetch_resource(url, timeout, ('application/xml', 'text/xml', 'application/rss+xml', 'application/atom+xml'),
                                    check_robots=True)

    def _fetch_resource(self, url: str, timeout: float, content_types: tuple[str, ...],
                        *, check_robots: bool = False) -> tuple[str, str]:
        current = canonical_url(url)
        for _ in range(int(self.extraction["max_redirects"]) + 1):  # type: ignore[index]
            if not allowed_url(current, set(self.allowed_sources)):
                raise WebRetrievalError("Redirect đi tới nguồn ngoài allowlist")
            if check_robots and current != canonical_url(url) and not self._robots_allow(current, timeout):
                raise WebRetrievalError('robots.txt không cho phép tải RSS sau chuyển hướng')
            assert_public_dns(urlsplit(current).hostname or "")
            request = Request(current, headers={"User-Agent": "VietnameseFactChecking/1.0", "Accept-Encoding": "gzip, deflate"})
            try:
                with build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
                    if response.headers.get_content_type() not in content_types:
                        raise WebRetrievalError("Nguồn web trả định dạng nội dung không phù hợp")
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
            except (URLError, TimeoutError, HTTPException) as error:
                raise WebRetrievalError("Hết thời gian hoặc không tải được trang nguồn web") from error
        raise WebRetrievalError("Trang web chuyển hướng quá nhiều lần")

    def search(self, claim: str, top_k: int = 3, *, source_urls: tuple[str, ...] = ()) -> list[RetrievedEvidence]:
        """Search without a publication-date restriction."""
        return self._run_search(claim, top_k, source_urls=source_urls)

    def search_time_window(self, claim: str, top_k: int, start_date: date,
                           end_date: date, *, language: str | None = None,
                           source_urls: tuple[str, ...] = ()) -> list[RetrievedEvidence]:
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
        return self._run_search(claim, top_k, options, (start_date, end_date), source_urls)

    def _run_search(self, claim: str, top_k: int, options: dict[str, object] | None = None,
                    date_window: tuple[date, date] | None = None,
                    source_urls: tuple[str, ...] = ()) -> list[RetrievedEvidence]:
        if top_k < 1:
            raise ValueError("top_k phải lớn hơn 0")
        self.last_attempts, self.last_candidates = [], []
        self.last_error = None
        self._page_cache = {}
        queries = search_queries(claim)
        lead = queries[1] if len(queries) > 1 else queries[0]
        quoted_lead = '"' + lead.replace('"', '') + '"'
        plain = re.sub(r"\s+ngày\s+\d{2}/\d{2}/\d{4}$", "", claim).strip()
        if date_window:
            # A general-index fallback must retain press sources. Date checks
            # still run against the original page even without a server filter.
            # The second request uses the general index: news-only and strict
            # index date/language filters can hide Vietnamese articles whose
            # publisher HTML has a perfectly valid date. Always recheck it here.
            attempts = [("dated_news", queries[0], options),
                        ("general_lead", quoted_lead,
                         {"topic": "general", "include_published_date": True, "exact_match": True,
                          "include_domains": []}),
                        ("general_terms", queries[-1],
                         {"topic": "general", "include_published_date": True, "include_domains": []})]
        else:
            attempts = [(f"general_{index + 1}", quoted_lead if index == 1 else query,
                         {**(options or {}), 'exact_match': True, 'include_domains': []} if index == 1 else options)
                        for index, query in enumerate(queries)]
        collected: dict[tuple[str, str], RetrievedEvidence] = {}

        def merge(items: list[RetrievedEvidence]) -> None:
            for item in items:
                key = (item.evidence.url, item.evidence.content)
                previous = collected.get(key)
                if previous is None or item.score > previous.score:
                    collected[key] = item

        if source_urls:
            if len(source_urls) > 3:
                raise ValueError("Chỉ nhận tối đa 3 URL nguồn cho mỗi lần kiểm chứng")
            items = self._search(claim, top_k, date_window=date_window, original_claim=claim,
                                 results_override=[{"url": url, "score": 1.0} for url in source_urls])
            merge(items)
            self.last_attempts.append({"stage": "direct_urls", "status": self.last_status, "count": len(items)})
        strong_match = lambda: any(eligible(plain, i.evidence.content, minimum_coverage=0.85)
                                   for i in collected.values())
        discovery_config = self.config.get('discovery', {})
        # Live feeds cannot reconstruct old news. Keep historical retrieval on
        # the search index instead of spending requests on irrelevant feeds.
        recent = date_window is None or abs((datetime.now().date() - date_window[1]).days) <= 14
        if self.enabled and discovery_config.get('enabled') and not strong_match():
            reference = date_window[1] if date_window else datetime.now().date()
            days = (reference, reference - timedelta(days=1))
            candidates = self.discovery.search(plain, date_window, sitemap_days=days, include_feeds=recent)
            items = self._search(plain, max(top_k, 20), date_window=date_window, original_claim=claim,
                                 results_override=candidates)
            merge(items)
            self.last_attempts.append({'stage': 'publisher_rss', 'status': self.last_status, 'count': len(items),
                                       'discovered_urls': len(candidates), 'feeds': self.discovery.last_feeds})
        for stage, query, request_options in attempts[:int(self.limits.get("requests_per_claim", 1))]:
            # A weak hit must not suppress the next query. One near-complete
            # passage is sufficient to stop discovery, regardless of verdict.
            if strong_match():
                break
            items = self._search(query, max(top_k, 20), request_options, date_window,
                                 original_claim=claim)
            merge(items)
            self.last_attempts.append({"stage": stage, "query": query, "status": self.last_status,
                                       "provider_results": self._provider_count, "count": len(items)})
            if self.last_status in {"missing_api_key", "disabled", "local_only", "invalid_provider_response"}:
                break
        ranked = sorted(collected.values(), key=lambda i: (
            verbatim_span(plain, i.evidence.content) is None,
            -relevance(plain, i.evidence.content), -i.score, i.evidence.passage_id))
        primary, remaining, documents = [], [], set()
        for item in ranked:
            (remaining if item.evidence.document_id in documents else primary).append(item)
            documents.add(item.evidence.document_id)
        selected = (primary + remaining)[:top_k]
        if selected:
            self.last_status = "ok"
        # Only HTML in memory for this call; no content is persisted.
        self._page_cache.clear()
        return selected

    def _search(self, claim: str, top_k: int,
                provider_overrides: dict[str, object] | None = None,
                date_window: tuple[date, date] | None = None, *, original_claim: str | None = None,
                results_override: list[dict[str, object]] | None = None) -> list[RetrievedEvidence]:
        self._provider_count = 0
        if top_k < 1:
            raise ValueError("top_k phải lớn hơn 0")
        if not self.enabled:
            self.last_status = "disabled"
            return []
        if not self.api_key and results_override is None:
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
            if results_override is None:
                self.ledger.reserve()
                response = self.provider_request(payload, self.api_key, float(self.limits["timeout_seconds"]))
            else:
                response = {"results": results_override}
        except WebRetrievalError as error:
            self.last_error = str(error)
            self.last_status = "local_only"
            return []
        results = response.get("results", []) if isinstance(response, dict) else None
        if not isinstance(results, list):
            self.last_status = "invalid_provider_response"
            return []
        collected: list[RetrievedEvidence] = []
        self._provider_count = len(results)
        self._prefetch_pages(results, original_claim or claim)
        seen_urls: set[str] = set()
        passage_query = re.sub(r"\s+ngày\s+\d{2}/\d{2}/\d{4}$", "", original_claim or claim)
        for rank, result in enumerate(results):
            if not isinstance(result, dict) or not isinstance(result.get("url"), str):
                continue
            url = canonical_url(result["url"])
            record: dict[str, object] = {"url": url, "query": claim, "status": "rejected"}
            self.last_candidates.append(record)
            if url in seen_urls:
                record["reason"] = "URL trùng trong kết quả tìm kiếm"
                continue
            if not allowed_url(url, set(self.allowed_sources)):
                record["reason"] = "URL không phải HTTPS hoặc hostname chưa có trong allowlist"
                continue
            seen_urls.add(url)
            try:
                if url not in self._page_cache:
                    raise WebRetrievalError('Đã đạt giới hạn số trang tải cho mỗi phát biểu')
                outcome = self._page_cache[url]
                if isinstance(outcome, WebRetrievalError):
                    raise outcome
                final_url, html = outcome
                final_url = canonical_url(final_url)
                if not allowed_url(final_url, set(self.allowed_sources)):
                    raise WebRetrievalError("Trang cuối cùng ngoài allowlist")
                title, passages = extract_passages(
                    html,
                    int(self.extraction["minimum_passage_chars"]),
                    int(self.extraction["maximum_passage_chars"]),
                    int(self.extraction["max_passages_per_page"]),
                    query=passage_query,
                )
                published_at = extract_published_at(html)
                date_source = "page" if published_at else None
                source_policy = self.allowed_sources[urlsplit(final_url).hostname or ""]
                # Official live tables/bulletins need their own dated snapshot;
                # the search index date cannot establish the table's validity.
                require_page_date = source_policy["category"] == "corporate" or "nchmf.gov.vn" in final_url
                if not published_at and not require_page_date:
                    published_at = _normalize_date(result.get("published_date"))
                    date_source = str(result.get('_date_source') or 'tavily') if published_at else None
                if date_window:
                    published = publication_date(published_at)
                    record["published_at"] = published_at
                    if published is None or not date_window[0] <= published <= date_window[1]:
                        record["reason"] = "Không rõ ngày xuất bản" if published is None else "Ngày xuất bản ngoài cửa sổ kiểm chứng"
                        continue
            except WebRetrievalError as error:
                record["reason"] = str(error)
                continue
            source = self.allowed_sources[urlsplit(final_url).hostname or ""]
            if final_url in seen_urls and final_url != url:
                record["reason"] = "Trùng trang sau chuyển hướng"
                continue
            seen_urls.add(final_url)
            try:
                base_score = float(result.get("score", 1.0))
                if not isfinite(base_score):
                    base_score = 0.0
            except (TypeError, ValueError):
                base_score = 0.0
            fetched_at = datetime.now(timezone.utc).isoformat()
            document_id = f"web-{sha256(final_url.encode('utf-8')).hexdigest()[:16]}"
            ranked_passages = sorted(enumerate(passages), key=lambda pair: -relevance(passage_query, pair[1]))
            accepted = 0
            for passage_index, passage in ranked_passages:
                if date_window and not eligible(passage_query, passage):
                    continue
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
                    published_at_source=date_source,
                    retrieved_at=fetched_at,
                    source_type={"government": "government", "international": "international_org", "press": "news", "corporate": "other"}[source["category"]],
                    authority_score={"government": 0.95, "international": 0.95, "press": 0.7, "corporate": 0.55}[source["category"]],
                )
                collected.append(RetrievedEvidence(evidence, base_score - rank * 0.001 - passage_index * 0.0001))
                accepted += 1
            record.update({"status": "accepted" if accepted else "rejected", "final_url": final_url,
                           "passages": accepted, "published_at": published_at})
            if not accepted:
                record["reason"] = "Không có đoạn đủ dài, khớp phát biểu trong nội dung trang gốc"
        # Give distinct articles a chance before taking extra passages from
        # the same page. Provider rank still determines article order.
        primary, remaining = [], []
        documents: set[str] = set()
        for item in collected:
            (remaining if item.evidence.document_id in documents else primary).append(item)
            documents.add(item.evidence.document_id)
        selected = (primary + remaining)[:top_k]
        self.last_status = "ok" if selected else "no_eligible_passages"
        return selected
