import pytest


@pytest.fixture(autouse=True)
def _isolate_user_workbook(tmp_path, monkeypatch):
    monkeypatch.setenv("ANGAD_USERS_XLSX", str(tmp_path / "users.xlsx"))
