# api/wiki_api.py
import logging

import requests

logger = logging.getLogger(__name__)

# Wikipedia asks API clients to identify themselves
HEADERS = {"User-Agent": "MeetingMinutesAI/3.0 (meeting analysis app)"}
TIMEOUT = 10


def search_wikipedia(query, limit=3, language="en", extract_chars=1200):
    """
    Full-text search Wikipedia and return intro extracts of the best matches

    Args:
        query: Free-text search query (a topic or a claim)
        limit: Maximum number of articles to return
        language: Wikipedia language edition
        extract_chars: Maximum characters per extract

    Returns:
        list: [{"title", "extract", "url"}], empty if nothing was found or the request failed
    """
    url = f"https://{language}.wikipedia.org/w/api.php"
    try:
        search = requests.get(url, headers=HEADERS, timeout=TIMEOUT, params={
            "action": "query", "list": "search", "srsearch": query,
            "srlimit": limit, "format": "json",
        })
        search.raise_for_status()
        titles = [hit["title"] for hit in search.json().get("query", {}).get("search", [])]
        if not titles:
            return []

        pages = requests.get(url, headers=HEADERS, timeout=TIMEOUT, params={
            "action": "query", "prop": "extracts|info", "inprop": "url",
            "exintro": True, "explaintext": True, "redirects": 1,
            "titles": "|".join(titles), "format": "json",
        })
        pages.raise_for_status()
        by_title = {
            page.get("title"): page
            for page in pages.json().get("query", {}).get("pages", {}).values()
        }
    except (requests.RequestException, ValueError) as e:
        logger.warning("Wikipedia request failed: %s", e)
        return []

    results = []
    for title in titles:  # keep search relevance order
        page = by_title.get(title)
        if page and page.get("extract"):
            results.append({
                "title": title,
                "extract": page["extract"][:extract_chars],
                "url": page.get("fullurl", f"https://{language}.wikipedia.org/wiki/{title.replace(' ', '_')}"),
            })
    return results


def format_results(results):
    """Render search results as text for an LLM prompt"""
    if not results:
        return "No relevant Wikipedia articles were found."
    return "\n\n".join(f"{r['title']} ({r['url']}):\n{r['extract']}" for r in results)
