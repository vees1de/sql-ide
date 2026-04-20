from __future__ import annotations

from types import SimpleNamespace

import app.agents.validation as validation_module
from app.agents.validation import SQLValidationAgent


def _set_limit_settings(monkeypatch, default_row_limit: int = 50, max_row_limit: int = 1000) -> None:
    monkeypatch.setattr(
        validation_module,
        "settings",
        SimpleNamespace(default_row_limit=default_row_limit, max_row_limit=max_row_limit),
    )


def test_validation_adds_default_limit_when_missing(monkeypatch) -> None:
    _set_limit_settings(monkeypatch)
    agent = SQLValidationAgent()

    result = agent.run("SELECT * FROM customer", "postgresql")

    assert result.valid
    assert "LIMIT 50" in result.sql
    assert any("LIMIT 50 was added automatically." == warning for warning in result.warnings)


def test_validation_preserves_user_limit(monkeypatch) -> None:
    _set_limit_settings(monkeypatch)
    agent = SQLValidationAgent()

    result = agent.run("SELECT * FROM customer LIMIT 5", "postgresql")

    assert result.valid
    assert "LIMIT 5" in result.sql
    assert all("added automatically" not in warning for warning in result.warnings)


def test_validation_caps_limit_at_max(monkeypatch) -> None:
    _set_limit_settings(monkeypatch)
    agent = SQLValidationAgent()

    result = agent.run("SELECT * FROM customer LIMIT 5000", "postgresql")

    assert result.valid
    assert "LIMIT 1000" in result.sql
    assert any("LIMIT 5000 was reduced to 1000." == warning for warning in result.warnings)
