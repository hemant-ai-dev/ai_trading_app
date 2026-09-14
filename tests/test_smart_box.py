from prediction.models import PredictionResult
from ui.smart_box import build_smart_box


def _pred(**kwargs):
    base = dict(
        signal="HOLD",
        confidence=60,
        predicted_price=100,
        target_price=102,
        stop_loss=98,
        price_low=97,
        price_high=103,
        trend="neutral",
        risk_level="Medium",
        score=0.2,
        market_regime="sideways",
        indicator_snapshot={
            "support_resistance": {"support": [99.5], "resistance": [101.8]},
        },
    )
    base.update(kwargs)
    return PredictionResult(**base)


def test_hold_exposes_consider_levels():
    box = build_smart_box(_pred(signal="HOLD"), 100.2)
    assert box["signal"] == "HOLD"
    assert box["consider_buy"] == 99.5
    assert box["consider_sell"] == 101.8


def test_buy_exposes_entry_target_stop():
    box = build_smart_box(_pred(signal="BUY", target_price=105, stop_loss=97), 100)
    assert box["headline"] == "BUY"
    assert box["entry"] == 100
    assert box["target"] == 105
    assert box["stop"] == 97
    assert box["confidence"] == 60
    assert box["risk_level"] == "Medium"
