"""Tool-using trading chat. Numbers come from internal APIs, not from the LLM."""

from __future__ import annotations

import json
import re
from typing import Any

from ai.nlu import last_chat_symbol, understand
from ai.registry import build_llm_provider
from ai.symbols import infer_symbol
from api import gateway
from config.loader import load_settings
from db.database import execute, fetch_all
from utils.logging import get_logger

logger = get_logger(__name__)

SYSTEM = """You are Angad, an educational trading assistant.
Use ONLY the JSON tool results provided. Never invent prices, indicators, news, or history.
Clearly label FACTS, ANALYSIS, FORECAST, and UNCERTAINTY.
If a tool failed or data is a fallback/delayed, say so.
Do not promise profits. Do not place live trades. Paper tasks are not broker orders.
Keep answers concise."""


def save_message(
    user_id: int,
    role: str,
    content: str,
    *,
    symbol: str | None = None,
    conversation_id: str = "desk",
    tools_json: str | None = None,
    citations_json: str | None = None,
) -> None:
    execute(
        """
        INSERT INTO TChatMessage (UserId, Role, Content, Symbol, ConversationId, ToolsJson, CitationsJson)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (int(user_id), role, content, symbol, conversation_id, tools_json, citations_json),
    )


def load_messages(user_id: int, *, conversation_id: str = "desk", limit: int = 40) -> list[dict[str, Any]]:
    rows = fetch_all(
        """
        SELECT * FROM TChatMessage
        WHERE UserId = ? AND IFNULL(ConversationId, 'desk') = ?
        ORDER BY MessageId DESC LIMIT ?
        """,
        (int(user_id), conversation_id, int(limit)),
    )
    return list(reversed(rows))


_ENV_WORDS = (
    "environment",
    "environmental",
    "climate",
    "esg",
    "carbon",
    "pollution",
    "sustainab",
    "green energy",
    "renewable",
    "weather",
)
_APP_ENV_WORDS = (
    "swagger",
    "excel",
    "users.xlsx",
    "internal api",
    "streamlit",
    "how does this app",
    "application environment",
    "where do you store",
    "password hash",
)


def _plain(text: str) -> str:
    cleaned = re.sub(r"[*_`#]+", "", text or "")
    return re.sub(r"\s+", " ", cleaned).strip()


def _is_env_question(q: str) -> bool:
    return any(w in q for w in _ENV_WORDS) or any(w in q for w in _APP_ENV_WORDS)


def _run_tools(question: str, symbol: str, user_id: int, intents: list[str] | None = None) -> list[dict[str, Any]]:
    q = question.lower()
    intents = intents or []
    about = any(w in q for w in ("tell me", "about", "outlook", "what is", "analyse", "analyze"))
    names: list[str] = []
    if _is_env_question(q) or "environment" in intents or "app" in intents:
        names.extend(["search_knowledge", "get_news"])
    if "quote" in intents or any(w in q for w in ("price", "quote", "ltp", "last trade", "current", "close", "rate")):
        names.append("get_quote")
    if any(w in q for w in ("indicator", "rsi", "macd", "ema", "atr", "fibonacci", "vwap")):
        names.append("get_indicators")
    if "news" in intents or any(w in q for w in ("news", "headline", "sentiment")):
        names.append("get_news")
    if "history" in intents or any(
        w in q for w in ("history", "previous prediction", "changed", "accuracy", "movement", "last 5", "last five", "days")
    ):
        names.append("get_bars")
        names.append("get_prediction_history")
    if (
        about
        or "analysis" in intents
        or "risk" in intents
        or any(w in q for w in ("analyze", "analysis", "outlook", "why", "hold", "buy", "sell", "risk", "target", "stop"))
    ):
        names.extend(["get_quote", "get_analysis"])
    if "app" in intents or any(w in q for w in ("knowledge", "how do you", "what does", "limit", "fallback", "paper")):
        names.append("search_knowledge")
    if "task" in intents or any(w in q for w in ("monitor", "notify me", "prepare a buy", "prepare a sell", "worker task")):
        names.append("create_paper_task")
    if not names:
        names = ["get_quote", "get_analysis", "get_news", "search_knowledge"]
    seen: list[str] = []
    for n in names:
        if n not in seen:
            seen.append(n)
    if "get_quote" not in seen and not _is_env_question(q):
        seen.insert(0, "get_quote")
    if "search_knowledge" not in seen:
        seen.append("search_knowledge")

    traces = []
    for name in seen[:6]:
        if name == "get_quote":
            traces.append({"tool": name, "result": gateway.get_quote(symbol)})
        elif name == "get_indicators":
            traces.append({"tool": name, "result": gateway.get_indicators(symbol)})
        elif name == "get_news":
            traces.append({"tool": name, "result": gateway.get_news(symbol)})
        elif name == "get_bars":
            traces.append({"tool": name, "result": gateway.get_history(symbol, "5d", "1d")})
        elif name == "get_prediction_history":
            traces.append({"tool": name, "result": gateway.get_prediction_history(symbol, user_id)})
        elif name == "get_analysis":
            traces.append({"tool": name, "result": gateway.get_analysis(symbol, user_id=user_id)})
        elif name == "search_knowledge":
            traces.append({"tool": name, "result": gateway.knowledge_search(question, limit=6)})
        elif name == "create_paper_task":
            traces.append(
                {
                    "tool": name,
                    "result": gateway.create_worker_task(
                        user_id=user_id, request_text=question, symbol=symbol
                    ),
                }
            )
    return traces


def _grounded_reply(question: str, symbol: str, traces: list[dict[str, Any]]) -> str:
    by = {t["tool"]: t["result"] for t in traces}
    parts: list[str] = []
    quote = by.get("get_quote") or {}
    analysis = by.get("get_analysis") or {}
    news = by.get("get_news") or {}
    hist = by.get("get_prediction_history") or {}
    bars = by.get("get_bars") or {}
    knowledge = by.get("search_knowledge") or {}
    task = by.get("create_paper_task") or {}
    q = question.lower()

    pretty = {
        "^NSEI": "Nifty 50",
        "^NSEBANK": "Bank Nifty",
        "^BSESN": "Sensex",
    }.get(symbol, symbol)
    parts.append(f"**Instrument:** {pretty} (`{symbol}`)")

    if quote.get("ok"):
        parts.append(
            f"**FACTS:** Last free daily close **₹{float(quote['price']):,.2f}** as of {quote.get('as_of')}. "
            f"Source `{quote.get('provider')}`. {quote.get('delay_note')}"
        )
        if quote.get("fallback_used"):
            parts.append(f"**UNCERTAINTY:** {quote.get('unavailable_note') or 'Fallback daily source in use.'}")
    elif quote:
        parts.append(f"**FACTS:** Daily quote not available for `{symbol}`. {quote.get('error')}")

    if analysis.get("ok"):
        pred = analysis.get("prediction") or {}
        expl = analysis.get("explanation") or {}
        px = analysis.get("latest_price")
        if px and not quote.get("ok"):
            parts.append(f"**FACTS:** Analysis engine last close ₹{float(px):,.2f}.")
        parts.append(
            f"**ANALYSIS:** Signal **{pred.get('signal')}** "
            f"({float(pred.get('confidence') or 0):.0f}% confidence), "
            f"regime `{pred.get('market_regime')}`. "
            f"{expl.get('suggested_action') or ''}"
        )
        reasons = pred.get("reasons_simple") or pred.get("reasons") or expl.get("reasons") or []
        if reasons:
            parts.append("Reasons: " + "; ".join(_plain(str(r)) for r in reasons[:4]))
        parts.append(
            f"**FORECAST:** Target ₹{float(pred.get('target_price') or 0):,.2f}, "
            f"stop ₹{float(pred.get('stop_loss') or 0):,.2f}, "
            f"model path ₹{float(pred.get('predicted_price') or 0):,.2f} "
            f"(range ₹{float(pred.get('price_low') or 0):,.2f}–₹{float(pred.get('price_high') or 0):,.2f}). "
            "Not a guaranteed next-day print."
        )
        if analysis.get("fallback_note"):
            parts.append(f"**UNCERTAINTY:** {analysis['fallback_note']}")
        parts.append(str(analysis.get("disclaimer") or ""))
    elif analysis:
        parts.append(f"**ANALYSIS:** {analysis.get('error')}")

    if news.get("ok"):
        titles = [n.get("title") for n in (news.get("equity") or [])[:3] if n.get("title")]
        world = [n.get("title") for n in (news.get("world") or [])[:3] if n.get("title")]
        if titles:
            parts.append("**NEWS (symbol):** " + " | ".join(titles))
        if world and _is_env_question(q):
            parts.append("**NEWS (world/environment context):** " + " | ".join(world))

    if bars.get("ok") and bars.get("bars"):
        series = bars["bars"]
        first = series[0]
        last = series[-1]
        try:
            a = float(first["close"])
            b = float(last["close"])
            chg = b - a
            pct = (chg / a * 100) if a else 0
            parts.append(
                f"**FACTS (last {len(series)} daily bars):** "
                f"{first.get('t')} ₹{a:,.2f} → {last.get('t')} ₹{b:,.2f} "
                f"({chg:+.2f}, {pct:+.2f}%). Daily closes only — not a live tape."
            )
        except (TypeError, ValueError, KeyError):
            pass

    if hist.get("ok") and hist.get("rows"):
        rows = hist["rows"]
        latest = rows[0]
        line = (
            f"**HISTORY:** Latest stored {latest.get('created_at')}: {latest.get('signal')} "
            f"predicted ₹{latest.get('predicted_price')} vs market ₹{latest.get('market_price')}."
        )
        if len(rows) > 1:
            prev = rows[1]
            line += (
                f" Previous {prev.get('created_at')}: {prev.get('signal')} "
                f"₹{prev.get('predicted_price')}."
            )
        parts.append(line)

    if task.get("ok"):
        parts.append(
            f"**TASK:** Created `{task.get('public_id')}` ({task.get('status')}). {task.get('note')}"
        )

    hits = knowledge.get("hits") or []
    if hits:
        env_hits = [h for h in hits if str(h.get("source") or "") in ("environment_esg", "app_environment")]
        pick = env_hits[:2] + [h for h in hits if h not in env_hits][:2] if _is_env_question(q) else hits[:2]
        for h in pick[:2]:
            parts.append(f"**KNOWLEDGE ({h.get('title')}):** {_plain(h.get('excerpt') or '')[:420]}")

    if _is_env_question(q) and not hits:
        parts.append(
            "**ENVIRONMENT:** I use the local ESG/climate knowledge file plus free RSS headlines. "
            "I do not invent carbon scores."
        )
    if not parts:
        return "I could not retrieve tools for that question. Try “Nifty 50 outlook” or TATAMOTORS.NS."
    return "\n\n".join(p for p in parts if p)


def _llm_polish(question: str, symbol: str, traces: list[dict[str, Any]], draft: str) -> str:
    settings = load_settings()
    llm = build_llm_provider(settings)
    if llm.__class__.__name__ == "NullLLM":
        return draft
    compact = json.dumps(traces, default=str)[:8000]
    try:
        text = llm.chat_text(
            system=SYSTEM,
            user=f"Question: {question}\nSymbol: {symbol}\nTool JSON:\n{compact}\n\nDraft to refine (keep all numbers unchanged):\n{draft}",
            max_tokens=500,
            temperature=0.2,
        )
        return text.strip() if text else draft
    except Exception:
        logger.exception("LLM polish failed")
        return draft


def answer(
    *,
    user_id: int,
    text: str,
    symbol: str | None = None,
    conversation_id: str = "desk",
) -> dict[str, Any]:
    q = (text or "").strip()
    if not q:
        return {"ok": False, "error": "Message is empty."}
    prev = last_chat_symbol(load_messages(int(user_id), conversation_id=conversation_id, limit=20))
    mind = understand(q, default_symbol=symbol, previous_symbol=prev)
    ticker = mind.symbol
    traces = _run_tools(mind.cleaned or q, ticker, int(user_id), mind.intents)
    body = _grounded_reply(mind.cleaned or q, ticker, traces)
    draft = f"_{mind.restated}_\n\n{body}"
    reply = _llm_polish(mind.cleaned or q, ticker, traces, draft)
    citations = []
    for t in traces:
        if t["tool"] == "search_knowledge":
            citations.extend((t["result"] or {}).get("hits") or [])
    tools_json = json.dumps([{"tool": t["tool"], "ok": bool((t["result"] or {}).get("ok", True))} for t in traces])
    cit_json = json.dumps(citations, default=str) if citations else None
    save_message(int(user_id), "user", q, symbol=ticker, conversation_id=conversation_id)
    save_message(
        int(user_id),
        "assistant",
        reply,
        symbol=ticker,
        conversation_id=conversation_id,
        tools_json=tools_json,
        citations_json=cit_json,
    )
    return {
        "ok": True,
        "symbol": ticker,
        "reply": reply,
        "tools": traces,
        "citations": citations,
        "understood": mind.restated,
        "cleaned": mind.cleaned,
        "used_llm": build_llm_provider(load_settings()).__class__.__name__ != "NullLLM",
    }
