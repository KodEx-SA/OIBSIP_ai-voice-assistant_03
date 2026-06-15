"""
web_search.py - Clare's web intelligence layer
Handles search via Brave API (primary) and SerpAPI (fallback),
plus page content extraction via httpx + BeautifulSoup.
"""

import os
import logging
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("clare.web_search")
logger.setLevel(logging.INFO)

BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"
SERP_URL = "https://serpapi.com/search"
PAGE_TIMEOUT = 10
MAX_PAGE_CHARS = 8000


class WebSearcher:
    def __init__(self):
        self.brave_key = os.getenv("BRAVE_API_KEY")
        self.serp_key = os.getenv("SERPAPI_KEY")

        if not self.brave_key and not self.serp_key:
            logger.warning(
                "No search API keys set (BRAVE_API_KEY / SERPAPI_KEY) - "
                "web search tools will return empty results until keys are added."
            )
            return

        if self.brave_key:
            logger.info("Brave Search API configured.")
        if self.serp_key:
            logger.info("SerpAPI configured.")

    async def search(self, query: str, count: int = 5) -> list[dict]:
        """Search the web. Tries Brave first, falls back to SerpAPI."""
        if not self.brave_key and not self.serp_key:
            logger.warning("web_search called but no API keys are set.")
            return []

        if self.brave_key:
            try:
                results = await self._brave_search(query, count)
                if results:
                    logger.info("Brave search succeeded - query: %s", query)
                    return results
                logger.warning("Brave returned no results, falling back to SerpAPI")
            except Exception as e:
                logger.warning("Brave search failed (%s), falling back to SerpAPI", e)

        if self.serp_key:
            try:
                results = await self._serp_search(query, count)
                logger.info("SerpAPI search succeeded - query: %s", query)
                return results
            except Exception as e:
                logger.error("SerpAPI also failed: %s", e)

        return []

    async def read_page(self, url: str) -> str:
        """Fetch a webpage and extract its main text content."""
        try:
            async with httpx.AsyncClient(
                timeout=PAGE_TIMEOUT,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; ClareBot/1.0)"},
            ) as client:
                response = await client.get(url)
                response.raise_for_status()

            text = self._extract_text(response.text)
            logger.info("Read page - url: %s, chars: %d", url, len(text))
            return text

        except httpx.TimeoutException:
            return f"[Timed out reading {url}]"
        except Exception as e:
            logger.error("Failed to read page %s: %s", url, e)
            return f"[Could not read page: {e}]"

    async def _brave_search(self, query: str, count: int) -> list[dict]:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                BRAVE_URL,
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": self.brave_key,
                },
                params={"q": query, "count": count},
            )
            response.raise_for_status()
            data = response.json()

        results = []
        for item in data.get("web", {}).get("results", []):
            results.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("description", ""),
                    "source": "brave",
                }
            )
        return results

    async def _serp_search(self, query: str, count: int) -> list[dict]:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                SERP_URL,
                params={
                    "q": query,
                    "api_key": self.serp_key,
                    "engine": "google",
                    "num": count,
                },
            )
            response.raise_for_status()
            data = response.json()

        results = []
        for item in data.get("organic_results", []):
            results.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                    "source": "serpapi",
                }
            )
        return results

    def _extract_text(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(
            ["script", "style", "nav", "footer", "header", "aside", "form", "iframe"]
        ):
            tag.decompose()

        main = (
            soup.find("main")
            or soup.find("article")
            or soup.find(id="content")
            or soup.find(class_="content")
            or soup.body
        )

        text = (main or soup).get_text(separator="\n", strip=True)
        lines = [line for line in text.splitlines() if line.strip()]
        cleaned = "\n".join(lines)

        return cleaned[:MAX_PAGE_CHARS]
