"""Broker adapter. Paper by default. Live Kite is not enabled until configured."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
import uuid

from db.database import execute, fetch_one, get_connection


class BrokerAdapter(ABC):
    name = "abstract"

    @abstractmethod
    def is_configured(self) -> bool: ...

    @abstractmethod
    def submit_order(
        self,
        *,
        user_id: int,
        task_id: int | None,
        symbol: str,
        side: str,
        quantity: float,
        limit_price: float | None,
    ) -> dict[str, Any]: ...


class PaperBroker(BrokerAdapter):
    """Simulated fills against TPaperAccount. Never talks to a live exchange."""

    name = "paper"

    def is_configured(self) -> bool:
        return True

    def ensure_account(self, user_id: int, starting_cash: float = 100000.0) -> dict[str, Any]:
        row = fetch_one("SELECT * FROM TPaperAccount WHERE UserId = ?", (int(user_id),))
        if row:
            return dict(row)
        execute(
            "INSERT INTO TPaperAccount (UserId, CashBalance) VALUES (?, ?)",
            (int(user_id), float(starting_cash)),
        )
        return fetch_one("SELECT * FROM TPaperAccount WHERE UserId = ?", (int(user_id),)) or {}

    def submit_order(
        self,
        *,
        user_id: int,
        task_id: int | None,
        symbol: str,
        side: str,
        quantity: float,
        limit_price: float | None,
    ) -> dict[str, Any]:
        acct = self.ensure_account(user_id)
        px = float(limit_price or 0)
        qty = float(quantity)
        if qty <= 0 or px <= 0:
            return {"ok": False, "status": "rejected", "reason": "Quantity and price must be positive."}
        notional = qty * px
        cash = float(acct.get("CashBalance") or 0)
        side = side.upper()
        if side == "BUY" and notional > cash:
            return {
                "ok": False,
                "status": "rejected",
                "reason": f"Paper cash ₹{cash:,.2f} is below notional ₹{notional:,.2f}. Not a live broker check.",
            }
        new_cash = cash - notional if side == "BUY" else cash + notional
        public_id = "P" + uuid.uuid4().hex[:10].upper()
        with get_connection(commit=True) as cn:
            cn.execute(
                "UPDATE TPaperAccount SET CashBalance = ?, UpdatedAt = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE UserId = ?",
                (new_cash, int(user_id)),
            )
            cn.execute(
                """
                INSERT INTO TPaperOrder (PublicId, UserId, TaskId, Symbol, Side, Quantity, LimitPrice, Status, FilledPrice, Broker)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'filled', ?, 'paper')
                """,
                (public_id, int(user_id), task_id, symbol, side, qty, px, px),
            )
        return {
            "ok": True,
            "status": "filled",
            "broker": "paper",
            "order_id": public_id,
            "filled_price": px,
            "quantity": qty,
            "cash_after": new_cash,
            "note": "Paper fill only. No live order was sent to a broker.",
        }


class UnconfiguredLiveBroker(BrokerAdapter):
    name = "kite_unconfigured"

    def is_configured(self) -> bool:
        return False

    def submit_order(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "ok": False,
            "status": "blocked",
            "reason": "Live broker is not configured. Use paper execution only.",
        }


def get_broker() -> BrokerAdapter:
    return PaperBroker()
