"""Web tools — web search and URL content extraction."""

import json
import logging
import re

logger = logging.getLogger(__name__)


# === Web Search ===


def web_search(query: str, max_results: int = 10) -> str:
    # Try ddgs first (newer package)
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if results:
            return _format_results(query, results)
    except ImportError:
        pass
    except Exception:
        pass

    # Try duckduckgo_search (older package)
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if results:
            return _format_results(query, results)
    except ImportError:
        pass
    except Exception:
        pass

    return (
        f"Web search unavailable (network restriction or missing package).\n"
        f"Query was: {query}\n\n"
        f"Alternative: use web_fetch with direct URLs, for example:\n"
        f"- https://arxiv.org/search/?query={query.replace(' ', '+')}\n"
        f"- https://scholar.google.com/scholar?q={query.replace(' ', '+')}"
    )


def _format_results(query: str, results: list[dict]) -> str:
    lines = [f"Search results for: {query}\n"]
    for i, r in enumerate(results, 1):
        lines.append(
            f"{i}. **{r.get('title', 'No title')}**\n"
            f"   URL: {r.get('href', r.get('url', 'N/A'))}\n"
            f"   {r.get('body', r.get('snippet', 'No snippet'))}\n"
        )
    return "\n".join(lines)


# === Web Fetch ===


def web_fetch(url: str, max_chars: int = 20000) -> str:
    try:
        import requests
    except ImportError:
        return "Error: requests package required: pip install requests"

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        }
        response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")

        # Plain text
        if "text/plain" in content_type:
            text = response.text[:max_chars]
            return f"[{url}]\n\n{text}"

        # HTML — extract readable text
        if "text/html" in content_type or not content_type:
            text = _extract_text_from_html(response.text)
            if len(text) > max_chars:
                text = text[:max_chars] + "\n\n... [truncated]"
            return f"[{url}]\n\n{text}"

        # PDF or other binary
        if "application/pdf" in content_type:
            return f"[{url}] PDF file detected ({len(response.content)} bytes). Cannot extract text directly."

        return f"[{url}] Unsupported content type: {content_type}"

    except Exception as e:
        return f"Error: fetch failed for {url}: {e}"


def _extract_text_from_html(html: str) -> str:
    """Extract readable text from HTML."""
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")

        # Remove script and style elements
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        # Get text
        text = soup.get_text(separator="\n")

        # Clean up whitespace
        lines = [line.strip() for line in text.splitlines()]
        lines = [line for line in lines if line]

        # Remove duplicate consecutive lines
        deduped = []
        for line in lines:
            if not deduped or line != deduped[-1]:
                deduped.append(line)

        return "\n".join(deduped)

    except ImportError:
        # Fallback: simple regex-based extraction
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text


