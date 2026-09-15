from tasks.parser import parse_intent, resolve_symbol
from db.bootstrap import initialize
from broker.paper import PaperBroker
from tasks import store
from workers.orchestrator import run_until_blocked
from prediction.archive import STRATEGY_VERSION


def test_resolve_and_parse_monitor_prepare():
    intent = parse_intent(
        "Monitor TATAMOTORS and prepare a buy order for 5 shares if the price falls below ₹640."
    )
    assert intent["symbol"] == "TATAMOTORS.NS"
    assert intent["action"] == "monitor_prepare"
    assert intent["quantity"] == 5
    assert intent["trigger"]["op"] == "below"
    assert intent["trigger"]["price"] == 640
    assert "monitor" in intent["plan"]
    assert "authorization" in intent["plan"]
    assert resolve_symbol("NIFTY") == "^NSEI"


def test_parse_notify():
    intent = parse_intent("Check TATAMOTORS price and notify me if it goes below ₹500.")
    assert intent["action"] == "notify"
    assert intent["trigger"]["price"] == 500


def test_paper_broker_and_task_queue(tmp_path, monkeypatch):
    monkeypatch.setenv("ANGAD_SQLITE_PATH", str(tmp_path / "trading_tool.db"))
    initialize()
    from auth.users import create_user

    rec, err = create_user("worker1", "w@example.com", "secret-pass1")
    assert err is None and rec is not None
    broker = PaperBroker()
    acct = broker.ensure_account(rec.user_id)
    assert float(acct["CashBalance"]) == 100000
    task = store.create_task(
        user_id=rec.user_id,
        request_text="Notify me if INFY goes below ₹1.",
        source="test",
        symbol="INFY.NS",
    )
    assert task["PublicId"].startswith("T")
    assert task["Status"] == "queued"
    rows = store.list_tasks(rec.user_id)
    assert len(rows) == 1
    assert STRATEGY_VERSION.startswith("angad")


def test_paper_reject_insufficient_cash(tmp_path, monkeypatch):
    monkeypatch.setenv("ANGAD_SQLITE_PATH", str(tmp_path / "trading_tool.db"))
    initialize()
    from auth.users import create_user

    rec, err = create_user("worker2", "w2@example.com", "secret-pass1")
    assert rec is not None
    out = PaperBroker().submit_order(
        user_id=rec.user_id,
        task_id=None,
        symbol="RELIANCE.NS",
        side="BUY",
        quantity=100000,
        limit_price=1000,
    )
    assert out["ok"] is False
    assert out["status"] == "rejected"
