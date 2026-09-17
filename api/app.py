"""Angad internal FastAPI application (v1)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from api import gateway
from api.deps import current_api_user, require_admin
from api.rate_limit import LIMITER
from api.schemas import ChatRequest, LoginRequest, TaskCreateRequest
from auth.api_tokens import issue_token
from auth.users import authenticate
from db.bootstrap import initialize
from services.api_monitor import log_usage, set_provider_enabled


@asynccontextmanager
async def lifespan(_app: FastAPI):
    initialize()
    yield


app = FastAPI(
    title="Angad Internal Trading API",
    version="1.0.0",
    description=(
        "First-party API for the Angad desk. Market numbers come from free Yahoo/Stooq daily "
        "bars and local Python analysis. Educational use only — not financial advice."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://127.0.0.1",
        "http://localhost:8501",
        "http://127.0.0.1:8501",
        "http://localhost:8765",
        "http://127.0.0.1:8765",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse("/docs")


@app.get("/api/docs", include_in_schema=False)
def swagger_alias() -> RedirectResponse:
    return RedirectResponse("/docs")


@app.get("/api/redoc", include_in_schema=False)
def redoc_alias() -> RedirectResponse:
    return RedirectResponse("/redoc")


@app.get("/api/v1/health", tags=["system"])
def health() -> dict[str, Any]:
    initialize()
    return {"ok": True, "service": "angad-internal", "data_mode": "daily"}


@app.post("/api/v1/auth/login", tags=["auth"])
def login(body: LoginRequest, request: Request) -> dict[str, Any]:
    ip = request.client.host if request.client else "unknown"
    if not LIMITER.allow(f"login:{ip}"):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many login attempts.")
    user, err = authenticate(body.username, body.password)
    if err or user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=err or "Invalid credentials.")
    token, expires = issue_token(user.user_id, label="fastapi")
    log_usage("angad_internal", operation="auth_login", success=True, endpoint="/api/v1/auth/login")
    return {
        "ok": True,
        "access_token": token,
        "token_type": "bearer",
        "expires_at": expires.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "user": {"user_id": user.user_id, "username": user.username, "role": user.role},
    }


@app.get("/api/v1/market/quote/{symbol}", tags=["market"])
def quote(symbol: str, _user: dict = Depends(current_api_user)) -> dict[str, Any]:
    return gateway.get_quote(symbol)


@app.get("/api/v1/market/history/{symbol}", tags=["market"])
def history(
    symbol: str,
    period: str = Query(default="3mo", max_length=8),
    interval: str = Query(default="1d", max_length=8),
    _user: dict = Depends(current_api_user),
) -> dict[str, Any]:
    if interval != "1d":
        return {
            "ok": False,
            "error": "This deployment serves daily bars only (interval=1d).",
            "code": "validation",
        }
    return gateway.get_history(symbol, period, "1d")


@app.get("/api/v1/market/indicators/{symbol}", tags=["market"])
def indicators(symbol: str, _user: dict = Depends(current_api_user)) -> dict[str, Any]:
    return gateway.get_indicators(symbol)


@app.get("/api/v1/market/analysis/{symbol}", tags=["market"])
def analysis(symbol: str, user: dict = Depends(current_api_user)) -> dict[str, Any]:
    return gateway.get_analysis(symbol, user_id=int(user["UserId"]))


@app.get("/api/v1/predictions/{symbol}", tags=["predictions"])
def predictions(symbol: str, user: dict = Depends(current_api_user)) -> dict[str, Any]:
    return gateway.get_analysis(symbol, user_id=int(user["UserId"]))


@app.get("/api/v1/predictions/{symbol}/history", tags=["predictions"])
def prediction_history(symbol: str, user: dict = Depends(current_api_user)) -> dict[str, Any]:
    return gateway.get_prediction_history(symbol, int(user["UserId"]))


@app.get("/api/v1/news/{symbol}", tags=["news"])
def news(symbol: str, _user: dict = Depends(current_api_user)) -> dict[str, Any]:
    return gateway.get_news(symbol)


@app.get("/api/v1/knowledge/search", tags=["knowledge"])
def knowledge(q: str = Query(min_length=2, max_length=300), _user: dict = Depends(current_api_user)) -> dict[str, Any]:
    return gateway.knowledge_search(q)


@app.post("/api/v1/ai/chat", tags=["ai"])
def chat(body: ChatRequest, user: dict = Depends(current_api_user)) -> dict[str, Any]:
    from ai.chat_agent import answer

    return answer(
        user_id=int(user["UserId"]),
        text=body.message,
        symbol=body.symbol,
        conversation_id=body.conversation_id or "trading_chat",
    )


@app.get("/api/v1/tasks", tags=["workers"])
def list_tasks(user: dict = Depends(current_api_user)) -> dict[str, Any]:
    return gateway.list_worker_tasks(int(user["UserId"]))


@app.post("/api/v1/tasks", tags=["workers"])
def create_task(body: TaskCreateRequest, user: dict = Depends(current_api_user)) -> dict[str, Any]:
    return gateway.create_worker_task(
        user_id=int(user["UserId"]),
        request_text=body.request_text,
        symbol=body.symbol,
    )


@app.get("/api/v1/system/api-status", tags=["system"])
def api_status(_user: dict = Depends(current_api_user)) -> dict[str, Any]:
    return gateway.system_status()


@app.post("/api/v1/system/providers/{api_code}/enabled", tags=["system"])
def set_enabled(api_code: str, enabled: bool, _admin: dict = Depends(require_admin)) -> dict[str, Any]:
    set_provider_enabled(api_code, enabled)
    return {"ok": True, "api_code": api_code, "enabled": enabled}
