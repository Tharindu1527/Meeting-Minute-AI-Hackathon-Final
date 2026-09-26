# agents/definitions/__init__.py
"""
Meeting Analysis Agent Definitions Package

This package contains definitions for the specialized agents used to
produce meeting minutes.
"""

# Import all agent definitions to ensure registration
from agents.definitions.transcriber import TranscriberAgent
from agents.definitions.analyzer import AnalyzerAgent
from agents.definitions.summarizer import SummarizerAgent
from agents.definitions.sentiment import SentimentAgent
from agents.definitions.action_item import ActionItemAgent
from agents.definitions.fact_checker import FactCheckerAgent
from agents.definitions.researcher import ResearcherAgent
from agents.definitions.translator import TranslatorAgent
