# agents/__init__.py
"""
Meeting Analysis Agents Package

This package contains the agents, tasks, and registry for producing meeting minutes.
"""

# Import the registry for easy access
from agents.registry import (
    get_agent,
    list_agents,
    register_agent,
    set_default_model
)

# Import base classes
from agents.base import BaseAgent

# Import all definitions to ensure registration
from agents.definitions import *
