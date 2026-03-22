from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from tools.retrieval import SQLiteRetriever
from tools.search import web_fetch

TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "mkt_tok",
    "ref",
    "ref_src",
    "spm",
    "source",
    "utm_campaign",
    "utm_content",
    "utm_id",
    "utm_medium",
    "utm_name",
    "utm_source",
    "utm_term",
}

COMMON_TICKER_STOPWORDS = {
    "A",
    "AN",
    "AND",
    "ARE",
    "AS",
    "AT",
    "BE",
    "BY",
    "FOR",
    "FROM",
    "HAS",
    "HE",
    "IN",
    "IS",
    "IT",
    "ITS",
    "NOT",
    "OF",
    "ON",
    "OR",
    "THE",
    "TO",
    "US",
    "USD",
    "WAS",
    "WE",
    "WITH",
}


def normalize_url(raw_url: str) -> str:
    """Normalize URL for stable dedup and canonical storage."""
    value = (raw_url or "").strip()
    if not value:
        return ""

    parsed = urlsplit(value)
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"

    cleaned_pairs: list[tuple[str, str]] = []
    for key, val in parse_qsl(parsed.query, keep_blank_values=True):
        key_lower = key.lower()
        if key_lower in TRACKING_QUERY_KEYS or key_lower.startswith("utm_"):
            continue
        cleaned_pairs.append((key, val))
    cleaned_pairs.sort()
    query = urlencode(cleaned_pairs, doseq=True)

    return urlunsplit((scheme, netloc, path, query, ""))


