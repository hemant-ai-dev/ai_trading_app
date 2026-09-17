from fastapi.testclient import TestClient

from api.app import app
from auth.users import create_user
from db.bootstrap import initialize
from knowledge.search import search_knowledge


def test_health_and_auth_quote(tmp_path, monkeypatch):
    monkeypatch.setenv("ANGAD_SQLITE_PATH", str(tmp_path / "trading_tool.db"))
    initialize()
    rec, err = create_user("apitester", "api@example.com", "secret-pass1")
    assert err is None and rec is not None
    client = TestClient(app)
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["data_mode"] == "daily"
    denied = client.get("/api/v1/market/quote/INFY.NS")
    assert denied.status_code == 401
    login = client.post("/api/v1/auth/login", json={"username": "apitester", "password": "secret-pass1"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    assert token.startswith("angad_")
    knowledge = client.get(
        "/api/v1/knowledge/search",
        params={"q": "paper trading workers"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert knowledge.status_code == 200
    assert knowledge.json()["ok"] is True
    assert search_knowledge("stop loss risk")


def test_chat_infer_symbol():
    from ai.chat_agent import infer_symbol

    assert infer_symbol("What is the current price of TATAMOTORS?", "INFY.NS") == "TATAMOTORS.NS"
    assert infer_symbol("Tell me about the nif50 stock", "TATAMOTORS.NS") == "^NSEI"
    assert infer_symbol("Nifty 50 outlook", None) == "^NSEI"
    assert infer_symbol("could you tell me about noifty50 last 5 days movement??", "^NSEI") == "^NSEI"
    assert infer_symbol("Tell me about the BHEL share details", "^NSEI") == "BHEL.NS"


def test_nlu_messy_questions():
    from ai.nlu import understand

    nif = understand("nfty ka rate", default_symbol="INFY.NS")
    assert nif.symbol == "^NSEI"
    assert "quote" in nif.intents
    tata = understand("tata motor kaisa hai")
    assert tata.symbol == "TATAMOTORS.NS"
    env = understand("enviroment news kya affect karega nif50")
    assert env.symbol == "^NSEI"
    assert "environment" in env.intents
    messy = understand("could you tell me about noifty50 last 5 days movement??")
    assert messy.symbol == "^NSEI"
    assert "history" in messy.intents or "analysis" in messy.intents
    follow = understand("price?", previous_symbol="RELIANCE.NS")
    assert follow.symbol == "RELIANCE.NS"
