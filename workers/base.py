"""Worker contracts. Each worker has a real input/output — not a decorative badge."""

from __future__ import annotations

from typing import Any, Protocol


class Worker(Protocol):
    code: str
    label: str

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        """Return {ok, status, detail, updates?}."""
        ...