def _sha256(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8", errors="ignore")).hexdigest()


def _clean_text(value: str) -> str:
    text = unescape(value or "")
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _strip_html(html: str) -> str:
    if not html:
        return ""

    text = re.sub(r"(?is)<!--.*?-->", " ", html)
    text = re.sub(r"(?is)<(script|style|noscript|svg|iframe|canvas)\b.*?>.*?</\1>", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    return _clean_text(text)


def _extract_title_from_html(html: str) -> str | None:
    if not html:
        return None

    for pattern in [
        r"(?is)<meta[^>]+(?:property|name)=[\"']og:title[\"'][^>]+content=[\"']([^\"']+)[\"']",
        r"(?is)<meta[^>]+(?:name|property)=[\"']twitter:title[\"'][^>]+content=[\"']([^\"']+)[\"']",
        r"(?is)<title[^>]*>(.*?)</title>",
    ]:
        m = re.search(pattern, html)
        if m:
            title = _clean_text(m.group(1))
            if title:
                return title
    return None


def _strip_jina_metadata(raw_content: str) -> tuple[str, str | None, str | None]:
    """Strip Jina Reader metadata header, return (content, title, published_at)."""
    if not raw_content:
        return ("", None, None)

    lines = raw_content.split("\n")
    title = None
    published_at = None
    content_start = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("Title:"):
            title = stripped[6:].strip()
            content_start = i + 1
        elif stripped.startswith("URL Source:"):
            content_start = i + 1
        elif stripped.startswith("Published Time:"):
            published_at = stripped[15:].strip()
            content_start = i + 1
        elif stripped.startswith("Markdown Content:"):
            content_start = i + 1
            break
        elif stripped and not stripped.startswith(("Title:", "URL Source:", "Published Time:", "Markdown Content:")):
            break

    body = "\n".join(lines[content_start:]).strip()
    return (body or raw_content, title or None, published_at or None)


def _clean_emoji_images(markdown: str) -> str:
    """Replace tiny emoji SVG image references with their alt-text emoji."""
    if not markdown:
        return ""
    return re.sub(
        r"!\[(?:Image\s*\d+:\s*)?([^\]]*?)\]\(https?://s\.w\.org/images/core/emoji/[^)]+\)",
        r"\1",
        markdown,
    )


def _extract_title_from_markdown(markdown: str) -> str | None:
    if not markdown:
        return None

    lines = [ln.strip() for ln in markdown.splitlines()[:60]]
    for line in lines:
        if re.match(r"^!\[.*\]\(.*\)$", line):
            continue
        if line.startswith("#"):
            title = _clean_text(line.lstrip("#"))
            title = re.sub(r"!\[.*?\]\([^)]*\)", "", title).strip()
            if title:
                return title
    for line in lines:
        if re.match(r"^!\[.*\]\(.*\)$", line):
            continue
        if line:
            cleaned = re.sub(r"!\[.*?\]\([^)]*\)", "", line).strip()
            if cleaned:
                return _clean_text(cleaned[:200])
    return None


def _parse_datetime(value: str | None) -> str | None:
    if not value:
        return None

    raw = value.strip()
    if not raw:
        return None

    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    except Exception:
        pass

    try:
        parsed = parsedate_to_datetime(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    except Exception:
        return None


def _extract_published_at_from_html(html: str) -> str | None:
    if not html:
        return None

    patterns = [
        r"(?is)<meta[^>]+(?:property|name)=[\"']article:published_time[\"'][^>]+content=[\"']([^\"']+)[\"']",
        r"(?is)<meta[^>]+(?:property|name)=[\"']og:published_time[\"'][^>]+content=[\"']([^\"']+)[\"']",
        r"(?is)<meta[^>]+(?:property|name)=[\"']publishdate[\"'][^>]+content=[\"']([^\"']+)[\"']",
        r"(?is)<meta[^>]+(?:property|name)=[\"']date[\"'][^>]+content=[\"']([^\"']+)[\"']",
        r"(?is)<time[^>]+datetime=[\"']([^\"']+)[\"']",
    ]

    for pattern in patterns:
        m = re.search(pattern, html)
        if not m:
            continue
        parsed = _parse_datetime(m.group(1))
        if parsed:
            return parsed
    return None


def _source_name_from_url(url: str) -> str | None:
    try:
        host = urlsplit(url).netloc.lower()
    except Exception:
        return None
    if not host:
        return None
    if host.startswith("www."):
        host = host[4:]
    return host


def _guess_content_type(url: str, content: str) -> str:
    lowered_url = (url or "").lower()
    lowered = (content or "").lower()[:5000]

    if "sec.gov" in lowered_url or "10-k" in lowered or "10-q" in lowered:
        return "filing"
    if "earnings" in lowered_url or "earnings" in lowered:
        return "earnings"
    if "research" in lowered_url or "analysis" in lowered_url:
        return "research"
    return "article"


def _extract_tickers_from_text(content: str, max_items: int = 6) -> list[str]:
    candidates = re.findall(r"\b[A-Z]{1,5}\b", (content or "")[:8000])
    seen: set[str] = set()
    output: list[str] = []
    for item in candidates:
        if item in COMMON_TICKER_STOPWORDS:
            continue
        if item in seen:
            continue
        seen.add(item)
        output.append(item)
        if len(output) >= max_items:
            break
    return output


def _merge_tags(user_tags: list[str] | None, ai_tags: list[str] | None, max_items: int = 12) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for source in (user_tags or []):
        text = _clean_text(str(source)).lower()
        if not text or text in seen:
            continue
        seen.add(text)
        merged.append(text)
        if len(merged) >= max_items:
            return merged
    for source in (ai_tags or []):
        text = _clean_text(str(source)).lower()
        if not text or text in seen:
            continue
        seen.add(text)
        merged.append(text)
        if len(merged) >= max_items:
            return merged
    return merged


def _safe_json_load(value: str) -> dict[str, Any] | None:
    if not value:
        return None

    text = value.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    try:
        parsed = json.loads(m.group(0))
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def _guess_category(url: str, content: str) -> str:
    """Heuristic category guess when AI extraction is unavailable."""
    text = (url + " " + content[:2000]).lower()
    if any(w in text for w in ("interview", "访谈", "交流", "纪要", "expert call")):
        return "interview"
    if any(w in text for w in ("paper", "论文", "arxiv", "abstract", "methodology")):
        return "paper"
    if any(w in text for w in ("research", "研报", "analysis", "initiat", "coverage", "rating")):
        return "research"
    return "other"


def _fallback_metadata(
    *,
    canonical_url: str,
    extracted_title: str | None,
    source_name: str | None,
    content: str,
    published_at_guess: str | None,
) -> dict[str, Any]:
    summary = _clean_text(content[:280])
    if len(content) > 280:
        summary += "..."

    tickers = _extract_tickers_from_text(content)

    return {
        "title": extracted_title or source_name or canonical_url,
        "summary": summary,
        "content_type": _guess_content_type(canonical_url, content),
        "category": _guess_category(canonical_url, content),
        "industry": None,
        "source_name": source_name,
        "published_at": published_at_guess,
        "tags": [],
        "companies": tickers,
        "language": "unknown",
        "confidence": 0.3,
    }


def extract_metadata_with_ai(
    *,
    canonical_url: str,
    extracted_title: str | None,
    source_name: str | None,
    content: str,
    published_at_guess: str | None,
) -> dict[str, Any]:
    """AI-first metadata extraction with deterministic fallback."""
    fallback = _fallback_metadata(
        canonical_url=canonical_url,
        extracted_title=extracted_title,
        source_name=source_name,
        content=content,
        published_at_guess=published_at_guess,
    )

    if not os.getenv("OPENAI_API_KEY"):
        return fallback

    try:
        from openai import OpenAI

        model = os.getenv("INGEST_METADATA_MODEL") or "gpt-5.4-mini"
        client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
        )

        excerpt = content[:12000]
        prompt = {
            "url": canonical_url,
            "title_hint": extracted_title,
            "source_name_hint": source_name,
            "published_at_hint": published_at_guess,
            "content_excerpt": excerpt,
        }

        response = client.chat.completions.create(
            model=model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Extract metadata from article content. Return strict JSON only with keys: "
                        "title, summary, content_type, category, industry, source_name, published_at, tags, companies, language, confidence. "
                        "Rules: "
                        "category must be one of: research (研报/行业分析), interview (专家访谈/管理层交流), paper (学术论文/白皮书), note (笔记/备忘), other; "
                        "industry is a short label like '半导体', '云计算', '新能源汽车', 'SaaS', 'Fintech' — use the most specific applicable term; "
                        "published_at must be ISO8601 or null; tags/companies are arrays of strings; "
                        "confidence is 0-1 float."
                    ),
                },
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ],
        )

        raw = (response.choices[0].message.content or "").strip()
        parsed = _safe_json_load(raw)
        if not parsed:
            return fallback

        merged = dict(fallback)
        merged.update({k: v for k, v in parsed.items() if v is not None})

        merged["title"] = _clean_text(str(merged.get("title") or fallback["title"]))[:300]
        merged["summary"] = _clean_text(str(merged.get("summary") or fallback["summary"]))[:500]
        merged["source_name"] = _clean_text(str(merged.get("source_name") or fallback["source_name"] or "")) or fallback["source_name"]
        merged["published_at"] = _parse_datetime(str(merged.get("published_at") or "")) or fallback["published_at"]

        tags = merged.get("tags")
        if isinstance(tags, list):
            merged["tags"] = [_clean_text(str(v)).lower() for v in tags if _clean_text(str(v))][:12]
        else:
            merged["tags"] = fallback["tags"]

        companies = merged.get("companies")
        if isinstance(companies, list):
            merged["companies"] = [_clean_text(str(v)).upper() for v in companies if _clean_text(str(v))][:8]
        else:
            merged["companies"] = fallback["companies"]

        try:
            merged["confidence"] = float(merged.get("confidence"))
        except Exception:
            merged["confidence"] = fallback["confidence"]

        if merged["confidence"] < 0:
            merged["confidence"] = 0.0
        if merged["confidence"] > 1:
            merged["confidence"] = 1.0

        # Parse category
        category = merged.get("category", "other")
        if category not in ("research", "interview", "paper", "note", "other"):
            category = "other"
        merged["category"] = category

        # Parse industry
        industry = merged.get("industry")
        if isinstance(industry, str):
            merged["industry"] = _clean_text(industry)[:50]
        else:
            merged["industry"] = None

        return merged

    except Exception:
        return fallback


