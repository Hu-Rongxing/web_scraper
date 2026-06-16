# -*- coding: utf-8 -*-
"""Article content extraction.

Production article extraction uses trafilatura first and Scrapling DOM text as
the fallback. This keeps article extraction scoped to the two project-standard
engines and avoids readability-lxml as a separate extraction path.
"""

from __future__ import annotations

import re
import json
from html import unescape
from dataclasses import dataclass
from typing import Any, Optional

from .config import DEFAULT_EXTRACT_STRATEGY, MIN_CONTENT_LENGTH, logger

try:
    import trafilatura
except ImportError:  # pragma: no cover - depends on local environment
    trafilatura = None

try:
    from scrapling import Selector
except ImportError:  # pragma: no cover - depends on local environment
    Selector = None


@dataclass
class ExtractedContent:
    """Normalized article extraction result."""

    title: str = ""
    content: str = ""
    author: Optional[str] = None
    date: Optional[str] = None
    summary: Optional[str] = None
    raw_html: str = ""
    method: str = ""


class ContentExtractor:
    """Extract readable article text with trafilatura and Scrapling fallback."""

    SUPPORTED_STRATEGY = "trafilatura"
    FALLBACK_SELECTORS = (
        "article",
        '[data-testid="article-body"]',
        '[role="article"]',
        "main",
        "body",
    )
    STRUCTURED_BODY_KEYS = {
        "articlebody",
        "body",
        "bodytext",
        "contentbody",
        "fulltext",
        "fullcontent",
        "text",
        "html",
        "nodetree",
        "paragraphs",
        "blocks",
    }
    STRUCTURED_TITLE_KEYS = ("headline", "title", "name")
    STRUCTURED_DATE_KEYS = (
        "datePublished",
        "dateModified",
        "publishedAt",
        "published_at",
        "publishTime",
        "createdAt",
        "created_at",
    )
    REJECTED_TEXT_MARKERS = (
        "warning: target url returned error",
        "securitycompromiseerror",
        "anonymous access to domain",
        "wayback machine",
        "saved from",
        "calendar view",
        "hubble-focused crawl",
        "webcache.googleusercontent.com",
        "title: just a moment",
        "checking your browser",
        "please enable js and disable any ad blocker",
        "please enable javascript and disable any ad blocker",
        "captcha",
        "access denied",
        "continue with a free trial",
        "already have an account?",
        "register an account to continue reading",
        "subscribe to continue",
        "log in to continue",
        "login to continue",
        "member only",
        "premium content",
    )

    def __init__(self, strategy: Optional[str] = None):
        self._strategy = strategy or DEFAULT_EXTRACT_STRATEGY

    def extract(self, html: str, url: str = "", **_: object) -> ExtractedContent:
        """Extract article content from already fetched HTML."""
        if self._strategy != self.SUPPORTED_STRATEGY:
            logger.warning(
                "Unsupported extract strategy %r; using trafilatura",
                self._strategy,
            )
        plain = self._extract_reader_plain_text(html)
        if plain:
            return plain
        structured = self._extract_structured_data(html)
        if structured and len(structured.content) >= MIN_CONTENT_LENGTH:
            structured.raw_html = html
            return structured
        return self._extract_trafilatura(html, url)

    def _extract_trafilatura(self, html: str, url: str) -> ExtractedContent:
        if not html:
            return ExtractedContent(method="trafilatura_empty")

        if trafilatura is None:
            logger.error("trafilatura is not installed; falling back to Scrapling")
            return self._extract_scrapling(html, method="scrapling_fallback_unavailable")

        try:
            content = trafilatura.extract(
                html,
                url=url,
                include_links=False,
                include_images=False,
                include_formatting=False,
                include_comments=False,
                deduplicate=True,
            )
            metadata = trafilatura.extract_metadata(html, default_url=url)
        except Exception as exc:
            logger.warning("trafilatura extraction failed: %s", exc)
            return self._extract_scrapling(html, method="scrapling_fallback_error")

        title = ""
        author = None
        date = None
        if metadata:
            title = metadata.title or ""
            author = metadata.author
            date = metadata.date
        if not title:
            title = self._extract_title_from_html(html)

        if not content or len(content.strip()) < MIN_CONTENT_LENGTH:
            fallback = self._extract_scrapling(
                html,
                method="scrapling_fallback_short",
                title=title,
                author=author,
                date=date,
            )
            if fallback.content:
                return fallback
            fallback.method = "trafilatura_short"
            return fallback

        return ExtractedContent(
            title=self._clean_title(title),
            content=content.strip(),
            author=author,
            date=date,
            raw_html=html,
            method="trafilatura",
        )

    def _extract_scrapling(
        self,
        html: str,
        *,
        method: str,
        title: str = "",
        author: Optional[str] = None,
        date: Optional[str] = None,
    ) -> ExtractedContent:
        """Fallback article extraction using Scrapling DOM text."""
        if not html:
            return ExtractedContent(method=method)

        if Selector is None:
            logger.error("scrapling is not installed; fallback extraction disabled")
            return ExtractedContent(
                title=self._clean_title(title or self._extract_title_from_html(html)),
                author=author,
                date=date,
                raw_html=html,
                method=f"{method}_unavailable",
            )

        try:
            doc = Selector(html)
            for css in self.FALLBACK_SELECTORS:
                element = next(iter(doc.css(css)), None)
                if not element:
                    continue
                raw_text = element.get_all_text() if hasattr(element, "get_all_text") else element.text
                content = self._clean_text(str(raw_text or ""))
                if len(content) >= MIN_CONTENT_LENGTH:
                    return ExtractedContent(
                        title=self._clean_title(title or self._extract_title_from_html(html)),
                        content=content,
                        author=author,
                        date=date,
                        raw_html=html,
                        method=method,
                    )
        except Exception as exc:
            logger.warning("Scrapling fallback extraction failed: %s", exc)
            method = f"{method}_error"

        return ExtractedContent(
            title=self._clean_title(title or self._extract_title_from_html(html)),
            author=author,
            date=date,
            raw_html=html,
            method=method,
        )

    def _extract_reader_plain_text(self, text: str) -> Optional[ExtractedContent]:
        """Extract text from reader services that return markdown/plain text."""
        if not text:
            return None
        sample = text[:2000].lower()
        has_html = re.search(r"<(?:html|body|article|main|p|div|script|head)\b", sample)
        looks_reader = (
            text.startswith("Title: ")
            or "\nURL Source:" in text[:1000]
            or "\nMarkdown Content:" in text[:2000]
        )
        if has_html and not looks_reader:
            return None
        if self._contains_rejected_text(text):
            title = self._extract_reader_title(text)
            return ExtractedContent(
                title=self._clean_title(title),
                raw_html=text,
                method="reader_plain_text_rejected",
            )

        lines = [line.strip() for line in text.replace("\r\n", "\n").split("\n")]
        title = ""
        body_lines: list[str] = []
        in_body = not looks_reader
        for line in lines:
            if not line:
                if body_lines and body_lines[-1]:
                    body_lines.append("")
                continue
            if line.startswith("Title: ") and not title:
                title = line.removeprefix("Title: ").strip()
                continue
            if line.startswith(("URL Source:", "Published Time:", "Markdown Content:")):
                if line.startswith("Markdown Content:"):
                    in_body = True
                continue
            if looks_reader and line.startswith(("Warning:", "Error:", '{"data":null')):
                return ExtractedContent(
                    title=self._clean_title(title),
                    raw_html=text,
                    method="reader_plain_text_rejected",
                )
            if in_body:
                body_lines.append(line)

        content = self._clean_reader_text("\n".join(body_lines))
        if len(content) < MIN_CONTENT_LENGTH:
            return None
        return ExtractedContent(
            title=self._clean_title(title),
            content=content,
            raw_html=text,
            method="reader_plain_text",
        )

    def _extract_structured_data(self, html: str) -> Optional[ExtractedContent]:
        """Extract complete article bodies from JSON-LD or front-end state."""
        if not html:
            return None

        for script_id in ("__NEXT_DATA__", "__NUXT_DATA__", "__APOLLO_STATE__"):
            for raw in self._script_contents(html, id_value=script_id):
                data = self._loads_jsonish(raw)
                result = self._extract_from_json(data, method=f"script_state:{script_id.lower()}")
                if result and len(result.content) >= MIN_CONTENT_LENGTH:
                    return result

        best: ExtractedContent | None = None
        for raw in self._script_contents(html, type_pattern=r"(?:application/json|application/ld\+json)"):
            data = self._loads_jsonish(raw)
            method = "json_ld" if "ld+json" in raw[:80].lower() or self._looks_like_json_ld(data) else "script_state"
            result = self._extract_from_json(data, method=method)
            if not result or len(result.content) < MIN_CONTENT_LENGTH:
                continue
            if method == "json_ld" and not self._json_data_has_article_body(data):
                continue
            if best is None or len(result.content) > len(best.content):
                best = result
        return best

    def _extract_from_json(self, data: Any, *, method: str) -> Optional[ExtractedContent]:
        if data is None:
            return None

        body, body_score = self._best_json_body(data)
        if not body:
            return None
        body = self._clean_structured_text(body)
        if self._contains_rejected_text(body):
            return None

        title = self._first_json_string(data, self.STRUCTURED_TITLE_KEYS)
        date = self._first_json_string(data, self.STRUCTURED_DATE_KEYS)
        summary = self._first_json_string(data, ("summary", "description")) if body_score >= 0 else ""
        return ExtractedContent(
            title=self._clean_title(title),
            content=body,
            date=date or None,
            method=method,
            summary=summary or None,
        )

    def _best_json_body(self, data: Any) -> tuple[str, int]:
        best_text = ""
        best_score = -1

        def visit(value: Any, path: tuple[str, ...] = ()) -> None:
            nonlocal best_text, best_score
            if isinstance(value, dict):
                for key, child in value.items():
                    key_text = str(key)
                    key_norm = key_text.lower()
                    if key_norm in self.STRUCTURED_BODY_KEYS and not self._is_summary_path(path + (key_text,)):
                        text = self._json_body_text(child)
                        score = len(text)
                        if key_norm in {"articlebody", "contentbody", "fulltext", "fullcontent"}:
                            score += 2000
                        if key_norm in {"nodetree", "paragraphs", "blocks"}:
                            score += 800
                        if len(text) >= MIN_CONTENT_LENGTH and score > best_score:
                            best_text = text
                            best_score = score
                    visit(child, path + (key_text,))
            elif isinstance(value, list):
                for child in value:
                    visit(child, path)

        visit(data)
        return best_text, best_score

    def _json_body_text(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return self._clean_structured_text(value)
        if isinstance(value, (int, float, bool)):
            return ""
        if isinstance(value, list):
            parts = [self._json_body_text(item) for item in value]
            return self._join_body_parts(parts)
        if isinstance(value, dict):
            parts: list[str] = []
            for key, child in value.items():
                key_norm = str(key).lower()
                if key_norm in {"text", "value", "content", "html", "children", "paragraphs", "blocks", "nodes"}:
                    parts.append(self._json_body_text(child))
            if not parts:
                for child in value.values():
                    text = self._json_body_text(child)
                    if text:
                        parts.append(text)
            return self._join_body_parts(parts)
        return ""

    @staticmethod
    def _join_body_parts(parts: list[str]) -> str:
        cleaned = [part.strip() for part in parts if part and part.strip()]
        return "\n\n".join(dict.fromkeys(cleaned))

    def _first_json_string(self, data: Any, keys: tuple[str, ...]) -> str:
        wanted = {key.lower() for key in keys}

        def visit(value: Any) -> str:
            if isinstance(value, dict):
                for key, child in value.items():
                    if str(key).lower() in wanted and isinstance(child, (str, int, float)):
                        text = str(child).strip()
                        if text and len(text) < 300:
                            return text
                for child in value.values():
                    found = visit(child)
                    if found:
                        return found
            elif isinstance(value, list):
                for child in value:
                    found = visit(child)
                    if found:
                        return found
            return ""

        return visit(data)

    def _script_contents(
        self,
        html: str,
        *,
        id_value: str | None = None,
        type_pattern: str | None = None,
    ) -> list[str]:
        scripts: list[str] = []
        for match in re.finditer(r"<script\b([^>]*)>(.*?)</script>", html, re.I | re.S):
            attrs = match.group(1) or ""
            body = unescape(match.group(2) or "").strip()
            if not body:
                continue
            if id_value and not re.search(rf"\bid\s*=\s*['\"]{re.escape(id_value)}['\"]", attrs, re.I):
                continue
            if type_pattern and not re.search(rf"\btype\s*=\s*['\"][^'\"]*{type_pattern}[^'\"]*['\"]", attrs, re.I):
                continue
            scripts.append(body)
        return scripts

    def _loads_jsonish(self, raw: str) -> Any:
        if not raw:
            return None
        cleaned = raw.strip()
        cleaned = re.sub(r"^\s*window\.[A-Za-z0-9_$]+\s*=\s*", "", cleaned)
        cleaned = cleaned.rstrip(";")
        try:
            return json.loads(cleaned)
        except Exception:
            pass
        cleaned = re.sub(
            r'("(?:datePublished|dateModified|publishedAt|createdAt)"\s*:\s*)(\d{4}-\d{2}-\d{2}T[0-9:.+-Z]+)',
            r'\1"\2"',
            cleaned,
        )
        try:
            return json.loads(cleaned)
        except Exception:
            return None

    def _looks_like_json_ld(self, data: Any) -> bool:
        found = False

        def visit(value: Any) -> None:
            nonlocal found
            if found:
                return
            if isinstance(value, dict):
                type_value = value.get("@type")
                if isinstance(type_value, str) and "article" in type_value.lower():
                    found = True
                    return
                if "@context" in value:
                    found = True
                    return
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        visit(data)
        return found

    def _json_data_has_article_body(self, data: Any) -> bool:
        if isinstance(data, dict):
            if isinstance(data.get("articleBody"), str) and data.get("articleBody", "").strip():
                return True
            return any(self._json_data_has_article_body(child) for child in data.values())
        if isinstance(data, list):
            return any(self._json_data_has_article_body(child) for child in data)
        return False

    def _contains_rejected_text(self, text: str) -> bool:
        sample = (text or "")[:12000].lower()
        return any(marker in sample for marker in self.REJECTED_TEXT_MARKERS)

    @staticmethod
    def _is_summary_path(path: tuple[str, ...]) -> bool:
        return any(part.lower() in {"description", "summary", "dek", "seo", "metadata", "meta"} for part in path)

    @staticmethod
    def _extract_reader_title(text: str) -> str:
        match = re.search(r"^Title:\s*(.+)$", text or "", re.M)
        return match.group(1).strip() if match else ""

    @staticmethod
    def _clean_structured_text(text: str) -> str:
        text = unescape(text or "")
        text = re.sub(r"<\s*(?:p|br|div|li|section|article|h[1-6])\b[^>]*>", "\n", text, flags=re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"[ \t\f\v]+", " ", text)
        text = re.sub(r"\n\s+", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def _clean_reader_text(text: str) -> str:
        text = re.sub(r"\n{3,}", "\n\n", text or "").strip()
        text = re.sub(r"^\s*={3,}\s*$", "", text, flags=re.M)
        return text.strip()

    @staticmethod
    def _clean_title(title: str) -> str:
        if not title:
            return ""
        title = re.sub(r"<[^>]+>", "", title)
        title = re.sub(r"&(?:amp|lt|gt|quot|nbsp|#\d+|#x[0-9a-fA-F]+);", " ", title)
        title = re.sub(r"\s+", " ", title).strip()
        title = re.sub(r"\s*[-|]\s*(?:Home|News|The .*|.*\.com|.*\.org)\s*$", "", title, flags=re.I)
        return title

    @staticmethod
    def _clean_text(text: str) -> str:
        text = re.sub(r"\s+", " ", text or "").strip()
        return text

    @staticmethod
    def _extract_title_from_html(html: str) -> str:
        for pattern in (
            r"<title[^>]*>(.+?)</title>",
            r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\'](.+?)["\']',
            r"<h1[^>]*>(.+?)</h1>",
        ):
            match = re.search(pattern, html, re.I | re.S)
            if not match:
                continue
            raw = re.sub(r"<[^>]+>", "", match.group(1))
            raw = re.sub(r"\s+", " ", raw).strip()
            if raw and len(raw) < 300:
                return raw
        return ""
