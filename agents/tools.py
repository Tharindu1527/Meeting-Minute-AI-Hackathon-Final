# agents/tools.py
"""Tools agents can call during a crew run"""
from crewai.tools import tool

from api.wiki_api import format_results, search_wikipedia


@tool("Wikipedia search")
def wikipedia_search(query: str) -> str:
    """Search Wikipedia for background on a topic or to check a factual claim.
    Input: a short search query such as a topic, organisation, person or claim.
    Returns extracts of the best-matching articles, each with its URL."""
    return format_results(search_wikipedia(query))
