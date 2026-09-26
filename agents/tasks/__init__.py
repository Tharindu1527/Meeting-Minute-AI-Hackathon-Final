# agents/tasks/__init__.py
"""
Meeting Analysis Tasks Package

This package contains task definitions for the steps that produce meeting minutes.
"""

from agents.tasks.task_base import BaseTask
from agents.tasks.transcription import TranscriptionTask
from agents.tasks.analysis import AnalysisTask
from agents.tasks.summary import SummaryTask
from agents.tasks.sentiment import SentimentTask
from agents.tasks.action_items import ActionItemsTask
from agents.tasks.fact_checking import FactCheckingTask
from agents.tasks.research import ResearchTask
from agents.tasks.translation import TranslationTask
