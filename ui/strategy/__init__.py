"""Strategy UI model: desk layout + chart widgets."""

from ui.strategy.desk import render_strategy_workspace
from ui.strategy.widgets import (  # noqa: F401
    collect_indicator_flags,
    merge_auto_indicators,
    render_accuracy_section,
    render_agent_trace,
    render_ai_explanation_panel,
    render_ai_signal_hero,
    render_compare_card,
    render_confidence_meter,
    render_fibonacci_panel,
    render_indicator_snapshot,
    render_insight_charts,
    render_main_chart,
    render_market_overview,
    render_news_panel,
    render_performance_strip,
    render_prediction_history,
    render_recent_analysis,
    render_risk_meter,
    render_risk_plan_panel,
    render_scenarios_panel,
    render_sentiment_card,
    render_strategy_master_panel,
    render_today_panel,
    render_volume_analysis,
    render_what_to_do_now,
)

__all__ = ["render_strategy_workspace"]
