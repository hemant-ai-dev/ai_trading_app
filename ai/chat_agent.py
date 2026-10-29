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


def _run_tools(question: str, symbol: str, user_id: int, mind) -> list[dict[str, Any]]:
    q = question.lower()
    intents = list(getattr(mind, "intents", None) or [])
    about = any(w in q for w in ("tell me", "about", "outlook", "what is", "analyse", "analyze"))
    names: list[str] = []
    if "option" in intents or any(w in q for w in ("option", "chain", "expiry", "strike", "premium", "atm")):
        names.append("get_option_chain")
    if _is_env_question(q) or "environment" in intents or "app" in intents:
        names.extend(["search_knowledge", "get_news"])
    if "quote" in intents or any(w in q for w in ("price", "quote", "ltp", "last trade", "current", "close", "rate", "open", "high", "low", "volume", "data")):
        names.append("get_quote")
        if any(w in q for w in ("today", "data", "ohlc")):
            names.extend(["get_indicators", "get_analysis"])
    if any(w in q for w in ("indicator", "rsi", "macd", "ema", "atr", "fibonacci", "vwap")) or "chart" in intents:
        names.append("get_indicators")
    if "chart" in intents:
        names.append("get_bars")
    if "news" in intents or any(w in q for w in ("news", "headline", "sentiment")):
        names.append("get_news")
    if "history" in intents or any(
        w in q for w in ("history", "previous prediction", "changed", "accuracy", "movement", "last 5", "last five", "days")
    ):
        names.append("get_bars")
        names.append("get_prediction_history")
    if "performance" in intents:
        names.append("get_prediction_history")
    if any(w in q for w in ("performance", "accuracy", "how well", "how often", "hit rate", "mae", "error rate")):
        names.append("get_prediction_performance")
    if any(
        w in q
        for w in (
            "why did",
            "why is",
            "why the",
            "stop loss",
            "invalidat",
            "last ten",
            "last 10",
            "previous prediction",
            "last prediction",
            "wrong",
            "missed",
            "failed prediction",
            "selected this",
            "bullish",
        )
    ):
        names.extend(["get_prediction_history", "get_prediction_performance", "get_prediction_explain"])
    if any(w in q for w in ("which stock", "which stocks", "setup", "screener", "screen for", "best stock", "candidates", "watchlist scan")):
        names.append("get_screener")
    if any(w in q for w in ("which strategy", "best strategy", "strategy performed", "strategy regime", "strategy registry", "performed best")):
        names.append("get_strategy_registry")
    if "compare" in intents or any(w in q for w in ("compare", " versus ", " vs ")):
        names.append("get_compare")
    if (
        about
        or "analysis" in intents
        or "risk" in intents
        or any(w in q for w in ("analyze", "analysis", "outlook", "why", "hold", "buy", "sell", "risk", "target", "trend"))
    ) and "get_option_chain" not in names:
        names.extend(["get_quote", "get_analysis"])
    if "get_option_chain" in names and any(w in q for w in ("analyze", "prediction", "recommend", "entry", "target")):
        names.append("get_analysis")
    if "app" in intents or any(w in q for w in ("knowledge", "how do you", "what does", "limit", "fallback", "paper")):
        names.append("search_knowledge")
    if "task" in intents or any(w in q for w in ("monitor", "notify me", "prepare a buy", "prepare a sell", "worker task")):
        names.append("create_paper_task")
    if not names:
        names = ["get_quote", "get_analysis", "search_knowledge"]
    seen: list[str] = []
    for n in names:
        if n not in seen:
            seen.append(n)
    if (
        "get_quote" not in seen
        and not _is_env_question(q)
        and "get_option_chain" not in seen
        and "get_compare" not in seen
    ):
        seen.insert(0, "get_quote")
    if "search_knowledge" not in seen:
        seen.append("search_knowledge")

    traces = []
    for name in seen[:9]:
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
        elif name == "get_prediction_performance":
            traces.append({"tool": name, "result": gateway.get_prediction_performance(symbol, user_id)})
        elif name == "get_prediction_explain":
            traces.append({"tool": name, "result": gateway.get_prediction_explain(symbol, user_id)})
        elif name == "get_screener":
            traces.append({"tool": name, "result": gateway.get_screener()})
        elif name == "get_strategy_registry":
            traces.append({"tool": name, "result": gateway.get_strategy_registry()})
        elif name == "get_analysis":
            traces.append({"tool": name, "result": gateway.get_analysis(symbol, user_id=user_id)})
        elif name == "get_compare":
            other = getattr(mind, "compare_symbol", None)
            if other:
                traces.append(
                    {
                        "tool": name,
                        "result": gateway.get_compare(symbol, other, user_id=user_id),
                    }
                )
        elif name == "get_option_chain":
            traces.append(
                {
                    "tool": name,
                    "result": gateway.get_option_chain(
                        symbol,
                        nearest=bool(getattr(mind, "nearest_expiry", False)),
                        right=getattr(mind, "option_right", None),
                        strike=getattr(mind, "strike", None),
                        view=getattr(mind, "chain_view", "all") or "all",
                        user_id=user_id,
                        include_rec="analysis" in intents or "prediction" in q,
                    ),
                }
            )
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
    explain = by.get("get_prediction_explain") or {}
    perf = by.get("get_prediction_performance") or {}
    screener = by.get("get_screener") or {}
    registry = by.get("get_strategy_registry") or {}
    compare = by.get("get_compare") or {}
    vision = by.get("analyze_image") or {}
    bars = by.get("get_bars") or {}
    knowledge = by.get("search_knowledge") or {}
    task = by.get("create_paper_task") or {}
    chain = by.get("get_option_chain") or {}
    indicators = by.get("get_indicators") or {}
    q = question.lower()

    pretty = {
        "^NSEI": "Nifty 50",
        "^NSEBANK": "Bank Nifty",
        "^BSESN": "Sensex",
    }.get(symbol, symbol)
    parts.append(f"**Instrument:** {pretty} (`{symbol}`)")

    if quote.get("ok"):
        ohlc = []
        if quote.get("open") is not None:
            ohlc.append(f"open ₹{float(quote['open']):,.2f}")
        if quote.get("high") is not None:
            ohlc.append(f"high ₹{float(quote['high']):,.2f}")
        if quote.get("low") is not None:
            ohlc.append(f"low ₹{float(quote['low']):,.2f}")
        prev = quote.get("previous_close")
        prev_txt = f" previous close ₹{float(prev):,.2f}" if prev is not None else ""
        vol = quote.get("volume")
        vol_txt = f" volume {float(vol):,.0f}" if vol is not None else ""
        parts.append(
            f"**FACTS:** Last **₹{float(quote['price']):,.2f}** as of {quote.get('as_of')}"
            + (f" ({', '.join(ohlc)})" if ohlc else "")
            + prev_txt
            + vol_txt
            + f". Source `{quote.get('provider')}`. {quote.get('delay_note')}"
        )
        if quote.get("fallback_used"):
            parts.append(f"**UNCERTAINTY:** {quote.get('unavailable_note') or 'Fallback daily source in use.'}")
    elif quote:
        parts.append(f"**FACTS:** Daily quote not available for `{symbol}`. {quote.get('error')}")

    if vision:
        if vision.get("ok") and vision.get("text"):
            parts.append(f"**IMAGE ({vision.get('source')}):** {vision.get('text')}")
            if vision.get("note"):
                parts.append(f"**IMAGE NOTE:** {vision['note']}")
        elif vision.get("error"):
            parts.append(f"**IMAGE:** {vision.get('error')}")

    if compare.get("ok") or compare.get("a") or compare.get("b"):
        def _sig(blob):
            prim = (blob or {}).get("prediction") or {}
            if isinstance(prim, dict) and prim:
                return f"{prim.get('signal')} {prim.get('confidence')}%"
            return (blob or {}).get("error") or "unavailable"
        parts.append(
            "**COMPARE (desk analyses, not P&L):** "
            f"A `{((compare.get('a') or {}).get('symbol'))}` {_sig(compare.get('a'))} · "
            f"B `{((compare.get('b') or {}).get('symbol'))}` {_sig(compare.get('b'))}."
        )
        parts.append(str(compare.get("disclaimer") or ""))

    if indicators.get("ok"):
        snap = indicators.get("indicators") or {}
        bits = []
        for key in ("rsi", "macd", "atr", "vwap", "trend_dir"):
            if snap.get(key) is not None:
                bits.append(f"{key} {snap.get(key)}")
        if bits:
            parts.append("**INDICATORS:** " + "; ".join(bits[:6]))

    if chain:
        if chain.get("ok"):
            meta = chain.get("meta") or {}
            parts.append(
                f"**OPTION CHAIN:** {pretty} expiry {chain.get('expiry')} ({meta.get('expiry_day')}, "
                f"{meta.get('days_remaining')} days, {meta.get('status')}). Spot ₹{chain.get('spot')}. "
                f"Source `{chain.get('source')}`. Tables are attached below."
            )
            rec = chain.get("recommendation") or {}
            if rec:
                parts.append(
                    f"**OPTION AI (recommendation, not a prediction guarantee):** {rec.get('action')} · "
                    f"bias {rec.get('bias')} · confidence {rec.get('confidence')}%. "
                    f"{rec.get('wait_text') or ''}"
                )
            hit = chain.get("contract")
            if hit:
                parts.append(
                    f"**CONTRACT:** strike {hit.get('strike')} {hit.get('right')} LTP ₹{hit.get('ltp')} "
                    f"OI {hit.get('open_interest')} ΔOI {hit.get('oi_change')} IV {hit.get('iv')} vol {hit.get('volume')}"
                )
        else:
            parts.append(f"**OPTION CHAIN:** {chain.get('error') or chain.get('note')}")

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
            f"**HISTORY:** Latest stored {latest.get('created_at')} "
            f"({latest.get('horizon') or 'n/a'}, {latest.get('status') or 'n/a'}): {latest.get('signal')} "
            f"predicted ₹{latest.get('predicted_price')} vs market ₹{latest.get('market_price')}."
        )
        if latest.get("actual_price") is not None:
            line += (
                f" Actual at target ₹{latest.get('actual_price')}"
                + (
                    f", error {float(latest.get('error_pct') or 0):.2f}%"
                    if latest.get("error_pct") is not None
                    else ""
                )
                + (
                    f" — direction {'hit' if latest.get('direction_ok') else 'miss'}."
                    if latest.get("direction_ok") is not None
                    else "."
                )
            )
        elif (latest.get("status") or "").lower() == "pending":
            line += f" Target {latest.get('target_time')} not reached yet — pending, not marked wrong."
        if len(rows) > 1:
            prev = rows[1]
            line += (
                f" Previous {prev.get('created_at')}: {prev.get('signal')} "
                f"₹{prev.get('predicted_price')}."
            )
        parts.append(line)

    if explain.get("ok") and explain.get("rows"):
        latest_ex = explain["rows"][0]
        facts = latest_ex.get("facts_at_prediction") or {}
        forecast = latest_ex.get("model_forecast") or {}
        outcome = latest_ex.get("outcome") or {}
        inds = facts.get("indicators") or {}
        parts.append(
            "**WHY (from stored snapshot, not hindsight):** "
            f"At {latest_ex.get('created_at')} the tape showed ₹{facts.get('market_price')} "
            f"in regime `{facts.get('regime')}` with RSI {inds.get('rsi')}, ATR {inds.get('atr')}, "
            f"trend {inds.get('trend')}. "
            f"**FORECAST then:** {forecast.get('signal')} toward ₹{forecast.get('predicted_price')} "
            f"via strategy `{forecast.get('strategy_id')}` / {forecast.get('model_version')}. "
            f"Reasons: {'; '.join(str(x) for x in (forecast.get('reasons') or [])[:4])}."
        )
        if outcome.get("pending"):
            parts.append("**OUTCOME:** Still pending — the actual print is not known yet.")
        else:
            parts.append(
                f"**OUTCOME (evaluated later):** actual ₹{outcome.get('actual_price')} · "
                f"direction {'ok' if outcome.get('direction_ok') else 'miss'} · "
                f"abs error {outcome.get('abs_error')}. This was not used to rewrite the original reasons."
            )
        if len(explain["rows"]) > 1:
            bits = []
            for row in explain["rows"][:10]:
                oc = row.get("outcome") or {}
                fc = row.get("model_forecast") or {}
                bits.append(
                    f"{row.get('created_at')}: {fc.get('signal')} pred ₹{fc.get('predicted_price')} "
                    f"actual {oc.get('actual_price') if not oc.get('pending') else 'pending'}"
                )
            parts.append("**LAST STORED PREDICTIONS:** " + " | ".join(bits))

    if perf.get("ok"):
        s = perf.get("stats") or {}
        ev = int(s.get("evaluated") or 0)
        line = (
            f"**PREDICTION PERFORMANCE (stored results only):** {int(s.get('total_predictions') or 0)} saved · "
            f"{ev} evaluated · {int(s.get('pending') or 0)} pending."
        )
        if s.get("direction_accuracy_pct") is not None:
            line += (
                f" Direction accuracy {s.get('direction_accuracy_pct')}% over {int(s.get('direction_total') or 0)} scored"
            )
            if s.get("mean_abs_error") is not None:
                line += f"; MAE ₹{s.get('mean_abs_error')}"
            if s.get("mean_abs_pct_error") is not None:
                line += f", MAPE {s.get('mean_abs_pct_error')}%"
            if s.get("range_pct") is not None:
                line += f"; range hit {s.get('range_pct')}%"
            line += "."
        elif ev:
            line += (
                f" {ev} evaluated rows predate direction scoring, so no accuracy figure is shown "
                "rather than inventing one."
            )
        else:
            line += " No evaluated predictions yet — no accuracy claim can be made."
        parts.append(line)
        parts.append(str(perf.get("disclaimer") or ""))
    elif perf:
        parts.append(f"**PREDICTION PERFORMANCE:** {perf.get('error')}")

    if screener.get("ok"):
        srows = screener.get("rows") or []
        if srows:
            tops = "; ".join(
                f"{r.get('symbol')} ({r.get('signal')}, conf {r.get('confidence')})"
                for r in srows[:5]
                if isinstance(r, dict)
            )
            parts.append(f"**SCREENER:** {len(srows)} scanned — top setups: {tops}.")
        else:
            parts.append("**SCREENER:** Universe scan returned no rows right now.")
        parts.append(str(screener.get("disclaimer") or ""))
    elif screener:
        parts.append(f"**SCREENER:** {screener.get('error')}")

    if registry.get("ok"):
        rrows = registry.get("rows") or []
        validated = [r for r in rrows if int(r.get("Completed") or 0) >= 20]
        if validated:
            best = max(validated, key=lambda r: (r.get("DirectionHits") or 0) / max(int(r.get("DirectionTotal") or 1), 1))
            acc = 100.0 * int(best.get("DirectionHits") or 0) / max(int(best.get("DirectionTotal") or 1), 1)
            parts.append(
                f"**STRATEGY REGISTRY:** Best validated: {best.get('StrategyId')} in "
                f"`{best.get('MarketRegime')}` / {best.get('Timeframe')} — {acc:.1f}% direction accuracy "
                f"over {int(best.get('DirectionTotal') or 0)} completed setups."
            )
        else:
            parts.append(
                f"**STRATEGY REGISTRY:** {len(rrows)} tracked buckets, none with ≥20 completed setups yet — "
                "regime defaults are in use; no strategy is 'best' based on one prediction."
            )
        parts.append(str(registry.get("disclaimer") or ""))
    elif registry:
        parts.append(f"**STRATEGY REGISTRY:** {registry.get('error')}")

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
    image_bytes: bytes | None = None,
    image_name: str | None = None,
    image_mime: str | None = None,
) -> dict[str, Any]:
    q = (text or "").strip()
    if not q and not image_bytes:
        return {"ok": False, "error": "Message is empty."}
    if not q and image_bytes:
        q = "Analyse this image. Separate what is visible from inference. Do not invent unread numbers."
    prev = last_chat_symbol(load_messages(int(user_id), conversation_id=conversation_id, limit=20))
    mind = understand(q, default_symbol=symbol, previous_symbol=prev)
    ticker = mind.symbol
    traces = _run_tools(mind.cleaned or q, ticker, int(user_id), mind)
    user_ui: dict[str, Any] = {}
    if image_bytes:
        try:
            from ai.media import MediaError, load_image, thumbnail_data_url
            from ai.vision import compact_live_context, describe_image

            img, meta = load_image(image_bytes, name=image_name, mime=image_mime)
            vis = describe_image(img, question=q, live_context=compact_live_context(traces))
            traces.append({"tool": "analyze_image", "result": vis})
            user_ui["image"] = {"thumb": thumbnail_data_url(img), "meta": meta}
        except Exception as exc:
            from ai.media import MediaError

            msg = str(exc) if isinstance(exc, MediaError) else "Could not read that attachment."
            traces.append({"tool": "analyze_image", "result": {"ok": False, "error": msg}})
    body = _grounded_reply(mind.cleaned or q, ticker, traces)
    draft = f"_{mind.restated}_\n\n{body}"
    reply = _llm_polish(mind.cleaned or q, ticker, traces, draft)
    citations = []
    for t in traces:
        if t["tool"] == "search_knowledge":
            citations.extend((t["result"] or {}).get("hits") or [])
    ui = dict(user_ui)
    for t in traces:
        if t["tool"] == "get_option_chain":
            ui["option_chain"] = t["result"]
        if t["tool"] == "get_bars":
            ui["bars"] = (t["result"] or {}).get("bars")
        if t["tool"] == "get_quote":
            ui["quote"] = t["result"]
        if t["tool"] == "analyze_image":
            ui["vision"] = {"source": (t.get("result") or {}).get("source")}
    tools_json = json.dumps(
        {
            "tools": [{"tool": t["tool"], "ok": bool((t["result"] or {}).get("ok", True))} for t in traces],
            "ui": ui,
        },
        default=str,
    )
    cit_json = json.dumps(citations, default=str) if citations else None
    user_text = q
    if image_name:
        user_text = f"{q}\n\n_(attached {image_name})_"
    save_message(
        int(user_id),
        "user",
        user_text,
        symbol=ticker,
        conversation_id=conversation_id,
        tools_json=json.dumps({"ui": user_ui}, default=str) if user_ui else None,
    )
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