def _fetch_content_from_url(url: str, max_chars: int = 20000) -> dict[str, Any]:
    fetch_result = web_fetch(url=url, max_chars=max_chars)
    if fetch_result.status == "ok":
        payload = fetch_result.data or {}
        raw_content = payload.get("content") or ""
        body, jina_title, jina_published = _strip_jina_metadata(raw_content)
        body = _clean_emoji_images(body)
        content = _clean_text(body)
        if content:
            return {
                "ok": True,
                "content": content,
                "title": jina_title or _extract_title_from_markdown(body),
                "published_at": jina_published,
                "method": "jina_reader",
                "meta": {
                    "char_count": payload.get("char_count"),
                    "truncated": payload.get("truncated"),
                },
            }

    try:
        with httpx.Client(timeout=25.0, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": "Mozilla/5.0 IRIS-URL-Ingest"})
            resp.raise_for_status()
            html = resp.text
            content = _strip_html(html)
            if not content:
                return {"ok": False, "error": "empty_content"}
            return {
                "ok": True,
                "content": content,
                "title": _extract_title_from_html(html),
                "published_at": _extract_published_at_from_html(html),
                "method": "direct_html",
                "meta": {"status_code": resp.status_code},
            }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def ingest_url_document(
    *,
    retriever: SQLiteRetriever,
    url: str,
    title: str | None = None,
    page_html: str | None = None,
    source_type: str = "manual_url",
    company: str | None = None,
    tags: list[str] | None = None,
    force_reingest: bool = False,
) -> dict[str, Any]:
    """Ingest URL content into knowledge base with dedup and AI metadata."""
    raw_url = (url or "").strip()
    if not raw_url.startswith(("http://", "https://")):
        return {"status": "failed", "error": "invalid_url"}

    canonical_url = normalize_url(raw_url)
    url_hash = _sha256(canonical_url)

    extracted_title = title
    published_guess = None
    extraction_method = None
    extraction_meta: dict[str, Any] = {
        "source": source_type,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    content = ""
    if page_html and page_html.strip():
        content = _strip_html(page_html)
        extracted_title = extracted_title or _extract_title_from_html(page_html)
        published_guess = _extract_published_at_from_html(page_html)
        extraction_method = "browser_html"
        extraction_meta["used_page_html"] = True
        extraction_meta["page_html_length"] = len(page_html)

    if len(content) < 400:
        fetched = _fetch_content_from_url(canonical_url)
        if fetched.get("ok"):
            fetched_content = _clean_text(fetched.get("content") or "")
            if len(fetched_content) > len(content):
                content = fetched_content
            if not extracted_title:
                extracted_title = fetched.get("title")
            if not published_guess:
                published_guess = fetched.get("published_at")
            extraction_method = extraction_method or fetched.get("method")
            extraction_meta["fetch_meta"] = fetched.get("meta", {})
        elif not content:
            return {
                "status": "failed",
                "error": "fetch_failed",
                "detail": fetched.get("error") or "unable_to_extract_content",
            }

    content = _clean_text(content)
    if len(content) < 40:
        return {
            "status": "failed",
            "error": "empty_content",
            "detail": "content too short after extraction",
        }

    content_hash = _sha256(content)

    if not force_reingest:
        duplicate = retriever.find_document_by_hashes(url_hash=url_hash, content_hash=content_hash)
        if duplicate:
            return {
                "status": "duplicate",
                "duplicate_of": duplicate.get("id"),
                "document": duplicate,
                "canonical_url": canonical_url,
            }

    source_name = _source_name_from_url(canonical_url)
    ai_metadata = extract_metadata_with_ai(
        canonical_url=canonical_url,
        extracted_title=extracted_title,
        source_name=source_name,
        content=content,
        published_at_guess=published_guess,
    )

    final_title = _clean_text(title or ai_metadata.get("title") or extracted_title or canonical_url)[:300]
    final_published_at = _parse_datetime(ai_metadata.get("published_at")) or published_guess
    final_tags = _merge_tags(tags, ai_metadata.get("tags") if isinstance(ai_metadata.get("tags"), list) else [])

    ai_companies = ai_metadata.get("companies")
    ai_company = None
    if isinstance(ai_companies, list) and ai_companies:
        ai_company = _clean_text(str(ai_companies[0])).upper()

    final_company = _clean_text(company).upper() if company else ai_company

    extraction_meta["extraction_method"] = extraction_method or "unknown"
    extraction_meta["content_length"] = len(content)

    saved = retriever.save_document(
        title=final_title,
        doc_type="url",
        content_text=content,
        source_path=raw_url,
        company=final_company,
        tags=final_tags,
        category=ai_metadata.get("category", "other"),
        industry=ai_metadata.get("industry"),
        source_type=source_type or "manual_url",
        source_name=source_name,
        published_at=final_published_at,
        canonical_url=canonical_url,
        url_hash=url_hash,
        content_hash=content_hash,
        ai_metadata=ai_metadata,
        extraction_meta=extraction_meta,
    )

    doc = retriever.get_document(saved["id"]) or saved

    return {
        "status": "ingested",
        "document": doc,
        "canonical_url": canonical_url,
    }
