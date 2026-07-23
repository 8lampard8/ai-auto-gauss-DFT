"""Web search for chat augmentation (DuckDuckGo, no API key needed)."""
from __future__ import annotations

import re
import httpx


def search_web(query: str, n: int = 5) -> list[dict]:
    """Search DuckDuckGo and return top results as [{title, url, snippet}]."""
    try:
        r = httpx.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            timeout=15,
            follow_redirects=True,
        )
        if r.status_code != 200:
            return []
        results: list[dict] = []
        for m in re.finditer(
            r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>.*?'
            r'class="result__snippet"[^>]*>(.*?)</a>',
            r.text, re.S,
        ):
            title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
            snippet = re.sub(r"<[^>]+>", "", m.group(3)).strip()
            url = m.group(1)
            # DuckDuckGo wraps URLs in a redirect; extract the actual URL
            u = re.search(r"uddg=([^&]+)", url)
            if u:
                from urllib.parse import unquote
                url = unquote(u.group(1))
            if title and snippet:
                results.append({"title": title, "url": url, "snippet": snippet[:300]})
            if len(results) >= n:
                break
        return results
    except Exception:
        return []


def format_search_context(query: str, results: list[dict]) -> str:
    """Format search results as context text for the AI system prompt."""
    if not results:
        return ""
    lines = [f"[联网搜索结果] 查询: \"{query}\""]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']}\n   {r['snippet']}\n   {r['url']}")
    lines.append("[/搜索结果] 请结合以上搜索结果回答用户问题,并引用来源。")
    return "\n".join(lines)
