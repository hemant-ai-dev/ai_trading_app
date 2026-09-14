"""
AI Trading Analyst package — Agentic multi-agent trading assistant.

Behaves like a desk of specialists coordinated by an orchestrator:
  Market Research → News → Technical → Patterns → Decision → Risk → Explain → Learn.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from analyst.pipeline import run_analyst_pipeline as run_analyst_pipeline

__all__ = ["run_analyst_pipeline"]


def __getattr__(name: str):
    if name == "run_analyst_pipeline":
        from analyst.pipeline import run_analyst_pipeline

        return run_analyst_pipeline
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
