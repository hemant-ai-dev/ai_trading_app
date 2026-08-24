"""
AI Trading Analyst package — Agentic multi-agent trading assistant.

Behaves like a desk of specialists coordinated by an orchestrator:
  Market Research → News → Technical → Patterns → Decision → Risk → Explain → Learn.
"""

from analyst.pipeline import run_analyst_pipeline

__all__ = ["run_analyst_pipeline"]
