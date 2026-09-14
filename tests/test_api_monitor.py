from services.api_monitor import NOT_PROVIDED, derive_status


def test_not_provided_constant():
    assert NOT_PROVIDED == "Not provided by API"


def test_derive_status_inactive():
    assert derive_status({"IsEnabled": 0, "TodayUsage": 0}) == "inactive"


def test_derive_status_failed():
    assert derive_status({"IsEnabled": 1, "TodayFailure": 2, "TodaySuccess": 0}) == "failed"


def test_derive_status_active():
    assert derive_status({"IsEnabled": 1, "TodayUsage": 2, "TodaySuccess": 2, "LastSuccessUtc": "x"}) == "active"
